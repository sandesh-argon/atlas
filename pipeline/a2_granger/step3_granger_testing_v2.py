#!/usr/bin/env python3
"""
A2 Step 3: Parallel Granger Causality Testing (Memory-Safe Version)
====================================================================
Runs Granger causality tests on prefiltered pairs with checkpointing.

MEMORY FIX: Saves incremental results to disk instead of keeping in RAM.
- Checkpoint stores only progress index + metadata (not all results)
- Results saved incrementally to separate files per checkpoint
- Final output combines all incremental files

Expected: 15.9M pairs, ~2.4 hours runtime with 20 cores
"""

import pandas as pd
import numpy as np
import pickle
from pathlib import Path
import sys
from datetime import datetime
from statsmodels.tsa.stattools import grangercausalitytests
from joblib import Parallel, delayed
import warnings
warnings.filterwarnings('ignore')

# V2.1 Configuration - import paths from config
sys.path.insert(0, str(Path(__file__).parent.parent))
from v21_config import A1_INPUT, A2_OUTPUT, A2_CHECKPOINTS, get_input_path


N_JOBS = 10  # Reduced to 10 cores for thermal safety (system crashed at 15)
MAXLAG = 5
CHECKPOINT_INTERVAL = 100000  # Save every 100K pairs

# Define paths
A1_CHECKPOINT = get_input_path()
FILTERED_PAIRS = A2_OUTPUT / "prefiltered_pairs.pkl"
CHECKPOINT_DIR = A2_CHECKPOINTS
RESULTS_DIR = A2_CHECKPOINTS / "granger_chunks"
PROGRESS_FILE = A2_OUTPUT / "progress.json"

# Ensure directories exist
CHECKPOINT_DIR.mkdir(exist_ok=True, parents=True)
RESULTS_DIR.mkdir(exist_ok=True, parents=True)

def update_progress(step, pct, elapsed_min, eta_min, items_done, items_total, extra=None):
    """Write progress to JSON file for external monitoring"""
    import json
    progress = {
        "step": step,
        "pct": round(pct, 1),
        "elapsed_min": round(elapsed_min, 1),
        "eta_min": round(eta_min, 1),
        "items_done": items_done,
        "items_total": items_total,
        "updated": datetime.now().isoformat()
    }
    if extra:
        progress.update(extra)
    with open(PROGRESS_FILE, 'w') as f:
        json.dump(progress, f, indent=2)

def load_data():
    """Load imputed data and filtered pairs"""
    print("=" * 80)
    print("LOADING DATA")
    print("=" * 80)

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

    # Find country with most complete data
    best_country = None
    best_count = 0

    for country in common_rows:
        X_series = X_aligned.loc[country].values
        Y_series = Y_aligned.loc[country].values

        valid_mask = ~(np.isnan(X_series) | np.isnan(Y_series))
        valid_count = valid_mask.sum()

        if valid_count > best_count:
            best_count = valid_count
            best_country = country

    if best_count < 25:
        return None

    # Extract time series
    X_series = X_aligned.loc[best_country].values
    Y_series = Y_aligned.loc[best_country].values

    # Remove NaN pairs
    valid_mask = ~(np.isnan(X_series) | np.isnan(Y_series))
    X_clean = X_series[valid_mask]
    Y_clean = Y_series[valid_mask]

    if len(X_clean) < 25:
        return None

    return X_clean, Y_clean, best_country

def run_granger_test(source, target, imputed_data, maxlag=5):
    """Run Granger causality test for one pair"""
    try:
        X_df = imputed_data[source]
        Y_df = imputed_data[target]

        data_prep = prepare_time_series(X_df, Y_df)

        if data_prep is None:
            return None

        X_clean, Y_clean, country = data_prep

        # Granger test format: column 0 is Y (target), column 1 is X (source)
        data = np.column_stack([Y_clean, X_clean])

        # Run Granger test
        result = grangercausalitytests(data, maxlag=maxlag, verbose=False)

        # Extract p-values for all lags
        p_values = {}
        f_stats = {}

        for lag in range(1, maxlag + 1):
            p_values[f'lag{lag}'] = result[lag][0]['ssr_ftest'][1]
            f_stats[f'lag{lag}'] = result[lag][0]['ssr_ftest'][0]

        # Get minimum p-value (most significant lag)
        min_p = min(p_values.values())
        best_lag = [k for k, v in p_values.items() if v == min_p][0].replace('lag', '')

        return {
            'source': source,
            'target': target,
            'best_lag': int(best_lag),
            'p_value': min_p,
            'f_statistic': f_stats[f'lag{best_lag}'],
            'country': country,
            'n_obs': len(X_clean),
            **{f'p_lag{i}': p_values[f'lag{i}'] for i in range(1, maxlag + 1)},
            **{f'f_lag{i}': f_stats[f'lag{i}'] for i in range(1, maxlag + 1)}
        }

    except Exception as e:
        return None

