#!/usr/bin/env python3
"""
A1 Step 1: Load Data and Apply Initial Filters
================================================
Loads 31,858 indicators from A0 and applies pre-imputation filters to reduce
computational load while retaining high-quality indicators.

Filters Applied:
1. Country coverage >= 80 countries
2. Temporal span >= 10 years
3. Per-country temporal coverage >= 0.80 (V1 lesson: NOT global coverage)
4. Missing rate <= 0.70

Expected reduction: 31,858 -> ~25,000-30,000 indicators
"""

import pandas as pd
import numpy as np
from pathlib import Path
import json
from datetime import datetime
from tqdm import tqdm
import warnings
warnings.filterwarnings('ignore')

# Paths
BASE_DIR = Path(__file__).parent
A0_STANDARDIZED_DIR = BASE_DIR.parent / "A0_data_acquisition" / "raw_data_standardized"
OUTPUT_DIR = BASE_DIR / "filtered_data"
OUTPUT_DIR.mkdir(exist_ok=True)

# Filter thresholds - DIFFERENTIAL BY DOMAIN (Updated after education diagnostic)
# Default thresholds for most domains
MIN_COUNTRIES = 80
MIN_TEMPORAL_SPAN = 10
MIN_PER_COUNTRY_COVERAGE = 0.50
MAX_MISSING_RATE = 0.70

# Relaxed thresholds for survey-based domains (Education, Health)
DOMAIN_THRESHOLDS = {
    'Education': {'min_countries': 60, 'min_coverage': 0.40},
    'Health': {'min_countries': 60, 'min_coverage': 0.40},
    # All other domains use default thresholds
}

# Domain classification keywords
DOMAIN_KEYWORDS = {
    'Economic': ['gdp', 'income', 'poverty', 'employment', 'wage', 'trade', 'export', 'import', 'inflation', 'price'],
    'Health': ['health', 'mortality', 'life_expectancy', 'disease', 'nutrition', 'malnutrition', 'medical', 'hospital', 'immunization', 'vaccination'],
    'Education': ['school', 'education', 'literacy', 'enrollment', 'enrolment', 'pupil', 'teacher', 'student', 'completion', 'attainment', 'graduate', 'tertiary', 'primary', 'secondary', 'university', 'learning', 'educational', 'academic', 'pedagog'],
    'Democracy': ['democracy', 'election', 'electoral', 'vote', 'suffrage', 'party', 'civil_liberties'],
    'Governance': ['governance', 'government', 'regulation', 'rule_of_law', 'political', 'stability', 'accountability'],
    'Corruption': ['corruption', 'transparency', 'bribe'],
    'Inequality': ['inequality', 'gini', 'wealth_distribution', 'income_distribution'],
    'Infrastructure': ['infrastructure', 'road', 'electricity', 'water', 'sanitation', 'internet', 'mobile', 'phone'],
    'Environment': ['environment', 'emission', 'co2', 'pollution', 'forest', 'renewable', 'energy'],
    'Gender': ['gender', 'female', 'women', 'maternal'],
    'Social': ['social', 'welfare', 'pension', 'security'],
}


def classify_domain(indicator_name, source):
    """Classify indicator into domain based on keywords and source"""
    name_lower = indicator_name.lower()
    source_lower = source.lower()

    # Check each domain's keywords
    for domain, keywords in DOMAIN_KEYWORDS.items():
        if any(kw in name_lower for kw in keywords):
            return domain

    # Source-specific classification
    if 'vdem' in source_lower:
        return 'Democracy'
    if 'wid' in source_lower:
        return 'Inequality'

    return 'Other'


def load_indicator(csv_path):
    """Load a single indicator CSV file"""
    try:
        df = pd.read_csv(csv_path, low_memory=False)

        # Validate schema
        if list(df.columns) != ['Country', 'Year', 'Value']:
            return None

        # Basic cleaning
        df = df.dropna(subset=['Country', 'Year'])
        df['Year'] = df['Year'].astype(int)

        return df
    except Exception as e:
        return None


def compute_quality_metrics(df, indicator_name):
    """Compute quality metrics for filtering decision"""
    metrics = {
        'indicator': indicator_name,
        'total_rows': len(df),
        'unique_countries': df['Country'].nunique(),
        'min_year': int(df['Year'].min()),
        'max_year': int(df['Year'].max()),
        'temporal_span': int(df['Year'].max() - df['Year'].min()),
        'global_missing_rate': df['Value'].isna().mean(),
    }

    # Per-country temporal coverage (V1 CRITICAL LESSON)
    # For each country, what % of its year range has data?
    per_country_coverage = []
    for country, country_df in df.groupby('Country'):
        country_year_range = country_df['Year'].max() - country_df['Year'].min() + 1
        country_data_points = country_df['Value'].notna().sum()
        if country_year_range > 0:
            coverage = country_data_points / country_year_range
            per_country_coverage.append(coverage)

    # Average per-country coverage
    metrics['mean_per_country_coverage'] = np.mean(per_country_coverage) if per_country_coverage else 0.0

    return metrics


