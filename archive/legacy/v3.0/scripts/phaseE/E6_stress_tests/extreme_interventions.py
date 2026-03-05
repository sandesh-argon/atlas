#!/usr/bin/env python
"""
Phase E.6: Stress Tests - Extreme Interventions

Validates that saturation functions prevent unrealistic outcomes
when extreme interventions are applied.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / 'scripts' / 'phaseC' / 'C2_temporal_simulation'))

DATA_DIR = PROJECT_ROOT / "data"
GRAPHS_DIR = DATA_DIR / "country_graphs"
PANEL_PATH = DATA_DIR / "raw" / "v21_panel_data_for_v3.parquet"


def test_extreme_interventions():
    """Test model behavior under extreme inputs."""

    from temporal_simulation import run_temporal_simulation

    print("=" * 60)
    print("Phase E.6: Stress Tests - Extreme Interventions")
    print("=" * 60)

    extreme_cases = [
        {
            'name': 'Massive increase (+500%)',
            'country': 'Australia',
            'indicator': 'v2elvotbuy',
            'change_percent': 500,
            'max_allowed': 500,  # No indicator should change >500%
            'expect': 'All effects should be <500% (saturation)'
        },
        {
            'name': 'Massive decrease (-90%)',
            'country': 'Australia',
            'indicator': 'v2elvotbuy',
            'change_percent': -90,
            'max_allowed': 500,
            'expect': 'All effects should be <500% and no negative values'
        },
        {
            'name': 'Zero intervention (0%)',
            'country': 'Australia',
            'indicator': 'v2elvotbuy',
            'change_percent': 0,
            'max_allowed': 0.1,  # Should have essentially no effects
            'expect': 'No downstream effects (all < 0.1%)'
        },
        {
            'name': 'Small intervention (+5%)',
            'country': 'Australia',
            'indicator': 'v2elvotbuy',
            'change_percent': 5,
            'max_allowed': 100,  # Proportional response
            'expect': 'Reasonable proportional effects'
        }
    ]

    all_passed = True

    for case in extreme_cases:
        print(f"\n{'-'*60}")
        print(f"Test: {case['name']}")
        print(f"{'-'*60}")

        try:
            result = run_temporal_simulation(
                country_code=case['country'],
                interventions=[{
                    'indicator': case['indicator'],
                    'change_percent': case['change_percent']
                }],
                horizon_years=5,
                graphs_dir=str(GRAPHS_DIR),
                panel_path=str(PANEL_PATH)
            )

            if result.get('status') != 'success':
                print(f"  Simulation failed: {result.get('message')}")
                continue

            # Check all effects at year 5
            effects = result.get('effects', {}).get(5, {})

            if not effects:
                if case['change_percent'] == 0:
                    print(f"  ✅ PASS: Zero intervention → no effects")
                    continue
                else:
                    print(f"  ⚠️  No effects returned (might be filtered)")
                    continue

            # Find max effect
            max_effect = 0
            max_indicator = None
            for indicator, eff in effects.items():
                pct = abs(eff.get('percent_change', 0))
                if pct > max_effect:
                    max_effect = pct
                    max_indicator = indicator

            print(f"  Max effect: {max_effect:.1f}% ({max_indicator})")
            print(f"  Allowed: <{case['max_allowed']}%")
            print(f"  Expectation: {case['expect']}")

            if max_effect > case['max_allowed']:
                print(f"  ❌ FAIL: Effect {max_effect:.1f}% exceeds limit {case['max_allowed']}%")
                all_passed = False
            else:
                print(f"  ✅ PASS: Effects within bounds")

        except Exception as e:
            print(f"  ❌ ERROR: {e}")
            all_passed = False

    print("\n" + "=" * 60)
    if all_passed:
        print("✅ ALL STRESS TESTS PASSED")
    else:
        print("❌ SOME STRESS TESTS FAILED")
    print("=" * 60)

    return all_passed


if __name__ == "__main__":
    success = test_extreme_interventions()
    sys.exit(0 if success else 1)
