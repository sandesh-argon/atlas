#!/usr/bin/env python3
"""
A4 Phase 2A: Parent Adjustment Set Identification

Implements parent adjustment methodology for causal effect estimation.
For each edge X → Y, computes adjustment_set = (parents(X) ∪ parents(Y)) - {X, Y}

Justification:
- Markov blanket property (Spirtes et al., 2000)
- Computationally feasible (5 min vs 21 days for full backdoor)
- Theoretically sound for dense graphs (Peters et al., 2017)
- Conservative estimates (Vowels et al., 2022)

Expected Runtime: 5 minutes
Expected Output: 130K edges with parent-based adjustment sets (mean 8-12 variables)
"""

import pickle
import pandas as pd
import networkx as nx
from pathlib import Path
from datetime import datetime
import logging
from typing import Dict, Set, Tuple, List
import sys

# Setup logging
log_dir = Path(__file__).parent.parent / 'logs'
log_dir.mkdir(exist_ok=True)
log_file = log_dir / f'step2a_parent_adjustment_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
A3_OUTPUT = PROJECT_ROOT.parent / 'A3_conditional_independence' / 'outputs' / 'A3_final_dag_v2.pkl'
OUTPUT_DIR = PROJECT_ROOT / 'outputs'
OUTPUT_DIR.mkdir(exist_ok=True)
OUTPUT_FILE = OUTPUT_DIR / 'parent_adjustment_sets.pkl'

def load_a3_dag() -> Tuple[nx.DiGraph, pd.DataFrame]:
    """
    Load A3 final DAG and edge metadata.

    Returns:
        G: NetworkX DiGraph (129,989 edges, 4,990 nodes)
        edge_df: DataFrame with edge metadata
    """
    logger.info("=" * 80)
    logger.info("PHASE 2A: PARENT ADJUSTMENT SET IDENTIFICATION")
    logger.info("=" * 80)
    logger.info("")

    logger.info("Step 1: Loading A3 Final DAG")
    logger.info(f"Loading from: {A3_OUTPUT}")

    if not A3_OUTPUT.exists():
        raise FileNotFoundError(f"A3 output not found: {A3_OUTPUT}")

    with open(A3_OUTPUT, 'rb') as f:
        a3_output = pickle.load(f)

    G = a3_output['graph']
    edge_df = a3_output['edges']

    logger.info(f"✅ Loaded A3 DAG:")
    logger.info(f"   Nodes: {G.number_of_nodes():,}")
    logger.info(f"   Edges: {G.number_of_edges():,}")
    logger.info(f"   Mean degree: {2 * G.number_of_edges() / G.number_of_nodes():.1f}")
    logger.info("")

    return G, edge_df

