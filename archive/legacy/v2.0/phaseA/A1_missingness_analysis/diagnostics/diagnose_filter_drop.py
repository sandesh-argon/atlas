#!/usr/bin/env python3
"""
A1 Filter Drop Diagnostic
=========================
Diagnoses why filtering dropped 80% of indicators (31,858 → 6,316).
Identifies the bottleneck filter and recommends threshold adjustments.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from collections import defaultdict
import json
from tqdm import tqdm

BASE_DIR = Path(__file__).parent
A0_STANDARDIZED_DIR = BASE_DIR.parent / "A0_data_acquisition" / "raw_data_standardized"

# Current thresholds
CURRENT_THRESHOLDS = {
    'min_countries': 80,
    'min_temporal_span': 10,
    'min_per_country_coverage': 0.80,
    'max_missing_rate': 0.70,
}

# Alternative thresholds to test
ALT_THRESHOLDS = {
    'per_country_coverage': [0.40, 0.50, 0.60, 0.70, 0.80],
    'country_coverage': [50, 60, 70, 80, 90],
}


def load_and_analyze_indicator(csv_path):
    """Load indicator and compute all metrics"""
    try:
        df = pd.read_csv(csv_path, low_memory=False)

        if list(df.columns) != ['Country', 'Year', 'Value']:
            return None

        df = df.dropna(subset=['Country', 'Year'])
        df['Year'] = df['Year'].astype(int)

        # Source identification
        source = csv_path.parent.name

        # Basic metrics
        metrics = {
            'indicator': csv_path.stem,
            'source': source,
            'total_rows': len(df),
            'unique_countries': df['Country'].nunique(),
            'min_year': int(df['Year'].min()),
            'max_year': int(df['Year'].max()),
            'temporal_span': int(df['Year'].max() - df['Year'].min()),
            'global_missing_rate': df['Value'].isna().mean(),
        }

        # Per-country temporal coverage
        per_country_coverage = []
        for country, country_df in df.groupby('Country'):
            country_year_range = country_df['Year'].max() - country_df['Year'].min() + 1
            country_data_points = country_df['Value'].notna().sum()
            if country_year_range > 0:
                coverage = country_data_points / country_year_range
                per_country_coverage.append(coverage)

        metrics['mean_per_country_coverage'] = np.mean(per_country_coverage) if per_country_coverage else 0.0

        return metrics

    except Exception:
        return None


def compute_filter_results(metrics, thresholds):
    """Apply filters and return pass/fail for each"""
    return {
        'country_coverage': metrics['unique_countries'] >= thresholds['min_countries'],
        'temporal_span': metrics['temporal_span'] >= thresholds['min_temporal_span'],
        'per_country_coverage': metrics['mean_per_country_coverage'] >= thresholds['min_per_country_coverage'],
        'missing_rate': metrics['global_missing_rate'] <= thresholds['max_missing_rate'],
    }


def classify_domain(indicator_name, source):
    """Classify indicator into domain"""
    name_lower = indicator_name.lower()
    source_lower = source.lower()

    # Economic indicators
    if any(kw in name_lower for kw in ['gdp', 'income', 'poverty', 'employment', 'wage', 'trade', 'export', 'import', 'inflation', 'price']):
        return 'Economic'

    # Health indicators
    if any(kw in name_lower for kw in ['health', 'mortality', 'life_expectancy', 'disease', 'nutrition', 'malnutrition', 'medical', 'hospital', 'immunization', 'vaccination']):
        return 'Health'

    # Education indicators
    if any(kw in name_lower for kw in ['education', 'school', 'literacy', 'enrollment', 'teacher', 'university', 'pupil', 'student']):
        return 'Education'

    # Democracy indicators
    if any(kw in name_lower for kw in ['democracy', 'election', 'electoral', 'vote', 'suffrage', 'party', 'civil_liberties']) or 'vdem' in source_lower:
        return 'Democracy'

    # Governance indicators
    if any(kw in name_lower for kw in ['governance', 'government', 'regulation', 'rule_of_law', 'political', 'stability', 'accountability']):
        return 'Governance'

    # Corruption indicators
    if any(kw in name_lower for kw in ['corruption', 'transparency', 'bribe']):
        return 'Corruption'

    # Inequality indicators
    if any(kw in name_lower for kw in ['inequality', 'gini', 'wealth_distribution', 'income_distribution']) or 'wid' in source_lower:
        return 'Inequality'

    # Infrastructure indicators
    if any(kw in name_lower for kw in ['infrastructure', 'road', 'electricity', 'water', 'sanitation', 'internet', 'mobile', 'phone']):
        return 'Infrastructure'

    # Environment indicators
    if any(kw in name_lower for kw in ['environment', 'emission', 'co2', 'pollution', 'forest', 'renewable', 'energy']):
        return 'Environment'

    # Gender indicators
    if any(kw in name_lower for kw in ['gender', 'female', 'women', 'maternal']):
        return 'Gender'

    # Social indicators
    if any(kw in name_lower for kw in ['social', 'welfare', 'pension', 'security']):
        return 'Social'

    return 'Other'


def main():
    print("=" * 80)
    print("A1 FILTER DROP DIAGNOSTIC")
    print("=" * 80)
    print(f"Current retention: 31,858 → 6,316 (19.8%)")
    print(f"Investigating why 80.2% of indicators were rejected...")
    print()

    # Load all indicators
    print("Loading all 31,858 indicators...")
    all_files = list(A0_STANDARDIZED_DIR.rglob("*.csv"))
    print(f"Found {len(all_files):,} files")
    print()

    # Analyze all indicators
    print("Analyzing indicators (this will take 10-15 minutes)...")
    all_metrics = []

    for csv_file in tqdm(all_files, desc="Analyzing"):
        metrics = load_and_analyze_indicator(csv_file)
        if metrics:
            all_metrics.append(metrics)

    df = pd.DataFrame(all_metrics)
    print(f"✅ Analyzed {len(df):,} indicators")
    print()

    # 1. INDIVIDUAL FILTER FAILURE RATES
    print("=" * 80)
    print("1. INDIVIDUAL FILTER FAILURE RATES")
    print("=" * 80)

    filter_results = df.apply(lambda row: compute_filter_results(row, CURRENT_THRESHOLDS), axis=1, result_type='expand')

    for filter_name in ['country_coverage', 'temporal_span', 'per_country_coverage', 'missing_rate']:
        pass_count = filter_results[filter_name].sum()
        fail_count = len(df) - pass_count
        fail_pct = fail_count / len(df) * 100

        print(f"{filter_name:25s}: {fail_count:6,} FAIL ({fail_pct:5.1f}%) | {pass_count:6,} PASS")

    # Combined pass rate
    all_pass = filter_results.all(axis=1).sum()
    print(f"{'ALL FILTERS':25s}: {len(df) - all_pass:6,} FAIL ({(len(df) - all_pass)/len(df)*100:5.1f}%) | {all_pass:6,} PASS")
    print()

    # 2. DISTRIBUTION BEFORE FILTERING
    print("=" * 80)
    print("2. DISTRIBUTION BEFORE FILTERING")
    print("=" * 80)

    for col, label in [
        ('unique_countries', 'Country coverage'),
        ('temporal_span', 'Temporal span (years)'),
        ('mean_per_country_coverage', 'Per-country coverage'),
        ('global_missing_rate', 'Global missing rate')
    ]:
        print(f"\n{label}:")
        print(f"  Min:    {df[col].min():.2f}")
        print(f"  25th:   {df[col].quantile(0.25):.2f}")
        print(f"  Median: {df[col].median():.2f}")
        print(f"  75th:   {df[col].quantile(0.75):.2f}")
        print(f"  Max:    {df[col].max():.2f}")

    print()

    # 3. EXAMPLE REJECTED INDICATORS (CLOSEST TO PASSING)
    print("=" * 80)
    print("3. TOP 20 REJECTED INDICATORS (CLOSEST TO PASSING)")
    print("=" * 80)

    # Compute "distance from passing" for each filter
    df['country_gap'] = CURRENT_THRESHOLDS['min_countries'] - df['unique_countries']
    df['temporal_gap'] = CURRENT_THRESHOLDS['min_temporal_span'] - df['temporal_span']
    df['coverage_gap'] = CURRENT_THRESHOLDS['min_per_country_coverage'] - df['mean_per_country_coverage']
    df['missing_gap'] = df['global_missing_rate'] - CURRENT_THRESHOLDS['max_missing_rate']

    # Rejected indicators
    rejected = df[~filter_results.all(axis=1)].copy()

    # Sort by "closest to passing" (sum of positive gaps)
    rejected['total_gap'] = (
        rejected['country_gap'].clip(lower=0) +
        rejected['temporal_gap'].clip(lower=0) * 0.1 +  # Scale temporal to [0,1] range
        rejected['coverage_gap'].clip(lower=0) +
        rejected['missing_gap'].clip(lower=0)
    )

    rejected_sorted = rejected.nsmallest(20, 'total_gap')

    for idx, row in rejected_sorted.iterrows():
        reasons = []
        if row['unique_countries'] < CURRENT_THRESHOLDS['min_countries']:
            reasons.append(f"countries: {row['unique_countries']:.0f} < 80")
        if row['temporal_span'] < CURRENT_THRESHOLDS['min_temporal_span']:
            reasons.append(f"span: {row['temporal_span']:.0f}y < 10y")
        if row['mean_per_country_coverage'] < CURRENT_THRESHOLDS['min_per_country_coverage']:
            reasons.append(f"coverage: {row['mean_per_country_coverage']:.1%} < 80%")
        if row['global_missing_rate'] > CURRENT_THRESHOLDS['max_missing_rate']:
            reasons.append(f"missing: {row['global_missing_rate']:.1%} > 70%")

        print(f"{row['indicator'][:50]:50s} | {', '.join(reasons)}")

    print()

    # 4. SOURCE-LEVEL REJECTION RATES
    print("=" * 80)
    print("4. TOP 10 SOURCES BY REJECTION RATE")
    print("=" * 80)

    source_stats = []
    for source in df['source'].unique():
        source_df = df[df['source'] == source]
        source_rejected = rejected[rejected['source'] == source]

        rejection_rate = len(source_rejected) / len(source_df)

        source_stats.append({
            'source': source,
            'total': len(source_df),
            'rejected': len(source_rejected),
            'rejection_rate': rejection_rate
        })

    source_stats_df = pd.DataFrame(source_stats).sort_values('rejected', ascending=False).head(10)

    for _, row in source_stats_df.iterrows():
        print(f"{row['source']:20s}: {row['rejection_rate']:5.1%} rejected ({row['rejected']:5,} / {row['total']:5,} indicators lost)")

    print()

    # 5. ALMOST PASSING INDICATORS
    print("=" * 80)
    print("5. 'ALMOST PASSING' INDICATORS (WITHIN 5% OF THRESHOLD)")
    print("=" * 80)

    almost_passing = {
        'country_coverage (75-79 countries)': len(rejected[(rejected['unique_countries'] >= 75) & (rejected['unique_countries'] < 80)]),
        'per_country_coverage (75-79%)': len(rejected[(rejected['mean_per_country_coverage'] >= 0.75) & (rejected['mean_per_country_coverage'] < 0.80)]),
        'missing_rate (70-75%)': len(rejected[(rejected['global_missing_rate'] > 0.70) & (rejected['global_missing_rate'] <= 0.75)]),
    }

    for criterion, count in almost_passing.items():
        print(f"{criterion:40s}: {count:5,} indicators")

    print()

    # 6. TEST ALTERNATIVE THRESHOLDS
    print("=" * 80)
    print("6. ALTERNATIVE THRESHOLD TESTING")
    print("=" * 80)

    print("\nTesting per-country coverage thresholds:")
    for threshold in ALT_THRESHOLDS['per_country_coverage']:
        alt_thresholds = CURRENT_THRESHOLDS.copy()
        alt_thresholds['min_per_country_coverage'] = threshold

        alt_results = df.apply(lambda row: compute_filter_results(row, alt_thresholds), axis=1, result_type='expand')
        alt_pass = alt_results.all(axis=1).sum()

        print(f"  Coverage >= {threshold:.0%}: {alt_pass:6,} indicators pass ({alt_pass/len(df)*100:5.1f}% retention)")

    print("\nTesting country coverage thresholds:")
    for threshold in ALT_THRESHOLDS['country_coverage']:
        alt_thresholds = CURRENT_THRESHOLDS.copy()
        alt_thresholds['min_countries'] = threshold

        alt_results = df.apply(lambda row: compute_filter_results(row, alt_thresholds), axis=1, result_type='expand')
        alt_pass = alt_results.all(axis=1).sum()

        print(f"  Countries >= {threshold}: {alt_pass:6,} indicators pass ({alt_pass/len(df)*100:5.1f}% retention)")

    print()

    # 7. DOMAIN COVERAGE ANALYSIS
    print("=" * 80)
    print("7. DOMAIN COVERAGE (CURRENT 6,316 vs RELAXED)")
    print("=" * 80)

    # Classify all indicators
    df['domain'] = df.apply(lambda row: classify_domain(row['indicator'], row['source']), axis=1)

    # Current passed indicators
    passed = df[filter_results.all(axis=1)]

    # Relaxed config: per_country_coverage >= 0.50
    relaxed_thresholds = CURRENT_THRESHOLDS.copy()
    relaxed_thresholds['min_per_country_coverage'] = 0.50
    relaxed_results = df.apply(lambda row: compute_filter_results(row, relaxed_thresholds), axis=1, result_type='expand')
    relaxed_passed = df[relaxed_results.all(axis=1)]

    print(f"\n{'Domain':20s} | Current (6,316) | Relaxed (50% cov) | Difference")
    print("-" * 80)

    for domain in sorted(df['domain'].unique()):
        current_count = len(passed[passed['domain'] == domain])
        relaxed_count = len(relaxed_passed[relaxed_passed['domain'] == domain])
        diff = relaxed_count - current_count

        print(f"{domain:20s} | {current_count:6,} ({current_count/len(passed)*100:4.1f}%) | {relaxed_count:6,} ({relaxed_count/len(relaxed_passed)*100:4.1f}%) | +{diff:5,}")

    print()

    # 8. RECOMMENDATIONS
    print("=" * 80)
    print("8. RECOMMENDATIONS")
    print("=" * 80)

    # Identify bottleneck filter
    filter_fail_rates = {
        'per_country_coverage': (len(df) - filter_results['per_country_coverage'].sum()) / len(df),
        'country_coverage': (len(df) - filter_results['country_coverage'].sum()) / len(df),
        'missing_rate': (len(df) - filter_results['missing_rate'].sum()) / len(df),
        'temporal_span': (len(df) - filter_results['temporal_span'].sum()) / len(df),
    }

    bottleneck = max(filter_fail_rates.items(), key=lambda x: x[1])

    print(f"\n🚨 BOTTLENECK FILTER: {bottleneck[0]} ({bottleneck[1]*100:.1f}% failure rate)")
    print()

    if bottleneck[0] == 'per_country_coverage':
        print("RECOMMENDATION: Relax per-country coverage threshold")
        print("  Current: >= 80% (too strict for survey-based indicators)")
        print("  Proposed: >= 50% or >= 60%")
        print()
        print("RATIONALE:")
        print("  - Survey indicators collected every 5 years = 20% coverage")
        print("  - Census indicators collected every 10 years = 10% coverage")
        print("  - Strict 80% filter rejects high-quality causal variables")
        print()
        print(f"IMPACT: 6,316 → ~{relaxed_results.all(axis=1).sum():,} indicators (better causal discovery)")

    elif bottleneck[0] == 'country_coverage':
        print("RECOMMENDATION: Lower country threshold")
        print("  Current: >= 80 countries")
        print("  Proposed: >= 60 or >= 70 countries")
        print()
        print("RATIONALE:")
        print("  - Niche indicators (patents, rural Gini) valuable despite <80 countries")
        print("  - OECD-focused indicators still capture rich-country dynamics")

    print()
    print("=" * 80)
    print("DIAGNOSTIC COMPLETE")
    print("=" * 80)

    # Save results
    df.to_csv(BASE_DIR / "diagnostic_full_results.csv", index=False)
    print(f"\n✅ Full results saved to: diagnostic_full_results.csv")


if __name__ == "__main__":
    main()
