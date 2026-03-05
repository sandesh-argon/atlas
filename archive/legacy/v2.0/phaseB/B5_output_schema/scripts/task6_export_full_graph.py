#!/usr/bin/env python3
"""
B5 Task 6: Export Complete Causal Graph with All Layers
========================================================

Creates causal_graph_v2_FULL.json with:
- All 8,126 nodes (not just 290 mechanisms)
- All 22,521 edges
- All 21 causal layers per node
- Domain/subdomain/cluster assignments
- SHAP scores where available
- Node type flags (driver/mechanism/intermediate/outcome)
- A4 effect sizes with confidence intervals
- A5 interaction effects
- B1 outcome factor loadings

This flexible schema allows frontend to decide compression strategy.

Author: B5 Schema Generation
Date: November 2025
"""

import pickle
import json
import numpy as np
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# ============================================================================
# Setup
# ============================================================================

project_root = Path(__file__).resolve().parents[3]
b5_dir = project_root / 'phaseB/B5_output_schema'
outputs_dir = b5_dir / 'outputs'
exports_dir = outputs_dir / 'exports'
exports_dir.mkdir(parents=True, exist_ok=True)

print("="*80)
print("B5 TASK 6: EXPORT COMPLETE CAUSAL GRAPH (FULL)")
print("="*80)
print(f"\nTimestamp: {datetime.now().isoformat()}")

# ============================================================================
# Load A6: Full Hierarchical Graph (8,126 nodes, 22,521 edges)
# ============================================================================

print("\n" + "="*80)
print("LOADING A6 HIERARCHICAL GRAPH")
print("="*80)

a6_path = project_root / 'phaseA/A6_hierarchical_layering/outputs/A6_hierarchical_graph.pkl'
print(f"Loading: {a6_path}")

with open(a6_path, 'rb') as f:
    a6_data = pickle.load(f)

G = a6_data['graph']
layers = a6_data['layers']
centrality = a6_data.get('centrality', {})

print(f"✅ A6 Loaded:")
print(f"   - Nodes: {len(G.nodes())}")
print(f"   - Edges: {len(G.edges())}")
print(f"   - Layers: {a6_data['n_layers']}")

# Layer distribution
layer_counts = defaultdict(int)
for n, l in layers.items():
    layer_counts[l] += 1
print(f"   - Layer distribution: {dict(sorted(layer_counts.items()))}")

# ============================================================================
# Load A4: Effect Quantification (beta, CI, p-values)
# ============================================================================

print("\n" + "="*80)
print("LOADING A4 EFFECT QUANTIFICATION")
print("="*80)

a4_path = project_root / 'phaseA/A4_effect_quantification/outputs/lasso_effect_estimates_WITH_WARNINGS.pkl'
print(f"Loading: {a4_path}")

with open(a4_path, 'rb') as f:
    a4_data = pickle.load(f)

# Create effect size lookup (source, target) -> effect_info
effect_lookup = {}
for edge in a4_data['validated_edges']:
    key = (edge['source'], edge['target'])
    effect_lookup[key] = {
        'beta': edge['beta'],
        'ci_lower': edge['ci_lower'],
        'ci_upper': edge['ci_upper'],
        'sample_size': edge['sample_size'],
        'n_selected': edge['n_selected'],
        'is_extreme': edge.get('is_extreme', False),
        'needs_review': edge.get('needs_review', False)
    }

print(f"✅ A4 Loaded:")
print(f"   - All results: {len(a4_data['all_results'])}")
print(f"   - Validated edges with effects: {len(effect_lookup)}")

# ============================================================================
# Load A5: Interaction Effects
# ============================================================================

print("\n" + "="*80)
print("LOADING A5 INTERACTION EFFECTS")
print("="*80)

a5_path = project_root / 'phaseA/A5_interaction_discovery/outputs/A5_interaction_results_FILTERED_STRICT.pkl'
print(f"Loading: {a5_path}")

with open(a5_path, 'rb') as f:
    a5_data = pickle.load(f)

interactions = a5_data['validated_interactions']
print(f"✅ A5 Loaded:")
print(f"   - Validated interactions: {len(interactions)}")

