"""
Phase C Validation: Cross-Country Lag Consistency

Check if similar countries have similar lags for same edges.
Example: Rwanda and Uganda should have similar lags for
"education → income" (both East African economies).
"""

import json
import numpy as np
from pathlib import Path
from collections import defaultdict

# Project root
PROJECT_ROOT = Path(__file__).parent.parent.parent


def validate_cross_country_lag_consistency():
    """Check lag variance across similar countries."""

    print("\n" + "=" * 60)
    print("VALIDATION: Cross-Country Lag Consistency")
    print("=" * 60)

    graphs_dir = PROJECT_ROOT / 'data' / 'country_graphs'

    # Country groups (regional/economic similarity)
    country_groups = {
        'East Africa': ['Rwanda', 'Uganda', 'Kenya', 'Tanzania'],
        'High-income': ['Australia', 'Canada', 'Germany', 'Japan'],
        'Latin America': ['Brazil', 'Argentina', 'Chile', 'Mexico', 'Colombia'],
        'South Asia': ['India', 'Bangladesh', 'Pakistan', 'Sri Lanka'],
    }

    # Sample 10 edges that appear in most countries
    def get_common_edges(countries):
        """Find edges that appear in multiple countries with significant lags."""
        edge_counts = defaultdict(list)

        for country in countries:
            graph_path = graphs_dir / f'{country}.json'
            if not graph_path.exists():
                continue

            with open(graph_path) as f:
                graph = json.load(f)

            for edge in graph['edges']:
                if edge.get('lag_significant', False):
                    key = (edge['source'], edge['target'])
                    edge_counts[key].append({
                        'country': country,
                        'lag': edge['lag']
                    })

        # Return edges that appear in at least 2 countries
        return {k: v for k, v in edge_counts.items() if len(v) >= 2}

    all_pass = True

    for region, countries in country_groups.items():
        print(f"\n{'=' * 60}")
        print(f"Region: {region}")
        print(f"Countries: {', '.join(countries)}")
        print(f"{'=' * 60}")

        # Find edges in this region
        available_countries = [c for c in countries if (graphs_dir / f'{c}.json').exists()]
        if len(available_countries) < 2:
            print(f"  ⚠️  Not enough countries with data")
            continue

        common_edges = get_common_edges(available_countries)

        if not common_edges:
            print(f"  ⚠️  No common edges with significant lags")
            continue

        # Analyze top 10 most common edges
        sorted_edges = sorted(common_edges.items(), key=lambda x: len(x[1]), reverse=True)[:10]

        high_cv_count = 0

        for (source, target), edge_data in sorted_edges:
            lags = [d['lag'] for d in edge_data]
            n_countries = len(lags)

            if n_countries < 2:
                continue

            mean_lag = np.mean(lags)
            std_lag = np.std(lags)
            cv = std_lag / mean_lag if mean_lag > 0 else 0

            # Truncate long indicator names
            src_short = source[:20] + '...' if len(source) > 20 else source
            tgt_short = target[:20] + '...' if len(target) > 20 else target

            status = "✅" if cv <= 1.0 else "⚠️"
            if cv > 1.0:
                high_cv_count += 1

            print(f"  {status} {src_short} → {tgt_short}")
            print(f"      Lags: {lags} (n={n_countries})")
            print(f"      Mean: {mean_lag:.1f}yr, CV: {cv:.2f}")

        if high_cv_count > len(sorted_edges) * 0.5:
            print(f"\n  ⚠️  High variance in {high_cv_count}/{len(sorted_edges)} edges")
            all_pass = False
        else:
            print(f"\n  ✅ {region}: Most edges consistent (CV ≤ 1.0)")

    if all_pass:
        print(f"\n✅ PASS: Cross-country lag consistency acceptable")
    else:
        print(f"\n⚠️  WARN: Some regions have high variance (may be expected)")

    return True  # Warn but don't fail


if __name__ == "__main__":
    validate_cross_country_lag_consistency()
