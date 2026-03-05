#!/usr/bin/env python3
"""
Phase 2B Validation: Temporal Causal Graphs
Validates all 4,663 temporal graph files (35 unified + 4,628 country-specific)
"""

import json
import os
import sys
from pathlib import Path
from collections import defaultdict
from datetime import datetime
import random

# Configuration
BASE_DIR = Path("<repo-root>/v3.1")
GRAPHS_DIR = BASE_DIR / "data" / "v3_1_temporal_graphs"
OUTPUT_DIR = BASE_DIR / "outputs"

# Expected counts
EXPECTED_UNIFIED = 35  # 1990-2024
EXPECTED_COUNTRIES = 4628  # 178 countries × variable years (1999-2024)
EXPECTED_TOTAL = EXPECTED_UNIFIED + EXPECTED_COUNTRIES

# Schema requirements
REQUIRED_ROOT_FIELDS = ["country", "year", "edges", "metadata", "saturation_thresholds", "provenance"]
REQUIRED_EDGE_FIELDS = ["source", "target", "beta", "ci_lower", "ci_upper", "std", "p_value", "lag", "r_squared", "n_samples", "n_bootstrap", "relationship_type"]
REQUIRED_METADATA_FIELDS = ["n_edges_computed", "n_edges_skipped", "n_edges_total", "coverage", "mean_beta", "std_beta", "median_p_value", "significant_edges_p05", "significant_edges_p01", "mean_lag", "lag_distribution", "dag_validated", "dag_cycles", "n_samples", "year_range", "computation_time_sec"]


def validate_file(filepath: Path) -> dict:
    """Validate a single temporal graph file."""
    result = {
        "file": str(filepath),
        "valid": True,
        "errors": [],
        "warnings": [],
        "stats": {}
    }

    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        result["valid"] = False
        result["errors"].append(f"Invalid JSON: {e}")
        return result
    except Exception as e:
        result["valid"] = False
        result["errors"].append(f"Read error: {e}")
        return result

    # Check root fields
    for field in REQUIRED_ROOT_FIELDS:
        if field not in data:
            result["valid"] = False
            result["errors"].append(f"Missing root field: {field}")

    if not result["valid"]:
        return result

    # Validate edges
    edges = data.get("edges", [])
    if len(edges) == 0:
        result["warnings"].append("No edges in file")

    invalid_edges = 0
    ci_violations = 0
    pvalue_violations = 0
    lag_violations = 0

    for i, edge in enumerate(edges):
        # Check required fields
        for field in REQUIRED_EDGE_FIELDS:
            if field not in edge:
                invalid_edges += 1
                break
        else:
            # Validate CI consistency (ci_lower <= beta <= ci_upper)
            # Allow some tolerance for floating point
            if edge["ci_lower"] > edge["beta"] + 0.001 or edge["ci_upper"] < edge["beta"] - 0.001:
                ci_violations += 1

            # Validate p-value range
            if edge["p_value"] < 0 or edge["p_value"] > 1:
                pvalue_violations += 1

            # Validate lag range
            if edge["lag"] < 0 or edge["lag"] > 5:
                lag_violations += 1

    if invalid_edges > 0:
        result["errors"].append(f"{invalid_edges} edges missing required fields")
        result["valid"] = False

    if ci_violations > 0:
        result["warnings"].append(f"{ci_violations} edges with CI violations (ci_lower > beta or ci_upper < beta)")

    if pvalue_violations > 0:
        result["errors"].append(f"{pvalue_violations} edges with invalid p-values")
        result["valid"] = False

    if lag_violations > 0:
        result["errors"].append(f"{lag_violations} edges with invalid lags (outside 0-5)")
        result["valid"] = False

    # Validate metadata
    metadata = data.get("metadata", {})
    for field in REQUIRED_METADATA_FIELDS:
        if field not in metadata:
            # n_countries only required for unified
            if field == "n_countries" and data.get("country") != "unified":
                continue
            result["warnings"].append(f"Missing metadata field: {field}")

    # Check DAG validation
    if not metadata.get("dag_validated", False):
        result["warnings"].append("DAG not validated")

    if metadata.get("dag_cycles", []):
        result["errors"].append(f"DAG has cycles: {metadata['dag_cycles']}")
        result["valid"] = False

    # Collect stats
    result["stats"] = {
        "country": data.get("country"),
        "year": data.get("year"),
        "n_edges": len(edges),
        "n_edges_computed": metadata.get("n_edges_computed", 0),
        "coverage": metadata.get("coverage", 0),
        "significant_p05": metadata.get("significant_edges_p05", 0),
        "mean_beta": metadata.get("mean_beta", 0),
        "mean_lag": metadata.get("mean_lag", 0),
        "n_samples": metadata.get("n_samples", 0)
    }

    return result


