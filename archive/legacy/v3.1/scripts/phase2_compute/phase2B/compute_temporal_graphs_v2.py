#!/usr/bin/env python3
"""
Phase 2B v2: Enhanced Temporal Causal Graphs with Full Non-Linearity Detection

Key Enhancements over v1:
- Tests 5 model types for EVERY edge (not just top 500)
- AIC-based model selection (not just R² improvement)
- Full nonlinearity metadata for simulation API
- Marginal effects at 25th/50th/75th percentiles
- Threshold detection for piecewise relationships

Output: data/v3_1_temporal_graphs/{unified,stratified,countries}/...

Based on literature review:
- Logarithmic: Education → Growth (diminishing returns)
- Saturation: Income → Health (Preston curve)
- Quadratic: Development → Environment (Kuznets curve)
- Threshold: Institutions → Growth (regime shifts)
- S-curve: Technology adoption
"""

import argparse
import json
import warnings
import time
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple, List, Dict, Any

import numpy as np
import pandas as pd
from numba import njit
from scipy import stats
from scipy.optimize import curve_fit, minimize_scalar
import networkx as nx
from multiprocessing import Pool
from tqdm import tqdm

warnings.filterwarnings('ignore')

# === PATHS ===
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
PANEL_PATH = DATA_DIR / "raw" / "v21_panel_data_for_v3.parquet"
EDGES_PATH = DATA_DIR / "raw" / "v21_causal_edges.csv"
GRAPHS_DIR = DATA_DIR / "country_graphs"
OUTPUT_DIR = DATA_DIR / "v3_1_temporal_graphs"
METADATA_DIR = DATA_DIR / "metadata"
INCOME_CLASS_PATH = METADATA_DIR / "income_classifications.json"

# === CONFIGURATION ===
MIN_YEAR = 1990
MAX_YEAR = 2024
YEARS = list(range(MIN_YEAR, MAX_YEAR + 1))

BOOTSTRAP_SAMPLES = 100
MIN_SAMPLES = 10
MAX_LAG = 5
N_JOBS = 8  # Increased for faster processing

# Non-linearity detection config
AIC_THRESHOLD = 2.0  # Minimum AIC improvement for non-linear
R2_IMPROVEMENT_MIN = 0.03  # Minimum R² improvement (3%)
PERCENTILES = [25, 50, 75]  # For marginal effect computation

# === INCOME CLASSIFICATION ===
def load_income_classifications() -> Dict:
    """Load dynamic income classifications."""
    if INCOME_CLASS_PATH.exists():
        with open(INCOME_CLASS_PATH) as f:
            return json.load(f)
    return {}

INCOME_CLASSIFICATIONS = load_income_classifications()

# === SATURATION THRESHOLDS ===
SATURATION_THRESHOLDS = {
    # Education (%)
    'literacy_rate': 95, 'SE.ADT.LITR.ZS': 95,
    'primary_completion': 98, 'SE.PRM.CMPT.ZS': 98,
    'secondary_enrollment': 95,

    # Economic ($)
    'gdp_per_capita': 50000, 'NY.GDP.PCAP.CD': 50000,
    'NY.GDP.PCAP.PP.CD': 60000,

    # Health
    'life_expectancy': 82, 'SP.DYN.LE00.IN': 82,
    'infant_survival': 995,  # per 1000

    # Infrastructure (%)
    'internet_access': 95, 'IT.NET.USER.ZS': 95,
    'electricity_access': 99, 'EG.ELC.ACCS.ZS': 99,
    'mobile_subscriptions': 120,  # Can exceed 100%

    # Governance (0-1)
    'democracy_index': 0.9, 'v2x_polyarchy': 0.9,
}


# === NUMBA OPTIMIZED FUNCTIONS ===

