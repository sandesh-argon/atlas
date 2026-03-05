#!/usr/bin/env python3
"""
B3.5 FINAL EXPORT: Visualization-Ready JSON
=============================================

Creates the final export with all 3 critical additions:
1. Edge moderator metadata from A5 interactions
2. Layer compression presets
3. Top K lists (multiple criteria)

INPUT:
  - B35_semantic_hierarchy.pkl
  - B35_shap_scores.pkl
  - A5_interaction_results_FILTERED_STRICT.pkl
  - A6_hierarchical_graph.pkl
  - B25_shap_scores.pkl

OUTPUT:
  - causal_graph_v2_FINAL.json (main visualization file)
  - B35_hierarchy_summary_FINAL.json (updated summary)

Author: Phase B3.5
Date: December 2025
"""

import pickle
import json
import numpy as np
from pathlib import Path
from datetime import datetime
from collections import defaultdict

project_root = Path(__file__).resolve().parents[3]
output_dir = Path(__file__).parent.parent / "outputs"

print("=" * 80)
print("B3.5 FINAL EXPORT: VISUALIZATION-READY JSON")
print("=" * 80)
print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# ============================================================================
# STEP 1: LOAD ALL DATA
# ============================================================================

print("\n[STEP 1] Loading all data sources...")

# B3.5 hierarchy
with open(output_dir / "B35_semantic_hierarchy.pkl", 'rb') as f:
    hierarchy = pickle.load(f)

# B3.5 SHAP scores (composite)
with open(output_dir / "B35_shap_scores.pkl", 'rb') as f:
    composite_scores = pickle.load(f)

# B2.5 raw SHAP scores
b25_path = project_root / "phaseB/B25_shap_computation/outputs/B25_shap_scores.pkl"
with open(b25_path, 'rb') as f:
    raw_shap = pickle.load(f)

# A5 interactions (moderators)
a5_path = project_root / "phaseA/A5_interaction_discovery/outputs/A5_interaction_results_FILTERED_STRICT.pkl"
with open(a5_path, 'rb') as f:
    a5_data = pickle.load(f)
interactions = a5_data['validated_interactions']

# A6 graph
a6_path = project_root / "phaseA/A6_hierarchical_layering/outputs/A6_hierarchical_graph.pkl"
with open(a6_path, 'rb') as f:
    a6_data = pickle.load(f)
G = a6_data['graph']
layers = a6_data['layers']
centrality = a6_data['centrality']

# Indicator labels
labels_path = project_root / "phaseB/B5_output_schema/outputs/indicator_labels_comprehensive.json"
with open(labels_path, 'r') as f:
    indicator_labels = json.load(f)

