#!/usr/bin/env python3
"""
B3.5: Semantic Hierarchy Construction with SHAP Scores
=======================================================

Builds a 6-level semantic hierarchy from B2 clusters for visualization.

INPUT:
  - B2_semantic_clustering.pkl (168 clusters, 3,872 nodes)
  - A6_hierarchical_graph.pkl (for causal_layer metadata)
  - indicator_labels_comprehensive.json (for human-readable labels)

OUTPUT:
  - B35_semantic_hierarchy.pkl (full tree structure)
  - B35_node_semantic_paths.json (fast lookup for visualization)
  - B35_hierarchy_summary.json (statistics)
  - B35_shap_scores.pkl (SHAP importance scores for all indicators)

HIERARCHY LEVELS:
  0. Super-domain (3 nodes): Social, Economic, Environmental
  1. Domain (9 nodes): Governance, Education, Health, etc.
  2. Subdomain (35-40 nodes): Executive, Judicial, Primary, etc.
  3. Coarse cluster (70-80 nodes): Governance_Executive, Education_Primary
  4. Fine cluster (168 nodes): Governance_Executive_0, Governance_Executive_1
  5. Indicator group (top K per cluster): Ranked by SHAP scores
  6. All indicators (3,872 nodes): Full detail

Author: Phase B3.5
Date: December 2025
"""

import pickle
import json
import sys
import numpy as np
from pathlib import Path
from datetime import datetime
from collections import defaultdict, Counter

# Project paths
project_root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(project_root))

output_dir = Path(__file__).parent.parent / "outputs"
output_dir.mkdir(exist_ok=True, parents=True)

print("=" * 80)
print("B3.5: SEMANTIC HIERARCHY CONSTRUCTION WITH SHAP SCORES")
print("=" * 80)

start_time = datetime.now()
print(f"Start time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")

# ============================================================================
# STEP 1: LOAD DATA
# ============================================================================

print("\n[STEP 1] Loading data...")

# B2 clusters
b2_path = project_root / "phaseB/B2_mechanism_identification/outputs/B2_semantic_clustering.pkl"
with open(b2_path, 'rb') as f:
    b2_data = pickle.load(f)

clusters = b2_data['fine_clusters']
node_assignments = b2_data['node_assignments']
coarse_clusters = b2_data.get('coarse_clusters', {})

print(f"   ✅ Loaded {len(clusters)} fine clusters")
print(f"   ✅ Loaded {len(node_assignments)} node assignments")

# A6 graph
a6_path = project_root / "phaseA/A6_hierarchical_layering/outputs/A6_hierarchical_graph.pkl"
with open(a6_path, 'rb') as f:
    a6_data = pickle.load(f)

G = a6_data['graph']
layers = a6_data['layers']
centrality = a6_data.get('centrality', {})