@njit(cache=True)
def compute_linear_stats(X: np.ndarray, y: np.ndarray) -> Tuple[float, float, float, float]:
    """Compute linear regression stats: beta, r2, sse, n."""
    n = len(X)
    if n < 3:
        return 0.0, -np.inf, np.inf, 0

    X_mean = np.mean(X)
    y_mean = np.mean(y)

    num = 0.0
    denom = 0.0
    for i in range(n):
        num += (X[i] - X_mean) * (y[i] - y_mean)
        denom += (X[i] - X_mean) ** 2

    if denom < 1e-10:
        return 0.0, -np.inf, np.inf, 0

    beta = num / denom
    intercept = y_mean - beta * X_mean

    ss_res = 0.0
    ss_tot = 0.0
    for i in range(n):
        y_pred = intercept + beta * X[i]
        ss_res += (y[i] - y_pred) ** 2
        ss_tot += (y[i] - y_mean) ** 2

    if ss_tot < 1e-10:
        return beta, 0.0, ss_res, n

    r2 = 1.0 - (ss_res / ss_tot)
    return beta, r2, ss_res, n


@njit(cache=True)
def bootstrap_betas_numba(X_std: np.ndarray, y_std: np.ndarray,
                          n_bootstrap: int, seed: int) -> np.ndarray:
    """Numba-optimized bootstrap for beta coefficients."""
    np.random.seed(seed)
    n = len(X_std)
    betas = np.zeros(n_bootstrap)

    for i in range(n_bootstrap):
        indices = np.random.randint(0, n, n)
        X_boot = X_std[indices]
        y_boot = y_std[indices]

        numerator = 0.0
        denominator = 0.0
        for j in range(n):
            numerator += X_boot[j] * y_boot[j]
            denominator += X_boot[j] * X_boot[j]

        betas[i] = numerator / (denominator + 1e-8)

    return betas


# === NON-LINEAR MODEL FUNCTIONS ===

def fit_logarithmic(X: np.ndarray, y: np.ndarray) -> Dict[str, Any]:
    """Fit y = a + b*log(x). Requires X > 0."""
    if np.any(X <= 0):
        return {'valid': False}

    try:
        log_X = np.log(X)
        beta, r2, sse, n = compute_linear_stats(log_X, y)

        if r2 < -1:  # Invalid
            return {'valid': False}

        # AIC = n*log(sse/n) + 2k (k=2 params)
        aic = n * np.log(sse / n + 1e-10) + 4

        # Marginal effect: dy/dx = b/x
        X_pcts = np.percentile(X, PERCENTILES)
        marginal_effects = [beta / x if x > 0 else 0 for x in X_pcts]

        return {
            'valid': True,
            'type': 'logarithmic',
            'r2': float(r2),
            'aic': float(aic),
            'sse': float(sse),
            'params': {'a': float(np.mean(y) - beta * np.mean(log_X)), 'b': float(beta)},
            'interpretation': 'diminishing_returns',
            'marginal_effects': {f'p{p}': float(m) for p, m in zip(PERCENTILES, marginal_effects)}
        }
    except Exception:
        return {'valid': False}


def fit_quadratic(X: np.ndarray, y: np.ndarray) -> Dict[str, Any]:
    """Fit y = a + bx + cx². Detects U-shape or inverted-U."""
    try:
        n = len(X)
        if n < 5:
            return {'valid': False}

        # Design matrix [1, x, x²]
        X_design = np.column_stack([np.ones(n), X, X**2])

        # OLS: (X'X)^-1 X'y
        XtX = X_design.T @ X_design
        Xty = X_design.T @ y

        # Add small regularization for stability
        params = np.linalg.solve(XtX + 1e-8 * np.eye(3), Xty)
        a, b, c = params

        y_pred = X_design @ params
        ss_res = np.sum((y - y_pred) ** 2)
        ss_tot = np.sum((y - np.mean(y)) ** 2)

        if ss_tot < 1e-10:
            return {'valid': False}

        r2 = 1.0 - (ss_res / ss_tot)
        aic = n * np.log(ss_res / n + 1e-10) + 6  # k=3 params

        # Determine shape
        if abs(c) < 1e-6:
            shape = 'linear'
        elif c < 0:
            shape = 'inverted_u'
            vertex_x = -b / (2 * c)
        else:
            shape = 'u_shaped'
            vertex_x = -b / (2 * c)

        # Marginal effect: dy/dx = b + 2cx
        X_pcts = np.percentile(X, PERCENTILES)
        marginal_effects = [b + 2*c*x for x in X_pcts]

        return {
            'valid': True,
            'type': 'quadratic',
            'shape': shape,
            'r2': float(r2),
            'aic': float(aic),
            'sse': float(ss_res),
            'params': {'a': float(a), 'b': float(b), 'c': float(c)},
            'vertex_x': float(vertex_x) if shape != 'linear' else None,
            'interpretation': 'kuznets_curve' if shape == 'inverted_u' else 'accelerating' if shape == 'u_shaped' else 'linear',
            'marginal_effects': {f'p{p}': float(m) for p, m in zip(PERCENTILES, marginal_effects)}
        }
    except Exception:
        return {'valid': False}


