#!/usr/bin/env python3
"""
Phase 3B Validation: Domain Composition Sanity

Verifies clusters have coherent domain structure:
- Domain counts sum to cluster size
- Primary domain is actually dominant (>20%)
- Mixed clusters are truly mixed (no domain >25%)
"""

import json
from pathlib import Path

BASE_DIR = Path("<repo-root>/v3.1")
CLUSTERS_DIR = BASE_DIR / "data" / "v3_1_development_clusters"


def check_domain_composition():
    """
    Verify clusters have coherent domain structure.
    """

    file = CLUSTERS_DIR / "unified" / "2024_clusters.json"
    with open(file) as f:
        data = json.load(f)

    print(f"\n{'='*60}")
    print("VALIDATION 3: DOMAIN COMPOSITION")
    print(f"{'='*60}")

    issues = []
    stats = {
        'total_clusters': len(data['clusters']),
        'domain_mismatches': 0,
        'weak_primary': 0,
        'false_mixed': 0
    }

    for cluster in data['clusters']:
        domain_comp = cluster.get('domain_composition', {})
        total_nodes = cluster['size']

        # Check 1: Domain counts add up to cluster size
        domain_sum = sum(domain_comp.values())

        if domain_sum != total_nodes:
            issues.append({
                'type': 'domain_count_mismatch',
                'cluster': cluster['name'],
                'expected': total_nodes,
                'actual': domain_sum,
                'diff': abs(total_nodes - domain_sum)
            })
            stats['domain_mismatches'] += 1

        # Check 2: Primary domain is actually dominant (>20%)
        primary = cluster.get('primary_domain')
        if primary and primary in domain_comp:
            primary_count = domain_comp[primary]
            primary_pct = primary_count / total_nodes if total_nodes > 0 else 0

            if primary_pct < 0.20:
                issues.append({
                    'type': 'weak_primary_domain',
                    'cluster': cluster['name'],
                    'primary_domain': primary,
                    'primary_percent': primary_pct * 100
                })
                stats['weak_primary'] += 1

        # Check 3: "Mixed" clusters should have no domain >25%
        if 'Mixed' in cluster['name']:
            max_domain_pct = max(domain_comp.values()) / total_nodes if domain_comp and total_nodes > 0 else 0

            if max_domain_pct > 0.25:
                issues.append({
                    'type': 'false_mixed_cluster',
                    'cluster': cluster['name'],
                    'max_domain_percent': max_domain_pct * 100
                })
                stats['false_mixed'] += 1

    # Also check country files for domain mismatches
    country_mismatches = 0
    country_dir = CLUSTERS_DIR / "countries"

    for country_file in country_dir.glob("*.json"):
        with open(country_file) as f:
            country_data = json.load(f)

        for cluster in country_data['clusters']:
            domain_comp = cluster.get('domain_composition', {})
            total_nodes = cluster['size']
            domain_sum = sum(domain_comp.values())

            if domain_sum != total_nodes:
                country_mismatches += 1

    # Report
    print(f"Total clusters (unified 2024): {stats['total_clusters']}")
    print(f"Domain count mismatches: {stats['domain_mismatches']}")
    print(f"Weak primary domains (<20%): {stats['weak_primary']}")
    print(f"False mixed clusters: {stats['false_mixed']}")
    print(f"Country file mismatches: {country_mismatches}")

    print(f"\n{'~'*40}")

    if issues:
        print("Issues Found:")
        for issue in issues[:10]:
            if issue['type'] == 'domain_count_mismatch':
                print(f"  Mismatch in {issue['cluster']}: expected {issue['expected']}, got {issue['actual']}")
            elif issue['type'] == 'weak_primary_domain':
                print(f"  Weak primary in {issue['cluster']}: {issue['primary_domain']} ({issue['primary_percent']:.1f}%)")
            elif issue['type'] == 'false_mixed_cluster':
                print(f"  False mixed: {issue['cluster']} (max domain: {issue['max_domain_percent']:.1f}%)")
    else:
        print("No issues found in unified 2024")

    # Summary
    print(f"\n{'~'*40}")
    print("SUMMARY:")
    # Pass if no domain mismatches and <10% weak primary
    passed = stats['domain_mismatches'] == 0 and stats['weak_primary'] < stats['total_clusters'] * 0.1
    print(f"  STATUS: {'PASS' if passed else 'FAIL'}")

    return {
        'unified_issues': len(issues),
        'domain_mismatches': stats['domain_mismatches'],
        'weak_primary': stats['weak_primary'],
        'false_mixed': stats['false_mixed'],
        'country_mismatches': country_mismatches,
        'passed': passed
    }


if __name__ == '__main__':
    result = check_domain_composition()
    exit(0 if result['passed'] else 1)