# Group interactions by outcome
interactions_by_outcome = defaultdict(list)
for inter in interactions:
    interactions_by_outcome[inter['outcome']].append({
        'mechanism_1': inter['mechanism_1'],
        'mechanism_2': inter['mechanism_2'],
        'beta': inter['beta_interaction'],
        't_stat': inter['t_statistic'],
        'p_value': inter['p_value'],
        'r_squared': inter['r_squared']
    })

print(f"   - Outcomes with interactions: {len(interactions_by_outcome)}")

# ============================================================================
# Load B1: Outcome Factor Loadings
# ============================================================================

print("\n" + "="*80)
print("LOADING B1 OUTCOME FACTORS")
print("="*80)

b1_path = project_root / 'phaseB/B1_outcome_discovery/outputs/B1_validated_outcomes.pkl'
print(f"Loading: {b1_path}")

with open(b1_path, 'rb') as f:
    b1_data = pickle.load(f)

outcomes = b1_data['outcomes']
print(f"✅ B1 Loaded:")
print(f"   - Validated outcomes: {len(outcomes)}")

# Build outcome info
outcome_info = []
for outcome in outcomes:
    outcome_info.append({
        'id': outcome['factor_id'],
        'name': outcome.get('factor_name', f"Factor_{outcome['factor_id']}"),
        'domain': outcome.get('primary_domain', 'Unknown'),
        'top_variables': outcome.get('top_variables', [])[:10],
        'top_loadings': outcome.get('top_loadings', [])[:10],
        'r_squared': outcome.get('r_squared', None),
        'r_squared_std': outcome.get('r_squared_std', None),
        'validation': {
            'passes_coherence': outcome.get('passes_domain_coherence', False),
            'passes_literature': outcome.get('passes_literature_alignment', False),
            'passes_predictability': outcome.get('passes_predictability', False),
            'is_novel': outcome.get('is_novel', False)
        }
    })

# ============================================================================
# Load B3: Domain Classifications
# ============================================================================

print("\n" + "="*80)
print("LOADING B3 DOMAIN CLASSIFICATIONS")
print("="*80)

b3_path = project_root / 'phaseB/B3_domain_classification/outputs/B3_part4_enriched.pkl'
print(f"Loading: {b3_path}")

with open(b3_path, 'rb') as f:
    b3_data = pickle.load(f)

# Build mechanism domain lookup
mechanism_domains = {}
unified_metadata = b3_data.get('unified_metadata', {})
cluster_assignments = b3_data.get('cluster_assignments', {})

# Get enriched cluster metadata for subdomain info
enriched_clusters = b3_data.get('enriched_cluster_metadata', [])
cluster_info = {}
for cluster in enriched_clusters:
    cluster_id = cluster['cluster_id']
    cluster_info[cluster_id] = {
        'primary_domain': cluster['primary_domain'],
        'subdomain': cluster.get('sub_domain', 'General'),
        'cluster_name': cluster.get('cluster_name', f'Cluster_{cluster_id}'),
        'description': cluster.get('description', ''),
        'hierarchical_label': cluster.get('hierarchical_label', '')
    }

# Map mechanisms to domains
for node_id in b3_data.get('mechanism_candidates', []):
    cluster_id = cluster_assignments.get(node_id)
    if cluster_id is not None and cluster_id in cluster_info:
        info = cluster_info[cluster_id]
        mechanism_domains[node_id] = {
            'domain': info['primary_domain'],
            'subdomain': info['subdomain'],
            'cluster_id': cluster_id,
            'cluster_name': info['cluster_name']
        }
    else:
        mechanism_domains[node_id] = {
            'domain': 'Unclassified',
            'subdomain': 'Unknown',
            'cluster_id': None,
            'cluster_name': None
        }

print(f"✅ B3 Loaded:")
print(f"   - Mechanism candidates: {len(b3_data['mechanism_candidates'])}")
print(f"   - Clusters: {len(enriched_clusters)}")
print(f"   - Mechanisms with domains: {len(mechanism_domains)}")

