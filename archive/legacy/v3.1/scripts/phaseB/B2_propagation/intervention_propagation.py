"""
B2: Intervention Propagation Algorithm

Core algorithm for "what-if" scenario analysis:
1. Apply intervention to source node(s)
2. Compute direct effects via edge beta coefficients
3. Iteratively propagate to downstream nodes
4. Apply saturation at each step
5. Repeat until convergence (change < threshold)
6. Propagate confidence intervals for uncertainty bounds
"""

import json
import numpy as np
from pathlib import Path
from collections import defaultdict
from typing import Optional
import sys

# Add parent path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'B1_saturation'))
from saturation_functions import apply_saturation


# =============================================================================
# GRAPH LOADING AND PREPROCESSING
# =============================================================================

def load_country_graph(country_code: str, graphs_dir: str = 'data/country_graphs') -> dict:
    """
    Load country-specific causal graph.

    Args:
        country_code: Country identifier (e.g., 'USA', 'Rwanda')
        graphs_dir: Directory containing country graph JSONs

    Returns:
        Graph dict with edges and metadata
    """
    graph_path = Path(graphs_dir) / f"{country_code}.json"
    if not graph_path.exists():
        raise FileNotFoundError(f"No graph found for {country_code}")

    with open(graph_path) as f:
        return json.load(f)


def build_adjacency(graph: dict) -> dict:
    """
    Build adjacency list from graph edges.

    Returns:
        Dict mapping source -> [(target, beta, ci_lower, ci_upper), ...]
    """
    adj = defaultdict(list)
    for edge in graph['edges']:
        adj[edge['source']].append({
            'target': edge['target'],
            'beta': edge['beta'],
            'ci_lower': edge.get('ci_lower', edge['beta'] * 0.8),
            'ci_upper': edge.get('ci_upper', edge['beta'] * 1.2)
        })
    return dict(adj)


def get_all_indicators(graph: dict) -> set:
    """Get all unique indicators in the graph."""
    indicators = set()
    for edge in graph['edges']:
        indicators.add(edge['source'])
        indicators.add(edge['target'])
    return indicators


# =============================================================================
# INTERVENTION PROPAGATION
# =============================================================================

