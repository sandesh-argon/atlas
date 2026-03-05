#!/usr/bin/env python3
"""
A4 Phase 3: Effect Estimation with LASSO-Regularized Parent Adjustment (V2.1)

Estimates causal effects for all edges using:
1. LASSO variable selection to reduce parent sets
2. OLS regression on selected controls
3. Bootstrap confidence intervals (100 iterations)
4. Filtering by effect size (|β|>0.12) and significance (CI doesn't cross 0)

Includes thermal monitoring and auto-checkpoint every 5000 edges.

V2.1 MODIFICATION: Uses v21_config for paths

Usage:
    # Test run (1000 edges)
    python scripts/step3_effect_estimation_lasso.py \
        --sample_size 1000 \
        --n_jobs 12

    # Full run (all 129,989 edges)
    python scripts/step3_effect_estimation_lasso.py \
        --n_jobs 12 \
        --bootstrap 100

Author: Claude & Sandesh
Date: November 17, 2025
"""

import warnings
warnings.filterwarnings('ignore')  # Suppress sklearn convergence warnings

import pickle
import pandas as pd
import numpy as np
from pathlib import Path
import argparse
import logging
from datetime import datetime
import sys
import time
import psutil

# V2.1 Configuration
sys.path.insert(0, str(Path(__file__).parent.parent))
from v21_config import A4_OUTPUT, A4_CHECKPOINTS, LOG_DIR, get_input_path

from sklearn.linear_model import LassoCV, LinearRegression
from sklearn.preprocessing import StandardScaler
from sklearn.utils import resample
from joblib import Parallel, delayed

# Suppress sklearn convergence warnings (they're expected with LASSO)
import warnings
from sklearn.exceptions import ConvergenceWarning
warnings.filterwarnings('ignore', category=ConvergenceWarning)
warnings.filterwarnings('ignore', message='Objective did not converge')

# Setup logging
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / 'step3_effect_estimation.log'
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Redirect stderr to log file so joblib verbose output is captured
# This enables intra-chunk progress monitoring via monitor.sh
class TeeStderr:
    """Tee stderr to both console and log file for joblib verbose output"""
    def __init__(self, log_file):
        self.terminal = sys.stderr
        self.log = open(log_file, 'a')
    def write(self, message):
        self.terminal.write(message)
        self.log.write(message)
        self.log.flush()
    def flush(self):
        self.terminal.flush()
        self.log.flush()

sys.stderr = TeeStderr(LOG_FILE)


class ThermalMonitor:
    """Monitor CPU temperature and usage"""
    def __init__(self, temp_limit=85, check_interval=60):
        self.temp_limit = temp_limit
        self.check_interval = check_interval
        self.last_check = time.time()
        self.warning_count = 0

    def check(self):
        """Check thermals, return True if safe"""
        if time.time() - self.last_check < self.check_interval:
            return True

        self.last_check = time.time()

        try:
            # Get CPU temps
            temps = psutil.sensors_temperatures()
            if 'coretemp' in temps:
                current_temps = [t.current for t in temps['coretemp']]
                max_temp = max(current_temps)

                if max_temp > self.temp_limit:
                    self.warning_count += 1
                    logger.warning(f"⚠️  CPU TEMP: {max_temp:.1f}°C (limit: {self.temp_limit}°C)")

                    if self.warning_count >= 3:
                        logger.error(f"🚨 THERMAL SHUTDOWN - {max_temp:.1f}°C for 3+ minutes")
                        return False
                else:
                    self.warning_count = 0
                    if int(time.time()) % 300 == 0:  # Log every 5 min
                        logger.info(f"✅ CPU temp: {max_temp:.1f}°C")
        except:
            pass  # Thermal sensors may not be available

        return True


def check_aws_spot_interruption():
    """
    Check for AWS SPOT instance interruption warning
    Returns True if interruption warning detected
    """
    try:
        import requests
        response = requests.get(
            'http://169.254.169.254/latest/meta-data/spot/instance-action',
            timeout=1
        )
        if response.status_code == 200:
            logger.warning("🚨 AWS SPOT INTERRUPTION WARNING - Instance will terminate in 2 minutes")
            return True
    except:
        pass  # Not on AWS or no interruption
    return False


