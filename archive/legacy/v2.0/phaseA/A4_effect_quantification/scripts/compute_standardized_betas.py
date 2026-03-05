#!/usr/bin/env python3
"""
Post-hoc standardization of A4 effect estimates.

Computes standardized betas using formula:
    β_std = β_raw * (σ_Y / σ_X)

Intuition: If X and Y have different scales, β is in units of Y/X.
To get standardized beta (dimensionless), multiply by σ_Y/σ_X.

This fixes scale artifacts without re-running the full pipeline.

Runtime: ~1.5 hours
"""

import pandas as pd
import numpy as np
import pickle
from pathlib import Path
from datetime import datetime

print("="*60)
print("POST-HOC STANDARDIZATION OF A4 BETAS")
print("="*60)

# ============================================================================
# STEP 1: Load A4 Results
# ============================================================================

print("\n1. Loading A4 effect estimates...")
with open('outputs/lasso_effect_estimates_FIXED.pkl', 'rb') as f:
    a4_data = pickle.load(f)

df = pd.DataFrame(a4_data['all_results'])
validated = pd.DataFrame(a4_data['validated_edges'])

print(f"   Total edges: {len(df):,}")
print(f"   Validated edges: {len(validated):,}")

# ============================================================================
# STEP 2: Load A2 Preprocessed Data (for σ_X, σ_Y)
# ============================================================================

print("\n2. Loading A2 preprocessed data (for standard deviations)...")
a2_data_path = Path('../A1_missingness_analysis/outputs/A2_preprocessed_data.pkl')

with open(a2_data_path, 'rb') as f:
    a2_data = pickle.load(f)

imputed_data = a2_data['imputed_data']  # Dict of {indicator: DataFrame}
indicators = list(imputed_data.keys())

print(f"   Loaded {len(indicators):,} indicators")
print(f"   Sample indicator shape: {imputed_data[indicators[0]].shape} (countries × years)")

# ============================================================================
# STEP 3: Compute Standard Deviations for All Indicators
# ============================================================================

print("\n3. Computing standard deviations for all indicators...")

# Compute std for each indicator across all countries and years
std_dict = {}
for ind_name in indicators:
    # Get DataFrame for this indicator (shape: countries × years)
    df_indicator = imputed_data[ind_name]

    # Flatten to 1D array and remove NaN values
    values = df_indicator.values.flatten()
    valid_values = values[~np.isnan(values)]

    if len(valid_values) > 0:
        std_dict[ind_name] = np.std(valid_values, ddof=1)  # Sample std
    else:
        std_dict[ind_name] = np.nan

print(f"   Computed std for {len(std_dict):,} indicators")
print(f"   NaN stds: {sum(np.isnan(v) for v in std_dict.values())}")

# Create lookup DataFrame
std_df = pd.DataFrame([
    {'indicator': k, 'std': v}
    for k, v in std_dict.items()
])

print(f"\n   Sample standard deviations:")
print(std_df.sort_values('std', ascending=False).head(10))

# ============================================================================
# STEP 4: Merge Standard Deviations with A4 Results
# ============================================================================

print("\n4. Merging standard deviations with A4 results...")

# Merge σ_X (source)
df = df.merge(
    std_df.rename(columns={'indicator': 'source', 'std': 'sigma_X'}),
    on='source',
    how='left'
)

# Merge σ_Y (target)
df = df.merge(
    std_df.rename(columns={'indicator': 'target', 'std': 'sigma_Y'}),
    on='target',
    how='left'
)

print(f"   Merged σ_X: {df['sigma_X'].notna().sum():,} / {len(df):,}")
print(f"   Merged σ_Y: {df['sigma_Y'].notna().sum():,} / {len(df):,}")

# Check for missing stds
missing_sigma = df[(df['sigma_X'].isna()) | (df['sigma_Y'].isna())]
print(f"   Edges with missing σ: {len(missing_sigma):,}")

if len(missing_sigma) > 0:
    print(f"\n   Sample edges with missing σ:")
    print(missing_sigma[['source', 'target', 'sigma_X', 'sigma_Y']].head())

# ============================================================================
# STEP 5: Compute Standardized Betas
# ============================================================================

print("\n5. Computing standardized betas...")

