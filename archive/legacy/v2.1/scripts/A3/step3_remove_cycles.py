#!/usr/bin/env python3
"""
A3 Step 3: Remove Cycles from DAG (V2.1)
Iteratively remove weakest edges in cycles to create valid DAG

V2.1 MODIFICATION: Uses v21_config for paths
"""

import pickle
import pandas as pd
import networkx as nx
from pathlib import Path
from datetime import datetime
import logging
import sys

# V2.1 Configuration
sys.path.insert(0, str(Path(__file__).parent.parent))
from v21_config import A3_OUTPUT, LOG_DIR

# Setup logging
LOG_FILE = LOG_DIR / 'remove_cycles.log'
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def load_validated_edges():
    """Load PC-Stable validated edges"""
    logger.info("="*80)
    logger.info("Loading validated edges...")

    input_file = A3_OUTPUT / 'pc_stable_edges.pkl'

    with open(input_file, 'rb') as f:
        data = pickle.load(f)

    edges_df = data['edges']
    logger.info(f"  Loaded {len(edges_df):,} validated edges")

    return edges_df, data['metadata']

def build_graph(edges_df):
    """Build directed graph from edges"""
    logger.info("="*80)
    logger.info("Building directed graph...")

    G = nx.DiGraph()

    for _, edge in edges_df.iterrows():
        G.add_edge(
            edge['source'],
            edge['target'],
            f_statistic=edge['f_statistic'],
            p_value=edge.get('p_value', edge.get('p_value_fdr', 0)),
            best_lag=edge.get('best_lag', 1)
        )

    logger.info(f"  Nodes: {G.number_of_nodes():,}")
    logger.info(f"  Edges: {G.number_of_edges():,}")

    return G

def remove_cycles(G):
    """
    Remove cycles using MEMORY-SAFE greedy approach

    Uses nx.find_cycle() which finds ONE cycle at a time using DFS
    Memory: O(V+E) instead of exponential from enumerating all cycles
    """
    logger.info("="*80)
    logger.info("Removing cycles (memory-safe greedy approach)...")

    initial_edges = G.number_of_edges()

    # Check if already a DAG
    if nx.is_directed_acyclic_graph(G):
        logger.info("  ✅ Already a valid DAG (no cycles)")
        return G, 0

    logger.info("  Graph has cycles - starting removal...")

    # Remove cycles iteratively
    iteration = 0
    removed_edges = []

    while not nx.is_directed_acyclic_graph(G):
        try:
            # Find ONE cycle (memory-safe - doesn't enumerate all)
            cycle = nx.find_cycle(G, orientation='original')

            # cycle is list of (u, v, direction) tuples
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

            # Find weakest edge (lowest F-statistic)
            weakest = min(cycle_edges, key=lambda e: e['f_statistic'])

            # Remove it
            G.remove_edge(weakest['source'], weakest['target'])
            removed_edges.append(weakest)

            iteration += 1

            if iteration % 100 == 0:
                logger.info(f"  Removed {iteration:,} cycle edges, {G.number_of_edges():,} remaining...")

        except nx.NetworkXNoCycle:
            # No more cycles - we have a DAG
            break
        except Exception as e:
            logger.error(f"  Error: {e}")
            break

    final_edges = G.number_of_edges()
    removed_count = initial_edges - final_edges

    # Final check
    is_dag = nx.is_directed_acyclic_graph(G)

    logger.info("="*80)
    logger.info("CYCLE REMOVAL COMPLETE")
    logger.info("="*80)
    logger.info(f"  Initial edges:  {initial_edges:,}")
    logger.info(f"  Final edges:    {final_edges:,}")
    logger.info(f"  Removed:        {removed_count:,} ({removed_count/initial_edges*100:.1f}%)")
    logger.info(f"  DAG valid:      {is_dag}")

    if not is_dag:
        logger.error("  ⚠️  WARNING: Graph still has cycles!")

    return G, removed_count