def load_checkpoint(checkpoint_path):
    """Load results from checkpoint file"""
    logger.info(f"📂 Loading checkpoint: {checkpoint_path}")
    with open(checkpoint_path, 'rb') as f:
        checkpoint_data = pickle.load(f)

    results = checkpoint_data['results']
    # Support both key names for backwards compatibility
    edges_completed = checkpoint_data.get('edges_completed', checkpoint_data.get('edges_done', 0))
    logger.info(f"  ✅ Loaded {len(results):,} completed edges")
    logger.info(f"  Resuming from edge {edges_completed:,}")

    return results, edges_completed


def load_data(adjustment_sets_path, data_path):
    """Load parent adjustment sets and preprocessed data"""
    logger.info("=" * 80)
    logger.info("LOADING DATA")
    logger.info("=" * 80)

    # Load parent adjustment sets
    logger.info(f"Loading parent adjustment sets from: {adjustment_sets_path}")
    with open(adjustment_sets_path, 'rb') as f:
        adj_data = pickle.load(f)

    parent_sets_df = adj_data['edges']
    logger.info(f"  Loaded {len(parent_sets_df):,} edges with parent sets")

    # Load preprocessed data
    logger.info(f"\nLoading preprocessed data from: {data_path}")
    with open(data_path, 'rb') as f:
        data_dict = pickle.load(f)

    # Convert dict of DataFrames to panel format
    imputed_data = data_dict['imputed_data']
    logger.info(f"  Converting {len(imputed_data)} variables to panel format...")

    panel_data = {}
    for var_name, df in imputed_data.items():
        panel_data[var_name] = df.stack()

    data = pd.DataFrame(panel_data)
    logger.info(f"  Data shape: {data.shape}")
    logger.info(f"  Observations: {len(data):,}")
    logger.info(f"  Variables: {len(data.columns):,}")

    return parent_sets_df, data


def estimate_effect_lasso(X_col, Y_col, parents, data, bootstrap_n=100):
    """
    Estimate causal effect with LASSO variable selection

    Returns:
        dict with beta, ci, n_selected, status
    """
    # Suppress warnings in worker process
    import warnings
    from sklearn.exceptions import ConvergenceWarning
    warnings.filterwarnings('ignore', category=ConvergenceWarning)
    warnings.filterwarnings('ignore', message='Objective did not converge')

    try:
        # Extract data
        X_data = data[X_col].values
        Y_data = data[Y_col].values

        # Filter parents that exist in data
        parents_available = [p for p in parents if p in data.columns and p != X_col and p != Y_col]
        if len(parents_available) == 0:
            return {
                'status': 'no_parents',
                'beta': np.nan,
                'ci_lower': np.nan,
                'ci_upper': np.nan,
                'n_selected': 0
            }

        Z_data = data[parents_available].values

        # Remove missing values
        mask = ~(np.isnan(X_data) | np.isnan(Y_data) | np.isnan(Z_data).any(axis=1))
        X_clean = X_data[mask]
        Y_clean = Y_data[mask]
        Z_clean = Z_data[mask]

        if len(X_clean) < 50:
            return {
                'status': 'insufficient_data',
                'beta': np.nan,
                'ci_lower': np.nan,
                'ci_upper': np.nan,
                'n_selected': 0
            }

        # Standardize
        scaler_X = StandardScaler()
        scaler_Y = StandardScaler()
        scaler_Z = StandardScaler()

        X_scaled = scaler_X.fit_transform(X_clean.reshape(-1, 1)).ravel()
        Y_scaled = scaler_Y.fit_transform(Y_clean.reshape(-1, 1)).ravel()
        Z_scaled = scaler_Z.fit_transform(Z_clean)

        # LASSO variable selection
        lasso = LassoCV(cv=5, n_jobs=1, max_iter=1000, random_state=42)
        lasso.fit(Z_scaled, Y_scaled)

        # Get selected variables
        selected_mask = lasso.coef_ != 0
        n_selected = np.sum(selected_mask)

        if n_selected == 0:
            # No controls selected - direct effect
            Z_selected = np.zeros((len(X_scaled), 0))
        else:
            Z_selected = Z_scaled[:, selected_mask]

        # OLS on X + selected controls
        X_with_controls = np.column_stack([X_scaled.reshape(-1, 1), Z_selected]) if n_selected > 0 else X_scaled.reshape(-1, 1)

        model = LinearRegression()
        model.fit(X_with_controls, Y_scaled)
        beta = model.coef_[0]  # Effect of X on Y

        # Bootstrap confidence intervals
        bootstrap_betas = []
        for _ in range(bootstrap_n):
            # Resample
            sample_idx = resample(range(len(X_clean)), random_state=None)
            X_boot = X_clean[sample_idx]
            Y_boot = Y_clean[sample_idx]
            Z_boot = Z_clean[sample_idx]

            # Standardize
            X_boot_scaled = StandardScaler().fit_transform(X_boot.reshape(-1, 1)).ravel()
            Y_boot_scaled = StandardScaler().fit_transform(Y_boot.reshape(-1, 1)).ravel()
            Z_boot_scaled = StandardScaler().fit_transform(Z_boot)

            # LASSO selection
            lasso_boot = LassoCV(cv=5, n_jobs=1, max_iter=1000, random_state=None)
            lasso_boot.fit(Z_boot_scaled, Y_boot_scaled)

            boot_selected_mask = lasso_boot.coef_ != 0
            if np.sum(boot_selected_mask) > 0:
                Z_boot_selected = Z_boot_scaled[:, boot_selected_mask]
                X_boot_with_controls = np.column_stack([X_boot_scaled.reshape(-1, 1), Z_boot_selected])
            else:
                X_boot_with_controls = X_boot_scaled.reshape(-1, 1)

            # OLS
            model_boot = LinearRegression()
            model_boot.fit(X_boot_with_controls, Y_boot_scaled)
            bootstrap_betas.append(model_boot.coef_[0])

        # 95% CI
        ci_lower, ci_upper = np.percentile(bootstrap_betas, [2.5, 97.5])

        return {
            'status': 'success',
            'beta': beta,
            'ci_lower': ci_lower,
            'ci_upper': ci_upper,
            'n_selected': n_selected,
            'sample_size': len(X_clean)
        }

    except Exception as e:
        logger.warning(f"  Error on {X_col} → {Y_col}: {str(e)[:100]}")
        return {
            'status': 'error',
            'beta': np.nan,
            'ci_lower': np.nan,
            'ci_upper': np.nan,
            'n_selected': 0
        }


