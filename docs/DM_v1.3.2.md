# ActProof — Latent Tension and Relaxation Time (DM v1.3.2)

**Diagnostic Metrics for Hidden Structural Stress**

---

## 1. Motivation

Standard CC monitoring detects active cost. But systems can carry **latent tension** — structural stress that is not yet visible in the CC signal but makes the system fragile to perturbation. A system with $CC \approx 0$ but high latent tension is a bomb waiting for a trigger.

DM v1.3.2 formalizes:
- How latent tension accumulates from past stress
- How quickly tension dissipates (relaxation time)
- How to detect systems that appear "calm" but are structurally brittle

---

## 2. Latent Tension Model

### 2.1 Tension Accumulation with Relaxation

$$\overline{T}_t = \gamma \cdot \overline{T}_{t-1} + T_t$$

where:
- $T_t$ is the instantaneous tension at step *t*
- $\gamma \in [0, 1]$ is the **relaxation factor** (memory decay)
- $\overline{T}_t$ is the accumulated tension ("scar tissue")

**Key property:** Even when $T_t = 0$ (no active tension), accumulated tension $\overline{T}_t$ decays geometrically but persists:

$$\overline{T}_{t+k} = \gamma^k \cdot \overline{T}_t \quad \text{(if no new tension)}$$

### 2.2 Relaxation Time

The **relaxation time** $\tau_R$ is the characteristic time for accumulated tension to decay to $1/e$ of its peak:

$$\tau_R = -\frac{1}{\ln \gamma}$$

| $\gamma$ | $\tau_R$ (steps) | Interpretation |
|-----------|-----------------|----------------|
| 0.99 | 100 | Long memory — tension persists for ~100 steps |
| 0.95 | 20 | Medium memory |
| 0.90 | 10 | Short memory — rapid forgetting |
| 0.50 | 1.4 | Very short memory |

**Recommended default:** $\gamma = 0.95$ ($\tau_R \approx 20$ turns)

---

## 3. Latent Tension Detection

A system is in the **latent tension regime** when:

$$CC_t < \mu_{CC} \quad \text{AND} \quad \overline{T}_t > \theta_T$$

In plain language: current cost is normal, but accumulated structural stress is above threshold.

### 3.1 Phase Space Trajectories

Plot $(CC_t, \overline{T}_t)$ to visualize system trajectories:

```
     T̄ (accumulated tension)
     ↑
     │  ╔═══════════════╗
     │  ║ LATENT DANGER  ║   ← Low CC, High T̄
     │  ║ (invisible to  ║
     │  ║  CC-only tools) ║
     │  ╚════════╤══════╝
     │           │ perturbation
     │           ↓
     │  ╔═══════════════╗
     │  ║   FLASHOVER    ║   ← High CC, High T̄
     │  ╚═══════════════╝
     └────────────────────→ CC (control cost)
```

The trajectory often follows a characteristic "L-shape":
1. CC spike → tension accumulates (rightward, then upward)
2. CC normalizes → tension persists (leftward, but stays high)
3. Next perturbation → faster CC spike because T̄ is already elevated

---

## 4. Relaxation Asymmetry

A critical observation: **tension accumulates faster than it dissipates.**

If a stress event lasts *k* steps with constant tension $T_{stress}$:

$$\overline{T}_{peak} = T_{stress} \cdot \frac{1 - \gamma^k}{1 - \gamma}$$

Relaxation back to pre-stress level takes:

$$k_{relax} = \frac{\ln(\varepsilon)}{\ln(\gamma)} \quad \text{steps to reach fraction } \varepsilon \text{ of peak}$$

For $\gamma = 0.95$ and $\varepsilon = 0.05$ (95% relaxation): $k_{relax} \approx 59$ steps.

A 10-step stress event at $\gamma = 0.95$ takes ~59 steps to fully relax — **6x the stress duration**.

This asymmetry explains why systems that appear "recovered" can be much more fragile than baseline.

---

## 5. Integration

### 5.1 In the Flashover Accumulator

The accumulated tension feeds into the flashover accumulator:

$$\Phi(t) = \gamma_\Phi \cdot \Phi(t-1) + \alpha_T \cdot \overline{T}_t + \alpha_{CC} \cdot CC_t$$

Latent tension keeps $\Phi$ elevated even when CC normalizes, providing the "long memory" needed to detect gradual degradation.

### 5.2 As Early Warning Signal

Monitor $\overline{T}_t$ as a standalone metric:
- When $\overline{T}_t > 2\sigma_T$: system carries unresolved structural stress
- When $\overline{T}_t$ fails to return to baseline within $3\tau_R$: possible permanent structural change (model degradation, distribution shift)

---

*DM v1.3.2 — Latent Tension and Relaxation Time*
*Author: Paweł Łuczak, Sokaris Oprogramowanie*