def fit_saturation(X: np.ndarray, y: np.ndarray) -> Dict[str, Any]:
    """Fit y = L*(1 - exp(-k*x)) for saturation/ceiling effects."""
    try:
        n = len(X)
        if n < 5:
            return {'valid': False}

        # Estimate ceiling L from data
        L_init = np.max(y) * 1.1

        def model(x, L, k):
            return L * (1 - np.exp(-k * x))

        # Initial guesses
        p0 = [L_init, 0.01]
        bounds = ([np.max(y) * 0.9, 1e-6], [np.max(y) * 2, 10])

        popt, _ = curve_fit(model, X, y, p0=p0, bounds=bounds, maxfev=1000)
        L, k = popt

        y_pred = model(X, L, k)
        ss_res = np.sum((y - y_pred) ** 2)
        ss_tot = np.sum((y - np.mean(y)) ** 2)

        if ss_tot < 1e-10:
            return {'valid': False}

        r2 = 1.0 - (ss_res / ss_tot)
        aic = n * np.log(ss_res / n + 1e-10) + 4  # k=2 params

        # Marginal effect: dy/dx = L*k*exp(-k*x)
        X_pcts = np.percentile(X, PERCENTILES)
        marginal_effects = [L * k * np.exp(-k * x) for x in X_pcts]

        # Saturation point (where effect drops to 10% of max)
        # Max effect at x=0 is L*k
        # Find x where L*k*exp(-k*x) = 0.1*L*k  =>  x = -ln(0.1)/k
        saturation_x = -np.log(0.1) / k if k > 0 else np.inf

        return {
            'valid': True,
            'type': 'saturation',
            'r2': float(r2),
            'aic': float(aic),
            'sse': float(ss_res),
            'params': {'L': float(L), 'k': float(k)},
            'ceiling': float(L),
            'saturation_point': float(saturation_x),
            'interpretation': 'ceiling_effect',
            'marginal_effects': {f'p{p}': float(m) for p, m in zip(PERCENTILES, marginal_effects)}
        }
    except Exception:
        return {'valid': False}


def fit_threshold(X: np.ndarray, y: np.ndarray) -> Dict[str, Any]:
    """Fit piecewise linear: different slopes before/after threshold."""
    try:
        n = len(X)
        if n < 10:
            return {'valid': False}

        # Test thresholds at 20th, 30th, ..., 80th percentiles
        best_sse = np.inf
        best_threshold = None
        best_params = None

        for pct in range(20, 85, 10):
            threshold = np.percentile(X, pct)

            # Split data
            mask_low = X < threshold
            mask_high = ~mask_low

            if mask_low.sum() < 3 or mask_high.sum() < 3:
                continue

            # Fit separate lines
            beta1, _, sse1, n1 = compute_linear_stats(X[mask_low], y[mask_low])
            beta2, _, sse2, n2 = compute_linear_stats(X[mask_high], y[mask_high])

            total_sse = sse1 + sse2

            if total_sse < best_sse:
                best_sse = total_sse
                best_threshold = threshold
                best_params = {
                    'threshold': float(threshold),
                    'beta_low': float(beta1),
                    'beta_high': float(beta2),
                    'n_low': int(n1),
                    'n_high': int(n2)
                }

        if best_params is None:
            return {'valid': False}

        ss_tot = np.sum((y - np.mean(y)) ** 2)
        if ss_tot < 1e-10:
            return {'valid': False}

        r2 = 1.0 - (best_sse / ss_tot)
        aic = n * np.log(best_sse / n + 1e-10) + 8  # k=4 params

        # Marginal effects are the slopes in each regime
        X_pcts = np.percentile(X, PERCENTILES)
        marginal_effects = []
        for x in X_pcts:
            if x < best_params['threshold']:
                marginal_effects.append(best_params['beta_low'])
            else:
                marginal_effects.append(best_params['beta_high'])

        return {
            'valid': True,
            'type': 'threshold',
            'r2': float(r2),
            'aic': float(aic),
            'sse': float(best_sse),
            'params': best_params,
            'interpretation': 'regime_shift',
            'marginal_effects': {f'p{p}': float(m) for p, m in zip(PERCENTILES, marginal_effects)}
        }
    except Exception:
        return {'valid': False}


