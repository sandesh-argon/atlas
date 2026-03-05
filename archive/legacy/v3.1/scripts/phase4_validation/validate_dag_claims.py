#!/usr/bin/env python3
"""
DAG Validation - Re-check that graphs are actually DAGs.
"""

import json
from pathlib import Path

try:
    import networkx as nx
    HAS_NETWORKX = True
except ImportError:
    HAS_NETWORKX = False

BASE_DIR = Path("<repo-root>/v3.1")

def verify_dag_validation():
    """Re-check DAG validation claims."""

    if not HAS_NETWORKX:
        print("⚠️  networkx not installed, skipping DAG verification")
        return 0

    false_claims = []
    total_files = 0

    unified_dir = BASE_DIR / 'data/v3_1_temporal_graphs/unified'

    for year in range(1990, 2025):
        file = unified_dir / f'{year}_graph.json'
        if not file.exists():
            continue

        total_files += 1

        with open(file) as f:
            data = json.load(f)

        # Build graph
        G = nx.DiGraph()
        for edge in data['edges']:
            G.add_edge(edge['source'], edge['target'])

        # Check for cycles
        try:
            cycles = list(nx.simple_cycles(G))
            has_cycles = len(cycles) > 0
        except Exception as e:
            has_cycles = True
            cycles = [f'error: {e}']

        # Compare with claim
        claimed_dag = data['metadata'].get('dag_validated', False)

        if claimed_dag and has_cycles:
            false_claims.append({
                'year': year,
                'claimed': 'DAG',
                'actual': 'HAS CYCLES',
                'n_cycles': len(cycles),
                'example_cycle': cycles[0][:5] if cycles and isinstance(cycles[0], list) else str(cycles[0])
            })
        elif not claimed_dag and not has_cycles:
            false_claims.append({
                'year': year,
                'claimed': 'NOT DAG',
                'actual': 'IS DAG',
                'n_cycles': 0
            })

    print(f"\n{'='*60}")
    print("DAG VALIDATION VERIFICATION")
    print(f"{'='*60}")
    print(f"Files checked: {total_files}")
    print(f"False claims: {len(false_claims)}")

    if false_claims:
        print("\n❌ Incorrect DAG Validation Claims:")
        for claim in false_claims:
            print(f"  Year {claim['year']}: Claimed {claim['claimed']}, Actually {claim['actual']}")
            if claim.get('example_cycle'):
                print(f"    Example cycle: {claim['example_cycle']}")
    else:
        print("\n✅ PASS: All DAG validations are accurate")

    return len(false_claims)

if __name__ == '__main__':
    verify_dag_validation()
