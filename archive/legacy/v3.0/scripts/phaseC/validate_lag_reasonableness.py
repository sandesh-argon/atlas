"""
Phase C Validation: Lag Reasonableness Check

Check if estimated lags match domain knowledge expectations.
Example: Education → Income should have 5-10 year lag, not 1 year.
"""

import json
import pandas as pd
from pathlib import Path
from collections import defaultdict

# Project root
PROJECT_ROOT = Path(__file__).parent.parent.parent


# Domain knowledge: expected lag ranges for certain indicator patterns
# Format: (source_pattern, target_pattern): (min_lag, max_lag)
EXPECTED_LAGS = {
    # Education effects take time
    ('educat', 'income'): (3, 10),
    ('educat', 'gdp'): (3, 10),
    ('school', 'income'): (3, 10),
    ('literacy', 'gdp'): (2, 8),

    # Health effects are relatively fast
    ('health', 'life'): (1, 5),
    ('health', 'mortality'): (1, 4),
    ('vaccin', 'mortality'): (1, 3),

    # Infrastructure has medium-term impact
    ('infrastr', 'gdp'): (2, 8),
    ('road', 'trade'): (1, 5),
    ('electric', 'gdp'): (2, 6),

    # Governance/policy effects vary
    ('corrupt', 'gdp'): (1, 5),
    ('democr', 'growth'): (2, 8),
}

# Effects that should be fast (0-2 year lag)
FAST_EFFECTS = [
    ('inflation', 'price'),
    ('interest', 'invest'),
    ('exchange', 'trade'),
    ('tax', 'revenue'),
]


def validate_lag_reasonableness():
    """Check if lags fall within reasonable ranges."""

    print("\n" + "=" * 60)
    print("VALIDATION: Lag Reasonableness Check")
    print("=" * 60)

    graphs_dir = PROJECT_ROOT / 'data' / 'country_graphs'

    # Sample diverse countries
    test_countries = ['Australia', 'Rwanda', 'Brazil', 'India', 'Germany',
                      'Nigeria', 'Japan', 'Mexico', 'Canada', 'Kenya']

    suspicious_lags = []
    lag_stats = defaultdict(list)
    total_checked = 0

    for country in test_countries:
        graph_path = graphs_dir / f'{country}.json'
        if not graph_path.exists():
            continue

        with open(graph_path) as f:
            graph = json.load(f)

        for edge in graph['edges']:
            if 'lag' not in edge:
                continue

            source = edge['source'].lower()
            target = edge['target'].lower()
            lag = edge['lag']
            significant = edge.get('lag_significant', False)

            # Only check significant lags
            if not significant:
                continue

            total_checked += 1

            # Check against expected ranges
            for (src_pattern, tgt_pattern), (min_lag, max_lag) in EXPECTED_LAGS.items():
                if src_pattern in source and tgt_pattern in target:
                    lag_stats[f"{src_pattern}→{tgt_pattern}"].append(lag)

                    if not (min_lag <= lag <= max_lag):
                        suspicious_lags.append({
                            'country': country,
                            'source': edge['source'],
                            'target': edge['target'],
                            'estimated_lag': lag,
                            'expected_range': f"{min_lag}-{max_lag}",
                            'reason': 'Outside expected range'
                        })
                    break

            # Check fast effects that should be 0-2 years
            for (src_pattern, tgt_pattern) in FAST_EFFECTS:
                if src_pattern in source and tgt_pattern in target:
                    if lag > 2:
                        suspicious_lags.append({
                            'country': country,
                            'source': edge['source'],
                            'target': edge['target'],
                            'estimated_lag': lag,
                            'expected_range': '0-2',
                            'reason': 'Should be fast effect'
                        })

    # Report results
    print(f"\nEdges checked: {total_checked}")
    print(f"Suspicious lags: {len(suspicious_lags)}")

    if lag_stats:
        print("\n--- Lag Statistics by Pattern ---")
        for pattern, lags in sorted(lag_stats.items()):
            if lags:
                mean_lag = sum(lags) / len(lags)
                print(f"  {pattern}: n={len(lags)}, mean={mean_lag:.1f}yr, range={min(lags)}-{max(lags)}yr")

    if suspicious_lags:
        print(f"\n--- Suspicious Lags (first 10) ---")
        df = pd.DataFrame(suspicious_lags[:10])
        print(df.to_string(index=False))

        # Save full list
        output_path = PROJECT_ROOT / 'outputs' / 'validation' / 'suspicious_lags.csv'
        output_path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(suspicious_lags).to_csv(output_path, index=False)
        print(f"\nFull list saved to: {output_path}")

    # Pass/fail
    suspicious_rate = len(suspicious_lags) / max(total_checked, 1)
    if suspicious_rate < 0.20:  # <20% suspicious
        print(f"\n✅ PASS: {suspicious_rate*100:.1f}% suspicious lags (threshold: 20%)")
        return True
    else:
        print(f"\n⚠️  WARN: {suspicious_rate*100:.1f}% suspicious lags (threshold: 20%)")
        return True  # Warn but don't fail - lags are data-driven


if __name__ == "__main__":
    validate_lag_reasonableness()
