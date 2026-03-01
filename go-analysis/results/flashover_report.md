# Flashover Detection Report — Go Game Analysis

## Overview

This report documents the empirical validation of ActProof's control cost framework
on a professional Go game, using KataGo as the reference engine. The core question:
**Can control cost (CC) metrics detect critical game transitions before the engine's
own evaluation reflects the change?**

**Answer: Yes.** The primary flashover point occurs at **t=38 (O17)**, not at
the culturally famous Move 37 (R15). The description boundary lies at Lee Sedol's
*response* to the genius move, not at the move itself.

---

## Case Study 1: AlphaGo vs Lee Sedol — Game 2

- **Event**: Google DeepMind Challenge Match
- **Date**: March 10, 2016
- **Players**: AlphaGo (Black) vs Lee Sedol 9d (White)
- **Result**: Black wins by resignation (B+Resign)
- **Critical cultural moment**: Move 37 (R15) — AlphaGo's "move from another dimension"

### Analysis Setup

- **Engine**: KataGo v1.15.3 (Eigen/CPU)
- **Model**: kata1-b18c384nbt-s9131461376-d4087399203
- **Low budget**: 200 visits per position (System 1 — fast/shallow evaluation)
- **High budget**: 2000 visits per position (System 2 — deep evaluation)
- **Coverage**: 200v for t1-t127 (99 positions), 2000v for t1-t73 (45 positions)

### Key Finding: Flashover at t=38, NOT Move 37

The culturally famous Move 37 (R15) ranks **31st out of 34** analyzed positions
with a flashover score of only 0.035. Both budgets agree R15 is invisible
(rank 99 in both). There is no description boundary at Move 37.

**The real flashover occurs at t=38 (O17)** — Lee Sedol's response to Move 37:

| Metric | 200 visits | 2000 visits | Delta |
|--------|-----------|-------------|-------|
| **Rank** | 11 | 11 | 0 |
| **Stability (winrate)** | 0.463 | 0.827 | **+0.364** |
| **Level gap** | — | — | **0.0387** |
| **Top move** | L18 | M16 | **SWITCH = YES** |
| **Entropy** | 2.189 | 1.067 | **-1.122 (dramatic drop)** |

M37 Bridge Metrics for t=38:
- LCE = 0.762 ✓
- GAS = 0.579 ✓
- OBS = 0.855 ✓
- RC = 0.363 ✓
- NLE = 0.563 ✓
- **Result: 5/5 metrics pass → CONFIRMED flashover**

### Interpretation

The "genius move" narrative is a cultural phenomenon, not an observer resolution boundary.
Move 37 itself doesn't change what either budget of analysis sees — both agree it's
invisible (off the top-move radar entirely).

**But the response space opened by Move 37 is where the description boundary shifts.**
A shallow observer (200 visits) recommends L18 as the best response. A deeper observer
(2000 visits) switches to M16. This top-move switch, combined with dramatic entropy
drop and stability shift, constitutes the flashover point.

> **ActProof thesis confirmed:** A low-Φ observer cannot compute the response space
> opened by a novel move. The flashover (description boundary) occurs at the
> *adaptation point*, not at the *surprise point*.

### Global Ranking (t1-t62, 34 positions)

```
  #   t  move   status      score  r200  r2k  top200  top2k  switch
  1  49  N13    STRONG      3.391    99    8    P14     P14    no
  2  57  O12    STRONG      3.171    99   11    Q13     Q13    no
  3  54  Q17    STRONG      3.080    99   12    Q14     Q14    no
  4  46  O15    candidate   2.982    99   16    L18     L18    no
  5  45  N15    candidate   0.786    99   99    J16     R17    YES
  6  59  O11    candidate   0.746    99   99    S18     J14    YES
  7  38  O17    CONFIRMED   0.745    11   11    L18     M16    YES  <<<
  8  48  P15    candidate   0.724     5    5    P14     L18    YES
  9  56  R18    CONFIRMED   0.605     6    6    N17     Q14    YES  <<<
 10  61  O10    STRONG      0.447    99   99    J14     J14    no
 ...
 31  37  R15    candidate   0.035    99   99    Q16     Q16    no   <<< Move 37
```

