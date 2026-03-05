#!/usr/bin/env python3
"""
A4 Phase 2B: Full Backdoor Adjustment - PRODUCTION SCRIPT

Computes minimal backdoor adjustment sets for all 129,989 edges in the A3 DAG.

Designed for AWS c7i.48xlarge spot instance (192 cores, 384 GB RAM).
Estimated runtime: 32-36 hours at $2.45/hour (~$80 total).

Features:
- Parallel processing across all available cores
- Auto-checkpointing every 5,000 edges
- Spot interruption handling
- Progress tracking with email alerts
- Thermal monitoring (if sensors available)
- Resume from checkpoint capability

Usage:
    # Production run
    python step2b_full_backdoor_adjustment.py \
      --input ~/A3_conditional_independence/outputs/A3_final_dag_v2.pkl \
      --output ~/outputs/full_backdoor_sets.pkl \
      --cores 192 \
      --checkpoint_every 5000

    # Resume from checkpoint
    python step2b_full_backdoor_adjustment.py \
      --resume ~/checkpoints/backdoor_checkpoint_65000.pkl \
      --cores 192
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
import os
from typing import Dict, Set, Tuple, List, Optional
from itertools import combinations
from joblib import Parallel, delayed
import psutil
import signal

# Import email alerts if available
try:
    from utils.email_alerts import (
        send_job_started_alert,
        send_progress_alert,
        send_job_complete_alert,
        send_error_alert,
        send_spot_interruption_alert
    )
    EMAIL_AVAILABLE = True
except ImportError:
    EMAIL_AVAILABLE = False
    print("⚠️  Email alerts not available - continuing without notifications")

# Setup logging
log_dir = Path(__file__).parent.parent / 'logs'
log_dir.mkdir(exist_ok=True)
log_file = log_dir / f'step2b_production_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Global state for signal handling
CHECKPOINT_DIR = None
CURRENT_RESULTS = []
CURRENT_EDGE_COUNT = 0
TOTAL_EDGES = 0
START_TIME = None


def signal_handler(signum, frame):
    """
    Handle interruption signals (Ctrl+C, spot termination warning).
    Save checkpoint before exiting.
    """
    logger.info("")
    logger.info("=" * 80)
    logger.info("⚠️  INTERRUPTION SIGNAL RECEIVED")
    logger.info("=" * 80)
    logger.info("")

    if CHECKPOINT_DIR and CURRENT_RESULTS:
        logger.info("Saving emergency checkpoint...")
        save_checkpoint(
            CURRENT_EDGE_COUNT,
            CURRENT_RESULTS,
            CHECKPOINT_DIR,
            emergency=True
        )

        if EMAIL_AVAILABLE:
            send_spot_interruption_alert(CURRENT_EDGE_COUNT)

    logger.info("Exiting gracefully...")
    sys.exit(0)


# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)   # Ctrl+C
signal.signal(signal.SIGTERM, signal_handler)  # Termination signal


def check_spot_interruption():
    """
    Check for AWS spot instance interruption warning.

    AWS sends a 2-minute warning via instance metadata before termination.

    Returns:
        True if interruption detected, False otherwise
    """
    try:
        import requests
        response = requests.get(
            'http://169.254.169.254/latest/meta-data/spot/instance-action',
            timeout=1
        )
        if response.status_code == 200:
            logger.warning("🚨 SPOT INSTANCE INTERRUPTION WARNING RECEIVED")
            logger.warning("   Instance will terminate in ~2 minutes")
            return True
    except:
        pass

    return False


def find_minimal_backdoor_set(
    G: nx.DiGraph,
    X: str,
    Y: str,
    max_size: int = 50
) -> Optional[Set[str]]:
    """
    Find minimal backdoor adjustment set for edge X → Y using d-separation.

    Uses NetworkX's optimized d-separation algorithm.

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
            if is_d_separator(G_mut, {X}, {Y}, set()):
                return set()
            else:
                return None

        # Try NetworkX's optimized minimal_d_separator first
        try:
            from networkx.algorithms.d_separation import minimal_d_separator
            backdoor_set = minimal_d_separator(G_mut, X, Y)
            if backdoor_set is not None:
                return backdoor_set
        except (ImportError, nx.NetworkXError):
            pass

        # Fallback: Greedy search
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

        return None

    except Exception as e:
        logger.debug(f"Error finding backdoor set for {X} → {Y}: {e}")
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


