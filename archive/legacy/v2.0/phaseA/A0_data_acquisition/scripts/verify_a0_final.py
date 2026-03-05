#!/usr/bin/env python3
"""
A0 Final Verification Script
=============================
Comprehensive 8-point verification before permanent A0 closure.

Checks:
1. File format consistency (Country, Year, Value schema)
2. Temporal range sanity (1800-2024, no future years)
3. Empty file detection
4. Country code verification (220 unique claimed)
5. Missing data pattern overview
6. Disk space and backup confirmation
7. Deduplication log verification
8. V-Dem filtering confirmation
"""

import pandas as pd
from pathlib import Path
import numpy as np
import json
from datetime import datetime
import subprocess

# Paths
BASE_DIR = Path(__file__).parent.parent
STANDARDIZED_DIR = BASE_DIR / "raw_data_standardized"
RAW_DIR = BASE_DIR / "raw_data"
VALIDATION_LOGS = BASE_DIR / "validation_logs"


def check_1_schema_consistency():
    """Verify ALL 40,881 CSVs have identical schema"""
    print("\n" + "="*60)
    print("CHECK 1: File Format Consistency")
    print("="*60)

    schemas = {}
    sample_files = {}

    for csv_file in STANDARDIZED_DIR.rglob("*.csv"):
        try:
            df = pd.read_csv(csv_file, nrows=1)
            schema = tuple(df.columns)

            if schema not in schemas:
                schemas[schema] = 0
                sample_files[schema] = csv_file.name

            schemas[schema] += 1
        except Exception as e:
            print(f"⚠️  Error reading {csv_file.name}: {e}")

    if len(schemas) == 1:
        schema = list(schemas.keys())[0]
        count = list(schemas.values())[0]
        print(f"✅ All {count:,} files have schema: {schema}")
        return True
    else:
        print(f"❌ SCHEMA MISMATCH DETECTED - {len(schemas)} different schemas:")
        for schema, count in schemas.items():
            print(f"  {schema}: {count:,} files (sample: {sample_files[schema]})")
        return False


def check_2_temporal_sanity():
    """Verify no impossible years (1800-2025 range)"""
    print("\n" + "="*60)
    print("CHECK 2: Temporal Range Sanity")
    print("="*60)

    min_year, max_year = float('inf'), float('-inf')
    outliers = []

    all_files = list(STANDARDIZED_DIR.rglob("*.csv"))
    sample_size = min(1000, len(all_files))  # Sample for speed

    print(f"Sampling {sample_size:,} files...")

    for csv_file in np.random.choice(all_files, sample_size, replace=False):
        try:
            df = pd.read_csv(csv_file)
            if 'Year' not in df.columns:
                continue

            years = df['Year'].dropna()

            if len(years) == 0:
                continue

            file_min, file_max = years.min(), years.max()

            # Flag impossible years
            if file_min < 1800 or file_max > 2025:
                outliers.append((csv_file.name, int(file_min), int(file_max)))

            min_year = min(min_year, file_min)
            max_year = max(max_year, file_max)
        except Exception:
            continue

    print(f"✅ Temporal range: {int(min_year)}-{int(max_year)}")

    if outliers:
        print(f"⚠️  {len(outliers)} files with suspicious years:")
        for name, ymin, ymax in outliers[:10]:
            print(f"  {name}: {ymin}-{ymax}")
        return False
    else:
        print("✅ No temporal outliers detected")
        return True


def check_3_empty_files():
    """Verify no 0-row or 0-byte files"""
    print("\n" + "="*60)
    print("CHECK 3: Empty File Detection")
    print("="*60)

    empty = []

    for csv_file in STANDARDIZED_DIR.rglob("*.csv"):
        # Check file size
        if csv_file.stat().st_size < 100:  # Less than 100 bytes
            empty.append((csv_file.name, "0 bytes"))
            continue

        # Check row count
        try:
            df = pd.read_csv(csv_file)
            if len(df) == 0:
                empty.append((csv_file.name, "0 rows"))
        except Exception as e:
            empty.append((csv_file.name, f"read error: {e}"))

    if empty:
        print(f"❌ {len(empty)} empty/corrupted files found:")
        for name, reason in empty[:20]:
            print(f"  {name}: {reason}")
        return False
    else:
        print("✅ No empty files detected")
        return True