def run_effect_estimation(parent_sets_df, data, sample_size=None, n_jobs=12, bootstrap_n=100,
                         effect_threshold=0.12, checkpoint_every=5000, resume_results=None,
                         resume_edges_completed=0):
    """Run effect estimation on all (or sample of) edges"""
    logger.info("\n" + "=" * 80)
    logger.info("EFFECT ESTIMATION WITH LASSO")
    logger.info("=" * 80)

    # Sample or use all
    if sample_size:
        np.random.seed(42)
        edges_to_process = parent_sets_df.sample(n=min(sample_size, len(parent_sets_df)), random_state=42)
        logger.info(f"\n🧪 TEST RUN: Processing {len(edges_to_process):,} sample edges")
    else:
        edges_to_process = parent_sets_df
        logger.info(f"\n🚀 FULL RUN: Processing all {len(edges_to_process):,} edges")

    logger.info(f"Parallel cores: {n_jobs}")
    logger.info(f"Bootstrap iterations: {bootstrap_n}")
    logger.info(f"Effect threshold: |β| > {effect_threshold}")
    logger.info(f"Checkpoint every: {checkpoint_every:,} edges\n")

    # Resume handling
    if resume_results is not None:
        results = resume_results
        logger.info(f"🔄 RESUMING: Skipping first {resume_edges_completed:,} edges")
        edges_to_process = edges_to_process.iloc[resume_edges_completed:]
        logger.info(f"  Remaining edges: {len(edges_to_process):,}\n")
    else:
        results = []

    # Thermal monitor
    thermal = ThermalMonitor(temp_limit=85, check_interval=60)

    # Process in chunks for checkpointing
    chunk_size = checkpoint_every
    n_chunks = (len(edges_to_process) + chunk_size - 1) // chunk_size

    start_time = time.time()

    for chunk_idx in range(n_chunks):
        # Check thermals and AWS spot interruption
        if not thermal.check():
            logger.error("⛔ STOPPING: Thermal limit exceeded")
            break

        if check_aws_spot_interruption():
            logger.warning("🚨 AWS SPOT INTERRUPTION - Saving checkpoint and exiting gracefully")
            break

        chunk_start = chunk_idx * chunk_size
        chunk_end = min((chunk_idx + 1) * chunk_size, len(edges_to_process))
        chunk = edges_to_process.iloc[chunk_start:chunk_end]

        logger.info(f"\n📦 Chunk {chunk_idx + 1}/{n_chunks}: Edges {chunk_start:,} - {chunk_end:,}")

        # Process chunk in parallel
        def process_edge(row):
            result = estimate_effect_lasso(
                row['source'], row['target'], row['adjustment_set'],
                data, bootstrap_n=bootstrap_n
            )
            result['source'] = row['source']
            result['target'] = row['target']
            return result

        # Change verbose to 10 for progress updates
        # Use batch_size='auto' to prevent last-batch straggler slowdown
        chunk_results = Parallel(n_jobs=n_jobs, verbose=10, batch_size='auto')(
            delayed(process_edge)(row)
            for _, row in chunk.iterrows()
        )

        results.extend(chunk_results)

        # Progress
        elapsed = time.time() - start_time
        edges_done = len(results)
        rate = edges_done / elapsed if elapsed > 0 else 0
        eta_seconds = (len(edges_to_process) - edges_done) / rate if rate > 0 else 0
        eta_hours = eta_seconds / 3600

        logger.info(f"✅ Chunk complete: {edges_done:,}/{len(edges_to_process):,} ({100*edges_done/len(edges_to_process):.1f}%)")
        logger.info(f"   Rate: {rate:.2f} edges/sec | ETA: {eta_hours:.1f} hours")

        # Write progress JSON every chunk (for external monitoring)
        import json
        progress_file = A4_OUTPUT / 'progress.json'
        total_edges = len(edges_to_process) + resume_edges_completed
        with open(progress_file, 'w') as f:
            json.dump({
                'step': 'A4_effect_estimation',
                'pct': 100.0 * (edges_done + resume_edges_completed) / total_edges,
                'elapsed_min': elapsed / 60,
                'eta_min': eta_seconds / 60,
                'items_done': edges_done + resume_edges_completed,
                'items_total': total_edges,
                'updated': datetime.now().isoformat(),
                'rate_per_sec': rate
            }, f, indent=2)

        # Checkpoint pkl every 10 chunks (~5000 edges) to avoid excessive disk writes
        if (chunk_idx + 1) % 10 == 0 or chunk_idx == n_chunks - 1:
            checkpoint_path = A4_CHECKPOINTS / f"effect_estimation_checkpoint_{edges_done}.pkl"
            with open(checkpoint_path, 'wb') as f:
                pickle.dump({
                    'results': results,
                    'edges_done': edges_done,
                    'timestamp': datetime.now().isoformat()
                }, f)
            logger.info(f"💾 Checkpoint saved: {checkpoint_path}")

    results_df = pd.DataFrame(results)

    # Filter by effect size and significance
    logger.info("\n" + "=" * 80)
    logger.info("FILTERING RESULTS")
    logger.info("=" * 80)

    success_df = results_df[results_df['status'] == 'success'].copy()
    logger.info(f"\nSuccess rate: {len(success_df)}/{len(results_df)} ({100*len(success_df)/len(results_df):.1f}%)")

    if len(success_df) > 0:
        # Effect size filter
        large_effect = success_df[np.abs(success_df['beta']) > effect_threshold].copy()
        logger.info(f"\nLarge effects (|β| > {effect_threshold}): {len(large_effect):,} ({100*len(large_effect)/len(success_df):.1f}%)")

        # Significance filter (CI doesn't cross 0)
        significant = large_effect[
            (large_effect['ci_lower'] > 0) | (large_effect['ci_upper'] < 0)
        ].copy()
        logger.info(f"Significant (CI doesn't cross 0): {len(significant):,} ({100*len(significant)/len(large_effect):.1f}% of large)")

        logger.info(f"\n📊 Final validated edges: {len(significant):,}")
        logger.info(f"\nEffect size distribution:")
        logger.info(f"  Mean |β|: {np.abs(significant['beta']).mean():.3f}")
        logger.info(f"  Median |β|: {np.abs(significant['beta']).median():.3f}")
        logger.info(f"\nCI width distribution:")
        logger.info(f"  Mean width: {(significant['ci_upper'] - significant['ci_lower']).mean():.3f}")
        logger.info(f"  Median width: {(significant['ci_upper'] - significant['ci_lower']).median():.3f}")
        logger.info(f"\nSelected controls distribution:")
        logger.info(f"  Mean: {significant['n_selected'].mean():.1f}")
        logger.info(f"  Median: {significant['n_selected'].median():.0f}")

        return results_df, significant
    else:
        logger.warning("⚠️  No successful effect estimations")
        return results_df, pd.DataFrame()


