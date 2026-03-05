#!/usr/bin/env python3
"""
Phase 3B Validation: Cluster Stability Check

Verifies that clusters don't change drastically year-to-year.
Since we don't store full node lists (to save space), we use
cluster size and domain composition as proxies for stability.
"""

import json
import numpy as np
from pathlib import Path
from collections import defaultdict

BASE_DIR = Path("<repo-root>/v3.1")
CLUSTERS_DIR = BASE_DIR / "data" / "v3_1_development_clusters"


def domain_composition_similarity(comp_a: dict, comp_b: dict) -> float:
    """
    Compute similarity between two domain compositions using cosine similarity.
    """
    all_domains = set(comp_a.keys()) | set(comp_b.keys())

    vec_a = np.array([comp_a.get(d, 0) for d in all_domains])
    vec_b = np.array([comp_b.get(d, 0) for d in all_domains])

    # Normalize
    norm_a = np.linalg.norm(vec_a)
    norm_b = np.linalg.norm(vec_b)

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return float(np.dot(vec_a, vec_b) / (norm_a * norm_b))


def check_temporal_cluster_stability():
    """
    Verify clusters don't change drastically year-to-year (unified graphs).
    Uses domain composition similarity as proxy since nodes aren't stored.
    """

    unified_dir = CLUSTERS_DIR / "unified"

    # Load all years
    timeline = {}
    for year in range(1990, 2025):
        file = unified_dir / f'{year}_clusters.json'
        if file.exists():
            with open(file) as f:
                timeline[year] = json.load(f)

    print(f"\n{'='*60}")
    print("VALIDATION 1: TEMPORAL CLUSTER STABILITY")
    print(f"{'='*60}")
    print(f"Years loaded: {len(timeline)}")

    # Track year-to-year changes
    instabilities = []
    all_transitions = []

    sorted_years = sorted(timeline.keys())

    for i in range(len(sorted_years) - 1):
        year_a = sorted_years[i]
        year_b = sorted_years[i + 1]

        clusters_a = timeline[year_a]['clusters']
        clusters_b = timeline[year_b]['clusters']

        # Match clusters by best domain composition similarity
        for cluster_a in clusters_a:
            comp_a = cluster_a.get('domain_composition', {})

            # Find best match in year_b
            best_match = None
            best_similarity = 0

            for cluster_b in clusters_b:
                comp_b = cluster_b.get('domain_composition', {})
                similarity = domain_composition_similarity(comp_a, comp_b)

                if similarity > best_similarity:
                    best_similarity = similarity
                    best_match = cluster_b

            transition = {
                'year_from': year_a,
                'year_to': year_b,
                'cluster_a': cluster_a['name'],
                'cluster_b': best_match['name'] if best_match else 'NONE',
                'size_a': cluster_a['size'],
                'size_b': best_match['size'] if best_match else 0,
                'similarity': best_similarity
            }
            all_transitions.append(transition)

            # Flag unstable transitions (similarity < 0.7 for domain composition)
            if best_similarity < 0.7:
                instabilities.append(transition)

    # Also check cluster count stability
    cluster_counts = [timeline[y]['summary']['n_clusters'] for y in sorted_years]
    count_changes = np.diff(cluster_counts)
    large_count_changes = np.sum(np.abs(count_changes) > 3)

    # Report
    print(f"\nTotal year-to-year transitions: {len(all_transitions)}")
    print(f"Unstable transitions (similarity < 0.7): {len(instabilities)}")
    print(f"Large cluster count changes (>3): {large_count_changes}")

    instability_rate = len(instabilities) / len(all_transitions) if all_transitions else 0

    if instabilities:
        print(f"\n{'~'*40}")
        print("Sample Unstable Transitions (first 5):")
        for item in instabilities[:5]:
            print(f"  {item['year_from']} -> {item['year_to']}: {item['cluster_a']}")
            print(f"    Best match: {item['cluster_b']} (similarity: {item['similarity']:.2f})")
            print(f"    Size: {item['size_a']} -> {item['size_b']}")

    # Summary
    print(f"\n{'~'*40}")
    print("SUMMARY:")
    print(f"  Instability rate: {instability_rate*100:.1f}%")

    passed = instability_rate < 0.20  # Pass if <20% unstable

    if passed:
        print("  STATUS: PASS")
    else:
        print("  STATUS: FAIL (>20% unstable)")

    return {
        'total_transitions': len(all_transitions),
        'unstable_transitions': len(instabilities),
        'instability_rate': instability_rate,
        'large_count_changes': int(large_count_changes),
        'cluster_count_range': [int(min(cluster_counts)), int(max(cluster_counts))],
        'passed': passed
    }


if __name__ == '__main__':
    result = check_temporal_cluster_stability()
    exit(0 if result['passed'] else 1)
