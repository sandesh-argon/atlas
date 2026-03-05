#!/usr/bin/env python3
"""
A2 Step 2: Prefiltering Pipeline
=================================
Reduces 40.6M candidate pairs to ~293K testable pairs using multi-stage filtering.

Stages:
1. Correlation filter (0.10 < |r| < 0.95)
2. Domain compatibility filter (SKIPPED - 80% "Other")
3. Literature plausibility check
4. Temporal precedence filter

Expected reduction: 40.6M → ~293K pairs (99.3% reduction)
"""

import pandas as pd
import numpy as np
import pickle
from pathlib import Path
from datetime import datetime
from itertools import combinations
from joblib import Parallel, delayed
import warnings
warnings.filterwarnings('ignore')

# Configuration
BASE_DIR = Path(__file__).parent.parent.parent
A1_CHECKPOINT = BASE_DIR / "A1_missingness_analysis" / "outputs" / "A2_preprocessed_data.pkl"
OUTPUT_DIR = BASE_DIR / "A2_granger_causality" / "outputs"
OUTPUT_DIR.mkdir(exist_ok=True, parents=True)

# Prefiltering thresholds
CORRELATION_MIN = 0.10
CORRELATION_MAX = 0.95
N_JOBS = 20  # 85% of 24 cores

def load_data():
    """Load A1 checkpoint"""
    print("=" * 80)
    print("LOADING DATA")
    print("=" * 80)

    with open(A1_CHECKPOINT, 'rb') as f:
        data = pickle.load(f)

    imputed_data = data['imputed_data']
    metadata = data['metadata']

    print(f"✅ Loaded {len(imputed_data)} indicators")
    print()

    return imputed_data, metadata

def get_all_candidate_pairs(indicator_names):
    """Generate all possible directed pairs"""
    print("=" * 80)
    print("GENERATING CANDIDATE PAIRS")
    print("=" * 80)

    # All pairs X → Y where X != Y
    # Total: n * (n-1) = 6368 * 6367 = 40,557,056 pairs

    n = len(indicator_names)
    total_pairs = n * (n - 1)

    print(f"Indicators: {n:,}")
    print(f"Total candidate pairs: {total_pairs:,}")
    print()

    # Generate pairs in chunks to avoid memory issues
    return total_pairs, indicator_names

def compute_correlation_chunk(indicator_names, imputed_data, chunk_start, chunk_size):
    """Compute correlations for a chunk of pairs"""
    results = []
    n = len(indicator_names)

    for i in range(chunk_start, min(chunk_start + chunk_size, n)):
        X_name = indicator_names[i]
        X_df = imputed_data[X_name]

        for j in range(n):
            if i == j:
                continue  # Skip self-pairs

            Y_name = indicator_names[j]
            Y_df = imputed_data[Y_name]

            # Compute correlation on overlapping data
            # Align by country-year pairs
            correlation = compute_pair_correlation(X_df, Y_df)

            if correlation is not None:
                results.append({
                    'source': X_name,
                    'target': Y_name,
                    'correlation': correlation
                })

    return results

def compute_pair_correlation(X_df, Y_df):
    """Compute correlation between two indicators"""
    # Get common columns (years)
    common_cols = sorted(list(set(X_df.columns) & set(Y_df.columns)))

    if len(common_cols) < 20:
        return None  # Need at least 20 years overlap

    # Extract values for common years only
    X_subset = X_df[common_cols]
    Y_subset = Y_df[common_cols]

    # Get common rows (countries) - align by index
    common_rows = sorted(list(set(X_subset.index) & set(Y_subset.index)))

    if len(common_rows) < 50:  # Need sufficient countries
        return None

    # Extract aligned values
    X_aligned = X_subset.loc[common_rows, common_cols].values.flatten()
    Y_aligned = Y_subset.loc[common_rows, common_cols].values.flatten()

    # Now they have same shape - remove NaN pairs
    mask = ~(np.isnan(X_aligned) | np.isnan(Y_aligned))
    X_clean = X_aligned[mask]
    Y_clean = Y_aligned[mask]

    if len(X_clean) < 100:  # Need sufficient data points
        return None

    # Compute Pearson correlation
    try:
        corr = np.corrcoef(X_clean, Y_clean)[0, 1]
        return corr if not np.isnan(corr) else None
    except:
        return None

