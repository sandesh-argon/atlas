#!/usr/bin/env python3
"""
A5 Step 3: Control Variable Pre-computation (V2.1)
==================================================

Pre-computes control variable sets from A4 parent adjustment sets.

V2.1 MODIFICATION: Uses v21_config for paths

For each interaction (M1, M2) → Outcome:
- Control set = union(parents(M1→Y), parents(M2→Y))
- Exclude M1, M2, Y from controls

Runtime: ~10 minutes
Output: precomputed_controls.pkl
"""

import pickle
import pandas as pd
import numpy as np
from pathlib import Path
import time
import sys

# V2.1 Configuration
sys.path.insert(0, str(Path(__file__).parent.parent))
from v21_config import A4_OUTPUT, A5_OUTPUT

print("="*80)
print("A5 STEP 3: CONTROL VARIABLE PRE-COMPUTATION (V2.1)")
print("="*80)

start_time = time.time()

# ============================================================================
# STEP 1: Load A4 Parent Adjustment Sets
# ============================================================================

print("\n[Step 1/5] Loading A4 parent adjustment sets...")

A4_PARENTS_PATH = A4_OUTPUT / 'parent_adjustment_sets.pkl'

if not A4_PARENTS_PATH.exists():
    print(f"ERROR: A4 parent sets not found at {A4_PARENTS_PATH}")
    exit(1)

with open(A4_PARENTS_PATH, 'rb') as f:
    parent_data = pickle.load(f)

print(f"Parent data loaded")

# Extract DataFrame
if isinstance(parent_data, dict) and 'edges' in parent_data:
    df_parents = parent_data['edges']
elif isinstance(parent_data, pd.DataFrame):
    df_parents = parent_data
else:
    print(f"ERROR: Unexpected data structure: {type(parent_data)}")
    exit(1)

print(f"Parent DataFrame: {len(df_parents):,} edges")

# Convert to dictionary for fast lookup
adjustment_sets = {}
for _, row in df_parents.iterrows():
    adj_set = row.get('adjustment_set', row.get('parent_set', []))
    if adj_set is None:
        adj_set = []
    adjustment_sets[(row['source'], row['target'])] = set(adj_set)

print(f"Adjustment sets dictionary: {len(adjustment_sets):,} edges")

# ============================================================================
# STEP 2: Load Mechanism Pairs from Step 1
# ============================================================================

print("\n[Step 2/5] Loading mechanism pairs from Step 1...")

PAIRS_PATH = A5_OUTPUT / 'mechanism_pairs_per_outcome.pkl'

if not PAIRS_PATH.exists():
    print(f"ERROR: Mechanism pairs not found at {PAIRS_PATH}")
    print(f"Run step1_identify_mechanisms.py first")
    exit(1)

with open(PAIRS_PATH, 'rb') as f:
    pairs_data = pickle.load(f)

outcomes = pairs_data['outcomes']
interaction_pairs = pairs_data['interaction_pairs']
n_total_pairs = pairs_data['metadata']['n_total_pairs']

print(f"Loaded {len(outcomes)} outcomes with {n_total_pairs:,} interaction pairs")

# ============================================================================
# STEP 3: Pre-compute Control Sets
# ============================================================================

print("\n[Step 3/5] Pre-computing control sets...")

precomputed_controls = {}
n_processed = 0
n_missing = 0
n_empty = 0

print(f"\n   Processing {n_total_pairs:,} interaction pairs...")

for outcome, pairs in interaction_pairs.items():
    for m1, m2 in pairs:
        n_processed += 1

        # Get parent sets for M1 → Y and M2 → Y
        parents_m1_y = adjustment_sets.get((m1, outcome), set())
        parents_m2_y = adjustment_sets.get((m2, outcome), set())

        if not parents_m1_y and not parents_m2_y:
            n_missing += 1
            control_set = set()
        else:
            # Union of parent sets
            control_set = parents_m1_y.union(parents_m2_y)
            # Exclude M1, M2, Y (no self-loops)
            control_set = control_set - {m1, m2, outcome}

        if len(control_set) == 0:
            n_empty += 1

        precomputed_controls[(outcome, m1, m2)] = tuple(sorted(control_set))

        if n_processed % 100000 == 0:
            print(f"   Progress: {n_processed:,}/{n_total_pairs:,} ({n_processed/n_total_pairs*100:.1f}%)")

print(f"\nControl pre-computation complete:")
print(f"   Total interactions: {n_processed:,}")
print(f"   Missing parent sets: {n_missing:,} ({n_missing/n_processed*100:.1f}%)")
print(f"   Empty control sets: {n_empty:,} ({n_empty/n_processed*100:.1f}%)")

# Statistics
control_sizes = [len(c) for c in precomputed_controls.values()]
print(f"\n   Control set size statistics:")
print(f"   Min: {min(control_sizes)}")
print(f"   Max: {max(control_sizes)}")
print(f"   Mean: {np.mean(control_sizes):.1f}")
print(f"   Median: {np.median(control_sizes):.1f}")

# ============================================================================
# STEP 4: Validate
# ============================================================================

print("\n[Step 4/5] Validating control sets...")

n_self_loops = 0
for (outcome, m1, m2), controls in precomputed_controls.items():
    if m1 in controls or m2 in controls or outcome in controls:
        n_self_loops += 1

if n_self_loops > 0:
    print(f"FAIL: Found {n_self_loops} self-loops")
    exit(1)
else:
    print(f"PASS: Zero self-loops detected")

# ============================================================================
# STEP 5: Save
# ============================================================================

print("\n[Step 5/5] Saving precomputed controls...")

output_data = {
    'precomputed_controls': precomputed_controls,
    'metadata': {
        'n_interactions': n_processed,
        'n_missing_parents': n_missing,
        'n_empty_controls': n_empty,
        'control_size_stats': {
            'min': min(control_sizes),
            'max': max(control_sizes),
            'mean': np.mean(control_sizes),
            'median': np.median(control_sizes)
        }
    }
}

output_path = A5_OUTPUT / 'precomputed_controls.pkl'
with open(output_path, 'wb') as f:
    pickle.dump(output_data, f)

print(f"Output saved to: {output_path}")
print(f"   File size: {output_path.stat().st_size / 1024**2:.1f} MB")

elapsed = time.time() - start_time
print(f"\n{'='*80}")
print("STEP 3 COMPLETE")
print(f"{'='*80}")
print(f"Runtime: {elapsed/60:.1f} minutes")
print(f"Next: Run run_interaction_discovery.py")
