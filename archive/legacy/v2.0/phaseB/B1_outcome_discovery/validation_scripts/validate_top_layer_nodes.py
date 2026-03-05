#!/usr/bin/env python3
"""
Pre-B1 Sanity Checks
====================

Validates that A6 top-layer nodes are suitable for factor analysis:
1. Top-layer node quality (terminal outcomes with high in-degree, low out-degree)
2. Virtual node count (filter INTERACT_* nodes)
3. Missing data rates (ensure well-measured indicators)

Author: Phase B1 Validation
Date: November 2025
"""

import pickle
import sys
from pathlib import Path
import pandas as pd
import numpy as np

# Add project root to path
project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

print("=" * 80)
print("PRE-B1 SANITY CHECKS")
print("=" * 80)

# ============================================================================
# CHECK 1: Top-Layer Node Quality
# ============================================================================

print("\n[CHECK 1] Loading A6 hierarchical graph...")
a6_path = project_root / "phaseA/A6_hierarchical_layering/outputs/A6_hierarchical_graph.pkl"

with open(a6_path, 'rb') as f:
    a6_data = pickle.load(f)

G = a6_data['graph']
layers = a6_data['layers']
metadata = a6_data['metadata']

print(f"✅ Loaded graph: {metadata['n_nodes']} nodes, {metadata['n_edges']} edges")

# Get min/max layers from layers dict
min_layer = min(layers.values())
max_layer = max(layers.values())
print(f"   Layers: {metadata['n_layers']} (min={min_layer}, max={max_layer})")

# Get top 2 layers
top_layer_nodes = [n for n, layer in layers.items() if layer >= max_layer - 1]

print(f"\n[CHECK 1] Top 2 layers (layers {max_layer-1} to {max_layer}):")
print(f"   Total nodes: {len(top_layer_nodes)}")

# Inspect sample nodes
print(f"\n   Sample nodes (first 15):")
for i, node in enumerate(top_layer_nodes[:15]):
    in_deg = G.in_degree(node)
    out_deg = G.out_degree(node)
    layer = layers[node]
    print(f"   {i+1:2d}. {node[:60]:60s} | L={layer:2d} | in={in_deg:3d}, out={out_deg:2d}")

# Check degree distribution
in_degrees = [G.in_degree(n) for n in top_layer_nodes]
out_degrees = [G.out_degree(n) for n in top_layer_nodes]

print(f"\n   Degree statistics:")
print(f"   In-degree:  mean={np.mean(in_degrees):.1f}, median={np.median(in_degrees):.0f}, max={max(in_degrees)}")
print(f"   Out-degree: mean={np.mean(out_degrees):.1f}, median={np.median(out_degrees):.0f}, max={max(out_degrees)}")

# Expected: High in-degree (many causes), low out-degree (terminal outcomes)
if np.median(out_degrees) > 5:
    print(f"   ⚠️  WARNING: Median out-degree={np.median(out_degrees):.0f} (expected <5 for terminal outcomes)")
else:
    print(f"   ✅ PASS: Low out-degree confirms terminal outcomes")

# ============================================================================
# CHECK 2: Virtual Node Count
# ============================================================================

print(f"\n[CHECK 2] Filtering virtual interaction nodes...")

virtual_top = [n for n in top_layer_nodes if n.startswith('INTERACT_')]
real_top = [n for n in top_layer_nodes if not n.startswith('INTERACT_')]

print(f"   Virtual nodes (INTERACT_*): {len(virtual_top)}")
print(f"   Real nodes: {len(real_top)}")

if len(virtual_top) > 0:
    print(f"\n   Sample virtual nodes:")
    for i, node in enumerate(virtual_top[:5]):
        print(f"   {i+1}. {node}")

if len(virtual_top) > 10:
    print(f"   ⚠️  WARNING: {len(virtual_top)} virtual nodes in top layers (expected <5)")
    print(f"      → This may indicate issue with A6 layering algorithm")
else:
    print(f"   ✅ PASS: Virtual node count reasonable")

print(f"\n   Real nodes to use for factor analysis: {len(real_top)}")

if len(real_top) < 20:
    print(f"   ⚠️  WARNING: Only {len(real_top)} real nodes (expected 25-35)")
    print(f"      → May have insufficient variables for robust factor analysis")
elif len(real_top) > 40:
    print(f"   ⚠️  WARNING: {len(real_top)} real nodes (expected 25-35)")
    print(f"      → May extract too many factors")
else:
    print(f"   ✅ PASS: Real node count in expected range (25-35)")

# ============================================================================
# CHECK 3: Missing Data Rates
# ============================================================================

