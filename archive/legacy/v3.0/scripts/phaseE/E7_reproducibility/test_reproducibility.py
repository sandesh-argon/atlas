#!/usr/bin/env python
"""
Phase E.7: Reproducibility Check

Verifies that simulations produce identical results when run multiple times.
Critical for API reliability.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / 'scripts' / 'phaseC' / 'C2_temporal_simulation'))

DATA_DIR = PROJECT_ROOT / "data"
GRAPHS_DIR = DATA_DIR / "country_graphs"
PANEL_PATH = DATA_DIR / "raw" / "v21_panel_data_for_v3.parquet"


def test_reproducibility():
    """Run same simulation 5 times, verify identical results."""

    from temporal_simulation import run_temporal_simulation

    print("=" * 60)
    print("Phase E.7: Reproducibility Check")
    print("=" * 60)

    # Fixed intervention
    country = 'Australia'
    intervention = {'indicator': 'v2elvotbuy', 'change_percent': 20}

    print(f"\nRunning simulation 5 times:")
    print(f"  Country: {country}")
    print(f"  Intervention: {intervention}")
    print()

    results = []

    for i in range(5):
        result = run_temporal_simulation(
            country_code=country,
            interventions=[intervention],
            horizon_years=5,
            graphs_dir=str(GRAPHS_DIR),
            panel_path=str(PANEL_PATH)
        )
        results.append(result)

        n_effects = len(result.get('effects', {}).get(5, {}))
        print(f"  Run {i+1}: {n_effects} indicators affected")

    # Compare results
    print("\nComparing results across runs...")

    all_identical = True

    for i in range(1, 5):
        # Check same indicators affected at year 5
        effects_0 = results[0].get('effects', {}).get(5, {})
        effects_i = results[i].get('effects', {}).get(5, {})

        indicators_0 = set(effects_0.keys())
        indicators_i = set(effects_i.keys())

        if indicators_0 != indicators_i:
            print(f"  ❌ Run {i+1} affected different indicators")
            print(f"     Run 1: {len(indicators_0)} indicators")
            print(f"     Run {i+1}: {len(indicators_i)} indicators")
            all_identical = False
            continue

        # Check same effect sizes
        for indicator in indicators_0:
            effect_0 = effects_0[indicator].get('percent_change', 0)
            effect_i = effects_i[indicator].get('percent_change', 0)

            diff = abs(effect_0 - effect_i)
            if diff > 0.0001:  # Tolerance: 0.0001%
                print(f"  ❌ Run {i+1} has different effect for {indicator}")
                print(f"     Run 1: {effect_0:.6f}%")
                print(f"     Run {i+1}: {effect_i:.6f}%")
                print(f"     Difference: {diff:.6f}%")
                all_identical = False
                break

    print()
    print("=" * 60)
    if all_identical:
        print("✅ ALL RUNS PRODUCED IDENTICAL RESULTS")
        print("   Simulation is deterministic")
    else:
        print("❌ REPRODUCIBILITY CHECK FAILED")
        print("   Non-deterministic behavior detected")
    print("=" * 60)

    return all_identical


if __name__ == "__main__":
    success = test_reproducibility()
    sys.exit(0 if success else 1)
