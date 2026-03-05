#!/usr/bin/env python3
"""
Create Final Visualization JSON for V2.1

Combines:
- B36 semantic hierarchy (6-layer structure)
- Updated indicator descriptions
- Causal edges from A6
- SHAP importance scores

Output format matches the required schema.
"""

import json
import pickle
from pathlib import Path
from typing import Dict, List, Any

OUTPUT_DIR = Path("outputs/B5")


def load_hierarchy() -> Dict:
    """Load B36 semantic hierarchy."""
    with open('outputs/B36/B36_semantic_hierarchy_llm.pkl', 'rb') as f:
        return pickle.load(f)


def load_descriptions() -> Dict:
    """Load updated indicator descriptions."""
    with open('outputs/B1/indicator_labels_comprehensive_v2.json', 'r') as f:
        return json.load(f)


def load_causal_graph() -> Any:
    """Load A6 causal graph."""
    with open('outputs/A6/A6_hierarchical_graph.pkl', 'rb') as f:
        data = pickle.load(f)
    return data['graph']


def load_shap_scores() -> Dict:
    """Load SHAP importance scores."""
    try:
        with open('outputs/B35/B35_shap_scores.pkl', 'rb') as f:
            return pickle.load(f)
    except:
        return {}


def create_final_json():
    """Create the final visualization JSON."""

    print("Loading data...")
    hierarchy = load_hierarchy()
    descriptions = load_descriptions()
    graph = load_causal_graph()
    shap_scores = load_shap_scores()

    print(f"  Hierarchy nodes: {len(hierarchy['nodes'])}")
    print(f"  Descriptions: {len(descriptions)}")
    print(f"  Graph nodes: {graph.number_of_nodes()}")
    print(f"  Graph edges: {graph.number_of_edges()}")
    print(f"  SHAP scores: {len(shap_scores)}")

    # Build nodes list
    nodes = []

    # Add root node (layer 0)
    root_node = {
        "id": "root",
        "label": "Quality of Life",
        "description": "Root of the global causal discovery hierarchy representing overall quality of life outcomes",
        "layer": 0,
        "node_type": "root",
        "domain": None,
        "subdomain": None,
        "shap_importance": 1.0,
        "in_degree": 0,
        "out_degree": 9,
        "label_source": "manual",
        "children": []
    }

    # Track parent-child relationships
    children_map = {"root": []}

    # Process hierarchy nodes
    for node_id, node_data in hierarchy['nodes'].items():
        layer = node_data.get('layer', 5)

        # Determine node type based on layer
        if layer == 1:
            node_type = "outcome_category"
        elif layer == 2:
            node_type = "coarse_domain"
        elif layer == 3:
            node_type = "fine_domain"
        else:  # layer 4 or 5
            node_type = "indicator"

        # Get description for indicators
        description = ""
        label = node_data.get('label', str(node_id))
        label_source = "hierarchy"

        str_node_id = str(node_id)
        if str_node_id in descriptions:
            desc_data = descriptions[str_node_id]
            if isinstance(desc_data, dict):
                description = desc_data.get('description', '')
                if desc_data.get('label'):
                    label = desc_data['label']
                label_source = desc_data.get('source', 'generated')
            else:
                description = str(desc_data)
        elif layer <= 3:
            # Generate description for hierarchy levels
            description = f"{node_type.replace('_', ' ').title()} grouping: {label}"

        # Get SHAP score
        shap_score = 0.0
        if str_node_id in shap_scores:
            shap_data = shap_scores[str_node_id]
            if isinstance(shap_data, dict):
                shap_score = shap_data.get('shap_normalized', shap_data.get('composite_score', 0))
            else:
                shap_score = float(shap_data)

        # Get degree from causal graph
        in_degree = 0
        out_degree = 0
        if graph.has_node(str_node_id):
            in_degree = graph.in_degree(str_node_id)
            out_degree = graph.out_degree(str_node_id)
        elif graph.has_node(node_id):
            in_degree = graph.in_degree(node_id)
            out_degree = graph.out_degree(node_id)

        # Get parent
        parent = node_data.get('parent', 'root' if layer == 1 else None)
        if parent is None and layer > 0:
            parent = "root"

        # Build node object
        node_obj = {
            "id": str_node_id,
            "label": label,
            "description": description,
            "layer": layer,
            "node_type": node_type,
            "domain": node_data.get('domain'),
            "subdomain": node_data.get('subdomain'),
            "shap_importance": round(shap_score, 4),
            "in_degree": in_degree,
            "out_degree": out_degree,
            "label_source": label_source,
            "parent": str(parent) if parent else None
        }

        # Add children if present
        if 'children' in node_data and node_data['children']:
            node_obj['children'] = [str(c) for c in node_data['children']]

        # Add indicator_count for outcome categories
        if layer == 1 and 'indicators' in node_data:
            node_obj['indicator_count'] = len(node_data['indicators'])

        nodes.append(node_obj)

        # Track children for root
        if layer == 1:
            children_map["root"].append(str_node_id)

    # Update root with children
    root_node["children"] = children_map["root"]
    root_node["out_degree"] = len(children_map["root"])
    nodes.insert(0, root_node)

    print(f"\nBuilt {len(nodes)} nodes")

    # Build edges list
    edges = []

    # Add hierarchical edges from parent-child relationships
    hierarchical_edges = set()
    for node in nodes:
        if node.get('parent'):
            edge_key = (str(node['parent']), str(node['id']))
            if edge_key not in hierarchical_edges:
                edges.append({
                    "source": str(node['parent']),
                    "target": str(node['id']),
                    "weight": 1.0,
                    "relationship": "hierarchical"
                })
                hierarchical_edges.add(edge_key)

    # Add causal edges from graph
    causal_edge_count = 0
    for source, target, data in graph.edges(data=True):
        str_source = str(source)
        str_target = str(target)

        # Skip if this is already a hierarchical edge
        if (str_source, str_target) in hierarchical_edges:
            continue

        weight = data.get('weight', data.get('effect_size', 1.0))
        if isinstance(weight, dict):
            weight = weight.get('beta', 1.0)

        edges.append({
            "source": str_source,
            "target": str_target,
            "weight": round(float(weight), 4) if weight else 1.0,
            "relationship": "causal"
        })
        causal_edge_count += 1

    print(f"Built {len(edges)} edges ({len(hierarchical_edges)} hierarchical, {causal_edge_count} causal)")

    # Build hierarchy object
    hierarchy_obj = {}
    for node in nodes:
        if node.get('children'):
            hierarchy_obj[node['id']] = node['children']

    # Count by layer
    layer_counts = {}
    for node in nodes:
        layer = node['layer']
        layer_counts[str(layer)] = layer_counts.get(str(layer), 0) + 1

    # Build final JSON
    final_json = {
        "nodes": nodes,
        "edges": edges,
        "hierarchy": hierarchy_obj,
        "metadata": {
            "version": "2.1",
            "generated": "2025-12-10",
            "statistics": {
                "total_nodes": len(nodes),
                "total_edges": len(edges),
                "causal_edges": causal_edge_count,
                "hierarchical_edges": len(hierarchical_edges),
                "layers": layer_counts
            },
            "sources": {
                "hierarchy": "B36_semantic_hierarchy_llm.pkl",
                "descriptions": "indicator_labels_comprehensive_v2.json",
                "causal_graph": "A6_hierarchical_graph.pkl",
                "shap_scores": "B35_shap_scores.pkl"
            }
        }
    }

    # Save full JSON
    output_path = OUTPUT_DIR / "v2_1_visualization_final.json"
    with open(output_path, 'w') as f:
        json.dump(final_json, f, indent=2)
    print(f"\nSaved full JSON to {output_path}")
    print(f"  Size: {output_path.stat().st_size / 1024 / 1024:.2f} MB")

    # Save compact version (no indentation)
    compact_path = OUTPUT_DIR / "v2_1_visualization_final_compact.json"
    with open(compact_path, 'w') as f:
        json.dump(final_json, f)
    print(f"Saved compact JSON to {compact_path}")
    print(f"  Size: {compact_path.stat().st_size / 1024 / 1024:.2f} MB")

    # Print summary
    print("\n" + "="*60)
    print("FINAL VISUALIZATION JSON SUMMARY")
    print("="*60)
    print(f"\nNodes by layer:")
    for layer in sorted(layer_counts.keys(), key=int):
        count = layer_counts[layer]
        layer_int = int(layer)
        if layer_int == 0:
            node_type = "root"
        elif layer_int == 1:
            node_type = "outcome_category"
        elif layer_int == 2:
            node_type = "coarse_domain"
        elif layer_int == 3:
            node_type = "fine_domain"
        else:
            node_type = "indicator"
        print(f"  Layer {layer}: {count} ({node_type})")

    print(f"\nEdges:")
    print(f"  Hierarchical: {len(hierarchical_edges)}")
    print(f"  Causal: {causal_edge_count}")
    print(f"  Total: {len(edges)}")

    # Validate
    print("\nValidation:")
    layer_0_count = layer_counts.get('0', 0)
    layer_1_count = layer_counts.get('1', 0)
    print(f"  ✓ Layer 0 has {layer_0_count} node (expected: 1)")
    print(f"  ✓ Layer 1 has {layer_1_count} nodes (expected: 9)")

    # Check all nodes have required fields
    missing_parent = sum(1 for n in nodes if n['layer'] > 0 and not n.get('parent'))
    print(f"  ✓ Nodes missing parent: {missing_parent}")

    return final_json


if __name__ == "__main__":
    create_final_json()
