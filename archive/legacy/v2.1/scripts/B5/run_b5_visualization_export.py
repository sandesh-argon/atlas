#!/usr/bin/env python3
"""
B5: Visualization Export (6-Layer Structure)
Generates final JSON with all required fields for dashboard visualization.

Updated to use B36 hierarchy with LLM-generated semantic names.

Required Fields (per OUTPUT_REQUIREMENTS.md):
- Top-level: metadata, nodes, edges, hierarchy, outcomes, interactions, clusters
- Node: id, label, layer, node_type, domain, subdomain, shap_importance, in_degree, out_degree, label_source, parent, children
- Edge: source, target, relationship, lag, effect_size, p_value, ci_lower, ci_upper, bootstrap_stability, sample_size
"""

import pickle
import json
import numpy as np
from pathlib import Path
from collections import defaultdict
from datetime import datetime

print("=" * 80)
print("B5: VISUALIZATION EXPORT (6-LAYER STRUCTURE WITH LLM NAMES)")
print("=" * 80)
print(f"Timestamp: {datetime.now().isoformat()}")

# Paths
BASE_DIR = Path('<repo-root>/v2.0/v2.1')
OUTPUT_DIR = BASE_DIR / 'outputs' / 'B5'
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

FINAL_DIR = Path('<repo-root>/final_semantic_viz')
FINAL_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================================
# STEP 1: LOAD DATA
# ============================================================================

print("\n[STEP 1] Loading data...")

# Load B36 hierarchy (with LLM-generated names)
hierarchy_path = BASE_DIR / 'outputs' / 'B36' / 'B36_semantic_hierarchy_llm.pkl'
with open(hierarchy_path, 'rb') as f:
    hierarchy_data = pickle.load(f)
print(f"   Loaded hierarchy with {len(hierarchy_data['nodes'])} nodes (B36 with LLM names)")

# Load semantic paths from B36
paths_path = BASE_DIR / 'outputs' / 'B36' / 'B36_semantic_paths.json'
with open(paths_path, 'r') as f:
    semantic_paths = json.load(f)
print(f"   Loaded {len(semantic_paths)} semantic paths")

# Load B1 outcomes
b1_path = BASE_DIR / 'outputs' / 'B1' / 'B1_validated_outcomes.pkl'
with open(b1_path, 'rb') as f:
    b1_data = pickle.load(f)
outcomes_data = b1_data['outcomes']
print(f"   Loaded {len(outcomes_data)} B1 outcomes")

# Load indicator labels
labels_path = BASE_DIR / 'outputs' / 'B1' / 'indicator_labels_comprehensive.json'
with open(labels_path, 'r') as f:
    indicator_labels = json.load(f)
print(f"   Loaded {len(indicator_labels)} indicator labels")

# Load SHAP scores - try B36 first, fall back to B35
shap_path = BASE_DIR / 'outputs' / 'B35' / 'B35_shap_scores.pkl'
if shap_path.exists():
    with open(shap_path, 'rb') as f:
        shap_scores = pickle.load(f)
    print(f"   Loaded SHAP scores for {len(shap_scores)} indicators")
else:
    # Create empty shap scores if not available
    shap_scores = {}
    print("   SHAP scores not found, using empty dict")

# Load A6 graph
a6_path = BASE_DIR / 'outputs' / 'A6' / 'A6_hierarchical_graph.pkl'
with open(a6_path, 'rb') as f:
    a6_data = pickle.load(f)
graph = a6_data['graph']
print(f"   Loaded graph with {graph.number_of_nodes()} nodes, {graph.number_of_edges()} edges")

# Load A5 interactions
a5_path = BASE_DIR / 'outputs' / 'A5' / 'A5_interaction_effects.pkl'
try:
    with open(a5_path, 'rb') as f:
        a5_data = pickle.load(f)
    interactions_data = a5_data.get('significant_interactions', [])
    if isinstance(interactions_data, dict):
        interactions_data = list(interactions_data.values())
    print(f"   Loaded {len(interactions_data)} interactions from A5")
except:
    interactions_data = []
    print("   No A5 interactions found")

