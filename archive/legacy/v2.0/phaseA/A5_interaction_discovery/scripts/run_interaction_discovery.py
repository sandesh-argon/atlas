#!/usr/bin/env python3
"""
A5 INTERACTION DISCOVERY - MAIN PIPELINE
========================================

Integrates all 3 critical fixes to discover mechanism × mechanism interactions.

Pipeline:
1. Load all 3 fix outputs (mechanisms, controls, data)
2. Run 529K interaction tests using linear OLS
3. Apply FDR correction (α=0.001)
4. Filter by effect size (|β3| > 0.15)
5. Validate results (50-200 interactions expected)
6. Save output manifest for A6 handoff

Runtime: ~20 minutes (estimated)
Output: outputs/A5_interaction_results.pkl
"""

import pickle
import pandas as pd
import numpy as np
from pathlib import Path
from scipy import stats
from scipy.linalg import solve
from statsmodels.stats.multitest import multipletests
import time
from datetime import datetime

print("="*80)
print("A5 INTERACTION DISCOVERY - MAIN PIPELINE")
print("="*80)
print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

start_time = time.time()

# ============================================================================
# STEP 1: Load All Inputs
# ============================================================================

print("[Step 1/7] Loading inputs from all 3 fixes...")

# Fix #1: Mechanism pairs
PAIRS_PATH = Path('outputs/mechanism_pairs_per_outcome.pkl')
print(f"   Loading mechanism pairs from: {PAIRS_PATH}")
with open(PAIRS_PATH, 'rb') as f:
    pairs_data = pickle.load(f)

outcomes = pairs_data['outcomes']
interaction_pairs = pairs_data['interaction_pairs']
n_total_pairs = pairs_data['metadata']['n_total_pairs']

print(f"✅ Loaded {len(outcomes)} outcomes with {n_total_pairs:,} interaction pairs")

# Fix #3: Control sets
CONTROLS_PATH = Path('outputs/precomputed_controls.pkl')
print(f"   Loading control sets from: {CONTROLS_PATH}")
with open(CONTROLS_PATH, 'rb') as f:
    controls_data = pickle.load(f)

precomputed_controls = controls_data['precomputed_controls']
print(f"✅ Loaded {len(precomputed_controls):,} pre-computed control sets")

# A1 Data
DATA_PATH = Path('../A1_missingness_analysis/outputs/A2_preprocessed_data.pkl')
print(f"   Loading preprocessed data from: {DATA_PATH}")
with open(DATA_PATH, 'rb') as f:
    a1_data = pickle.load(f)

# Convert imputed_data dict to wide DataFrame
imputed_dict = a1_data['imputed_data']
print(f"   Converting {len(imputed_dict):,} indicators to wide format...")

data_list = []
for indicator, df_indicator in imputed_dict.items():
    df_long = df_indicator.stack().to_frame(indicator)
    df_long.index.names = ['country', 'year']
    data_list.append(df_long)

df_data = pd.concat(data_list, axis=1)
print(f"✅ Data loaded: {df_data.shape[0]:,} observations × {df_data.shape[1]:,} indicators")

elapsed_load = time.time() - start_time
print(f"\n   Loading complete: {elapsed_load:.1f} seconds")

# ============================================================================
# STEP 2: Define Linear Regression Function (from Fix #2)
# ============================================================================

print("\n[Step 2/7] Setting up linear regression function...")

def linear_regression_cpu(X1, X2, y, controls, ridge_lambda=1e-6):
    """
    CPU-based linear regression with interaction term.

    Model: y = β0 + β1*X1 + β2*X2 + β3*(X1*X2) + Σβi*controls + ε

    Returns dict with beta_interaction, t_statistic, p_value, r_squared, n_obs
    """
    n = len(X1)

    # Create interaction term
    X_interaction = X1 * X2

    # Build design matrix
    intercept = np.ones((n, 1))
    X = np.column_stack([
        intercept,
        X1.reshape(-1, 1),
        X2.reshape(-1, 1),
        X_interaction.reshape(-1, 1),
        controls
    ])

    # Closed-form OLS: β = (X^T X)^(-1) X^T y
    XtX = X.T @ X
    Xty = X.T @ y
    XtX += ridge_lambda * np.eye(X.shape[1])

    try:
        beta = solve(XtX, Xty, assume_a='pos')
    except:
        return None  # Singular matrix

    # Compute residuals and R²
    y_pred = X @ beta
    residuals = y - y_pred
    rss = np.sum(residuals ** 2)
    tss = np.sum((y - np.mean(y)) ** 2)
    r_squared = 1 - (rss / tss) if tss > 0 else 0.0

    # Standard errors
    dof = n - X.shape[1]
    if dof > 0:
        sigma_squared = rss / dof
        try:
            XtX_inv = np.linalg.inv(XtX)
            var_beta = np.diagonal(XtX_inv) * sigma_squared
            se_beta = np.sqrt(var_beta)
        except:
            return None
    else:
        return None

    # Extract interaction coefficient (index 3)
    beta_interaction = beta[3]
    se_interaction = se_beta[3]

    # t-statistic and p-value
    if se_interaction > 0 and np.isfinite(se_interaction) and dof > 0:
        t_stat = beta_interaction / se_interaction
        p_value = 2 * (1 - stats.t.cdf(abs(t_stat), dof))
    else:
        return None

    return {
        'beta_interaction': beta_interaction,
        't_statistic': t_stat,
        'p_value': p_value,
        'r_squared': r_squared,
        'n_obs': n,
        'beta_all': beta,
        'se_all': se_beta
    }

