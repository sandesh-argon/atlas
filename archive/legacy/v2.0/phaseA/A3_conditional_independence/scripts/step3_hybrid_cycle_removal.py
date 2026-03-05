#!/usr/bin/env python3
"""
A3 Step 3: Hybrid Cycle Removal

Strategy:
1. Identify bidirectional Granger pairs (feedback loops)
2. Keep stronger direction, remove weaker
3. Apply weighted FAS to remaining cycles (minimize sum of F-statistics removed)

This preserves important feedback loops while creating a valid DAG.
"""

import pickle
import pandas as pd
import numpy as np
import networkx as nx
from pathlib import Path
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def load_data():
    """Load PC-Stable validated edges and A2 Granger edges"""
    logger.info("="*80)
    logger.info("LOADING DATA")
    logger.info("="*80)

    # Load PC-Stable validated edges
    pc_file = Path(__file__).parent.parent / 'outputs' / 'A3_validated_fisher_z_v2.pkl'
    logger.info(f"Loading PC-Stable edges from: {pc_file}")

    with open(pc_file, 'rb') as f:
        pc_data = pickle.load(f)

    validated_edges = pc_data['validated_edges']
    logger.info(f"  Loaded {len(validated_edges):,} PC-Stable validated edges")

    # Load A2 Granger edges (for bidirectional pair detection)
    a2_file = Path(__file__).parent.parent.parent / 'A2_granger_causality' / 'outputs' / 'granger_fdr_corrected.pkl'
    logger.info(f"Loading A2 Granger edges from: {a2_file}")

    with open(a2_file, 'rb') as f:
        a2_data = pickle.load(f)

    a2_edges = a2_data['results'][a2_data['results']['significant_fdr_001']].copy()
    logger.info(f"  Loaded {len(a2_edges):,} A2 Granger edges (q<0.01)")

    return validated_edges, a2_edges

def find_bidirectional_pairs(validated_edges, a2_edges):
    """
    Find bidirectional Granger pairs that survived PC-Stable
    These are feedback loops where both X→Y and Y→X were Granger-significant
    """
    logger.info("\n" + "="*80)
    logger.info("STEP 3A: IDENTIFY BIDIRECTIONAL PAIRS (FEEDBACK LOOPS)")
    logger.info("="*80)

    # Create lookup for PC-Stable validated edges
    validated_set = set(
        (row['source'], row['target'])
        for _, row in validated_edges.iterrows()
    )

    # Find bidirectional pairs in A2 that both survived PC-Stable
    bidirectional_pairs = []
    checked_pairs = set()

    for _, edge in validated_edges.iterrows():
        source = edge['source']
        target = edge['target']

        # Check if reverse edge exists in validated edges
        reverse_edge = (target, source)

        if reverse_edge in validated_set:
            # Found bidirectional pair
            pair = tuple(sorted([source, target]))

            if pair not in checked_pairs:
                checked_pairs.add(pair)

                # Get F-statistics from validated edges
                fwd = validated_edges[
                    (validated_edges['source'] == source) &
                    (validated_edges['target'] == target)
                ]['f_statistic'].values[0]

                rev = validated_edges[
                    (validated_edges['source'] == target) &
                    (validated_edges['target'] == source)
                ]['f_statistic'].values[0]

                bidirectional_pairs.append({
                    'var1': source,
                    'var2': target,
                    'f_stat_1to2': fwd,
                    'f_stat_2to1': rev,
                    'stronger_direction': (source, target) if fwd > rev else (target, source),
                    'weaker_direction': (target, source) if fwd > rev else (source, target),
                    'f_diff': abs(fwd - rev)
                })

    bidirectional_df = pd.DataFrame(bidirectional_pairs)

    logger.info(f"\nFound {len(bidirectional_df)} bidirectional pairs (feedback loops)")

    if len(bidirectional_df) > 0:
        logger.info(f"\nF-statistic difference distribution:")
        logger.info(f"  Mean: {bidirectional_df['f_diff'].mean():.2f}")
        logger.info(f"  Median: {bidirectional_df['f_diff'].median():.2f}")
        logger.info(f"  Max: {bidirectional_df['f_diff'].max():.2f}")

        # Sample
        logger.info(f"\nTop 10 feedback loops by F-stat difference:")
        top10 = bidirectional_df.nlargest(10, 'f_diff')
        for idx, row in top10.iterrows():
            stronger = row['stronger_direction']
            logger.info(f"  {stronger[0]:40s} → {stronger[1]:40s} | F_diff={row['f_diff']:.1f}")

    return bidirectional_df

