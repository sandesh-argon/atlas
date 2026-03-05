"""
C.1: Lag Structure Estimation

Estimate optimal time lags for each edge using Granger causality tests.
For each edge (A → B), test if past values of A help predict B beyond
what past values of B alone can predict.

Algorithm:
1. For each country graph
2. For each edge (source → target)
3. Extract time series for both indicators
4. Run Granger test at lags 1-5 years
5. Store optimal lag (lowest p-value if significant)

Output: Updated country graphs with 'lag' field per edge
"""

import json
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Optional
from concurrent.futures import ProcessPoolExecutor, as_completed
from tqdm import tqdm
import warnings
import time
import sys

# Suppress statsmodels warnings
warnings.filterwarnings('ignore')

from statsmodels.tsa.stattools import grangercausalitytests


# =============================================================================
# DATA LOADING
# =============================================================================

def load_panel_data(panel_path: str = 'data/raw/v21_panel_data_for_v3.parquet') -> pd.DataFrame:
    """Load panel data in long format."""
    return pd.read_parquet(panel_path)


def get_country_timeseries(panel_df: pd.DataFrame, country: str) -> pd.DataFrame:
    """
    Get time series data for a country in wide format.

    Returns:
        DataFrame with year as index, indicators as columns
    """
    country_data = panel_df[panel_df['country'] == country].copy()

    if len(country_data) == 0:
        return pd.DataFrame()

    # Pivot to wide format: rows=years, cols=indicators
    wide = country_data.pivot_table(
        index='year',
        columns='indicator_id',
        values='value',
        aggfunc='first'
    )

    return wide.sort_index()


def load_country_graph(country_code: str, graphs_dir: str = 'data/country_graphs') -> dict:
    """Load country graph JSON."""
    graph_path = Path(graphs_dir) / f"{country_code}.json"
    if not graph_path.exists():
        return None
    with open(graph_path) as f:
        return json.load(f)


def save_country_graph(graph: dict, country_code: str, graphs_dir: str = 'data/country_graphs'):
    """Save updated country graph."""
    graph_path = Path(graphs_dir) / f"{country_code}.json"
    with open(graph_path, 'w') as f:
        json.dump(graph, f, indent=2)


# =============================================================================
# GRANGER CAUSALITY TESTING
# =============================================================================