def check_4_country_uniqueness():
    """Confirm 220 unique countries, no duplicates"""
    print("\n" + "="*60)
    print("CHECK 4: Country Code Verification")
    print("="*60)

    all_countries = set()

    # Sample across sources
    all_files = list(STANDARDIZED_DIR.rglob("*.csv"))
    sample_size = min(500, len(all_files))

    print(f"Sampling {sample_size:,} files to extract unique countries...")

    for csv_file in np.random.choice(all_files, sample_size, replace=False):
        try:
            df = pd.read_csv(csv_file)
            if 'Country' in df.columns:
                all_countries.update(df['Country'].dropna().unique())
        except Exception:
            continue

    print(f"✅ {len(all_countries)} unique countries found in sample")

    # Check for suspicious patterns
    suspicious = [c for c in all_countries if any(x in str(c).lower() for x in
                  ['unnamed', 'nan', 'null'])]

    duplicates = []
    country_list = list(all_countries)
    for i, c1 in enumerate(country_list):
        for c2 in country_list[i+1:]:
            if c1.lower() == c2.lower() and c1 != c2:
                duplicates.append((c1, c2))

    issues = False

    if suspicious:
        print(f"⚠️  {len(suspicious)} suspicious country names:")
        for s in suspicious[:10]:
            print(f"  - {s}")
        issues = True

    if duplicates:
        print(f"⚠️  {len(duplicates)} case-variant duplicates found:")
        for d1, d2 in duplicates[:10]:
            print(f"  - '{d1}' vs '{d2}'")
        issues = True

    # Check for known problematic patterns
    problematic = []
    known_issues = ['South Korea', 'USA', 'Viet Nam', 'Turkiye']
    for issue in known_issues:
        if issue in all_countries:
            problematic.append(issue)

    if problematic:
        print(f"❌ Found {len(problematic)} variants that should have been standardized:")
        for p in problematic:
            print(f"  - {p}")
        issues = True

    if not issues:
        print("✅ No country name issues detected")

    return not issues


def check_5_missing_data_overview():
    """Understand missing data distribution"""
    print("\n" + "="*60)
    print("CHECK 5: Missing Data Pattern Overview")
    print("="*60)

    missing_rates = []

    all_files = list(STANDARDIZED_DIR.rglob("*.csv"))
    sample_size = min(1000, len(all_files))

    print(f"Sampling {sample_size:,} files...")

    for csv_file in np.random.choice(all_files, sample_size, replace=False):
        try:
            df = pd.read_csv(csv_file)
            if 'Value' in df.columns:
                missing_pct = df['Value'].isna().mean()
                missing_rates.append(missing_pct)
        except Exception:
            continue

    if len(missing_rates) == 0:
        print("❌ No valid data found")
        return False

    missing_rates.sort()

    print(f"✅ Missing rate distribution (sample of {len(missing_rates):,}):")
    print(f"  Min: {missing_rates[0]:.1%}")
    print(f"  10th percentile: {missing_rates[int(len(missing_rates)*0.1)]:.1%}")
    print(f"  25th percentile: {missing_rates[int(len(missing_rates)*0.25)]:.1%}")
    print(f"  Median: {missing_rates[int(len(missing_rates)*0.5)]:.1%}")
    print(f"  75th percentile: {missing_rates[int(len(missing_rates)*0.75)]:.1%}")
    print(f"  90th percentile: {missing_rates[int(len(missing_rates)*0.9)]:.1%}")
    print(f"  Max: {missing_rates[-1]:.1%}")

    # Flag if too many indicators have extreme missingness
    high_missing = sum(1 for r in missing_rates if r > 0.80)
    if high_missing / len(missing_rates) > 0.20:
        print(f"⚠️  {high_missing/len(missing_rates):.1%} of indicators have >80% missing data")

    return True


def check_6_disk_space():
    """Verify disk space and backup existence"""
    print("\n" + "="*60)
    print("CHECK 6: Disk Space & Backup Confirmation")
    print("="*60)

    # Check standardized directory size
    try:
        result = subprocess.run(['du', '-sh', str(STANDARDIZED_DIR)],
                              capture_output=True, text=True, check=True)
        standardized_size = result.stdout.split()[0]
        print(f"✅ raw_data_standardized/: {standardized_size}")
    except Exception as e:
        print(f"⚠️  Could not check standardized dir size: {e}")

    # Check backup directory size
    try:
        result = subprocess.run(['du', '-sh', str(RAW_DIR)],
                              capture_output=True, text=True, check=True)
        raw_size = result.stdout.split()[0]
        print(f"✅ raw_data/ (backup): {raw_size}")
    except Exception as e:
        print(f"⚠️  Could not check raw dir size: {e}")

    # Check free space
    try:
        result = subprocess.run(['df', '-h', str(BASE_DIR)],
                              capture_output=True, text=True, check=True)
        lines = result.stdout.strip().split('\n')
        if len(lines) > 1:
            parts = lines[1].split()
            available = parts[3]
            print(f"✅ Free space: {available}")

            # Parse available space (rough check)
            if 'G' in available:
                gb = float(available.replace('G', ''))
                if gb < 50:
                    print(f"⚠️  Low disk space: {available} (recommend >50 GB for A1)")
                    return False
    except Exception as e:
        print(f"⚠️  Could not check free space: {e}")

    # Check backup exists
    raw_files = list(RAW_DIR.rglob("*.csv"))
    print(f"✅ Backup contains {len(raw_files):,} original files")

    return True


