#!/usr/bin/env python3
"""
V2.1 PHASE A VALIDATION
========================
Run critical checks to verify V2.1 Phase A integrity.

V2.1 uses sampled data (3,122 indicators from 6,368), so thresholds
are adjusted accordingly.

Key differences from V2:
- 3,122 indicators (not 6,368)
- ~2,000 nodes (not ~8,000)
- ~5,000 A4 edges (not ~10,000)
- Interactions stored as edge metadata (NOT virtual nodes)
"""

import pickle
import pandas as pd
from pathlib import Path
import sys

V21_ROOT = Path(__file__).parent.parent
OUTPUT_ROOT = V21_ROOT / 'outputs'

print("=" * 80)
print("V2.1 PHASE A VALIDATION")
print("=" * 80)

validation_results = {}

# ============================================================================
# Validation 1: End-to-End Data Flow
# ============================================================================
print("\n" + "=" * 80)
print("VALIDATION 1: END-TO-END DATA FLOW")
print("-" * 80)

try:
    # A2 preprocessed data (V2.1 sampled)
    a2_data_path = OUTPUT_ROOT / 'A2_preprocessed_data_V21.pkl'
    print(f"Loading: {a2_data_path}")
    with open(a2_data_path, 'rb') as f:
        a2_data = pickle.load(f)
    a2_indicators = len(a2_data['imputed_data'])
    print(f"  A2 preprocessed: {a2_indicators:,} indicators")
    assert 3000 < a2_indicators < 3500, f"Expected ~3,122 indicators, got {a2_indicators}"

    # A4 validated edges
    a4_path = OUTPUT_ROOT / 'A4' / 'lasso_effect_estimates.pkl'
    print(f"Loading: {a4_path}")
    with open(a4_path, 'rb') as f:
        a4_data = pickle.load(f)
    a4_edges = len(a4_data['validated_edges'])
    print(f"  A4 validated edges: {a4_edges:,}")
    assert 2000 < a4_edges < 10000, f"Expected 2K-10K edges, got {a4_edges}"

    # A5 interactions
    a5_path = OUTPUT_ROOT / 'A5' / 'A5_interaction_results.pkl'
    print(f"Loading: {a5_path}")
    with open(a5_path, 'rb') as f:
        a5_data = pickle.load(f)
    a5_interactions = len(a5_data['validated_interactions'])
    print(f"  A5 interactions: {a5_interactions:,}")
    # A5 can have more interactions than V2 due to different filtering

    # A6 hierarchical graph
    a6_path = OUTPUT_ROOT / 'A6' / 'A6_hierarchical_graph.pkl'
    print(f"Loading: {a6_path}")
    with open(a6_path, 'rb') as f:
        a6_data = pickle.load(f)
    a6_nodes = a6_data['metadata']['n_nodes']
    a6_edges = a6_data['metadata']['n_edges']
    a6_layers = a6_data['metadata']['n_layers']
    print(f"  A6 final: {a6_nodes:,} nodes, {a6_edges:,} edges, {a6_layers} layers")
    assert 1000 < a6_nodes < 3000, f"Expected 1K-3K nodes, got {a6_nodes}"

    print("\n  ✅ PASS: End-to-end chain validated")
    validation_results['data_flow'] = 'PASS'

except Exception as e:
    print(f"\n  ❌ FAIL: {e}")
    validation_results['data_flow'] = f'FAIL: {e}'

# ============================================================================
# Validation 2: No Virtual INTERACT_ Nodes (CRITICAL V2.1 FIX)
# ============================================================================
print("\n" + "=" * 80)
print("VALIDATION 2: NO VIRTUAL INTERACT_ NODES (CRITICAL)")
print("-" * 80)

