#!/usr/bin/env python3
"""
Compute Stratified Temporal SHAP for Quality of Life

Computes SHAP importance for:
1. Unified (global average) - all 178 countries pooled
2. Stratified (3 income groups) - dynamic membership by year
3. Country-specific - individual country models

Output schema matches CLAUDE.md documentation.
"""

import json
import time
import argparse
import warnings
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed

import numpy as np
import pandas as pd
import lightgbm as lgb
import shap

warnings.filterwarnings('ignore')

# =============================================================================
# CONFIGURATION
# =============================================================================

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = DATA_DIR / "v3_1_temporal_shap"

# Input paths
PANEL_PATH = DATA_DIR / "raw" / "v21_panel_data_for_v3.parquet"
V21_HIERARCHY_PATH = Path("<repo-root>/v2.1/outputs/B5/v2_1_visualization.json")
INDICATOR_PROPS_PATH = DATA_DIR / "metadata" / "indicator_properties.json"
INCOME_CLASS_PATH = DATA_DIR / "metadata" / "income_classifications.json"
CANONICAL_COUNTRIES_DIR = DATA_DIR / "v3_1_temporal_graphs" / "countries"

# Computation parameters
MIN_YEAR = 1990
MAX_YEAR = 2024
MIN_SAMPLES = 30  # Minimum observations for SHAP
MIN_INDICATORS = 20  # Minimum indicators with data
N_BOOTSTRAP = 100  # Bootstrap iterations for confidence intervals
N_JOBS = 8  # Parallel cores

# LightGBM parameters
MODEL_PARAMS = {
    'n_estimators': 100,
    'max_depth': 5,
    'learning_rate': 0.1,
    'subsample': 0.8,
    'colsample_bytree': 0.8,
    'min_child_samples': 10,
    'random_state': 42,
    'verbose': -1,
    'n_jobs': 1,  # Inner parallelism disabled for outer parallelization
    'force_col_wise': True
}

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

# Domain mappings
DOMAIN_KEY_MAP = {
    'Health & Longevity': 'health_longevity',
    'Education & Knowledge': 'education_knowledge',
    'Income & Living Standards': 'income_living_standards',
    'Equality & Fairness': 'equality_fairness',
    'Safety & Security': 'safety_security',
    'Governance & Democracy': 'governance_democracy',
    'Infrastructure & Access': 'infrastructure_access',
    'Employment & Work': 'employment_work',
    'Environment & Sustainability': 'environment_sustainability'
}

DOMAIN_SHORT_MAP = {
    'Health': 'Health & Longevity',
    'Education': 'Education & Knowledge',
    'Economic': 'Income & Living Standards',
    'Equality': 'Equality & Fairness',
    'Security': 'Safety & Security',
    'Governance': 'Governance & Democracy',
    'Infrastructure': 'Infrastructure & Access',
    'Employment': 'Employment & Work',
    'Environment': 'Environment & Sustainability'
}


def log(msg: str):
    """Print timestamped log message."""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


# =============================================================================
# DATA LOADING
# =============================================================================

def load_panel_data() -> pd.DataFrame:
    """Load panel data from parquet."""
    log("Loading panel data...")
    panel = pd.read_parquet(PANEL_PATH)
    log(f"  Loaded {len(panel):,} rows")
    return panel


def load_canonical_countries() -> list:
    """Get list of 178 canonical countries."""
    if CANONICAL_COUNTRIES_DIR.exists():
        countries = sorted([d.name for d in CANONICAL_COUNTRIES_DIR.iterdir() if d.is_dir()])
    else:
        raise FileNotFoundError(f"Canonical countries directory not found: {CANONICAL_COUNTRIES_DIR}")
    log(f"  Canonical countries: {len(countries)}")
    return countries


def load_income_classifications() -> dict:
    """Load dynamic income classifications."""
    with open(INCOME_CLASS_PATH) as f:
        data = json.load(f)
    log(f"  Income classifications loaded for {len(data['countries'])} countries")
    return data


def load_indicator_directions() -> dict:
    """Load indicator direction metadata (positive/negative)."""
    if not INDICATOR_PROPS_PATH.exists():
        return {}
    with open(INDICATOR_PROPS_PATH) as f:
        props = json.load(f)
    indicators = props.get('indicators', props)
    directions = {k: v.get('direction', 'positive') for k, v in indicators.items() if isinstance(v, dict)}
    log(f"  Indicator directions: {len(directions)}")
    return directions


