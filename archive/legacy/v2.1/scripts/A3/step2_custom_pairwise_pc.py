#!/usr/bin/env python3
"""
A3 Step 2: Custom Pairwise PC-Stable (V2.1)
Handles missing data via pairwise deletion
Runtime: 10-12 hours on 114K edges with 8 cores

V2.1 MODIFICATION: Uses v21_config for paths
"""

import pickle
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
from scipy.stats import pearsonr, norm
import statsmodels.api as sm
from itertools import combinations
from joblib import Parallel, delayed
from tqdm import tqdm
import logging
import sys
import time

# V2.1 Configuration
sys.path.insert(0, str(Path(__file__).parent.parent))
from v21_config import A3_OUTPUT, LOG_DIR, get_input_path
import json

PROGRESS_FILE = A3_OUTPUT / "progress.json"

def update_progress(step, pct, elapsed_min, eta_min, items_done, items_total, extra=None):
    """Write progress to JSON file for external monitoring"""
    progress = {
        "step": step,
        "pct": round(pct, 1),
        "elapsed_min": round(elapsed_min, 1),
        "eta_min": round(eta_min, 1),
        "items_done": items_done,
        "items_total": items_total,
        "updated": datetime.now().isoformat()
    }
    if extra:
        progress.update(extra)
    with open(PROGRESS_FILE, 'w') as f:
        json.dump(progress, f, indent=2)

# Setup logging
LOG_FILE = LOG_DIR / 'pairwise_pc.log'
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def load_prepruned_edges():
    """Load smart pre-pruned edges (114K)"""
    logger.info("="*80)
    logger.info("Loading pre-pruned edges...")

    prepruned_file = A3_OUTPUT / 'smart_prepruned_edges.pkl'

    with open(prepruned_file, 'rb') as f:
        data = pickle.load(f)

    edges_df = data['edges']
    logger.info(f"  Loaded {len(edges_df):,} pre-pruned edges")
    logger.info(f"  Variables: {data['metadata']['coverage']['total_variables']:,}")

    return edges_df

def load_imputed_data():
    """Load A1 imputed data as dict"""
    logger.info("="*80)
    logger.info("Loading A1 imputed data...")

    a1_file = get_input_path()

    with open(a1_file, 'rb') as f:
        a1_data = pickle.load(f)

    imputed_data_dict = a1_data['imputed_data']

    # Convert each indicator to long format (country-year series)
    logger.info(f"  Converting {len(imputed_data_dict):,} indicators to long format...")

    data_dict = {}
    for indicator_name, df in imputed_data_dict.items():
        # Stack: country × year → (country, year) series
        series = df.stack()
        data_dict[indicator_name] = series

    logger.info(f"  Converted {len(data_dict):,} indicators")

    return data_dict

def fisher_z_test(partial_r, n, alpha=0.001):
    """
    Fisher-Z test for partial correlation significance

    H0: partial_r = 0 (X and Y are independent given Z)
    H1: partial_r ≠ 0 (X and Y are dependent given Z)

    Returns: True if independent (p-value > alpha), False otherwise
    """
    if abs(partial_r) > 0.999:  # Avoid log(0)
        partial_r = 0.999 * np.sign(partial_r)

    # Fisher-Z transformation
    z = 0.5 * np.log((1 + partial_r) / (1 - partial_r))

    # Standard error
    se = 1 / np.sqrt(n - 3)

    # Test statistic
    z_stat = abs(z / se)

    # P-value (two-tailed)
    p_value = 2 * (1 - norm.cdf(z_stat))

    # Decision: independent if p > alpha
    is_independent = (p_value > alpha)

    return is_independent

def compute_partial_correlation(x, y, z):
    """
    Compute partial correlation: corr(X, Y | Z)
    Formula: (r_xy - r_xz * r_yz) / sqrt((1 - r_xz²)(1 - r_yz²))
    """
    try:
        r_xy, _ = pearsonr(x, y)
        r_xz, _ = pearsonr(x, z)
        r_yz, _ = pearsonr(y, z)

        numerator = r_xy - (r_xz * r_yz)
        denominator = np.sqrt((1 - r_xz**2) * (1 - r_yz**2))

        if denominator < 1e-10:  # Avoid division by zero
            return 0.0

        return numerator / denominator
    except:
        return 0.0

def compute_partial_correlation_multiple(x, y, Z):
    """
    Compute partial correlation with multiple conditioning variables
    Using regression residuals method
    """
    try:
        # Regress X on Z, get residuals
        model_x = sm.OLS(x, sm.add_constant(Z)).fit()
        resid_x = model_x.resid

        # Regress Y on Z, get residuals
        model_y = sm.OLS(y, sm.add_constant(Z)).fit()
        resid_y = model_y.resid

        # Correlation of residuals = partial correlation
        partial_r, _ = pearsonr(resid_x, resid_y)
        return partial_r
    except:
        return 0.0

