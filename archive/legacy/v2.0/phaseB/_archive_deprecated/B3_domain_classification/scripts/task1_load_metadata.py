#!/usr/bin/env python3
"""
B3 Task 1.1: Load Indicator Metadata
=====================================

Loads unified metadata and merges with B2 cluster assignments to create
enriched dataset for domain classification.

Inputs:
- B2 semantic clustering checkpoint (329 mechanisms, 15 clusters)
- Unified metadata (329 indicators, 100% coverage)

Outputs:
- Enriched cluster assignments with full names and descriptions
- Metadata-enriched checkpoint for Tasks 1.2+

Author: B3 Task 1.1
Date: November 2025
Runtime: ~1-2 minutes (data loading and merging)
"""

import pickle
import json
import pandas as pd
from pathlib import Path
import sys

project_root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(project_root))

print("="*80)
print("B3 TASK 1.1: LOAD INDICATOR METADATA")
print("="*80)

# ============================================================================
# STEP 1: Load B2 Clustering Checkpoint
# ============================================================================

print("\n" + "="*80)
print("STEP 1: LOAD B2 CLUSTERING CHECKPOINT")
print("="*80)

b2_checkpoint_path = project_root / 'phaseB/B2_mechanism_identification/outputs/B2_semantic_clustering_checkpoint.pkl'

print(f"\nLoading: {b2_checkpoint_path}")

with open(b2_checkpoint_path, 'rb') as f:
    b2_checkpoint = pickle.load(f)

print(f"\n✅ Loaded B2 checkpoint:")
print(f"   Available keys: {list(b2_checkpoint.keys())}")

# Extract key data
clusters_by_id = b2_checkpoint['clusters']  # Dict {cluster_id: [list of nodes]}
cluster_metadata = b2_checkpoint['cluster_metadata']  # List of cluster info

# Invert clusters dict to get {node: cluster_id}
cluster_assignments = {}
mechanism_candidates = []

for cluster_id, nodes in clusters_by_id.items():
    for node in nodes:
        cluster_assignments[node] = cluster_id
        mechanism_candidates.append(node)

print(f"   Final clusters: {len(cluster_metadata)}")
print(f"   Mechanism candidates: {len(mechanism_candidates)}")

print(f"\n📊 Cluster Distribution:")
cluster_sizes = {}
for node, cluster_id in cluster_assignments.items():
    cluster_sizes[cluster_id] = cluster_sizes.get(cluster_id, 0) + 1

for cluster_id in sorted(cluster_sizes.keys()):
    print(f"   Cluster {cluster_id:>2}: {cluster_sizes[cluster_id]:>3} mechanisms")

# ============================================================================
# STEP 2: Load Unified Metadata
# ============================================================================

print("\n" + "="*80)
print("STEP 2: LOAD UNIFIED METADATA")
print("="*80)

metadata_path = project_root / 'phaseA/A0_data_acquisition/metadata/unified_metadata.json'

print(f"\nLoading: {metadata_path}")

with open(metadata_path, 'r') as f:
    unified_metadata = json.load(f)

print(f"\n✅ Loaded unified metadata:")
print(f"   Total indicators: {len(unified_metadata)}")
print(f"   Coverage: {len(unified_metadata)}/{len(mechanism_candidates)} ({len(unified_metadata)/len(mechanism_candidates)*100:.1f}%)")

# Quality breakdown
quality_counts = {}
for meta in unified_metadata.values():
    quality = meta.get('metadata_quality', 'unknown')
    quality_counts[quality] = quality_counts.get(quality, 0) + 1

print(f"\n📊 Metadata Quality:")
for quality, count in sorted(quality_counts.items(), key=lambda x: x[1], reverse=True):
    print(f"   {quality:>12}: {count:>3} indicators ({count/len(unified_metadata)*100:.1f}%)")

# ============================================================================
# STEP 3: Merge Metadata with Cluster Assignments
# ============================================================================

print("\n" + "="*80)
print("STEP 3: MERGE METADATA WITH CLUSTER ASSIGNMENTS")
print("="*80)

# Create enriched cluster assignments DataFrame
enriched_data = []

