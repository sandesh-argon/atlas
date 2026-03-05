#!/usr/bin/env python3
"""
Phase 3B Validation: Cluster Size Distribution

Verifies cluster sizes are reasonable:
- No single cluster >50% of nodes
- <30% of clusters are tiny (<10 nodes)
- Largest cluster <10x median
"""

import json
import numpy as np
from pathlib import Path

BASE_DIR = Path("<repo-root>/v3.1")
CLUSTERS_DIR = BASE_DIR / "data" / "v3_1_development_clusters"


def check_cluster_size_distribution():
    """
    Verify cluster sizes are reasonable (not all tiny or one giant).
    """

    # Check unified 2024 (most complete)
    file = CLUSTERS_DIR / "unified" / "2024_clusters.json"
    with open(file) as f:
        data = json.load(f)

    print(f"\n{'='*60}")
    print("VALIDATION 2: CLUSTER SIZE DISTRIBUTION")
    print(f"{'='*60}")

    sizes = np.array([c['size'] for c in data['clusters']])
    total_nodes = sizes.sum()

    print(f"Total clusters: {len(sizes)}")
    print(f"Total nodes: {total_nodes}")
    print(f"Mean cluster size: {sizes.mean():.1f}")
    print(f"Median cluster size: {np.median(sizes):.1f}")
    print(f"Largest cluster: {sizes.max()} ({sizes.max()/total_nodes*100:.1f}% of nodes)")
    print(f"Smallest cluster: {sizes.min()}")

    # Check for issues
    issues = []

    # Issue 1: One giant cluster (>50% of nodes)
    if sizes.max() > total_nodes * 0.5:
        issues.append({
            'type': 'giant_cluster',
            'size': int(sizes.max()),
            'percent': float(sizes.max() / total_nodes * 100)
        })

    # Issue 2: Too many tiny clusters (<10 nodes, >30% of clusters)
    tiny_clusters = int((sizes < 10).sum())
    if tiny_clusters / len(sizes) > 0.3:
        issues.append({
            'type': 'too_many_tiny',
            'count': tiny_clusters,
            'percent': float(tiny_clusters / len(sizes) * 100)
        })

    # Issue 3: Very uneven distribution (largest > 10x median)
    if sizes.max() > 10 * np.median(sizes):
        issues.append({
            'type': 'uneven_distribution',
            'largest': int(sizes.max()),
            'median': int(np.median(sizes)),
            'ratio': float(sizes.max() / np.median(sizes))
        })

    # Also check a sample of countries
    country_issues = []
    country_dir = CLUSTERS_DIR / "countries"

    for country_file in list(country_dir.glob("*.json"))[:20]:  # Sample 20 countries
        with open(country_file) as f:
            country_data = json.load(f)

        country_sizes = np.array([c['size'] for c in country_data['clusters']])
        country_total = country_sizes.sum()

        if country_sizes.max() > country_total * 0.5:
            country_issues.append({
                'country': country_data['country'],
                'largest_percent': float(country_sizes.max() / country_total * 100)
            })

    # Report
    print(f"\n{'~'*40}")

    if issues:
        print("UNIFIED 2024 Issues:")
        for issue in issues:
            if issue['type'] == 'giant_cluster':
                print(f"  Giant cluster: {issue['size']} nodes ({issue['percent']:.1f}% of total)")
            elif issue['type'] == 'too_many_tiny':
                print(f"  Too many tiny clusters: {issue['count']} ({issue['percent']:.1f}%)")
            elif issue['type'] == 'uneven_distribution':
                print(f"  Uneven: Largest {issue['largest']} vs median {issue['median']} (ratio: {issue['ratio']:.1f}x)")
    else:
        print("Unified 2024: All checks passed")

    if country_issues:
        print(f"\nCountries with giant clusters (>50%): {len(country_issues)}")
        for ci in country_issues[:3]:
            print(f"  {ci['country']}: {ci['largest_percent']:.1f}%")
    else:
        print("\nCountry sample: No giant clusters found")

    # Summary
    print(f"\n{'~'*40}")
    print("SUMMARY:")
    passed = len(issues) == 0
    print(f"  Unified issues: {len(issues)}")
    print(f"  Country giant clusters: {len(country_issues)}")
    print(f"  STATUS: {'PASS' if passed else 'FAIL'}")

    return {
        'unified_issues': issues,
        'country_giant_clusters': len(country_issues),
        'total_clusters': len(sizes),
        'total_nodes': int(total_nodes),
        'size_stats': {
            'mean': float(sizes.mean()),
            'median': float(np.median(sizes)),
            'min': int(sizes.min()),
            'max': int(sizes.max())
        },
        'passed': passed
    }


if __name__ == '__main__':
    result = check_cluster_size_distribution()
    exit(0 if result['passed'] else 1)
