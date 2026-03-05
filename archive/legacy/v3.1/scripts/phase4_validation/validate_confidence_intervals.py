#!/usr/bin/env python3
"""
Confidence Interval Validation - Verify CI bounds bracket beta correctly.
"""

import json
from pathlib import Path

BASE_DIR = Path("<repo-root>/v3.1")

def check_confidence_intervals():
    """Verify CI bounds are correct."""

    violations = []
    total_edges = 0

    unified_dir = BASE_DIR / 'data/v3_1_temporal_graphs/unified'

    for year in range(1990, 2025):
        file = unified_dir / f'{year}_graph.json'
        if not file.exists():
            continue

        with open(file) as f:
            data = json.load(f)

        for edge in data['edges']:
            total_edges += 1
            beta = edge['beta']
            ci_lower = edge.get('ci_lower')
            ci_upper = edge.get('ci_upper')

            if ci_lower is None or ci_upper is None:
                violations.append({
                    'type': 'missing_ci',
                    'year': year,
                    'edge': f"{edge['source']} → {edge['target']}"
                })
            elif ci_lower > ci_upper:
                violations.append({
                    'type': 'inverted_ci',
                    'year': year,
                    'edge': f"{edge['source']} → {edge['target']}",
                    'ci_lower': ci_lower,
                    'ci_upper': ci_upper
                })
            elif ci_lower > beta + 0.001 or ci_upper < beta - 0.001:
                # Allow small tolerance for floating point
                violations.append({
                    'type': 'beta_outside_ci',
                    'year': year,
                    'edge': f"{edge['source']} → {edge['target']}",
                    'beta': beta,
                    'ci_lower': ci_lower,
                    'ci_upper': ci_upper
                })

    print(f"\n{'='*60}")
    print("CONFIDENCE INTERVAL VALIDATION")
    print(f"{'='*60}")
    print(f"Total edges checked: {total_edges:,}")
    print(f"Violations found: {len(violations)}")

    if violations:
        # Group by type
        by_type = {}
        for v in violations:
            t = v['type']
            by_type[t] = by_type.get(t, 0) + 1

        print("\nViolation breakdown:")
        for t, count in by_type.items():
            print(f"  {t}: {count}")

        print("\n❌ Sample CI Issues:")
        for v in violations[:10]:
            if v['type'] == 'missing_ci':
                print(f"  Missing CI: {v['edge']} (year {v['year']})")
            elif v['type'] == 'inverted_ci':
                print(f"  Inverted CI: {v['edge']} (year {v['year']})")
                print(f"    ci_lower={v['ci_lower']:.3f} > ci_upper={v['ci_upper']:.3f}")
            else:
                print(f"  Beta outside CI: {v['edge']} (year {v['year']})")
                print(f"    β={v['beta']:.3f}, CI=[{v['ci_lower']:.3f}, {v['ci_upper']:.3f}]")
    else:
        print("\n✅ PASS: All CIs are valid")

    return len(violations)

if __name__ == '__main__':
    n = check_confidence_intervals()
    exit(0 if n == 0 else 1)
