"""
B3: Simulation Runner - End-to-End Intervention Simulation

Complete pipeline for running "what-if" scenarios:
1. Load country graph and baseline data
2. Accept intervention specification
3. Run propagation algorithm
4. Return formatted results with uncertainty bounds
"""

import json
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import Optional
import sys

# Add parent paths for imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'B1_saturation'))
sys.path.insert(0, str(Path(__file__).parent.parent / 'B2_propagation'))

from saturation_functions import apply_saturation, get_saturation_function
from intervention_propagation import (
    load_country_graph,
    build_adjacency,
    propagate_intervention,
    compute_effects
)


# =============================================================================
# DATA LOADING
# =============================================================================

def find_best_year_for_indicators(
    country_code: str,
    indicators: list[str],
    panel_path: str = 'data/raw/v21_panel_data_for_v3.parquet'
) -> tuple[int, list[str]]:
    """
    Find the most recent year where all intervention indicators have data.

    Args:
        country_code: Country identifier
        indicators: List of indicator IDs to check
        panel_path: Path to panel data

    Returns:
        (best_year, missing_indicators) - missing_indicators is empty if all found
    """
    panel = pd.read_parquet(panel_path)
    country_col = 'country' if 'country' in panel.columns else 'country_text_id'
    country_data = panel[panel[country_col] == country_code]

    if country_data.empty:
        raise ValueError(f"No data found for country: {country_code}")

    # Get years sorted descending (most recent first)
    years = sorted(country_data['year'].unique(), reverse=True)

    # For each year, check if all indicators have data
    for year in years:
        year_data = country_data[country_data['year'] == year]
        year_indicators = set(year_data['indicator_id'].unique())

        missing = [ind for ind in indicators if ind not in year_indicators]
        if not missing:
            return int(year), []

    # No year has all indicators - find the year with most coverage
    best_year = None
    min_missing = len(indicators) + 1
    best_missing = indicators

    for year in years:
        year_data = country_data[country_data['year'] == year]
        year_indicators = set(year_data['indicator_id'].unique())
        missing = [ind for ind in indicators if ind not in year_indicators]

        if len(missing) < min_missing:
            min_missing = len(missing)
            best_year = int(year)
            best_missing = missing

    return best_year, best_missing


def load_baseline_values(
    country_code: str,
    panel_path: str = 'data/raw/v21_panel_data_for_v3.parquet',
    year: Optional[int] = None
) -> dict:
    """
    Load baseline indicator values for a country.

    Uses most recent year if not specified.
    Handles both wide and long format panel data.

    Args:
        country_code: Country identifier (full name like 'Rwanda')
        panel_path: Path to panel data
        year: Specific year to use (default: most recent)

    Returns:
        Dict of {indicator: value}
    """
    panel = pd.read_parquet(panel_path)

    # Check if data is in long format (country, year, indicator_id, value)
    is_long_format = 'indicator_id' in panel.columns and 'value' in panel.columns

    # Filter to country
    country_col = 'country' if 'country' in panel.columns else 'country_text_id'
    country_data = panel[panel[country_col] == country_code]

    if country_data.empty:
        raise ValueError(f"No data found for country: {country_code}")

    # Use most recent year if not specified
    if year is None:
        year = country_data['year'].max()

    year_data = country_data[country_data['year'] == year]

    if year_data.empty:
        raise ValueError(f"No data for {country_code} in year {year}")

    # Convert to dict based on format
    baseline = {}

    if is_long_format:
        # Long format: pivot to wide
        for _, row in year_data.iterrows():
            indicator = row['indicator_id']
            val = row['value']
            if pd.notna(val):
                baseline[indicator] = float(val)
    else:
        # Wide format: each column is an indicator
        exclude_cols = {'country_text_id', 'country', 'country_code', 'iso3', 'year'}
        for col in year_data.columns:
            if col not in exclude_cols:
                val = year_data[col].iloc[0]
                if pd.notna(val):
                    baseline[col] = float(val)

    return baseline, int(year)


