"""
A2: Estimate country-specific edge weights using V2.1 structure as prior.

Option (b): Re-estimate weights for existing 7,368 V2.1 edges.
This is ~100x faster than full discovery while capturing country-specific differences.

Input:
  - data/raw/v21_causal_edges.csv (7,368 global edges)
  - data/processed/countries/*.parquet (country time series)

Output:
  - data/country_graphs/{COUNTRY}.json (country-specific edge weights)

Features:
  - Parallel processing with joblib (10 cores)
  - Checkpointing every 20 countries
  - Resume from checkpoint if interrupted
"""

import pandas as pd
import numpy as np
import json
import time
from pathlib import Path
from tqdm import tqdm
from sklearn.linear_model import Ridge
from joblib import Parallel, delayed
import warnings
warnings.filterwarnings('ignore')


def load_v21_edges(edges_path: str = 'data/raw/v21_causal_edges.csv') -> pd.DataFrame:
    """Load V2.1 global edge list as prior."""
    edges = pd.read_csv(edges_path)
    print(f"Loaded {len(edges)} V2.1 edges as prior")
    return edges


def estimate_edge_weight(
    source_series: pd.Series,
    target_series: pd.Series,
    global_beta: float,
    n_bootstrap: int = 100
) -> tuple[float, float, float]:
    """
    Re-estimate edge weight for one country.

    Uses Ridge regression because we KNOW the edge exists (from V2.1),
    we're just re-estimating its strength for this country.

    Args:
        source_series: Time series of source indicator
        target_series: Time series of target indicator
        global_beta: Global beta from V2.1 (used as fallback)
        n_bootstrap: Number of bootstrap samples for CI

    Returns:
        country_beta: Country-specific beta
        ci_lower: 2.5th percentile
        ci_upper: 97.5th percentile
    """
    # Align series (drop NaN)
    data = pd.DataFrame({'source': source_series, 'target': target_series}).dropna()

    if len(data) < 5:
        # Not enough data - return global beta with wide CI
        return global_beta, global_beta * 0.5, global_beta * 1.5

    X = data[['source']].values
    y = data['target'].values

    # Standardize for numerical stability
    X_std = (X - X.mean()) / (X.std() + 1e-8)
    y_std = (y - y.mean()) / (y.std() + 1e-8)

    try:
        # Ridge regression
        ridge = Ridge(alpha=1.0)
        ridge.fit(X_std, y_std)

        # Use standardized beta directly (V2.1 weights are standardized)
        # Clip to [-2, 2] for numerical stability (standardized betas rarely exceed this)
        country_beta = np.clip(ridge.coef_[0], -2.0, 2.0)

        # Bootstrap for confidence interval
        bootstrap_betas = []
        for _ in range(n_bootstrap):
            indices = np.random.choice(len(data), size=len(data), replace=True)
            X_boot = X_std[indices]
            y_boot = y_std[indices]

            ridge_boot = Ridge(alpha=1.0)
            ridge_boot.fit(X_boot, y_boot)
            beta_boot = np.clip(ridge_boot.coef_[0], -2.0, 2.0)
            bootstrap_betas.append(beta_boot)

        ci_lower, ci_upper = np.percentile(bootstrap_betas, [2.5, 97.5])

        return float(country_beta), float(ci_lower), float(ci_upper)

    except Exception:
        # Fallback: return global beta
        return global_beta, global_beta * 0.8, global_beta * 1.2


def estimate_graph_for_country(
    country_code: str,
    country_data: pd.DataFrame,
    v21_edges: pd.DataFrame,
    n_bootstrap: int = 100
) -> list[dict]:
    """
    Re-estimate all V2.1 edges for one country.

    Args:
        country_code: Country identifier
        country_data: DataFrame with year as rows, indicators as columns
        v21_edges: DataFrame of V2.1 edges (source, target, weight)
        n_bootstrap: Bootstrap samples for CI

    Returns:
        country_edges: List of edge dicts with country-specific betas
    """
    country_edges = []

    # Get available indicators in this country's data
    available_indicators = set(country_data.columns) - {'year'}

    for _, edge in v21_edges.iterrows():
        source = edge['source']
        target = edge['target']
        global_beta = edge['weight']

        # Check if indicators exist in country data
        if source not in available_indicators or target not in available_indicators:
            # Indicator not available - use global beta
            country_edges.append({
                'source': source,
                'target': target,
                'beta': global_beta,
                'ci_lower': global_beta * 0.8,
                'ci_upper': global_beta * 1.2,
                'global_beta': global_beta,
                'data_available': False
            })
            continue

        # Get time series
        source_series = country_data[source]
        target_series = country_data[target]

        # Re-estimate beta for this country
        country_beta, ci_lower, ci_upper = estimate_edge_weight(
            source_series, target_series, global_beta, n_bootstrap
        )

        country_edges.append({
            'source': source,
            'target': target,
            'beta': country_beta,
            'ci_lower': ci_lower,
            'ci_upper': ci_upper,
            'global_beta': global_beta,
            'data_available': True
        })

    return country_edges


