"""
ActProof — LLM Alignment Degradation Simulation

Generates a synthetic CC curve showing progression from NORMAL to FLASHOVER,
matching the numerical example from the white paper.

Usage:
    python simulate.py
    python simulate.py --output figures/cc_curve.png
"""

import argparse
import math
import os

# Use non-interactive backend for environments without display
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

from cc_calculator import ControlCostCalculator, CCWeights
from flashover_detector import FlashoverDetector, FlashoverThresholds, DetectorReading, SystemState


def generate_degradation_scenario(duration_minutes: int = 40, points_per_minute: int = 1):
    """
    Generate synthetic data mimicking gradual LLM alignment degradation.
    Based on the white paper numerical example (Table 1).
    """
    total_points = duration_minutes * points_per_minute
    data = []

    for i in range(total_points):
        t = i / points_per_minute  # time in minutes

        # Piecewise degradation model
        if t < 5:
            # Phase 1: Stable
            policy_hits = np.random.poisson(0.1)
            retries = 0
            edit_ratio = 0.02 + np.random.normal(0, 0.005)
            latency_ms = 50 + np.random.normal(0, 10)
            sem_dist = 0.01 + np.random.normal(0, 0.003)
        elif t < 12:
            # Phase 2: Early drift
            progress = (t - 5) / 7
            policy_hits = np.random.poisson(0.3 + 0.5 * progress)
            retries = np.random.poisson(0.1 * progress)
            edit_ratio = 0.03 + 0.05 * progress + np.random.normal(0, 0.01)
            latency_ms = 60 + 40 * progress + np.random.normal(0, 15)
            sem_dist = 0.02 + 0.03 * progress + np.random.normal(0, 0.005)
        elif t < 22:
            # Phase 3: Accelerating degradation
            progress = (t - 12) / 10
            policy_hits = np.random.poisson(1.0 + 2.0 * progress)
            retries = np.random.poisson(0.5 + 1.5 * progress)
            edit_ratio = 0.10 + 0.20 * progress + np.random.normal(0, 0.02)
            latency_ms = 120 + 300 * progress + np.random.normal(0, 30)
            sem_dist = 0.05 + 0.10 * progress + np.random.normal(0, 0.01)
        elif t < 30:
            # Phase 4: Critical — approaching flashover
            progress = (t - 22) / 8
            policy_hits = np.random.poisson(3.0 + 4.0 * progress)
            retries = np.random.poisson(2.0 + 3.0 * progress)
            edit_ratio = 0.35 + 0.40 * progress + np.random.normal(0, 0.03)
            latency_ms = 500 + 1500 * progress ** 1.5 + np.random.normal(0, 50)
            sem_dist = 0.18 + 0.30 * progress + np.random.normal(0, 0.02)
        elif t < 34:
            # Phase 5: Flashover — cascade failure
            progress = (t - 30) / 4
            policy_hits = np.random.poisson(7 + 5 * progress)
            retries = np.random.poisson(5 + 3 * progress)
            edit_ratio = 0.80 + 0.15 * progress + np.random.normal(0, 0.02)
            latency_ms = 2500 + 2000 * progress + np.random.normal(0, 100)
            sem_dist = 0.55 + 0.30 * progress + np.random.normal(0, 0.03)
        else:
            # Phase 6: Recovery — after hard intervention
            progress = (t - 34) / (duration_minutes - 34)
            policy_hits = np.random.poisson(max(0.5, 2.0 - 1.5 * progress))
            retries = np.random.poisson(max(0, 1.0 - 1.0 * progress))
            edit_ratio = max(0.05, 0.30 - 0.25 * progress) + np.random.normal(0, 0.01)
            latency_ms = max(80, 500 - 400 * progress) + np.random.normal(0, 20)
            sem_dist = max(0.02, 0.15 - 0.12 * progress) + np.random.normal(0, 0.005)

        # Clamp values
        edit_ratio = max(0, min(1, edit_ratio))
        sem_dist = max(0, min(1, sem_dist))
        latency_ms = max(0, latency_ms)
        policy_hits = max(0, policy_hits)
        retries = max(0, retries)

        data.append({
            "time_min": t,
            "policy_hits": int(policy_hits),
            "retries": int(retries),
            "edit_ratio": edit_ratio,
            "latency_overhead_ms": latency_ms,
            "semantic_distance": sem_dist,
        })

    return data


