#!/usr/bin/env python3
"""
B2 Semantic Clustering (Early B3 Method)
=========================================

Applies semantic clustering to 329 mechanism candidates using sentence-transformers:
1. Enhance variable names with domain hints
2. Compute semantic embeddings (all-MiniLM-L6-v2)
3. Determine optimal cluster count (silhouette score optimization)
4. Hierarchical clustering with optimal count
5. Merge tiny clusters (<10 nodes) into nearest neighbors
6. Label clusters by dominant domain

IMPORTANT: This is the PREPARED script for user approval.
DO NOT EXECUTE until user confirms to proceed.

Author: Phase B2 → B3 Integration
Date: November 2025
"""

import pickle
import json
import sys
from pathlib import Path
import pandas as pd
import numpy as np
from datetime import datetime

# Semantic clustering libraries
from sentence_transformers import SentenceTransformer
from sklearn.cluster import AgglomerativeClustering
from sklearn.metrics import silhouette_score
from scipy.spatial.distance import cdist

# Add project root to path
project_root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(project_root))

print("="*80)
print("B2 SEMANTIC CLUSTERING (EARLY B3 METHOD)")
print("="*80)

start_time = datetime.now().timestamp()
print(f"Start time: {datetime.fromtimestamp(start_time).strftime('%Y-%m-%d %H:%M:%S')}")

# Directories
output_dir = Path(__file__).resolve().parents[2] / "outputs"
diag_dir = Path(__file__).resolve().parents[2] / "diagnostics"

# Load bridging subgraph checkpoint
checkpoint_path = output_dir / "B2_bridging_subgraph_checkpoint.pkl"
print(f"\nLoading bridging subgraph checkpoint...")

with open(checkpoint_path, 'rb') as f:
    checkpoint = pickle.load(f)

mechanism_candidates = checkpoint['mechanism_candidates']
centrality_scores = checkpoint['centrality_scores']
layers = checkpoint['layers']

print(f"✅ Loaded checkpoint:")
print(f"   Mechanism candidates: {len(mechanism_candidates)}")

# ============================================================================
# STEP 1: Enhance Variable Names (Critical for Quality)
# ============================================================================

print("\n" + "="*80)
print("STEP 1: ENHANCING VARIABLE NAMES")
print("="*80)

def enhance_variable_name(node):
    """Convert variable code to human-readable text with domain hints"""

    # Map known prefixes to domains
    domain_hints = {
        'v2ju': 'judicial',
        'v2ps': 'political participation',
        'v2cl': 'civil liberties',
        'v2cs': 'civil society',
        'v2ex': 'executive',
        'v2el': 'elections',
        'v2dl': 'deliberation',
        'v2sm': 'social media',
        'v2me': 'media',
        'v2sv': 'sovereignty',
        'v3pe': 'political equality',
        'wdi_': 'world development indicator',
        'REPR': 'reproductive health',
        'GER': 'gross enrollment rate',
        'OAEP': 'over-age enrollment',
        'NERT': 'net enrollment rate',
        'BR': 'birth rate',
        'NW': 'natural wealth',
        'BX': 'balance of payments',
        'pwt_': 'penn world table',
        'INTERACT_': 'interaction term',
        'atop_': 'alliance treaty',
        'e_cow_': 'correlates of war',
        'opri_': 'organizational power',
        'yptf': 'youth transfer',
        'aptd': 'adult transfer',
        'wcom': 'wage compensation',
        'ygsm': 'youth government spending',
        'wgsm': 'adult government spending',
        'wpinn': 'private investment',
        'ypinn': 'youth private investment',
        'yprn': 'youth private income',
        'wprn': 'adult private income',
        'eofgh': 'economic freedom',
    }

    text = node  # Start with raw code

    # Add domain hint if prefix matches
    for prefix, hint in domain_hints.items():
        if node.lower().startswith(prefix.lower()):
            text = f"{hint} {node}"
            break

    return text

# Apply to all mechanisms
print(f"\nEnhancing variable names for {len(mechanism_candidates)} mechanisms...")
mechanism_texts_enhanced = [enhance_variable_name(node) for node in mechanism_candidates]