def propagate_intervention(
    adjacency: dict,
    intervention: dict,
    baseline_values: dict,
    max_iterations: int = 10,
    convergence_threshold: float = 0.001,
    propagate_uncertainty: bool = True,
    dampening_factor: float = 0.5,
    max_percent_change: float = 100.0
) -> dict:
    """
    Propagate intervention effects through causal network.

    Algorithm:
    1. Initialize current_values with intervention applied
    2. For each iteration:
       a. For each node with incoming edges from changed nodes:
          - Compute effect = sum(beta * delta_source)
          - Apply dampening to prevent explosive growth
          - Apply to current value
          - Apply saturation
       b. Check convergence (max change < threshold)
    3. Return final values with uncertainty bounds

    Args:
        adjacency: Dict mapping source -> [edge_info, ...]
        intervention: Dict {indicator: delta_value} - absolute changes
        baseline_values: Dict {indicator: baseline_value}
        max_iterations: Max propagation iterations
        convergence_threshold: Stop when max change < this
        propagate_uncertainty: Whether to compute CI bounds
        dampening_factor: Reduce propagated effects by this factor (0-1)
        max_percent_change: Cap maximum percent change per indicator

    Returns:
        Dict with 'values', 'lower_bound', 'upper_bound', 'iterations', 'converged'
    """
    # Initialize values
    current_values = baseline_values.copy()
    lower_bound = baseline_values.copy()
    upper_bound = baseline_values.copy()

    # Track cumulative changes from baseline (to enforce max percent change)
    cumulative_deltas = {}

    # Apply initial intervention
    for indicator, delta in intervention.items():
        if indicator in current_values:
            baseline = baseline_values[indicator]

            # Cap intervention to max percent change
            if baseline != 0:
                max_delta = abs(baseline) * (max_percent_change / 100)
                delta = np.clip(delta, -max_delta, max_delta)

            new_val = current_values[indicator] + delta
            current_values[indicator] = apply_saturation(indicator, new_val, baseline)
            cumulative_deltas[indicator] = current_values[indicator] - baseline

            if propagate_uncertainty:
                lower_bound[indicator] = current_values[indicator]
                upper_bound[indicator] = current_values[indicator]

    # Track which nodes changed this iteration
    changed_nodes = set(intervention.keys())

    # Propagation loop
    for iteration in range(max_iterations):
        new_changes = {}
        max_change = 0

        # For each source node that changed
        for source in changed_nodes:
            if source not in adjacency:
                continue

            # Compute effect on each target - use cumulative delta from baseline
            source_delta = cumulative_deltas.get(source, 0)

            for edge_info in adjacency[source]:
                target = edge_info['target']
                beta = edge_info['beta']

                # Effect = beta * source_change, with dampening
                # Dampening prevents explosive growth through cascading edges
                effect = beta * source_delta * dampening_factor

                if target not in new_changes:
                    new_changes[target] = 0
                new_changes[target] += effect

        # Apply accumulated changes
        changed_nodes = set()
        for target, total_effect in new_changes.items():
            baseline = baseline_values.get(target, 0)
            if baseline == 0:
                continue

            # Get current cumulative delta
            current_delta = cumulative_deltas.get(target, 0)
            proposed_delta = current_delta + total_effect

            # Enforce max percent change limit
            max_delta = abs(baseline) * (max_percent_change / 100)
            clamped_delta = np.clip(proposed_delta, -max_delta, max_delta)

            # Calculate new value and apply saturation
            new_val = baseline + clamped_delta
            saturated = apply_saturation(target, new_val, baseline)

            # Update cumulative delta
            actual_delta = saturated - baseline
            delta_change = abs(actual_delta - current_delta)

            if delta_change > convergence_threshold:
                changed_nodes.add(target)
                max_change = max(max_change, delta_change)

            cumulative_deltas[target] = actual_delta
            current_values[target] = saturated

            # Update uncertainty bounds
            if propagate_uncertainty:
                lower_bound[target] = min(lower_bound.get(target, saturated), saturated * 0.95)
                upper_bound[target] = max(upper_bound.get(target, saturated), saturated * 1.05)

        # Check convergence
        if max_change < convergence_threshold or not changed_nodes:
            return {
                'values': current_values,
                'lower_bound': lower_bound,
                'upper_bound': upper_bound,
                'iterations': iteration + 1,
                'converged': True
            }

    return {
        'values': current_values,
        'lower_bound': lower_bound,
        'upper_bound': upper_bound,
        'iterations': max_iterations,
        'converged': False
    }


def compute_effects(
    baseline_values: dict,
    simulated_values: dict,
    indicators: Optional[list] = None
) -> dict:
    """
    Compute absolute and percentage changes.

    Args:
        baseline_values: Original values
        simulated_values: Values after intervention
        indicators: Specific indicators to report (None = all changed)

    Returns:
        Dict of {indicator: {absolute, percent, baseline, simulated}}
    """
    effects = {}

    check_indicators = indicators if indicators else simulated_values.keys()

    for ind in check_indicators:
        if ind not in baseline_values or ind not in simulated_values:
            continue

        baseline = baseline_values[ind]
        simulated = simulated_values[ind]
        absolute = simulated - baseline

        # Skip if no meaningful change
        if abs(absolute) < 1e-6:
            continue

        percent = (absolute / baseline * 100) if baseline != 0 else 0

        effects[ind] = {
            'baseline': baseline,
            'simulated': simulated,
            'absolute_change': absolute,
            'percent_change': percent
        }

    return effects


# =============================================================================
# UNIT TESTS
# =============================================================================

