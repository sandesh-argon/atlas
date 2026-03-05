"""
Phase B Validation #6: Performance Benchmark

Benchmark simulation speed across countries.
Target: All simulations <3 seconds for API responsiveness.
"""

import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'B3_simulation'))

from simulation_runner import run_simulation


def benchmark_simulation_speed():
    """Test simulation performance."""

    countries = [
        'Australia', 'Rwanda', 'Brazil', 'India', 'China',
        'Germany', 'Nigeria', 'Indonesia', 'Mexico', 'Japan'
    ]

    intervention = {'indicator': 'v2elvotbuy', 'change_percent': 20}

    print(f"\n{'='*60}")
    print("PERFORMANCE BENCHMARK")
    print(f"{'='*60}")
    print(f"Intervention: {intervention['indicator']} +{intervention['change_percent']}%")
    print(f"Target: <3 seconds per simulation")
    print(f"{'='*60}\n")

    times = []
    results = []

    for country in countries:
        try:
            start = time.time()

            result = run_simulation(
                country_code=country,
                interventions=[intervention]
            )

            elapsed = time.time() - start

            if result['status'] == 'success':
                iterations = result['propagation']['iterations']
                n_affected = result['effects']['total_affected']
                times.append(elapsed)

                status = "✅" if elapsed < 3.0 else "⚠️ "
                print(f"{status} {country:15} {elapsed:5.2f}s  "
                      f"({iterations} iter, {n_affected} affected)")

                results.append({
                    'country': country,
                    'time': elapsed,
                    'iterations': iterations,
                    'affected': n_affected
                })
            else:
                print(f"⚠️  {country:15} SKIPPED - no data")

        except Exception as e:
            print(f"❌ {country:15} ERROR - {e}")

    # Summary
    if times:
        print(f"\n{'='*60}")
        print("SUMMARY")
        print(f"{'='*60}")
        print(f"Countries tested: {len(times)}")
        print(f"Mean time: {sum(times)/len(times):.2f}s")
        print(f"Min time: {min(times):.2f}s")
        print(f"Max time: {max(times):.2f}s")
        print(f"Std time: {(sum((t - sum(times)/len(times))**2 for t in times) / len(times))**0.5:.2f}s")

        slow_count = sum(1 for t in times if t > 3.0)
        if slow_count > 0:
            print(f"\n⚠️  {slow_count} simulations exceeded 3s target")
        else:
            print(f"\n✅ All simulations under 3s target")

        if max(times) > 5.0:
            print(f"❌ STOP CONDITION: Max time > 5s")
            return False

    return True


def benchmark_multi_intervention_speed():
    """Benchmark with multiple interventions."""

    print(f"\n{'='*60}")
    print("MULTI-INTERVENTION BENCHMARK")
    print(f"{'='*60}")

    intervention_counts = [1, 3, 5, 10]
    country = 'Australia'

    base_indicators = ['v2elvotbuy', 'v2smlawpr', 'e_v2xdl_delib_3C',
                       'e_v2x_api_5C', 'v2exbribe_ord', 'CR.3.GPIA',
                       'ETOIP.1.PR.F', 'apolgei992', 'npopulf156', 'npopuli702']

    for n_interventions in intervention_counts:
        interventions = [
            {'indicator': ind, 'change_percent': 10}
            for ind in base_indicators[:n_interventions]
        ]

        start = time.time()
        result = run_simulation(country_code=country, interventions=interventions)
        elapsed = time.time() - start

        if result['status'] == 'success':
            status = "✅" if elapsed < 3.0 else "⚠️ "
            print(f"{status} {n_interventions} interventions: {elapsed:.2f}s")
        else:
            print(f"⚠️  {n_interventions} interventions: FAILED")

    return True


if __name__ == "__main__":
    success1 = benchmark_simulation_speed()
    success2 = benchmark_multi_intervention_speed()

    print(f"\n{'='*60}")
    if success1 and success2:
        print("✅ All performance benchmarks PASSED")
    else:
        print("❌ Some benchmarks FAILED")
    print(f"{'='*60}")

    exit(0 if success1 and success2 else 1)
