#!/usr/bin/env python
"""
Phase E.1: Historical Case Identification (V2)

Improved approach: Find cases where SOURCE indicators in the causal graph
have significant changes, so we can validate downstream effects.
"""

import json
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Set
from collections import defaultdict, Counter

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
GRAPHS_DIR = DATA_DIR / "country_graphs"
PANEL_PATH = DATA_DIR / "raw" / "v21_panel_data_for_v3.parquet"
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "phaseE"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def load_panel_data() -> pd.DataFrame:
    """Load panel data."""
    print("Loading panel data...")
    df = pd.read_parquet(PANEL_PATH)
    return df


def get_graph_source_indicators(country: str) -> Dict[str, int]:
    """Get indicators that are sources in the graph (have outgoing edges)."""
    graph_path = GRAPHS_DIR / f"{country}.json"
    if not graph_path.exists():
        return {}

    with open(graph_path) as f:
        graph = json.load(f)

    # Count outgoing edges per source
    sources = Counter(e['source'] for e in graph['edges'] if e.get('data_available', True))
    return dict(sources)


def get_downstream_indicators(country: str, source: str) -> Set[str]:
    """Get indicators downstream of source."""
    graph_path = GRAPHS_DIR / f"{country}.json"
    if not graph_path.exists():
        return set()

    with open(graph_path) as f:
        graph = json.load(f)

    downstream = set()
    for edge in graph['edges']:
        if edge.get('source') == source and edge.get('data_available', True):
            downstream.add(edge.get('target'))

    return downstream


def find_source_indicator_changes(
    df: pd.DataFrame,
    country: str,
    source_indicators: Dict[str, int],
    min_change_pct: float = 15.0,
    min_downstream: int = 5
) -> List[Dict]:
    """Find significant changes in source indicators."""
    country_data = df[df['country'] == country]
    if country_data.empty:
        return []

    # Filter to indicators that are sources with enough downstream
    good_sources = {ind for ind, count in source_indicators.items() if count >= min_downstream}

    changes = []

    for indicator in good_sources:
        ind_data = country_data[country_data['indicator_id'] == indicator].sort_values('year')

        if len(ind_data) < 7:  # Need enough data
            continue

        values = ind_data.set_index('year')['value']

        # Look for significant year-over-year changes
        for year in values.index[3:-3]:
            if year - 1 not in values.index or year not in values.index:
                continue

            before_val = values[year - 1]
            after_val = values[year]

            if before_val == 0 or pd.isna(before_val) or pd.isna(after_val):
                continue

            pct_change = ((after_val - before_val) / abs(before_val)) * 100

            if abs(pct_change) >= min_change_pct:
                downstream = get_downstream_indicators(country, indicator)
                downstream_in_data = downstream & set(country_data['indicator_id'].unique())

                if len(downstream_in_data) >= 3:
                    changes.append({
                        'country': country,
                        'indicator': indicator,
                        'year': int(year),
                        'before_value': float(before_val),
                        'after_value': float(after_val),
                        'percent_change': float(pct_change),
                        'n_downstream': len(downstream),
                        'n_downstream_with_data': len(downstream_in_data),
                        'outgoing_edges': source_indicators[indicator]
                    })

    return changes


def identify_all_cases(df: pd.DataFrame, n_per_country: int = 3) -> List[Dict]:
    """Identify validation cases across all countries with graphs."""
    all_cases = []

    countries = sorted([f.stem for f in GRAPHS_DIR.glob("*.json") if not f.name.startswith("_")])
    print(f"\nScanning {len(countries)} countries for validation cases...")

    for i, country in enumerate(countries):
        if i % 20 == 0:
            print(f"  Progress: {i}/{len(countries)}")

        # Get source indicators for this country
        sources = get_graph_source_indicators(country)
        if not sources:
            continue

        # Find significant changes
        changes = find_source_indicator_changes(df, country, sources)

        if changes:
            # Score and take best cases
            for case in changes:
                # Score based on: change magnitude, downstream coverage, recency
                score = (
                    min(abs(case['percent_change']), 50) / 50 * 30 +
                    min(case['n_downstream_with_data'], 20) / 20 * 40 +
                    max(0, (case['year'] - 1995)) / 25 * 20 +
                    (10 if case['year'] <= 2018 else 0)  # Need outcome data
                )
                case['score'] = score

            # Sort by score and take top N
            changes.sort(key=lambda x: x['score'], reverse=True)
            all_cases.extend(changes[:n_per_country])

    return all_cases


def main():
    """Main entry point."""
    print("=" * 60)
    print("Phase E.1: Historical Case Identification (V2)")
    print("=" * 60)

    # Load data
    df = load_panel_data()

    # Identify cases
    cases = identify_all_cases(df, n_per_country=3)

    # Sort by score
    cases.sort(key=lambda x: x['score'], reverse=True)

    # Take top 50 cases
    top_cases = cases[:50]

    print(f"\n{'=' * 60}")
    print(f"Found {len(cases)} total cases, keeping top {len(top_cases)}")
    print("=" * 60)

    # Show top 15
    print("\nTop 15 validation cases:")
    for i, case in enumerate(top_cases[:15], 1):
        print(f"  {i}. {case['country']:20s} {case['indicator']:25s} "
              f"({case['year']}) {case['percent_change']:+.1f}% "
              f"[{case['n_downstream_with_data']} downstream] "
              f"score={case['score']:.1f}")

    # Save cases
    output_file = OUTPUT_DIR / "validation_cases_v2.json"
    with open(output_file, 'w') as f:
        json.dump(top_cases, f, indent=2)
    print(f"\nCases saved to: {output_file}")

    # Summary stats
    countries = set(c['country'] for c in top_cases)
    indicators = set(c['indicator'] for c in top_cases)
    years = [c['year'] for c in top_cases]

    print(f"\nSummary:")
    print(f"  Countries: {len(countries)}")
    print(f"  Unique indicators: {len(indicators)}")
    print(f"  Year range: {min(years)}-{max(years)}")
    print(f"  Mean downstream indicators: {np.mean([c['n_downstream_with_data'] for c in top_cases]):.1f}")

    return top_cases


if __name__ == "__main__":
    main()
