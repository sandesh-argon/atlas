#!/usr/bin/env python3
"""
Phase 1 Pre-Flight: Audit Panel Data for V3.1 Temporal Computation

Checks:
1. Data structure (long format: country, year, indicator_id, value)
2. Year coverage per country
3. Indicator coverage per year
4. Recommends MIN_YEAR_FOR_SHAP and MIN_YEAR_FOR_GRAPHS
5. Identifies countries with sufficient temporal data

Output: data/v3_1_data_audit.json
"""

import json
import sys
from pathlib import Path
from datetime import datetime

import pandas as pd
import numpy as np

# Paths
PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
PANEL_PATH = DATA_DIR / "raw" / "v21_panel_data_for_v3.parquet"
OUTPUT_PATH = DATA_DIR / "v3_1_data_audit.json"

# Minimum thresholds
MIN_INDICATORS_FOR_SHAP = 50      # Need at least 50 indicators
MIN_YEARS_FOR_SHAP = 5            # Need at least 5 years of data
MIN_YEARS_FOR_GRAPHS = 10         # Need at least 10 years for stable betas
MIN_COUNTRIES_FOR_YEAR = 100      # Year needs at least 100 countries


def load_panel_data() -> pd.DataFrame:
    """Load panel data and verify structure."""
    print("Loading panel data...")
    df = pd.read_parquet(PANEL_PATH)

    print(f"  Shape: {df.shape[0]:,} rows × {df.shape[1]} columns")
    print(f"  Columns: {df.columns.tolist()}")

    # Verify required columns
    required_cols = ['country', 'year', 'indicator_id', 'value']
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        print(f"  ERROR: Missing columns: {missing}")
        sys.exit(1)

    print("  Structure: VALID (long format)")
    return df


def analyze_year_coverage(df: pd.DataFrame) -> dict:
    """Analyze data coverage by year."""
    print("\nAnalyzing year coverage...")

    coverage = {}
    for year in range(1990, 2025):
        year_data = df[df['year'] == year]

        if len(year_data) == 0:
            coverage[year] = {
                'countries': 0,
                'indicators': 0,
                'observations': 0,
                'usable_for_shap': False,
                'usable_for_graphs': False
            }
            continue

        n_countries = year_data['country'].nunique()
        n_indicators = year_data['indicator_id'].nunique()
        n_obs = len(year_data)

        coverage[year] = {
            'countries': n_countries,
            'indicators': n_indicators,
            'observations': n_obs,
            'usable_for_shap': n_countries >= MIN_COUNTRIES_FOR_YEAR,
            'usable_for_graphs': n_countries >= MIN_COUNTRIES_FOR_YEAR
        }

        print(f"  {year}: {n_countries} countries, {n_indicators} indicators, {n_obs:,} obs")

    return coverage


def analyze_country_coverage(df: pd.DataFrame) -> dict:
    """Analyze data coverage by country."""
    print("\nAnalyzing country coverage...")

    # Get unique countries from V3.0 graph files (these are the ones we care about)
    graphs_dir = DATA_DIR / "country_graphs"
    v30_countries = set()
    if graphs_dir.exists():
        v30_countries = {f.stem for f in graphs_dir.glob("*.json")}
        print(f"  V3.0 countries with graphs: {len(v30_countries)}")

    # Analyze coverage per country
    country_stats = {}
    countries_in_data = df['country'].unique()

    for country in countries_in_data:
        country_data = df[df['country'] == country]

        years_with_data = sorted(country_data['year'].unique())
        n_years = len(years_with_data)
        n_indicators = country_data['indicator_id'].nunique()

        # Check if enough data for temporal analysis
        has_enough_years_shap = n_years >= MIN_YEARS_FOR_SHAP
        has_enough_years_graph = n_years >= MIN_YEARS_FOR_GRAPHS
        has_enough_indicators = n_indicators >= MIN_INDICATORS_FOR_SHAP

        country_stats[country] = {
            'year_range': [int(min(years_with_data)), int(max(years_with_data))],
            'n_years': n_years,
            'n_indicators': n_indicators,
            'usable_for_shap': has_enough_years_shap and has_enough_indicators,
            'usable_for_graphs': has_enough_years_graph and has_enough_indicators,
            'in_v30_graphs': country in v30_countries
        }

    # Summary
    usable_shap = sum(1 for c in country_stats.values() if c['usable_for_shap'])
    usable_graphs = sum(1 for c in country_stats.values() if c['usable_for_graphs'])

    print(f"  Total countries in data: {len(country_stats)}")
    print(f"  Usable for temporal SHAP: {usable_shap}")
    print(f"  Usable for temporal graphs: {usable_graphs}")

    return country_stats


def determine_min_years(year_coverage: dict) -> tuple:
    """Determine minimum years to start computation."""
    print("\nDetermining minimum years...")

    min_year_shap = None
    min_year_graphs = None

    for year in range(1990, 2025):
        if year_coverage[year]['countries'] >= MIN_COUNTRIES_FOR_YEAR:
            if min_year_shap is None:
                min_year_shap = year
            # For graphs, need cumulative 10+ years
            if year - 1990 >= MIN_YEARS_FOR_GRAPHS - 1 and min_year_graphs is None:
                min_year_graphs = year

    # Fallback to reasonable defaults
    if min_year_shap is None:
        min_year_shap = 1995
    if min_year_graphs is None:
        min_year_graphs = 2000

    print(f"  Recommended MIN_YEAR_FOR_SHAP: {min_year_shap}")
    print(f"  Recommended MIN_YEAR_FOR_GRAPHS: {min_year_graphs}")

    return min_year_shap, min_year_graphs


