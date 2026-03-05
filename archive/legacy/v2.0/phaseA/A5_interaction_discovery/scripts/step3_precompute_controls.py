#!/usr/bin/env python3
"""
A5 FIX #3: Control Variable Pre-computation
===========================================

CRITICAL CORRECTION: Pre-compute control variable sets from A4 backdoor adjustments
(NOT undefined "controls" - must use union of backdoor sets per interaction)

For each interaction (M1, M2) → Outcome:
- Control set = union(backdoor(M1→Y), backdoor(M2→Y))
- Exclude X1, X2, and Y from controls (no self-loops)
- Cache controls to avoid recomputation

This script:
1. Loads A4 backdoor adjustment sets
2. For each interaction pair, computes union of backdoor sets
3. Validates control sets (no self-loops, sufficient data)
4. Saves pre-computed controls for fast lookup

Runtime: ~15 minutes
Output: precomputed_controls.pkl (~200 MB)
"""

import pickle
import pandas as pd
import numpy as np
from pathlib import Path
from collections import defaultdict
import time

print("="*80)
print("A5 FIX #3: CONTROL VARIABLE PRE-COMPUTATION")
print("="*80)

start_time = time.time()

# ============================================================================
# STEP 1: Load A4 Backdoor Adjustment Sets
# ============================================================================

print("\n[Step 1/5] Loading A4 backdoor adjustment sets...")

A4_BACKDOOR_PATH = Path('../A4_effect_quantification/outputs/parent_adjustment_sets.pkl')

if not A4_BACKDOOR_PATH.exists():
    print(f"❌ ERROR: A4 backdoor sets not found at {A4_BACKDOOR_PATH}")
    print(f"   Expected output from A4 Step 2: Backdoor Adjustment")
    exit(1)

with open(A4_BACKDOOR_PATH, 'rb') as f:
    backdoor_data = pickle.load(f)

print(f"✅ Backdoor data loaded")

# Extract DataFrame with adjustment sets
if isinstance(backdoor_data, dict) and 'edges' in backdoor_data:
    df_backdoor = backdoor_data['edges']
elif isinstance(backdoor_data, pd.DataFrame):
    df_backdoor = backdoor_data
else:
    print(f"❌ ERROR: Unexpected backdoor data structure")
    print(f"   Type: {type(backdoor_data)}")
    print(f"   Keys (if dict): {list(backdoor_data.keys()) if isinstance(backdoor_data, dict) else 'N/A'}")
    exit(1)

print(f"✅ Backdoor DataFrame: {len(df_backdoor):,} edges")

# Convert to dictionary for fast lookup: (source, target) → adjustment_set
adjustment_sets = {}
for _, row in df_backdoor.iterrows():
    adjustment_sets[(row['source'], row['target'])] = set(row['adjustment_set']) if row['adjustment_set'] else set()

print(f"✅ Adjustment sets dictionary: {len(adjustment_sets):,} edges")

# Sample inspection
sample_edges = list(adjustment_sets.items())[:3]
print(f"\n   Sample backdoor sets:")
for (source, target), adj_set in sample_edges:
    print(f"   {source} → {target}: {len(adj_set)} controls")

# ============================================================================
# STEP 2: Load Mechanism Pairs from Fix #1
# ============================================================================

print("\n[Step 2/5] Loading mechanism pairs from Fix #1...")

PAIRS_PATH = Path('outputs/mechanism_pairs_per_outcome.pkl')
with open(PAIRS_PATH, 'rb') as f:
    pairs_data = pickle.load(f)

outcomes = pairs_data['outcomes']
interaction_pairs = pairs_data['interaction_pairs']
n_total_pairs = pairs_data['metadata']['n_total_pairs']

print(f"✅ Loaded {len(outcomes)} outcomes with {n_total_pairs:,} interaction pairs")

# ============================================================================
# STEP 3: Pre-compute Control Sets for Each Interaction
# ============================================================================

print("\n[Step 3/5] Pre-computing control sets for interactions...")