def detect_nonlinearity(X: np.ndarray, y: np.ndarray,
                        linear_r2: float, linear_sse: float) -> Dict[str, Any]:
    """
    Test all non-linear models and select best by AIC.
    Returns nonlinearity metadata for the edge.
    """
    n = len(X)
    if n < MIN_SAMPLES:
        return {'type': 'linear', 'detected': False}

    # Linear AIC
    linear_aic = n * np.log(linear_sse / n + 1e-10) + 4

    # Fit all non-linear models
    models = {
        'logarithmic': fit_logarithmic(X, y),
        'quadratic': fit_quadratic(X, y),
        'saturation': fit_saturation(X, y),
        'threshold': fit_threshold(X, y)
    }

    # Find best model by AIC
    best_model = 'linear'
    best_aic = linear_aic
    best_result = None

    for name, result in models.items():
        if not result.get('valid', False):
            continue

        model_aic = result['aic']
        model_r2 = result['r2']

        # Check improvement thresholds
        aic_improvement = linear_aic - model_aic
        r2_improvement = model_r2 - linear_r2

        if aic_improvement > AIC_THRESHOLD and r2_improvement > R2_IMPROVEMENT_MIN:
            if model_aic < best_aic:
                best_aic = model_aic
                best_model = name
                best_result = result

    if best_model == 'linear':
        return {
            'type': 'linear',
            'detected': False,
            'aic_linear': float(linear_aic),
            'models_tested': list(models.keys())
        }

    return {
        'type': best_result['type'],
        'detected': True,
        'r2_linear': float(linear_r2),
        'r2_nonlinear': float(best_result['r2']),
        'improvement': float(best_result['r2'] - linear_r2),
        'aic_linear': float(linear_aic),
        'aic_nonlinear': float(best_result['aic']),
        'aic_improvement': float(linear_aic - best_result['aic']),
        'params': best_result.get('params', {}),
        'interpretation': best_result.get('interpretation', ''),
        'marginal_effects': best_result.get('marginal_effects', {}),
        'shape': best_result.get('shape'),
        'ceiling': best_result.get('ceiling'),
        'saturation_point': best_result.get('saturation_point'),
        'vertex_x': best_result.get('vertex_x'),
        'threshold': best_result.get('params', {}).get('threshold')
    }


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


def get_income_group(country: str, year: int) -> Tuple[str, str, Optional[float]]:
    """Get income classification for country/year."""
    year_str = str(year)

    countries_data = INCOME_CLASSIFICATIONS.get('countries', {})

    if country in countries_data:
        country_data = countries_data[country]
        by_year = country_data.get('by_year', {})

        if year_str in by_year:
            year_data = by_year[year_str]
            group_4tier = year_data.get('classification_4tier', 'Unknown')
            group_3tier = year_data.get('classification_3tier') or 'unknown'
            gni = year_data.get('gni_per_capita')

            return group_4tier, group_3tier.lower(), gni

        # Fallback to current classification
        group_3tier = country_data.get('current_classification_3tier') or 'unknown'
        return (
            country_data.get('current_classification_4tier', 'Unknown'),
            group_3tier.lower(),
            None
        )

    return 'Unknown', 'unknown', None


