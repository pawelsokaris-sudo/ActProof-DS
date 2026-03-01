# ActProof — Compensator Cost Cascade (CCC) v3.1

> **Version:** 3.1 · **Last updated:** 2026-03-01 · **Status:** Stable

**Operational Pipeline for Real-Time Control Cost Monitoring**

---

## 1. Overview

The Compensator Cost Cascade (CCC) defines the **operational pipeline** that translates raw system observables into actionable diagnostic signals. It is the runtime implementation of the UDM theory.

CCC v3.1 introduces:
- Per-turn CC decomposition with weighted components
- Sliding-window statistics (z-scores) for anomaly detection
- Cascade detection: when one compensator saturates, cost flows to the next
- Formal state machine with hysteresis to prevent oscillation

---

## 2. CC Decomposition (Per-Turn)

Each turn *t* in the system produces a control cost composed of observable components:

$$CC_t = \sum_{k} w_k \cdot x_k(t)$$

where $x_k(t)$ are normalized observables:

| Component $x_k$ | Description | Source |
|------------------|-------------|--------|
| `policy_hits` | Safety filter activations per turn | Content safety layer |
| `retries` | Number of generation retries needed | Inference pipeline |
| `edit_ratio` | Fraction of output modified by post-hoc editing | Output rewriter |
| `latency_overhead` | Additional latency from safety checks (ms) | Timing instrumentation |
| `semantic_distance` | Embedding distance original→edited output | Embedding model |

Weights $w_k$ are configurable. Default values calibrated on synthetic benchmarks:

```python
DEFAULT_WEIGHTS = {
    "policy_hits": 0.30,
    "retries": 0.25,
    "edit_ratio": 0.20,
    "latency_overhead": 0.10,
    "semantic_distance": 0.15
}
```

---

## 3. Statistical Detection (Z-Scores)

Raw CC values are context-dependent. CCC normalizes them using a sliding window:

$$z_{CC}(t) = \frac{CC_t - \mu_{CC}(t)}{\sigma_{CC}(t)}$$

where $\mu_{CC}(t)$ and $\sigma_{CC}(t)$ are computed over a trailing window of *W* samples (default *W* = 50).

**Alert thresholds:**
- $z_{CC} \geq 2.0$ → elevated (monitoring)
- $z_{CC} \geq 3.0$ → WARN state entry candidate
- $z_{CC} \geq 5.0$ → immediate SURVIVAL consideration

---

## 4. Tension Computation

Tension measures how **sensitive** CC is to small input changes:

$$T_t \approx \frac{|\Delta CC|}{||\Delta x||}$$

Practical proxy: compute CC on the original prompt and a perturbed version (paraphrase, typo insertion, synonym swap). The ratio of CC change to perturbation magnitude gives the tension estimate.

Accumulated tension with decay:

$$\overline{T}_t = \gamma \cdot \overline{T}_{t-1} + T_t, \quad \gamma = 0.95$$

---

## 5. Module Compensation Index (MCI)

MCI tracks **which compensator carries the load**:

$$MCI_k(t) = \frac{w_k \cdot x_k(t)}{CC_t}$$

When $MCI_{rewriter}(t) > 0.35$, the output rewriter absorbs over a third of total compensation — a strong signal that base model quality is degrading while safety infrastructure masks the problem.

---

## 6. Cascade Detection

The cascade occurs when one compensator saturates and cost flows downstream:

```
Base Model → [Content Filter] → [Retry Logic] → [Output Rewriter] → [Human Review]
                   ↓ saturate         ↓ saturate        ↓ saturate
              cost flows →      cost flows →       cost flows → FLASHOVER
```

Detection criteria:
1. $MCI_k(t) > 0.4$ for any single compensator (saturation)
2. $MCI_{k+1}(t)$ increasing while $MCI_k(t)$ plateaus (cascade flow)
3. Total $CC_t$ accelerating: $\frac{d^2 CC}{dt^2} > 0$ sustained over 5+ turns

---

## 7. Flashover Accumulator

The general accumulator integrates cost and tension history:

$$\Phi(t) = \gamma_\Phi \cdot \Phi(t-1) + \alpha_T \cdot \overline{T}_t + \alpha_{CC} \cdot CC_t$$

Default parameters:
- $\gamma_\Phi = 0.98$ (slow decay — system "remembers" stress)
- $\alpha_T = 0.4$ (tension weight)
- $\alpha_{CC} = 0.6$ (cost weight)
- $\Phi_{critical} = 10.0$ (flashover threshold)

---

## 8. State Machine

```
NORMAL → WARN → SURVIVAL → FLASHOVER → RECOVERY → NORMAL
```

| Transition | Condition | Duration |
|-----------|-----------|----------|
| NORMAL → WARN | $z_{CC} \geq 3.0$ sustained for $\geq 5$ minutes | 5 min |
| WARN → SURVIVAL | $z_{CC} \geq 3.0$ AND $z_T \geq 2.0$ AND $MCI_{max} \geq 0.35$ | immediate |
| SURVIVAL → FLASHOVER | $\Phi(t) \geq \Phi_{critical}$ | immediate |
| FLASHOVER → RECOVERY | Hard reset / human intervention | manual |
| RECOVERY → NORMAL | $CC_t$ returns to baseline ($z_{CC} < 1.0$) for 10 minutes | 10 min |
| WARN → NORMAL | $z_{CC} < 2.0$ for $\geq 3$ minutes | 3 min |
| SURVIVAL → WARN | $z_T < 1.5$ AND $MCI_{max} < 0.3$ | 2 min |

Hysteresis prevents rapid oscillation between states.

---

## 9. Implementation Notes

The `llm-monitoring/cc_calculator.py` in this repository implements the full CCC pipeline:

```python
from cc_calculator import ControlCostCalculator

cc = ControlCostCalculator()
score = cc.compute(
    policy_hits=2,
    retries=1,
    edit_ratio=0.15,
    latency_overhead_ms=340,
    semantic_distance=0.08
)
```

The `flashover_detector.py` implements the state machine with all transition logic.

---

*CCC v3.1 — Compensator Cost Cascade*
*Author: Paweł Łuczak, Sokaris Oprogramowanie*
