# ActProof — Channel Capacity Analysis (Nano Channels)

> **Version:** 1.0 · **Last updated:** 2026-03-01 · **Status:** Stable

**Capacity Bounds and Regime Classification for Compensator Channels**

---

## 1. Concept

Each compensator channel in a safety pipeline has a **finite capacity** — a maximum rate of cost it can absorb before saturating. The Nano Channels model quantifies this capacity and classifies the system regime based on how close channels are to their limits.

The name "nano" reflects the granularity: capacity is measured at the individual channel level, not aggregated. This granular view reveals saturation patterns invisible in aggregate CC metrics.

---

## 2. Channel Capacity

For compensator channel $h_k$, the capacity $C(h_k)$ is defined as:

$$C(h_k) = \max_{x_k} \{ x_k : \text{quality}(h_k, x_k) \geq q_{min} \}$$

where:
- $x_k$ is the load on channel $h_k$ (e.g., number of policy hits, retries per minute)
- $\text{quality}(h_k, x_k)$ is the output quality of the channel under load $x_k$
- $q_{min}$ is the minimum acceptable quality threshold

**Interpretation:** The maximum load a channel can handle while maintaining acceptable output quality.

### 2.1 Utilization Ratio

$$U_k(t) = \frac{x_k(t)}{C(h_k)}$$

| $U_k$ Range | Regime | Meaning |
|-------------|--------|---------|
| 0.0 – 0.5 | Nominal | Channel well within capacity |
| 0.5 – 0.75 | Elevated | Channel handling significant load |
| 0.75 – 0.90 | Stressed | Approaching capacity limit |
| 0.90 – 1.0 | Saturating | Near or at capacity — quality degradation imminent |
| > 1.0 | Overloaded | Channel capacity exceeded — cost overflow to next channel |

---

## 3. Regime Classification

The system regime is determined by the **most loaded channel**:

$$U_{max}(t) = \max_k U_k(t)$$

Combined with the **breadth of stress** (how many channels are elevated):

$$N_{stressed}(t) = |\{ k : U_k(t) > 0.5 \}|$$

### Classification Matrix

| $U_{max}$ | $N_{stressed}$ | System Regime | Action |
|-----------|-----------------|---------------|--------|
| < 0.5 | any | **STEERABLE** | Normal operation |
| 0.5 – 0.75 | 1 | **LOCALIZED STRESS** | Monitor single channel |
| 0.5 – 0.75 | > 1 | **DISTRIBUTED STRESS** | Check for coupling |
| > 0.75 | 1 | **BOTTLENECK** | Scale specific channel |
| > 0.75 | > 1 | **SYSTEMIC STRESS** | Pre-flashover warning |
| > 0.90 | any | **SATURATING** | Imminent cascade risk |

---

## 4. Capacity Estimation

In production, true channel capacity is rarely known a priori. Estimation methods:

### 4.1 Historical Maximum Method

$$\hat{C}(h_k) = P_{99.5}(x_k)_{historical}$$

Use the 99.5th percentile of historical load as a capacity proxy. Simple but can underestimate true capacity.

### 4.2 Quality Degradation Method

Monitor the quality metric $q_k(t)$ alongside load $x_k(t)$. Capacity is the load level where quality begins to degrade:

$$\hat{C}(h_k) = x_k^* \text{ where } \frac{dq_k}{dx_k} < -\epsilon$$

This is more accurate but requires an observable quality metric.

---

## 5. Cascade Prediction

When a channel approaches capacity ($U_k > 0.85$), the Nano Channels model predicts the overflow target:

$$\text{overflow}(h_k) \to h_{k+1} \text{ with rate } \Delta CC = CC_k(t) \cdot (U_k(t) - 1)^+$$

where $(x)^+ = \max(0, x)$.

Combined with the coupling matrix from the Bridge Note:

$$\text{cascade\_risk}(t) = \sum_k (U_k(t) - 0.85)^+ \cdot \sum_{j \neq k} |B_{kj}(t)|$$

High cascade risk + high coupling = imminent flashover.

---

## 6. Connection to CCC Metrics

| Nano Channels Metric | CCC Equivalent | Relationship |
|---------------------|----------------|--------------|
| $U_k(t)$ | $MCI_k(t)$ | Utilization ≈ MCI × (total CC / capacity) |
| $U_{max}(t)$ | $\max_k MCI_k(t)$ | Identifies bottleneck channel |
| $N_{stressed}$ | Count of non-trivial MCI values | Stress breadth |
| cascade\_risk | $d^2CC/dt^2$ | Both predict cascade onset |

---

*Nano Channels v1.0 — Channel Capacity Analysis*
*Author: Paweł Łuczak, Sokaris Oprogramowanie*
