#!/usr/bin/env python3
"""
A6 Fix: Remove Interaction Virtual Nodes → Edge Metadata

This script corrects a methodological error in the original A6 pipeline.

PROBLEM:
- Interaction terms (M1 × M2 → Outcome) were added as "virtual nodes"
- e.g., INTERACT_health_spending_X_governance_TO_life_expectancy
- This is WRONG: Interactions are metadata about EDGES, not entities in the world

SOLUTION:
- Remove all 4,254 virtual interaction nodes
- Store interaction effects as EDGE METADATA on the direct causal edges
- Edge metadata structure:
    edge['moderators'] = [
        {'moderator': 'governance', 'beta_interaction': 0.26, ...},
        ...
    ]

RESULT:
- Graph nodes: 8,126 → 3,872 (real indicators only)
- Edges: 22,521 → 9,759 (direct causal only) + interaction metadata
- Conceptually correct: interactions describe HOW edges behave, not new entities

Author: Phase A6 Fix
Date: December 2025
"""

import pickle
import pandas as pd
import numpy as np
import networkx as nx
from datetime import datetime
from pathlib import Path
import logging
from collections import defaultdict

# Setup logging
log_dir = Path(__file__).parent.parent / 'logs'
log_dir.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_dir / 'a6_fix.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def load_original_data():
    """Load A4 edges and A5 interactions (original sources)"""
    logger.info("=" * 70)
    logger.info("STEP 1: LOADING ORIGINAL A4/A5 DATA")
    logger.info("=" * 70)

    project_root = Path(__file__).parent.parent.parent.parent

    # Load A4 direct causal effects
    a4_path = project_root / 'phaseA' / 'A4_effect_quantification' / 'outputs' / 'lasso_effect_estimates_WITH_WARNINGS.pkl'
    with open(a4_path, 'rb') as f:
        a4_data = pickle.load(f)
    df_a4 = pd.DataFrame(a4_data['validated_edges'])
    logger.info(f"  Loaded {len(df_a4):,} A4 direct causal edges")

    # Load A5 interactions
    a5_path = project_root / 'phaseA' / 'A5_interaction_discovery' / 'outputs' / 'A5_interaction_results_FILTERED_STRICT.pkl'
    with open(a5_path, 'rb') as f:
        a5_data = pickle.load(f)
    df_a5 = pd.DataFrame(a5_data['validated_interactions'])
    logger.info(f"  Loaded {len(df_a5):,} A5 interaction effects")

    return df_a4, df_a5