def get_top_confounders(X, Y, edges_df, max_confounders=10):
    """
    Identify potential confounders:
    - Variables that Granger-cause both X and Y (common causes)
    - Ranked by F-statistic (stronger causes = better confounders)
    """
    # Find variables that cause both X and Y
    causes_X = edges_df[edges_df['target'] == X]
    causes_Y = edges_df[edges_df['target'] == Y]

    # Common causes (potential confounders)
    common_sources = set(causes_X['source'].unique()) & set(causes_Y['source'].unique())

    if len(common_sources) == 0:
        return []

    # Rank by average F-statistic (mean of F for X→cause and Y→cause)
    confounders_with_scores = []

    for source in common_sources:
        f_x = causes_X[causes_X['source'] == source]['f_statistic'].mean()
        f_y = causes_Y[causes_Y['source'] == source]['f_statistic'].mean()
        avg_f = (f_x + f_y) / 2
        confounders_with_scores.append((source, avg_f))

    # Sort by F-statistic descending
    confounders_with_scores.sort(key=lambda x: x[1], reverse=True)

    # Return top N
    top_confounders = [c[0] for c in confounders_with_scores[:max_confounders]]

    return top_confounders

def test_single_edge(edge_dict, edges_df, data_dict,
                     max_cond_size=2, max_confounders=10,
                     min_obs=30, alpha=0.001):
    """
    Test a single edge for conditional independence using Fisher-Z test
    Returns: (edge_dict, status, reason)
    """
    X = edge_dict['source']
    Y = edge_dict['target']

    # Get pairwise data (only X and Y, drop NaN)
    try:
        x_series = data_dict[X]
        y_series = data_dict[Y]

        # Align and drop NaN
        df_pair = pd.DataFrame({'X': x_series, 'Y': y_series}).dropna()

        if len(df_pair) < min_obs:
            return (None, 'insufficient_obs', f'n={len(df_pair)}')

    except KeyError:
        return (None, 'missing_variable', f'{X} or {Y} not in data')

    # Get potential confounders
    confounders = get_top_confounders(X, Y, edges_df, max_confounders)

    if len(confounders) == 0:
        # No confounders - can't be confounded, keep edge
        return (edge_dict, 'validated', 'no_confounders')

    # Test conditional independence
    # Level 1: Single confounders
    for Z in confounders:
        try:
            z_series = data_dict[Z]
            df_cond = pd.DataFrame({
                'X': x_series,
                'Y': y_series,
                'Z': z_series
            }).dropna()

            if len(df_cond) < min_obs:
                continue

            # Compute partial correlation
            partial_r = compute_partial_correlation(
                df_cond['X'].values,
                df_cond['Y'].values,
                df_cond['Z'].values
            )

            # Fisher-Z test for independence
            is_independent = fisher_z_test(partial_r, len(df_cond), alpha)

            if is_independent:
                # Edge becomes independent when conditioning on Z
                return (None, 'confounded', f'by {Z}, partial_r={partial_r:.3f}')

        except:
            continue

    # Level 2: Pairs of confounders
    if max_cond_size >= 2 and len(confounders) >= 2:
        for Z1, Z2 in combinations(confounders[:5], 2):  # Top 5 only for pairs
            try:
                z1_series = data_dict[Z1]
                z2_series = data_dict[Z2]

                df_cond = pd.DataFrame({
                    'X': x_series,
                    'Y': y_series,
                    'Z1': z1_series,
                    'Z2': z2_series
                }).dropna()

                if len(df_cond) < min_obs:
                    continue

                partial_r = compute_partial_correlation_multiple(
                    df_cond['X'].values,
                    df_cond['Y'].values,
                    df_cond[['Z1', 'Z2']].values
                )

                # Fisher-Z test for independence
                is_independent = fisher_z_test(partial_r, len(df_cond), alpha)

                if is_independent:
                    return (None, 'confounded', f'by {Z1},{Z2}, partial_r={partial_r:.3f}')

            except:
                continue

    # Edge survived all tests
    return (edge_dict, 'validated', 'survived_all_tests')