print(f"   ✅ Loaded hierarchy: {hierarchy['metadata']['total_indicators']} indicators")
print(f"   ✅ Loaded {len(interactions)} interactions (moderators)")
print(f"   ✅ Loaded graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

# ============================================================================
# STEP 2: BUILD EDGE MODERATOR METADATA
# ============================================================================

print("\n[STEP 2] Building edge moderator metadata...")

# Group interactions by (mechanism_1, outcome) pair to create edge moderators
# In A5, interaction is: outcome ~ mechanism_1 * mechanism_2
# So mechanism_2 moderates the mechanism_1 → outcome relationship

edge_moderators = defaultdict(list)

for inter in interactions:
    source = inter['mechanism_1']
    target = inter['outcome']
    moderator = inter['mechanism_2']

    edge_key = (source, target)

    # Get moderator label
    mod_label = indicator_labels.get(moderator, {}).get('label', moderator)

    edge_moderators[edge_key].append({
        'variable': moderator,
        'label': mod_label[:80] if mod_label else moderator,
        'interaction_beta': round(inter['beta_interaction'], 4),
        't_statistic': round(inter['t_statistic'], 3),
        'p_value': inter['p_value'],
        'significant': inter['significant_fdr']
    })

print(f"   ✅ Built moderators for {len(edge_moderators)} unique edges")

# Count edges with moderators in final graph
edges_with_mods = 0
for u, v in G.edges():
    if (u, v) in edge_moderators:
        edges_with_mods += 1

print(f"   ✅ {edges_with_mods}/{G.number_of_edges()} edges have moderators ({100*edges_with_mods/G.number_of_edges():.1f}%)")

# ============================================================================
# STEP 3: BUILD EDGES LIST WITH MODERATORS
# ============================================================================

print("\n[STEP 3] Building edges list with moderators...")

edges_list = []
for u, v, data in G.edges(data=True):
    # Handle None values
    weight = data.get('weight') or data.get('beta') or 0
    beta = data.get('beta') or 0

    edge = {
        'source': u,
        'target': v,
        'weight': round(float(weight), 4),
        'beta': round(float(beta), 4),
        'source_layer': layers.get(u, -1),
        'target_layer': layers.get(v, -1),
        'moderators': edge_moderators.get((u, v), [])
    }
    edges_list.append(edge)

print(f"   ✅ Built {len(edges_list)} edges")

# Sample edge with moderator
sample_with_mod = next((e for e in edges_list if len(e['moderators']) > 0), None)
if sample_with_mod:
    print(f"   Sample edge with moderator:")
    print(f"      {sample_with_mod['source']} → {sample_with_mod['target']}")
    print(f"      Moderators: {len(sample_with_mod['moderators'])}")
    print(f"      First moderator: {sample_with_mod['moderators'][0]['variable']}")

# ============================================================================
# STEP 4: BUILD LAYER COMPRESSION PRESETS
# ============================================================================

print("\n[STEP 4] Building layer compression presets...")

max_layer = max(layers.values()) if layers else 20

# Determine layer distribution for smart presets
layer_counts = defaultdict(int)
for node_id, layer in layers.items():
    layer_counts[layer] += 1

# Create compression presets
layer_compression_presets = {
    'minimal_2': {
        'bands': [
            list(range(0, 15)),  # Mechanisms (layers 0-14)
            list(range(15, max_layer + 1))  # Outcomes (layers 15+)
        ],
        'labels': ['Mechanisms', 'Outcomes'],
        'description': 'Binary view: everything is either a mechanism or an outcome'
    },
    'standard_5': {
        'bands': [
            [0],  # Drivers (layer 0)
            list(range(1, 6)),  # Early mechanisms (1-5)
            list(range(6, 15)),  # Middle mechanisms (6-14)
            list(range(15, 19)),  # Late mechanisms (15-18)
            list(range(19, max_layer + 1))  # Outcomes (19+)
        ],
        'labels': ['Drivers', 'Early Mechanisms', 'Middle Mechanisms', 'Late Mechanisms', 'Outcomes'],
        'description': 'Balanced 5-band view for general exploration'
    },
    'detailed_7': {
        'bands': [
            [0],  # Root drivers
            list(range(1, 4)),  # Early
            list(range(4, 8)),  # Early-mid
            list(range(8, 12)),  # Mid
            list(range(12, 16)),  # Late-mid
            list(range(16, 19)),  # Late
            list(range(19, max_layer + 1))  # Outcomes
        ],
        'labels': ['Root Drivers', 'Early', 'Early-Mid', 'Middle', 'Late-Mid', 'Late', 'Outcomes'],
        'description': 'Detailed 7-band view for analysis'
    },
    'full': {
        'bands': [[i] for i in range(max_layer + 1)],
        'labels': [f'Layer {i}' for i in range(max_layer + 1)],
        'description': 'Full layer resolution (all 21 layers)'
    }
}

# Add node counts per band
for preset_name, preset in layer_compression_presets.items():
    band_counts = []
    for band in preset['bands']:
        count = sum(layer_counts[layer] for layer in band)
        band_counts.append(count)
    preset['band_counts'] = band_counts

print(f"   ✅ Created {len(layer_compression_presets)} compression presets")
for name, preset in layer_compression_presets.items():
    print(f"      {name}: {len(preset['bands'])} bands - {preset['band_counts']}")

# ============================================================================
# STEP 5: BUILD TOP K LISTS
# ============================================================================

print("\n[STEP 5] Building Top K lists...")

# Get betweenness scores
betweenness = centrality.get('betweenness', {})
pagerank = centrality.get('pagerank', {})

# Sort and create lists
def get_label(node_id):
    return indicator_labels.get(node_id, {}).get('label', node_id)[:80]

# Top 20 by SHAP (raw)
shap_sorted = sorted(
    [(k, v.get('shap_normalized', 0)) for k, v in raw_shap.items()],
    key=lambda x: x[1],
    reverse=True
)[:20]

top_by_shap = [
    {'id': node_id, 'score': round(score, 4), 'label': get_label(node_id), 'layer': layers.get(node_id, -1)}
    for node_id, score in shap_sorted
]

# Top 20 by betweenness
between_sorted = sorted(betweenness.items(), key=lambda x: x[1], reverse=True)[:20]
top_by_betweenness = [
    {'id': node_id, 'score': round(score, 6), 'label': get_label(node_id), 'layer': layers.get(node_id, -1)}
    for node_id, score in between_sorted
]

# Top 20 by composite
composite_sorted = sorted(
    [(k, v.get('composite_score', 0)) for k, v in composite_scores.items()],
    key=lambda x: x[1],
    reverse=True
)[:20]

top_by_composite = [
    {'id': node_id, 'score': round(score, 4), 'label': get_label(node_id), 'layer': layers.get(node_id, -1)}
    for node_id, score in composite_sorted
]

# Top by layer (drivers and outcomes)
layer_0_nodes = [(n, composite_scores.get(n, {}).get('composite_score', 0))
                 for n, l in layers.items() if l == 0]
layer_0_sorted = sorted(layer_0_nodes, key=lambda x: x[1], reverse=True)[:20]
top_drivers = [
    {'id': node_id, 'score': round(score, 4), 'label': get_label(node_id)}
    for node_id, score in layer_0_sorted
]

# Outcomes (layer 19+)
outcome_layers = [n for n, l in layers.items() if l >= 19]
outcome_nodes = [(n, composite_scores.get(n, {}).get('composite_score', 0))
                 for n in outcome_layers]
outcome_sorted = sorted(outcome_nodes, key=lambda x: x[1], reverse=True)[:20]
top_outcomes = [
    {'id': node_id, 'score': round(score, 4), 'label': get_label(node_id), 'layer': layers.get(node_id, -1)}
    for node_id, score in outcome_sorted
]

# Top by degree (most connected)
degree_sorted = sorted(dict(G.degree()).items(), key=lambda x: x[1], reverse=True)[:20]
top_by_degree = [
    {'id': node_id, 'degree': degree, 'label': get_label(node_id), 'layer': layers.get(node_id, -1)}
    for node_id, degree in degree_sorted
]

top_lists = {
    'by_shap': top_by_shap,
    'by_betweenness': top_by_betweenness,
    'by_composite': top_by_composite,
    'by_degree': top_by_degree,
    'drivers': top_drivers,
    'outcomes': top_outcomes
}

print(f"   ✅ Created {len(top_lists)} top-K lists")
for name, lst in top_lists.items():
    print(f"      {name}: {len(lst)} items")

# ============================================================================
# STEP 6: BUILD NODES LIST WITH FULL METADATA
# ============================================================================

print("\n[STEP 6] Building nodes list with full metadata...")

# Get semantic paths
paths_path = output_dir / "B35_node_semantic_paths.json"
with open(paths_path, 'r') as f:
    semantic_paths = json.load(f)

nodes_list = []
for node_id in G.nodes():
    path_data = semantic_paths.get(node_id, {})
    score_data = composite_scores.get(node_id, {})
    shap_data = raw_shap.get(node_id, {})

    node = {
        'id': node_id,
        'label': get_label(node_id),
        'description': indicator_labels.get(node_id, {}).get('description', '')[:200],

        # Semantic hierarchy path
        'semantic_path': {
            'super_domain': path_data.get('super_domain', 'Unknown'),
            'domain': path_data.get('domain', 'Unknown'),
            'subdomain': path_data.get('subdomain', 'Unknown'),
            'fine_cluster': path_data.get('fine_cluster', 'Unknown'),
            'full_path': path_data.get('full_path', '')
        },

        # Causal metadata
        'causal_layer': layers.get(node_id, -1),
        'is_driver': layers.get(node_id, -1) == 0,
        'is_outcome': layers.get(node_id, -1) >= 19,

        # Scores
        'scores': {
            'shap': round(shap_data.get('shap_normalized', 0), 4),
            'betweenness': round(betweenness.get(node_id, 0), 6),
            'pagerank': round(pagerank.get(node_id, 0), 6),
            'composite': round(score_data.get('composite_score', 0), 4),
            'degree': G.degree(node_id)
        }
    }
    nodes_list.append(node)

print(f"   ✅ Built {len(nodes_list)} node entries")

# ============================================================================
# STEP 7: ASSEMBLE FINAL OUTPUT
# ============================================================================

print("\n[STEP 7] Assembling final output...")

# Count statistics
n_drivers = sum(1 for n in nodes_list if n['is_driver'])
n_outcomes = sum(1 for n in nodes_list if n['is_outcome'])
n_edges_with_mods = sum(1 for e in edges_list if len(e['moderators']) > 0)
total_moderators = sum(len(e['moderators']) for e in edges_list)

final_output = {
    'metadata': {
        'version': '2.2-B35-FINAL',
        'timestamp': datetime.now().isoformat(),
        'node_count': len(nodes_list),
        'edge_count': len(edges_list),
        'layers': max_layer + 1,
        'hierarchy_levels': 7,
        'shap_coverage': round(sum(1 for n in nodes_list if n['scores']['shap'] > 0) / len(nodes_list), 3),
        'statistics': {
            'n_drivers': n_drivers,
            'n_outcomes': n_outcomes,
            'n_mechanisms': len(nodes_list) - n_drivers - n_outcomes,
            'n_edges_with_moderators': n_edges_with_mods,
            'total_moderator_effects': total_moderators
        }
    },

    # Core graph data
    'nodes': nodes_list,
    'edges': edges_list,

    # Visualization aids
    'layer_compression_presets': layer_compression_presets,
    'top_lists': top_lists,

    # Hierarchy for drill-down
    'hierarchy': {
        'super_domains': hierarchy['levels'][0],
        'domains': hierarchy['levels'][1],
        'subdomains': hierarchy['levels'][2],
        'coarse_clusters': hierarchy['levels'][3],
        'fine_clusters': hierarchy['levels'][4]
    }
}

print(f"   ✅ Final output assembled")

# ============================================================================
# STEP 8: EXPORT
# ============================================================================

print("\n[STEP 8] Exporting...")

# Main JSON file
json_path = output_dir / "causal_graph_v2_FINAL.json"
with open(json_path, 'w') as f:
    json.dump(final_output, f, indent=2)
print(f"   ✅ Saved: {json_path}")
print(f"      Size: {json_path.stat().st_size / (1024*1024):.1f} MB")

# Updated summary
summary = {
    'metadata': final_output['metadata'],
    'layer_compression_presets': {
        name: {'bands': len(p['bands']), 'labels': p['labels']}
        for name, p in layer_compression_presets.items()
    },
    'top_lists_summary': {name: len(lst) for name, lst in top_lists.items()},
    'domain_distribution': hierarchy['metadata'].get('domain_distribution', {}),
    'layer_distribution': dict(sorted(layer_counts.items()))
}

summary_path = output_dir / "B35_hierarchy_summary_FINAL.json"
with open(summary_path, 'w') as f:
    json.dump(summary, f, indent=2)
print(f"   ✅ Saved: {summary_path}")

# ============================================================================
# VALIDATION
# ============================================================================

print("\n" + "=" * 80)
print("VALIDATION CHECKS")
print("=" * 80)

# Check 1: All nodes have scores
nodes_with_scores = sum(1 for n in nodes_list if 'scores' in n and n['scores']['composite'] > 0)
print(f"\n✅ Check 1: Nodes with scores: {nodes_with_scores}/{len(nodes_list)} ({100*nodes_with_scores/len(nodes_list):.1f}%)")

# Check 2: Edges with moderators
print(f"✅ Check 2: Edges with moderators: {n_edges_with_mods}/{len(edges_list)} ({100*n_edges_with_mods/len(edges_list):.1f}%)")
print(f"   Total moderator effects: {total_moderators}")

# Check 3: Compression presets
print(f"✅ Check 3: Compression presets: {len(layer_compression_presets)}")

# Check 4: Top lists
print(f"✅ Check 4: Top lists: {len(top_lists)} lists with {sum(len(l) for l in top_lists.values())} total entries")

# Check 5: Layer distribution
print(f"✅ Check 5: Layer distribution:")
print(f"   Drivers (layer 0): {n_drivers}")
print(f"   Mechanisms (1-18): {len(nodes_list) - n_drivers - n_outcomes}")
print(f"   Outcomes (19+): {n_outcomes}")

# ============================================================================
# SUMMARY
# ============================================================================

print("\n" + "=" * 80)
print("B3.5 FINAL EXPORT COMPLETE")
print("=" * 80)

print(f"""
Summary:
   Nodes: {len(nodes_list):,}
   Edges: {len(edges_list):,}
   Edges with moderators: {n_edges_with_mods:,} ({100*n_edges_with_mods/len(edges_list):.1f}%)
   Total moderator effects: {total_moderators:,}

   Layer compression presets: {len(layer_compression_presets)}
   Top-K lists: {len(top_lists)}

Output files:
   - {json_path}
   - {summary_path}

🎯 READY FOR VISUALIZATION
""")
