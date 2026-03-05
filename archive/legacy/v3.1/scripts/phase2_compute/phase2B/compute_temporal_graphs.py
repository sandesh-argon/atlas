#!/usr/bin/env python3
"""
Phase 2B: Compute Temporal Causal Graphs - Full Academic Spec

Features:
- Bootstrap CIs with Numba optimization
- Lag selection (0-5 years, select by R²)
- P-value from t-statistic
- DAG validation
- Non-linearity detection (top 500 edges)
- Saturation thresholds metadata

Output: data/v3_1_temporal_graphs/{countries}/{country}/{year}_graph.json
"""

import argparse
import json
import warnings
import time
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple, List, Dict

import numpy as np
import pandas as pd
from numba import njit
from scipy import stats
import networkx as nx
from multiprocessing import Pool
from tqdm import tqdm

warnings.filterwarnings('ignore')

# === PATHS ===
PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
PANEL_PATH = DATA_DIR / "raw" / "v21_panel_data_for_v3.parquet"
EDGES_PATH = DATA_DIR / "raw" / "v21_causal_edges.csv"
GRAPHS_DIR = DATA_DIR / "country_graphs"
OUTPUT_DIR = DATA_DIR / "v3_1_temporal_graphs"
METADATA_DIR = DATA_DIR / "metadata"

# === CONFIGURATION ===
MIN_YEAR = 1990
MAX_YEAR = 2024
YEARS = list(range(MIN_YEAR, MAX_YEAR + 1))

BOOTSTRAP_SAMPLES = 100
MIN_SAMPLES = 10
MAX_LAG = 5  # Test lags 0-5
N_JOBS = 4  # Start conservative, can increase
TOP_N_NONLINEAR = 500  # Test non-linearity for top N edges

# === SATURATION THRESHOLDS ===
# Applied during simulation, stored as metadata
SATURATION_THRESHOLDS = {
    # Education (%)
    'literacy_rate': 80,
    'SE.ADT.LITR.ZS': 80,
    'primary_completion': 90,
    'SE.PRM.CMPT.ZS': 90,

    # Economic ($)
    'gdp_per_capita': 50000,
    'NY.GDP.PCAP.CD': 50000,
    'NY.GDP.PCAP.PP.CD': 50000,

    # Health
    'life_expectancy': 78,
    'SP.DYN.LE00.IN': 78,

    # Infrastructure (%)
    'internet_access': 85,
    'IT.NET.USER.ZS': 85,
    'electricity_access': 95,
    'EG.ELC.ACCS.ZS': 95,

    # Governance (index 0-1)
    'democracy_index': 0.8,
    'v2x_polyarchy': 0.8,
}


# === NUMBA OPTIMIZED FUNCTIONS ===

@njit(cache=True)
def bootstrap_betas_numba(X_std: np.ndarray, y_std: np.ndarray,
                          n_bootstrap: int, seed: int) -> np.ndarray:
    """
    Numba-optimized bootstrap for beta coefficients.
    JIT compiled for speed, no internal parallelism (we parallelize at process level).
    """
    np.random.seed(seed)
    n = len(X_std)
    betas = np.zeros(n_bootstrap)

    for i in range(n_bootstrap):
        # Generate bootstrap indices
        indices = np.random.randint(0, n, n)
        X_boot = X_std[indices]
        y_boot = y_std[indices]

        # Compute beta: cov(X,Y)/var(X) for standardized = correlation
        numerator = 0.0
        denominator = 0.0
        for j in range(n):
            numerator += X_boot[j] * y_boot[j]
            denominator += X_boot[j] * X_boot[j]

        betas[i] = numerator / (denominator + 1e-8)

    return betas