print(f"✅ Enhanced variable names")
print(f"\n   Sample enhanced names:")
for i, (orig, enhanced) in enumerate(list(zip(mechanism_candidates, mechanism_texts_enhanced))[:5]):
    print(f"      {orig[:40]:40s} → {enhanced[:60]}")

# ============================================================================
# STEP 2: Compute Semantic Embeddings
# ============================================================================

print("\n" + "="*80)
print("STEP 2: COMPUTING SEMANTIC EMBEDDINGS")
print("="*80)

print(f"\nLoading sentence-transformer model (all-MiniLM-L6-v2)...")
model = SentenceTransformer('all-MiniLM-L6-v2')
print(f"✅ Model loaded")

print(f"\nEmbedding {len(mechanism_texts_enhanced)} variable names...")
embeddings = model.encode(mechanism_texts_enhanced, show_progress_bar=True)

print(f"✅ Embeddings computed: {embeddings.shape}")
print(f"   Shape: ({len(mechanism_candidates)}, {embeddings.shape[1]})")
print(f"   Embedding dimension: {embeddings.shape[1]}")

# ============================================================================
# STEP 3: Determine Optimal Cluster Count (Silhouette Score)
# ============================================================================

print("\n" + "="*80)
print("STEP 3: OPTIMAL CLUSTER COUNT (SILHOUETTE OPTIMIZATION)")
print("="*80)

print(f"\nTarget cluster count: 15-30")
print(f"Testing range: [15, 16, ..., 30]")

silhouette_scores = []
cluster_range = list(range(15, 31))

print(f"\nComputing silhouette scores...")
for n_clusters in cluster_range:
    clustering = AgglomerativeClustering(n_clusters=n_clusters, linkage='ward')
    labels = clustering.fit_predict(embeddings)
    score = silhouette_score(embeddings, labels)
    silhouette_scores.append(score)

    if n_clusters % 5 == 0:
        print(f"   {n_clusters} clusters → silhouette score: {score:.3f}")

# Select cluster count with best silhouette score
best_idx = np.argmax(silhouette_scores)
best_n_clusters = cluster_range[best_idx]
best_score = silhouette_scores[best_idx]

print(f"\n✅ Optimal cluster count: {best_n_clusters} (silhouette: {best_score:.3f})")

# Show top 5 candidates
top5_idx = np.argsort(silhouette_scores)[-5:][::-1]
print(f"\n   Top 5 candidates:")
for idx in top5_idx:
    n = cluster_range[idx]
    s = silhouette_scores[idx]
    print(f"      {n} clusters: {s:.3f}")

# ============================================================================
# STEP 4: Final Clustering with Optimal Count
# ============================================================================

print("\n" + "="*80)
print("STEP 4: HIERARCHICAL CLUSTERING")
print("="*80)

print(f"\nRunning hierarchical clustering with {best_n_clusters} clusters...")
final_clustering = AgglomerativeClustering(n_clusters=best_n_clusters, linkage='ward')
final_labels = final_clustering.fit_predict(embeddings)

# Group mechanisms by cluster
semantic_clusters = {}
for node, label in zip(mechanism_candidates, final_labels):
    if label not in semantic_clusters:
        semantic_clusters[label] = []
    semantic_clusters[label].append(node)

# Sort clusters by size (largest first)
semantic_clusters = {cid: nodes for cid, nodes in sorted(semantic_clusters.items(), key=lambda x: len(x[1]), reverse=True)}

print(f"✅ Clustering complete: {len(semantic_clusters)} clusters")

# Compute cluster size statistics
cluster_sizes = [len(nodes) for nodes in semantic_clusters.values()]

print(f"\nCluster size distribution:")
print(f"   Min:    {min(cluster_sizes)}")
print(f"   Median: {np.median(cluster_sizes):.1f}")
print(f"   Mean:   {np.mean(cluster_sizes):.1f}")
print(f"   Max:    {max(cluster_sizes)}")