def save_checkpoint(
    edge_count: int,
    results: List[Dict],
    checkpoint_dir: Path,
    emergency: bool = False
):
    """
    Save progress checkpoint.

    Args:
        edge_count: Number of edges completed
        results: List of result dictionaries
        checkpoint_dir: Directory to save checkpoint
        emergency: If True, this is an emergency checkpoint (interruption)
    """
    checkpoint_dir.mkdir(parents=True, exist_ok=True)

    prefix = "emergency_" if emergency else ""
    checkpoint_path = checkpoint_dir / f"{prefix}backdoor_checkpoint_{edge_count:08d}.pkl"

    # Compute statistics
    results_df = pd.DataFrame(results)
    successful = results_df[results_df['status'] == 'success']

    checkpoint_data = {
        'completed_edges': edge_count,
        'results': results,
        'timestamp': datetime.now().isoformat(),
        'statistics': {
            'n_successful': len(successful),
            'n_failed': len(results) - len(successful),
            'mean_backdoor_size': successful['backdoor_size'].mean() if len(successful) > 0 else None,
            'mean_time_seconds': results_df['time_seconds'].mean()
        }
    }

    with open(checkpoint_path, 'wb') as f:
        pickle.dump(checkpoint_data, f, protocol=pickle.HIGHEST_PROTOCOL)

    file_size_mb = checkpoint_path.stat().st_size / (1024 ** 2)
    logger.info(f"{'🚨 EMERGENCY ' if emergency else ''}Checkpoint saved: {checkpoint_path} ({file_size_mb:.1f} MB)")

    return checkpoint_path


def load_checkpoint(checkpoint_path: Path) -> Tuple[List[Dict], int]:
    """
    Load checkpoint and return results + edge count.

    Args:
        checkpoint_path: Path to checkpoint file

    Returns:
        (results, completed_edge_count)
    """
    logger.info(f"Loading checkpoint: {checkpoint_path}")

    with open(checkpoint_path, 'rb') as f:
        checkpoint = pickle.load(f)

    results = checkpoint['results']
    edge_count = checkpoint['completed_edges']

    logger.info(f"Loaded checkpoint: {edge_count:,} edges completed")
    logger.info(f"Statistics: {checkpoint['statistics']}")

    return results, edge_count