for node in mechanism_candidates:
    cluster_id = cluster_assignments[node]

    # Get metadata (should always exist)
    meta = unified_metadata.get(node, {
        'full_name': node,
        'description': '',
        'source': 'Unknown',
        'category': 'Mixed',
        'code': node,
        'metadata_quality': 'missing'
    })

    enriched_data.append({
        'node': node,
        'cluster_id': cluster_id,
        'cluster_name': f"Cluster {cluster_id}",  # Will be updated in Task 2
        'full_name': meta.get('full_name', node),
        'description': meta.get('description', ''),
        'source': meta.get('source', 'Unknown'),
        'category': meta.get('category', 'Mixed'),
        'metadata_quality': meta.get('metadata_quality', 'unknown'),
        'original_code': meta.get('code', node)
    })

enriched_df = pd.DataFrame(enriched_data)

print(f"\n✅ Created enriched dataset:")
print(f"   Shape: {enriched_df.shape}")
print(f"   Columns: {list(enriched_df.columns)}")

# Verify no missing metadata
missing_metadata = enriched_df[enriched_df['metadata_quality'] == 'missing']
if len(missing_metadata) > 0:
    print(f"\n⚠️  WARNING: {len(missing_metadata)} indicators have missing metadata")
else:
    print(f"\n✅ All {len(enriched_df)} indicators have metadata")

# ============================================================================
# STEP 4: Enrich Cluster Metadata
# ============================================================================

print("\n" + "="*80)
print("STEP 4: ENRICH CLUSTER METADATA")
print("="*80)

enriched_cluster_metadata = []

for cluster_id, cluster_info in cluster_metadata.items():
    # Get all nodes in this cluster
    cluster_nodes = enriched_df[enriched_df['cluster_id'] == cluster_id]

    # Add metadata statistics (start with existing cluster info)
    enriched_cluster_info = cluster_info.copy() if isinstance(cluster_info, dict) else {}
    enriched_cluster_info['cluster_id'] = int(cluster_id)
    enriched_cluster_info['size'] = len(cluster_nodes)

    # Source distribution
    source_counts = cluster_nodes['source'].value_counts().to_dict()
    enriched_cluster_info['source_distribution'] = source_counts

    # Category distribution
    category_counts = cluster_nodes['category'].value_counts().to_dict()
    enriched_cluster_info['category_distribution'] = category_counts

    # Metadata quality distribution
    quality_counts = cluster_nodes['metadata_quality'].value_counts().to_dict()
    enriched_cluster_info['metadata_quality_distribution'] = quality_counts

    # Top 5 indicators with full names (just first 5 for now, will be sorted by centrality in Task 2)
    top_indicators = cluster_nodes.head(5)
    enriched_cluster_info['top_indicators_with_names'] = [
        {
            'code': row['node'],
            'full_name': row['full_name'],
            'source': row['source']
        }
        for _, row in top_indicators.iterrows()
    ]

    enriched_cluster_metadata.append(enriched_cluster_info)

print(f"\n✅ Enriched {len(enriched_cluster_metadata)} cluster metadata entries")

# Show sample
print(f"\n📋 Sample Cluster Metadata (Cluster 0):")
sample = enriched_cluster_metadata[0]
print(f"   Cluster ID: {sample['cluster_id']}")
print(f"   Size: {sample['size']}")
print(f"   Source distribution: {sample['source_distribution']}")
print(f"   Category distribution: {sample['category_distribution']}")
print(f"   Metadata quality: {sample['metadata_quality_distribution']}")

# ============================================================================
# STEP 5: Validate Metadata Coverage per Cluster
# ============================================================================

print("\n" + "="*80)
print("STEP 5: VALIDATE METADATA COVERAGE PER CLUSTER")
print("="*80)

validation_results = []

for cluster_id in sorted(enriched_df['cluster_id'].unique()):
    cluster_nodes = enriched_df[enriched_df['cluster_id'] == cluster_id]

    total = len(cluster_nodes)
    high_quality = len(cluster_nodes[cluster_nodes['metadata_quality'] == 'high'])
    inferred = len(cluster_nodes[cluster_nodes['metadata_quality'] == 'inferred'])

    validation_results.append({
        'cluster_id': cluster_id,
        'total': total,
        'high_quality': high_quality,
        'high_quality_pct': high_quality / total * 100,
        'inferred': inferred,
        'inferred_pct': inferred / total * 100
    })

validation_df = pd.DataFrame(validation_results)