def remove_weaker_feedback_directions(validated_edges, bidirectional_df):
    """
    Remove weaker direction from each bidirectional pair
    Keep stronger direction
    """
    logger.info("\n" + "="*80)
    logger.info("REMOVING WEAKER FEEDBACK DIRECTIONS")
    logger.info("="*80)

    if len(bidirectional_df) == 0:
        logger.info("  No bidirectional pairs to process")
        return validated_edges.copy()

    # Create list of edges to remove (weaker directions)
    edges_to_remove = set(
        row['weaker_direction']
        for _, row in bidirectional_df.iterrows()
    )

    logger.info(f"  Removing {len(edges_to_remove):,} weaker feedback directions")

    # Filter out weaker directions
    filtered_edges = validated_edges[
        ~validated_edges.apply(
            lambda row: (row['source'], row['target']) in edges_to_remove,
            axis=1
        )
    ].copy()

    logger.info(f"  Before: {len(validated_edges):,} edges")
    logger.info(f"  After:  {len(filtered_edges):,} edges")
    logger.info(f"  Removed: {len(validated_edges) - len(filtered_edges):,} edges")

    return filtered_edges

def weighted_fas(G, max_iterations=100000):
    """
    Weighted Feedback Arc Set (FAS) algorithm
    Iteratively find and remove weakest edge in cycles

    Memory-safe: Uses nx.find_cycle() (one cycle at a time)
    """
    logger.info("\n" + "="*80)
    logger.info("STEP 3B: WEIGHTED FAS ON REMAINING CYCLES")
    logger.info("="*80)

    initial_edges = G.number_of_edges()

    if nx.is_directed_acyclic_graph(G):
        logger.info("  ✅ Already a valid DAG (no cycles)")
        return G, 0, []

    logger.info(f"  Graph has cycles - starting weighted removal...")
    logger.info(f"  Initial edges: {initial_edges:,}")

    iteration = 0
    removed_edges = []

    while not nx.is_directed_acyclic_graph(G):
        try:
            # Find ONE cycle (memory-safe)
            cycle = nx.find_cycle(G, orientation='original')

            # Extract forward edges in cycle
            cycle_edges = []
            for u, v, direction in cycle:
                if direction == 'forward' and G.has_edge(u, v):
                    edge_data = G[u][v]
                    cycle_edges.append({
                        'source': u,
                        'target': v,
                        'f_statistic': edge_data.get('f_statistic', 0)
                    })

            if not cycle_edges:
                logger.warning("  Found cycle but no forward edges?")
                break

            # Find WEAKEST edge (lowest F-statistic)
            weakest = min(cycle_edges, key=lambda e: e['f_statistic'])

            # Remove it
            G.remove_edge(weakest['source'], weakest['target'])
            removed_edges.append(weakest)

            iteration += 1

            if iteration % 1000 == 0:
                logger.info(f"  Iteration {iteration:,}: Removed {len(removed_edges):,} edges, {G.number_of_edges():,} remaining")

            if iteration >= max_iterations:
                logger.warning(f"  Reached max iterations ({max_iterations:,})")
                break

        except nx.NetworkXNoCycle:
            # No more cycles
            break
        except Exception as e:
            logger.error(f"  Error: {e}")
            break

    final_edges = G.number_of_edges()
    removed_count = initial_edges - final_edges
    is_dag = nx.is_directed_acyclic_graph(G)

    logger.info(f"\n  Results:")
    logger.info(f"    Initial edges:  {initial_edges:,}")
    logger.info(f"    Final edges:    {final_edges:,}")
    logger.info(f"    Removed:        {removed_count:,} ({removed_count/initial_edges*100:.1f}%)")
    logger.info(f"    DAG valid:      {is_dag}")
    logger.info(f"    Iterations:     {iteration:,}")

    if removed_count > 0:
        removed_f_stats = [e['f_statistic'] for e in removed_edges]
        logger.info(f"\n  Removed edges F-statistic distribution:")
        logger.info(f"    Mean:   {np.mean(removed_f_stats):.2f}")
        logger.info(f"    Median: {np.median(removed_f_stats):.2f}")
        logger.info(f"    Min:    {np.min(removed_f_stats):.2f}")
        logger.info(f"    Max:    {np.max(removed_f_stats):.2f}")

    return G, removed_count, removed_edges

