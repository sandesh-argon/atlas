#!/usr/bin/env python3
"""
A5 Step 1: Mechanism Identification (V2.1)
==========================================

Identifies outcome nodes and mechanism pairs for interaction testing.

V2.1 MODIFICATION: Uses v21_config for paths

Pipeline:
1. Load A4 validated edges
2. Build causal graph
3. Identify outcome nodes (high in-degree, upper layers)
4. Identify mechanisms per outcome (predecessors)
5. Generate mechanism × mechanism pairs
6. Save for A5 main pipeline

Runtime: ~5 minutes
Output: mechanism_pairs_per_outcome.pkl
"""

import pickle
import pandas as pd
import numpy as np
import networkx as nx
from pathlib import Path
from itertools import combinations
import time
import sys

# V2.1 Configuration
sys.path.insert(0, str(Path(__file__).parent.parent))
from v21_config import A4_OUTPUT, A5_OUTPUT

print("="*80)
print("A5 STEP 1: MECHANISM IDENTIFICATION (V2.1)")
print("="*80)

start_time = time.time()

# ============================================================================
# STEP 1: Load A4 Validated Edges
# ============================================================================

print("\n[Step 1/6] Loading A4 validated edges...")

A4_PATH = A4_OUTPUT / 'lasso_effect_estimates.pkl'

if not A4_PATH.exists():
    print(f"ERROR: A4 output not found at {A4_PATH}")
    exit(1)

with open(A4_PATH, 'rb') as f:
    a4_data = pickle.load(f)

df_validated = pd.DataFrame(a4_data['validated_edges'])
print(f"Loaded {len(df_validated):,} validated edges")

# Check required columns
required_cols = ['source', 'target', 'beta', 'ci_lower', 'ci_upper']
missing_cols = [col for col in required_cols if col not in df_validated.columns]
if missing_cols:
    print(f"ERROR: Missing columns: {missing_cols}")
    print(f"Available columns: {df_validated.columns.tolist()}")
    exit(1)

print(f"All required columns present")

# ============================================================================
# STEP 2: Build NetworkX Directed Graph
# ============================================================================

print("\n[Step 2/6] Building causal graph...")

G = nx.DiGraph()

for _, row in df_validated.iterrows():
    G.add_edge(row['source'], row['target'],
               beta=row['beta'],
               ci_lower=row['ci_lower'],
               ci_upper=row['ci_upper'])

print(f"Graph constructed:")
print(f"   Nodes: {G.number_of_nodes():,}")
print(f"   Edges: {G.number_of_edges():,}")

# Check for cycles
if not nx.is_directed_acyclic_graph(G):
    print("WARNING: Graph contains cycles - using approximate layering")
else:
    print("Graph is a valid DAG")

# ============================================================================
# STEP 3: Assign Layers and Identify Outcomes
# ============================================================================

print("\n[Step 3/6] Identifying outcome nodes...")

in_degrees = dict(G.in_degree())
out_degrees = dict(G.out_degree())

# Calculate layers via topological sort
try:
    topo_order = list(nx.topological_sort(G))
    layers = {}
    for node in topo_order:
        if G.in_degree(node) == 0:
            layers[node] = 0
        else:
            layers[node] = max(layers[pred] for pred in G.predecessors(node)) + 1
except:
    print("   Using in-degree as layer proxy (graph has cycles)")
    layers = {node: G.in_degree(node) for node in G.nodes()}

max_layer = max(layers.values())
print(f"Layer assignment complete (max layer: {max_layer})")

# Composite scoring for outcome identification
outcome_scores = {}
for node in G.nodes():
    in_deg_norm = in_degrees[node] / max(in_degrees.values()) if max(in_degrees.values()) > 0 else 0
    out_deg_norm = 1 - (out_degrees[node] / max(out_degrees.values())) if max(out_degrees.values()) > 0 else 1
    layer_norm = layers[node] / max_layer if max_layer > 0 else 0
    outcome_scores[node] = 0.4 * in_deg_norm + 0.2 * out_deg_norm + 0.4 * layer_norm

# Filter outcomes
MIN_IN_DEGREE = 3
MIN_LAYER_PERCENTILE = 0.50
layer_threshold = np.percentile(list(layers.values()), MIN_LAYER_PERCENTILE * 100)

