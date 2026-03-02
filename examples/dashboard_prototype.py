"""
ActProof — Grafana-Compatible Metrics Exporter (Dashboard Prototype)

Exposes ActProof diagnostic metrics via a Prometheus-compatible /metrics endpoint.
Uses only Python standard library (http.server) — no extra dependencies.

Usage:
    # Start the exporter with built-in synthetic data simulation
    python dashboard_prototype.py

    # Custom port and update interval
    python dashboard_prototype.py --port 9120 --interval 5

    # Then configure Prometheus to scrape:
    #   - job_name: 'actproof'
    #     static_configs:
    #       - targets: ['localhost:9120']

    # Import in Grafana → Add Prometheus data source → Dashboard

Architecture:
    ┌──────────────┐     ┌───────────────┐     ┌──────────────────┐
    │  LLM Pipeline│────▶│ ActProof Core  │────▶│ /metrics (Prom.) │
    │  (simulated) │     │ CC, T, Φ, MCI  │     │  :9120           │
    └──────────────┘     └───────────────┘     └──────────────────┘
                                                        │
                                                 ┌──────▼──────┐
                                                 │  Prometheus  │
                                                 │  → Grafana   │
                                                 └──────────────┘
"""

import argparse
import math
import random
import sys
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler

# Add parent paths so we can import from llm-monitoring
sys.path.insert(0, __import__("os").path.join(__import__("os").path.dirname(__file__), "..", "llm-monitoring"))

from cc_calculator import ControlCostCalculator, CCWeights, TensionEstimator, MCITracker
from flashover_detector import FlashoverDetector, FlashoverThresholds, DetectorReading, SystemState


# ─── Prometheus Exposition Format Helpers ───────────────────────────────────

def _format_gauge(name: str, help_text: str, value: float, labels: dict = None) -> str:
    """Format a single Prometheus gauge metric."""
    lines = [
        f"# HELP {name} {help_text}",
        f"# TYPE {name} gauge",
    ]
    label_str = ""
    if labels:
        pairs = ",".join(f'{k}="{v}"' for k, v in labels.items())
        label_str = f"{{{pairs}}}"
    lines.append(f"{name}{label_str} {value:.6f}")
    return "\n".join(lines)


def _format_counter(name: str, help_text: str, value: int, labels: dict = None) -> str:
    """Format a single Prometheus counter metric."""
    lines = [
        f"# HELP {name} {help_text}",
        f"# TYPE {name} counter",
    ]
    label_str = ""
    if labels:
        pairs = ",".join(f'{k}="{v}"' for k, v in labels.items())
        label_str = f"{{{pairs}}}"
    lines.append(f"{name}{label_str} {value}")
    return "\n".join(lines)


def _format_info(name: str, help_text: str, labels: dict) -> str:
    """Format a Prometheus info metric (label-only gauge=1)."""
    lines = [
        f"# HELP {name} {help_text}",
        f"# TYPE {name} gauge",
    ]
    pairs = ",".join(f'{k}="{v}"' for k, v in labels.items())
    lines.append(f"{name}{{{pairs}}} 1")
    return "\n".join(lines)


# ─── Metrics Store ──────────────────────────────────────────────────────────

