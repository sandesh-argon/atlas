#!/usr/bin/env python3
"""
Phase B2 (Revised): Full Mechanism Clustering - NO PRUNING
===========================================================

This script processes ALL 8,126 indicators from A6 without pruning.
The purpose is to cluster indicators into semantic groups, NOT to filter them.

Key Changes from Original B2:
1. NO bridge quality filtering - all indicators are kept
2. Clustering on FULL graph (8,126 nodes)
3. Output: cluster assignments for ALL indicators

Clustering Method:
- Louvain community detection on full graph
- Resolution parameter sweep to find optimal cluster count (40-80 clusters)

Author: Phase B2 Revised
Date: December 2025
"""

import pickle
import json
import sys
from pathlib import Path
import pandas as pd
import numpy as np
import networkx as nx
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

# Project paths
project_root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(project_root))

output_dir = Path(__file__).parent.parent / "outputs"
output_dir.mkdir(exist_ok=True, parents=True)

print("="*80)
print("PHASE B2 (REVISED): FULL MECHANISM CLUSTERING - NO PRUNING")
print("="*80)

start_time = datetime.now()
print(f"Start time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")

# ============================================================================
# STEP 1: Load A6 Hierarchical Graph (FULL - no filtering)
# ============================================================================

print("\n[STEP 1] Loading A6 hierarchical graph (FULL)...")

a6_path = project_root / "phaseA/A6_hierarchical_layering/outputs/A6_hierarchical_graph.pkl"
print(f"   Loading from: {a6_path}")

with open(a6_path, 'rb') as f:
    a6_data = pickle.load(f)

G = a6_data['graph']
layers = a6_data['layers']
metadata = a6_data['metadata']