@njit(cache=True)
def compute_r_squared_numba(X: np.ndarray, y: np.ndarray) -> float:
    """Compute R² for lag selection."""
    n = len(X)
    if n < 3:
        return -np.inf

    # Means
    X_mean = np.mean(X)
    y_mean = np.mean(y)

    # Standardize
    X_std = (X - X_mean)
    y_std = (y - y_mean)

    # Beta
    num = 0.0
    denom = 0.0
    for i in range(n):
        num += X_std[i] * y_std[i]
        denom += X_std[i] * X_std[i]

    if denom < 1e-8:
        return -np.inf

    beta = num / denom

    # Predicted values and R²
    ss_res = 0.0
    ss_tot = 0.0
    for i in range(n):
        y_pred = y_mean + beta * X_std[i]
        ss_res += (y[i] - y_pred) ** 2
        ss_tot += (y[i] - y_mean) ** 2

    if ss_tot < 1e-8:
        return -np.inf

    return 1.0 - (ss_res / ss_tot)


@njit(cache=True)
def compute_quadratic_r_squared_numba(X: np.ndarray, y: np.ndarray) -> float:
    """Compute R² for quadratic fit (X + X²) using normal equations."""
    n = len(X)
    if n < 4:
        return -np.inf

    y_mean = np.mean(y)

    # Build design matrix: [1, X, X²]
    # Use normal equations: beta = (X'X)^-1 X'y
    # For 3 params, compute manually to avoid matrix ops

    sum_1 = float(n)
    sum_x = np.sum(X)
    sum_x2 = np.sum(X * X)
    sum_x3 = np.sum(X * X * X)
    sum_x4 = np.sum(X * X * X * X)
    sum_y = np.sum(y)
    sum_xy = np.sum(X * y)
    sum_x2y = np.sum(X * X * y)

    # Solve 3x3 system using Cramer's rule (simplified)
    # This is approximate but fast
    X_centered = X - np.mean(X)
    X2_centered = X * X - np.mean(X * X)
    y_centered = y - y_mean

    # Simple quadratic fit via correlation
    denom1 = np.sum(X_centered * X_centered)
    denom2 = np.sum(X2_centered * X2_centered)

    if denom1 < 1e-8 or denom2 < 1e-8:
        return -np.inf

    beta1 = np.sum(X_centered * y_centered) / denom1
    residual1 = y_centered - beta1 * X_centered
    beta2 = np.sum(X2_centered * residual1) / denom2

    # Compute R²
    y_pred = y_mean + beta1 * X_centered + beta2 * X2_centered
    ss_res = np.sum((y - y_pred) ** 2)
    ss_tot = np.sum((y - y_mean) ** 2)

    if ss_tot < 1e-8:
        return -np.inf

    return 1.0 - (ss_res / ss_tot)


# === HELPER FUNCTIONS ===

def get_git_commit() -> str:
    """Get current git commit hash."""
    try:
        result = subprocess.run(
            ['git', 'rev-parse', '--short', 'HEAD'],
            capture_output=True, text=True, cwd=PROJECT_ROOT
        )
        return result.stdout.strip() if result.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


def load_panel_data() -> pd.DataFrame:
    """Load panel data."""
    print("Loading panel data...")
    df = pd.read_parquet(PANEL_PATH)
    print(f"  Loaded {len(df):,} rows")
    return df


def load_edges() -> pd.DataFrame:
    """Load V2.1 causal edges."""
    print("Loading causal edges...")
    edges = pd.read_csv(EDGES_PATH)
    print(f"  Loaded {len(edges):,} edges")
    return edges


def get_countries() -> list:
    """Get list of countries from V3.0 graphs."""
    countries = []
    for f in GRAPHS_DIR.glob('*.json'):
        if f.stem != '_lag_checkpoint':
            countries.append(f.stem)
    return sorted(countries)


def pivot_country_year_data(
    panel: pd.DataFrame,
    country: str,
    year: int
) -> Optional[pd.DataFrame]:
    """Pivot country data up to specified year to wide format."""
    mask = (panel['country'] == country) & (panel['year'] <= year)
    country_data = panel[mask]

    if len(country_data) == 0:
        return None

    wide = country_data.pivot_table(
        index='year',
        columns='indicator_id',
        values='value',
        aggfunc='mean'
    )

    return wide