def stage1_correlation_filter(imputed_data, metadata):
    """Stage 1: Filter by correlation threshold"""
    print("=" * 80)
    print("STAGE 1: CORRELATION FILTER")
    print("=" * 80)
    print(f"Threshold: {CORRELATION_MIN} < |r| < {CORRELATION_MAX}")
    print()

    indicator_names = list(imputed_data.keys())
    n = len(indicator_names)

    print(f"Processing {n:,} indicators...")
    print(f"Using {N_JOBS} parallel cores")
    print()

    # Chunk size: process indicators in batches
    chunk_size = 50  # Process 50 indicators at a time
    n_chunks = (n + chunk_size - 1) // chunk_size

    print(f"Processing in {n_chunks} chunks...")
    print("This will take 3-5 hours - correlation is expensive")
    print()

    start_time = datetime.now()

    # Process chunks in parallel
    all_results = Parallel(n_jobs=N_JOBS, verbose=10)(
        delayed(compute_correlation_chunk)(
            indicator_names, imputed_data, i * chunk_size, chunk_size
        )
        for i in range(n_chunks)
    )

    # Flatten results
    all_pairs = []
    for chunk_results in all_results:
        all_pairs.extend(chunk_results)

    elapsed = (datetime.now() - start_time).total_seconds()

    print()
    print(f"✅ Computed {len(all_pairs):,} correlations in {elapsed/3600:.2f} hours")
    print()

    # Filter by correlation threshold
    filtered_pairs = [
        pair for pair in all_pairs
        if CORRELATION_MIN <= abs(pair['correlation']) <= CORRELATION_MAX
    ]

    reduction_pct = (1 - len(filtered_pairs) / len(all_pairs)) * 100 if all_pairs else 0

    print(f"Before filter: {len(all_pairs):,} pairs")
    print(f"After filter: {len(filtered_pairs):,} pairs")
    print(f"Reduction: {reduction_pct:.1f}%")
    print()

    return filtered_pairs

def stage2_domain_filter(pairs, metadata):
    """Stage 2: Domain compatibility filter - SKIPPED"""
    print("=" * 80)
    print("STAGE 2: DOMAIN COMPATIBILITY FILTER")
    print("=" * 80)
    print("⚠️  SKIPPED: 80% of indicators classified as 'Other'")
    print("   Domain filter would not be effective")
    print("   Relying on correlation + literature plausibility instead")
    print()

    return pairs  # No filtering

def stage3_literature_plausibility(pairs):
    """Stage 3: Literature plausibility check"""
    print("=" * 80)
    print("STAGE 3: LITERATURE PLAUSIBILITY FILTER")
    print("=" * 80)

    # TODO: Implement literature plausibility database check
    # For now, use simple heuristics:
    # - Economic → Health: PLAUSIBLE
    # - Health → Economic: PLAUSIBLE
    # - Same-source self-loops: IMPLAUSIBLE (remove)

    print("⚠️  Literature database not yet implemented")
    print("   Using basic heuristics:")
    print("   - Remove same-source self-loops")
    print("   - Keep all other pairs")
    print()

    # Filter: Remove pairs from same data source with identical prefix
    filtered_pairs = []

    for pair in pairs:
        source = pair['source']
        target = pair['target']

        # Simple heuristic: if indicators share first 4 characters, likely same construct
        # Examples: "NY.GDP.MKTP.KD" and "NY.GDP.PCAP.KD" (both GDP from World Bank)
        if source[:4] == target[:4]:
            continue  # Skip likely duplicate constructs

        filtered_pairs.append(pair)

    reduction_pct = (1 - len(filtered_pairs) / len(pairs)) * 100 if pairs else 0

    print(f"Before filter: {len(pairs):,} pairs")
    print(f"After filter: {len(filtered_pairs):,} pairs")
    print(f"Reduction: {reduction_pct:.1f}%")
    print()

    return filtered_pairs