def main():
    start_time = datetime.now()

    logger.info("\n" + "="*80)
    logger.info("A3 STEP 3: HYBRID CYCLE REMOVAL")
    logger.info("="*80)
    logger.info(f"Started: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("="*80 + "\n")

    # Load data
    validated_edges, a2_edges = load_data()

    # Step 3A: Identify and handle bidirectional pairs
    bidirectional_df = find_bidirectional_pairs(validated_edges, a2_edges)
    edges_after_feedback = remove_weaker_feedback_directions(validated_edges, bidirectional_df)

    # Build graph
    logger.info("\n" + "="*80)
    logger.info("BUILDING GRAPH")
    logger.info("="*80)

    G = nx.DiGraph()
    for _, edge in edges_after_feedback.iterrows():
        G.add_edge(
            edge['source'],
            edge['target'],
            f_statistic=edge['f_statistic'],
            p_value=edge.get('p_value', None),
            best_lag=edge.get('best_lag', None)
        )

    logger.info(f"  Nodes: {G.number_of_nodes():,}")
    logger.info(f"  Edges: {G.number_of_edges():,}")
    logger.info(f"  Is DAG: {nx.is_directed_acyclic_graph(G)}")

    # Step 3B: Weighted FAS on remaining cycles
    G_final, removed_count, removed_edges = weighted_fas(G)

    # Extract final edge list
    logger.info("\n" + "="*80)
    logger.info("EXTRACTING FINAL EDGE LIST")
    logger.info("="*80)

    final_edges = []
    for u, v, data in G_final.edges(data=True):
        final_edges.append({
            'source': u,
            'target': v,
            'f_statistic': data.get('f_statistic'),
            'p_value': data.get('p_value'),
            'best_lag': data.get('best_lag')
        })

    final_edges_df = pd.DataFrame(final_edges)

    logger.info(f"  Final edges: {len(final_edges_df):,}")

    # Validation
    logger.info("\n" + "="*80)
    logger.info("DAG VALIDATION")
    logger.info("="*80)

    is_dag = nx.is_directed_acyclic_graph(G_final)
    logger.info(f"  Is DAG: {is_dag}")

    if is_dag:
        logger.info("  ✅ Valid DAG (no cycles)")
    else:
        logger.error("  ❌ Still has cycles!")

    # Connectivity
    largest_cc = max(nx.weakly_connected_components(G_final), key=len)
    connectivity = len(largest_cc) / G_final.number_of_nodes()
    logger.info(f"  Connectivity: {connectivity:.1%}")

    # Statistics
    logger.info("\n" + "="*80)
    logger.info("FINAL STATISTICS")
    logger.info("="*80)

    logger.info(f"\nEdge count progression:")
    logger.info(f"  PC-Stable validated:        {len(validated_edges):>10,}")
    logger.info(f"  After feedback removal:     {len(edges_after_feedback):>10,}")
    logger.info(f"  After weighted FAS:         {len(final_edges_df):>10,}")
    logger.info(f"  Total reduction:            {len(validated_edges) - len(final_edges_df):>10,} ({(1 - len(final_edges_df)/len(validated_edges))*100:.1f}%)")

    logger.info(f"\nF-statistic distribution:")
    logger.info(f"  Mean:   {final_edges_df['f_statistic'].mean():.2f}")
    logger.info(f"  Median: {final_edges_df['f_statistic'].median():.2f}")
    logger.info(f"  Min:    {final_edges_df['f_statistic'].min():.2f}")
    logger.info(f"  Max:    {final_edges_df['f_statistic'].max():.2f}")

    # Save results
    logger.info("\n" + "="*80)
    logger.info("SAVING RESULTS")
    logger.info("="*80)

    output_dir = Path(__file__).parent.parent / 'outputs'

    # Save final DAG
    output_data = {
        'graph': G_final,
        'edges': final_edges_df,
        'validation': {
            'is_dag': is_dag,
            'n_nodes': G_final.number_of_nodes(),
            'n_edges': len(final_edges_df),
            'connectivity': connectivity
        },
        'metadata': {
            'timestamp': datetime.now().isoformat(),
            'input_edges_pc_stable': len(validated_edges),
            'after_feedback_removal': len(edges_after_feedback),
            'after_weighted_fas': len(final_edges_df),
            'bidirectional_pairs_found': len(bidirectional_df),
            'weighted_fas_removed': removed_count,
            'method': 'Hybrid: Feedback loop handling + Weighted FAS',
            'total_reduction_pct': (1 - len(final_edges_df)/len(validated_edges))*100
        }
    }

    # Save pickle
    pkl_file = output_dir / 'A3_final_dag_v2.pkl'
    with open(pkl_file, 'wb') as f:
        pickle.dump(output_data, f)
    logger.info(f"  Saved: {pkl_file}")

    # Save CSV
    csv_file = output_dir / 'A3_final_edge_list_v2.csv'
    final_edges_df.to_csv(csv_file, index=False)
    logger.info(f"  Saved: {csv_file}")

    # Save GraphML
    graphml_file = output_dir / 'A3_final_dag_v2.graphml'
    nx.write_graphml(G_final, graphml_file)
    logger.info(f"  Saved: {graphml_file}")

    # Runtime
    end_time = datetime.now()
    runtime = (end_time - start_time).total_seconds() / 60

    logger.info("\n" + "="*80)
    logger.info("COMPLETE")
    logger.info("="*80)
    logger.info(f"  Runtime: {runtime:.1f} minutes")
    logger.info(f"  Final DAG: {len(final_edges_df):,} edges, {G_final.number_of_nodes():,} nodes")
    logger.info(f"  Valid: {is_dag}")
    logger.info("="*80 + "\n")

if __name__ == '__main__':
    main()