def validate_dag(edges: List[dict]) -> Tuple[bool, List]:
    """Check if edge set forms a valid DAG."""
    G = nx.DiGraph()
    for e in edges:
        G.add_edge(e['source'], e['target'])

    is_dag = nx.is_directed_acyclic_graph(G)
    cycles = list(nx.simple_cycles(G))[:10] if not is_dag else []

    return is_dag, cycles


def get_saturation_info(indicator_id: str) -> Optional[dict]:
    """Get saturation threshold info for an indicator."""
    for key, threshold in SATURATION_THRESHOLDS.items():
        if key in indicator_id or indicator_id == key:
            return {'has_saturation': True, 'threshold': threshold, 'matched_pattern': key}
    return None


# === CORE COMPUTATION ===

def compute_edge_enhanced(
    data_matrix: np.ndarray,
    col_to_idx: dict,
    source: str,
    target: str,
    n_bootstrap: int = 100
) -> Optional[dict]:
    """
    Compute edge with FULL non-linearity detection.
    Tests all model types, selects best by AIC.
    """
    if source not in col_to_idx or target not in col_to_idx:
        return None

    src_idx = col_to_idx[source]
    tgt_idx = col_to_idx[target]

    X_full = data_matrix[:, src_idx]
    y_full = data_matrix[:, tgt_idx]

    valid_full = ~(np.isnan(X_full) | np.isnan(y_full))

    # Find best lag by R²
    best_lag = 0
    best_r2 = -np.inf
    best_X = None
    best_y = None
    best_n = 0
    best_sse = np.inf

    for lag in range(0, MAX_LAG + 1):
        if lag == 0:
            X_lag = X_full
            y_lag = y_full
            valid = valid_full
        else:
            X_lag = X_full[:-lag]
            y_lag = y_full[lag:]
            valid = ~(np.isnan(X_lag) | np.isnan(y_lag))

        n_valid = valid.sum()
        if n_valid < MIN_SAMPLES:
            continue

        X_clean = X_lag[valid]
        y_clean = y_lag[valid]

        beta, r2, sse, n = compute_linear_stats(X_clean, y_clean)

        if r2 > best_r2:
            best_r2 = r2
            best_lag = lag
            best_X = X_clean.copy()
            best_y = y_clean.copy()
            best_n = n_valid
            best_sse = sse

    if best_X is None or best_n < MIN_SAMPLES:
        return None

    # Standardize for bootstrap
    X_std = (best_X - best_X.mean()) / (best_X.std() + 1e-8)
    y_std = (best_y - best_y.mean()) / (best_y.std() + 1e-8)

    # Bootstrap
    seed = hash((source, target)) % (2**31)
    betas = bootstrap_betas_numba(X_std, y_std, n_bootstrap, seed)

    mean_beta = float(np.mean(betas))
    std_beta = float(np.std(betas))

    # P-value
    if std_beta > 1e-8:
        t_stat = mean_beta / std_beta
        p_value = float(2 * stats.t.sf(abs(t_stat), df=best_n - 2))
    else:
        p_value = 0.0 if abs(mean_beta) > 0.1 else 1.0

    # NON-LINEARITY DETECTION (the key enhancement)
    nonlinearity = detect_nonlinearity(best_X, best_y, best_r2, best_sse)

    # Saturation info
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
        'relationship_type': nonlinearity['type'],
        'nonlinearity': nonlinearity
    }

    if source_sat:
        result['source_saturation'] = source_sat
    if target_sat:
        result['target_saturation'] = target_sat

    return result


def pivot_data(panel: pd.DataFrame, country: str = None, year: int = None,
               stratum: str = None, countries_in_stratum: List[str] = None) -> Optional[pd.DataFrame]:
    """Pivot panel data to wide format for computation."""

    if country:
        # Single country
        mask = (panel['country'] == country) & (panel['year'] <= year)
    elif stratum == 'unified':
        # All countries
        mask = panel['year'] <= year
    elif stratum and countries_in_stratum:
        # Stratified by income group
        mask = (panel['country'].isin(countries_in_stratum)) & (panel['year'] <= year)
    else:
        return None

    subset = panel[mask]
    if len(subset) == 0:
        return None

    if country:
        wide = subset.pivot_table(
            index='year', columns='indicator_id', values='value', aggfunc='mean'
        )
    else:
        wide = subset.pivot_table(
            index=['country', 'year'], columns='indicator_id', values='value', aggfunc='mean'
        )

    return wide


