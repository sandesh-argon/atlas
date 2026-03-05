#!/usr/bin/env python3
"""
A3 Step 1b: Pre-prune to top 100K edges by F-statistic
Rationale: Reduces PC-Stable search space by 92% while retaining strongest signals
"""

import pickle
import pandas as pd
from pathlib import Path

def prune_to_top_edges(n_edges=100000):
    """Select top N edges by Granger F-statistic"""
    print(f"\n{'='*60}")
    print(f"Pre-pruning to top {n_edges:,} edges...")

    # Load A2 results
    a2_file = Path(__file__).parent.parent.parent / "A2_granger_causality" / "outputs" / "granger_fdr_corrected.pkl"

    with open(a2_file, 'rb') as f:
        fdr_data = pickle.load(f)

    # Filter to q<0.01
    edges_df = fdr_data['results']
    significant = edges_df[edges_df['significant_fdr_001']].copy()

    print(f"  Significant edges @ q<0.01: {len(significant):,}")

    # Sort by F-statistic (descending)
    significant = significant.sort_values('f_statistic', ascending=False)

    # Take top N
    top_edges = significant.head(n_edges)

    print(f"  Selected top {len(top_edges):,} edges")
    print(f"  F-statistic range: {top_edges['f_statistic'].min():.2f} - {top_edges['f_statistic'].max():.2f}")
    print(f"  Median F-statistic: {top_edges['f_statistic'].median():.2f}")

    # Save pruned edges
    output_dir = Path(__file__).parent.parent / 'outputs'
    output_dir.mkdir(exist_ok=True)

    output_file = output_dir / 'granger_top_100k.pkl'

    with open(output_file, 'wb') as f:
        pickle.dump({
            'edges': top_edges,
            'n_edges': len(top_edges),
            'pruning_criterion': 'f_statistic',
            'from_total': len(significant)
        }, f)

    print(f"  ✅ Saved: {output_file}")
    print(f"\n{'='*60}")

    return top_edges

if __name__ == '__main__':
    prune_to_top_edges(n_edges=100000)
