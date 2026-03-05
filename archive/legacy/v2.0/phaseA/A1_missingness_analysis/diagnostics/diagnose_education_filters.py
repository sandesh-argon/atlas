#!/usr/bin/env python3
"""
Education Filter Diagnostic
===========================
Analyzes why UNESCO education indicators fail quality filters.
"""

import pandas as pd
from pathlib import Path
import json

BASE_DIR = Path(__file__).parent
A0_STANDARDIZED_DIR = BASE_DIR.parent / "A0_data_acquisition" / "raw_data_standardized"

# Current filter thresholds
MIN_COUNTRIES = 80
MIN_TEMPORAL_SPAN = 10
MIN_PER_COUNTRY_COVERAGE = 0.50
MAX_MISSING_RATE = 0.70

# Education keywords
EDUCATION_KEYWORDS = [
    'school', 'education', 'literacy', 'enrollment', 'enrolment',
    'pupil', 'teacher', 'student', 'completion', 'attainment',
    'graduate', 'tertiary', 'primary', 'secondary', 'university',
    'learning', 'educational', 'academic', 'pedagog'
]


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

        import numpy as np
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
    print("EDUCATION INDICATOR FILTER DIAGNOSTIC")
    print("=" * 80)
    print()

    # Find all UNESCO files
    unesco_files = list((A0_STANDARDIZED_DIR / "unesco").glob("*.csv")) if (A0_STANDARDIZED_DIR / "unesco").exists() else []

    print(f"UNESCO files found: {len(unesco_files):,}")

    if len(unesco_files) == 0:
        print("❌ NO UNESCO FILES FOUND - UNESCO extraction likely failed")
        print()
        print("RECOMMENDATION: Re-run UNESCO scraper from A0")
        return

    print()

    # Analyze all UNESCO indicators
    print("Analyzing UNESCO indicators...")
    unesco_metrics = []

    for csv_file in unesco_files:
        metrics = compute_quality_metrics(csv_file)
        if metrics:
            unesco_metrics.append(metrics)

    df = pd.DataFrame(unesco_metrics)

    print(f"✅ Analyzed {len(df):,} UNESCO indicators")
    print()

    # Identify education indicators
    df['is_education'] = df['indicator'].apply(
        lambda x: any(kw in x.lower() for kw in EDUCATION_KEYWORDS)
    )

    education_df = df[df['is_education']].copy()
    non_education_df = df[~df['is_education']].copy()

    print("=" * 80)
    print("UNESCO BREAKDOWN")
    print("=" * 80)
    print(f"Total UNESCO indicators: {len(df):,}")
    print(f"  Education-related: {len(education_df):,} ({len(education_df)/len(df)*100:.1f}%)")
    print(f"  Non-education: {len(non_education_df):,} ({len(non_education_df)/len(df)*100:.1f}%)")
    print()

    # Apply filters to education indicators
    education_df['pass_countries'] = education_df['unique_countries'] >= MIN_COUNTRIES
    education_df['pass_temporal'] = education_df['temporal_span'] >= MIN_TEMPORAL_SPAN
    education_df['pass_coverage'] = education_df['mean_per_country_coverage'] >= MIN_PER_COUNTRY_COVERAGE
    education_df['pass_missing'] = education_df['global_missing_rate'] <= MAX_MISSING_RATE
    education_df['pass_all'] = (
        education_df['pass_countries'] &
        education_df['pass_temporal'] &
        education_df['pass_coverage'] &
        education_df['pass_missing']
    )

    passed = education_df[education_df['pass_all']]
    failed = education_df[~education_df['pass_all']]

    print("=" * 80)
    print("EDUCATION FILTER RESULTS")
    print("=" * 80)
    print(f"Total education indicators: {len(education_df):,}")
    print(f"  PASS all filters: {len(passed):,} ({len(passed)/len(education_df)*100:.1f}%)")
    print(f"  FAIL filters: {len(failed):,} ({len(failed)/len(education_df)*100:.1f}%)")
    print()

    # Filter-specific failure rates
    print("FILTER FAILURE BREAKDOWN:")
    print(f"  Country coverage (<{MIN_COUNTRIES}): {(~education_df['pass_countries']).sum():,} FAIL ({(~education_df['pass_countries']).mean()*100:.1f}%)")
    print(f"  Temporal span (<{MIN_TEMPORAL_SPAN}y): {(~education_df['pass_temporal']).sum():,} FAIL ({(~education_df['pass_temporal']).mean()*100:.1f}%)")
    print(f"  Per-country coverage (<{MIN_PER_COUNTRY_COVERAGE:.0%}): {(~education_df['pass_coverage']).sum():,} FAIL ({(~education_df['pass_coverage']).mean()*100:.1f}%)")
    print(f"  Missing rate (>{MAX_MISSING_RATE:.0%}): {(~education_df['pass_missing']).sum():,} FAIL ({(~education_df['pass_missing']).mean()*100:.1f}%)")
    print()

    # Quality distribution
    print("=" * 80)
    print("QUALITY DISTRIBUTION (EDUCATION INDICATORS)")
    print("=" * 80)
    print(f"Country coverage: {education_df['unique_countries'].min():.0f} - {education_df['unique_countries'].max():.0f} (median: {education_df['unique_countries'].median():.0f})")
    print(f"Temporal span: {education_df['temporal_span'].min():.0f} - {education_df['temporal_span'].max():.0f} years (median: {education_df['temporal_span'].median():.0f})")
    print(f"Per-country coverage: {education_df['mean_per_country_coverage'].min():.1%} - {education_df['mean_per_country_coverage'].max():.1%} (median: {education_df['mean_per_country_coverage'].median():.1%})")
    print(f"Missing rate: {education_df['global_missing_rate'].min():.1%} - {education_df['global_missing_rate'].max():.1%} (median: {education_df['global_missing_rate'].median():.1%})")
    print()

    # Example failed indicators
    if len(failed) > 0:
        print("=" * 80)
        print("TOP 20 FAILED EDUCATION INDICATORS (CLOSEST TO PASSING)")
        print("=" * 80)

        # Compute "distance from passing"
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

    # Test relaxed thresholds
    print("=" * 80)
    print("TESTING RELAXED THRESHOLDS (EDUCATION ONLY)")
    print("=" * 80)

    test_configs = [
        {'coverage': 0.30, 'countries': 60},
        {'coverage': 0.30, 'countries': 80},
        {'coverage': 0.40, 'countries': 60},
        {'coverage': 0.40, 'countries': 80},
        {'coverage': 0.50, 'countries': 60},
    ]

    for config in test_configs:
        test_pass = (
            (education_df['unique_countries'] >= config['countries']) &
            (education_df['temporal_span'] >= MIN_TEMPORAL_SPAN) &
            (education_df['mean_per_country_coverage'] >= config['coverage']) &
            (education_df['global_missing_rate'] <= MAX_MISSING_RATE)
        ).sum()

        print(f"  Coverage >={config['coverage']:.0%}, Countries >={config['countries']}: {test_pass:,} education indicators pass ({test_pass/len(education_df)*100:.1f}%)")

    print()

    # Recommendations
    print("=" * 80)
    print("RECOMMENDATIONS")
    print("=" * 80)

    # Identify bottleneck
    bottleneck_rates = {
        'country_coverage': (~education_df['pass_countries']).mean(),
        'temporal_span': (~education_df['pass_temporal']).mean(),
        'per_country_coverage': (~education_df['pass_coverage']).mean(),
        'missing_rate': (~education_df['pass_missing']).mean(),
    }

    bottleneck = max(bottleneck_rates.items(), key=lambda x: x[1])

    print(f"🚨 BOTTLENECK FILTER FOR EDUCATION: {bottleneck[0]} ({bottleneck[1]*100:.1f}% failure rate)")
    print()

    if bottleneck[0] == 'per_country_coverage':
        print("RECOMMENDATION: Implement differential threshold for education domain")
        print("  Current (all domains): Per-country coverage >= 50%")
        print("  Proposed (education): Per-country coverage >= 30%")
        print()
        print("RATIONALE:")
        print("  - Education data collected via periodic surveys (every 3-5 years)")
        print("  - UNESCO UIS has inherent sparsity due to data collection constraints")
        print("  - Survey-based indicators have lower temporal density than admin data")

    elif bottleneck[0] == 'country_coverage':
        print("RECOMMENDATION: Implement differential threshold for education domain")
        print("  Current (all domains): Country coverage >= 80")
        print("  Proposed (education): Country coverage >= 60")
        print()
        print("RATIONALE:")
        print("  - UNESCO prioritizes developing countries (may miss OECD)")
        print("  - Education indicators still valuable with 60+ countries")

    print()

    # Save results
    results = {
        'total_unesco': len(df),
        'education_indicators': len(education_df),
        'passed_education': len(passed),
        'failed_education': len(failed),
        'bottleneck_filter': bottleneck[0],
        'bottleneck_failure_rate': float(bottleneck[1]),
        'quality_stats': {
            'median_countries': float(education_df['unique_countries'].median()),
            'median_temporal_span': float(education_df['temporal_span'].median()),
            'median_coverage': float(education_df['mean_per_country_coverage'].median()),
            'median_missing': float(education_df['global_missing_rate'].median()),
        }
    }

    with open(BASE_DIR / "education_filter_diagnostic.json", 'w') as f:
        json.dump(results, f, indent=2)

    print(f"✅ Results saved to: education_filter_diagnostic.json")


if __name__ == "__main__":
    main()
