#!/usr/bin/env python
"""
Phase E.1: Quick Case Identification

Fast approach: Scan a subset of countries to find validation cases.
"""

import json
import pandas as pd
import numpy as np
from pathlib import Path
from collections import Counter

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
GRAPHS_DIR = DATA_DIR / "country_graphs"
PANEL_PATH = DATA_DIR / "raw" / "v21_panel_data_for_v3.parquet"
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "phaseE"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Priority countries (good data coverage)
PRIORITY_COUNTRIES = [
    "Australia", "Brazil", "Canada", "China", "France", "Germany",
    "India", "Indonesia", "Italy", "Japan", "Mexico", "Russia",
    "South Africa", "South Korea", "Spain", "Turkey", "United Kingdom",
    "United States of America", "Argentina", "Colombia", "Egypt",
    "Nigeria", "Pakistan", "Philippines", "Thailand", "Vietnam"
]


def main():
    print("=" * 60)
    print("Phase E.1: Quick Case Identification")
    print("=" * 60)

    # Load data
    print("Loading panel data...")
    df = pd.read_parquet(PANEL_PATH)
    print(f"  Shape: {df.shape}")

    all_cases = []

    for country in PRIORITY_COUNTRIES:
        graph_path = GRAPHS_DIR / f"{country}.json"
        if not graph_path.exists():
            continue

        print(f"\n  Scanning {country}...")

        # Load graph
        with open(graph_path) as f:
            graph = json.load(f)

        # Get source indicators with many outgoing edges
        source_counts = Counter(e['source'] for e in graph['edges']
                               if e.get('data_available', True))
        top_sources = [ind for ind, count in source_counts.most_common(20)
                      if count >= 5]

        # Get country panel data
        country_data = df[df['country'] == country]
        available_inds = set(country_data['indicator_id'].unique())

        # Filter to sources that exist in panel
        valid_sources = [s for s in top_sources if s in available_inds]

        for indicator in valid_sources[:10]:  # Check top 10
            ind_data = country_data[country_data['indicator_id'] == indicator].sort_values('year')

            if len(ind_data) < 7:
                continue

            values = ind_data.set_index('year')['value']

            # Find significant changes
            for year in list(values.index)[3:-3]:
                if year - 1 not in values.index or year not in values.index:
                    continue

                before = values[year - 1]
                after = values[year]

                if before == 0 or pd.isna(before) or pd.isna(after):
                    continue

                pct_change = ((after - before) / abs(before)) * 100

                if abs(pct_change) >= 15:  # Significant change
                    # Count downstream with data
                    downstream = set(e['target'] for e in graph['edges']
                                    if e['source'] == indicator and e.get('data_available', True))
                    downstream_with_data = len(downstream & available_inds)

                    if downstream_with_data >= 3:
                        all_cases.append({
                            'country': country,
                            'indicator': indicator,
                            'year': int(year),
                            'percent_change': float(pct_change),
                            'n_downstream': downstream_with_data,
                            'outgoing_edges': source_counts[indicator]
                        })

    # Sort by downstream count and take top 30
    all_cases.sort(key=lambda x: (x['n_downstream'], abs(x['percent_change'])), reverse=True)
    top_cases = all_cases[:30]

    print(f"\n{'=' * 60}")
    print(f"Found {len(all_cases)} cases, keeping top {len(top_cases)}")
    print("=" * 60)

    print("\nTop validation cases:")
    for i, c in enumerate(top_cases[:15], 1):
        print(f"  {i:2d}. {c['country']:25s} {c['indicator']:20s} "
              f"({c['year']}) {c['percent_change']:+6.1f}% [{c['n_downstream']} downstream]")

    # Save
    output_file = OUTPUT_DIR / "validation_cases_v2.json"
    with open(output_file, 'w') as f:
        json.dump(top_cases, f, indent=2)
    print(f"\nSaved to: {output_file}")

    return top_cases


if __name__ == "__main__":
    main()