outcome_candidates = sorted(outcome_scores.items(), key=lambda x: x[1], reverse=True)
outcomes = [
    node for node, score in outcome_candidates
    if in_degrees[node] >= MIN_IN_DEGREE and layers[node] >= layer_threshold
][:30]

print(f"\nIdentified {len(outcomes)} outcome nodes:")
print(f"   Min in-degree: {min(in_degrees[o] for o in outcomes)}")
print(f"   Max in-degree: {max(in_degrees[o] for o in outcomes)}")
print(f"   Mean in-degree: {np.mean([in_degrees[o] for o in outcomes]):.1f}")

# ============================================================================
# STEP 4: Identify Mechanisms per Outcome
# ============================================================================

print("\n[Step 4/6] Identifying mechanisms for each outcome...")

mechanisms_per_outcome = {}
total_mechanisms = 0

MIN_OUT_DEGREE = 2
MIN_IN_DEGREE_MECH = 1
MIN_LAYER_MECH = 2
MAX_LAYER_MECH = max_layer - 1

for outcome in outcomes:
    try:
        predecessors = nx.ancestors(G, outcome)
        mechanisms = {
            node for node in predecessors
            if out_degrees[node] >= MIN_OUT_DEGREE
            and in_degrees[node] >= MIN_IN_DEGREE_MECH
            and MIN_LAYER_MECH <= layers[node] <= MAX_LAYER_MECH
        }
    except Exception as e:
        print(f"   WARNING: Error finding mechanisms for {outcome}: {e}")
        mechanisms = set()

    mechanisms_per_outcome[outcome] = list(mechanisms)
    total_mechanisms += len(mechanisms)

print(f"\nMechanism identification complete:")
print(f"   Total outcomes: {len(outcomes)}")
print(f"   Total mechanisms: {total_mechanisms:,}")
print(f"   Mean mechanisms per outcome: {total_mechanisms / len(outcomes):.1f}")

# ============================================================================
# STEP 5: Generate Interaction Pairs
# ============================================================================

print("\n[Step 5/6] Generating mechanism × mechanism interaction pairs...")

interaction_pairs = {}
total_pairs = 0

for outcome, mechanisms in mechanisms_per_outcome.items():
    pairs = list(combinations(mechanisms, 2))
    interaction_pairs[outcome] = pairs
    total_pairs += len(pairs)

print(f"\nInteraction pair generation complete:")
print(f"   Total interaction pairs: {total_pairs:,}")
print(f"   Mean pairs per outcome: {total_pairs / len(outcomes):.1f}")

# Validate search space
print(f"\n{'='*80}")
print("SEARCH SPACE VALIDATION")
print(f"{'='*80}")

if 400_000 <= total_pairs <= 800_000:
    print(f"PASS: Search space size ({total_pairs:,}) is within expected range 400K-800K")
elif 200_000 <= total_pairs < 400_000:
    print(f"ACCEPTABLE: Search space size ({total_pairs:,}) is below target but reasonable")
elif total_pairs < 200_000:
    print(f"WARNING: Search space small ({total_pairs:,} < 200K) - may have few interactions")
else:
    print(f"WARNING: Search space larger than expected ({total_pairs:,} > 800K)")

# ============================================================================
# STEP 6: Save Output
# ============================================================================

print(f"\n[Step 6/6] Saving output...")

OUTPUT_DIR = A5_OUTPUT
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

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
        'graph_stats': {
            'n_nodes': G.number_of_nodes(),
            'n_edges': G.number_of_edges(),
            'is_dag': nx.is_directed_acyclic_graph(G)
        }
    }
}

output_path = OUTPUT_DIR / 'mechanism_pairs_per_outcome.pkl'
with open(output_path, 'wb') as f:
    pickle.dump(output_data, f)

print(f"Output saved to: {output_path}")
print(f"   File size: {output_path.stat().st_size / 1024**2:.1f} MB")

elapsed = time.time() - start_time
print(f"\n{'='*80}")
print("STEP 1 COMPLETE")
print(f"{'='*80}")
print(f"Runtime: {elapsed/60:.1f} minutes")
print(f"Next: Run step3_precompute_controls.py")
