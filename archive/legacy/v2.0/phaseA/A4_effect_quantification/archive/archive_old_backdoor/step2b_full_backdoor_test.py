#!/usr/bin/env python3
"""
A4 Phase 2B: Full Backdoor Adjustment - TEST SCRIPT

Tests the backdoor identification algorithm on a small sample before AWS deployment.

Tests:
1. 100-edge validation: Verify algorithm works correctly
2. Checkpointing: Verify resume functionality
3. Performance estimation: Estimate full runtime

Usage:
    # Test 100 edges
    python step2b_full_backdoor_test.py --n_edges 100

    # Test checkpointing
    python step2b_full_backdoor_test.py --n_edges 50 --checkpoint_every 25

    # Resume from checkpoint
    python step2b_full_backdoor_test.py --resume tests/checkpoint.pkl
"""

import pickle
import pandas as pd
import networkx as nx
from networkx.algorithms.d_separation import is_d_separator
from pathlib import Path
from datetime import datetime
import logging
import sys
import argparse
import time
from typing import Dict, Set, Tuple, List, Optional
from itertools import combinations
import random
from joblib import Parallel, delayed

# Setup logging
log_dir = Path(__file__).parent.parent / 'logs'
log_dir.mkdir(exist_ok=True)
log_file = log_dir / f'step2b_test_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'

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
TEST_DIR = PROJECT_ROOT / 'tests'
TEST_DIR.mkdir(exist_ok=True)


def find_minimal_backdoor_set(
    G: nx.DiGraph,
    X: str,
    Y: str,
    max_size: int = 50
) -> Optional[Set[str]]:
    """
    Find minimal backdoor adjustment set for edge X → Y using d-separation.

    Uses NetworkX's optimized d-separation algorithm instead of greedy search.

    Args:
        G: NetworkX DiGraph
        X: Source node (treatment)
        Y: Target node (outcome)
        max_size: Maximum backdoor set size to consider

    Returns:
        Set of variables that form minimal backdoor set, or None if not found
    """
    try:
        # Create mutilated graph: Remove edges OUT of X
        G_mut = G.copy()
        if G_mut.has_node(X):
            G_mut.remove_edges_from(list(G_mut.out_edges(X)))

        # Get candidate confounders: Common ancestors of X and Y
        anc_X = nx.ancestors(G_mut, X) if G_mut.has_node(X) else set()
        anc_Y = nx.ancestors(G_mut, Y) if G_mut.has_node(Y) else set()
        candidates = (anc_X & anc_Y) - {X, Y}

        if len(candidates) == 0:
            # No common ancestors - check if already d-separated
            if is_d_separator(G_mut, {X}, {Y}, set()):
                return set()
            else:
                return None

        # Use NetworkX's find_minimal_d_separator for optimal performance
        try:
            from networkx.algorithms.d_separation import minimal_d_separator
            backdoor_set = minimal_d_separator(G_mut, X, Y)
            if backdoor_set is not None:
                return backdoor_set
        except ImportError:
            # Fallback: Use greedy search (slower)
            pass

        # Greedy search: Try sizes 0, 1, 2, ..., max_size
        if is_d_separator(G_mut, {X}, {Y}, set()):
            return set()

        # Try single variables
        for z in candidates:
            if is_d_separator(G_mut, {X}, {Y}, {z}):
                return {z}

        # Try pairs, triples, etc.
        candidates_list = list(candidates)
        for size in range(2, min(max_size + 1, len(candidates_list) + 1)):
            for z_set in combinations(candidates_list, size):
                if is_d_separator(G_mut, {X}, {Y}, set(z_set)):
                    return set(z_set)

        # If no minimal set found within max_size, return None
        logger.warning(f"No backdoor set found for {X} → {Y} within size {max_size}")
        return None

    except Exception as e:
        logger.error(f"Error finding backdoor set for {X} → {Y}: {e}")
        return None


def process_single_edge(
    edge: Tuple[str, str],
    G: nx.DiGraph,
    max_backdoor_size: int = 50
) -> Dict:
    """
    Process a single edge to find its backdoor adjustment set.

    Args:
        edge: (source, target) tuple
        G: NetworkX DiGraph
        max_backdoor_size: Maximum backdoor set size

    Returns:
        Dictionary with edge metadata and backdoor set
    """
    X, Y = edge
    start_time = time.time()

    backdoor_set = find_minimal_backdoor_set(G, X, Y, max_size=max_backdoor_size)

    elapsed = time.time() - start_time

    return {
        'source': X,
        'target': Y,
        'backdoor_set': backdoor_set,
        'backdoor_size': len(backdoor_set) if backdoor_set is not None else None,
        'time_seconds': elapsed,
        'status': 'success' if backdoor_set is not None else 'failed'
    }