def pivot_unified_year_data(
    panel: pd.DataFrame,
    year: int
) -> Optional[pd.DataFrame]:
    """
    Pivot ALL countries' data up to specified year to wide format.
    Each row is a (country, year) observation.
    """
    mask = panel['year'] <= year
    subset = panel[mask]

    if len(subset) == 0:
        return None

    # Create (country, year) index
    wide = subset.pivot_table(
        index=['country', 'year'],
        columns='indicator_id',
        values='value',
        aggfunc='mean'
    )

    return wide


def validate_dag(edges: List[dict]) -> Tuple[bool, List]:
    """Check if edge set forms a valid DAG."""
    G = nx.DiGraph()
    for e in edges:
        G.add_edge(e['source'], e['target'])

    is_dag = nx.is_directed_acyclic_graph(G)

    if not is_dag:
        # Find cycles (limit to first 10)
        try:
            cycles = list(nx.simple_cycles(G))[:10]
        except:
            cycles = []
    else:
        cycles = []

    return is_dag, cycles


def get_saturation_info(indicator_id: str) -> Optional[dict]:
    """Get saturation threshold info for an indicator."""
    for key, threshold in SATURATION_THRESHOLDS.items():
        if key in indicator_id or indicator_id == key:
            return {
                'has_saturation': True,
                'threshold': threshold,
                'matched_pattern': key
            }
    return None


# === CORE COMPUTATION ===

def compute_edge_full(
    data_matrix: np.ndarray,
    years_array: np.ndarray,
    col_to_idx: dict,
    source: str,
    target: str,
    n_bootstrap: int = 100
) -> Optional[dict]:
    """
    Compute edge with full academic stats:
    - Best lag (0-5) selected by R²
    - Beta with bootstrap CIs
    - P-value from t-statistic
    - Saturation info
    """
    if source not in col_to_idx or target not in col_to_idx:
        return None

    src_idx = col_to_idx[source]
    tgt_idx = col_to_idx[target]

    X_full = data_matrix[:, src_idx]
    y_full = data_matrix[:, tgt_idx]

    # Find valid observations for full series
    valid_full = ~(np.isnan(X_full) | np.isnan(y_full))

    # Test each lag, find best by R²
    best_lag = 0
    best_r2 = -np.inf
    best_X = None
    best_y = None
    best_n = 0

    for lag in range(0, MAX_LAG + 1):
        if lag == 0:
            X_lag = X_full
            y_lag = y_full
            valid = valid_full
        else:
            # X is lagged (earlier), y is current
            X_lag = X_full[:-lag]
            y_lag = y_full[lag:]
            valid = ~(np.isnan(X_lag) | np.isnan(y_lag))

        n_valid = valid.sum()
        if n_valid < MIN_SAMPLES:
            continue

        X_clean = X_lag[valid]
        y_clean = y_lag[valid]

        r2 = compute_r_squared_numba(X_clean, y_clean)

        if r2 > best_r2:
            best_r2 = r2
            best_lag = lag
            best_X = X_clean
            best_y = y_clean
            best_n = n_valid

    if best_X is None or best_n < MIN_SAMPLES:
        return None

    # Standardize
    X_std = (best_X - best_X.mean()) / (best_X.std() + 1e-8)
    y_std = (best_y - best_y.mean()) / (best_y.std() + 1e-8)

    # Bootstrap with Numba
    seed = hash((source, target)) % (2**31)
    betas = bootstrap_betas_numba(X_std, y_std, n_bootstrap, seed)

    mean_beta = float(np.mean(betas))
    std_beta = float(np.std(betas))

    # P-value from t-statistic
    if std_beta > 1e-8:
        t_stat = mean_beta / std_beta
        # Two-tailed p-value with n-2 degrees of freedom
        p_value = float(2 * stats.t.sf(abs(t_stat), df=best_n - 2))
    else:
        p_value = 0.0 if abs(mean_beta) > 0.1 else 1.0

    # Get saturation info
    source_sat = get_saturation_info(source)
    target_sat = get_saturation_info(target)

    result = {
        'source': source,
        'target': target,
        'beta': mean_beta,
        'ci_lower': float(np.percentile(betas, 2.5)),
        'ci_upper': float(np.percentile(betas, 97.5)),
        'std': std_beta,
        'p_value': p_value,
        'lag': best_lag,
        'r_squared': float(best_r2) if best_r2 > -np.inf else 0.0,
        'n_samples': best_n,
        'n_bootstrap': n_bootstrap,
    }

    # Add saturation flags if applicable
    if source_sat:
        result['source_saturation'] = source_sat
    if target_sat:
        result['target_saturation'] = target_sat

    return result


