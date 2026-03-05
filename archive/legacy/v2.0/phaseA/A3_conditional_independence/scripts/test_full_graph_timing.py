#!/usr/bin/env python3
"""
Test runtime estimate for causallearn PC-Stable on FULL 1.16M edges
Runs on small sample (1K, 5K, 10K edges) to extrapolate timing
"""

import pickle
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime
import time
from causallearn.search.ConstraintBased.PC import pc

def load_full_edges():
    """Load full 1.16M edges @ q<0.01"""
    print(f"\n{'='*60}")
    print("Loading FULL A2 edges (1.16M)...")

    a2_file = Path(__file__).parent.parent.parent / "A2_granger_causality" / "outputs" / "granger_fdr_corrected.pkl"

    with open(a2_file, 'rb') as f:
        fdr_data = pickle.load(f)

    edges_df = fdr_data['results']
    significant = edges_df[edges_df['significant_fdr_001']].copy()

    print(f"  Loaded {len(significant):,} edges")

    return significant

def load_imputed_data():
    """Load A1 imputed data"""
    print(f"\n{'='*60}")
    print("Loading A1 imputed data...")

    a1_file = Path(__file__).parent.parent.parent / 'A1_missingness_analysis' / 'outputs' / 'A2_preprocessed_data.pkl'

    with open(a1_file, 'rb') as f:
        a1_data = pickle.load(f)

    imputed_data = a1_data['imputed_data']
    print(f"  Loaded {len(imputed_data):,} indicators")

    return imputed_data

def prepare_data_matrix(imputed_data, edges_df, max_indicators=None):
    """Build data matrix for PC-Stable"""
    print(f"\n{'='*60}")
    print("Preparing data matrix...")

    # Get indicators involved in edges
    active_indicators = sorted(set(edges_df['source'].unique()) | set(edges_df['target'].unique()))

    if max_indicators and len(active_indicators) > max_indicators:
        active_indicators = active_indicators[:max_indicators]
        print(f"  Limiting to {max_indicators} indicators for test")

    print(f"  Active indicators: {len(active_indicators):,}")

    # Build panel data
    all_data = []
    indicator_names = []

    for idx, indicator in enumerate(active_indicators):
        if indicator not in imputed_data:
            continue

        df = imputed_data[indicator]
        stacked = df.stack().reset_index()
        stacked.columns = ['Country', 'Year', indicator]

        if len(all_data) == 0:
            all_data = stacked
        else:
            all_data = all_data.merge(stacked, on=['Country', 'Year'], how='outer')

        indicator_names.append(indicator)

        if (idx + 1) % 200 == 0:
            print(f"  Processed {idx+1}/{len(active_indicators)}")

    # Drop incomplete observations
    all_data = all_data.dropna()

    print(f"  Complete observations: {len(all_data):,}")
    print(f"  Final indicators: {len(indicator_names):,}")

    # Extract data matrix
    data_matrix = all_data[indicator_names].values

    print(f"  Data matrix shape: {data_matrix.shape}")
    print(f"  Memory: {data_matrix.nbytes / 1e9:.2f} GB")

    return data_matrix, indicator_names

def test_pc_timing(data_matrix, indicator_names, test_name, alpha=0.001):
    """Run PC-Stable and time it"""
    print(f"\n{'='*60}")
    print(f"TEST: {test_name}")
    print(f"  Variables: {data_matrix.shape[1]}")
    print(f"  Observations: {data_matrix.shape[0]}")
    print(f"  Alpha: {alpha}")
    print(f"\n⏱️  Starting at {datetime.now().strftime('%H:%M:%S')}")
    print(f"{'='*60}\n")

    start = time.time()

    try:
        cg = pc(
            data_matrix,
            alpha=alpha,
            indep_test='fisherz',
            stable=True,
            uc_rule=1,
            uc_priority=3,
            mvpc=False,
            correction_name='MV',
            verbose=False,  # Suppress verbose output for timing
            show_progress=False
        )

        elapsed = time.time() - start

        print(f"\n✅ COMPLETED")
        print(f"  Runtime: {elapsed:.2f} seconds ({elapsed/60:.2f} minutes)")
        print(f"  Output edges: {len(cg.G.get_graph_edges())}")
        print(f"  Output nodes: {cg.G.get_num_nodes()}")

        return elapsed, len(cg.G.get_graph_edges())

    except Exception as e:
        print(f"\n❌ FAILED: {e}")
        return None, None

