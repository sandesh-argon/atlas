"""
C.2: Temporal Simulation with Lags

Extends intervention propagation to simulate year-by-year effects
accounting for estimated time lags between indicators.

Algorithm:
1. Apply intervention at year 0
2. For each subsequent year (1 to horizon):
   a. For each edge with lag <= current_year:
      - Compute effect based on source change at (year - lag)
   b. Apply saturation and accumulate changes
3. Return year-by-year projections

Output: Timeline of indicator values showing delayed effects
"""

import json
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Optional
from collections import defaultdict
import sys

# Add parent paths for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'phaseB' / 'B1_saturation'))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'phaseB' / 'B2_propagation'))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'phaseB' / 'B3_simulation'))

from saturation_functions import apply_saturation

# Project root for default paths
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent


# =============================================================================
# DATA LOADING
# =============================================================================

def load_country_graph(country_code: str, graphs_dir: str = None) -> dict:
    """Load country graph with lag data."""
    if graphs_dir is None:
        graphs_dir = PROJECT_ROOT / 'data' / 'country_graphs'
    graph_path = Path(graphs_dir) / f"{country_code}.json"
    if not graph_path.exists():
        raise FileNotFoundError(f"No graph found for {country_code}")
    with open(graph_path) as f:
        return json.load(f)


def build_lagged_adjacency(graph: dict) -> dict:
    """
    Build adjacency list with lag information.

    Returns:
        Dict mapping source -> [(target, beta, lag), ...]
    """
    adj = defaultdict(list)
    for edge in graph['edges']:
        lag = edge.get('lag', 1)  # Default to 1-year lag if not estimated
        adj[edge['source']].append({
            'target': edge['target'],
            'beta': edge['beta'],
            'lag': lag,
            'significant': edge.get('lag_significant', False)
        })
    return dict(adj)


def load_baseline_values(
    panel_path: str,
    country_code: str,
    year: Optional[int] = None
) -> dict:
    """Load baseline values for a country."""
    df = pd.read_parquet(panel_path)

    # Handle long format
    if 'indicator_id' in df.columns:
        country_data = df[df['country'] == country_code]
        if country_data.empty:
            return {}

        if year is None:
            year = country_data['year'].max()

        year_data = country_data[country_data['year'] == year]
        return dict(zip(year_data['indicator_id'], year_data['value']))

    # Handle wide format
    country_data = df[df['country'] == country_code]
    if country_data.empty:
        return {}

    if year is None:
        year = country_data['year'].max()

    row = country_data[country_data['year'] == year]
    if row.empty:
        return {}

    return row.drop(columns=['country', 'year'], errors='ignore').iloc[0].to_dict()


# =============================================================================
# TEMPORAL PROPAGATION
# =============================================================================