def test_nonlinearity(
    data_matrix: np.ndarray,
    col_to_idx: dict,
    edge: dict
) -> dict:
    """
    Test if quadratic fit is significantly better than linear.
    Returns updated edge dict with relationship_type.
    """
    source = edge['source']
    target = edge['target']
    lag = edge.get('lag', 0)

    if source not in col_to_idx or target not in col_to_idx:
        edge['relationship_type'] = 'linear'
        return edge

    src_idx = col_to_idx[source]
    tgt_idx = col_to_idx[target]

    X_full = data_matrix[:, src_idx]
    y_full = data_matrix[:, tgt_idx]

    # Apply lag
    if lag > 0:
        X = X_full[:-lag]
        y = y_full[lag:]
    else:
        X = X_full
        y = y_full

    valid = ~(np.isnan(X) | np.isnan(y))
    if valid.sum() < MIN_SAMPLES + 2:
        edge['relationship_type'] = 'linear'
        return edge

    X_clean = X[valid]
    y_clean = y[valid]

    # Linear R²
    r2_linear = compute_r_squared_numba(X_clean, y_clean)

    # Quadratic R²
    r2_quad = compute_quadratic_r_squared_numba(X_clean, y_clean)

    # Check if quadratic is 10% better
    improvement = r2_quad - r2_linear

    if improvement > 0.10:
        edge['relationship_type'] = 'quadratic'
        edge['r2_linear'] = float(r2_linear)
        edge['r2_quadratic'] = float(r2_quad)
        edge['nonlinearity_improvement'] = float(improvement)
    else:
        edge['relationship_type'] = 'linear'

    return edge


