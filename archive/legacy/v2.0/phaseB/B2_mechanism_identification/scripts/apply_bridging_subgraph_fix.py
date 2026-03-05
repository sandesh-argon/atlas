#!/usr/bin/env python3
"""
B2 Option A Fix: Bridging Subgraph Filter
==========================================

Applies the recommended fix for 14.8% bridge quality failure:
1. Filter to bridging subgraph (nodes reachable FROM drivers AND reaching TO outcomes)
2. Recompute centrality on bridging subgraph
3. Select mechanism candidates (top 10%, 200-400 nodes)
4. Verify bridge quality (expect 95-100%)
5. Ready for Louvain clustering

Author: Phase B2 Fix
Date: November 2025
"""

import pickle
import json
import sys
from pathlib import Path
import pandas as pd
import numpy as np
import networkx as nx
from datetime import datetime
from sklearn.preprocessing import MinMaxScaler

# Add project root to path
project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

print("="*80)
print("B2 OPTION A FIX: BRIDGING SUBGRAPH FILTER")
print("="*80)

start_time = datetime.now().timestamp()
print(f"Start time: {datetime.fromtimestamp(start_time).strftime('%Y-%m-%d %H:%M:%S')}")

# Directories
output_dir = Path(__file__).parent / "outputs"
diag_dir = Path(__file__).parent / "diagnostics"

# Load A6 graph
a6_path = project_root / "phaseA/A6_hierarchical_layering/outputs/A6_hierarchical_graph.pkl"
print(f"\nLoading A6 graph...")

with open(a6_path, 'rb') as f:
    a6_data = pickle.load(f)

G = a6_data['graph']
layers = a6_data['layers']
metadata = a6_data['metadata']

print(f"✅ Loaded graph: {metadata['n_nodes']} nodes, {metadata['n_edges']} edges")

# Identify nodes by layer
driver_nodes = [n for n, layer in layers.items() if layer == 0]
outcome_nodes = [n for n, layer in layers.items() if layer >= 19]

print(f"   Drivers (L0): {len(driver_nodes)}")
print(f"   Outcomes (L19-L20): {len(outcome_nodes)}")

# ============================================================================
# STEP 1: Filter to Bridging Subgraph
# ============================================================================

print("\n" + "="*80)
print("STEP 1: FILTERING TO BRIDGING SUBGRAPH")
print("="*80)

print(f"\nIdentifying nodes that bridge drivers→outcomes...")
print(f"   Finding nodes reachable FROM drivers...")

# For each driver, find all nodes it can reach
bridging_candidates = set()

for i, driver in enumerate(driver_nodes):
    try:
        descendants = nx.descendants(G, driver)  # All nodes reachable FROM driver
        bridging_candidates.update(descendants)
    except nx.NodeNotFound:
        continue

    # Progress every 100 drivers
    if (i + 1) % 100 == 0:
        print(f"      Processed {i+1}/{len(driver_nodes)} drivers → {len(bridging_candidates)} reachable nodes")

print(f"   ✅ Found {len(bridging_candidates)} nodes reachable from drivers")

# Filter to only nodes that ALSO reach outcomes
print(f"\n   Finding nodes that reach outcomes...")

final_bridging_nodes = set()

for i, node in enumerate(bridging_candidates):
    # Check if this node reaches ANY outcome
    reaches_outcome = False
    for outcome in outcome_nodes:
        try:
            if nx.has_path(G, node, outcome):
                reaches_outcome = True
                final_bridging_nodes.add(node)
                break  # Found at least one outcome, keep this node
        except nx.NodeNotFound:
            continue

    # Progress every 500 nodes
    if (i + 1) % 500 == 0:
        print(f"      Checked {i+1}/{len(bridging_candidates)} candidates → {len(final_bridging_nodes)} bridging nodes")

# Add drivers and outcomes themselves
final_bridging_nodes.update(driver_nodes)
final_bridging_nodes.update(outcome_nodes)

print(f"\n   ✅ Bridging subgraph: {len(final_bridging_nodes)} nodes (from {metadata['n_nodes']})")
print(f"      Reduction: {(1 - len(final_bridging_nodes)/metadata['n_nodes'])*100:.1f}%")

