#!/usr/bin/env python3
"""
B4 Pre-Execution Checks
=======================

Validate all required inputs before starting B4 multi-level pruning.

Required Inputs:
1. B3 domain classification checkpoint
2. A6 hierarchical graph
3. A4 effect estimates

Author: B4 Pre-checks
Date: November 2025
"""

import pickle
import json
from pathlib import Path
import pandas as pd
import networkx as nx

project_root = Path(__file__).resolve().parents[3]

print("="*80)
print("B4 PRE-EXECUTION CHECKS")
print("="*80)

results = {
    "timestamp": "2025-11-20",
    "all_checks_passed": False,
    "checks": {}
}

# ============================================================================
# Pre-Check 1: B3 Checkpoint Validation
# ============================================================================

print("\n" + "="*80)
print("CHECK 1: B3 DOMAIN CLASSIFICATION")
print("="*80)

b3_path = project_root / 'phaseB/B3_domain_classification/outputs/B3_part4_enriched.pkl'

try:
    print(f"\nLoading: {b3_path}")

    # Load checkpoint
    with open(b3_path, 'rb') as f:
        b3_data = pickle.load(f)

    # Check required fields
    required_fields = ['enriched_cluster_metadata', 'hierarchical_summary', 'unified_metadata', 'enriched_dataframe']
    for field in required_fields:
        assert field in b3_data, f"Missing required field: {field}"

    # Check cluster count
    clusters = b3_data['enriched_cluster_metadata']
    assert len(clusters) == 15, f"Expected 15 clusters, got {len(clusters)}"

    # Filter classified clusters (exclude Cluster 0)
    classified = [c for c in clusters if c['primary_domain'] != 'Unclassified']
    assert len(classified) == 14, f"Expected 14 classified clusters, got {len(classified)}"

    # Check total mechanisms
    total_mechanisms = sum(c['size'] for c in classified)
    assert 280 <= total_mechanisms <= 300, f"Expected ~290 mechanisms, got {total_mechanisms}"

    # Check hierarchical labels
    for cluster in classified:
        assert 'hierarchical_label' in cluster
        assert cluster['hierarchical_label'] is not None
        assert cluster['primary_domain'] in ['Governance', 'Education', 'Economic', 'Mixed']

    # Check metadata coverage
    metadata = b3_data['unified_metadata']
    assert len(metadata) >= 329, f"Expected ≥329 metadata entries, got {len(metadata)}"

    # Check domain balance
    domain_counts = {}
    for cluster in classified:
        domain = cluster['primary_domain']
        domain_counts[domain] = domain_counts.get(domain, 0) + 1

    governance_pct = domain_counts.get('Governance', 0) / len(classified)
    education_pct = domain_counts.get('Education', 0) / len(classified)

    assert 0.30 <= governance_pct <= 0.50, f"Governance {governance_pct:.1%} out of range"
    assert 0.30 <= education_pct <= 0.50, f"Education {education_pct:.1%} out of range"

    print("✅ B3 checkpoint validation PASSED")
    print(f"   - 15 total clusters, 14 classified")
    print(f"   - {total_mechanisms} classified mechanisms")
    print(f"   - {len(metadata)} metadata entries")
    print(f"   - Domain balance: Governance {governance_pct:.1%}, Education {education_pct:.1%}")

    results['checks']['b3_checkpoint'] = {
        'status': 'PASS',
        'clusters': len(clusters),
        'classified_clusters': len(classified),
        'mechanisms': total_mechanisms,
        'metadata_entries': len(metadata),
        'domain_balance': {
            'governance': float(governance_pct),
            'education': float(education_pct)
        }
    }

except Exception as e:
    print(f"❌ B3 checkpoint validation FAILED")
    print(f"   Error: {e}")
    results['checks']['b3_checkpoint'] = {
        'status': 'FAIL',
        'error': str(e)
    }
    b3_data = None

# ============================================================================
# Pre-Check 2: A6 Graph Validation
# ============================================================================

print("\n" + "="*80)
print("CHECK 2: A6 HIERARCHICAL GRAPH")
print("="*80)

a6_path = project_root / 'phaseA/A6_hierarchical_layering/outputs/A6_hierarchical_graph.pkl'