# Load A4 effect estimates
a4_path = BASE_DIR / 'outputs' / 'A4' / 'A4_effect_estimates.pkl'
try:
    with open(a4_path, 'rb') as f:
        a4_data = pickle.load(f)
    effect_estimates = a4_data.get('effect_estimates', {})
    print(f"   Loaded {len(effect_estimates)} effect estimates from A4")
except:
    effect_estimates = {}
    print("   No A4 effect estimates found")


def get_label(ind):
    """Get label string from indicator labels dict"""
    label_data = indicator_labels.get(ind, {})
    if isinstance(label_data, dict):
        return label_data.get('label', ind)
    return str(label_data) if label_data else ind


def get_label_source(ind):
    """Get label source from indicator labels dict"""
    label_data = indicator_labels.get(ind, {})
    if isinstance(label_data, dict):
        return label_data.get('source', 'Unknown')
    return 'Unknown'


# ============================================================================
# STEP 2: COMPUTE NODE DEGREES (from graph)
# ============================================================================

print("\n[STEP 2] Computing node degrees...")

in_degrees = dict(graph.in_degree())
out_degrees = dict(graph.out_degree())
print(f"   Computed degrees for {len(in_degrees)} nodes")

# ============================================================================
# STEP 3: DETERMINE NODE TYPES
# ============================================================================

print("\n[STEP 3] Determining node types...")


def get_node_type(node_id):
    """Determine node type based on graph structure"""
    in_deg = in_degrees.get(node_id, 0)
    out_deg = out_degrees.get(node_id, 0)

    if out_deg == 0 and in_deg > 0:
        return 'outcome'
    elif in_deg == 0 and out_deg > 0:
        return 'driver'
    elif in_deg > 0 and out_deg > 0:
        return 'mechanism'
    else:
        return 'intermediate'


# ============================================================================
# STEP 4: BUILD NODES ARRAY
# ============================================================================

print("\n[STEP 4] Building nodes array...")

nodes = []
layer_counts = defaultdict(int)

# Add root node - B36 format has root as dict with label
root_children = hierarchy_data['root'].get('children', [])
# Convert numeric children IDs to strings if needed
root_children_str = [str(c) for c in root_children]

nodes.append({
    "id": "root",
    "label": hierarchy_data['root'].get('label', "Quality of Life"),
    "description": "Global development indicators organized by QoL outcomes",
    "layer": 0,
    "node_type": "root",
    "domain": None,
    "subdomain": None,
    "shap_importance": 0.0,
    "in_degree": 0,
    "out_degree": len(root_children),
    "label_source": "system",
    "parent": None,
    "children": root_children_str,
    "is_indicator": False
})
layer_counts[0] = 1

