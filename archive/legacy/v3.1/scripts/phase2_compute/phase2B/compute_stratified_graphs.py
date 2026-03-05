#!/usr/bin/env python3
"""
Phase 2B: Compute Stratified Temporal Causal Graphs

Computes temporal causal graphs for:
1. Unified (global average) - all countries pooled
2. Stratified (3 income groups) - dynamic membership by year
3. Country-specific - individual country graphs

Features:
- Bootstrap CIs with Numba optimization
- Lag selection (0-5 years, select by R²)
- P-value from t-statistic
- DAG validation
- Non-linearity detection (top 500 edges)
- Dynamic income stratification
"""

import argparse
import json
import warnings
import time
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple, List, Dict
from concurrent.futures import ProcessPoolExecutor, as_completed

import numpy as np
import pandas as pd
from numba import njit
from scipy import stats
import networkx as nx

warnings.filterwarnings('ignore')

# === PATHS ===
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
PANEL_PATH = DATA_DIR / "raw" / "v21_panel_data_for_v3.parquet"
EDGES_PATH = DATA_DIR / "raw" / "v21_causal_edges.csv"
INCOME_CLASS_PATH = DATA_DIR / "metadata" / "income_classifications.json"
CANONICAL_COUNTRIES_DIR = DATA_DIR / "v3_1_temporal_graphs" / "countries"
OUTPUT_DIR = DATA_DIR / "v3_1_temporal_graphs"

# === CONFIGURATION ===
MIN_YEAR = 1990
MAX_YEAR = 2024
YEARS = list(range(MIN_YEAR, MAX_YEAR + 1))

BOOTSTRAP_SAMPLES = 100
MIN_SAMPLES = 10
MAX_LAG = 5
N_JOBS = 8
TOP_N_NONLINEAR = 500

# Stratum definitions
STRATA = {
    'developing': {
        'name': 'Developing Countries',
        'wb_groups': ['Low income', 'Lower middle income']
    },
    'emerging': {
        'name': 'Emerging Countries',
        'wb_groups': ['Upper middle income']
    },
    'advanced': {
        'name': 'Advanced Countries',
        'wb_groups': ['High income']
    }
}

# === SATURATION THRESHOLDS ===
SATURATION_THRESHOLDS = {
    'literacy_rate': 80, 'SE.ADT.LITR.ZS': 80,
    'primary_completion': 90, 'SE.PRM.CMPT.ZS': 90,
    'gdp_per_capita': 50000, 'NY.GDP.PCAP.CD': 50000,
    'life_expectancy': 78, 'SP.DYN.LE00.IN': 78,
    'internet_access': 85, 'IT.NET.USER.ZS': 85,
    'electricity_access': 95, 'EG.ELC.ACCS.ZS': 95,
    'democracy_index': 0.8, 'v2x_polyarchy': 0.8,
}


def log(msg: str):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


# === NUMBA OPTIMIZED FUNCTIONS ===

@njit(cache=True)
def bootstrap_betas_numba(X_std: np.ndarray, y_std: np.ndarray,
                          n_bootstrap: int, seed: int) -> np.ndarray:
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


@njit(cache=True)
def compute_r_squared_numba(X: np.ndarray, y: np.ndarray) -> float:
    n = len(X)
    if n < 3:
        return -np.inf
    X_mean = np.mean(X)
    y_mean = np.mean(y)
    X_std = (X - X_mean)
    y_std = (y - y_mean)
    num = 0.0
    denom = 0.0
    for i in range(n):
        num += X_std[i] * y_std[i]
        denom += X_std[i] * X_std[i]
    if denom < 1e-8:
        return -np.inf
    beta = num / denom
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
    n = len(X)
    if n < 4:
        return -np.inf
    y_mean = np.mean(y)
    X_centered = X - np.mean(X)
    X2_centered = X * X - np.mean(X * X)
    y_centered = y - y_mean
    denom1 = np.sum(X_centered * X_centered)
    denom2 = np.sum(X2_centered * X2_centered)
    if denom1 < 1e-8 or denom2 < 1e-8:
        return -np.inf
    beta1 = np.sum(X_centered * y_centered) / denom1
    residual1 = y_centered - beta1 * X_centered
    beta2 = np.sum(X2_centered * residual1) / denom2
    y_pred = y_mean + beta1 * X_centered + beta2 * X2_centered
    ss_res = np.sum((y - y_pred) ** 2)
    ss_tot = np.sum((y - y_mean) ** 2)
    if ss_tot < 1e-8:
        return -np.inf
    return 1.0 - (ss_res / ss_tot)