def extrapolate_full_runtime(test_results):
    """Extrapolate runtime for full graph"""
    print(f"\n{'='*80}")
    print("EXTRAPOLATION TO FULL 1.16M EDGES")
    print(f"{'='*80}\n")

    # PC-Stable complexity is roughly O(V^2 * E) where V=variables, E=edges
    # But practically more like O(V * E^1.5) due to adaptive pruning

    for test_name, (n_vars, runtime_sec, output_edges) in test_results.items():
        if runtime_sec is None:
            continue

        print(f"{test_name}:")
        print(f"  Variables: {n_vars}")
        print(f"  Runtime: {runtime_sec:.1f} sec ({runtime_sec/60:.1f} min)")
        print(f"  Output edges: {output_edges}")

        # Extrapolate to full graph
        # Assume full graph has ~5,500 variables (from full edge set)
        full_vars = 5500

        # Linear extrapolation (conservative)
        linear_multiplier = full_vars / n_vars
        linear_estimate_hours = (runtime_sec * linear_multiplier) / 3600

        # Quadratic extrapolation (pessimistic)
        quad_multiplier = (full_vars / n_vars) ** 2
        quad_estimate_hours = (runtime_sec * quad_multiplier) / 3600

        # Power 1.5 extrapolation (realistic for PC-Stable)
        power_multiplier = (full_vars / n_vars) ** 1.5
        power_estimate_hours = (runtime_sec * power_multiplier) / 3600

        print(f"\n  Extrapolation to {full_vars} variables:")
        print(f"    Linear (O(V)):     {linear_estimate_hours:.1f} hours")
        print(f"    Power 1.5 (O(V^1.5)): {power_estimate_hours:.1f} hours")
        print(f"    Quadratic (O(V^2)): {quad_estimate_hours:.1f} hours")
        print(f"\n  REALISTIC ESTIMATE: {power_estimate_hours:.1f} - {quad_estimate_hours:.1f} hours")
        print(f"  ({power_estimate_hours/24:.1f} - {quad_estimate_hours/24:.1f} days)")
        print()

def main():
    """Main test pipeline"""
    print("\n" + "="*80)
    print("PC-STABLE FULL GRAPH TIMING TEST")
    print("="*80)
    print("\nThis will test causallearn on samples to estimate full 1.16M edge runtime")
    print()

    # Load data
    edges_df = load_full_edges()
    imputed_data = load_imputed_data()

    # Test scenarios
    test_results = {}

    # Test 1: 500 variables (quick test - ~2-5 min)
    print(f"\n{'='*80}")
    print("TEST 1: 500 variables (~5% of full graph)")
    print(f"{'='*80}")

    data_matrix_500, indicator_names_500 = prepare_data_matrix(
        imputed_data, edges_df, max_indicators=500
    )

    runtime_500, edges_500 = test_pc_timing(
        data_matrix_500, indicator_names_500, "500 Variables", alpha=0.001
    )

    test_results["500 vars"] = (500, runtime_500, edges_500)

    # Test 2: 1000 variables (medium test - ~10-20 min)
    print(f"\n{'='*80}")
    print("TEST 2: 1000 variables (~18% of full graph)")
    print(f"{'='*80}")

    data_matrix_1000, indicator_names_1000 = prepare_data_matrix(
        imputed_data, edges_df, max_indicators=1000
    )

    runtime_1000, edges_1000 = test_pc_timing(
        data_matrix_1000, indicator_names_1000, "1000 Variables", alpha=0.001
    )

    test_results["1000 vars"] = (1000, runtime_1000, edges_1000)

    # Test 3: 2000 variables (large test - ~40-80 min)
    print(f"\n{'='*80}")
    print("TEST 3: 2000 variables (~36% of full graph)")
    print(f"{'='*80}")

    data_matrix_2000, indicator_names_2000 = prepare_data_matrix(
        imputed_data, edges_df, max_indicators=2000
    )

    runtime_2000, edges_2000 = test_pc_timing(
        data_matrix_2000, indicator_names_2000, "2000 Variables", alpha=0.001
    )

    test_results["2000 vars"] = (2000, runtime_2000, edges_2000)

    # Extrapolate
    extrapolate_full_runtime(test_results)

    print(f"\n{'='*80}")
    print("TEST COMPLETE")
    print(f"{'='*80}\n")

    # Save results
    output_file = Path(__file__).parent.parent / 'outputs' / 'timing_test_results.pkl'
    with open(output_file, 'wb') as f:
        pickle.dump(test_results, f)

    print(f"Results saved to: {output_file}")

if __name__ == '__main__':
    main()