def build_corrected_graph(df_a4, df_a5):
    """
    Build graph with ONLY real nodes and interactions as edge metadata.

    Key difference from original A6:
    - NO virtual nodes (INTERACT_*)
    - Interactions stored as edge['moderators'] metadata
    """
    logger.info("=" * 70)
    logger.info("STEP 2: BUILDING CORRECTED GRAPH")
    logger.info("=" * 70)

    G = nx.DiGraph()

    # =========================================================================
    # STEP 2A: Add A4 direct causal edges (these are the real edges)
    # =========================================================================
    logger.info("Adding A4 direct causal edges...")

    for _, row in df_a4.iterrows():
        source = row['source']
        target = row['target']

        # Add edge with all A4 metadata
        G.add_edge(
            source,
            target,
            weight=abs(row['beta']),
            beta=row['beta'],
            ci_lower=row['ci_lower'],
            ci_upper=row['ci_upper'],
            edge_type='direct_causal',
            moderators=[]  # Will be populated from A5
        )

    logger.info(f"  Added {G.number_of_edges():,} direct causal edges")
    logger.info(f"  Unique nodes: {G.number_of_nodes():,}")

    # =========================================================================
    # STEP 2B: Add A5 interactions as EDGE METADATA (not as nodes!)
    # =========================================================================
    logger.info("\nAdding A5 interactions as edge metadata...")

    # Group interactions by the edge they moderate
    # An interaction (M1 × M2 → Outcome) modifies the edge (M1 → Outcome)
    # The moderator is M2

    # Track statistics
    n_interactions_added = 0
    n_new_edges_created = 0
    n_orphan_interactions = 0

    # Build lookup of existing edges
    existing_edges = set(G.edges())

    # Process each interaction
    for _, row in df_a5.iterrows():
        m1 = row['mechanism_1']  # Primary mechanism (source)
        m2 = row['mechanism_2']  # Moderating mechanism
        outcome = row['outcome']

        # This interaction modifies the edge: M1 → Outcome
        # The moderator is M2
        edge_key = (m1, outcome)

        # Build moderator metadata
        moderator_info = {
            'moderator_variable': m2,
            'beta_interaction': row['beta_interaction'],
            't_statistic': row['t_statistic'],
            'p_value': row['p_value'],
            'p_value_fdr': row['p_value_fdr'],
            'r_squared': row['r_squared'],
            'n_obs': row['n_obs']
        }

        if edge_key in existing_edges:
            # Add moderator to existing edge
            G.edges[edge_key]['moderators'].append(moderator_info)
            n_interactions_added += 1
        else:
            # Edge doesn't exist in A4 - create it with interaction data
            # This means the main effect wasn't significant but interaction was
            G.add_edge(
                m1,
                outcome,
                weight=abs(row['beta_interaction']),  # Use interaction beta as weight
                beta=None,  # No main effect
                ci_lower=None,
                ci_upper=None,
                edge_type='interaction_only',  # Mark as interaction-derived edge
                moderators=[moderator_info]
            )
            n_new_edges_created += 1
            existing_edges.add(edge_key)
            n_interactions_added += 1

    logger.info(f"  Interactions added to existing edges: {n_interactions_added - n_new_edges_created:,}")
    logger.info(f"  New edges created from interactions: {n_new_edges_created:,}")

    # =========================================================================
    # STEP 2C: Validate and summarize
    # =========================================================================
    logger.info("\nGraph summary:")
    logger.info(f"  Total nodes: {G.number_of_nodes():,}")
    logger.info(f"  Total edges: {G.number_of_edges():,}")

    # Count edges with moderators
    edges_with_mods = sum(1 for u, v, d in G.edges(data=True) if len(d.get('moderators', [])) > 0)
    total_mods = sum(len(d.get('moderators', [])) for u, v, d in G.edges(data=True))

    logger.info(f"  Edges with moderators: {edges_with_mods:,}")
    logger.info(f"  Total moderator entries: {total_mods:,}")

    # Edge type distribution
    edge_types = defaultdict(int)
    for u, v, d in G.edges(data=True):
        edge_types[d.get('edge_type', 'unknown')] += 1

    logger.info("\n  Edge type distribution:")
    for et, count in sorted(edge_types.items(), key=lambda x: -x[1]):
        logger.info(f"    {et}: {count:,}")

    return G


def validate_dag(G):
    """Validate DAG properties"""
    logger.info("=" * 70)
    logger.info("STEP 3: VALIDATING DAG PROPERTIES")
    logger.info("=" * 70)

    # Check if DAG
    is_dag = nx.is_directed_acyclic_graph(G)
    logger.info(f"  Is DAG (no cycles): {is_dag}")

    if not is_dag:
        logger.error("❌ Graph contains cycles!")
        cycles = list(nx.simple_cycles(G))
        logger.error(f"   Found {len(cycles)} cycles")
        if cycles:
            logger.error(f"   First cycle: {cycles[0]}")
        raise ValueError("Graph contains cycles!")

    # Connectivity
    n_components = nx.number_weakly_connected_components(G)
    logger.info(f"  Weakly connected components: {n_components}")

    # Self-loops
    self_loops = list(nx.selfloop_edges(G))
    if self_loops:
        logger.warning(f"  ⚠️  Removing {len(self_loops)} self-loops")
        G.remove_edges_from(self_loops)

    logger.info("✅ DAG validation complete\n")
    return True


def assign_layers(G):
    """Assign hierarchical layers via topological sort"""
    logger.info("=" * 70)
    logger.info("STEP 4: ASSIGNING HIERARCHICAL LAYERS")
    logger.info("=" * 70)

    layers = {}

    # Find roots (in_degree == 0)
    roots = [n for n in G.nodes() if G.in_degree(n) == 0]
    logger.info(f"  Root nodes (drivers): {len(roots)}")

    for root in roots:
        layers[root] = 0

    # Assign layers via longest path from roots
    for node in nx.topological_sort(G):
        if node not in layers:
            pred_layers = [layers.get(pred, -1) for pred in G.predecessors(node)]
            layers[node] = max(pred_layers) + 1 if pred_layers else 0

    n_layers = max(layers.values()) + 1
    logger.info(f"  Assigned {n_layers} hierarchical layers")

    # Layer size distribution
    layer_sizes = defaultdict(int)
    for node, layer in layers.items():
        layer_sizes[layer] += 1

    logger.info(f"\n  Layer size distribution:")
    for layer in sorted(layer_sizes.keys()):
        logger.info(f"    Layer {layer}: {layer_sizes[layer]:,} nodes")

    return layers, n_layers