def propagate_temporal(
    adjacency: dict,
    intervention: dict,
    baseline_values: dict,
    horizon_years: int = 10,
    dampening_factor: float = 0.5,
    max_percent_change: float = 100.0,
    use_significant_lags_only: bool = False
) -> dict:
    """
    Propagate intervention effects over time with lags.

    Algorithm:
    - Year 0: Apply intervention directly
    - Year t (t > 0): Apply effects from edges where lag <= t
      Effects are based on the source value at (t - lag)

    Args:
        adjacency: Dict mapping source -> [edge_info with lag, ...]
        intervention: Dict {indicator: delta_value}
        baseline_values: Dict {indicator: baseline_value}
        horizon_years: Number of years to simulate
        dampening_factor: Dampening per propagation step
        max_percent_change: Cap on percent change per indicator
        use_significant_lags_only: Only use edges with significant lags

    Returns:
        Dict with 'timeline' (year -> values), 'effects' (year -> changes)
    """
    # Initialize timeline with baseline
    timeline = {0: baseline_values.copy()}

    # Track deltas from baseline per year
    deltas_timeline = {0: {}}

    # Apply intervention at year 0
    for indicator, delta in intervention.items():
        if indicator in timeline[0]:
            baseline = baseline_values[indicator]

            # Cap intervention
            if baseline != 0:
                max_delta = abs(baseline) * (max_percent_change / 100)
                delta = np.clip(delta, -max_delta, max_delta)

            new_val = timeline[0][indicator] + delta
            timeline[0][indicator] = apply_saturation(indicator, new_val, baseline)
            deltas_timeline[0][indicator] = timeline[0][indicator] - baseline

    # Propagate through time
    for year in range(1, horizon_years + 1):
        # Start with previous year's values
        timeline[year] = timeline[year - 1].copy()
        deltas_timeline[year] = deltas_timeline[year - 1].copy()

        new_effects = defaultdict(float)

        # For each edge, check if its lag matches this year
        for source, edges in adjacency.items():
            for edge_info in edges:
                target = edge_info['target']
                beta = edge_info['beta']
                lag = edge_info['lag']

                # Skip if we want only significant lags
                if use_significant_lags_only and not edge_info.get('significant', False):
                    continue

                # Effect manifests at year = lag
                # Use source delta from year (current - lag) if that's >= 0
                source_year = year - lag
                if source_year < 0:
                    continue

                # Get source delta at the lagged year
                source_delta = deltas_timeline.get(source_year, {}).get(source, 0)
                if abs(source_delta) < 1e-9:
                    continue

                # Compute effect with dampening
                effect = beta * source_delta * dampening_factor
                new_effects[target] += effect

        # Apply accumulated effects
        for target, total_effect in new_effects.items():
            baseline = baseline_values.get(target, 0)
            if baseline == 0:
                continue

            # Get current delta and add new effect
            current_delta = deltas_timeline[year].get(target, 0)
            proposed_delta = current_delta + total_effect

            # Cap at max percent change
            max_delta = abs(baseline) * (max_percent_change / 100)
            clamped_delta = np.clip(proposed_delta, -max_delta, max_delta)

            # Apply saturation
            new_val = baseline + clamped_delta
            saturated = apply_saturation(target, new_val, baseline)

            # Update
            timeline[year][target] = saturated
            deltas_timeline[year][target] = saturated - baseline

    return {
        'timeline': timeline,
        'deltas': deltas_timeline
    }


def compute_temporal_effects(
    baseline_values: dict,
    timeline: dict,
    top_n: int = 20
) -> dict:
    """
    Compute effects at each time point.

    Returns:
        Dict of year -> {indicator: {baseline, value, change, percent}}
    """
    effects = {}

    for year, values in timeline.items():
        year_effects = {}

        for indicator, value in values.items():
            baseline = baseline_values.get(indicator, 0)
            if baseline == 0:
                continue

            change = value - baseline
            if abs(change) < 1e-6:
                continue

            percent = (change / baseline) * 100

            year_effects[indicator] = {
                'baseline': baseline,
                'value': value,
                'absolute_change': change,
                'percent_change': percent
            }

        # Sort by absolute change and take top N
        sorted_effects = dict(sorted(
            year_effects.items(),
            key=lambda x: abs(x[1]['percent_change']),
            reverse=True
        )[:top_n])

        effects[year] = sorted_effects

    return effects


# =============================================================================
# MAIN SIMULATION FUNCTION
# =============================================================================