# === DATA LOADING ===

def load_panel_data() -> pd.DataFrame:
    log("Loading panel data...")
    df = pd.read_parquet(PANEL_PATH)
    log(f"  Loaded {len(df):,} rows")
    return df


def load_edges() -> pd.DataFrame:
    log("Loading causal edges...")
    edges = pd.read_csv(EDGES_PATH)
    log(f"  Loaded {len(edges):,} edges")
    return edges


def load_income_classifications() -> dict:
    with open(INCOME_CLASS_PATH) as f:
        data = json.load(f)
    log(f"  Income classifications loaded for {len(data['countries'])} countries")
    return data


def load_canonical_countries() -> list:
    if CANONICAL_COUNTRIES_DIR.exists():
        # Use archived structure to get canonical list
        archived_dir = DATA_DIR / "_archive" / "v3_1_temporal_graphs_old_20260114" / "countries"
        if archived_dir.exists():
            return sorted([d.name for d in archived_dir.iterdir() if d.is_dir()])
    # Fallback to panel data
    panel = pd.read_parquet(PANEL_PATH)
    return sorted([c for c in panel['country'].unique() if isinstance(c, str) and not c.replace('.', '').isdigit()])


def get_countries_in_stratum(income_data: dict, stratum: str, year: int) -> list:
    """Get countries belonging to a stratum for a specific year."""
    wb_groups = STRATA[stratum]['wb_groups']
    countries = []
    for country, info in income_data['countries'].items():
        year_data = info.get('by_year', {}).get(str(year), {})
        classification = year_data.get('classification_4tier')
        if classification in wb_groups:
            countries.append(country)
    return sorted(countries)


def get_country_classification(income_data: dict, country: str, year: int) -> dict:
    info = income_data['countries'].get(country, {})
    year_data = info.get('by_year', {}).get(str(year), {})
    return {
        'group_4tier': year_data.get('classification_4tier'),
        'group_3tier': year_data.get('classification_3tier'),
        'gni_per_capita': year_data.get('gni_per_capita')
    }


# === HELPER FUNCTIONS ===

def get_git_commit() -> str:
    try:
        result = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'],
                                capture_output=True, text=True, cwd=PROJECT_ROOT)
        return result.stdout.strip() if result.returncode == 0 else "unknown"
    except:
        return "unknown"


def pivot_data(panel: pd.DataFrame, countries: list, year: int) -> Optional[pd.DataFrame]:
    """Pivot data for specified countries up to year."""
    mask = (panel['country'].isin(countries)) & (panel['year'] <= year)
    subset = panel[mask]
    if len(subset) == 0:
        return None
    wide = subset.pivot_table(
        index=['country', 'year'],
        columns='indicator_id',
        values='value',
        aggfunc='mean'
    )
    return wide


def validate_dag(edges: List[dict]) -> Tuple[bool, List]:
    G = nx.DiGraph()
    for e in edges:
        G.add_edge(e['source'], e['target'])
    is_dag = nx.is_directed_acyclic_graph(G)
    cycles = [] if is_dag else list(nx.simple_cycles(G))[:10]
    return is_dag, cycles


def get_saturation_info(indicator_id: str) -> Optional[dict]:
    for key, threshold in SATURATION_THRESHOLDS.items():
        if key in indicator_id or indicator_id == key:
            return {'has_saturation': True, 'threshold': threshold, 'matched_pattern': key}
    return None


