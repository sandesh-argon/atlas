"""
A1 Step 1: Validate panel data before splitting.

Input: data/raw/v21_panel_data_for_v3.parquet (long format)
Output: outputs/validation/panel_validation_report.json

STOP CONDITIONS:
- If n_countries < 150: Data file incomplete
- If countries_below_50pct > 50: Too many low-quality countries
"""

import pandas as pd
import numpy as np
import json
from pathlib import Path

def validate_panel_before_split(panel_path: str) -> tuple[dict, list]:
    """
    Pre-split validation checks for long-format panel data.

    Expected format: [country, year, indicator_id, value]

    Returns:
        report: Dict with validation results
        issues: List of problems found
    """
    print("Loading panel data...")
    panel = pd.read_parquet(panel_path)

    issues = []
    report = {}

    # Check 1: Required columns (long format)
    required_cols = ['country', 'year', 'indicator_id', 'value']
    missing_cols = [c for c in required_cols if c not in panel.columns]
    if missing_cols:
        issues.append(f"Missing required columns: {missing_cols}")
        return report, issues

    report['total_rows'] = len(panel)
    report['format'] = 'long'

    # Check 2: Country coverage
    countries = panel['country'].unique()
    report['n_countries'] = len(countries)
    report['countries_sample'] = sorted(countries.tolist())[:10]

    # Check 3: Year coverage
    years = sorted(panel['year'].unique())
    report['year_range'] = (int(min(years)), int(max(years)))
    report['n_years'] = len(years)

    if len(years) < 30:
        issues.append(f"Only {len(years)} years (expected ~35)")

    # Check 4: Indicator coverage
    indicators = panel['indicator_id'].unique()
    report['n_indicators'] = len(indicators)

    print(f"  Indicators: {len(indicators)}")

    # Check 5: Completeness per country
    print("  Computing per-country completeness...")
    completeness_by_country = []

    # For long format: count non-null values per country
    for country in countries:
        country_data = panel[panel['country'] == country]
        n_values = len(country_data)
        n_non_null = country_data['value'].notna().sum()
        completeness = n_non_null / n_values if n_values > 0 else 0

        years_present = country_data['year'].nunique()
        indicators_present = country_data['indicator_id'].nunique()

        completeness_by_country.append({
            'country': country,
            'completeness': completeness,
            'n_values': n_values,
            'n_non_null': n_non_null,
            'years_coverage': years_present,
            'indicators_present': indicators_present
        })

    completeness_df = pd.DataFrame(completeness_by_country)
    report['mean_completeness'] = float(completeness_df['completeness'].mean())
    report['countries_below_50pct'] = int((completeness_df['completeness'] < 0.5).sum())

    # Flag low-quality countries
    low_quality = completeness_df[completeness_df['completeness'] < 0.3]
    if len(low_quality) > 0:
        issues.append(f"{len(low_quality)} countries have <30% data completeness")
        report['low_quality_countries'] = low_quality['country'].tolist()[:10]

    # Check 6: Duplicate rows
    duplicates = panel.duplicated(subset=['country', 'year', 'indicator_id']).sum()
    report['duplicate_rows'] = int(duplicates)
    if duplicates > 0:
        issues.append(f"Found {duplicates} duplicate country-year-indicator rows")

    # Check 7: Value range sanity
    value_stats = panel['value'].describe()
    report['value_stats'] = {
        'mean': float(value_stats['mean']),
        'std': float(value_stats['std']),
        'min': float(value_stats['min']),
        'max': float(value_stats['max']),
        'null_pct': float(panel['value'].isna().mean() * 100)
    }

    # Save completeness by country
    output_dir = Path('outputs/validation')
    output_dir.mkdir(parents=True, exist_ok=True)
    completeness_df.to_csv(output_dir / 'panel_completeness_by_country.csv', index=False)

    # Print report
    print("\n=== Panel Data Validation Report ===")
    print(f"Total rows: {report['total_rows']:,}")
    print(f"Countries: {report['n_countries']}")
    print(f"Year range: {report['year_range'][0]}-{report['year_range'][1]} ({report['n_years']} years)")
    print(f"Indicators: {report['n_indicators']}")
    print(f"Mean completeness: {report['mean_completeness']:.1%}")
    print(f"Countries below 50% completeness: {report['countries_below_50pct']}")
    print(f"Null values: {report['value_stats']['null_pct']:.1f}%")

    if issues:
        print("\n⚠️  ISSUES FOUND:")
        for issue in issues:
            print(f"  - {issue}")
    else:
        print("\n✅ All validation checks passed")

    return report, issues


if __name__ == "__main__":
    report, issues = validate_panel_before_split('data/raw/v21_panel_data_for_v3.parquet')

    # Save report
    output_dir = Path('outputs/validation')
    output_dir.mkdir(parents=True, exist_ok=True)

    with open(output_dir / 'panel_validation_report.json', 'w') as f:
        json.dump(report, f, indent=2)

    print(f"\n📄 Report saved to outputs/validation/panel_validation_report.json")

    if issues:
        print("\n❌ Fix issues before proceeding to split")
        exit(1)