def validate_temporal_consistency(unified_files: list, sample_size: int = 10) -> list:
    """Check temporal consistency - no extreme jumps between years."""
    warnings = []

    # Sort by year
    unified_files.sort(key=lambda x: x["stats"]["year"])

    # Sample random edges to track across years
    if len(unified_files) < 2:
        return warnings

    # Load first and last year to compare
    first_path = Path(unified_files[0]["file"])
    last_path = Path(unified_files[-1]["file"])

    try:
        with open(first_path) as f:
            first_data = json.load(f)
        with open(last_path) as f:
            last_data = json.load(f)

        # Create edge lookup
        first_edges = {(e["source"], e["target"]): e["beta"] for e in first_data["edges"]}
        last_edges = {(e["source"], e["target"]): e["beta"] for e in last_data["edges"]}

        # Find common edges and check for extreme changes
        common = set(first_edges.keys()) & set(last_edges.keys())
        extreme_changes = 0
        for edge in common:
            delta = abs(last_edges[edge] - first_edges[edge])
            if delta > 0.8:  # Extreme change threshold
                extreme_changes += 1

        if extreme_changes > len(common) * 0.1:  # More than 10% extreme changes
            warnings.append(f"High temporal instability: {extreme_changes}/{len(common)} edges changed by >0.8")

    except Exception as e:
        warnings.append(f"Could not check temporal consistency: {e}")

    return warnings