# Check for tiny clusters
tiny_clusters = {cid: nodes for cid, nodes in semantic_clusters.items() if len(nodes) < 10}

if len(tiny_clusters) > 0:
    print(f"\n⚠️  WARNING: {len(tiny_clusters)} clusters have <10 nodes:")
    for cid, nodes in tiny_clusters.items():
        print(f"      Cluster {cid}: {len(nodes)} nodes")
    print(f"\n   Will merge with nearest neighbors in next step")
else:
    print(f"\n✅ All {len(semantic_clusters)} clusters meet minimum size (≥10 nodes)")

# ============================================================================
# STEP 5: Merge Tiny Clusters (<10 nodes)
# ============================================================================

print("\n" + "="*80)
print("STEP 5: MERGING TINY CLUSTERS")
print("="*80)

def merge_tiny_clusters(clusters, embeddings_arr, mechanism_list, min_size=10):
    """Merge small clusters into nearest neighbors"""

    # Compute cluster centroids
    centroids = {}
    for cid, nodes in clusters.items():
        indices = [i for i, node in enumerate(mechanism_list) if node in nodes]
        centroids[cid] = np.mean(embeddings_arr[indices], axis=0)

    # Find tiny clusters
    tiny_cluster_ids = [cid for cid, nodes in clusters.items() if len(nodes) < min_size]

    if len(tiny_cluster_ids) == 0:
        print(f"\n✅ No tiny clusters to merge")
        return clusters

    print(f"\nMerging {len(tiny_cluster_ids)} tiny clusters...")

    # Merge each tiny cluster into nearest neighbor
    merged_clusters = {cid: nodes.copy() for cid, nodes in clusters.items()}

    for tiny_cid in tiny_cluster_ids:
        # Find nearest cluster (by centroid distance)
        tiny_centroid = centroids[tiny_cid]

        distances = []
        for other_cid, other_centroid in centroids.items():
            if other_cid == tiny_cid:
                continue
            if other_cid in tiny_cluster_ids:
                continue  # Don't merge into another tiny cluster
            dist = np.linalg.norm(tiny_centroid - other_centroid)
            distances.append((other_cid, dist))

        if len(distances) == 0:
            # All other clusters are tiny - merge into largest
            other_sizes = [(cid, len(nodes)) for cid, nodes in merged_clusters.items() if cid != tiny_cid]
            nearest_cid = max(other_sizes, key=lambda x: x[1])[0]
        else:
            # Merge into nearest
            nearest_cid = min(distances, key=lambda x: x[1])[0]

        merged_clusters[nearest_cid].extend(merged_clusters[tiny_cid])
        del merged_clusters[tiny_cid]

        print(f"   Merged cluster {tiny_cid} ({len(clusters[tiny_cid])} nodes) → cluster {nearest_cid}")

    return merged_clusters

# Apply merging
final_clusters = merge_tiny_clusters(
    semantic_clusters,
    embeddings,
    mechanism_candidates,
    min_size=10
)

print(f"\n✅ After merging: {len(final_clusters)} clusters")

# Recompute cluster sizes
final_cluster_sizes = [len(nodes) for nodes in final_clusters.values()]
print(f"\nFinal cluster size distribution:")
print(f"   Min:    {min(final_cluster_sizes)}")
print(f"   Median: {np.median(final_cluster_sizes):.1f}")
print(f"   Mean:   {np.mean(final_cluster_sizes):.1f}")
print(f"   Max:    {max(final_cluster_sizes)}")

# ============================================================================
# STEP 6: Label Clusters by Dominant Domain
# ============================================================================

print("\n" + "="*80)
print("STEP 6: DOMAIN LABELING")
print("="*80)