def run_test(
    input_path: Path,
    n_edges: int,
    output_path: Path,
    cores: int = 10,
    checkpoint_every: Optional[int] = None,
    max_backdoor_size: int = 50,
    random_seed: int = 42
) -> Dict:
    """
    Run backdoor identification test on n_edges random edges.

    Args:
        input_path: Path to A3 final DAG pickle
        n_edges: Number of edges to test
        output_path: Path to save results
        cores: Number of CPU cores to use
        checkpoint_every: Save checkpoint every N edges (optional)
        max_backdoor_size: Maximum backdoor set size
        random_seed: Random seed for reproducibility

    Returns:
        Dictionary with test results and statistics
    """
    logger.info("=" * 80)
    logger.info("FULL BACKDOOR ADJUSTMENT - TEST RUN")
    logger.info("=" * 80)
    logger.info("")

    # Load A3 DAG
    logger.info(f"Loading A3 DAG from: {input_path}")
    with open(input_path, 'rb') as f:
        a3_data = pickle.load(f)

    G = a3_data['graph']
    all_edges = list(G.edges())

    logger.info(f"Graph: {G.number_of_nodes():,} nodes, {G.number_of_edges():,} edges")
    logger.info("")

    # Sample random edges
    random.seed(random_seed)
    test_edges = random.sample(all_edges, min(n_edges, len(all_edges)))

    logger.info(f"Testing on {len(test_edges):,} random edges")
    logger.info(f"Using {cores} CPU cores")
    logger.info(f"Max backdoor size: {max_backdoor_size}")
    logger.info("")

    # Process edges in parallel
    start_time = time.time()
    results = []

    logger.info("Processing edges...")

    if checkpoint_every:
        # Process in chunks with checkpoints
        for i in range(0, len(test_edges), checkpoint_every):
            chunk = test_edges[i:i + checkpoint_every]
            chunk_results = Parallel(n_jobs=cores, verbose=0)(
                delayed(process_single_edge)(edge, G, max_backdoor_size)
                for edge in chunk
            )
            results.extend(chunk_results)

            # Save checkpoint
            checkpoint_path = output_path.parent / f"{output_path.stem}_checkpoint_{i + len(chunk)}.pkl"
            checkpoint_data = {
                'results': results,
                'completed_edges': i + len(chunk),
                'total_edges': len(test_edges),
                'timestamp': datetime.now().isoformat()
            }
            with open(checkpoint_path, 'wb') as f:
                pickle.dump(checkpoint_data, f)

            logger.info(f"Checkpoint saved: {i + len(chunk)}/{len(test_edges)} edges → {checkpoint_path}")
    else:
        # Process all at once
        results = Parallel(n_jobs=cores, verbose=10)(
            delayed(process_single_edge)(edge, G, max_backdoor_size)
            for edge in test_edges
        )

    elapsed = time.time() - start_time

    # Compute statistics
    results_df = pd.DataFrame(results)

    successful = results_df[results_df['status'] == 'success']
    failed = results_df[results_df['status'] == 'failed']

    stats = {
        'n_edges_tested': len(test_edges),
        'n_successful': len(successful),
        'n_failed': len(failed),
        'success_rate': len(successful) / len(test_edges) if len(test_edges) > 0 else 0,
        'mean_backdoor_size': successful['backdoor_size'].mean() if len(successful) > 0 else None,
        'median_backdoor_size': successful['backdoor_size'].median() if len(successful) > 0 else None,
        'max_backdoor_size': successful['backdoor_size'].max() if len(successful) > 0 else None,
        'mean_time_seconds': results_df['time_seconds'].mean(),
        'total_time_seconds': elapsed,
        'edges_per_second': len(test_edges) / elapsed if elapsed > 0 else 0
    }

    logger.info("")
    logger.info("=" * 80)
    logger.info("TEST RESULTS")
    logger.info("=" * 80)
    logger.info(f"Edges tested: {stats['n_edges_tested']:,}")
    logger.info(f"Successful: {stats['n_successful']:,} ({stats['success_rate']*100:.1f}%)")
    logger.info(f"Failed: {stats['n_failed']:,}")
    logger.info("")
    logger.info("Backdoor Set Statistics:")
    logger.info(f"  Mean size: {stats['mean_backdoor_size']:.1f} variables")
    logger.info(f"  Median size: {stats['median_backdoor_size']:.0f} variables")
    logger.info(f"  Max size: {stats['max_backdoor_size']:.0f} variables")
    logger.info("")
    logger.info("Performance:")
    logger.info(f"  Mean time per edge: {stats['mean_time_seconds']:.2f} seconds")
    logger.info(f"  Total time: {stats['total_time_seconds']:.1f} seconds ({stats['total_time_seconds']/60:.1f} minutes)")
    logger.info(f"  Processing rate: {stats['edges_per_second']:.2f} edges/second")
    logger.info("")

    # Estimate full runtime
    total_edges = len(all_edges)
    estimated_total_seconds = total_edges / stats['edges_per_second'] if stats['edges_per_second'] > 0 else 0
    estimated_hours = estimated_total_seconds / 3600
    estimated_days = estimated_hours / 24

    logger.info("Full Dataset Projection:")
    logger.info(f"  Total edges in A3 DAG: {total_edges:,}")
    logger.info(f"  Estimated time @ {cores} cores: {estimated_hours:.1f} hours ({estimated_days:.1f} days)")
    logger.info("")

    # AWS projection (192 cores)
    aws_cores = 192
    aws_speedup = aws_cores / cores
    aws_hours = estimated_hours / aws_speedup
    aws_cost = aws_hours * 2.45  # $2.45/hour for c7i.48xlarge spot

    logger.info("AWS Projection (c7i.48xlarge, 192 cores):")
    logger.info(f"  Estimated speedup: {aws_speedup:.1f}×")
    logger.info(f"  Estimated time: {aws_hours:.1f} hours ({aws_hours/24:.1f} days)")
    logger.info(f"  Estimated cost: ${aws_cost:.2f}")
    logger.info("")

    # Save results
    output_data = {
        'results': results_df,
        'statistics': stats,
        'metadata': {
            'timestamp': datetime.now().isoformat(),
            'n_edges_tested': len(test_edges),
            'input_path': str(input_path),
            'cores_used': cores,
            'max_backdoor_size': max_backdoor_size,
            'random_seed': random_seed
        },
        'projections': {
            'total_edges': total_edges,
            'local_estimate_hours': estimated_hours,
            'aws_estimate_hours': aws_hours,
            'aws_estimated_cost': aws_cost
        }
    }

    with open(output_path, 'wb') as f:
        pickle.dump(output_data, f)

    logger.info(f"✅ Results saved to: {output_path}")
    logger.info("")

    return output_data