class ActProofMetrics:
    """
    Thread-safe metrics store that integrates ActProof components and
    renders Prometheus exposition format.
    """

    def __init__(self):
        self._lock = threading.Lock()

        # ActProof components
        self.calculator = ControlCostCalculator(
            weights=CCWeights(
                policy_hits=0.30,
                retries=0.25,
                edit_ratio=0.20,
                latency=0.10,
                semantic_dist=0.15,
            ),
            baseline_window=1440,
            ema_alpha=0.1,
        )
        self.tension = TensionEstimator(window=100, ema_alpha=0.1)
        self.mci = MCITracker(ema_alpha=0.05)
        self.detector = FlashoverDetector(thresholds=FlashoverThresholds())

        # Latest readings
        self._cc_raw = 0.0
        self._cc_ema = 0.0
        self._z_cc = 0.0
        self._tension_val = 0.0
        self._phi = 0.0
        self._state = SystemState.NORMAL
        self._mci_values: dict[str, float] = {}
        self._total_updates = 0
        self._state_transitions = 0
        self._last_update_ts = 0.0

        # Component-level readings (for per-component gauges)
        self._policy_hits = 0
        self._retries = 0
        self._edit_ratio = 0.0
        self._latency_ms = 0.0
        self._semantic_dist = 0.0

    def update(
        self,
        policy_hits: int = 0,
        retries: int = 0,
        edit_ratio: float = 0.0,
        latency_overhead_ms: float = 0.0,
        semantic_distance: float = 0.0,
    ):
        """Ingest one observation from the LLM pipeline."""
        with self._lock:
            # Store raw component values
            self._policy_hits = policy_hits
            self._retries = retries
            self._edit_ratio = edit_ratio
            self._latency_ms = latency_overhead_ms
            self._semantic_dist = semantic_distance

            # CC calculation
            cc = self.calculator.compute(
                policy_hits=policy_hits,
                retries=retries,
                edit_ratio=edit_ratio,
                latency_overhead_ms=latency_overhead_ms,
                semantic_distance=semantic_distance,
            )
            self._cc_raw = cc
            self._cc_ema = self.calculator.ema or 0.0
            self._z_cc = self.calculator.z_score or 0.0

            # Tension — approximate from prompt perturbation
            prompt_dist = 0.05 + random.gauss(0, 0.01)  # simulated
            self._tension_val = self.tension.observe(abs(prompt_dist), abs(cc - self._cc_ema))

            # MCI
            compensator_costs = {
                "retry": retries * 0.25,
                "sce_rewrite": edit_ratio * 0.5 + semantic_distance * 0.3,
                "scope_cap": policy_hits * 0.15,
                "latency_gate": min(latency_overhead_ms / 1000, 1.0) * 0.1,
            }
            self._mci_values = self.mci.observe(compensator_costs)

            # Flashover detection
            prev_state = self._state
            result = self.detector.update(DetectorReading(
                cc_ema=self._cc_ema,
                z_cc=self._z_cc,
                tension=self._tension_val,
                z_t=self._tension_val / max(0.01, self.calculator.baseline_std or 0.01),
                mci_sce=self._mci_values.get("sce_rewrite", 0.0),
            ))
            self._phi = result.phi
            self._state = result.state
            self._total_updates += 1
            self._last_update_ts = time.time()

            if result.state != prev_state:
                self._state_transitions += 1

    def render_metrics(self) -> str:
        """Render all metrics in Prometheus exposition format."""
        with self._lock:
            sections = []

            # ── Core CC metrics ──
            sections.append(_format_gauge(
                "actproof_cc_raw",
                "Raw Control Cost for the latest turn",
                self._cc_raw,
            ))
            sections.append(_format_gauge(
                "actproof_cc_ema",
                "Exponential Moving Average of Control Cost",
                self._cc_ema,
            ))
            sections.append(_format_gauge(
                "actproof_cc_zscore",
                "Z-score of CC EMA relative to rolling baseline",
                self._z_cc,
            ))
            sections.append(_format_gauge(
                "actproof_cc_baseline_mean",
                "Rolling baseline mean of CC",
                self.calculator.baseline_mean or 0.0,
            ))
            sections.append(_format_gauge(
                "actproof_cc_baseline_std",
                "Rolling baseline standard deviation of CC",
                self.calculator.baseline_std or 0.0,
            ))

            # ── CC component breakdown ──
            sections.append(_format_gauge(
                "actproof_cc_component",
                "Individual CC component value",
                float(self._policy_hits),
                {"component": "policy_hits"},
            ))
            sections.append(_format_gauge(
                "actproof_cc_component",
                "Individual CC component value",
                float(self._retries),
                {"component": "retries"},
            ))
            sections.append(_format_gauge(
                "actproof_cc_component",
                "Individual CC component value",
                self._edit_ratio,
                {"component": "edit_ratio"},
            ))
            sections.append(_format_gauge(
                "actproof_cc_component",
                "Individual CC component value",
                self._latency_ms,
                {"component": "latency_overhead_ms"},
            ))
            sections.append(_format_gauge(
                "actproof_cc_component",
                "Individual CC component value",
                self._semantic_dist,
                {"component": "semantic_distance"},
            ))

            # ── Tension ──
            sections.append(_format_gauge(
                "actproof_tension",
                "System tension T(t) — sensitivity of CC to input perturbations",
                self._tension_val,
            ))

            # ── Flashover accumulator ──
            sections.append(_format_gauge(
                "actproof_phi",
                "Flashover accumulator Phi(t)",
                self._phi,
            ))
            sections.append(_format_gauge(
                "actproof_phi_critical",
                "Critical threshold for Phi (flashover trigger)",
                self.detector.thresholds.phi_critical,
            ))
            sections.append(_format_gauge(
                "actproof_phi_ratio",
                "Current Phi as fraction of critical threshold (1.0 = flashover)",
                self._phi / max(self.detector.thresholds.phi_critical, 1e-9),
            ))

            # ── State ──
            state_numeric = {
                SystemState.NORMAL: 0,
                SystemState.WARN: 1,
                SystemState.SURVIVAL: 2,
                SystemState.FLASHOVER: 3,
                SystemState.RECOVERY: 4,
            }
            sections.append(_format_gauge(
                "actproof_state",
                "Current system state (0=NORMAL, 1=WARN, 2=SURVIVAL, 3=FLASHOVER, 4=RECOVERY)",
                float(state_numeric.get(self._state, 0)),
            ))
            sections.append(_format_info(
                "actproof_state_info",
                "Current system state as label",
                {"state": self._state.value},
            ))

            # ── MCI per compensator ──
            for comp, val in self._mci_values.items():
                sections.append(_format_gauge(
                    "actproof_mci",
                    "Module Coupling Index per compensator",
                    val,
                    {"compensator": comp},
                ))

            # ── Operational counters ──
            sections.append(_format_counter(
                "actproof_updates_total",
                "Total number of CC updates processed",
                self._total_updates,
            ))
            sections.append(_format_counter(
                "actproof_state_transitions_total",
                "Total number of state transitions",
                self._state_transitions,
            ))
            sections.append(_format_gauge(
                "actproof_last_update_timestamp",
                "Unix timestamp of last metrics update",
                self._last_update_ts,
            ))

            return "\n\n".join(sections) + "\n"