def infer_domain(variable_name):
    """Classify variable by domain based on name patterns"""
    name_lower = variable_name.lower()

    # Domain keywords
    if any(x in name_lower for x in ['v2ju', 'v2cl', 'v2ps', 'v2ex', 'v2sm', 'v2cs', 'v2el', 'v2dl', 'v2me', 'v2sv', 'v3pe']):
        return 'Governance'
    elif any(x in name_lower for x in ['wdi_mortu', 'repr', 'health', 'mortality', 'life_exp']):
        return 'Health'
    elif any(x in name_lower for x in ['ger', 'oaep', 'nert', 'educ', 'school', 'enroll']):
        return 'Education'
    elif any(x in name_lower for x in ['gdp', 'income', 'tax', 'debt', 'trade', 'econ', 'pwt_', 'bx', 'nw']):
        return 'Economic'
    elif any(x in name_lower for x in ['birth', 'fertility', 'population', 'demog', 'br']):
        return 'Demographic'
    elif any(x in name_lower for x in ['atop_', 'e_cow_', 'alliance', 'war', 'conflict']):
        return 'International'
    elif any(x in name_lower for x in ['transfer', 'spending', 'investment', 'ygsm', 'wgsm', 'yptf', 'aptd']):
        return 'Fiscal'
    else:
        return 'Mixed'

print(f"\nLabeling {len(final_clusters)} clusters by dominant domain...")

cluster_metadata = {}
for cid, nodes in final_clusters.items():
    # Count domain distribution
    domains = [infer_domain(node) for node in nodes]
    domain_counts = {}
    for d in domains:
        domain_counts[d] = domain_counts.get(d, 0) + 1

    # Primary domain = most common
    primary_domain = max(domain_counts, key=domain_counts.get)
    coherence = domain_counts[primary_domain] / len(nodes)

    # Top 5 variables by centrality
    node_centralities = [(node, centrality_scores.get(node, 0)) for node in nodes]
    top_variables = sorted(node_centralities, key=lambda x: x[1], reverse=True)[:5]

    cluster_metadata[cid] = {
        'cluster_id': int(cid),
        'cluster_name': f"{primary_domain}: Cluster {cid}",
        'primary_domain': primary_domain,
        'nodes': nodes,
        'size': len(nodes),
        'domain_distribution': {k: int(v) for k, v in domain_counts.items()},
        'coherence': float(coherence),
        'top_variables': [node for node, _ in top_variables],
        'top_centralities': [float(score) for _, score in top_variables]
    }

print(f"✅ Domain labeling complete")

# Show cluster summaries
print(f"\nCluster summaries:")
domain_summary = {}
for cid, meta in cluster_metadata.items():
    domain = meta['primary_domain']
    domain_summary[domain] = domain_summary.get(domain, 0) + 1

    print(f"\n   Cluster {cid}: {meta['cluster_name']}")
    print(f"      Size: {meta['size']} nodes")
    print(f"      Coherence: {meta['coherence']:.2%}")
    print(f"      Domain distribution: {meta['domain_distribution']}")
    print(f"      Top 3 variables: {', '.join(meta['top_variables'][:3])}")

print(f"\n📊 Domain distribution across {len(final_clusters)} clusters:")
for domain, count in sorted(domain_summary.items(), key=lambda x: x[1], reverse=True):
    print(f"   {domain}: {count} clusters")

# ============================================================================
# STEP 7: Save Results
# ============================================================================

print("\n" + "="*80)
print("STEP 7: SAVING RESULTS")
print("="*80)

# Save semantic clustering results
semantic_results = {
    'method': 'semantic_clustering',
    'model': 'all-MiniLM-L6-v2',
    'embedding_dim': int(embeddings.shape[1]),
    'optimal_n_clusters': int(best_n_clusters),
    'silhouette_score': float(best_score),
    'final_n_clusters': len(final_clusters),
    'cluster_size_distribution': {
        'min': int(min(final_cluster_sizes)),
        'median': float(np.median(final_cluster_sizes)),
        'mean': float(np.mean(final_cluster_sizes)),
        'max': int(max(final_cluster_sizes))
    },
    'domain_distribution': {k: int(v) for k, v in domain_summary.items()},
    'timestamp': datetime.now().isoformat()
}

with open(output_dir / "B2_semantic_clustering_results.json", 'w') as f:
    json.dump(semantic_results, f, indent=2)

print(f"✅ Clustering results saved: {output_dir}/B2_semantic_clustering_results.json")

