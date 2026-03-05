#!/usr/bin/env python3
"""
A2 Step 4: FDR Correction (Benjamini-Hochberg)
================================================
Applies multiple testing correction to Granger causality results.

Input: 9.2M Granger test results with raw p-values
Output: FDR-corrected significant edges at q<0.05 and q<0.01
"""

import pandas as pd
import numpy as np
import pickle
from pathlib import Path
import sys
from datetime import datetime
from statsmodels.stats.multitest import multipletests

# V2.1 Configuration - import paths from config
sys.path.insert(0, str(Path(__file__).parent.parent))
from v21_config import A2_OUTPUT

A2_OUTPUT.mkdir(exist_ok=True, parents=True)

# Input file
GRANGER_RESULTS = A2_OUTPUT / "granger_test_results.pkl"

def load_granger_results():
    """Load Granger test results"""
    print("=" * 80)
    print("LOADING GRANGER TEST RESULTS")
    print("=" * 80)

    with open(GRANGER_RESULTS, 'rb') as f:
        data = pickle.load(f)

    results_df = data['results']
    metadata = data['metadata']

    print(f"✅ Loaded {len(results_df):,} Granger test results")
    print(f"   Tests from: {metadata['timestamp']}")
    print(f"   Max lag: {metadata['maxlag']}")
    print()
    print(f"Raw p-value statistics:")
    print(f"  p<0.05: {metadata['n_significant_005']:,} ({metadata['n_significant_005']/len(results_df)*100:.1f}%)")
    print(f"  p<0.01: {metadata['n_significant_001']:,} ({metadata['n_significant_001']/len(results_df)*100:.1f}%)")
    print()

    return results_df, metadata

def apply_fdr_correction(results_df, alpha=0.05):
    """Apply Benjamini-Hochberg FDR correction"""
    print("=" * 80)
    print("APPLYING FDR CORRECTION (BENJAMINI-HOCHBERG)")
    print("=" * 80)

    p_values = results_df['p_value'].values

    print(f"Input tests: {len(p_values):,}")
    print(f"Alpha level: {alpha}")
    print()

    # Apply Benjamini-Hochberg correction
    print("Running Benjamini-Hochberg procedure...")
    reject, pvals_corrected, alphacSidak, alphacBonf = multipletests(
        p_values,
        alpha=alpha,
        method='fdr_bh',
        is_sorted=False,
        returnsorted=False
    )

    print(f"✅ FDR correction complete")
    print()

    # Add corrected values to dataframe
    results_df = results_df.copy()
    results_df['p_value_fdr'] = pvals_corrected
    results_df['significant_fdr_005'] = reject  # Reject null at alpha=0.05
    results_df['significant_fdr_001'] = pvals_corrected < 0.01  # Stricter threshold

    # Statistics
    n_significant_005 = reject.sum()
    n_significant_001 = results_df['significant_fdr_001'].sum()

    print(f"Results after FDR correction:")
    print(f"  q<0.05: {n_significant_005:,} ({n_significant_005/len(results_df)*100:.1f}%)")
    print(f"  q<0.01: {n_significant_001:,} ({n_significant_001/len(results_df)*100:.1f}%)")
    print()

    # Reduction stats
    raw_005 = results_df['significant_005'].sum()
    raw_001 = results_df['significant_001'].sum()

    reduction_005 = (raw_005 - n_significant_005) / raw_005 * 100
    reduction_001 = (raw_001 - n_significant_001) / raw_001 * 100

    print(f"Reduction from raw p-values:")
    print(f"  α=0.05: {raw_005:,} → {n_significant_005:,} ({reduction_005:.1f}% reduction)")
    print(f"  α=0.01: {raw_001:,} → {n_significant_001:,} ({reduction_001:.1f}% reduction)")
    print()

    return results_df, n_significant_005, n_significant_001