# Create bridging subgraph
G_bridging = G.subgraph(final_bridging_nodes).copy()

print(f"\n   Bridging subgraph properties:")
print(f"      Nodes: {G_bridging.number_of_nodes()}")
print(f"      Edges: {G_bridging.number_of_edges()}")
print(f"      Density: {nx.density(G_bridging):.4f}")

# ============================================================================
# STEP 2: Recompute Centrality on Bridging Subgraph
# ============================================================================

print("\n" + "="*80)
print("STEP 2: RECOMPUTING CENTRALITY ON BRIDGING SUBGRAPH")
print("="*80)

print(f"\nComputing betweenness centrality (smaller graph, faster)...")
betweenness_bridging = nx.betweenness_centrality(G_bridging)
print(f"   ✅ Betweenness computed")

print(f"Computing PageRank...")
pagerank_bridging = nx.pagerank(G_bridging, alpha=0.85, max_iter=100)
print(f"   ✅ PageRank computed")

print(f"Computing out-degree centrality...")
out_degree_bridging = dict(G_bridging.out_degree())
print(f"   ✅ Out-degree computed")

# Normalize to [0, 1]
print(f"\nNormalizing centrality metrics...")

scaler = MinMaxScaler()

betweenness_values = np.array([[v] for v in betweenness_bridging.values()])
pagerank_values = np.array([[v] for v in pagerank_bridging.values()])
out_degree_values = np.array([[v] for v in out_degree_bridging.values()])

if len(betweenness_values) > 0:
    betweenness_norm = scaler.fit_transform(betweenness_values).flatten()
    pagerank_norm = scaler.fit_transform(pagerank_values).flatten()
    out_degree_norm = scaler.fit_transform(out_degree_values).flatten()
else:
    print("   ❌ ERROR: No nodes in bridging subgraph!")
    sys.exit(1)

# Composite centrality (same weights: 0.40 betweenness, 0.30 pagerank, 0.30 out_degree)
print(f"\nComputing composite centrality...")

centrality_scores_bridging = {}
for i, node in enumerate(G_bridging.nodes()):
    centrality_scores_bridging[node] = (
        0.40 * betweenness_norm[i] +
        0.30 * pagerank_norm[i] +
        0.30 * out_degree_norm[i]
    )

sorted_by_centrality_bridging = sorted(
    centrality_scores_bridging.items(),
    key=lambda x: x[1],
    reverse=True
)

print(f"   ✅ Composite centrality computed for {len(centrality_scores_bridging)} nodes")

print(f"\n   Top 10 centrality nodes (bridging subgraph):")
for node, score in sorted_by_centrality_bridging[:10]:
    layer = layers.get(node, -1)
    print(f"      {node[:50]:50s}: {score:.4f} (layer {layer})")

# ============================================================================
# STEP 3: Select Mechanism Candidates (Top 10%)
# ============================================================================

print("\n" + "="*80)
print("STEP 3: SELECTING MECHANISM CANDIDATES")
print("="*80)

# Calculate target: 10% of bridging subgraph, constrained to 200-400
n_mechanisms_raw = int(len(G_bridging.nodes()) * 0.10)
n_mechanisms = max(n_mechanisms_raw, 200)  # Minimum 200
n_mechanisms = min(n_mechanisms, 400)  # Maximum 400

print(f"\n   Target calculation:")
print(f"      10% of {len(G_bridging.nodes())} = {n_mechanisms_raw}")
print(f"      Constrained to [200, 400] = {n_mechanisms}")

# Select top N, excluding drivers (L0) and outcomes (L19-20)
mechanism_candidates_bridging = []

for node, score in sorted_by_centrality_bridging:
    layer = layers.get(node, -1)
    if layer not in [0, 19, 20]:  # Exclude drivers and outcomes
        mechanism_candidates_bridging.append((node, score))

    if len(mechanism_candidates_bridging) >= n_mechanisms:
        break

