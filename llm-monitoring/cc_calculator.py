"""
ActProof — Control Cost Calculator (CCC Implementation)

Computes the Compensator Cost Cascade metric from observable production signals.
No access to model internals required.
"""

import math
from collections import deque
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class CCWeights:
    """Weights for CC formula components. Calibrate per deployment."""
    policy_hits: float = 0.30
    retries: float = 0.25
    edit_ratio: float = 0.20
    latency: float = 0.10
    semantic_dist: float = 0.15


@dataclass
class CCReading:
    """Single CC measurement with component breakdown."""
    timestamp: float
    cc_total: float
    policy_hits: float
    retries: float
    edit_ratio: float
    latency_overhead_ms: float
    semantic_distance: float


class ControlCostCalculator:
    """
    Computes CC(t) from observable signals in a production LLM pipeline.

    Usage:
        cc = ControlCostCalculator()
        score = cc.compute(policy_hits=2, retries=1, edit_ratio=0.15,
                           latency_overhead_ms=340, semantic_distance=0.08)
    """

    def __init__(
        self,
        weights: Optional[CCWeights] = None,
        baseline_window: int = 1440,  # 24h at 1 reading/min
        ema_alpha: float = 0.1,
    ):
        self.weights = weights or CCWeights()
        self.baseline_window = baseline_window
        self.ema_alpha = ema_alpha

        self._history: deque[float] = deque(maxlen=baseline_window)
        self._ema: Optional[float] = None

    def compute(
        self,
        policy_hits: int = 0,
        retries: int = 0,
        edit_ratio: float = 0.0,
        latency_overhead_ms: float = 0.0,
        semantic_distance: float = 0.0,
    ) -> float:
        """
        Compute CC for a single turn/request.

        Args:
            policy_hits: Number of safety policy filter activations
            retries: Number of generation retries
            edit_ratio: Fraction of output modified by safety rewriting (0.0-1.0)
            latency_overhead_ms: Additional latency from safety processing (ms)
            semantic_distance: Cosine distance between draft and final output (0.0-1.0)

        Returns:
            CC score (unbounded positive float)
        """
        w = self.weights

        # Normalize latency to 0-1 scale (assuming 1000ms as reference)
        latency_norm = min(latency_overhead_ms / 1000.0, 5.0)

        cc = (
            w.policy_hits * policy_hits
            + w.retries * retries
            + w.edit_ratio * edit_ratio
            + w.latency * latency_norm
            + w.semantic_dist * semantic_distance
        )

        self._update_baseline(cc)
        return cc

    def _update_baseline(self, cc: float):
        """Update rolling baseline and EMA."""
        self._history.append(cc)
        if self._ema is None:
            self._ema = cc
        else:
            self._ema = self.ema_alpha * cc + (1 - self.ema_alpha) * self._ema

    @property
    def ema(self) -> Optional[float]:
        """Current exponential moving average of CC."""
        return self._ema

    @property
    def baseline_mean(self) -> Optional[float]:
        """Rolling baseline mean."""
        if not self._history:
            return None
        return sum(self._history) / len(self._history)

    @property
    def baseline_std(self) -> Optional[float]:
        """Rolling baseline standard deviation."""
        if len(self._history) < 2:
            return None
        mean = self.baseline_mean
        variance = sum((x - mean) ** 2 for x in self._history) / (len(self._history) - 1)
        return math.sqrt(variance)

    @property
    def z_score(self) -> Optional[float]:
        """Current z-score of EMA relative to baseline."""
        if self._ema is None or self.baseline_std is None or self.baseline_std < 1e-9:
            return None
        return (self._ema - self.baseline_mean) / self.baseline_std


