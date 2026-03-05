#!/usr/bin/env python3
"""
A6 Hierarchical Layering - Main Pipeline (V2.1)

Assigns hierarchical layers to all nodes in the combined causal graph (A4 + A5)
using topological sort and computes centrality metrics.

V2.1 MODIFICATION: Uses v21_config for paths

Critical Features:
1. Virtual edge weight assignment (from A4/A5 betas)
2. Known outcome validation (≥70% in top 2 layers)
3. DAG validation with cycle detection

Runtime: 2-3 hours
"""

import pickle
import pandas as pd
import numpy as np
import networkx as nx
from datetime import datetime
from pathlib import Path
import logging
import sys

# V2.1 Configuration
sys.path.insert(0, str(Path(__file__).parent.parent))
from v21_config import A4_OUTPUT, A5_OUTPUT, A6_OUTPUT, LOG_DIR

# Setup logging
log_dir = LOG_DIR
log_dir.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_dir / 'a6_run.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Known outcomes for validation (from V1 + literature)
KNOWN_OUTCOMES = [
    'wdi_life_expectancy',
    'wdi_years_schooling',
    'wdi_gdp_per_capita',
    'wdi_infant_mortality',
    'wdi_gini_index',
    'wdi_homicides',
    'who_nutrition_index',
    'wdi_internet_access',
    'wdi_unemployment',
    'wdi_poverty_rate'
]

def load_data():
    """Load A4 edges and A5 interactions"""
    logger.info("=" * 70)
    logger.info("STEP 1: LOADING DATA")
    logger.info("=" * 70)

    # V2.1: Use config paths
    # Load A4
    logger.info("Loading A4 direct causal effects...")
    a4_path = A4_OUTPUT / 'lasso_effect_estimates.pkl'
    with open(a4_path, 'rb') as f:
        a4_data = pickle.load(f)
    df_a4 = pd.DataFrame(a4_data['validated_edges'])
    logger.info(f"  Loaded {len(df_a4):,} A4 edges from {a4_path}")

    # Load A5
    logger.info("Loading A5 mechanism interactions...")
    a5_path = A5_OUTPUT / 'A5_interaction_results.pkl'
    with open(a5_path, 'rb') as f:
        a5_data = pickle.load(f)
    df_a5 = pd.DataFrame(a5_data['validated_interactions'])
    logger.info(f"  Loaded {len(df_a5):,} A5 interactions from {a5_path}")

    logger.info("✅ Data loading complete\n")
    return df_a4, df_a5

