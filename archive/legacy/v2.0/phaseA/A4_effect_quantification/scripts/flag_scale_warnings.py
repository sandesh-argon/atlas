#!/usr/bin/env python3
"""
Flag edges with extreme scale mismatches for manual review in Phase B.

Instead of attempting post-hoc standardization (which doesn't work for
fundamentally different units), we:
1. Identify edges with extreme |β| or scale mismatches
2. Flag them for manual review in Phase B
3. Provide context (variable types, scales, effect interpretation)

Runtime: ~5 minutes
"""

import pandas as pd
import numpy as np
import pickle
from pathlib import Path
from datetime import datetime

print("="*60)
print("FLAGGING SCALE WARNINGS IN A4 RESULTS")
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
# STEP 2: Load Variable Metadata (for scale context)
# ============================================================================

print("\n2. Loading variable metadata...")
a2_data_path = Path('../A1_missingness_analysis/outputs/A2_preprocessed_data.pkl')

with open(a2_data_path, 'rb') as f:
    a2_data = pickle.load(f)

imputed_data = a2_data['imputed_data']
indicators = list(imputed_data.keys())

# Compute scale statistics for each variable
scale_stats = {}
for ind_name in indicators:
    df_indicator = imputed_data[ind_name]
    values = df_indicator.values.flatten()
    valid_values = values[~np.isnan(values)]

    if len(valid_values) > 0:
        scale_stats[ind_name] = {
            'mean': np.mean(valid_values),
            'std': np.std(valid_values, ddof=1),
            'min': np.min(valid_values),
            'max': np.max(valid_values),
            'median': np.median(valid_values),
            'range': np.max(valid_values) - np.min(valid_values)
        }

print(f"   Computed scale stats for {len(scale_stats):,} indicators")

# ============================================================================
# STEP 3: Identify Extreme Effects
# ============================================================================

print("\n3. Identifying extreme effects...")

# Define thresholds
EXTREME_BETA_THRESHOLD = 10.0  # |β| > 10 is extreme
LARGE_BETA_THRESHOLD = 1.0     # |β| > 1 is large

# Classify edges
df['is_extreme'] = df['beta'].abs() > EXTREME_BETA_THRESHOLD
df['is_large'] = df['beta'].abs() > LARGE_BETA_THRESHOLD

extreme_count = df['is_extreme'].sum()
large_count = df['is_large'].sum()

print(f"   Extreme effects (|β|>{EXTREME_BETA_THRESHOLD}): {extreme_count:,} ({extreme_count/len(df)*100:.1f}%)")
print(f"   Large effects (|β|>{LARGE_BETA_THRESHOLD}): {large_count:,} ({large_count/len(df)*100:.1f}%)")

# ============================================================================
# STEP 4: Add Scale Context to Edges
# ============================================================================

print("\n4. Adding scale context to edges...")

def add_scale_context(row):
    """Add scale information for source and target variables"""
    source_stats = scale_stats.get(row['source'], {})
    target_stats = scale_stats.get(row['target'], {})

    return pd.Series({
        'source_mean': source_stats.get('mean', np.nan),
        'source_std': source_stats.get('std', np.nan),
        'source_range': source_stats.get('range', np.nan),
        'target_mean': target_stats.get('mean', np.nan),
        'target_std': target_stats.get('std', np.nan),
        'target_range': target_stats.get('range', np.nan),
        'scale_ratio': source_stats.get('std', 1) / target_stats.get('std', 1) if target_stats.get('std', 0) > 0 else np.nan
    })

scale_context = df.apply(add_scale_context, axis=1)
df = pd.concat([df, scale_context], axis=1)

print(f"   Added scale context to {len(df):,} edges")

# ============================================================================
# STEP 5: Create Warning Flags
# ============================================================================

print("\n5. Creating warning flags...")

# Flag 1: Extreme beta (|β| > 10)
df['warning_extreme_beta'] = df['is_extreme']

# Flag 2: Scale mismatch (σ_X / σ_Y > 1000 or < 0.001)
df['warning_scale_mismatch'] = (
    (df['scale_ratio'] > 1000) |
    (df['scale_ratio'] < 0.001)
)

# Flag 3: High leverage (source variable has huge range)
df['warning_high_leverage'] = df['source_range'] > 1e9

# Combined warning flag
df['needs_review'] = (
    df['warning_extreme_beta'] |
    df['warning_scale_mismatch'] |
    df['warning_high_leverage']
)

# Filter to validated edges with warnings
validated_warnings = df[
    (df['status'] == 'success') &
    (df['beta'].abs() > 0.12) &
    (df['ci_lower'] * df['ci_upper'] > 0) &
    (np.sign(df['beta']) == np.sign(df['ci_lower'])) &
    (np.sign(df['beta']) == np.sign(df['ci_upper'])) &
    (df['needs_review'])
].copy()

print(f"\n   Warning flags:")
print(f"      Extreme beta: {df['warning_extreme_beta'].sum():,}")
print(f"      Scale mismatch: {df['warning_scale_mismatch'].sum():,}")
print(f"      High leverage: {df['warning_high_leverage'].sum():,}")
print(f"      Total needing review: {df['needs_review'].sum():,}")
print(f"      Validated edges needing review: {len(validated_warnings):,}")