def process_chunk(chunk_pairs, imputed_data, chunk_id):
    """Process a chunk of pairs"""
    results = []

    for idx, row in chunk_pairs.iterrows():
        result = run_granger_test(row['source'], row['target'], imputed_data, MAXLAG)

        if result is not None:
            results.append(result)

    return results

def run_granger_tests_parallel(imputed_data, pairs_df):
    """Run Granger tests with parallel processing and checkpointing

    MEMORY-SAFE VERSION: Saves incremental results to disk, not RAM
    """
    print("=" * 80)
    print("PARALLEL GRANGER CAUSALITY TESTING (MEMORY-SAFE)")
    print("=" * 80)
    print(f"Total pairs: {len(pairs_df):,}")
    print(f"Parallel cores: {N_JOBS}")
    print(f"Max lag: {MAXLAG}")
    print(f"Checkpoint interval: {CHECKPOINT_INTERVAL:,} pairs")
    print()

    # Check for existing checkpoint (progress tracker only, not results)
    checkpoint_file = CHECKPOINT_DIR / "granger_progress_v2.pkl"
    start_idx = 0
    total_successful = 0

    if checkpoint_file.exists():
        print("Found existing checkpoint, resuming...")
        try:
            with open(checkpoint_file, 'rb') as f:
                checkpoint = pickle.load(f)
                start_idx = checkpoint['last_index']
                total_successful = checkpoint['total_successful']
            print(f"✅ Resuming from pair {start_idx:,}")
            print(f"✅ Already completed: {total_successful:,} successful tests")
            print()
        except Exception as e:
            print(f"⚠️  Checkpoint file corrupted, starting from scratch: {e}")
            print()
            start_idx = 0
            total_successful = 0

    # Split remaining pairs into chunks
    remaining_pairs = pairs_df.iloc[start_idx:]
    n_chunks = (len(remaining_pairs) + CHECKPOINT_INTERVAL - 1) // CHECKPOINT_INTERVAL

    print(f"Processing {n_chunks} checkpoints...")
    print()

    start_time = datetime.now()

    for chunk_idx in range(n_chunks):
        chunk_start = chunk_idx * CHECKPOINT_INTERVAL
        chunk_end = min((chunk_idx + 1) * CHECKPOINT_INTERVAL, len(remaining_pairs))

        chunk_pairs = remaining_pairs.iloc[chunk_start:chunk_end]

        chunk_time_start = datetime.now()

        print(f"Checkpoint {chunk_idx + 1}/{n_chunks}: Processing pairs {start_idx + chunk_start:,} - {start_idx + chunk_end:,}")

        # Split chunk into sub-chunks for parallel processing
        sub_chunk_size = len(chunk_pairs) // N_JOBS + 1
        sub_chunks = [chunk_pairs.iloc[i:i+sub_chunk_size] for i in range(0, len(chunk_pairs), sub_chunk_size)]

        # Process in parallel
        chunk_results = Parallel(n_jobs=N_JOBS, verbose=10)(
            delayed(process_chunk)(sub_chunk, imputed_data, i)
            for i, sub_chunk in enumerate(sub_chunks)
        )

        # Flatten chunk results
        chunk_results_flat = []
        for sub_results in chunk_results:
            chunk_results_flat.extend(sub_results)

        # Save chunk results to disk immediately (NOT kept in memory)
        chunk_file = RESULTS_DIR / f"chunk_{start_idx + chunk_start:08d}_{start_idx + chunk_end:08d}.pkl"
        with open(chunk_file, 'wb') as f:
            pickle.dump(chunk_results_flat, f)

        chunk_successful = len(chunk_results_flat)
        total_successful += chunk_successful
        chunk_elapsed = (datetime.now() - chunk_time_start).total_seconds()

        # Save lightweight checkpoint (NO RESULTS, just progress metadata)
        checkpoint = {
            'last_index': start_idx + chunk_end,
            'total_successful': total_successful,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'chunk_files': sorted([f.name for f in RESULTS_DIR.glob("chunk_*.pkl")])
        }

        with open(checkpoint_file, 'wb') as f:
            pickle.dump(checkpoint, f)

        # Progress report
        total_processed = start_idx + chunk_end
        pct_complete = total_processed / len(pairs_df) * 100
        elapsed_total = (datetime.now() - start_time).total_seconds()
        est_remaining = (elapsed_total / (chunk_idx + 1)) * (n_chunks - chunk_idx - 1)

        # Update progress JSON file for external monitoring
        update_progress(
            step="A2_granger",
            pct=pct_complete,
            elapsed_min=elapsed_total / 60,
            eta_min=est_remaining / 60,
            items_done=total_processed,
            items_total=len(pairs_df),
            extra={"successful_tests": total_successful, "chunk": f"{chunk_idx+1}/{n_chunks}"}
        )

        print(f"  ✅ Chunk saved: {chunk_successful:,} successful tests → {chunk_file.name}")
        print(f"  Total successful: {total_successful:,}")
        print(f"  Progress: {total_processed:,} / {len(pairs_df):,} ({pct_complete:.1f}%)")
        print(f"  Chunk time: {chunk_elapsed/60:.1f} min")
        print(f"  Elapsed: {elapsed_total/3600:.2f} hours")
        print(f"  Estimated remaining: {est_remaining/3600:.2f} hours")
        print()

        # Clear chunk results from memory
        del chunk_results
        del chunk_results_flat

    total_elapsed = (datetime.now() - start_time).total_seconds()

    print()
    print(f"✅ Granger testing complete in {total_elapsed/3600:.2f} hours")
    print(f"   Successful tests: {total_successful:,} / {len(pairs_df):,} ({total_successful/len(pairs_df)*100:.1f}%)")
    print()

    return total_successful

