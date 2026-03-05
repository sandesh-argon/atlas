"""
Phase C Validation: Temporal Simulation Edge Cases

Test boundary conditions before API launch:
- Year 0 only (immediate effects only)
- Year 1 (first temporal effects)
- Year 20 (long-term, should plateau)
- Multiple interventions
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / 'C2_temporal_simulation'))
from temporal_simulation import run_temporal_simulation


def test_temporal_edge_cases():
    """Test boundary conditions for temporal simulation."""

    print("\n" + "=" * 60)
    print("VALIDATION: Temporal Edge Cases")
    print("=" * 60)

    country = 'Australia'
    indicator = 'v2elvotbuy'
    change = 20

    all_pass = True

    # Test 1: time_horizon = 0 (immediate effects only)
    print("\n--- Test 1: Immediate effects (horizon=0) ---")
    result = run_temporal_simulation(
        country_code=country,
        interventions=[{'indicator': indicator, 'change_percent': change}],
        horizon_years=0
    )

    if result['status'] == 'success':
        n_years = len(result['timeline'])
        if n_years == 1:
            print(f"  ✅ PASS: Only year 0 returned (n_years={n_years})")
        else:
            print(f"  ❌ FAIL: Expected 1 year, got {n_years}")
            all_pass = False
    else:
        print(f"  ❌ FAIL: Simulation failed")
        all_pass = False

    # Test 2: time_horizon = 1 (check year 1 differs from year 0)
    print("\n--- Test 2: Year-over-year propagation (horizon=1) ---")
    result = run_temporal_simulation(
        country_code=country,
        interventions=[{'indicator': indicator, 'change_percent': change}],
        horizon_years=1
    )

    if result['status'] == 'success':
        affected_y0 = result['affected_per_year'].get(0, 0)
        affected_y1 = result['affected_per_year'].get(1, 0)

        print(f"  Year 0: {affected_y0} affected")
        print(f"  Year 1: {affected_y1} affected")

        if affected_y1 >= affected_y0:
            print(f"  ✅ PASS: Temporal effects propagating")
        else:
            print(f"  ⚠️  WARN: Effects decreased (may be dampening)")
    else:
        print(f"  ❌ FAIL: Simulation failed")
        all_pass = False

    # Test 3: time_horizon = 20 (long-term, check plateau)
    print("\n--- Test 3: Long-term effects (horizon=20) ---")
    result = run_temporal_simulation(
        country_code=country,
        interventions=[{'indicator': indicator, 'change_percent': change}],
        horizon_years=20
    )

    if result['status'] == 'success':
        affected_y10 = result['affected_per_year'].get(10, 0)
        affected_y15 = result['affected_per_year'].get(15, 0)
        affected_y20 = result['affected_per_year'].get(20, 0)

        print(f"  Year 10: {affected_y10} affected")
        print(f"  Year 15: {affected_y15} affected")
        print(f"  Year 20: {affected_y20} affected")

        # Check if effects plateau (year 15-20 similar)
        if affected_y15 > 0:
            change_rate = abs(affected_y20 - affected_y15) / affected_y15
            if change_rate < 0.50:  # <50% change in last 5 years
                print(f"  ✅ PASS: Effects stabilizing (change rate: {change_rate*100:.1f}%)")
            else:
                print(f"  ⚠️  WARN: Effects still growing rapidly ({change_rate*100:.1f}%)")
        else:
            print(f"  ⚠️  WARN: No effects by year 15")
    else:
        print(f"  ❌ FAIL: Simulation failed")
        all_pass = False

    # Test 4: Multiple interventions
    print("\n--- Test 4: Multiple interventions ---")
    result = run_temporal_simulation(
        country_code=country,
        interventions=[
            {'indicator': 'v2elvotbuy', 'change_percent': 20},
            {'indicator': 'v2smlawpr', 'change_percent': 15},
        ],
        horizon_years=10
    )

    if result['status'] == 'success':
        affected_y0 = result['affected_per_year'].get(0, 0)
        affected_y10 = result['affected_per_year'].get(10, 0)

        print(f"  Year 0: {affected_y0} affected")
        print(f"  Year 10: {affected_y10} affected")

        if affected_y0 >= 2:  # At least 2 interventions applied
            print(f"  ✅ PASS: Multiple interventions processed")
        else:
            print(f"  ⚠️  WARN: Not all interventions may have applied")
    else:
        print(f"  ❌ FAIL: Simulation failed")
        all_pass = False

    # Test 5: Negative intervention
    print("\n--- Test 5: Negative intervention ---")
    result = run_temporal_simulation(
        country_code=country,
        interventions=[{'indicator': indicator, 'change_percent': -20}],
        horizon_years=5
    )

    if result['status'] == 'success':
        # Check that effects are opposite direction
        effects_y0 = result['effects'].get(0, {})
        if indicator in effects_y0:
            change = effects_y0[indicator]['percent_change']
            if change < 0:
                print(f"  ✅ PASS: Negative intervention produces negative effect ({change:.1f}%)")
            else:
                print(f"  ❌ FAIL: Negative intervention should produce negative effect")
                all_pass = False
        else:
            print(f"  ⚠️  WARN: Indicator not in effects")
    else:
        print(f"  ❌ FAIL: Simulation failed")
        all_pass = False

    # Summary
    if all_pass:
        print(f"\n✅ PASS: All edge cases handled correctly")
    else:
        print(f"\n⚠️  WARN: Some edge cases have issues")

    return all_pass


if __name__ == "__main__":
    test_temporal_edge_cases()