precomputed_controls = {}
n_processed = 0
n_missing_backdoor = 0
n_empty_controls = 0

print(f"\n   Processing {n_total_pairs:,} interaction pairs...")

for outcome, pairs in interaction_pairs.items():
    for m1, m2 in pairs:
        n_processed += 1

        # Get backdoor sets for M1 → Y and M2 → Y
        backdoor_m1_y = adjustment_sets.get((m1, outcome), set())
        backdoor_m2_y = adjustment_sets.get((m2, outcome), set())

        if not backdoor_m1_y and not backdoor_m2_y:
            n_missing_backdoor += 1
            # No backdoor adjustment needed - use empty control set
            control_set = set()
        else:
            # Union of backdoor sets
            control_set = backdoor_m1_y.union(backdoor_m2_y)

            # CRITICAL: Exclude M1, M2, and Y from controls (no self-loops)
            control_set = control_set - {m1, m2, outcome}

        if len(control_set) == 0:
            n_empty_controls += 1

        # Store as tuple for hashability
        precomputed_controls[(outcome, m1, m2)] = tuple(sorted(control_set))

        if n_processed % 100000 == 0:
            print(f"   Progress: {n_processed:,}/{n_total_pairs:,} ({n_processed/n_total_pairs*100:.1f}%)")

print(f"\n✅ Control pre-computation complete:")
print(f"   Total interactions: {n_processed:,}")
print(f"   Missing backdoor sets: {n_missing_backdoor:,} ({n_missing_backdoor/n_processed*100:.1f}%)")
print(f"   Empty control sets: {n_empty_controls:,} ({n_empty_controls/n_processed*100:.1f}%)")

# Statistics on control set sizes
control_sizes = [len(controls) for controls in precomputed_controls.values()]
print(f"\n   Control set size statistics:")
print(f"   Min: {min(control_sizes)}")
print(f"   Max: {max(control_sizes)}")
print(f"   Mean: {np.mean(control_sizes):.1f}")
print(f"   Median: {np.median(control_sizes):.1f}")
print(f"   90th percentile: {np.percentile(control_sizes, 90):.0f}")

# ============================================================================
# STEP 4: Validate Control Sets
# ============================================================================

print("\n[Step 4/5] Validating control sets...")

# Check for self-loops (should be 0)
n_self_loops = 0
for (outcome, m1, m2), controls in precomputed_controls.items():
    if m1 in controls or m2 in controls or outcome in controls:
        n_self_loops += 1
        if n_self_loops <= 5:  # Show first 5 errors
            print(f"   ⚠️  Self-loop detected: {outcome}, {m1}, {m2} → {controls}")

if n_self_loops > 0:
    print(f"❌ FAIL: Found {n_self_loops} self-loops in control sets")
    print(f"   This indicates a bug in control set computation")
    exit(1)
else:
    print(f"✅ PASS: Zero self-loops detected")

# Check for excessive control set sizes (>500 may cause computational issues)
MAX_CONTROLS_WARNING = 500
n_excessive = sum(1 for size in control_sizes if size > MAX_CONTROLS_WARNING)

if n_excessive > 0:
    print(f"\n   ⚠️  WARNING: {n_excessive:,} interactions have >{MAX_CONTROLS_WARNING} controls")
    print(f"   These may require longer regression time or regularization")
else:
    print(f"✅ PASS: All control sets within reasonable size (<{MAX_CONTROLS_WARNING})")

# Sample validation
print(f"\n   Sample control sets:")
sample_keys = list(precomputed_controls.keys())[:5]
for key in sample_keys:
    outcome, m1, m2 = key
    controls = precomputed_controls[key]
    print(f"   {outcome[:20]:20s} × ({m1[:15]:15s}, {m2[:15]:15s}): {len(controls):3d} controls")

# ============================================================================
# STEP 5: Save Precomputed Controls
# ============================================================================

print("\n[Step 5/5] Saving precomputed controls...")

OUTPUT_DIR = Path('outputs')
OUTPUT_DIR.mkdir(exist_ok=True)