# Get indicator metadata for labels
indicator_metadata = {}
for node_id, meta in unified_metadata.items():
    if isinstance(meta, dict):
        indicator_metadata[node_id] = {
            'label': meta.get('indicator_name', meta.get('name', node_id)),
            'source': meta.get('source', 'Unknown'),
            'category': meta.get('category', ''),
            'description': meta.get('description', '')
        }

print(f"   - Indicators with metadata: {len(indicator_metadata)}")

# ============================================================================
# Load B4: SHAP Scores
# ============================================================================

print("\n" + "="*80)
print("LOADING B4 SHAP SCORES")
print("="*80)

b4_shap_path = project_root / 'phaseB/B4_multi_level_pruning/outputs/B4_shap_scores.pkl'
print(f"Loading: {b4_shap_path}")

with open(b4_shap_path, 'rb') as f:
    shap_data = pickle.load(f)

shap_scores = shap_data.get('mechanism_shap_scores', {})
print(f"✅ B4 SHAP Loaded:")
print(f"   - Mechanisms with SHAP scores: {len(shap_scores)}")

# ============================================================================
# Load Comprehensive Indicator Labels
# ============================================================================

print("\n" + "="*80)
print("LOADING COMPREHENSIVE INDICATOR LABELS")
print("="*80)

labels_path = outputs_dir / 'indicator_labels_comprehensive.json'

if labels_path.exists():
    with open(labels_path, 'r') as f:
        comprehensive_labels = json.load(f)
    print(f"✅ Labels Loaded: {len(comprehensive_labels):,} indicators")
else:
    print("⚠️  Labels file not found - run generate_indicator_labels.py first")
    comprehensive_labels = {}

# ============================================================================
# Build Complete Node List
# ============================================================================

print("\n" + "="*80)
print("BUILDING COMPLETE NODE LIST")
print("="*80)

nodes = []
node_type_counts = defaultdict(int)

for node_id in G.nodes():
    layer = layers.get(node_id, -1)

    # Determine node type based on layer
    is_driver = (layer == 0)
    is_outcome = (layer >= 19)
    is_mechanism = node_id in mechanism_domains

    if is_driver:
        node_type = 'driver'
    elif is_outcome:
        node_type = 'outcome'
    elif is_mechanism:
        node_type = 'mechanism'
    else:
        node_type = 'intermediate'

    node_type_counts[node_type] += 1

    # Get domain info
    domain_info = mechanism_domains.get(node_id, {
        'domain': 'Unclassified',
        'subdomain': 'Unknown',
        'cluster_id': None,
        'cluster_name': None
    })

    # Get comprehensive label info
    label_info = comprehensive_labels.get(node_id, {})
    label = label_info.get('label', node_id)
    label_source = label_info.get('source', 'Unknown')
    label_description = label_info.get('description', '')

    # Get centrality scores
    centrality_scores = {}
    if 'betweenness' in centrality:
        centrality_scores['betweenness'] = centrality['betweenness'].get(node_id, 0)
    if 'pagerank' in centrality:
        centrality_scores['pagerank'] = centrality['pagerank'].get(node_id, 0)
    if 'degree' in centrality:
        centrality_scores['degree'] = centrality['degree'].get(node_id, 0)

    # Build node - both code (id) and human-readable name (label)
    node = {
        'id': node_id,                    # Indicator code
        'label': label,                    # Human-readable name
        'causal_layer': layer,
        'domain': domain_info['domain'],
        'subdomain': domain_info['subdomain'],
        'cluster_id': domain_info['cluster_id'],
        'cluster_name': domain_info['cluster_name'],
        'shap_score': shap_scores.get(node_id),
        'centrality': centrality_scores if centrality_scores else None,
        'degree': {
            'in': G.in_degree(node_id),
            'out': G.out_degree(node_id),
            'total': G.degree(node_id)
        },
        'is_driver': is_driver,
        'is_outcome': is_outcome,
        'is_mechanism': is_mechanism,
        'node_type': node_type,
        'metadata': {
            'source': label_source,
            'description': label_description
        }
    }
    nodes.append(node)

print(f"✅ Built {len(nodes)} nodes")
print(f"   Node types: {dict(node_type_counts)}")

