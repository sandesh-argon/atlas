"""
Critical Validation #3: Extreme Beta Audit

Manually inspect the clipped betas to ensure they're reasonable.
Even after clipping to [-10, +10], check if β=10 edges make sense.
"""

import json
import pandas as pd
from pathlib import Path


def audit_extreme_betas(threshold: float = 5.0):
    """
    Find edges with |β| > threshold and review.

    For each extreme edge, check:
    - Is it theoretically plausible?
    - How many countries have this extreme value?
    """
    extreme_edges = []

    graph_dir = Path('data/country_graphs')
    graph_files = [f for f in graph_dir.glob('*.json')
                   if f.stem not in ['progress', 'estimation_progress']]

    for graph_file in graph_files:
        country = graph_file.stem

        with open(graph_file) as f:
            graph = json.load(f)

        for edge in graph['edges']:
            beta = edge['beta']

            if abs(beta) > threshold:
                extreme_edges.append({
                    'country': country,
                    'source': edge['source'],
                    'target': edge['target'],
                    'beta': beta,
                    'data_available': edge.get('data_available', True)
                })

    if extreme_edges:
        df = pd.DataFrame(extreme_edges).sort_values('beta', ascending=False, key=abs)

        print(f"Found {len(df)} edges with |β| > {threshold}\n")

        # Save full list
        df.to_csv('outputs/validation/extreme_betas.csv', index=False)

        print("Top 20 extreme edges:")
        print(df.head(20).to_string(index=False))

        # Group by edge (across countries) to find systematic issues
        edge_groups = df.groupby(['source', 'target']).agg(
            n_countries=('country', 'count'),
            mean_beta=('beta', 'mean'),
            std_beta=('beta', 'std'),
            sample_countries=('country', lambda x: ', '.join(list(x)[:3]))
        ).reset_index().sort_values('n_countries', ascending=False)

        print("\n\nEdges with systematic extreme betas (>5 countries):")
        systematic = edge_groups[edge_groups['n_countries'] >= 5]
        if len(systematic) > 0:
            print(systematic.head(20).to_string(index=False))
        else:
            print("  None found (no edge has extreme beta in 5+ countries)")

        edge_groups.to_csv('outputs/validation/extreme_betas_grouped.csv', index=False)

        # Check stop condition
        n_edges_over_8 = len(df[abs(df['beta']) > 8])
        print(f"\n\nEdges with |β| > 8: {n_edges_over_8}")

        if n_edges_over_8 > 100:
            print(f"❌ STOP CONDITION: >100 edges have |β| > 8")
            return False
        else:
            print(f"✅ Extreme betas within acceptable range")
            return True
    else:
        print(f"✅ No edges with |β| > {threshold}")
        return True


if __name__ == "__main__":
    audit_extreme_betas(threshold=5.0)
