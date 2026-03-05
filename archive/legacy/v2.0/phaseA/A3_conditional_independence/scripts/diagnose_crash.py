"""
Safe diagnostic script to identify PC-Stable crash cause

This script will:
1. Test with 1 core (no parallelization) on small sample
2. Monitor memory usage closely
3. Add extensive logging
4. Identify the exact point of failure
"""

import pickle
import pandas as pd
import numpy as np
import psutil
import os
import time
import sys
import traceback
from pathlib import Path
from datetime import datetime

# Setup paths
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
A2_DIR = PROJECT_ROOT / "phaseA" / "A2_granger_causality"
A1_DIR = PROJECT_ROOT / "phaseA" / "A1_missingness_analysis"

A2_FDR_FILE = A2_DIR / "outputs" / "granger_fdr_corrected.pkl"
A1_DATA_FILE = A1_DIR / "outputs" / "A2_preprocessed_data.pkl"

def log_memory(msg):
    """Log memory usage"""
    process = psutil.Process(os.getpid())
    mem_mb = process.memory_info().rss / (1024 * 1024)
    available_mb = psutil.virtual_memory().available / (1024 * 1024)

    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")
    print(f"  Process memory: {mem_mb:.1f} MB")
    print(f"  System available: {available_mb:.1f} MB")
    print(f"  System usage: {psutil.virtual_memory().percent:.1f}%")

    # Warning if getting close to limits
    if mem_mb > 10000:
        print(f"  ⚠️  WARNING: Process using >10 GB")
    if psutil.virtual_memory().percent > 90:
        print(f"  ⚠️  WARNING: System RAM >90%")

    return mem_mb

def safe_load_a2_edges(limit=None):
    """Safely load A2 edges with memory monitoring"""
    print("=" * 80)
    print("STEP 1: Loading A2 Granger Edges")
    print("=" * 80)

    log_memory("Before loading A2 edges")

    try:
        with open(A2_FDR_FILE, 'rb') as f:
            fdr_data = pickle.load(f)

        log_memory("After loading A2 pickle")

        results_df = fdr_data['results']
        log_memory("After extracting results DataFrame")

        edges_q01 = results_df[results_df['significant_fdr_001']].copy()
        log_memory("After filtering to q<0.01")

        if limit:
            edges_q01 = edges_q01.head(limit)
            print(f"Limited to {limit} edges for testing")

        print(f"✓ Loaded {len(edges_q01):,} edges")
        print()

        return edges_q01

    except Exception as e:
        print(f"✗ FAILED to load A2 edges: {e}")
        traceback.print_exc()
        sys.exit(1)

def safe_load_a1_data():
    """Safely load A1 data with memory monitoring"""
    print("=" * 80)
    print("STEP 2: Loading A1 Imputed Data")
    print("=" * 80)

    log_memory("Before loading A1 data")

    try:
        with open(A1_DATA_FILE, 'rb') as f:
            a1_data = pickle.load(f)

        log_memory("After loading A1 pickle")

        imputed_data_dict = a1_data['imputed_data']
        log_memory("After extracting imputed_data dict")

        print(f"Converting {len(imputed_data_dict)} indicators to long format...")

        # Convert in batches to avoid memory spike
        batch_size = 1000
        all_indicators_long = []

        indicator_list = list(imputed_data_dict.items())
        n_batches = (len(indicator_list) + batch_size - 1) // batch_size

        for batch_idx in range(n_batches):
            start_idx = batch_idx * batch_size
            end_idx = min((batch_idx + 1) * batch_size, len(indicator_list))

            batch_indicators = indicator_list[start_idx:end_idx]

            for indicator_name, df in batch_indicators:
                df_long = df.stack().rename(indicator_name).to_frame()
                all_indicators_long.append(df_long)

            if (batch_idx + 1) % 2 == 0:
                log_memory(f"Processed {end_idx}/{len(indicator_list)} indicators")

        print("Concatenating all indicators...")
        imputed_data = pd.concat(all_indicators_long, axis=1)
        log_memory("After concatenating all indicators")

        imputed_data.index.names = ['Country', 'Year']

        print(f"✓ Loaded {len(imputed_data.columns):,} indicators, {len(imputed_data):,} observations")
        print()

        return imputed_data

    except Exception as e:
        print(f"✗ FAILED to load A1 data: {e}")
        traceback.print_exc()
        sys.exit(1)

