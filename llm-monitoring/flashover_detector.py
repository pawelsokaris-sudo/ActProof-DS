"""
ActProof — Flashover Detector

State machine implementation: NORMAL → WARN → SURVIVAL → FLASHOVER
With Φ(t) accumulator for predictive detection.
"""

from enum import Enum
from dataclasses import dataclass
from typing import Optional


class SystemState(Enum):
    NORMAL = "NORMAL"
    WARN = "WARN"
    SURVIVAL = "SURVIVAL"
    FLASHOVER = "FLASHOVER"
    RECOVERY = "RECOVERY"


@dataclass
class FlashoverThresholds:
    """Configurable thresholds for state transitions."""
    # NORMAL → WARN
    z_cc_warn: float = 3.0
    warn_sustain_steps: int = 5       # consecutive steps above threshold

    # WARN → SURVIVAL
    z_t_survival: float = 2.0
    mci_sce_survival: float = 0.35

    # SURVIVAL → FLASHOVER
    phi_critical: float = 10.0
    phi_pre_flashover_ratio: float = 0.85

    # Φ accumulator parameters
    gamma_phi: float = 0.95           # decay factor
    alpha_t: float = 0.3             # tension weight
    alpha_cc: float = 0.7            # CC weight


@dataclass
class DetectorReading:
    """Input to the flashover detector at each timestep."""
    cc_ema: float
    z_cc: Optional[float]
    tension: Optional[float] = None
    z_t: Optional[float] = None
    mci_sce: Optional[float] = None


@dataclass
class DetectorOutput:
    """Output of the flashover detector at each timestep."""
    state: SystemState
    phi: float
    steps_in_warn: int
    message: str


class FlashoverDetector:
    """
    Implements the ActProof flashover detection state machine.

    Tracks system state and the flashover accumulator Φ(t).

    Usage:
        detector = FlashoverDetector()
        for reading in stream:
            result = detector.update(reading)
            if result.state == SystemState.FLASHOVER:
                trigger_alert(result)
    """

    def __init__(self, thresholds: Optional[FlashoverThresholds] = None):
        self.thresholds = thresholds or FlashoverThresholds()
        self._state = SystemState.NORMAL
        self._phi = 0.0
        self._warn_counter = 0
        self._step = 0

    def update(self, reading: DetectorReading) -> DetectorOutput:
        """
        Process one timestep and return current state.

        Args:
            reading: Current measurements (CC, tension, MCI)

        Returns:
            DetectorOutput with state, Φ(t), and diagnostic message
        """
        self._step += 1
        th = self.thresholds

        # Update Φ accumulator
        cc_contrib = th.alpha_cc * reading.cc_ema if reading.cc_ema else 0
        t_contrib = th.alpha_t * reading.tension if reading.tension else 0
        self._phi = th.gamma_phi * self._phi + cc_contrib + t_contrib

        # State transitions
        prev_state = self._state
        msg = ""

        if self._state == SystemState.NORMAL:
            if reading.z_cc is not None and reading.z_cc >= th.z_cc_warn:
                self._warn_counter += 1
                if self._warn_counter >= th.warn_sustain_steps:
                    self._state = SystemState.WARN
                    msg = f"→ WARN: z_CC={reading.z_cc:.2f} sustained for {self._warn_counter} steps"
            else:
                self._warn_counter = 0

        elif self._state == SystemState.WARN:
            # Check for escalation to SURVIVAL
            z_t_ok = reading.z_t is not None and reading.z_t >= th.z_t_survival
            mci_ok = reading.mci_sce is not None and reading.mci_sce >= th.mci_sce_survival

            if z_t_ok and mci_ok:
                self._state = SystemState.SURVIVAL
                msg = f"→ SURVIVAL: z_T={reading.z_t:.2f}, MCI(SCE)={reading.mci_sce:.2f}"
            elif reading.z_cc is not None and reading.z_cc < th.z_cc_warn:
                # De-escalate
                self._warn_counter = 0
                self._state = SystemState.NORMAL
                msg = "→ NORMAL: CC normalized"

        elif self._state == SystemState.SURVIVAL:
            # Check for FLASHOVER
            if self._phi >= th.phi_critical:
                self._state = SystemState.FLASHOVER
                msg = f"→ FLASHOVER: Φ={self._phi:.2f} ≥ Φ_crit={th.phi_critical:.2f}"
            elif self._phi >= th.phi_critical * th.phi_pre_flashover_ratio:
                msg = f"⚠ PRE-FLASHOVER: Φ={self._phi:.2f} ({self._phi/th.phi_critical*100:.0f}% of Φ_crit)"
            # De-escalate if conditions improve
            elif (reading.z_t is not None and reading.z_t < th.z_t_survival
                  and reading.mci_sce is not None and reading.mci_sce < th.mci_sce_survival):
                self._state = SystemState.WARN
                msg = "→ WARN: T and MCI decreased"

        elif self._state == SystemState.FLASHOVER:
            # Only manual intervention or CC collapse triggers recovery
            if reading.z_cc is not None and reading.z_cc < th.z_cc_warn:
                self._state = SystemState.RECOVERY
                msg = "→ RECOVERY: CC dropped after intervention"

        elif self._state == SystemState.RECOVERY:
            if reading.z_cc is not None and reading.z_cc < 1.0:
                self._state = SystemState.NORMAL
                self._phi = 0.0
                self._warn_counter = 0
                msg = "→ NORMAL: full recovery"

        if not msg:
            msg = f"{self._state.value}: Φ={self._phi:.2f}, z_CC={reading.z_cc or 0:.2f}"

        return DetectorOutput(
            state=self._state,
            phi=self._phi,
            steps_in_warn=self._warn_counter,
            message=msg,
        )

    @property
    def state(self) -> SystemState:
        return self._state

    @property
    def phi(self) -> float:
        return self._phi

    def reset(self):
        """Hard reset — use after manual intervention."""
        self._state = SystemState.NORMAL
        self._phi = 0.0
        self._warn_counter = 0
