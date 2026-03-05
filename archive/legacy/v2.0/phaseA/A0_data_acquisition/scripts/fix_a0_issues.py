#!/usr/bin/env python3
"""
A0 Issue Fixer
==============
Fixes all issues found by verify_a0_final.py:
1. Remove files with wrong schema (not Country,Year,Value)
2. Remove files with future years (>2025)
3. Remove empty files (0 bytes)
4. Remove files with sub-national regions (>300 unique countries)
"""

import pandas as pd
from pathlib import Path
import json
from datetime import datetime

BASE_DIR = Path(__file__).parent.parent
STANDARDIZED_DIR = BASE_DIR / "raw_data_standardized"
LOG_FILE = BASE_DIR / "validation_logs" / f"a0_fixes_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

fixes = {
    'wrong_schema': [],
    'future_years': [],
    'empty_files': [],
    'sub_national': []
}


def fix_schema_issues():
    """Remove files without (Country, Year, Value) schema"""
    print("\n🔧 Fixing schema issues...")

    for csv_file in STANDARDIZED_DIR.rglob("*.csv"):
        try:
            df = pd.read_csv(csv_file, nrows=1, low_memory=False)
            expected = ('Country', 'Year', 'Value')

            if tuple(df.columns) != expected:
                print(f"  Removing {csv_file.name} (schema: {tuple(df.columns[:3])})")
                csv_file.unlink()
                fixes['wrong_schema'].append(str(csv_file.name))
        except Exception as e:
            print(f"  Error with {csv_file.name}: {e}")
            csv_file.unlink()
            fixes['wrong_schema'].append(str(csv_file.name))

    print(f"✅ Removed {len(fixes['wrong_schema'])} files with wrong schema")


def fix_future_years():
    """Remove files with years > 2025"""
    print("\n🔧 Fixing future year issues...")

    for csv_file in STANDARDIZED_DIR.rglob("*.csv"):
        try:
            df = pd.read_csv(csv_file, low_memory=False)

            if 'Year' not in df.columns:
                continue

            max_year = df['Year'].max()

            if max_year > 2025:
                print(f"  Removing {csv_file.name} (max year: {int(max_year)})")
                csv_file.unlink()
                fixes['future_years'].append(str(csv_file.name))
        except Exception:
            continue

    print(f"✅ Removed {len(fixes['future_years'])} files with future years")


def fix_empty_files():
    """Remove 0-byte files"""
    print("\n🔧 Fixing empty files...")

    for csv_file in STANDARDIZED_DIR.rglob("*.csv"):
        if csv_file.stat().st_size < 100:
            print(f"  Removing {csv_file.name} (0 bytes)")
            csv_file.unlink()
            fixes['empty_files'].append(str(csv_file.name))

    print(f"✅ Removed {len(fixes['empty_files'])} empty files")


def fix_sub_national():
    """Remove files with sub-national regions (>300 unique countries)"""
    print("\n🔧 Fixing sub-national region issues...")

    for csv_file in STANDARDIZED_DIR.rglob("*.csv"):
        try:
            df = pd.read_csv(csv_file, low_memory=False)

            if 'Country' not in df.columns:
                continue

            unique_countries = df['Country'].nunique()

            if unique_countries > 300:
                print(f"  Removing {csv_file.name} ({unique_countries} unique countries)")
                csv_file.unlink()
                fixes['sub_national'].append(str(csv_file.name))
        except Exception:
            continue

    print(f"✅ Removed {len(fixes['sub_national'])} files with sub-national regions")


def main():
    print("="*60)
    print("A0 ISSUE FIXER")
    print("="*60)

    # Run all fixes
    fix_empty_files()  # Run first (fastest)
    fix_schema_issues()
    fix_future_years()
    fix_sub_national()

    # Summary
    total_removed = sum(len(v) for v in fixes.values())

    print("\n" + "="*60)
    print("FIX SUMMARY")
    print("="*60)
    print(f"✅ Total files removed: {total_removed}")
    print(f"  - Wrong schema: {len(fixes['wrong_schema'])}")
    print(f"  - Future years: {len(fixes['future_years'])}")
    print(f"  - Empty files: {len(fixes['empty_files'])}")
    print(f"  - Sub-national: {len(fixes['sub_national'])}")

    # Save log
    with open(LOG_FILE, 'w') as f:
        json.dump(fixes, f, indent=2)

    print(f"\n📝 Log saved to: {LOG_FILE.relative_to(BASE_DIR)}")

    # Final count
    remaining = len(list(STANDARDIZED_DIR.rglob("*.csv")))
    print(f"\n✅ Remaining indicators: {remaining:,}")


if __name__ == "__main__":
    main()