def compute_file_estimates(min_year_shap: int, min_year_graphs: int,
                           country_stats: dict) -> dict:
    """Estimate output file counts based on usable countries/years."""

    # Count usable countries
    usable_countries_shap = sum(1 for c in country_stats.values() if c['usable_for_shap'])
    usable_countries_graphs = sum(1 for c in country_stats.values() if c['usable_for_graphs'])

    # Year counts
    shap_years = 2024 - min_year_shap + 1
    graph_years = 2024 - min_year_graphs + 1

    # File estimates
    n_targets = 9
    n_regions = 11

    shap_files = n_targets * (usable_countries_shap + 1) * shap_years  # +1 for unified
    regional_shap_files = n_targets * n_regions * shap_years
    graph_files = (usable_countries_graphs + 1) * graph_years  # +1 for unified
    spillover_files = shap_years
    feedback_files = usable_countries_graphs + 1

    return {
        'temporal_shap': {
            'countries': usable_countries_shap + 1,
            'targets': n_targets,
            'years': shap_years,
            'total_files': shap_files
        },
        'regional_shap': {
            'regions': n_regions,
            'targets': n_targets,
            'years': shap_years,
            'total_files': regional_shap_files
        },
        'temporal_graphs': {
            'countries': usable_countries_graphs + 1,
            'years': graph_years,
            'total_files': graph_files
        },
        'spillovers': {
            'years': shap_years,
            'total_files': spillover_files
        },
        'feedback_loops': {
            'countries': usable_countries_graphs + 1,
            'total_files': feedback_files
        },
        'grand_total': shap_files + regional_shap_files + graph_files + spillover_files + feedback_files
    }


def main():
    """Run full data audit."""
    print("=" * 60)
    print("V3.1 Pre-Flight Data Audit")
    print("=" * 60)

    # Load data
    df = load_panel_data()

    # Analyze coverage
    year_coverage = analyze_year_coverage(df)
    country_stats = analyze_country_coverage(df)

    # Determine minimum years
    min_year_shap, min_year_graphs = determine_min_years(year_coverage)

    # Compute file estimates
    file_estimates = compute_file_estimates(min_year_shap, min_year_graphs, country_stats)

    # Build report
    report = {
        'audit_date': datetime.now().isoformat(),
        'panel_structure': {
            'format': 'long',
            'columns': ['country', 'year', 'indicator_id', 'value'],
            'total_rows': int(len(df)),
            'year_range': [1990, 2024],
            'unique_countries': int(df['country'].nunique()),
            'unique_indicators': int(df['indicator_id'].nunique())
        },
        'coverage_by_year': {str(k): v for k, v in year_coverage.items()},
        'recommended_config': {
            'MIN_YEAR_FOR_SHAP': min_year_shap,
            'MIN_YEAR_FOR_GRAPHS': min_year_graphs,
            'SHAP_YEARS': list(range(min_year_shap, 2025)),
            'GRAPH_YEARS': list(range(min_year_graphs, 2025))
        },
        'file_estimates': file_estimates,
        'country_summary': {
            'total_in_data': len(country_stats),
            'usable_for_shap': sum(1 for c in country_stats.values() if c['usable_for_shap']),
            'usable_for_graphs': sum(1 for c in country_stats.values() if c['usable_for_graphs'])
        },
        'thresholds_used': {
            'MIN_INDICATORS_FOR_SHAP': MIN_INDICATORS_FOR_SHAP,
            'MIN_YEARS_FOR_SHAP': MIN_YEARS_FOR_SHAP,
            'MIN_YEARS_FOR_GRAPHS': MIN_YEARS_FOR_GRAPHS,
            'MIN_COUNTRIES_FOR_YEAR': MIN_COUNTRIES_FOR_YEAR
        }
    }

    # Save report
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, 'w') as f:
        json.dump(report, f, indent=2)

    # Print summary
    print("\n" + "=" * 60)
    print("AUDIT SUMMARY")
    print("=" * 60)
    print(f"Panel data: {len(df):,} observations")
    print(f"Countries usable for SHAP: {report['country_summary']['usable_for_shap']}")
    print(f"Countries usable for graphs: {report['country_summary']['usable_for_graphs']}")
    print(f"")
    print(f"Recommended configuration:")
    print(f"  MIN_YEAR_FOR_SHAP: {min_year_shap} ({2024 - min_year_shap + 1} years)")
    print(f"  MIN_YEAR_FOR_GRAPHS: {min_year_graphs} ({2024 - min_year_graphs + 1} years)")
    print(f"")
    print(f"Estimated output files:")
    print(f"  Temporal SHAP: {file_estimates['temporal_shap']['total_files']:,}")
    print(f"  Regional SHAP: {file_estimates['regional_shap']['total_files']:,}")
    print(f"  Temporal Graphs: {file_estimates['temporal_graphs']['total_files']:,}")
    print(f"  Spillovers: {file_estimates['spillovers']['total_files']}")
    print(f"  Feedback Loops: {file_estimates['feedback_loops']['total_files']}")
    print(f"  TOTAL: {file_estimates['grand_total']:,}")
    print(f"")
    print(f"Report saved to: {OUTPUT_PATH}")
    print("=" * 60)

    # Status check
    if report['country_summary']['usable_for_shap'] >= 100:
        print("\n READY TO PROCEED WITH PHASE 1")
    else:
        print("\n WARNING: Limited country coverage - review report")

    return report


if __name__ == "__main__":
    main()