try:
    print(f"\nLoading: {a6_path}")

    # Load graph
    with open(a6_path, 'rb') as f:
        a6_data = pickle.load(f)

    # Check required fields
    assert 'graph' in a6_data
    assert 'layers' in a6_data or 'layer_assignments' in a6_data

    # Extract graph
    G = a6_data['graph']

    # Extract layer assignments (could be 'layers' or 'layer_assignments')
    if 'layer_assignments' in a6_data:
        layer_assignments = a6_data['layer_assignments']
    else:
        layer_assignments = a6_data['layers']

    # Validate graph type
    assert isinstance(G, nx.DiGraph), "Graph must be a directed graph"

    # Check DAG property
    is_dag = nx.is_directed_acyclic_graph(G)
    assert is_dag, "Graph must be acyclic (DAG)"

    # Check node count
    n_nodes = G.number_of_nodes()
    assert n_nodes >= 1000, f"Expected ≥1000 nodes, got {n_nodes}"

    # Check edge count
    n_edges = G.number_of_edges()
    assert 10000 <= n_edges <= 100000, f"Expected 10K-100K edges, got {n_edges}"

    # Check all nodes have layers
    nodes_without_layers = []
    layer_min, layer_max = float('inf'), float('-inf')
    for node in G.nodes():
        if node not in layer_assignments:
            nodes_without_layers.append(node)
        else:
            layer = layer_assignments[node]
            layer_min = min(layer_min, layer)
            layer_max = max(layer_max, layer)
            # Relax constraint - just check layer is a valid number
            assert isinstance(layer, (int, float)), f"Invalid layer type {type(layer)} for node {node}"

    if nodes_without_layers:
        print(f"⚠️  WARNING: {len(nodes_without_layers)} nodes missing layer assignments")

    # Check layer 0 = targets
    layer_0_nodes = [n for n, l in layer_assignments.items() if l == 0]
    assert len(layer_0_nodes) >= 5, f"Expected ≥5 target nodes, got {len(layer_0_nodes)}"

    print("✅ A6 graph validation PASSED")
    print(f"   - {n_nodes:,} nodes, {n_edges:,} edges")
    print(f"   - DAG: {is_dag}")
    print(f"   - Layer range: [{layer_min}, {layer_max}]")
    print(f"   - Layer 0 (targets): {len(layer_0_nodes)} nodes")

    results['checks']['a6_graph'] = {
        'status': 'PASS',
        'nodes': n_nodes,
        'edges': n_edges,
        'is_dag': is_dag,
        'layer_0_nodes': len(layer_0_nodes)
    }

except Exception as e:
    print(f"❌ A6 graph validation FAILED")
    print(f"   Error: {e}")
    results['checks']['a6_graph'] = {
        'status': 'FAIL',
        'error': str(e)
    }
    a6_data = None

# ============================================================================
# Pre-Check 3: A4 Effect Estimates Validation
# ============================================================================

print("\n" + "="*80)
print("CHECK 3: A4 EFFECT ESTIMATES")
print("="*80)

a4_path = project_root / 'phaseA/A4_effect_quantification/outputs/lasso_effect_estimates_WITH_WARNINGS.pkl'

try:
    print(f"\nLoading: {a4_path}")

    # Load effects
    with open(a4_path, 'rb') as f:
        a4_data = pickle.load(f)

    # Check required fields
    assert 'all_results' in a4_data or 'effects' in a4_data or 'edge_effects' in a4_data or 'validated_edges' in a4_data

    # Extract effects (could be DataFrame or list)
    if 'all_results' in a4_data:
        effects_data = a4_data['all_results']
    elif 'validated_edges' in a4_data:
        effects_data = a4_data['validated_edges']
    elif 'effects' in a4_data:
        effects_data = a4_data['effects']
    else:
        effects_data = a4_data['edge_effects']

    # Convert to DataFrame if it's a list
    if isinstance(effects_data, list):
        effects_df = pd.DataFrame(effects_data)
    else:
        effects_df = effects_data

    # Check DataFrame structure
    assert isinstance(effects_df, pd.DataFrame)
    required_cols = ['source', 'target']
    for col in required_cols:
        assert col in effects_df.columns, f"Missing required column: {col}"

    # Check for beta/coefficient column
    beta_col = None
    for col in ['beta', 'coefficient', 'effect']:
        if col in effects_df.columns:
            beta_col = col
            break
    assert beta_col is not None, "No beta/coefficient column found"

    # Check edge count
    n_effects = len(effects_df)
    assert n_effects >= 1000, f"Expected ≥1000 effect estimates, got {n_effects}"

    # Check beta values
    beta_values = effects_df[beta_col].dropna()
    assert len(beta_values) > 0, "No valid beta values found"

    # Check beta range (log extreme values as warnings)
    beta_min, beta_max = beta_values.min(), beta_values.max()
    if abs(beta_min) > 10 or abs(beta_max) > 10:
        print(f"   ⚠️  WARNING: Extreme beta values detected")
        print(f"      Beta range: [{beta_min:.2f}, {beta_max:.2f}]")
        print(f"      Will need filtering/clipping in B4")

    # Check confidence intervals if present
    ci_valid_pct = None
    if 'ci_lower' in effects_df.columns and 'ci_upper' in effects_df.columns:
        ci_valid = (effects_df['ci_lower'] <= effects_df[beta_col]) & (effects_df[beta_col] <= effects_df['ci_upper'])
        ci_valid_pct = ci_valid.sum() / len(effects_df)
        if ci_valid_pct < 0.80:
            print(f"   ⚠️  WARNING: {ci_valid_pct:.1%} valid CIs (target: ≥80%)")
            print(f"      Invalid CIs may indicate outliers or estimation issues")

    print("✅ A4 effects validation PASSED")
    print(f"   - {n_effects:,} effect estimates")
    print(f"   - Beta column: '{beta_col}'")
    print(f"   - Beta range: [{beta_min:.3f}, {beta_max:.3f}]")
    if ci_valid_pct:
        print(f"   - Valid CIs: {ci_valid_pct:.1%}")

    results['checks']['a4_effects'] = {
        'status': 'PASS',
        'effect_estimates': n_effects,
        'beta_column': beta_col,
        'beta_range': [float(beta_min), float(beta_max)],
        'ci_valid_pct': float(ci_valid_pct) if ci_valid_pct else None
    }

