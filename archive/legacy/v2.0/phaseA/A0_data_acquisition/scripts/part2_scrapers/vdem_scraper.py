#!/usr/bin/env python3
"""
V-Dem (Varieties of Democracy) Data Scraper

Extracts individual indicators from V-Dem Country-Year Full+Others v15 dataset
into standardized CSV format (Country, Year, Value).

Source: https://v-dem.net/
Dataset: V-Dem Country-Year Full+Others v15
Indicators: 4,607 columns (includes indices, indicators, and external variables)
Coverage: ~200 countries, 1789-2024
"""

import pandas as pd
from pathlib import Path
import json
from datetime import datetime
import sys

# Configuration
BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "raw_data" / "vdem"
LOG_DIR = BASE_DIR / "extraction_logs"
PROGRESS_FILE = LOG_DIR / "vdem_progress.json"

# V-Dem CSV file (already extracted from zip)
VDEM_CSV = BASE_DIR / "V-Dem-CY-Full+Others-v15.csv"

# Metadata columns to skip (not indicators)
SKIP_COLUMNS = [
    'country_name', 'country_text_id', 'country_id', 'year',
    'historical_date', 'project', 'historical', 'histname',
    'codingstart', 'codingend', 'codingstart_contemp', 'codingend_contemp',
    'codingstart_hist', 'codingend_hist', 'gapstart1', 'gapstart2',
    'gapstart3', 'gapend1', 'gapend2', 'gapend3'
]

def load_vdem_data():
    """Load V-Dem dataset into pandas DataFrame"""
    print(f"Loading V-Dem dataset into memory...")
    print(f"File: {VDEM_CSV}")
    print(f"(This may take 1-2 minutes for 400+ MB file)")

    try:
        df = pd.read_csv(VDEM_CSV, low_memory=False)

        print(f"✅ Loaded successfully")
        print(f"   Shape: {df.shape[0]:,} rows × {df.shape[1]:,} columns")
        print(f"   Years: {df['year'].min()} - {df['year'].max()}")
        print(f"   Countries: {df['country_name'].nunique()} unique")

        return df

    except Exception as e:
        print(f"❌ Error loading dataset: {str(e)}")
        sys.exit(1)

def identify_indicators(df):
    """Identify all indicator columns (non-metadata)"""
    indicator_cols = [col for col in df.columns if col not in SKIP_COLUMNS]

    print(f"\nIdentified {len(indicator_cols):,} indicators to extract")
    print(f"   (Excluding {len(SKIP_COLUMNS)} metadata columns)")

    return indicator_cols

def extract_indicator(df, indicator_id):
    """Extract single indicator into standardized format"""
    try:
        subset = df[['country_name', 'year', indicator_id]].copy()
        subset = subset.dropna(subset=[indicator_id])

        if len(subset) == 0:
            return {'indicator_id': indicator_id, 'status': 'empty'}

        subset.columns = ['Country', 'Year', 'Value']
        subset['Year'] = subset['Year'].astype(int)

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
        return {'indicator_id': indicator_id, 'status': 'error', 'error': str(e)}

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
    """Extract all indicators from V-Dem dataset"""
    print(f"\n{'='*80}")
    print(f"  EXTRACTING {len(indicator_cols):,} V-DEM INDICATORS")
    print(f"{'='*80}\n")

    completed = []
    failed = []
    empty = []
    total = len(indicator_cols)

    for idx, indicator_id in enumerate(indicator_cols, 1):
        result = extract_indicator(df, indicator_id)

        if result['status'] == 'success':
            completed.append(indicator_id)
            if idx % 200 == 0:
                print(f"[{idx:4d}/{total}] {indicator_id:40s} | "
                      f"{result['rows_extracted']:6,} rows | "
                      f"{result['countries']:3d} countries | "
                      f"{result['year_range'][0]}-{result['year_range'][1]}")
        elif result['status'] == 'empty':
            empty.append(indicator_id)
        else:
            failed.append({'indicator_id': indicator_id, 'error': result.get('error', 'Unknown')})

        if idx % 500 == 0:
            stats = {'total': total, 'completed': len(completed), 'empty': len(empty), 'failed': len(failed)}
            save_progress(completed, failed, empty, stats)

    print(f"\n{'='*80}")
    print(f"  EXTRACTION COMPLETE")
    print(f"{'='*80}")
    print(f"Total indicators: {total:,}")
    print(f"✅ Extracted successfully: {len(completed):,}")
    print(f"⚠️  Empty (no data): {len(empty):,}")
    print(f"❌ Failed (errors): {len(failed):,}")

    stats = {'total': total, 'completed': len(completed), 'empty': len(empty), 'failed': len(failed)}
    save_progress(completed, failed, empty, stats)

    return completed, failed, empty

def main():
    """Main execution"""
    print("="*80)
    print(" " * 25 + "V-DEM DATA EXTRACTION")
    print("="*80)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Output directory: {OUTPUT_DIR}")
    print()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    df = load_vdem_data()
    indicator_cols = identify_indicators(df)
    completed, failed, empty = extract_all_indicators(df, indicator_cols)

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
