#!/usr/bin/env python3
"""
A3 Step 2: PC-Stable using causallearn (optimized, on pruned edges)
Runtime: 4-8 hours (not 19+ hours)
"""

import pickle
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime
from causallearn.search.ConstraintBased.PC import pc
import networkx as nx
import logging
import sys

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(Path(__file__).parent.parent / 'logs' / 'pc_causallearn.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def load_pruned_edges():
    """Load top 100K edges from Step 1b"""
    logger.info("="*60)
    logger.info("Loading pruned edges...")

    pruned_file = Path(__file__).parent.parent / 'outputs' / 'granger_top_100k.pkl'

    with open(pruned_file, 'rb') as f:
        data = pickle.load(f)

    edges_df = data['edges']
    logger.info(f"  Loaded {len(edges_df):,} pruned edges")

    return edges_df

def load_imputed_data():
    """Load A1 imputed data"""
    logger.info("="*60)
    logger.info("Loading A1 imputed data...")

    a1_file = Path(__file__).parent.parent.parent / 'A1_missingness_analysis' / 'outputs' / 'A2_preprocessed_data.pkl'

    with open(a1_file, 'rb') as f:
        a1_data = pickle.load(f)

    imputed_data = a1_data['imputed_data']
    logger.info(f"  Loaded {len(imputed_data):,} indicators")

    return imputed_data

def prepare_data_matrix(imputed_data, edges_df):
    """Build data matrix for PC-Stable (only active indicators)"""
    logger.info("="*60)
    logger.info("Preparing data matrix...")

    # Get indicators involved in pruned edges
    active_indicators = sorted(set(edges_df['source'].unique()) | set(edges_df['target'].unique()))

    logger.info(f"  Active indicators: {len(active_indicators):,}")

    # Build panel data
    all_data = []
    indicator_names = []

    for idx, indicator in enumerate(active_indicators):
        if indicator not in imputed_data:
            logger.warning(f"  Missing indicator: {indicator}")
            continue

        df = imputed_data[indicator]
        stacked = df.stack().reset_index()
        stacked.columns = ['Country', 'Year', indicator]

        if len(all_data) == 0:
            all_data = stacked
        else:
            all_data = all_data.merge(stacked, on=['Country', 'Year'], how='outer')

        indicator_names.append(indicator)

        if (idx + 1) % 500 == 0:
            logger.info(f"  Processed {idx+1}/{len(active_indicators)} indicators")

    # Drop incomplete observations
    logger.info("  Dropping rows with missing values...")
    all_data = all_data.dropna()

    logger.info(f"  Complete observations: {len(all_data):,}")
    logger.info(f"  Final indicators: {len(indicator_names):,}")

    # Extract data matrix
    data_matrix = all_data[indicator_names].values

    logger.info(f"  Data matrix shape: {data_matrix.shape}")
    logger.info(f"  Memory: {data_matrix.nbytes / 1e9:.2f} GB")

    return data_matrix, indicator_names

def run_pc_stable(data_matrix, indicator_names, alpha=0.001):
    """Run causallearn PC-Stable"""
    logger.info("="*60)
    logger.info("Running PC-Stable (causallearn)...")
    logger.info(f"  Alpha: {alpha}")
    logger.info(f"  Estimated runtime: 4-8 hours")
    logger.info(f"\n⏳ Starting at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("="*60)

    start = datetime.now()

    cg = pc(
        data_matrix,
        alpha=alpha,
        indep_test='fisherz',
        stable=True,
        uc_rule=1,
        uc_priority=3,
        mvpc=False,
        correction_name='MV',
        verbose=True,
        show_progress=True
    )

    end = datetime.now()
    runtime_hours = (end - start).total_seconds() / 3600

    logger.info("="*60)
    logger.info("✅ PC-Stable complete!")
    logger.info(f"  Runtime: {runtime_hours:.2f} hours")
    logger.info(f"  Graph nodes: {cg.G.get_num_nodes()}")
    logger.info(f"  Graph edges: {len(cg.G.get_graph_edges())}")

    return cg, runtime_hours

def convert_to_networkx(cg, indicator_names):
    """Convert causallearn graph to NetworkX"""
    logger.info("="*60)
    logger.info("Converting to NetworkX...")

    G = nx.DiGraph()

    for edge in cg.G.get_graph_edges():
        i = edge.get_node1()
        j = edge.get_node2()

        source = indicator_names[i]
        target = indicator_names[j]

        G.add_edge(source, target)

    logger.info(f"  Edges: {G.number_of_edges():,}")
    logger.info(f"  Nodes: {G.number_of_nodes():,}")

    return G

def validate_output(G, input_edges):
    """Validate against A3 success criteria"""
    logger.info("="*60)
    logger.info("Validating output...")

    n_edges = G.number_of_edges()
    n_nodes = G.number_of_nodes()

    # Edge count
    logger.info(f"\n  1. Edge count: {n_edges:,}")
    if 10_000 <= n_edges <= 100_000:
        logger.info(f"     ✅ PASS")
    else:
        logger.info(f"     ⚠️  Outside 10K-100K range")

    # DAG
    is_dag = nx.is_directed_acyclic_graph(G)
    logger.info(f"\n  2. DAG: {is_dag}")
    if is_dag:
        logger.info(f"     ✅ PASS")
    else:
        logger.info(f"     ❌ FAIL - Cycles detected")

    # Connectivity
    if n_nodes > 0:
        largest_cc = max(nx.weakly_connected_components(G), key=len)
        connectivity = len(largest_cc) / n_nodes
    else:
        connectivity = 0.0

    logger.info(f"\n  3. Connectivity: {connectivity:.2%}")
    if connectivity > 0.80:
        logger.info(f"     ✅ PASS")
    else:
        logger.info(f"     ⚠️  <80%")

    # Reduction
    reduction = 1 - (n_edges / input_edges)
    logger.info(f"\n  4. Reduction: {reduction:.2%}")
    logger.info(f"     Input: {input_edges:,}")
    logger.info(f"     Output: {n_edges:,}")

    return {
        'n_edges': n_edges,
        'n_nodes': n_nodes,
        'is_dag': is_dag,
        'connectivity': connectivity,
        'reduction': reduction
    }

def save_output(G, validation, runtime_hours):
    """Save A3 output"""
    logger.info("="*60)
    logger.info("Saving output...")

    output_dir = Path(__file__).parent.parent / 'outputs'

    output = {
        'graph': G,
        'validation': validation,
        'metadata': {
            'timestamp': datetime.now().isoformat(),
            'runtime_hours': runtime_hours,
            'method': 'PC-Stable (causallearn, pruned)',
            'alpha': 0.001,
            'input_edges': 100_000
        }
    }

    with open(output_dir / 'A3_validated_edges.pkl', 'wb') as f:
        pickle.dump(output, f)

    logger.info(f"  ✅ Saved: outputs/A3_validated_edges.pkl")

    # Edge list CSV
    edge_list = [{'source': s, 'target': t} for s, t in G.edges()]
    pd.DataFrame(edge_list).to_csv(output_dir / 'A3_edge_list.csv', index=False)

    logger.info(f"  ✅ Saved: outputs/A3_edge_list.csv")

def main():
    """Main pipeline"""
    overall_start = datetime.now()

    # Load data
    edges_df = load_pruned_edges()
    imputed_data = load_imputed_data()

    # Prepare matrix
    data_matrix, indicator_names = prepare_data_matrix(imputed_data, edges_df)

    # Run PC-Stable
    cg, runtime_hours = run_pc_stable(data_matrix, indicator_names, alpha=0.001)

    # Convert to NetworkX
    G = convert_to_networkx(cg, indicator_names)

    # Validate
    validation = validate_output(G, input_edges=len(edges_df))

    # Save
    overall_runtime = (datetime.now() - overall_start).total_seconds() / 3600
    save_output(G, validation, overall_runtime)

    logger.info("="*80)
    logger.info("✅ A3 COMPLETE")
    logger.info(f"  Runtime: {overall_runtime:.2f} hours")
    logger.info("="*80)

if __name__ == '__main__':
    main()