def extract_significant_edges(results_df, alpha=0.05):
    """Extract FDR-significant edges"""
    print("=" * 80)
    print("EXTRACTING SIGNIFICANT EDGES")
    print("=" * 80)

    # Filter for q<0.05
    significant_df = results_df[results_df['significant_fdr_005']].copy()

    print(f"Significant edges (q<{alpha}): {len(significant_df):,}")
    print()

    # Sort by FDR-corrected p-value
    significant_df = significant_df.sort_values('p_value_fdr')

    # Statistics
    print(f"Distribution of significant edges:")
    print(f"  Best lag 1: {(significant_df['best_lag'] == 1).sum():,}")
    print(f"  Best lag 2: {(significant_df['best_lag'] == 2).sum():,}")
    print(f"  Best lag 3: {(significant_df['best_lag'] == 3).sum():,}")
    print(f"  Best lag 4: {(significant_df['best_lag'] == 4).sum():,}")
    print(f"  Best lag 5: {(significant_df['best_lag'] == 5).sum():,}")
    print()

    print(f"Top 10 most significant edges:")
    for idx, row in significant_df.head(10).iterrows():
        print(f"  {row['source']:40s} → {row['target']:40s} (lag={row['best_lag']}, q={row['p_value_fdr']:.2e})")
    print()

    return significant_df

def save_results(results_df, significant_df, metadata, n_sig_005, n_sig_001):
    """Save FDR-corrected results"""
    print("=" * 80)
    print("SAVING RESULTS")
    print("=" * 80)

    # Save full results with FDR corrections
    full_output = A2_OUTPUT / "granger_fdr_corrected.pkl"

    full_checkpoint = {
        'results': results_df,
        'metadata': {
            **metadata,
            'fdr_timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'n_significant_fdr_005': n_sig_005,
            'n_significant_fdr_001': n_sig_001,
            'fdr_method': 'Benjamini-Hochberg'
        }
    }

    with open(full_output, 'wb') as f:
        pickle.dump(full_checkpoint, f)

    full_size = full_output.stat().st_size / (1024**2)
    print(f"✅ Saved full results: {full_output}")
    print(f"   Size: {full_size:.1f} MB")
    print()

    # Save significant edges only (for next step)
    sig_output = A2_OUTPUT / "significant_edges_fdr.pkl"

    sig_checkpoint = {
        'edges': significant_df,
        'metadata': {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'n_edges': len(significant_df),
            'n_fdr_001': n_sig_001,
            'alpha': 0.05,
            'method': 'Benjamini-Hochberg FDR'
        }
    }

    with open(sig_output, 'wb') as f:
        pickle.dump(sig_checkpoint, f)

    sig_size = sig_output.stat().st_size / (1024**2)
    print(f"✅ Saved significant edges: {sig_output}")
    print(f"   Size: {sig_size:.1f} MB")
    print(f"   Edges: {len(significant_df):,}")
    print()

def main():
    print("=" * 80)
    print("A2 STEP 4: FDR CORRECTION (BENJAMINI-HOCHBERG)")
    print("=" * 80)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Load Granger results
    results_df, metadata = load_granger_results()

    # Apply FDR correction
    results_df, n_sig_005, n_sig_001 = apply_fdr_correction(results_df, alpha=0.05)

    # Extract significant edges
    significant_df = extract_significant_edges(results_df, alpha=0.05)

    # Save results
    save_results(results_df, significant_df, metadata, n_sig_005, n_sig_001)

    print("=" * 80)
    print("FDR CORRECTION COMPLETE")
    print("=" * 80)
    print()
    print(f"Summary:")
    print(f"  Total tests: {len(results_df):,}")
    print(f"  Raw significant (p<0.05): {metadata['n_significant_005']:,}")
    print(f"  FDR significant (q<0.05): {n_sig_005:,}")
    print(f"  FDR significant (q<0.01): {n_sig_001:,}")
    print()
    print("Next Step: Bootstrap validation")
    print("Estimated time: 2-4 hours")
    print()

if __name__ == "__main__":
    main()
