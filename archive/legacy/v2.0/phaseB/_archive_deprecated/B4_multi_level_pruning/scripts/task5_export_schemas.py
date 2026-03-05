#!/usr/bin/env python3
"""
B4 Task 5: Export Graph Schemas
================================

Export 3 pruned graphs to JSON format for visualization dashboard.

Schema includes:
- Metadata (version, timestamp, validation scores)
- Nodes (id, label, domain, subdomain, shap_score, layer)
- Edges (source, target, effect, confidence)

Author: B4 Task 5
Date: November 2025
"""

import pickle
import json
from pathlib import Path
import networkx as nx
from datetime import datetime

# ============================================================================
# Setup
# ============================================================================

project_root = Path(__file__).resolve().parents[3]
b4_dir = project_root / 'phaseB/B4_multi_level_pruning'
outputs_dir = b4_dir / 'outputs'

print("="*80)
print("B4 TASK 5: EXPORT GRAPH SCHEMAS")
print("="*80)
print(f"\nTimestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"Estimated duration: 30 minutes")

# ============================================================================
# Step 1: Load Data
# ============================================================================

print("\n" + "="*80)
print("STEP 1: LOAD DATA")
print("="*80)

# Load pruned graphs
pruned_path = outputs_dir / 'B4_pruned_graphs.pkl'
with open(pruned_path, 'rb') as f:
    pruned_data = pickle.load(f)

print(f"✅ Loaded pruned graphs")

# Load layer assignments from prepared data
prepared_path = outputs_dir / 'B4_prepared_data.pkl'
with open(prepared_path, 'rb') as f:
    prepared_data = pickle.load(f)

layer_assignments = prepared_data['graph']['layer_assignments']
print(f"✅ Loaded layer assignments: {len(layer_assignments)} nodes")

# Load validation results
validation_path = outputs_dir / 'B4_comprehensive_validation.json'
with open(validation_path, 'r') as f:
    validation = json.load(f)

print(f"✅ Loaded validation results")

# ============================================================================
# Step 2: Export Each Graph
# ============================================================================

print("\n" + "="*80)
print("STEP 2: EXPORT GRAPH SCHEMAS")
print("="*80)

exported_schemas = {}

for graph_name in ['full_graph', 'professional_graph', 'simplified_graph']:
    graph_data = pruned_data[graph_name]
    graph = graph_data['graph']
    mech_df = graph_data['mechanism_df']

    print(f"\n📊 Exporting {graph_name.replace('_', ' ').title()}...")

    # Build node list
    nodes = []
    for _, row in mech_df.iterrows():
        mechanism = row['mechanism']

        # Get layer from A6
        layer = layer_assignments.get(mechanism, -1)

        node = {
            'id': str(mechanism),
            'label': str(mechanism),  # Could be enhanced with readable labels
            'domain': str(row['domain']),
            'subdomain': str(row['subdomain']),
            'hierarchical_label': str(row['hierarchical_label']),
            'shap_score': float(row['shap_score']),
            'layer': int(layer),
            'cluster_id': int(row['cluster_id'])
        }
        nodes.append(node)

    # Build edge list
    edges = []
    for u, v, data in graph.edges(data=True):
        edge = {
            'source': str(u),
            'target': str(v),
            'effect': float(data.get('effect', 0.0)) if 'effect' in data else None,
            'lag': int(data.get('lag', 1)) if 'lag' in data else 1
        }
        edges.append(edge)

    # Create schema
    schema = {
        'metadata': {
            'version': '2.0',
            'graph_type': graph_name.replace('_graph', ''),
            'timestamp': datetime.now().isoformat(),
            'target_audience': graph_data['target_audience'],
            'level': graph_data['level'],
            'validation': {
                'overall_pass': validation['summary']['overall_pass'],
                'checks_passed': validation['summary']['checks_passed'],
                'total_checks': validation['summary']['total_checks']
            }
        },
        'statistics': {
            'nodes': len(nodes),
            'edges': len(edges),
            'domains': len(mech_df['domain'].unique()),
            'subdomains': len(mech_df['hierarchical_label'].unique()),
            'shap_retention': float(graph_data.get('shap_retention', 1.0)),
            'domain_balance': {k: float(v) for k, v in graph_data['domain_balance'].items()}
        },
        'nodes': nodes,
        'edges': edges
    }

    # Save schema
    schema_filename = f"B4_{graph_name.replace('_graph', '')}_schema.json"
    schema_path = outputs_dir / schema_filename

    with open(schema_path, 'w') as f:
        json.dump(schema, f, indent=2)

    print(f"   ✅ Saved: {schema_filename}")
    print(f"      Nodes: {len(nodes)}, Edges: {len(edges)}")
    print(f"      Size: {schema_path.stat().st_size / 1024:.1f} KB")

    exported_schemas[graph_name] = {
        'filename': schema_filename,
        'nodes': len(nodes),
        'edges': len(edges),
        'size_kb': schema_path.stat().st_size / 1024
    }

# ============================================================================
# Step 3: Create Export Manifest
# ============================================================================

print("\n" + "="*80)
print("STEP 3: CREATE EXPORT MANIFEST")
print("="*80)

manifest = {
    'metadata': {
        'timestamp': datetime.now().isoformat(),
        'task': 'B4_task5_export_schemas',
        'version': '2.0'
    },
    'exported_schemas': exported_schemas,
    'validation_summary': validation['summary'],
    'usage_notes': {
        'full': 'Academic research, complete causal analysis, methodology transparency',
        'professional': 'Policy analysis, scenario testing, 40% of mechanisms (top SHAP)',
        'simplified': 'Public communication, storytelling, top 3 sub-domains'
    }
}

manifest_path = outputs_dir / 'B4_export_manifest.json'
with open(manifest_path, 'w') as f:
    json.dump(manifest, f, indent=2)

print(f"\n✅ Saved export manifest: {manifest_path.name}")

# ============================================================================
# Summary
# ============================================================================

print("\n" + "="*80)
print("TASK 5 COMPLETE - EXPORT SUMMARY")
print("="*80)

print(f"\n📊 Exported Schemas:")
for graph_name, info in exported_schemas.items():
    print(f"   - {info['filename']:<35} {info['nodes']:>4} nodes, {info['edges']:>4} edges, {info['size_kb']:>6.1f} KB")

print(f"\n✅ All graph schemas exported successfully")
print(f"🎯 Next Step: Task 6 - Create Completion Documentation")

print("\n" + "="*80)
print("✅ TASK 5 COMPLETE")
print("="*80)