def safe_test_single_edge(edge, granger_adj, data, alpha=0.001):
    """Test a single edge with memory monitoring"""
    from itertools import combinations
    from scipy.stats import norm

    source = edge['source']
    target = edge['target']

    # Find potential confounders
    x_neighbors = granger_adj.get(source, set())
    y_neighbors = granger_adj.get(target, set())
    potential_confounders = list((x_neighbors & y_neighbors) - {source, target})

    # Test marginal independence first
    cols = [source, target]
    sub_data = data[cols].dropna()

    n = len(sub_data)
    if n < 10:
        return edge  # Not enough data, keep edge

    # Simple correlation
    corr = sub_data.corr().iloc[0, 1]

    # Fisher's Z test
    if abs(corr) >= 0.9999:
        return edge  # Very strong correlation, keep

    z = 0.5 * np.log((1 + corr) / (1 - corr))
    test_stat = abs(z) * np.sqrt(n - 3)
    p_value = 2 * (1 - norm.cdf(test_stat))

    if p_value > alpha:
        return None  # Independent, remove edge

    # Test with conditioning sets (max size 3 for safety)
    for cond_size in range(1, min(len(potential_confounders), 3) + 1):
        for Z_set in combinations(potential_confounders, cond_size):
            # Test conditional independence
            cols = [source, target] + list(Z_set)
            sub_data = data[cols].dropna()

            n = len(sub_data)
            if n < 10 + cond_size:
                continue

            try:
                corr_matrix = sub_data.corr().values
                precision = np.linalg.inv(corr_matrix)
                partial_corr = -precision[0, 1] / np.sqrt(precision[0, 0] * precision[1, 1])

                if abs(partial_corr) >= 0.9999:
                    continue

                z = 0.5 * np.log((1 + partial_corr) / (1 - partial_corr))
                test_stat = abs(z) * np.sqrt(n - cond_size - 3)
                p_value = 2 * (1 - norm.cdf(test_stat))

                if p_value > alpha:
                    return None  # Conditionally independent, remove

            except:
                continue  # Singular matrix or other error, skip

    return edge  # Keep edge

def test_with_n_cores(edges_df, data, n_cores, sample_size=100):
    """Test PC-Stable with specific number of cores"""
    print("=" * 80)
    print(f"STEP 3: Testing with {n_cores} core(s) - {sample_size} edges")
    print("=" * 80)

    log_memory(f"Before processing with {n_cores} cores")

    # Build adjacency graph
    granger_adj = {}
    for _, row in edges_df.iterrows():
        source, target = row['source'], row['target']

        if source not in granger_adj:
            granger_adj[source] = set()
        if target not in granger_adj:
            granger_adj[target] = set()

        granger_adj[source].add(target)
        granger_adj[target].add(source)

    log_memory("After building adjacency graph")

    edges_to_test = edges_df.to_dict('records')

    print(f"Testing {len(edges_to_test)} edges...")
    start_time = time.time()

    try:
        if n_cores == 1:
            # Sequential processing
            validated = []
            for i, edge in enumerate(edges_to_test):
                result = safe_test_single_edge(edge, granger_adj, data)
                if result is not None:
                    validated.append(result)

                if (i + 1) % 20 == 0:
                    log_memory(f"Processed {i+1}/{len(edges_to_test)} edges")

        else:
            # Parallel processing
            from joblib import Parallel, delayed

            print(f"Starting parallel processing with {n_cores} cores...")

            results = Parallel(n_jobs=n_cores, backend='threading', verbose=10)(
                delayed(safe_test_single_edge)(edge, granger_adj, data)
                for edge in edges_to_test
            )

            validated = [r for r in results if r is not None]

        elapsed = time.time() - start_time

        log_memory("After processing complete")

        print()
        print(f"✓ Completed in {elapsed:.2f} seconds")
        print(f"  Validated: {len(validated)}/{len(edges_to_test)} edges")
        print(f"  Reduction: {(1 - len(validated)/len(edges_to_test))*100:.2f}%")
        print(f"  Rate: {len(edges_to_test)/elapsed:.1f} edges/sec")
        print()

        return True

    except Exception as e:
        print(f"\n✗ CRASHED with {n_cores} cores: {e}")
        traceback.print_exc()
        log_memory("At crash point")
        return False

def main():
    print("\n")
    print("=" * 80)
    print("PC-STABLE CRASH DIAGNOSTIC")
    print("=" * 80)
    print("\n")

    # Load data with small sample
    edges_df = safe_load_a2_edges(limit=100)
    data = safe_load_a1_data()

    print("\n")
    print("=" * 80)
    print("RUNNING TESTS WITH DIFFERENT CORE COUNTS")
    print("=" * 80)
    print("\n")

    # Test with 1 core first
    success_1 = test_with_n_cores(edges_df, data, n_cores=1, sample_size=100)

    if not success_1:
        print("\n⚠️  FAILED WITH 1 CORE - Fundamental issue, not parallelization")
        sys.exit(1)

    print("\n✓ 1 core test PASSED\n")
    time.sleep(2)

    # Test with 4 cores
    success_4 = test_with_n_cores(edges_df, data, n_cores=4, sample_size=100)

    if not success_4:
        print("\n⚠️  FAILED WITH 4 CORES - Parallelization issue detected")
        sys.exit(1)

    print("\n✓ 4 cores test PASSED\n")
    time.sleep(2)

    # Test with 8 cores
    success_8 = test_with_n_cores(edges_df, data, n_cores=8, sample_size=100)

    if not success_8:
        print("\n⚠️  FAILED WITH 8 CORES - Higher parallelization issue")
        sys.exit(1)

    print("\n✓ 8 cores test PASSED\n")

    print("=" * 80)
    print("ALL DIAGNOSTIC TESTS PASSED ✓")
    print("=" * 80)
    print("\nSafe to proceed with 10 cores on full dataset")
    print("=" * 80)

if __name__ == "__main__":
    main()
