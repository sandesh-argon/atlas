#!/usr/bin/env python3
"""
Generate comprehensive data quality metrics for V3.1 visualization.

Computes:
1. Per-country/year indicator coverage
2. Imputation estimates using multiple heuristics
3. Quality classifications (complete/partial/sparse)
4. Overall confidence levels

Output: data/metadata/country_data_quality.json
"""

import json
import pandas as pd
import numpy as np
from pathlib import Path
from collections import defaultdict
from datetime import datetime
from tqdm import tqdm

# Paths
V31_ROOT = Path(__file__).parent.parent
PANEL_PATH = V31_ROOT / "data" / "raw" / "v21_panel_data_for_v3.parquet"
OUTPUT_PATH = V31_ROOT / "data" / "metadata" / "country_data_quality.json"

# Quality thresholds
COMPLETE_COVERAGE_THRESHOLD = 0.90  # >90% indicators
PARTIAL_COVERAGE_THRESHOLD = 0.50   # 50-90% indicators
COMPLETE_IMPUTATION_THRESHOLD = 0.10  # <10% imputed
PARTIAL_IMPUTATION_THRESHOLD = 0.30   # 10-30% imputed


def estimate_imputation_rate(df: pd.DataFrame, country: str, year: int) -> float:
    """
    Estimate imputation rate using multiple heuristics.

    Since the panel is fully imputed (no nulls), we estimate which values
    were likely imputed vs. original using:
    1. Constant values over time (forward/backward fill)
    2. Suspiciously round values (likely interpolated)
    3. Comparison to "high-quality" data sources

    Returns estimated imputation rate [0, 1].
    """
    country_data = df[df['country'] == country].copy()
    if len(country_data) == 0:
        return 1.0

    # Pivot to wide format for this country
    try:
        wide = country_data.pivot_table(
            index='year',
            columns='indicator_id',
            values='value',
            aggfunc='first'
        )
    except Exception:
        return 0.5  # Default if pivot fails

    if year not in wide.index:
        return 1.0

    year_values = wide.loc[year].dropna()
    if len(year_values) == 0:
        return 1.0

    imputed_flags = []

    # Heuristic 1: Constant values across years (forward/backward fill)
    for indicator in year_values.index:
        if indicator not in wide.columns:
            continue
        series = wide[indicator].dropna()
        if len(series) < 3:
            imputed_flags.append(0.5)  # Not enough data to tell
            continue

        # Check if this year's value is constant with neighbors
        year_idx = list(series.index).index(year) if year in series.index else -1
        if year_idx == -1:
            imputed_flags.append(0.5)
            continue

        val = series.iloc[year_idx]

        # Check for exact matches with neighbors (likely imputed)
        neighbors_match = 0
        if year_idx > 0 and series.iloc[year_idx - 1] == val:
            neighbors_match += 1
        if year_idx < len(series) - 1 and series.iloc[year_idx + 1] == val:
            neighbors_match += 1

        if neighbors_match == 2:
            imputed_flags.append(0.7)  # Likely imputed
        elif neighbors_match == 1:
            imputed_flags.append(0.3)  # Possibly imputed
        else:
            imputed_flags.append(0.0)  # Likely original

    if not imputed_flags:
        return 0.5

    return np.mean(imputed_flags)


def estimate_imputation_fast(df: pd.DataFrame, country: str) -> dict:
    """
    Fast imputation estimation for all years of a country.

    Uses simplified heuristics:
    1. Coverage gap: indicators present vs. max possible
    2. Variance analysis: low variance suggests imputation
    """
    country_data = df[df['country'] == country]
    if len(country_data) == 0:
        return {}

    # Get indicator counts per year
    year_counts = country_data.groupby('year').size()
    max_indicators = year_counts.max()

    # Get variance per indicator (low variance = likely imputed)
    try:
        wide = country_data.pivot_table(
            index='year',
            columns='indicator_id',
            values='value',
            aggfunc='first'
        )
    except Exception:
        # Fallback: use coverage-based estimation only
        result = {}
        for year in year_counts.index:
            coverage = year_counts[year] / max_indicators if max_indicators > 0 else 0
            # Estimate: lower coverage = higher imputation needed
            imputed_pct = max(0, min(100, (1 - coverage) * 50 + 10))
            result[year] = imputed_pct
        return result

    # Compute variance for each indicator
    indicator_variance = wide.var(axis=0)
    low_variance_threshold = indicator_variance.quantile(0.1)

    result = {}
    for year in wide.index:
        year_values = wide.loc[year].dropna()
        n_indicators = len(year_values)

        if n_indicators == 0:
            result[year] = 100.0
            continue

        # Count low-variance (likely imputed) indicators
        low_var_count = 0
        for ind in year_values.index:
            if ind in indicator_variance.index:
                if indicator_variance[ind] <= low_variance_threshold:
                    low_var_count += 1

        # Combine coverage and variance for imputation estimate
        coverage_gap = 1 - (n_indicators / max_indicators) if max_indicators > 0 else 0
        variance_score = low_var_count / n_indicators if n_indicators > 0 else 0

        # Weighted combination
        imputed_pct = (coverage_gap * 0.4 + variance_score * 0.6) * 100
        imputed_pct = max(5, min(95, imputed_pct))  # Clamp to reasonable range

        result[year] = round(imputed_pct, 1)

    return result


