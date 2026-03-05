#!/usr/bin/env python3
"""
A1 Step 3: Apply Optimal Imputation Configuration
=================================================
Applies the optimal configuration (KNN @ 70% threshold) to the full filtered dataset.
Implements imputation tier weighting from V1 lessons learned.

Optimal Configuration from Step 2:
- Method: KNN (K-Nearest Neighbors)
- Missingness Threshold: 70%
- Expected Edge Retention: 76.6%

Imputation Tier Weighting (V1 Evidence):
- Tier 1 (Observed): 1.0 weight
- Tier 2 (Interpolated): 0.85 weight
- Tier 3 (MICE/KNN <40% missing): 0.70 weight
- Tier 4 (MICE/KNN >40% missing): 0.50 weight
"""

import pandas as pd
import numpy as np
from pathlib import Path
import json
from datetime import datetime
from tqdm import tqdm
import warnings
warnings.filterwarnings('ignore')

from sklearn.impute import KNNImputer
import pickle

# Paths
BASE_DIR = Path(__file__).parent
FILTERED_DATA = BASE_DIR / "filtered_data"
OUTPUT_DIR = BASE_DIR / "imputed_data"
OUTPUT_DIR.mkdir(exist_ok=True)

# Load optimal config
with open(BASE_DIR / "optimal_imputation_config.json", 'r') as f:
    OPTIMAL_CONFIG = json.load(f)

IMPUTATION_METHOD = OPTIMAL_CONFIG['method']
MISSING_THRESHOLD = OPTIMAL_CONFIG['threshold']

# Tier weights (V1 validated)
TIER_WEIGHTS = {
    'observed': 1.0,
    'interpolated': 0.85,
    'imputed_low_missing': 0.70,  # <40% missing
    'imputed_high_missing': 0.50,  # >40% missing
}


def load_all_indicators():
    """Load all filtered indicators"""
    print("Loading all filtered indicators...")

    all_files = list(FILTERED_DATA.rglob("*.csv"))
    indicators_data = {}
    metadata = {}

    for csv_file in tqdm(all_files, desc="Loading indicators"):
        try:
            df = pd.read_csv(csv_file)
            if list(df.columns) != ['Country', 'Year', 'Value']:
                continue

            # Compute missingness
            missing_rate = df['Value'].isna().mean()

            # Apply threshold filter
            if missing_rate <= MISSING_THRESHOLD:
                # Pivot to wide format (countries × years)
                pivot = df.pivot(index='Country', columns='Year', values='Value')

                indicator_name = csv_file.stem
                source = csv_file.parent.name

                indicators_data[indicator_name] = pivot
                metadata[indicator_name] = {
                    'source': source,
                    'missing_rate_pre_imputation': missing_rate,
                    'n_countries': len(pivot),
                    'n_years': len(pivot.columns),
                }
        except Exception:
            continue

    print(f"✅ Loaded {len(indicators_data):,} indicators")
    return indicators_data, metadata


def apply_knn_imputation(data, n_neighbors=5):
    """Apply KNN imputation and track imputation tiers"""
    # Create tier tracking matrix (same shape as data)
    tiers = pd.DataFrame(index=data.index, columns=data.columns, dtype=str)

    # Mark observed values as Tier 1
    tiers[data.notna()] = 'observed'

    # First apply linear interpolation (Tier 2)
    interpolated = data.interpolate(axis=1, method='linear', limit_direction='both')

    # Track which values were interpolated
    newly_filled = interpolated.notna() & data.isna()
    tiers[newly_filled] = 'interpolated'

    # Apply KNN to remaining missing values
    imputer = KNNImputer(n_neighbors=n_neighbors)
    imputed_values = imputer.fit_transform(interpolated)
    imputed_df = pd.DataFrame(imputed_values, index=data.index, columns=data.columns)

    # Compute missing rate in original data (for tier classification)
    original_missing_rate = data.isna().mean().mean()

    # Track KNN-imputed values (Tier 3 or 4 based on original missingness)
    knn_filled = imputed_df.notna() & interpolated.isna()
    if original_missing_rate < 0.40:
        tiers[knn_filled] = 'imputed_low_missing'
    else:
        tiers[knn_filled] = 'imputed_high_missing'

    return imputed_df, tiers


def apply_tier_weights(data, tiers):
    """Apply imputation tier weights to the data"""
    weighted_data = data.copy()

    for tier, weight in TIER_WEIGHTS.items():
        mask = (tiers == tier)
        weighted_data[mask] = weighted_data[mask] * weight

    return weighted_data


