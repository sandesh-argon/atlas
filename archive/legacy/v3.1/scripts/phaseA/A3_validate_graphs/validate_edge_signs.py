"""
Critical Validation #1: Edge Sign Consistency

Check if edge signs (positive/negative) are consistent with theory.
Example: health_expenditure → life_expectancy should be POSITIVE
"""

import json
import pandas as pd
from pathlib import Path

# Define theoretically expected signs (source_pattern, target_pattern, expected_sign)
EXPECTED_SIGNS = [
    # Health relationships
    ('health', 'life_expect', 'positive'),
    ('health', 'mortality', 'negative'),
    ('physician', 'life_expect', 'positive'),
    ('physician', 'mortality', 'negative'),
    ('immunization', 'mortality', 'negative'),

    # Education relationships
    ('education', 'literacy', 'positive'),
    ('school', 'literacy', 'positive'),
    ('education', 'poverty', 'negative'),

    # Economic relationships
    ('gdp', 'life_expect', 'positive'),
    ('gdp', 'poverty', 'negative'),
    ('income', 'life_expect', 'positive'),

    # Environmental relationships
    ('pollution', 'life_expect', 'negative'),
    ('co2', 'life_expect', 'negative'),

    # Governance relationships
    ('corruption', 'gdp', 'negative'),
    ('rule_of_law', 'gdp', 'positive'),
]


def check_sign_consistency():
    """
    Check if edge signs match theoretical expectations.
    Flag edges where theory says positive but country graph is negative.
    """
    graph_dir = Path('data/country_graphs')
    graph_files = [f for f in graph_dir.glob('*.json')
                   if f.stem not in ['progress', 'estimation_progress']]

    print(f"Checking {len(graph_files)} country graphs for sign consistency...\n")

    violations = []
    all_checks = []

    for expected_source, expected_target, expected_sign in EXPECTED_SIGNS:
        sign_by_country = {}
        matching_edges = []

        for graph_file in graph_files:
            country = graph_file.stem

            with open(graph_file) as f:
                graph = json.load(f)

            # Find matching edges
            for edge in graph['edges']:
                source_match = expected_source.lower() in edge['source'].lower()
                target_match = expected_target.lower() in edge['target'].lower()

                if source_match and target_match and edge.get('data_available', True):
                    actual_sign = 'positive' if edge['beta'] > 0 else 'negative'
                    sign_by_country[country] = {
                        'sign': actual_sign,
                        'beta': edge['beta'],
                        'source': edge['source'],
                        'target': edge['target']
                    }
                    matching_edges.append({
                        'country': country,
                        'source': edge['source'],
                        'target': edge['target'],
                        'beta': edge['beta'],
                        'expected_sign': expected_sign,
                        'actual_sign': actual_sign,
                        'match': actual_sign == expected_sign
                    })

        # Check consistency
        if sign_by_country:
            n_countries = len(sign_by_country)
            n_mismatched = sum(1 for v in sign_by_country.values()
                              if v['sign'] != expected_sign)

            check_result = {
                'edge_pattern': f"{expected_source} → {expected_target}",
                'expected_sign': expected_sign,
                'n_countries': n_countries,
                'n_matched': n_countries - n_mismatched,
                'n_mismatched': n_mismatched,
                'percent_mismatch': n_mismatched / n_countries if n_countries > 0 else 0
            }
            all_checks.append(check_result)

            if n_mismatched > n_countries * 0.1:  # >10% mismatch
                violations.append(check_result)

        all_checks.extend(matching_edges)

    # Summary
    checks_df = pd.DataFrame([c for c in all_checks if 'edge_pattern' in c])

    if len(checks_df) > 0:
        print("Sign Consistency Summary:")
        print(checks_df.to_string(index=False))
        print()

    if violations:
        print(f"⚠️  {len(violations)} sign consistency violations found (>10% mismatch):\n")
        for v in violations:
            print(f"  {v['edge_pattern']}: {v['n_mismatched']}/{v['n_countries']} "
                  f"countries have unexpected sign ({v['percent_mismatch']:.1%})")

        violations_df = pd.DataFrame(violations)
        violations_df.to_csv('outputs/validation/sign_violations.csv', index=False)

        return False
    else:
        print("✅ All edge signs consistent with theory (or <10% violations)")
        return True


if __name__ == "__main__":
    check_sign_consistency()