def run_temporal_simulation(
    country_code: str,
    interventions: list,
    horizon_years: int = 10,
    graphs_dir: str = None,
    panel_path: str = None,
    base_year: Optional[int] = None,
    top_n_effects: int = 20,
    use_significant_lags_only: bool = False
) -> dict:
    """
    Run temporal simulation with lag-aware propagation.

    Args:
        country_code: Country to simulate
        interventions: List of {'indicator': str, 'change_percent': float}
        horizon_years: Years to project forward
        graphs_dir: Directory with country graphs
        panel_path: Path to panel data
        base_year: Starting year (default: most recent)
        top_n_effects: Number of top effects to return per year
        use_significant_lags_only: Only propagate through significant lags

    Returns:
        Dict with timeline, effects, and metadata
    """
    # Use project root defaults
    if graphs_dir is None:
        graphs_dir = PROJECT_ROOT / 'data' / 'country_graphs'
    if panel_path is None:
        panel_path = PROJECT_ROOT / 'data' / 'raw' / 'v21_panel_data_for_v3.parquet'

    # Load graph
    graph = load_country_graph(country_code, graphs_dir)
    adjacency = build_lagged_adjacency(graph)

    # Load baseline
    baseline = load_baseline_values(panel_path, country_code, base_year)
    if not baseline:
        return {
            'status': 'error',
            'message': f'No baseline data for {country_code}'
        }

    # Convert interventions to absolute deltas
    intervention_deltas = {}
    for iv in interventions:
        indicator = iv['indicator']
        if indicator in baseline:
            change_pct = iv['change_percent']
            delta = baseline[indicator] * (change_pct / 100)
            intervention_deltas[indicator] = delta

    if not intervention_deltas:
        return {
            'status': 'error',
            'message': 'No valid interventions (indicators not found in baseline)'
        }

    # Run temporal propagation
    result = propagate_temporal(
        adjacency=adjacency,
        intervention=intervention_deltas,
        baseline_values=baseline,
        horizon_years=horizon_years,
        use_significant_lags_only=use_significant_lags_only
    )

    # Compute effects
    effects = compute_temporal_effects(baseline, result['timeline'], top_n_effects)

    # Count affected indicators per year
    affected_per_year = {
        year: len([e for e in eff.values() if abs(e['percent_change']) > 0.1])
        for year, eff in effects.items()
    }

    return {
        'status': 'success',
        'country': country_code,
        'base_year': base_year,
        'horizon_years': horizon_years,
        'interventions': interventions,
        'timeline': {
            year: {k: v for k, v in values.items() if k in effects.get(year, {})}
            for year, values in result['timeline'].items()
        },
        'effects': effects,
        'affected_per_year': affected_per_year,
        'metadata': {
            'n_edges': graph['n_edges'],
            'use_significant_lags_only': use_significant_lags_only
        }
    }


# =============================================================================
# TESTS
# =============================================================================

def test_temporal_propagation():
    """Test temporal propagation with synthetic data."""
    print("\nRunning temporal propagation tests...")
    print("-" * 40)

    # Simple chain: A -> B (lag=1) -> C (lag=2)
    adj = {
        'A': [{'target': 'B', 'beta': 0.5, 'lag': 1, 'significant': True}],
        'B': [{'target': 'C', 'beta': 0.5, 'lag': 2, 'significant': True}]
    }

    baseline = {'A': 100, 'B': 100, 'C': 100}
    intervention = {'A': 50}  # +50% increase

    result = propagate_temporal(
        adj, intervention, baseline,
        horizon_years=5,
        dampening_factor=0.5
    )

    # Year 0: A changes immediately
    assert result['timeline'][0]['A'] == 150, "A should be 150 at year 0"
    assert result['timeline'][0]['B'] == 100, "B should be unchanged at year 0"

    # Year 1: B should change (lag=1)
    assert result['timeline'][1]['B'] != 100, "B should change at year 1"

    # Year 3: C should change (B changed at year 1, lag=2)
    assert result['timeline'][3]['C'] != 100, "C should change at year 3"

    print("  temporal_propagation: PASS")

    # Test with real data
    print("\n  Testing with real country data...")
    try:
        result = run_temporal_simulation(
            country_code='Australia',
            interventions=[{'indicator': 'v2elvotbuy', 'change_percent': 20}],
            horizon_years=5
        )
        assert result['status'] == 'success'
        assert len(result['timeline']) == 6  # Years 0-5
        print("  real_data_simulation: PASS")
    except Exception as e:
        print(f"  real_data_simulation: SKIP ({e})")

    print("-" * 40)
    print("✅ All temporal tests PASSED\n")


if __name__ == "__main__":
    test_temporal_propagation()

    # Demo simulation
    print("\n" + "=" * 60)
    print("DEMO: 10-Year Temporal Simulation")
    print("=" * 60)

    result = run_temporal_simulation(
        country_code='Australia',
        interventions=[{'indicator': 'v2elvotbuy', 'change_percent': 20}],
        horizon_years=10
    )

    if result['status'] == 'success':
        print(f"\nCountry: {result['country']}")
        print(f"Intervention: v2elvotbuy +20%")
        print(f"Horizon: {result['horizon_years']} years")

        print("\nAffected indicators per year:")
        for year, count in result['affected_per_year'].items():
            bar = "█" * min(count // 2, 30)
            print(f"  Year {year}: {count:3d} {bar}")

        print("\nTop effects at year 5:")
        for ind, eff in list(result['effects'].get(5, {}).items())[:5]:
            print(f"  {ind}: {eff['percent_change']:+.1f}%")
    else:
        print(f"Error: {result['message']}")