# === CORE COMPUTATION ===

def compute_edge(data_matrix: np.ndarray, col_to_idx: dict,
                 source: str, target: str, n_bootstrap: int = 100) -> Optional[dict]:
    """Compute edge with lag selection and bootstrap CIs."""
    if source not in col_to_idx or target not in col_to_idx:
        return None

    src_idx = col_to_idx[source]
    tgt_idx = col_to_idx[target]
    X_full = data_matrix[:, src_idx]
    y_full = data_matrix[:, tgt_idx]
    valid_full = ~(np.isnan(X_full) | np.isnan(y_full))

    best_lag, best_r2, best_X, best_y, best_n = 0, -np.inf, None, None, 0

    for lag in range(0, MAX_LAG + 1):
        if lag == 0:
            X_lag, y_lag, valid = X_full, y_full, valid_full
        else:
            X_lag, y_lag = X_full[:-lag], y_full[lag:]
            valid = ~(np.isnan(X_lag) | np.isnan(y_lag))

        n_valid = valid.sum()
        if n_valid < MIN_SAMPLES:
            continue

        X_clean, y_clean = X_lag[valid], y_lag[valid]
        r2 = compute_r_squared_numba(X_clean, y_clean)

        if r2 > best_r2:
            best_r2, best_lag = r2, lag
            best_X, best_y, best_n = X_clean, y_clean, n_valid

    if best_X is None or best_n < MIN_SAMPLES:
        return None

    X_std = (best_X - best_X.mean()) / (best_X.std() + 1e-8)
    y_std = (best_y - best_y.mean()) / (best_y.std() + 1e-8)

    seed = hash((source, target)) % (2**31)
    betas = bootstrap_betas_numba(X_std, y_std, n_bootstrap, seed)

    mean_beta = float(np.mean(betas))
    std_beta = float(np.std(betas))

    if std_beta > 1e-8:
        t_stat = mean_beta / std_beta
        p_value = float(2 * stats.t.sf(abs(t_stat), df=best_n - 2))
    else:
        p_value = 0.0 if abs(mean_beta) > 0.1 else 1.0

    result = {
        'source': source, 'target': target,
        'beta': mean_beta,
        'ci_lower': float(np.percentile(betas, 2.5)),
        'ci_upper': float(np.percentile(betas, 97.5)),
        'std': std_beta, 'p_value': p_value,
        'lag': best_lag,
        'r_squared': float(best_r2) if best_r2 > -np.inf else 0.0,
        'n_samples': best_n, 'n_bootstrap': n_bootstrap,
    }

    source_sat = get_saturation_info(source)
    target_sat = get_saturation_info(target)
    if source_sat:
        result['source_saturation'] = source_sat
    if target_sat:
        result['target_saturation'] = target_sat

    return result


def test_nonlinearity(data_matrix: np.ndarray, col_to_idx: dict, edge: dict) -> dict:
    """Test if quadratic fit is better than linear."""
    source, target, lag = edge['source'], edge['target'], edge.get('lag', 0)

    if source not in col_to_idx or target not in col_to_idx:
        edge['relationship_type'] = 'linear'
        return edge

    X_full = data_matrix[:, col_to_idx[source]]
    y_full = data_matrix[:, col_to_idx[target]]

    if lag > 0:
        X, y = X_full[:-lag], y_full[lag:]
    else:
        X, y = X_full, y_full

    valid = ~(np.isnan(X) | np.isnan(y))
    if valid.sum() < MIN_SAMPLES + 2:
        edge['relationship_type'] = 'linear'
        return edge

    X_clean, y_clean = X[valid], y[valid]
    r2_linear = compute_r_squared_numba(X_clean, y_clean)
    r2_quad = compute_quadratic_r_squared_numba(X_clean, y_clean)

    if r2_quad - r2_linear > 0.10:
        edge['relationship_type'] = 'quadratic'
        edge['r2_linear'] = float(r2_linear)
        edge['r2_quadratic'] = float(r2_quad)
    else:
        edge['relationship_type'] = 'linear'

    return edge