def load_v21_domains() -> dict:
    """Load V2.1 domain hierarchy."""
    with open(V21_HIERARCHY_PATH) as f:
        data = json.load(f)

    domain_indicators = defaultdict(list)
    for node in data['nodes']:
        if isinstance(node.get('id'), str) and node.get('domain'):
            full_domain = DOMAIN_SHORT_MAP.get(node['domain'], node['domain'])
            domain_indicators[full_domain].append(node['id'])

    for outcome in data.get('outcomes', []):
        for ind in outcome.get('top_indicators', []):
            if ind not in domain_indicators[outcome['name']]:
                domain_indicators[outcome['name']].append(ind)

    domains = {}
    for domain_name, indicators in domain_indicators.items():
        domain_key = DOMAIN_KEY_MAP.get(domain_name)
        if domain_key and indicators:
            domains[domain_key] = {'name': domain_name, 'indicators': indicators}

    log(f"  Domains loaded: {len(domains)}")
    for k, v in domains.items():
        log(f"    {k}: {len(v['indicators'])} indicators")
    return domains


def get_countries_in_stratum(income_data: dict, stratum: str, year: int) -> list:
    """Get countries belonging to a stratum for a specific year (dynamic membership)."""
    wb_groups = STRATA[stratum]['wb_groups']
    countries = []

    for country, info in income_data['countries'].items():
        year_data = info.get('by_year', {}).get(str(year), {})
        classification = year_data.get('classification_4tier')
        if classification in wb_groups:
            countries.append(country)

    return sorted(countries)


def get_country_classification(income_data: dict, country: str, year: int) -> dict:
    """Get income classification for a country in a specific year."""
    info = income_data['countries'].get(country, {})
    year_data = info.get('by_year', {}).get(str(year), {})
    return {
        'group_4tier': year_data.get('classification_4tier'),
        'group_3tier': year_data.get('classification_3tier'),
        'gni_per_capita': year_data.get('gni_per_capita')
    }


# =============================================================================
# FEATURE ENGINEERING
# =============================================================================

def create_quality_of_life_target(wide: pd.DataFrame, domains: dict,
                                   indicator_directions: dict) -> tuple:
    """
    Create composite Quality of Life target from domain aggregates.

    Returns:
        tuple: (target_series, domain_aggregates_dict, domain_stats_dict)
    """
    domain_aggregates = {}
    domain_stats = {}

    for domain_key, info in domains.items():
        available = [ind for ind in info['indicators'] if ind in wide.columns]
        if len(available) < 3:
            continue

        normalized_parts = []
        used_indicators = []

        for ind in available:
            col = wide[ind]
            valid_count = col.notna().sum()
            if valid_count < 10:
                continue

            min_val, max_val = col.min(), col.max()
            if max_val - min_val < 1e-10:
                continue

            # Normalize to [0, 1]
            normalized = (col - min_val) / (max_val - min_val)

            # Invert negative outcomes (so higher = better)
            if indicator_directions.get(ind, 'positive') == 'negative':
                normalized = 1.0 - normalized

            normalized_parts.append(normalized)
            used_indicators.append(ind)

        if len(normalized_parts) < 3:
            continue

        # Compute domain aggregate (arithmetic mean)
        stacked = np.column_stack([p.values for p in normalized_parts])
        domain_agg = np.nanmean(stacked, axis=1)
        domain_aggregates[domain_key] = domain_agg
        domain_stats[domain_key] = {
            'n_indicators': len(used_indicators),
            'indicators': used_indicators
        }

    if len(domain_aggregates) < 3:
        return None, None, None

    # Composite quality of life = mean of all domain aggregates
    all_domains = np.column_stack(list(domain_aggregates.values()))
    qol_target = pd.Series(np.nanmean(all_domains, axis=1), index=wide.index)

    return qol_target, domain_aggregates, domain_stats


def prepare_features(wide: pd.DataFrame, min_coverage: int = 10) -> pd.DataFrame:
    """Prepare feature matrix with imputation."""
    # Filter columns with minimum coverage
    valid_cols = [c for c in wide.columns if wide[c].notna().sum() >= min_coverage]
    X = wide[valid_cols].copy()

    # Impute with median
    X = X.fillna(X.median())

    # Drop any remaining all-NaN columns
    X = X.dropna(axis=1, how='all')

    return X