print(f"   ✅ Loaded FULL graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
print(f"   ✅ Layers: {a6_data['n_layers']} levels (0-{a6_data['n_layers']-1})")

# Node distribution by layer type
driver_nodes = [n for n, layer in layers.items() if layer == 0]
outcome_nodes = [n for n, layer in layers.items() if layer >= 19]
mechanism_nodes = [n for n, layer in layers.items() if 1 <= layer <= 18]

print(f"\n   Node distribution:")
print(f"      Drivers (L0): {len(driver_nodes)}")
print(f"      Mechanisms (L1-L18): {len(mechanism_nodes)}")
print(f"      Outcomes (L19+): {len(outcome_nodes)}")
print(f"      TOTAL: {len(layers)}")

# ============================================================================
# STEP 2: Load Indicator Labels/Metadata
# ============================================================================

print("\n[STEP 2] Loading indicator metadata...")

labels_path = project_root / "phaseB/B5_output_schema/outputs/indicator_labels_comprehensive.json"

if labels_path.exists():
    with open(labels_path, 'r') as f:
        indicator_labels = json.load(f)
    print(f"   ✅ Loaded labels for {len(indicator_labels)} indicators")
else:
    print(f"   ⚠️  No labels file found, using indicator IDs as labels")
    indicator_labels = {}

# ============================================================================
# STEP 3: Compute Centrality Scores for ALL nodes
# ============================================================================

print("\n[STEP 3] Computing centrality scores for ALL nodes...")

# Convert to undirected for community detection (Louvain requires undirected)
G_undirected = G.to_undirected()
print(f"   Converted to undirected: {G_undirected.number_of_edges()} edges")

# PageRank (on directed graph)
print(f"   Computing PageRank...")
pagerank = nx.pagerank(G, alpha=0.85, max_iter=100)
print(f"   ✅ PageRank computed")

# Degree centrality (on undirected)
print(f"   Computing degree centrality...")
degree_centrality = nx.degree_centrality(G_undirected)
print(f"   ✅ Degree centrality computed")

# Save centrality scores
centrality_scores = {
    'pagerank': pagerank,
    'degree': degree_centrality
}

print(f"\n   Centrality statistics:")
pr_values = list(pagerank.values())
print(f"      PageRank: min={min(pr_values):.6f}, max={max(pr_values):.6f}, mean={np.mean(pr_values):.6f}")
deg_values = list(degree_centrality.values())
print(f"      Degree:   min={min(deg_values):.6f}, max={max(deg_values):.6f}, mean={np.mean(deg_values):.6f}")

# ============================================================================
# STEP 4: Louvain Community Detection (Resolution Sweep)
# ============================================================================

print("\n[STEP 4] Running Louvain community detection...")

# Target: 40-80 clusters (semantic groupings)
TARGET_CLUSTERS_MIN = 40
TARGET_CLUSTERS_MAX = 100

# Resolution sweep
resolutions = [0.3, 0.5, 0.7, 1.0, 1.2, 1.5, 2.0, 2.5, 3.0]
best_partition = None
best_resolution = None
best_n_clusters = 0
best_modularity = 0

print(f"   Sweeping resolutions: {resolutions}")
print(f"   Target cluster range: {TARGET_CLUSTERS_MIN}-{TARGET_CLUSTERS_MAX}")

for resolution in resolutions:
    partition = community_louvain.best_partition(G_undirected, resolution=resolution, random_state=42)
    n_clusters = len(set(partition.values()))
    modularity = community_louvain.modularity(partition, G_undirected)

    print(f"      Resolution {resolution:.1f}: {n_clusters} clusters, modularity={modularity:.4f}")

    # Check if in target range and better modularity
    if TARGET_CLUSTERS_MIN <= n_clusters <= TARGET_CLUSTERS_MAX:
        if modularity > best_modularity:
            best_partition = partition
            best_resolution = resolution
            best_n_clusters = n_clusters
            best_modularity = modularity
    elif best_partition is None:
        # Keep track of closest if none in range yet
        if n_clusters >= TARGET_CLUSTERS_MIN:
            best_partition = partition
            best_resolution = resolution
            best_n_clusters = n_clusters
            best_modularity = modularity

# If still no good partition, use resolution 1.0
if best_partition is None:
    print(f"\n   ⚠️  No resolution in target range, using default resolution=1.0")
    best_partition = community_louvain.best_partition(G_undirected, resolution=1.0, random_state=42)
    best_resolution = 1.0
    best_n_clusters = len(set(best_partition.values()))
    best_modularity = community_louvain.modularity(best_partition, G_undirected)

print(f"\n   ✅ Selected: resolution={best_resolution}, clusters={best_n_clusters}, modularity={best_modularity:.4f}")

# ============================================================================
# STEP 5: Analyze Cluster Composition
# ============================================================================

print("\n[STEP 5] Analyzing cluster composition...")

# Cluster statistics
cluster_sizes = Counter(best_partition.values())
cluster_stats = []

for cluster_id in sorted(cluster_sizes.keys()):
    size = cluster_sizes[cluster_id]

    # Get nodes in this cluster
    cluster_nodes = [n for n, c in best_partition.items() if c == cluster_id]

    # Layer distribution
    cluster_layers = [layers.get(n, -1) for n in cluster_nodes]
    layer_distribution = Counter(cluster_layers)

    # Mean PageRank
    cluster_pagerank = [pagerank.get(n, 0) for n in cluster_nodes]
    mean_pagerank = np.mean(cluster_pagerank)

    # Sample indicators (top 5 by PageRank)
    sorted_nodes = sorted(cluster_nodes, key=lambda x: pagerank.get(x, 0), reverse=True)
    top_nodes = sorted_nodes[:5]

    cluster_stats.append({
        'cluster_id': cluster_id,
        'size': size,
        'mean_pagerank': mean_pagerank,
        'layer_distribution': dict(layer_distribution),
        'top_nodes': top_nodes,
        'sample_labels': [indicator_labels.get(n, {}).get('label', n) for n in top_nodes[:3]]
    })

# Sort by size (largest first)
cluster_stats.sort(key=lambda x: x['size'], reverse=True)

print(f"\n   Cluster size distribution:")
print(f"      Largest:  {cluster_stats[0]['size']} nodes")
print(f"      Smallest: {cluster_stats[-1]['size']} nodes")
print(f"      Median:   {np.median([c['size'] for c in cluster_stats]):.0f} nodes")
print(f"      Mean:     {np.mean([c['size'] for c in cluster_stats]):.1f} nodes")

print(f"\n   Top 10 clusters by size:")
for cs in cluster_stats[:10]:
    sample_labels = ', '.join(cs['sample_labels'][:2])
    print(f"      Cluster {cs['cluster_id']:2d}: {cs['size']:4d} nodes | Sample: {sample_labels[:60]}...")

# ============================================================================
# STEP 6: Assign Domain Labels (from indicator metadata)
# ============================================================================

print("\n[STEP 6] Assigning preliminary domain labels to clusters...")

# Domain keywords for classification
DOMAIN_KEYWORDS = {
    'Governance': ['v2', 'vdem', 'polity', 'democracy', 'corruption', 'rule', 'law', 'electoral', 'executive', 'judicial', 'legislative'],
    'Education': ['edu', 'school', 'literacy', 'enrollment', 'unesco', 'attainment', 'completion', 'teacher', 'pupil'],
    'Health': ['health', 'mortality', 'life', 'disease', 'medical', 'physician', 'hospital', 'vaccine', 'birth', 'death'],
    'Economic': ['gdp', 'gni', 'trade', 'export', 'import', 'investment', 'inflation', 'employment', 'wage', 'income'],
    'Infrastructure': ['electric', 'water', 'sanitation', 'internet', 'mobile', 'road', 'transport'],
    'Environment': ['emission', 'forest', 'land', 'pollution', 'climate', 'carbon'],
    'Social': ['population', 'gender', 'inequality', 'poverty', 'social', 'welfare']
}

def classify_cluster_domain(cluster_nodes, indicator_labels):
    """Classify cluster domain based on indicator names and labels"""
    domain_scores = {d: 0 for d in DOMAIN_KEYWORDS}

    for node in cluster_nodes:
        # Check node ID
        node_lower = node.lower()

        # Check label if available
        label = indicator_labels.get(node, {}).get('label', '').lower()
        desc = indicator_labels.get(node, {}).get('description', '').lower()

        text = f"{node_lower} {label} {desc}"

        for domain, keywords in DOMAIN_KEYWORDS.items():
            for kw in keywords:
                if kw in text:
                    domain_scores[domain] += 1

    # Get top domain
    if max(domain_scores.values()) > 0:
        top_domain = max(domain_scores, key=domain_scores.get)
        return top_domain, domain_scores[top_domain]
    return 'Mixed', 0

# Classify each cluster
for cs in cluster_stats:
    cluster_nodes = [n for n, c in best_partition.items() if c == cs['cluster_id']]
    domain, score = classify_cluster_domain(cluster_nodes, indicator_labels)
    cs['primary_domain'] = domain
    cs['domain_score'] = score

# Domain distribution
domain_counts = Counter([cs['primary_domain'] for cs in cluster_stats])
print(f"\n   Domain distribution across clusters:")
for domain, count in domain_counts.most_common():
    print(f"      {domain}: {count} clusters")

# ============================================================================
# STEP 7: Save Results
# ============================================================================

print("\n[STEP 7] Saving results...")

# Full clustering results
results = {
    'partition': best_partition,  # node_id -> cluster_id
    'n_clusters': best_n_clusters,
    'resolution': best_resolution,
    'modularity': best_modularity,
    'cluster_stats': cluster_stats,
    'centrality_scores': centrality_scores,
    'layers': layers,  # Preserve A6 layers for reference
    'metadata': {
        'n_nodes': G.number_of_nodes(),
        'n_edges': G.number_of_edges(),
        'timestamp': datetime.now().isoformat(),
        'method': 'Louvain community detection (no pruning)',
        'target_clusters': f'{TARGET_CLUSTERS_MIN}-{TARGET_CLUSTERS_MAX}'
    }
}

# Save pickle
output_path = output_dir / "B2_full_clustering.pkl"
with open(output_path, 'wb') as f:
    pickle.dump(results, f)
print(f"   ✅ Saved: {output_path}")

# Save JSON summary
json_summary = {
    'n_clusters': best_n_clusters,
    'n_nodes': G.number_of_nodes(),
    'resolution': best_resolution,
    'modularity': best_modularity,
    'cluster_sizes': {str(cs['cluster_id']): cs['size'] for cs in cluster_stats},
    'cluster_domains': {str(cs['cluster_id']): cs['primary_domain'] for cs in cluster_stats},
    'domain_distribution': dict(domain_counts),
    'timestamp': datetime.now().isoformat()
}

json_path = output_dir / "B2_full_clustering_summary.json"
with open(json_path, 'w') as f:
    json.dump(json_summary, f, indent=2)
print(f"   ✅ Saved: {json_path}")

# ============================================================================
# SUMMARY
# ============================================================================

elapsed = (datetime.now() - start_time).total_seconds()
print("\n" + "="*80)
print("B2 FULL CLUSTERING COMPLETE")
print("="*80)

print(f"""
Summary:
   Total nodes clustered: {G.number_of_nodes()} (ALL indicators - NO PRUNING)
   Number of clusters: {best_n_clusters}
   Resolution: {best_resolution}
   Modularity: {best_modularity:.4f}

   Domain distribution:
""")
for domain, count in domain_counts.most_common():
    print(f"      {domain}: {count} clusters")

print(f"""
   Runtime: {elapsed/60:.1f} minutes

Output files:
   - {output_path}
   - {json_path}

Next step: Run B3.5 semantic hierarchy builder
""")