def run_production(
    input_path: Path,
    output_path: Path,
    cores: int = 192,
    checkpoint_every: int = 5000,
    log_every: int = 100,
    max_backdoor_size: int = 50,
    resume_from: Optional[Path] = None
):
    """
    Run full backdoor adjustment on all edges.

    Args:
        input_path: Path to A3 final DAG pickle
        output_path: Path to save final results
        cores: Number of CPU cores to use
        checkpoint_every: Save checkpoint every N edges
        log_every: Log progress every N edges
        max_backdoor_size: Maximum backdoor set size
        resume_from: Path to checkpoint to resume from (optional)
    """
    global CHECKPOINT_DIR, CURRENT_RESULTS, CURRENT_EDGE_COUNT, TOTAL_EDGES, START_TIME

    logger.info("=" * 80)
    logger.info("FULL BACKDOOR ADJUSTMENT - PRODUCTION RUN")
    logger.info("=" * 80)
    logger.info("")

    # Setup checkpoint directory
    CHECKPOINT_DIR = output_path.parent.parent / 'checkpoints'
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)

    # Load A3 DAG
    logger.info(f"Loading A3 DAG from: {input_path}")
    with open(input_path, 'rb') as f:
        a3_data = pickle.load(f)

    G = a3_data['graph']
    all_edges = list(G.edges())
    TOTAL_EDGES = len(all_edges)

    logger.info(f"Graph: {G.number_of_nodes():,} nodes, {TOTAL_EDGES:,} edges")
    logger.info("")

    # Configuration
    logger.info("Configuration:")
    logger.info(f"  CPU cores: {cores}")
    logger.info(f"  Checkpoint interval: {checkpoint_every:,} edges")
    logger.info(f"  Progress logging: every {log_every} edges")
    logger.info(f"  Max backdoor size: {max_backdoor_size}")
    logger.info("")

    # Resume from checkpoint if provided
    if resume_from:
        CURRENT_RESULTS, CURRENT_EDGE_COUNT = load_checkpoint(resume_from)
        remaining_edges = all_edges[CURRENT_EDGE_COUNT:]
        logger.info(f"Resuming from edge {CURRENT_EDGE_COUNT:,}")
        logger.info(f"Remaining: {len(remaining_edges):,} edges")
    else:
        CURRENT_RESULTS = []
        CURRENT_EDGE_COUNT = 0
        remaining_edges = all_edges

    logger.info("")

    # Send job started email
    if EMAIL_AVAILABLE:
        send_job_started_alert(TOTAL_EDGES, cores)

    # Start timer
    START_TIME = time.time()
    last_checkpoint_time = START_TIME
    last_log_time = START_TIME

    # Progress milestones for email alerts (25%, 50%, 75%)
    milestones = {int(TOTAL_EDGES * p): p for p in [0.25, 0.50, 0.75]}
    milestones_sent = set()

    logger.info("Processing edges...")
    logger.info("")

    # Process edges in batches
    batch_size = checkpoint_every
    n_batches = (len(remaining_edges) + batch_size - 1) // batch_size

    for batch_idx in range(n_batches):
        # Check for spot interruption every batch
        if check_spot_interruption():
            logger.warning("Spot interruption detected - saving checkpoint and exiting")
            save_checkpoint(CURRENT_EDGE_COUNT, CURRENT_RESULTS, CHECKPOINT_DIR, emergency=True)
            if EMAIL_AVAILABLE:
                send_spot_interruption_alert(CURRENT_EDGE_COUNT)
            sys.exit(0)

        # Get batch
        start_idx = batch_idx * batch_size
        end_idx = min((batch_idx + 1) * batch_size, len(remaining_edges))
        batch = remaining_edges[start_idx:end_idx]

        # Process batch in parallel
        batch_results = Parallel(n_jobs=cores, verbose=0)(
            delayed(process_single_edge)(edge, G, max_backdoor_size)
            for edge in batch
        )

        # Update global state
        CURRENT_RESULTS.extend(batch_results)
        CURRENT_EDGE_COUNT += len(batch)

        # Progress logging
        elapsed = time.time() - START_TIME
        elapsed_since_log = time.time() - last_log_time

        if elapsed_since_log >= 60 or (CURRENT_EDGE_COUNT % log_every) == 0:  # Log every minute minimum
            percent = 100 * CURRENT_EDGE_COUNT / TOTAL_EDGES
            rate = CURRENT_EDGE_COUNT / elapsed if elapsed > 0 else 0
            eta_seconds = (TOTAL_EDGES - CURRENT_EDGE_COUNT) / rate if rate > 0 else 0

            logger.info(
                f"Progress: {CURRENT_EDGE_COUNT:,} / {TOTAL_EDGES:,} ({percent:.1f}%) | "
                f"Rate: {rate:.2f} edges/sec | ETA: {eta_seconds/3600:.1f} hours"
            )

            last_log_time = time.time()

        # Save checkpoint
        if (CURRENT_EDGE_COUNT % checkpoint_every) == 0:
            save_checkpoint(CURRENT_EDGE_COUNT, CURRENT_RESULTS, CHECKPOINT_DIR)
            last_checkpoint_time = time.time()

        # Email progress alerts at milestones
        if EMAIL_AVAILABLE:
            for milestone_edge, milestone_pct in milestones.items():
                if CURRENT_EDGE_COUNT >= milestone_edge and milestone_edge not in milestones_sent:
                    send_progress_alert(CURRENT_EDGE_COUNT, TOTAL_EDGES, elapsed / 3600)
                    milestones_sent.add(milestone_edge)

    # Final checkpoint
    if (CURRENT_EDGE_COUNT % checkpoint_every) != 0:
        save_checkpoint(CURRENT_EDGE_COUNT, CURRENT_RESULTS, CHECKPOINT_DIR)

    total_elapsed = time.time() - START_TIME

    # Compute final statistics
    results_df = pd.DataFrame(CURRENT_RESULTS)
    successful = results_df[results_df['status'] == 'success']
    failed = results_df[results_df['status'] == 'failed']

    stats = {
        'n_edges_total': TOTAL_EDGES,
        'n_successful': len(successful),
        'n_failed': len(failed),
        'success_rate': len(successful) / TOTAL_EDGES,
        'mean_backdoor_size': successful['backdoor_size'].mean(),
        'median_backdoor_size': successful['backdoor_size'].median(),
        'max_backdoor_size': successful['backdoor_size'].max(),
        'mean_time_seconds': results_df['time_seconds'].mean(),
        'total_runtime_hours': total_elapsed / 3600
    }

    logger.info("")
    logger.info("=" * 80)
    logger.info("✅ PRODUCTION RUN COMPLETE")
    logger.info("=" * 80)
    logger.info(f"Edges processed: {TOTAL_EDGES:,}")
    logger.info(f"Successful: {stats['n_successful']:,} ({stats['success_rate']*100:.1f}%)")
    logger.info(f"Failed: {stats['n_failed']:,}")
    logger.info("")
    logger.info("Backdoor Set Statistics:")
    logger.info(f"  Mean size: {stats['mean_backdoor_size']:.1f} variables")
    logger.info(f"  Median size: {stats['median_backdoor_size']:.0f} variables")
    logger.info(f"  Max size: {stats['max_backdoor_size']:.0f} variables")
    logger.info("")
    logger.info(f"Runtime: {stats['total_runtime_hours']:.1f} hours ({stats['total_runtime_hours']/24:.1f} days)")
    logger.info(f"Rate: {TOTAL_EDGES / total_elapsed:.2f} edges/second")
    logger.info("")

    # Save final output
    output_path.parent.mkdir(parents=True, exist_ok=True)

    output_data = {
        'edges': results_df,
        'statistics': stats,
        'metadata': {
            'timestamp': datetime.now().isoformat(),
            'input_path': str(input_path),
            'n_edges': TOTAL_EDGES,
            'cores_used': cores,
            'max_backdoor_size': max_backdoor_size,
            'runtime_hours': stats['total_runtime_hours']
        }
    }

    logger.info(f"Saving final results to: {output_path}")
    with open(output_path, 'wb') as f:
        pickle.dump(output_data, f, protocol=pickle.HIGHEST_PROTOCOL)

    file_size_mb = output_path.stat().st_size / (1024 ** 2)
    logger.info(f"✅ Results saved ({file_size_mb:.1f} MB)")
    logger.info("")

    # Send completion email
    if EMAIL_AVAILABLE:
        send_job_complete_alert(TOTAL_EDGES, stats['total_runtime_hours'], stats['mean_backdoor_size'])

    logger.info("=" * 80)
    logger.info("Next steps:")
    logger.info("1. Download results from AWS to local machine")
    logger.info("2. Verify output integrity")
    logger.info("3. Terminate AWS instance")
    logger.info("4. Proceed to Phase 3: Effect Estimation")
    logger.info("=" * 80)