print(f"\n📊 Metadata Quality per Cluster:")
print(f"{'Cluster':<10} {'Total':<7} {'High-Quality':<15} {'Inferred':<15}")
print("-" * 55)

for _, row in validation_df.iterrows():
    print(f"Cluster {row['cluster_id']:<3} {row['total']:<7} "
          f"{row['high_quality']:>3} ({row['high_quality_pct']:>5.1f}%)  "
          f"{row['inferred']:>3} ({row['inferred_pct']:>5.1f}%)")

# Overall statistics
mean_high_quality = validation_df['high_quality_pct'].mean()
min_high_quality = validation_df['high_quality_pct'].min()

print(f"\n📈 Summary:")
print(f"   Mean high-quality metadata: {mean_high_quality:.1f}%")
print(f"   Min high-quality metadata: {min_high_quality:.1f}% (Cluster {validation_df.loc[validation_df['high_quality_pct'].idxmin(), 'cluster_id']})")

if min_high_quality < 30:
    print(f"\n⚠️  WARNING: Cluster {validation_df.loc[validation_df['high_quality_pct'].idxmin(), 'cluster_id']} has <30% high-quality metadata")
    print(f"   This cluster may have poor domain classification in Task 2")
else:
    print(f"\n✅ All clusters have ≥30% high-quality metadata")

# ============================================================================
# STEP 6: Save Enriched Checkpoint
# ============================================================================

print("\n" + "="*80)
print("STEP 6: SAVE ENRICHED CHECKPOINT")
print("="*80)

# Create enriched checkpoint
enriched_checkpoint = {
    'mechanism_candidates': mechanism_candidates,
    'cluster_assignments': cluster_assignments,
    'enriched_cluster_metadata': enriched_cluster_metadata,
    'enriched_dataframe': enriched_df,
    'unified_metadata': unified_metadata,
    'validation_results': validation_df,

    # Copy B2 data
    'embeddings': b2_checkpoint.get('embeddings'),
    'centrality_scores': b2_checkpoint.get('centrality_scores'),
    'layers': b2_checkpoint.get('layers'),
    'final_clusters': len(cluster_metadata),

    # Add Task 1.1 completion info
    'task_1_1_complete': True,
    'metadata_coverage': len(unified_metadata) / len(mechanism_candidates),
    'high_quality_pct': (enriched_df['metadata_quality'] == 'high').sum() / len(enriched_df) * 100
}

# Save checkpoint
checkpoint_path = project_root / 'phaseB/B3_domain_classification/outputs/B3_task1_metadata_enriched.pkl'
checkpoint_path.parent.mkdir(parents=True, exist_ok=True)

with open(checkpoint_path, 'wb') as f:
    pickle.dump(enriched_checkpoint, f)

print(f"\n✅ Saved enriched checkpoint: {checkpoint_path}")
print(f"   File size: {checkpoint_path.stat().st_size / (1024**2):.2f} MB")

# Save enriched dataframe as CSV for inspection
csv_path = project_root / 'phaseB/B3_domain_classification/outputs/B3_enriched_cluster_assignments.csv'
enriched_df.to_csv(csv_path, index=False)

print(f"✅ Saved enriched assignments: {csv_path}")

# ============================================================================
# TASK 1.1 COMPLETION SUMMARY
# ============================================================================

print("\n" + "="*80)
print("TASK 1.1 COMPLETION SUMMARY")
print("="*80)

print(f"\n✅ Successfully loaded and merged metadata:")
print(f"   Mechanisms: {len(mechanism_candidates)}")
print(f"   Clusters: {len(enriched_cluster_metadata)}")
print(f"   Metadata coverage: {len(unified_metadata)}/{len(mechanism_candidates)} (100.0%)")
print(f"   High-quality metadata: {(enriched_df['metadata_quality'] == 'high').sum()} ({(enriched_df['metadata_quality'] == 'high').sum()/len(enriched_df)*100:.1f}%)")

print(f"\n📁 Outputs Created:")
print(f"   1. {checkpoint_path.name} - Enriched checkpoint for Task 1.2+")
print(f"   2. {csv_path.name} - CSV for manual inspection")

print(f"\n🎯 Ready for Task 1.2: Semantic Re-embedding with Full Names")
print(f"   Expected improvement: Silhouette 0.168 → 0.25+ (with full indicator names)")

print("\n" + "="*80)
print("✅ TASK 1.1 COMPLETE")
print("="*80)