class TensionEstimator:
    """
    Estimates system tension T(t) — sensitivity of CC to small perturbations.

    Feed pairs of (prompt_similarity, cc_difference) from near-duplicate requests.
    High tension = small input changes cause large CC changes = system is brittle.
    """

    def __init__(self, window: int = 100, ema_alpha: float = 0.1):
        self._ratios: deque[float] = deque(maxlen=window)
        self._ema: Optional[float] = None
        self._ema_alpha = ema_alpha

    def observe(self, prompt_distance: float, cc_difference: float) -> float:
        """
        Record a perturbation-response observation.

        Args:
            prompt_distance: How different the two prompts were (small positive float)
            cc_difference: Absolute difference in CC between the two (positive float)

        Returns:
            Current tension estimate
        """
        if prompt_distance < 1e-9:
            return self._ema or 0.0

        ratio = cc_difference / prompt_distance
        self._ratios.append(ratio)

        if self._ema is None:
            self._ema = ratio
        else:
            self._ema = self._ema_alpha * ratio + (1 - self._ema_alpha) * self._ema

        return self._ema

    @property
    def tension(self) -> Optional[float]:
        return self._ema


class MCITracker:
    """
    Tracks Module Coupling Index — which compensator absorbs the most cost.

    Rising MCI(DG→SCE) means the safety rewriting module handles an increasing
    share of total compensation = base model degrading, safety masking it.
    """

    def __init__(self, ema_alpha: float = 0.05):
        self._ema_alpha = ema_alpha
        self._mci: dict[str, Optional[float]] = {}

    def observe(self, compensator_costs: dict[str, float]) -> dict[str, float]:
        """
        Record cost distribution across compensators.

        Args:
            compensator_costs: e.g. {"retry": 0.3, "sce_rewrite": 1.2, "scope_cap": 0.1}

        Returns:
            Current MCI (fraction) per compensator
        """
        total = sum(compensator_costs.values())
        if total < 1e-9:
            return {k: 0.0 for k in compensator_costs}

        fractions = {k: v / total for k, v in compensator_costs.items()}

        for k, frac in fractions.items():
            if k not in self._mci or self._mci[k] is None:
                self._mci[k] = frac
            else:
                self._mci[k] = self._ema_alpha * frac + (1 - self._ema_alpha) * self._mci[k]

        return {k: v for k, v in self._mci.items() if v is not None}


if __name__ == "__main__":
    # Demo usage
    calc = ControlCostCalculator()

    # Simulate 10 requests with increasing compensation
    samples = [
        {"policy_hits": 0, "retries": 0, "edit_ratio": 0.02, "latency_overhead_ms": 50, "semantic_distance": 0.01},
        {"policy_hits": 0, "retries": 0, "edit_ratio": 0.03, "latency_overhead_ms": 55, "semantic_distance": 0.01},
        {"policy_hits": 1, "retries": 0, "edit_ratio": 0.05, "latency_overhead_ms": 80, "semantic_distance": 0.03},
        {"policy_hits": 1, "retries": 1, "edit_ratio": 0.10, "latency_overhead_ms": 150, "semantic_distance": 0.05},
        {"policy_hits": 2, "retries": 1, "edit_ratio": 0.15, "latency_overhead_ms": 300, "semantic_distance": 0.08},
        {"policy_hits": 2, "retries": 2, "edit_ratio": 0.25, "latency_overhead_ms": 500, "semantic_distance": 0.12},
        {"policy_hits": 3, "retries": 2, "edit_ratio": 0.35, "latency_overhead_ms": 700, "semantic_distance": 0.18},
        {"policy_hits": 4, "retries": 3, "edit_ratio": 0.50, "latency_overhead_ms": 1200, "semantic_distance": 0.25},
        {"policy_hits": 5, "retries": 4, "edit_ratio": 0.70, "latency_overhead_ms": 2000, "semantic_distance": 0.40},
        {"policy_hits": 7, "retries": 5, "edit_ratio": 0.90, "latency_overhead_ms": 3500, "semantic_distance": 0.60},
    ]

    print("ActProof CC Calculator — Demo")
    print("=" * 60)
    for i, s in enumerate(samples):
        cc = calc.compute(**s)
        z = calc.z_score
        z_str = f"{z:+.2f}" if z is not None else "n/a"
        print(f"  Turn {i+1:2d}: CC = {cc:.3f}  EMA = {calc.ema:.3f}  z = {z_str}")
    print("=" * 60)
