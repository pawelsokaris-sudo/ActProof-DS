# -*- coding: utf-8 -*-
"""
ActProof: Flashover Detection from CC Series
=============================================
Applies the ActProof state machine to a CC(t) curve and identifies
flashover candidates — positions where the description boundary
shifts between low and high analysis budgets.

Uses the M37 Bridge criteria from the empirical Go analysis:
  - Level switch (top move changes between budgets)
  - Rank delta >= 3
  - Level gap > threshold
  - Stability delta > threshold
  - Entropy drop (policy becomes more concentrated at high budget)

Usage:
    python detect_flashover.py --input cc_output.json
    python detect_flashover.py --low analysis_200.jsonl --high analysis_2000.jsonl --sgf game.sgf
"""

import json
import argparse
import sys
from pathlib import Path

# Import compute_cc if running standalone
try:
    from compute_cc import parse_sgf_moves, load_analysis, compute_cc_series
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent))
    from compute_cc import parse_sgf_moves, load_analysis, compute_cc_series


def detect_flashover(cc_series, thresholds=None):
    """
    Apply flashover detection criteria to CC series.

    M37 Bridge Metrics (from empirical validation):
      LCE: Level Change Evidence (top move switch)
      GAS: Gap-Adjusted Score (level_gap weighted by rank_delta)
      OBS: Observer Resolution Shift (stability_delta)
      RC:  Rank Compression (rank approaching capacity)
      NLE: Non-Linear Entropy (entropy ratio change)

    A position is CONFIRMED flashover when >= 4/5 metrics pass AND level_switch = True.
    A position is STRONG candidate when >= 4/5 metrics pass OR (rank_delta >= 3 AND level_gap > 0.02).
    """
    if thresholds is None:
        thresholds = {
            "stability_delta_min": 0.05,
            "level_gap_min": 0.02,
            "rank_delta_min": 3,
            "entropy_delta_min": 0.15,
            "cc_min": 0.1,
        }

    results = []

    for entry in cc_series:
        if entry is None:
            continue

        metrics_pass = 0
        metric_details = {}

        # LCE: Level Change Evidence
        lce = 1.0 if entry["top_switch"] else 0.0
        metric_details["LCE"] = round(lce, 3)
        if lce > 0.5:
            metrics_pass += 1

        # GAS: Gap-Adjusted Score
        gas = entry["level_gap"] * (1 + entry["rank_delta"])
        metric_details["GAS"] = round(gas, 3)
        if gas > 0.03:
            metrics_pass += 1

        # OBS: Observer Resolution Shift
        obs = entry["stability_delta"]
        metric_details["OBS"] = round(obs, 3)
        if obs > thresholds["stability_delta_min"]:
            metrics_pass += 1

        # RC: Rank Compression
        rc = entry["rank_delta"] / 10.0
        metric_details["RC"] = round(rc, 3)
        if entry["rank_delta"] >= thresholds["rank_delta_min"]:
            metrics_pass += 1

        # NLE: Non-Linear Entropy
        nle = entry["entropy_delta"]
        metric_details["NLE"] = round(nle, 3)
        if nle > thresholds["entropy_delta_min"]:
            metrics_pass += 1

        # Classification
        if metrics_pass >= 4 and entry["top_switch"]:
            status = "CONFIRMED"
        elif metrics_pass >= 4 or (entry["rank_delta"] >= 3 and entry["level_gap"] > 0.02):
            status = "STRONG"
        elif metrics_pass >= 2:
            status = "candidate"
        else:
            status = "normal"

        # Composite flashover score
        score = (
            0.25 * lce
            + 0.20 * min(gas * 10, 1.0)
            + 0.20 * min(obs * 5, 1.0)
            + 0.15 * min(rc * 3, 1.0)
            + 0.20 * min(nle * 3, 1.0)
        )

        results.append({
            "t": entry["t"],
            "move": entry["move"],
            "color": entry["color"],
            "status": status,
            "score": round(score, 3),
            "metrics_pass": metrics_pass,
            "top_switch": entry["top_switch"],
            "top_low": entry["top_low"],
            "top_high": entry["top_high"],
            "cc": entry["cc"],
            "metrics": metric_details,
        })

    return results


def print_ranking(results, top_n=15):
    """Print ranked flashover candidates."""
    ranked = sorted(results, key=lambda x: x["score"], reverse=True)

    print(f"\n{'#':>3}  {'t':>3}  {'move':<6} {'status':<12} {'score':>6}  "
          f"{'pass':>4}  {'top_lo':<6} {'top_hi':<6} {'switch':<6}  "
          f"{'LCE':>5} {'GAS':>5} {'OBS':>5} {'RC':>5} {'NLE':>5}")
    print("-" * 95)

    for i, r in enumerate(ranked[:top_n], 1):
        m = r["metrics"]
        sw = "YES" if r["top_switch"] else "no"
        marker = " <<<" if r["status"] in ("CONFIRMED", "STRONG") else ""
        print(f"{i:3d}  {r['t']:3d}  {r['move']:<6} {r['status']:<12} {r['score']:6.3f}  "
              f"{r['metrics_pass']:4d}  {r['top_low']:<6} {r['top_high']:<6} {sw:<6}  "
              f"{m['LCE']:5.3f} {m['GAS']:5.3f} {m['OBS']:5.3f} {m['RC']:5.3f} {m['NLE']:5.3f}"
              f"{marker}")


def main():
    parser = argparse.ArgumentParser(description="ActProof Flashover Detection")
    parser.add_argument("--input", help="Pre-computed CC JSON file")
    parser.add_argument("--low", help="Low-budget analysis JSONL")
    parser.add_argument("--high", help="High-budget analysis JSONL")
    parser.add_argument("--sgf", help="SGF game file")
    parser.add_argument("--output", help="Output JSON file")
    parser.add_argument("--top", type=int, default=15, help="Show top N candidates")
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

    results = detect_flashover(cc_series)
    print_ranking(results, args.top)

    # Summary
    confirmed = [r for r in results if r["status"] == "CONFIRMED"]
    strong = [r for r in results if r["status"] == "STRONG"]
    print(f"\nCONFIRMED flashover points: {[r['t'] for r in confirmed]}")
    print(f"STRONG candidates: {[r['t'] for r in strong]}")

    if args.output:
        with open(args.output, 'w') as f:
            json.dump({"results": results}, f, indent=2)
        print(f"\nFull results written to {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