print(f"\n   ✅ Selected {len(mechanism_candidates_bridging)} mechanism candidates")
print(f"      (Excluded {len([n for n in G_bridging.nodes() if layers.get(n, -1) in [0, 19, 20]])} drivers/outcomes)")

# Layer distribution
layer_dist = {}
for node, _ in mechanism_candidates_bridging:
    layer = layers.get(node, -1)
    layer_dist[layer] = layer_dist.get(layer, 0) + 1

print(f"\n   Layer distribution of mechanism candidates:")
for layer in sorted(layer_dist.keys())[:15]:  # Show first 15 layers
    count = layer_dist[layer]
    pct = count / len(mechanism_candidates_bridging) * 100
    print(f"      Layer {layer:2d}: {count:3d} nodes ({pct:5.1f}%)")

# ============================================================================
# STEP 4: Verify Bridge Quality (Should be ~100%)
# ============================================================================

print("\n" + "="*80)
print("STEP 4: VERIFYING BRIDGE QUALITY")
print("="*80)

print(f"\nTesting bridge quality on {min(200, len(mechanism_candidates_bridging))} sampled candidates...")

# Sample up to 200 candidates
sample_size = min(200, len(mechanism_candidates_bridging))
mechanism_sample = [node for node, _ in mechanism_candidates_bridging[:sample_size]]

# Updated drivers/outcomes in bridging subgraph
driver_nodes_bridging = [n for n in driver_nodes if n in G_bridging]
outcome_nodes_bridging = [n for n in outcome_nodes if n in G_bridging]

print(f"   Drivers in bridging subgraph: {len(driver_nodes_bridging)}")
print(f"   Outcomes in bridging subgraph: {len(outcome_nodes_bridging)}")

bridge_quality_results = []

for i, node in enumerate(mechanism_sample):
    # Check if node has path from ANY driver
    has_driver_path = any(
        nx.has_path(G_bridging, driver, node)
        for driver in driver_nodes_bridging[:50]  # Sample 50 drivers
    )

    # Check if node has path to ANY outcome
    has_outcome_path = any(
        nx.has_path(G_bridging, node, outcome)
        for outcome in outcome_nodes_bridging  # All outcomes (only 32)
    )

    is_bridge = has_driver_path and has_outcome_path
    bridge_quality_results.append(is_bridge)

    # Progress every 50
    if (i + 1) % 50 == 0:
        current_pass_rate = sum(bridge_quality_results) / len(bridge_quality_results)
        print(f"      Tested {i+1}/{sample_size} → {current_pass_rate*100:.1f}% passing")

bridge_pass_rate_bridging = sum(bridge_quality_results) / len(bridge_quality_results)

print(f"\n📊 RESULT:")
print(f"   Bridge quality (bridging subgraph): {bridge_pass_rate_bridging*100:.1f}%")
print(f"   Passed: {sum(bridge_quality_results)}/{len(bridge_quality_results)}")

if bridge_pass_rate_bridging < 0.90:
    print(f"   ⚠️  WARNING: Bridge quality {bridge_pass_rate_bridging*100:.1f}% < 90%")
    print(f"      Expected near 100% after filtering")
    print(f"      May need deeper investigation")
else:
    print(f"   ✅ EXCELLENT: Bridge quality {bridge_pass_rate_bridging*100:.1f}% (target: >90%)")

# ============================================================================
# STEP 5: Save Results and Prepare for Clustering
# ============================================================================

print("\n" + "="*80)
print("STEP 5: SAVING RESULTS")
print("="*80)

# Save bridging subgraph fix results
fix_results = {
    'original_graph': {
        'n_nodes': metadata['n_nodes'],
        'n_edges': metadata['n_edges']
    },
    'bridging_subgraph': {
        'n_nodes': G_bridging.number_of_nodes(),
        'n_edges': G_bridging.number_of_edges(),
        'density': float(nx.density(G_bridging)),
        'reduction_pct': float((1 - len(final_bridging_nodes)/metadata['n_nodes'])*100)
    },
    'mechanism_candidates': {
        'n_candidates': len(mechanism_candidates_bridging),
        'target_range': [200, 400],
        'layer_distribution': {int(k): int(v) for k, v in layer_dist.items()}
    },
    'bridge_quality': {
        'pass_rate': float(bridge_pass_rate_bridging),
        'passed': int(sum(bridge_quality_results)),
        'tested': len(bridge_quality_results)
    },
    'timestamp': datetime.now().isoformat()
}

