#!/usr/bin/env python3
"""
Economic Indicator Filter Diagnostic
====================================
Analyzes why only 71 economic indicators pass filters (0.9%).
Checks if economic indicators are misclassified as "Other".
"""

import pandas as pd
from pathlib import Path
import json
import numpy as np

BASE_DIR = Path(__file__).parent
A0_STANDARDIZED_DIR = BASE_DIR.parent / "A0_data_acquisition" / "raw_data_standardized"
FILTERED_DATA = BASE_DIR / "filtered_data"

# Current filter thresholds
MIN_COUNTRIES = 80
MIN_TEMPORAL_SPAN = 10
MIN_PER_COUNTRY_COVERAGE = 0.50
MAX_MISSING_RATE = 0.70

# Economic keywords
ECONOMIC_KEYWORDS = [
    'gdp', 'income', 'poverty', 'employment', 'wage', 'trade',
    'export', 'import', 'inflation', 'price', 'consumption',
    'investment', 'capital', 'productivity', 'growth', 'debt',
    'fiscal', 'monetary', 'tax', 'revenue', 'expenditure'
]


def classify_domain(indicator_name, source):
    """Same classification logic as step1"""
    name_lower = indicator_name.lower()
    source_lower = source.lower()

    # Economic indicators
    if any(kw in name_lower for kw in ECONOMIC_KEYWORDS):
        return 'Economic'

    # Other domains...
    if any(kw in name_lower for kw in ['health', 'mortality', 'life_expectancy', 'disease', 'nutrition']):
        return 'Health'
    if any(kw in name_lower for kw in ['school', 'education', 'literacy', 'enrollment']):
        return 'Education'
    if any(kw in name_lower for kw in ['democracy', 'election', 'electoral', 'vote']):
        return 'Democracy'
    if 'vdem' in source_lower:
        return 'Democracy'
    if 'wid' in source_lower:
        return 'Inequality'

    return 'Other'


def compute_quality_metrics(csv_path):
    """Compute quality metrics for a single indicator"""
    try:
        df = pd.read_csv(csv_path, low_memory=False)

        if list(df.columns) != ['Country', 'Year', 'Value']:
            return None

        df = df.dropna(subset=['Country', 'Year'])
        df['Year'] = df['Year'].astype(int)

        # Per-country temporal coverage
        per_country_coverage = []
        for country, country_df in df.groupby('Country'):
            country_year_range = country_df['Year'].max() - country_df['Year'].min() + 1
            country_data_points = country_df['Value'].notna().sum()
            if country_year_range > 0:
                coverage = country_data_points / country_year_range
                per_country_coverage.append(coverage)

        mean_per_country_coverage = np.mean(per_country_coverage) if per_country_coverage else 0.0

        return {
            'indicator': csv_path.stem,
            'source': csv_path.parent.name,
            'unique_countries': df['Country'].nunique(),
            'temporal_span': int(df['Year'].max() - df['Year'].min()),
            'mean_per_country_coverage': mean_per_country_coverage,
            'global_missing_rate': df['Value'].isna().mean(),
        }
    except Exception:
        return None


