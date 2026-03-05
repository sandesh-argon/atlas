#!/usr/bin/env python3
"""
Generate data quality metrics from V2.1 actual tier metadata.

Uses the REAL imputation tracking from V2's preprocessing:
- Tier 'observed': Original data point (no imputation)
- Tier 'interpolated': Imputed via temporal interpolation or MICE

Output: data/metadata/country_data_quality.json
"""

import json
import pickle
import pandas as pd
import numpy as np
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime
from tqdm import tqdm

# Paths
V31_ROOT = Path(__file__).parent.parent
V21_PREPROCESSED = Path("<repo-root>/v2.1/outputs/A2_preprocessed_data_V21.pkl")
OUTPUT_PATH = V31_ROOT / "data" / "metadata" / "country_data_quality.json"

# Quality thresholds
COMPLETE_OBSERVED_THRESHOLD = 0.50  # >50% observed = complete
PARTIAL_OBSERVED_THRESHOLD = 0.25   # 25-50% observed = partial


def classify_quality(observed_pct: float) -> str:
    """
    Classify year quality based on observed (non-imputed) percentage.

    Returns: 'complete', 'partial', or 'sparse'
    """
    if observed_pct >= COMPLETE_OBSERVED_THRESHOLD * 100:
        return 'complete'
    elif observed_pct >= PARTIAL_OBSERVED_THRESHOLD * 100:
        return 'partial'
    else:
        return 'sparse'


def classify_confidence(avg_observed_pct: float) -> str:
    """
    Classify overall country confidence based on average observed percentage.

    Returns: 'high', 'medium', or 'low'
    """
    if avg_observed_pct >= 50:
        return 'high'
    elif avg_observed_pct >= 30:
        return 'medium'
    else:
        return 'low'