def combine_results():
    """Combine incremental chunk files into final output"""
    print("=" * 80)
    print("COMBINING INCREMENTAL RESULTS")
    print("=" * 80)

    chunk_files = sorted(RESULTS_DIR.glob("chunk_*.pkl"))
    print(f"Found {len(chunk_files)} chunk files")
    print()

    all_results = []
    for chunk_file in chunk_files:
        with open(chunk_file, 'rb') as f:
            chunk_results = pickle.load(f)
            all_results.extend(chunk_results)
        print(f"  Loaded {len(chunk_results):,} results from {chunk_file.name}")

    print()
    print(f"✅ Combined {len(all_results):,} total results")
    print()

    return all_results

def save_results(results):
    """Save Granger test results"""
    output_file = A2_OUTPUT / "granger_test_results.pkl"

    print("=" * 80)
    print("SAVING FINAL RESULTS")
    print("=" * 80)

    # Convert to DataFrame
    results_df = pd.DataFrame(results)

    # Add significance flags
    results_df['significant_005'] = results_df['p_value'] < 0.05
    results_df['significant_001'] = results_df['p_value'] < 0.01

    checkpoint = {
        'results': results_df,
        'metadata': {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'n_tests': len(results_df),
            'n_significant_005': results_df['significant_005'].sum(),
            'n_significant_001': results_df['significant_001'].sum(),
            'maxlag': MAXLAG
        }
    }

    with open(output_file, 'wb') as f:
        pickle.dump(checkpoint, f)

    file_size = output_file.stat().st_size / (1024**2)

    print(f"✅ Saved: {output_file}")
    print(f"   Size: {file_size:.1f} MB")
    print(f"   Tests: {len(results_df):,}")
    print(f"   Significant (p<0.05): {results_df['significant_005'].sum():,}")
    print(f"   Significant (p<0.01): {results_df['significant_001'].sum():,}")
    print()

def main():
    print("=" * 80)
    print("A2 STEP 3: GRANGER CAUSALITY TESTING (MEMORY-SAFE)")
    print("=" * 80)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Load data
    imputed_data, pairs_df = load_data()

    # Run Granger tests (saves incremental results to disk)
    total_successful = run_granger_tests_parallel(imputed_data, pairs_df)

    # Combine incremental results
    results = combine_results()

    # Save final results
    save_results(results)

    print("=" * 80)
    print("GRANGER TESTING COMPLETE")
    print("=" * 80)
    print()
    print("Next Step: FDR correction (Benjamini-Hochberg)")
    print("Estimated time: 1 hour")
    print()

if __name__ == "__main__":
    main()
