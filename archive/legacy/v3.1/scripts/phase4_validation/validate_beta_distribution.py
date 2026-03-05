#!/usr/bin/env python3
"""
Beta Distribution Validation - Ensure betas are in reasonable range.
"""

import json
import numpy as np
from pathlib import Path

BASE_DIR = Path("<repo-root>/v3.1")

def check_beta_distribution():
    """Validate that betas are in reasonable range."""

    all_betas = []
    extreme_betas = []

    # Check unified graphs
    unified_dir = BASE_DIR / 'data/v3_1_temporal_graphs/unified'

    for year in range(1990, 2025):
        file = unified_dir / f'{year}_graph.json'
        if file.exists():
            with open(file) as f:
                data = json.load(f)

            for edge in data['edges']:
                beta = edge['beta']
                all_betas.append(beta)

                if abs(beta) > 3:
                    extreme_betas.append({
                        'year': year,
                        'edge': f"{edge['source']} → {edge['target']}",
                        'beta': beta,
                        'p_value': edge.get('p_value'),
                        'n_samples': edge.get('n_samples')
                    })

    # Statistics
    betas = np.array(all_betas)

    print(f"\n{'='*60}")
    print("BETA DISTRIBUTION VALIDATION")
    print(f"{'='*60}")
    print(f"Total betas: {len(betas):,}")
    print(f"Mean: {betas.mean():.3f}")
    print(f"Std: {betas.std():.3f}")
    print(f"Min: {betas.min():.3f}")
    print(f"Max: {betas.max():.3f}")
    print(f"Median: {np.median(betas):.3f}")
    print(f"\nPercentiles:")
    print(f"  1%: {np.percentile(betas, 1):.3f}")
    print(f"  5%: {np.percentile(betas, 5):.3f}")
    print(f"  95%: {np.percentile(betas, 95):.3f}")
    print(f"  99%: {np.percentile(betas, 99):.3f}")

    extreme_pct = len(extreme_betas) / len(betas) * 100
    print(f"\nExtreme betas (|β| > 3): {len(extreme_betas)} ({extreme_pct:.2f}%)")

    if extreme_betas:
        print("\n⚠️  Top 10 Extreme Betas:")
        for item in sorted(extreme_betas, key=lambda x: abs(x['beta']), reverse=True)[:10]:
            print(f"  {item['edge']}")
            print(f"    Year: {item['year']}, β={item['beta']:.3f}")
            p_val = item['p_value']
            if p_val is not None:
                print(f"    p={p_val:.2e}, n={item['n_samples']}")

    # Validation checks
    print("\n" + "-"*40)
    print("Validation Checks:")

    passed = True

    # Check 1: Mean should be close to 0 (but not necessarily exactly 0 for real causal effects)
    if abs(betas.mean()) > 0.5:
        print(f"  ⚠️  Mean beta ({betas.mean():.3f}) far from 0")
    else:
        print(f"  ✅ Mean beta ({betas.mean():.3f}) reasonable")

    # Check 2: Std should be reasonable
    if betas.std() > 2.0:
        print(f"  ⚠️  High variance in betas (std={betas.std():.3f})")
    else:
        print(f"  ✅ Beta variance reasonable (std={betas.std():.3f})")

    # Check 3: <1% extreme values
    if extreme_pct > 1:
        print(f"  ❌ Too many extreme betas: {extreme_pct:.2f}% > 1%")
        passed = False
    else:
        print(f"  ✅ Extreme betas acceptable: {extreme_pct:.2f}% < 1%")

    if passed:
        print("\n✅ PASS: Beta distribution looks reasonable")
    else:
        print("\n❌ FAIL: Beta distribution has issues")

    return len(extreme_betas)

if __name__ == '__main__':
    check_beta_distribution()
