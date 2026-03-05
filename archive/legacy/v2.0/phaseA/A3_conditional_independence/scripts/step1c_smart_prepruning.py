#!/usr/bin/env python3
"""
A3 Step 1c: Smart Pre-Pruning
Intelligently reduce 1.16M edges to 50K-100K high-confidence edges
Based on: FDR q-value, F-statistic, and correlation strength
"""

import pickle
import pandas as pd
import numpy as np
from pathlib import Path
import argparse

def smart_prepruning(input_file, fdr_cutoff=0.001, f_stat_min=10.0, corr_min=0.30):
    """
    Apply intelligent filters to keep only high-confidence Granger edges

    Filters:
    1. Stricter FDR: q < 0.001 (vs 0.01)
    2. Strong predictive power: F-statistic > 10
    3. Strong association: |correlation| > 0.30
    """
    print(f"\n{'='*80}")
    print("A3 SMART PRE-PRUNING")
    print(f"{'='*80}\n")

    # Load A2 results
    print(f"Loading A2 Granger edges...")
    with open(input_file, 'rb') as f:
        fdr_data = pickle.load(f)

    edges_df = fdr_data['results']

    # Starting point
    initial_q01 = edges_df[edges_df['significant_fdr_001']].copy()
    print(f"  Starting edges (q<0.01): {len(initial_q01):,}")

    # Apply smart filters
    print(f"\nApplying smart filters:")
    print(f"  1. FDR p-value < {fdr_cutoff}")
    print(f"  2. F-statistic > {f_stat_min}")
    print(f"  Note: Skipping correlation filter (not available in A2 output)")

    high_confidence = edges_df[
        (edges_df['p_value_fdr'] < fdr_cutoff) &
        (edges_df['f_statistic'] > f_stat_min)
    ].copy()

    print(f"\n{'='*80}")
    print("PRUNING RESULTS")
    print(f"{'='*80}\n")

    print(f"Input edges (q<0.01):     {len(initial_q01):,}")
    print(f"Output edges (filtered):  {len(high_confidence):,}")
    print(f"Reduction:                {(1 - len(high_confidence)/len(initial_q01))*100:.1f}%")

    # Statistics
    print(f"\nEdge Statistics:")
    print(f"  F-statistic range:  {high_confidence['f_statistic'].min():.2f} - {high_confidence['f_statistic'].max():.2f}")
    print(f"  F-statistic median: {high_confidence['f_statistic'].median():.2f}")
    print(f"  FDR p-value range:  {high_confidence['p_value_fdr'].min():.2e} - {high_confidence['p_value_fdr'].max():.2e}")
    print(f"  FDR p-value median: {high_confidence['p_value_fdr'].median():.2e}")

    # Check target range
    print(f"\n{'='*80}")
    if 50_000 <= len(high_confidence) <= 100_000:
        print("✅ OUTPUT IN TARGET RANGE (50K-100K)")
    elif len(high_confidence) < 50_000:
        print(f"⚠️  OUTPUT BELOW TARGET ({len(high_confidence):,} < 50K)")
        print("   Consider relaxing filters:")
        print(f"     - FDR q-value < 0.005 (instead of {fdr_cutoff})")
        print(f"     - F-statistic > 8 (instead of {f_stat_min})")
        print(f"     - |Correlation| > 0.25 (instead of {corr_min})")
    else:
        print(f"⚠️  OUTPUT ABOVE TARGET ({len(high_confidence):,} > 100K)")
        print("   Consider stricter filters:")
        print(f"     - FDR q-value < 0.0005 (instead of {fdr_cutoff})")
        print(f"     - F-statistic > 12 (instead of {f_stat_min})")
        print(f"     - |Correlation| > 0.35 (instead of {corr_min})")
    print(f"{'='*80}\n")

    # Domain coverage check (if domain info available)
    print("Checking variable coverage...")
    unique_sources = high_confidence['source'].nunique()
    unique_targets = high_confidence['target'].nunique()
    unique_vars = len(set(high_confidence['source'].unique()) | set(high_confidence['target'].unique()))

    print(f"  Unique sources: {unique_sources:,}")
    print(f"  Unique targets: {unique_targets:,}")
    print(f"  Total variables: {unique_vars:,}")

    # Save results
    output_dir = Path(__file__).parent.parent / 'outputs'
    output_file = output_dir / 'smart_prepruned_edges.pkl'

    output_data = {
        'edges': high_confidence,
        'metadata': {
            'n_edges': len(high_confidence),
            'filters': {
                'fdr_cutoff': fdr_cutoff,
                'f_stat_min': f_stat_min,
                'corr_min': corr_min
            },
            'statistics': {
                'f_stat_min': float(high_confidence['f_statistic'].min()),
                'f_stat_max': float(high_confidence['f_statistic'].max()),
                'f_stat_median': float(high_confidence['f_statistic'].median()),
                'fdr_pval_min': float(high_confidence['p_value_fdr'].min()),
                'fdr_pval_max': float(high_confidence['p_value_fdr'].max()),
                'fdr_pval_median': float(high_confidence['p_value_fdr'].median()),
            },
            'coverage': {
                'unique_sources': unique_sources,
                'unique_targets': unique_targets,
                'total_variables': unique_vars
            }
        }
    }

    with open(output_file, 'wb') as f:
        pickle.dump(output_data, f)

    print(f"\n✅ Saved to: {output_file}")
    print(f"\n{'='*80}\n")

    return high_confidence

def main():
    parser = argparse.ArgumentParser(description='Smart pre-pruning of Granger edges')
    parser.add_argument('--fdr_cutoff', type=float, default=0.001,
                       help='FDR q-value cutoff (default: 0.001)')
    parser.add_argument('--f_stat_min', type=float, default=10.0,
                       help='Minimum F-statistic (default: 10.0)')
    parser.add_argument('--corr_min', type=float, default=0.30,
                       help='Minimum |correlation| (default: 0.30)')

    args = parser.parse_args()

    # Input file (fixed path relative to script)
    input_file = Path(__file__).parent.parent.parent / 'A2_granger_causality' / 'outputs' / 'granger_fdr_corrected.pkl'

    # Run pruning
    smart_prepruning(
        input_file=input_file,
        fdr_cutoff=args.fdr_cutoff,
        f_stat_min=args.f_stat_min,
        corr_min=args.corr_min
    )

if __name__ == '__main__':
    main()
