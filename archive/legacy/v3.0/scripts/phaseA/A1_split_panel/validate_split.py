"""
A1 Step 3: Validate country split was successful.

Checks:
1. All expected countries have files
2. Row counts are reasonable
3. Sample country (Rwanda) validates correctly
"""

import pandas as pd
from pathlib import Path


def validate_country_splits(countries_dir: str, expected_countries_file: str = None):
    """
    Verify split was successful.

    Args:
        countries_dir: Path to data/processed/countries/
        expected_countries_file: Path to v21_data_quality.csv (optional)
    """
    print("Validating country split...")

    countries_dir = Path(countries_dir)
    split_files = list(countries_dir.glob('*.parquet'))
    split_countries = set([f.stem for f in split_files])

    issues = []

    # Check expected countries if quality file provided
    if expected_countries_file:
        expected_df = pd.read_csv(expected_countries_file)
        expected_countries = set(expected_df['country'].tolist())

        missing = expected_countries - split_countries
        extra = split_countries - expected_countries

        if missing:
            issues.append(f"Missing country files: {list(missing)[:10]}...")
        if extra:
            # Extra is OK - might have more countries than in quality filter
            print(f"  Note: {len(extra)} extra countries beyond quality filter")

        print(f"Expected countries: {len(expected_countries)}")

    print(f"Split files found: {len(split_files)}")

    # Check each file
    stats = []
    for split_file in split_files:
        country_code = split_file.stem
        try:
            country_data = pd.read_parquet(split_file)

            # Should have 'year' column
            if 'year' not in country_data.columns:
                issues.append(f"{country_code}: Missing 'year' column")
                continue

            n_years = len(country_data)
            n_indicators = len(country_data.columns) - 1  # Exclude year
            year_range = f"{country_data['year'].min()}-{country_data['year'].max()}"

            stats.append({
                'country': country_code,
                'n_years': n_years,
                'n_indicators': n_indicators,
                'year_range': year_range
            })

            # Sanity checks
            if n_years < 5:
                issues.append(f"{country_code}: Only {n_years} years of data")
            if n_indicators < 100:
                issues.append(f"{country_code}: Only {n_indicators} indicators")

        except Exception as e:
            issues.append(f"{country_code}: Error reading file - {e}")

    stats_df = pd.DataFrame(stats)

    # Summary
    print(f"\nSplit validation summary:")
    print(f"  Countries processed: {len(stats_df)}")
    print(f"  Mean years per country: {stats_df['n_years'].mean():.1f}")
    print(f"  Mean indicators per country: {stats_df['n_indicators'].mean():.0f}")
    print(f"  Country with most data: {stats_df.loc[stats_df['n_indicators'].idxmax(), 'country']}")
    print(f"  Country with least data: {stats_df.loc[stats_df['n_indicators'].idxmin(), 'country']}")

    # Spot check Rwanda
    if 'Rwanda' in split_countries:
        rwa_data = pd.read_parquet(countries_dir / 'Rwanda.parquet')
        print(f"\n  Rwanda spot check:")
        print(f"    Years: {len(rwa_data)}")
        print(f"    Indicators: {len(rwa_data.columns) - 1}")
        print(f"    Year range: {rwa_data['year'].min()}-{rwa_data['year'].max()}")

    if issues:
        print(f"\n⚠️  ISSUES FOUND ({len(issues)}):")
        for issue in issues[:10]:  # Show first 10
            print(f"  - {issue}")
        if len(issues) > 10:
            print(f"  ... and {len(issues) - 10} more")
        return False
    else:
        print("\n✅ Split validation passed")
        return True


if __name__ == "__main__":
    success = validate_country_splits(
        countries_dir='data/processed/countries',
        expected_countries_file='data/raw/v21_data_quality.csv'
    )

    if not success:
        print("\n❌ Split validation failed - review issues before A.2")
        exit(1)
