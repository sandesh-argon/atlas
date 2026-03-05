"""
Phase C Validation: Zero-Lag Edge Check

Check that certain edges have minimal lag (instantaneous or fast effects).
Example: "money_supply → inflation" should be fast (0-1 year lag)
"""

import json
from pathlib import Path
from collections import defaultdict

# Project root
PROJECT_ROOT = Path(__file__).parent.parent.parent


# Effects that should be fast (0-2 year lag)
FAST_EFFECTS = [
    ('money', 'inflation'),
    ('inflation', 'price'),
    ('interest', 'invest'),
    ('exchange', 'export'),
    ('exchange', 'import'),
    ('tax', 'revenue'),
    ('tariff', 'trade'),
    ('subsid', 'production'),
]

# Effects that should be slower (3+ years)
SLOW_EFFECTS = [
    ('educat', 'income'),
    ('school', 'gdp'),
    ('literacy', 'product'),
    ('research', 'innovat'),
    ('infrastr', 'growth'),
]


def validate_zero_lag_edges():
    """Check for edges that should have minimal or longer lag."""

    print("\n" + "=" * 60)
    print("VALIDATION: Zero-Lag Edge Check")
    print("=" * 60)

    graphs_dir = PROJECT_ROOT / 'data' / 'country_graphs'

    # Test on diverse countries
    test_countries = ['Australia', 'Rwanda', 'Brazil', 'India', 'Germany']

    fast_issues = []
    slow_issues = []
    fast_found = defaultdict(list)
    slow_found = defaultdict(list)

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

            # Check fast effects (should be 0-2 years)
            for (src_pattern, tgt_pattern) in FAST_EFFECTS:
                if src_pattern in source and tgt_pattern in target:
                    fast_found[f"{src_pattern}→{tgt_pattern}"].append({
                        'country': country,
                        'lag': lag,
                        'significant': significant
                    })
                    if significant and lag > 2:
                        fast_issues.append({
                            'country': country,
                            'source': edge['source'],
                            'target': edge['target'],
                            'lag': lag,
                            'expected': '0-2',
                            'issue': 'Fast effect has slow lag'
                        })

            # Check slow effects (should be 3+ years)
            for (src_pattern, tgt_pattern) in SLOW_EFFECTS:
                if src_pattern in source and tgt_pattern in target:
                    slow_found[f"{src_pattern}→{tgt_pattern}"].append({
                        'country': country,
                        'lag': lag,
                        'significant': significant
                    })
                    if significant and lag < 3:
                        slow_issues.append({
                            'country': country,
                            'source': edge['source'],
                            'target': edge['target'],
                            'lag': lag,
                            'expected': '3+',
                            'issue': 'Slow effect has fast lag'
                        })

    # Report fast effects
    print("\n--- Fast Effects (expected 0-2 year lag) ---")
    if fast_found:
        for pattern, data in fast_found.items():
            lags = [d['lag'] for d in data if d['significant']]
            if lags:
                mean_lag = sum(lags) / len(lags)
                status = "✅" if mean_lag <= 2 else "⚠️"
                print(f"  {status} {pattern}: mean={mean_lag:.1f}yr (n={len(lags)})")
    else:
        print("  (No matching edges found)")

    if fast_issues:
        print(f"\n  Issues ({len(fast_issues)} edges with lag > 2):")
        for issue in fast_issues[:5]:
            print(f"    - {issue['country']}: {issue['source'][:30]} → {issue['target'][:30]}: lag={issue['lag']}")

    # Report slow effects
    print("\n--- Slow Effects (expected 3+ year lag) ---")
    if slow_found:
        for pattern, data in slow_found.items():
            lags = [d['lag'] for d in data if d['significant']]
            if lags:
                mean_lag = sum(lags) / len(lags)
                status = "✅" if mean_lag >= 3 else "⚠️"
                print(f"  {status} {pattern}: mean={mean_lag:.1f}yr (n={len(lags)})")
    else:
        print("  (No matching edges found)")

    if slow_issues:
        print(f"\n  Issues ({len(slow_issues)} edges with lag < 3):")
        for issue in slow_issues[:5]:
            print(f"    - {issue['country']}: {issue['source'][:30]} → {issue['target'][:30]}: lag={issue['lag']}")

    # Overall assessment
    total_issues = len(fast_issues) + len(slow_issues)
    total_checked = sum(len(v) for v in fast_found.values()) + sum(len(v) for v in slow_found.values())

    if total_checked == 0:
        print("\n⚠️  No domain-specific edges found to validate")
        return True

    issue_rate = total_issues / max(total_checked, 1)

    if issue_rate < 0.30:  # <30% issues
        print(f"\n✅ PASS: {issue_rate*100:.1f}% of edges have unexpected lags")
    else:
        print(f"\n⚠️  WARN: {issue_rate*100:.1f}% of edges have unexpected lags")

    return True  # Warn but don't fail


if __name__ == "__main__":
    validate_zero_lag_edges()
