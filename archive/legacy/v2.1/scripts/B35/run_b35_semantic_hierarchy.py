#!/usr/bin/env python3
"""
B3.5: Semantic Hierarchy Construction with Flexible 7 Layers (V2.1)
====================================================================

Builds a 7-level semantic hierarchy from B2 clusters for visualization.

V2.1 APPROACH (Corrected):
- Fixed Layers (0-3): Root, Super-domains, Domains, Subdomains
- Flexible Layers (4-6/7): Coarse clusters, Fine clusters, Indicators
- Optional Layer 7: Split Layer 6 if >500 nodes

HIERARCHY LEVELS:
  Layer 0: Root QoL Target (1 node)
  Layer 1: Super-domains (3 nodes) - Social, Economic, Governance
  Layer 2: Domains (6-10 nodes) - Health, Education, GDP, etc.
  Layer 3: Subdomains (35-50 nodes)
  Layer 4: Coarse Clusters (80-120 nodes)
  Layer 5: Fine Clusters (150-200 nodes from B2)
  Layer 6: Indicators (actual variables)
  Layer 7 (optional): Split Layer 6 if crowded

INPUT:
  - B2_semantic_clustering.pkl
  - A6_hierarchical_graph.pkl
  - B25_shap_scores.pkl (real SHAP scores)

OUTPUT:
  - B35_semantic_hierarchy.pkl
  - B35_node_semantic_paths.json
  - causal_graph_v2_FINAL.json (visualization-ready)

Author: Phase B3.5 V2.1
Date: December 2025
"""

import pickle
import json
import sys
import numpy as np
from pathlib import Path
from datetime import datetime
from collections import defaultdict, Counter

# V2.1 Configuration
sys.path.insert(0, str(Path(__file__).parent.parent))
from v21_config import A6_OUTPUT, B2_OUTPUT, B25_OUTPUT, B35_OUTPUT, B1_OUTPUT

output_dir = B35_OUTPUT
output_dir.mkdir(exist_ok=True, parents=True)

print("=" * 80)
print("B3.5: SEMANTIC HIERARCHY WITH FLEXIBLE 7 LAYERS (V2.1)")
print("=" * 80)

start_time = datetime.now()
print(f"Start time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")

# ============================================================================
# CONFIGURATION
# ============================================================================

HIERARCHY_CONFIG = {
    'max_layers': 7,
    'expand_if_crowded': True,
    'crowding_threshold': 500,  # Split Layer 6 if >500 nodes

    'fixed_layers': {
        0: 1,       # Root
        1: 3,       # Super-domains
        2: 10,      # Domains (6-10 flexible)
        3: 50,      # Subdomains (35-50 flexible)
    },

    'flexible_layers': {
        4: 100,     # Coarse clusters (target)
        5: 200,     # Fine clusters (from B2)
        6: None,    # All indicators (no target)
        7: None,    # Optional split
    }
}

# Super-domain mapping
SUPER_DOMAIN_MAP = {
    'Social': ['Governance', 'Education', 'Health', 'Security', 'Development'],
    'Economic': ['Economic', 'Demographics', 'Research'],
    'Environmental': ['Environment'],
}

# ============================================================================
# STEP 1: LOAD DATA
# ============================================================================

print("\n[STEP 1] Loading data...")

# B2 clusters
b2_path = B2_OUTPUT / "B2_semantic_clustering.pkl"
with open(b2_path, 'rb') as f:
    b2_data = pickle.load(f)

fine_clusters = b2_data.get('fine_clusters', {})
node_assignments = b2_data.get('node_assignments', b2_data.get('partition', {}))
coarse_clusters = b2_data.get('coarse_clusters', {})

print(f"   ✅ Loaded {len(fine_clusters)} fine clusters")
print(f"   ✅ Loaded {len(node_assignments)} node assignments")

# A6 graph
a6_path = A6_OUTPUT / "A6_hierarchical_graph.pkl"
with open(a6_path, 'rb') as f:
    a6_data = pickle.load(f)

G = a6_data['graph']
layers = a6_data['layers']
centrality = a6_data.get('centrality', {})

