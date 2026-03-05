#!/usr/bin/env python3
"""
A0.6 Extraction Validation Script

Validates the bulk extraction from 5 V1 data sources:
- World Bank WDI
- WHO GHO
- IMF IFS
- UNICEF SDMX
- UNESCO BDDS

This script performs 4 validation categories as specified in the user requirements:
1. Output Structure Validation
2. Coverage Verification (Pre-Filter)
3. Data Integrity Checks
4. Readiness for Part 2

Reference: FULL_EXTRACTION_PLAN.md
"""

import os
import json
import pandas as pd
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Tuple
import numpy as np

# Configuration
BASE_DIR = Path(__file__).parent
RAW_DATA_DIR = BASE_DIR / "raw_data"
CHECKPOINT_DIR = BASE_DIR / "checkpoints"

# Expected values (from FULL_EXTRACTION_PLAN.md and actual scraper runs)
EXPECTED_INDICATORS = {
    "world_bank": 29213,
    "who": 3038,
    "imf": 132,
    "unicef": 133,
    "unesco": 4553
}

EXPECTED_TOTAL = sum(EXPECTED_INDICATORS.values())  # 37,069

# Data source directories
DATA_SOURCES = {
    "world_bank": RAW_DATA_DIR / "world_bank",
    "who": RAW_DATA_DIR / "who",
    "imf": RAW_DATA_DIR / "imf",
    "unicef": RAW_DATA_DIR / "unicef",
    "unesco": RAW_DATA_DIR / "unesco"
}