def compute_graph_case(
    panel: pd.DataFrame,
    edges_df: pd.DataFrame,
    country: str = None,
    year: int = None,
    stratum: str = None,
    countries_in_stratum: List[str] = None,
    n_bootstrap: int = 100
) -> Tuple[Optional[dict], Optional[str]]:
    """
    Compute temporal graph for one case (country, unified, or stratified).
    """
    wide = pivot_data(panel, country=country, year=year,
                      stratum=stratum, countries_in_stratum=countries_in_stratum)

    if wide is None:
        return None, "No data available"

    if len(wide) < MIN_SAMPLES:
        return None, f"Insufficient samples: {len(wide)} < {MIN_SAMPLES}"

    start_time = time.time()

    columns = wide.columns.tolist()
    col_to_idx = {col: i for i, col in enumerate(columns)}
    data_matrix = wide.values

    # Compute all edges
    computed_edges = []
    skipped_edges = 0

    for _, row in edges_df.iterrows():
        source, target = row['source'], row['target']

        edge_result = compute_edge_enhanced(
            data_matrix, col_to_idx, source, target, n_bootstrap
        )

        if edge_result:
            computed_edges.append(edge_result)
        else:
            skipped_edges += 1

    if len(computed_edges) == 0:
        return None, "No edges could be computed"

    # Sort by |beta|
    computed_edges.sort(key=lambda e: abs(e['beta']), reverse=True)

    # DAG validation
    is_dag, cycles = validate_dag(computed_edges)

    compute_time = time.time() - start_time

    # Summary stats
    betas = [e['beta'] for e in computed_edges]
    p_values = [e['p_value'] for e in computed_edges]
    lags = [e['lag'] for e in computed_edges]

    # Non-linearity summary
    nonlinear_counts = {}
    for e in computed_edges:
        nl_type = e.get('relationship_type', 'linear')
        nonlinear_counts[nl_type] = nonlinear_counts.get(nl_type, 0) + 1

    # Build result
    result = {
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
            'nonlinearity_summary': nonlinear_counts,
            'dag_validated': is_dag,
            'dag_cycles': cycles if not is_dag else [],
            'n_samples': len(wide),
            'year_range': [MIN_YEAR, year],
            'computation_time_sec': round(compute_time, 2)
        },
        'saturation_thresholds': SATURATION_THRESHOLDS,
        'provenance': {
            'computation_date': datetime.now().isoformat(),
            'code_version': 'v3.1.1',
            'git_commit': get_git_commit(),
            'n_bootstrap': n_bootstrap,
            'max_lag_tested': MAX_LAG,
            'aic_threshold': AIC_THRESHOLD,
            'r2_improvement_min': R2_IMPROVEMENT_MIN,
            'full_nonlinearity_detection': True
        }
    }

    if country:
        result['country'] = country
        group_4tier, group_3tier, gni = get_income_group(country, year)
        result['income_classification'] = {
            'group_4tier': group_4tier,
            'group_3tier': group_3tier
        }
        if gni:
            result['income_classification']['gni_per_capita'] = gni
    elif stratum == 'unified':
        result['stratum'] = 'unified'
        result['stratum_name'] = 'Global Average (All Countries)'
        n_countries = wide.index.get_level_values('country').nunique() if isinstance(wide.index, pd.MultiIndex) else 1
        result['stratification'] = {
            'n_countries': n_countries,
            'countries_in_stratum': countries_in_stratum or []
        }
    elif stratum:
        result['stratum'] = stratum
        result['stratum_name'] = stratum.title() + ' Countries'
        n_countries = len(countries_in_stratum) if countries_in_stratum else 0
        result['stratification'] = {
            'n_countries': n_countries,
            'countries_in_stratum': countries_in_stratum or []
        }

    return result, None