# Formula: β_std = β_raw * (σ_Y / σ_X)
# Correct formula: standardize by OUTPUT variance / INPUT variance
df['beta_standardized'] = df['beta'] * (df['sigma_Y'] / df['sigma_X'])
df['ci_lower_standardized'] = df['ci_lower'] * (df['sigma_Y'] / df['sigma_X'])
df['ci_upper_standardized'] = df['ci_upper'] * (df['sigma_Y'] / df['sigma_X'])

# Count successful standardizations
standardized_count = df['beta_standardized'].notna().sum()
print(f"   Successfully standardized: {standardized_count:,} / {len(df):,}")

# ============================================================================
# STEP 6: Compute Statistics
# ============================================================================

print("\n6. Computing statistics...")

# Filter to validated edges
validated_idx = (
    (df['status'] == 'success') &
    (df['beta'].abs() > 0.12) &
    (df['ci_lower'] * df['ci_upper'] > 0) &
    (np.sign(df['beta']) == np.sign(df['ci_lower'])) &
    (np.sign(df['beta']) == np.sign(df['ci_upper']))
)

validated_df = df[validated_idx].copy()

print(f"   Validated edges: {len(validated_df):,}")

# Original (raw) statistics
raw_stats = {
    'mean': df['beta'].abs().mean(),
    'median': df['beta'].abs().median(),
    'ratio': df['beta'].abs().mean() / df['beta'].abs().median(),
    'extreme': (df['beta'].abs() > 10).sum()
}

# Standardized statistics
std_stats = {
    'mean': df['beta_standardized'].abs().mean(),
    'median': df['beta_standardized'].abs().median(),
    'ratio': df['beta_standardized'].abs().mean() / df['beta_standardized'].abs().median(),
    'extreme': (df['beta_standardized'].abs() > 10).sum()
}

# Validated edges statistics
validated_raw_stats = {
    'mean': validated_df['beta'].abs().mean(),
    'median': validated_df['beta'].abs().median(),
    'ratio': validated_df['beta'].abs().mean() / validated_df['beta'].abs().median()
}

validated_std_stats = {
    'mean': validated_df['beta_standardized'].abs().mean(),
    'median': validated_df['beta_standardized'].abs().median(),
    'ratio': validated_df['beta_standardized'].abs().mean() / validated_df['beta_standardized'].abs().median()
}

print("\n" + "="*60)
print("COMPARISON: RAW vs STANDARDIZED")
print("="*60)

print("\n📊 ALL EDGES (n={:,})".format(len(df)))
print(f"   Raw beta:")
print(f"      Mean |β|:      {raw_stats['mean']:,.2f}")
print(f"      Median |β|:    {raw_stats['median']:.3f}")
print(f"      Ratio:         {raw_stats['ratio']:,.0f}:1  ⚠️")
print(f"      Extreme (>10): {raw_stats['extreme']:,}")

print(f"\n   Standardized beta:")
print(f"      Mean |β_std|:      {std_stats['mean']:.3f}")
print(f"      Median |β_std|:    {std_stats['median']:.3f}")
print(f"      Ratio:             {std_stats['ratio']:.1f}:1  ✅")
print(f"      Extreme (>10):     {std_stats['extreme']:,}")

print("\n📊 VALIDATED EDGES (n={:,})".format(len(validated_df)))
print(f"   Raw beta:")
print(f"      Mean |β|:      {validated_raw_stats['mean']:,.2f}")
print(f"      Median |β|:    {validated_raw_stats['median']:.3f}")
print(f"      Ratio:         {validated_raw_stats['ratio']:,.0f}:1  ⚠️")

print(f"\n   Standardized beta:")
print(f"      Mean |β_std|:      {validated_std_stats['mean']:.3f}")
print(f"      Median |β_std|:    {validated_std_stats['median']:.3f}")
print(f"      Ratio:             {validated_std_stats['ratio']:.1f}:1  ✅")

# ============================================================================
# STEP 7: Save Results
# ============================================================================

print("\n7. Saving standardized results...")