print(f"   ✅ Loaded graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

# Indicator labels
labels_path = project_root / "phaseB/B5_output_schema/outputs/indicator_labels_comprehensive.json"
with open(labels_path, 'r') as f:
    indicator_labels = json.load(f)

print(f"   ✅ Loaded labels for {len(indicator_labels)} indicators")

# ============================================================================
# STEP 2: CLUSTER NAME CORRECTIONS
# ============================================================================

print("\n[STEP 2] Applying cluster name corrections...")

# Corrections based on manual review of coherence-flagged clusters
CLUSTER_CORRECTIONS = {
    # Governance_Sovereignty contains v2dd* (direct democracy) variables
    'Governance_Sovereignty_0': {'rename': 'Governance_Direct_Democracy_0'},
    'Governance_Sovereignty_1': {'rename': 'Governance_Direct_Democracy_1'},
}

# Apply corrections
corrected_clusters = {}
corrected_assignments = {}

for cluster_name, cluster_data in clusters.items():
    new_name = cluster_name

    if cluster_name in CLUSTER_CORRECTIONS:
        correction = CLUSTER_CORRECTIONS[cluster_name]
        if 'rename' in correction:
            new_name = correction['rename']
            print(f"   Renamed: {cluster_name} → {new_name}")

    corrected_clusters[new_name] = cluster_data.copy()

# Update node assignments
for node_id, cluster_name in node_assignments.items():
    new_name = cluster_name
    if cluster_name in CLUSTER_CORRECTIONS:
        correction = CLUSTER_CORRECTIONS[cluster_name]
        if 'rename' in correction:
            new_name = correction['rename']
    corrected_assignments[node_id] = new_name

clusters = corrected_clusters
node_assignments = corrected_assignments

print(f"   ✅ Applied {len(CLUSTER_CORRECTIONS)} cluster corrections")

# ============================================================================
# STEP 3: LOAD REAL SHAP SCORES FROM B2.5
# ============================================================================

print("\n[STEP 3] Loading real SHAP scores from B2.5...")

# Load B2.5 computed SHAP scores (LightGBM TreeSHAP on B1-discovered outcomes)
b25_path = project_root / "phaseB/B25_shap_computation/outputs/B25_shap_scores.pkl"

if b25_path.exists():
    with open(b25_path, 'rb') as f:
        b25_shap_data = pickle.load(f)
    print(f"   ✅ Loaded B2.5 SHAP scores for {len(b25_shap_data)} indicators")
    shap_method = "LightGBM TreeSHAP (B2.5 - B1 discovered outcomes)"
else:
    print(f"   ⚠️ B2.5 SHAP scores not found, using composite fallback")
    b25_shap_data = {}
    shap_method = "composite (fallback)"

# Also load centrality for composite scoring
pagerank = centrality.get('pagerank', {})
betweenness = centrality.get('betweenness', {})

# Normalize helper
def normalize_dict(d):
    if not d:
        return {}
    values = list(d.values())
    min_v, max_v = min(values), max(values)
    if max_v == min_v:
        return {k: 0.5 for k in d}
    return {k: (v - min_v) / (max_v - min_v) for k, v in d.items()}

norm_pagerank = normalize_dict(pagerank)
norm_betweenness = normalize_dict(betweenness)

# Build shap_scores dict with real SHAP + composite components
shap_scores = {}
max_layer = max(layers.values()) if layers else 20

for node_id in G.nodes():
    # Get real SHAP score from B2.5 (if available)
    b25_data = b25_shap_data.get(node_id, {})
    real_shap = b25_data.get('shap_normalized', 0.0)
    shap_n_outcomes = b25_data.get('n_outcomes', 0)

    # Component scores for composite
    pr_score = norm_pagerank.get(node_id, 0.0)
    bw_score = norm_betweenness.get(node_id, 0.0)

    # Layer score: earlier layers (0) = more important
    layer = layers.get(node_id, max_layer)
    layer_score = 1.0 - (layer / max_layer)

    # Degree score
    degree = G.degree(node_id)
    max_degree = max(dict(G.degree()).values()) if G.degree() else 1
    degree_score = degree / max_degree

    # Composite score for structural importance
    composite_structural = (
        0.30 * bw_score +
        0.25 * layer_score +
        0.25 * pr_score +
        0.20 * degree_score
    )

    # Final score: Use real SHAP if available, weighted with structural
    if shap_n_outcomes > 0:
        # Real SHAP available: 50% SHAP + 30% betweenness + 15% layer + 5% degree
        composite = (
            0.50 * real_shap +
            0.30 * bw_score +
            0.15 * layer_score +
            0.05 * degree_score
        )
    else:
        # Fallback to structural composite
        composite = composite_structural

    shap_scores[node_id] = {
        'composite_score': composite,
        'shap_real': real_shap,
        'shap_n_outcomes': shap_n_outcomes,
        'betweenness': bw_score,
        'pagerank': pr_score,
        'layer_score': layer_score,
        'degree_score': degree_score,
        'raw_layer': layer
    }

# Statistics
scores = [s['composite_score'] for s in shap_scores.values()]
real_shap_count = sum(1 for s in shap_scores.values() if s['shap_n_outcomes'] > 0)
print(f"   SHAP scores computed for {len(shap_scores)} nodes")
print(f"   Real SHAP coverage: {real_shap_count}/{len(shap_scores)} ({real_shap_count/len(shap_scores)*100:.1f}%)")
print(f"   Score distribution: min={min(scores):.4f}, max={max(scores):.4f}, mean={np.mean(scores):.4f}")
print(f"   Method: {shap_method}")

# Top 10 most important indicators
top_10 = sorted(shap_scores.items(), key=lambda x: x[1]['composite_score'], reverse=True)[:10]
print(f"\n   Top 10 most important indicators:")
for node_id, score in top_10:
    label = indicator_labels.get(node_id, {}).get('label', node_id)[:50]
    real_tag = " [SHAP]" if score['shap_n_outcomes'] > 0 else ""
    print(f"      {score['composite_score']:.4f} | {node_id}: {label}{real_tag}")

# ============================================================================
# STEP 4: BUILD LEVEL 0 (SUPER-DOMAINS)
# ============================================================================

print("\n[STEP 4] Building Level 0: Super-domains...")

SUPER_DOMAIN_MAP = {
    'Social': ['Governance', 'Education', 'Health', 'Security', 'Development'],
    'Economic': ['Economic', 'Demographics', 'Research'],
    'Environmental': ['Environment']
}

level_0 = {}
for super_domain, child_domains in SUPER_DOMAIN_MAP.items():
    level_0[super_domain] = {
        'id': f"L0_{super_domain}",
        'label': super_domain,
        'children': child_domains,
        'level': 0,
        'type': 'super_domain'
    }

print(f"   ✅ Created {len(level_0)} super-domains: {list(level_0.keys())}")

# ============================================================================
# STEP 5: BUILD LEVEL 1 (DOMAINS)
# ============================================================================

print("\n[STEP 5] Building Level 1: Domains...")

# Extract unique domains from cluster names
domains = set()
for cluster_name in clusters.keys():
    domain = cluster_name.split('_')[0]
    domains.add(domain)

level_1 = {}
for domain in sorted(domains):
    # Find parent super-domain
    parent_super = 'Social'  # Default
    for super_domain, child_list in SUPER_DOMAIN_MAP.items():
        if domain in child_list:
            parent_super = super_domain
            break

    level_1[domain] = {
        'id': f"L1_{domain}",
        'label': domain,
        'parent': parent_super,
        'children': [],  # Will populate later
        'level': 1,
        'type': 'domain'
    }

print(f"   ✅ Created {len(level_1)} domains: {list(level_1.keys())}")

# ============================================================================
# STEP 6: BUILD LEVEL 2 (SUBDOMAINS)
# ============================================================================

print("\n[STEP 6] Building Level 2: Subdomains...")

# Extract subdomains from cluster names (first 2 parts)
subdomains = defaultdict(set)
for cluster_name in clusters.keys():
    parts = cluster_name.split('_')
    if len(parts) >= 2:
        domain = parts[0]
        subdomain = f"{parts[0]}_{parts[1]}"
        subdomains[domain].add(subdomain)

level_2 = {}
for domain, subdomain_set in subdomains.items():
    for subdomain in sorted(subdomain_set):
        subdomain_label = subdomain.split('_')[1] if '_' in subdomain else subdomain

        level_2[subdomain] = {
            'id': f"L2_{subdomain}",
            'label': subdomain_label,
            'full_name': subdomain,
            'parent': domain,
            'children': [],  # Will populate later
            'level': 2,
            'type': 'subdomain'
        }

print(f"   ✅ Created {len(level_2)} subdomains")

# ============================================================================
# STEP 7: BUILD LEVEL 3 (COARSE CLUSTERS)
# ============================================================================

print("\n[STEP 7] Building Level 3: Coarse clusters...")

# Coarse = cluster name without final numeric suffix
coarse_to_fine = defaultdict(list)
for cluster_name in clusters.keys():
    parts = cluster_name.split('_')

    # Remove last part if it's numeric
    if len(parts) >= 3 and parts[-1].isdigit():
        coarse_name = '_'.join(parts[:-1])
    else:
        coarse_name = cluster_name

    coarse_to_fine[coarse_name].append(cluster_name)

level_3 = {}
for coarse_name, fine_list in coarse_to_fine.items():
    parts = coarse_name.split('_')

    # Parent = subdomain (first 2 parts)
    parent = f"{parts[0]}_{parts[1]}" if len(parts) >= 2 else parts[0]

    # Count total indicators
    total_indicators = sum(len(clusters[fine]['indicators']) for fine in fine_list)

    level_3[coarse_name] = {
        'id': f"L3_{coarse_name}",
        'label': coarse_name.replace('_', ' → '),
        'parent': parent,
        'children': fine_list,
        'total_indicators': total_indicators,
        'level': 3,
        'type': 'coarse_cluster'
    }

print(f"   ✅ Created {len(level_3)} coarse clusters")

# ============================================================================
# STEP 8: BUILD LEVEL 4 (FINE CLUSTERS)
# ============================================================================

print("\n[STEP 8] Building Level 4: Fine clusters...")

level_4 = {}
for cluster_name, cluster_data in clusters.items():
    parts = cluster_name.split('_')

    # Parent = coarse cluster
    if len(parts) >= 3 and parts[-1].isdigit():
        parent = '_'.join(parts[:-1])
    else:
        parent = cluster_name

    # Get representative label
    rep_label = cluster_data.get('representative_label', cluster_name)

    # Compute cluster-level importance (mean SHAP score)
    cluster_indicators = cluster_data['indicators']
    cluster_shap_scores = [
        shap_scores.get(ind, {}).get('composite_score', 0.0)
        for ind in cluster_indicators
    ]
    mean_importance = np.mean(cluster_shap_scores) if cluster_shap_scores else 0.0

    level_4[cluster_name] = {
        'id': f"L4_{cluster_name}",
        'label': rep_label,
        'parent': parent,
        'indicators': cluster_indicators,
        'size': len(cluster_indicators),
        'mean_importance': mean_importance,
        'level': 4,
        'type': 'fine_cluster'
    }

print(f"   ✅ Created {len(level_4)} fine clusters")

# ============================================================================
# STEP 9: BUILD LEVEL 5 (INDICATOR GROUPS - TOP K BY SHAP)
# ============================================================================

print("\n[STEP 9] Building Level 5: Indicator groups (ranked by SHAP)...")

level_5 = {}
for cluster_name, cluster_data in level_4.items():
    indicators = cluster_data['indicators']

    # Sort by SHAP score
    scored_indicators = [
        (ind, shap_scores.get(ind, {}).get('composite_score', 0.0))
        for ind in indicators
    ]
    scored_indicators.sort(key=lambda x: x[1], reverse=True)

    # Top K (5-10 depending on cluster size)
    k = min(10, max(5, len(indicators) // 3))
    top_k = scored_indicators[:k]

    # Get labels for top indicators
    top_with_labels = []
    for ind, score in top_k:
        label = indicator_labels.get(ind, {}).get('label', ind)
        top_with_labels.append({
            'id': ind,
            'label': label,
            'shap_score': score
        })

    level_5[cluster_name] = {
        'id': f"L5_{cluster_name}",
        'label': f"Top {k} indicators",
        'parent': cluster_name,
        'top_indicators': top_with_labels,
        'hidden_count': len(indicators) - k,
        'level': 5,
        'type': 'indicator_group'
    }

print(f"   ✅ Created {len(level_5)} indicator groups")

# ============================================================================
# STEP 10: BUILD LEVEL 6 (ALL INDICATORS)
# ============================================================================

print("\n[STEP 10] Building Level 6: All indicators...")

level_6 = {}
for node_id, cluster_name in node_assignments.items():
    label = indicator_labels.get(node_id, {}).get('label', node_id)
    description = indicator_labels.get(node_id, {}).get('description', '')

    shap_data = shap_scores.get(node_id, {})

    level_6[node_id] = {
        'id': node_id,
        'label': label,
        'description': description[:200] if description else '',
        'parent': cluster_name,
        'causal_layer': layers.get(node_id, -1),
        'shap_score': shap_data.get('composite_score', 0.0),
        'pagerank': shap_data.get('pagerank', 0.0),
        'degree': G.degree(node_id) if node_id in G else 0,
        'level': 6,
        'type': 'indicator'
    }

print(f"   ✅ Created {len(level_6)} indicator entries")

# ============================================================================
# STEP 11: WIRE UP PARENT-CHILD RELATIONSHIPS
# ============================================================================

print("\n[STEP 11] Wiring parent-child relationships...")

# Level 1 children = Level 2 subdomains
for subdomain, data in level_2.items():
    parent = data['parent']
    if parent in level_1:
        level_1[parent]['children'].append(subdomain)

# Level 2 children = Level 3 coarse clusters
for coarse, data in level_3.items():
    parent = data['parent']
    if parent in level_2:
        level_2[parent]['children'].append(coarse)

print(f"   ✅ Parent-child relationships established")

# ============================================================================
# STEP 12: ASSEMBLE COMPLETE HIERARCHY
# ============================================================================

print("\n[STEP 12] Assembling complete hierarchy...")

hierarchy = {
    'metadata': {
        'version': '2.2-B35',
        'timestamp': datetime.now().isoformat(),
        'total_indicators': len(level_6),
        'total_fine_clusters': len(level_4),
        'total_coarse_clusters': len(level_3),
        'total_subdomains': len(level_2),
        'total_domains': len(level_1),
        'total_super_domains': len(level_0),
        'levels': 7,
        'shap_method': shap_method,
        'shap_real_coverage': f"{real_shap_count}/{len(shap_scores)} ({real_shap_count/len(shap_scores)*100:.1f}%)"
    },
    'levels': {
        0: level_0,
        1: level_1,
        2: level_2,
        3: level_3,
        4: level_4,
        5: level_5,
        6: level_6
    }
}

print(f"   ✅ Hierarchy assembled: {hierarchy['metadata']}")

# ============================================================================
# STEP 13: BUILD SEMANTIC PATHS (FAST LOOKUP)
# ============================================================================

print("\n[STEP 13] Building semantic paths for fast lookup...")

semantic_paths = {}
for node_id, cluster_name in node_assignments.items():
    # Traverse upward through hierarchy
    parts = cluster_name.split('_')

    # Fine cluster → Coarse cluster
    if len(parts) >= 3 and parts[-1].isdigit():
        coarse = '_'.join(parts[:-1])
    else:
        coarse = cluster_name

    # Coarse → Subdomain
    subdomain = f"{parts[0]}_{parts[1]}" if len(parts) >= 2 else parts[0]

    # Subdomain → Domain
    domain = parts[0]

    # Domain → Super-domain
    super_domain = 'Social'  # Default
    for sd, domains_list in SUPER_DOMAIN_MAP.items():
        if domain in domains_list:
            super_domain = sd
            break

    # Get indicator label
    label = indicator_labels.get(node_id, {}).get('label', node_id)

    semantic_paths[node_id] = {
        'indicator_id': node_id,
        'indicator_label': label[:100],
        'fine_cluster': cluster_name,
        'coarse_cluster': coarse,
        'subdomain': subdomain,
        'domain': domain,
        'super_domain': super_domain,
        'semantic_parent': cluster_name,
        'full_path': f"{super_domain} > {domain} > {subdomain.split('_')[1] if '_' in subdomain else subdomain} > {cluster_name}",
        'shap_score': shap_scores.get(node_id, {}).get('composite_score', 0.0),
        'causal_layer': layers.get(node_id, -1)
    }

print(f"   ✅ Built semantic paths for {len(semantic_paths)} nodes")

# ============================================================================
# STEP 14: EXPORT OUTPUTS
# ============================================================================

print("\n[STEP 14] Exporting outputs...")

# Output 1: Full hierarchy (pickle)
hierarchy_path = output_dir / "B35_semantic_hierarchy.pkl"
with open(hierarchy_path, 'wb') as f:
    pickle.dump(hierarchy, f)
print(f"   ✅ Saved: {hierarchy_path}")

# Output 2: Semantic paths (JSON for visualization)
paths_path = output_dir / "B35_node_semantic_paths.json"
with open(paths_path, 'w') as f:
    json.dump(semantic_paths, f, indent=2)
print(f"   ✅ Saved: {paths_path}")

# Output 3: SHAP scores (pickle)
shap_path = output_dir / "B35_shap_scores.pkl"
with open(shap_path, 'wb') as f:
    pickle.dump(shap_scores, f)
print(f"   ✅ Saved: {shap_path}")

# Output 4: Summary statistics (JSON)
summary = {
    'metadata': hierarchy['metadata'],
    'level_counts': {
        'L0_super_domains': len(level_0),
        'L1_domains': len(level_1),
        'L2_subdomains': len(level_2),
        'L3_coarse_clusters': len(level_3),
        'L4_fine_clusters': len(level_4),
        'L5_indicator_groups': len(level_5),
        'L6_indicators': len(level_6)
    },
    'domain_distribution': {
        domain: len([c for c in level_4 if c.startswith(domain)])
        for domain in level_1.keys()
    },
    'super_domain_distribution': {
        sd: sum(len([c for c in level_4 if c.startswith(d)]) for d in domains)
        for sd, domains in SUPER_DOMAIN_MAP.items()
    },
    'shap_statistics': {
        'min': float(min(scores)),
        'max': float(max(scores)),
        'mean': float(np.mean(scores)),
        'median': float(np.median(scores)),
        'std': float(np.std(scores))
    },
    'cluster_size_distribution': {
        'min': min(c['size'] for c in level_4.values()),
        'max': max(c['size'] for c in level_4.values()),
        'mean': float(np.mean([c['size'] for c in level_4.values()])),
        'median': float(np.median([c['size'] for c in level_4.values()]))
    }
}

summary_path = output_dir / "B35_hierarchy_summary.json"
with open(summary_path, 'w') as f:
    json.dump(summary, f, indent=2)
print(f"   ✅ Saved: {summary_path}")

# ============================================================================
# SUMMARY
# ============================================================================

elapsed = (datetime.now() - start_time).total_seconds()

print("\n" + "=" * 80)
print("B3.5 SEMANTIC HIERARCHY CONSTRUCTION COMPLETE")
print("=" * 80)

print(f"""
Summary:
   Total indicators: {len(level_6)}
   Fine clusters: {len(level_4)}
   Coarse clusters: {len(level_3)}
   Subdomains: {len(level_2)}
   Domains: {len(level_1)}
   Super-domains: {len(level_0)}

   SHAP scores computed for {len(shap_scores)} nodes
   Mean SHAP score: {np.mean(scores):.4f}

   Runtime: {elapsed:.1f} seconds

Output files:
   - {hierarchy_path}
   - {paths_path}
   - {shap_path}
   - {summary_path}

Hierarchy structure:
   Level 0: {len(level_0)} super-domains
   Level 1: {len(level_1)} domains
   Level 2: {len(level_2)} subdomains
   Level 3: {len(level_3)} coarse clusters
   Level 4: {len(level_4)} fine clusters
   Level 5: {len(level_5)} indicator groups (lazy-loaded)
   Level 6: {len(level_6)} indicators (lazy-loaded)

Ready for visualization export! ✅
""")
