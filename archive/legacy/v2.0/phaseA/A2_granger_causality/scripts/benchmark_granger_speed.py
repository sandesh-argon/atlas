#!/usr/bin/env python3
"""
Benchmark Granger Causality Test Speed
=======================================
Runs actual Granger tests on a sample to measure real performance.
"""

import pandas as pd
import numpy as np
import pickle
from pathlib import Path
import time
from statsmodels.tsa.stattools import grangercausalitytests
import warnings
warnings.filterwarnings('ignore')

# Paths
BASE_DIR = Path(__file__).parent.parent.parent
A1_CHECKPOINT = BASE_DIR / "A1_missingness_analysis" / "outputs" / "A2_preprocessed_data.pkl"
FILTERED_PAIRS = BASE_DIR / "A2_granger_causality" / "outputs" / "prefiltered_pairs.pkl"

def load_data():
    """Load checkpoint and filtered pairs"""
    print("Loading data...")

    with open(A1_CHECKPOINT, 'rb') as f:
        a1_data = pickle.load(f)

    with open(FILTERED_PAIRS, 'rb') as f:
        pairs_data = pickle.load(f)

    imputed_data = a1_data['imputed_data']
    pairs_df = pairs_data['pairs']

    print(f"✅ Loaded {len(imputed_data)} indicators")
    print(f"✅ Loaded {len(pairs_df):,} filtered pairs")
    print()

    return imputed_data, pairs_df

def prepare_time_series(X_df, Y_df):
    """Prepare aligned time series for Granger test"""
    # Get common years and countries
    common_cols = sorted(list(set(X_df.columns) & set(Y_df.columns)))
    common_rows = sorted(list(set(X_df.index) & set(Y_df.index)))

    if len(common_cols) < 20 or len(common_rows) < 50:
        return None

    # Extract aligned data
    X_aligned = X_df.loc[common_rows, common_cols]
    Y_aligned = Y_df.loc[common_rows, common_cols]

    # For each country, create time series
    # Use country with most complete data
    best_country = None
    best_count = 0

    for country in common_rows:
        X_series = X_aligned.loc[country].values
        Y_series = Y_aligned.loc[country].values

        # Count non-NaN pairs
        valid_mask = ~(np.isnan(X_series) | np.isnan(Y_series))
        valid_count = valid_mask.sum()

        if valid_count > best_count:
            best_count = valid_count
            best_country = country

    if best_count < 25:  # Need at least 25 time points for lag-5 test
        return None

    # Extract best time series
    X_series = X_aligned.loc[best_country].values
    Y_series = Y_aligned.loc[best_country].values

    # Remove NaN pairs
    valid_mask = ~(np.isnan(X_series) | np.isnan(Y_series))
    X_clean = X_series[valid_mask]
    Y_clean = Y_series[valid_mask]

    if len(X_clean) < 25:
        return None

    # Stack for Granger test format
    data = np.column_stack([Y_clean, X_clean])

    return data

def run_single_granger_test(data, maxlag=5):
    """Run single Granger test and return p-value"""
    try:
        result = grangercausalitytests(data, maxlag=maxlag, verbose=False)

        # Extract p-value for lag-5
        p_value = result[maxlag][0]['ssr_ftest'][1]

        return p_value
    except:
        return None

def benchmark_granger_tests(imputed_data, pairs_df, sample_size=1000):
    """Run benchmark on sample of pairs"""
    print("=" * 80)
    print("GRANGER CAUSALITY SPEED BENCHMARK")
    print("=" * 80)
    print(f"Sample size: {sample_size} pairs")
    print()

    # Sample random pairs
    sample_pairs = pairs_df.sample(min(sample_size, len(pairs_df)))

    print("Running Granger tests...")
    successful_tests = 0
    failed_tests = 0
    test_times = []

    start_total = time.time()

    for idx, row in sample_pairs.iterrows():
        source = row['source']
        target = row['target']

        # Prepare data
        try:
            X_df = imputed_data[source]
            Y_df = imputed_data[target]

            data = prepare_time_series(X_df, Y_df)

            if data is None:
                failed_tests += 1
                continue

            # Time the Granger test
            start = time.time()
            p_value = run_single_granger_test(data, maxlag=5)
            elapsed = time.time() - start

            if p_value is not None:
                test_times.append(elapsed)
                successful_tests += 1
            else:
                failed_tests += 1

        except Exception as e:
            failed_tests += 1

    total_elapsed = time.time() - start_total

    print()
    print("=" * 80)
    print("BENCHMARK RESULTS")
    print("=" * 80)

    if len(test_times) == 0:
        print("❌ No successful tests - check data format")
        return

    test_times = np.array(test_times)

    print(f"Successful tests: {successful_tests}")
    print(f"Failed tests: {failed_tests}")
    print(f"Success rate: {successful_tests / sample_size * 100:.1f}%")
    print()

    print("Time per Granger test:")
    print(f"  Mean: {test_times.mean():.4f}s")
    print(f"  Median: {np.median(test_times):.4f}s")
    print(f"  Min: {test_times.min():.4f}s")
    print(f"  Max: {test_times.max():.4f}s")
    print()

    # Extrapolate to full dataset
    per_test = test_times.median()

    print("=" * 80)
    print("EXTRAPOLATED TIMELINE")
    print("=" * 80)

    scenarios = [
        ("Current (0.10-0.95)", 15_889_478),
        ("Threshold 0.20-0.90", 8_213_238),
        ("Threshold 0.30-0.90", 4_930_434),
        ("Threshold 0.40-0.90", 3_130_126),
        ("Threshold 0.50-0.90", 1_965_010),
    ]

    for name, n_pairs in scenarios:
        # Account for 2 directions (X→Y and Y→X tested separately)
        # But Granger test already tests both in one call
        operations = n_pairs * 5  # 5 lags tested

        seconds = operations * per_test
        days = seconds / (24 * 3600)

        status = "✅" if days <= 10 else "⚠️" if days <= 20 else "❌"

        print(f"{name:25s}: {n_pairs:>10,} pairs")
        print(f"  → {operations:>12,} operations")
        print(f"  → {days:>6.1f} days {status}")
        print()

    # Recommendation
    print("=" * 80)
    print("RECOMMENDATION")
    print("=" * 80)

    # Find best threshold that keeps us under 10 days
    best_option = None
    for name, n_pairs in scenarios:
        operations = n_pairs * 5
        days = operations * per_test / (24 * 3600)

        if days <= 10:
            best_option = (name, n_pairs, days)
            break

    if best_option:
        print(f"✅ Use: {best_option[0]}")
        print(f"   Pairs: {best_option[1]:,}")
        print(f"   Estimated runtime: {best_option[2]:.1f} days")
        print()
        print("   Rationale: Maximizes causal discovery within 10-day target")
    else:
        # All options too slow
        print("⚠️  All thresholds exceed 10-day target")
        print(f"   Fastest option: {scenarios[-1][0]}")
        print(f"   Runtime: {scenarios[-1][1] * 5 * per_test / (24 * 3600):.1f} days")

    print()

def main():
    print("=" * 80)
    print("GRANGER CAUSALITY BENCHMARK")
    print("=" * 80)
    print()

    # Load data
    imputed_data, pairs_df = load_data()

    # Run benchmark
    benchmark_granger_tests(imputed_data, pairs_df, sample_size=1000)

    print("=" * 80)
    print("BENCHMARK COMPLETE")
    print("=" * 80)

if __name__ == "__main__":
    main()