def compute_graph_case(
    panel: pd.DataFrame,
    edges_df: pd.DataFrame,
    country: str,
    year: int,
    n_bootstrap: int = 100
) -> Tuple[Optional[dict], Optional[str]]:
    """
    Compute temporal graph for one (country, year) case.
    Full academic spec: lag selection, p-values, DAG validation, non-linearity.
    """
    # Get wide data
    wide = pivot_country_year_data(panel, country, year)

    if wide is None:
        return None, f"No data for country '{country}'"

    if len(wide) < MIN_SAMPLES:
        return None, f"Insufficient samples: {len(wide)} < {MIN_SAMPLES}"

    start_time = time.time()

    # Convert to numpy
    columns = wide.columns.tolist()
    col_to_idx = {col: i for i, col in enumerate(columns)}
    data_matrix = wide.values
    years_array = wide.index.values

    # Compute all edges
    computed_edges = []
    skipped_edges = 0

    for _, row in edges_df.iterrows():
        source, target = row['source'], row['target']

        edge_result = compute_edge_full(
            data_matrix, years_array, col_to_idx,
            source, target, n_bootstrap
        )

        if edge_result:
            computed_edges.append(edge_result)
        else:
            skipped_edges += 1

    if len(computed_edges) == 0:
        return None, "No edges could be computed"

    # Sort by |beta| and test non-linearity for top N
    computed_edges.sort(key=lambda e: abs(e['beta']), reverse=True)

    for i in range(min(TOP_N_NONLINEAR, len(computed_edges))):
        computed_edges[i] = test_nonlinearity(
            data_matrix, col_to_idx, computed_edges[i]
        )

    # Mark remaining as linear
    for i in range(TOP_N_NONLINEAR, len(computed_edges)):
        computed_edges[i]['relationship_type'] = 'linear'

    # DAG validation
    is_dag, cycles = validate_dag(computed_edges)

    compute_time = time.time() - start_time

    # Summary stats
    betas = [e['beta'] for e in computed_edges]
    p_values = [e['p_value'] for e in computed_edges]
    lags = [e['lag'] for e in computed_edges]
    nonlinear_count = sum(1 for e in computed_edges if e.get('relationship_type') == 'quadratic')

    result = {
        'country': country,
        'year': year,
        'edges': computed_edges,
        'metadata': {
            'n_edges_computed': len(computed_edges),
            'n_edges_skipped': skipped_edges,
            'n_edges_total': len(edges_df),
            'coverage': len(computed_edges) / len(edges_df),
            'mean_beta': float(np.mean(betas)),
            'std_beta': float(np.std(betas)),
            'median_p_value': float(np.median(p_values)),
            'significant_edges_p05': sum(1 for p in p_values if p < 0.05),
            'significant_edges_p01': sum(1 for p in p_values if p < 0.01),
            'mean_lag': float(np.mean(lags)),
            'lag_distribution': {str(i): int(lags.count(i)) for i in range(MAX_LAG + 1)},
            'nonlinear_edges': nonlinear_count,
            'dag_validated': is_dag,
            'dag_cycles': cycles if not is_dag else [],
            'n_samples': len(wide),
            'year_range': [int(wide.index.min()), int(wide.index.max())],
            'computation_time_sec': round(compute_time, 2)
        },
        'saturation_thresholds': SATURATION_THRESHOLDS,
        'provenance': {
            'computation_date': datetime.now().isoformat(),
            'code_version': 'v3.1.0',
            'git_commit': get_git_commit(),
            'n_bootstrap': n_bootstrap,
            'max_lag_tested': MAX_LAG,
            'nonlinearity_threshold': 0.10,
            'top_n_nonlinear_tested': TOP_N_NONLINEAR
        }
    }

    return result, None


def compute_unified_graph_case(
    panel: pd.DataFrame,
    edges_df: pd.DataFrame,
    year: int,
    n_bootstrap: int = 100
) -> Tuple[Optional[dict], Optional[str]]:
    """
    Compute unified (global) temporal graph for one year.
    Pools ALL countries' data up to that year.
    """
    # Get wide data for all countries
    wide = pivot_unified_year_data(panel, year)

    if wide is None:
        return None, f"No data for year {year}"

    if len(wide) < MIN_SAMPLES:
        return None, f"Insufficient samples: {len(wide)} < {MIN_SAMPLES}"

    start_time = time.time()

    # Convert to numpy
    columns = wide.columns.tolist()
    col_to_idx = {col: i for i, col in enumerate(columns)}
    data_matrix = wide.values
    # For unified, use row index as pseudo-years for lag calculation
    years_array = np.arange(len(wide))

    # Compute all edges
    computed_edges = []
    skipped_edges = 0

    for _, row in edges_df.iterrows():
        source, target = row['source'], row['target']

        edge_result = compute_edge_full(
            data_matrix, years_array, col_to_idx,
            source, target, n_bootstrap
        )

        if edge_result:
            computed_edges.append(edge_result)
        else:
            skipped_edges += 1

    if len(computed_edges) == 0:
        return None, "No edges could be computed"

    # Sort by |beta| and test non-linearity for top N
    computed_edges.sort(key=lambda e: abs(e['beta']), reverse=True)

    for i in range(min(TOP_N_NONLINEAR, len(computed_edges))):
        computed_edges[i] = test_nonlinearity(
            data_matrix, col_to_idx, computed_edges[i]
        )

    # Mark remaining as linear
    for i in range(TOP_N_NONLINEAR, len(computed_edges)):
        computed_edges[i]['relationship_type'] = 'linear'

    # DAG validation
    is_dag, cycles = validate_dag(computed_edges)

    compute_time = time.time() - start_time

    # Summary stats
    betas = [e['beta'] for e in computed_edges]
    p_values = [e['p_value'] for e in computed_edges]
    lags = [e['lag'] for e in computed_edges]
    nonlinear_count = sum(1 for e in computed_edges if e.get('relationship_type') == 'quadratic')

    # Get unique countries in data
    n_countries = wide.index.get_level_values('country').nunique()

    result = {
        'country': 'unified',
        'year': year,
        'edges': computed_edges,
        'metadata': {
            'n_edges_computed': len(computed_edges),
            'n_edges_skipped': skipped_edges,
            'n_edges_total': len(edges_df),
            'coverage': len(computed_edges) / len(edges_df),
            'mean_beta': float(np.mean(betas)),
            'std_beta': float(np.std(betas)),
            'median_p_value': float(np.median(p_values)),
            'significant_edges_p05': sum(1 for p in p_values if p < 0.05),
            'significant_edges_p01': sum(1 for p in p_values if p < 0.01),
            'mean_lag': float(np.mean(lags)),
            'lag_distribution': {str(i): int(lags.count(i)) for i in range(MAX_LAG + 1)},
            'nonlinear_edges': nonlinear_count,
            'dag_validated': is_dag,
            'dag_cycles': cycles if not is_dag else [],
            'n_samples': len(wide),
            'n_countries': n_countries,
            'year_range': [1990, year],
            'computation_time_sec': round(compute_time, 2)
        },
        'saturation_thresholds': SATURATION_THRESHOLDS,
        'provenance': {
            'computation_date': datetime.now().isoformat(),
            'code_version': 'v3.1.0',
            'git_commit': get_git_commit(),
            'n_bootstrap': n_bootstrap,
            'max_lag_tested': MAX_LAG,
            'nonlinearity_threshold': 0.10,
            'top_n_nonlinear_tested': TOP_N_NONLINEAR
        }
    }

    return result, None


