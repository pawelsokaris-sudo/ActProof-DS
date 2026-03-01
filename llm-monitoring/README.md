# LLM Monitoring — Applying ActProof to Production LLMs

## Overview

This directory contains a proof-of-concept implementation of ActProof's control cost
framework applied to LLM production monitoring. It demonstrates how the CCC formula
and flashover state machine can be deployed as an external monitoring layer.

## Components

### cc_calculator.py
Implementation of the CCC control cost formula:
```
CC_turn = w1·policy_hits + w2·retries + w3·edit_ratio + w4·latency + w5·SemanticDist
```
Configurable weights, rolling baseline, z-score normalization.

### flashover_detector.py
State machine implementation with four states:
- **NORMAL** — CC within expected range
- **WARN** — CC elevated (z_CC ≥ 3 for ≥ 5 min)
- **SURVIVAL** — system brittle (+ z_T ≥ 2, MCI ≥ 0.35)
- **FLASHOVER** — cascade failure (Φ(t) ≥ Φ_critical)

Includes the flashover accumulator Φ(t) with exponential decay.

### simulate.py
Generates synthetic data mimicking a production LLM experiencing gradual alignment
degradation. Produces CC curve visualization with annotated state transitions.

## Integration

The monitoring layer is designed to consume signals from existing safety infrastructure:
- Policy filter activation logs
- Retry/rewrite counts
- Latency measurements
- Semantic similarity scores (draft vs. final output)

Compatible with Prometheus metrics export for Grafana dashboards.

## Quick Start

```bash
# Run simulation with default parameters
python simulate.py

# Custom scenario
python simulate.py --degradation-rate 0.08 --duration-minutes 60 --output figures/custom.png
```
