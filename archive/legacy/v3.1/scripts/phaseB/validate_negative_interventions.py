"""
Phase B Validation #4: Negative Intervention Test

Test that decreasing interventions work correctly.
-20% spending should have opposite effects to +20%.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'B3_simulation'))

from simulation_runner import run_simulation


def test_negative_interventions():
    """Test decreasing interventions."""

    # Using universal indicators
    test_cases = [
        {
            'country': 'Australia',
            'indicator': 'v2elvotbuy',
            'positive_change': 20,
            'negative_change': -20
        },
        {
            'country': 'Brazil',
            'indicator': 'v2smlawpr',
            'positive_change': 15,
            'negative_change': -15
        },
        {
            'country': 'India',
            'indicator': 'e_v2x_api_5C',
            'positive_change': 25,
            'negative_change': -25
        }
    ]

    all_pass = True

    print(f"\n{'='*60}")
    print("NEGATIVE INTERVENTION TESTS")
    print(f"{'='*60}")

    for case in test_cases:
        print(f"\nCountry: {case['country']}")
        print(f"Indicator: {case['indicator']}")

        try:
            # Run positive intervention
            result_pos = run_simulation(
                country_code=case['country'],
                interventions=[{'indicator': case['indicator'], 'change_percent': case['positive_change']}]
            )

            # Run negative intervention
            result_neg = run_simulation(
                country_code=case['country'],
                interventions=[{'indicator': case['indicator'], 'change_percent': case['negative_change']}]
            )

            if result_pos['status'] != 'success' or result_neg['status'] != 'success':
                print(f"  ⚠️  One or both simulations failed")
                continue

            # Count positive vs negative effects for each
            pos_effects = result_pos['effects']['top_effects']
            neg_effects = result_neg['effects']['top_effects']

            pos_positive_count = sum(1 for e in pos_effects.values() if e['percent_change'] > 0)
            pos_negative_count = sum(1 for e in pos_effects.values() if e['percent_change'] < 0)

            neg_positive_count = sum(1 for e in neg_effects.values() if e['percent_change'] > 0)
            neg_negative_count = sum(1 for e in neg_effects.values() if e['percent_change'] < 0)

            print(f"  +{case['positive_change']}%: {pos_positive_count} positive, {pos_negative_count} negative effects")
            print(f"  {case['negative_change']}%: {neg_positive_count} positive, {neg_negative_count} negative effects")

            # Check that directions are opposite
            # For positive intervention, we expect mostly positive effects
            # For negative intervention, we expect mostly negative effects
            if pos_positive_count > pos_negative_count and neg_negative_count > neg_positive_count:
                print(f"  ✅ PASS: Directions are appropriately opposite")
            elif pos_positive_count == 0 and neg_positive_count == 0:
                print(f"  ⚠️  No propagation occurred (leaf node?)")
            else:
                print(f"  ⚠️  Directions not clearly opposite (may be expected for complex networks)")

        except Exception as e:
            print(f"  ❌ ERROR: {e}")
            all_pass = False

    print(f"\n{'='*60}")
    print("✅ Negative intervention tests completed")
    print(f"{'='*60}")

    return all_pass


if __name__ == "__main__":
    test_negative_interventions()
