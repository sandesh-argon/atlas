"""
A3 Step 2: PC-Stable Conditional Independence Testing

Removes spurious correlations from A2 Granger edges using PC-Stable algorithm.

Input: 1,157,230 Granger-validated edges @ q<0.01
Output: 30K-80K validated causal edges (97-99% reduction)

Runtime: 2-4 days (12 cores)
Checkpoint: Every 10K edges
"""

import pickle
import pandas as pd
import numpy as np
import networkx as nx
from pathlib import Path
from datetime import datetime
import time
import logging
import sys

# Paths
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
A2_DIR = PROJECT_ROOT / "phaseA" / "A2_granger_causality"
A1_DIR = PROJECT_ROOT / "phaseA" / "A1_missingness_analysis"
A3_DIR = PROJECT_ROOT / "phaseA" / "A3_conditional_independence"

A2_FDR_FILE = A2_DIR / "outputs" / "granger_fdr_corrected.pkl"
A1_DATA_FILE = A1_DIR / "outputs" / "A2_preprocessed_data.pkl"

CHECKPOINT_FILE = A3_DIR / "checkpoints" / "a3_pc_stable_progress.pkl"
LOG_FILE = A3_DIR / "logs" / "step2_pc_stable.log"
OUTPUT_FILE = A3_DIR / "outputs" / "A3_validated_edges.pkl"

# Configuration
N_CORES = 16  # Increased for better utilization
CHECKPOINT_INTERVAL = 10000  # Every 10K edges
ALPHA = 0.001  # Stricter than A2

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def load_a2_edges():
    """Load A2 FDR-corrected edges @ q<0.01"""
    logger.info("Loading A2 Granger edges...")

    with open(A2_FDR_FILE, 'rb') as f:
        fdr_data = pickle.load(f)

    results_df = fdr_data['results']
    edges_q01 = results_df[results_df['significant_fdr_001']].copy()

    logger.info(f"Loaded {len(edges_q01):,} edges @ q<0.01")
    return edges_q01

def load_a1_data():
    """Load A1 imputed data in long format"""
    logger.info("Loading A1 imputed data...")

    with open(A1_DATA_FILE, 'rb') as f:
        a1_data = pickle.load(f)

    imputed_data_dict = a1_data['imputed_data']

    # Convert to long format
    all_indicators_long = []
    for indicator_name, df in imputed_data_dict.items():
        df_long = df.stack().rename(indicator_name).to_frame()
        all_indicators_long.append(df_long)

    imputed_data = pd.concat(all_indicators_long, axis=1)
    imputed_data.index.names = ['Country', 'Year']

    logger.info(f"Loaded {len(imputed_data.columns):,} indicators, {len(imputed_data):,} observations")
    logger.info(f"Missing rate: {imputed_data.isna().sum().sum() / (len(imputed_data) * len(imputed_data.columns)):.2%}")

    return imputed_data

def test_conditional_independence_fisherz(data, X, Y, Z_set, alpha=0.001):
    """
    Test conditional independence using Fisher's Z transformation

    Tests: X ⊥ Y | Z_set (X independent of Y given conditioning set Z)

    Returns: (is_independent, p_value, test_statistic)
    """
    from scipy.stats import norm

    # Get relevant columns (drop NaN pairwise)
    cols = [X, Y] + list(Z_set)
    sub_data = data[cols].dropna()

    n = len(sub_data)

    # Need at least 3 observations + conditioning set size
    min_obs = max(10, len(Z_set) + 3)
    if n < min_obs:
        return False, 1.0, 0.0  # Not enough data, assume dependent

    # Compute partial correlation
    partial_corr = 0.0  # Initialize

    if len(Z_set) == 0:
        # No conditioning - simple correlation
        partial_corr = sub_data[[X, Y]].corr().iloc[0, 1]
    else:
        # Partial correlation using matrix inversion
        corr_matrix = sub_data.corr().values

        # Indices
        x_idx = cols.index(X)
        y_idx = cols.index(Y)

        try:
            # Precision matrix (inverse of correlation matrix)
            precision = np.linalg.inv(corr_matrix)

            # Partial correlation from precision matrix
            partial_corr = -precision[x_idx, y_idx] / np.sqrt(precision[x_idx, x_idx] * precision[y_idx, y_idx])
        except np.linalg.LinAlgError:
            # Singular matrix - assume dependent
            return False, 1.0, 0.0

    # Fisher's Z transformation
    if abs(partial_corr) >= 1.0:
        # Perfect correlation/anti-correlation - dependent
        return False, 0.0, np.inf

    z = 0.5 * np.log((1 + partial_corr) / (1 - partial_corr))

    # Test statistic
    test_stat = abs(z) * np.sqrt(n - len(Z_set) - 3)

    # P-value (two-tailed)
    p_value = 2 * (1 - norm.cdf(test_stat))

    # Independent if p_value > alpha
    is_independent = (p_value > alpha)

    return is_independent, p_value, test_stat