# === I/O FUNCTIONS ===

class NumpyEncoder(json.JSONEncoder):
    """JSON encoder that handles numpy types."""
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)


def save_result(result: dict):
    """Save result to JSON file."""
    out_dir = OUTPUT_DIR / "countries" / result['country']
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{result['year']}_graph.json"

    with open(out_path, 'w') as f:
        json.dump(result, f, indent=2, cls=NumpyEncoder)


def save_unified_result(result: dict):
    """Save unified result to JSON file."""
    out_dir = OUTPUT_DIR / "unified"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{result['year']}_graph.json"

    with open(out_path, 'w') as f:
        json.dump(result, f, indent=2, cls=NumpyEncoder)


def get_completed_unified() -> set:
    """Get set of completed unified years."""
    completed = set()
    unified_dir = OUTPUT_DIR / "unified"
    if unified_dir.exists():
        for f in unified_dir.glob("*_graph.json"):
            year = int(f.stem.replace("_graph", ""))
            completed.add(year)
    return completed


def get_completed_cases() -> set:
    """Scan output directory for completed cases."""
    completed = set()
    countries_dir = OUTPUT_DIR / "countries"
    if countries_dir.exists():
        for country_dir in countries_dir.iterdir():
            if country_dir.is_dir():
                for f in country_dir.glob("*_graph.json"):
                    year = int(f.stem.replace("_graph", ""))
                    completed.add((country_dir.name, year))
    return completed


def save_checkpoint(checkpoint_data: dict):
    """Save checkpoint file."""
    checkpoint_path = OUTPUT_DIR / "checkpoint.json"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(checkpoint_path, 'w') as f:
        json.dump(checkpoint_data, f, indent=2)


def log_failure(country: str, year: int, reason: str):
    """Log a failure."""
    log_path = OUTPUT_DIR / "failures.jsonl"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    entry = {
        'timestamp': datetime.now().isoformat(),
        'country': country,
        'year': year,
        'reason': reason
    }
    with open(log_path, 'a') as f:
        f.write(json.dumps(entry) + '\n')


# === RUN MODES ===

