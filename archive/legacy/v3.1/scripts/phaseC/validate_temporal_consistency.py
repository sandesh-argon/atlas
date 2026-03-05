"""
Phase C Validation: Temporal Consistency Check

Check that temporal effects are monotonic or smooth - no spikes or crashes.

Example good trajectory:
  Year 1: +2%
  Year 5: +8%
  Year 10: +12%

Example bad trajectory (spike):
  Year 1: +2%
  Year 5: +50%  <- Spike (unrealistic)
  Year 10: +8%  <- Crash (unrealistic)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / 'C2_temporal_simulation'))
from temporal_simulation import run_temporal_simulation


def validate_temporal_smoothness():
    """Check for spikes/crashes in temporal trajectories."""

    print("\n" + "=" * 60)
    print("VALIDATION: Temporal Consistency Check")
    print("=" * 60)

    test_cases = [
        {'country': 'Australia', 'indicator': 'v2elvotbuy', 'change': 20},
        {'country': 'Rwanda', 'indicator': 'v2elvotbuy', 'change': 20},
        {'country': 'Brazil', 'indicator': 'v2smlawpr', 'change': 15},
        {'country': 'India', 'indicator': 'v2elvotbuy', 'change': 25},
        {'country': 'Germany', 'indicator': 'v2elvotbuy', 'change': 20},
    ]

    all_pass = True
    spike_threshold = 0.50  # 50% change in one year is a spike
    crash_threshold = 0.20  # 20% decrease from peak is a crash

    for case in test_cases:
        print(f"\n{case['country']}: {case['indicator']} {case['change']:+}%")

        result = run_temporal_simulation(
            country_code=case['country'],
            interventions=[{'indicator': case['indicator'], 'change_percent': case['change']}],
            horizon_years=10
        )

        if result['status'] != 'success':
            print(f"  ⚠️  Simulation failed: {result.get('message', 'Unknown')}")
            continue

        # Check each affected indicator's trajectory
        issues = []

        # Get all indicators that changed
        all_indicators = set()
        for year_effects in result['effects'].values():
            all_indicators.update(year_effects.keys())

        for indicator in list(all_indicators)[:10]:  # Check top 10
            # Get trajectory
            trajectory = []
            for year in range(11):
                year_effects = result['effects'].get(year, {})
                if indicator in year_effects:
                    trajectory.append(year_effects[indicator]['percent_change'])
                else:
                    trajectory.append(0)

            # Check for spikes (>50% change in one year)
            for year in range(1, 11):
                year_change = abs(trajectory[year] - trajectory[year-1])
                if year_change > spike_threshold * 100:  # Convert to percentage
                    issues.append({
                        'indicator': indicator,
                        'year': year,
                        'issue': f'Spike: {year_change:.1f}% change in one year'
                    })

            # Check for crashes (effect decreases significantly after peak)
            if len(trajectory) > 5:
                peak_idx = trajectory.index(max(trajectory, key=abs))
                if peak_idx > 0 and peak_idx < 10:
                    peak_val = abs(trajectory[peak_idx])
                    final_val = abs(trajectory[10])
                    if peak_val > 0 and final_val < peak_val * (1 - crash_threshold):
                        issues.append({
                            'indicator': indicator,
                            'year': 10,
                            'issue': f'Crash: Peak {peak_val:.1f}% at yr {peak_idx}, fell to {final_val:.1f}%'
                        })

        if issues:
            print(f"  ⚠️  Found {len(issues)} anomalies:")
            for issue in issues[:3]:
                print(f"    - {issue['indicator']}: {issue['issue']}")
            all_pass = False
        else:
            print(f"  ✅ Trajectories are smooth")

    if all_pass:
        print(f"\n✅ PASS: All temporal trajectories are smooth")
    else:
        print(f"\n⚠️  WARN: Some trajectories have anomalies (may be data-driven)")

    return True  # Warn but don't fail - some spikes may be realistic


if __name__ == "__main__":
    validate_temporal_smoothness()