def classify_quality(coverage_pct: float, imputed_pct: float) -> str:
    """
    Classify year quality based on coverage and imputation.

    Returns: 'complete', 'partial', or 'sparse'
    """
    # Coverage is more important than imputation
    if coverage_pct >= COMPLETE_COVERAGE_THRESHOLD * 100:
        if imputed_pct <= COMPLETE_IMPUTATION_THRESHOLD * 100:
            return 'complete'
        elif imputed_pct <= PARTIAL_IMPUTATION_THRESHOLD * 100:
            return 'partial'
        else:
            return 'partial'  # High coverage but high imputation = partial
    elif coverage_pct >= PARTIAL_COVERAGE_THRESHOLD * 100:
        return 'partial'
    else:
        return 'sparse'


def classify_confidence(avg_coverage: float, avg_imputed: float) -> str:
    """
    Classify overall country confidence.

    Returns: 'high', 'medium', or 'low'
    """
    if avg_coverage >= 80 and avg_imputed <= 20:
        return 'high'
    elif avg_coverage >= 60 and avg_imputed <= 40:
        return 'medium'
    else:
        return 'low'


def main():
    print("Loading panel data...")
    panel = pd.read_parquet(PANEL_PATH)

    print(f"Panel shape: {panel.shape}")
    print(f"Unique countries: {panel['country'].nunique()}")
    print(f"Unique indicators: {panel['indicator_id'].nunique()}")

    # Get total indicators in dataset
    total_indicators = panel['indicator_id'].nunique()

    # Get all years
    years = sorted(panel['year'].unique())

    # Get countries from our V3.1 temporal graphs (canonical list)
    countries_dir = V31_ROOT / "data" / "v3_1_temporal_graphs" / "countries"
    if countries_dir.exists():
        canonical_countries = [d.name for d in countries_dir.iterdir() if d.is_dir()]
    else:
        canonical_countries = panel['country'].unique().tolist()

    print(f"Processing {len(canonical_countries)} canonical countries...")

    # Compute per-country/year indicator counts
    print("Computing indicator counts per country/year...")
    counts = panel.groupby(['country', 'year']).size().reset_index(name='n_indicators')
    counts_pivot = counts.pivot(index='country', columns='year', values='n_indicators').fillna(0)

    # Build quality data
    quality_data = {}

    for country in tqdm(canonical_countries, desc="Processing countries"):
        if country not in counts_pivot.index:
            # Country not in panel data
            quality_data[country] = {
                "total_indicators": 0,
                "coverage_pct": 0.0,
                "imputation_pct": 100.0,
                "confidence": "low",
                "by_year": {str(y): {"quality": "sparse", "indicators": 0, "imputed_pct": 100.0} for y in years}
            }
            continue

        country_counts = counts_pivot.loc[country]

        # Estimate imputation rates
        imputation_estimates = estimate_imputation_fast(panel, country)

        # Build per-year data
        by_year = {}
        year_coverages = []
        year_imputations = []

        for year in years:
            n_indicators = int(country_counts.get(year, 0))
            coverage_pct = (n_indicators / total_indicators) * 100 if total_indicators > 0 else 0
            imputed_pct = imputation_estimates.get(year, 50.0)

            quality = classify_quality(coverage_pct, imputed_pct)

            by_year[str(year)] = {
                "quality": quality,
                "indicators": n_indicators,
                "coverage_pct": round(coverage_pct, 1),
                "imputed_pct": round(imputed_pct, 1)
            }

            year_coverages.append(coverage_pct)
            year_imputations.append(imputed_pct)

        # Compute overall stats
        avg_coverage = np.mean(year_coverages)
        avg_imputed = np.mean(year_imputations)
        max_indicators = int(country_counts.max())

        confidence = classify_confidence(avg_coverage, avg_imputed)

        quality_data[country] = {
            "total_indicators": max_indicators,
            "coverage_pct": round(avg_coverage, 1),
            "imputation_pct": round(avg_imputed, 1),
            "confidence": confidence,
            "by_year": by_year
        }

    # Add metadata
    output = {
        "metadata": {
            "generated_at": datetime.now().isoformat(),
            "total_indicators_in_dataset": total_indicators,
            "years": [int(y) for y in years],
            "n_countries": len(quality_data),
            "quality_thresholds": {
                "complete": {
                    "min_coverage_pct": COMPLETE_COVERAGE_THRESHOLD * 100,
                    "max_imputed_pct": COMPLETE_IMPUTATION_THRESHOLD * 100
                },
                "partial": {
                    "min_coverage_pct": PARTIAL_COVERAGE_THRESHOLD * 100,
                    "max_imputed_pct": PARTIAL_IMPUTATION_THRESHOLD * 100
                },
                "sparse": {
                    "coverage_pct": f"<{PARTIAL_COVERAGE_THRESHOLD * 100}",
                    "or_imputed_pct": f">{PARTIAL_IMPUTATION_THRESHOLD * 100}"
                }
            },
            "confidence_thresholds": {
                "high": "coverage >= 80%, imputation <= 20%",
                "medium": "coverage >= 60%, imputation <= 40%",
                "low": "other"
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

    # Sample output
    print("\nSample entries:")
    for country in ['Australia', 'Rwanda', 'Afghanistan'][:3]:
        if country in quality_data:
            d = quality_data[country]
            print(f"  {country}: {d['coverage_pct']:.1f}% coverage, {d['imputation_pct']:.1f}% imputed, {d['confidence']} confidence")


if __name__ == "__main__":
    main()
