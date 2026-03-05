#!/usr/bin/env python3
"""
Penn World Tables (PWT) Data Scraper

Downloads Penn World Tables 11.0 and extracts individual indicators
into standardized CSV format (Country, Year, Value).

Source: https://www.rug.nl/ggdc/productivity/pwt/
Dataset: Penn World Tables 11.0
Indicators: ~180 variables (GDP, productivity, capital, labor)
Coverage: 185 countries, 1950-2023
"""

import pandas as pd
import requests
from pathlib import Path
import json
from datetime import datetime
import sys

# Configuration
BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "raw_data" / "penn"
LOG_DIR = BASE_DIR / "extraction_logs"
PROGRESS_FILE = LOG_DIR / "penn_progress.json"

# Penn World Tables 11.0 Excel download URL
PWT_URL = "https://dataverse.nl/api/access/datafile/554105"

# Metadata columns to skip (not indicators)
SKIP_COLUMNS = [
    'countrycode',  # ISO country code
    'country',  # Country name
    'currency_unit',  # Local currency
    'year'  # Year (will use as index)
]

def download_pwt_dataset():
    """Download Penn World Tables 11.0 Excel file"""
    print(f"Downloading Penn World Tables 11.0...")
    print(f"URL: {PWT_URL}")

    try:
        response = requests.get(PWT_URL, timeout=300)
        response.raise_for_status()

        # Save raw Excel for reference
        raw_file = OUTPUT_DIR / "pwt110.xlsx"
        with open(raw_file, 'wb') as f:
            f.write(response.content)

        print(f"✅ Downloaded successfully ({len(response.content) / 1024 / 1024:.1f} MB)")
        print(f"   Saved to: {raw_file}")

        return raw_file

    except Exception as e:
        print(f"❌ Error downloading PWT dataset: {str(e)}")
        sys.exit(1)

def load_pwt_data(excel_file):
    """Load PWT dataset from Excel into pandas DataFrame"""
    print(f"\nLoading PWT dataset into memory...")

    try:
        # Read Excel file (Data sheet)
        df = pd.read_excel(excel_file, sheet_name='Data')

        print(f"✅ Loaded successfully")
        print(f"   Shape: {df.shape[0]:,} rows × {df.shape[1]:,} columns")
        print(f"   Years: {df['year'].min()} - {df['year'].max()}")
        print(f"   Countries: {df['country'].nunique()} unique")

        return df

    except Exception as e:
        print(f"❌ Error loading dataset: {str(e)}")
        sys.exit(1)

def identify_indicators(df):
    """Identify all indicator columns (non-metadata)"""
    # Get all columns except metadata
    indicator_cols = [col for col in df.columns if col not in SKIP_COLUMNS]

    print(f"\nIdentified {len(indicator_cols)} indicators to extract")
    print(f"   (Excluding {len(SKIP_COLUMNS)} metadata columns)")

    return indicator_cols

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
        # Select columns: country name, year, indicator value
        subset = df[['country', 'year', indicator_id]].copy()

        # Drop rows where indicator value is null
        subset = subset.dropna(subset=[indicator_id])

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

def extract_all_indicators(df, indicator_cols):
    """Extract all indicators from PWT dataset"""
    print(f"\n{'='*80}")
    print(f"  EXTRACTING {len(indicator_cols):,} PENN WORLD TABLES INDICATORS")
    print(f"{'='*80}\n")

    completed = []
    failed = []
    empty = []

    total = len(indicator_cols)

    for idx, indicator_id in enumerate(indicator_cols, 1):
        result = extract_indicator(df, indicator_id)

        if result['status'] == 'success':
            completed.append(indicator_id)

            # Progress update every 20 indicators
            print(f"[{idx:3d}/{total}] {indicator_id:30s} | "
                  f"{result['rows_extracted']:5,} rows | "
                  f"{result['countries']:3d} countries | "
                  f"{result['year_range'][0]}-{result['year_range'][1]}")

        elif result['status'] == 'empty':
            empty.append(indicator_id)
            print(f"[{idx:3d}/{total}] {indicator_id:30s} | EMPTY (no data)")

        else:  # error
            failed.append({
                'indicator_id': indicator_id,
                'error': result.get('error', 'Unknown error')
            })
            print(f"[{idx:3d}/{total}] {indicator_id:30s} | ERROR: {result.get('error', 'Unknown')}")

    # Final summary
    print(f"\n{'='*80}")
    print(f"  EXTRACTION COMPLETE")
    print(f"{'='*80}")
    print(f"Total indicators: {total:,}")
    print(f"✅ Extracted successfully: {len(completed):,}")
    print(f"⚠️  Empty (no data): {len(empty):,}")
    print(f"❌ Failed (errors): {len(failed):,}")

    if empty:
        print(f"\nEmpty indicators:")
        for ind in empty:
            print(f"   - {ind}")

    if failed:
        print(f"\nFailed indicators:")
        for item in failed:
            print(f"   - {item['indicator_id']}: {item['error']}")

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
    print(" " * 20 + "PENN WORLD TABLES EXTRACTION")
    print("="*80)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Output directory: {OUTPUT_DIR}")
    print()

    # Create directories
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    # Check if file already exists locally
    local_file = BASE_DIR / "pwt100.xlsx"
    if local_file.exists():
        print(f"Using existing file: {local_file}")
        raw_file = OUTPUT_DIR / "pwt100.xlsx"
        import shutil
        shutil.copy(local_file, raw_file)
        print(f"✅ Copied to output directory")
    else:
        # Download dataset
        raw_file = download_pwt_dataset()

    # Load into memory
    df = load_pwt_data(raw_file)

    # Identify indicators
    indicator_cols = identify_indicators(df)

    # Extract all indicators
    completed, failed, empty = extract_all_indicators(df, indicator_cols)

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
