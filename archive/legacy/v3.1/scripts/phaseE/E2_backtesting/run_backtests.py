#!/usr/bin/env python
"""
Phase E.2: Run Historical Backtests

Executes backtests on all identified validation cases.
"""

import json
import sys
from pathlib import Path
from typing import Dict, List
from dataclasses import asdict
import time

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / 'scripts' / 'phaseE' / 'E2_backtesting'))

from backtest_framework import BacktestFramework, BacktestResult, calculate_aggregate_metrics

OUTPUT_DIR = PROJECT_ROOT / "outputs" / "phaseE"
CASES_FILE = OUTPUT_DIR / "validation_cases_v2.json"


def load_validation_cases() -> List[Dict]:
    """Load identified validation cases."""
    if not CASES_FILE.exists():
        print(f"Error: {CASES_FILE} not found. Run E1_case_selection first.")
        sys.exit(1)

    with open(CASES_FILE) as f:
        return json.load(f)


def run_all_backtests(
    cases: List[Dict],
    validation_lag: int = 3,
    max_cases: int = 30
) -> List[BacktestResult]:
    """Run backtests on all cases."""
    framework = BacktestFramework()
    results = []

    total_cases = min(len(cases), max_cases)
    completed = 0

    print(f"\nRunning {total_cases} backtests (lag={validation_lag} years)...")
    print("-" * 60)

    for case in cases[:max_cases]:
        completed += 1
        country = case['country']
        indicator = case['indicator']
        year = case['year']
        change = case['percent_change']

        print(f"  {completed}/{total_cases}: {country} {indicator} ({year})", end="")
        sys.stdout.flush()

        start = time.time()
        result = framework.run_backtest(
            country=country,
            indicator=indicator,
            intervention_year=year,
            observed_change_percent=change,
            validation_lag=validation_lag
        )
        elapsed = time.time() - start

        if result.success:
            print(f" -> r²={result.r_squared:.3f}, n={result.n_indicators_compared} ({elapsed:.1f}s)")
        else:
            print(f" -> FAILED: {result.error_message} ({elapsed:.1f}s)")

        results.append(result)

    return results


def print_summary(results: List[BacktestResult], metrics: Dict):
    """Print summary of backtest results."""
    print("\n" + "=" * 60)
    print("BACKTEST RESULTS SUMMARY")
    print("=" * 60)

    print(f"\nTotal backtests: {metrics['n_total']}")
    print(f"Successful: {metrics['n_successful']}")
    print(f"Failed: {metrics['n_total'] - metrics['n_successful']}")

    print(f"\n--- Accuracy Metrics ---")
    print(f"Mean r²:     {metrics['mean_r_squared']:.4f}")
    print(f"Median r²:   {metrics['median_r_squared']:.4f}")
    print(f"Std r²:      {metrics['std_r_squared']:.4f}")
    print(f"Mean r:      {metrics['mean_pearson_r']:.4f}")
    print(f"Mean MAE:    {metrics['mean_mae']:.4f}")
    print(f"Mean RMSE:   {metrics['mean_rmse']:.4f}")

    print(f"\n--- Validation Target ---")
    target = 0.5
    if metrics['mean_r_squared'] >= target:
        print(f"[PASS] Mean r² ({metrics['mean_r_squared']:.4f}) >= {target}")
    else:
        print(f"[FAIL] Mean r² ({metrics['mean_r_squared']:.4f}) < {target}")

    # Per-domain breakdown
    print(f"\n--- Per-Case Results ---")
    successful = [r for r in results if r.success]
    for r in sorted(successful, key=lambda x: x.r_squared, reverse=True)[:10]:
        print(f"  {r.country:20s} {r.indicator:20s} r²={r.r_squared:.3f} (n={r.n_indicators_compared})")


def save_results(results: List[BacktestResult], metrics: Dict):
    """Save results to files."""
    # Save detailed results
    results_data = [asdict(r) for r in results]
    results_file = OUTPUT_DIR / "backtest_results.json"
    with open(results_file, 'w') as f:
        json.dump(results_data, f, indent=2)
    print(f"\nDetailed results saved to: {results_file}")

    # Save metrics
    metrics_file = OUTPUT_DIR / "backtest_metrics.json"
    with open(metrics_file, 'w') as f:
        json.dump(metrics, f, indent=2)
    print(f"Metrics saved to: {metrics_file}")


def main():
    """Main entry point."""
    print("=" * 60)
    print("Phase E.2: Historical Backtesting")
    print("=" * 60)

    # Load cases
    cases = load_validation_cases()
    print(f"Loaded {len(cases)} validation cases")

    # Run backtests
    results = run_all_backtests(cases, validation_lag=3, max_cases=30)

    # Calculate metrics
    metrics = calculate_aggregate_metrics(results)

    # Print and save results
    print_summary(results, metrics)
    save_results(results, metrics)

    return 0 if metrics['validation_passed'] else 1


if __name__ == "__main__":
    sys.exit(main())