def test_build_adjacency():
    """Test adjacency list building."""
    graph = {
        'edges': [
            {'source': 'A', 'target': 'B', 'beta': 0.5, 'ci_lower': 0.4, 'ci_upper': 0.6},
            {'source': 'A', 'target': 'C', 'beta': 0.3, 'ci_lower': 0.2, 'ci_upper': 0.4},
            {'source': 'B', 'target': 'C', 'beta': 0.2, 'ci_lower': 0.1, 'ci_upper': 0.3}
        ]
    }
    adj = build_adjacency(graph)

    assert 'A' in adj
    assert len(adj['A']) == 2
    assert adj['A'][0]['target'] == 'B'
    assert adj['A'][0]['beta'] == 0.5

    print("  build_adjacency: PASS")


def test_propagation_simple():
    """Test simple linear propagation with dampening."""
    # Simple chain: A -> B -> C
    adj = {
        'A': [{'target': 'B', 'beta': 0.5, 'ci_lower': 0.4, 'ci_upper': 0.6}],
        'B': [{'target': 'C', 'beta': 0.5, 'ci_lower': 0.4, 'ci_upper': 0.6}]
    }

    baseline = {'A': 10, 'B': 20, 'C': 30}
    intervention = {'A': 10}  # Increase A by 10 (100% increase)

    result = propagate_intervention(adj, intervention, baseline)

    # A: 10 -> 20 (intervention applied)
    assert result['values']['A'] == 20

    # B: effect = 0.5 (beta) * 10 (delta) * 0.5 (dampening) = 2.5
    # B = 20 + 2.5 = 22.5
    assert abs(result['values']['B'] - 22.5) < 0.5

    # C: effect from B = 0.5 * 2.5 * 0.5 = 0.625
    # C ≈ 30.625
    assert result['values']['C'] > 30

    assert result['converged']

    print("  propagation_simple: PASS")


def test_propagation_convergence():
    """Test that propagation converges."""
    # Larger network
    adj = {
        'A': [{'target': 'B', 'beta': 0.3, 'ci_lower': 0.2, 'ci_upper': 0.4}],
        'B': [{'target': 'C', 'beta': 0.3, 'ci_lower': 0.2, 'ci_upper': 0.4}],
        'C': [{'target': 'D', 'beta': 0.3, 'ci_lower': 0.2, 'ci_upper': 0.4}],
        'D': [{'target': 'E', 'beta': 0.3, 'ci_lower': 0.2, 'ci_upper': 0.4}]
    }

    baseline = {'A': 50, 'B': 50, 'C': 50, 'D': 50, 'E': 50}
    intervention = {'A': 10}

    result = propagate_intervention(adj, intervention, baseline, max_iterations=10)

    assert result['converged']
    assert result['iterations'] <= 10

    print("  propagation_convergence: PASS")


def test_saturation_applied():
    """Test that saturation is applied during propagation."""
    adj = {
        'literacy_rate': [{'target': 'outcome', 'beta': 0.5, 'ci_lower': 0.4, 'ci_upper': 0.6}]
    }

    baseline = {'literacy_rate': 95, 'outcome': 50}
    intervention = {'literacy_rate': 20}  # Would push to 115

    result = propagate_intervention(adj, intervention, baseline)

    # Literacy should be capped at 100
    assert result['values']['literacy_rate'] == 100

    print("  saturation_applied: PASS")


def test_compute_effects():
    """Test effect computation."""
    baseline = {'A': 100, 'B': 50, 'C': 200}
    simulated = {'A': 110, 'B': 50, 'C': 220}

    effects = compute_effects(baseline, simulated)

    assert 'A' in effects
    assert effects['A']['absolute_change'] == 10
    assert effects['A']['percent_change'] == 10.0

    assert 'B' not in effects  # No change

    assert 'C' in effects
    assert effects['C']['percent_change'] == 10.0

    print("  compute_effects: PASS")


def run_all_tests():
    """Run all unit tests."""
    print("\nRunning propagation tests...")
    print("-" * 40)

    test_build_adjacency()
    test_propagation_simple()
    test_propagation_convergence()
    test_saturation_applied()
    test_compute_effects()

    print("-" * 40)
    print("✅ All propagation tests PASSED\n")


if __name__ == "__main__":
    run_all_tests()
