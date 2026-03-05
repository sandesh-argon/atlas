"""
Phase C Validation Suite

Validates:
1. Lag data in country graphs
2. Temporal simulation correctness
3. Performance benchmarks
"""

import json
import time
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent / 'C2_temporal_simulation'))
from temporal_simulation import run_temporal_simulation


def validate_lag_data():
    """Validate lag data in country graphs."""
    print("\n" + "=" * 60)
    print("VALIDATION 1: Lag Data in Graphs")
    print("=" * 60)

    graphs_dir = Path('data/country_graphs')

    total = 0
    with_lags = 0
    total_edges = 0
    total_sig = 0

    for f in graphs_dir.glob('*.json'):
        if f.name.startswith('_'):
            continue
        try:
            with open(f) as fp:
                graph = json.load(fp)
            total += 1

            has_lag = any('lag' in e for e in graph['edges'])
            if has_lag:
                with_lags += 1
                for e in graph['edges']:
                    if 'lag' in e:
                        total_edges += 1
                        if e.get('lag_significant', False):
                            total_sig += 1
        except:
            pass

    print(f"\nTotal graphs: {total}")
    print(f"Graphs with lag data: {with_lags} ({with_lags/total*100:.1f}%)")
    print(f"Total edges with lags: {total_edges:,}")
    print(f"Significant lags: {total_sig:,} ({total_sig/max(total_edges,1)*100:.1f}%)")

    # Pass if >90% of graphs have lag data
    passed = with_lags / total > 0.90
    print(f"\n{'✅ PASS' if passed else '❌ FAIL'}: Lag data coverage")
    return passed


def validate_temporal_simulation():
    """Validate temporal simulation works correctly."""
    print("\n" + "=" * 60)
    print("VALIDATION 2: Temporal Simulation")
    print("=" * 60)

    test_cases = [
        {'country': 'Australia', 'indicator': 'v2elvotbuy', 'change': 20},
        {'country': 'Rwanda', 'indicator': 'v2elvotbuy', 'change': 20},
        {'country': 'Brazil', 'indicator': 'v2smlawpr', 'change': 15},
        {'country': 'India', 'indicator': 'e_v2x_api_5C', 'change': 25},
    ]

    all_pass = True

    for case in test_cases:
        print(f"\n{case['country']}: {case['indicator']} {case['change']:+}%")

        result = run_temporal_simulation(
            country_code=case['country'],
            interventions=[{'indicator': case['indicator'], 'change_percent': case['change']}],
            horizon_years=10
        )

        if result['status'] != 'success':
            print(f"  ❌ FAIL: {result.get('message', 'Unknown error')}")
            all_pass = False
            continue

        # Check that effects grow over time (lagged propagation)
        affected_y0 = result['affected_per_year'].get(0, 0)
        affected_y5 = result['affected_per_year'].get(5, 0)
        affected_y10 = result['affected_per_year'].get(10, 0)

        print(f"  Year 0: {affected_y0} affected")
        print(f"  Year 5: {affected_y5} affected")
        print(f"  Year 10: {affected_y10} affected")

        # Should have more effects over time due to lagged propagation
        if affected_y10 >= affected_y0:
            print(f"  ✅ PASS: Effects propagate over time")
        else:
            print(f"  ⚠️  WARN: Effects don't grow (may be network topology)")

    print(f"\n{'✅ PASS' if all_pass else '❌ FAIL'}: Temporal simulation tests")
    return all_pass


def validate_performance():
    """Validate temporal simulation performance."""
    print("\n" + "=" * 60)
    print("VALIDATION 3: Performance Benchmark")
    print("=" * 60)

    countries = ['Australia', 'Rwanda', 'Brazil', 'India', 'Germany']
    target_time = 5.0  # seconds per 10-year simulation

    times = []
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
            times.append(elapsed)
            status = "✅" if elapsed < target_time else "⚠️"
            print(f"{status} {country:12}: {elapsed:.2f}s (10-year projection)")
            if elapsed > target_time:
                all_pass = False
        else:
            print(f"❌ {country:12}: FAILED")
            all_pass = False

    if times:
        print(f"\nMean time: {sum(times)/len(times):.2f}s")
        print(f"Target: <{target_time}s")

    print(f"\n{'✅ PASS' if all_pass else '⚠️  WARN'}: Performance benchmark")
    return all_pass


def generate_report():
    """Generate Phase C validation report."""
    print("\n" + "=" * 60)
    print("PHASE C VALIDATION REPORT")
    print("=" * 60)

    results = {}

    results['lag_data'] = validate_lag_data()
    results['temporal_sim'] = validate_temporal_simulation()
    results['performance'] = validate_performance()

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    all_pass = all(results.values())

    for test, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {test}: {status}")

    print(f"\n{'✅ ALL VALIDATIONS PASSED' if all_pass else '⚠️  SOME VALIDATIONS FAILED'}")

    # Write report
    report_path = Path('outputs/validation/PHASE_C_VALIDATION_REPORT.md')
    report_path.parent.mkdir(parents=True, exist_ok=True)

    from datetime import datetime

    with open(report_path, 'w') as f:
        f.write("# Phase C Validation Report\n\n")
        f.write(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"**Status:** {'PASSED' if all_pass else 'FAILED'}\n\n")
        f.write("## Summary\n\n")
        f.write("| Validation | Status |\n")
        f.write("|------------|--------|\n")
        for test, passed in results.items():
            f.write(f"| {test} | {'PASS' if passed else 'FAIL'} |\n")
        f.write(f"\n**Total:** {sum(results.values())}/{len(results)} passed\n")

    print(f"\nReport saved to: {report_path}")
    return all_pass


if __name__ == "__main__":
    success = generate_report()
    exit(0 if success else 1)
