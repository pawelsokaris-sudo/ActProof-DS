# ActProof — Bridge Note: Channel Coupling Detection

> **Version:** 1.0 · **Last updated:** 2026-03-01 · **Status:** Stable

**Perturbation-Response Analysis for Cross-Channel Interactions**

---

## 1. Problem Statement

In multi-layer safety systems, compensators do not operate independently. A perturbation in one channel (e.g., increased content filter activations) can propagate to other channels (e.g., increased retries, higher rewriting load). The **Bridge Note** formalizes detection of these cross-channel couplings.

Without coupling detection, a single-channel monitoring approach underestimates systemic risk: each channel appears individually manageable, while the combined load pushes the system toward flashover.

---

## 2. Channel Model

Let the system have *n* compensator channels $h_1, h_2, \ldots, h_n$, each with its own cost contribution $CC_k(t) = w_k \cdot x_k(t)$.

The **coupling matrix** at time *t*:

$$B_{ij}(t) = \frac{\partial CC_i(t)}{\partial x_j(t)}$$

**Interpretation:**
- $B_{ij} \approx 0$: channels *i* and *j* operate independently
- $B_{ij} > 0$: perturbation in channel *j* increases cost in channel *i* (positive coupling)
- $B_{ij} < 0$: perturbation in channel *j* decreases cost in channel *i* (compensation transfer)

---

## 3. Detection Method

Since analytic gradients are typically unavailable in production, we estimate the coupling matrix empirically:

### 3.1 Natural Perturbation Method

Monitor co-variation of channel costs over a sliding window:

$$\hat{B}_{ij} = \text{corr}(CC_i, CC_j)_{t-W:t}$$

When $|\hat{B}_{ij}|$ exceeds a threshold (default 0.6), channels *i* and *j* are flagged as coupled.

### 3.2 Active Perturbation Method (Testing Environments)

Inject controlled perturbations into channel *j* and measure the response in channel *i*:

$$\hat{B}_{ij} = \frac{\Delta CC_i}{\Delta x_j} \bigg|_{\text{other channels constant}}$$

This provides causal (not merely correlational) evidence of coupling.

---

## 4. Bridge Events

A **bridge event** occurs when coupling creates a cost amplification loop:

$$\sum_{i \neq j} |B_{ij}(t)| > \theta_{bridge}$$

This indicates that a perturbation in any single channel will amplify across the system — the precursor to cascading failure.

### Bridge Event Classification

| Type | Pattern | Risk |
|------|---------|------|
| **Linear bridge** | Channel A → Channel B → increased cost | Moderate |
| **Circular bridge** | A → B → C → A (feedback loop) | High |
| **Saturating bridge** | Channel A saturates → cost flood to B, C, D | Critical |

---

## 5. Integration with CCC Pipeline

The Bridge Note extends the CCC state machine with coupling awareness:

1. In **WARN** state: compute coupling matrix $B(t)$ over recent window
2. If bridge event detected ($\sum |B_{ij}| > \theta_{bridge}$): accelerate transition to **SURVIVAL**
3. In **SURVIVAL** state: monitor coupling for feedback loops (circular bridges)
4. Circular bridge detection → immediate escalation to **FLASHOVER** risk

---

## 6. Practical Example

Consider an LLM safety pipeline:

```
Input → [Prompt Shield] → [Model] → [Content Filter] → [Rewriter] → Output
```

- **Normal operation:** Each layer handles its own class of issues independently
- **Coupling scenario:** Prompt Shield misses an adversarial pattern → Model generates borderline content → Content Filter triggers at high rate → Rewriter saturates → Latency spikes → Retries increase → **Bridge event**: Filter + Rewriter + Retry channels coupled
- **Without bridge detection:** Each channel shows z-score of ~2.5 (below WARN threshold)
- **With bridge detection:** Combined coupling exceeds bridge threshold → early WARN

This is the scenario where standard per-channel monitoring fails but ActProof's coupling detection catches the emerging risk.

---

*Bridge Note v1.0 — Channel Coupling Detection*
*Author: Paweł Łuczak, Sokaris Oprogramowanie*