# Add all hierarchy nodes
for node_id, node_info in hierarchy_data['nodes'].items():
    layer = node_info['layer']
    layer_counts[layer] += 1

    # Get SHAP score for indicators
    shap_value = 0.0
    if layer == 5:  # Indicator
        shap_data = shap_scores.get(node_id, {})
        if isinstance(shap_data, dict):
            shap_value = shap_data.get('shap_normalized', 0.0)
        else:
            shap_value = float(shap_data) if shap_data else 0.0

    # Get domain and subdomain - B36 uses 'label' not 'name'
    domain = node_info.get('domain', None)
    subdomain = None

    if layer >= 3:
        # Get parent coarse domain as subdomain
        parent_id = node_info.get('parent')
        parent_id_str = str(parent_id) if parent_id is not None else None
        if parent_id_str and parent_id_str in hierarchy_data['nodes']:
            parent = hierarchy_data['nodes'][parent_id_str]
            if parent['layer'] == 2:
                subdomain = parent.get('label', parent.get('name', ''))

    # Determine node type based on layer (use hierarchy node_type if available)
    hierarchy_node_type = node_info.get('node_type')
    if layer == 5:
        node_type = get_node_type(node_id)
    elif layer == 0:
        node_type = 'root'
    elif layer == 1:
        node_type = 'outcome_category'
    elif layer == 2:
        node_type = 'coarse_domain'
    elif layer == 3:
        node_type = 'fine_domain'
    elif layer == 4:
        # Use hierarchy node_type if available (can be 'indicator' for promoted)
        node_type = hierarchy_node_type if hierarchy_node_type else 'indicator_group'
    else:
        node_type = 'unknown'

    # Get causal layer for indicators
    causal_layer = a6_data.get('layer_assignments', {}).get(node_id, 0) if layer == 5 else 0

    # Get node label - prefer indicator_labels for indicators (Layer 5 and promoted Layer 4)
    # Fall back to B36 hierarchy label, then to node_id
    is_promoted = node_info.get('promoted', False)
    if layer == 5 or (layer == 4 and is_promoted):
        # Use indicator_labels if available and not just a code-like placeholder
        label_from_file = get_label(node_id)
        hierarchy_label = node_info.get('label', node_info.get('name', node_id))
        # Check if label_from_file is a real label (not just formatted code)
        if label_from_file and label_from_file != node_id and label_from_file != node_id.replace('_', ' '):
            node_label = label_from_file
        else:
            node_label = hierarchy_label
    else:
        node_label = node_info.get('label', node_info.get('name', node_id))

    # Get parent and children, convert to strings if needed
    parent_val = node_info.get('parent')
    parent_str = str(parent_val) if parent_val is not None else None
    if parent_str == 'None':
        parent_str = 'root'

    children_raw = node_info.get('children', [])
    children_str = [str(c) for c in children_raw] if children_raw else []

    node = {
        "id": str(node_id),
        "label": node_label,
        "layer": layer,
        "node_type": node_type,
        "domain": domain,
        "subdomain": subdomain,
        "shap_importance": shap_value,
        "in_degree": in_degrees.get(node_id, 0),
        "out_degree": out_degrees.get(node_id, 0),
        "label_source": get_label_source(node_id) if layer == 5 else "hierarchy",
        "parent": parent_str,
        "children": children_str,
        "is_indicator": layer == 5
    }

    # Add extra fields for indicators
    if layer == 5:
        node["causal_layer"] = causal_layer
        # B36 semantic paths have 'path' key with full path string
        path_info = semantic_paths.get(node_id, {})
        if isinstance(path_info, dict):
            node["semantic_path"] = path_info.get('path', '')
        else:
            node["semantic_path"] = str(path_info) if path_info else ''
        node["description"] = indicator_labels.get(node_id, {}).get('description', '') if isinstance(indicator_labels.get(node_id), dict) else ''

    # Add promoted flag for Layer 4 nodes
    if layer == 4:
        promoted = node_info.get('promoted', False)
        if promoted:
            node["promoted"] = True

    nodes.append(node)

print(f"   Built {len(nodes)} nodes")
for layer in range(6):
    print(f"      Layer {layer}: {layer_counts[layer]} nodes")

# ============================================================================
# STEP 5: BUILD EDGES ARRAY
# ============================================================================

print("\n[STEP 5] Building edges array...")

edges = []

# Add causal edges from graph
for source, target, edge_data in graph.edges(data=True):
    # Get effect estimate if available
    edge_key = f"{source}_{target}"
    effect = effect_estimates.get(edge_key, {})

    edge = {
        "source": source,
        "target": target,
        "relationship": "causal",
        "lag": edge_data.get('lag', 0),
        "effect_size": effect.get('effect_size', 0),
        "p_value": effect.get('p_value', edge_data.get('p_value', 1.0)),
        "ci_lower": effect.get('ci_lower', 0),
        "ci_upper": effect.get('ci_upper', 0),
        "bootstrap_stability": effect.get('bootstrap_stability', 0),
        "sample_size": effect.get('sample_size', 0)
    }
    edges.append(edge)

causal_edge_count = len(edges)

# Add hierarchical edges
for node_id, node_info in hierarchy_data['nodes'].items():
    parent_id = node_info.get('parent')
    if parent_id:
        edge = {
            "source": parent_id,
            "target": node_id,
            "relationship": "hierarchical",
            "lag": 0,
            "effect_size": 0,
            "p_value": 1.0,
            "ci_lower": 0,
            "ci_upper": 0,
            "bootstrap_stability": 0,
            "sample_size": 0
        }
        edges.append(edge)

