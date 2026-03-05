#!/usr/bin/env python3
"""
A5 FIX #1: Correct Search Space Implementation
==============================================

CRITICAL CORRECTION: V2 spec requires testing mechanism × mechanism interactions
for each outcome (NOT mechanism × outcome).

This script:
1. Loads A4 validated edges (9,759 edges)
2. Identifies outcome nodes (high in-degree, Layer 5-6 from topological sort)
3. For each outcome, identifies mechanism nodes (direct/indirect predecessors)
4. Generates mechanism × mechanism pairs per outcome
5. Estimates search space size (target: ~600K tests)

Runtime: ~10 minutes
Output: mechanism_pairs_per_outcome.pkl (~50 MB)
"""

import pickle
import pandas as pd
import numpy as np
import networkx as nx
from pathlib import Path
from collections import defaultdict
import time

print("="*80)
print("A5 FIX #1: MECHANISM IDENTIFICATION & SEARCH SPACE CORRECTION")
print("="*80)

start_time = time.time()

# ============================================================================
# STEP 1: Load A4 Validated Edges
# ============================================================================

print("\n[Step 1/5] Loading A4 validated edges...")

A4_OUTPUT = Path('../A4_effect_quantification/outputs/lasso_effect_estimates_WITH_WARNINGS.pkl')

if not A4_OUTPUT.exists():
    print(f"❌ ERROR: A4 output not found at {A4_OUTPUT}")
    exit(1)

with open(A4_OUTPUT, 'rb') as f:
    a4_data = pickle.load(f)

df_validated = pd.DataFrame(a4_data['validated_edges'])
print(f"✅ Loaded {len(df_validated):,} validated edges")

# Check required columns
required_cols = ['source', 'target', 'beta', 'ci_lower', 'ci_upper']
missing_cols = [col for col in required_cols if col not in df_validated.columns]
if missing_cols:
    print(f"❌ ERROR: Missing columns: {missing_cols}")
    exit(1)

print(f"✅ All required columns present")

# ============================================================================
# STEP 2: Build NetworkX Directed Graph
# ============================================================================

print("\n[Step 2/5] Building causal graph...")

G = nx.DiGraph()

# Add edges from validated results
for _, row in df_validated.iterrows():
    G.add_edge(row['source'], row['target'],
               beta=row['beta'],
               ci_lower=row['ci_lower'],
               ci_upper=row['ci_upper'])

print(f"✅ Graph constructed:")
print(f"   Nodes: {G.number_of_nodes():,}")
print(f"   Edges: {G.number_of_edges():,}")

# Check for cycles (DAG validation)
if not nx.is_directed_acyclic_graph(G):
    print("⚠️  WARNING: Graph contains cycles - will use approximate topological ordering")
    # Use strongly connected components to handle cycles
    scc = list(nx.strongly_connected_components(G))
    print(f"   Found {len(scc)} strongly connected components")
else:
    print("✅ Graph is a valid DAG")

# ============================================================================
# STEP 3: Identify Outcome Nodes
# ============================================================================

print("\n[Step 3/5] Identifying outcome nodes...")

# Calculate node statistics
in_degrees = dict(G.in_degree())
out_degrees = dict(G.out_degree())

# Outcome criteria (from V2 spec + your corrections):
# - High in-degree (many causal parents)
# - Low out-degree (few/no children - near top of causal hierarchy)
# - Topologically "high" (Layer 5-6 position)

# Calculate approximate topological layers
try:
    topo_order = list(nx.topological_sort(G))
    # Assign layers based on longest path from sources
    layers = {}
    for node in topo_order:
        if G.in_degree(node) == 0:
            layers[node] = 0  # Source node
        else:
            layers[node] = max(layers[pred] for pred in G.predecessors(node)) + 1
except:
    # If graph has cycles, use approximate layering
    print("   Using approximate layering (graph has cycles)")
    layers = {}
    for node in G.nodes():
        # Layer = average distance from source nodes
        try:
            distances = [nx.shortest_path_length(G, source, node)
                        for source in G.nodes() if G.out_degree(source) > 0 and G.in_degree(source) == 0]
            if distances:
                layers[node] = int(np.mean(distances))
            else:
                layers[node] = G.in_degree(node)  # Fallback to in-degree
        except:
            layers[node] = G.in_degree(node)

max_layer = max(layers.values())
print(f"✅ Layer assignment complete (max layer: {max_layer})")

# Identify outcomes using composite scoring
outcome_scores = {}
for node in G.nodes():
    # Score based on:
    # 1. High in-degree (normalized)
    # 2. Low out-degree (normalized, inverted)
    # 3. High layer position (normalized)

    in_deg_norm = in_degrees[node] / max(in_degrees.values()) if max(in_degrees.values()) > 0 else 0
    out_deg_norm = 1 - (out_degrees[node] / max(out_degrees.values())) if max(out_degrees.values()) > 0 else 1
    layer_norm = layers[node] / max_layer if max_layer > 0 else 0

    # Weighted composite score (favor in-degree and layer)
    outcome_scores[node] = 0.4 * in_deg_norm + 0.2 * out_deg_norm + 0.4 * layer_norm