def compute_graph(wide: pd.DataFrame, edges_df: pd.DataFrame,
                  n_bootstrap: int = 100) -> Tuple[List[dict], dict]:
    """Compute all edges for a dataset."""
    columns = wide.columns.tolist()
    col_to_idx = {col: i for i, col in enumerate(columns)}
    data_matrix = wide.values

    computed_edges = []
    skipped = 0

    for _, row in edges_df.iterrows():
        edge = compute_edge(data_matrix, col_to_idx, row['source'], row['target'], n_bootstrap)
        if edge:
            computed_edges.append(edge)
        else:
            skipped += 1

    if computed_edges:
        computed_edges.sort(key=lambda e: abs(e['beta']), reverse=True)
        for i in range(min(TOP_N_NONLINEAR, len(computed_edges))):
            computed_edges[i] = test_nonlinearity(data_matrix, col_to_idx, computed_edges[i])
        for i in range(TOP_N_NONLINEAR, len(computed_edges)):
            computed_edges[i]['relationship_type'] = 'linear'

    return computed_edges, {'skipped': skipped, 'total': len(edges_df)}


# === COMPUTATION WORKERS ===

def compute_unified_year(year: int, panel: pd.DataFrame, edges_df: pd.DataFrame,
                         canonical_countries: list) -> dict:
    """Compute unified graph for one year."""
    start_time = time.time()

    wide = pivot_data(panel, canonical_countries, year)
    if wide is None or len(wide) < MIN_SAMPLES:
        return {'year': year, 'status': 'skipped', 'reason': 'Insufficient data'}

    computed_edges, edge_stats = compute_graph(wide, edges_df, BOOTSTRAP_SAMPLES)

    if not computed_edges:
        return {'year': year, 'status': 'skipped', 'reason': 'No edges computed'}

    is_dag, cycles = validate_dag(computed_edges)
    elapsed = time.time() - start_time

    betas = [e['beta'] for e in computed_edges]
    p_values = [e['p_value'] for e in computed_edges]
    lags = [e['lag'] for e in computed_edges]
    n_countries = wide.index.get_level_values('country').nunique()

    output = {
        'stratum': 'unified',
        'stratum_name': 'Global Average (All Countries)',
        'year': year,
        'stratification': {
            'countries_in_stratum': sorted(wide.index.get_level_values('country').unique().tolist()),
            'n_countries': n_countries,
            'note': 'Global average - see stratified views for income-specific patterns'
        },
        'edges': computed_edges,
        'metadata': {
            'n_edges_computed': len(computed_edges),
            'n_edges_skipped': edge_stats['skipped'],
            'n_edges_total': edge_stats['total'],
            'coverage': len(computed_edges) / edge_stats['total'],
            'mean_beta': float(np.mean(betas)),
            'std_beta': float(np.std(betas)),
            'significant_edges_p05': sum(1 for p in p_values if p < 0.05),
            'mean_lag': float(np.mean(lags)),
            'nonlinear_edges': sum(1 for e in computed_edges if e.get('relationship_type') == 'quadratic'),
            'dag_validated': is_dag,
            'n_samples': len(wide),
            'n_countries': n_countries,
            'year_range': [MIN_YEAR, year],
            'computation_time_sec': round(elapsed, 2)
        },
        'provenance': {
            'computation_date': datetime.now().isoformat(),
            'code_version': 'v3.1.0',
            'n_bootstrap': BOOTSTRAP_SAMPLES
        }
    }

    return {'year': year, 'status': 'success', 'output': output, 'elapsed': elapsed}


