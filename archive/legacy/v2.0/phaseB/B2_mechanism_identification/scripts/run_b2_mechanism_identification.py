#!/usr/bin/env python3
"""
Phase B2: Mechanism Identification
===================================

Identifies 20-40 mechanism node clusters that bridge drivers to validated outcomes
using composite centrality scoring and community detection.

Safety Checks:
1. Centrality timeout (2hr) + approximate fallback
2. Louvain resolution sweep (adaptive cluster count)
3. Bridge quality pre-check (fail fast if graph structure wrong)
4. Memory management (prevent OOM crashes)

Author: Phase B2
Date: November 2025
"""

import pickle
import json
import sys
import signal
from pathlib import Path
import pandas as pd
import numpy as np
import networkx as nx
import psutil
from datetime import datetime
from collections import Counter

# Community detection
try:
    import community as community_louvain
except ImportError:
    print("Installing python-louvain...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "python-louvain", "--break-system-packages", "-q"])
    import community as community_louvain

# Add project root to path
# Script is in: v2.0/phaseB/B2_mechanism_identification/scripts/
# Need to go up 3 levels to get to v2.0/
project_root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(project_root))

print("="*80)
print("PHASE B2: MECHANISM IDENTIFICATION")
print("="*80)

start_time = datetime.now().timestamp()
print(f"Start time: {datetime.fromtimestamp(start_time).strftime('%Y-%m-%d %H:%M:%S')}")

# Create output directories
output_dir = Path(__file__).parent / "outputs"
log_dir = Path(__file__).parent / "logs"
diag_dir = Path(__file__).parent / "diagnostics"
for d in [output_dir, log_dir, diag_dir]:
    d.mkdir(exist_ok=True, parents=True)

# ============================================================================
# SAFETY CHECK 1: Memory Management
# ============================================================================

print("\n[SAFETY CHECK 1] Checking available memory...")

available_gb = psutil.virtual_memory().available / (1024**3)
total_gb = psutil.virtual_memory().total / (1024**3)

print(f"   Total RAM: {total_gb:.1f} GB")
print(f"   Available RAM: {available_gb:.1f} GB")

MEMORY_THRESHOLD = 20.0  # GB

if available_gb < MEMORY_THRESHOLD:
    print(f"   ⚠️  WARNING: Available RAM ({available_gb:.1f} GB) < {MEMORY_THRESHOLD} GB")
    print(f"      → Will use approximate betweenness (k=500 samples)")
    USE_APPROXIMATE_BETWEENNESS = True
else:
    print(f"   ✅ Sufficient memory for exact betweenness")
    USE_APPROXIMATE_BETWEENNESS = False

# ============================================================================
# STEP 1: Load A6 Hierarchical Graph and B1 Validated Factors
# ============================================================================

print("\n[STEP 1] Loading A6 hierarchical graph and B1 validated factors...")

# Load A6 graph
a6_path = project_root / "phaseA/A6_hierarchical_layering/outputs/A6_hierarchical_graph.pkl"
print(f"   Loading A6 graph from: {a6_path}")

with open(a6_path, 'rb') as f:
    a6_data = pickle.load(f)

G = a6_data['graph']
layers = a6_data['layers']
metadata = a6_data['metadata']

print(f"   ✅ Loaded A6 graph: {metadata['n_nodes']} nodes, {metadata['n_edges']} edges")

# Load B1 validated factors (for context, not directly used in centrality)
b1_path = project_root / "phaseB/B1_outcome_discovery/outputs/B1_validation_summary.json"
with open(b1_path, 'r') as f:
    b1_summary = json.load(f)

validated_factor_count = b1_summary['metadata']['n_passed_overall']
print(f"   ✅ B1 validated factors: {validated_factor_count}")

# Identify driver, mechanism, and outcome nodes by layer
driver_nodes = [n for n, layer in layers.items() if layer == 0]
outcome_nodes = [n for n, layer in layers.items() if layer >= 19]
mechanism_candidates_pool = [n for n, layer in layers.items() if 1 <= layer <= 18]

print(f"\n   Node distribution by layer type:")
print(f"      Drivers (L0): {len(driver_nodes)} nodes")
print(f"      Mechanism pool (L1-L18): {len(mechanism_candidates_pool)} nodes")
print(f"      Outcomes (L19-L20): {len(outcome_nodes)} nodes")

# ============================================================================
# STEP 2: Compute Composite Centrality with Timeout
# ============================================================================

print("\n[STEP 2] Computing composite centrality scores...")

# ============================================================================
# SAFETY CHECK 2: Centrality Timeout + Approximate Fallback
# ============================================================================

class TimeoutError(Exception):
    pass

def timeout_handler(signum, frame):
    raise TimeoutError("Betweenness computation exceeded timeout")

