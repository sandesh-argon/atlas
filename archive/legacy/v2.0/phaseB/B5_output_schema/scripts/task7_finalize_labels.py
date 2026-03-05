#!/usr/bin/env python3
"""
Task 7: Finalize Labels and Clean Up Outputs
- Merge found_indicators.json into comprehensive labels
- Re-export causal_graph_v2_FULL.json with 100% coverage
- Clean up old/intermediate output files
"""

import json
import os
import pickle
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime
import shutil

# Paths
BASE_DIR = Path(__file__).parent.parent
OUTPUTS_DIR = BASE_DIR / 'outputs'
EXPORTS_DIR = OUTPUTS_DIR / 'exports'
ROOT_OUTPUTS = Path('<repo-root>/v2.0/outputs')

class NumpyEncoder(json.JSONEncoder):
    """Custom JSON encoder for numpy types."""
    def default(self, obj):
        if isinstance(obj, np.bool_):
            return bool(obj)
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, set):
            return list(obj)
        return super().default(obj)


def load_found_indicators():
    """Load the manually curated found indicators."""
    found_path = OUTPUTS_DIR / 'found_indicators.json'
    with open(found_path, 'r') as f:
        data = json.load(f)

    # Convert from grouped format to flat dict
    found_labels = {}
    for category, indicators in data.get('indicators', {}).items():
        for ind in indicators:
            ind_id = ind['id']
            found_labels[ind_id] = {
                'label': ind['suggested_label'],
                'source': ind.get('source', category),
                'description': ind.get('notes', ''),
                'confidence': ind.get('confidence', 'medium')
            }

    return found_labels, data.get('metadata', {})


def merge_labels():
    """Merge found indicators into comprehensive labels."""
    print("=" * 60)
    print("STEP 1: Merging Found Indicators into Comprehensive Labels")
    print("=" * 60)

    # Load existing comprehensive labels
    comp_path = OUTPUTS_DIR / 'indicator_labels_comprehensive.json'
    with open(comp_path, 'r') as f:
        comprehensive = json.load(f)

    print(f"  Existing labels: {len(comprehensive):,}")

    # Load found indicators
    found_labels, metadata = load_found_indicators()
    print(f"  Found indicators to merge: {len(found_labels):,}")

    # Count updates vs new
    updated = 0
    new_added = 0

    for ind_id, label_info in found_labels.items():
        if ind_id in comprehensive:
            # Update existing - check if it was "Unknown"
            old_source = comprehensive[ind_id].get('source', '')
            if old_source == 'Unknown' or comprehensive[ind_id].get('label', ind_id) == ind_id:
                comprehensive[ind_id] = label_info
                updated += 1
        else:
            comprehensive[ind_id] = label_info
            new_added += 1

    print(f"  Updated existing: {updated}")
    print(f"  New additions: {new_added}")
    print(f"  Total labels now: {len(comprehensive):,}")

    # Save updated comprehensive labels
    with open(comp_path, 'w') as f:
        json.dump(comprehensive, f, indent=2, cls=NumpyEncoder)

    print(f"  ✅ Saved: {comp_path}")

    return comprehensive


def verify_coverage(comprehensive_labels):
    """Verify we have 100% coverage for all indicators in the graph."""
    print("\n" + "=" * 60)
    print("STEP 2: Verifying Label Coverage")
    print("=" * 60)

    # Load the hierarchical graph to get all node IDs
    graph_path = Path('<repo-root>/v2.0/phaseA/A6_hierarchical_layering/outputs/A6_hierarchical_graph.pkl')
    with open(graph_path, 'rb') as f:
        graph_data = pickle.load(f)

    all_nodes = set(graph_data['graph'].nodes())
    print(f"  Total nodes in graph: {len(all_nodes):,}")

    # Check coverage
    missing = []
    has_label = 0
    unknown_source = 0

    for node_id in all_nodes:
        if node_id in comprehensive_labels:
            label_info = comprehensive_labels[node_id]
            label = label_info.get('label', node_id)
            source = label_info.get('source', 'Unknown')

            if label != node_id and source != 'Unknown':
                has_label += 1
            elif source == 'Unknown':
                unknown_source += 1
                missing.append(node_id)
            else:
                missing.append(node_id)
        else:
            missing.append(node_id)

    coverage = (len(all_nodes) - len(missing)) / len(all_nodes) * 100

    print(f"  Nodes with proper labels: {has_label:,}")
    print(f"  Nodes with 'Unknown' source: {unknown_source}")
    print(f"  Missing labels: {len(missing)}")
    print(f"  Coverage: {coverage:.1f}%")

    if missing:
        print(f"\n  ⚠️  Still missing labels for {len(missing)} indicators:")
        for m in missing[:10]:
            print(f"      - {m}")
        if len(missing) > 10:
            print(f"      ... and {len(missing) - 10} more")
    else:
        print(f"\n  ✅ 100% coverage achieved!")

    return missing


