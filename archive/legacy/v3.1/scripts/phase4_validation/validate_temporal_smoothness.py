#!/usr/bin/env python3
"""
Temporal Smoothness Validation - Flag edges where beta changes >0.5 in single year.
"""

import json
import numpy as np
from pathlib import Path

BASE_DIR = Path("<repo-root>/v3.1")

def check_temporal_smoothness():
    """Flag edges where beta changes >0.5 in single year."""

    issues = []

    # Test unified graphs (easiest to validate)
    unified_dir = BASE_DIR / 'data/v3_1_temporal_graphs/unified'

    # Load all years
    timeline = {}
    for year in range(1990, 2025):
        file = unified_dir / f'{year}_graph.json'
        if file.exists():
            with open(file) as f:
                timeline[year] = json.load(f)

    # Check each edge
    edge_timelines = {}
    for year, graph in timeline.items():
        for edge in graph['edges']:
            key = (edge['source'], edge['target'])
            if key not in edge_timelines:
                edge_timelines[key] = {}
            edge_timelines[key][year] = edge['beta']

    # Detect jumps
    for edge_key, years_data in edge_timelines.items():
        sorted_years = sorted(years_data.keys())

        for i in range(len(sorted_years) - 1):
            year_a = sorted_years[i]
            year_b = sorted_years[i + 1]

            beta_a = years_data[year_a]
            beta_b = years_data[year_b]

            change = abs(beta_b - beta_a)

            if change > 0.5:  # Suspicious jump
                issues.append({
                    'edge': f"{edge_key[0]} → {edge_key[1]}",
                    'year_from': year_a,
                    'year_to': year_b,
                    'beta_from': round(beta_a, 3),
                    'beta_to': round(beta_b, 3),
                    'change': round(change, 3),
                    'severity': 'critical' if change > 1.0 else 'warning'
                })

    # Report
    print(f"\n{'='*60}")
    print("TEMPORAL SMOOTHNESS VALIDATION")
    print(f"{'='*60}")
    print(f"Total edges tracked: {len(edge_timelines)}")
    print(f"Total year-to-year transitions: {sum(len(v)-1 for v in edge_timelines.values() if len(v) > 1)}")
    print(f"Issues found: {len(issues)}")

    # Calculate percentage
    total_transitions = sum(len(v)-1 for v in edge_timelines.values() if len(v) > 1)
    pct_issues = len(issues) / total_transitions * 100 if total_transitions > 0 else 0
    print(f"Issue rate: {pct_issues:.2f}%")

    if issues:
        # Count by severity
        critical = sum(1 for i in issues if i['severity'] == 'critical')
        warning = sum(1 for i in issues if i['severity'] == 'warning')
        print(f"\n  Critical (>1.0 change): {critical}")
        print(f"  Warning (0.5-1.0 change): {warning}")

        print("\n⚠️  Top 20 Suspicious Year-to-Year Changes:")
        for issue in sorted(issues, key=lambda x: x['change'], reverse=True)[:20]:
            print(f"  {issue['edge']}")
            print(f"    {issue['year_from']}: β={issue['beta_from']}")
            print(f"    {issue['year_to']}: β={issue['beta_to']}")
            print(f"    Change: {issue['change']} ({issue['severity']})")
            print()
    else:
        print("✅ All edges show smooth temporal progression")

    # Pass/fail
    if pct_issues < 5:
        print(f"\n✅ PASS: Issue rate {pct_issues:.2f}% < 5%")
    else:
        print(f"\n❌ FAIL: Issue rate {pct_issues:.2f}% >= 5%")

    # Save report
    report_path = BASE_DIR / 'data/v3_1_temporal_graphs/smoothness_report.json'
    with open(report_path, 'w') as f:
        json.dump({
            'total_edges': len(edge_timelines),
            'total_transitions': total_transitions,
            'n_issues': len(issues),
            'issue_rate_pct': pct_issues,
            'max_acceptable_change': 0.5,
            'issues': issues
        }, f, indent=2)

    return len(issues)

if __name__ == '__main__':
    n_issues = check_temporal_smoothness()
    exit(0 if n_issues < 100 else 1)
