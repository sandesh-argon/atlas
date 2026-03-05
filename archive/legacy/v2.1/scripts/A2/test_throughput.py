#!/usr/bin/env python3
"""
A2 Throughput Test - Measure actual performance before full run

Tests:
1. Prefiltering: correlation computation on sample of indicators
2. Granger testing: run on sample of pairs

Returns accurate time estimates for full run.
"""

import pickle
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import time
import sys

# V2.1 Configuration
sys.path.insert(0, str(Path(__file__).parent.parent))
from v21_config import get_input_path, A2_OUTPUT

print("=" * 80)
print("A2 THROUGHPUT TEST")
print("=" * 80)
print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# Load data
print("\n[1/4] Loading V2.1 data...")
with open(get_input_path(), 'rb') as f:
    data = pickle.load(f)

imputed_data = data['imputed_data']
indicator_names = list(imputed_data.keys())
n_indicators = len(indicator_names)

print(f"  Loaded {n_indicators:,} indicators")
print(f"  Total pairs to test: {n_indicators * (n_indicators - 1):,}")

# ============================================================================
# TEST 1: Correlation computation throughput
# ============================================================================
print("\n[2/4] Testing correlation computation throughput...")

def compute_pair_correlation(X_df, Y_df):
    """Compute correlation between two indicators"""
    common_cols = sorted(list(set(X_df.columns) & set(Y_df.columns)))
    if len(common_cols) < 20:
        return None

    X_subset = X_df[common_cols]
    Y_subset = Y_df[common_cols]
    common_rows = sorted(list(set(X_subset.index) & set(Y_subset.index)))

    if len(common_rows) < 50:
        return None

    X_aligned = X_subset.loc[common_rows, common_cols].values.flatten()
    Y_aligned = Y_subset.loc[common_rows, common_cols].values.flatten()

    mask = ~(np.isnan(X_aligned) | np.isnan(Y_aligned))
    X_clean = X_aligned[mask]
    Y_clean = Y_aligned[mask]

    if len(X_clean) < 100:
        return None

    try:
        corr = np.corrcoef(X_clean, Y_clean)[0, 1]
        return corr if not np.isnan(corr) else None
    except:
        return None

# Test on 100 indicators (10,000 pairs)
test_n = min(100, n_indicators)
test_indicators = indicator_names[:test_n]
test_pairs = test_n * (test_n - 1)

print(f"  Testing {test_n} indicators ({test_pairs:,} pairs)...")

start = time.time()
corr_count = 0
for i in range(test_n):
    X_name = test_indicators[i]
    X_df = imputed_data[X_name]
    for j in range(test_n):
        if i == j:
            continue
        Y_name = test_indicators[j]
        Y_df = imputed_data[Y_name]
        corr = compute_pair_correlation(X_df, Y_df)
        if corr is not None:
            corr_count += 1

elapsed_corr = time.time() - start
corr_rate = test_pairs / elapsed_corr

# Extrapolate to full run
total_pairs = n_indicators * (n_indicators - 1)
estimated_corr_time = total_pairs / corr_rate

print(f"  ✅ Computed {corr_count:,} correlations in {elapsed_corr:.1f}s")
print(f"  Throughput: {corr_rate:.0f} pairs/second")
print(f"  Estimated full prefiltering time: {estimated_corr_time/3600:.2f} hours")

# ============================================================================
# TEST 2: Granger causality throughput (using statsmodels)
# ============================================================================
print("\n[3/4] Testing Granger causality throughput...")

from statsmodels.tsa.stattools import grangercausalitytests
import warnings
warnings.filterwarnings('ignore')

def run_granger_test(X_df, Y_df, maxlag=3):
    """Run Granger causality test between two indicators"""
    common_cols = sorted(list(set(X_df.columns) & set(Y_df.columns)))
    if len(common_cols) < 20:
        return None

    common_rows = sorted(list(set(X_df.index) & set(Y_df.index)))
    if len(common_rows) < 50:
        return None

    # Get mean across countries for each year (simplification for speed test)
    X_series = X_df.loc[common_rows, common_cols].mean(axis=0).values
    Y_series = Y_df.loc[common_rows, common_cols].mean(axis=0).values

    # Remove NaN
    mask = ~(np.isnan(X_series) | np.isnan(Y_series))
    X_clean = X_series[mask]
    Y_clean = Y_series[mask]

    if len(X_clean) < maxlag + 5:
        return None

    try:
        data_matrix = np.column_stack([Y_clean, X_clean])
        result = grangercausalitytests(data_matrix, maxlag=maxlag, verbose=False)
        # Get minimum p-value across lags
        min_p = min(result[lag][0]['ssr_ftest'][1] for lag in range(1, maxlag + 1))
        return min_p
    except:
        return None

# Test on 50 pairs
test_granger_n = 50
print(f"  Testing {test_granger_n} Granger tests...")

start = time.time()
granger_count = 0
for i in range(min(test_granger_n, test_n - 1)):
    X_name = test_indicators[i]
    Y_name = test_indicators[i + 1]
    X_df = imputed_data[X_name]
    Y_df = imputed_data[Y_name]
    p_val = run_granger_test(X_df, Y_df, maxlag=3)
    if p_val is not None:
        granger_count += 1

elapsed_granger = time.time() - start
granger_rate = test_granger_n / elapsed_granger

# Estimate pairs after prefiltering (typically ~5-10% pass correlation filter)
# Based on V2 run: ~293K pairs passed prefiltering from 40.6M
filter_rate = 0.05  # Conservative estimate
estimated_filtered_pairs = int(total_pairs * filter_rate)
estimated_granger_time = estimated_filtered_pairs / granger_rate

print(f"  ✅ Completed {granger_count}/{test_granger_n} Granger tests in {elapsed_granger:.1f}s")
print(f"  Throughput: {granger_rate:.1f} tests/second")
print(f"  Estimated pairs after prefiltering: ~{estimated_filtered_pairs:,}")
print(f"  Estimated Granger testing time: {estimated_granger_time/3600:.2f} hours")

# ============================================================================
# SUMMARY
# ============================================================================
print("\n" + "=" * 80)
print("THROUGHPUT TEST SUMMARY")
print("=" * 80)

total_estimated = estimated_corr_time + estimated_granger_time

print(f"""
V2.1 Pipeline Estimates:
  Total indicators: {n_indicators:,}
  Total pairs: {total_pairs:,}

Step 2 - Prefiltering (correlation):
  Throughput: {corr_rate:.0f} pairs/second
  Estimated time: {estimated_corr_time/3600:.2f} hours

Step 3 - Granger Testing:
  Throughput: {granger_rate:.1f} tests/second
  Estimated pairs: ~{estimated_filtered_pairs:,} (after filtering)
  Estimated time: {estimated_granger_time/3600:.2f} hours

TOTAL ESTIMATED A2 TIME: {total_estimated/3600:.1f} hours
""")

# Save estimates
estimates = {
    'timestamp': datetime.now().isoformat(),
    'n_indicators': n_indicators,
    'total_pairs': total_pairs,
    'corr_throughput': corr_rate,
    'corr_estimated_hours': estimated_corr_time / 3600,
    'granger_throughput': granger_rate,
    'granger_estimated_pairs': estimated_filtered_pairs,
    'granger_estimated_hours': estimated_granger_time / 3600,
    'total_estimated_hours': total_estimated / 3600
}

import json
estimates_file = A2_OUTPUT / 'throughput_estimates.json'
with open(estimates_file, 'w') as f:
    json.dump(estimates, f, indent=2)

print(f"Estimates saved to: {estimates_file}")
