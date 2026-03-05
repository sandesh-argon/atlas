#!/usr/bin/env python3
"""
A1 Validation 2: Check for Zero-Variance Indicators
===================================================
Identifies indicators with near-zero variance that would cause issues in Granger tests.
"""

import pandas as pd
import numpy as np
import pickle
from pathlib import Path
from collections import defaultdict

# Paths
BASE_DIR = Path(__file__).parent.parent
CHECKPOINT = BASE_DIR / "outputs" / "A1_imputed_data.pkl"

def load_checkpoint():
    """Load A1 imputed data checkpoint"""
    print("Loading A1 checkpoint...")
    with open(CHECKPOINT, 'rb') as f:
        data = pickle.load(f)
    print(f"✅ Loaded {len(data['imputed_data'])} indicators")
    return data

def compute_variance_stats(indicator_df):
    """Compute variance statistics for an indicator"""
    # Flatten all country-year values
    all_values = indicator_df.values.flatten()
    # Remove NaN values
    valid_values = all_values[~np.isnan(all_values)]

    if len(valid_values) == 0:
        return {
            'variance': 0.0,
            'std': 0.0,
            'n_unique': 0,
            'n_values': 0,
            'min': np.nan,
            'max': np.nan,
        }

    return {
        'variance': np.var(valid_values),
        'std': np.std(valid_values),
        'n_unique': len(np.unique(valid_values)),
        'n_values': len(valid_values),
        'min': np.min(valid_values),
        'max': np.max(valid_values),
    }

def main():
    print("=" * 80)
    print("A1 VALIDATION 2: ZERO-VARIANCE INDICATOR CHECK")
    print("=" * 80)
    print()

    # Load data
    checkpoint_data = load_checkpoint()
    imputed_data = checkpoint_data['imputed_data']
    tier_data = checkpoint_data['tier_data']
    print()

    # Compute variance for all indicators
    print("Computing variance statistics for all indicators...")
    variance_stats = {}
    for name, df in imputed_data.items():
        variance_stats[name] = compute_variance_stats(df)

    print(f"✅ Analyzed {len(variance_stats)} indicators")
    print()

    # Identify problematic indicators
    print("=" * 80)
    print("VARIANCE ANALYSIS")
    print("=" * 80)

    # Threshold 1: Near-zero variance (<0.01)
    near_zero_var = [(name, stats) for name, stats in variance_stats.items()
                     if stats['variance'] < 0.01 and stats['n_values'] > 0]

    # Threshold 2: Low unique values (<5)
    low_unique = [(name, stats) for name, stats in variance_stats.items()
                  if stats['n_unique'] < 5 and stats['n_values'] > 0]

    # Threshold 3: Constant values (variance = 0)
    constant = [(name, stats) for name, stats in variance_stats.items()
                if stats['variance'] == 0.0 and stats['n_values'] > 0]

    print(f"Near-zero variance (<0.01): {len(near_zero_var)} indicators ({len(near_zero_var)/len(variance_stats)*100:.2f}%)")
    print(f"Low unique values (<5): {len(low_unique)} indicators ({len(low_unique)/len(variance_stats)*100:.2f}%)")
    print(f"Constant (variance = 0): {len(constant)} indicators ({len(constant)/len(variance_stats)*100:.2f}%)")
    print()

    # Show examples of flagged indicators
    if near_zero_var:
        print("=" * 80)
        print("NEAR-ZERO VARIANCE INDICATORS (Examples)")
        print("=" * 80)

        for name, stats in sorted(near_zero_var, key=lambda x: x[1]['variance'])[:10]:
            # Get tier distribution for this indicator
            tier_dist = tier_data[name].stack().value_counts().to_dict()
            tier_summary = {k: v for k, v in tier_dist.items()}

            print(f"\n{name}:")
            print(f"  Variance: {stats['variance']:.6f}")
            print(f"  Std Dev: {stats['std']:.6f}")
            print(f"  Range: [{stats['min']:.3f}, {stats['max']:.3f}]")
            print(f"  Unique values: {stats['n_unique']}")
            print(f"  Total values: {stats['n_values']}")
            print(f"  Tier distribution: {tier_summary}")

        print()

    if constant:
        print("=" * 80)
        print("CONSTANT INDICATORS (Variance = 0)")
        print("=" * 80)

        for name, stats in constant[:10]:
            tier_dist = tier_data[name].stack().value_counts().to_dict()
            print(f"\n{name}:")
            print(f"  Constant value: {stats['min']:.3f}")
            print(f"  Total values: {stats['n_values']}")
            print(f"  Tier distribution: {tier_dist}")

        print()

    # Distribution of variance across all indicators
    print("=" * 80)
    print("VARIANCE DISTRIBUTION (ALL INDICATORS)")
    print("=" * 80)

    variances = [stats['variance'] for stats in variance_stats.values() if stats['n_values'] > 0]
    variances = np.array(variances)

    print(f"Mean variance: {variances.mean():.6f}")
    print(f"Median variance: {np.median(variances):.6f}")
    print(f"Std of variances: {variances.std():.6f}")
    print()

    # Percentiles
    print("Variance percentiles:")
    for p in [1, 5, 10, 25, 50, 75, 90, 95, 99]:
        print(f"  {p}th: {np.percentile(variances, p):.6f}")
    print()

    # Check relationship between tier and variance
    print("=" * 80)
    print("VARIANCE BY IMPUTATION TIER")
    print("=" * 80)

    tier_variance = defaultdict(list)
    for name, stats in variance_stats.items():
        if stats['n_values'] == 0:
            continue

        # Get dominant tier for this indicator
        tier_dist = tier_data[name].stack().value_counts()
        if len(tier_dist) > 0:
            dominant_tier = tier_dist.idxmax()
            tier_variance[dominant_tier].append(stats['variance'])

    for tier in ['observed', 'interpolated', 'imputed_low_missing', 'imputed_high_missing']:
        if tier in tier_variance:
            variances_tier = np.array(tier_variance[tier])
            print(f"{tier}:")
            print(f"  Mean variance: {variances_tier.mean():.6f}")
            print(f"  Median variance: {np.median(variances_tier):.6f}")
            print(f"  % near-zero (<0.01): {(variances_tier < 0.01).mean()*100:.2f}%")
    print()

    # Recommendation
    print("=" * 80)
    print("RECOMMENDATION")
    print("=" * 80)

    flagged_count = len(near_zero_var)
    flagged_pct = flagged_count / len(variance_stats) * 100

    if flagged_pct < 1.0:
        print(f"✅ PASS: Only {flagged_count} indicators ({flagged_pct:.2f}%) have near-zero variance")
        print("   → Acceptable loss - remove these indicators before A2")
        print(f"   → Updated count: {len(variance_stats) - flagged_count} indicators")
    elif flagged_pct < 3.0:
        print(f"⚠️ WARNING: {flagged_count} indicators ({flagged_pct:.2f}%) have near-zero variance")
        print("   → Borderline - review examples and decide:")
        print("      Option 1: Remove all flagged indicators")
        print("      Option 2: Re-impute with k=3 (fewer neighbors, more variance)")
    else:
        print(f"❌ FAIL: {flagged_count} indicators ({flagged_pct:.2f}%) have near-zero variance")
        print("   → KNN parameter likely too aggressive (k=5)")
        print("   → RECOMMEND: Re-run Step 3 with k=3 for more variance preservation")

    if constant:
        print()
        print(f"⚠️ CRITICAL: {len(constant)} indicators are perfectly constant (variance = 0)")
        print("   → These MUST be removed before A2 (will cause division-by-zero errors)")

    print()

if __name__ == "__main__":
    main()