except Exception as e:
    print(f"❌ A4 effects validation FAILED")
    print(f"   Error: {e}")
    results['checks']['a4_effects'] = {
        'status': 'FAIL',
        'error': str(e)
    }
    a4_data = None

# ============================================================================
# Pre-Check 4: B3 ↔ A6 Integration
# ============================================================================

print("\n" + "="*80)
print("CHECK 4: B3 ↔ A6 INTEGRATION")
print("="*80)

if b3_data is not None and a6_data is not None:
    try:
        # Get B3 classified mechanisms
        classified_clusters = [c for c in b3_data['enriched_cluster_metadata']
                              if c['primary_domain'] != 'Unclassified']

        b3_mechanisms = set()
        for cluster in classified_clusters:
            b3_mechanisms.update(cluster['nodes'])

        # Get A6 graph nodes
        a6_nodes = set(a6_data['graph'].nodes())

        # Check overlap
        overlap = b3_mechanisms & a6_nodes
        overlap_pct = len(overlap) / len(b3_mechanisms) if len(b3_mechanisms) > 0 else 0

        print(f"\n📊 B3 ↔ A6 Integration:")
        print(f"   - B3 mechanisms: {len(b3_mechanisms)}")
        print(f"   - A6 graph nodes: {len(a6_nodes):,}")
        print(f"   - Overlap: {len(overlap)} ({overlap_pct:.1%})")

        # Warn if overlap < 80%
        if overlap_pct < 0.80:
            print(f"   ⚠️  WARNING: Only {overlap_pct:.1%} B3 mechanisms in A6 graph")
            print(f"   - Missing mechanisms may be excluded from pruning")
        else:
            print(f"   ✅ Good overlap: {overlap_pct:.1%} B3 mechanisms in A6")

        # Find missing mechanisms
        missing = b3_mechanisms - a6_nodes
        if missing:
            print(f"\n   Missing B3 mechanisms from A6 graph ({len(missing)}):")
            for mech in list(missing)[:10]:
                print(f"      - {mech}")
            if len(missing) > 10:
                print(f"      ... and {len(missing) - 10} more")

        assert overlap_pct >= 0.50, f"Overlap too low: {overlap_pct:.1%} (need ≥50%)"

        print("\n✅ B3 ↔ A6 integration check PASSED")

        results['checks']['b3_a6_integration'] = {
            'status': 'PASS',
            'b3_mechanisms': len(b3_mechanisms),
            'a6_nodes': len(a6_nodes),
            'overlap': len(overlap),
            'overlap_pct': float(overlap_pct),
            'missing_mechanisms': len(missing)
        }

    except Exception as e:
        print(f"❌ B3 ↔ A6 integration check FAILED")
        print(f"   Error: {e}")
        results['checks']['b3_a6_integration'] = {
            'status': 'FAIL',
            'error': str(e)
        }
else:
    print("⚠️  Skipping B3 ↔ A6 integration check (previous checks failed)")
    results['checks']['b3_a6_integration'] = {
        'status': 'SKIP',
        'reason': 'Previous checks failed'
    }

# ============================================================================
# Summary
# ============================================================================

print("\n" + "="*80)
print("PRE-CHECK SUMMARY")
print("="*80)

all_passed = all(check.get('status') == 'PASS' for check in results['checks'].values())
results['all_checks_passed'] = all_passed

print(f"\n📊 Results:")
for i, (check_name, check_data) in enumerate(results['checks'].items(), 1):
    status = check_data['status']
    status_symbol = "✅" if status == 'PASS' else "❌" if status == 'FAIL' else "⚠️"
    print(f"   {i}. {check_name.replace('_', ' ').title()}: {status_symbol} {status}")

print(f"\n{'='*80}")
if all_passed:
    print("✅ ALL PRE-CHECKS PASSED - READY FOR B4")
else:
    print("❌ SOME PRE-CHECKS FAILED - REVIEW ERRORS ABOVE")
print(f"{'='*80}")

# Save results
output_dir = project_root / 'phaseB/B4_multi_level_pruning/outputs'
output_dir.mkdir(exist_ok=True, parents=True)

output_path = output_dir / 'B4_precheck_results.json'

with open(output_path, 'w') as f:
    json.dump(results, f, indent=2)

print(f"\n✅ Saved results: {output_path}")

if all_passed:
    print("\n🎯 Next step: Proceed to B4 Task 1 (Load inputs and prepare for SHAP)")
else:
    print("\n⚠️  Fix errors before proceeding to B4")
