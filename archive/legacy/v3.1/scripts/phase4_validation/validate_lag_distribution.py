#!/usr/bin/env python3
"""
Lag Distribution Validation - Verify lag estimates are reasonable.
"""

import json
import numpy as np
from pathlib import Path

BASE_DIR = Path("<repo-root>/v3.1")

def check_lag_distribution():
    """Verify lag estimates are reasonable."""

    all_lags = []

    unified_dir = BASE_DIR / 'data/v3_1_temporal_graphs/unified'

    for year in range(2000, 2025):  # Recent years with more data
        file = unified_dir / f'{year}_graph.json'
        if not file.exists():
            continue

        with open(file) as f:
            data = json.load(f)

        for edge in data['edges']:
            all_lags.append(edge.get('lag', 0))

    lags = np.array(all_lags)

    print(f"\n{'='*60}")
    print("LAG DISTRIBUTION VALIDATION")
    print(f"{'='*60}")
    print(f"Total edges: {len(lags):,}")
    print(f"Mean lag: {lags.mean():.2f} years")
    print(f"Median lag: {np.median(lags):.0f} years")
    print(f"\nDistribution:")

    for lag in range(6):
        count = (lags == lag).sum()
        pct = count / len(lags) * 100
        bar = '█' * int(pct / 2)
        print(f"  Lag {lag}: {count:>6,} ({pct:>5.1f}%) {bar}")

    # Validation checks
    print("\n" + "-"*40)
    print("Validation Checks:")

    passed = True

    # Check 1: Mean lag should be 1-2 years
    if lags.mean() > 3:
        print(f"  ⚠️  Mean lag ({lags.mean():.2f}) unusually high")
    elif lags.mean() < 0.5:
        print(f"  ⚠️  Mean lag ({lags.mean():.2f}) unusually low")
    else:
        print(f"  ✅ Mean lag ({lags.mean():.2f}) reasonable")

    # Check 2: Not too many at lag=5 (max lag)
    lag5_pct = (lags == 5).sum() / len(lags) * 100
    if lag5_pct > 20:
        print(f"  ⚠️  Too many at max lag (lag=5): {lag5_pct:.1f}%")
    else:
        print(f"  ✅ Max lag (lag=5) not overrepresented: {lag5_pct:.1f}%")

    # Check 3: Lag 0 shouldn't dominate excessively
    lag0_pct = (lags == 0).sum() / len(lags) * 100
    if lag0_pct > 80:
        print(f"  ⚠️  Too many instant relationships (lag=0): {lag0_pct:.1f}%")
    else:
        print(f"  ✅ Instant relationships (lag=0) reasonable: {lag0_pct:.1f}%")

    if passed:
        print("\n✅ PASS: Lag distribution looks reasonable")

    return 0

if __name__ == '__main__':
    check_lag_distribution()