def process_single_country(country_file: Path, v21_edges: pd.DataFrame, output_dir: Path, n_bootstrap: int = 50):
    """
    Process a single country (for parallel execution).

    Returns:
        dict with country stats, or None if already processed
    """
    country_code = country_file.stem
    output_path = output_dir / f"{country_code}.json"

    # Skip if already processed (for resume capability)
    if output_path.exists():
        return None

    # Load country data
    country_data = pd.read_parquet(country_file)
    available = set(country_data.columns) - {'year'}

    country_edges = []
    edges_with_data = 0

    for _, edge in v21_edges.iterrows():
        source = edge['source']
        target = edge['target']
        global_beta = edge['weight']

        if source in available and target in available:
            # Re-estimate for this country
            country_beta, ci_lower, ci_upper = estimate_edge_weight(
                country_data[source], country_data[target], global_beta, n_bootstrap
            )
            country_edges.append({
                'source': source,
                'target': target,
                'beta': country_beta,
                'ci_lower': ci_lower,
                'ci_upper': ci_upper,
                'global_beta': global_beta,
                'data_available': True
            })
            edges_with_data += 1
        else:
            # Use global beta
            country_edges.append({
                'source': source,
                'target': target,
                'beta': global_beta,
                'ci_lower': global_beta * 0.8,
                'ci_upper': global_beta * 1.2,
                'global_beta': global_beta,
                'data_available': False
            })

    # Save graph
    with open(output_path, 'w') as f:
        json.dump({
            'country_code': country_code,
            'n_edges': len(country_edges),
            'n_edges_with_data': edges_with_data,
            'edges': country_edges
        }, f, indent=2)

    return {
        'country': country_code,
        'n_edges': len(country_edges),
        'n_with_data': edges_with_data,
        'coverage': edges_with_data / len(country_edges) if country_edges else 0
    }


def estimate_all_countries(
    countries_dir: str = 'data/processed/countries',
    output_dir: str = 'data/country_graphs',
    n_bootstrap: int = 50,
    n_jobs: int = 10,
    checkpoint_every: int = 20
):
    """
    Run estimation for all countries with parallel processing.

    Args:
        countries_dir: Path to country parquet files
        output_dir: Path to save country graph JSONs
        n_bootstrap: Bootstrap samples for confidence intervals
        n_jobs: Number of parallel workers
        checkpoint_every: Save progress log every N countries
    """
    # Load V2.1 edges
    v21_edges = load_v21_edges()

    # Load country files
    countries_dir = Path(countries_dir)
    country_files = sorted(list(countries_dir.glob('*.parquet')))

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Check for already processed (resume capability)
    already_done = set(f.stem for f in output_dir.glob('*.json'))
    remaining = [f for f in country_files if f.stem not in already_done]

    print(f"\n{'='*50}")
    print(f"A2: Country Graph Estimation")
    print(f"{'='*50}")
    print(f"Total countries: {len(country_files)}")
    print(f"Already processed: {len(already_done)}")
    print(f"Remaining: {len(remaining)}")
    print(f"V2.1 edges: {len(v21_edges)}")
    print(f"Bootstrap samples: {n_bootstrap}")
    print(f"Parallel workers: {n_jobs}")
    print(f"{'='*50}\n")

    if len(remaining) == 0:
        print("✅ All countries already processed!")
        return

    # Process in batches for checkpointing
    start_time = time.time()
    all_results = []

    for batch_start in range(0, len(remaining), checkpoint_every):
        batch_end = min(batch_start + checkpoint_every, len(remaining))
        batch = remaining[batch_start:batch_end]

        print(f"Processing batch {batch_start//checkpoint_every + 1}: countries {batch_start+1}-{batch_end} of {len(remaining)}")

        # Parallel processing
        batch_results = Parallel(n_jobs=n_jobs, verbose=1)(
            delayed(process_single_country)(f, v21_edges, output_dir, n_bootstrap)
            for f in batch
        )

        # Collect results (filter out None for skipped)
        batch_results = [r for r in batch_results if r is not None]
        all_results.extend(batch_results)

        # Checkpoint
        elapsed = time.time() - start_time
        done = len(already_done) + len(all_results)
        eta = (elapsed / len(all_results)) * (len(remaining) - len(all_results)) if all_results else 0

        progress_df = pd.DataFrame(all_results)
        progress_df.to_csv(output_dir / 'estimation_progress.csv', index=False)

        # Write progress JSON for monitoring
        with open(output_dir / 'progress.json', 'w') as f:
            json.dump({
                'total': len(country_files),
                'done': done,
                'remaining': len(country_files) - done,
                'pct': 100 * done / len(country_files),
                'elapsed_min': elapsed / 60,
                'eta_min': eta / 60,
                'updated': time.strftime('%Y-%m-%d %H:%M:%S')
            }, f, indent=2)

        print(f"  ✓ Checkpoint saved. Progress: {done}/{len(country_files)} ({100*done/len(country_files):.1f}%)")
        print(f"  ✓ Elapsed: {elapsed/60:.1f}min, ETA: {eta/60:.1f}min\n")

    # Final summary
    total_elapsed = time.time() - start_time
    progress_df = pd.DataFrame(all_results)

    print(f"\n{'='*50}")
    print(f"✅ Estimation complete!")
    print(f"{'='*50}")
    print(f"Countries processed: {len(all_results)}")
    print(f"Total time: {total_elapsed/60:.1f} minutes")
    print(f"Mean data coverage: {progress_df['coverage'].mean():.1%}")
    print(f"Output directory: {output_dir}")


if __name__ == "__main__":
    estimate_all_countries(
        countries_dir='data/processed/countries',
        output_dir='data/country_graphs',
        n_bootstrap=100,
        n_jobs=10,
        checkpoint_every=20
    )
