#!/usr/bin/env python3
"""
Validation 1: Pairwise Deletion Consistency Check

Verifies that pairwise deletion didn't create statistical artifacts
by checking consistency of independence judgments across different conditioning sets.
"""

import pickle
import pandas as pd
import numpy as np
from pathlib import Path
from scipy.stats import pearsonr, norm
from itertools import combinations
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def fisher_z_test(partial_r, n, alpha=0.001):
    """Fisher-Z test for partial correlation significance"""
    if abs(partial_r) > 0.999:
        partial_r = 0.999 * np.sign(partial_r)

    z = 0.5 * np.log((1 + partial_r) / (1 - partial_r))
    se = 1 / np.sqrt(n - 3)
    z_stat = abs(z / se)
    p_value = 2 * (1 - norm.cdf(z_stat))

    is_independent = (p_value > alpha)
    return is_independent, p_value

def compute_partial_correlation(x, y, z):
    """Compute partial correlation: corr(X, Y | Z)"""
    r_xy, _ = pearsonr(x, y)
    r_xz, _ = pearsonr(x, z)
    r_yz, _ = pearsonr(y, z)

    numerator = r_xy - (r_xz * r_yz)
    denominator = np.sqrt((1 - r_xz**2) * (1 - r_yz**2))

    if denominator < 1e-10:
        return 0.0

    return numerator / denominator

def load_data():
    """Load A3 outputs and A2 preprocessed data"""
    logger.info("Loading A3 final DAG and A2 data...")

    # Load final DAG
    with open('../outputs/A3_final_dag.pkl', 'rb') as f:
        a3_data = pickle.load(f)

    # Load PC-Stable validated edges (before cycle removal)
    with open('../outputs/A3_validated_fisher_z_alpha_0.001.pkl', 'rb') as f:
        pc_data = pickle.load(f)

    # Load A2 preprocessed data
    with open('../../A2_granger_causality/outputs/A2_preprocessed_data.pkl', 'rb') as f:
        a2_data = pickle.load(f)

    return a3_data, pc_data, a2_data

def get_conditioning_sets(edge_info, removed_edges_df):
    """
    Infer conditioning sets used during PC-Stable testing
    by checking which confounders removed similar edges
    """
    # This is an approximation since we didn't save conditioning sets
    # We'll use the removed_edges_df to infer which confounders were tested

    if 'confounder' not in removed_edges_df.columns:
        return []

    source = edge_info['source']
    target = edge_info['target']

    # Find edges with same source/target that were removed
    similar_removed = removed_edges_df[
        (removed_edges_df['source'] == source) &
        (removed_edges_df['target'] == target)
    ]

    if len(similar_removed) > 0 and 'confounder' in similar_removed.columns:
        return similar_removed['confounder'].tolist()

    return []

def validate_consistency(final_edges, data_dict, sample_size=100):
    """
    Sample edges and verify consistency across different conditioning sets
    """
    logger.info("="*80)
    logger.info("VALIDATION 1: PAIRWISE DELETION CONSISTENCY")
    logger.info("="*80)

    # Sample random edges
    if len(final_edges) > sample_size:
        sample_edges = final_edges.sample(sample_size, random_state=42)
    else:
        sample_edges = final_edges

    logger.info(f"Testing {len(sample_edges)} sampled edges...")

    results = []

    for idx, edge in sample_edges.iterrows():
        X = edge['source']
        Y = edge['target']

        # Get data
        if X not in data_dict or Y not in data_dict:
            continue

        x_series = data_dict[X]
        y_series = data_dict[Y]

        # Get pairwise data (X, Y only)
        df_pair = pd.DataFrame({'X': x_series, 'Y': y_series}).dropna()

        if len(df_pair) < 30:
            continue

        # Find potential confounders (other variables with high correlation)
        confounders = []
        for Z in list(data_dict.keys())[:50]:  # Test first 50 variables as confounders
            if Z == X or Z == Y:
                continue

            z_series = data_dict[Z]
            df_temp = pd.DataFrame({'X': x_series, 'Z': z_series}).dropna()

            if len(df_temp) < 30:
                continue

            r_xz, _ = pearsonr(df_temp['X'], df_temp['Z'])
            if abs(r_xz) > 0.3:  # Potential confounder
                confounders.append(Z)
                if len(confounders) >= 5:
                    break

        if len(confounders) < 2:
            continue

        # Test consistency across different conditioning sets
        test_results = []
        sample_sizes = []

        for Z in confounders[:3]:
            z_series = data_dict[Z]
            df_cond = pd.DataFrame({
                'X': x_series,
                'Y': y_series,
                'Z': z_series
            }).dropna()

            if len(df_cond) < 30:
                continue

            partial_r = compute_partial_correlation(
                df_cond['X'].values,
                df_cond['Y'].values,
                df_cond['Z'].values
            )

            is_independent, p_value = fisher_z_test(partial_r, len(df_cond), alpha=0.001)

            test_results.append(is_independent)
            sample_sizes.append(len(df_cond))

        if len(test_results) < 2:
            continue

        # Check consistency
        consistent = len(set(test_results)) == 1  # All same result

        # Calculate sample size variability
        if len(sample_sizes) > 1:
            size_range = max(sample_sizes) - min(sample_sizes)
            size_ratio = max(sample_sizes) / min(sample_sizes) if min(sample_sizes) > 0 else 0
        else:
            size_range = 0
            size_ratio = 1.0

        # Calculate data overlap
        overlap_pct = min(sample_sizes) / max(sample_sizes) * 100 if max(sample_sizes) > 0 else 0

        results.append({
            'source': X,
            'target': Y,
            'consistent': consistent,
            'n_tests': len(test_results),
            'sample_sizes': sample_sizes,
            'size_ratio': size_ratio,
            'overlap_pct': overlap_pct
        })

    return pd.DataFrame(results)