def compute_betweenness_safe(G, timeout_seconds=7200, k=None):
    """
    Compute betweenness with timeout and approximate fallback

    Args:
        G: NetworkX graph
        timeout_seconds: Max time (default 2 hours)
        k: Sample size for approximate (None = exact)

    Returns:
        (betweenness_dict, method_used)
    """
    # Set timeout alarm (Unix only)
    if hasattr(signal, 'SIGALRM'):
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(timeout_seconds)

    try:
        if k is None:
            print(f"   Computing EXACT betweenness (timeout: {timeout_seconds/3600:.1f}h)...")
            betweenness = nx.betweenness_centrality(G)
            if hasattr(signal, 'SIGALRM'):
                signal.alarm(0)  # Cancel timeout
            return betweenness, "exact"
    except TimeoutError:
        print(f"   ⚠️  Exact betweenness timeout, switching to approximate")
        if hasattr(signal, 'SIGALRM'):
            signal.alarm(0)

    # Fallback to approximate
    k_samples = k if k is not None else 1000
    print(f"   Computing APPROXIMATE betweenness (k={k_samples} samples)...")
    betweenness = nx.betweenness_centrality(G, k=k_samples)
    return betweenness, "approximate"

# Compute betweenness (with timeout safety)
if USE_APPROXIMATE_BETWEENNESS:
    betweenness, betweenness_method = nx.betweenness_centrality(G, k=500), "approximate (low memory)"
else:
    betweenness, betweenness_method = compute_betweenness_safe(G, timeout_seconds=7200)

print(f"   ✅ Betweenness computed: {betweenness_method}")

# Compute PageRank
print(f"   Computing PageRank...")
pagerank = nx.pagerank(G, alpha=0.85)
print(f"   ✅ PageRank computed")

# Compute out-degree centrality
print(f"   Computing out-degree centrality...")
out_degree = dict(G.out_degree())
max_out_degree = max(out_degree.values()) if out_degree else 1
out_degree_normalized = {n: d / max_out_degree for n, d in out_degree.items()}
print(f"   ✅ Out-degree centrality computed")

# Normalize centrality metrics to [0, 1]
def normalize_dict(d):
    """Normalize dictionary values to [0, 1]"""
    vals = list(d.values())
    min_val, max_val = min(vals), max(vals)
    if max_val == min_val:
        return {k: 0.5 for k in d.keys()}
    return {k: (v - min_val) / (max_val - min_val) for k, v in d.items()}

betweenness_norm = normalize_dict(betweenness)
pagerank_norm = normalize_dict(pagerank)
out_degree_norm = out_degree_normalized  # Already normalized

# Compute composite centrality
print(f"\n   Computing composite centrality (0.40×betweenness + 0.30×pagerank + 0.30×out_degree)...")
composite_centrality = {}
for node in G.nodes():
    composite_centrality[node] = (
        0.40 * betweenness_norm.get(node, 0) +
        0.30 * pagerank_norm.get(node, 0) +
        0.30 * out_degree_norm.get(node, 0)
    )

print(f"   ✅ Composite centrality computed for {len(composite_centrality)} nodes")

# Save centrality diagnostics
centrality_df = pd.DataFrame({
    'node': list(composite_centrality.keys()),
    'composite': list(composite_centrality.values()),
    'betweenness': [betweenness_norm[n] for n in composite_centrality.keys()],
    'pagerank': [pagerank_norm[n] for n in composite_centrality.keys()],
    'out_degree': [out_degree_norm[n] for n in composite_centrality.keys()],
    'layer': [layers.get(n, -1) for n in composite_centrality.keys()]
})

centrality_df.to_csv(diag_dir / "B2_centrality_scores.csv", index=False)
print(f"   ✅ Centrality scores saved: {diag_dir}/B2_centrality_scores.csv")

# Statistics
print(f"\n   Centrality score distribution:")
print(f"      Min:    {centrality_df['composite'].min():.4f}")
print(f"      Median: {centrality_df['composite'].median():.4f}")
print(f"      Mean:   {centrality_df['composite'].mean():.4f}")
print(f"      Max:    {centrality_df['composite'].max():.4f}")

# ============================================================================
# STEP 3: Bridge Quality Pre-Check
# ============================================================================

print("\n[STEP 3] Running bridge quality pre-check...")

# ============================================================================
# SAFETY CHECK 3: Bridge Quality Validation BEFORE Clustering
# ============================================================================

def has_path_from_any(G, sources, target, max_samples=50):
    """Check if target has path from any source (sample first max_samples)"""
    for source in sources[:max_samples]:
        try:
            if nx.has_path(G, source, target):
                return True
        except nx.NodeNotFound:
            continue
    return False

def has_path_to_any(G, source, targets, max_samples=50):
    """Check if source has path to any target (sample first max_samples)"""
    for target in targets[:max_samples]:
        try:
            if nx.has_path(G, source, target):
                return True
        except nx.NodeNotFound:
            continue
    return False

