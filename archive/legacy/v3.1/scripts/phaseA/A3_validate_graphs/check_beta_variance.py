"""
Critical Validation #4: Cross-Country Beta Variance

For each edge in V2.1, check how much country betas vary.

Low variance = edge is stable across countries (good)
High variance = edge is country-specific (investigate)
"""

import json
import pandas as pd
import numpy as np
from pathlib import Path


def check_beta_variance():
    """
    For each V2.1 edge, compute:
    - Mean beta across countries
    - Std dev of beta
    - Coefficient of variation (CV = std/|mean|)

    Flag edges with CV > 1.0 (high variance).
    """
    # Collect country betas for each edge
    edge_betas = {}

    graph_dir = Path('data/country_graphs')
    graph_files = [f for f in graph_dir.glob('*.json')
                   if f.stem not in ['progress', 'estimation_progress']]

    for graph_file in graph_files:
        with open(graph_file) as f:
            graph = json.load(f)

        for edge in graph['edges']:
            if edge.get('data_available', True):
                edge_key = (edge['source'], edge['target'])

                if edge_key not in edge_betas:
                    edge_betas[edge_key] = []

                edge_betas[edge_key].append(edge['beta'])

    # Compute variance statistics
    variance_results = []

    for (source, target), betas in edge_betas.items():
        betas = np.array(betas)

        mean_beta = np.mean(betas)
        std_beta = np.std(betas)
        median_beta = np.median(betas)

        # Coefficient of variation (use absolute mean to handle negative means)
        if abs(mean_beta) > 0.001:
            cv = std_beta / abs(mean_beta)
        else:
            cv = np.inf if std_beta > 0 else 0

        variance_results.append({
            'source': source,
            'target': target,
            'n_countries': len(betas),
            'mean_beta': mean_beta,
            'median_beta': median_beta,
            'std_beta': std_beta,
            'cv': cv,
            'min_beta': np.min(betas),
            'max_beta': np.max(betas)
        })

    df = pd.DataFrame(variance_results)

    # Filter out infinite CV
    df_finite = df[df['cv'] < np.inf].copy()

    # Sort by CV
    df_sorted = df_finite.sort_values('cv', ascending=False)

    # Save full report
    df_sorted.to_csv('outputs/validation/edge_variance.csv', index=False)

    # Statistics
    mean_cv = df_finite['cv'].mean()
    median_cv = df_finite['cv'].median()

    print(f"Analyzed {len(df)} edges\n")
    print(f"CV Statistics (lower is more stable):")
    print(f"  Mean CV: {mean_cv:.2f}")
    print(f"  Median CV: {median_cv:.2f}")
    print()

    # Distribution of CV
    print("CV Distribution:")
    bins = [(0, 0.5), (0.5, 1.0), (1.0, 2.0), (2.0, 5.0), (5.0, np.inf)]
    for low, high in bins:
        if high == np.inf:
            count = len(df_finite[df_finite['cv'] >= low])
            label = f"  CV >= {low}: {count} edges"
        else:
            count = len(df_finite[(df_finite['cv'] >= low) & (df_finite['cv'] < high)])
            label = f"  CV {low}-{high}: {count} edges"
        print(label)

    print()

    # Flag high variance edges
    high_variance = df_finite[df_finite['cv'] > 1.0]

    print(f"Edges with high variance (CV > 1.0): {len(high_variance)}\n")

    if len(high_variance) > 0:
        print("Top 20 most variable edges:")
        print(high_variance.head(20)[['source', 'target', 'n_countries', 'mean_beta', 'std_beta', 'cv']].to_string(index=False))

    # Check stop condition
    if mean_cv > 2.0:
        print(f"\n❌ STOP CONDITION: Mean CV ({mean_cv:.2f}) > 2.0")
        return False
    else:
        print(f"\n✅ Beta variance is acceptable (mean CV = {mean_cv:.2f})")
        return True


if __name__ == "__main__":
    check_beta_variance()