# =============================================================================
# SHAP COMPUTATION
# =============================================================================

def compute_shap_with_bootstrap(X: pd.DataFrame, y: pd.Series,
                                 n_bootstrap: int = N_BOOTSTRAP) -> dict:
    """
    Compute SHAP values with bootstrap confidence intervals.

    Returns:
        dict: {indicator_id: {'mean': float, 'std': float, 'ci_lower': float, 'ci_upper': float}}
    """
    shap_results = []
    r2_scores = []

    for seed in range(n_bootstrap):
        np.random.seed(seed)

        # Bootstrap sample
        idx = np.random.choice(len(X), size=len(X), replace=True)
        X_boot = X.iloc[idx]
        y_boot = y.iloc[idx]

        # Train model
        model = lgb.LGBMRegressor(**MODEL_PARAMS)
        model.fit(X_boot, y_boot)

        # Compute R² on full data
        y_pred = model.predict(X)
        ss_res = np.sum((y.values - y_pred) ** 2)
        ss_tot = np.sum((y.values - np.mean(y.values)) ** 2)
        r2 = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
        r2_scores.append(r2)

        # Compute SHAP values
        explainer = shap.TreeExplainer(model)
        shap_values = explainer.shap_values(X)

        # Mean absolute SHAP per feature
        mean_abs_shap = np.abs(shap_values).mean(axis=0)
        shap_results.append(mean_abs_shap)

    # Aggregate bootstrap results
    shap_matrix = np.array(shap_results)  # (n_bootstrap, n_features)

    # Compute statistics per feature
    mean_shap = shap_matrix.mean(axis=0)
    std_shap = shap_matrix.std(axis=0)
    ci_lower = np.percentile(shap_matrix, 2.5, axis=0)
    ci_upper = np.percentile(shap_matrix, 97.5, axis=0)

    # Normalize so max = 1.0
    max_shap = mean_shap.max() if mean_shap.max() > 0 else 1.0

    # Build result dict
    result = {}
    for i, col in enumerate(X.columns):
        result[col] = {
            'mean': round(mean_shap[i] / max_shap, 6),
            'std': round(std_shap[i] / max_shap, 6),
            'ci_lower': round(ci_lower[i] / max_shap, 6),
            'ci_upper': round(ci_upper[i] / max_shap, 6)
        }

    return result, np.mean(r2_scores), np.std(r2_scores)


# =============================================================================
# OUTPUT GENERATION
# =============================================================================

def create_stratified_output(stratum: str, year: int, countries: list,
                              shap_importance: dict, metadata: dict,
                              income_data: dict) -> dict:
    """Create output JSON for stratified view."""
    return {
        'stratum': stratum,
        'stratum_name': STRATA[stratum]['name'],
        'target': 'quality_of_life',
        'target_name': 'Quality of Life',
        'year': year,
        'stratification': {
            'classification_source': 'World Bank GNI per capita',
            'wb_groups_included': STRATA[stratum]['wb_groups'],
            'countries_in_stratum': countries,
            'n_countries': len(countries),
            'dynamic_note': 'Country membership changes by year based on income classification'
        },
        'shap_importance': shap_importance,
        'metadata': metadata,
        'data_quality': {
            'mean_ci_width': round(np.mean([v['ci_upper'] - v['ci_lower'] for v in shap_importance.values()]), 4) if shap_importance else 0
        },
        'provenance': {
            'computation_date': datetime.now().isoformat(),
            'code_version': 'v3.1.0',
            'model': 'LightGBM',
            'hyperparameters': {k: v for k, v in MODEL_PARAMS.items() if k not in ['verbose', 'n_jobs', 'force_col_wise']}
        }
    }