def compute_stratum_year(stratum: str, year: int, panel: pd.DataFrame,
                         edges_df: pd.DataFrame, income_data: dict) -> dict:
    """Compute stratified graph for one stratum-year."""
    start_time = time.time()

    countries = get_countries_in_stratum(income_data, stratum, year)
    if len(countries) < 5:
        return {'stratum': stratum, 'year': year, 'status': 'skipped', 'reason': f'Too few countries: {len(countries)}'}

    wide = pivot_data(panel, countries, year)
    if wide is None or len(wide) < MIN_SAMPLES:
        return {'stratum': stratum, 'year': year, 'status': 'skipped', 'reason': 'Insufficient data'}

    computed_edges, edge_stats = compute_graph(wide, edges_df, BOOTSTRAP_SAMPLES)

    if not computed_edges:
        return {'stratum': stratum, 'year': year, 'status': 'skipped', 'reason': 'No edges computed'}

    is_dag, cycles = validate_dag(computed_edges)
    elapsed = time.time() - start_time

    betas = [e['beta'] for e in computed_edges]
    p_values = [e['p_value'] for e in computed_edges]
    n_countries = wide.index.get_level_values('country').nunique()

    output = {
        'stratum': stratum,
        'stratum_name': STRATA[stratum]['name'],
        'year': year,
        'stratification': {
            'classification_source': 'World Bank GNI per capita',
            'wb_groups_included': STRATA[stratum]['wb_groups'],
            'countries_in_stratum': countries,
            'n_countries': len(countries),
            'dynamic_note': 'Country membership changes by year based on income classification'
        },
        'edges': computed_edges,
        'metadata': {
            'n_edges_computed': len(computed_edges),
            'n_edges_skipped': edge_stats['skipped'],
            'n_edges_total': edge_stats['total'],
            'coverage': len(computed_edges) / edge_stats['total'],
            'mean_beta': float(np.mean(betas)),
            'significant_edges_p05': sum(1 for p in p_values if p < 0.05),
            'nonlinear_edges': sum(1 for e in computed_edges if e.get('relationship_type') == 'quadratic'),
            'dag_validated': is_dag,
            'n_samples': len(wide),
            'n_countries': n_countries,
            'year_range': [MIN_YEAR, year],
            'computation_time_sec': round(elapsed, 2)
        },
        'provenance': {
            'computation_date': datetime.now().isoformat(),
            'code_version': 'v3.1.0',
            'n_bootstrap': BOOTSTRAP_SAMPLES
        }
    }

    return {'stratum': stratum, 'year': year, 'status': 'success', 'output': output, 'elapsed': elapsed}


def compute_country_year(country: str, year: int, panel: pd.DataFrame,
                         edges_df: pd.DataFrame, income_data: dict) -> dict:
    """Compute country-specific graph for one country-year."""
    start_time = time.time()

    mask = (panel['country'] == country) & (panel['year'] <= year)
    country_data = panel[mask]

    if len(country_data) < 100:
        return {'country': country, 'year': year, 'status': 'skipped', 'reason': 'Insufficient data'}

    wide = country_data.pivot_table(index='year', columns='indicator_id', values='value', aggfunc='mean')

    if len(wide) < MIN_SAMPLES:
        return {'country': country, 'year': year, 'status': 'skipped', 'reason': f'Insufficient years: {len(wide)}'}

    computed_edges, edge_stats = compute_graph(wide, edges_df, BOOTSTRAP_SAMPLES)

    if not computed_edges:
        return {'country': country, 'year': year, 'status': 'skipped', 'reason': 'No edges computed'}

    is_dag, cycles = validate_dag(computed_edges)
    elapsed = time.time() - start_time

    income_class = get_country_classification(income_data, country, year)
    betas = [e['beta'] for e in computed_edges]
    p_values = [e['p_value'] for e in computed_edges]

    output = {
        'country': country,
        'year': year,
        'income_classification': income_class,
        'edges': computed_edges,
        'metadata': {
            'n_edges_computed': len(computed_edges),
            'n_edges_skipped': edge_stats['skipped'],
            'n_edges_total': edge_stats['total'],
            'coverage': len(computed_edges) / edge_stats['total'],
            'mean_beta': float(np.mean(betas)),
            'significant_edges_p05': sum(1 for p in p_values if p < 0.05),
            'nonlinear_edges': sum(1 for e in computed_edges if e.get('relationship_type') == 'quadratic'),
            'dag_validated': is_dag,
            'n_samples': len(wide),
            'year_range': [int(wide.index.min()), year],
            'computation_time_sec': round(elapsed, 2)
        },
        'provenance': {
            'computation_date': datetime.now().isoformat(),
            'code_version': 'v3.1.0',
            'n_bootstrap': BOOTSTRAP_SAMPLES
        }
    }

    return {'country': country, 'year': year, 'status': 'success', 'output': output, 'elapsed': elapsed}