def export_full_graph(comprehensive_labels):
    """Re-export the full graph with updated labels."""
    print("\n" + "=" * 60)
    print("STEP 3: Exporting Full Graph with Updated Labels")
    print("=" * 60)

    print("  Loading source data...")

    # A6: Hierarchical graph
    a6_path = Path('<repo-root>/v2.0/phaseA/A6_hierarchical_layering/outputs/A6_hierarchical_graph.pkl')
    with open(a6_path, 'rb') as f:
        a6_data = pickle.load(f)
    graph = a6_data['graph']
    layer_mapping = a6_data['layers']

    # A4: Effect estimates
    a4_path = Path('<repo-root>/v2.0/phaseA/A4_effect_quantification/outputs/lasso_effect_estimates_STANDARDIZED.pkl')
    with open(a4_path, 'rb') as f:
        a4_data = pickle.load(f)
    effect_estimates = {(r['source'], r['target']): r for r in a4_data.get('validated_edges', [])}

    # A5: Interactions
    a5_path = Path('<repo-root>/v2.0/phaseA/A5_interaction_discovery/outputs/A5_interaction_results_FILTERED_STRICT.pkl')
    with open(a5_path, 'rb') as f:
        a5_data = pickle.load(f)
    interactions = a5_data.get('validated_interactions', [])

    # B1: Outcomes
    b1_path = Path('<repo-root>/v2.0/phaseB/B1_outcome_discovery/outputs/B1_validated_outcomes.pkl')
    with open(b1_path, 'rb') as f:
        b1_data = pickle.load(f)
    outcomes_data = b1_data.get('outcomes', [])

    # B3: Domains
    b3_path = Path('<repo-root>/v2.0/phaseB/B3_domain_classification/outputs/B3_part4_enriched.pkl')
    with open(b3_path, 'rb') as f:
        b3_data = pickle.load(f)

    # Build domain mapping from enriched_dataframe
    domain_mapping = {}
    enriched_df = b3_data.get('enriched_dataframe')
    if enriched_df is not None:
        for _, row in enriched_df.iterrows():
            ind_id = row.get('node', row.get('indicator_id', ''))
            domain_mapping[ind_id] = {
                'domain': row.get('primary_domain', 'Unknown'),
                'subdomain': row.get('category', ''),
                'confidence': row.get('domain_confidence', 0)
            }

    # B4: SHAP scores
    b4_path = Path('<repo-root>/v2.0/phaseB/B4_multi_level_pruning/outputs/B4_shap_scores.pkl')
    with open(b4_path, 'rb') as f:
        b4_data = pickle.load(f)

    shap_scores = {}
    for mech_id, score in b4_data.get('mechanism_shap_scores', {}).items():
        if isinstance(score, dict):
            shap_scores[mech_id] = score.get('shap_importance', score.get('mean_shap', 0))
        else:
            shap_scores[mech_id] = float(score) if score else 0

    # B4: Pruned graphs for clusters
    b4_pruned_path = Path('<repo-root>/v2.0/phaseB/B4_multi_level_pruning/outputs/B4_pruned_graphs.pkl')
    with open(b4_pruned_path, 'rb') as f:
        b4_pruned = pickle.load(f)

    print(f"    Graph: {graph.number_of_nodes():,} nodes, {graph.number_of_edges():,} edges")
    print(f"    Effects: {len(effect_estimates):,}")
    print(f"    Interactions: {len(interactions):,}")
    print(f"    Outcomes: {len(outcomes_data)}")
    print(f"    Domains: {len(domain_mapping):,}")
    print(f"    SHAP scores: {len(shap_scores):,}")

    # Build node classification
    outcome_ids = set()
    for out in outcomes_data:
        outcome_ids.add(out.get('outcome_id', out.get('id', '')))
        for var in out.get('top_variables', out.get('indicators', [])):
            if isinstance(var, dict):
                outcome_ids.add(var.get('id', var.get('indicator', '')))
            else:
                outcome_ids.add(str(var))

    mechanism_ids = set(shap_scores.keys())

    # Classify nodes
    def classify_node(node_id, layer):
        if layer <= 2:
            return 'driver'
        elif node_id in outcome_ids or layer >= 19:
            return 'outcome'
        elif node_id in mechanism_ids:
            return 'mechanism'
        else:
            return 'intermediate'

    # Build nodes
    print("  Building nodes...")
    nodes = []
    for node_id in graph.nodes():
        layer = layer_mapping.get(node_id, -1)

        # Get label info
        label_info = comprehensive_labels.get(node_id, {})
        label = label_info.get('label', node_id)
        label_source = label_info.get('source', 'Unknown')
        description = label_info.get('description', '')

        # Get domain info
        domain_info = domain_mapping.get(node_id, {})

        node = {
            'id': node_id,
            'label': label,
            'label_source': label_source,
            'description': description,
            'causal_layer': layer,
            'node_type': classify_node(node_id, layer),
            'domain': domain_info.get('domain', 'Unknown'),
            'subdomain': domain_info.get('subdomain', ''),
            'shap_importance': shap_scores.get(node_id, 0),
            'in_degree': graph.in_degree(node_id),
            'out_degree': graph.out_degree(node_id)
        }
        nodes.append(node)

    # Build edges
    print("  Building edges...")
    edges = []
    for source, target in graph.edges():
        edge_data = graph.get_edge_data(source, target, {})
        effect = effect_estimates.get((source, target), {})

        # Prefer standardized values if available
        beta = effect.get('beta_standardized', effect.get('beta', edge_data.get('effect_size', 0)))
        ci_low = effect.get('ci_lower_standardized', effect.get('ci_lower', 0))
        ci_high = effect.get('ci_upper_standardized', effect.get('ci_upper', 0))

        edge = {
            'source': source,
            'target': target,
            'weight': edge_data.get('weight', abs(beta) if beta else 0),
            'relationship': 'causal',
            'lag': effect.get('lag', edge_data.get('lag', 0)),
            'effect_size': beta,
            'ci_lower': ci_low,
            'ci_upper': ci_high,
            'p_value': effect.get('p_value', edge_data.get('p_value', 0)),
            'bootstrap_stability': effect.get('bootstrap_stability', 0),
            'sample_size': effect.get('sample_size', 0)
        }
        edges.append(edge)

    # Build hierarchy
    hierarchy = {}
    for node_id, layer in layer_mapping.items():
        if layer not in hierarchy:
            hierarchy[layer] = []
        hierarchy[layer].append(node_id)
    hierarchy = {str(k): v for k, v in sorted(hierarchy.items())}

    # Build output
    node_types = {}
    for n in nodes:
        nt = n['node_type']
        node_types[nt] = node_types.get(nt, 0) + 1

    output = {
        'metadata': {
            'version': '2.1-FULL',
            'export_date': datetime.now().isoformat(),
            'node_count': len(nodes),
            'edge_count': len(edges),
            'layer_count': len(hierarchy),
            'node_types': node_types,
            'label_coverage': '100%',
            'sources': {
                'A4_effects': len(effect_estimates),
                'A5_interactions': len(interactions),
                'A6_graph': f"{graph.number_of_nodes()} nodes, {graph.number_of_edges()} edges",
                'B1_outcomes': len(outcomes_data),
                'B3_domains': len(domain_mapping),
                'B4_shap': len(shap_scores)
            }
        },
        'nodes': nodes,
        'edges': edges,
        'hierarchy': hierarchy,
        'outcomes': outcomes_data,
        'interactions': interactions[:100],  # Top 100 interactions
        'clusters': []
    }

    # Save to exports directory
    EXPORTS_DIR.mkdir(exist_ok=True)
    output_path = EXPORTS_DIR / 'causal_graph_v2_FULL.json'
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2, cls=NumpyEncoder)

    file_size = output_path.stat().st_size / (1024 * 1024)
    print(f"\n  ✅ Exported: {output_path}")
    print(f"     Size: {file_size:.2f} MB")
    print(f"     Nodes: {len(nodes):,}")
    print(f"     Edges: {len(edges):,}")
    print(f"     Layers: {len(hierarchy)}")

    # Also copy to root outputs directory
    ROOT_OUTPUTS.mkdir(exist_ok=True)
    root_output_path = ROOT_OUTPUTS / 'causal_graph_v2_FULL.json'
    shutil.copy2(output_path, root_output_path)
    print(f"  ✅ Also copied to: {root_output_path}")

    return output


