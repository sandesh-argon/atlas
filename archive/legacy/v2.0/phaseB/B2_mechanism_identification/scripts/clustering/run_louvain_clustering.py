#!/usr/bin/env python3
"""
B2 Step 5: Louvain Clustering
==============================

Applies Louvain community detection to identify mechanism clusters:
1. Resolution sweep to find optimal cluster count (15-30)
2. Execute Louvain with optimal resolution
3. Validate cluster sizes (merge tiny clusters if needed)
4. Save cluster assignments for domain labeling

Author: Phase B2 Clustering
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
from community import community_louvain

# Add project root to path
project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

print("="*80)
print("B2 STEP 5: LOUVAIN CLUSTERING")
print("="*80)

start_time = datetime.now().timestamp()
print(f"Start time: {datetime.fromtimestamp(start_time).strftime('%Y-%m-%d %H:%M:%S')}")

# Directories
output_dir = Path(__file__).parent / "outputs"
diag_dir = Path(__file__).parent / "diagnostics"

# Load bridging subgraph checkpoint
checkpoint_path = output_dir / "B2_bridging_subgraph_checkpoint.pkl"
print(f"\nLoading bridging subgraph checkpoint...")

with open(checkpoint_path, 'rb') as f:
    checkpoint = pickle.load(f)

G_bridging = checkpoint['graph']
mechanism_candidates = checkpoint['mechanism_candidates']
mechanism_scores = checkpoint['mechanism_scores']
centrality_scores = checkpoint['centrality_scores']
layers = checkpoint['layers']

print(f"✅ Loaded checkpoint:")
print(f"   Bridging subgraph: {G_bridging.number_of_nodes()} nodes, {G_bridging.number_of_edges()} edges")
print(f"   Mechanism candidates: {len(mechanism_candidates)}")

# ============================================================================
# STEP 5A: Create Mechanism Subgraph
# ============================================================================

print("\n" + "="*80)
print("STEP 5A: CREATING MECHANISM SUBGRAPH")
print("="*80)

# Create subgraph of mechanism candidates only
mechanism_subgraph = G_bridging.subgraph(mechanism_candidates).copy()

print(f"\nMechanism subgraph properties:")
print(f"   Nodes: {mechanism_subgraph.number_of_nodes()}")
print(f"   Edges: {mechanism_subgraph.number_of_edges()}")
print(f"   Density: {nx.density(mechanism_subgraph):.4f}")

# Check connectivity
n_components = nx.number_weakly_connected_components(mechanism_subgraph)
largest_cc = max(nx.weakly_connected_components(mechanism_subgraph), key=len)
print(f"   Components: {n_components}")
print(f"   Largest component: {len(largest_cc)} nodes ({len(largest_cc)/mechanism_subgraph.number_of_nodes()*100:.1f}%)")

if n_components > 1:
    print(f"\n⚠️  WARNING: Mechanism subgraph has {n_components} disconnected components")
    print(f"   Louvain will cluster each component separately")

# ============================================================================
# STEP 5B: Resolution Sweep (Find Optimal Cluster Count)
# ============================================================================

print("\n" + "="*80)
print("STEP 5B: RESOLUTION SWEEP")
print("="*80)

print(f"\nTarget cluster count: 15-30 (revised from 20-40)")
print(f"Testing resolutions: [0.5, 0.75, 1.0, 1.25, 1.5]")
print(f"Trials per resolution: 5 (different random seeds)")

def find_optimal_resolution(G, target_min=15, target_max=30, trials=5):
    """Test resolutions to find optimal cluster count"""
    results = []

    test_resolutions = [0.5, 0.75, 1.0, 1.25, 1.5]
    test_seeds = [42, 123, 456, 789, 1011]

    for resolution in test_resolutions:
        cluster_counts = []

        for seed in test_seeds:
            partition = community_louvain.best_partition(
                G.to_undirected(),  # Louvain requires undirected
                resolution=resolution,
                random_state=seed
            )
            n_clusters = len(set(partition.values()))
            cluster_counts.append(n_clusters)

        mean_clusters = np.mean(cluster_counts)
        std_clusters = np.std(cluster_counts)

        in_target = target_min <= mean_clusters <= target_max

        results.append({
            'resolution': resolution,
            'mean_clusters': mean_clusters,
            'std_clusters': std_clusters,
            'min_clusters': min(cluster_counts),
            'max_clusters': max(cluster_counts),
            'in_target': in_target
        })

        status = "✅" if in_target else "  "
        print(f"   {status} Resolution {resolution:.2f}: {mean_clusters:.1f} ± {std_clusters:.1f} clusters (range: {min(cluster_counts)}-{max(cluster_counts)})")

    # Select resolution closest to target range
    valid = [r for r in results if r['in_target']]

    if valid:
        # Pick resolution closest to midpoint (22.5)
        best = sorted(valid, key=lambda x: abs(x['mean_clusters'] - 22.5))[0]
        print(f"\n✅ Selected resolution={best['resolution']:.2f} → {best['mean_clusters']:.1f} clusters (WITHIN TARGET)")
    else:
        # Pick resolution closest to nearest target boundary
        best = min(results, key=lambda x: min(
            abs(x['mean_clusters'] - target_min),
            abs(x['mean_clusters'] - target_max)
        ))
        print(f"\n⚠️  Selected resolution={best['resolution']:.2f} → {best['mean_clusters']:.1f} clusters (CLOSEST TO TARGET)")
        print(f"   Note: No resolution produced clusters in [15, 30] range")

    return best['resolution'], results

optimal_resolution, resolution_results = find_optimal_resolution(
    mechanism_subgraph,
    target_min=15,
    target_max=30,
    trials=5
)

# ============================================================================
# STEP 5C: Execute Louvain with Optimal Resolution
# ============================================================================

print("\n" + "="*80)
print("STEP 5C: LOUVAIN CLUSTERING")
print("="*80)

print(f"\nRunning Louvain with resolution={optimal_resolution:.2f}...")

# Run Louvain with optimal resolution (seed=42 for reproducibility)
partition = community_louvain.best_partition(
    mechanism_subgraph.to_undirected(),
    resolution=optimal_resolution,
    random_state=42
)

n_clusters = len(set(partition.values()))

print(f"✅ Louvain clustering complete: {n_clusters} clusters")

# Group nodes by cluster
clusters = {}
for node, cluster_id in partition.items():
    if cluster_id not in clusters:
        clusters[cluster_id] = []
    clusters[cluster_id].append(node)

# Sort clusters by size (largest first)
clusters = {cid: nodes for cid, nodes in sorted(clusters.items(), key=lambda x: len(x[1]), reverse=True)}

# Compute cluster statistics
cluster_sizes = [len(nodes) for nodes in clusters.values()]

print(f"\nCluster size distribution:")
print(f"   Min:    {min(cluster_sizes)}")
print(f"   Median: {np.median(cluster_sizes):.1f}")
print(f"   Mean:   {np.mean(cluster_sizes):.1f}")
print(f"   Max:    {max(cluster_sizes)}")

# Check for tiny clusters (<10 nodes)
tiny_clusters = {cid: nodes for cid, nodes in clusters.items() if len(nodes) < 10}

if len(tiny_clusters) > 0:
    print(f"\n⚠️  WARNING: {len(tiny_clusters)} clusters have <10 nodes:")
    for cid, nodes in tiny_clusters.items():
        print(f"      Cluster {cid}: {len(nodes)} nodes")
    print(f"\n   These will be merged with nearest neighbors in validation step")
else:
    print(f"\n✅ All {n_clusters} clusters meet minimum size requirement (≥10 nodes)")

# Show top 5 largest clusters
print(f"\nTop 5 largest clusters:")
for i, (cid, nodes) in enumerate(list(clusters.items())[:5]):
    print(f"   Cluster {cid}: {len(nodes)} nodes ({len(nodes)/len(mechanism_candidates)*100:.1f}%)")
    # Show top 3 nodes by centrality
    top_nodes = sorted(nodes, key=lambda n: centrality_scores.get(n, 0), reverse=True)[:3]
    for node in top_nodes:
        layer = layers.get(node, -1)
        score = centrality_scores.get(node, 0)
        print(f"      - {node[:50]:50s} (L{layer}, centrality={score:.3f})")

# ============================================================================
# STEP 5D: Save Clustering Results
# ============================================================================

print("\n" + "="*80)
print("STEP 5D: SAVING RESULTS")
print("="*80)

# Save clustering results
clustering_results = {
    'resolution': float(optimal_resolution),
    'n_clusters': int(n_clusters),
    'cluster_size_distribution': {
        'min': int(min(cluster_sizes)),
        'median': float(np.median(cluster_sizes)),
        'mean': float(np.mean(cluster_sizes)),
        'max': int(max(cluster_sizes))
    },
    'tiny_clusters': {int(cid): len(nodes) for cid, nodes in tiny_clusters.items()},
    'resolution_sweep': [
        {
            'resolution': float(r['resolution']),
            'mean_clusters': float(r['mean_clusters']),
            'std_clusters': float(r['std_clusters']),
            'in_target': bool(r['in_target'])
        }
        for r in resolution_results
    ],
    'timestamp': datetime.now().isoformat()
}

with open(output_dir / "B2_clustering_results.json", 'w') as f:
    json.dump(clustering_results, f, indent=2)

print(f"✅ Clustering results saved: {output_dir}/B2_clustering_results.json")

# Save cluster assignments
cluster_assignments = []
for cid, nodes in clusters.items():
    for node in nodes:
        cluster_assignments.append({
            'node': node,
            'cluster_id': int(cid),
            'cluster_size': len(nodes),
            'centrality_score': centrality_scores.get(node, 0),
            'layer': layers.get(node, -1)
        })

cluster_df = pd.DataFrame(cluster_assignments)
cluster_df = cluster_df.sort_values(['cluster_id', 'centrality_score'], ascending=[True, False])
cluster_df.to_csv(output_dir / "B2_cluster_assignments.csv", index=False)

print(f"✅ Cluster assignments saved: {output_dir}/B2_cluster_assignments.csv")

# Save checkpoint for domain labeling
clustering_checkpoint = {
    'mechanism_subgraph': mechanism_subgraph,
    'clusters': clusters,
    'partition': partition,
    'centrality_scores': centrality_scores,
    'layers': layers,
    'optimal_resolution': optimal_resolution,
    'metadata': clustering_results
}

with open(output_dir / "B2_clustering_checkpoint.pkl", 'wb') as f:
    pickle.dump(clustering_checkpoint, f)

print(f"✅ Clustering checkpoint saved: {output_dir}/B2_clustering_checkpoint.pkl")

# ============================================================================
# SUMMARY
# ============================================================================

elapsed_time = datetime.now().timestamp() - start_time

print("\n" + "="*80)
print("LOUVAIN CLUSTERING COMPLETE")
print("="*80)

print(f"\n📊 Summary:")
print(f"   Mechanism candidates: {len(mechanism_candidates)}")
print(f"   Clusters: {n_clusters} (target: 15-30)")
print(f"   Mean cluster size: {np.mean(cluster_sizes):.1f} nodes")
print(f"   Tiny clusters (<10): {len(tiny_clusters)}")
print(f"   Optimal resolution: {optimal_resolution:.2f}")
print(f"   Runtime: {elapsed_time/60:.1f} minutes")

if 15 <= n_clusters <= 30:
    print(f"\n✅ SUCCESS: Cluster count {n_clusters} within target range [15, 30]")
else:
    print(f"\n⚠️  WARNING: Cluster count {n_clusters} outside target range [15, 30]")

if len(tiny_clusters) <= 3:
    print(f"✅ SUCCESS: Tiny clusters {len(tiny_clusters)} ≤ 3 (acceptable)")
else:
    print(f"⚠️  WARNING: {len(tiny_clusters)} tiny clusters (expected ≤3)")

print(f"\n✅ Ready for domain labeling!")
print(f"   Next step: Semantic clustering to assign domain labels")
print(f"   Expected runtime: 1-2 hours")

print(f"\n📁 Outputs:")
print(f"   - {output_dir}/B2_clustering_results.json")
print(f"   - {output_dir}/B2_cluster_assignments.csv")
print(f"   - {output_dir}/B2_clustering_checkpoint.pkl")

print(f"\n{'='*80}")