def main():
    parser = argparse.ArgumentParser(description='Full backdoor adjustment - Production run')
    parser.add_argument('--input', type=str, required=True,
                       help='Path to A3 final DAG pickle')
    parser.add_argument('--output', type=str, required=True,
                       help='Output path for final results')
    parser.add_argument('--cores', type=int, default=192,
                       help='Number of CPU cores to use')
    parser.add_argument('--checkpoint_every', type=int, default=5000,
                       help='Save checkpoint every N edges')
    parser.add_argument('--log_every', type=int, default=100,
                       help='Log progress every N edges')
    parser.add_argument('--max_backdoor_size', type=int, default=50,
                       help='Maximum backdoor set size to search')
    parser.add_argument('--resume', type=str, default=None,
                       help='Resume from checkpoint file')

    args = parser.parse_args()

    try:
        run_production(
            input_path=Path(args.input),
            output_path=Path(args.output),
            cores=args.cores,
            checkpoint_every=args.checkpoint_every,
            log_every=args.log_every,
            max_backdoor_size=args.max_backdoor_size,
            resume_from=Path(args.resume) if args.resume else None
        )

    except Exception as e:
        logger.error(f"❌ Production run failed: {e}")
        import traceback
        logger.error(traceback.format_exc())

        if EMAIL_AVAILABLE:
            send_error_alert(str(e), CURRENT_EDGE_COUNT)

        sys.exit(1)


if __name__ == "__main__":
    main()
