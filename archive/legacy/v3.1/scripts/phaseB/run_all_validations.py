"""
Phase B Master Validation Runner

Runs all 6 validation scripts and generates summary report.
"""

import subprocess
import sys
from pathlib import Path
from datetime import datetime


def run_validation(script_name: str) -> tuple[bool, str]:
    """Run a validation script and capture output."""
    script_path = Path(__file__).parent / script_name

    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout per script
        )
        output = result.stdout + result.stderr
        success = result.returncode == 0
        return success, output
    except subprocess.TimeoutExpired:
        return False, "TIMEOUT: Script took >5 minutes"
    except Exception as e:
        return False, f"ERROR: {e}"


def main():
    """Run all validations and generate report."""

    validations = [
        ('validate_multi_intervention.py', 'Multi-Intervention Stress Test'),
        ('validate_cross_country_consistency.py', 'Cross-Country Consistency'),
        ('validate_saturation_boundaries.py', 'Saturation Boundaries'),
        ('validate_negative_interventions.py', 'Negative Interventions'),
        ('validate_zero_effect.py', 'Zero-Effect (Leaf Nodes)'),
        ('benchmark_performance.py', 'Performance Benchmark')
    ]

    print("=" * 70)
    print("PHASE B AIRTIGHT VALIDATION")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    results = []
    all_outputs = []

    for script, name in validations:
        print(f"\n>>> Running: {name}")
        print("-" * 50)

        success, output = run_validation(script)
        results.append((name, success))
        all_outputs.append((name, output))

        # Print abbreviated output
        lines = output.strip().split('\n')
        if len(lines) > 30:
            for line in lines[:10]:
                print(line)
            print(f"... ({len(lines) - 20} lines omitted) ...")
            for line in lines[-10:]:
                print(line)
        else:
            print(output)

        status = "✅ PASS" if success else "❌ FAIL"
        print(f"\nResult: {status}")

    # Summary
    print("\n" + "=" * 70)
    print("VALIDATION SUMMARY")
    print("=" * 70)

    passed = 0
    failed = 0

    for name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"  {status}  {name}")
        if success:
            passed += 1
        else:
            failed += 1

    print("-" * 70)
    print(f"Total: {passed}/{len(results)} passed")

    if failed == 0:
        print("\n✅ ALL VALIDATIONS PASSED - Ready for Phase C")
    else:
        print(f"\n❌ {failed} VALIDATION(S) FAILED - Fix before Phase C")

    print("=" * 70)

    # Save detailed report
    report_path = Path('outputs/validation/PHASE_B_VALIDATION_REPORT.md')
    report_path.parent.mkdir(parents=True, exist_ok=True)

    with open(report_path, 'w') as f:
        f.write("# Phase B Airtight Validation Report\n\n")
        f.write(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"**Status:** {'PASSED' if failed == 0 else 'FAILED'}\n\n")
        f.write("## Summary\n\n")
        f.write(f"| Validation | Status |\n")
        f.write(f"|------------|--------|\n")
        for name, success in results:
            status = "PASS" if success else "FAIL"
            f.write(f"| {name} | {status} |\n")
        f.write(f"\n**Total:** {passed}/{len(results)} passed\n\n")

        f.write("## Detailed Output\n\n")
        for name, output in all_outputs:
            f.write(f"### {name}\n\n```\n{output}\n```\n\n")

    print(f"\nDetailed report saved to: {report_path}")

    return failed == 0


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