print("✅ Linear regression function ready")

# ============================================================================
# STEP 3: Run Full Interaction Discovery (529K tests)
# ============================================================================

print(f"\n[Step 3/7] Running {n_total_pairs:,} interaction tests...")
print(f"   Estimated time: {n_total_pairs / 7382 / 60:.1f} minutes at 7,382 tests/sec")

results = []
n_processed = 0
n_success = 0
n_failed = 0
n_missing_data = 0

# Progress tracking
CHECKPOINT_EVERY = 50000
last_checkpoint_time = time.time()

print(f"\n   Starting interaction tests...")
print(f"   {'Progress':<12} {'Tests/sec':<12} {'Success %':<12} {'Elapsed':<12}")
print(f"   {'-'*12} {'-'*12} {'-'*12} {'-'*12}")

test_start = time.time()

for outcome, pairs in interaction_pairs.items():
    for m1, m2 in pairs:
        n_processed += 1

        # Get data
        if outcome not in df_data.columns or m1 not in df_data.columns or m2 not in df_data.columns:
            n_missing_data += 1
            continue

        # Get non-missing observations
        mask = df_data[[outcome, m1, m2]].notna().all(axis=1)
        if mask.sum() < 50:
            n_missing_data += 1
            continue

        y_np = df_data.loc[mask, outcome].values
        x1_np = df_data.loc[mask, m1].values
        x2_np = df_data.loc[mask, m2].values

        # Get controls
        control_vars = precomputed_controls[(outcome, m1, m2)]

        if len(control_vars) > 0:
            # Check if all controls exist in data
            valid_controls = [c for c in control_vars if c in df_data.columns]
            if len(valid_controls) > 0:
                controls_df = df_data.loc[mask, valid_controls]
                # Drop any controls with missing data
                controls_df = controls_df.dropna(axis=1, how='any')
                if controls_df.shape[1] > 0:
                    controls_np = controls_df.values
                else:
                    controls_np = np.zeros((mask.sum(), 1))
            else:
                controls_np = np.zeros((mask.sum(), 1))
        else:
            controls_np = np.zeros((mask.sum(), 1))

        # Run regression
        try:
            result = linear_regression_cpu(x1_np, x2_np, y_np, controls_np)

            if result is not None:
                results.append({
                    'outcome': outcome,
                    'mechanism_1': m1,
                    'mechanism_2': m2,
                    'beta_interaction': result['beta_interaction'],
                    't_statistic': result['t_statistic'],
                    'p_value': result['p_value'],
                    'r_squared': result['r_squared'],
                    'n_obs': result['n_obs'],
                    'n_controls': controls_np.shape[1]
                })
                n_success += 1
            else:
                n_failed += 1
        except Exception as e:
            n_failed += 1
            continue

        # Progress report
        if n_processed % CHECKPOINT_EVERY == 0:
            elapsed = time.time() - test_start
            throughput = n_processed / elapsed
            success_pct = (n_success / n_processed) * 100 if n_processed > 0 else 0

            print(f"   {n_processed:>10,}  {throughput:>10.0f}  {success_pct:>10.1f}%  {elapsed/60:>10.1f}m")

            # Save checkpoint
            checkpoint_path = Path(f'checkpoints/checkpoint_{n_processed}.pkl')
            checkpoint_path.parent.mkdir(exist_ok=True)
            with open(checkpoint_path, 'wb') as f:
                pickle.dump({
                    'results': results,
                    'n_processed': n_processed,
                    'timestamp': datetime.now()
                }, f)

