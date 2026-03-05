#!/usr/bin/env python3
"""
A4 Phase 2C: LASSO Selection Validation

Validates that LASSO can effectively reduce parent adjustment sets
from median 108 controls to ~30-50 effective controls while maintaining
statistical power.

Tests on 100 random edges to ensure approach is viable before full run.

Usage:
    python scripts/step2c_validate_lasso_selection.py \
        --adjustment_sets outputs/parent_adjustment_sets.pkl \
        --data ../A1_missingness_analysis/outputs/A2_preprocessed_data.pkl \
        --sample_size 100 \
        --output diagnostics/lasso_validation_results.pkl

Author: Claude & Sandesh
Date: November 17, 2025
"""

import pickle
import pandas as pd
import numpy as np
from pathlib import Path
import argparse
import logging
from datetime import datetime
import sys

from sklearn.linear_model import LassoCV
from sklearn.preprocessing import StandardScaler
from sklearn.utils import resample
from joblib import Parallel, delayed

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/step2c_lasso_validation.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


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
    logger.info(f"  Mean parent set size: {parent_sets_df['adjustment_set'].apply(len).mean():.1f}")
    logger.info(f"  Median parent set size: {parent_sets_df['adjustment_set'].apply(len).median():.0f}")

    # Load preprocessed data
    logger.info(f"\nLoading preprocessed data from: {data_path}")
    with open(data_path, 'rb') as f:
        data_dict = pickle.load(f)

    # Convert dict of DataFrames to panel format
    imputed_data = data_dict['imputed_data']
    logger.info(f"  Converting {len(imputed_data)} variables to panel format...")

    # Stack all variables into panel: (country, year) x variables
    panel_data = {}
    for var_name, df in imputed_data.items():
        # df is (country x years), we want to stack it
        panel_data[var_name] = df.stack()

    data = pd.DataFrame(panel_data)
    logger.info(f"  Data shape: {data.shape}")
    logger.info(f"  Observations: {len(data):,}")
    logger.info(f"  Variables: {len(data.columns):,}")

    return parent_sets_df, data


def test_lasso_selection(X_col, Y_col, parents, data, bootstrap_n=10):
    """
    Test LASSO selection on a single edge

    Returns:
        dict with selection statistics
    """
    try:
        # Extract data
        X_data = data[X_col].values
        Y_data = data[Y_col].values

        # Filter parents that exist in data
        parents_available = [p for p in parents if p in data.columns]
        if len(parents_available) == 0:
            return {
                'status': 'no_parents',
                'n_parents': 0,
                'n_selected': 0,
                'selection_stability': 0.0,
                'effective_df': len(data)
            }

        Z_data = data[parents_available].values

        # Remove missing values
        mask = ~(np.isnan(X_data) | np.isnan(Y_data) | np.isnan(Z_data).any(axis=1))
        X_clean = X_data[mask]
        Y_clean = Y_data[mask]
        Z_clean = Z_data[mask]

        if len(X_clean) < 50:  # Need minimum sample size
            return {
                'status': 'insufficient_data',
                'n_parents': len(parents_available),
                'n_selected': 0,
                'selection_stability': 0.0,
                'effective_df': len(X_clean)
            }

        # Standardize
        scaler_Z = StandardScaler()
        Z_scaled = scaler_Z.fit_transform(Z_clean)

        scaler_Y = StandardScaler()
        Y_scaled = scaler_Y.fit_transform(Y_clean.reshape(-1, 1)).ravel()

        # LASSO selection
        lasso = LassoCV(cv=5, n_jobs=1, max_iter=1000, random_state=42)
        lasso.fit(Z_scaled, Y_scaled)

        # Get selected variables
        selected_mask = lasso.coef_ != 0
        n_selected = np.sum(selected_mask)

        # Bootstrap stability (how often same variables selected)
        if bootstrap_n > 0:
            selection_counts = np.zeros(len(parents_available))

            for _ in range(bootstrap_n):
                # Resample
                sample_idx = resample(range(len(X_clean)), random_state=None)
                X_boot = X_clean[sample_idx]
                Y_boot = Y_clean[sample_idx]
                Z_boot = Z_clean[sample_idx]

                # Standardize
                Z_boot_scaled = StandardScaler().fit_transform(Z_boot)
                Y_boot_scaled = StandardScaler().fit_transform(Y_boot.reshape(-1, 1)).ravel()

                # LASSO
                lasso_boot = LassoCV(cv=5, n_jobs=1, max_iter=1000, random_state=None)
                lasso_boot.fit(Z_boot_scaled, Y_boot_scaled)

                # Track selections
                selection_counts += (lasso_boot.coef_ != 0).astype(int)

            # Stability: what fraction of bootstrap samples selected each variable
            selection_stability = (selection_counts / bootstrap_n)[selected_mask].mean() if n_selected > 0 else 0.0
        else:
            selection_stability = 1.0  # No bootstrap, assume stable

        # Effective degrees of freedom
        effective_df = len(X_clean) - n_selected - 1

        return {
            'status': 'success',
            'n_parents': len(parents_available),
            'n_selected': n_selected,
            'selection_stability': selection_stability,
            'effective_df': effective_df,
            'sample_size': len(X_clean)
        }

    except Exception as e:
        logger.warning(f"  Error on {X_col} → {Y_col}: {e}")
        return {
            'status': 'error',
            'n_parents': len(parents) if parents else 0,
            'n_selected': 0,
            'selection_stability': 0.0,
            'effective_df': 0
        }


