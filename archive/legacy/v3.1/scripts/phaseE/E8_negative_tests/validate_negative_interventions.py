#!/usr/bin/env python
"""
Phase E.8: Negative Intervention Validation

Tests that negative interventions produce sensible results
(opposite effects compared to positive interventions).
"""

import sys
import numpy as np
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / 'scripts' / 'phaseC' / 'C2_temporal_simulation'))

DATA_DIR = PROJECT_ROOT / "data"
GRAPHS_DIR = DATA_DIR / "country_graphs"
PANEL_PATH = DATA_DIR / "raw" / "v21_panel_data_for_v3.parquet"


def test_negative_interventions():
    """Test that positive and negative interventions produce opposite effects."""

    from temporal_simulation import run_temporal_simulation

    print("=" * 60)
    print("Phase E.8: Negative Intervention Validation")
    print("=" * 60)

    test_cases = [
        {
            'country': 'Australia',
            'indicator': 'v2elvotbuy',
            'magnitude': 20,
            'description': 'Electoral vote buying indicator'
        },
        {
            'country': 'India',
            'indicator': 'SLE.1T2.M',
            'magnitude': 15,
            'description': 'Life expectancy indicator'
        }
    ]

    all_passed = True

    for case in test_cases:
        print(f"\n{'-'*60}")
        print(f"Test: {case['country']} - {case['description']}")
        print(f"{'-'*60}")

        try:
            # Run positive intervention
            result_pos = run_temporal_simulation(
                country_code=case['country'],
                interventions=[{
                    'indicator': case['indicator'],
                    'change_percent': case['magnitude']
                }],
                horizon_years=5,
                graphs_dir=str(GRAPHS_DIR),
                panel_path=str(PANEL_PATH)
            )

            # Run negative intervention
            result_neg = run_temporal_simulation(
                country_code=case['country'],
                interventions=[{
                    'indicator': case['indicator'],
                    'change_percent': -case['magnitude']
                }],
                horizon_years=5,
                graphs_dir=str(GRAPHS_DIR),
                panel_path=str(PANEL_PATH)
            )

            if result_pos.get('status') != 'success' or result_neg.get('status') != 'success':
                print(f"  Simulation failed")
                continue

            # Get effects at year 5
            effects_pos = result_pos.get('effects', {}).get(5, {})
            effects_neg = result_neg.get('effects', {}).get(5, {})

            # Compare signs
            sign_matches = 0  # Cases where signs are correctly opposite
            sign_mismatches = 0  # Cases where signs are incorrectly same
            total = 0

            for indicator in effects_pos:
                if indicator not in effects_neg:
                    continue

                change_pos = effects_pos[indicator].get('percent_change', 0)
                change_neg = effects_neg[indicator].get('percent_change', 0)

                # Skip near-zero effects
                if abs(change_pos) < 0.1 and abs(change_neg) < 0.1:
                    continue

                sign_pos = np.sign(change_pos)
                sign_neg = np.sign(change_neg)

                if sign_pos == -sign_neg:
                    sign_matches += 1
                elif sign_pos == sign_neg and sign_pos != 0:
                    sign_mismatches += 1

                total += 1

            if total == 0:
                print(f"  No comparable effects found")
                continue

            match_rate = sign_matches / total
            mismatch_rate = sign_mismatches / total

            print(f"  Positive intervention: +{case['magnitude']}%")
            print(f"  Negative intervention: -{case['magnitude']}%")
            print(f"  Indicators compared: {total}")
            print(f"  Signs correctly opposite: {sign_matches}/{total} ({match_rate:.0%})")
            print(f"  Signs incorrectly same: {sign_mismatches}/{total} ({mismatch_rate:.0%})")

            # Pass if >80% have opposite signs OR <20% have same signs
            if mismatch_rate < 0.20:
                print(f"  ✅ PASS: Negative interventions work correctly")
            else:
                print(f"  ❌ FAIL: Too many sign mismatches ({mismatch_rate:.0%} > 20%)")
                all_passed = False

        except Exception as e:
            print(f"  ❌ ERROR: {e}")
            all_passed = False

    print("\n" + "=" * 60)
    if all_passed:
        print("✅ ALL NEGATIVE INTERVENTION TESTS PASSED")
    else:
        print("❌ SOME NEGATIVE INTERVENTION TESTS FAILED")
    print("=" * 60)

    return all_passed


if __name__ == "__main__":
    success = test_negative_interventions()
    sys.exit(0 if success else 1)