# === I/O FUNCTIONS ===

class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, np.bool_):
            return bool(obj)
        return super().default(obj)


def save_result(result: dict, output_type: str = 'country'):
    """Save result to JSON file."""
    if output_type == 'country':
        out_dir = OUTPUT_DIR / "countries" / result['country']
        out_path = out_dir / f"{result['year']}_graph.json"
    elif output_type == 'unified':
        out_dir = OUTPUT_DIR / "unified"
        out_path = out_dir / f"{result['year']}_graph.json"
    elif output_type == 'stratified':
        out_dir = OUTPUT_DIR / "stratified" / result['stratum']
        out_path = out_dir / f"{result['year']}_graph.json"
    else:
        return

    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_path, 'w') as f:
        json.dump(result, f, indent=2, cls=NumpyEncoder)


def get_completed_cases(output_type: str) -> set:
    """Scan for completed cases."""
    completed = set()

    if output_type == 'unified':
        unified_dir = OUTPUT_DIR / "unified"
        if unified_dir.exists():
            for f in unified_dir.glob("*_graph.json"):
                year = int(f.stem.replace("_graph", ""))
                completed.add(year)

    elif output_type == 'stratified':
        strat_dir = OUTPUT_DIR / "stratified"
        if strat_dir.exists():
            for stratum_dir in strat_dir.iterdir():
                if stratum_dir.is_dir():
                    for f in stratum_dir.glob("*_graph.json"):
                        year = int(f.stem.replace("_graph", ""))
                        completed.add((stratum_dir.name, year))

    elif output_type == 'country':
        countries_dir = OUTPUT_DIR / "countries"
        if countries_dir.exists():
            for country_dir in countries_dir.iterdir():
                if country_dir.is_dir():
                    for f in country_dir.glob("*_graph.json"):
                        year = int(f.stem.replace("_graph", ""))
                        completed.add((country_dir.name, year))

    return completed


def get_countries_by_stratum(year: int) -> Dict[str, List[str]]:
    """Get countries grouped by income stratum for a given year."""
    strata = {'developing': [], 'emerging': [], 'advanced': []}

    for country in get_countries():
        _, group_3tier, _ = get_income_group(country, year)
        if group_3tier in strata:
            strata[group_3tier].append(country)

    return strata


# === RUN MODES ===

def run_test(panel: pd.DataFrame, edges: pd.DataFrame):
    """Test enhanced non-linearity detection."""
    print("\n" + "=" * 60)
    print("TEST MODE: Enhanced Non-Linearity Detection")
    print("=" * 60)

    test_cases = [
        ('United States', 2020),
        ('China', 2015),
        ('Rwanda', 2010),
    ]

    for country, year in test_cases:
        print(f"\n{country} / {year}:")

        result, reason = compute_graph_case(
            panel, edges, country=country, year=year,
            n_bootstrap=BOOTSTRAP_SAMPLES
        )

        if result:
            meta = result['metadata']
            print(f"  Edges: {meta['n_edges_computed']} ({meta['coverage']:.1%} coverage)")
            print(f"  Significant (p<0.05): {meta['significant_edges_p05']}")
            print(f"  Non-linearity breakdown:")
            for nl_type, count in meta['nonlinearity_summary'].items():
                print(f"    {nl_type}: {count}")
            print(f"  Time: {meta['computation_time_sec']:.1f}s")

            # Show sample non-linear edges
            nl_edges = [e for e in result['edges'] if e['relationship_type'] != 'linear'][:3]
            if nl_edges:
                print(f"\n  Sample non-linear edges:")
                for e in nl_edges:
                    print(f"    {e['source'][:30]} → {e['target'][:30]}")
                    print(f"      Type: {e['relationship_type']}, R² improvement: {e['nonlinearity'].get('improvement', 0):.3f}")

            save_result(result, 'country')
        else:
            print(f"  FAILED: {reason}")


