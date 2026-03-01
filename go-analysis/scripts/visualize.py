# -*- coding: utf-8 -*-
"""
ActProof: Visualize CC Curve from Go Analysis
==============================================
Generates CC(t) curve plots with annotated state transitions
and flashover detection points.

Usage:
    python visualize.py --input cc_output.json --output figures/
    python visualize.py --low analysis_200.jsonl --high analysis_2000.jsonl --sgf game.sgf --output figures/
"""

import json
import argparse
import sys
from pathlib import Path

try:
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

try:
    from compute_cc import parse_sgf_moves, load_analysis, compute_cc_series
    from detect_flashover import detect_flashover
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent))
    from compute_cc import parse_sgf_moves, load_analysis, compute_cc_series
    from detect_flashover import detect_flashover


def plot_cc_curve(cc_series, flashover_results, output_path, title="ActProof CC(t) — Control Cost Curve"):
    """Generate CC curve plot with flashover annotations."""
    if not HAS_MATPLOTLIB:
        print("matplotlib not installed. Install with: pip install matplotlib", file=sys.stderr)
        return

    turns = [e["t"] for e in cc_series if e is not None]
    cc_values = [e["cc"] for e in cc_series if e is not None]

    # Build flashover lookup
    flashover_map = {r["t"]: r for r in flashover_results}

    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(16, 12), sharex=True,
                                         gridspec_kw={"height_ratios": [3, 1, 1]})

    # --- Panel 1: CC Curve ---
    ax1.plot(turns, cc_values, 'b-', linewidth=1.0, alpha=0.7, label='CC(t)')

    # Smoothed CC (rolling average)
    window = 5
    if len(cc_values) > window:
        smoothed = []
        for i in range(len(cc_values)):
            start = max(0, i - window + 1)
            smoothed.append(sum(cc_values[start:i + 1]) / (i - start + 1))
        ax1.plot(turns, smoothed, 'b-', linewidth=2.5, alpha=0.9, label=f'CC(t) smoothed (w={window})')

    # Annotate flashover points
    for t in turns:
        if t in flashover_map:
            r = flashover_map[t]
            if r["status"] == "CONFIRMED":
                ax1.axvline(x=t, color='red', linestyle='--', alpha=0.8, linewidth=1.5)
                ax1.annotate(f't={t}\n{r["move"]}\nCONFIRMED',
                           xy=(t, cc_values[turns.index(t)]),
                           fontsize=8, color='red', fontweight='bold',
                           xytext=(10, 20), textcoords='offset points',
                           arrowprops=dict(arrowstyle='->', color='red'))
            elif r["status"] == "STRONG":
                ax1.axvline(x=t, color='orange', linestyle=':', alpha=0.6)

    # Move 37 marker
    if 37 in turns:
        idx_37 = turns.index(37)
        ax1.axvline(x=37, color='green', linestyle='-.', alpha=0.5, linewidth=1)
        ax1.annotate('Move 37\n(R15)',
                     xy=(37, cc_values[idx_37]),
                     fontsize=8, color='green',
                     xytext=(-40, 30), textcoords='offset points',
                     arrowprops=dict(arrowstyle='->', color='green'))

    ax1.set_ylabel('Control Cost CC(t)')
    ax1.set_title(title)
    ax1.legend(loc='upper left')
    ax1.grid(True, alpha=0.3)

    # --- Panel 2: Level Gap ---
    level_gaps = [e.get("level_gap", 0) for e in cc_series if e is not None]
    ax2.bar(turns, level_gaps, color='purple', alpha=0.6, width=1.0)
    ax2.set_ylabel('Level Gap')
    ax2.axhline(y=0.05, color='red', linestyle='--', alpha=0.5, label='threshold')
    ax2.grid(True, alpha=0.3)

    # --- Panel 3: Top Move Switch ---
    switches = [1 if (e is not None and e.get("top_switch")) else 0 for e in cc_series if e is not None]
    colors = ['red' if s else 'lightgray' for s in switches]
    ax3.bar(turns, switches, color=colors, width=1.0)
    ax3.set_ylabel('Top-Move\nSwitch')
    ax3.set_xlabel('Move Number')
    ax3.set_yticks([0, 1])
    ax3.set_yticklabels(['No', 'Yes'])
    ax3.grid(True, alpha=0.3)

    plt.tight_layout()

    output_file = Path(output_path) / "cc_curve.png"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print(f"Saved: {output_file}", file=sys.stderr)
    plt.close()


def plot_flashover_ranking(flashover_results, output_path):
    """Generate ranking visualization of flashover candidates."""
    if not HAS_MATPLOTLIB:
        return

    # Top 15 by score
    ranked = sorted(flashover_results, key=lambda x: x["score"], reverse=True)[:15]

    fig, ax = plt.subplots(figsize=(12, 6))

    colors = []
    for r in ranked:
        if r["status"] == "CONFIRMED":
            colors.append('#d32f2f')
        elif r["status"] == "STRONG":
            colors.append('#ff9800')
        elif r["status"] == "candidate":
            colors.append('#2196f3')
        else:
            colors.append('#9e9e9e')

    labels = [f"t={r['t']} {r['move']}" for r in ranked]
    scores = [r["score"] for r in ranked]

    bars = ax.barh(range(len(ranked)), scores, color=colors, edgecolor='white', linewidth=0.5)
    ax.set_yticks(range(len(ranked)))
    ax.set_yticklabels(labels, fontsize=9)
    ax.set_xlabel('Flashover Score')
    ax.set_title('ActProof Flashover Ranking — Top 15 Candidates')
    ax.invert_yaxis()

    # Legend
    patches = [
        mpatches.Patch(color='#d32f2f', label='CONFIRMED'),
        mpatches.Patch(color='#ff9800', label='STRONG'),
        mpatches.Patch(color='#2196f3', label='candidate'),
    ]
    ax.legend(handles=patches, loc='lower right')

    plt.tight_layout()
    output_file = Path(output_path) / "flashover_ranking.png"
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print(f"Saved: {output_file}", file=sys.stderr)
    plt.close()


def main():
    parser = argparse.ArgumentParser(description="ActProof CC Curve Visualization")
    parser.add_argument("--input", help="Pre-computed CC JSON file")
    parser.add_argument("--low", help="Low-budget analysis JSONL")
    parser.add_argument("--high", help="High-budget analysis JSONL")
    parser.add_argument("--sgf", help="SGF game file")
    parser.add_argument("--output", default="figures", help="Output directory for figures")
    parser.add_argument("--title", default=None, help="Plot title")
    args = parser.parse_args()

    if args.input:
        with open(args.input, 'r') as f:
            data = json.load(f)
        cc_series = data["cc_series"]
    elif args.low and args.high and args.sgf:
        with open(args.sgf, 'r') as f:
            sgf_content = f.read()
        moves = parse_sgf_moves(sgf_content)
        analysis_low = load_analysis(args.low)
        analysis_high = load_analysis(args.high)
        cc_series = compute_cc_series(moves, analysis_low, analysis_high)
        cc_series = [x for x in cc_series if x is not None]
    else:
        print("Error: provide either --input or (--low, --high, --sgf)", file=sys.stderr)
        sys.exit(1)

    flashover_results = detect_flashover(cc_series)

    title = args.title or "ActProof CC(t) — AlphaGo vs Lee Sedol Game 2"
    plot_cc_curve(cc_series, flashover_results, args.output, title)
    plot_flashover_ranking(flashover_results, args.output)


if __name__ == "__main__":
    main()