# ============================================================================
# STEP 6: Save Results
# ============================================================================

print("\n6. Saving flagged results...")

# Save validated edges with warnings
validated_warnings_sorted = validated_warnings.sort_values('beta', key=abs, ascending=False)
validated_warnings_sorted[
    ['source', 'target', 'beta', 'ci_lower', 'ci_upper',
     'source_std', 'target_std', 'scale_ratio',
     'warning_extreme_beta', 'warning_scale_mismatch', 'warning_high_leverage']
].to_csv('diagnostics/validated_edges_scale_warnings.csv', index=False)

print(f"   Saved {len(validated_warnings):,} flagged edges to: diagnostics/validated_edges_scale_warnings.csv")

# Update A4 data with warning flags
a4_data_with_flags = {
    'all_results': df.to_dict('records'),
    'validated_edges': df[
        (df['status'] == 'success') &
        (df['beta'].abs() > 0.12) &
        (df['ci_lower'] * df['ci_upper'] > 0) &
        (np.sign(df['beta']) == np.sign(df['ci_lower'])) &
        (np.sign(df['beta']) == np.sign(df['ci_upper']))
    ].to_dict('records'),
    'metadata': {
        **a4_data['metadata'],
        'scale_warnings_added': True,
        'warning_flags_timestamp': datetime.now().isoformat(),
        'n_extreme_beta': int(df['warning_extreme_beta'].sum()),
        'n_scale_mismatch': int(df['warning_scale_mismatch'].sum()),
        'n_high_leverage': int(df['warning_high_leverage'].sum()),
        'n_validated_warnings': len(validated_warnings)
    }
}

with open('outputs/lasso_effect_estimates_WITH_WARNINGS.pkl', 'wb') as f:
    pickle.dump(a4_data_with_flags, f)

print(f"   Saved to: outputs/lasso_effect_estimates_WITH_WARNINGS.pkl")

# Create summary report
summary = f"""A4 Scale Warning Flags Summary
{"="*60}

Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

OVERVIEW:
  Total edges: {len(df):,}
  Validated edges: {len(a4_data_with_flags['validated_edges']):,}

WARNING FLAGS:
  Extreme beta (|β|>10): {df['warning_extreme_beta'].sum():,} ({df['warning_extreme_beta'].sum()/len(df)*100:.1f}%)
  Scale mismatch: {df['warning_scale_mismatch'].sum():,} ({df['warning_scale_mismatch'].sum()/len(df)*100:.1f}%)
  High leverage: {df['warning_high_leverage'].sum():,} ({df['warning_high_leverage'].sum()/len(df)*100:.1f}%)

VALIDATED EDGES WITH WARNINGS: {len(validated_warnings):,} / 9,759 ({len(validated_warnings)/9759*100:.1f}%)

TOP 10 EXTREME EFFECTS (validated):
"""

# Add top 10 examples
top_10 = validated_warnings_sorted.head(10)
for i, row in top_10.iterrows():
    summary += f"\n  {row['source'][:30]:30s} → {row['target'][:30]:30s}"
    summary += f"\n     β = {row['beta']:,.2f}  [{row['ci_lower']:.2f}, {row['ci_upper']:.2f}]"
    summary += f"\n     σ_X = {row['source_std']:,.2f}, σ_Y = {row['target_std']:.2f}  (ratio: {row['scale_ratio']:.2e})"
    summary += f"\n     Flags: "
    flags = []
    if row['warning_extreme_beta']: flags.append("extreme")
    if row['warning_scale_mismatch']: flags.append("scale_mismatch")
    if row['warning_high_leverage']: flags.append("high_leverage")
    summary += ", ".join(flags)
    summary += "\n"

summary += f"""
INTERPRETATION:
  These edges are NOT errors, but require interpretation in context:
  - Extreme betas often involve fundamentally different scales (GDP → mortality rate)
  - High-leverage variables (population, GDP) naturally have large effects
  - Will be flagged for manual review in Phase B
  - May be excluded from simplified graphs (Levels 4-5)

NEXT STEPS:
  1. Use lasso_effect_estimates_WITH_WARNINGS.pkl for A5
  2. In Phase B: Filter extreme edges from public-facing graphs
  3. Provide "Scale Warning" labels in expert-level visualizations
  4. Document interpretation guidance in methodology

STATUS: READY FOR A5 (with warnings documented)
"""

with open('outputs/scale_warnings_summary.txt', 'w') as f:
    f.write(summary)

print(f"   Saved summary to: outputs/scale_warnings_summary.txt")

print("\n" + "="*60)
print("SCALE WARNING FLAGGING COMPLETE")
print("="*60)
print(f"✅ {len(validated_warnings):,} validated edges flagged for review")
print(f"✅ {9759 - len(validated_warnings):,} validated edges ready for A5 without warnings")
print(f"✅ All edges documented with scale context")
print("="*60)
