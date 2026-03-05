#!/usr/bin/env python3
"""
A1 Validation 1: Verify Temporal Alignment Across Indicators
=============================================================
Checks if indicators have sufficient temporal overlap for Granger causality (≥20 years).
"""

import pandas as pd
import numpy as np
import pickle
from pathlib import Path
from collections import defaultdict
import itertools

# Paths
BASE_DIR = Path(__file__).parent.parent
CHECKPOINT = BASE_DIR / "outputs" / "A1_imputed_data.pkl"

def load_checkpoint():
    """Load A1 imputed data checkpoint"""
    print("Loading A1 checkpoint...")
    with open(CHECKPOINT, 'rb') as f:
        data = pickle.load(f)
    print(f"✅ Loaded {len(data['imputed_data'])} indicators")
    return data

def get_temporal_range(indicator_df):
    """Get min and max year for an indicator (across all countries)"""
    # Years are column names
    years = [int(col) for col in indicator_df.columns if str(col).isdigit()]
    if not years:
        return None, None
    return min(years), max(years)

def count_valid_years(indicator_df):
    """Count years with at least one non-null value across all countries"""
    valid_years = 0
    for col in indicator_df.columns:
        if str(col).isdigit() and indicator_df[col].notna().any():
            valid_years += 1
    return valid_years

def compute_overlap(range1, range2):
    """Compute overlapping years between two temporal ranges"""
    min1, max1 = range1
    min2, max2 = range2

    if min1 is None or min2 is None:
        return 0

    overlap_start = max(min1, min2)
    overlap_end = min(max1, max2)

    if overlap_start > overlap_end:
        return 0

    return overlap_end - overlap_start + 1