def load_country_data(
    country_code: str,
    graphs_dir: str = 'data/country_graphs',
    panel_path: str = 'data/raw/v21_panel_data_for_v3.parquet',
    year: Optional[int] = None
) -> tuple[dict, dict, dict, int]:
    """
    Load all data needed for simulation.

    Returns:
        (graph, adjacency, baseline_values, year)
    """
    graph = load_country_graph(country_code, graphs_dir)
    adjacency = build_adjacency(graph)
    baseline, data_year = load_baseline_values(country_code, panel_path, year)

    return graph, adjacency, baseline, data_year


# =============================================================================
# SIMULATION RUNNER
# =============================================================================

def run_simulation(
    country_code: str,
    interventions: list[dict],
    graphs_dir: str = 'data/country_graphs',
    panel_path: str = 'data/raw/v21_panel_data_for_v3.parquet',
    year: Optional[int] = None,
    max_iterations: int = 10,
    top_n_effects: int = 20
) -> dict:
    """
    Run complete intervention simulation.

    Args:
        country_code: Country identifier (e.g., 'Rwanda', 'USA')
        interventions: List of {indicator, change_percent} or {indicator, change_absolute}
        graphs_dir: Path to country graphs
        panel_path: Path to panel data
        year: Base year for simulation (auto-detects best year if None)
        max_iterations: Max propagation iterations
        top_n_effects: Number of top effects to return

    Returns:
        Simulation result dict with baseline, simulated, effects, metadata
    """
    # Extract intervention indicator IDs
    intervention_indicators = [intv['indicator'] for intv in interventions]

    # If no year specified, find the best year where all interventions have data
    if year is None:
        best_year, missing = find_best_year_for_indicators(
            country_code, intervention_indicators, panel_path
        )

        if missing:
            # Some indicators have no data in any year
            return {
                'status': 'error',
                'message': f'Indicators not found in any year for {country_code}: {missing}',
                'missing_indicators': missing,
                'interventions': [
                    {'indicator': ind, 'status': 'error', 'reason': 'no data available'}
                    for ind in missing
                ]
            }

        year = best_year

    # Load data for the determined year
    graph, adjacency, baseline, data_year = load_country_data(
        country_code, graphs_dir, panel_path, year
    )

    # Convert interventions to absolute changes
    intervention_deltas = {}
    intervention_details = []

    for intv in interventions:
        indicator = intv['indicator']

        if indicator not in baseline:
            intervention_details.append({
                'indicator': indicator,
                'status': 'skipped',
                'reason': f'indicator not in baseline data for year {data_year}'
            })
            continue

        baseline_val = baseline[indicator]

        if 'change_percent' in intv:
            delta = baseline_val * (intv['change_percent'] / 100)
            intervention_details.append({
                'indicator': indicator,
                'baseline': baseline_val,
                'change_percent': intv['change_percent'],
                'change_absolute': delta,
                'status': 'applied'
            })
        elif 'change_absolute' in intv:
            delta = intv['change_absolute']
            intervention_details.append({
                'indicator': indicator,
                'baseline': baseline_val,
                'change_absolute': delta,
                'change_percent': (delta / baseline_val * 100) if baseline_val != 0 else 0,
                'status': 'applied'
            })
        else:
            continue

        intervention_deltas[indicator] = delta

    if not intervention_deltas:
        return {
            'status': 'error',
            'message': f'No valid interventions to apply for {country_code} in year {data_year}',
            'interventions': intervention_details
        }

    # Run propagation
    result = propagate_intervention(
        adjacency=adjacency,
        intervention=intervention_deltas,
        baseline_values=baseline,
        max_iterations=max_iterations,
        propagate_uncertainty=True
    )

    # Compute effects
    all_effects = compute_effects(baseline, result['values'])

    # Sort by absolute percent change
    sorted_effects = sorted(
        all_effects.items(),
        key=lambda x: abs(x[1]['percent_change']),
        reverse=True
    )

    # Top N effects
    top_effects = dict(sorted_effects[:top_n_effects])

    # Build response
    return {
        'status': 'success',
        'country': country_code,
        'base_year': data_year,
        'interventions': intervention_details,
        'propagation': {
            'iterations': result['iterations'],
            'converged': result['converged']
        },
        'effects': {
            'total_affected': len(all_effects),
            'top_effects': top_effects
        },
        'metadata': {
            'n_edges': graph['n_edges'],
            'n_edges_with_data': graph.get('n_edges_with_data', 'unknown'),
            'timestamp': datetime.now().isoformat()
        }
    }