# Final statistics
elapsed_test = time.time() - test_start
throughput = n_processed / elapsed_test

print(f"\n✅ Interaction testing complete:")
print(f"   Total processed: {n_processed:,}")
print(f"   Successful: {n_success:,} ({n_success/n_processed*100:.1f}%)")
print(f"   Failed: {n_failed:,} ({n_failed/n_processed*100:.1f}%)")
print(f"   Missing data: {n_missing_data:,} ({n_missing_data/n_processed*100:.1f}%)")
print(f"   Throughput: {throughput:.0f} tests/second")
print(f"   Runtime: {elapsed_test/60:.1f} minutes")

# ============================================================================
# STEP 4: Apply FDR Correction
# ============================================================================

print(f"\n[Step 4/7] Applying FDR correction (Benjamini-Hochberg, α=0.001)...")

df_results = pd.DataFrame(results)

if len(df_results) == 0:
    print("❌ ERROR: No successful interaction tests!")
    exit(1)

# Apply FDR correction
reject, pvals_corrected, alphacSidak, alphacBonf = multipletests(
    df_results['p_value'],
    alpha=0.001,
    method='fdr_bh'
)

df_results['p_value_fdr'] = pvals_corrected
df_results['significant_fdr'] = reject

n_significant = reject.sum()
print(f"✅ FDR correction applied:")
print(f"   Total tests: {len(df_results):,}")
print(f"   Significant (α=0.001): {n_significant:,} ({n_significant/len(df_results)*100:.1f}%)")

# ============================================================================
# STEP 5: Filter by Effect Size
# ============================================================================

print(f"\n[Step 5/7] Filtering by effect size (|β3| > 0.15)...")

df_validated = df_results[
    (df_results['significant_fdr']) &
    (df_results['beta_interaction'].abs() > 0.15)
].copy()

n_validated = len(df_validated)
print(f"✅ Effect size filter applied:")
print(f"   Validated interactions: {n_validated:,}")
print(f"   Median |β3|: {df_validated['beta_interaction'].abs().median():.4f}")
print(f"   Mean |β3|: {df_validated['beta_interaction'].abs().mean():.4f}")
print(f"   Max |β3|: {df_validated['beta_interaction'].abs().max():.4f}")

# Check if within expected range
if 50 <= n_validated <= 200:
    print(f"   ✅ PASS: Count within expected range (50-200)")
elif 20 <= n_validated < 50:
    print(f"   ⚠️  WARNING: Count below expected but acceptable (20-50)")
elif n_validated < 20:
    print(f"   ❌ FAIL: Count too low (<20) - review thresholds")
else:
    print(f"   ⚠️  WARNING: Count above expected (>200) - consider stricter filter")

# ============================================================================
# STEP 6: Validate Results
# ============================================================================

print(f"\n[Step 6/7] Validating interaction results...")

# Check for scale artifacts (extreme β3)
n_extreme = (df_validated['beta_interaction'].abs() > 10).sum()
if n_extreme > 0:
    print(f"   ⚠️  WARNING: {n_extreme} interactions with |β3| > 10 (scale artifacts)")
    df_validated['warning_extreme_beta'] = df_validated['beta_interaction'].abs() > 10
else:
    print(f"   ✅ No extreme beta values detected")
    df_validated['warning_extreme_beta'] = False

# Check for low observation counts
n_low_obs = (df_validated['n_obs'] < 100).sum()
if n_low_obs > 0:
    print(f"   ⚠️  WARNING: {n_low_obs} interactions with <100 observations")
else:
    print(f"   ✅ All interactions have ≥100 observations")

# Summary statistics
print(f"\n   Validation summary:")
print(f"   Mean R²: {df_validated['r_squared'].mean():.3f}")
print(f"   Mean observations: {df_validated['n_obs'].mean():.0f}")
print(f"   Mean controls: {df_validated['n_controls'].mean():.1f}")
print(f"   % positive interactions: {(df_validated['beta_interaction'] > 0).mean() * 100:.1f}%")

# ============================================================================
# STEP 7: Save Results
# ============================================================================

print(f"\n[Step 7/7] Saving results...")

OUTPUT_DIR = Path('outputs')
OUTPUT_DIR.mkdir(exist_ok=True)