def main():
    print("=" * 80)
    print("A1 STEP 3: APPLY OPTIMAL IMPUTATION CONFIGURATION")
    print("=" * 80)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    print("OPTIMAL CONFIGURATION:")
    print(f"  Method: {IMPUTATION_METHOD.upper()}")
    print(f"  Missingness Threshold: {MISSING_THRESHOLD:.0%}")
    print(f"  Expected Edge Retention: {OPTIMAL_CONFIG['edge_retention']:.1%}")
    print()

    print("IMPUTATION TIER WEIGHTING:")
    for tier, weight in TIER_WEIGHTS.items():
        print(f"  {tier:25s}: {weight:.2f}")
    print()

    # Load all indicators
    indicators_data, metadata = load_all_indicators()
    print()

    # Apply imputation to each indicator
    print("Applying KNN imputation with tier tracking...")
    imputed_data = {}
    tier_data = {}
    imputation_stats = []

    for indicator_name, data in tqdm(indicators_data.items(), desc="Imputing"):
        try:
            # Apply KNN imputation
            imputed, tiers = apply_knn_imputation(data)

            # Apply tier weights
            weighted = apply_tier_weights(imputed, tiers)

            imputed_data[indicator_name] = weighted
            tier_data[indicator_name] = tiers

            # Compute statistics
            tier_counts = tiers.stack().value_counts().to_dict()
            total_values = len(tiers.stack())

            stats = {
                'indicator': indicator_name,
                'source': metadata[indicator_name]['source'],
                'n_countries': metadata[indicator_name]['n_countries'],
                'n_years': metadata[indicator_name]['n_years'],
                'missing_rate_pre': metadata[indicator_name]['missing_rate_pre_imputation'],
                'pct_observed': tier_counts.get('observed', 0) / total_values,
                'pct_interpolated': tier_counts.get('interpolated', 0) / total_values,
                'pct_imputed_low': tier_counts.get('imputed_low_missing', 0) / total_values,
                'pct_imputed_high': tier_counts.get('imputed_high_missing', 0) / total_values,
            }
            imputation_stats.append(stats)

        except Exception as e:
            print(f"⚠️  Failed to impute {indicator_name}: {e}")
            continue

    print(f"✅ Successfully imputed {len(imputed_data):,} indicators")
    print()

    # Summary statistics
    stats_df = pd.DataFrame(imputation_stats)

    print("=" * 80)
    print("IMPUTATION SUMMARY")
    print("=" * 80)
    print(f"Total indicators: {len(imputed_data):,}")
    print()

    print("TIER DISTRIBUTION (AVERAGE ACROSS ALL INDICATORS):")
    print(f"  Observed (Tier 1, weight 1.00): {stats_df['pct_observed'].mean():.1%}")
    print(f"  Interpolated (Tier 2, weight 0.85): {stats_df['pct_interpolated'].mean():.1%}")
    print(f"  KNN Low Missing (Tier 3, weight 0.70): {stats_df['pct_imputed_low'].mean():.1%}")
    print(f"  KNN High Missing (Tier 4, weight 0.50): {stats_df['pct_imputed_high'].mean():.1%}")
    print()

    print("QUALITY DISTRIBUTION:")
    print(f"  Pre-imputation missing: {stats_df['missing_rate_pre'].mean():.1%} (median: {stats_df['missing_rate_pre'].median():.1%})")
    print(f"  Countries: {stats_df['n_countries'].min():.0f} - {stats_df['n_countries'].max():.0f} (median: {stats_df['n_countries'].median():.0f})")
    print(f"  Years: {stats_df['n_years'].min():.0f} - {stats_df['n_years'].max():.0f} (median: {stats_df['n_years'].median():.0f})")
    print()

    # Save imputed data
    print("Saving imputed data...")

    # Save as pickle for efficient loading
    with open(BASE_DIR / "A1_imputed_data.pkl", 'wb') as f:
        pickle.dump({
            'imputed_data': imputed_data,
            'tier_data': tier_data,
            'metadata': metadata,
        }, f)

    # Save statistics
    stats_df.to_csv(BASE_DIR / "step3_imputation_stats.csv", index=False)

    # Save final metadata
    final_metadata = {
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'optimal_config': OPTIMAL_CONFIG,
        'tier_weights': TIER_WEIGHTS,
        'n_indicators': len(imputed_data),
        'tier_distribution': {
            'observed': float(stats_df['pct_observed'].mean()),
            'interpolated': float(stats_df['pct_interpolated'].mean()),
            'imputed_low_missing': float(stats_df['pct_imputed_low'].mean()),
            'imputed_high_missing': float(stats_df['pct_imputed_high'].mean()),
        },
        'quality': {
            'mean_missing_rate_pre': float(stats_df['missing_rate_pre'].mean()),
            'median_countries': float(stats_df['n_countries'].median()),
            'median_years': float(stats_df['n_years'].median()),
        }
    }

    with open(BASE_DIR / "A1_final_metadata.json", 'w') as f:
        json.dump(final_metadata, f, indent=2)

    print(f"✅ Imputed data saved to: A1_imputed_data.pkl")
    print(f"✅ Statistics saved to: step3_imputation_stats.csv")
    print(f"✅ Metadata saved to: A1_final_metadata.json")
    print()

    # Validation checks
    print("=" * 80)
    print("VALIDATION CHECKS")
    print("=" * 80)

    expected_range = (4000, 6000)
    if len(imputed_data) < expected_range[0]:
        print(f"⚠️  WARNING: Only {len(imputed_data):,} indicators (expected {expected_range[0]:,}-{expected_range[1]:,})")
    elif len(imputed_data) > expected_range[1]:
        print(f"⚠️  WARNING: {len(imputed_data):,} indicators (expected {expected_range[0]:,}-{expected_range[1]:,})")
    else:
        print(f"✅ Indicator count within expected range: {len(imputed_data):,}")

    # Check tier distribution is reasonable
    observed_pct = stats_df['pct_observed'].mean()
    if observed_pct < 0.50:
        print(f"⚠️  WARNING: Only {observed_pct:.1%} observed data (low quality)")
    else:
        print(f"✅ Observed data: {observed_pct:.1%} (good quality)")

    print()
    print("=" * 80)
    print("STEP 3 COMPLETE - Ready for A2 (Granger Causality)")
    print("=" * 80)


if __name__ == "__main__":
    main()