def main():
    print("Loading V2.1 preprocessed data with tier metadata...")
    with open(V21_PREPROCESSED, 'rb') as f:
        v21_data = pickle.load(f)

    tier_data = v21_data['tier_data']
    imputed_data = v21_data['imputed_data']

    print(f"Loaded {len(tier_data)} indicators with tier tracking")

    # Get all countries and years from tier data
    sample_ind = list(tier_data.keys())[0]
    all_countries = list(tier_data[sample_ind].index)
    years = [int(y) for y in tier_data[sample_ind].columns]

    print(f"Countries in tier data: {len(all_countries)}")
    print(f"Years: {years[0]} - {years[-1]}")

    # Get canonical countries from V3.1 temporal graphs
    countries_dir = V31_ROOT / "data" / "v3_1_temporal_graphs" / "countries"
    if countries_dir.exists():
        canonical_countries = [d.name for d in countries_dir.iterdir() if d.is_dir()]
    else:
        canonical_countries = all_countries

    print(f"Canonical countries (V3.1): {len(canonical_countries)}")

    # Map canonical names to tier data index names
    # (tier data uses same names, but let's verify)
    tier_country_set = set(all_countries)
    matched = [c for c in canonical_countries if c in tier_country_set]
    unmatched = [c for c in canonical_countries if c not in tier_country_set]

    print(f"Matched: {len(matched)}, Unmatched: {len(unmatched)}")
    if unmatched:
        print(f"Sample unmatched: {unmatched[:5]}")

    # Pre-compute per-country/year tier stats
    print("\nComputing per-country/year tier statistics...")

    # Initialize storage
    country_year_stats = defaultdict(lambda: defaultdict(dict))

    # Process all indicators and aggregate by country/year
    for ind_name in tqdm(tier_data.keys(), desc="Processing indicators"):
        tier_df = tier_data[ind_name]

        for country in tier_df.index:
            for year in tier_df.columns:
                tier_val = tier_df.loc[country, year]

                if country not in country_year_stats:
                    country_year_stats[country] = defaultdict(lambda: {'observed': 0, 'interpolated': 0, 'total': 0})

                year_int = int(year)
                country_year_stats[country][year_int]['total'] += 1

                if tier_val == 'observed':
                    country_year_stats[country][year_int]['observed'] += 1
                else:  # 'interpolated' or any other value
                    country_year_stats[country][year_int]['interpolated'] += 1

    # Build quality data for canonical countries
    print("\nBuilding quality data...")
    quality_data = {}

    total_indicators = len(tier_data)

    for country in tqdm(canonical_countries, desc="Processing canonical countries"):
        if country not in country_year_stats:
            # Country not in tier data - mark as low quality
            quality_data[country] = {
                "total_indicators": 0,
                "coverage_pct": 0.0,
                "observed_pct": 0.0,
                "imputed_pct": 100.0,
                "confidence": "low",
                "by_year": {str(y): {
                    "quality": "sparse",
                    "indicators": 0,
                    "observed": 0,
                    "observed_pct": 0.0,
                    "imputed_pct": 100.0
                } for y in years}
            }
            continue

        stats = country_year_stats[country]

        # Build per-year data
        by_year = {}
        year_observed_pcts = []
        year_indicator_counts = []

        for year in years:
            if year in stats:
                s = stats[year]
                n_total = s['total']
                n_observed = s['observed']
                n_interpolated = s['interpolated']

                observed_pct = (n_observed / n_total * 100) if n_total > 0 else 0
                imputed_pct = (n_interpolated / n_total * 100) if n_total > 0 else 100
                coverage_pct = (n_total / total_indicators * 100) if total_indicators > 0 else 0

                quality = classify_quality(observed_pct)

                by_year[str(year)] = {
                    "quality": quality,
                    "indicators": n_total,
                    "observed": n_observed,
                    "observed_pct": round(observed_pct, 1),
                    "imputed_pct": round(imputed_pct, 1),
                    "coverage_pct": round(coverage_pct, 1)
                }

                year_observed_pcts.append(observed_pct)
                year_indicator_counts.append(n_total)
            else:
                by_year[str(year)] = {
                    "quality": "sparse",
                    "indicators": 0,
                    "observed": 0,
                    "observed_pct": 0.0,
                    "imputed_pct": 100.0,
                    "coverage_pct": 0.0
                }
                year_observed_pcts.append(0)
                year_indicator_counts.append(0)

        # Compute overall stats
        avg_observed_pct = np.mean(year_observed_pcts) if year_observed_pcts else 0
        avg_imputed_pct = 100 - avg_observed_pct
        max_indicators = max(year_indicator_counts) if year_indicator_counts else 0
        avg_coverage = np.mean([(c / total_indicators * 100) for c in year_indicator_counts]) if year_indicator_counts else 0

        confidence = classify_confidence(avg_observed_pct)

        quality_data[country] = {
            "total_indicators": max_indicators,
            "coverage_pct": round(avg_coverage, 1),
            "observed_pct": round(avg_observed_pct, 1),
            "imputed_pct": round(avg_imputed_pct, 1),
            "confidence": confidence,
            "by_year": by_year
        }

    # Add metadata
    output = {
        "metadata": {
            "generated_at": datetime.now().isoformat(),
            "source": "V2.1 A2_preprocessed_data_V21.pkl tier_data",
            "total_indicators_in_dataset": total_indicators,
            "years": years,
            "n_countries": len(quality_data),
            "tier_definitions": {
                "observed": "Original data point (no imputation needed)",
                "interpolated": "Imputed via temporal interpolation or MICE"
            },
            "quality_thresholds": {
                "complete": f"observed_pct >= {COMPLETE_OBSERVED_THRESHOLD * 100}%",
                "partial": f"observed_pct >= {PARTIAL_OBSERVED_THRESHOLD * 100}%",
                "sparse": f"observed_pct < {PARTIAL_OBSERVED_THRESHOLD * 100}%"
            },
            "confidence_thresholds": {
                "high": "avg_observed >= 50%",
                "medium": "avg_observed >= 30%",
                "low": "avg_observed < 30%"
            }
        },
        "countries": quality_data
    }

    # Save
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, 'w') as f:
        json.dump(output, f, indent=2)

    print(f"\nSaved to {OUTPUT_PATH}")

    # Summary stats
    confidences = [d['confidence'] for d in quality_data.values()]
    print(f"\nConfidence distribution:")
    print(f"  High: {confidences.count('high')}")
    print(f"  Medium: {confidences.count('medium')}")
    print(f"  Low: {confidences.count('low')}")

    # Overall tier distribution
    total_observed = sum(s[y]['observed'] for s in country_year_stats.values() for y in s)
    total_all = sum(s[y]['total'] for s in country_year_stats.values() for y in s)
    print(f"\nOverall tier distribution:")
    print(f"  Observed: {total_observed / total_all * 100:.1f}%")
    print(f"  Interpolated: {(total_all - total_observed) / total_all * 100:.1f}%")

    # Sample output
    print("\nSample entries:")
    for country in ['Australia', 'Rwanda', 'Afghanistan'][:3]:
        if country in quality_data:
            d = quality_data[country]
            print(f"  {country}: {d['observed_pct']:.1f}% observed, {d['imputed_pct']:.1f}% imputed, {d['confidence']} confidence")


if __name__ == "__main__":
    main()