# Add root to outcome edges
for outcome_id in hierarchy_data['root']['children']:
    edge = {
        "source": "root",
        "target": outcome_id,
        "relationship": "hierarchical",
        "lag": 0,
        "effect_size": 0,
        "p_value": 1.0,
        "ci_lower": 0,
        "ci_upper": 0,
        "bootstrap_stability": 0,
        "sample_size": 0
    }
    edges.append(edge)

hierarchical_edge_count = len(edges) - causal_edge_count

print(f"   Built {len(edges)} edges (causal: {causal_edge_count}, hierarchical: {hierarchical_edge_count})")

# ============================================================================
# STEP 6: BUILD INTERACTIONS ARRAY
# ============================================================================

print("\n[STEP 6] Building interactions array...")

interactions = []
for inter in interactions_data[:100]:  # Top 100
    if isinstance(inter, dict):
        interactions.append(inter)
    else:
        interactions.append({
            "source": str(inter[0]) if len(inter) > 0 else "",
            "moderator": str(inter[1]) if len(inter) > 1 else "",
            "target": str(inter[2]) if len(inter) > 2 else ""
        })

print(f"   Built {len(interactions)} interactions")

# ============================================================================
# STEP 7: BUILD CLUSTERS (Fine Domains = Layer 3)
# ============================================================================

print("\n[STEP 7] Building clusters...")

clusters = []

# Use fine domains as clusters
fine_domains = [n for n in hierarchy_data['nodes'].values() if n['layer'] == 3]

for fd in fine_domains:
    # B36 uses 'label' not 'name'
    cluster = {
        "id": str(fd.get('id', '')),
        "name": fd.get('label', fd.get('name', '')),
        "parent": str(fd.get('parent', '')) if fd.get('parent') is not None else None,
        "indicators": fd.get('indicators', []),
        "size": len(fd.get('indicators', []))
    }
    clusters.append(cluster)

print(f"   Built {len(clusters)} clusters")

# ============================================================================
# STEP 8: BUILD OUTCOMES METADATA
# ============================================================================

print("\n[STEP 8] Building outcomes metadata...")

outcomes_meta = []

for oid, odata in outcomes_data.items():
    # Find matching outcome in hierarchy
    outcome_node = None
    for nid, ninfo in hierarchy_data['nodes'].items():
        if ninfo['layer'] == 1 and ninfo.get('id') == oid:
            outcome_node = ninfo
            break

    outcome = {
        "id": oid,
        "name": odata['name'],
        "description": odata.get('description', ''),
        "domain": odata.get('domain', odata['name'].split()[0]),
        "indicator_count": len(odata.get('all_indicators', [])),
        "top_indicators": odata.get('top_indicators', [])[:10],
        "children": outcome_node.get('children', []) if outcome_node else []
    }
    outcomes_meta.append(outcome)

print(f"   Built metadata for {len(outcomes_meta)} outcomes")

# ============================================================================
# STEP 9: BUILD HIERARCHY WITH ITEMS PER LAYER
# ============================================================================

print("\n[STEP 9] Building hierarchy with items per layer...")

# Build hierarchy items by layer
hierarchy_by_layer = defaultdict(list)

# Layer 0: Root
hierarchy_by_layer[0].append({
    "id": "root",
    "label": hierarchy_data['root'].get('label', "Quality of Life"),
    "parent": None,
    "children": root_children_str
})

# Other layers - B36 uses 'label' not 'name'
for node_id, node_info in hierarchy_data['nodes'].items():
    layer = node_info['layer']
    node_label = node_info.get('label', node_info.get('name', str(node_id)))
    parent_val = node_info.get('parent')
    parent_str = str(parent_val) if parent_val is not None else 'root'
    if parent_str == 'None':
        parent_str = 'root'
    children_raw = node_info.get('children', [])
    children_str = [str(c) for c in children_raw] if children_raw else []

    hierarchy_by_layer[layer].append({
        "id": str(node_id),
        "label": node_label,
        "parent": parent_str,
        "children": children_str
    })