def main():
    parser = argparse.ArgumentParser(description='Effect estimation with LASSO-regularized parent adjustment')
    parser.add_argument('--adjustment_sets', type=str,
                        default=str(A4_OUTPUT / 'parent_adjustment_sets.pkl'),
                        help='Path to parent adjustment sets pickle')
    parser.add_argument('--data', type=str,
                        default=str(get_input_path()),
                        help='Path to preprocessed data pickle')
    parser.add_argument('--sample_size', type=int, default=None,
                        help='Number of edges to test (default: None = all edges)')
    parser.add_argument('--n_jobs', type=int, default=12,
                        help='Number of parallel cores (default: 12)')
    parser.add_argument('--bootstrap', type=int, default=100,
                        help='Bootstrap iterations (default: 100)')
    parser.add_argument('--effect_threshold', type=float, default=0.12,
                        help='Minimum |beta| to keep (default: 0.12)')
    parser.add_argument('--checkpoint_every', type=int, default=500,
                        help='Checkpoint every N edges (default: 500 for ~1 min progress updates)')
    parser.add_argument('--output', type=str,
                        default=str(A4_OUTPUT / 'lasso_effect_estimates.pkl'),
                        help='Output path for results')
    parser.add_argument('--resume', type=str, default=None,
                        help='Resume from checkpoint file (e.g., checkpoints/effect_estimation_checkpoint_5000.pkl)')

    args = parser.parse_args()

    # Create output directories (V2.1: use config paths)
    A4_OUTPUT.mkdir(parents=True, exist_ok=True)
    A4_CHECKPOINTS.mkdir(parents=True, exist_ok=True)

    # Log start
    logger.info("=" * 80)
    logger.info("A4 PHASE 3: EFFECT ESTIMATION WITH LASSO")
    logger.info("=" * 80)
    logger.info(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Mode: {'TEST' if args.sample_size else 'FULL'}")
    if args.sample_size:
        logger.info(f"Sample size: {args.sample_size:,} edges")
    logger.info(f"Cores: {args.n_jobs}")
    logger.info(f"Bootstrap: {args.bootstrap}")
    logger.info("=" * 80)

    # Load data
    parent_sets_df, data = load_data(args.adjustment_sets, args.data)

    # Resume handling
    resume_results = None
    resume_edges_completed = 0
    if args.resume:
        resume_results, resume_edges_completed = load_checkpoint(args.resume)
        logger.info("")

    # Run estimation
    all_results, validated_edges = run_effect_estimation(
        parent_sets_df, data,
        sample_size=args.sample_size,
        n_jobs=args.n_jobs,
        bootstrap_n=args.bootstrap,
        effect_threshold=args.effect_threshold,
        checkpoint_every=args.checkpoint_every,
        resume_results=resume_results,
        resume_edges_completed=resume_edges_completed
    )

    # Save results
    logger.info("\n" + "=" * 80)
    logger.info("SAVING RESULTS")
    logger.info("=" * 80)

    output_data = {
        'all_results': all_results,
        'validated_edges': validated_edges,
        'metadata': {
            'timestamp': datetime.now().isoformat(),
            'sample_size': args.sample_size,
            'n_jobs': args.n_jobs,
            'bootstrap_n': args.bootstrap,
            'effect_threshold': args.effect_threshold,
            'n_total': len(all_results),
            'n_validated': len(validated_edges)
        }
    }

    with open(args.output, 'wb') as f:
        pickle.dump(output_data, f)

    logger.info(f"  Saved: {args.output}")
    logger.info("\n" + "=" * 80)
    logger.info("COMPLETE")
    logger.info("=" * 80)
    logger.info(f"Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Total edges processed: {len(all_results):,}")
    logger.info(f"Validated edges: {len(validated_edges):,}")
    logger.info("=" * 80)


if __name__ == "__main__":
    main()