# Select top 20-30 outcome nodes (conservative estimate for V2 spec)
outcome_candidates = sorted(outcome_scores.items(), key=lambda x: x[1], reverse=True)

# Apply hard thresholds:
# - Must have in-degree >= 3 (at least 3 causal parents)
# - Must be in top 50% of layers (upper causal hierarchy)
MIN_IN_DEGREE = 3
MIN_LAYER_PERCENTILE = 0.50

layer_threshold = np.percentile(list(layers.values()), MIN_LAYER_PERCENTILE * 100)

outcomes = [
    node for node, score in outcome_candidates
    if in_degrees[node] >= MIN_IN_DEGREE and layers[node] >= layer_threshold
][:30]  # Cap at 30 outcomes

print(f"\n✅ Identified {len(outcomes)} outcome nodes:")
print(f"   Min in-degree: {min(in_degrees[o] for o in outcomes)}")
print(f"   Max in-degree: {max(in_degrees[o] for o in outcomes)}")
print(f"   Mean in-degree: {np.mean([in_degrees[o] for o in outcomes]):.1f}")
print(f"   Min layer: {min(layers[o] for o in outcomes)}")
print(f"   Max layer: {max(layers[o] for o in outcomes)}")

print(f"\n   Top 10 outcomes by score:")
for i, outcome in enumerate(outcomes[:10], 1):
    print(f"   {i:2d}. {outcome[:50]:50s} (in_deg={in_degrees[outcome]:3d}, layer={layers[outcome]:2d})")

# ============================================================================
# STEP 4: Identify Mechanisms per Outcome
# ============================================================================

print("\n[Step 4/5] Identifying mechanisms for each outcome...")

mechanisms_per_outcome = {}
total_mechanisms = 0

for outcome in outcomes:
    # Mechanisms = all nodes that can reach the outcome (predecessors in graph)
    # Use BFS to find all ancestors up to depth 3 (balance between coverage and computational cost)

    mechanisms = set()

    # Get all predecessors (nodes that have paths to outcome)
    try:
        # All nodes that can reach outcome
        predecessors = nx.ancestors(G, outcome)

        # Filter to "high-centrality" mechanisms:
        # - Must have at least 2 outgoing edges (influences multiple nodes)
        # - Must have at least 1 incoming edge (not a pure source/driver)
        # - Must be in layers 2-4 (intermediate causal position)

        MIN_OUT_DEGREE = 2
        MIN_IN_DEGREE_MECH = 1
        MIN_LAYER_MECH = 2
        MAX_LAYER_MECH = max_layer - 1  # Not in top layer (that's outcomes)

        mechanisms = {
            node for node in predecessors
            if out_degrees[node] >= MIN_OUT_DEGREE
            and in_degrees[node] >= MIN_IN_DEGREE_MECH
            and MIN_LAYER_MECH <= layers[node] <= MAX_LAYER_MECH
        }

    except Exception as e:
        print(f"   ⚠️  Error finding mechanisms for {outcome}: {e}")
        mechanisms = set()

    mechanisms_per_outcome[outcome] = list(mechanisms)
    total_mechanisms += len(mechanisms)

print(f"\n✅ Mechanism identification complete:")
print(f"   Total outcomes: {len(outcomes)}")
print(f"   Total mechanisms across all outcomes: {total_mechanisms:,}")
print(f"   Mean mechanisms per outcome: {total_mechanisms / len(outcomes):.1f}")
print(f"   Min mechanisms: {min(len(m) for m in mechanisms_per_outcome.values())}")
print(f"   Max mechanisms: {max(len(m) for m in mechanisms_per_outcome.values())}")

# ============================================================================
# STEP 5: Generate Mechanism × Mechanism Pairs per Outcome
# ============================================================================

print("\n[Step 5/5] Generating mechanism × mechanism interaction pairs...")

interaction_pairs = {}
total_pairs = 0

for outcome, mechanisms in mechanisms_per_outcome.items():
    # Generate all unique pairs (M1, M2) where M1 != M2
    # Order matters for interpretation but not statistical testing
    # Use combinations (unordered) to avoid duplicate testing

    from itertools import combinations

    pairs = list(combinations(mechanisms, 2))
    interaction_pairs[outcome] = pairs
    total_pairs += len(pairs)

print(f"\n✅ Interaction pair generation complete:")
print(f"   Total interaction pairs: {total_pairs:,}")
print(f"   Mean pairs per outcome: {total_pairs / len(outcomes):.1f}")

# Verify search space size
print(f"\n{'='*80}")
print("SEARCH SPACE VALIDATION")
print(f"{'='*80}")

if 400_000 <= total_pairs <= 800_000:
    print(f"✅ PASS: Search space size ({total_pairs:,}) is within expected range 400K-800K")