def main():
    logger.info("\n" + "="*80)
    logger.info("A3 VALIDATION 1: PAIRWISE DELETION CONSISTENCY CHECK")
    logger.info("="*80)

    # Load data
    a3_data, pc_data, a2_data = load_data()

    final_edges = a3_data['edges']
    data_dict = a2_data['data_dict']

    logger.info(f"\nFinal edges: {len(final_edges):,}")
    logger.info(f"Variables in data: {len(data_dict):,}")

    # Run consistency validation
    results_df = validate_consistency(final_edges, data_dict, sample_size=100)

    logger.info("\n" + "="*80)
    logger.info("CONSISTENCY RESULTS")
    logger.info("="*80)

    if len(results_df) == 0:
        logger.warning("⚠️  No edges could be tested (insufficient confounders)")
        return

    consistent_pct = (results_df['consistent'].sum() / len(results_df)) * 100
    mean_overlap = results_df['overlap_pct'].mean()

    logger.info(f"\nEdges tested: {len(results_df)}")
    logger.info(f"Consistent judgments: {results_df['consistent'].sum()} / {len(results_df)} ({consistent_pct:.1f}%)")
    logger.info(f"Mean data overlap: {mean_overlap:.1f}%")

    # Flag problematic edges
    inconsistent = results_df[~results_df['consistent']]
    low_overlap = results_df[results_df['overlap_pct'] < 50]

    logger.info(f"\nInconsistent edges: {len(inconsistent)} ({len(inconsistent)/len(results_df)*100:.1f}%)")
    logger.info(f"Low overlap (<50%): {len(low_overlap)} ({len(low_overlap)/len(results_df)*100:.1f}%)")

    # Sample size statistics
    all_sizes = [s for sizes in results_df['sample_sizes'] for s in sizes]
    logger.info(f"\nSample size statistics:")
    logger.info(f"  Mean: {np.mean(all_sizes):.0f}")
    logger.info(f"  Median: {np.median(all_sizes):.0f}")
    logger.info(f"  Min: {np.min(all_sizes):.0f}")
    logger.info(f"  Max: {np.max(all_sizes):.0f}")

    # Validation thresholds
    logger.info("\n" + "="*80)
    logger.info("VALIDATION ASSESSMENT")
    logger.info("="*80)

    passes = []

    if consistent_pct >= 95:
        logger.info("✅ PASS: Consistency ≥95%")
        passes.append(True)
    elif consistent_pct >= 90:
        logger.info("⚠️  WARNING: Consistency 90-95% (acceptable but borderline)")
        passes.append(True)
    else:
        logger.info(f"❌ FAIL: Consistency <90% ({consistent_pct:.1f}%)")
        passes.append(False)

    if mean_overlap >= 60:
        logger.info("✅ PASS: Mean overlap ≥60%")
        passes.append(True)
    elif mean_overlap >= 50:
        logger.info("⚠️  WARNING: Mean overlap 50-60% (acceptable but low)")
        passes.append(True)
    else:
        logger.info(f"❌ FAIL: Mean overlap <50% ({mean_overlap:.1f}%)")
        passes.append(False)

    logger.info("\n" + "="*80)

    if all(passes):
        logger.info("✅ VALIDATION 1: PASSED")
        logger.info("Pairwise deletion is statistically consistent.")
    else:
        logger.info("❌ VALIDATION 1: FAILED")
        logger.info("Pairwise deletion may have introduced statistical artifacts.")
        logger.info("\nRecommendation: Add data stability filter (remove edges with <50% overlap)")

    logger.info("="*80)

    # Save results
    output_file = Path('../diagnostics/validation1_pairwise_consistency.pkl')
    output_file.parent.mkdir(exist_ok=True)

    validation_output = {
        'results': results_df,
        'summary': {
            'edges_tested': len(results_df),
            'consistent_pct': consistent_pct,
            'mean_overlap': mean_overlap,
            'passed': all(passes)
        }
    }

    with open(output_file, 'wb') as f:
        pickle.dump(validation_output, f)

    logger.info(f"\n✅ Saved: {output_file}")

if __name__ == '__main__':
    main()
