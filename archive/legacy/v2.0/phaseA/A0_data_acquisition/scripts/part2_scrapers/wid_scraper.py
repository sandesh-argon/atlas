#!/usr/bin/env python3
"""
World Inequality Database (WID) Data Scraper

Extracts individual indicators from WID country-level files
into standardized CSV format (Country, Year, Value).

Source: https://wid.world/data/
Dataset: WID All Data (2025)
Indicators: ~1,938 variables (income, wealth, inequality measures)
Coverage: ~200 countries, varies by indicator (1800-2023)

Note: Extracts only p0p100 percentile (full population average) to avoid
excessive dimensionality from percentile breakdowns (p0p10, p90p100, etc.)
"""

import pandas as pd
from pathlib import Path
import json
from datetime import datetime
import sys
from glob import glob

# Configuration
BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "raw_data" / "wid"
LOG_DIR = BASE_DIR / "extraction_logs"
PROGRESS_FILE = LOG_DIR / "wid_progress.json"

# Target percentile (full population average)
TARGET_PERCENTILE = 'p0p100'

def load_country_metadata():
    """Load country code to name mapping"""
    print("Loading country metadata...")

    try:
        countries_df = pd.read_csv(BASE_DIR / "WID_countries.csv", sep=';')
        country_map = dict(zip(countries_df['alpha2'], countries_df['shortname']))
        print(f"✅ Loaded {len(country_map)} countries")
        return country_map
    except Exception as e:
        print(f"❌ Error loading countries: {str(e)}")
        sys.exit(1)

def load_all_wid_data(country_map):
    """Load all WID country files and combine"""
    print(f"\nLoading WID data from country files...")
    print(f"(This may take 2-3 minutes for 814 MB archive)")

    try:
        # Find all country data files
        data_files = sorted(glob(str(BASE_DIR / "WID_data_*.csv")))
        print(f"   Found {len(data_files)} country files")

        # Load and combine all files
        dfs = []
        for i, file in enumerate(data_files):
            if (i + 1) % 50 == 0:
                print(f"   Loading file {i+1}/{len(data_files)}...")

            df = pd.read_csv(file, sep=';')
            # Filter to target percentile only
            df = df[df['percentile'] == TARGET_PERCENTILE]
            dfs.append(df)

        combined = pd.concat(dfs, ignore_index=True)

        # Map country codes to names
        combined['country_name'] = combined['country'].map(country_map)

        print(f"✅ Loaded successfully")
        print(f"   Shape: {combined.shape[0]:,} rows × {combined.shape[1]:,} columns")
        print(f"   Years: {combined['year'].min()} - {combined['year'].max()}")
        print(f"   Countries: {combined['country'].nunique()} unique")
        print(f"   Variables: {combined['variable'].nunique()} unique")
        print(f"   Percentile: {TARGET_PERCENTILE} (full population)")

        return combined

    except Exception as e:
        print(f"❌ Error loading WID data: {str(e)}")
        sys.exit(1)

def identify_indicators(df):
    """Identify all unique variables (indicators)"""
    indicator_ids = df['variable'].unique().tolist()

    print(f"\nIdentified {len(indicator_ids)} indicators to extract")
    print(f"   (Filtered to percentile: {TARGET_PERCENTILE})")

    return indicator_ids

def extract_indicator(df, indicator_id):
    """
    Extract single indicator into standardized format

    Returns dict with:
    - indicator_id: The indicator name
    - rows_extracted: Number of non-null rows
    - countries: Number of unique countries
    - year_range: (min, max) years
    - status: 'success' or 'empty'
    """
    try:
        # Filter to this indicator
        subset = df[df['variable'] == indicator_id].copy()

        # Select columns: country name, year, value
        subset = subset[['country_name', 'year', 'value']].copy()

        # Drop rows where value is null
        subset = subset.dropna(subset=['value'])

        if len(subset) == 0:
            return {
                'indicator_id': indicator_id,
                'rows_extracted': 0,
                'countries': 0,
                'year_range': None,
                'status': 'empty'
            }

        # Rename columns to standard format
        subset.columns = ['Country', 'Year', 'Value']

        # Convert year to int
        subset['Year'] = subset['Year'].astype(int)

        # Save to CSV
        output_file = OUTPUT_DIR / f"{indicator_id}.csv"
        subset.to_csv(output_file, index=False)

        return {
            'indicator_id': indicator_id,
            'rows_extracted': len(subset),
            'countries': subset['Country'].nunique(),
            'year_range': (int(subset['Year'].min()), int(subset['Year'].max())),
            'status': 'success'
        }

    except Exception as e:
        return {
            'indicator_id': indicator_id,
            'rows_extracted': 0,
            'countries': 0,
            'year_range': None,
            'status': 'error',
            'error': str(e)
        }

