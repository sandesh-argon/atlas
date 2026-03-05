#!/usr/bin/env python3
"""
Phase 3B Validation: Cluster Density Realism

Verifies cluster density is in reasonable range:
- Mean density 0.02-0.10
- No cluster >0.30 density (over-connected)
- Large clusters (>20 nodes) shouldn't have <0.01 density
"""

import json
import numpy as np
from pathlib import Path

BASE_DIR = Path("<repo-root>/v3.1")
CLUSTERS_DIR = BASE_DIR / "data" / "v3_1_development_clusters"


def check_cluster_density():
    """
    Verify cluster density is in reasonable range.
    """

    file = CLUSTERS_DIR / "unified" / "2024_clusters.json"
    with open(file) as f:
        data = json.load(f)

    print(f"\n{'='*60}")
    print("VALIDATION 5: CLUSTER DENSITY")
    print(f"{'='*60}")

    issues = []
    densities = []

    for cluster in data['clusters']:
        density = cluster.get('density', 0)
        densities.append(density)

        # Flag very high density (>0.30) - suggests over-connected
        if density > 0.30:
            issues.append({
                'cluster': cluster['name'],
                'density': density,
                'size': cluster['size'],
                'issue': 'very_high_density'
            })
        # Flag very low density for large clusters
        elif density < 0.01 and cluster['size'] > 20:
            issues.append({
                'cluster': cluster['name'],
                'density': density,
                'size': cluster['size'],
                'issue': 'very_low_density'
            })

    densities = np.array(densities)

    print(f"Total clusters: {len(densities)}")
    print(f"Mean density: {densities.mean():.4f}")
    print(f"Median density: {np.median(densities):.4f}")
    print(f"Min density: {densities.min():.4f}")
    print(f"Max density: {densities.max():.4f}")

    # Check if mean is in expected range
    mean_in_range = 0.02 <= densities.mean() <= 0.10

    print(f"\nExpected mean range: [0.02, 0.10]")
    print(f"Mean in range: {'Yes' if mean_in_range else 'No'}")

    print(f"\n{'~'*40}")

    if issues:
        print(f"Density Issues ({len(issues)}):")
        for issue in issues[:10]:
            print(f"  {issue['cluster']}: density={issue['density']:.4f}, size={issue['size']} ({issue['issue']})")
    else:
        print("All cluster densities are reasonable")

    # Also check sample of country files
    country_high_density = 0
    country_dir = CLUSTERS_DIR / "countries"

    for country_file in country_dir.glob("*.json"):
        with open(country_file) as f:
            country_data = json.load(f)

        for cluster in country_data['clusters']:
            if cluster.get('density', 0) > 0.30:
                country_high_density += 1

    print(f"\nCountry files: {country_high_density} clusters with density > 0.30")

    # Summary
    print(f"\n{'~'*40}")
    print("SUMMARY:")

    # Pass if mean in range and <5 high density issues
    passed = mean_in_range and len([i for i in issues if i['issue'] == 'very_high_density']) < 5

    print(f"  Mean in range: {mean_in_range}")
    print(f"  High density issues: {len([i for i in issues if i['issue'] == 'very_high_density'])}")
    print(f"  STATUS: {'PASS' if passed else 'WARN'}")

    return {
        'density_stats': {
            'mean': float(densities.mean()),
            'median': float(np.median(densities)),
            'min': float(densities.min()),
            'max': float(densities.max())
        },
        'mean_in_range': mean_in_range,
        'issues': len(issues),
        'high_density_issues': len([i for i in issues if i['issue'] == 'very_high_density']),
        'low_density_issues': len([i for i in issues if i['issue'] == 'very_low_density']),
        'country_high_density': country_high_density,
        'passed': passed
    }


if __name__ == '__main__':
    result = check_cluster_density()
    exit(0 if result['passed'] else 1)