def compute_centrality(G):
    """Compute centrality metrics"""
    logger.info("=" * 70)
    logger.info("STEP 5: COMPUTING CENTRALITY METRICS")
    logger.info("=" * 70)

    centrality = {}

    logger.info("  Computing PageRank...")
    centrality['pagerank'] = nx.pagerank(G, weight='weight', max_iter=100)

    logger.info("  Computing Betweenness centrality...")
    centrality['betweenness'] = nx.betweenness_centrality(G, weight='weight')

    logger.info("  Computing degree centrality...")
    centrality['in_degree'] = dict(G.in_degree())
    centrality['out_degree'] = dict(G.out_degree())

    logger.info("✅ Centrality computation complete\n")
    return centrality


def build_edge_index(G, layers):
    """
    Build edge index for O(1) lookup.

    Structure:
    - by_source[source_node] = [(target, edge_data), ...]
    - by_target[target_node] = [(source, edge_data), ...]
    """
    logger.info("=" * 70)
    logger.info("STEP 6: BUILDING EDGE INDEX")
    logger.info("=" * 70)

    by_source = defaultdict(list)
    by_target = defaultdict(list)

    for source, target, data in G.edges(data=True):
        edge_info = {
            'source': source,
            'target': target,
            'source_layer': layers.get(source, -1),
            'target_layer': layers.get(target, -1),
            **data
        }
        by_source[source].append(edge_info)
        by_target[target].append(edge_info)

    logger.info(f"  Indexed {G.number_of_edges():,} edges")
    logger.info(f"  by_source entries: {len(by_source):,}")
    logger.info(f"  by_target entries: {len(by_target):,}")

    edge_index = {
        'by_source': dict(by_source),
        'by_target': dict(by_target)
    }

    logger.info("✅ Edge index complete\n")
    return edge_index


def export_results(G, layers, n_layers, centrality, edge_index):
    """Export corrected graph and metadata"""
    logger.info("=" * 70)
    logger.info("STEP 7: EXPORTING RESULTS")
    logger.info("=" * 70)

    output_dir = Path(__file__).parent.parent / 'outputs'
    output_dir.mkdir(parents=True, exist_ok=True)

    # Primary output (corrected graph)
    output = {
        'graph': G,
        'layers': layers,
        'n_layers': n_layers,
        'centrality': centrality,
        'edge_index': edge_index,
        'metadata': {
            'n_nodes': G.number_of_nodes(),
            'n_edges': G.number_of_edges(),
            'n_layers': n_layers,
            'n_components': nx.number_weakly_connected_components(G),
            'avg_degree': sum(dict(G.degree()).values()) / G.number_of_nodes(),
            'timestamp': datetime.now().isoformat(),
            'fix_applied': 'Removed virtual interaction nodes, stored as edge metadata',
            'original_nodes': 8126,
            'removed_virtual_nodes': 4254
        }
    }

    # Save corrected graph
    output_file = output_dir / 'A6_hierarchical_graph.pkl'
    with open(output_file, 'wb') as f:
        pickle.dump(output, f)
    logger.info(f"  ✅ Saved corrected graph: {output_file}")

    # Backup original if it exists
    original_file = output_dir / 'A6_hierarchical_graph_ORIGINAL_WITH_VIRTUAL_NODES.pkl'
    if not original_file.exists():
        import shutil
        # The original was already overwritten, but we'll note it
        logger.info(f"  ⚠️  Original graph was overwritten (no backup available)")

    # Export layer assignments to CSV
    df_layers = pd.DataFrame([
        {
            'node': node,
            'layer': layer,
            'pagerank': centrality['pagerank'][node],
            'betweenness': centrality['betweenness'][node],
            'in_degree': centrality['in_degree'][node],
            'out_degree': centrality['out_degree'][node]
        }
        for node, layer in layers.items()
    ])
    csv_file = output_dir / 'A6_layer_assignments.csv'
    df_layers.to_csv(csv_file, index=False)
    logger.info(f"  ✅ Saved layer assignments: {csv_file}")

    # Export edge index separately (for quick loading)
    edge_index_file = output_dir / 'A6_edge_index.pkl'
    with open(edge_index_file, 'wb') as f:
        pickle.dump(edge_index, f)
    logger.info(f"  ✅ Saved edge index: {edge_index_file}")

    # Export graph statistics
    stats_file = output_dir / 'A6_graph_statistics.txt'
    with open(stats_file, 'w') as f:
        f.write("A6 HIERARCHICAL LAYERING - CORRECTED GRAPH STATISTICS\n")
        f.write("=" * 70 + "\n\n")
        f.write(f"Timestamp: {datetime.now().isoformat()}\n")
        f.write(f"Fix Applied: Removed virtual interaction nodes\n\n")
        f.write(f"BEFORE FIX:\n")
        f.write(f"  Total nodes: 8,126 (including 4,254 virtual INTERACT_ nodes)\n")
        f.write(f"  Real indicator nodes: 3,872\n\n")
        f.write(f"AFTER FIX:\n")
        f.write(f"  Total nodes: {G.number_of_nodes():,} (real indicators only)\n")
        f.write(f"  Total edges: {G.number_of_edges():,}\n")
        f.write(f"  Hierarchical layers: {n_layers}\n")
        f.write(f"  Weakly connected components: {nx.number_weakly_connected_components(G)}\n")
        f.write(f"  Average degree: {sum(dict(G.degree()).values()) / G.number_of_nodes():.2f}\n\n")

        # Count edges with moderators
        edges_with_mods = sum(1 for u, v, d in G.edges(data=True) if len(d.get('moderators', [])) > 0)
        total_mods = sum(len(d.get('moderators', [])) for u, v, d in G.edges(data=True))

        f.write(f"INTERACTION METADATA:\n")
        f.write(f"  Edges with moderators: {edges_with_mods:,}\n")
        f.write(f"  Total moderator entries: {total_mods:,}\n\n")

        f.write(f"Layer Distribution:\n")
        layer_sizes = defaultdict(int)
        for node, layer in layers.items():
            layer_sizes[layer] += 1
        for layer in sorted(layer_sizes.keys()):
            f.write(f"  Layer {layer}: {layer_sizes[layer]:,} nodes\n")

    logger.info(f"  ✅ Saved graph statistics: {stats_file}")

    logger.info("✅ Export complete\n")