# === JSON ENCODER ===

class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)


# === RUN FUNCTIONS ===

def run_unified(panel: pd.DataFrame, edges_df: pd.DataFrame,
                canonical_countries: list, years: list, resume: bool = True) -> list:
    """Run unified graph computation."""
    log(f"\n{'='*60}")
    log("COMPUTING UNIFIED (GLOBAL) GRAPHS")
    log(f"{'='*60}")

    output_dir = OUTPUT_DIR / "unified"
    output_dir.mkdir(parents=True, exist_ok=True)

    if resume:
        years_to_run = [y for y in years if not (output_dir / f"{y}_graph.json").exists()]
        if len(years) - len(years_to_run) > 0:
            log(f"Resuming: skipping {len(years) - len(years_to_run)} completed years")
        years = years_to_run

    if not years:
        log("All unified years completed!")
        return []

    log(f"Years: {len(years)} ({years[0]}-{years[-1]})")

    results = []
    for year in years:
        result = compute_unified_year(year, panel, edges_df, canonical_countries)
        results.append(result)

        if result['status'] == 'success':
            with open(output_dir / f"{year}_graph.json", 'w') as f:
                json.dump(result['output'], f, indent=2, cls=NumpyEncoder)
            log(f"  Year {year}: {result['output']['metadata']['n_edges_computed']} edges, {result['elapsed']:.1f}s")
        else:
            log(f"  Year {year}: SKIPPED - {result['reason']}")

    return results


def run_stratified(panel: pd.DataFrame, edges_df: pd.DataFrame,
                   income_data: dict, years: list, n_jobs: int = N_JOBS,
                   resume: bool = True) -> list:
    """Run stratified graph computation in parallel."""
    log(f"\n{'='*60}")
    log("COMPUTING STRATIFIED GRAPHS")
    log(f"{'='*60}")

    for stratum in STRATA:
        (OUTPUT_DIR / "stratified" / stratum).mkdir(parents=True, exist_ok=True)

    tasks = []
    skipped = 0
    for stratum in STRATA:
        for year in years:
            output_path = OUTPUT_DIR / "stratified" / stratum / f"{year}_graph.json"
            if resume and output_path.exists():
                skipped += 1
            else:
                tasks.append((stratum, year))

    if skipped > 0:
        log(f"Resuming: skipping {skipped} completed tasks")

    if not tasks:
        log("All stratified tasks completed!")
        return []

    log(f"Tasks to run: {len(tasks)}")
    log(f"Parallel workers: {n_jobs}")

    results = []
    completed = 0

    with ProcessPoolExecutor(max_workers=n_jobs) as executor:
        futures = {
            executor.submit(compute_stratum_year, stratum, year, panel, edges_df, income_data): (stratum, year)
            for stratum, year in tasks
        }

        for future in as_completed(futures):
            stratum, year = futures[future]
            try:
                result = future.result()
                results.append(result)
                completed += 1

                if result['status'] == 'success':
                    output_path = OUTPUT_DIR / "stratified" / stratum / f"{year}_graph.json"
                    with open(output_path, 'w') as f:
                        json.dump(result['output'], f, indent=2, cls=NumpyEncoder)
                    log(f"  [{completed}/{len(tasks)}] {stratum}/{year}: {result['output']['metadata']['n_edges_computed']} edges")
                else:
                    log(f"  [{completed}/{len(tasks)}] {stratum}/{year}: SKIPPED")
            except Exception as e:
                log(f"  [{completed}/{len(tasks)}] {stratum}/{year}: ERROR - {e}")

    return results


