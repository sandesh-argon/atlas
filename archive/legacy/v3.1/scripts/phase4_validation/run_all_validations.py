#!/usr/bin/env python3
"""
Master validation script - runs all Phase 2B validation checks.
"""

import subprocess
import sys
from pathlib import Path
from datetime import datetime

BASE_DIR = Path("<repo-root>/v3.1")
SCRIPTS_DIR = BASE_DIR / "scripts/phase4_validation"

VALIDATIONS = [
    ("Temporal Smoothness", "validate_temporal_smoothness.py"),
    ("Beta Distribution", "validate_beta_distribution.py"),
    ("Confidence Intervals", "validate_confidence_intervals.py"),
    ("DAG Claims", "validate_dag_claims.py"),
    ("Lag Distribution", "validate_lag_distribution.py"),
    ("P-Values", "validate_p_values.py"),
    ("Coverage Consistency", "validate_coverage_consistency.py"),
]

def run_all():
    print("=" * 60)
    print("V3.1 PHASE 2B COMPREHENSIVE VALIDATION SUITE")
    print("=" * 60)
    print(f"Started: {datetime.now().isoformat()}")
    print()

    results = []

    for name, script in VALIDATIONS:
        script_path = SCRIPTS_DIR / script
        print(f"\n{'─' * 60}")
        print(f"Running: {name}")
        print(f"{'─' * 60}")

        try:
            result = subprocess.run(
                [sys.executable, str(script_path)],
                capture_output=False,
                cwd=str(BASE_DIR)
            )
            results.append((name, result.returncode == 0))
        except Exception as e:
            print(f"Error running {name}: {e}")
            results.append((name, False))

    # Summary
    print("\n" + "=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)
    print()

    passed = 0
    failed = 0

    for name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"  {name:<25} {status}")
        if success:
            passed += 1
        else:
            failed += 1

    print()
    print(f"Total: {passed}/{len(results)} passed")

    if failed == 0:
        print("\n✅ ALL VALIDATIONS PASSED - Phase 2B is production-ready!")
    else:
        print(f"\n⚠️  {failed} validation(s) need attention")

    print(f"\nCompleted: {datetime.now().isoformat()}")

    return failed == 0

if __name__ == "__main__":
    success = run_all()
    sys.exit(0 if success else 1)