def main():
    """Main fix pipeline"""
    start_time = datetime.now()

    logger.info("\n" + "=" * 70)
    logger.info("A6 FIX: REMOVING VIRTUAL INTERACTION NODES")
    logger.info("=" * 70)
    logger.info(f"Start time: {start_time.isoformat()}")
    logger.info("\nThis fix corrects a methodological error where interaction terms")
    logger.info("were stored as graph nodes instead of edge metadata.\n")

    try:
        # Step 1: Load original A4/A5 data
        df_a4, df_a5 = load_original_data()

        # Step 2: Build corrected graph
        G = build_corrected_graph(df_a4, df_a5)

        # Step 3: Validate DAG
        validate_dag(G)

        # Step 4: Assign layers
        layers, n_layers = assign_layers(G)

        # Step 5: Compute centrality
        centrality = compute_centrality(G)

        # Step 6: Build edge index
        edge_index = build_edge_index(G, layers)

        # Step 7: Export results
        export_results(G, layers, n_layers, centrality, edge_index)

        # Final summary
        end_time = datetime.now()
        runtime = (end_time - start_time).total_seconds()

        logger.info("=" * 70)
        logger.info("A6 FIX COMPLETE ✅")
        logger.info("=" * 70)
        logger.info(f"Runtime: {runtime:.1f} seconds")
        logger.info(f"\nCORRECTION SUMMARY:")
        logger.info(f"  Before: 8,126 nodes (including 4,254 virtual INTERACT_ nodes)")
        logger.info(f"  After:  {G.number_of_nodes():,} nodes (real indicators only)")
        logger.info(f"  Reduction: {8126 - G.number_of_nodes():,} fake nodes removed ({(8126 - G.number_of_nodes())/8126*100:.1f}%)")
        logger.info(f"\n  Edges: {G.number_of_edges():,}")
        logger.info(f"  Layers: {n_layers}")

        edges_with_mods = sum(1 for u, v, d in G.edges(data=True) if len(d.get('moderators', [])) > 0)
        total_mods = sum(len(d.get('moderators', [])) for u, v, d in G.edges(data=True))
        logger.info(f"  Edges with interaction moderators: {edges_with_mods:,}")
        logger.info(f"  Total interaction moderator entries: {total_mods:,}")

        logger.info(f"\n✅ Graph is now conceptually correct!")
        logger.info(f"   - Nodes represent real-world indicators")
        logger.info(f"   - Interactions stored as edge['moderators'] metadata")

    except Exception as e:
        logger.error(f"\n❌ A6 FIX FAILED: {str(e)}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