def save_progress(completed, failed, empty, stats):
    """Save extraction progress"""
    progress = {
        'timestamp': datetime.now().isoformat(),
        'completed': completed,
        'failed': failed,
        'empty': empty,
        'stats': stats
    }

    with open(PROGRESS_FILE, 'w') as f:
        json.dump(progress, f, indent=2)

def extract_all_indicators(df, indicator_ids):
    """Extract all indicators from WID dataset"""
    print(f"\n{'='*80}")
    print(f"  EXTRACTING {len(indicator_ids):,} WID INDICATORS")
    print(f"{'='*80}\n")

    completed = []
    failed = []
    empty = []

    total = len(indicator_ids)

    for idx, indicator_id in enumerate(indicator_ids, 1):
        result = extract_indicator(df, indicator_id)

        if result['status'] == 'success':
            completed.append(indicator_id)

            # Progress update every 100 indicators
            if idx % 100 == 0:
                print(f"[{idx:4d}/{total}] {indicator_id:30s} | "
                      f"{result['rows_extracted']:6,} rows | "
                      f"{result['countries']:3d} countries | "
                      f"{result['year_range'][0]}-{result['year_range'][1]}")

        elif result['status'] == 'empty':
            empty.append(indicator_id)

        else:  # error
            failed.append({
                'indicator_id': indicator_id,
                'error': result.get('error', 'Unknown error')
            })

        # Save progress every 200 indicators
        if idx % 200 == 0:
            stats = {
                'total': total,
                'completed': len(completed),
                'empty': len(empty),
                'failed': len(failed)
            }
            save_progress(completed, failed, empty, stats)

    # Final summary
    print(f"\n{'='*80}")
    print(f"  EXTRACTION COMPLETE")
    print(f"{'='*80}")
    print(f"Total indicators: {total:,}")
    print(f"✅ Extracted successfully: {len(completed):,}")
    print(f"⚠️  Empty (no data): {len(empty):,}")
    print(f"❌ Failed (errors): {len(failed):,}")

    if empty:
        print(f"\nEmpty indicators (first 20):")
        for ind in empty[:20]:
            print(f"   - {ind}")
        if len(empty) > 20:
            print(f"   ... and {len(empty) - 20} more")

    if failed:
        print(f"\nFailed indicators:")
        for item in failed[:10]:
            print(f"   - {item['indicator_id']}: {item['error']}")
        if len(failed) > 10:
            print(f"   ... and {len(failed) - 10} more")

    # Save final progress
    stats = {
        'total': total,
        'completed': len(completed),
        'empty': len(empty),
        'failed': len(failed)
    }
    save_progress(completed, failed, empty, stats)

    return completed, failed, empty

def main():
    """Main execution"""
    print("="*80)
    print(" " * 20 + "WID DATA EXTRACTION")
    print("="*80)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Output directory: {OUTPUT_DIR}")
    print(f"Target percentile: {TARGET_PERCENTILE} (full population)")
    print()

    # Create directories
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    # Load country metadata
    country_map = load_country_metadata()

    # Load all WID data
    df = load_all_wid_data(country_map)

    # Identify indicators
    indicator_ids = identify_indicators(df)

    # Extract all indicators
    completed, failed, empty = extract_all_indicators(df, indicator_ids)

    # Final report
    print(f"\n{'='*80}")
    print(f"  FINAL REPORT")
    print(f"{'='*80}")
    print(f"CSV files created: {len(completed):,}")
    print(f"Empty indicators: {len(empty):,}")
    print(f"Failed extractions: {len(failed):,}")
    print(f"\nOutput location: {OUTPUT_DIR}")
    print(f"Progress log: {PROGRESS_FILE}")
    print("="*80)

    return 0 if len(failed) == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