def build_combined_graph(df_a4, df_a5):
    """
    Build combined NetworkX directed graph with interactions as EDGE METADATA.

    CRITICAL FIX (December 2025):
    - NO virtual INTERACT_ nodes created
    - Interactions stored as edge['moderators'] metadata on existing edges
    - This preserves real node count (not inflated by virtual nodes)

    For each A5 interaction (M1 × M2 → Outcome):
    - Find existing edge M1 → Outcome, add M2 to moderators list
    - Find existing edge M2 → Outcome, add M1 to moderators list
    - Store interaction beta, r², p-value as moderator metadata
    """
    logger.info("=" * 70)
    logger.info("STEP 2: BUILDING COMBINED GRAPH")
    logger.info("=" * 70)

    G = nx.DiGraph()

    # Add A4 edges (direct causal effects)
    logger.info("Adding A4 direct causal effects...")
    for _, row in df_a4.iterrows():
        G.add_edge(
            row['source'],
            row['target'],
            weight=abs(row['beta']),
            beta=row['beta'],
            ci_lower=row['ci_lower'],
            ci_upper=row['ci_upper'],
            edge_type='direct',
            moderators=[]  # Initialize empty moderators list
        )
    n_a4_edges = G.number_of_edges()
    logger.info(f"  Added {n_a4_edges:,} A4 direct edges")

    # Add A5 interactions as EDGE METADATA (NOT virtual nodes!)
    logger.info("Adding A5 interactions as edge metadata (NO virtual nodes)...")
    n_interactions_added = 0
    n_edges_with_moderators = 0
    n_new_edges_for_interactions = 0

    for _, row in df_a5.iterrows():
        m1 = row['mechanism_1']
        m2 = row['mechanism_2']
        outcome = row['outcome']
        beta3 = row['beta_interaction']

        # Create moderator metadata entry
        moderator_entry = {
            'moderator': None,  # Will be set per-edge
            'partner': None,    # The other mechanism in the interaction
            'beta_interaction': beta3,
            'r_squared': row['r_squared'],
            'p_value': row['p_value'],
            't_statistic': row.get('t_statistic', None)
        }

        # Add M2 as moderator on M1 → Outcome edge
        if G.has_edge(m1, outcome):
            mod_entry_m1 = moderator_entry.copy()
            mod_entry_m1['moderator'] = m2
            mod_entry_m1['partner'] = m1
            G[m1][outcome]['moderators'].append(mod_entry_m1)
            n_interactions_added += 1
        else:
            # Create new edge if direct effect not in A4
            G.add_edge(
                m1, outcome,
                weight=abs(beta3) / 2,  # Use interaction effect as proxy
                beta=None,  # No direct beta available
                edge_type='interaction_only',
                moderators=[{
                    'moderator': m2,
                    'partner': m1,
                    'beta_interaction': beta3,
                    'r_squared': row['r_squared'],
                    'p_value': row['p_value'],
                    't_statistic': row.get('t_statistic', None)
                }]
            )
            n_new_edges_for_interactions += 1
            n_interactions_added += 1

        # Add M1 as moderator on M2 → Outcome edge
        if G.has_edge(m2, outcome):
            mod_entry_m2 = moderator_entry.copy()
            mod_entry_m2['moderator'] = m1
            mod_entry_m2['partner'] = m2
            G[m2][outcome]['moderators'].append(mod_entry_m2)
            n_interactions_added += 1
        else:
            # Create new edge if direct effect not in A4
            G.add_edge(
                m2, outcome,
                weight=abs(beta3) / 2,
                beta=None,
                edge_type='interaction_only',
                moderators=[{
                    'moderator': m1,
                    'partner': m2,
                    'beta_interaction': beta3,
                    'r_squared': row['r_squared'],
                    'p_value': row['p_value'],
                    't_statistic': row.get('t_statistic', None)
                }]
            )
            n_new_edges_for_interactions += 1
            n_interactions_added += 1

    # Count edges with moderators
    for u, v, data in G.edges(data=True):
        if data.get('moderators') and len(data['moderators']) > 0:
            n_edges_with_moderators += 1

    logger.info(f"  ✅ NO virtual nodes created (interactions stored as edge metadata)")
    logger.info(f"  Interaction entries added: {n_interactions_added:,}")
    logger.info(f"  Edges with moderators: {n_edges_with_moderators:,}")
    logger.info(f"  New edges for interaction-only effects: {n_new_edges_for_interactions:,}")
    logger.info(f"  Total edges: {G.number_of_edges():,}")
    logger.info(f"  Total REAL nodes: {G.number_of_nodes():,}")

    # Verify no virtual nodes
    virtual_nodes = [n for n in G.nodes() if 'INTERACT_' in str(n)]
    if len(virtual_nodes) > 0:
        logger.error(f"❌ BUG: Found {len(virtual_nodes)} virtual INTERACT_ nodes!")
        raise ValueError("Virtual nodes should not exist - interactions must be edge metadata!")
    else:
        logger.info(f"  ✅ VERIFIED: 0 virtual INTERACT_ nodes (correct behavior)")

    # Edge weight distribution
    weights = [d['weight'] for _, _, d in G.edges(data=True)]
    logger.info(f"\n  Edge weight distribution:")
    logger.info(f"    Min: {np.min(weights):.4f}")
    logger.info(f"    Median: {np.median(weights):.4f}")
    logger.info(f"    Mean: {np.mean(weights):.4f}")
    logger.info(f"    Max: {np.max(weights):.4f}")

    logger.info("✅ Graph construction complete\n")
    return G

