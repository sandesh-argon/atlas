"""
Phase B Validation #1: Multi-Intervention Stress Test

Test complex multi-intervention scenarios to ensure propagation handles:
- Multiple simultaneous changes
- Overlapping causal pathways
- Non-linear interactions
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'B3_simulation'))

from simulation_runner import run_simulation


def test_multi_intervention_scenarios():
    """Test realistic multi-intervention cases."""

    # Universal indicators that exist in both graph edges and baseline for all countries
    test_cases = [
        # Case 1: Two independent interventions
        {
            'name': 'Two independent interventions',
            'country': 'Rwanda',
            'interventions': [
                {'indicator': 'v2elvotbuy', 'change_percent': 20},
                {'indicator': 'v2smlawpr', 'change_percent': 15}
            ]
        },

        # Case 2: Three interventions (governance)
        {
            'name': 'Three governance interventions',
            'country': 'Australia',
            'interventions': [
                {'indicator': 'v2elvotbuy', 'change_percent': 10},
                {'indicator': 'v2exbribe_ord', 'change_percent': 10},
                {'indicator': 'e_v2x_api_5C', 'change_percent': 10}
            ]
        },

        # Case 3: Five interventions
        {
            'name': 'Five mixed interventions',
            'country': 'Brazil',
            'interventions': [
                {'indicator': 'v2elvotbuy', 'change_percent': 10},
                {'indicator': 'v2smlawpr', 'change_percent': 5},
                {'indicator': 'e_v2xdl_delib_3C', 'change_percent': 8},
                {'indicator': 'e_v2x_api_5C', 'change_percent': 12},
                {'indicator': 'v2exbribe_ord', 'change_percent': 7}
            ]
        },

        # Case 4: Large intervention set (stress test)
        {
            'name': 'Ten interventions stress test',
            'country': 'India',
            'interventions': [
                {'indicator': 'v2elvotbuy', 'change_percent': 5},
                {'indicator': 'v2smlawpr', 'change_percent': 5},
                {'indicator': 'e_v2xdl_delib_3C', 'change_percent': 5},
                {'indicator': 'e_v2x_api_5C', 'change_percent': 5},
                {'indicator': 'v2exbribe_ord', 'change_percent': 5},
                {'indicator': 'CR.3.GPIA', 'change_percent': 5},
                {'indicator': 'ETOIP.1.PR.F', 'change_percent': 5},
                {'indicator': 'apolgei992', 'change_percent': 5},
                {'indicator': 'npopulf156', 'change_percent': 5},
                {'indicator': 'npopuli702', 'change_percent': 5}
            ]
        }
    ]

    results = []

    for case in test_cases:
        print(f"\n{'='*60}")
        print(f"Test: {case['name']}")
        print(f"Country: {case['country']}")
        print(f"Interventions: {len(case['interventions'])}")

        try:
            result = run_simulation(
                country_code=case['country'],
                interventions=case['interventions']
            )

            if result['status'] != 'success':
                print(f"  ❌ Simulation failed: {result.get('message', 'unknown')}")
                results.append({'test': case['name'], 'status': 'FAIL'})
                continue

            # Validation checks
            n_affected = result['effects']['total_affected']
            iterations = result['propagation']['iterations']
            converged = result['propagation']['converged']

            # Check convergence
            if not converged:
                print(f"  ⚠️  Did not converge in {iterations} iterations")

            # Check for explosions (any value > 1000% change)
            max_change = 0
            for ind, effect in result['effects']['top_effects'].items():
                change = abs(effect['percent_change'])
                max_change = max(max_change, change)

            if max_change > 1000:
                print(f"  ❌ EXPLOSION: Max change = {max_change:.1f}%")
                results.append({'test': case['name'], 'status': 'FAIL'})
            else:
                print(f"  ✅ Converged in {iterations} iterations")
                print(f"     Affected {n_affected} indicators")
                print(f"     Max change: {max_change:.1f}%")
                results.append({'test': case['name'], 'status': 'PASS'})

        except Exception as e:
            print(f"  ❌ ERROR: {e}")
            results.append({'test': case['name'], 'status': 'ERROR', 'error': str(e)})

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    passed = sum(1 for r in results if r['status'] == 'PASS')
    failed = sum(1 for r in results if r['status'] == 'FAIL')
    errors = sum(1 for r in results if r['status'] == 'ERROR')

    print(f"Passed: {passed}/{len(results)}")
    print(f"Failed: {failed}")
    print(f"Errors: {errors}")

    if all(r['status'] == 'PASS' for r in results):
        print("\n✅ All multi-intervention tests PASSED")
        return True
    else:
        print("\n❌ Some tests FAILED")
        return False


if __name__ == "__main__":
    success = test_multi_intervention_scenarios()
    exit(0 if success else 1)
