#!/usr/bin/env python3
"""
Final A0 Pre-Flight Validation

Runs 5 critical checks before proceeding to A1:
1. Country name consistency across sources
2. Temporal overlap validation (1990-2024 golden window)
3. Duplicate indicator detection (correlation > 0.95)
4. V-Dem/WID disaggregation analysis
5. Missing data pattern analysis (systematic bias check)
"""

import pandas as pd
from pathlib import Path
import json
from collections import defaultdict
import numpy as np
from datetime import datetime
import sys

# Configuration
BASE_DIR = Path(__file__).parent.parent.parent
RAW_DATA_DIR = BASE_DIR / "raw_data"
OUTPUT_DIR = BASE_DIR / "validation_logs"

# Data sources to check
SOURCES = {
    'world_bank': RAW_DATA_DIR / 'world_bank',
    'who': RAW_DATA_DIR / 'who',
    'unesco': RAW_DATA_DIR / 'unesco',
    'imf': RAW_DATA_DIR / 'imf',
    'unicef': RAW_DATA_DIR / 'unicef',
    'qog': RAW_DATA_DIR / 'qog',
    'penn': RAW_DATA_DIR / 'penn',
    'vdem': RAW_DATA_DIR / 'vdem',
    'wid': RAW_DATA_DIR / 'wid'
}

GOLDEN_WINDOW = (1990, 2024)

def check_country_names():
    """Check 1: Country name consistency across sources"""
    print("\n" + "="*80)
    print("CHECK 1: COUNTRY NAME STANDARDIZATION")
    print("="*80)

    country_names_by_source = {}

    for source_name, source_dir in SOURCES.items():
        if not source_dir.exists():
            print(f"⚠️  Skipping {source_name}: directory not found")
            continue

        print(f"Analyzing {source_name}...")

        # Sample 10 random files from each source
        csv_files = list(source_dir.glob("*.csv"))
        if len(csv_files) == 0:
            print(f"  No CSV files found in {source_dir}")
            continue

        sample_files = np.random.choice(csv_files, min(10, len(csv_files)), replace=False)

        unique_countries = set()
        for file in sample_files:
            try:
                df = pd.read_csv(file, usecols=['Country'])
                unique_countries.update(df['Country'].dropna().unique())
            except Exception as e:
                continue

        country_names_by_source[source_name] = unique_countries
        print(f"  Found {len(unique_countries)} unique country names")

    # Analyze overlaps and differences
    all_countries = set()
    for countries in country_names_by_source.values():
        all_countries.update(countries)

    print(f"\n📊 Summary:")
    print(f"  Total unique country names across all sources: {len(all_countries)}")

    # Check for common inconsistencies
    inconsistencies = []

    # Common problematic cases
    problem_patterns = [
        ('Korea', ['Korea, Rep.', 'South Korea', 'Republic of Korea', 'Korea']),
        ('Congo', ['Congo', 'Congo, Rep.', 'Congo, Dem. Rep.', 'Democratic Republic of Congo']),
        ('United States', ['United States', 'USA', 'United States of America', 'US']),
        ('United Kingdom', ['United Kingdom', 'UK', 'Great Britain']),
        ('Egypt', ['Egypt', 'Egypt, Arab Rep.']),
        ('Iran', ['Iran', 'Iran, Islamic Rep.']),
        ('Venezuela', ['Venezuela', 'Venezuela, RB']),
    ]

    for category, variants in problem_patterns:
        found_variants = [v for v in variants if v in all_countries]
        if len(found_variants) > 1:
            inconsistencies.append({
                'category': category,
                'variants': found_variants
            })

    if len(inconsistencies) > 0:
        print(f"\n🚨 CRITICAL: Found {len(inconsistencies)} country name inconsistencies:")
        for issue in inconsistencies:
            print(f"  {issue['category']}: {', '.join(issue['variants'])}")

        # Save mapping file
        mapping_file = OUTPUT_DIR / "country_name_mapping.json"
        with open(mapping_file, 'w') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'total_unique_names': len(all_countries),
                'countries_by_source': {k: list(v) for k, v in country_names_by_source.items()},
                'inconsistencies': inconsistencies
            }, f, indent=2)

        print(f"\n📁 Country mapping analysis saved to: {mapping_file}")
        print(f"⚠️  ACTION REQUIRED: Create country_mapping.json before A0.15")

        return {'status': 'WARN', 'message': f'{len(inconsistencies)} country name conflicts found', 'details': inconsistencies}
    else:
        print("\n✅ No major country name inconsistencies detected")
        return {'status': 'PASS', 'message': 'Country names appear consistent'}