def run_test(panel: pd.DataFrame, edges: pd.DataFrame):
    """Run test on 3 cases."""
    print("\n" + "=" * 60)
    print("TEST MODE: Running 3 test cases")
    print("=" * 60)

    test_cases = [
        ('United States', 2020),
        ('Rwanda', 2015),
        ('Germany', 2010),
    ]

    for country, year in test_cases:
        print(f"\nTesting: {country} / {year}")

        start = time.time()
        result, failure_reason = compute_graph_case(
            panel, edges, country, year,
            n_bootstrap=BOOTSTRAP_SAMPLES
        )
        elapsed = time.time() - start

        if result:
            meta = result['metadata']
            print(f"  Edges: {meta['n_edges_computed']} ({meta['coverage']:.1%} coverage)")
            print(f"  Significant (p<0.05): {meta['significant_edges_p05']}")
            print(f"  Mean lag: {meta['mean_lag']:.1f}")
            print(f"  Nonlinear: {meta['nonlinear_edges']}")
            print(f"  DAG valid: {meta['dag_validated']}")
            print(f"  Time: {elapsed:.1f}s")

            save_result(result)
        else:
            print(f"  Failed: {failure_reason}")

    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)


def run_timing_test(panel: pd.DataFrame, edges: pd.DataFrame):
    """Run timing test."""
    print("\n" + "=" * 60)
    print("TIMING TEST")
    print("=" * 60)

    test_cases = [('United States', 2020), ('Rwanda', 2015)]
    times = []

    for country, year in test_cases:
        print(f"\nTiming: {country} / {year}")
        start = time.time()
        result, _ = compute_graph_case(panel, edges, country, year, BOOTSTRAP_SAMPLES)
        elapsed = time.time() - start
        if result:
            times.append(elapsed)
            print(f"  Time: {elapsed:.1f}s")

    if times:
        avg = np.mean(times)
        countries = get_countries()
        total = len(countries) * len(YEARS)
        est_hours = (total * 0.8 * avg) / 3600 / N_JOBS

        print(f"\nAverage: {avg:.1f}s per case")
        print(f"Estimated: {est_hours:.1f} hours with {N_JOBS} workers")


def _process_case_worker(args):
    """Worker for multiprocessing."""
    country, year, n_bootstrap = args
    try:
        panel = pd.read_parquet(PANEL_PATH)
        edges = pd.read_csv(EDGES_PATH)
        result, reason = compute_graph_case(panel, edges, country, year, n_bootstrap)
        return (country, year, result, reason)
    except Exception as e:
        return (country, year, None, f"Exception: {str(e)}")


def run_production(panel: pd.DataFrame, edges: pd.DataFrame, resume: bool = False):
    """Run full production with multiprocessing."""
    print("\n" + "=" * 60)
    print("PRODUCTION RUN: Full Academic Spec")
    print(f"Using {N_JOBS} workers")
    print("=" * 60)

    countries = get_countries()
    all_cases = [(c, y) for c in countries for y in YEARS]

    print(f"Total cases: {len(all_cases):,}")

    completed = get_completed_cases() if resume else set()
    if resume:
        print(f"Already completed: {len(completed):,}")

    remaining = [c for c in all_cases if c not in completed]
    print(f"Remaining: {len(remaining):,}")

    if not remaining:
        print("\nAll done!")
        return

    case_args = [(c, y, BOOTSTRAP_SAMPLES) for c, y in remaining]

    print("\nStarting computation...\n")

    start_time = time.time()
    successes = 0
    failures = 0

    with Pool(processes=N_JOBS) as pool:
        results_iter = pool.imap_unordered(_process_case_worker, case_args, chunksize=5)

        for i, (country, year, result, reason) in enumerate(
            tqdm(results_iter, total=len(case_args), desc="Computing")
        ):
            if result:
                save_result(result)
                successes += 1
            else:
                log_failure(country, year, reason)
                failures += 1

            if (i + 1) % 100 == 0:
                elapsed = time.time() - start_time
                rate = (successes + failures) / elapsed
                eta = (len(remaining) - i - 1) / rate / 3600 if rate > 0 else 0
                save_checkpoint({
                    'timestamp': datetime.now().isoformat(),
                    'processed': i + 1,
                    'successes': successes,
                    'failures': failures,
                    'eta_hours': eta
                })

    total_time = time.time() - start_time
    print(f"\nDone in {total_time/3600:.1f} hours")
    print(f"Successes: {successes:,}, Failures: {failures:,}")