def run_validation(parent_sets_df, data, sample_size=100, n_jobs=12):
    """Run LASSO validation on sample of edges"""
    logger.info("\n" + "=" * 80)
    logger.info("LASSO SELECTION VALIDATION")
    logger.info("=" * 80)

    # Sample random edges
    np.random.seed(42)
    sample_edges = parent_sets_df.sample(n=min(sample_size, len(parent_sets_df)), random_state=42)

    logger.info(f"\nTesting LASSO selection on {len(sample_edges):,} random edges...")
    logger.info(f"Using {n_jobs} parallel cores")
    logger.info("Estimated time: ~15-20 minutes with parallel processing\n")

    # Run in parallel
    logger.info("Starting parallel LASSO validation...")

    def process_edge(row):
        X = row['source']
        Y = row['target']
        parents = row['adjustment_set']
        result = test_lasso_selection(X, Y, parents, data, bootstrap_n=10)
        result['source'] = X
        result['target'] = Y
        return result

    results = Parallel(n_jobs=n_jobs, verbose=10)(
        delayed(process_edge)(row)
        for _, row in sample_edges.iterrows()
    )

    results_df = pd.DataFrame(results)

    # Summary statistics
    logger.info("\n" + "=" * 80)
    logger.info("VALIDATION RESULTS")
    logger.info("=" * 80)

    success_df = results_df[results_df['status'] == 'success']

    logger.info(f"\nSuccess rate: {len(success_df)}/{len(results_df)} ({100*len(success_df)/len(results_df):.1f}%)")

    if len(success_df) > 0:
        logger.info("\nParent set reduction:")
        logger.info(f"  Original parents (mean): {success_df['n_parents'].mean():.1f}")
        logger.info(f"  Original parents (median): {success_df['n_parents'].median():.0f}")
        logger.info(f"  Selected controls (mean): {success_df['n_selected'].mean():.1f}")
        logger.info(f"  Selected controls (median): {success_df['n_selected'].median():.0f}")
        logger.info(f"  Reduction: {100*(1 - success_df['n_selected'].mean()/success_df['n_parents'].mean()):.1f}%")

        logger.info("\nSelection stability:")
        logger.info(f"  Mean stability: {success_df['selection_stability'].mean():.3f}")
        logger.info(f"  Median stability: {success_df['selection_stability'].median():.3f}")
        logger.info(f"  (Stability = fraction of bootstrap samples selecting same variables)")

        logger.info("\nDegrees of freedom:")
        logger.info(f"  Mean effective df: {success_df['effective_df'].mean():.1f}")
        logger.info(f"  Median effective df: {success_df['effective_df'].median():.0f}")
        logger.info(f"  Min effective df: {success_df['effective_df'].min():.0f}")

        logger.info("\nSample size:")
        logger.info(f"  Mean sample size: {success_df['sample_size'].mean():.1f}")
        logger.info(f"  Median sample size: {success_df['sample_size'].median():.0f}")

        # Success criteria
        logger.info("\n" + "=" * 80)
        logger.info("SUCCESS CRITERIA CHECK")
        logger.info("=" * 80)

        mean_selected = success_df['n_selected'].mean()
        mean_df = success_df['effective_df'].mean()
        mean_stability = success_df['selection_stability'].mean()

        criteria = {
            'Mean selected controls 30-50': (30 <= mean_selected <= 50, mean_selected),
            'Mean effective df >100': (mean_df > 100, mean_df),
            'Mean stability >0.80': (mean_stability > 0.80, mean_stability)
        }

        all_pass = True
        for criterion, (passed, value) in criteria.items():
            status = "✅ PASS" if passed else "❌ FAIL"
            logger.info(f"  {status}: {criterion} (value: {value:.1f})")
            if not passed:
                all_pass = False

        if all_pass:
            logger.info("\n🎉 ALL CRITERIA PASSED - LASSO approach validated!")
            logger.info("Ready to proceed to Phase 3 (full effect estimation)")
        else:
            logger.warning("\n⚠️  Some criteria failed - review approach before proceeding")
    else:
        logger.error("\n❌ No successful LASSO selections - approach not viable")

    return results_df


