"""
Fix extreme beta values in all country graphs.

The V2.1 global edges contain extreme weights (up to 1.7e+12).
These propagated to country graphs for edges where data_available=False.

This script clips ALL beta values to [-10, +10] range.
"""

import json
from pathlib import Path


def fix_extreme_betas(
    graphs_dir: str = 'data/country_graphs',
    beta_min: float = -10.0,
    beta_max: float = 10.0
):
    """
    Clip all beta values in country graphs to [beta_min, beta_max].

    Also clips ci_lower, ci_upper, and global_beta for consistency.
    """
    graph_dir = Path(graphs_dir)
    graph_files = [f for f in graph_dir.glob('*.json')
                   if f.stem not in ['progress', 'estimation_progress']]

    print(f"Fixing beta values in {len(graph_files)} country graphs...")
    print(f"Clipping range: [{beta_min}, {beta_max}]")
    print()

    total_fixed = 0
    total_edges = 0

    for graph_file in graph_files:
        with open(graph_file) as f:
            graph = json.load(f)

        edges_fixed = 0

        for edge in graph['edges']:
            total_edges += 1

            # Track if any value needs fixing
            needs_fix = False

            # Clip beta
            if edge['beta'] < beta_min or edge['beta'] > beta_max:
                edge['beta'] = max(beta_min, min(beta_max, edge['beta']))
                needs_fix = True

            # Clip global_beta
            if 'global_beta' in edge:
                if edge['global_beta'] < beta_min or edge['global_beta'] > beta_max:
                    edge['global_beta'] = max(beta_min, min(beta_max, edge['global_beta']))
                    needs_fix = True

            # Clip confidence intervals
            if 'ci_lower' in edge:
                if edge['ci_lower'] < beta_min or edge['ci_lower'] > beta_max:
                    edge['ci_lower'] = max(beta_min, min(beta_max, edge['ci_lower']))
                    needs_fix = True

            if 'ci_upper' in edge:
                if edge['ci_upper'] < beta_min or edge['ci_upper'] > beta_max:
                    edge['ci_upper'] = max(beta_min, min(beta_max, edge['ci_upper']))
                    needs_fix = True

            if needs_fix:
                edges_fixed += 1

        total_fixed += edges_fixed

        # Save fixed graph
        with open(graph_file, 'w') as f:
            json.dump(graph, f, indent=2)

    print(f"Fixed {total_fixed} edges out of {total_edges} total edges")
    print(f"({100 * total_fixed / total_edges:.2f}% of edges had extreme values)")


if __name__ == "__main__":
    fix_extreme_betas()