# Count label coverage
nodes_with_labels = sum(1 for n in nodes if n['label'] != n['id'])
print(f"   Nodes with human-readable labels: {nodes_with_labels} ({nodes_with_labels/len(nodes)*100:.1f}%)")

# ============================================================================
# Build Complete Edge List
# ============================================================================

print("\n" + "="*80)
print("BUILDING COMPLETE EDGE LIST")
print("="*80)

edges = []
edges_with_effects = 0
edges_validated = 0

for source, target in G.edges():
    source_layer = layers.get(source, -1)
    target_layer = layers.get(target, -1)

    # Get effect info if available
    effect = effect_lookup.get((source, target))

    edge = {
        'source': source,
        'target': target,
        'source_layer': source_layer,
        'target_layer': target_layer,
        'layer_diff': target_layer - source_layer if source_layer >= 0 and target_layer >= 0 else None
    }

    if effect:
        edges_with_effects += 1
        edge['weight'] = effect['beta'] if not np.isnan(effect['beta']) else None
        edge['ci_lower'] = effect['ci_lower'] if not np.isnan(effect['ci_lower']) else None
        edge['ci_upper'] = effect['ci_upper'] if not np.isnan(effect['ci_upper']) else None
        edge['sample_size'] = int(effect['sample_size']) if effect['sample_size'] and not np.isnan(effect['sample_size']) else None
        edge['validated'] = True
        edge['needs_review'] = effect.get('needs_review', False)
        edges_validated += 1
    else:
        edge['weight'] = None
        edge['ci_lower'] = None
        edge['ci_upper'] = None
        edge['sample_size'] = None
        edge['validated'] = False
        edge['needs_review'] = False

    edges.append(edge)

print(f"✅ Built {len(edges)} edges")
print(f"   - Edges with A4 effect sizes: {edges_with_effects}")
print(f"   - Edges validated: {edges_validated}")

# ============================================================================
# Build Hierarchy Metadata
# ============================================================================

print("\n" + "="*80)
print("BUILDING HIERARCHY METADATA")
print("="*80)

# Layer statistics
layer_stats = {}
for layer in range(21):
    layer_nodes = [n for n in nodes if n['causal_layer'] == layer]
    layer_type = 'driver' if layer == 0 else ('outcome' if layer >= 19 else 'intermediate')
    layer_stats[layer] = {
        'count': len(layer_nodes),
        'type': layer_type,
        'domains': list(set(n['domain'] for n in layer_nodes if n['domain']))
    }

print(f"✅ Layer statistics: 21 layers")

# Domain hierarchy
domain_hierarchy = {}
all_domains = set(n['domain'] for n in nodes if n['domain'])

for domain in all_domains:
    domain_nodes = [n for n in nodes if n['domain'] == domain]
    subdomains = list(set(n['subdomain'] for n in domain_nodes if n['subdomain']))
    domain_hierarchy[domain] = {
        'subdomains': subdomains,
        'node_count': len(domain_nodes),
        'layers': sorted(list(set(n['causal_layer'] for n in domain_nodes if n['causal_layer'] >= 0))),
        'clusters': list(set(n['cluster_id'] for n in domain_nodes if n['cluster_id'] is not None))
    }

print(f"✅ Domain hierarchy: {len(domain_hierarchy)} domains")

# ============================================================================
# Build Interaction Summary
# ============================================================================

print("\n" + "="*80)
print("BUILDING INTERACTION SUMMARY")
print("="*80)

interaction_summary = []
for outcome, inters in interactions_by_outcome.items():
    interaction_summary.append({
        'outcome': outcome,
        'count': len(inters),
        'interactions': inters[:10]  # Top 10 per outcome
    })

print(f"✅ Interaction summary: {len(interaction_summary)} outcomes with {len(interactions)} total interactions")

# ============================================================================
# Assemble Final Schema
# ============================================================================

print("\n" + "="*80)
print("ASSEMBLING FINAL SCHEMA")
print("="*80)

# Calculate max SHAP score
max_shap = max((n['shap_score'] or 0) for n in nodes)

