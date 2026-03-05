"""
Phase C Airtight Validation Master Runner

Runs all 6 validation scripts and generates a comprehensive report.
"""

import sys
import subprocess
from pathlib import Path
from datetime import datetime
import io
from contextlib import redirect_stdout

# Project root
PROJECT_ROOT = Path(__file__).parent.parent.parent


def run_all_validations():
    """Run all Phase C airtight validations."""

    print("=" * 70)
    print("PHASE C AIRTIGHT VALIDATION SUITE")
    print("=" * 70)
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    results = {}
    outputs = {}

    # Import and run each validation
    validation_modules = [
        ('Lag Reasonableness', 'validate_lag_reasonableness'),
        ('Temporal Consistency', 'validate_temporal_consistency'),
        ('Cross-Country Lag Consistency', 'validate_lag_consistency'),
        ('Zero-Lag Edges', 'validate_zero_lag_edges'),
        ('Temporal Edge Cases', 'validate_temporal_edge_cases'),
        ('Performance Benchmark', 'benchmark_temporal_performance'),
    ]

    for name, module_name in validation_modules:
        print(f"\n\n{'#' * 70}")
        print(f"# {name}")
        print(f"{'#' * 70}")

        try:
            # Import module
            if module_name == 'validate_lag_reasonableness':
                from validate_lag_reasonableness import validate_lag_reasonableness
                result = validate_lag_reasonableness()
            elif module_name == 'validate_temporal_consistency':
                from validate_temporal_consistency import validate_temporal_smoothness
                result = validate_temporal_smoothness()
            elif module_name == 'validate_lag_consistency':
                from validate_lag_consistency import validate_cross_country_lag_consistency
                result = validate_cross_country_lag_consistency()
            elif module_name == 'validate_zero_lag_edges':
                from validate_zero_lag_edges import validate_zero_lag_edges
                result = validate_zero_lag_edges()
            elif module_name == 'validate_temporal_edge_cases':
                from validate_temporal_edge_cases import test_temporal_edge_cases
                result = test_temporal_edge_cases()
            elif module_name == 'benchmark_temporal_performance':
                from benchmark_temporal_performance import benchmark_temporal_performance
                result = benchmark_temporal_performance()
            else:
                result = False

            results[name] = result

        except Exception as e:
            print(f"\n❌ ERROR: {e}")
            results[name] = False

    # Summary
    print("\n\n" + "=" * 70)
    print("FINAL SUMMARY")
    print("=" * 70)

    all_pass = True
    for name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {name}: {status}")
        if not passed:
            all_pass = False

    print(f"\nTotal: {sum(results.values())}/{len(results)} passed")

    if all_pass:
        print("\n" + "=" * 70)
        print("✅ ALL VALIDATIONS PASSED - Ready for Phase D")
        print("=" * 70)
    else:
        print("\n" + "=" * 70)
        print("⚠️  SOME VALIDATIONS HAVE WARNINGS - Review before Phase D")
        print("=" * 70)

    # Generate report
    report_path = PROJECT_ROOT / 'outputs' / 'validation' / 'PHASE_C_AIRTIGHT_VALIDATION.md'
    report_path.parent.mkdir(parents=True, exist_ok=True)

    with open(report_path, 'w') as f:
        f.write("# Phase C Airtight Validation Report\n\n")
        f.write(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"**Status:** {'PASSED' if all_pass else 'WARNINGS'}\n\n")
        f.write("## Summary\n\n")
        f.write("| Validation | Status |\n")
        f.write("|------------|--------|\n")
        for name, passed in results.items():
            f.write(f"| {name} | {'PASS' if passed else 'WARN'} |\n")
        f.write(f"\n**Total:** {sum(results.values())}/{len(results)} passed\n\n")
        f.write("## Notes\n\n")
        f.write("- Lag reasonableness checks domain knowledge patterns\n")
        f.write("- Temporal consistency checks for spikes/crashes\n")
        f.write("- Cross-country checks regional consistency\n")
        f.write("- Performance target: <5s per simulation\n")

    print(f"\nReport saved to: {report_path}")

    return all_pass


if __name__ == "__main__":
    success = run_all_validations()
    exit(0 if success else 1)