def create_unified_output(year: int, countries: list, shap_importance: dict,
                           metadata: dict) -> dict:
    """Create output JSON for unified (global) view."""
    return {
        'stratum': 'unified',
        'stratum_name': 'Global Average (All Countries)',
        'target': 'quality_of_life',
        'target_name': 'Quality of Life',
        'year': year,
        'stratification': {
            'countries_in_stratum': countries,
            'n_countries': len(countries),
            'note': 'Global average - may not reflect context-specific patterns. See stratified views for income-appropriate insights.'
        },
        'shap_importance': shap_importance,
        'metadata': metadata,
        'data_quality': {
            'mean_ci_width': round(np.mean([v['ci_upper'] - v['ci_lower'] for v in shap_importance.values()]), 4) if shap_importance else 0
        },
        'provenance': {
            'computation_date': datetime.now().isoformat(),
            'code_version': 'v3.1.0',
            'model': 'LightGBM',
            'hyperparameters': {k: v for k, v in MODEL_PARAMS.items() if k not in ['verbose', 'n_jobs', 'force_col_wise']}
        }
    }


def create_country_output(country: str, year: int, income_class: dict,
                           shap_importance: dict, metadata: dict) -> dict:
    """Create output JSON for country-specific view."""
    return {
        'country': country,
        'target': 'quality_of_life',
        'target_name': 'Quality of Life',
        'year': year,
        'income_classification': income_class,
        'shap_importance': shap_importance,
        'metadata': metadata,
        'data_quality': {
            'mean_ci_width': round(np.mean([v['ci_upper'] - v['ci_lower'] for v in shap_importance.values()]), 4) if shap_importance else 0
        },
        'provenance': {
            'computation_date': datetime.now().isoformat(),
            'code_version': 'v3.1.0',
            'model': 'LightGBM',
            'hyperparameters': {k: v for k, v in MODEL_PARAMS.items() if k not in ['verbose', 'n_jobs', 'force_col_wise']}
        }
    }


# =============================================================================
# COMPUTATION WORKERS
# =============================================================================

def compute_unified_year(year: int, panel: pd.DataFrame, domains: dict,
                          indicator_directions: dict, canonical_countries: list) -> dict:
    """Compute unified SHAP for a single year."""
    start_time = time.time()

    # Filter data up to this year
    subset = panel[(panel['year'] <= year) & (panel['country'].isin(canonical_countries))]

    if len(subset) < MIN_SAMPLES:
        return {'year': year, 'status': 'skipped', 'reason': f'Insufficient data: {len(subset)} rows'}

    # Pivot to wide format
    wide = subset.pivot_table(
        index=['country', 'year'],
        columns='indicator_id',
        values='value',
        aggfunc='first'
    )

    # Create target
    qol_target, domain_aggs, domain_stats = create_quality_of_life_target(
        wide, domains, indicator_directions
    )

    if qol_target is None:
        return {'year': year, 'status': 'skipped', 'reason': 'Could not create target'}

    # Prepare features
    X = prepare_features(wide)

    # Remove NaN targets
    valid_mask = ~qol_target.isna()
    X = X[valid_mask]
    y = qol_target[valid_mask]

    if len(X) < MIN_SAMPLES:
        return {'year': year, 'status': 'skipped', 'reason': f'Insufficient valid samples: {len(X)}'}

    # Compute SHAP
    shap_importance, r2_mean, r2_std = compute_shap_with_bootstrap(X, y, N_BOOTSTRAP)

    # Get unique countries in this data
    countries_in_data = sorted(X.index.get_level_values('country').unique().tolist())

    elapsed = time.time() - start_time

    metadata = {
        'n_samples': len(X),
        'n_countries': len(countries_in_data),
        'n_indicators': len(X.columns),
        'n_bootstrap': N_BOOTSTRAP,
        'r2_mean': round(r2_mean, 4),
        'r2_std': round(r2_std, 4),
        'year_range': [int(X.index.get_level_values('year').min()), year],
        'computation_time_sec': round(elapsed, 2)
    }

    output = create_unified_output(year, countries_in_data, shap_importance, metadata)

    return {'year': year, 'status': 'success', 'output': output, 'elapsed': elapsed}


