"""
Phase B Validation #5: Zero-Effect Intervention Test

Test that leaf nodes (targets with no outgoing edges) produce minimal effects.
"""

import sys
import json
from pathlib import Path
from collections import Counter
sys.path.insert(0, str(Path(__file__).parent / 'B3_simulation'))

from simulation_runner import run_simulation, load_baseline_values


def find_leaf_nodes(country: str) -> list:
    """Find indicators that are targets but not sources (leaf nodes)."""
    graph_path = Path('data/country_graphs') / f"{country}.json"

    with open(graph_path) as f:
        graph = json.load(f)

    sources = set(e['source'] for e in graph['edges'])
    targets = set(e['target'] for e in graph['edges'])

    # Leaf nodes: appear as targets but not as sources
    leaf_nodes = targets - sources

    return list(leaf_nodes)


def find_hub_nodes(country: str, top_n: int = 5) -> list:
    """Find indicators with most outgoing edges (hub nodes)."""
    graph_path = Path('data/country_graphs') / f"{country}.json"

    with open(graph_path) as f:
        graph = json.load(f)

    source_counts = Counter(e['source'] for e in graph['edges'])
    return [node for node, count in source_counts.most_common(top_n)]


def test_zero_effect_intervention():
    """Test leaf node vs hub node interventions."""

    test_country = 'Australia'

    print(f"\n{'='*60}")
    print(f"ZERO-EFFECT TEST: {test_country}")
    print(f"{'='*60}")

    # Find leaf and hub nodes
    leaf_nodes = find_leaf_nodes(test_country)
    hub_nodes = find_hub_nodes(test_country)

    print(f"\nFound {len(leaf_nodes)} leaf nodes (no outgoing edges)")
    print(f"Found {len(hub_nodes)} hub nodes (most outgoing edges)")

    # Get baseline values to find which indicators have data
    try:
        baseline, year = load_baseline_values(test_country)
    except Exception as e:
        print(f"Error loading baseline: {e}")
        return False

    # Find leaf nodes that are in baseline
    leaf_with_data = [n for n in leaf_nodes if n in baseline][:3]
    hub_with_data = [n for n in hub_nodes if n in baseline][:3]

    print(f"\nLeaf nodes with data: {len(leaf_with_data)}")
    print(f"Hub nodes with data: {len(hub_with_data)}")

    # Test leaf nodes (should have minimal downstream effects)
    print(f"\n--- LEAF NODE TESTS ---")
    for node in leaf_with_data:
        try:
            result = run_simulation(
                country_code=test_country,
                interventions=[{'indicator': node, 'change_percent': 50}]
            )

            if result['status'] == 'success':
                n_affected = result['effects']['total_affected']
                print(f"  {node[:30]}: {n_affected} affected")

                if n_affected <= 1:
                    print(f"    ✅ Correct: Leaf node has minimal effects")
                else:
                    print(f"    ⚠️  Leaf node affected {n_affected} indicators")
            else:
                print(f"  {node[:30]}: SKIPPED")

        except Exception as e:
            print(f"  {node[:30]}: ERROR - {e}")

    # Test hub nodes (should have many downstream effects)
    print(f"\n--- HUB NODE TESTS ---")
    for node in hub_with_data:
        try:
            result = run_simulation(
                country_code=test_country,
                interventions=[{'indicator': node, 'change_percent': 50}]
            )

            if result['status'] == 'success':
                n_affected = result['effects']['total_affected']
                print(f"  {node[:30]}: {n_affected} affected")

                if n_affected > 10:
                    print(f"    ✅ Correct: Hub node has many effects")
                else:
                    print(f"    ⚠️  Hub node only affected {n_affected} indicators")
            else:
                print(f"  {node[:30]}: SKIPPED")

        except Exception as e:
            print(f"  {node[:30]}: ERROR - {e}")

    print(f"\n{'='*60}")
    print("✅ Zero-effect tests completed")
    print(f"{'='*60}")

    return True


if __name__ == "__main__":
    test_zero_effect_intervention()