def pairwise_pc_stable(edges_df, data_dict,
                       max_cond_size=2, max_confounders=10,
                       min_obs=30, alpha=0.001,
                       n_cores=8, checkpoint_every=5000):
    """
    Run pairwise PC-Stable with parallelization and checkpointing
    """
    logger.info("="*80)
    logger.info("PAIRWISE PC-STABLE")
    logger.info("="*80)
    logger.info(f"  Edges to test: {len(edges_df):,}")
    logger.info(f"  Max conditioning set size: {max_cond_size}")
    logger.info(f"  Max confounders per edge: {max_confounders}")
    logger.info(f"  Min observations: {min_obs}")
    logger.info(f"  Alpha (Fisher-Z test): {alpha}")
    logger.info(f"  Parallel cores: {n_cores}")
    logger.info(f"  Checkpoint every: {checkpoint_every:,} edges")
    logger.info("="*80)

    # Convert edges to list of dicts
    edges_list = edges_df.to_dict('records')
    total_edges = len(edges_list)

    # Check for checkpoint
    checkpoint_file = A3_OUTPUT / 'checkpoints' / 'pairwise_pc_checkpoint.pkl'
    checkpoint_file.parent.mkdir(parents=True, exist_ok=True)
    start_idx = 0
    validated_edges = []
    failed_stats = {'insufficient_obs': 0, 'missing_variable': 0, 'confounded': 0}

    if checkpoint_file.exists():
        logger.info("Loading checkpoint...")
        with open(checkpoint_file, 'rb') as f:
            checkpoint = pickle.load(f)
        start_idx = checkpoint['edges_processed']
        validated_edges = checkpoint['validated_edges']
        failed_stats = checkpoint['failed_stats']
        logger.info(f"  Resuming from edge {start_idx:,}")

    # Process in chunks
    start_time = time.time()

    for chunk_start in range(start_idx, total_edges, checkpoint_every):
        chunk_end = min(chunk_start + checkpoint_every, total_edges)
        chunk = edges_list[chunk_start:chunk_end]

        logger.info(f"\nProcessing chunk {chunk_start:,} - {chunk_end:,} ({len(chunk):,} edges)")

        # Sequential processing (parallel was causing deadlocks with large DataFrame)
        results = []
        for edge in chunk:
            result = test_single_edge(edge, edges_df, data_dict,
                                      max_cond_size, max_confounders, min_obs, alpha)
            results.append(result)

        # Process results
        chunk_validated = 0
        for edge, status, reason in results:
            if edge is not None:
                validated_edges.append(edge)
                chunk_validated += 1
            else:
                failed_stats[status] = failed_stats.get(status, 0) + 1

        # Checkpoint
        elapsed = time.time() - start_time
        progress = chunk_end / total_edges

        checkpoint_data = {
            'edges_processed': chunk_end,
            'total_edges': total_edges,
            'validated_edges': validated_edges,
            'failed_stats': failed_stats,
            'timestamp': datetime.now().isoformat(),
            'elapsed_seconds': elapsed
        }

        with open(checkpoint_file, 'wb') as f:
            pickle.dump(checkpoint_data, f)

        # Stats
        rate = chunk_end / elapsed if elapsed > 0 else 0
        eta_seconds = (total_edges - chunk_end) / rate if rate > 0 else 0

        logger.info(f"  Chunk validated: {chunk_validated:,}/{len(chunk):,} ({chunk_validated/len(chunk)*100:.1f}%)")
        logger.info(f"  Total validated so far: {len(validated_edges):,}")
        logger.info(f"  Progress: {chunk_end:,}/{total_edges:,} ({progress*100:.1f}%)")
        logger.info(f"  Rate: {rate:.1f} edges/sec")
        logger.info(f"  Elapsed: {elapsed/3600:.2f} hours")
        logger.info(f"  ETA: {eta_seconds/3600:.2f} hours")

        # Update progress JSON for external monitoring
        update_progress(
            step="A3_pc_stable",
            pct=progress * 100,
            elapsed_min=elapsed / 60,
            eta_min=eta_seconds / 60,
            items_done=chunk_end,
            items_total=total_edges,
            extra={"validated_edges": len(validated_edges), "rate_per_sec": round(rate, 1)}
        )

    logger.info("\n" + "="*80)
    logger.info("PAIRWISE PC-STABLE COMPLETE")
    logger.info("="*80)
    logger.info(f"  Input edges: {total_edges:,}")
    logger.info(f"  Validated edges: {len(validated_edges):,}")
    logger.info(f"  Reduction: {(1 - len(validated_edges)/total_edges)*100:.1f}%")
    logger.info(f"\n  Removed edges breakdown:")
    logger.info(f"    Insufficient observations: {failed_stats.get('insufficient_obs', 0):,}")
    logger.info(f"    Missing variables: {failed_stats.get('missing_variable', 0):,}")
    logger.info(f"    Confounded: {failed_stats.get('confounded', 0):,}")
    logger.info(f"\n  Runtime: {elapsed/3600:.2f} hours")
    logger.info("="*80)

    return pd.DataFrame(validated_edges), failed_stats

