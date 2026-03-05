#!/usr/bin/env python3
"""
B4 Task 1: Load & Prepare Data
================================

Loads B3, A6, A4 checkpoints, extracts relevant subgraphs, and prepares data for SHAP computation.

Outputs:
- B4_prepared_data.pkl: Combined dataset ready for Task 2
- B4_beta_clipping_metadata.json: Documentation of extreme beta handling

Author: B4 Task 1
Date: November 2025
"""

import pickle
import json
from pathlib import Path
import pandas as pd
import networkx as nx
import numpy as np
from datetime import datetime

# ============================================================================
# Setup
# ============================================================================

project_root = Path(__file__).resolve().parents[3]
b4_dir = project_root / 'phaseB/B4_multi_level_pruning'
outputs_dir = b4_dir / 'outputs'
outputs_dir.mkdir(exist_ok=True, parents=True)

print("="*80)
print("B4 TASK 1: LOAD & PREPARE DATA")
print("="*80)
print(f"\nTimestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"Estimated duration: 35 minutes")

# ============================================================================
# Step 1: Load B3 Checkpoint
# ============================================================================

print("\n" + "="*80)
print("STEP 1: LOAD B3 DOMAIN CLASSIFICATION")
print("="*80)

b3_path = project_root / 'phaseB/B3_domain_classification/outputs/B3_part4_enriched.pkl'
print(f"\nLoading: {b3_path}")

with open(b3_path, 'rb') as f:
    b3_data = pickle.load(f)

# Extract classified clusters (exclude Cluster 0)
all_clusters = b3_data['enriched_cluster_metadata']
classified_clusters = [c for c in all_clusters if c['primary_domain'] != 'Unclassified']

print(f"\n✅ B3 Data Loaded:")
print(f"   - Total clusters: {len(all_clusters)}")
print(f"   - Classified clusters: {len(classified_clusters)}")

# Extract mechanisms from classified clusters
b3_mechanisms = set()
for cluster in classified_clusters:
    b3_mechanisms.update(cluster['nodes'])

print(f"   - Total mechanisms: {len(b3_mechanisms)}")

# Extract domain distribution
domain_counts = {}
for cluster in classified_clusters:
    domain = cluster['primary_domain']
    domain_counts[domain] = domain_counts.get(domain, 0) + 1

print(f"\n📊 Domain Distribution:")
for domain, count in sorted(domain_counts.items(), key=lambda x: -x[1]):
    pct = count / len(classified_clusters)
    print(f"   - {domain}: {count} clusters ({pct:.1%})")

# ============================================================================
# Step 2: Load A6 Hierarchical Graph
# ============================================================================

print("\n" + "="*80)
print("STEP 2: LOAD A6 HIERARCHICAL GRAPH")
print("="*80)

a6_path = project_root / 'phaseA/A6_hierarchical_layering/outputs/A6_hierarchical_graph.pkl'
print(f"\nLoading: {a6_path}")

with open(a6_path, 'rb') as f:
    a6_data = pickle.load(f)

# Extract graph and layers
G_full = a6_data['graph']
if 'layer_assignments' in a6_data:
    layer_assignments = a6_data['layer_assignments']
else:
    layer_assignments = a6_data['layers']

print(f"\n✅ A6 Graph Loaded:")
print(f"   - Total nodes: {G_full.number_of_nodes():,}")
print(f"   - Total edges: {G_full.number_of_edges():,}")
print(f"   - Is DAG: {nx.is_directed_acyclic_graph(G_full)}")

# Extract subgraph for B3 mechanisms
print(f"\n📊 Extracting subgraph for {len(b3_mechanisms)} B3 mechanisms...")

# Find nodes present in both
b3_in_a6 = b3_mechanisms & set(G_full.nodes())
print(f"   - B3 mechanisms in A6: {len(b3_in_a6)} ({len(b3_in_a6)/len(b3_mechanisms):.1%})")

# Create subgraph (include all ancestors and descendants)
subgraph_nodes = set(b3_in_a6)

# Add all ancestors (nodes that point to B3 mechanisms)
print("   - Adding ancestors...")
for node in b3_in_a6:
    ancestors = nx.ancestors(G_full, node)
    subgraph_nodes.update(ancestors)

# Add all descendants (nodes pointed to by B3 mechanisms)
print("   - Adding descendants...")
for node in b3_in_a6:
    descendants = nx.descendants(G_full, node)
    subgraph_nodes.update(descendants)

G_subgraph = G_full.subgraph(subgraph_nodes).copy()

print(f"\n✅ Subgraph Created:")
print(f"   - Nodes: {G_subgraph.number_of_nodes():,}")
print(f"   - Edges: {G_subgraph.number_of_edges():,}")
print(f"   - Is DAG: {nx.is_directed_acyclic_graph(G_subgraph)}")

# ============================================================================
# Step 3: Load A4 Effect Estimates
# ============================================================================

print("\n" + "="*80)
print("STEP 3: LOAD A4 EFFECT ESTIMATES")
print("="*80)

a4_path = project_root / 'phaseA/A4_effect_quantification/outputs/lasso_effect_estimates_WITH_WARNINGS.pkl'
print(f"\nLoading: {a4_path}")

with open(a4_path, 'rb') as f:
    a4_data = pickle.load(f)

# Extract effects (handle multiple possible field names)
if 'all_results' in a4_data:
    effects_data = a4_data['all_results']
elif 'validated_edges' in a4_data:
    effects_data = a4_data['validated_edges']
elif 'effects' in a4_data:
    effects_data = a4_data['effects']
else:
    effects_data = a4_data['edge_effects']

# Convert to DataFrame if needed
if isinstance(effects_data, list):
    effects_df = pd.DataFrame(effects_data)
else:
    effects_df = effects_data.copy()

print(f"\n✅ A4 Effects Loaded:")
print(f"   - Total effect estimates: {len(effects_df):,}")

# Find beta column
beta_col = None
for col in ['beta', 'coefficient', 'effect']:
    if col in effects_df.columns:
        beta_col = col
        break

if beta_col is None:
    raise ValueError("No beta/coefficient column found in A4 data")

print(f"   - Beta column: '{beta_col}'")

# ============================================================================
# Step 4: Document Extreme Beta Values (NEW - Critical Addition)
# ============================================================================

print("\n" + "="*80)
print("STEP 4: DOCUMENT & CLIP EXTREME BETA VALUES")
print("="*80)

# Get beta statistics BEFORE clipping
beta_values = effects_df[beta_col].dropna()
beta_min_orig = beta_values.min()
beta_max_orig = beta_values.max()
beta_mean = beta_values.mean()
beta_median = beta_values.median()

print(f"\n📊 Original Beta Statistics:")
print(f"   - Range: [{beta_min_orig:.2f}, {beta_max_orig:.2f}]")
print(f"   - Mean: {beta_mean:.3f}")
print(f"   - Median: {beta_median:.3f}")

# Identify extreme betas (|beta| > 10)
extreme_betas = effects_df[effects_df[beta_col].abs() > 10]
extreme_pct = len(extreme_betas) / len(effects_df)

print(f"\n⚠️  Extreme Beta Values (|β| > 10):")
print(f"   - Count: {len(extreme_betas):,} ({extreme_pct:.2%})")
print(f"   - Min extreme: {extreme_betas[beta_col].min():.2f}")
print(f"   - Max extreme: {extreme_betas[beta_col].max():.2f}")

# Preserve original betas
effects_df['beta_original'] = effects_df[beta_col]

# Clip to [-10, 10]
effects_df[beta_col] = effects_df[beta_col].clip(-10, 10)

# Get statistics AFTER clipping
beta_values_clipped = effects_df[beta_col].dropna()
clipped_count = (effects_df[beta_col] != effects_df['beta_original']).sum()
clipped_pct = clipped_count / len(effects_df)

print(f"\n✅ Beta Clipping Applied:")
print(f"   - Clipped count: {clipped_count:,} ({clipped_pct:.2%})")
print(f"   - New range: [{beta_values_clipped.min():.2f}, {beta_values_clipped.max():.2f}]")
print(f"   - New mean: {beta_values_clipped.mean():.3f}")
print(f"   - New median: {beta_values_clipped.median():.3f}")

# Save clipping metadata
clipping_metadata = {
    'timestamp': datetime.now().isoformat(),
    'total_effects': len(effects_df),
    'clipped_count': int(clipped_count),
    'clipped_pct': float(clipped_pct),
    'clip_range': [-10, 10],
    'original_range': [float(beta_min_orig), float(beta_max_orig)],
    'clipped_range': [float(beta_values_clipped.min()), float(beta_values_clipped.max())],
    'original_stats': {
        'mean': float(beta_mean),
        'median': float(beta_median)
    },
    'clipped_stats': {
        'mean': float(beta_values_clipped.mean()),
        'median': float(beta_values_clipped.median())
    },
    'justification': (
        "Effect estimates clipped to [-10, 10] to handle scale artifacts. "
        "Preserves ordinal rankings while preventing extreme values from dominating SHAP computation. "
        "Original values preserved in 'beta_original' column for reference."
    )
}

clipping_path = outputs_dir / 'B4_beta_clipping_metadata.json'
with open(clipping_path, 'w') as f:
    json.dump(clipping_metadata, f, indent=2)

print(f"\n✅ Saved clipping metadata: {clipping_path}")

# ============================================================================
# Step 5: Merge Data & Create Prepared Dataset
# ============================================================================

print("\n" + "="*80)
print("STEP 5: MERGE DATA & CREATE PREPARED DATASET")
print("="*80)

# Filter effects to only include edges in subgraph
print(f"\n📊 Filtering effects to subgraph edges...")
subgraph_edges = set(G_subgraph.edges())

# Create edge tuples from effects
effects_df['edge_tuple'] = list(zip(effects_df['source'], effects_df['target']))
effects_in_subgraph = effects_df[effects_df['edge_tuple'].isin(subgraph_edges)]

print(f"   - Original effects: {len(effects_df):,}")
print(f"   - Effects in subgraph: {len(effects_in_subgraph):,}")
print(f"   - Retention: {len(effects_in_subgraph)/len(effects_df):.1%}")

# Create prepared data structure
prepared_data = {
    'metadata': {
        'timestamp': datetime.now().isoformat(),
        'task': 'B4_task1_load_and_prepare',
        'version': '2.0',
        'inputs': {
            'b3_checkpoint': str(b3_path),
            'a6_checkpoint': str(a6_path),
            'a4_checkpoint': str(a4_path)
        }
    },
    'b3_data': {
        'all_clusters': all_clusters,
        'classified_clusters': classified_clusters,
        'mechanisms': list(b3_mechanisms),
        'domain_distribution': domain_counts
    },
    'graph': {
        'full_graph': G_full,
        'subgraph': G_subgraph,
        'layer_assignments': layer_assignments
    },
    'effects': {
        'all_effects': effects_df,
        'subgraph_effects': effects_in_subgraph,
        'beta_column': beta_col,
        'clipping_applied': True
    },
    'statistics': {
        'b3_clusters': len(classified_clusters),
        'b3_mechanisms': len(b3_mechanisms),
        'a6_full_nodes': G_full.number_of_nodes(),
        'a6_full_edges': G_full.number_of_edges(),
        'subgraph_nodes': G_subgraph.number_of_nodes(),
        'subgraph_edges': G_subgraph.number_of_edges(),
        'total_effects': len(effects_df),
        'subgraph_effects': len(effects_in_subgraph),
        'beta_clipped_count': int(clipped_count),
        'beta_clipped_pct': float(clipped_pct)
    }
}

# Save prepared data
prepared_path = outputs_dir / 'B4_prepared_data.pkl'
with open(prepared_path, 'wb') as f:
    pickle.dump(prepared_data, f, protocol=pickle.HIGHEST_PROTOCOL)

print(f"\n✅ Saved prepared data: {prepared_path}")

# ============================================================================
# Summary
# ============================================================================

print("\n" + "="*80)
print("TASK 1 COMPLETE - SUMMARY")
print("="*80)

print(f"\n📊 Data Loaded:")
print(f"   - B3: {len(classified_clusters)} clusters, {len(b3_mechanisms)} mechanisms")
print(f"   - A6: {G_full.number_of_nodes():,} nodes, {G_full.number_of_edges():,} edges")
print(f"   - A4: {len(effects_df):,} effect estimates")

print(f"\n📊 Subgraph Extracted:")
print(f"   - Nodes: {G_subgraph.number_of_nodes():,}")
print(f"   - Edges: {G_subgraph.number_of_edges():,}")
print(f"   - Effects: {len(effects_in_subgraph):,}")

print(f"\n📊 Beta Clipping:")
print(f"   - Original range: [{beta_min_orig:.2f}, {beta_max_orig:.2f}]")
print(f"   - Clipped range: [-10, 10]")
print(f"   - Affected: {clipped_count:,} effects ({clipped_pct:.2%})")

print(f"\n✅ Outputs:")
print(f"   - {prepared_path.name} ({prepared_path.stat().st_size / (1024**2):.1f} MB)")
print(f"   - {clipping_path.name} ({clipping_path.stat().st_size / 1024:.1f} KB)")

print(f"\n🎯 Next Step: Task 2 - SHAP Computation (2-3 hours)")
print(f"   Estimated to complete: {(datetime.now().replace(hour=datetime.now().hour+2)).strftime('%H:%M')}")

print("\n" + "="*80)
print("✅ TASK 1 COMPLETE")
print("="*80)