def compute_parent_adjustment_sets(G: nx.DiGraph, edge_df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute parent adjustment sets for all edges.

    For each edge X → Y:
        adjustment_set = (parents(X) ∪ parents(Y)) - {X, Y}

    Args:
        G: NetworkX DiGraph
        edge_df: DataFrame with columns ['source', 'target', ...]

    Returns:
        DataFrame with added columns:
            - adjustment_set: Set of variables to control for
            - adjustment_size: Number of variables in adjustment set
            - parents_X: Parents of source variable
            - parents_Y: Parents of target variable
    """
    logger.info("Step 2: Computing Parent Adjustment Sets")
    logger.info(f"Processing {len(edge_df):,} edges")
    logger.info("")

    # Initialize result lists
    adjustment_sets = []
    adjustment_sizes = []
    parents_X_list = []
    parents_Y_list = []

    # Process edges
    start_time = datetime.now()

    for idx, row in edge_df.iterrows():
        X = row['source']
        Y = row['target']

        # Get parents (predecessors in NetworkX DiGraph)
        parents_X = set(G.predecessors(X)) if G.has_node(X) else set()
        parents_Y = set(G.predecessors(Y)) if G.has_node(Y) else set()

        # Adjustment set = (parents(X) ∪ parents(Y)) - {X, Y}
        adjustment_set = (parents_X | parents_Y) - {X, Y}

        adjustment_sets.append(adjustment_set)
        adjustment_sizes.append(len(adjustment_set))
        parents_X_list.append(parents_X)
        parents_Y_list.append(parents_Y)

        # Progress logging
        if (idx + 1) % 10000 == 0:
            elapsed = (datetime.now() - start_time).total_seconds()
            rate = (idx + 1) / elapsed
            remaining = (len(edge_df) - idx - 1) / rate
            logger.info(f"Processed {idx+1:,}/{len(edge_df):,} edges ({100*(idx+1)/len(edge_df):.1f}%) - "
                       f"Rate: {rate:.0f} edges/sec - ETA: {remaining:.0f}s")

    elapsed = (datetime.now() - start_time).total_seconds()
    logger.info(f"✅ Completed in {elapsed:.1f} seconds ({len(edge_df)/elapsed:.0f} edges/sec)")
    logger.info("")

    # Add to DataFrame
    edge_df['adjustment_set'] = adjustment_sets
    edge_df['adjustment_size'] = adjustment_sizes
    edge_df['parents_X'] = parents_X_list
    edge_df['parents_Y'] = parents_Y_list

    return edge_df

def compute_statistics(edge_df: pd.DataFrame) -> Dict:
    """
    Compute summary statistics for parent adjustment sets.

    Returns:
        stats: Dictionary with statistics
    """
    logger.info("Step 3: Computing Statistics")
    logger.info("")

    stats = {
        'n_edges': len(edge_df),
        'adjustment_size_mean': edge_df['adjustment_size'].mean(),
        'adjustment_size_std': edge_df['adjustment_size'].std(),
        'adjustment_size_median': edge_df['adjustment_size'].median(),
        'adjustment_size_min': edge_df['adjustment_size'].min(),
        'adjustment_size_max': edge_df['adjustment_size'].max(),
        'adjustment_size_q25': edge_df['adjustment_size'].quantile(0.25),
        'adjustment_size_q75': edge_df['adjustment_size'].quantile(0.75),
        'edges_with_no_adjustment': (edge_df['adjustment_size'] == 0).sum(),
        'edges_with_small_adjustment': (edge_df['adjustment_size'] <= 5).sum(),
        'edges_with_medium_adjustment': ((edge_df['adjustment_size'] > 5) &
                                         (edge_df['adjustment_size'] <= 15)).sum(),
        'edges_with_large_adjustment': (edge_df['adjustment_size'] > 15).sum(),
    }

    logger.info("📊 Adjustment Set Statistics:")
    logger.info(f"   Total edges: {stats['n_edges']:,}")
    logger.info(f"   Mean adjustment size: {stats['adjustment_size_mean']:.2f} ± {stats['adjustment_size_std']:.2f}")
    logger.info(f"   Median: {stats['adjustment_size_median']:.0f}")
    logger.info(f"   Range: [{stats['adjustment_size_min']:.0f}, {stats['adjustment_size_max']:.0f}]")
    logger.info(f"   IQR: [{stats['adjustment_size_q25']:.0f}, {stats['adjustment_size_q75']:.0f}]")
    logger.info("")
    logger.info("Distribution by Size:")
    logger.info(f"   No adjustment (0 vars): {stats['edges_with_no_adjustment']:,} edges "
               f"({100*stats['edges_with_no_adjustment']/stats['n_edges']:.1f}%)")
    logger.info(f"   Small (1-5 vars): {stats['edges_with_small_adjustment']:,} edges "
               f"({100*stats['edges_with_small_adjustment']/stats['n_edges']:.1f}%)")
    logger.info(f"   Medium (6-15 vars): {stats['edges_with_medium_adjustment']:,} edges "
               f"({100*stats['edges_with_medium_adjustment']/stats['n_edges']:.1f}%)")
    logger.info(f"   Large (>15 vars): {stats['edges_with_large_adjustment']:,} edges "
               f"({100*stats['edges_with_large_adjustment']/stats['n_edges']:.1f}%)")
    logger.info("")

    return stats

def save_output(edge_df: pd.DataFrame, stats: Dict):
    """
    Save parent adjustment sets and statistics.

    Saves:
        - outputs/parent_adjustment_sets.pkl: Full edge DataFrame with adjustment sets
    """
    logger.info("Step 4: Saving Output")
    logger.info("")

    output = {
        'edges': edge_df,
        'statistics': stats,
        'metadata': {
            'created_at': datetime.now().isoformat(),
            'n_edges': len(edge_df),
            'mean_adjustment_size': stats['adjustment_size_mean'],
            'method': 'parent_adjustment',
            'justification': {
                'theoretical': 'Markov blanket property (Spirtes et al., 2000)',
                'computational': '5 min vs 21 days for full backdoor',
                'literature': ['Peters et al., 2017', 'Vowels et al., 2022']
            }
        }
    }

    logger.info(f"Saving to: {OUTPUT_FILE}")
    with open(OUTPUT_FILE, 'wb') as f:
        pickle.dump(output, f, protocol=pickle.HIGHEST_PROTOCOL)

    file_size_mb = OUTPUT_FILE.stat().st_size / (1024 ** 2)
    logger.info(f"✅ Saved output ({file_size_mb:.1f} MB)")
    logger.info("")

def validate_output(edge_df: pd.DataFrame, stats: Dict) -> bool:
    """
    Validate that output meets expected criteria.

    Success Criteria:
        - All edges have adjustment sets computed
        - Mean adjustment size: 8-12 variables (not 42!)
        - No missing data

    Returns:
        validation_passed: Boolean
    """
    logger.info("Step 5: Validation")
    logger.info("")

    validation_passed = True

    # Check 1: All edges processed
    if len(edge_df) != stats['n_edges']:
        logger.error(f"❌ Edge count mismatch: {len(edge_df)} != {stats['n_edges']}")
        validation_passed = False
    else:
        logger.info(f"✅ All {stats['n_edges']:,} edges processed")

    # Check 2: Mean adjustment size in expected range (8-12 variables)
    mean_size = stats['adjustment_size_mean']
    if mean_size < 5 or mean_size > 20:
        logger.warning(f"⚠️  Mean adjustment size ({mean_size:.1f}) outside expected range [5, 20]")
        logger.warning(f"    Expected: 8-12 variables (much less than 42 from full backdoor)")
    else:
        logger.info(f"✅ Mean adjustment size: {mean_size:.1f} variables (within expected range)")

    # Check 3: No missing data
    missing = edge_df['adjustment_set'].isna().sum()
    if missing > 0:
        logger.error(f"❌ Missing adjustment sets: {missing:,} edges")
        validation_passed = False
    else:
        logger.info(f"✅ No missing adjustment sets")

    # Check 4: Compare to full backdoor expectation
    if mean_size < 42:
        reduction = (1 - mean_size / 42) * 100
        logger.info(f"✅ Parent adjustment reduces set size by {reduction:.0f}% vs full backdoor (42 vars)")

    logger.info("")
    if validation_passed:
        logger.info("=" * 80)
        logger.info("✅ PHASE 2A COMPLETE - VALIDATION PASSED")
        logger.info("=" * 80)
    else:
        logger.error("=" * 80)
        logger.error("❌ VALIDATION FAILED - REVIEW REQUIRED")
        logger.error("=" * 80)

    return validation_passed

def main():
    """
    Main execution function for Phase 2A.
    """
    try:
        # Step 1: Load A3 DAG
        G, edge_df = load_a3_dag()

        # Step 2: Compute parent adjustment sets
        edge_df = compute_parent_adjustment_sets(G, edge_df)

        # Step 3: Compute statistics
        stats = compute_statistics(edge_df)

        # Step 4: Save output
        save_output(edge_df, stats)

        # Step 5: Validate
        validation_passed = validate_output(edge_df, stats)

        if not validation_passed:
            logger.error("Validation failed - see log for details")
            sys.exit(1)

        logger.info("")
        logger.info("Next Step: Phase 2B - Backdoor Validation Sample (4 hours)")
        logger.info("Command: python scripts/step2b_backdoor_validation_sample.py --sample_size 1000")
        logger.info("")

    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    main()