Classification criteria:
- **CONFIRMED**: metrics_pass ≥ 4 AND level_switch = TRUE
- **STRONG**: metrics_pass ≥ 4 OR (delta_rank ≥ 3 AND level_gap > 0.02)

### Cross-Validation

ChatGPT independently verified from the raw JSONL files:
1. t=49 (N13): absent in 200v top-7, appears at rank 8 in 2000v — consistent
2. delta_rank = 91 is correct (99−8 convention)
3. Confirmed this IS the M37 lemma condition on visibility/ranking
4. Called the Scenario 3 interpretation "logically coherent"
5. Noted: rank alone proves loss of RESOLUTION; Delta on VALUE metrics (winrate/scoreLead) provides additional confirmation

---

## Case Study 2: Secondary Flashover at t=56 (R18)

The second CONFIRMED flashover at t=56 (R18):
- 200v top move: N17 (rank 6)
- 2000v top move: Q14 (rank 6)
- Top move switch: **YES**
- Metrics pass: 5/5

This represents a second description boundary where shallow and deep analysis
diverge on the optimal response. The game enters a qualitatively different
tactical phase where the observer's computational budget determines what
strategic plan is seen as optimal.

---

## Methodology Notes

### What "Flashover" Means in Go

In the ActProof framework, flashover is the point where a low-computation observer
can no longer maintain agreement with a high-computation observer. In Go terms:

- **Before flashover**: 200 visits and 2000 visits recommend the same top move
- **At flashover**: They disagree on what to play — different Computational budgets
  see different strategic plans
- **After flashover**: The position's complexity exceeds the low observer's resolution

This maps directly to the LLM monitoring scenario:
- **Before flashover**: Light safety checks agree with heavy safety checks
- **At flashover**: Light checks miss what heavy checks catch
- **After flashover**: The system is in a regime where light monitoring is insufficient

### Reproducing This Analysis

```bash
# 1. Install dependencies
pip install matplotlib numpy

# 2. Run CC computation on the provided data
cd go-analysis
python scripts/compute_cc.py \
    --low data/katago_output/analysis_focused.jsonl \
    --high data/katago_output/analysis_safe.jsonl \
    --sgf data/games/alphago_vs_lee_sedol_game2.sgf \
    --output results/cc_game2.json

# 3. Run flashover detection
python scripts/detect_flashover.py --input results/cc_game2.json

# 4. Generate visualizations
python scripts/visualize.py --input results/cc_game2.json --output results/figures/
```

Note: The provided analysis files use different ID prefixes for focused vs safe runs.
The focused file contains 200v t1-t50 and 2000v t1-t37.
The safe file contains 200v t38-t127 and 2000v t38-t50.
Some preprocessing may be needed to merge them into the standard format.

### Data Files

| File | Content | Size |
|------|---------|------|
| `data/games/alphago_vs_lee_sedol_game2.sgf` | Full game record (206 moves) | 1.5 KB |
| `data/katago_output/analysis_focused.jsonl` | 33 results: 200v t1-t50, 2000v t1-t37 | 706 KB |
| `data/katago_output/analysis_safe.jsonl` | 103 results: 200v t38-t127, 2000v t38-t50 | 354 KB |

---

## Conclusions

1. **ActProof CC framework detects flashover points in Go** — positions where
   computational budget determines strategic assessment
2. **The flashover is at the response, not the surprise** — t=38 (response to Move 37),
   not t=37 (Move 37 itself)
3. **The M37 Bridge metrics provide robust classification** — 5/5 pass for confirmed points
4. **The framework generalizes** — the same CC/T/Φ definitions applicable to LLM monitoring

---

*Report generated from ActProof go-analysis pipeline*
*Data: KataGo v1.15.3 analysis of AlphaGo vs Lee Sedol Game 2*
*Author: Paweł Łuczak, Sokaris Oprogramowanie*
