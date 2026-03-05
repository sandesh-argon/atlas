#!/usr/bin/env python3
"""
P-Value Distribution Validation - Verify significance levels make sense.
"""

import json
import numpy as np
from pathlib import Path

BASE_DIR = Path("<repo-root>/v3.1")

def check_p_value_distribution():
    """Verify p-values make sense."""

    p_values = []

    # Check 2024 (most data)
    file = BASE_DIR / 'data/v3_1_temporal_graphs/unified/2024_graph.json'

    if not file.exists():
        print("❌ 2024 unified graph not found")
        return 1

    with open(file) as f:
        data = json.load(f)

    for edge in data['edges']:
        p = edge.get('p_value')
        if p is not None:
            p_values.append(p)

    p_values = np.array(p_values)

    print(f"\n{'='*60}")
    print("P-VALUE DISTRIBUTION VALIDATION")
    print(f"{'='*60}")
    print(f"Total p-values: {len(p_values):,}")

    sig_05 = (p_values < 0.05).sum()
    sig_01 = (p_values < 0.01).sum()
    sig_001 = (p_values < 0.001).sum()
    not_sig = (p_values >= 0.05).sum()

    print(f"\nSignificance breakdown:")
    print(f"  p < 0.001: {sig_001:>6,} ({sig_001/len(p_values)*100:.1f}%)")
    print(f"  p < 0.01:  {sig_01:>6,} ({sig_01/len(p_values)*100:.1f}%)")
    print(f"  p < 0.05:  {sig_05:>6,} ({sig_05/len(p_values)*100:.1f}%)")
    print(f"  p >= 0.05: {not_sig:>6,} ({not_sig/len(p_values)*100:.1f}%)")

    # P-value distribution statistics
    print(f"\nP-value statistics:")
    print(f"  Mean: {p_values.mean():.4f}")
    print(f"  Median: {np.median(p_values):.4f}")
    print(f"  Min: {p_values.min():.2e}")
    print(f"  Max: {p_values.max():.4f}")

    # Validation
    print("\n" + "-"*40)
    print("Validation Checks:")

    sig_rate = sig_05 / len(p_values) * 100

    # For a real causal graph, we expect high significance
    if sig_rate >= 70 and sig_rate <= 99:
        print(f"  ✅ Significance rate ({sig_rate:.1f}%) in expected range (70-99%)")
        print("\n✅ PASS: High significance rate expected for true causal edges")
    elif sig_rate > 99:
        print(f"  ⚠️  Significance rate ({sig_rate:.1f}%) unusually high")
        print("\n⚠️  WARNING: Almost all edges significant - check for issues")
    else:
        print(f"  ⚠️  Significance rate ({sig_rate:.1f}%) lower than expected")
        print("\n⚠️  WARNING: Only {sig_rate:.1f}% of edges significant")

    return 0

if __name__ == '__main__':
    check_p_value_distribution()
