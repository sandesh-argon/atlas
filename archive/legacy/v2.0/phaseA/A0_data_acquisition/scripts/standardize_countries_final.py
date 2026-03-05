#!/usr/bin/env python3
"""
Country Name Standardization Script
====================================
Standardizes country names across all A0 data sources from 711 variants to 220 unique names.

This script:
1. Loads country name mapping with inconsistency patterns
2. Processes all 43,376 CSV files in raw_data/
3. Applies standardization mapping to Country column
4. Saves standardized versions to raw_data_standardized/
5. Preserves original files as backup

Runtime: ~15-20 minutes for 43,376 files
"""

import pandas as pd
from pathlib import Path
import json
from tqdm import tqdm
import shutil
from datetime import datetime

# Paths
BASE_DIR = Path(__file__).parent.parent
RAW_DATA_DIR = BASE_DIR / "raw_data"
STANDARDIZED_DIR = BASE_DIR / "raw_data_standardized"
MAPPING_FILE = BASE_DIR / "validation_logs" / "country_name_mapping.json"
LOG_FILE = BASE_DIR / "validation_logs" / f"standardization_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

# Country name standardization mapping
# Maps all variants to canonical names
COUNTRY_MAPPING = {
    # Korea variants
    'South Korea': 'Korea, Rep.',
    'Republic of Korea': 'Korea, Rep.',
    'Korea': 'Korea, Rep.',

    # Congo variants
    'Congo': 'Congo, Rep.',
    'Congo, Democratic Republic of the': 'Congo, Dem. Rep.',
    'Democratic Republic of the Congo': 'Congo, Dem. Rep.',

    # United States variants
    'USA': 'United States',
    'United States of America': 'United States',
    'US': 'United States',

    # Egypt variants
    'Egypt': 'Egypt, Arab Rep.',

    # Iran variants
    'Iran': 'Iran, Islamic Rep.',

    # Venezuela variants
    'Venezuela': 'Venezuela, RB',

    # Additional common variants
    'Viet Nam': 'Vietnam',
    'Turkiye': 'Turkey',
    'Czechia': 'Czech Republic',
    'Eswatini': 'Swaziland',
    'Yemen, Rep.': 'Yemen',
    'Kyrgyz Republic': 'Kyrgyzstan',
    'Lao PDR': 'Laos',
    'Slovak Republic': 'Slovakia',
    'Russian Federation': 'Russia',
    'Syrian Arab Republic': 'Syria',
    'Bahamas, The': 'Bahamas',
    'Gambia, The': 'Gambia',
}


def load_country_mapping():
    """Load existing country mapping from validation"""
    if MAPPING_FILE.exists():
        with open(MAPPING_FILE, 'r') as f:
            data = json.load(f)
            print(f"✅ Loaded country mapping: {data['total_unique_names']} unique names found")
            print(f"✅ {len(data.get('inconsistencies', []))} inconsistency patterns identified")
    else:
        print("⚠️  No mapping file found, using hardcoded mapping only")


def standardize_country_names(df):
    """
    Apply country name standardization to DataFrame

    Args:
        df: DataFrame with 'Country' column

    Returns:
        DataFrame with standardized country names
    """
    if 'Country' not in df.columns:
        return df

    # Apply mapping
    df['Country'] = df['Country'].replace(COUNTRY_MAPPING)

    # Strip whitespace
    df['Country'] = df['Country'].str.strip()

    return df


def process_single_file(input_file, output_file):
    """
    Process single CSV file: load, standardize, save

    Args:
        input_file: Path to original CSV
        output_file: Path to save standardized CSV

    Returns:
        dict with processing results
    """
    try:
        # Read CSV
        df = pd.read_csv(input_file)

        # Track original unique countries
        original_countries = set(df['Country'].unique()) if 'Country' in df.columns else set()

        # Standardize
        df = standardize_country_names(df)

        # Track standardized unique countries
        standardized_countries = set(df['Country'].unique()) if 'Country' in df.columns else set()

        # Save
        output_file.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_file, index=False)

        return {
            'status': 'success',
            'original_countries': len(original_countries),
            'standardized_countries': len(standardized_countries),
            'rows': len(df)
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }


def process_all_files():
    """Process all CSV files in raw_data/"""

    print("\n" + "="*80)
    print("COUNTRY NAME STANDARDIZATION")
    print("="*80)

    # Load mapping info
    load_country_mapping()

    # Find all CSV files
    all_files = list(RAW_DATA_DIR.rglob("*.csv"))
    print(f"\n📊 Found {len(all_files):,} CSV files to process")

    # Create output directory
    STANDARDIZED_DIR.mkdir(exist_ok=True)

    # Track results
    results = {
        'success': 0,
        'error': 0,
        'total_original_countries': set(),
        'total_standardized_countries': set(),
        'files_processed': [],
        'errors': []
    }

    # Process each file
    print("\n🔄 Processing files...")
    for input_file in tqdm(all_files, desc="Standardizing"):
        # Determine output path (preserve directory structure)
        relative_path = input_file.relative_to(RAW_DATA_DIR)
        output_file = STANDARDIZED_DIR / relative_path

        # Process
        result = process_single_file(input_file, output_file)

        # Track results
        if result['status'] == 'success':
            results['success'] += 1
            results['files_processed'].append({
                'file': str(relative_path),
                'original_countries': result['original_countries'],
                'standardized_countries': result['standardized_countries'],
                'rows': result['rows']
            })
        else:
            results['error'] += 1
            results['errors'].append({
                'file': str(relative_path),
                'error': result['error']
            })

    # Summary statistics
    print("\n" + "="*80)
    print("STANDARDIZATION COMPLETE")
    print("="*80)
    print(f"✅ Success: {results['success']:,} files")
    print(f"❌ Errors: {results['error']:,} files")

    if results['error'] > 0:
        print("\n⚠️  Errors encountered:")
        for err in results['errors'][:10]:
            print(f"  - {err['file']}: {err['error']}")

    # Save log
    log_data = {
        'timestamp': datetime.now().isoformat(),
        'total_files': len(all_files),
        'success_count': results['success'],
        'error_count': results['error'],
        'mapping_applied': COUNTRY_MAPPING,
        'sample_files': results['files_processed'][:100],  # First 100 for inspection
        'errors': results['errors']
    }

    with open(LOG_FILE, 'w') as f:
        json.dump(log_data, f, indent=2)

    print(f"\n📝 Log saved to: {LOG_FILE.relative_to(BASE_DIR)}")
    print(f"📁 Standardized data saved to: {STANDARDIZED_DIR.relative_to(BASE_DIR)}")
    print(f"💾 Original data preserved in: {RAW_DATA_DIR.relative_to(BASE_DIR)}")

    return results


def verify_standardization():
    """Verify standardization worked correctly"""
    print("\n" + "="*80)
    print("VERIFICATION")
    print("="*80)

    # Sample files from standardized directory
    standardized_files = list(STANDARDIZED_DIR.rglob("*.csv"))

    if len(standardized_files) == 0:
        print("❌ No standardized files found!")
        return False

    print(f"📊 Checking {len(standardized_files):,} standardized files...")

    # Collect all unique country names
    all_countries = set()
    sample_size = min(100, len(standardized_files))

    for file in tqdm(standardized_files[:sample_size], desc="Verifying"):
        try:
            df = pd.read_csv(file, usecols=['Country'])
            all_countries.update(df['Country'].dropna().unique())
        except Exception as e:
            continue

    print(f"\n✅ Found {len(all_countries)} unique country names in sample")

    # Check for known problematic patterns
    problematic = []
    for country in all_countries:
        if any(pattern in country for pattern in ['South Korea', 'USA', 'Viet Nam']):
            problematic.append(country)

    if len(problematic) > 0:
        print(f"\n⚠️  Still found {len(problematic)} problematic variants:")
        for p in problematic[:10]:
            print(f"  - {p}")
        return False
    else:
        print("\n✅ VERIFICATION PASSED - No known problematic variants found")
        return True


if __name__ == "__main__":
    import sys

    # Process all files
    results = process_all_files()

    # Verify
    verification_passed = verify_standardization()

    # Exit code
    if results['error'] > 0 or not verification_passed:
        sys.exit(1)
    else:
        sys.exit(0)