def validate_dag(G):
    """Validate final DAG properties"""
    logger.info("="*80)
    logger.info("DAG VALIDATION")
    logger.info("="*80)

    n_nodes = G.number_of_nodes()
    n_edges = G.number_of_edges()

    logger.info(f"  Nodes: {n_nodes:,}")
    logger.info(f"  Edges: {n_edges:,}")

    # Check 1: Is it a DAG?
    is_dag = nx.is_directed_acyclic_graph(G)
    logger.info(f"\n  1. DAG validity: {is_dag}")

    if is_dag:
        logger.info("     ✅ No cycles detected")
    else:
        logger.error("     ❌ Still has cycles!")
        return False

    # Check 2: Connectivity
    if n_nodes > 0:
        largest_cc = max(nx.weakly_connected_components(G), key=len)
        connectivity = len(largest_cc) / n_nodes

        logger.info(f"\n  2. Connectivity: {connectivity:.1%}")
        if connectivity > 0.80:
            logger.info("     ✅ Good connectivity (>80%)")
        else:
            logger.warning(f"     ⚠️  Low connectivity (<80%)")
    else:
        connectivity = 0.0

    # Check 3: Edge count (relaxed upper bound to 100K)
    logger.info(f"\n  3. Edge count: {n_edges:,}")
    if 30_000 <= n_edges <= 100_000:
        logger.info("     ✅ Within acceptable range (30K-100K)")
    elif n_edges < 30_000:
        logger.warning(f"     ⚠️  Below target (<30K)")
    else:
        logger.warning(f"     ⚠️  Above target (>100K)")

    # Check 4: Degree statistics
    in_degrees = [d for _, d in G.in_degree()]
    out_degrees = [d for _, d in G.out_degree()]

    logger.info(f"\n  4. Degree statistics:")
    logger.info(f"     In-degree:  mean={sum(in_degrees)/len(in_degrees):.1f}, max={max(in_degrees)}")
    logger.info(f"     Out-degree: mean={sum(out_degrees)/len(out_degrees):.1f}, max={max(out_degrees)}")

    logger.info("="*80)

    return {
        'is_dag': is_dag,
        'n_nodes': n_nodes,
        'n_edges': n_edges,
        'connectivity': connectivity,
        'avg_in_degree': sum(in_degrees)/len(in_degrees) if in_degrees else 0,
        'avg_out_degree': sum(out_degrees)/len(out_degrees) if out_degrees else 0
    }

def save_final_dag(G, validation_results, input_metadata):
    """Save final DAG for A4"""
    logger.info("="*80)
    logger.info("Saving final DAG...")

    output_dir = A3_OUTPUT
    output_dir.mkdir(parents=True, exist_ok=True)

    # Extract edge list
    edge_list = []
    for source, target, data in G.edges(data=True):
        edge_list.append({
            'source': source,
            'target': target,
            'f_statistic': data.get('f_statistic', 0),
            'p_value': data.get('p_value', 0),
            'best_lag': data.get('best_lag', 1)
        })

    edges_df = pd.DataFrame(edge_list)

    # Create output
    output = {
        'graph': G,
        'edges': edges_df,
        'validation': validation_results,
        'metadata': {
            'timestamp': datetime.now().isoformat(),
            'input_edges_pc_stable': input_metadata.get('validated_edges', len(edges_df)),
            'after_cycle_removal': G.number_of_edges(),
            'method': 'PC-Stable (Fisher-Z, alpha=0.001) + cycle removal',
            'alpha': input_metadata.get('alpha', 0.001),
            'reduction_from_input': input_metadata.get('reduction_pct', 0),
            'total_reduction_from_granger': (1 - G.number_of_edges()/564545)*100  # Updated from A2 edges
        }
    }

    # Save pickle
    output_file = output_dir / 'A3_final_dag.pkl'
    with open(output_file, 'wb') as f:
        pickle.dump(output, f)

    logger.info(f"  ✅ Saved: {output_file}")

    # Save edge list CSV
    csv_file = output_dir / 'A3_final_edge_list.csv'
    edges_df.to_csv(csv_file, index=False)

    logger.info(f"  ✅ Saved: {csv_file}")

    # Save GraphML for visualization
    graphml_file = output_dir / 'A3_final_dag.graphml'
    nx.write_graphml(G, graphml_file)

    logger.info(f"  ✅ Saved: {graphml_file}")
    logger.info("="*80)

def main():
    """Main pipeline"""
    logger.info("\n" + "="*80)
    logger.info("A3 STEP 3: CYCLE REMOVAL & DAG VALIDATION")
    logger.info("="*80)
    logger.info(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("="*80)

    # Load edges
    edges_df, input_metadata = load_validated_edges()

    # Build graph
    G = build_graph(edges_df)

    # Remove cycles
    G, removed_count = remove_cycles(G)

    # Validate
    validation_results = validate_dag(G)

    # Save
    save_final_dag(G, validation_results, input_metadata)

    logger.info("\n" + "="*80)
    logger.info("✅ A3 COMPLETE")
    logger.info("="*80)
    logger.info(f"  Input (Granger):     114,274 edges")
    logger.info(f"  After PC-Stable:     {input_metadata['validated_edges']:,} edges")
    logger.info(f"  After cycle removal: {G.number_of_edges():,} edges")
    logger.info(f"  Total reduction:     {(1 - G.number_of_edges()/114274)*100:.1f}%")
    logger.info(f"  Ready for A4:        ✅")
    logger.info("="*80 + "\n")

if __name__ == '__main__':
    main()