def validate_dag(G):
    """Validate directed acyclic graph properties"""
    logger.info("=" * 70)
    logger.info("STEP 3: VALIDATING DAG PROPERTIES")
    logger.info("=" * 70)

    # Check if DAG
    is_dag = nx.is_directed_acyclic_graph(G)
    logger.info(f"  Is DAG (no cycles): {is_dag}")

    if not is_dag:
        logger.error("❌ Graph contains cycles!")
        # Find cycles
        try:
            cycles = list(nx.simple_cycles(G))
            logger.error(f"   Found {len(cycles)} cycles")
            if len(cycles) > 0:
                logger.error(f"   First cycle: {cycles[0]}")
        except:
            pass
        raise ValueError("Graph contains cycles - cannot proceed with topological sort!")

    # Check connectivity
    n_components = nx.number_weakly_connected_components(G)
    logger.info(f"  Weakly connected components: {n_components}")

    if n_components > 5:
        logger.warning(f"⚠️  {n_components} disconnected components (expected ≤5)")
    else:
        logger.info(f"  ✅ Connectivity acceptable (≤5 components)")

    # Check for self-loops
    self_loops = list(nx.selfloop_edges(G))
    logger.info(f"  Self-loops: {len(self_loops)}")
    if len(self_loops) > 0:
        logger.warning(f"⚠️  Found {len(self_loops)} self-loops - removing")
        G.remove_edges_from(self_loops)

    logger.info("✅ DAG validation complete\n")
    return True

def assign_layers(G):
    """
    Apply topological sort to assign hierarchical layers.

    Layer assignment: layer[node] = max(layer[predecessor] + 1 for all predecessors)
    """
    logger.info("=" * 70)
    logger.info("STEP 4: ASSIGNING HIERARCHICAL LAYERS")
    logger.info("=" * 70)

    layers = {}

    # Find root nodes (in_degree == 0)
    roots = [n for n in G.nodes() if G.in_degree(n) == 0]
    logger.info(f"  Root nodes (drivers): {len(roots)}")

    for root in roots:
        layers[root] = 0

    # Assign layers via longest path from roots
    logger.info("  Assigning layers via topological sort...")
    for node in nx.topological_sort(G):
        if node not in layers:
            # Layer = max(predecessor layers) + 1
            pred_layers = [layers.get(pred, -1) for pred in G.predecessors(node)]
            if pred_layers:
                layers[node] = max(pred_layers) + 1
            else:
                layers[node] = 0

    n_layers = max(layers.values()) + 1
    logger.info(f"  ✅ Assigned {n_layers} hierarchical layers (0 to {n_layers-1})")

    # Layer size distribution
    layer_sizes = {i: 0 for i in range(n_layers)}
    for node, layer in layers.items():
        layer_sizes[layer] += 1

    logger.info(f"\n  Layer size distribution:")
    for layer in range(n_layers):
        logger.info(f"    Layer {layer}: {layer_sizes[layer]:,} nodes")

    # Validate layer assignments
    logger.info(f"\n  Validating layer consistency...")
    violations = 0
    for u, v in G.edges():
        if layers[u] >= layers[v]:
            violations += 1
            if violations <= 5:
                logger.warning(f"    ⚠️  Edge {u} (L{layers[u]}) → {v} (L{layers[v]}) violates ordering")

    if violations > 0:
        logger.error(f"❌ Found {violations} layer ordering violations!")
        raise ValueError("Layer assignment violated edge ordering constraint!")
    else:
        logger.info(f"  ✅ All edges satisfy layer ordering (source < target)")

    logger.info("✅ Layer assignment complete\n")
    return layers, n_layers

def compute_centrality(G):
    """Compute centrality metrics with weighted PageRank"""
    logger.info("=" * 70)
    logger.info("STEP 5: COMPUTING CENTRALITY METRICS")
    logger.info("=" * 70)

    centrality = {}

    # PageRank (weighted by edge beta)
    logger.info("  Computing PageRank (weighted)...")
    centrality['pagerank'] = nx.pagerank(G, weight='weight', max_iter=100)
    logger.info(f"    Converged: {len(centrality['pagerank']):,} nodes")

    # Betweenness centrality (this is slow for large graphs)
    logger.info("  Computing Betweenness centrality...")
    logger.info("    (This may take 30-60 minutes for 4K+ nodes)")
    centrality['betweenness'] = nx.betweenness_centrality(G, weight='weight')
    logger.info(f"    Completed: {len(centrality['betweenness']):,} nodes")

    # Degree centrality
    logger.info("  Computing Degree centrality...")
    centrality['in_degree'] = dict(G.in_degree())
    centrality['out_degree'] = dict(G.out_degree())
    logger.info(f"    In-degree: {len(centrality['in_degree']):,} nodes")
    logger.info(f"    Out-degree: {len(centrality['out_degree']):,} nodes")

    # Summary statistics
    logger.info(f"\n  Centrality distributions:")
    logger.info(f"    PageRank - Min: {min(centrality['pagerank'].values()):.6f}, "
                f"Max: {max(centrality['pagerank'].values()):.6f}")
    logger.info(f"    Betweenness - Min: {min(centrality['betweenness'].values()):.6f}, "
                f"Max: {max(centrality['betweenness'].values()):.6f}")
    logger.info(f"    In-degree - Min: {min(centrality['in_degree'].values())}, "
                f"Max: {max(centrality['in_degree'].values())}")
    logger.info(f"    Out-degree - Min: {min(centrality['out_degree'].values())}, "
                f"Max: {max(centrality['out_degree'].values())}")

    logger.info("✅ Centrality computation complete\n")
    return centrality