def compute_stratum_year(stratum: str, year: int, panel: pd.DataFrame,
                          domains: dict, indicator_directions: dict,
                          income_data: dict) -> dict:
    """Compute stratified SHAP for a single stratum-year."""
    start_time = time.time()

    # Get countries in this stratum for this year
    countries = get_countries_in_stratum(income_data, stratum, year)

    if len(countries) < 5:
        return {'stratum': stratum, 'year': year, 'status': 'skipped',
                'reason': f'Too few countries: {len(countries)}'}

    # Filter data
    subset = panel[(panel['year'] <= year) & (panel['country'].isin(countries))]

    if len(subset) < MIN_SAMPLES:
        return {'stratum': stratum, 'year': year, 'status': 'skipped',
                'reason': f'Insufficient data: {len(subset)} rows'}

    # Pivot to wide format
    wide = subset.pivot_table(
        index=['country', 'year'],
        columns='indicator_id',
        values='value',
        aggfunc='first'
    )

    # Create target
    qol_target, domain_aggs, domain_stats = create_quality_of_life_target(
        wide, domains, indicator_directions
    )

    if qol_target is None:
        return {'stratum': stratum, 'year': year, 'status': 'skipped',
                'reason': 'Could not create target'}

    # Prepare features
    X = prepare_features(wide)

    # Remove NaN targets
    valid_mask = ~qol_target.isna()
    X = X[valid_mask]
    y = qol_target[valid_mask]

    if len(X) < MIN_SAMPLES:
        return {'stratum': stratum, 'year': year, 'status': 'skipped',
                'reason': f'Insufficient valid samples: {len(X)}'}

    # Compute SHAP
    shap_importance, r2_mean, r2_std = compute_shap_with_bootstrap(X, y, N_BOOTSTRAP)

    elapsed = time.time() - start_time

    metadata = {
        'n_samples': len(X),
        'n_countries': len(countries),
        'n_indicators': len(X.columns),
        'n_bootstrap': N_BOOTSTRAP,
        'r2_mean': round(r2_mean, 4),
        'r2_std': round(r2_std, 4),
        'year_range': [int(X.index.get_level_values('year').min()), year],
        'computation_time_sec': round(elapsed, 2)
    }

    output = create_stratified_output(stratum, year, countries, shap_importance,
                                       metadata, income_data)

    return {'stratum': stratum, 'year': year, 'status': 'success',
            'output': output, 'elapsed': elapsed}


def compute_country_year(country: str, year: int, panel: pd.DataFrame,
                          domains: dict, indicator_directions: dict,
                          income_data: dict) -> dict:
    """Compute country-specific SHAP for a single country-year."""
    start_time = time.time()

    # Filter data for this country up to this year
    subset = panel[(panel['year'] <= year) & (panel['country'] == country)]

    if len(subset) < 100:  # Need enough rows for country-specific
        return {'country': country, 'year': year, 'status': 'skipped',
                'reason': f'Insufficient data: {len(subset)} rows'}

    # Pivot to wide format
    wide = subset.pivot_table(
        index='year',
        columns='indicator_id',
        values='value',
        aggfunc='first'
    )

    # Create target
    qol_target, domain_aggs, domain_stats = create_quality_of_life_target(
        wide, domains, indicator_directions
    )

    if qol_target is None:
        return {'country': country, 'year': year, 'status': 'skipped',
                'reason': 'Could not create target'}

    # Prepare features
    X = prepare_features(wide, min_coverage=5)  # Lower threshold for single country

    # Remove NaN targets
    valid_mask = ~qol_target.isna()
    X = X[valid_mask]
    y = qol_target[valid_mask]

    if len(X) < 10:  # Lower threshold for single country
        return {'country': country, 'year': year, 'status': 'skipped',
                'reason': f'Insufficient valid samples: {len(X)}'}

    # Compute SHAP with full bootstrap iterations
    shap_importance, r2_mean, r2_std = compute_shap_with_bootstrap(X, y, n_bootstrap=N_BOOTSTRAP)

    # Get income classification
    income_class = get_country_classification(income_data, country, year)

    elapsed = time.time() - start_time

    metadata = {
        'n_samples': len(X),
        'n_indicators': len(X.columns),
        'n_bootstrap': N_BOOTSTRAP,
        'r2_mean': round(r2_mean, 4),
        'r2_std': round(r2_std, 4),
        'year_range': [int(X.index.min()), year],
        'computation_time_sec': round(elapsed, 2)
    }

    output = create_country_output(country, year, income_class, shap_importance, metadata)

    return {'country': country, 'year': year, 'status': 'success',
            'output': output, 'elapsed': elapsed}


# =============================================================================
# PARALLEL EXECUTION
# =============================================================================

