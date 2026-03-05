"""
Phase C Validation: Performance Benchmark

Benchmark temporal simulation performance across:
- Different countries
- Different time horizons
- Multiple interventions

Target: <5 seconds for any simulation
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / 'C2_temporal_simulation'))
from temporal_simulation import run_temporal_simulation


def benchmark_temporal_performance():
    """Test performance across various scenarios."""

    print("\n" + "=" * 60)
    print("VALIDATION: Temporal Performance Benchmark")
    print("=" * 60)
    print("Target: All simulations <5 seconds")

    target_time = 5.0  # seconds

    # Test 1: Different countries
    print("\n--- Test 1: Country Performance (10-year horizon) ---")
    countries = ['Australia', 'Rwanda', 'Brazil', 'India', 'Germany',
                 'Nigeria', 'Japan', 'Mexico', 'Canada', 'Kenya']

    country_times = []
    all_pass = True

    for country in countries:
        start = time.time()

        result = run_temporal_simulation(
            country_code=country,
            interventions=[{'indicator': 'v2elvotbuy', 'change_percent': 20}],
            horizon_years=10
        )

        elapsed = time.time() - start

        if result['status'] == 'success':
            country_times.append(elapsed)
            status = "✅" if elapsed < target_time else "❌"
            if elapsed >= target_time:
                all_pass = False
            print(f"  {status} {country:12}: {elapsed:.2f}s")
        else:
            print(f"  ⚠️  {country:12}: FAILED")

    if country_times:
        print(f"\n  Mean: {sum(country_times)/len(country_times):.2f}s")
        print(f"  Max:  {max(country_times):.2f}s")

    # Test 2: Different time horizons
    print("\n--- Test 2: Time Horizon Performance (Australia) ---")
    horizons = [1, 5, 10, 15, 20]

    horizon_times = []

    for horizon in horizons:
        start = time.time()

        result = run_temporal_simulation(
            country_code='Australia',
            interventions=[{'indicator': 'v2elvotbuy', 'change_percent': 20}],
            horizon_years=horizon
        )

        elapsed = time.time() - start

        if result['status'] == 'success':
            horizon_times.append(elapsed)
            status = "✅" if elapsed < target_time else "❌"
            if elapsed >= target_time:
                all_pass = False
            print(f"  {status} {horizon:2} years: {elapsed:.2f}s")
        else:
            print(f"  ⚠️  {horizon:2} years: FAILED")

    # Test 3: Multiple interventions
    print("\n--- Test 3: Multiple Interventions (10-year horizon) ---")
    intervention_counts = [1, 3, 5, 10]

    base_indicators = ['v2elvotbuy', 'v2smlawpr', 'e_v2xdl_delib_3C',
                       'e_v2x_api_5C', 'v2exbribe_ord', 'CR.3.GPIA',
                       'ETOIP.1.PR.F', 'apolgei992', 'npopulf156', 'npopuli702']

    multi_times = []

    for n_interventions in intervention_counts:
        interventions = [
            {'indicator': ind, 'change_percent': 10}
            for ind in base_indicators[:n_interventions]
        ]

        start = time.time()

        result = run_temporal_simulation(
            country_code='Australia',
            interventions=interventions,
            horizon_years=10
        )

        elapsed = time.time() - start

        if result['status'] == 'success':
            multi_times.append(elapsed)
            status = "✅" if elapsed < target_time else "❌"
            if elapsed >= target_time:
                all_pass = False
            print(f"  {status} {n_interventions:2} interventions: {elapsed:.2f}s")
        else:
            print(f"  ⚠️  {n_interventions:2} interventions: FAILED")

    # Test 4: Stress test (20 years, 10 interventions)
    print("\n--- Test 4: Stress Test (20 years, 10 interventions) ---")

    interventions = [
        {'indicator': ind, 'change_percent': 10}
        for ind in base_indicators
    ]

    start = time.time()

    result = run_temporal_simulation(
        country_code='India',
        interventions=interventions,
        horizon_years=20
    )

    elapsed = time.time() - start

    if result['status'] == 'success':
        status = "✅" if elapsed < target_time else "❌"
        if elapsed >= target_time:
            all_pass = False
        affected = result['affected_per_year'].get(20, 0)
        print(f"  {status} Stress test: {elapsed:.2f}s ({affected} indicators affected at year 20)")
    else:
        print(f"  ⚠️  Stress test: FAILED")

    # Summary
    print(f"\n{'=' * 60}")
    print("SUMMARY")
    print(f"{'=' * 60}")

    all_times = country_times + horizon_times + multi_times
    if all_times:
        print(f"Total simulations: {len(all_times)}")
        print(f"Mean time: {sum(all_times)/len(all_times):.2f}s")
        print(f"Max time: {max(all_times):.2f}s")
        print(f"Target: <{target_time}s")

    if all_pass:
        print(f"\n✅ PASS: All simulations under {target_time}s target")
    else:
        print(f"\n❌ FAIL: Some simulations exceeded {target_time}s target")

    return all_pass


if __name__ == "__main__":
    success = benchmark_temporal_performance()
    exit(0 if success else 1)
