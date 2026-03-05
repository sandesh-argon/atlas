#!/usr/bin/env python3
"""
Phase 3B Validation: Cross-Country Consistency

Verifies similar countries have similar cluster structures.
Groups tested: G7, BRICS, Nordic, Sub-Saharan Africa
"""

import json
import numpy as np
from pathlib import Path

BASE_DIR = Path("<repo-root>/v3.1")
CLUSTERS_DIR = BASE_DIR / "data" / "v3_1_development_clusters"

# Country name mappings (code to file name)
COUNTRY_NAMES = {
    'USA': 'United States',
    'CAN': 'Canada',
    'GBR': 'United Kingdom',
    'FRA': 'France',
    'DEU': 'Germany',
    'ITA': 'Italy',
    'JPN': 'Japan',
    'BRA': 'Brazil',
    'RUS': 'Russia',
    'IND': 'India',
    'CHN': 'China',
    'ZAF': 'South Africa',
    'SWE': 'Sweden',
    'NOR': 'Norway',
    'DNK': 'Denmark',
    'FIN': 'Finland',
    'ISL': 'Iceland',
    'RWA': 'Rwanda',
    'KEN': 'Kenya',
    'UGA': 'Uganda',
    'TZA': 'Tanzania',
    'ETH': 'Ethiopia'
}


def check_cross_country_consistency():
    """
    Verify similar countries have similar cluster patterns.
    """

    country_groups = {
        'G7': ['USA', 'CAN', 'GBR', 'FRA', 'DEU', 'ITA', 'JPN'],
        'BRICS': ['BRA', 'RUS', 'IND', 'CHN', 'ZAF'],
        'Nordic': ['SWE', 'NOR', 'DNK', 'FIN', 'ISL'],
        'Sub-Saharan Africa': ['RWA', 'KEN', 'UGA', 'TZA', 'ETH']
    }

    print(f"\n{'='*60}")
    print("VALIDATION 4: CROSS-COUNTRY CONSISTENCY")
    print(f"{'='*60}")

    results = {}
    high_variance_groups = []

    for group_name, country_codes in country_groups.items():
        print(f"\n{group_name}:")

        group_data = []
        for country_code in country_codes:
            country_name = COUNTRY_NAMES.get(country_code, country_code)
            file = CLUSTERS_DIR / "countries" / f"{country_name}_clusters.json"

            if file.exists():
                with open(file) as f:
                    data = json.load(f)
                    group_data.append({
                        'country': country_name,
                        'code': country_code,
                        'n_clusters': data['summary']['n_clusters'],
                        'largest_cluster': data['summary']['largest_cluster'],
                        'mean_cluster_size': data['summary']['mean_cluster_size']
                    })
            else:
                print(f"  {country_code}: File not found ({country_name})")

        if len(group_data) < 2:
            print(f"  Not enough data ({len(group_data)} countries)")
            results[group_name] = {'status': 'insufficient_data'}
            continue

        # Compute statistics
        n_clusters = np.array([d['n_clusters'] for d in group_data])
        mean_n = np.mean(n_clusters)
        std_n = np.std(n_clusters)
        cv = std_n / mean_n if mean_n > 0 else 0  # Coefficient of variation

        print(f"  Countries found: {len(group_data)}")
        print(f"  Cluster count: {mean_n:.1f} +/- {std_n:.1f} (CV: {cv:.2f})")

        # Check for high variance
        if cv > 0.5:
            print(f"  WARNING: High variance in cluster count (CV > 0.5)")
            high_variance_groups.append(group_name)
        else:
            print(f"  OK: Consistent cluster structure")

        # Show range
        for d in group_data:
            status = "outlier" if abs(d['n_clusters'] - mean_n) > 2 * std_n else ""
            print(f"    {d['code']}: {d['n_clusters']} clusters {status}")

        results[group_name] = {
            'countries': len(group_data),
            'mean_clusters': float(mean_n),
            'std_clusters': float(std_n),
            'cv': float(cv),
            'high_variance': cv > 0.5
        }

    # Summary
    print(f"\n{'~'*40}")
    print("SUMMARY:")
    print(f"  Groups analyzed: {len(results)}")
    print(f"  High variance groups: {len(high_variance_groups)}")

    # Pass if no groups have CV > 0.5
    passed = len(high_variance_groups) == 0

    print(f"  STATUS: {'PASS' if passed else 'WARN'}")

    return {
        'groups': results,
        'high_variance_groups': high_variance_groups,
        'passed': passed
    }


if __name__ == '__main__':
    result = check_cross_country_consistency()
    exit(0 if result['passed'] else 1)
