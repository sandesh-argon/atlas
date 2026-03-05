#!/usr/bin/env python3
"""
A4 Phase 2: Parent Adjustment Set Identification (V2.1)

Implements parent adjustment methodology for causal effect estimation.
For each edge X -> Y, computes adjustment_set = (parents(X) | parents(Y)) - {X, Y}

Justification:
- Markov blanket property (Spirtes et al., 2000)
- Computationally feasible (5 min vs 21 days for full backdoor)
- Theoretically sound for dense graphs (Peters et al., 2017)
- Conservative estimates (Vowels et al., 2022)

V2.1 MODIFICATION: Uses v21_config for paths

Expected Runtime: 2-5 minutes
Expected Output: 58K edges with parent-based adjustment sets
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
from v21_config import A3_OUTPUT, A4_OUTPUT, LOG_DIR

# Setup logging
LOG_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / 'step2_parent_adjustment.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def load_a3_dag():
    """Load A3 final DAG and edge metadata."""
    logger.info("=" * 80)
    logger.info("A4 PHASE 2: PARENT ADJUSTMENT SET IDENTIFICATION")
    logger.info("=" * 80)

    a3_file = A3_OUTPUT / 'A3_final_dag.pkl'
    logger.info(f"\nLoading A3 DAG from: {a3_file}")

    with open(a3_file, 'rb') as f:
        a3_output = pickle.load(f)

    G = a3_output['graph']
    edge_df = a3_output['edges']

    logger.info(f"  Nodes: {G.number_of_nodes():,}")
    logger.info(f"  Edges: {G.number_of_edges():,}")
    logger.info(f"  Mean degree: {2 * G.number_of_edges() / G.number_of_nodes():.1f}")

    return G, edge_df


def compute_parent_adjustment_sets(G, edge_df):
    """
    Compute parent adjustment sets for all edges.

    For each edge X -> Y:
        adjustment_set = (parents(X) | parents(Y)) - {X, Y}
    """
    logger.info("\n" + "=" * 80)
    logger.info("Computing Parent Adjustment Sets")
    logger.info(f"Processing {len(edge_df):,} edges")

    adjustment_sets = []
    adjustment_sizes = []
    parents_X_list = []
    parents_Y_list = []

    start_time = datetime.now()

    for idx, row in edge_df.iterrows():
        X = row['source']
        Y = row['target']

        # Get parents (predecessors in NetworkX DiGraph)
        parents_X = set(G.predecessors(X)) if G.has_node(X) else set()
        parents_Y = set(G.predecessors(Y)) if G.has_node(Y) else set()

        # Adjustment set = (parents(X) | parents(Y)) - {X, Y}
        adjustment_set = (parents_X | parents_Y) - {X, Y}

        adjustment_sets.append(adjustment_set)
        adjustment_sizes.append(len(adjustment_set))
        parents_X_list.append(parents_X)
        parents_Y_list.append(parents_Y)

        if (idx + 1) % 10000 == 0:
            elapsed = (datetime.now() - start_time).total_seconds()
            rate = (idx + 1) / elapsed
            remaining = (len(edge_df) - idx - 1) / rate
            logger.info(f"  Processed {idx+1:,}/{len(edge_df):,} ({100*(idx+1)/len(edge_df):.1f}%) - "
                       f"Rate: {rate:.0f}/sec - ETA: {remaining:.0f}s")

    elapsed = (datetime.now() - start_time).total_seconds()
    logger.info(f"  Completed in {elapsed:.1f}s ({len(edge_df)/elapsed:.0f} edges/sec)")

    # Add to DataFrame
    edge_df = edge_df.copy()
    edge_df['adjustment_set'] = adjustment_sets
    edge_df['adjustment_size'] = adjustment_sizes
    edge_df['parents_X'] = parents_X_list
    edge_df['parents_Y'] = parents_Y_list

    return edge_df


def compute_statistics(edge_df):
    """Compute summary statistics for parent adjustment sets."""
    logger.info("\n" + "=" * 80)
    logger.info("Adjustment Set Statistics")

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
                                         (edge_df['adjustment_size'] <= 20)).sum(),
        'edges_with_large_adjustment': (edge_df['adjustment_size'] > 20).sum(),
    }

    logger.info(f"  Total edges: {stats['n_edges']:,}")
    logger.info(f"  Mean adjustment size: {stats['adjustment_size_mean']:.2f} +/- {stats['adjustment_size_std']:.2f}")
    logger.info(f"  Median: {stats['adjustment_size_median']:.0f}")
    logger.info(f"  Range: [{stats['adjustment_size_min']:.0f}, {stats['adjustment_size_max']:.0f}]")
    logger.info(f"  IQR: [{stats['adjustment_size_q25']:.0f}, {stats['adjustment_size_q75']:.0f}]")
    logger.info("")
    logger.info("Distribution by Size:")
    logger.info(f"  No adjustment (0 vars): {stats['edges_with_no_adjustment']:,} ({100*stats['edges_with_no_adjustment']/stats['n_edges']:.1f}%)")
    logger.info(f"  Small (1-5 vars): {stats['edges_with_small_adjustment']:,} ({100*stats['edges_with_small_adjustment']/stats['n_edges']:.1f}%)")
    logger.info(f"  Medium (6-20 vars): {stats['edges_with_medium_adjustment']:,} ({100*stats['edges_with_medium_adjustment']/stats['n_edges']:.1f}%)")
    logger.info(f"  Large (>20 vars): {stats['edges_with_large_adjustment']:,} ({100*stats['edges_with_large_adjustment']/stats['n_edges']:.1f}%)")

    return stats


def save_output(edge_df, stats):
    """Save parent adjustment sets."""
    logger.info("\n" + "=" * 80)
    logger.info("Saving Output")

    A4_OUTPUT.mkdir(parents=True, exist_ok=True)
    output_file = A4_OUTPUT / 'parent_adjustment_sets.pkl'

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
                'computational': '5 min vs days for full backdoor',
                'literature': ['Peters et al., 2017', 'Vowels et al., 2022']
            }
        }
    }

    with open(output_file, 'wb') as f:
        pickle.dump(output, f, protocol=pickle.HIGHEST_PROTOCOL)

    file_size_mb = output_file.stat().st_size / (1024 ** 2)
    logger.info(f"  Saved: {output_file} ({file_size_mb:.1f} MB)")

    return output_file


def validate_output(edge_df, stats):
    """Validate output meets expected criteria."""
    logger.info("\n" + "=" * 80)
    logger.info("Validation")

    validation_passed = True

    # Check 1: All edges processed
    if edge_df['adjustment_set'].isna().sum() > 0:
        logger.error("  Missing adjustment sets")
        validation_passed = False
    else:
        logger.info(f"  All {stats['n_edges']:,} edges have adjustment sets")

    # Check 2: Mean adjustment size reasonable
    mean_size = stats['adjustment_size_mean']
    if mean_size < 1 or mean_size > 50:
        logger.warning(f"  Mean adjustment size ({mean_size:.1f}) may be unusual")
    else:
        logger.info(f"  Mean adjustment size: {mean_size:.1f} variables")

    if validation_passed:
        logger.info("\n" + "=" * 80)
        logger.info("PHASE 2 COMPLETE - VALIDATION PASSED")
        logger.info("=" * 80)

    return validation_passed


def main():
    """Main execution function."""
    try:
        # Load A3 DAG
        G, edge_df = load_a3_dag()

        # Compute parent adjustment sets
        edge_df = compute_parent_adjustment_sets(G, edge_df)

        # Compute statistics
        stats = compute_statistics(edge_df)

        # Save output
        save_output(edge_df, stats)

        # Validate
        validation_passed = validate_output(edge_df, stats)

        if not validation_passed:
            sys.exit(1)

        logger.info("")
        logger.info("Next: Run step3_effect_estimation_lasso.py")
        logger.info("=" * 80 + "\n")

    except Exception as e:
        logger.error(f"Fatal error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()