# Save cluster metadata
with open(output_dir / "B2_cluster_metadata.json", 'w') as f:
    json.dump({str(k): v for k, v in cluster_metadata.items()}, f, indent=2)

print(f"✅ Cluster metadata saved: {output_dir}/B2_cluster_metadata.json")

# Save cluster assignments
cluster_assignments = []
for cid, meta in cluster_metadata.items():
    for node in meta['nodes']:
        cluster_assignments.append({
            'node': node,
            'cluster_id': int(cid),
            'cluster_name': meta['cluster_name'],
            'primary_domain': meta['primary_domain'],
            'cluster_size': meta['size'],
            'cluster_coherence': meta['coherence'],
            'centrality_score': centrality_scores.get(node, 0),
            'layer': layers.get(node, -1)
        })

cluster_df = pd.DataFrame(cluster_assignments)
cluster_df = cluster_df.sort_values(['cluster_id', 'centrality_score'], ascending=[True, False])
cluster_df.to_csv(output_dir / "B2_semantic_cluster_assignments.csv", index=False)

print(f"✅ Cluster assignments saved: {output_dir}/B2_semantic_cluster_assignments.csv")

# Save final checkpoint for B3
semantic_checkpoint = {
    'clusters': final_clusters,
    'cluster_metadata': cluster_metadata,
    'embeddings': embeddings,
    'centrality_scores': centrality_scores,
    'layers': layers,
    'results': semantic_results
}

with open(output_dir / "B2_semantic_clustering_checkpoint.pkl", 'wb') as f:
    pickle.dump(semantic_checkpoint, f)

print(f"✅ Semantic clustering checkpoint saved: {output_dir}/B2_semantic_clustering_checkpoint.pkl")

# ============================================================================
# SUMMARY
# ============================================================================

elapsed_time = datetime.now().timestamp() - start_time

print("\n" + "="*80)
print("SEMANTIC CLUSTERING COMPLETE")
print("="*80)

print(f"\n📊 Summary:")
print(f"   Mechanism candidates: {len(mechanism_candidates)}")
print(f"   Optimal cluster count: {best_n_clusters} (silhouette: {best_score:.3f})")
print(f"   Final clusters: {len(final_clusters)} (after merging)")
print(f"   Mean cluster size: {np.mean(final_cluster_sizes):.1f} nodes")
print(f"   Mean coherence: {np.mean([m['coherence'] for m in cluster_metadata.values()])*100:.1f}%")
print(f"   Runtime: {elapsed_time/60:.1f} minutes")

# Validate against success criteria
print(f"\n✅ Success Criteria:")
if 15 <= len(final_clusters) <= 30:
    print(f"   ✅ Cluster count: {len(final_clusters)} (target: 15-30)")
else:
    print(f"   ⚠️  Cluster count: {len(final_clusters)} (target: 15-30)")

if min(final_cluster_sizes) >= 10:
    print(f"   ✅ Minimum cluster size: {min(final_cluster_sizes)} (target: ≥10)")
else:
    print(f"   ⚠️  Minimum cluster size: {min(final_cluster_sizes)} (target: ≥10)")

mean_coherence = np.mean([m['coherence'] for m in cluster_metadata.values()])
if mean_coherence >= 0.60:
    print(f"   ✅ Mean coherence: {mean_coherence*100:.1f}% (target: ≥60%)")
else:
    print(f"   ⚠️  Mean coherence: {mean_coherence*100:.1f}% (target: ≥60%)")

print(f"\n✅ Ready for B3 domain classification!")
print(f"   Mechanism clusters prepared with semantic grouping")
print(f"   Expected: B3 will refine domain labels and add metadata")

print(f"\n📁 Outputs:")
print(f"   - {output_dir}/B2_semantic_clustering_results.json")
print(f"   - {output_dir}/B2_cluster_metadata.json")
print(f"   - {output_dir}/B2_semantic_cluster_assignments.csv")
print(f"   - {output_dir}/B2_semantic_clustering_checkpoint.pkl")

print(f"\n{'='*80}")