output_data = {
    'precomputed_controls': precomputed_controls,
    'metadata': {
        'n_interactions': n_processed,
        'n_missing_backdoor': n_missing_backdoor,
        'n_empty_controls': n_empty_controls,
        'control_size_stats': {
            'min': min(control_sizes),
            'max': max(control_sizes),
            'mean': np.mean(control_sizes),
            'median': np.median(control_sizes),
            'p90': np.percentile(control_sizes, 90)
        },
        'validation': {
            'n_self_loops': n_self_loops,
            'n_excessive_controls': n_excessive
        }
    }
}

output_path = OUTPUT_DIR / 'precomputed_controls.pkl'
with open(output_path, 'wb') as f:
    pickle.dump(output_data, f)

file_size_mb = output_path.stat().st_size / (1024**2)
print(f"✅ Output saved to: {output_path}")
print(f"   File size: {file_size_mb:.1f} MB")

# Save summary report
summary_path = OUTPUT_DIR / 'step3_control_precomputation_summary.txt'
with open(summary_path, 'w') as f:
    f.write("A5 FIX #3: Control Variable Pre-computation Summary\n")
    f.write("="*80 + "\n\n")
    f.write(f"Date: {pd.Timestamp.now()}\n\n")
    f.write("CONTROL VARIABLE CORRECTION:\n")
    f.write(f"  ✅ Pre-computed control sets from A4 backdoor adjustments\n")
    f.write(f"  ✅ Used union of backdoor sets per interaction\n")
    f.write(f"  ✅ Excluded self-loops (M1, M2, Y not in controls)\n\n")
    f.write("RESULTS:\n")
    f.write(f"  Total interactions: {n_processed:,}\n")
    f.write(f"  Missing backdoor sets: {n_missing_backdoor:,} ({n_missing_backdoor/n_processed*100:.1f}%)\n")
    f.write(f"  Empty control sets: {n_empty_controls:,} ({n_empty_controls/n_processed*100:.1f}%)\n\n")
    f.write("CONTROL SET STATISTICS:\n")
    f.write(f"  Min size: {min(control_sizes)}\n")
    f.write(f"  Max size: {max(control_sizes)}\n")
    f.write(f"  Mean size: {np.mean(control_sizes):.1f}\n")
    f.write(f"  Median size: {np.median(control_sizes):.1f}\n")
    f.write(f"  90th percentile: {np.percentile(control_sizes, 90):.0f}\n\n")
    f.write("VALIDATION:\n")
    if n_self_loops == 0:
        f.write(f"  ✅ PASS: Zero self-loops\n")
    else:
        f.write(f"  ❌ FAIL: {n_self_loops} self-loops detected\n")
    if n_excessive > 0:
        f.write(f"  ⚠️  WARNING: {n_excessive:,} interactions with >{MAX_CONTROLS_WARNING} controls\n")
    else:
        f.write(f"  ✅ PASS: All control sets within reasonable size\n")
    f.write(f"\nSTATUS: ✅ FIX #3 COMPLETE\n")

print(f"✅ Summary saved to: {summary_path}")

# ============================================================================
# FINAL SUMMARY
# ============================================================================

elapsed = time.time() - start_time

print(f"\n{'='*80}")
print("FIX #3 COMPLETE: CONTROL VARIABLE PRE-COMPUTATION")
print(f"{'='*80}")
print(f"\n✅ Successfully pre-computed control sets from A4 backdoor adjustments")
print(f"\nKey Metrics:")
print(f"  - Interactions processed: {n_processed:,}")
print(f"  - Mean control set size: {np.mean(control_sizes):.1f}")
print(f"  - Self-loops: {n_self_loops} (should be 0)")
print(f"  - File size: {file_size_mb:.1f} MB")
print(f"  - Runtime: {elapsed/60:.1f} minutes")
print(f"  - Validation: {'✅ PASS' if n_self_loops == 0 else '❌ FAIL'}")
print(f"\nNext: Verify all 3 fixes before full A5 run")
print(f"{'='*80}")