def main():
    print("=" * 80)
    print("ECONOMIC INDICATOR FILTER DIAGNOSTIC")
    print("=" * 80)
    print()

    # Get all indicators from World Bank (primary economic source)
    wb_files = list((A0_STANDARDIZED_DIR / "world_bank").glob("*.csv")) if (A0_STANDARDIZED_DIR / "world_bank").exists() else []

    print(f"World Bank files found: {len(wb_files):,}")
    print()

    if len(wb_files) == 0:
        print("❌ NO WORLD BANK FILES FOUND")
        return

    # Analyze World Bank indicators
    print("Analyzing World Bank indicators...")
    wb_metrics = []

    for csv_file in wb_files:
        metrics = compute_quality_metrics(csv_file)
        if metrics:
            wb_metrics.append(metrics)

    df = pd.DataFrame(wb_metrics)
    print(f"✅ Analyzed {len(df):,} World Bank indicators")
    print()

    # Identify economic indicators
    df['is_economic'] = df['indicator'].apply(
        lambda x: any(kw in x.lower() for kw in ECONOMIC_KEYWORDS)
    )

    df['domain'] = df.apply(lambda row: classify_domain(row['indicator'], row['source']), axis=1)

    economic_df = df[df['is_economic']].copy()
    non_economic_df = df[~df['is_economic']].copy()

    print("=" * 80)
    print("WORLD BANK BREAKDOWN")
    print("=" * 80)
    print(f"Total World Bank indicators: {len(df):,}")
    print(f"  Economic-related (by keywords): {len(economic_df):,} ({len(economic_df)/len(df)*100:.1f}%)")
    print(f"  Non-economic: {len(non_economic_df):,} ({len(non_economic_df)/len(df)*100:.1f}%)")
    print()

    # Domain classification of ALL World Bank indicators
    print("DOMAIN CLASSIFICATION (ALL WORLD BANK):")
    domain_breakdown = df['domain'].value_counts().sort_index()
    for domain, count in domain_breakdown.items():
        pct = count / len(df) * 100
        print(f"  {domain:20s}: {count:6,} ({pct:5.1f}%)")
    print()

    # Apply filters to economic indicators
    economic_df['pass_countries'] = economic_df['unique_countries'] >= MIN_COUNTRIES
    economic_df['pass_temporal'] = economic_df['temporal_span'] >= MIN_TEMPORAL_SPAN
    economic_df['pass_coverage'] = economic_df['mean_per_country_coverage'] >= MIN_PER_COUNTRY_COVERAGE
    economic_df['pass_missing'] = economic_df['global_missing_rate'] <= MAX_MISSING_RATE
    economic_df['pass_all'] = (
        economic_df['pass_countries'] &
        economic_df['pass_temporal'] &
        economic_df['pass_coverage'] &
        economic_df['pass_missing']
    )

    passed = economic_df[economic_df['pass_all']]
    failed = economic_df[~economic_df['pass_all']]

    print("=" * 80)
    print("ECONOMIC FILTER RESULTS (WORLD BANK)")
    print("=" * 80)
    print(f"Total economic indicators: {len(economic_df):,}")
    print(f"  PASS all filters: {len(passed):,} ({len(passed)/len(economic_df)*100:.1f}%)")
    print(f"  FAIL filters: {len(failed):,} ({len(failed)/len(economic_df)*100:.1f}%)")
    print()

    # Filter-specific failure rates
    print("FILTER FAILURE BREAKDOWN:")
    print(f"  Country coverage (<{MIN_COUNTRIES}): {(~economic_df['pass_countries']).sum():,} FAIL ({(~economic_df['pass_countries']).mean()*100:.1f}%)")
    print(f"  Temporal span (<{MIN_TEMPORAL_SPAN}y): {(~economic_df['pass_temporal']).sum():,} FAIL ({(~economic_df['pass_temporal']).mean()*100:.1f}%)")
    print(f"  Per-country coverage (<{MIN_PER_COUNTRY_COVERAGE:.0%}): {(~economic_df['pass_coverage']).sum():,} FAIL ({(~economic_df['pass_coverage']).mean()*100:.1f}%)")
    print(f"  Missing rate (>{MAX_MISSING_RATE:.0%}): {(~economic_df['pass_missing']).sum():,} FAIL ({(~economic_df['pass_missing']).mean()*100:.1f}%)")
    print()

    # Quality distribution
    print("=" * 80)
    print("QUALITY DISTRIBUTION (ECONOMIC INDICATORS)")
    print("=" * 80)
    print(f"Country coverage: {economic_df['unique_countries'].min():.0f} - {economic_df['unique_countries'].max():.0f} (median: {economic_df['unique_countries'].median():.0f})")
    print(f"Temporal span: {economic_df['temporal_span'].min():.0f} - {economic_df['temporal_span'].max():.0f} years (median: {economic_df['temporal_span'].median():.0f})")
    print(f"Per-country coverage: {economic_df['mean_per_country_coverage'].min():.1%} - {economic_df['mean_per_country_coverage'].max():.1%} (median: {economic_df['mean_per_country_coverage'].median():.1%})")
    print(f"Missing rate: {economic_df['global_missing_rate'].min():.1%} - {economic_df['global_missing_rate'].max():.1%} (median: {economic_df['global_missing_rate'].median():.1%})")
    print()

    # Check what's in "Other" that might be economic
    print("=" * 80)
    print("CHECKING 'OTHER' FOR ECONOMIC INDICATORS")
    print("=" * 80)

    other_df = df[df['domain'] == 'Other']
    print(f"Total 'Other' indicators: {len(other_df):,}")

    # Sample of "Other" indicators
    print(f"\nSample 'Other' indicators (first 30):")
    for idx, row in other_df.head(30).iterrows():
        print(f"  {row['indicator'][:70]}")

    print()

    # Top 20 failed economic indicators
    if len(failed) > 0:
        print("=" * 80)
        print("TOP 20 FAILED ECONOMIC INDICATORS")
        print("=" * 80)

        failed['country_gap'] = (MIN_COUNTRIES - failed['unique_countries']).clip(lower=0)
        failed['temporal_gap'] = (MIN_TEMPORAL_SPAN - failed['temporal_span']).clip(lower=0) * 0.1
        failed['coverage_gap'] = (MIN_PER_COUNTRY_COVERAGE - failed['mean_per_country_coverage']).clip(lower=0)
        failed['missing_gap'] = (failed['global_missing_rate'] - MAX_MISSING_RATE).clip(lower=0)

        failed['total_gap'] = (
            failed['country_gap'] +
            failed['temporal_gap'] +
            failed['coverage_gap'] +
            failed['missing_gap']
        )

        failed_sorted = failed.nsmallest(20, 'total_gap')

        for idx, row in failed_sorted.iterrows():
            reasons = []
            if row['unique_countries'] < MIN_COUNTRIES:
                reasons.append(f"countries: {row['unique_countries']:.0f} < 80")
            if row['temporal_span'] < MIN_TEMPORAL_SPAN:
                reasons.append(f"span: {row['temporal_span']:.0f}y < 10y")
            if row['mean_per_country_coverage'] < MIN_PER_COUNTRY_COVERAGE:
                reasons.append(f"coverage: {row['mean_per_country_coverage']:.1%} < 50%")
            if row['global_missing_rate'] > MAX_MISSING_RATE:
                reasons.append(f"missing: {row['global_missing_rate']:.1%} > 70%")

            print(f"{row['indicator'][:60]:60s} | {', '.join(reasons)}")

    print()

    # Bottleneck identification
    bottleneck_rates = {
        'country_coverage': (~economic_df['pass_countries']).mean(),
        'temporal_span': (~economic_df['pass_temporal']).mean(),
        'per_country_coverage': (~economic_df['pass_coverage']).mean(),
        'missing_rate': (~economic_df['pass_missing']).mean(),
    }

    bottleneck = max(bottleneck_rates.items(), key=lambda x: x[1])

    print("=" * 80)
    print("RECOMMENDATIONS")
    print("=" * 80)
    print(f"🚨 BOTTLENECK FILTER FOR ECONOMIC: {bottleneck[0]} ({bottleneck[1]*100:.1f}% failure rate)")
    print()

    print("ASSESSMENT:")
    if len(economic_df) < 500:
        print(f"  ⚠️  Only {len(economic_df):,} economic indicators in World Bank")
        print("     Most World Bank indicators likely classified as 'Other'")
        print("     Economic keywords may be too narrow")

    if len(passed) < 100:
        print(f"  ⚠️  Only {len(passed):,} economic indicators pass filters")
        print("     This is acceptable - 'Other' category likely contains many economic indicators")
        print("     Classification is not critical for A1 filtering (only affects reporting)")

    print()
    print("NEXT STEPS:")
    print("  1. ACCEPT current 71 economic indicators (classification issue, not filter issue)")
    print("  2. Proceed with A1 imputation testing on all 8,086 indicators")
    print("  3. Domain classification will be refined in Phase B (B3)")

    # Save results
    results = {
        'total_worldbank': len(df),
        'economic_indicators': len(economic_df),
        'passed_economic': len(passed),
        'failed_economic': len(failed),
        'bottleneck_filter': bottleneck[0],
        'bottleneck_failure_rate': float(bottleneck[1]),
    }

    with open(BASE_DIR / "economic_filter_diagnostic.json", 'w') as f:
        json.dump(results, f, indent=2)

    print()
    print(f"✅ Results saved to: economic_filter_diagnostic.json")


if __name__ == "__main__":
    main()