def test_single_edge(edge, granger_adj, data, alpha, max_cond_set_size):
    """Test a single edge for conditional independence (for parallelization)"""
    from itertools import combinations

    source = edge['source']
    target = edge['target']

    # Find potential confounders
    x_neighbors = granger_adj.get(source, set())
    y_neighbors = granger_adj.get(target, set())
    potential_confounders = (x_neighbors & y_neighbors) - {source, target}

    # Test conditional independence
    for cond_size in range(min(len(potential_confounders), max_cond_set_size) + 1):
        if cond_size == 0:
            is_indep, p_val, test_stat = test_conditional_independence_fisherz(
                data, source, target, [], alpha
            )
            if is_indep:
                return None  # Edge removed
        else:
            for Z_set in combinations(potential_confounders, cond_size):
                is_indep, p_val, test_stat = test_conditional_independence_fisherz(
                    data, source, target, Z_set, alpha
                )
                if is_indep:
                    return None  # Edge removed

    return edge  # Edge validated

def pc_stable_skeleton(data, edges_df, alpha=0.001, max_cond_set_size=3):
    """
    Simplified PC-Stable skeleton phase with parallelization

    For each Granger edge X → Y:
    1. Find potential confounders: variables that are adjacent to both X and Y in Granger graph
    2. Test conditional independence X ⊥ Y | Z for subsets of confounders
    3. If found independent, remove edge

    This is a conservative approximation of full PC-Stable optimized for large-scale graphs.
    """
    from joblib import Parallel, delayed

    logger.info("Starting PC-Stable skeleton phase...")
    logger.info(f"Alpha: {alpha}, Max conditioning set size: {max_cond_set_size}")
    logger.info(f"Parallelization: {N_CORES} cores")

    # Build adjacency from Granger edges
    logger.info("Building Granger adjacency graph...")
    granger_adj = {}
    for _, row in edges_df.iterrows():
        source, target = row['source'], row['target']

        if source not in granger_adj:
            granger_adj[source] = set()
        if target not in granger_adj:
            granger_adj[target] = set()

        granger_adj[source].add(target)
        granger_adj[target].add(source)  # Treat as undirected for skeleton

    logger.info(f"Graph has {len(granger_adj):,} nodes")

    # Track validated edges
    validated_edges = []
    edges_to_test = edges_df.to_dict('records')
    total_edges = len(edges_to_test)

    # Load checkpoint if exists
    start_idx = 0
    if CHECKPOINT_FILE.exists():
        logger.info("Loading checkpoint...")
        with open(CHECKPOINT_FILE, 'rb') as f:
            checkpoint = pickle.load(f)

        start_idx = checkpoint.get('edges_processed', 0)
        validated_edges = checkpoint.get('validated_edges_list', [])
        logger.info(f"Resuming from edge {start_idx:,}")

    # Start processing
    start_time = time.time()

    # Process in chunks for checkpointing
    chunk_size = CHECKPOINT_INTERVAL
    for chunk_start in range(start_idx, total_edges, chunk_size):
        chunk_end = min(chunk_start + chunk_size, total_edges)
        chunk_edges = edges_to_test[chunk_start:chunk_end]

        # Process chunk in parallel (threading backend to avoid memory duplication)
        chunk_results = Parallel(n_jobs=N_CORES, backend='threading', verbose=0)(
            delayed(test_single_edge)(edge, granger_adj, data, alpha, max_cond_set_size)
            for edge in chunk_edges
        )

        # Filter out removed edges (None values)
        validated_chunk = [edge for edge in chunk_results if edge is not None]
        validated_edges.extend(validated_chunk)

        # Checkpoint after each chunk
        i = chunk_end - 1
        elapsed = time.time() - start_time
        progress = (i + 1) / total_edges

        checkpoint = {
            'edges_processed': i + 1,
            'total_edges': total_edges,
            'validated_edges': len(validated_edges),
            'validated_edges_list': validated_edges,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'elapsed_seconds': elapsed,
            'alpha': alpha,
            'max_cond_set_size': max_cond_set_size
        }

        with open(CHECKPOINT_FILE, 'wb') as f:
            pickle.dump(checkpoint, f)

        logger.info(f"Checkpoint {i+1:,}/{total_edges:,} ({progress*100:.2f}%) - {len(validated_edges):,} edges validated - {elapsed/3600:.2f}h elapsed")

    logger.info(f"Skeleton phase complete: {len(validated_edges):,} validated edges (from {total_edges:,})")

    return validated_edges