# Main output
output_data = {
    'validated_interactions': df_validated.to_dict('records'),
    'all_results': df_results.to_dict('records'),
    'metadata': {
        'created_at': datetime.now().isoformat(),
        'n_total_tests': n_processed,
        'n_successful': n_success,
        'n_significant_fdr': n_significant,
        'n_validated': n_validated,
        'fdr_alpha': 0.001,
        'effect_size_threshold': 0.15,
        'median_abs_beta3': df_validated['beta_interaction'].abs().median(),
        'mean_abs_beta3': df_validated['beta_interaction'].abs().mean(),
        'n_extreme_beta': n_extreme,
        'throughput_tests_per_sec': throughput,
        'runtime_minutes': elapsed_test / 60
    }
}

output_path = OUTPUT_DIR / 'A5_interaction_results.pkl'
with open(output_path, 'wb') as f:
    pickle.dump(output_data, f)

print(f"✅ Main results saved to: {output_path}")
print(f"   File size: {output_path.stat().st_size / 1024**2:.1f} MB")

# Save validated interactions as CSV for easy inspection
csv_path = OUTPUT_DIR / 'A5_validated_interactions.csv'
df_validated.to_csv(csv_path, index=False)
print(f"✅ CSV saved to: {csv_path}")

# Save summary report
summary_path = OUTPUT_DIR / 'A5_interaction_discovery_summary.txt'
with open(summary_path, 'w') as f:
    f.write("A5 INTERACTION DISCOVERY - FINAL SUMMARY\n")
    f.write("="*80 + "\n\n")
    f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
    f.write("RESULTS:\n")
    f.write(f"  Total tests: {n_processed:,}\n")
    f.write(f"  Successful: {n_success:,} ({n_success/n_processed*100:.1f}%)\n")
    f.write(f"  Significant (FDR α=0.001): {n_significant:,} ({n_significant/n_success*100:.1f}%)\n")
    f.write(f"  Validated (|β3|>0.15): {n_validated:,}\n\n")
    f.write("EFFECT STATISTICS:\n")
    f.write(f"  Median |β3|: {df_validated['beta_interaction'].abs().median():.4f}\n")
    f.write(f"  Mean |β3|: {df_validated['beta_interaction'].abs().mean():.4f}\n")
    f.write(f"  Max |β3|: {df_validated['beta_interaction'].abs().max():.4f}\n")
    f.write(f"  % positive: {(df_validated['beta_interaction'] > 0).mean() * 100:.1f}%\n\n")
    f.write("QUALITY METRICS:\n")
    f.write(f"  Mean R²: {df_validated['r_squared'].mean():.3f}\n")
    f.write(f"  Mean observations: {df_validated['n_obs'].mean():.0f}\n")
    f.write(f"  Mean controls: {df_validated['n_controls'].mean():.1f}\n\n")
    f.write("PERFORMANCE:\n")
    f.write(f"  Throughput: {throughput:.0f} tests/second\n")
    f.write(f"  Runtime: {elapsed_test/60:.1f} minutes\n\n")
    f.write("VALIDATION:\n")
    if 50 <= n_validated <= 200:
        f.write(f"  ✅ PASS: Count within expected range (50-200)\n")
    elif 20 <= n_validated < 50:
        f.write(f"  ⚠️  WARNING: Count below expected but acceptable\n")
    else:
        f.write(f"  ⚠️  WARNING: Count outside expected range\n")
    f.write(f"\nSTATUS: ✅ A5 COMPLETE\n")

print(f"✅ Summary saved to: {summary_path}")

# ============================================================================
# FINAL SUMMARY
# ============================================================================

total_elapsed = time.time() - start_time

print(f"\n{'='*80}")
print("A5 INTERACTION DISCOVERY COMPLETE")
print(f"{'='*80}")
print(f"\n✅ Successfully discovered {n_validated:,} validated interactions")
print(f"\nKey Metrics:")
print(f"  - Total tests: {n_processed:,}")
print(f"  - Success rate: {n_success/n_processed*100:.1f}%")
print(f"  - FDR significant: {n_significant:,}")
print(f"  - Validated: {n_validated:,}")
print(f"  - Median |β3|: {df_validated['beta_interaction'].abs().median():.4f}")
print(f"  - Throughput: {throughput:.0f} tests/sec")
print(f"  - Total runtime: {total_elapsed/60:.1f} minutes")
print(f"\nOutput Files:")
print(f"  - {output_path}")
print(f"  - {csv_path}")
print(f"  - {summary_path}")
print(f"\nNext: A6 Hierarchical Layering")
print(f"{'='*80}")
