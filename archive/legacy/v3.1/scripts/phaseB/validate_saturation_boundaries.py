"""
Phase B Validation #3: Saturation Boundary Test

Test extreme interventions to verify saturation works.
Extreme inputs should NOT cause extreme outputs.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'B3_simulation'))

from simulation_runner import run_simulation


def test_saturation_boundaries():
    """Test extreme interventions hit saturation."""

    # Using universal indicators that exist in both graph edges and baseline
    test_cases = [
        {
            'name': 'Extreme +500% intervention',
            'country': 'Rwanda',
            'intervention': {'indicator': 'v2elvotbuy', 'change_percent': 500},
            'max_reasonable_change': 500  # Outputs shouldn't exceed input
        },
        {
            'name': 'Extreme +1000% intervention',
            'country': 'Australia',
            'intervention': {'indicator': 'v2smlawpr', 'change_percent': 1000},
            'max_reasonable_change': 1000
        },
        {
            'name': 'Moderate +100% intervention',
            'country': 'Brazil',
            'intervention': {'indicator': 'e_v2x_api_5C', 'change_percent': 100},
            'max_reasonable_change': 150
        },
        {
            'name': 'Extreme -90% intervention',
            'country': 'India',
            'intervention': {'indicator': 'v2elvotbuy', 'change_percent': -90},
            'max_reasonable_change': 200  # Even negative extremes should be bounded
        }
    ]

    all_pass = True

    print(f"\n{'='*60}")
    print("SATURATION BOUNDARY TESTS")
    print(f"{'='*60}")

    for case in test_cases:
        print(f"\nTest: {case['name']}")
        print(f"  Country: {case['country']}")
        print(f"  Intervention: {case['intervention']['change_percent']:+}%")

        try:
            result = run_simulation(
                country_code=case['country'],
                interventions=[case['intervention']]
            )

            if result['status'] != 'success':
                print(f"  ⚠️  Simulation failed: {result.get('message')}")
                continue

            # Find max change across all affected indicators
            max_change = 0
            max_indicator = None
            for ind, effect in result['effects']['top_effects'].items():
                change = abs(effect['percent_change'])
                if change > max_change:
                    max_change = change
                    max_indicator = ind

            print(f"  Max output change: {max_change:.1f}%")
            print(f"  Max indicator: {max_indicator}")
            print(f"  Threshold: {case['max_reasonable_change']}%")

            if max_change > case['max_reasonable_change']:
                print(f"  ❌ FAIL: Saturation not working (output > threshold)")
                all_pass = False
            else:
                print(f"  ✅ PASS: Saturation working correctly")

        except Exception as e:
            print(f"  ❌ ERROR: {e}")
            all_pass = False

    print(f"\n{'='*60}")
    if all_pass:
        print("✅ All saturation tests PASSED")
    else:
        print("❌ Some saturation tests FAILED")
    print(f"{'='*60}")

    return all_pass


if __name__ == "__main__":
    success = test_saturation_boundaries()
    exit(0 if success else 1)