def test_granger_lag(
    source_series: pd.Series,
    target_series: pd.Series,
    max_lag: int = 5,
    min_obs: int = 15
) -> dict:
    """
    Test Granger causality and find optimal lag.

    Args:
        source_series: Time series of source indicator
        target_series: Time series of target indicator
        max_lag: Maximum lag to test (years)
        min_obs: Minimum observations required

    Returns:
        Dict with optimal_lag, p_value, f_stat, significant
    """
    # Align series and drop NaN
    combined = pd.DataFrame({
        'source': source_series,
        'target': target_series
    }).dropna()

    if len(combined) < min_obs:
        return {
            'optimal_lag': int(1),
            'p_value': float(1.0),
            'f_stat': float(0.0),
            'significant': False,
            'n_obs': int(len(combined))
        }

    # Granger test requires [target, source] order
    data = combined[['target', 'source']].values

    best_lag = 1
    best_pvalue = 1.0
    best_fstat = 0.0

    try:
        # Test each lag
        for lag in range(1, min(max_lag + 1, len(combined) // 3)):
            try:
                result = grangercausalitytests(data, maxlag=[lag], verbose=False)

                # Get F-test p-value (most common test)
                f_test = result[lag][0]['ssr_ftest']
                p_value = f_test[1]
                f_stat = f_test[0]

                if p_value < best_pvalue:
                    best_pvalue = p_value
                    best_fstat = f_stat
                    best_lag = lag

            except Exception:
                continue

    except Exception:
        pass

    # Ensure all values are JSON-serializable Python types
    return {
        'optimal_lag': int(best_lag),
        'p_value': float(best_pvalue),
        'f_stat': float(best_fstat),
        'significant': bool(best_pvalue < 0.05),
        'n_obs': int(len(combined))
    }


# =============================================================================
# COUNTRY PROCESSING
# =============================================================================

def process_country(
    country_code: str,
    panel_df: pd.DataFrame,
    graphs_dir: str = 'data/country_graphs',
    max_lag: int = 5
) -> dict:
    """
    Process all edges for a single country.

    Returns:
        Dict with country stats and updated graph
    """
    # Load graph
    graph = load_country_graph(country_code, graphs_dir)
    if graph is None:
        return {'country': country_code, 'status': 'no_graph', 'edges_processed': 0}

    # Get country time series
    ts_data = get_country_timeseries(panel_df, country_code)
    if ts_data.empty:
        return {'country': country_code, 'status': 'no_data', 'edges_processed': 0}

    available_indicators = set(ts_data.columns)

    edges_processed = 0
    edges_significant = 0
    lag_distribution = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}

    # Process each edge
    for edge in graph['edges']:
        source = edge['source']
        target = edge['target']

        # Check if both indicators have data
        if source not in available_indicators or target not in available_indicators:
            edge['lag'] = 1  # Default lag
            edge['lag_pvalue'] = 1.0
            edge['lag_significant'] = False
            continue

        # Run Granger test
        result = test_granger_lag(
            ts_data[source],
            ts_data[target],
            max_lag=max_lag
        )

        # Update edge
        edge['lag'] = result['optimal_lag']
        edge['lag_pvalue'] = result['p_value']
        edge['lag_significant'] = result['significant']

        edges_processed += 1
        if result['significant']:
            edges_significant += 1
            lag_distribution[result['optimal_lag']] = lag_distribution.get(result['optimal_lag'], 0) + 1

    # Save updated graph
    save_country_graph(graph, country_code, graphs_dir)

    return {
        'country': country_code,
        'status': 'success',
        'edges_processed': edges_processed,
        'edges_significant': edges_significant,
        'significant_pct': edges_significant / max(edges_processed, 1) * 100,
        'lag_distribution': lag_distribution
    }


def process_country_wrapper(args):
    """Wrapper for parallel processing."""
    country_code, panel_df, graphs_dir, max_lag = args
    try:
        return process_country(country_code, panel_df, graphs_dir, max_lag)
    except Exception as e:
        return {
            'country': country_code,
            'status': 'error',
            'error': str(e),
            'edges_processed': 0
        }


# =============================================================================
# MAIN EXECUTION
# =============================================================================

def estimate_all_lags(
    graphs_dir: str = 'data/country_graphs',
    panel_path: str = 'data/raw/v21_panel_data_for_v3.parquet',
    n_workers: int = 10,
    max_lag: int = 5,
    checkpoint_every: int = 10,
    test_countries: Optional[list] = None
):
    """
    Estimate lags for all country graphs.

    Args:
        graphs_dir: Directory with country graphs
        panel_path: Path to panel data
        n_workers: Number of parallel workers
        max_lag: Maximum lag to test
        checkpoint_every: Save checkpoint every N countries
        test_countries: If provided, only process these countries (for testing)
    """
    print("=" * 60)
    print("C.1: LAG STRUCTURE ESTIMATION")
    print("=" * 60)

    # Load panel data
    print("\nLoading panel data...")
    start_load = time.time()
    panel_df = load_panel_data(panel_path)
    print(f"  Loaded in {time.time() - start_load:.1f}s")
    print(f"  Shape: {panel_df.shape}")

    # Get list of countries
    graph_files = list(Path(graphs_dir).glob("*.json"))
    all_countries = [f.stem for f in graph_files]

    if test_countries:
        countries = [c for c in test_countries if c in all_countries]
    else:
        countries = all_countries

    print(f"\nCountries to process: {len(countries)}")
    print(f"Workers: {n_workers}")
    print(f"Max lag: {max_lag} years")

    # Check for existing checkpoint
    checkpoint_path = Path(graphs_dir) / "_lag_checkpoint.json"
    completed = set()
    if checkpoint_path.exists():
        with open(checkpoint_path) as f:
            checkpoint = json.load(f)
            completed = set(checkpoint.get('completed', []))
        print(f"  Resuming from checkpoint: {len(completed)} already done")

    # Filter out completed
    remaining = [c for c in countries if c not in completed]
    print(f"  Remaining: {len(remaining)}")

    if not remaining:
        print("\nAll countries already processed!")
        return

    # Process countries
    results = []
    start_time = time.time()

    # Prepare arguments
    args_list = [(c, panel_df, graphs_dir, max_lag) for c in remaining]

    print(f"\nProcessing {len(remaining)} countries...")

    with ProcessPoolExecutor(max_workers=n_workers) as executor:
        futures = {executor.submit(process_country_wrapper, args): args[0]
                   for args in args_list}

        with tqdm(total=len(remaining), desc="Countries") as pbar:
            for future in as_completed(futures):
                result = future.result()
                results.append(result)
                completed.add(result['country'])
                pbar.update(1)

                # Checkpoint
                if len(results) % checkpoint_every == 0:
                    with open(checkpoint_path, 'w') as f:
                        json.dump({'completed': list(completed)}, f)

    # Final checkpoint
    with open(checkpoint_path, 'w') as f:
        json.dump({'completed': list(completed)}, f)

    elapsed = time.time() - start_time

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    successful = [r for r in results if r['status'] == 'success']
    print(f"Processed: {len(successful)}/{len(remaining)} countries")
    print(f"Time: {elapsed:.1f}s ({elapsed/60:.1f} min)")
    print(f"Time per country: {elapsed/len(remaining):.2f}s")

    if successful:
        total_edges = sum(r['edges_processed'] for r in successful)
        total_significant = sum(r['edges_significant'] for r in successful)
        mean_significant_pct = np.mean([r['significant_pct'] for r in successful])

        print(f"\nEdges processed: {total_edges}")
        print(f"Edges with significant lag: {total_significant} ({total_significant/total_edges*100:.1f}%)")
        print(f"Mean significant per country: {mean_significant_pct:.1f}%")

        # Aggregate lag distribution
        total_lag_dist = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        for r in successful:
            for lag, count in r.get('lag_distribution', {}).items():
                total_lag_dist[int(lag)] = total_lag_dist.get(int(lag), 0) + count

        print(f"\nLag distribution (significant edges):")
        for lag in range(1, 6):
            count = total_lag_dist.get(lag, 0)
            pct = count / max(total_significant, 1) * 100
            bar = "█" * int(pct / 2)
            print(f"  {lag} year: {count:5d} ({pct:5.1f}%) {bar}")

    # Estimate full run time
    if test_countries and len(remaining) < len(all_countries):
        time_per_country = elapsed / len(remaining)
        total_estimate = time_per_country * len(all_countries)
        print(f"\n" + "=" * 60)
        print("ETA FOR FULL RUN")
        print("=" * 60)
        print(f"Test set: {len(remaining)} countries in {elapsed:.1f}s")
        print(f"Time per country: {time_per_country:.2f}s")
        print(f"Full run ({len(all_countries)} countries): {total_estimate/60:.1f} min ({total_estimate/3600:.1f} hours)")


def run_test_set(n_test: int = 10):
    """Run on a small test set to estimate ETA."""
    # Get diverse test countries
    test_countries = [
        'Australia', 'Rwanda', 'Brazil', 'India', 'Germany',
        'Nigeria', 'Japan', 'Mexico', 'Canada', 'Kenya'
    ][:n_test]

    print(f"Running test set with {len(test_countries)} countries...")
    print(f"Test countries: {test_countries}")

    estimate_all_lags(
        n_workers=10,
        max_lag=5,
        test_countries=test_countries
    )


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        run_test_set(10)
    else:
        estimate_all_lags(n_workers=10, max_lag=5)