def validate_dag(edges_df):
    """Validate DAG properties"""
    import networkx as nx

    logger.info("\n" + "="*80)
    logger.info("DAG VALIDATION")
    logger.info("="*80)

    # Build graph
    G = nx.DiGraph()
    for _, edge in edges_df.iterrows():
        G.add_edge(edge['source'], edge['target'])

    n_edges = G.number_of_edges()
    n_nodes = G.number_of_nodes()

    logger.info(f"  Nodes: {n_nodes:,}")
    logger.info(f"  Edges: {n_edges:,}")

    # Check DAG
    is_dag = nx.is_directed_acyclic_graph(G)
    logger.info(f"\n  DAG: {is_dag}")

    if not is_dag:
        logger.warning("  ⚠️  Cycles detected!")
        try:
            cycles = list(nx.simple_cycles(G))
            logger.warning(f"  Found {len(cycles)} cycles")
            if len(cycles) > 0:
                logger.warning(f"  Sample cycle: {cycles[0]}")
        except:
            pass
    else:
        logger.info("  ✅ No cycles (valid DAG)")

    # Connectivity
    if n_nodes > 0:
        largest_cc = max(nx.weakly_connected_components(G), key=len)
        connectivity = len(largest_cc) / n_nodes
        logger.info(f"\n  Connectivity: {connectivity:.1%}")

        if connectivity > 0.80:
            logger.info("  ✅ Good connectivity (>80%)")
        else:
            logger.warning(f"  ⚠️  Graph fragmented (<80%)")
    else:
        connectivity = 0.0

    # Target range check
    logger.info(f"\n  Edge count check:")
    if 30_000 <= n_edges <= 80_000:
        logger.info(f"  ✅ Within target range (30K-80K)")
    elif n_edges < 30_000:
        logger.warning(f"  ⚠️  Below target range (<30K)")
    else:
        logger.warning(f"  ⚠️  Above target range (>80K)")

    logger.info("="*80)

    return {
        'is_dag': is_dag,
        'n_nodes': n_nodes,
        'n_edges': n_edges,
        'connectivity': connectivity,
        'graph': G
    }

def save_output(edges_df, validation_results, failed_stats, runtime_hours):
    """Save final A3 output"""
    logger.info("\n" + "="*80)
    logger.info("SAVING OUTPUT")
    logger.info("="*80)

    output_dir = A3_OUTPUT
    output_dir.mkdir(parents=True, exist_ok=True)

    output = {
        'validated_edges': edges_df,
        'graph': validation_results['graph'],
        'validation': {
            'is_dag': validation_results['is_dag'],
            'n_nodes': validation_results['n_nodes'],
            'n_edges': validation_results['n_edges'],
            'connectivity': validation_results['connectivity']
        },
        'failed_stats': failed_stats,
        'metadata': {
            'timestamp': datetime.now().isoformat(),
            'runtime_hours': runtime_hours,
            'method': 'Custom Pairwise PC-Stable',
            'parameters': {
                'max_cond_size': 2,
                'max_confounders': 10,
                'min_obs': 30,
                'independence_threshold': 0.05
            }
        }
    }

    # Save pickle
    output_file = output_dir / 'A3_validated_edges.pkl'
    with open(output_file, 'wb') as f:
        pickle.dump(output, f)

    logger.info(f"  ✅ Saved: {output_file}")

    # Save edge list CSV
    edge_list = edges_df[['source', 'target', 'f_statistic', 'p_value_fdr']].copy()
    csv_file = output_dir / 'A3_edge_list.csv'
    edge_list.to_csv(csv_file, index=False)

    logger.info(f"  ✅ Saved: {csv_file}")
    logger.info("="*80)

def main():
    """Main pipeline"""
    overall_start = time.time()

    logger.info("\n" + "="*80)
    logger.info("A3 CUSTOM PAIRWISE PC-STABLE")
    logger.info("="*80)
    logger.info(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("="*80)

    # Load data
    edges_df = load_prepruned_edges()
    data_dict = load_imputed_data()

    # Run pairwise PC-Stable
    validated_edges, failed_stats = pairwise_pc_stable(
        edges_df, data_dict,
        max_cond_size=2,
        max_confounders=10,
        min_obs=30,
        alpha=0.001,  # Fisher-Z test significance level
        n_cores=8,
        checkpoint_every=5000
    )

    # Validate DAG
    validation_results = validate_dag(validated_edges)

    # Save output
    runtime_hours = (time.time() - overall_start) / 3600
    save_output(validated_edges, validation_results, failed_stats, runtime_hours)

    logger.info("\n" + "="*80)
    logger.info("✅ A3 COMPLETE")
    logger.info(f"  Runtime: {runtime_hours:.2f} hours")
    logger.info(f"  Final edges: {len(validated_edges):,}")
    logger.info("="*80 + "\n")

if __name__ == '__main__':
    main()