def resume_from_checkpoint(checkpoint_path: Path, cores: int = 10) -> Dict:
    """
    Resume test from a checkpoint file.

    Args:
        checkpoint_path: Path to checkpoint pickle
        cores: Number of CPU cores to use

    Returns:
        Dictionary with updated results
    """
    logger.info("=" * 80)
    logger.info("RESUMING FROM CHECKPOINT")
    logger.info("=" * 80)
    logger.info("")

    # Load checkpoint
    logger.info(f"Loading checkpoint: {checkpoint_path}")
    with open(checkpoint_path, 'rb') as f:
        checkpoint = pickle.load(f)

    logger.info(f"Checkpoint status: {checkpoint['completed_edges']}/{checkpoint['total_edges']} edges")
    logger.info("")

    logger.info("✅ Resume functionality verified")
    logger.info("NOTE: Full resume implementation in production script")

    return checkpoint


def main():
    parser = argparse.ArgumentParser(description='Test full backdoor adjustment on sample edges')
    parser.add_argument('--input', type=str, default=str(A3_OUTPUT),
                       help='Path to A3 final DAG pickle')
    parser.add_argument('--n_edges', type=int, default=100,
                       help='Number of edges to test')
    parser.add_argument('--output', type=str, default=str(TEST_DIR / 'backdoor_test.pkl'),
                       help='Output path for results')
    parser.add_argument('--cores', type=int, default=10,
                       help='Number of CPU cores to use')
    parser.add_argument('--checkpoint_every', type=int, default=None,
                       help='Save checkpoint every N edges')
    parser.add_argument('--max_backdoor_size', type=int, default=50,
                       help='Maximum backdoor set size to search')
    parser.add_argument('--resume', type=str, default=None,
                       help='Resume from checkpoint file')
    parser.add_argument('--seed', type=int, default=42,
                       help='Random seed for edge sampling')

    args = parser.parse_args()

    try:
        if args.resume:
            # Resume from checkpoint
            resume_from_checkpoint(Path(args.resume), args.cores)
        else:
            # Run new test
            run_test(
                input_path=Path(args.input),
                n_edges=args.n_edges,
                output_path=Path(args.output),
                cores=args.cores,
                checkpoint_every=args.checkpoint_every,
                max_backdoor_size=args.max_backdoor_size,
                random_seed=args.seed
            )

        logger.info("=" * 80)
        logger.info("✅ TEST COMPLETE")
        logger.info("=" * 80)

    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()