def main():
    parser = argparse.ArgumentParser(description='Validate LASSO selection for parent adjustment')
    parser.add_argument('--adjustment_sets', type=str,
                        default='outputs/parent_adjustment_sets.pkl',
                        help='Path to parent adjustment sets pickle')
    parser.add_argument('--data', type=str,
                        default='../A1_missingness_analysis/outputs/A2_preprocessed_data.pkl',
                        help='Path to preprocessed data pickle')
    parser.add_argument('--sample_size', type=int, default=100,
                        help='Number of edges to test (default: 100)')
    parser.add_argument('--output', type=str,
                        default='diagnostics/lasso_validation_results.pkl',
                        help='Output path for validation results')
    parser.add_argument('--n_jobs', type=int, default=12,
                        help='Number of parallel cores to use (default: 12)')

    args = parser.parse_args()

    # Create output directory
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)

    # Log start
    logger.info("=" * 80)
    logger.info("A4 PHASE 2C: LASSO SELECTION VALIDATION")
    logger.info("=" * 80)
    logger.info(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Sample size: {args.sample_size} edges")
    logger.info("=" * 80)

    # Load data
    parent_sets_df, data = load_data(args.adjustment_sets, args.data)

    # Run validation
    results_df = run_validation(parent_sets_df, data, args.sample_size, args.n_jobs)

    # Save results
    logger.info("\n" + "=" * 80)
    logger.info("SAVING RESULTS")
    logger.info("=" * 80)

    output_data = {
        'results': results_df,
        'summary': {
            'n_tested': len(results_df),
            'n_success': len(results_df[results_df['status'] == 'success']),
            'mean_parents': results_df[results_df['status'] == 'success']['n_parents'].mean(),
            'mean_selected': results_df[results_df['status'] == 'success']['n_selected'].mean(),
            'mean_effective_df': results_df[results_df['status'] == 'success']['effective_df'].mean(),
            'mean_stability': results_df[results_df['status'] == 'success']['selection_stability'].mean()
        },
        'metadata': {
            'timestamp': datetime.now().isoformat(),
            'sample_size': args.sample_size,
            'adjustment_sets_path': args.adjustment_sets,
            'data_path': args.data
        }
    }

    with open(args.output, 'wb') as f:
        pickle.dump(output_data, f)

    logger.info(f"  Saved: {args.output}")
    logger.info("\n" + "=" * 80)
    logger.info("VALIDATION COMPLETE")
    logger.info("=" * 80)
    logger.info(f"Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 80)


if __name__ == "__main__":
    main()
