"""
ActProof — Minimal Control Cost Example (20 lines)

Demonstrates the core idea: measure how hard safety infrastructure works.
"""

# Weights: how much each signal contributes to control cost
W = {"policy_hits": 0.30, "retries": 0.25, "edit_ratio": 0.20, "latency": 0.10, "semantic_dist": 0.15}

def cc(policy_hits=0, retries=0, edit_ratio=0.0, latency_ms=0, semantic_dist=0.0):
    return (W["policy_hits"] * policy_hits + W["retries"] * retries +
            W["edit_ratio"] * edit_ratio + W["latency"] * min(latency_ms/1000, 5) +
            W["semantic_dist"] * semantic_dist)

# Normal operation: low CC
print(f"Normal:    CC = {cc(policy_hits=0, retries=0, edit_ratio=0.02, latency_ms=50, semantic_dist=0.01):.3f}")
# Elevated: safety working harder
print(f"Elevated:  CC = {cc(policy_hits=2, retries=1, edit_ratio=0.15, latency_ms=300, semantic_dist=0.08):.3f}")
# Critical: approaching flashover
print(f"Critical:  CC = {cc(policy_hits=5, retries=3, edit_ratio=0.60, latency_ms=2000, semantic_dist=0.35):.3f}")
# Flashover: cascade failure
print(f"Flashover: CC = {cc(policy_hits=8, retries=5, edit_ratio=0.90, latency_ms=4000, semantic_dist=0.70):.3f}")
