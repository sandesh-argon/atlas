"""
Critical Validation #2: Indicator Coverage

Check which V2.1 indicators are missing in country graphs.
If 50+ countries are missing "GDP", that's a problem for simulation.
"""

import json
import pandas as pd
from pathlib import Path


def check_indicator_coverage():
    """
    For each indicator in V2.1, count how many countries have data.
    Flag indicators with <50% coverage.
    """
    # Load V2.1 nodes
    nodes = pd.read_csv('data/raw/v21_nodes.csv')

    # Get layer 5 indicators (actual indicators, not hierarchy nodes)
    indicators = nodes[nodes['layer'] == 5]['id'].tolist()

    print(f"Checking coverage for {len(indicators)} layer-5 indicators...\n")

    # Count coverage per indicator
    coverage = {ind: 0 for ind in indicators}

    graph_dir = Path('data/country_graphs')
    graph_files = [f for f in graph_dir.glob('*.json')
                   if f.stem not in ['progress', 'estimation_progress']]
    n_countries = len(graph_files)

    for graph_file in graph_files:
        with open(graph_file) as f:
            graph = json.load(f)

        # Get unique indicators with data in this graph
        graph_indicators = set()
        for edge in graph['edges']:
            if edge.get('data_available', False):
                graph_indicators.add(edge['source'])
                graph_indicators.add(edge['target'])

        # Update coverage counts
        for ind in graph_indicators:
            if ind in coverage:
                coverage[ind] += 1

    # Compute percentages
    coverage_df = pd.DataFrame([
        {
            'indicator': ind,
            'n_countries': count,
            'coverage_pct': count / n_countries if n_countries > 0 else 0
        }
        for ind, count in coverage.items()
    ]).sort_values('coverage_pct')

    # Save full coverage report
    coverage_df.to_csv('outputs/validation/indicator_coverage.csv', index=False)

    # Flag low coverage
    low_coverage = coverage_df[coverage_df['coverage_pct'] < 0.5]
    very_low = coverage_df[coverage_df['coverage_pct'] < 0.3]

    print(f"Total indicators: {len(coverage_df)}")
    print(f"Indicators with <50% coverage: {len(low_coverage)}")
    print(f"Indicators with <30% coverage: {len(very_low)}")
    print()

    # Coverage distribution
    print("Coverage Distribution:")
    bins = [(0, 0.1), (0.1, 0.3), (0.3, 0.5), (0.5, 0.7), (0.7, 0.9), (0.9, 1.01)]
    for low, high in bins:
        count = len(coverage_df[(coverage_df['coverage_pct'] >= low) &
                                (coverage_df['coverage_pct'] < high)])
        print(f"  {int(low*100)}-{int(high*100)}%: {count} indicators")

    print()

    if len(very_low) > 0:
        print(f"⚠️  {len(very_low)} indicators have <30% coverage:")
        print(very_low.head(15).to_string(index=False))
        return False
    elif len(low_coverage) > 50:
        print(f"⚠️  {len(low_coverage)} indicators have <50% coverage")
        return False
    else:
        print("✅ Indicator coverage is acceptable")
        return True


if __name__ == "__main__":
    check_indicator_coverage()
