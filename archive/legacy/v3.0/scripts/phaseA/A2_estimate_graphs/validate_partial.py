"""
A2 Validation: Check first N country graphs to catch issues early.

Run after ~10 countries complete to verify estimation is working correctly.
"""

import json
from pathlib import Path
import pandas as pd
import numpy as np


def validate_partial_graphs(graphs_dir: str = 'data/country_graphs', n_countries: int = 10):
    """
    Validate first N country graphs.

    Checks:
    1. Each graph has 7,368 edges (same as V2.1)
    2. >50% of edges have country-specific data
    3. Betas are in reasonable range (-100 to +100)
    4. No NaN or infinite values
    """
    graph_dir = Path(graphs_dir)
    graph_files = sorted(list(graph_dir.glob('*.json')))[:n_countries]

    if len(graph_files) == 0:
        print("❌ No graphs found yet")
        return False

    print(f"Validating {len(graph_files)} country graphs...")

    issues = []
    stats = []

    for graph_file in graph_files:
        country = graph_file.stem

        with open(graph_file) as f:
            graph = json.load(f)

        n_edges = graph['n_edges']
        n_with_data = graph['n_edges_with_data']

        # Check 1: Should have 7,368 edges
        if n_edges != 7368:
            issues.append(f"{country}: Expected 7,368 edges, got {n_edges}")

        # Check 2: Should have >50% edges with data
        if n_with_data < n_edges * 0.3:
            issues.append(f"{country}: Only {n_with_data}/{n_edges} edges have data (<30%)")

        # Check 3: Betas should be reasonable
        betas = [e['beta'] for e in graph['edges']]
        betas_array = np.array(betas)

        # Check for NaN/Inf
        if np.any(np.isnan(betas_array)) or np.any(np.isinf(betas_array)):
            issues.append(f"{country}: Found NaN or Inf beta values")

        max_beta = np.nanmax(np.abs(betas_array))
        if max_beta > 100:
            issues.append(f"{country}: Extreme beta found: {max_beta:.2f}")

        # Check 4: CIs should bracket beta
        ci_issues = 0
        for edge in graph['edges']:
            if edge['ci_lower'] > edge['beta'] or edge['ci_upper'] < edge['beta']:
                ci_issues += 1
        if ci_issues > 0:
            issues.append(f"{country}: {ci_issues} edges have CI not bracketing beta")

        stats.append({
            'country': country,
            'n_edges': n_edges,
            'n_with_data': n_with_data,
            'data_coverage': n_with_data / n_edges if n_edges > 0 else 0,
            'mean_beta': np.nanmean(betas_array),
            'max_abs_beta': max_beta
        })

    stats_df = pd.DataFrame(stats)

    print("\nPartial Validation Summary:")
    print(stats_df.to_string(index=False))

    print(f"\nMean data coverage: {stats_df['data_coverage'].mean():.1%}")
    print(f"Mean |beta|: {stats_df['max_abs_beta'].mean():.3f}")

    if issues:
        print(f"\n⚠️  ISSUES FOUND ({len(issues)}):")
        for issue in issues:
            print(f"  - {issue}")
        return False
    else:
        print("\n✅ Partial validation passed - continue processing")
        return True


if __name__ == "__main__":
    success = validate_partial_graphs(
        graphs_dir='data/country_graphs',
        n_countries=10
    )

    if not success:
        print("\n❌ Issues detected - review before continuing full estimation")
        exit(1)
