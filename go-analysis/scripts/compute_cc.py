# -*- coding: utf-8 -*-
"""
ActProof: Compute CC(t) from KataGo Analysis Output
====================================================
Computes the Control Cost curve for each move in a game by comparing
KataGo evaluations at two budget levels (low vs high visits).

CC at each move is derived from:
  - Rank divergence: how differently the engine ranks the played move
  - Stability delta: winrate change between budgets
  - Level gap: root evaluation difference between budgets
  - Entropy delta: policy distribution entropy change

Usage:
    python compute_cc.py --low analysis_200.jsonl --high analysis_2000.jsonl --sgf game.sgf
"""

import json
import re
import math
import argparse
import sys
from pathlib import Path


def parse_sgf_moves(sgf_text):
    """Extract moves from SGF as list of (color, sgf_coord)."""
    pattern = re.compile(r';([BW])\[([a-s]{2})\]')
    return [(m.group(1), m.group(2)) for m in pattern.finditer(sgf_text)]


def sgf_to_gtp(coord):
    """Convert SGF coordinate (e.g., 'dp') to GTP (e.g., 'D4')."""
    if not coord:
        return "pass"
    col = ord(coord[0]) - ord('a')
    row = ord(coord[1]) - ord('a')
    gtp_col = chr(ord('A') + col + (1 if col >= 8 else 0))  # skip I
    gtp_row = 19 - row
    return f"{gtp_col}{gtp_row}"


def load_analysis(filepath):
    """Load KataGo analysis JSONL into dict keyed by id."""
    results = {}
    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                results[data.get("id", "")] = data
            except json.JSONDecodeError:
                pass
    return results


def find_rank(result, move_gtp):
    """Find the rank and winrate of a specific move in KataGo output."""
    for idx, mi in enumerate(result.get("moveInfos", [])):
        if mi.get("move") == move_gtp:
            return idx + 1, mi.get("winrate", 0.5)
    return 99, 0.5  # not found in top moves


def compute_entropy(result):
    """Compute policy entropy from move visit distribution."""
    move_infos = result.get("moveInfos", [])
    total_visits = sum(mi.get("visits", 0) for mi in move_infos)
    if total_visits == 0:
        return 0.0
    entropy = 0.0
    for mi in move_infos:
        p = mi.get("visits", 0) / total_visits
        if p > 0:
            entropy -= p * math.log2(p)
    return entropy


def compute_cc_series(moves, analysis_low, analysis_high, budget_low="200", budget_high="2000"):
    """
    Compute CC(t) for each move in the game.

    CC is a composite metric:
      - rank_delta: |rank_low - rank_high| / 10
      - stability_delta: |winrate_low - winrate_high|
      - level_gap: |root_wr_low - root_wr_high|
      - entropy_delta: |entropy_low - entropy_high| / max_entropy

    CC(t) = w1*rank_delta + w2*stability_delta + w3*level_gap + w4*entropy_delta
    """
    WEIGHTS = {
        "rank_delta": 0.30,
        "stability_delta": 0.25,
        "level_gap": 0.25,
        "entropy_delta": 0.20,
    }

    cc_series = []

    for t in range(1, len(moves) + 1):
        key_low = f"{budget_low}_t{t}"
        key_high = f"{budget_high}_t{t}"

        if key_low not in analysis_low or key_high not in analysis_high:
            cc_series.append(None)
            continue

        r_low = analysis_low[key_low]
        r_high = analysis_high[key_high]

        played_gtp = sgf_to_gtp(moves[t - 1][1])

        # Rank divergence
        rank_low, wr_low = find_rank(r_low, played_gtp)
        rank_high, wr_high = find_rank(r_high, played_gtp)
        rank_delta = abs(rank_low - rank_high) / 10.0

        # Stability: how much does the move's evaluation change with more compute
        stability_delta = abs(wr_low - wr_high)

        # Level gap: root position evaluation difference
        wr_root_low = r_low.get("rootInfo", {}).get("winrate", 0.5)
        wr_root_high = r_high.get("rootInfo", {}).get("winrate", 0.5)
        level_gap = abs(wr_root_high - wr_root_low)

        # Entropy: how concentrated is the policy
        entropy_low = compute_entropy(r_low)
        entropy_high = compute_entropy(r_high)
        entropy_delta = abs(entropy_low - entropy_high) / max(entropy_low, entropy_high, 1.0)

        # Top move switch detection
        top_low = r_low.get("moveInfos", [{}])[0].get("move", "?") if r_low.get("moveInfos") else "?"
        top_high = r_high.get("moveInfos", [{}])[0].get("move", "?") if r_high.get("moveInfos") else "?"
        top_switch = top_low != top_high

        # Composite CC
        cc = (
            WEIGHTS["rank_delta"] * rank_delta
            + WEIGHTS["stability_delta"] * stability_delta
            + WEIGHTS["level_gap"] * level_gap
            + WEIGHTS["entropy_delta"] * entropy_delta
        )

        cc_series.append({
            "t": t,
            "move": played_gtp,
            "color": moves[t - 1][0],
            "cc": round(cc, 4),
            "rank_low": rank_low,
            "rank_high": rank_high,
            "rank_delta": round(rank_delta, 4),
            "wr_low": round(wr_low, 4),
            "wr_high": round(wr_high, 4),
            "stability_delta": round(stability_delta, 4),
            "level_gap": round(level_gap, 4),
            "entropy_low": round(entropy_low, 4),
            "entropy_high": round(entropy_high, 4),
            "entropy_delta": round(entropy_delta, 4),
            "top_low": top_low,
            "top_high": top_high,
            "top_switch": top_switch,
        })

    return cc_series


def main():
    parser = argparse.ArgumentParser(description="Compute ActProof CC(t) from KataGo analysis")
    parser.add_argument("--low", required=True, help="Path to low-budget analysis JSONL")
    parser.add_argument("--high", required=True, help="Path to high-budget analysis JSONL")
    parser.add_argument("--sgf", required=True, help="Path to SGF game file")
    parser.add_argument("--output", default=None, help="Output JSON file (default: stdout)")
    parser.add_argument("--budget-low", default="200", help="Low budget label (default: 200)")
    parser.add_argument("--budget-high", default="2000", help="High budget label (default: 2000)")
    args = parser.parse_args()

    # Load SGF
    with open(args.sgf, 'r') as f:
        sgf_content = f.read()
    moves = parse_sgf_moves(sgf_content)
    print(f"Loaded {len(moves)} moves from SGF", file=sys.stderr)

    # Load analysis
    analysis_low = load_analysis(args.low)
    analysis_high = load_analysis(args.high)
    print(f"Loaded {len(analysis_low)} low-budget, {len(analysis_high)} high-budget results", file=sys.stderr)

    # Compute CC
    cc_series = compute_cc_series(moves, analysis_low, analysis_high, args.budget_low, args.budget_high)

    # Filter None entries
    cc_valid = [x for x in cc_series if x is not None]
    print(f"Computed CC for {len(cc_valid)} positions", file=sys.stderr)

    # Output
    output = {
        "game": args.sgf,
        "budget_low": args.budget_low,
        "budget_high": args.budget_high,
        "total_moves": len(moves),
        "analyzed_moves": len(cc_valid),
        "cc_series": cc_valid,
    }

    if args.output:
        with open(args.output, 'w') as f:
            json.dump(output, f, indent=2)
        print(f"Written to {args.output}", file=sys.stderr)
    else:
        print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
