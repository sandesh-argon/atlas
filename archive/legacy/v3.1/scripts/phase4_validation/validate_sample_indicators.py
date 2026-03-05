#!/usr/bin/env python3
"""
Phase 3B Validation: Sample Indicators Quality

Verifies sample indicators are present and reasonable:
- All clusters have sample indicators
- Sample count is consistent (3-5 per cluster)
- Sample labels aren't empty or too short
"""

import json
from pathlib import Path

BASE_DIR = Path("<repo-root>/v3.1")
CLUSTERS_DIR = BASE_DIR / "data" / "v3_1_development_clusters"


def check_sample_indicators():
    """
    Verify sample indicators are present and reasonable.
    """

    file = CLUSTERS_DIR / "unified" / "2024_clusters.json"
    with open(file) as f:
        data = json.load(f)

    print(f"\n{'='*60}")
    print("VALIDATION 6: SAMPLE INDICATORS")
    print(f"{'='*60}")

    issues = []
    sample_counts = []

    for cluster in data['clusters']:
        sample_indicators = cluster.get('sample_indicators', [])
        sample_counts.append(len(sample_indicators))

        # Check 1: No samples
        if not sample_indicators:
            issues.append({
                'cluster': cluster['name'],
                'issue': 'no_samples'
            })
            continue

        # Check 2: Too few samples
        if len(sample_indicators) < 3:
            issues.append({
                'cluster': cluster['name'],
                'issue': 'too_few_samples',
                'count': len(sample_indicators)
            })

        # Check 3: Empty or very short labels
        short_labels = [s for s in sample_indicators if len(s) < 5]
        if short_labels:
            issues.append({
                'cluster': cluster['name'],
                'issue': 'short_labels',
                'count': len(short_labels)
            })

    # Report
    print(f"Total clusters: {len(data['clusters'])}")
    print(f"Sample count range: {min(sample_counts)}-{max(sample_counts)}")
    print(f"Mean samples per cluster: {sum(sample_counts)/len(sample_counts):.1f}")

    print(f"\n{'~'*40}")

    if issues:
        print(f"Issues Found ({len(issues)}):")
        for issue in issues[:10]:
            if issue['issue'] == 'no_samples':
                print(f"  {issue['cluster']}: No sample indicators")
            elif issue['issue'] == 'too_few_samples':
                print(f"  {issue['cluster']}: Only {issue['count']} samples")
            elif issue['issue'] == 'short_labels':
                print(f"  {issue['cluster']}: {issue['count']} very short labels")
    else:
        print("All clusters have adequate sample indicators")

    # Check country files too
    country_issues = 0
    country_dir = CLUSTERS_DIR / "countries"

    for country_file in country_dir.glob("*.json"):
        with open(country_file) as f:
            country_data = json.load(f)

        for cluster in country_data['clusters']:
            if not cluster.get('sample_indicators'):
                country_issues += 1

    print(f"\nCountry files: {country_issues} clusters without samples")

    # Sample output
    print(f"\n{'~'*40}")
    print("Sample indicators from largest cluster:")
    largest = max(data['clusters'], key=lambda x: x['size'])
    for ind in largest.get('sample_indicators', [])[:5]:
        print(f"  - {ind}")

    # Summary
    print(f"\n{'~'*40}")
    print("SUMMARY:")

    # Pass if no clusters missing samples
    passed = len([i for i in issues if i['issue'] == 'no_samples']) == 0

    print(f"  Clusters missing samples: {len([i for i in issues if i['issue'] == 'no_samples'])}")
    print(f"  Country clusters missing: {country_issues}")
    print(f"  STATUS: {'PASS' if passed else 'FAIL'}")

    return {
        'total_clusters': len(data['clusters']),
        'sample_count_range': [min(sample_counts), max(sample_counts)],
        'issues': len(issues),
        'no_samples': len([i for i in issues if i['issue'] == 'no_samples']),
        'too_few_samples': len([i for i in issues if i['issue'] == 'too_few_samples']),
        'country_issues': country_issues,
        'passed': passed
    }


if __name__ == '__main__':
    result = check_sample_indicators()
    exit(0 if result['passed'] else 1)