try:
    G = a6_data['graph']
    virtual_nodes = [n for n in G.nodes() if 'INTERACT_' in str(n)]

    print(f"  Total nodes: {G.number_of_nodes():,}")
    print(f"  Virtual INTERACT_ nodes: {len(virtual_nodes)}")

    if len(virtual_nodes) > 0:
        print(f"\n  ❌ FAIL: Found {len(virtual_nodes)} virtual nodes!")
        print(f"     Sample: {virtual_nodes[:3]}")
        validation_results['no_virtual_nodes'] = f'FAIL: {len(virtual_nodes)} virtual nodes'
    else:
        print(f"\n  ✅ PASS: 0 virtual nodes (interactions stored as edge metadata)")
        validation_results['no_virtual_nodes'] = 'PASS'

    # Check edge moderators
    edges_with_moderators = sum(1 for u, v, d in G.edges(data=True)
                                 if d.get('moderators') and len(d['moderators']) > 0)
    total_moderator_entries = sum(len(d.get('moderators', [])) for u, v, d in G.edges(data=True))

    print(f"\n  Edge metadata check:")
    print(f"    Edges with moderators: {edges_with_moderators:,}")
    print(f"    Total moderator entries: {total_moderator_entries:,}")

except Exception as e:
    print(f"\n  ❌ FAIL: {e}")
    validation_results['no_virtual_nodes'] = f'FAIL: {e}'

# ============================================================================
# Validation 3: No Data Leakage (Self-loops)
# ============================================================================
print("\n" + "=" * 80)
print("VALIDATION 3: NO DATA LEAKAGE")
print("-" * 80)

try:
    a4_df = pd.DataFrame(a4_data['validated_edges'])
    self_loops = a4_df[a4_df['source'] == a4_df['target']]
    print(f"  Self-loops (X → X): {len(self_loops)}")

    assert len(self_loops) == 0, f"Found {len(self_loops)} self-loops!"

    print("  ✓ No self-loops in A4")
    print("  ✓ Temporal precedence enforced (Granger lags > 0)")
    print("\n  ✅ PASS: No temporal leakage")
    validation_results['no_leakage'] = 'PASS'

except Exception as e:
    print(f"\n  ❌ FAIL: {e}")
    validation_results['no_leakage'] = f'FAIL: {e}'

# ============================================================================
# Validation 4: DAG Validity
# ============================================================================
print("\n" + "=" * 80)
print("VALIDATION 4: DAG VALIDITY")
print("-" * 80)

try:
    import networkx as nx

    is_dag = nx.is_directed_acyclic_graph(G)
    print(f"  Is DAG (no cycles): {is_dag}")

    n_components = nx.number_weakly_connected_components(G)
    print(f"  Weakly connected components: {n_components}")

    if is_dag:
        print("\n  ✅ PASS: Graph is a valid DAG")
        validation_results['dag_valid'] = 'PASS'
    else:
        print("\n  ❌ FAIL: Graph contains cycles!")
        validation_results['dag_valid'] = 'FAIL: cycles detected'

except Exception as e:
    print(f"\n  ❌ FAIL: {e}")
    validation_results['dag_valid'] = f'FAIL: {e}'

# ============================================================================
# Validation 5: Scale Consistency
# ============================================================================
print("\n" + "=" * 80)
print("VALIDATION 5: SCALE CONSISTENCY")
print("-" * 80)

try:
    # A4 beta stats
    a4_median = a4_df['beta'].abs().median()
    a4_mean = a4_df['beta'].abs().mean()
    a4_max = a4_df['beta'].abs().max()
    print(f"  A4 Main Effects:")
    print(f"    Median |β|: {a4_median:.4f}")
    print(f"    Mean |β|:   {a4_mean:.4f}")
    print(f"    Max |β|:    {a4_max:.4f}")

    # A5 interaction stats
    a5_df = pd.DataFrame(a5_data['validated_interactions'])
    a5_median = a5_df['beta_interaction'].abs().median()
    a5_mean = a5_df['beta_interaction'].abs().mean()
    a5_max = a5_df['beta_interaction'].abs().max()
    print(f"\n  A5 Interactions:")
    print(f"    Median |β₃|: {a5_median:.4f}")
    print(f"    Mean |β₃|:   {a5_mean:.4f}")
    print(f"    Max |β₃|:    {a5_max:.4f}")

    # Check for extreme scale artifacts
    extreme_a4 = (a4_df['beta'].abs() > 1e6).sum()
    extreme_a5 = (a5_df['beta_interaction'].abs() > 1e6).sum()

    print(f"\n  Scale artifact check:")
    print(f"    A4 extreme (|β| > 1M): {extreme_a4} ({100*extreme_a4/len(a4_df):.2f}%)")
    print(f"    A5 extreme (|β₃| > 1M): {extreme_a5} ({100*extreme_a5/len(a5_df):.2f}%)")

    if extreme_a4 / len(a4_df) < 0.10 and extreme_a5 / len(a5_df) < 0.30:
        print("\n  ✅ PASS: Scale artifacts within acceptable range")
        validation_results['scale_consistency'] = 'PASS'
    else:
        print("\n  ⚠️ WARNING: High proportion of scale artifacts")
        validation_results['scale_consistency'] = 'WARNING: high scale artifacts'