def _process_country_worker(args):
    """Worker for country multiprocessing."""
    country, year, n_bootstrap = args
    try:
        panel = pd.read_parquet(PANEL_PATH)
        edges = pd.read_csv(EDGES_PATH)
        result, reason = compute_graph_case(
            panel, edges, country=country, year=year, n_bootstrap=n_bootstrap
        )
        return ('country', country, year, result, reason)
    except Exception as e:
        return ('country', country, year, None, str(e))


def run_full_production(panel: pd.DataFrame, edges: pd.DataFrame, resume: bool = False):
    """Run full production: unified + stratified + countries."""
    print("\n" + "=" * 60)
    print("FULL PRODUCTION RUN: Enhanced Non-Linearity v2")
    print(f"Using {N_JOBS} workers")
    print("=" * 60)

    all_countries = get_countries()

    # Phase 1: Unified
    print("\n--- Phase 1: Unified (Global) ---")
    completed_unified = get_completed_cases('unified') if resume else set()
    remaining_unified = [y for y in YEARS if y not in completed_unified]
    print(f"Unified years remaining: {len(remaining_unified)}")

    for year in tqdm(remaining_unified, desc="Unified"):
        result, _ = compute_graph_case(
            panel, edges, stratum='unified', year=year,
            countries_in_stratum=all_countries, n_bootstrap=BOOTSTRAP_SAMPLES
        )
        if result:
            save_result(result, 'unified')

    # Phase 2: Stratified
    print("\n--- Phase 2: Stratified (by income) ---")
    completed_strat = get_completed_cases('stratified') if resume else set()
    strata = ['developing', 'emerging', 'advanced']

    for stratum in strata:
        print(f"\n  {stratum.title()}:")
        remaining = [(stratum, y) for y in YEARS if (stratum, y) not in completed_strat]

        for _, year in tqdm(remaining, desc=f"  {stratum}"):
            countries_in_stratum = get_countries_by_stratum(year)[stratum]
            if len(countries_in_stratum) < 3:
                continue

            result, _ = compute_graph_case(
                panel, edges, stratum=stratum, year=year,
                countries_in_stratum=countries_in_stratum, n_bootstrap=BOOTSTRAP_SAMPLES
            )
            if result:
                save_result(result, 'stratified')

    # Phase 3: Countries (parallel)
    print("\n--- Phase 3: Country-Specific ---")
    completed_country = get_completed_cases('country') if resume else set()
    all_cases = [(c, y) for c in all_countries for y in YEARS]
    remaining = [c for c in all_cases if c not in completed_country]
    print(f"Country cases remaining: {len(remaining):,}")

    if remaining:
        case_args = [(c, y, BOOTSTRAP_SAMPLES) for c, y in remaining]

        successes = 0
        failures = 0

        with Pool(processes=N_JOBS) as pool:
            results_iter = pool.imap_unordered(_process_country_worker, case_args, chunksize=10)

            for output_type, country, year, result, reason in tqdm(results_iter, total=len(case_args), desc="Countries"):
                if result:
                    save_result(result, 'country')
                    successes += 1
                else:
                    failures += 1

        print(f"\nCountries: {successes:,} successes, {failures:,} failures")

    print("\n" + "=" * 60)
    print("PRODUCTION COMPLETE")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description='Phase 2B v2: Enhanced Non-Linearity Detection')
    parser.add_argument('--test', action='store_true', help='Test mode')
    parser.add_argument('--resume', action='store_true', help='Resume from checkpoint')
    parser.add_argument('--unified-only', action='store_true', help='Only compute unified')
    args = parser.parse_args()

    panel = load_panel_data()
    edges = load_edges()

    if args.test:
        run_test(panel, edges)
    elif args.unified_only:
        print("Running unified only...")
        all_countries = get_countries()
        for year in tqdm(YEARS, desc="Unified"):
            result, _ = compute_graph_case(
                panel, edges, stratum='unified', year=year,
                countries_in_stratum=all_countries, n_bootstrap=BOOTSTRAP_SAMPLES
            )
            if result:
                save_result(result, 'unified')
    else:
        run_full_production(panel, edges, resume=args.resume)


if __name__ == "__main__":
    main()
