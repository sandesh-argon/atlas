"""
A1 Step 2: Split panel data into country-specific files.

Input: data/raw/v21_panel_data_for_v3.parquet (long format)
Output: data/processed/countries/{COUNTRY}.parquet (wide format per country)

Wide format: rows = years, columns = indicators
This format is needed for time series analysis in A.2.
"""

import pandas as pd
from pathlib import Path
from tqdm import tqdm


def split_panel_by_country(panel_path: str, output_dir: str, use_quality_filter: bool = True):
    """
    Split panel data into country-specific wide-format files.

    Args:
        panel_path: Path to long-format panel parquet
        output_dir: Directory to save country files
        use_quality_filter: If True, only include countries from data_quality.csv (202 main countries)
    """
    print("Loading panel data...")
    panel = pd.read_parquet(panel_path)

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Get list of countries to process
    if use_quality_filter:
        # Use the 202 main analysis countries from V2.1 quality assessment
        quality_path = Path('data/raw/v21_data_quality.csv')
        if quality_path.exists():
            quality_df = pd.read_csv(quality_path)
            countries = quality_df['country'].tolist()
            print(f"Using {len(countries)} countries from quality filter")
        else:
            print("⚠️  Quality filter file not found, using all countries")
            countries = panel['country'].unique().tolist()
    else:
        countries = panel['country'].unique().tolist()

    print(f"Splitting into {len(countries)} country files...")

    # Track statistics
    stats = []

    for country in tqdm(countries, desc="Countries"):
        # Filter data for this country
        country_data = panel[panel['country'] == country].copy()

        if len(country_data) == 0:
            print(f"  ⚠️  No data for {country}")
            continue

        # Pivot to wide format: rows=years, columns=indicators
        try:
            country_wide = country_data.pivot(
                index='year',
                columns='indicator_id',
                values='value'
            )
            country_wide = country_wide.reset_index()
            country_wide.columns.name = None  # Remove column index name

            # Save as parquet (sanitize "/" in country names)
            safe_country = country.replace('/', '_')
            output_path = output_dir / f"{safe_country}.parquet"
            country_wide.to_parquet(output_path, index=False)

            # Track stats
            n_years = len(country_wide)
            n_indicators = len(country_wide.columns) - 1  # Exclude 'year' column
            completeness = country_wide.drop(columns=['year']).notna().mean().mean()

            stats.append({
                'country': country,
                'n_years': n_years,
                'n_indicators': n_indicators,
                'completeness': completeness,
                'rows_in_long': len(country_data)
            })

        except Exception as e:
            print(f"  ❌ Error processing {country}: {e}")
            stats.append({
                'country': country,
                'n_years': 0,
                'n_indicators': 0,
                'completeness': 0,
                'error': str(e)
            })

    # Save stats
    stats_df = pd.DataFrame(stats)
    stats_path = Path('outputs/validation/country_split_stats.csv')
    stats_path.parent.mkdir(parents=True, exist_ok=True)
    stats_df.to_csv(stats_path, index=False)

    # Summary
    successful = stats_df[stats_df.get('error', '').isna() | (stats_df.get('error', '') == '')]
    if 'error' not in stats_df.columns:
        successful = stats_df

    print(f"\n✅ Split complete!")
    print(f"  Files created: {len(successful)}")
    print(f"  Output directory: {output_dir}")
    print(f"  Mean completeness: {successful['completeness'].mean():.1%}")
    print(f"  Stats saved to: {stats_path}")


if __name__ == "__main__":
    split_panel_by_country(
        panel_path='data/raw/v21_panel_data_for_v3.parquet',
        output_dir='data/processed/countries',
        use_quality_filter=True  # Use 202 main countries
    )