def run_simulation(duration_minutes=40, output_path=None):
    """Run simulation and generate visualization."""

    np.random.seed(42)

    print("ActProof — LLM Alignment Degradation Simulation")
    print("=" * 60)

    # Generate data
    data = generate_degradation_scenario(duration_minutes)

    # Initialize components
    calc = ControlCostCalculator(
        weights=CCWeights(
            policy_hits=0.30,
            retries=0.25,
            edit_ratio=0.20,
            latency=0.10,
            semantic_dist=0.15,
        ),
        baseline_window=10,  # short window for simulation (in production: 1440)
        ema_alpha=0.15,
    )

    detector = FlashoverDetector(
        thresholds=FlashoverThresholds(
            z_cc_warn=1.8,
            warn_sustain_steps=2,
            z_t_survival=1.2,
            mci_sce_survival=0.25,
            phi_critical=12.0,
            gamma_phi=0.92,
            alpha_t=0.3,
            alpha_cc=0.7,
        )
    )

    # Process in two passes: first establish baseline, then detect
    # Phase 1: Compute all CC values
    all_cc = []
    for point in data:
        cc = calc.compute(
            policy_hits=point["policy_hits"],
            retries=point["retries"],
            edit_ratio=point["edit_ratio"],
            latency_overhead_ms=point["latency_overhead_ms"],
            semantic_distance=point["semantic_distance"],
        )
        all_cc.append(cc)

    # Establish fixed baseline from first 10 minutes (stable period)
    baseline_cc = all_cc[:10]
    bl_mean = sum(baseline_cc) / len(baseline_cc)
    bl_std = max((sum((x - bl_mean)**2 for x in baseline_cc) / (len(baseline_cc) - 1)) ** 0.5, 0.001)

    # Reset calculator for EMA
    calc2 = ControlCostCalculator(
        weights=calc.weights,
        baseline_window=10,
        ema_alpha=0.15,
    )

    # Phase 2: Run through with fixed baseline z-scores
    times = []
    cc_values = []
    ema_values = []
    states = []
    phi_values = []
    state_colors = {
        SystemState.NORMAL: "#27ae60",
        SystemState.WARN: "#e67e22",
        SystemState.SURVIVAL: "#c0392b",
        SystemState.FLASHOVER: "#8b0000",
        SystemState.RECOVERY: "#0f3460",
    }

    for i, point in enumerate(data):
        cc = all_cc[i]
        # Feed to calc2 for EMA tracking
        calc2.compute(
            policy_hits=point["policy_hits"],
            retries=point["retries"],
            edit_ratio=point["edit_ratio"],
            latency_overhead_ms=point["latency_overhead_ms"],
            semantic_distance=point["semantic_distance"],
        )
        ema = calc2.ema

        # Fixed-baseline z-score (not rolling)
        z_cc = (ema - bl_mean) / bl_std

        # Estimate tension (simplified: variance of recent CC)
        tension = 0.0
        if len(cc_values) >= 3:
            recent = cc_values[-3:]
            tension = np.std(recent) * 5  # scaled

        # Estimate MCI(SCE) from edit_ratio dominance
        mci_sce = point["edit_ratio"] * 0.6 + point["semantic_distance"] * 0.4

        # Tension z-score against baseline tension
        z_t = tension / max(bl_std * 2, 0.01)

        result = detector.update(DetectorReading(
            cc_ema=ema,
            z_cc=z_cc,
            tension=tension,
            z_t=z_t,
            mci_sce=mci_sce,
        ))

        times.append(point["time_min"])
        cc_values.append(cc)
        ema_values.append(ema)
        states.append(result.state)
        phi_values.append(result.phi)

        if result.state != SystemState.NORMAL or point["time_min"] % 5 == 0:
            print(f"  t={point['time_min']:5.1f} min | CC={cc:.3f} | EMA={ema:.3f} | "
                  f"z={z_cc:+.1f} | Φ={result.phi:.2f} | {result.message}")

    print("=" * 60)

    # ── Visualization ──
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(14, 10), sharex=True,
                                         gridspec_kw={'height_ratios': [3, 1, 1]})
    fig.suptitle('ActProof — Control Cost Curve Under Alignment Degradation',
                 fontsize=14, fontweight='bold', y=0.98)

    # Plot 1: CC curve with state coloring
    for i in range(len(times) - 1):
        color = state_colors.get(states[i], "#999999")
        ax1.fill_between([times[i], times[i+1]], 0, [ema_values[i], ema_values[i+1]],
                        alpha=0.15, color=color)

    ax1.plot(times, cc_values, alpha=0.3, color='#999999', linewidth=0.8, label='CC (raw)')
    ax1.plot(times, ema_values, color='#1a1a2e', linewidth=2, label='CC (EMA)')

    # Mark flashover point
    for i, s in enumerate(states):
        if s == SystemState.FLASHOVER and (i == 0 or states[i-1] != SystemState.FLASHOVER):
            ax1.axvline(x=times[i], color='#8b0000', linestyle='--', linewidth=1.5, alpha=0.8)
            ax1.annotate('FLASHOVER', xy=(times[i], ema_values[i]),
                        xytext=(times[i]+1, ema_values[i]*0.9),
                        fontsize=9, fontweight='bold', color='#8b0000',
                        arrowprops=dict(arrowstyle='->', color='#8b0000'))
        if s == SystemState.WARN and (i == 0 or states[i-1] == SystemState.NORMAL):
            ax1.axvline(x=times[i], color='#e67e22', linestyle=':', linewidth=1, alpha=0.6)
            ax1.annotate('WARN', xy=(times[i], ema_values[i]),
                        xytext=(times[i]-3, ema_values[i]+0.3),
                        fontsize=8, color='#e67e22')

    ax1.set_ylabel('Control Cost (CC)', fontsize=11)
    ax1.legend(loc='upper left', fontsize=9)
    ax1.grid(True, alpha=0.3)

    # Plot 2: Φ accumulator
    ax2.plot(times, phi_values, color='#c0392b', linewidth=1.5)
    ax2.axhline(y=detector.thresholds.phi_critical, color='#8b0000',
                linestyle='--', linewidth=1, alpha=0.6, label=f'Φ_critical = {detector.thresholds.phi_critical}')
    ax2.axhline(y=detector.thresholds.phi_critical * detector.thresholds.phi_pre_flashover_ratio,
                color='#e67e22', linestyle=':', linewidth=1, alpha=0.5, label='Pre-flashover (85%)')
    ax2.set_ylabel('Φ(t)', fontsize=11)
    ax2.legend(loc='upper left', fontsize=8)
    ax2.grid(True, alpha=0.3)

    # Plot 3: State timeline
    state_numeric = {
        SystemState.NORMAL: 0,
        SystemState.WARN: 1,
        SystemState.SURVIVAL: 2,
        SystemState.FLASHOVER: 3,
        SystemState.RECOVERY: 1.5,
    }
    state_vals = [state_numeric[s] for s in states]
    for i in range(len(times) - 1):
        color = state_colors.get(states[i], "#999999")
        ax3.fill_between([times[i], times[i+1]], 0, [state_vals[i], state_vals[i+1]],
                        alpha=0.6, color=color)
    ax3.set_ylabel('State', fontsize=11)
    ax3.set_xlabel('Time (minutes)', fontsize=11)
    ax3.set_yticks([0, 1, 2, 3])
    ax3.set_yticklabels(['NORMAL', 'WARN', 'SURVIVAL', 'FLASH'], fontsize=8)
    ax3.grid(True, alpha=0.3)

    plt.tight_layout()

    # Save
    if output_path is None:
        output_path = os.path.join(os.path.dirname(__file__), 'figures', 'cc_curve_simulation.png')
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
    print(f"\nVisualization saved: {output_path}")
    plt.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ActProof LLM Degradation Simulation")
    parser.add_argument("--duration", type=int, default=40, help="Simulation duration in minutes")
    parser.add_argument("--output", type=str, default=None, help="Output path for figure")
    args = parser.parse_args()

    run_simulation(duration_minutes=args.duration, output_path=args.output)