def run_validation():
    """Run full validation suite."""
    print("=" * 60)
    print("PHASE 2B VALIDATION: Temporal Causal Graphs")
    print("=" * 60)
    print(f"Started: {datetime.now().isoformat()}")
    print()

    results = {
        "unified": [],
        "countries": defaultdict(list),
        "summary": {
            "total_files": 0,
            "valid_files": 0,
            "invalid_files": 0,
            "total_errors": 0,
            "total_warnings": 0
        }
    }

    # Validate unified files
    print("Validating unified graphs...")
    unified_dir = GRAPHS_DIR / "unified"
    if unified_dir.exists():
        unified_files = list(unified_dir.glob("*.json"))
        print(f"  Found {len(unified_files)} unified files (expected {EXPECTED_UNIFIED})")

        for fpath in sorted(unified_files):
            result = validate_file(fpath)
            results["unified"].append(result)
            results["summary"]["total_files"] += 1
            if result["valid"]:
                results["summary"]["valid_files"] += 1
            else:
                results["summary"]["invalid_files"] += 1
            results["summary"]["total_errors"] += len(result["errors"])
            results["summary"]["total_warnings"] += len(result["warnings"])
    else:
        print("  ERROR: unified directory not found!")
        results["summary"]["total_errors"] += 1

    # Validate country-specific files
    print("\nValidating country-specific graphs...")
    countries_dir = GRAPHS_DIR / "countries"
    if countries_dir.exists():
        country_dirs = [d for d in countries_dir.iterdir() if d.is_dir()]
        print(f"  Found {len(country_dirs)} countries")

        total_country_files = 0
        for country_dir in sorted(country_dirs):
            country_files = list(country_dir.glob("*.json"))
            total_country_files += len(country_files)

            for fpath in sorted(country_files):
                result = validate_file(fpath)
                results["countries"][country_dir.name].append(result)
                results["summary"]["total_files"] += 1
                if result["valid"]:
                    results["summary"]["valid_files"] += 1
                else:
                    results["summary"]["invalid_files"] += 1
                results["summary"]["total_errors"] += len(result["errors"])
                results["summary"]["total_warnings"] += len(result["warnings"])

        print(f"  Found {total_country_files} country files (expected ~{EXPECTED_COUNTRIES})")
    else:
        print("  ERROR: countries directory not found!")
        results["summary"]["total_errors"] += 1

    # Temporal consistency check
    print("\nChecking temporal consistency...")
    temporal_warnings = validate_temporal_consistency(results["unified"])
    for w in temporal_warnings:
        print(f"  WARNING: {w}")
        results["summary"]["total_warnings"] += 1

    # Print summary
    print("\n" + "=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)
    print(f"Total files:    {results['summary']['total_files']}")
    print(f"Valid files:    {results['summary']['valid_files']}")
    print(f"Invalid files:  {results['summary']['invalid_files']}")
    print(f"Total errors:   {results['summary']['total_errors']}")
    print(f"Total warnings: {results['summary']['total_warnings']}")
    print()

    # File count check
    expected_total = EXPECTED_UNIFIED + EXPECTED_COUNTRIES
    actual_total = results["summary"]["total_files"]
    if actual_total == expected_total:
        print(f"✅ File count matches: {actual_total}")
    elif actual_total >= expected_total * 0.95:
        print(f"⚠️  File count close: {actual_total} (expected {expected_total})")
    else:
        print(f"❌ File count mismatch: {actual_total} (expected {expected_total})")

    # Overall status
    print()
    if results["summary"]["invalid_files"] == 0 and results["summary"]["total_errors"] == 0:
        print("✅ VALIDATION PASSED")
        status = "PASSED"
    elif results["summary"]["invalid_files"] < results["summary"]["total_files"] * 0.01:
        print("⚠️  VALIDATION PASSED WITH WARNINGS")
        status = "PASSED_WITH_WARNINGS"
    else:
        print("❌ VALIDATION FAILED")
        status = "FAILED"

    # Show sample errors
    if results["summary"]["total_errors"] > 0:
        print("\nSample errors:")
        error_count = 0
        for result in results["unified"]:
            if result["errors"]:
                print(f"  {result['file']}: {result['errors'][:2]}")
                error_count += 1
                if error_count >= 5:
                    break

        for country, country_results in results["countries"].items():
            if error_count >= 5:
                break
            for result in country_results:
                if result["errors"]:
                    print(f"  {result['file']}: {result['errors'][:2]}")
                    error_count += 1
                    if error_count >= 5:
                        break

    # Show sample stats
    print("\nSample file statistics:")
    print("-" * 40)

    # Unified sample
    if results["unified"]:
        sample = results["unified"][len(results["unified"])//2]  # Middle year
        stats = sample["stats"]
        print(f"Unified {stats['year']}:")
        print(f"  Edges: {stats['n_edges']}, Coverage: {stats['coverage']:.1%}")
        print(f"  Significant (p<0.05): {stats['significant_p05']}")
        print(f"  Mean lag: {stats['mean_lag']:.2f} years")

    # Country sample
    sample_countries = ["Japan", "United States", "Germany", "Brazil", "South Africa"]
    for country in sample_countries:
        if country in results["countries"] and results["countries"][country]:
            sample = results["countries"][country][-1]  # Latest year
            stats = sample["stats"]
            print(f"\n{country} {stats['year']}:")
            print(f"  Edges: {stats['n_edges']}, Coverage: {stats['coverage']:.1%}")
            print(f"  Significant (p<0.05): {stats['significant_p05']}")
            break

    # Coverage distribution
    print("\nCoverage distribution (unified):")
    coverages = [r["stats"]["coverage"] for r in results["unified"] if r["stats"]]
    if coverages:
        print(f"  Min: {min(coverages):.1%}, Max: {max(coverages):.1%}, Mean: {sum(coverages)/len(coverages):.1%}")

    # Write detailed report
    report_path = OUTPUT_DIR / "PHASE2B_VALIDATION.md"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    with open(report_path, 'w') as f:
        f.write("# Phase 2B Validation Report\n\n")
        f.write(f"**Generated:** {datetime.now().isoformat()}\n")
        f.write(f"**Status:** {status}\n\n")
        f.write("## Summary\n\n")
        f.write(f"| Metric | Value |\n")
        f.write(f"|--------|-------|\n")
        f.write(f"| Total files | {results['summary']['total_files']} |\n")
        f.write(f"| Valid files | {results['summary']['valid_files']} |\n")
        f.write(f"| Invalid files | {results['summary']['invalid_files']} |\n")
        f.write(f"| Total errors | {results['summary']['total_errors']} |\n")
        f.write(f"| Total warnings | {results['summary']['total_warnings']} |\n\n")

        f.write("## File Counts\n\n")
        f.write(f"| Type | Found | Expected |\n")
        f.write(f"|------|-------|----------|\n")
        f.write(f"| Unified | {len(results['unified'])} | {EXPECTED_UNIFIED} |\n")
        f.write(f"| Country-specific | {sum(len(v) for v in results['countries'].values())} | {EXPECTED_COUNTRIES} |\n")
        f.write(f"| **Total** | {results['summary']['total_files']} | {expected_total} |\n\n")

        f.write("## Unified Graph Coverage by Year\n\n")
        f.write("| Year | Edges | Coverage | Significant (p<0.05) | Samples |\n")
        f.write("|------|-------|----------|---------------------|----------|\n")
        for result in results["unified"]:
            stats = result["stats"]
            if stats:
                f.write(f"| {stats['year']} | {stats['n_edges']} | {stats['coverage']:.1%} | {stats['significant_p05']} | {stats['n_samples']} |\n")

        if results["summary"]["total_errors"] > 0:
            f.write("\n## Errors\n\n")
            for result in results["unified"]:
                if result["errors"]:
                    f.write(f"- `{result['file']}`: {', '.join(result['errors'])}\n")
            for country, country_results in results["countries"].items():
                for result in country_results:
                    if result["errors"]:
                        f.write(f"- `{result['file']}`: {', '.join(result['errors'])}\n")

        if results["summary"]["total_warnings"] > 0:
            f.write("\n## Warnings (sample)\n\n")
            warning_count = 0
            for result in results["unified"]:
                if result["warnings"] and warning_count < 20:
                    f.write(f"- `{result['file']}`: {', '.join(result['warnings'][:2])}\n")
                    warning_count += 1

    print(f"\nDetailed report written to: {report_path}")
    print(f"Completed: {datetime.now().isoformat()}")

    return results["summary"]["invalid_files"] == 0


if __name__ == "__main__":
    success = run_validation()
    sys.exit(0 if success else 1)