# ─── HTTP Handler ───────────────────────────────────────────────────────────

class MetricsHandler(BaseHTTPRequestHandler):
    """Serves /metrics in Prometheus exposition format."""

    metrics_store: ActProofMetrics = None  # set by server setup

    def do_GET(self):
        if self.path == "/metrics":
            body = self.metrics_store.render_metrics().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        elif self.path == "/" or self.path == "/health":
            body = b'{"status":"ok","service":"actproof-exporter"}\n'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        else:
            self.send_error(404, "Not Found. Try /metrics or /health")

    def log_message(self, format, *args):
        """Suppress default access logging to keep console clean."""
        pass


# ─── Synthetic Data Generator (built-in demo) ──────────────────────────────

def _generate_next_point(step: int, total_steps: int) -> dict:
    """
    Generate a single synthetic observation that gradually degrades.
    Mimics the simulation phases from simulate.py but runs in real-time.
    """
    progress = step / max(total_steps, 1)

    if progress < 0.15:
        # Stable
        return {
            "policy_hits": random.choice([0, 0, 0, 0, 1]),
            "retries": 0,
            "edit_ratio": 0.02 + random.gauss(0, 0.005),
            "latency_overhead_ms": 50 + random.gauss(0, 10),
            "semantic_distance": 0.01 + random.gauss(0, 0.003),
        }
    elif progress < 0.35:
        # Early drift
        p = (progress - 0.15) / 0.20
        return {
            "policy_hits": random.choice([0, 0, 1, 1, 2]) if p > 0.5 else random.choice([0, 0, 0, 1]),
            "retries": 1 if random.random() < 0.2 * p else 0,
            "edit_ratio": max(0, 0.03 + 0.07 * p + random.gauss(0, 0.01)),
            "latency_overhead_ms": max(0, 60 + 80 * p + random.gauss(0, 15)),
            "semantic_distance": max(0, 0.02 + 0.04 * p + random.gauss(0, 0.005)),
        }
    elif progress < 0.60:
        # Accelerating
        p = (progress - 0.35) / 0.25
        return {
            "policy_hits": int(max(0, 1 + 3 * p + random.gauss(0, 0.5))),
            "retries": int(max(0, 0.5 + 2 * p + random.gauss(0, 0.3))),
            "edit_ratio": max(0, min(1, 0.10 + 0.25 * p + random.gauss(0, 0.02))),
            "latency_overhead_ms": max(0, 150 + 500 * p + random.gauss(0, 30)),
            "semantic_distance": max(0, min(1, 0.06 + 0.14 * p + random.gauss(0, 0.01))),
        }
    elif progress < 0.80:
        # Critical
        p = (progress - 0.60) / 0.20
        return {
            "policy_hits": int(max(0, 4 + 5 * p + random.gauss(0, 1))),
            "retries": int(max(0, 3 + 3 * p + random.gauss(0, 0.5))),
            "edit_ratio": max(0, min(1, 0.40 + 0.35 * p + random.gauss(0, 0.03))),
            "latency_overhead_ms": max(0, 800 + 2000 * p ** 1.5 + random.gauss(0, 60)),
            "semantic_distance": max(0, min(1, 0.22 + 0.30 * p + random.gauss(0, 0.02))),
        }
    elif progress < 0.90:
        # Flashover
        p = (progress - 0.80) / 0.10
        return {
            "policy_hits": int(max(0, 8 + 5 * p + random.gauss(0, 1))),
            "retries": int(max(0, 5 + 3 * p + random.gauss(0, 0.5))),
            "edit_ratio": max(0, min(1, 0.82 + 0.15 * p + random.gauss(0, 0.02))),
            "latency_overhead_ms": max(0, 3000 + 2000 * p + random.gauss(0, 100)),
            "semantic_distance": max(0, min(1, 0.60 + 0.25 * p + random.gauss(0, 0.03))),
        }
    else:
        # Recovery
        p = (progress - 0.90) / 0.10
        return {
            "policy_hits": int(max(0, 3 - 2.5 * p + random.gauss(0, 0.5))),
            "retries": int(max(0, 2 - 1.5 * p + random.gauss(0, 0.3))),
            "edit_ratio": max(0, min(1, 0.30 - 0.25 * p + random.gauss(0, 0.01))),
            "latency_overhead_ms": max(0, 400 - 300 * p + random.gauss(0, 20)),
            "semantic_distance": max(0, min(1, 0.12 - 0.10 * p + random.gauss(0, 0.005))),
        }