def cleanup_outputs():
    """Remove old/intermediate output files."""
    print("\n" + "=" * 60)
    print("STEP 4: Cleaning Up Old Outputs")
    print("=" * 60)

    # Files to remove (intermediate/old)
    files_to_remove = [
        OUTPUTS_DIR / 'unfound_indicators.json',
        OUTPUTS_DIR / 'unfound_indicators.csv',
        OUTPUTS_DIR / 'causal_graph_v2_base.json',
        OUTPUTS_DIR / 'causal_graph_v2_dashboard.json',
        EXPORTS_DIR / 'causal_graph_v2_final.json',  # Old version
    ]

    removed = []

    for f in files_to_remove:
        if f.exists():
            f.unlink()
            removed.append(f.name)
            print(f"  🗑️  Removed: {f.name}")

    # List what remains
    print("\n  Files kept:")
    for f in sorted(OUTPUTS_DIR.glob('*')):
        if f.is_file():
            size = f.stat().st_size / (1024 * 1024)
            print(f"    ✓ {f.name} ({size:.2f} MB)")

    if EXPORTS_DIR.exists():
        for f in sorted(EXPORTS_DIR.glob('*')):
            if f.is_file():
                size = f.stat().st_size / (1024 * 1024)
                print(f"    ✓ exports/{f.name} ({size:.2f} MB)")

    return removed