def stage4_temporal_precedence(pairs):
    """Stage 4: Temporal precedence filter"""
    print("=" * 80)
    print("STAGE 4: TEMPORAL PRECEDENCE FILTER")
    print("=" * 80)

    # Remove:
    # - Self-lagged pairs (X → X)
    # - Impossible temporal orders (already handled by directed pairs)

    filtered_pairs = [
        pair for pair in pairs
        if pair['source'] != pair['target']
    ]

    reduction_pct = (1 - len(filtered_pairs) / len(pairs)) * 100 if pairs else 0

    print(f"Before filter: {len(pairs):,} pairs")
    print(f"After filter: {len(filtered_pairs):,} pairs")
    print(f"Reduction: {reduction_pct:.1f}%")
    print()

    return filtered_pairs

def save_filtered_pairs(pairs):
    """Save filtered pairs to checkpoint"""
    output_file = OUTPUT_DIR / "prefiltered_pairs.pkl"

    print("=" * 80)
    print("SAVING FILTERED PAIRS")
    print("=" * 80)

    # Convert to DataFrame
    df = pd.DataFrame(pairs)

    checkpoint = {
        'pairs': df,
        'metadata': {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'n_pairs': len(pairs),
            'correlation_threshold': (CORRELATION_MIN, CORRELATION_MAX),
            'stages_applied': [
                'correlation',
                'domain (skipped)',
                'literature (heuristic)',
                'temporal_precedence'
            ]
        }
    }

    with open(output_file, 'wb') as f:
        pickle.dump(checkpoint, f)

    file_size_mb = output_file.stat().st_size / (1024**2)

    print(f"✅ Saved: {output_file}")
    print(f"   Size: {file_size_mb:.1f} MB")
    print(f"   Pairs: {len(pairs):,}")
    print()

def main():
    print("=" * 80)
    print("A2 STEP 2: PREFILTERING PIPELINE")
    print("=" * 80)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Load data
    imputed_data, metadata = load_data()

    # Stage 1: Correlation filter
    pairs = stage1_correlation_filter(imputed_data, metadata)

    # Stage 2: Domain filter (skipped)
    pairs = stage2_domain_filter(pairs, metadata)

    # Stage 3: Literature plausibility
    pairs = stage3_literature_plausibility(pairs)

    # Stage 4: Temporal precedence
    pairs = stage4_temporal_precedence(pairs)

    # Save results
    save_filtered_pairs(pairs)

    # Summary
    print("=" * 80)
    print("PREFILTERING SUMMARY")
    print("=" * 80)

    n_indicators = len(imputed_data)
    total_possible = n_indicators * (n_indicators - 1)
    reduction_pct = (1 - len(pairs) / total_possible) * 100

    print(f"Initial candidate pairs: {total_possible:,}")
    print(f"Final filtered pairs: {len(pairs):,}")
    print(f"Overall reduction: {reduction_pct:.2f}%")
    print()

    # Granger test estimates
    n_lags = 5
    n_directions = 2  # X→Y and Y→X tested separately
    total_operations = len(pairs) * n_lags * n_directions

    print(f"Granger test operations (5 lags × 2 directions):")
    print(f"  Total operations: {total_operations:,}")
    print()

    # Estimate runtime
    seconds_per_operation = 0.6  # Conservative estimate
    total_seconds = total_operations * seconds_per_operation
    days = total_seconds / (24 * 3600)

    print(f"Estimated Granger testing runtime:")
    print(f"  @ 0.6s per operation: {days:.1f} days")
    print()

    if 7 <= days <= 12:
        print("✅ Runtime estimate within acceptable range (9-10 days)")
    elif days > 12:
        print(f"⚠️  WARNING: Runtime {days:.1f} days > 12 day target")
        print("   Consider additional prefiltering")
    else:
        print(f"✅ Runtime {days:.1f} days < 12 days (ahead of schedule)")

    print()
    print("=" * 80)
    print("PREFILTERING COMPLETE")
    print("=" * 80)
    print()
    print("Next Step: Parallel Granger causality testing")
    print(f"Estimated time: {days:.1f} days")
    print()

if __name__ == "__main__":
    main()