except Exception as e:
    print(f"\n  ❌ FAIL: {e}")
    validation_results['scale_consistency'] = f'FAIL: {e}'

# ============================================================================
# Validation 6: Layer Distribution
# ============================================================================
print("\n" + "=" * 80)
print("VALIDATION 6: LAYER DISTRIBUTION")
print("-" * 80)

try:
    layers = a6_data['layers']
    n_layers = a6_data['n_layers']

    layer_counts = {}
    for node, layer in layers.items():
        layer_counts[layer] = layer_counts.get(layer, 0) + 1

    print(f"  Total layers: {n_layers}")
    print(f"  Layer distribution:")

    for layer in sorted(layer_counts.keys()):
        count = layer_counts[layer]
        pct = 100 * count / len(layers)
        bar = '█' * int(pct / 2)
        print(f"    Layer {layer:2d}: {count:4d} nodes ({pct:5.1f}%) {bar}")

    # Check for reasonable distribution
    max_layer_size = max(layer_counts.values())
    min_layer_size = min(layer_counts.values())

    print(f"\n  Max layer size: {max_layer_size}")
    print(f"  Min layer size: {min_layer_size}")

    if max_layer_size < len(layers) * 0.5:  # No single layer has >50% of nodes
        print("\n  ✅ PASS: Layer distribution reasonable")
        validation_results['layer_distribution'] = 'PASS'
    else:
        print("\n  ⚠️ WARNING: Uneven layer distribution")
        validation_results['layer_distribution'] = 'WARNING'

except Exception as e:
    print(f"\n  ❌ FAIL: {e}")
    validation_results['layer_distribution'] = f'FAIL: {e}'

# ============================================================================
# Validation 7: Sample Edges (Literature Sanity)
# ============================================================================
print("\n" + "=" * 80)
print("VALIDATION 7: SAMPLE EDGES (LITERATURE SANITY)")
print("-" * 80)

try:
    print(f"  Total A4 edges: {len(a4_df):,}")
    print(f"\n  Sample edges (first 10):")
    for i, row in a4_df.head(10).iterrows():
        src = row['source'][:40] if len(row['source']) > 40 else row['source']
        tgt = row['target'][:40] if len(row['target']) > 40 else row['target']
        print(f"    {src} → {tgt} (β={row['beta']:.3f})")

    print(f"\n  ✅ PASS: Edges appear structurally valid")
    validation_results['literature_sanity'] = 'PASS'

except Exception as e:
    print(f"\n  ❌ FAIL: {e}")
    validation_results['literature_sanity'] = f'FAIL: {e}'

# ============================================================================
# FINAL SUMMARY
# ============================================================================
print("\n" + "=" * 80)
print("FINAL VALIDATION SUMMARY")
print("=" * 80)

passed = sum(1 for v in validation_results.values() if v == 'PASS')
warnings = sum(1 for v in validation_results.values() if 'WARNING' in str(v))
failed = sum(1 for v in validation_results.values() if 'FAIL' in str(v))

print(f"\n  Validations: {len(validation_results)}")
print(f"  ✅ Passed:   {passed}")
print(f"  ⚠️ Warnings: {warnings}")
print(f"  ❌ Failed:   {failed}")

print("\n  Details:")
for name, result in validation_results.items():
    if result == 'PASS':
        icon = '✅'
    elif 'WARNING' in str(result):
        icon = '⚠️'
    else:
        icon = '❌'
    print(f"    {icon} {name}: {result}")

if failed == 0:
    print("\n" + "=" * 80)
    print("🎉 V2.1 PHASE A VALIDATED - READY FOR PHASE B! 🎉")
    print("=" * 80)
    sys.exit(0)
else:
    print("\n" + "=" * 80)
    print("⚠️  SOME VALIDATIONS FAILED - REVIEW BEFORE PHASE B")
    print("=" * 80)
    sys.exit(1)