elif 200_000 <= total_pairs < 400_000:
    print(f"⚠️  ACCEPTABLE: Search space size ({total_pairs:,}) is below target but reasonable")
    print(f"   Consider lowering mechanism filters to increase coverage")
elif total_pairs < 200_000:
    print(f"❌ FAIL: Search space too small ({total_pairs:,} < 200K)")
    print(f"   Need to relax mechanism identification criteria")
    exit(1)
else:
    print(f"⚠️  WARNING: Search space larger than expected ({total_pairs:,} > 800K)")
    print(f"   Consider stricter mechanism filters or runtime will exceed 5 hours")

# ============================================================================
# STEP 6: Save Output
# ============================================================================

print(f"\n[Step 6/6] Saving output...")

output_data = {
    'outcomes': outcomes,
    'mechanisms_per_outcome': mechanisms_per_outcome,
    'interaction_pairs': interaction_pairs,
    'metadata': {
        'n_outcomes': len(outcomes),
        'n_total_mechanisms': total_mechanisms,
        'n_total_pairs': total_pairs,
        'mean_mechanisms_per_outcome': total_mechanisms / len(outcomes),
        'mean_pairs_per_outcome': total_pairs / len(outcomes),
        'layer_info': {
            'max_layer': max_layer,
            'outcome_layer_range': [min(layers[o] for o in outcomes), max(layers[o] for o in outcomes)],
            'mechanism_layer_range': [MIN_LAYER_MECH, MAX_LAYER_MECH]
        },
        'filters_applied': {
            'outcome_min_in_degree': MIN_IN_DEGREE,
            'outcome_min_layer_percentile': MIN_LAYER_PERCENTILE,
            'mechanism_min_out_degree': MIN_OUT_DEGREE,
            'mechanism_min_in_degree': MIN_IN_DEGREE_MECH,
            'mechanism_layer_range': [MIN_LAYER_MECH, MAX_LAYER_MECH]
        },
        'graph_stats': {
            'n_nodes': G.number_of_nodes(),
            'n_edges': G.number_of_edges(),
            'is_dag': nx.is_directed_acyclic_graph(G)
        }
    }
}

OUTPUT_DIR = Path('outputs')
OUTPUT_DIR.mkdir(exist_ok=True)

output_path = OUTPUT_DIR / 'mechanism_pairs_per_outcome.pkl'
with open(output_path, 'wb') as f:
    pickle.dump(output_data, f)

print(f"✅ Output saved to: {output_path}")
print(f"   File size: {output_path.stat().st_size / 1024**2:.1f} MB")

# Save summary report
summary_path = OUTPUT_DIR / 'step1_mechanism_identification_summary.txt'
with open(summary_path, 'w') as f:
    f.write("A5 FIX #1: Mechanism Identification Summary\n")
    f.write("="*80 + "\n\n")
    f.write(f"Date: {pd.Timestamp.now()}\n\n")
    f.write("SEARCH SPACE CORRECTION:\n")
    f.write(f"  ✅ Corrected to mechanism × mechanism interactions (not mechanism × outcome)\n\n")
    f.write("RESULTS:\n")
    f.write(f"  Outcomes identified: {len(outcomes)}\n")
    f.write(f"  Total mechanisms: {total_mechanisms:,}\n")
    f.write(f"  Mean mechanisms/outcome: {total_mechanisms / len(outcomes):.1f}\n")
    f.write(f"  Total interaction pairs: {total_pairs:,}\n")
    f.write(f"  Mean pairs/outcome: {total_pairs / len(outcomes):.1f}\n\n")
    f.write("VALIDATION:\n")
    if 400_000 <= total_pairs <= 800_000:
        f.write(f"  ✅ PASS: Search space size in expected range (400K-800K)\n")
    elif 200_000 <= total_pairs < 400_000:
        f.write(f"  ⚠️  ACCEPTABLE: Search space slightly below target but reasonable\n")
    else:
        f.write(f"  ❌ FAIL: Search space outside expected range\n")
    f.write(f"\nSTATUS: ✅ FIX #1 COMPLETE\n")

print(f"✅ Summary saved to: {summary_path}")

# ============================================================================
# FINAL SUMMARY
# ============================================================================

elapsed = time.time() - start_time

print(f"\n{'='*80}")
print("FIX #1 COMPLETE: MECHANISM IDENTIFICATION & SEARCH SPACE CORRECTION")
print(f"{'='*80}")
print(f"\n✅ Successfully corrected search space to mechanism × mechanism interactions")
print(f"\nKey Metrics:")
print(f"  - Outcomes: {len(outcomes)}")
print(f"  - Mechanisms: {total_mechanisms:,}")
print(f"  - Interaction pairs: {total_pairs:,}")
print(f"  - Search space: {'VALIDATED ✅' if 200_000 <= total_pairs <= 800_000 else 'NEEDS REVIEW ⚠️'}")
print(f"\nRuntime: {elapsed/60:.1f} minutes")
print(f"\nNext: Implement Fix #2 (Linear GPU Regression)")
print(f"{'='*80}")