def orient_edges(validated_edges, edges_df):
    """
    Orient edges using Granger temporal precedence

    Since we have temporal information from Granger causality (lag structure),
    we can directly orient edges: X(t-lag) → Y(t)
    """
    logger.info("Orienting edges using Granger temporal precedence...")

    oriented_edges = []

    for edge_dict in validated_edges:
        # Find original edge info from edges_df
        source = edge_dict['source']
        target = edge_dict['target']

        # Granger causality gives us directionality: source → target
        oriented_edges.append(edge_dict)

    logger.info(f"Oriented {len(oriented_edges):,} edges")

    return oriented_edges

def validate_dag(oriented_edges):
    """Validate that result is a DAG (no cycles)"""
    logger.info("Validating DAG properties...")

    # Build graph
    G = nx.DiGraph()
    for edge in oriented_edges:
        G.add_edge(edge['source'], edge['target'])

    # Check for cycles
    is_dag = nx.is_directed_acyclic_graph(G)

    if not is_dag:
        logger.warning("⚠️  Graph has cycles! This should not happen with temporal precedence.")
        try:
            cycles = list(nx.simple_cycles(G))
            logger.warning(f"Found {len(cycles)} cycles")
            logger.warning(f"Sample cycle: {cycles[0]}")
        except:
            pass
    else:
        logger.info("✓ Graph is a valid DAG")

    # Check connectivity
    if len(G.nodes()) > 0:
        largest_cc = max(nx.weakly_connected_components(G), key=len)
        connectivity = len(largest_cc) / len(G.nodes())
        logger.info(f"Largest component: {len(largest_cc):,} nodes ({connectivity:.1%} of total)")

    return is_dag, G

def main():
    logger.info("=" * 80)
    logger.info("A3 STEP 2: PC-STABLE CONDITIONAL INDEPENDENCE")
    logger.info("=" * 80)
    logger.info(f"Configuration: alpha={ALPHA}, cores={N_CORES}, checkpoint every {CHECKPOINT_INTERVAL:,} edges")
    logger.info("")

    # Load data
    edges_df = load_a2_edges()
    data = load_a1_data()

    # Run PC-Stable skeleton
    validated_edges = pc_stable_skeleton(data, edges_df, alpha=ALPHA, max_cond_set_size=3)

    # Convert to DataFrame
    validated_df = pd.DataFrame(validated_edges)

    # Orient edges
    oriented_edges = orient_edges(validated_edges, edges_df)
    oriented_df = pd.DataFrame(oriented_edges)

    # Validate DAG
    is_dag, G = validate_dag(oriented_edges)

    # Save results
    logger.info("Saving results...")

    output = {
        'validated_edges': oriented_df,
        'graph': G,
        'metadata': {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'n_input_edges': len(edges_df),
            'n_validated_edges': len(oriented_df),
            'reduction_ratio': 1 - (len(oriented_df) / len(edges_df)),
            'alpha': ALPHA,
            'is_dag': is_dag,
            'n_nodes': G.number_of_nodes(),
            'connectivity': len(max(nx.weakly_connected_components(G), key=len)) / G.number_of_nodes() if G.number_of_nodes() > 0 else 0
        }
    }

    with open(OUTPUT_FILE, 'wb') as f:
        pickle.dump(output, f)

    logger.info(f"✓ Saved validated edges: {OUTPUT_FILE}")
    logger.info("")
    logger.info("=" * 80)
    logger.info("FINAL RESULTS")
    logger.info("=" * 80)
    logger.info(f"Input edges: {len(edges_df):,}")
    logger.info(f"Validated edges: {len(oriented_df):,}")
    logger.info(f"Reduction: {(1 - len(oriented_df)/len(edges_df))*100:.2f}%")
    logger.info(f"DAG valid: {is_dag}")
    logger.info(f"Nodes: {G.number_of_nodes():,}")
    logger.info(f"Connectivity: {output['metadata']['connectivity']:.1%}")
    logger.info("=" * 80)

if __name__ == "__main__":
    main()