# === UNIFIED (GLOBAL) COMPUTATION ===

def run_unified_test(panel: pd.DataFrame, edges: pd.DataFrame):
    """Test unified computation with a few years."""
    print("\n=== UNIFIED TEST ===")
    print("Testing years: 2000, 2010, 2020\n")

    test_years = [2000, 2010, 2020]

    for year in test_years:
        print(f"\nYear {year}:")
        result, reason = compute_unified_graph_case(panel, edges, year, n_bootstrap=50)

        if result:
            meta = result['metadata']
            print(f"  Samples: {meta['n_samples']:,} ({meta['n_countries']} countries)")
            print(f"  Edges computed: {meta['n_edges_computed']:,}/{meta['n_edges_total']}")
            print(f"  Significant (p<0.05): {meta['significant_edges_p05']:,}")
            print(f"  Time: {meta['computation_time_sec']:.1f}s")
        else:
            print(f"  FAILED: {reason}")

    # Estimate full run time
    print("\n--- Timing Estimate ---")
    sample_year = 2020
    times = []
    for _ in range(3):
        start = time.time()
        compute_unified_graph_case(panel, edges, sample_year, n_bootstrap=BOOTSTRAP_SAMPLES)
        times.append(time.time() - start)

    avg = np.mean(times)
    total_est = avg * len(YEARS)
    print(f"Avg time per year: {avg:.1f}s")
    print(f"Estimated total (35 years): {total_est/60:.1f} minutes")


def run_unified_production(panel: pd.DataFrame, edges: pd.DataFrame, resume: bool = False):
    """Run unified (global) production for all years."""
    print("\n" + "=" * 60)
    print("UNIFIED PRODUCTION RUN: Global Temporal Graphs")
    print("=" * 60)

    print(f"Total years: {len(YEARS)}")

    completed = get_completed_unified() if resume else set()
    if resume:
        print(f"Already completed: {len(completed)}")

    remaining = [y for y in YEARS if y not in completed]
    print(f"Remaining: {len(remaining)}")

    if not remaining:
        print("\nAll done!")
        return

    print("\nStarting computation...\n")

    start_time = time.time()
    successes = 0
    failures = 0

    for year in tqdm(remaining, desc="Computing unified"):
        result, reason = compute_unified_graph_case(panel, edges, year, BOOTSTRAP_SAMPLES)

        if result:
            save_unified_result(result)
            successes += 1
        else:
            log_failure('unified', year, reason)
            failures += 1

    total_time = time.time() - start_time
    print(f"\nDone in {total_time/60:.1f} minutes")
    print(f"Successes: {successes}, Failures: {failures}")


def main():
    parser = argparse.ArgumentParser(description='Compute Temporal Graphs - Full Spec')
    parser.add_argument('--test', action='store_true', help='Test country-specific computation')
    parser.add_argument('--test-timing', action='store_true', help='Timing test for country-specific')
    parser.add_argument('--resume', action='store_true', help='Resume from checkpoint')
    parser.add_argument('--unified', action='store_true', help='Run unified (global) production')
    parser.add_argument('--unified-test', action='store_true', help='Test unified computation')
    args = parser.parse_args()

    panel = load_panel_data()
    edges = load_edges()

    if args.test:
        run_test(panel, edges)
    elif args.test_timing:
        run_timing_test(panel, edges)
    elif args.unified_test:
        run_unified_test(panel, edges)
    elif args.unified:
        run_unified_production(panel, edges, resume=args.resume)
    else:
        run_production(panel, edges, resume=args.resume)


if __name__ == "__main__":
    main()