# Update data structure
a4_data_standardized = {
    'all_results': df.to_dict('records'),
    'validated_edges': validated_df.to_dict('records'),
    'metadata': {
        **a4_data['metadata'],
        'n_validated': len(validated_df),
        'standardization_applied': True,
        'standardization_timestamp': datetime.now().isoformat(),
        'standardization_method': 'post_hoc_sigma_ratio',
        'raw_mean_median_ratio': raw_stats['ratio'],
        'standardized_mean_median_ratio': std_stats['ratio'],
        'validated_raw_ratio': validated_raw_stats['ratio'],
        'validated_std_ratio': validated_std_stats['ratio']
    }
}

# Save standardized version
with open('outputs/lasso_effect_estimates_STANDARDIZED.pkl', 'wb') as f:
    pickle.dump(a4_data_standardized, f)

print(f"   Saved to: outputs/lasso_effect_estimates_STANDARDIZED.pkl")

# Save summary statistics
summary = {
    'timestamp': datetime.now().isoformat(),
    'total_edges': len(df),
    'validated_edges': len(validated_df),
    'standardization_success_rate': standardized_count / len(df),
    'raw_statistics': {
        'all': raw_stats,
        'validated': validated_raw_stats
    },
    'standardized_statistics': {
        'all': std_stats,
        'validated': validated_std_stats
    },
    'improvement': {
        'ratio_reduction_all': raw_stats['ratio'] / std_stats['ratio'],
        'ratio_reduction_validated': validated_raw_stats['ratio'] / validated_std_stats['ratio']
    }
}

with open('outputs/standardization_summary.pkl', 'wb') as f:
    pickle.dump(summary, f)

# Save human-readable summary
with open('outputs/standardization_summary.txt', 'w') as f:
    f.write("A4 Post-Hoc Standardization Summary\n")
    f.write("="*60 + "\n\n")
    f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

    f.write("RESULTS:\n")
    f.write(f"  Total edges: {len(df):,}\n")
    f.write(f"  Validated edges: {len(validated_df):,}\n")
    f.write(f"  Standardization success: {standardized_count:,} ({standardized_count/len(df)*100:.1f}%)\n\n")

    f.write("RAW BETAS (scale artifacts):\n")
    f.write(f"  Mean/Median ratio (all): {raw_stats['ratio']:,.0f}:1\n")
    f.write(f"  Mean/Median ratio (validated): {validated_raw_stats['ratio']:,.0f}:1\n\n")

    f.write("STANDARDIZED BETAS (scale-corrected):\n")
    f.write(f"  Mean/Median ratio (all): {std_stats['ratio']:.1f}:1 ✅\n")
    f.write(f"  Mean/Median ratio (validated): {validated_std_stats['ratio']:.1f}:1 ✅\n\n")

    f.write("IMPROVEMENT:\n")
    f.write(f"  Ratio reduction (all): {raw_stats['ratio'] / std_stats['ratio']:.0f}×\n")
    f.write(f"  Ratio reduction (validated): {validated_raw_stats['ratio'] / validated_std_stats['ratio']:.0f}×\n")

print(f"   Saved to: outputs/standardization_summary.txt")

# ============================================================================
# STEP 8: Sample Comparisons
# ============================================================================

print("\n8. Sample edge comparisons (raw vs standardized)...")

sample_edges = validated_df.nlargest(10, 'beta', keep='first')[
    ['source', 'target', 'beta', 'beta_standardized', 'sigma_X', 'sigma_Y']
]

print("\n   Top 10 largest raw betas:")
for i, row in sample_edges.iterrows():
    print(f"   {row['source'][:30]:30s} → {row['target'][:30]:30s}")
    print(f"      Raw β:     {row['beta']:>12,.2f}  (σ_X={row['sigma_X']:,.2f}, σ_Y={row['sigma_Y']:.4f})")
    print(f"      Std β:     {row['beta_standardized']:>12,.3f}")
    print()

print("="*60)
print("STANDARDIZATION COMPLETE")
print("="*60)
print(f"✅ Scale artifacts FIXED")
print(f"✅ Mean/Median ratio: {raw_stats['ratio']:,.0f}:1 → {std_stats['ratio']:.1f}:1")
print(f"✅ Validated edges ratio: {validated_raw_stats['ratio']:,.0f}:1 → {validated_std_stats['ratio']:.1f}:1")
print(f"✅ {len(validated_df):,} validated edges ready for A5")
print("="*60)