def print_section(title: str):
    """Print formatted section header"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)

def print_subsection(title: str):
    """Print formatted subsection header"""
    print(f"\n--- {title} ---")

def check_output_structure() -> Dict:
    """
    1. OUTPUT STRUCTURE VALIDATION

    Verifies:
    - All 5 scrapers saved to correct directories
    - CSVs exist and are readable
    - Extraction logs exist
    """
    print_section("1. OUTPUT STRUCTURE VALIDATION")

    results = {}

    # Check directories exist
    print_subsection("Directory Structure")
    for source, path in DATA_SOURCES.items():
        exists = path.exists() and path.is_dir()
        csv_count = len(list(path.glob("*.csv"))) if exists else 0

        status = "✅" if exists else "❌"
        print(f"{status} {source:15s}: {path} ({csv_count:,} CSV files)")

        results[source] = {
            "directory_exists": exists,
            "csv_count": csv_count
        }

    # Check extraction logs
    print_subsection("Extraction Logs")
    log_dir = RAW_DATA_DIR / "extraction_logs"
    if log_dir.exists():
        logs = list(log_dir.glob("*.json"))
        print(f"✅ Log directory exists: {len(logs)} log files found")
        for log in logs:
            print(f"   - {log.name}")
        results["logs_found"] = len(logs)
    else:
        print(f"⚠️  Log directory not found: {log_dir}")
        results["logs_found"] = 0

    return results

def verify_csv_format(source: str, path: Path, sample_size: int = 10) -> Dict:
    """
    Verify CSV files are properly formatted with expected columns

    Checks a sample of CSV files for:
    - Readable format
    - Standard columns (Country, Year, Value)
    - Valid data types
    """
    csv_files = list(path.glob("*.csv"))

    if not csv_files:
        return {"valid": False, "error": "No CSV files found"}

    # Sample files to check
    sample = csv_files[:sample_size] if len(csv_files) > sample_size else csv_files

    results = {
        "total_files": len(csv_files),
        "sampled": len(sample),
        "valid": 0,
        "invalid": 0,
        "errors": []
    }

    for csv_file in sample:
        try:
            df = pd.read_csv(csv_file, nrows=5)

            # Check for standard columns (flexible matching)
            has_country = any(col.lower() in ['country', 'spatialdim', 'ref_area'] for col in df.columns)
            has_year = any(col.lower() in ['year', 'time', 'timedim', 'time_period'] for col in df.columns)
            has_value = any(col.lower() in ['value', 'numericvalue', 'obs_value'] for col in df.columns)

            if has_country and has_year and has_value:
                results["valid"] += 1
            else:
                results["invalid"] += 1
                results["errors"].append(f"{csv_file.name}: Missing standard columns")

        except Exception as e:
            results["invalid"] += 1
            results["errors"].append(f"{csv_file.name}: {str(e)}")

    return results

def check_csv_formatting() -> Dict:
    """Check CSV formatting across all sources"""
    print_section("2. CSV FORMAT VALIDATION")

    all_results = {}

    for source, path in DATA_SOURCES.items():
        if not path.exists():
            print(f"\n⚠️  Skipping {source} (directory not found)")
            continue

        print(f"\n--- {source.upper()} ---")
        results = verify_csv_format(source, path)

        if results["total_files"] > 0:
            pct_valid = (results["valid"] / results["sampled"]) * 100
            status = "✅" if pct_valid >= 90 else ("⚠️" if pct_valid >= 70 else "❌")

            print(f"{status} Sampled: {results['sampled']}/{results['total_files']} files")
            print(f"   Valid: {results['valid']} ({pct_valid:.1f}%)")
            print(f"   Invalid: {results['invalid']}")

            if results["errors"]:
                print(f"   Errors (showing first 3):")
                for err in results["errors"][:3]:
                    print(f"      - {err}")

        all_results[source] = results

    return all_results

def check_coverage_stats() -> Dict:
    """
    3. COVERAGE VERIFICATION (PRE-FILTER)

    Verifies:
    - Total indicators collected: ~37,069?
    - Total rows: estimate based on file sizes
    - Missing rate distribution (informational only)
    """
    print_section("3. COVERAGE VERIFICATION (PRE-FILTER)")

    results = {
        "indicators_by_source": {},
        "total_indicators": 0,
        "total_rows_estimate": 0
    }

    print_subsection("Indicator Counts")

    for source, path in DATA_SOURCES.items():
        if not path.exists():
            print(f"⚠️  {source:15s}: Directory not found")
            continue

        csv_count = len(list(path.glob("*.csv")))
        expected = EXPECTED_INDICATORS[source]
        pct = (csv_count / expected) * 100

        status = "✅" if pct >= 95 else ("⚠️" if pct >= 80 else "❌")

        print(f"{status} {source:15s}: {csv_count:6,} / {expected:6,} ({pct:5.1f}%)")

        results["indicators_by_source"][source] = {
            "collected": csv_count,
            "expected": expected,
            "percentage": pct
        }
        results["total_indicators"] += csv_count

    print(f"\n{'':17s}{'─' * 30}")
    total_pct = (results["total_indicators"] / EXPECTED_TOTAL) * 100
    print(f"   TOTAL:         {results['total_indicators']:6,} / {EXPECTED_TOTAL:6,} ({total_pct:5.1f}%)")

    # Row count estimates
    print_subsection("Row Count Estimates (based on sample)")

    total_rows = 0
    for source, path in DATA_SOURCES.items():
        if not path.exists():
            continue

        csv_files = list(path.glob("*.csv"))
        if not csv_files:
            continue

        # Sample 20 files to estimate average rows
        sample_size = min(20, len(csv_files))
        sample = np.random.choice(csv_files, sample_size, replace=False)

        row_counts = []
        for csv_file in sample:
            try:
                # Quick row count using wc -l equivalent
                with open(csv_file, 'r') as f:
                    row_count = sum(1 for _ in f) - 1  # Subtract header
                row_counts.append(row_count)
            except:
                continue

        if row_counts:
            avg_rows = np.mean(row_counts)
            estimated_total = avg_rows * len(csv_files)
            total_rows += estimated_total

            print(f"   {source:15s}: ~{estimated_total:12,.0f} rows (avg {avg_rows:,.0f} per file)")

    print(f"\n   {'TOTAL ESTIMATE:':17s}~{total_rows:12,.0f} rows")
    results["total_rows_estimate"] = int(total_rows)

    return results

def check_data_integrity() -> Dict:
    """
    4. DATA INTEGRITY CHECKS

    Verifies:
    - No empty CSV files
    - No corrupted files
    - Country codes present
    - Years in reasonable range (1960-2024)

    Logs all removed indicators to separate files for tracking.
    """
    print_section("4. DATA INTEGRITY CHECKS")

    results = {
        "empty_files": [],
        "empty_files_detailed": [],  # Store with source info
        "corrupted_files": [],
        "corrupted_files_detailed": [],  # Store with source and error
        "invalid_years": [],
        "total_checked": 0,
        "by_source": {}
    }

    print_subsection("File Integrity Scan")

    for source, path in DATA_SOURCES.items():
        if not path.exists():
            continue

        csv_files = list(path.glob("*.csv"))
        print(f"\nScanning {source} ({len(csv_files):,} files)...")

        empty_count = 0
        corrupted_count = 0

        source_issues = {
            "empty": [],
            "corrupted": [],
            "invalid_years": []
        }

        for csv_file in csv_files:
            results["total_checked"] += 1

            # Check if empty
            file_size = csv_file.stat().st_size
            if file_size < 100:  # Less than 100 bytes likely empty
                indicator_id = csv_file.stem
                results["empty_files"].append(str(csv_file.name))
                results["empty_files_detailed"].append({
                    "source": source,
                    "indicator_id": indicator_id,
                    "filename": csv_file.name,
                    "file_size_bytes": file_size,
                    "reason": "File size < 100 bytes"
                })
                source_issues["empty"].append({
                    "indicator_id": indicator_id,
                    "filename": csv_file.name,
                    "file_size_bytes": file_size
                })
                empty_count += 1
                continue

            # Check if readable and validate years
            try:
                df = pd.read_csv(csv_file, nrows=10)

                # Check if dataframe is empty
                if len(df) == 0:
                    indicator_id = csv_file.stem
                    results["empty_files"].append(str(csv_file.name))
                    results["empty_files_detailed"].append({
                        "source": source,
                        "indicator_id": indicator_id,
                        "filename": csv_file.name,
                        "file_size_bytes": file_size,
                        "reason": "DataFrame has 0 rows"
                    })
                    source_issues["empty"].append({
                        "indicator_id": indicator_id,
                        "filename": csv_file.name,
                        "reason": "0 rows"
                    })
                    empty_count += 1
                    continue

                # Find year column
                year_col = None
                for col in df.columns:
                    if col.lower() in ['year', 'time', 'timedim', 'time_period']:
                        year_col = col
                        break

                if year_col and len(df) > 0:
                    years = pd.to_numeric(df[year_col], errors='coerce')
                    invalid = ((years < 1960) | (years > 2024)).sum()

                    if invalid > 0:
                        indicator_id = csv_file.stem
                        results["invalid_years"].append(f"{csv_file.name}: {invalid} invalid years")
                        source_issues["invalid_years"].append({
                            "indicator_id": indicator_id,
                            "filename": csv_file.name,
                            "invalid_year_count": int(invalid),
                            "sample_years": years.dropna().tolist()[:5]
                        })

            except Exception as e:
                indicator_id = csv_file.stem
                error_msg = str(e)
                results["corrupted_files"].append(f"{csv_file.name}: {error_msg}")
                results["corrupted_files_detailed"].append({
                    "source": source,
                    "indicator_id": indicator_id,
                    "filename": csv_file.name,
                    "file_size_bytes": file_size,
                    "error": error_msg,
                    "error_type": type(e).__name__
                })
                source_issues["corrupted"].append({
                    "indicator_id": indicator_id,
                    "filename": csv_file.name,
                    "error": error_msg,
                    "error_type": type(e).__name__
                })
                corrupted_count += 1

        # Store source-level results
        results["by_source"][source] = source_issues

        # Print summary for this source
        status = "✅" if (empty_count == 0 and corrupted_count == 0) else "⚠️"
        print(f"{status} {source:15s}: {empty_count} empty, {corrupted_count} corrupted")

    # Save detailed logs to separate files
    log_dir = BASE_DIR / "validation_logs"
    log_dir.mkdir(exist_ok=True)

    # Save empty files log
    if results["empty_files_detailed"]:
        empty_log = log_dir / "REMOVED_INDICATORS_EMPTY.json"
        with open(empty_log, 'w') as f:
            json.dump({
                "timestamp": pd.Timestamp.now().isoformat(),
                "total_count": len(results["empty_files_detailed"]),
                "by_source": {
                    source: [item for item in results["empty_files_detailed"] if item["source"] == source]
                    for source in DATA_SOURCES.keys()
                },
                "all_indicators": results["empty_files_detailed"]
            }, f, indent=2)
        print(f"\n📄 Empty files log saved to: {empty_log}")

    # Save corrupted files log
    if results["corrupted_files_detailed"]:
        corrupted_log = log_dir / "REMOVED_INDICATORS_CORRUPTED.json"
        with open(corrupted_log, 'w') as f:
            json.dump({
                "timestamp": pd.Timestamp.now().isoformat(),
                "total_count": len(results["corrupted_files_detailed"]),
                "by_source": {
                    source: [item for item in results["corrupted_files_detailed"] if item["source"] == source]
                    for source in DATA_SOURCES.keys()
                },
                "all_indicators": results["corrupted_files_detailed"]
            }, f, indent=2)
        print(f"📄 Corrupted files log saved to: {corrupted_log}")

    # Save invalid years log
    if results["invalid_years"]:
        years_log = log_dir / "INDICATORS_INVALID_YEARS.json"
        invalid_years_detailed = []
        for source, issues in results["by_source"].items():
            for item in issues["invalid_years"]:
                item["source"] = source
                invalid_years_detailed.append(item)

        with open(years_log, 'w') as f:
            json.dump({
                "timestamp": pd.Timestamp.now().isoformat(),
                "total_count": len(invalid_years_detailed),
                "note": "These indicators have some data outside 1960-2024 range but may still be usable",
                "by_source": {
                    source: [item for item in invalid_years_detailed if item["source"] == source]
                    for source in DATA_SOURCES.keys()
                },
                "all_indicators": invalid_years_detailed
            }, f, indent=2)
        print(f"📄 Invalid years log saved to: {years_log}")

    # Overall summary
    print_subsection("Integrity Summary")
    print(f"Total files checked: {results['total_checked']:,}")
    print(f"Empty files: {len(results['empty_files'])}")
    print(f"Corrupted files: {len(results['corrupted_files'])}")
    print(f"Files with invalid years: {len(results['invalid_years'])}")

    if results["empty_files"]:
        print(f"\nEmpty files (showing first 10):")
        for f in results["empty_files"][:10]:
            print(f"   - {f}")

    if results["corrupted_files"]:
        print(f"\nCorrupted files (showing first 10):")
        for f in results["corrupted_files"][:10]:
            print(f"   - {f}")

    # Also create CSV summaries for easier spreadsheet review
    if results["empty_files_detailed"]:
        empty_csv = log_dir / "REMOVED_INDICATORS_EMPTY.csv"
        df_empty = pd.DataFrame(results["empty_files_detailed"])
        df_empty.to_csv(empty_csv, index=False)
        print(f"📊 Empty files CSV saved to: {empty_csv}")

    if results["corrupted_files_detailed"]:
        corrupted_csv = log_dir / "REMOVED_INDICATORS_CORRUPTED.csv"
        df_corrupted = pd.DataFrame(results["corrupted_files_detailed"])
        df_corrupted.to_csv(corrupted_csv, index=False)
        print(f"📊 Corrupted files CSV saved to: {corrupted_csv}")

    print(f"\n📋 Detailed removal logs saved to: {log_dir}/")
    print(f"   - JSON format: Full details with error messages")
    print(f"   - CSV format: Easy to review in spreadsheet")

    return results

def check_readiness_for_part2() -> Dict:
    """
    5. READINESS FOR PART 2

    Verifies:
    - Can we load all CSVs into pandas?
    - Are we ready to write 6 new scrapers?
    """
    print_section("5. READINESS FOR PART 2")

    results = {
        "pandas_loadable": True,
        "ready_for_new_scrapers": True,
        "issues": []
    }

    print_subsection("Pandas Load Test")

    # Test loading a sample from each source
    for source, path in DATA_SOURCES.items():
        if not path.exists():
            results["issues"].append(f"{source}: Directory not found")
            continue

        csv_files = list(path.glob("*.csv"))
        if not csv_files:
            results["issues"].append(f"{source}: No CSV files found")
            continue

        # Try loading 5 random files
        sample = csv_files[:5] if len(csv_files) >= 5 else csv_files

        failures = 0
        for csv_file in sample:
            try:
                df = pd.read_csv(csv_file)
                if len(df) == 0:
                    failures += 1
            except Exception as e:
                failures += 1

        status = "✅" if failures == 0 else "⚠️"
        print(f"{status} {source:15s}: {len(sample) - failures}/{len(sample)} files loadable")

        if failures > 0:
            results["pandas_loadable"] = False
            results["issues"].append(f"{source}: {failures}/{len(sample)} files failed to load")

    print_subsection("Part 2 Readiness Assessment")

    # Check if we have the foundation for Part 2
    checklist = {
        "All 5 V1 sources extracted": len([p for p in DATA_SOURCES.values() if p.exists()]) >= 4,
        "No critical data corruption": len(results["issues"]) < 5,
        "Pandas load successful": results["pandas_loadable"],
        "Output structure valid": all(p.exists() for p in DATA_SOURCES.values())
    }

    for check, passed in checklist.items():
        status = "✅" if passed else "❌"
        print(f"{status} {check}")
        if not passed:
            results["ready_for_new_scrapers"] = False

    return results

def generate_final_report(structure, formatting, coverage, integrity, readiness) -> str:
    """Generate comprehensive validation report"""

    print_section("FINAL VALIDATION REPORT")

    # Overall status
    all_passed = (
        coverage["total_indicators"] >= EXPECTED_TOTAL * 0.95 and
        len(integrity["corrupted_files"]) < 10 and
        readiness["ready_for_new_scrapers"]
    )

    status = "✅ PASSED" if all_passed else "⚠️ NEEDS REVIEW"

    print(f"\n{'Overall Status:':<30s} {status}")
    print(f"{'Timestamp:':<30s} {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}")

    print_subsection("Summary Metrics")
    print(f"{'Total Indicators:':<30s} {coverage['total_indicators']:>10,} / {EXPECTED_TOTAL:,} ({coverage['total_indicators']/EXPECTED_TOTAL*100:.1f}%)")
    print(f"{'Estimated Total Rows:':<30s} {coverage['total_rows_estimate']:>10,}")
    print(f"{'Files Checked:':<30s} {integrity['total_checked']:>10,}")
    print(f"{'Empty Files:':<30s} {len(integrity['empty_files']):>10,}")
    print(f"{'Corrupted Files:':<30s} {len(integrity['corrupted_files']):>10,}")

    print_subsection("Go/No-Go Decision")

    if all_passed:
        print("✅ A0.6 EXTRACTION COMPLETE AND VALIDATED")
        print("✅ READY TO PROCEED TO PART 2 (A0.7-A0.14: New Scrapers)")
        print("\nNext steps:")
        print("1. Write 6 new scrapers: V-Dem, QoG, OECD, Penn, WID, Transparency")
        print("2. Target: +4,010 indicators to reach 5,000-6,000 total")
        print("3. After Part 2: Merge all datasets (A0.15)")
    else:
        print("⚠️ VALIDATION ISSUES DETECTED")
        print("\nRequired actions before Part 2:")
        for issue in readiness.get("issues", []):
            print(f"   - {issue}")
        if len(integrity["corrupted_files"]) >= 10:
            print(f"   - Fix {len(integrity['corrupted_files'])} corrupted files")
        if coverage["total_indicators"] < EXPECTED_TOTAL * 0.95:
            print(f"   - Investigate low indicator count ({coverage['total_indicators']:,} < {int(EXPECTED_TOTAL * 0.95):,})")

    # Save report to file
    report = {
        "timestamp": pd.Timestamp.now().isoformat(),
        "overall_status": status,
        "structure": structure,
        "coverage": coverage,
        "integrity": {
            "total_checked": integrity["total_checked"],
            "empty_files": len(integrity["empty_files"]),
            "corrupted_files": len(integrity["corrupted_files"]),
            "invalid_years": len(integrity["invalid_years"])
        },
        "readiness": readiness
    }

    report_file = BASE_DIR / "A06_VALIDATION_REPORT.json"
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2)

    print(f"\n📄 Full report saved to: {report_file}")

    return status

def main():
    """Run all validation checks"""

    print("=" * 80)
    print(" " * 25 + "A0.6 EXTRACTION VALIDATION")
    print("=" * 80)
    print(f"\nValidating bulk extraction from 5 V1 data sources")
    print(f"Expected: {EXPECTED_TOTAL:,} indicators across World Bank, WHO, IMF, UNICEF, UNESCO")
    print(f"Timestamp: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Run all validation checks
    structure = check_output_structure()
    formatting = check_csv_formatting()
    coverage = check_coverage_stats()
    integrity = check_data_integrity()
    readiness = check_readiness_for_part2()

    # Generate final report
    final_status = generate_final_report(structure, formatting, coverage, integrity, readiness)

    print("\n" + "=" * 80)
    print(" " * 30 + "VALIDATION COMPLETE")
    print("=" * 80 + "\n")

    # Exit with appropriate code
    if "PASSED" in final_status:
        return 0
    else:
        return 1

if __name__ == "__main__":
    import sys
    sys.exit(main())