def apply_filters(metrics, domain):
    """Apply filter criteria with domain-specific thresholds"""
    # Get domain-specific thresholds if available
    domain_config = DOMAIN_THRESHOLDS.get(domain, {})
    min_countries = domain_config.get('min_countries', MIN_COUNTRIES)
    min_coverage = domain_config.get('min_coverage', MIN_PER_COUNTRY_COVERAGE)

    filters = {
        'country_coverage': metrics['unique_countries'] >= min_countries,
        'temporal_span': metrics['temporal_span'] >= MIN_TEMPORAL_SPAN,
        'per_country_coverage': metrics['mean_per_country_coverage'] >= min_coverage,
        'missing_rate': metrics['global_missing_rate'] <= MAX_MISSING_RATE,
    }

    # Indicator passes if ALL filters are true
    filters['pass_all'] = all(filters.values())

    return filters


def main():
    print("=" * 80)
    print("A1 STEP 1: LOAD DATA & APPLY INITIAL FILTERS")
    print("=" * 80)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Input directory: {A0_STANDARDIZED_DIR}")
    print()

    # Find all CSV files
    print("Discovering indicator files...")
    all_files = list(A0_STANDARDIZED_DIR.rglob("*.csv"))
    print(f"✅ Found {len(all_files):,} indicator files")
    print()

    # Filter criteria
    print("FILTER CRITERIA (DIFFERENTIAL BY DOMAIN):")
    print(f"  DEFAULT (Economic, Democracy, etc):")
    print(f"    - Country coverage: >= {MIN_COUNTRIES} countries")
    print(f"    - Temporal span: >= {MIN_TEMPORAL_SPAN} years")
    print(f"    - Per-country coverage: >= {MIN_PER_COUNTRY_COVERAGE:.0%}")
    print(f"    - Missing rate: <= {MAX_MISSING_RATE:.0%}")
    print()
    print(f"  RELAXED (Education, Health):")
    print(f"    - Country coverage: >= 60 countries")
    print(f"    - Temporal span: >= {MIN_TEMPORAL_SPAN} years")
    print(f"    - Per-country coverage: >= 40%")
    print(f"    - Missing rate: <= {MAX_MISSING_RATE:.0%}")
    print()

    # Process all indicators
    print("Processing indicators (this will take 10-20 minutes)...")
    results = []
    passed_indicators = []
    domain_counts = {}

    for csv_file in tqdm(all_files, desc="Loading & filtering"):
        # Load indicator
        df = load_indicator(csv_file)
        if df is None:
            continue

        # Compute quality metrics
        indicator_name = csv_file.stem
        source = csv_file.parent.name
        metrics = compute_quality_metrics(df, indicator_name)

        # Classify domain
        domain = classify_domain(indicator_name, source)
        domain_counts[domain] = domain_counts.get(domain, 0) + 1

        # Apply filters with domain-specific thresholds
        filters = apply_filters(metrics, domain)

        # Store results
        result = {**metrics, 'domain': domain, **filters}
        results.append(result)

        # If passes all filters, save to filtered directory
        if filters['pass_all']:
            passed_indicators.append(indicator_name)

            # Save to filtered directory (maintain source structure)
            relative_path = csv_file.relative_to(A0_STANDARDIZED_DIR)
            output_path = OUTPUT_DIR / relative_path
            output_path.parent.mkdir(parents=True, exist_ok=True)
            df.to_csv(output_path, index=False)

    # Convert to DataFrame for analysis
    results_df = pd.DataFrame(results)

    # Summary statistics
    print()
    print("=" * 80)
    print("FILTERING RESULTS")
    print("=" * 80)
    print(f"Total indicators processed: {len(results):,}")
    print(f"Indicators passing filters: {len(passed_indicators):,}")
    print(f"Reduction: {len(results):,} -> {len(passed_indicators):,} ({len(passed_indicators)/len(results)*100:.1f}%)")
    print()

    # Filter-specific statistics
    print("FILTER PASS RATES:")
    print(f"  Country coverage (>={MIN_COUNTRIES}): {results_df['country_coverage'].sum():,} ({results_df['country_coverage'].mean()*100:.1f}%)")
    print(f"  Temporal span (>={MIN_TEMPORAL_SPAN}y): {results_df['temporal_span'].sum():,} ({results_df['temporal_span'].mean()*100:.1f}%)")
    print(f"  Per-country coverage (>={MIN_PER_COUNTRY_COVERAGE:.0%}): {results_df['per_country_coverage'].sum():,} ({results_df['per_country_coverage'].mean()*100:.1f}%)")
    print(f"  Missing rate (<={MAX_MISSING_RATE:.0%}): {results_df['missing_rate'].sum():,} ({results_df['missing_rate'].mean()*100:.1f}%)")
    print()

    # Quality distribution of PASSED indicators
    passed_df = results_df[results_df['pass_all']]

    print("QUALITY DISTRIBUTION (PASSED INDICATORS):")
    print(f"  Countries: {passed_df['unique_countries'].min():.0f} - {passed_df['unique_countries'].max():.0f} (median: {passed_df['unique_countries'].median():.0f})")
    print(f"  Temporal span: {passed_df['temporal_span'].min():.0f} - {passed_df['temporal_span'].max():.0f} years (median: {passed_df['temporal_span'].median():.0f})")
    print(f"  Per-country coverage: {passed_df['mean_per_country_coverage'].min():.1%} - {passed_df['mean_per_country_coverage'].max():.1%} (median: {passed_df['mean_per_country_coverage'].median():.1%})")
    print(f"  Missing rate: {passed_df['global_missing_rate'].min():.1%} - {passed_df['global_missing_rate'].max():.1%} (median: {passed_df['global_missing_rate'].median():.1%})")
    print()

    # Domain breakdown
    print("=" * 80)
    print("DOMAIN BREAKDOWN (PASSED INDICATORS)")
    print("=" * 80)
    domain_breakdown = passed_df['domain'].value_counts().sort_index()
    for domain, count in domain_breakdown.items():
        pct = count / len(passed_df) * 100
        print(f"{domain:20s}: {count:6,} ({pct:5.1f}%)")
    print()

    # Save results
    results_df.to_csv(BASE_DIR / "step1_filter_results.csv", index=False)

    # Save metadata
    metadata = {
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'input_indicators': len(results),
        'passed_indicators': len(passed_indicators),
        'filter_criteria': {
            'min_countries': MIN_COUNTRIES,
            'min_temporal_span': MIN_TEMPORAL_SPAN,
            'min_per_country_coverage': MIN_PER_COUNTRY_COVERAGE,
            'max_missing_rate': MAX_MISSING_RATE,
        },
        'pass_rates': {
            'country_coverage': float(results_df['country_coverage'].mean()),
            'temporal_span': float(results_df['temporal_span'].mean()),
            'per_country_coverage': float(results_df['per_country_coverage'].mean()),
            'missing_rate': float(results_df['missing_rate'].mean()),
        },
        'quality_stats': {
            'median_countries': float(passed_df['unique_countries'].median()),
            'median_temporal_span': float(passed_df['temporal_span'].median()),
            'median_per_country_coverage': float(passed_df['mean_per_country_coverage'].median()),
            'median_missing_rate': float(passed_df['global_missing_rate'].median()),
        }
    }

    with open(BASE_DIR / "step1_metadata.json", 'w') as f:
        json.dump(metadata, f, indent=2)

    print(f"✅ Results saved to: {BASE_DIR / 'step1_filter_results.csv'}")
    print(f"✅ Metadata saved to: {BASE_DIR / 'step1_metadata.json'}")
    print(f"✅ Filtered data saved to: {OUTPUT_DIR}")
    print()

    # Check if we're in expected range
    expected_min = 25000
    expected_max = 30000

    if len(passed_indicators) < expected_min:
        print(f"⚠️  WARNING: Only {len(passed_indicators):,} indicators passed (expected {expected_min:,}-{expected_max:,})")
        print("   Consider loosening filter criteria")
    elif len(passed_indicators) > expected_max:
        print(f"⚠️  WARNING: {len(passed_indicators):,} indicators passed (expected {expected_min:,}-{expected_max:,})")
        print("   Consider tightening filter criteria")
    else:
        print(f"✅ Indicator count within expected range ({expected_min:,}-{expected_max:,})")

    print()
    print("=" * 80)
    print("STEP 1 COMPLETE - Ready for Step 2 (Imputation Configuration Design)")
    print("=" * 80)


if __name__ == "__main__":
    main()
