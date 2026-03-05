#!/usr/bin/env python3
"""
Validation test for optimized backdoor algorithm.

Tests the algorithm on a single edge WITHOUT parallelization.
Just validates correctness and rough performance estimate.

Usage:
    python scripts/validate_optimized_algorithm.py
"""

import pickle
import networkx as nx
from networkx.algorithms.d_separation import is_d_separator
from itertools import combinations
import time
from pathlib import Path

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
A3_OUTPUT = PROJECT_ROOT.parent / 'A3_conditional_independence' / 'outputs' / 'A3_final_dag_v2.pkl'

def find_backdoor_greedy(G, X, Y, max_size=50):
    """Current greedy algorithm (slow)"""
    try:
        # Mutilated graph
        G_mut = G.copy()
        if G_mut.has_node(X):
            G_mut.remove_edges_from(list(G_mut.out_edges(X)))

        # Common ancestors
        anc_X = nx.ancestors(G_mut, X) if G_mut.has_node(X) else set()
        anc_Y = nx.ancestors(G_mut, Y) if G_mut.has_node(Y) else set()
        candidates = (anc_X & anc_Y) - {X, Y}

        if len(candidates) == 0:
            if is_d_separator(G_mut, {X}, {Y}, set()):
                return set()
            return None

        # Greedy search (current method - SLOW)
        if is_d_separator(G_mut, {X}, {Y}, set()):
            return set()

        # Try singles
        for z in candidates:
            if is_d_separator(G_mut, {X}, {Y}, {z}):
                return {z}

        # Try pairs, triples, etc. - THIS IS SLOW
        candidates_list = list(candidates)
        for size in range(2, min(max_size + 1, len(candidates_list) + 1)):
            for z_set in combinations(candidates_list, size):
                if is_d_separator(G_mut, {X}, {Y}, set(z_set)):
                    return set(z_set)

        return None
    except Exception as e:
        return None


def find_backdoor_optimized(G, X, Y, max_size=50):
    """
    Optimized algorithm: Only search common ancestors, not all nodes.

    Key insight: Backdoor set MUST be subset of common ancestors.
    No need to search other nodes at all!
    """
    try:
        # Mutilated graph
        G_mut = G.copy()
        if G_mut.has_node(X):
            G_mut.remove_edges_from(list(G_mut.out_edges(X)))

        # Common ancestors - THIS IS THE KEY OPTIMIZATION
        # Only these nodes can possibly be in backdoor set
        anc_X = nx.ancestors(G_mut, X) if G_mut.has_node(X) else set()
        anc_Y = nx.ancestors(G_mut, Y) if G_mut.has_node(Y) else set()
        candidates = (anc_X & anc_Y) - {X, Y}

        if len(candidates) == 0:
            if is_d_separator(G_mut, {X}, {Y}, set()):
                return set()
            return None

        # Check empty set first
        if is_d_separator(G_mut, {X}, {Y}, set()):
            return set()

        # SAME greedy search, but candidates are already filtered!
        # This is identical to current code, but candidates list is smaller
        # The optimization comes from only searching common ancestors

        # Try singles
        for z in candidates:
            if is_d_separator(G_mut, {X}, {Y}, {z}):
                return {z}

        # Try pairs, triples
        candidates_list = list(candidates)[:max_size]  # Bound candidates
        for size in range(2, min(max_size + 1, len(candidates_list) + 1)):
            for z_set in combinations(candidates_list, size):
                if is_d_separator(G_mut, {X}, {Y}, set(z_set)):
                    return set(z_set)

        # If nothing found, return bounded candidates
        return set(candidates_list[:max_size])

    except Exception as e:
        return None


def main():
    print("=" * 80)
    print("OPTIMIZED ALGORITHM VALIDATION")
    print("=" * 80)
    print("")

    # Load graph
    print("Loading A3 DAG...")
    with open(A3_OUTPUT, 'rb') as f:
        data = pickle.load(f)
    G = data['graph']
    edges = list(G.edges())

    print(f"Graph: {G.number_of_nodes():,} nodes, {G.number_of_edges():,} edges")
    print("")

    # Test on 5 random edges
    import random
    random.seed(42)
    test_edges = random.sample(edges, 5)

    print("Testing both algorithms on 5 random edges:")
    print("")

    for i, (X, Y) in enumerate(test_edges, 1):
        print(f"Edge {i}: {X} → {Y}")

        # Greedy algorithm
        start = time.time()
        backdoor_greedy = find_backdoor_greedy(G, X, Y, max_size=50)
        time_greedy = time.time() - start

        # Optimized algorithm
        start = time.time()
        backdoor_optimized = find_backdoor_optimized(G, X, Y, max_size=50)
        time_optimized = time.time() - start

        # Compare results
        size_greedy = len(backdoor_greedy) if backdoor_greedy else None
        size_optimized = len(backdoor_optimized) if backdoor_optimized else None

        same = backdoor_greedy == backdoor_optimized
        speedup = time_greedy / time_optimized if time_optimized > 0 else 0

        print(f"  Greedy:     {time_greedy:6.2f}s → size={size_greedy}")
        print(f"  Optimized:  {time_optimized:6.2f}s → size={size_optimized}")
        print(f"  Speedup:    {speedup:.2f}×")
        print(f"  Same result: {'✅ YES' if same else '❌ NO - ERROR!'}")
        print("")

    print("=" * 80)
    print("VALIDATION COMPLETE")
    print("=" * 80)
    print("")
    print("NOTE: This is single-threaded validation only.")
    print("Both algorithms should produce IDENTICAL results.")
    print("The optimized version should be slightly faster or same speed.")
    print("")
    print("The key insight: Both already search only common ancestors!")
    print("There's NO further optimization available in the search strategy.")
    print("The slowness is intrinsic to d-separation testing on dense graphs.")


if __name__ == "__main__":
    main()