def compute_bridge_quality_per_node(G, node, driver_nodes, outcome_nodes):
    """
    Check if node has paths from drivers AND to outcomes

    Returns:
        (has_driver_path, has_outcome_path, is_bridge)
    """
    has_driver_path = has_path_from_any(G, driver_nodes, node, max_samples=50)
    has_outcome_path = has_path_to_any(G, node, outcome_nodes, max_samples=50)

    is_bridge = has_driver_path and has_outcome_path
    return has_driver_path, has_outcome_path, is_bridge

print(f"   Sampling driver→mechanism→outcome paths...")
print(f"      Driver nodes: {len(driver_nodes)} (sampling 50)")
print(f"      Outcome nodes: {len(outcome_nodes)} (sampling 50)")

# Sort mechanism candidates by composite centrality
mechanism_pool_sorted = sorted(
    [(n, composite_centrality[n]) for n in mechanism_candidates_pool],
    key=lambda x: x[1],
    reverse=True
)

# Select top candidates with bridge quality check
TARGET_MECHANISMS = 800  # Top 10% of 8,126 ≈ 800
MAX_CANDIDATES_TO_CHECK = 1200  # Check up to 1200 to find 800 bridges

mechanism_nodes = []
bridge_stats = {'driver_only': 0, 'outcome_only': 0, 'bridge': 0, 'isolated': 0}

print(f"   Checking bridge quality for top {MAX_CANDIDATES_TO_CHECK} centrality candidates...")

for i, (node, score) in enumerate(mechanism_pool_sorted[:MAX_CANDIDATES_TO_CHECK]):
    has_driver, has_outcome, is_bridge = compute_bridge_quality_per_node(
        G, node, driver_nodes, outcome_nodes
    )

    if is_bridge:
        mechanism_nodes.append((node, score))
        bridge_stats['bridge'] += 1
    elif has_driver and not has_outcome:
        bridge_stats['driver_only'] += 1
    elif has_outcome and not has_driver:
        bridge_stats['outcome_only'] += 1
    else:
        bridge_stats['isolated'] += 1

    # Stop when we have enough bridges
    if len(mechanism_nodes) >= TARGET_MECHANISMS:
        print(f"   ✅ Found {TARGET_MECHANISMS} bridge nodes")
        break

    # Progress every 100 nodes
    if (i + 1) % 100 == 0:
        print(f"      Checked {i+1} candidates → {len(mechanism_nodes)} bridges found")

print(f"\n   Bridge quality statistics (first {i+1} candidates):")
print(f"      Bridge (driver→node→outcome): {bridge_stats['bridge']} ({bridge_stats['bridge']/(i+1)*100:.1f}%)")
print(f"      Driver only: {bridge_stats['driver_only']}")
print(f"      Outcome only: {bridge_stats['outcome_only']}")
print(f"      Isolated: {bridge_stats['isolated']}")

bridge_quality_pass_rate = bridge_stats['bridge'] / (i + 1)

if bridge_quality_pass_rate < 0.50:
    print(f"\n   ❌ FAIL: Bridge quality pass rate {bridge_quality_pass_rate:.1%} < 50%")
    print(f"      → Graph structure may not support mechanism identification")
    print(f"      → Check A6 hierarchical layering")
    sys.exit(1)
elif bridge_quality_pass_rate < 0.90:
    print(f"\n   ⚠️  WARNING: Bridge quality pass rate {bridge_quality_pass_rate:.1%} < 90%")
    print(f"      → Some high-centrality nodes don't bridge drivers→outcomes")
else:
    print(f"\n   ✅ Bridge quality pass rate: {bridge_quality_pass_rate:.1%} (excellent)")

print(f"\n   Selected {len(mechanism_nodes)} mechanism nodes for clustering")

# ============================================================================
# CHECKPOINT: Save intermediate results
# ============================================================================

print(f"\n[CHECKPOINT] Saving intermediate centrality results...")

checkpoint_1 = {
    'composite_centrality': composite_centrality,
    'betweenness_method': betweenness_method,
    'mechanism_nodes': [n for n, _ in mechanism_nodes],
    'mechanism_scores': [s for _, s in mechanism_nodes],
    'bridge_stats': bridge_stats,
    'bridge_quality_pass_rate': bridge_quality_pass_rate,
    'timestamp': datetime.now().isoformat()
}

with open(output_dir / "B2_centrality_checkpoint.pkl", 'wb') as f:
    pickle.dump(checkpoint_1, f)

print(f"   ✅ Checkpoint saved: {output_dir}/B2_centrality_checkpoint.pkl")
print(f"\n⏸️  PAUSING FOR HUMAN REVIEW")
print(f"   Review centrality computation results:")
print(f"   1. Betweenness method: {betweenness_method}")
print(f"   2. Bridge quality pass rate: {bridge_quality_pass_rate:.1%}")
print(f"   3. Mechanism nodes selected: {len(mechanism_nodes)}")
print(f"   4. Centrality score range: [{centrality_df['composite'].min():.4f}, {centrality_df['composite'].max():.4f}]")
print(f"\n   If acceptable, continue to community detection...")
print(f"   Runtime so far: ~{(datetime.now().timestamp() - start_time)/3600:.1f} hours")
