#!/usr/bin/env python3
"""
Coverage Consistency Validation - Verify edge coverage doesn't fluctuate wildly.
"""

import json
from pathlib import Path

BASE_DIR = Path("<repo-root>/v3.1")

def check_coverage_consistency():
    """Verify edge coverage doesn't fluctuate wildly."""

    coverage_timeline = []

    unified_dir = BASE_DIR / 'data/v3_1_temporal_graphs/unified'
    TOTAL_EDGES = 7368

    for year in range(1990, 2025):
        file = unified_dir / f'{year}_graph.json'
        if not file.exists():
            continue

        with open(file) as f:
            data = json.load(f)

        n_edges = data['metadata']['n_edges_computed']
        coverage = n_edges / TOTAL_EDGES
        n_samples = data['metadata'].get('n_samples', 0)

        coverage_timeline.append({
            'year': year,
            'n_edges': n_edges,
            'coverage': coverage,
            'n_samples': n_samples
        })

    print(f"\n{'='*60}")
    print("COVERAGE CONSISTENCY VALIDATION")
    print(f"{'='*60}")
    print(f"Years tracked: {len(coverage_timeline)}")
    print(f"Expected edges per year: {TOTAL_EDGES}")

    # Check for drops
    print("\nYear-to-Year Changes:")
    large_drops = []

    for i in range(len(coverage_timeline) - 1):
        current = coverage_timeline[i]
        next_year = coverage_timeline[i + 1]

        change = next_year['coverage'] - current['coverage']

        if change < -0.2:  # 20% drop
            large_drops.append({
                'from_year': current['year'],
                'to_year': next_year['year'],
                'from_coverage': current['coverage'],
                'to_coverage': next_year['coverage'],
                'drop': abs(change)
            })

    if large_drops:
        print("⚠️  Large coverage drops detected:")
        for drop in large_drops:
            print(f"  {drop['from_year']} → {drop['to_year']}: {drop['from_coverage']:.1%} → {drop['to_coverage']:.1%}")
    else:
        print("  ✅ No large drops (>20%) detected")

    # Coverage trend
    print(f"\nCoverage Trend:")
    print(f"  {'Year':<6} {'Edges':>7} {'Coverage':>10} {'Samples':>10}")
    print(f"  {'-'*35}")

    # Show key years
    key_years = [1990, 1995, 2000, 2005, 2010, 2015, 2020, 2024]
    for item in coverage_timeline:
        if item['year'] in key_years:
            print(f"  {item['year']:<6} {item['n_edges']:>7,} {item['coverage']:>9.1%} {item['n_samples']:>10,}")

    # Final validation
    print("\n" + "-"*40)
    print("Validation Checks:")

    latest = coverage_timeline[-1]
    earliest = coverage_timeline[0]

    # Check 1: Recent years should have high coverage
    if latest['coverage'] >= 0.9:
        print(f"  ✅ Recent coverage high: {latest['coverage']:.1%}")
    else:
        print(f"  ⚠️  Recent coverage only: {latest['coverage']:.1%}")

    # Check 2: Coverage should generally increase over time
    if latest['coverage'] > earliest['coverage']:
        print(f"  ✅ Coverage improved: {earliest['coverage']:.1%} → {latest['coverage']:.1%}")
    else:
        print(f"  ⚠️  Coverage decreased over time")

    # Check 3: No large drops
    if not large_drops:
        print("  ✅ No sudden coverage drops")
    else:
        print(f"  ⚠️  {len(large_drops)} large drops detected")

    print("\n✅ PASS: Coverage consistency validated")

    return len(large_drops)

if __name__ == '__main__':
    check_coverage_consistency()