def validate_known_outcomes(layers, n_layers):
    """
    CRITICAL ADDITION 2: Validate Known Outcome Placement

    Check that ≥70% of known outcomes are in top 2 layers.
    """
    logger.info("=" * 70)
    logger.info("STEP 6: VALIDATING KNOWN OUTCOME PLACEMENT")
    logger.info("=" * 70)

    top_2_layers = set([n_layers - 1, n_layers - 2])

    found_outcomes = []
    missing_outcomes = []
    outcome_layers = {}

    for outcome in KNOWN_OUTCOMES:
        if outcome in layers:
            found_outcomes.append(outcome)
            outcome_layers[outcome] = layers[outcome]
        else:
            missing_outcomes.append(outcome)

    logger.info(f"  Known outcomes in graph: {len(found_outcomes)} / {len(KNOWN_OUTCOMES)}")

    if len(missing_outcomes) > 0:
        logger.warning(f"  ⚠️  Missing outcomes: {missing_outcomes}")

    # Check placement in top 2 layers
    in_top_2 = sum(1 for outcome in found_outcomes if layers[outcome] in top_2_layers)
    pct_in_top_2 = in_top_2 / len(found_outcomes) if len(found_outcomes) > 0 else 0

    logger.info(f"\n  Outcome layer placement:")
    for outcome in sorted(found_outcomes, key=lambda x: layers[x], reverse=True):
        layer = layers[outcome]
        in_top = "✅" if layer in top_2_layers else "⚠️ "
        logger.info(f"    {in_top} {outcome}: Layer {layer}/{n_layers-1}")

    logger.info(f"\n  Outcomes in top 2 layers: {in_top_2}/{len(found_outcomes)} ({pct_in_top_2:.1%})")

    # Check bottom 50% constraint
    bottom_50_threshold = n_layers * 0.50
    in_bottom_50 = sum(1 for outcome in found_outcomes if layers[outcome] < bottom_50_threshold)

    logger.info(f"  Outcomes in bottom 50%: {in_bottom_50}/{len(found_outcomes)}")

    # Validate success criteria
    if pct_in_top_2 >= 0.70:
        logger.info(f"  ✅ SUCCESS: {pct_in_top_2:.1%} of outcomes in top 2 layers (≥70% required)")
    else:
        logger.warning(f"  ⚠️  WARNING: Only {pct_in_top_2:.1%} in top 2 layers (≥70% required)")

    if in_bottom_50 > 0:
        logger.warning(f"  ⚠️  WARNING: {in_bottom_50} outcomes in bottom 50% (should be 0)")
    else:
        logger.info(f"  ✅ SUCCESS: No outcomes in bottom 50%")

    logger.info("✅ Known outcome validation complete\n")

    return {
        'found_outcomes': found_outcomes,
        'missing_outcomes': missing_outcomes,
        'outcome_layers': outcome_layers,
        'pct_in_top_2': pct_in_top_2,
        'n_in_bottom_50': in_bottom_50
    }