def _simulation_loop(metrics: ActProofMetrics, interval: float, duration_steps: int):
    """
    Background thread: feeds synthetic data into ActProofMetrics at regular intervals.
    Runs a full degradation→flashover→recovery cycle.
    """
    step = 0
    cycle = 0
    state_names = {
        SystemState.NORMAL: "[OK] NORMAL",
        SystemState.WARN: "[!!] WARN",
        SystemState.SURVIVAL: "[**] SURVIVAL",
        SystemState.FLASHOVER: "[XX] FLASHOVER",
        SystemState.RECOVERY: "[..] RECOVERY",
    }

    while True:
        point = _generate_next_point(step, duration_steps)
        metrics.update(**point)

        with metrics._lock:
            state = metrics._state
            cc = metrics._cc_ema
            phi = metrics._phi

        state_str = state_names.get(state, str(state))
        print(
            f"  [{cycle}:{step:3d}/{duration_steps}] "
            f"CC_ema={cc:.3f}  Phi={phi:.2f}  {state_str}"
            f"  | hits={point['policy_hits']} ret={point['retries']} "
            f"edit={point['edit_ratio']:.2f} lat={point['latency_overhead_ms']:.0f}ms "
            f"sem={point['semantic_distance']:.3f}"
        )

        step += 1
        if step >= duration_steps:
            step = 0
            cycle += 1
            # Reset detector for next cycle
            metrics.detector.reset()
            print(f"\n  -- Cycle {cycle} complete, restarting degradation scenario --\n")

        time.sleep(interval)


# ─── Main ───────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="ActProof — Grafana-Compatible Metrics Exporter",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python dashboard_prototype.py                    # defaults: port 9120, 3s interval
  python dashboard_prototype.py --port 8080        # custom port
  python dashboard_prototype.py --interval 1       # faster simulation (1s per step)
  python dashboard_prototype.py --steps 200        # longer degradation cycle

Prometheus scrape config:
  scrape_configs:
    - job_name: 'actproof'
      scrape_interval: 5s
      static_configs:
        - targets: ['localhost:9120']

Grafana panels (recommended):
  • CC EMA time-series           → actproof_cc_ema
  • CC z-score with thresholds   → actproof_cc_zscore (threshold: 3.0)
  • Φ accumulator vs critical    → actproof_phi, actproof_phi_critical
  • System state timeline        → actproof_state
  • MCI breakdown (stacked area) → actproof_mci{compensator=~".+"}
  • Tension gauge                → actproof_tension
        """,
    )
    parser.add_argument(
        "--port", type=int, default=9120,
        help="HTTP port for /metrics endpoint (default: 9120)",
    )
    parser.add_argument(
        "--interval", type=float, default=3.0,
        help="Seconds between synthetic data updates (default: 3.0)",
    )
    parser.add_argument(
        "--steps", type=int, default=120,
        help="Steps per full degradation cycle (default: 120)",
    )
    args = parser.parse_args()

    # Banner
    print("=" * 64)
    print("  ActProof — Grafana-Compatible Metrics Exporter")
    print("  Dashboard Prototype for Prometheus + Grafana")
    print("=" * 64)
    print(f"  Port       : {args.port}")
    print(f"  Interval   : {args.interval}s")
    print(f"  Cycle steps: {args.steps}")
    print(f"  Endpoints  : http://localhost:{args.port}/metrics")
    print(f"               http://localhost:{args.port}/health")
    print("=" * 64)
    print()

    # Set up metrics + handler
    metrics = ActProofMetrics()
    MetricsHandler.metrics_store = metrics

    # Start simulation thread
    sim_thread = threading.Thread(
        target=_simulation_loop,
        args=(metrics, args.interval, args.steps),
        daemon=True,
    )
    sim_thread.start()
    print("  [+] Simulation thread started")

    # Start HTTP server
    server = HTTPServer(("0.0.0.0", args.port), MetricsHandler)
    print(f"  [+] HTTP server listening on :{args.port}")
    print(f"\n  Scrape http://localhost:{args.port}/metrics with Prometheus")
    print("  Press Ctrl+C to stop\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Shutting down...")
        server.shutdown()
        print("  Done.")


if __name__ == "__main__":
    main()
