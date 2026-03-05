"""
Phase B Validation #2: Cross-Country Consistency Check

Test if similar countries respond similarly to same intervention.
"""

import sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).parent / 'B3_simulation'))

from simulation_runner import run_simulation


def test_cross_country_consistency():
    """Test regional consistency."""

    # Define country groups
    country_groups = {
        'East Africa': ['Rwanda', 'Uganda', 'Kenya', 'Tanzania'],
        'High-income': ['Australia', 'Canada', 'Norway', 'Sweden'],
        'Latin America': ['Brazil', 'Argentina', 'Chile', 'Colombia'],
        'South Asia': ['India', 'Bangladesh', 'Pakistan', 'Sri Lanka']
    }

    # Standard intervention (using universal indicator)
    intervention = {'indicator': 'v2elvotbuy', 'change_percent': 20}

    all_pass = True

    for region, countries in country_groups.items():
        print(f"\n{'='*60}")
        print(f"Region: {region}")
        print(f"Intervention: {intervention['indicator']} +{intervention['change_percent']}%")
        print(f"{'='*60}")

        results = []

        for country in countries:
            try:
                result = run_simulation(
                    country_code=country,
                    interventions=[intervention]
                )

                if result['status'] != 'success':
                    print(f"  {country}: SKIPPED - {result.get('message', 'no data')}")
                    continue

                n_affected = result['effects']['total_affected']
                max_change = 0
                for ind, effect in result['effects']['top_effects'].items():
                    max_change = max(max_change, abs(effect['percent_change']))

                results.append({
                    'country': country,
                    'n_affected': n_affected,
                    'max_change': max_change
                })

                print(f"  {country}: {n_affected} affected, max change {max_change:.1f}%")

            except Exception as e:
                print(f"  {country}: ERROR - {e}")

        # Check variance within region
        if len(results) >= 2:
            n_affected_values = [r['n_affected'] for r in results]
            max_change_values = [r['max_change'] for r in results]

            # Coefficient of variation for n_affected
            if np.mean(n_affected_values) > 0:
                cv_affected = np.std(n_affected_values) / np.mean(n_affected_values)
            else:
                cv_affected = 0

            print(f"\n  Regional Stats:")
            print(f"    Mean affected: {np.mean(n_affected_values):.1f}")
            print(f"    Std affected: {np.std(n_affected_values):.1f}")
            print(f"    CV: {cv_affected:.2f}")

            if cv_affected > 2.0:
                print(f"  ⚠️  High variance (CV > 2.0)")
            else:
                print(f"  ✅ Consistent responses (CV <= 2.0)")
        else:
            print(f"\n  Insufficient data for region ({len(results)} countries)")

    return all_pass


if __name__ == "__main__":
    test_cross_country_consistency()