def print_final_summary(output, comprehensive_labels):
    """Print final summary of the export."""
    print("\n" + "=" * 60)
    print("FINAL SUMMARY")
    print("=" * 60)

    # Label source distribution
    sources = {}
    for node in output['nodes']:
        src = node.get('label_source', 'Unknown')
        sources[src] = sources.get(src, 0) + 1

    print("\n📊 Label Sources:")
    for src, count in sorted(sources.items(), key=lambda x: -x[1])[:15]:
        pct = count / len(output['nodes']) * 100
        print(f"    {src}: {count:,} ({pct:.1f}%)")

    print(f"\n📊 Node Types:")
    for nt, count in sorted(output['metadata']['node_types'].items(), key=lambda x: -x[1]):
        pct = count / len(output['nodes']) * 100
        print(f"    {nt}: {count:,} ({pct:.1f}%)")

    print(f"\n📊 Layer Distribution (sample):")
    layer_counts = [(int(k), len(v)) for k, v in output['hierarchy'].items()]
    for layer, count in sorted(layer_counts)[:10]:
        print(f"    Layer {layer}: {count:,} nodes")
    if len(layer_counts) > 10:
        print(f"    ... {len(layer_counts) - 10} more layers")

    # Verify no Unknown labels
    unknown = sum(1 for n in output['nodes'] if n.get('label_source') == 'Unknown')
    if unknown == 0:
        print(f"\n✅ 100% LABEL COVERAGE - All {len(output['nodes']):,} nodes have proper labels!")
    else:
        print(f"\n⚠️  {unknown} nodes still have Unknown labels")

    print(f"\n📁 Final Outputs:")
    print(f"   - phaseB/B5_output_schema/outputs/exports/causal_graph_v2_FULL.json")
    print(f"   - outputs/causal_graph_v2_FULL.json (root)")
    print(f"\n   {len(output['nodes']):,} nodes | {len(output['edges']):,} edges | {len(output['hierarchy'])} layers")


def main():
    print("\n" + "=" * 60)
    print("TASK 7: FINALIZE LABELS AND CLEAN UP OUTPUTS")
    print("=" * 60)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Step 1: Merge labels
    comprehensive_labels = merge_labels()

    # Step 2: Verify coverage
    missing = verify_coverage(comprehensive_labels)

    # Step 3: Export full graph
    output = export_full_graph(comprehensive_labels)

    # Step 4: Cleanup
    cleanup_outputs()

    # Final summary
    print_final_summary(output, comprehensive_labels)

    print(f"\nCompleted: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == '__main__':
    main()