def export_results(G, layers, n_layers, centrality, outcome_validation):
    """Export hierarchical graph with metadata"""
    logger.info("=" * 70)
    logger.info("STEP 7: EXPORTING RESULTS")
    logger.info("=" * 70)

    # Prepare output
    output = {
        'graph': G,
        'layers': layers,
        'n_layers': n_layers,
        'centrality': centrality,
        'outcome_validation': outcome_validation,
        'metadata': {
            'n_nodes': G.number_of_nodes(),
            'n_edges': G.number_of_edges(),
            'n_layers': n_layers,
            'n_components': nx.number_weakly_connected_components(G),
            'avg_degree': sum(dict(G.degree()).values()) / G.number_of_nodes(),
            'timestamp': datetime.now().isoformat()
        }
    }

    # V2.1: Use config path
    output_dir = A6_OUTPUT
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save primary output
    output_file = output_dir / 'A6_hierarchical_graph.pkl'
    with open(output_file, 'wb') as f:
        pickle.dump(output, f)
    logger.info(f"  ✅ Saved hierarchical graph: {output_file}")

    # Export layer assignments to CSV
    df_layers = pd.DataFrame([
        {'node': node, 'layer': layer, 'pagerank': centrality['pagerank'][node],
         'betweenness': centrality['betweenness'][node],
         'in_degree': centrality['in_degree'][node],
         'out_degree': centrality['out_degree'][node]}
        for node, layer in layers.items()
    ])
    csv_file = output_dir / 'A6_layer_assignments.csv'
    df_layers.to_csv(csv_file, index=False)
    logger.info(f"  ✅ Saved layer assignments: {csv_file}")

    # Export graph statistics
    stats_file = output_dir / 'A6_graph_statistics.txt'
    with open(stats_file, 'w') as f:
        f.write("A6 HIERARCHICAL LAYERING - GRAPH STATISTICS\n")
        f.write("=" * 70 + "\n\n")
        f.write(f"Timestamp: {datetime.now().isoformat()}\n\n")
        f.write(f"Graph Structure:\n")
        f.write(f"  Total nodes: {G.number_of_nodes():,}\n")
        f.write(f"  Total edges: {G.number_of_edges():,}\n")
        f.write(f"  Hierarchical layers: {n_layers}\n")
        f.write(f"  Weakly connected components: {nx.number_weakly_connected_components(G)}\n")
        f.write(f"  Average degree: {sum(dict(G.degree()).values()) / G.number_of_nodes():.2f}\n\n")

        f.write(f"Layer Distribution:\n")
        layer_sizes = {i: sum(1 for n, l in layers.items() if l == i) for i in range(n_layers)}
        for layer, size in layer_sizes.items():
            f.write(f"  Layer {layer}: {size:,} nodes\n")

        f.write(f"\nKnown Outcome Validation:\n")
        f.write(f"  Outcomes found: {len(outcome_validation['found_outcomes'])} / {len(KNOWN_OUTCOMES)}\n")
        f.write(f"  In top 2 layers: {outcome_validation['pct_in_top_2']:.1%}\n")
        f.write(f"  In bottom 50%: {outcome_validation['n_in_bottom_50']}\n")

    logger.info(f"  ✅ Saved graph statistics: {stats_file}")

    logger.info("✅ Export complete\n")

def main():
    """Main pipeline"""
    start_time = datetime.now()

    logger.info("\n" + "=" * 70)
    logger.info("A6 HIERARCHICAL LAYERING - STARTING")
    logger.info("=" * 70)
    logger.info(f"Start time: {start_time.isoformat()}\n")

    try:
        # Step 1: Load data
        df_a4, df_a5 = load_data()

        # Step 2: Build combined graph
        G = build_combined_graph(df_a4, df_a5)

        # Step 3: Validate DAG
        validate_dag(G)

        # Step 4: Assign layers
        layers, n_layers = assign_layers(G)

        # Step 5: Compute centrality
        centrality = compute_centrality(G)

        # Step 6: Validate known outcomes
        outcome_validation = validate_known_outcomes(layers, n_layers)

        # Step 7: Export results
        export_results(G, layers, n_layers, centrality, outcome_validation)

        # Final summary
        end_time = datetime.now()
        runtime = (end_time - start_time).total_seconds() / 3600

        logger.info("=" * 70)
        logger.info("A6 HIERARCHICAL LAYERING - COMPLETE ✅")
        logger.info("=" * 70)
        logger.info(f"End time: {end_time.isoformat()}")
        logger.info(f"Runtime: {runtime:.2f} hours")
        logger.info(f"\nFinal Statistics:")
        logger.info(f"  Nodes: {G.number_of_nodes():,}")
        logger.info(f"  Edges: {G.number_of_edges():,}")
        logger.info(f"  Layers: {n_layers}")
        logger.info(f"  Outcomes in top 2: {outcome_validation['pct_in_top_2']:.1%}")
        logger.info(f"\n✅ Ready for Phase B!")

    except Exception as e:
        logger.error(f"\n❌ A6 FAILED: {str(e)}", exc_info=True)
        raise

if __name__ == "__main__":
    main()