def run_unified(panel: pd.DataFrame, domains: dict, indicator_directions: dict,
                canonical_countries: list, years: list, n_jobs: int = N_JOBS,
                resume: bool = True) -> list:
    """Run unified SHAP computation in parallel across years."""
    log(f"\n{'='*60}")
    log("COMPUTING UNIFIED (GLOBAL) SHAP")
    log(f"{'='*60}")

    output_dir = OUTPUT_DIR / "unified" / "quality_of_life"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Filter out already completed years if resuming
    if resume:
        years_to_run = [y for y in years if not (output_dir / f"{y}_shap.json").exists()]
        skipped = len(years) - len(years_to_run)
        if skipped > 0:
            log(f"Resuming: skipping {skipped} already completed years")
        years = years_to_run

    if not years:
        log("All unified years already completed!")
        return []

    log(f"Years: {len(years)} ({years[0]}-{years[-1]})")
    log(f"Parallel workers: {n_jobs}")

    results = []
    start_time = time.time()
    completed = 0

    with ProcessPoolExecutor(max_workers=n_jobs) as executor:
        futures = {
            executor.submit(compute_unified_year, year, panel, domains,
                          indicator_directions, canonical_countries): year
            for year in years
        }

        for future in as_completed(futures):
            year = futures[future]
            try:
                result = future.result()
                results.append(result)
                completed += 1

                if result['status'] == 'success':
                    # Save output
                    output_path = output_dir / f"{year}_shap.json"
                    with open(output_path, 'w') as f:
                        json.dump(result['output'], f, indent=2)
                    log(f"  [{completed}/{len(years)}] Year {year}: R²={result['output']['metadata']['r2_mean']:.3f}, "
                        f"{result['output']['metadata']['n_samples']} samples, {result['elapsed']:.1f}s")
                else:
                    log(f"  [{completed}/{len(years)}] Year {year}: SKIPPED - {result['reason']}")
            except Exception as e:
                log(f"  [{completed}/{len(years)}] Year {year}: ERROR - {str(e)}")
                results.append({'year': year, 'status': 'error', 'error': str(e)})

    elapsed = time.time() - start_time
    success_count = sum(1 for r in results if r['status'] == 'success')
    log(f"\nUnified complete: {success_count}/{len(years)} years in {elapsed:.1f}s")

    return results


def run_stratified(panel: pd.DataFrame, domains: dict, indicator_directions: dict,
                   income_data: dict, years: list, n_jobs: int = N_JOBS,
                   resume: bool = True) -> list:
    """Run stratified SHAP computation in parallel across strata × years."""
    log(f"\n{'='*60}")
    log("COMPUTING STRATIFIED SHAP")
    log(f"{'='*60}")

    # Create output directories
    for stratum in STRATA:
        (OUTPUT_DIR / "stratified" / stratum / "quality_of_life").mkdir(parents=True, exist_ok=True)

    # Build task list, filtering completed if resuming
    tasks = []
    skipped = 0
    for stratum in STRATA:
        for year in years:
            output_path = OUTPUT_DIR / "stratified" / stratum / "quality_of_life" / f"{year}_shap.json"
            if resume and output_path.exists():
                skipped += 1
            else:
                tasks.append((stratum, year))

    if skipped > 0:
        log(f"Resuming: skipping {skipped} already completed tasks")

    if not tasks:
        log("All stratified tasks already completed!")
        return []

    log(f"Strata: {list(STRATA.keys())}")
    log(f"Years: {len(years)} ({years[0]}-{years[-1]})")
    log(f"Tasks to run: {len(tasks)}")
    log(f"Parallel workers: {n_jobs}")

    results = []
    start_time = time.time()
    completed = 0
    total_tasks = len(tasks)

    with ProcessPoolExecutor(max_workers=n_jobs) as executor:
        futures = {
            executor.submit(compute_stratum_year, stratum, year, panel, domains,
                          indicator_directions, income_data): (stratum, year)
            for stratum, year in tasks
        }

        for future in as_completed(futures):
            stratum, year = futures[future]
            try:
                result = future.result()
                results.append(result)
                completed += 1

                if result['status'] == 'success':
                    output_path = OUTPUT_DIR / "stratified" / stratum / "quality_of_life" / f"{year}_shap.json"
                    with open(output_path, 'w') as f:
                        json.dump(result['output'], f, indent=2)
                    log(f"  [{completed}/{total_tasks}] {stratum}/{year}: "
                        f"R²={result['output']['metadata']['r2_mean']:.3f}, "
                        f"{result['output']['stratification']['n_countries']} countries, "
                        f"{result['elapsed']:.1f}s")
                else:
                    log(f"  [{completed}/{total_tasks}] {stratum}/{year}: SKIPPED - {result['reason']}")
            except Exception as e:
                log(f"  [{completed}/{total_tasks}] {stratum}/{year}: ERROR - {str(e)}")
                results.append({'stratum': stratum, 'year': year, 'status': 'error', 'error': str(e)})

    elapsed = time.time() - start_time
    success_count = sum(1 for r in results if r['status'] == 'success')
    log(f"\nStratified complete: {success_count}/{total_tasks} tasks in {elapsed:.1f}s")

    return results