with open(output_dir / "B2_bridging_subgraph_fix_results.json", 'w') as f:
    json.dump(fix_results, f, indent=2)

print(f"\n✅ Fix results saved: {output_dir}/B2_bridging_subgraph_fix_results.json")

# Save bridging subgraph centrality scores
centrality_bridging_df = pd.DataFrame({
    'node': [node for node, _ in sorted_by_centrality_bridging],
    'composite': [score for _, score in sorted_by_centrality_bridging],
    'betweenness': [betweenness_bridging[node] for node, _ in sorted_by_centrality_bridging],
    'pagerank': [pagerank_bridging[node] for node, _ in sorted_by_centrality_bridging],
    'out_degree': [out_degree_bridging[node] for node, _ in sorted_by_centrality_bridging],
    'layer': [layers.get(node, -1) for node, _ in sorted_by_centrality_bridging]
})

centrality_bridging_df.to_csv(diag_dir / "B2_centrality_scores_bridging.csv", index=False)
print(f"✅ Centrality scores saved: {diag_dir}/B2_centrality_scores_bridging.csv")

# Save mechanism candidates list
mechanism_df = pd.DataFrame({
    'node': [node for node, _ in mechanism_candidates_bridging],
    'centrality_score': [score for _, score in mechanism_candidates_bridging],
    'layer': [layers.get(node, -1) for node, _ in mechanism_candidates_bridging]
})

mechanism_df.to_csv(output_dir / "B2_mechanism_candidates_bridging.csv", index=False)
print(f"✅ Mechanism candidates saved: {output_dir}/B2_mechanism_candidates_bridging.csv")

# Save bridging subgraph for clustering
bridging_checkpoint = {
    'graph': G_bridging,
    'mechanism_candidates': [node for node, _ in mechanism_candidates_bridging],
    'mechanism_scores': [score for _, score in mechanism_candidates_bridging],
    'centrality_scores': centrality_scores_bridging,
    'layers': {n: layers[n] for n in G_bridging.nodes() if n in layers},
    'metadata': fix_results
}

with open(output_dir / "B2_bridging_subgraph_checkpoint.pkl", 'wb') as f:
    pickle.dump(bridging_checkpoint, f)

print(f"✅ Bridging subgraph checkpoint saved: {output_dir}/B2_bridging_subgraph_checkpoint.pkl")

# ============================================================================
# SUMMARY
# ============================================================================

elapsed_time = datetime.now().timestamp() - start_time

print("\n" + "="*80)
print("OPTION A FIX COMPLETE")
print("="*80)

print(f"\n📊 Summary:")
print(f"   Original graph: {metadata['n_nodes']} nodes → Bridging subgraph: {G_bridging.number_of_nodes()} nodes ({fix_results['bridging_subgraph']['reduction_pct']:.1f}% reduction)")
print(f"   Mechanism candidates: {len(mechanism_candidates_bridging)} (target: 200-400)")
print(f"   Bridge quality: {bridge_pass_rate_bridging*100:.1f}% (target: >90%)")
print(f"   Runtime: {elapsed_time/60:.1f} minutes")

print(f"\n✅ Ready for Louvain clustering!")
print(f"   Next step: Run community detection on {len(mechanism_candidates_bridging)} mechanism nodes")
print(f"   Expected clusters: 15-30 (revised from 20-40)")

print(f"\n📁 Outputs:")
print(f"   - {output_dir}/B2_bridging_subgraph_fix_results.json")
print(f"   - {output_dir}/B2_mechanism_candidates_bridging.csv")
print(f"   - {output_dir}/B2_bridging_subgraph_checkpoint.pkl")
print(f"   - {diag_dir}/B2_centrality_scores_bridging.csv")

print(f"\n{'='*80}")