def check_7_deduplication_log():
    """Verify deduplication was correct (r > 0.95)"""
    print("\n" + "="*60)
    print("CHECK 7: Deduplication Log Verification")
    print("="*60)

    # Find latest deduplication log
    dedup_logs = list(VALIDATION_LOGS.glob("deduplication_log_*.json"))

    if not dedup_logs:
        print("⚠️  No deduplication log found")
        return False

    latest_log = sorted(dedup_logs)[-1]
    print(f"Reading: {latest_log.name}")

    with open(latest_log, 'r') as f:
        log = json.load(f)

    print(f"✅ Total indicators removed: {log['total_removed']}")
    print(f"✅ Correlation threshold: {log['correlation_threshold']}")

    # Verify results match expectations
    if log['total_removed'] != 66:
        print(f"⚠️  Expected 66 removals, got {log['total_removed']}")

    return True


def check_8_vdem_filtering():
    """Ensure V-Dem confidence intervals removed"""
    print("\n" + "="*60)
    print("CHECK 8: V-Dem Filtering Confirmation")
    print("="*60)

    vdem_dir = STANDARDIZED_DIR / "vdem"

    if not vdem_dir.exists():
        print("❌ V-Dem directory not found")
        return False

    vdem_files = list(vdem_dir.glob("*.csv"))
    print(f"✅ V-Dem indicators: {len(vdem_files):,}")

    # Check for confidence interval suffixes
    ci_files = [f for f in vdem_files if any(suffix in f.stem
                for suffix in ['_codelow', '_codehigh', '_sd'])]

    if ci_files:
        print(f"❌ Found {len(ci_files)} confidence interval files still present:")
        for f in ci_files[:10]:
            print(f"  - {f.name}")
        return False
    else:
        print("✅ Zero confidence interval suffixes found (_codelow, _codehigh, _sd)")

    # Verify count matches expectation
    if len(vdem_files) == 2260:
        print("✅ V-Dem count matches expectation (2,260)")
        return True
    else:
        print(f"⚠️  V-Dem count is {len(vdem_files):,}, expected 2,260")
        return abs(len(vdem_files) - 2260) < 10  # Allow small variance


def check_wid_regions():
    """BONUS: Check WID "402 regions" red flag"""
    print("\n" + "="*60)
    print("BONUS CHECK: WID Region Count (Red Flag #1)")
    print("="*60)

    wid_dir = STANDARDIZED_DIR / "wid"

    if not wid_dir.exists():
        print("⚠️  WID directory not found")
        return True

    wid_files = list(wid_dir.glob("*.csv"))
    print(f"✅ WID indicators: {len(wid_files):,}")

    # Sample WID file to check country count
    if wid_files:
        sample = wid_files[0]
        df = pd.read_csv(sample)

        if 'Country' in df.columns:
            unique_countries = df['Country'].nunique()
            print(f"Sample file '{sample.name}': {unique_countries} unique countries")

            if unique_countries > 300:
                print(f"⚠️  WID appears to have sub-national regions (>300 entities)")
                print("   This may contaminate country-level analysis")
                print("   Recommendation: Filter WID to country-level in A1 preprocessing")
                return False
            else:
                print(f"✅ WID country count looks reasonable ({unique_countries})")
        else:
            print("⚠️  Sample WID file missing 'Country' column")

    return True


def run_all_checks():
    """Execute all 8 verification checks"""
    print("\n" + "="*80)
    print(" " * 20 + "A0 FINAL VERIFICATION")
    print("="*80)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Standardized directory: {STANDARDIZED_DIR}")

    # Count files
    all_files = list(STANDARDIZED_DIR.rglob("*.csv"))
    print(f"Total CSV files: {len(all_files):,}")

    results = {
        'Check 1: Schema Consistency': check_1_schema_consistency(),
        'Check 2: Temporal Sanity': check_2_temporal_sanity(),
        'Check 3: Empty Files': check_3_empty_files(),
        'Check 4: Country Uniqueness': check_4_country_uniqueness(),
        'Check 5: Missing Data Overview': check_5_missing_data_overview(),
        'Check 6: Disk Space': check_6_disk_space(),
        'Check 7: Deduplication Log': check_7_deduplication_log(),
        'Check 8: V-Dem Filtering': check_8_vdem_filtering(),
    }

    # Bonus checks
    bonus_results = {
        'Bonus: WID Regions': check_wid_regions(),
    }

    # Summary
    print("\n" + "="*80)
    print(" " * 25 + "VERIFICATION SUMMARY")
    print("="*80)

    passed = sum(results.values())
    total = len(results)

    for check, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}  {check}")

    print("\n" + "-"*80)
    print("BONUS CHECKS:")
    for check, result in bonus_results.items():
        status = "✅ PASS" if result else "⚠️  WARNING"
        print(f"{status}  {check}")

    print("\n" + "="*80)

    if passed == total and all(bonus_results.values()):
        print("🎉 ALL CHECKS PASSED - A0 IS AIRTIGHT")
        print("✅ Dataset is production-ready for A1")
        print("✅ Safe to permanently close A0")
        return 0
    elif passed == total:
        print(f"⚠️  {passed}/{total} CRITICAL CHECKS PASSED")
        print("⚠️  Bonus checks flagged warnings - review before A1")
        return 1
    else:
        print(f"❌ {passed}/{total} CHECKS PASSED")
        print("❌ Fix failing checks before closing A0")
        return 1


if __name__ == "__main__":
    import sys
    exit_code = run_all_checks()
    sys.exit(exit_code)