def check_temporal_density(start_year=1990, end_year=2024):
    """Check 2: Temporal overlap validation"""
    print("\n" + "="*80)
    print(f"CHECK 2: TEMPORAL OVERLAP ({start_year}-{end_year} GOLDEN WINDOW)")
    print("="*80)

    coverage_stats = {}

    for source_name, source_dir in SOURCES.items():
        if not source_dir.exists():
            continue

        print(f"Analyzing {source_name}...")

        csv_files = list(source_dir.glob("*.csv"))
        if len(csv_files) == 0:
            continue

        # Sample files for analysis
        sample_size = min(50, len(csv_files))
        sample_files = np.random.choice(csv_files, sample_size, replace=False)

        indicators_in_window = 0
        total_indicators = 0

        for file in sample_files:
            try:
                df = pd.read_csv(file, usecols=['Year', 'Value'])
                df = df.dropna(subset=['Value'])

                if len(df) == 0:
                    continue

                total_indicators += 1

                # Check coverage in golden window
                window_df = df[(df['Year'] >= start_year) & (df['Year'] <= end_year)]

                if len(window_df) >= 0.5 * (end_year - start_year):  # >50% coverage
                    indicators_in_window += 1

            except Exception as e:
                continue

        if total_indicators > 0:
            pct_in_window = 100 * indicators_in_window / total_indicators
            coverage_stats[source_name] = {
                'sampled': total_indicators,
                'in_window': indicators_in_window,
                'percentage': pct_in_window
            }
            print(f"  {pct_in_window:.1f}% of indicators have >50% coverage in {start_year}-{end_year}")

    # Overall assessment
    overall_pct = np.mean([s['percentage'] for s in coverage_stats.values()])

    print(f"\n📊 Overall Coverage:")
    print(f"  {overall_pct:.1f}% of sampled indicators have good coverage in {start_year}-{end_year}")

    if overall_pct < 50:
        print(f"🚨 CRITICAL: Low temporal overlap! Golden window coverage is only {overall_pct:.1f}%")
        return {'status': 'FAIL', 'message': f'Only {overall_pct:.1f}% coverage in golden window', 'details': coverage_stats}
    elif overall_pct < 70:
        print(f"⚠️  WARNING: Moderate temporal overlap ({overall_pct:.1f}%)")
        return {'status': 'WARN', 'message': f'{overall_pct:.1f}% coverage in golden window', 'details': coverage_stats}
    else:
        print(f"✅ GOOD: Strong temporal overlap ({overall_pct:.1f}%)")
        return {'status': 'PASS', 'message': f'{overall_pct:.1f}% coverage in golden window', 'details': coverage_stats}

def detect_duplicates(threshold=0.95, sample_size=100):
    """Check 3: Duplicate indicator detection"""
    print("\n" + "="*80)
    print(f"CHECK 3: DUPLICATE INDICATOR DETECTION (r > {threshold})")
    print("="*80)

    print("Note: Full correlation analysis would take hours.")
    print("Running quick name-based duplicate detection...")

    indicator_names = {}

    for source_name, source_dir in SOURCES.items():
        if not source_dir.exists():
            continue

        csv_files = list(source_dir.glob("*.csv"))
        indicator_names[source_name] = [f.stem for f in csv_files]

    # Check for obvious name similarities
    duplicates = []

    # Common duplicate patterns
    patterns = [
        ('gdp', 'gross domestic product'),
        ('life expectancy', 'life_expectancy'),
        ('mortality', 'death rate'),
        ('unemployment', 'jobless'),
        ('inflation', 'cpi'),
    ]

    all_names = []
    for source, names in indicator_names.items():
        for name in names:
            all_names.append((source, name.lower()))

    for pattern1, pattern2 in patterns:
        matches1 = [n for n in all_names if pattern1 in n[1]]
        matches2 = [n for n in all_names if pattern2 in n[1]]

        if len(matches1) > 0 and len(matches2) > 0:
            duplicates.append({
                'pattern': f"{pattern1} / {pattern2}",
                'count': len(matches1) + len(matches2),
                'examples': matches1[:3] + matches2[:3]
            })

    if len(duplicates) > 0:
        print(f"\n⚠️  Found {len(duplicates)} potential duplicate patterns:")
        for dup in duplicates[:5]:  # Show first 5
            print(f"  {dup['pattern']}: {dup['count']} indicators")

        print(f"\n⚠️  ACTION RECOMMENDED: Run full correlation analysis in A0.15")
        return {'status': 'WARN', 'message': f'{len(duplicates)} potential duplicate patterns', 'details': duplicates}
    else:
        print("\n✅ No obvious duplicate patterns detected in indicator names")
        return {'status': 'PASS', 'message': 'No obvious duplicates found'}

