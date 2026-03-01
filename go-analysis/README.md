# Go Analysis — Empirical Validation of ActProof

## Overview

This directory contains the empirical foundation of ActProof: analysis of Go games using KataGo
to demonstrate that control cost dynamics reliably predict critical game transitions (flashover).

**Primary finding:** Flashover at **t=38 (O17)**, not at culturally famous Move 37 (R15).
The description boundary lies at the *response* to the surprising move, not at the move itself.

## Game Analyzed

**AlphaGo vs Lee Sedol — Game 2** (Google DeepMind Challenge Match, March 10, 2016)
- AlphaGo (Black) vs Lee Sedol 9d (White)
- Result: B+Resign
- Cultural significance: Move 37 — AlphaGo's "move from another dimension"

## Methodology

1. **Dual-budget analysis**: Each position evaluated at 200 visits (System 1) and 2000 visits (System 2)
2. **CC computation**: Control cost derived from rank divergence, stability delta, level gap, and entropy change between budgets
3. **Flashover detection**: M37 Bridge criteria (5 metrics: LCE, GAS, OBS, RC, NLE)
4. **Validation**: Compare ActProof's detection with KataGo's own evaluation shift

## Quick Start

```bash
# Compute CC curve from existing analysis data
python scripts/compute_cc.py \
    --low data/katago_output/analysis_focused.jsonl \
    --high data/katago_output/analysis_safe.jsonl \
    --sgf data/games/alphago_vs_lee_sedol_game2.sgf \
    --output results/cc_game2.json

# Detect flashover points
python scripts/detect_flashover.py --input results/cc_game2.json

# Generate visualizations
python scripts/visualize.py --input results/cc_game2.json --output results/figures/
```

## Directory Structure

```
go-analysis/
├── README.md                       ← this file
├── scripts/
│   ├── compute_cc.py               ← CC(t) computation from KataGo dual-budget output
│   ├── detect_flashover.py         ← M37 Bridge flashover detection (5 metrics)
│   └── visualize.py                ← CC curve, level gap, and ranking visualizations
├── data/
│   ├── games/
│   │   └── alphago_vs_lee_sedol_game2.sgf
│   └── katago_output/
│       ├── analysis_focused.jsonl  ← 200v t1-t50, 2000v t1-t37 (33 results, 706 KB)
│       └── analysis_safe.jsonl     ← 200v t38-t127, 2000v t38-t50 (103 results, 354 KB)
└── results/
    ├── figures/                    ← generated CC curve plots
    └── flashover_report.md         ← documented case study with full data
```

## Key Results Summary

| Position | Move | Status | Score | Top-Move Switch | Top (200v → 2000v) |
|----------|------|--------|-------|-----------------|---------------------|
| t=38 | O17 | **CONFIRMED** | 0.745 | YES | L18 → M16 |
| t=56 | R18 | **CONFIRMED** | 0.605 | YES | N17 → Q14 |
| t=37 | R15 | candidate | 0.035 | no | Q16 → Q16 |

Move 37 (the famous "genius move") shows no description boundary — both budgets agree.
The flashover occurs at the *response space* opened by Move 37, not at the move itself.

→ See [results/flashover_report.md](results/flashover_report.md) for complete analysis.

## Requirements

- Python 3.8+
- matplotlib, numpy (for visualization only)
- KataGo (only if running new analyses)
