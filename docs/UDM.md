# ActProof — Universal Diagnostic Model (UDM) v1.0

**Unified Diagnostic Model for Autonomous Systems**

> *The world iterates states and accumulates consequences.*
> *A model iterates descriptions without consequences.*
> *Decisional autonomy arises where the cost of steering/compensation is borne.*

---

## 1. Fundamental Assumptions

The ActProof system is modeled as an ordered quadruple:

$$\Sigma = (\mathcal{S}, \mathcal{M}, \mathcal{C}, \Phi)$$

where:
- **S** (State Space): the real state space (e.g., warehouse resources, stellar positions, physical system state)
- **M** (Model Space): the space of descriptions and predictions (e.g., LLM, Newton/GR model, simplified process model)
- **C** (Constraint Set): the set of constraints (safety, limits, causality, resources)
- **Φ** (Accumulator): the memory/history operator (accumulation of costs and tensions)

---

## 2. Base Objects and the Matching Problem

### 2.1 World, Observations, and Information

At step *t*, the world has state $s_t \in \mathcal{S}$ and generates observations:

$$y_t \in \mathcal{Y}$$

Let $\mathcal{I}_t$ denote information available at step *t* (e.g., history, boundary conditions, context).

### 2.2 Local Model

Family of models:

$$\mathcal{M} = \{ M_\theta : \theta \in \Theta \}$$

Model prediction (without compensation):

$$\hat{y}_t(\theta) = M_\theta(\mathcal{I}_t)$$

### 2.3 Compensator (Missing Contribution)

We allow a family of compensations:

$$\mathcal{C} = \{ c_\phi : \phi \in \Phi \}$$

which are added to predictions (typically additively):

$$\hat{y}_t(\theta, \phi) = \hat{y}_t(\theta) \oplus c_\phi(\mathcal{I}_t), \quad \text{typically } \oplus \equiv +$$

### 2.4 Loss and Conformity Threshold

Loss function:

$$\mathcal{L}_t(\theta, \phi) := \ell(y_t, \hat{y}_t(\theta, \phi))$$

Acceptance threshold $\varepsilon_t > 0$.

---

## 3. Core Metrics

### 3.1 Control Cost — CC(t)

Let $J_t(\phi) \geq 0$ be the compensation cost (control energy, logistics cost, contribution norm, etc.).

> **Definition (Control Cost)**
>
> $$\boxed{CC_t(\theta) := \min_{\phi \in \Phi} \left\{ J_t(\phi) : \mathcal{L}_t(\theta, \phi) \leq \varepsilon_t \right\}}$$

**Interpretation:** $CC_t(\theta)$ is the *minimum surcharge* needed (within the class of admissible compensations) for the model to match the observation within tolerance $\varepsilon_t$.

### 3.2 Structural Tension — T(t)

Tension is a **continuous** measure of brittleness: how sensitive the minimum cost CC is to perturbations of model parameters.

**Absolute version:**

$$\boxed{T_t(\theta) := \|\nabla_\theta CC_t(\theta)\|}$$

**Relative version (recommended numerically):**

$$\boxed{T_t^{rel}(\theta) := \|\nabla_\theta \log(CC_t(\theta) + \delta)\|, \quad \delta > 0}$$

### 3.3 Worst-case Tension (Engineering Variant)

If the system has multiple constraints $x_i(t) \leq L_i$, the "weakest link" tension:

$$T_{sys}(t) := \max_i \left[ \max\left(0, \frac{x_i(t) - L_i}{L_i}\right) \right]$$

A practical variant (Kernel/Policy), independent of gradients over θ.

### 3.4 Module Compensation Index — MCI

MCI describes the flow of cost between modules (who "pays" for whom):

$$MCI_{i \to j} := \frac{\partial CC_j}{\partial y_i}$$

---

## 4. Memory (Accumulation and Relaxation)

We distinguish *step-wise* from *cumulative* quantities:

- $CC_t$ — cost at step *t*
- $\overline{CC}_t$ — cumulative cost
- $T_t$ — tension at step *t*
- $\overline{T}_t$ — cumulative tension ("scar")

> **Accumulation definitions:**
>
> Cost accumulation:
> $$\boxed{\overline{CC}_t = \overline{CC}_{t-1} + CC_t}$$
>
> Tension accumulation with relaxation:
> $$\boxed{\overline{T}_t = \gamma \cdot \overline{T}_{t-1} + T_t, \quad \gamma \in [0, 1]}$$

### 4.1 Flashover (Loss-of-Controllability Threshold)

General accumulator:

$$\Phi(t) = \gamma_\Phi \cdot \Phi(t-1) + \alpha_T \cdot \overline{T}_t + \alpha_{CC} \cdot CC_t$$

Operational condition:

$$\Phi(t) < \Phi_{critical}$$

When $\Phi(t) \geq \Phi_{critical}$, the system has entered **flashover** — safety infrastructure can no longer compensate for base model degradation.

---

## 5. Delay Dynamics (Optional Instance)

If the system is causally constrained with delay τ, the toy model DDE:

$$\frac{d^2 x}{dt^2} + 2\zeta\omega \frac{dx}{dt} + \omega^2 x(t - \tau) = u(t)$$

Then the natural control cost:

$$CC = \int \|u(t)\|^2 \, dt$$

**Diagnostic thesis (not ontological):**

$$\tau \uparrow \implies \text{maintaining stability requires greater } CC$$

---

## 6. Cross-Domain Instantiation

The UDM is **scale-invariant** — the same definitions of CC, T apply across domains:

| Variable | Factory (C.E.R.A.) | Galaxy (Macro) | Black Hole (Thermo) |
|----------|-------------------|----------------|---------------------|
| State (x) | Recipe / resources / process | Positions / velocities | Mass M, entropy S |
| Model (M) | Intent + process model | Baryonic model | BH (Schwarzschild/Kerr) |
| Delay (τ) | Deliveries / inertia | r/c (proxy) | horizon effects (proxy) |
| Cost (CC) | Purchases / energy / overtime | "missing contribution" to v² | ΔS_bit, CC_E |
| Tension (T) | Constraint violations / brittleness | baryon profile fragility | relative fragility 2ΔM/M |
| Accumulator (Φ) | Fatigue / tech debt | history and structure | accumulation of S changes |

### 6.1 Galaxy Rotation Curves

$$y(r) = v_{obs}^2(r), \quad \hat{y}(r;\theta) = v_{bar}^2(r;\theta)$$

Simplest additive compensation:

$$CC(r) = \max(0, v_{obs}^2(r) - v_{bar}^2(r;\theta))$$

### 6.2 Black Holes (Thermodynamics)

For accretion step ΔM and BH entropy in bits $S_{bit}$:

$$CC_{bit} = \Delta S_{bit}$$

Minimum energetic cost in the spirit of Landauer (with $T_H$ as Hawking temperature):

$$CC_E = \Delta S_{bit} \cdot k_B T_H \ln 2$$

### 6.3 CPHS / C.E.R.A. Systems

Control u(t) is real action (purchase, correction, process constraint):

$$CC = \min_u \left\{ \int \|u(t)\|^2 dt : \mathcal{L} \leq \varepsilon \right\}$$

---

## 7. Minimal Definitions (For Citation)

$$\boxed{CC_t(\theta) = \min_\phi \{ J_t(\phi) : \mathcal{L}_t(\theta, \phi) \leq \varepsilon_t \}, \quad T_t^{rel}(\theta) = \|\nabla_\theta \log(CC_t(\theta) + \delta)\|}$$

$$\boxed{\overline{CC}_t = \overline{CC}_{t-1} + CC_t, \quad \overline{T}_t = \gamma \cdot \overline{T}_{t-1} + T_t}$$

---

*Source: ActProof UDM v1.0 — Unified Diagnostic Model for Autonomous Systems*
*Author: Paweł Łuczak, Sokaris Oprogramowanie*