print(f"   ✅ Loaded graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

# B2.5 SHAP scores
shap_path = B35_OUTPUT / "B25_shap_scores.pkl"
if not shap_path.exists():
    shap_path = B25_OUTPUT / "B25_shap_scores.pkl"

if shap_path.exists():
    with open(shap_path, 'rb') as f:
        b25_shap_data = pickle.load(f)
    print(f"   ✅ Loaded B2.5 SHAP scores for {len(b25_shap_data)} indicators")
    shap_method = "LightGBM TreeSHAP"
else:
    print(f"   ⚠️ B2.5 SHAP scores not found, using composite fallback")
    b25_shap_data = {}
    shap_method = "composite (fallback)"

# Indicator labels (optional)
labels_path = B1_OUTPUT / "indicator_labels_comprehensive.json"
if labels_path.exists():
    with open(labels_path, 'r') as f:
        indicator_labels = json.load(f)
    print(f"   ✅ Loaded labels for {len(indicator_labels)} indicators")
else:
    indicator_labels = {}
    print(f"   ⚠️ No labels file, using indicator IDs")

# ============================================================================
# STEP 2: COMPUTE SHAP SCORES
# ============================================================================

print("\n[STEP 2] Computing node importance scores...")

pagerank = centrality.get('pagerank', {})
betweenness = centrality.get('betweenness', {})

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

shap_scores = {}
max_layer = max(layers.values()) if layers else 20

for node_id in G.nodes():
    b25_data = b25_shap_data.get(node_id, {})
    real_shap = b25_data.get('shap_normalized', 0.0)
    shap_n_outcomes = b25_data.get('n_outcomes', 0)

    pr_score = norm_pagerank.get(node_id, 0.0)
    bw_score = norm_betweenness.get(node_id, 0.0)

    layer = layers.get(node_id, max_layer)
    layer_score = 1.0 - (layer / max_layer) if max_layer > 0 else 0.5

    degree = G.degree(node_id)
    max_degree = max(dict(G.degree()).values()) if G.degree() else 1
    degree_score = degree / max_degree

    # Composite score
    if shap_n_outcomes > 0:
        composite = (
            0.50 * real_shap +
            0.25 * bw_score +
            0.15 * layer_score +
            0.10 * degree_score
        )
    else:
        composite = (
            0.30 * bw_score +
            0.25 * layer_score +
            0.25 * pr_score +
            0.20 * degree_score
        )

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

scores = [s['composite_score'] for s in shap_scores.values()]
real_shap_count = sum(1 for s in shap_scores.values() if s['shap_n_outcomes'] > 0)
print(f"   SHAP scores computed for {len(shap_scores)} nodes")
print(f"   Real SHAP coverage: {real_shap_count}/{len(shap_scores)} ({100*real_shap_count/len(shap_scores):.1f}%)")
print(f"   Method: {shap_method}")

# ============================================================================
# STEP 3: BUILD LAYER 0 (ROOT)
# ============================================================================

print("\n[STEP 3] Building Layer 0: Root...")

level_0 = {
    'Quality_of_Life_Index': {
        'id': 'L0_QoL',
        'label': 'Quality of Life Index',
        'children': ['Social', 'Economic', 'Environmental'],
        'level': 0,
        'type': 'root'
    }
}

print(f"   ✅ Created root node")

# ============================================================================
# STEP 4: BUILD LAYER 1 (SUPER-DOMAINS)
# ============================================================================

print("\n[STEP 4] Building Layer 1: Super-domains...")

level_1 = {}
for super_domain, child_domains in SUPER_DOMAIN_MAP.items():
    level_1[super_domain] = {
        'id': f"L1_{super_domain}",
        'label': super_domain,
        'parent': 'Quality_of_Life_Index',
        'children': child_domains,
        'level': 1,
        'type': 'super_domain'
    }

print(f"   ✅ Created {len(level_1)} super-domains: {list(level_1.keys())}")

# ============================================================================
# STEP 5: BUILD LAYER 2 (DOMAINS)
# ============================================================================

print("\n[STEP 5] Building Layer 2: Domains...")

# Extract unique domains from fine cluster names
domains = set()
for cluster_name in fine_clusters.keys():
    domain = cluster_name.split('_')[0]
    domains.add(domain)

level_2 = {}
for domain in sorted(domains):
    # Find parent super-domain
    parent_super = 'Social'  # Default
    for super_domain, child_list in SUPER_DOMAIN_MAP.items():
        if domain in child_list:
            parent_super = super_domain
            break

    level_2[domain] = {
        'id': f"L2_{domain}",
        'label': domain,
        'parent': parent_super,
        'children': [],
        'level': 2,
        'type': 'domain'
    }

print(f"   ✅ Created {len(level_2)} domains")

# ============================================================================
# STEP 6: BUILD LAYER 3 (SUBDOMAINS)
# ============================================================================

print("\n[STEP 6] Building Layer 3: Subdomains...")

subdomains = defaultdict(set)
for cluster_name in fine_clusters.keys():
    parts = cluster_name.split('_')
    if len(parts) >= 2:
        domain = parts[0]
        subdomain = f"{parts[0]}_{parts[1]}"
        subdomains[domain].add(subdomain)

level_3 = {}
for domain, subdomain_set in subdomains.items():
    for subdomain in sorted(subdomain_set):
        subdomain_label = subdomain.split('_')[1] if '_' in subdomain else subdomain

        level_3[subdomain] = {
            'id': f"L3_{subdomain}",
            'label': subdomain_label,
            'full_name': subdomain,
            'parent': domain,
            'children': [],
            'level': 3,
            'type': 'subdomain'
        }

print(f"   ✅ Created {len(level_3)} subdomains")

# ============================================================================
# STEP 7: BUILD LAYER 4 (COARSE CLUSTERS)
# ============================================================================

print("\n[STEP 7] Building Layer 4: Coarse clusters...")

# Aggregate fine clusters into coarse (remove final numeric suffix)
coarse_to_fine = defaultdict(list)
for cluster_name in fine_clusters.keys():
    parts = cluster_name.split('_')
    if len(parts) >= 3 and parts[-1].isdigit():
        coarse_name = '_'.join(parts[:-1])
    else:
        coarse_name = cluster_name
    coarse_to_fine[coarse_name].append(cluster_name)

level_4 = {}
for coarse_name, fine_list in coarse_to_fine.items():
    parts = coarse_name.split('_')
    parent = f"{parts[0]}_{parts[1]}" if len(parts) >= 2 else parts[0]

    # Count total indicators
    total_indicators = sum(len(fine_clusters[fine]['indicators']) for fine in fine_list)

    level_4[coarse_name] = {
        'id': f"L4_{coarse_name}",
        'label': coarse_name.replace('_', ' → '),
        'parent': parent,
        'children': fine_list,
        'total_indicators': total_indicators,
        'level': 4,
        'type': 'coarse_cluster'
    }

print(f"   ✅ Created {len(level_4)} coarse clusters")

# ============================================================================
# STEP 8: BUILD LAYER 5 (FINE CLUSTERS)
# ============================================================================

print("\n[STEP 8] Building Layer 5: Fine clusters...")

level_5 = {}
for cluster_name, cluster_data in fine_clusters.items():
    parts = cluster_name.split('_')

    # Parent = coarse cluster
    if len(parts) >= 3 and parts[-1].isdigit():
        parent = '_'.join(parts[:-1])
    else:
        parent = cluster_name

    # Get representative label
    rep_label = cluster_data.get('representative_label', cluster_name)
    cluster_indicators = cluster_data.get('indicators', [])

    # Compute cluster-level importance
    cluster_shap_scores = [
        shap_scores.get(ind, {}).get('composite_score', 0.0)
        for ind in cluster_indicators
    ]
    mean_importance = np.mean(cluster_shap_scores) if cluster_shap_scores else 0.0

    level_5[cluster_name] = {
        'id': f"L5_{cluster_name}",
        'label': rep_label,
        'parent': parent,
        'indicators': cluster_indicators,
        'size': len(cluster_indicators),
        'mean_importance': mean_importance,
        'level': 5,
        'type': 'fine_cluster'
    }

print(f"   ✅ Created {len(level_5)} fine clusters")

# ============================================================================
# STEP 9: BUILD LAYER 6 (INDICATORS)
# ============================================================================

print("\n[STEP 9] Building Layer 6: All indicators...")

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
# STEP 10: OPTIONAL LAYER 7 SPLIT (IF CROWDED)
# ============================================================================

print("\n[STEP 10] Checking if Layer 7 split needed...")

level_7 = {}
CROWDING_THRESHOLD = HIERARCHY_CONFIG['crowding_threshold']

if HIERARCHY_CONFIG['expand_if_crowded'] and len(level_6) > CROWDING_THRESHOLD:
    print(f"   ⚠️ Layer 6 has {len(level_6)} nodes (> {CROWDING_THRESHOLD}) - splitting to Layer 7")

    # Sort by SHAP score
    sorted_indicators = sorted(
        level_6.items(),
        key=lambda x: x[1]['shap_score'],
        reverse=True
    )

    # Top 50% → Layer 6, Bottom 50% → Layer 7
    split_point = len(sorted_indicators) // 2

    high_importance = dict(sorted_indicators[:split_point])
    low_importance = dict(sorted_indicators[split_point:])

    # Update level_6 with high importance only
    level_6 = high_importance

    # Create level_7 with low importance
    for node_id, data in low_importance.items():
        level_7[node_id] = {**data, 'level': 7, 'type': 'indicator_secondary'}

    print(f"   ✅ Split: Layer 6 = {len(level_6)} (high SHAP), Layer 7 = {len(level_7)} (low SHAP)")
else:
    print(f"   ✅ No split needed ({len(level_6)} nodes ≤ {CROWDING_THRESHOLD})")

# ============================================================================
# STEP 11: WIRE UP PARENT-CHILD RELATIONSHIPS
# ============================================================================

print("\n[STEP 11] Wiring parent-child relationships...")

# Level 1 children = Level 2 domains
for domain, data in level_2.items():
    parent = data['parent']
    if parent in level_1:
        if domain not in level_1[parent]['children']:
            level_1[parent]['children'].append(domain)

# Level 2 children = Level 3 subdomains
for subdomain, data in level_3.items():
    parent = data['parent']
    if parent in level_2:
        level_2[parent]['children'].append(subdomain)

# Level 3 children = Level 4 coarse clusters
for coarse, data in level_4.items():
    parent = data['parent']
    if parent in level_3:
        level_3[parent]['children'].append(coarse)

print(f"   ✅ Parent-child relationships established")

# ============================================================================
# STEP 12: ASSEMBLE COMPLETE HIERARCHY
# ============================================================================

print("\n[STEP 12] Assembling complete hierarchy...")

n_layers = 7 if level_7 else 6

hierarchy = {
    'metadata': {
        'version': '2.1-B35',
        'timestamp': datetime.now().isoformat(),
        'total_indicators': len(level_6) + len(level_7),
        'total_fine_clusters': len(level_5),
        'total_coarse_clusters': len(level_4),
        'total_subdomains': len(level_3),
        'total_domains': len(level_2),
        'total_super_domains': len(level_1),
        'layers': n_layers + 1,  # +1 for Layer 0
        'layer_split': len(level_7) > 0,
        'shap_method': shap_method,
        'shap_real_coverage': f"{real_shap_count}/{len(shap_scores)} ({100*real_shap_count/len(shap_scores):.1f}%)"
    },
    'levels': {
        0: level_0,
        1: level_1,
        2: level_2,
        3: level_3,
        4: level_4,
        5: level_5,
        6: level_6,
    }
}

if level_7:
    hierarchy['levels'][7] = level_7

print(f"   ✅ Hierarchy assembled with {n_layers + 1} levels")

# ============================================================================
# STEP 13: BUILD SEMANTIC PATHS
# ============================================================================

print("\n[STEP 13] Building semantic paths...")

def get_super_domain(domain):
    for sd, domains in SUPER_DOMAIN_MAP.items():
        if domain in domains:
            return sd
    return 'Social'

semantic_paths = {}
all_indicators = {**level_6, **level_7} if level_7 else level_6

for node_id, node_data in all_indicators.items():
    cluster_name = node_data.get('parent', 'Unclassified_0')
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
    super_domain = get_super_domain(domain)

    label = indicator_labels.get(node_id, {}).get('label', node_id)

    semantic_paths[node_id] = {
        'indicator_id': node_id,
        'indicator_label': label[:100] if label else node_id,
        'fine_cluster': cluster_name,
        'coarse_cluster': coarse,
        'subdomain': subdomain,
        'domain': domain,
        'super_domain': super_domain,
        'semantic_parent': cluster_name,
        'full_path': f"{super_domain} > {domain} > {subdomain.split('_')[1] if '_' in subdomain else subdomain} > {cluster_name}",
        'shap_score': shap_scores.get(node_id, {}).get('composite_score', 0.0),
        'causal_layer': layers.get(node_id, -1),
        'hierarchy_level': node_data.get('level', 6)
    }

print(f"   ✅ Built semantic paths for {len(semantic_paths)} nodes")

# ============================================================================
# STEP 14: EXPORT VISUALIZATION-READY JSON (V2.0 COMPATIBLE FORMAT)
# ============================================================================

print("\n[STEP 14] Exporting visualization-ready JSON (V2.0 compatible)...")

# Identify drivers (layer <= 5) and outcomes (high SHAP indicators)
all_indicators_combined = {**level_6, **level_7} if level_7 else level_6
driver_threshold_layer = 5
outcome_shap_threshold = 0.3

n_drivers = sum(1 for n in all_indicators_combined.values() if n.get('causal_layer', 99) <= driver_threshold_layer)
n_outcomes = sum(1 for n, data in all_indicators_combined.items()
                 if shap_scores.get(n, {}).get('shap_real', 0) > outcome_shap_threshold)
n_mechanisms = len(all_indicators_combined) - n_drivers - n_outcomes

# Count edges with moderators
edges_with_moderators = sum(1 for u, v, d in G.edges(data=True) if d.get('moderators'))
total_moderator_effects = sum(len(d.get('moderators', [])) for u, v, d in G.edges(data=True))

# Build nodes list (V2.0 compatible format)
viz_nodes = []
for node_id, path_data in semantic_paths.items():
    node_shap_data = shap_scores.get(node_id, {})
    causal_layer = path_data['causal_layer']
    shap_real = node_shap_data.get('shap_real', 0.0)

    # Determine node type
    is_driver = causal_layer <= driver_threshold_layer
    is_outcome = shap_real > outcome_shap_threshold

    viz_nodes.append({
        'id': node_id,
        'label': path_data['indicator_label'],
        'description': indicator_labels.get(node_id, {}).get('description', '')[:200],
        'semantic_path': {
            'super_domain': path_data['super_domain'],
            'domain': path_data['domain'],
            'subdomain': path_data['subdomain'],
            'fine_cluster': path_data['fine_cluster'],
            'full_path': path_data['full_path']
        },
        'causal_layer': causal_layer,
        'is_driver': is_driver,
        'is_outcome': is_outcome,
        'scores': {
            'shap': round(shap_real, 6),
            'betweenness': round(node_shap_data.get('betweenness', 0), 6),
            'pagerank': round(node_shap_data.get('pagerank', 0), 6),
            'composite': round(node_shap_data.get('composite_score', 0), 4),
            'degree': G.degree(node_id) if node_id in G else 0
        }
    })

# Build edges list (V2.0 compatible format)
viz_edges = []
for u, v, data in G.edges(data=True):
    if u in semantic_paths and v in semantic_paths:
        moderators = data.get('moderators', [])
        weight_val = data.get('weight') or data.get('beta') or 1.0
        beta_val = data.get('beta') or data.get('weight') or 0.0
        viz_edges.append({
            'source': u,
            'target': v,
            'weight': round(abs(float(weight_val)), 6),
            'beta': round(float(beta_val), 6),
            'source_layer': layers.get(u, -1),
            'target_layer': layers.get(v, -1),
            'moderators': moderators if isinstance(moderators, list) else []
        })

# Compute SHAP metrics
shap_computed = sum(1 for s in shap_scores.values() if s.get('shap_real', 0) > 0 or s.get('shap_n_outcomes', 0) > 0)
shap_nonzero = sum(1 for s in shap_scores.values() if s.get('shap_real', 0) > 0)

# Domain distribution for metadata
domain_dist = defaultdict(int)
for path in semantic_paths.values():
    domain_dist[path['domain']] += 1

# Get max causal layer
max_causal_layer = max(layers.values()) if layers else 20

# Build layer compression presets (V2.0 feature)
layer_compression_presets = {
    'full': {
        'name': 'Full Network',
        'description': 'All indicators visible',
        'visible_layers': list(range(max_causal_layer + 1)),
        'node_count': len(viz_nodes)
    },
    'simplified': {
        'name': 'Simplified View',
        'description': 'Key drivers and outcomes only',
        'visible_layers': list(range(min(6, max_causal_layer + 1))) + [max_causal_layer],
        'node_count': n_drivers + n_outcomes
    },
    'outcomes_only': {
        'name': 'Outcomes Focus',
        'description': 'High-importance outcome indicators',
        'visible_layers': [max_causal_layer - 2, max_causal_layer - 1, max_causal_layer],
        'node_count': n_outcomes
    }
}

# Build top lists (V2.0 feature)
sorted_by_shap = sorted(shap_scores.items(), key=lambda x: x[1].get('shap_real', 0), reverse=True)
sorted_by_betweenness = sorted(shap_scores.items(), key=lambda x: x[1].get('betweenness', 0), reverse=True)
sorted_by_degree = sorted([(n, {'degree': G.degree(n)}) for n in G.nodes()], key=lambda x: x[1]['degree'], reverse=True)

top_lists = {
    'by_shap': [{'id': n, 'score': round(d.get('shap_real', 0), 4)} for n, d in sorted_by_shap[:20]],
    'by_betweenness': [{'id': n, 'score': round(d.get('betweenness', 0), 4)} for n, d in sorted_by_betweenness[:20]],
    'by_degree': [{'id': n, 'degree': d['degree']} for n, d in sorted_by_degree[:20]]
}

# Build hierarchy summary (V2.0 feature)
hierarchy_summary = {
    'levels': n_layers + 1,
    'structure': {
        0: {'name': 'Root', 'count': len(level_0)},
        1: {'name': 'Super-domains', 'count': len(level_1), 'items': list(level_1.keys())},
        2: {'name': 'Domains', 'count': len(level_2), 'items': list(level_2.keys())},
        3: {'name': 'Subdomains', 'count': len(level_3)},
        4: {'name': 'Coarse Clusters', 'count': len(level_4)},
        5: {'name': 'Fine Clusters', 'count': len(level_5)},
        6: {'name': 'Indicators', 'count': len(level_6)},
    }
}
if level_7:
    hierarchy_summary['structure'][7] = {'name': 'Indicators (Secondary)', 'count': len(level_7)}

# Final visualization JSON (V2.0 COMPATIBLE)
viz_output = {
    'metadata': {
        'version': '2.1-B35-FINAL',
        'timestamp': datetime.now().isoformat(),
        'node_count': len(viz_nodes),
        'edge_count': len(viz_edges),
        'layers': max_causal_layer + 1,
        'hierarchy_levels': n_layers + 1,
        'statistics': {
            'n_drivers': n_drivers,
            'n_outcomes': n_outcomes,
            'n_mechanisms': n_mechanisms,
            'n_edges_with_moderators': edges_with_moderators,
            'total_moderator_effects': total_moderator_effects
        },
        'shap_metrics': {
            'computed_coverage': round(shap_computed / len(shap_scores), 3) if shap_scores else 0,
            'nonzero_rate': round(shap_nonzero / len(shap_scores), 3) if shap_scores else 0,
            'nodes_with_shap': shap_nonzero,
            'interpretation': f"{shap_nonzero} of {len(shap_scores)} indicators ({100*shap_nonzero/len(shap_scores):.1f}%) have non-zero outcome-predictive importance"
        },
        'shap_coverage_nonzero': round(shap_nonzero / len(shap_scores), 3) if shap_scores else 0,
        'shap_coverage_computed': round(shap_computed / len(shap_scores), 3) if shap_scores else 0,
        'domain_distribution': dict(domain_dist)
    },
    'nodes': viz_nodes,
    'edges': viz_edges,
    'layer_compression_presets': layer_compression_presets,
    'top_lists': top_lists,
    'hierarchy': hierarchy_summary
}

viz_json_path = output_dir / "causal_graph_v2_FINAL.json"
with open(viz_json_path, 'w') as f:
    json.dump(viz_output, f)
print(f"   ✅ Saved: {viz_json_path}")

# ============================================================================
# STEP 15: SAVE ALL OUTPUTS
# ============================================================================

print("\n[STEP 15] Saving all outputs...")

# Full hierarchy (pickle)
hierarchy_path = output_dir / "B35_semantic_hierarchy.pkl"
with open(hierarchy_path, 'wb') as f:
    pickle.dump(hierarchy, f)
print(f"   ✅ Saved: {hierarchy_path}")

# Semantic paths (JSON)
paths_path = output_dir / "B35_node_semantic_paths.json"
with open(paths_path, 'w') as f:
    json.dump(semantic_paths, f, indent=2)
print(f"   ✅ Saved: {paths_path}")

# SHAP scores (pickle)
shap_output_path = output_dir / "B35_shap_scores.pkl"
with open(shap_output_path, 'wb') as f:
    pickle.dump(shap_scores, f)
print(f"   ✅ Saved: {shap_output_path}")

# Summary statistics (JSON)
summary = {
    'metadata': hierarchy['metadata'],
    'level_counts': {
        'L0_root': len(level_0),
        'L1_super_domains': len(level_1),
        'L2_domains': len(level_2),
        'L3_subdomains': len(level_3),
        'L4_coarse_clusters': len(level_4),
        'L5_fine_clusters': len(level_5),
        'L6_indicators': len(level_6),
        'L7_indicators_secondary': len(level_7) if level_7 else 0
    },
    'domain_distribution': {
        domain: len([c for c in level_5 if c.startswith(domain)])
        for domain in level_2.keys()
    },
    'shap_statistics': {
        'min': float(min(scores)),
        'max': float(max(scores)),
        'mean': float(np.mean(scores)),
        'median': float(np.median(scores)),
        'std': float(np.std(scores))
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
print("B3.5 SEMANTIC HIERARCHY COMPLETE")
print("=" * 80)

print(f"""
Summary:
   Total indicators: {len(level_6) + len(level_7)}
   Hierarchy levels: {n_layers + 1}
   Layer 7 split: {'Yes' if level_7 else 'No'}

   Layer distribution:
      L0 Root: {len(level_0)}
      L1 Super-domains: {len(level_1)}
      L2 Domains: {len(level_2)}
      L3 Subdomains: {len(level_3)}
      L4 Coarse Clusters: {len(level_4)}
      L5 Fine Clusters: {len(level_5)}
      L6 Indicators: {len(level_6)}{f' (high SHAP)' if level_7 else ''}
      L7 Indicators: {len(level_7)} (low SHAP) {'⚠️ SPLIT APPLIED' if level_7 else ''}

   SHAP coverage: {real_shap_count}/{len(shap_scores)} ({100*real_shap_count/len(shap_scores):.1f}%)
   Mean SHAP: {np.mean(scores):.4f}

   Runtime: {elapsed:.1f} seconds

Output files:
   - {hierarchy_path}
   - {paths_path}
   - {shap_output_path}
   - {summary_path}
   - {viz_json_path} (visualization-ready)

✅ PHASE B COMPLETE - Ready for visualization!
""")