def format_simulation_results(result: dict) -> str:
    """
    Format simulation results for display.

    Args:
        result: Simulation result dict

    Returns:
        Formatted string
    """
    if result['status'] != 'success':
        return f"Simulation failed: {result.get('message', 'unknown error')}"

    lines = [
        f"\n{'='*60}",
        f"SIMULATION RESULTS: {result['country']}",
        f"{'='*60}",
        f"\nBase Year: {result['base_year']}",
        f"\nInterventions Applied:"
    ]

    for intv in result['interventions']:
        if intv['status'] == 'applied':
            lines.append(f"  - {intv['indicator']}: {intv['change_percent']:+.1f}% "
                        f"({intv['baseline']:.2f} → {intv['baseline'] + intv['change_absolute']:.2f})")

    lines.extend([
        f"\nPropagation: {result['propagation']['iterations']} iterations, "
        f"converged={result['propagation']['converged']}",
        f"\nTotal Indicators Affected: {result['effects']['total_affected']}",
        f"\nTop Effects:"
    ])

    for ind, effect in result['effects']['top_effects'].items():
        lines.append(
            f"  {ind[:40]:<40} {effect['percent_change']:>+8.2f}% "
            f"({effect['baseline']:.2f} → {effect['simulated']:.2f})"
        )

    lines.append(f"\n{'='*60}\n")

    return '\n'.join(lines)


def save_simulation_results(result: dict, output_path: str):
    """Save simulation results to JSON file."""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(result, f, indent=2, default=str)


# =============================================================================
# TEST SCENARIOS
# =============================================================================

def test_rwanda_health_spending():
    """
    Test scenario: Rwanda +20% health indicator.

    This is a key validation scenario from the project brief.
    """
    print("\n" + "="*60)
    print("TEST: Rwanda +20% Health Indicator")
    print("="*60)

    try:
        result = run_simulation(
            country_code='Rwanda',
            interventions=[
                {'indicator': 'v2pehealth', 'change_percent': 20},  # V-Dem health indicator
            ]
        )

        print(format_simulation_results(result))

        # Save results
        output_path = 'outputs/simulations/Rwanda_health_intervention.json'
        save_simulation_results(result, output_path)
        print(f"Results saved to: {output_path}")

        return result['status'] == 'success'

    except Exception as e:
        print(f"Test failed with error: {e}")
        return False


def test_simple_simulation():
    """Test with a country that should have good data coverage."""
    print("\n" + "="*60)
    print("TEST: Simple Simulation (Australia)")
    print("="*60)

    try:
        result = run_simulation(
            country_code='Australia',
            interventions=[
                {'indicator': 'v2elirreg_osp', 'change_percent': 10}  # Election irregularities
            ],
            top_n_effects=10
        )

        if result['status'] == 'success':
            print(f"✅ Simulation successful")
            print(f"   Iterations: {result['propagation']['iterations']}")
            print(f"   Converged: {result['propagation']['converged']}")
            print(f"   Effects: {result['effects']['total_affected']} indicators")
            return True
        else:
            print(f"❌ Simulation failed: {result.get('message')}")
            return False

    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        return False


def run_all_tests():
    """Run all simulation tests."""
    print("\nRunning simulation tests...")

    results = []

    # Test 1: Simple simulation
    results.append(('Simple simulation', test_simple_simulation()))

    # Test 2: Rwanda health spending
    results.append(('Rwanda health spending', test_rwanda_health_spending()))

    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {name}: {status}")

    all_passed = all(r[1] for r in results)
    print("="*60)
    if all_passed:
        print("✅ All simulation tests PASSED\n")
    else:
        print("❌ Some tests FAILED\n")

    return all_passed


if __name__ == "__main__":
    run_all_tests()