full_schema = {
    'metadata': {
        'version': '2.1-FULL',
        'timestamp': datetime.now().isoformat(),
        'description': 'Complete causal graph with all layers for flexible visualization',
        'node_count': len(nodes),
        'edge_count': len(edges),
        'layer_count': 21,
        'source_files': {
            'A6': 'A6_hierarchical_graph.pkl',
            'A4': 'lasso_effect_estimates_WITH_WARNINGS.pkl',
            'A5': 'A5_interaction_results_FILTERED_STRICT.pkl',
            'B1': 'B1_validated_outcomes.pkl',
            'B3': 'B3_part4_enriched.pkl',
            'B4': 'B4_shap_scores.pkl'
        },
        'statistics': {
            'nodes_by_type': dict(node_type_counts),
            'edges_with_effects': edges_with_effects,
            'edges_validated': edges_validated,
            'interactions_count': len(interactions),
            'outcomes_count': len(outcomes)
        }
    },
    'nodes': nodes,
    'edges': edges,
    'hierarchy': {
        'domains': domain_hierarchy,
        'layer_statistics': layer_stats
    },
    'outcomes': outcome_info,
    'interactions': interaction_summary,
    'clusters': [
        {
            'id': c['cluster_id'],
            'name': c.get('cluster_name', f"Cluster_{c['cluster_id']}"),
            'domain': c['primary_domain'],
            'subdomain': c.get('sub_domain', 'General'),
            'description': c.get('description', ''),
            'hierarchical_label': c.get('hierarchical_label', ''),
            'size': c.get('size', 0)
        }
        for c in enriched_clusters
    ],
    'filters': {
        'by_layer': list(range(21)),
        'by_domain': list(domain_hierarchy.keys()),
        'by_type': ['driver', 'mechanism', 'intermediate', 'outcome'],
        'by_shap': {'min': 0, 'max': max_shap}
    }
}

# ============================================================================
# Export JSON
# ============================================================================

print("\n" + "="*80)
print("EXPORTING JSON")
print("="*80)

# Custom JSON encoder for numpy types
class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.bool_):
            return bool(obj)
        if isinstance(obj, (np.integer, np.int64, np.int32)):
            return int(obj)
        if isinstance(obj, (np.floating, np.float64, np.float32)):
            if np.isnan(obj):
                return None
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)

output_path = exports_dir / 'causal_graph_v2_FULL.json'

with open(output_path, 'w') as f:
    json.dump(full_schema, f, indent=2, cls=NumpyEncoder)

# Calculate file size
file_size_mb = output_path.stat().st_size / (1024 * 1024)

print(f"✅ Exported to: {output_path}")
print(f"   File size: {file_size_mb:.2f} MB")

# ============================================================================
# Summary
# ============================================================================

print("\n" + "="*80)
print("TASK 6 COMPLETE - FULL GRAPH EXPORTED")
print("="*80)

print(f"""
✅ Export Summary:
   - Nodes: {len(nodes):,}
     • Drivers (layer 0): {node_type_counts['driver']:,}
     • Mechanisms: {node_type_counts['mechanism']:,}
     • Intermediate: {node_type_counts['intermediate']:,}
     • Outcomes (layer 19-20): {node_type_counts['outcome']:,}

   - Edges: {len(edges):,}
     • With A4 effect sizes: {edges_with_effects:,}
     • Validated: {edges_validated:,}

   - Layers: 21 (0-20)
   - Domains: {len(domain_hierarchy)}
   - Outcomes: {len(outcomes)}
   - Interactions: {len(interactions):,}
   - Clusters: {len(enriched_clusters)}

   - File: {output_path.name}
   - Size: {file_size_mb:.2f} MB

Frontend Usage:
   // Load full schema
   const graph = await fetch('causal_graph_v2_FULL.json').then(r => r.json());

   // Desktop: All layers
   const allNodes = graph.nodes;

   // Mobile: Compress layers, filter by SHAP
   const mobileNodes = graph.nodes.filter(n =>
     n.shap_score > 0.005 || n.is_driver || n.is_outcome
   );

   // Layer compression for smaller screens
   const layerMapping = {{
     0: 'drivers',
     '1-5': 'early',
     '6-14': 'middle',
     '15-18': 'late',
     '19-20': 'outcomes'
   }};
""")

print("="*80)