print(f"\n[CHECK 3] Checking missing data rates in top-layer nodes...")
a1_path = project_root / "phaseA/A1_missingness_analysis/outputs/A2_preprocessed_data.pkl"

with open(a1_path, 'rb') as f:
    a1_data = pickle.load(f)

# A1 imputed_data is a dict: {indicator_name: Series}
imputed_data = a1_data['imputed_data']

print(f"✅ Loaded A1 data: {len(imputed_data)} indicators")

# Check which real_top nodes are in imputed_data
real_top_in_data = [n for n in real_top if n in imputed_data]
real_top_missing = [n for n in real_top if n not in imputed_data]

print(f"   Real top-layer nodes in A1 data: {len(real_top_in_data)}/{len(real_top)}")

if len(real_top_missing) > 0:
    print(f"   ⚠️  WARNING: {len(real_top_missing)} real nodes NOT in A1 data:")
    for node in real_top_missing[:10]:
        print(f"      - {node}")

# Calculate missing rates for real top-layer nodes
# Note: imputed_data values are DataFrames (countries x years)
missing_rates = {}
for node in real_top_in_data:
    df = imputed_data[node]
    # Calculate missing rate across all cells (countries × years)
    if isinstance(df, pd.DataFrame):
        missing_rate = df.isna().sum().sum() / (df.shape[0] * df.shape[1])
    else:
        # If it's a Series somehow
        missing_rate = df.isna().mean()
    missing_rates[node] = missing_rate

if len(missing_rates) > 0:
    missing_series = pd.Series(missing_rates)

    print(f"\n   Missing rate statistics (after A1 imputation):")
    print(f"   Mean:   {missing_series.mean():.1%}")
    print(f"   Median: {missing_series.median():.1%}")
    print(f"   Min:    {missing_series.min():.1%}")
    print(f"   Max:    {missing_series.max():.1%}")
    print(f"   Q75:    {missing_series.quantile(0.75):.1%}")

    # Nodes with >30% missing
    high_missing = missing_series[missing_series > 0.30]
    if len(high_missing) > 0:
        print(f"\n   ⚠️  WARNING: {len(high_missing)} nodes with >30% missing:")
        for node, rate in high_missing.head(10).items():
            print(f"      - {node[:60]:60s}: {rate:.1%}")

    # Overall assessment
    if missing_series.mean() > 0.30:
        print(f"\n   ❌ FAIL: Mean missing rate {missing_series.mean():.1%} > 30%")
        print(f"      → Top-layer outcomes should be well-measured indicators")
        print(f"      → Consider investigating A6 layering algorithm")
    elif missing_series.mean() > 0.20:
        print(f"\n   ⚠️  WARNING: Mean missing rate {missing_series.mean():.1%} > 20%")
        print(f"      → Factor analysis may be less reliable")
    else:
        print(f"\n   ✅ PASS: Mean missing rate {missing_series.mean():.1%} < 20%")

# ============================================================================
# SUMMARY
# ============================================================================

print("\n" + "=" * 80)
print("SUMMARY: PRE-B1 SANITY CHECKS")
print("=" * 80)

checks_passed = 0
checks_total = 3

# Check 1: Out-degree
if np.median(out_degrees) <= 5:
    print("✅ CHECK 1 PASS: Top-layer nodes are terminal outcomes")
    checks_passed += 1
else:
    print(f"⚠️  CHECK 1 WARN: Median out-degree={np.median(out_degrees):.0f} (expected ≤5)")

# Check 2: Virtual node count
if len(virtual_top) <= 10 and 20 <= len(real_top) <= 40:
    print("✅ CHECK 2 PASS: Virtual nodes filtered, real node count reasonable")
    checks_passed += 1
else:
    print(f"⚠️  CHECK 2 WARN: Virtual={len(virtual_top)}, Real={len(real_top)}")

# Check 3: Missing rates
if len(missing_rates) > 0 and missing_series.mean() <= 0.30:
    print("✅ CHECK 3 PASS: Missing rates acceptable for factor analysis")
    checks_passed += 1
else:
    print(f"❌ CHECK 3 FAIL: Missing rates too high or nodes not in A1 data")

print(f"\n{'='*80}")
print(f"RESULT: {checks_passed}/{checks_total} checks passed")

if checks_passed == checks_total:
    print("✅ ALL CHECKS PASSED - READY FOR B1 FACTOR ANALYSIS")
    sys.exit(0)
elif checks_passed >= 2:
    print("⚠️  PROCEED WITH CAUTION - Review warnings above")
    sys.exit(0)
else:
    print("❌ MULTIPLE FAILURES - DO NOT PROCEED - Investigate A6 output")
    sys.exit(1)