hierarchy = {
    "root": {
        "id": "root",
        "children": root_children_str
    },
    "layer_names": {
        "0": "Root",
        "1": "Outcomes",
        "2": "Coarse Domains",
        "3": "Fine Domains",
        "4": "Indicator Groups",
        "5": "Indicators"
    },
    "levels": 6,
    "structure": {
        "0": {"name": "Root", "count": layer_counts.get(0, 0)},
        "1": {"name": "Outcomes", "count": layer_counts.get(1, 0)},
        "2": {"name": "Coarse Domains", "count": layer_counts.get(2, 0)},
        "3": {"name": "Fine Domains", "count": layer_counts.get(3, 0)},
        "4": {"name": "Indicator Groups", "count": layer_counts.get(4, 0)},
        "5": {"name": "Indicators", "count": layer_counts.get(5, 0)}
    }
}

# Add actual items per layer
for layer_num in range(6):
    hierarchy[str(layer_num)] = hierarchy_by_layer.get(layer_num, [])

print(f"   Built hierarchy with items per layer")

# ============================================================================
# STEP 10: BUILD FINAL JSON
# ============================================================================

print("\n[STEP 10] Building final JSON...")

visualization_json = {
    "metadata": {
        "version": "V2.1-6LAYER-LLM",
        "generated": datetime.now().isoformat(),
        "approach": "6-Layer Semantic Hierarchy with LLM-Generated Names",
        "description": "Quality of Life visualization with 6-layer semantic hierarchy and LLM-generated domain names (Max 5 children per outcome)",
        "statistics": {
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "causal_edges": causal_edge_count,
            "hierarchical_edges": hierarchical_edge_count,
            "layers": {
                "0_root": layer_counts.get(0, 0),
                "1_outcomes": layer_counts.get(1, 0),
                "2_coarse_domains": layer_counts.get(2, 0),
                "3_fine_domains": layer_counts.get(3, 0),
                "4_indicator_groups": layer_counts.get(4, 0),
                "5_indicators": layer_counts.get(5, 0)
            },
            "outcomes_count": len(outcomes_meta),
            "interactions_count": len(interactions),
            "clusters_count": len(clusters)
        }
    },
    "nodes": nodes,
    "edges": edges,
    "hierarchy": hierarchy,
    "outcomes": outcomes_meta,
    "interactions": interactions,
    "clusters": clusters
}

# ============================================================================
# STEP 11: SAVE OUTPUT
# ============================================================================

print("\n[STEP 11] Saving outputs...")

# Save full JSON
output_path = OUTPUT_DIR / 'v2_1_visualization.json'
with open(output_path, 'w') as f:
    json.dump(visualization_json, f, indent=2)
print(f"   Saved: {output_path}")

# Save to final directory
final_path = FINAL_DIR / 'v2_1_full.json'
with open(final_path, 'w') as f:
    json.dump(visualization_json, f, indent=2)
print(f"   Saved: {final_path}")

# Save compact version
compact_path = OUTPUT_DIR / 'v2_1_visualization_compact.json'
with open(compact_path, 'w') as f:
    json.dump(visualization_json, f, separators=(',', ':'))
print(f"   Saved compact: {compact_path}")

# Get file sizes
import os
full_size = os.path.getsize(output_path) / (1024 * 1024)
compact_size = os.path.getsize(compact_path) / (1024 * 1024)

print("\n" + "=" * 80)
print("B5 VISUALIZATION EXPORT COMPLETE")
print("=" * 80)

print(f"""
Summary:
   Total nodes: {len(nodes):,}
   Total edges: {len(edges):,}
     - Causal: {causal_edge_count:,}
     - Hierarchical: {hierarchical_edge_count:,}
   Outcomes: {len(outcomes_meta)}
   Interactions: {len(interactions)}
   Clusters: {len(clusters)}

Layer Structure:
   Layer 0 (Root):              {layer_counts.get(0, 0):>5} nodes
   Layer 1 (Outcomes):          {layer_counts.get(1, 0):>5} nodes
   Layer 2 (Coarse Domains):    {layer_counts.get(2, 0):>5} nodes
   Layer 3 (Fine Domains):      {layer_counts.get(3, 0):>5} nodes
   Layer 4 (Indicator Groups):  {layer_counts.get(4, 0):>5} nodes
   Layer 5 (Indicators):        {layer_counts.get(5, 0):>5} nodes

File Sizes:
   Full JSON: {full_size:.2f} MB
   Compact JSON: {compact_size:.2f} MB

Output files:
   - {output_path}
   - {compact_path}
   - {final_path}
""")