def main():
    print("=" * 80)
    print("A1 VALIDATION 1: TEMPORAL ALIGNMENT CHECK")
    print("=" * 80)
    print()

    # Load data
    checkpoint_data = load_checkpoint()
    imputed_data = checkpoint_data['imputed_data']
    print()

    # Compute temporal ranges for all indicators
    print("Computing temporal ranges for all indicators...")
    temporal_ranges = {}
    valid_year_counts = {}

    for name, df in imputed_data.items():
        min_year, max_year = get_temporal_range(df)
        temporal_ranges[name] = (min_year, max_year)
        valid_year_counts[name] = count_valid_years(df)

    # Filter out indicators with no temporal data
    valid_indicators = {k: v for k, v in temporal_ranges.items() if v[0] is not None}
    print(f"✅ {len(valid_indicators)} indicators have valid temporal data")
    print()

    # Statistics on temporal ranges
    print("=" * 80)
    print("TEMPORAL RANGE STATISTICS")
    print("=" * 80)

    min_years = [r[0] for r in valid_indicators.values()]
    max_years = [r[1] for r in valid_indicators.values()]
    spans = [r[1] - r[0] + 1 for r in valid_indicators.values()]

    print(f"Start years: {min(min_years)} - {max(min_years)} (median: {np.median(min_years):.0f})")
    print(f"End years: {min(max_years)} - {max(max_years)} (median: {np.median(max_years):.0f})")
    print(f"Temporal spans: {min(spans)} - {max(spans)} years (median: {np.median(spans):.0f})")
    print()

    # Find "orphan indicators" with very old start dates
    print("Pre-1960 indicators (potential orphans):")
    pre_1960 = [(name, r) for name, r in valid_indicators.items() if r[0] < 1960]
    for name, (min_y, max_y) in sorted(pre_1960, key=lambda x: x[1][0])[:10]:
        print(f"  {name}: {min_y}-{max_y} ({max_y - min_y + 1} years)")
    print(f"  ... {len(pre_1960)} total indicators start before 1960")
    print()

    # Sample pairwise overlap (test 10,000 random pairs)
    print("=" * 80)
    print("PAIRWISE OVERLAP ANALYSIS (10,000 random pairs)")
    print("=" * 80)

    indicator_list = list(valid_indicators.keys())
    sample_size = min(10000, len(indicator_list) * (len(indicator_list) - 1) // 2)

    overlaps = []
    for _ in range(sample_size):
        idx1, idx2 = np.random.choice(len(indicator_list), 2, replace=False)
        name1, name2 = indicator_list[idx1], indicator_list[idx2]
        overlap = compute_overlap(valid_indicators[name1], valid_indicators[name2])
        overlaps.append(overlap)

    overlaps = np.array(overlaps)

    print(f"Overlap distribution (years):")
    print(f"  Mean: {overlaps.mean():.1f} years")
    print(f"  Median: {np.median(overlaps):.1f} years")
    print(f"  Min-Max: {overlaps.min()}-{overlaps.max()} years")
    print()

    # Critical thresholds for Granger causality
    print("Granger causality requirements:")
    pct_20plus = (overlaps >= 20).mean() * 100
    pct_30plus = (overlaps >= 30).mean() * 100
    pct_40plus = (overlaps >= 40).mean() * 100

    print(f"  ≥20 years overlap: {pct_20plus:.1f}% of pairs ({'✅ PASS' if pct_20plus >= 90 else '⚠️ WARNING'})")
    print(f"  ≥30 years overlap: {pct_30plus:.1f}% of pairs")
    print(f"  ≥40 years overlap: {pct_40plus:.1f}% of pairs")
    print()

    # Find orphan indicators with <10 year overlap with others
    print("=" * 80)
    print("ORPHAN INDICATORS (<10 YEAR OVERLAP WITH MOST INDICATORS)")
    print("=" * 80)

    orphan_candidates = []
    for name in list(valid_indicators.keys())[:100]:  # Test first 100 for speed
        overlaps_with_others = []
        for other_name in indicator_list[:100]:
            if name != other_name:
                overlap = compute_overlap(valid_indicators[name], valid_indicators[other_name])
                overlaps_with_others.append(overlap)

        mean_overlap = np.mean(overlaps_with_others)
        if mean_overlap < 10:
            orphan_candidates.append((name, mean_overlap, valid_indicators[name]))

    if orphan_candidates:
        print("Found potential orphans:")
        for name, avg_overlap, (min_y, max_y) in sorted(orphan_candidates, key=lambda x: x[1])[:10]:
            print(f"  {name}: {min_y}-{max_y}, avg overlap {avg_overlap:.1f} years")
    else:
        print("✅ No orphan indicators found (all have ≥10 year avg overlap)")
    print()

    # Golden temporal window analysis
    print("=" * 80)
    print("GOLDEN TEMPORAL WINDOW ANALYSIS")
    print("=" * 80)

    windows = [
        (1990, 2024, "1990-2024"),
        (1995, 2024, "1995-2024"),
        (2000, 2024, "2000-2024"),
    ]

    for start, end, label in windows:
        # Count indicators with ≥80% coverage in window
        window_span = end - start + 1
        min_required_years = int(window_span * 0.80)

        indicators_in_window = 0
        for name, (min_y, max_y) in valid_indicators.items():
            # Check if indicator covers this window
            if min_y <= start and max_y >= end:
                # Indicator spans full window
                indicators_in_window += 1
            elif min_y <= end and max_y >= start:
                # Partial overlap - check if ≥80% coverage
                overlap_start = max(min_y, start)
                overlap_end = min(max_y, end)
                overlap_years = overlap_end - overlap_start + 1
                if overlap_years >= min_required_years:
                    indicators_in_window += 1

        pct = indicators_in_window / len(valid_indicators) * 100
        print(f"{label}: {indicators_in_window:,} indicators ({pct:.1f}%) have ≥80% coverage")

    print()

    # Recommendation
    print("=" * 80)
    print("RECOMMENDATION")
    print("=" * 80)

    if pct_20plus >= 90:
        print("✅ PASS: ≥90% of indicator pairs have sufficient overlap (≥20 years) for Granger")
        print("   → No temporal alignment issues expected in A2")
    elif pct_20plus >= 75:
        print("⚠️ WARNING: 75-90% of pairs have ≥20 year overlap")
        print("   → Consider applying golden window filter (1990-2024) in A2 preprocessing")
    else:
        print("❌ FAIL: <75% of pairs have sufficient overlap")
        print("   → MUST apply golden window filter before A2 or expect many failed Granger tests")

    print()
    print("Suggested golden window: 1990-2024 (best balance of coverage and span)")
    print()

if __name__ == "__main__":
    main()