def run_countries(panel: pd.DataFrame, domains: dict, indicator_directions: dict,
                  income_data: dict, canonical_countries: list, years: list,
                  n_jobs: int = N_JOBS, resume: bool = True) -> list:
    """Run country-specific SHAP computation in parallel across countries × years."""
    log(f"\n{'='*60}")
    log("COMPUTING COUNTRY-SPECIFIC SHAP")
    log(f"{'='*60}")

    # Build task list, filtering completed if resuming
    tasks = []
    skipped = 0
    for country in canonical_countries:
        country_dir = OUTPUT_DIR / "countries" / country / "quality_of_life"
        for year in years:
            output_path = country_dir / f"{year}_shap.json"
            if resume and output_path.exists():
                skipped += 1
            else:
                tasks.append((country, year))

    if skipped > 0:
        log(f"Resuming: skipping {skipped} already completed tasks")

    if not tasks:
        log("All country tasks already completed!")
        return []

    log(f"Countries: {len(canonical_countries)}")
    log(f"Years: {len(years)} ({years[0]}-{years[-1]})")
    log(f"Tasks to run: {len(tasks)}")
    log(f"Parallel workers: {n_jobs}")

    results = []
    start_time = time.time()
    completed = 0
    total_tasks = len(tasks)

    with ProcessPoolExecutor(max_workers=n_jobs) as executor:
        futures = {
            executor.submit(compute_country_year, country, year, panel, domains,
                          indicator_directions, income_data): (country, year)
            for country, year in tasks
        }

        for future in as_completed(futures):
            country, year = futures[future]
            try:
                result = future.result()
                results.append(result)
                completed += 1

                if result['status'] == 'success':
                    # Create country directory
                    country_dir = OUTPUT_DIR / "countries" / country / "quality_of_life"
                    country_dir.mkdir(parents=True, exist_ok=True)

                    output_path = country_dir / f"{year}_shap.json"
                    with open(output_path, 'w') as f:
                        json.dump(result['output'], f, indent=2)

                    if completed % 100 == 0 or completed == total_tasks:
                        log(f"  [{completed}/{total_tasks}] {country}/{year}: "
                            f"R²={result['output']['metadata']['r2_mean']:.3f}, "
                            f"{result['elapsed']:.1f}s")
                else:
                    if completed % 500 == 0:
                        log(f"  [{completed}/{total_tasks}] Progress... ({sum(1 for r in results if r['status'] == 'success')} successes)")
            except Exception as e:
                results.append({'country': country, 'year': year, 'status': 'error', 'error': str(e)})

    elapsed = time.time() - start_time
    success_count = sum(1 for r in results if r['status'] == 'success')
    log(f"\nCountry-specific complete: {success_count}/{total_tasks} tasks in {elapsed:.1f}s")
    log(f"Average per task: {elapsed/total_tasks:.2f}s")

    return results


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description='Compute Stratified Temporal SHAP')
    parser.add_argument('--test', action='store_true', help='Run small test (3 years, 5 countries)')
    parser.add_argument('--unified-only', action='store_true', help='Only compute unified')
    parser.add_argument('--stratified-only', action='store_true', help='Only compute stratified')
    parser.add_argument('--countries-only', action='store_true', help='Only compute countries')
    parser.add_argument('--n-jobs', type=int, default=N_JOBS, help=f'Parallel workers (default: {N_JOBS})')
    parser.add_argument('--years', type=str, help='Year range, e.g., "2000-2024"')
    args = parser.parse_args()

    log("="*60)
    log("STRATIFIED TEMPORAL SHAP COMPUTATION")
    log("="*60)
    log(f"Start time: {datetime.now().isoformat()}")
    log(f"Output directory: {OUTPUT_DIR}")
    log(f"Parallel workers: {args.n_jobs}")

    # Load data
    log("\nLoading data...")
    panel = load_panel_data()
    canonical_countries = load_canonical_countries()
    income_data = load_income_classifications()
    indicator_directions = load_indicator_directions()
    domains = load_v21_domains()

    # Determine years
    if args.years:
        start, end = map(int, args.years.split('-'))
        years = list(range(start, end + 1))
    elif args.test:
        years = [2000, 2010, 2020]
    else:
        years = list(range(MIN_YEAR, MAX_YEAR + 1))

    # Determine countries for test
    if args.test:
        test_countries = ['United States', 'China', 'India', 'Germany', 'Brazil']
        canonical_countries = [c for c in test_countries if c in canonical_countries]
        log(f"\nTEST MODE: {len(years)} years, {len(canonical_countries)} countries")

    total_start = time.time()

    # Run computations
    if not args.stratified_only and not args.countries_only:
        unified_results = run_unified(panel, domains, indicator_directions,
                                       canonical_countries, years, args.n_jobs)

    if not args.unified_only and not args.countries_only:
        stratified_results = run_stratified(panel, domains, indicator_directions,
                                             income_data, years, args.n_jobs)

    if not args.unified_only and not args.stratified_only:
        country_results = run_countries(panel, domains, indicator_directions,
                                         income_data, canonical_countries, years,
                                         args.n_jobs)

    total_elapsed = time.time() - total_start

    # Summary
    log(f"\n{'='*60}")
    log("COMPUTATION COMPLETE")
    log(f"{'='*60}")
    log(f"Total time: {total_elapsed/60:.1f} minutes ({total_elapsed/3600:.2f} hours)")

    # Count output files
    unified_files = len(list((OUTPUT_DIR / "unified" / "quality_of_life").glob("*.json")))
    stratified_files = sum(len(list((OUTPUT_DIR / "stratified" / s / "quality_of_life").glob("*.json")))
                          for s in STRATA)
    country_files = len(list((OUTPUT_DIR / "countries").rglob("*.json")))

    log(f"\nOutput files:")
    log(f"  Unified: {unified_files}")
    log(f"  Stratified: {stratified_files}")
    log(f"  Country-specific: {country_files}")
    log(f"  Total: {unified_files + stratified_files + country_files}")

    # ETA for full run (if test)
    if args.test:
        # Estimate based on test timing
        full_years = MAX_YEAR - MIN_YEAR + 1  # 35
        full_countries = 178

        # Unified ETA
        if 'unified_results' in dir():
            unified_time_per_year = total_elapsed / len(years) if not args.stratified_only and not args.countries_only else 0
            unified_eta = unified_time_per_year * full_years
        else:
            unified_eta = 0

        # Stratified ETA
        stratified_eta = unified_eta * 3 * 0.8  # 3 strata, slightly less data each

        # Country ETA (the bulk)
        if 'country_results' in dir():
            country_time = sum(r.get('elapsed', 0) for r in country_results if r.get('status') == 'success')
            country_tasks_done = sum(1 for r in country_results if r.get('status') == 'success')
            if country_tasks_done > 0:
                time_per_country_year = country_time / country_tasks_done
                country_eta = time_per_country_year * full_countries * full_years
            else:
                country_eta = 0
        else:
            country_eta = 0

        total_eta = unified_eta + stratified_eta + country_eta

        log(f"\n{'='*60}")
        log("ESTIMATED TIME FOR FULL RUN")
        log(f"{'='*60}")
        log(f"  Unified ({full_years} years): {unified_eta/60:.1f} min")
        log(f"  Stratified (3 × {full_years} years): {stratified_eta/60:.1f} min")
        log(f"  Countries ({full_countries} × {full_years} years): {country_eta/3600:.1f} hours")
        log(f"  TOTAL ETA: {total_eta/3600:.1f} hours ({total_eta/3600/24:.1f} days)")


if __name__ == '__main__':
    main()