def run_countries(panel: pd.DataFrame, edges_df: pd.DataFrame,
                  income_data: dict, canonical_countries: list, years: list,
                  n_jobs: int = N_JOBS, resume: bool = True) -> list:
    """Run country-specific graph computation in parallel."""
    log(f"\n{'='*60}")
    log("COMPUTING COUNTRY-SPECIFIC GRAPHS")
    log(f"{'='*60}")

    tasks = []
    skipped = 0
    for country in canonical_countries:
        country_dir = OUTPUT_DIR / "countries" / country
        for year in years:
            output_path = country_dir / f"{year}_graph.json"
            if resume and output_path.exists():
                skipped += 1
            else:
                tasks.append((country, year))

    if skipped > 0:
        log(f"Resuming: skipping {skipped} completed tasks")

    if not tasks:
        log("All country tasks completed!")
        return []

    log(f"Tasks to run: {len(tasks)}")
    log(f"Parallel workers: {n_jobs}")

    results = []
    completed = 0

    with ProcessPoolExecutor(max_workers=n_jobs) as executor:
        futures = {
            executor.submit(compute_country_year, country, year, panel, edges_df, income_data): (country, year)
            for country, year in tasks
        }

        for future in as_completed(futures):
            country, year = futures[future]
            try:
                result = future.result()
                results.append(result)
                completed += 1

                if result['status'] == 'success':
                    country_dir = OUTPUT_DIR / "countries" / country
                    country_dir.mkdir(parents=True, exist_ok=True)
                    with open(country_dir / f"{year}_graph.json", 'w') as f:
                        json.dump(result['output'], f, indent=2, cls=NumpyEncoder)

                    if completed % 100 == 0:
                        log(f"  [{completed}/{len(tasks)}] Progress...")
            except Exception as e:
                pass

    success = sum(1 for r in results if r.get('status') == 'success')
    log(f"Completed: {success}/{len(tasks)} successful")

    return results


# === MAIN ===

def main():
    parser = argparse.ArgumentParser(description='Compute Stratified Temporal Graphs')
    parser.add_argument('--test', action='store_true', help='Run test on 3 years')
    parser.add_argument('--unified-only', action='store_true')
    parser.add_argument('--stratified-only', action='store_true')
    parser.add_argument('--countries-only', action='store_true')
    parser.add_argument('--n-jobs', type=int, default=N_JOBS)
    parser.add_argument('--years', type=str, help='Year range, e.g., "2000-2024"')
    args = parser.parse_args()

    log("="*60)
    log("STRATIFIED TEMPORAL GRAPHS COMPUTATION")
    log("="*60)

    panel = load_panel_data()
    edges_df = load_edges()
    income_data = load_income_classifications()
    canonical_countries = load_canonical_countries()
    log(f"  Canonical countries: {len(canonical_countries)}")

    if args.years:
        start, end = map(int, args.years.split('-'))
        years = list(range(start, end + 1))
    elif args.test:
        years = [2000, 2010, 2020]
    else:
        years = YEARS

    total_start = time.time()

    if not args.stratified_only and not args.countries_only:
        run_unified(panel, edges_df, canonical_countries, years)

    if not args.unified_only and not args.countries_only:
        run_stratified(panel, edges_df, income_data, years, args.n_jobs)

    if not args.unified_only and not args.stratified_only:
        run_countries(panel, edges_df, income_data, canonical_countries, years, args.n_jobs)

    total_elapsed = time.time() - total_start
    log(f"\n{'='*60}")
    log(f"COMPLETE: {total_elapsed/60:.1f} minutes")
    log(f"{'='*60}")


if __name__ == '__main__':
    main()