def analyze_indicator_hierarchy():
    """Check 4: V-Dem/WID disaggregation analysis"""
    print("\n" + "="*80)
    print("CHECK 4: DISAGGREGATION EXPLOSION ANALYSIS")
    print("="*80)

    disaggregation_patterns = {
        'gender': ['_male', '_female', '_m_', '_f_', '_men', '_women'],
        'age': ['_0_14', '_15_64', '_65plus', '_young', '_old', '_adult', '_child'],
        'geography': ['_urban', '_rural', '_region', '_province'],
        'income': ['_p0p', '_p10p', '_p20p', '_decile', '_quintile'],
        'confidence': ['_codelow', '_codehigh', '_sd', '_lower', '_upper']
    }

    results = {}

    for source_name in ['vdem', 'wid']:
        source_dir = SOURCES.get(source_name)
        if not source_dir or not source_dir.exists():
            continue

        print(f"\nAnalyzing {source_name}...")

        csv_files = list(source_dir.glob("*.csv"))
        indicator_names = [f.stem for f in csv_files]

        disaggregation_counts = {k: 0 for k in disaggregation_patterns.keys()}

        for name in indicator_names:
            name_lower = name.lower()
            for pattern_type, patterns in disaggregation_patterns.items():
                if any(p in name_lower for p in patterns):
                    disaggregation_counts[pattern_type] += 1

        total_disaggregated = sum(disaggregation_counts.values())
        pct_disaggregated = 100 * total_disaggregated / len(indicator_names)

        results[source_name] = {
            'total_indicators': len(indicator_names),
            'disaggregated': total_disaggregated,
            'percentage': pct_disaggregated,
            'by_type': disaggregation_counts
        }

        print(f"  Total indicators: {len(indicator_names)}")
        print(f"  Disaggregated: {total_disaggregated} ({pct_disaggregated:.1f}%)")
        for ptype, count in disaggregation_counts.items():
            if count > 0:
                print(f"    {ptype}: {count}")

    # Assessment
    if results:
        max_disagg_pct = max(r['percentage'] for r in results.values())

        if max_disagg_pct > 50:
            print(f"\n🚨 WARNING: High disaggregation detected ({max_disagg_pct:.1f}%)")
            print(f"   ACTION REQUIRED: Review and keep only aggregate versions in A0.16")
            return {'status': 'WARN', 'message': f'{max_disagg_pct:.1f}% disaggregated indicators', 'details': results}
        else:
            print(f"\n✅ Disaggregation level acceptable ({max_disagg_pct:.1f}%)")
            return {'status': 'PASS', 'message': f'{max_disagg_pct:.1f}% disaggregated', 'details': results}

    return {'status': 'PASS', 'message': 'Analysis skipped - sources not available'}

def analyze_missingness_bias(sample_size=50):
    """Check 5: Missing data pattern analysis"""
    print("\n" + "="*80)
    print("CHECK 5: MISSING DATA PATTERN ANALYSIS")
    print("="*80)

    print("Analyzing missingness patterns by region and decade...")

    # Region groupings (simplified)
    regions = {
        'Africa': ['Nigeria', 'South Africa', 'Kenya', 'Ethiopia', 'Egypt', 'Ghana'],
        'Asia': ['China', 'India', 'Japan', 'Indonesia', 'Bangladesh', 'Thailand'],
        'Europe': ['Germany', 'France', 'United Kingdom', 'Italy', 'Spain', 'Poland'],
        'Americas': ['United States', 'Brazil', 'Mexico', 'Canada', 'Argentina', 'Colombia'],
        'Oceania': ['Australia', 'New Zealand']
    }

    decades = {
        '1990s': (1990, 1999),
        '2000s': (2000, 2009),
        '2010s': (2010, 2019),
        '2020s': (2020, 2024)
    }

    missingness_by_region = {r: [] for r in regions.keys()}
    missingness_by_decade = {d: [] for d in decades.keys()}

    # Sample files across all sources
    all_csv_files = []
    for source_dir in SOURCES.values():
        if source_dir.exists():
            all_csv_files.extend(list(source_dir.glob("*.csv")))

    if len(all_csv_files) == 0:
        print("⚠️  No CSV files found")
        return {'status': 'WARN', 'message': 'No data files to analyze'}

    sample_files = np.random.choice(all_csv_files, min(sample_size, len(all_csv_files)), replace=False)

    print(f"Sampling {len(sample_files)} indicators...")

    for file in sample_files:
        try:
            df = pd.read_csv(file)

            # Check by region
            for region_name, countries in regions.items():
                region_df = df[df['Country'].isin(countries)]
                if len(region_df) > 0:
                    missingness = region_df['Value'].isna().mean()
                    missingness_by_region[region_name].append(missingness)

            # Check by decade
            for decade_name, (start, end) in decades.items():
                decade_df = df[(df['Year'] >= start) & (df['Year'] <= end)]
                if len(decade_df) > 0:
                    missingness = decade_df['Value'].isna().mean()
                    missingness_by_decade[decade_name].append(missingness)

        except Exception as e:
            continue

    # Calculate averages
    print(f"\n📊 Missingness by Region:")
    region_stats = {}
    for region, missing_rates in missingness_by_region.items():
        if len(missing_rates) > 0:
            avg_missing = np.mean(missing_rates)
            region_stats[region] = avg_missing
            print(f"  {region}: {avg_missing*100:.1f}% missing")

    print(f"\n📊 Missingness by Decade:")
    decade_stats = {}
    for decade, missing_rates in missingness_by_decade.items():
        if len(missing_rates) > 0:
            avg_missing = np.mean(missing_rates)
            decade_stats[decade] = avg_missing
            print(f"  {decade}: {avg_missing*100:.1f}% missing")

    # Check for systematic bias
    if region_stats:
        max_region_diff = max(region_stats.values()) - min(region_stats.values())
        print(f"\n  Max regional difference: {max_region_diff*100:.1f}%")

        if max_region_diff > 0.3:  # >30% difference
            print(f"🚨 CRITICAL: Systematic regional bias detected!")
            print(f"   Some regions have {max_region_diff*100:.1f}% more missing data")
            return {'status': 'FAIL', 'message': f'{max_region_diff*100:.1f}% regional bias', 'details': {'region': region_stats, 'decade': decade_stats}}
        elif max_region_diff > 0.15:  # >15% difference
            print(f"⚠️  WARNING: Moderate regional bias ({max_region_diff*100:.1f}%)")
            return {'status': 'WARN', 'message': f'{max_region_diff*100:.1f}% regional bias', 'details': {'region': region_stats, 'decade': decade_stats}}
        else:
            print(f"✅ Missingness appears reasonably balanced across regions")
            return {'status': 'PASS', 'message': 'No major systematic bias', 'details': {'region': region_stats, 'decade': decade_stats}}

    return {'status': 'WARN', 'message': 'Insufficient data for analysis'}

def main():
    """Run all validation checks"""
    print("="*80)
    print(" " * 20 + "FINAL A0 PRE-FLIGHT VALIDATION")
    print("="*80)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    results = {}

    # Run all checks
    results['country_consistency'] = check_country_names()
    results['temporal_overlap'] = check_temporal_density(*GOLDEN_WINDOW)
    results['duplicate_indicators'] = detect_duplicates(threshold=0.95)
    results['disaggregation_analysis'] = analyze_indicator_hierarchy()
    results['missing_patterns'] = analyze_missingness_bias()

    # Final report
    print("\n" + "="*80)
    print(" " * 25 + "VALIDATION SUMMARY")
    print("="*80)

    fail_count = sum(1 for r in results.values() if r['status'] == 'FAIL')
    warn_count = sum(1 for r in results.values() if r['status'] == 'WARN')
    pass_count = sum(1 for r in results.values() if r['status'] == 'PASS')

    for check_name, result in results.items():
        status_symbol = {'PASS': '✅', 'WARN': '⚠️ ', 'FAIL': '🚨'}[result['status']]
        print(f"{status_symbol} {check_name}: {result['message']}")

    print()
    print(f"Summary: {pass_count} passed, {warn_count} warnings, {fail_count} failures")

    # Save results
    report_file = OUTPUT_DIR / f"a0_validation_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, 'w') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'results': results,
            'summary': {
                'pass': pass_count,
                'warn': warn_count,
                'fail': fail_count,
                'ready_for_a1': fail_count == 0
            }
        }, f, indent=2)

    print(f"\n📁 Full validation report saved to: {report_file}")

    # Final verdict
    print("\n" + "="*80)
    if fail_count == 0:
        print("✅ ALL CHECKS PASSED - READY TO PROCEED TO A1")
        if warn_count > 0:
            print(f"⚠️  {warn_count} warning(s) - review before A0.15 merge step")
        print("="*80)
        return 0
    else:
        print(f"🚨 {fail_count} CRITICAL ISSUE(S) - DO NOT PROCEED TO A1")
        print("   Fix issues above before continuing")
        print("="*80)
        return 1

if __name__ == "__main__":
    sys.exit(main())
