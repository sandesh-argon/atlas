#!/usr/bin/env python3
"""
Phase 2A: Compute Temporal SHAP with Bootstrap Confidence Intervals

For each (country, target, year):
1. Load panel data up to year Y (cumulative window)
2. Compute target composite
3. Train LightGBM model
4. Compute SHAP values with bootstrap CIs
5. Save JSON with data quality and provenance

Output: data/v3_1_temporal_shap/{unified,countries}/{target}/{year}_shap.json

Usage:
    python compute_temporal_shap.py --test          # Test 3 cases
    python compute_temporal_shap.py --test-timing   # Time estimate run
    python compute_temporal_shap.py                 # Full run
    python compute_temporal_shap.py --resume        # Resume from checkpoint
"""

import argparse
import json
import warnings
import time
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd
import lightgbm as lgb
import shap
from tqdm import tqdm

warnings.filterwarnings('ignore')

# === PATHS ===
PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
PANEL_PATH = DATA_DIR / "raw" / "v21_panel_data_for_v3.parquet"
NODES_PATH = DATA_DIR / "raw" / "v21_nodes.csv"
GRAPHS_DIR = DATA_DIR / "country_graphs"
METADATA_DIR = DATA_DIR / "metadata"
OUTPUT_DIR = DATA_DIR / "v3_1_temporal_shap"

# === CONFIGURATION ===
MIN_YEAR = 1995
MAX_YEAR = 2024
YEARS = list(range(MIN_YEAR, MAX_YEAR + 1))

BOOTSTRAP_SAMPLES = 100
MIN_SAMPLES = 10  # Minimum observations to train model
MIN_INDICATORS = 20  # Minimum indicators needed

# Model hyperparameters (LightGBM)
MODEL_PARAMS = {
    'n_estimators': 100,
    'max_depth': 5,
    'learning_rate': 0.1,
    'subsample': 0.8,
    'random_state': 42,
    'verbose': -1,
    'n_jobs': 1  # Use 1 to avoid conflict with outer parallelization
}

# Target definitions - outcome indicators for each domain
TARGETS = {
    'quality_of_life': {
        'name': 'Quality of Life',
        'outcomes': [
            {'ids': ['SP.DYN.LE00.IN', 'wdi_lifexp'], 'negative': False, 'name': 'Life Expectancy'},
            {'ids': ['NY.GDP.PCAP.KD', 'NY.GDP.PCAP.PP.KD'], 'negative': False, 'name': 'GDP per Capita'},
            {'ids': ['SP.DYN.IMRT.IN', 'SH.DYN.MORT'], 'negative': True, 'name': 'Infant Mortality'},
            {'ids': ['SE.ADT.LITR.ZS'], 'negative': False, 'name': 'Literacy Rate'},
            {'ids': ['SI.POV.GINI'], 'negative': True, 'name': 'Gini Index'},
        ]
    },
    'health': {
        'name': 'Health',
        'outcomes': [
            {'ids': ['SP.DYN.LE00.IN', 'wdi_lifexp'], 'negative': False, 'name': 'Life Expectancy'},
            {'ids': ['SP.DYN.IMRT.IN'], 'negative': True, 'name': 'Infant Mortality'},
            {'ids': ['SH.XPD.CHEX.PC.CD'], 'negative': False, 'name': 'Health Expenditure'},
        ]
    },
    'education': {
        'name': 'Education',
        'outcomes': [
            {'ids': ['SE.ADT.LITR.ZS'], 'negative': False, 'name': 'Literacy Rate'},
            {'ids': ['SE.PRM.NENR', 'SE.PRM.ENRR'], 'negative': False, 'name': 'Primary Enrollment'},
            {'ids': ['SE.SEC.NENR', 'SE.SEC.ENRR'], 'negative': False, 'name': 'Secondary Enrollment'},
        ]
    },
    'economic': {
        'name': 'Economic',
        'outcomes': [
            {'ids': ['NY.GDP.PCAP.KD', 'NY.GDP.PCAP.PP.KD'], 'negative': False, 'name': 'GDP per Capita'},
            {'ids': ['NY.GDP.MKTP.KD.ZG'], 'negative': False, 'name': 'GDP Growth'},
            {'ids': ['SL.UEM.TOTL.ZS'], 'negative': True, 'name': 'Unemployment'},
        ]
    },
    'governance': {
        'name': 'Governance',
        'outcomes': [
            {'ids': ['v2x_polyarchy'], 'negative': False, 'name': 'Electoral Democracy'},
            {'ids': ['v2x_libdem'], 'negative': False, 'name': 'Liberal Democracy'},
            {'ids': ['v2x_corr'], 'negative': True, 'name': 'Corruption'},
        ]
    },
    'environment': {
        'name': 'Environment',
        'outcomes': [
            {'ids': ['EN.ATM.CO2E.PC'], 'negative': True, 'name': 'CO2 Emissions'},
            {'ids': ['AG.LND.FRST.ZS'], 'negative': False, 'name': 'Forest Area'},
            {'ids': ['EG.ELC.ACCS.ZS'], 'negative': False, 'name': 'Electricity Access'},
        ]
    },
    'demographics': {
        'name': 'Demographics',
        'outcomes': [
            {'ids': ['SP.DYN.LE00.IN'], 'negative': False, 'name': 'Life Expectancy'},
            {'ids': ['SP.POP.GROW'], 'negative': False, 'name': 'Population Growth'},
            {'ids': ['SP.URB.TOTL.IN.ZS'], 'negative': False, 'name': 'Urbanization'},
        ]
    },
    'security': {
        'name': 'Security',
        'outcomes': [
            {'ids': ['VC.IHR.PSRC.P5'], 'negative': True, 'name': 'Homicide Rate'},
            {'ids': ['v2x_rule'], 'negative': False, 'name': 'Rule of Law'},
        ]
    },
    'development': {
        'name': 'Development',
        'outcomes': [
            {'ids': ['NY.GDP.PCAP.KD'], 'negative': False, 'name': 'GDP per Capita'},
            {'ids': ['EG.ELC.ACCS.ZS'], 'negative': False, 'name': 'Electricity Access'},
            {'ids': ['IT.NET.USER.ZS'], 'negative': False, 'name': 'Internet Users'},
        ]
    }
}


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


def load_leaf_indicators() -> set:
    """Load leaf indicator IDs (node_type='indicator')."""
    nodes = pd.read_csv(NODES_PATH)
    leaf_ids = set(nodes[nodes['node_type'] == 'indicator']['id'])
    return leaf_ids


def get_all_panel_indicators(panel: pd.DataFrame) -> set:
    """Get all indicator IDs from panel data."""
    return set(panel['indicator_id'].unique())


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
    year: int,
    valid_indicators: set = None
) -> Optional[pd.DataFrame]:
    """
    Pivot country data up to specified year to wide format.

    Args:
        panel: Full panel data
        country: Country name
        year: Max year (inclusive)
        valid_indicators: Optional set to filter indicators (if None, use all)

    Returns DataFrame with years as rows, indicators as columns.
    """
    # Filter to country and year range
    mask = (panel['country'] == country) & (panel['year'] <= year)
    country_data = panel[mask]

    if len(country_data) == 0:
        return None

    # Filter to valid indicators if specified
    if valid_indicators is not None:
        country_data = country_data[country_data['indicator_id'].isin(valid_indicators)]

    if len(country_data) == 0:
        return None

    # Pivot to wide format
    wide = country_data.pivot_table(
        index='year',
        columns='indicator_id',
        values='value',
        aggfunc='mean'
    )

    return wide


def pivot_unified_year_data(
    panel: pd.DataFrame,
    year: int,
    valid_indicators: set = None
) -> Optional[pd.DataFrame]:
    """
    Pivot ALL countries' data up to specified year to wide format (unified/global).

    Each row = (country, year) combination.

    Args:
        panel: Full panel data
        year: Max year (inclusive)
        valid_indicators: Optional set to filter indicators (if None, use all)

    Returns DataFrame with (country, year) as rows, indicators as columns.
    """
    # Filter to year range
    mask = panel['year'] <= year
    data = panel[mask]

    if len(data) == 0:
        return None

    # Filter to valid indicators if specified
    if valid_indicators is not None:
        data = data[data['indicator_id'].isin(valid_indicators)]

    if len(data) == 0:
        return None

    # Pivot to wide format with (country, year) as index
    wide = data.pivot_table(
        index=['country', 'year'],
        columns='indicator_id',
        values='value',
        aggfunc='mean'
    )

    return wide


def compute_target_composite(
    wide_data: pd.DataFrame,
    target_config: dict
) -> tuple:
    """
    Compute target composite from outcome indicators.

    Returns: (composite_values, components_used, data_quality)
    """
    components = []
    components_used = []
    data_quality = {}

    for outcome in target_config['outcomes']:
        # Try each fallback indicator
        values = None
        used_id = None

        for ind_id in outcome['ids']:
            if ind_id in wide_data.columns:
                vals = wide_data[ind_id].values.astype(float)
                non_nan = np.sum(~np.isnan(vals))
                if non_nan >= 3:  # Need at least 3 observations
                    values = vals
                    used_id = ind_id
                    break

        if values is None:
            continue

        # Normalize to [0, 1]
        min_val = np.nanmin(values)
        max_val = np.nanmax(values)

        if max_val > min_val:
            normalized = (values - min_val) / (max_val - min_val)
        else:
            normalized = np.ones_like(values) * 0.5

        # Invert negative indicators
        if outcome['negative']:
            normalized = 1 - normalized

        components.append(normalized)
        components_used.append(outcome['name'])
        data_quality[outcome['name']] = {
            'indicator_id': used_id,
            'n_observations': int(np.sum(~np.isnan(values))),
            'coverage': float(np.sum(~np.isnan(values)) / len(values))
        }

    if len(components) < 2:
        return None, [], {}

    # Mean across components
    composite = np.nanmean(components, axis=0)

    return composite, components_used, data_quality


def _single_bootstrap_shap(X: np.ndarray, y: np.ndarray, indicators: list, seed: int) -> np.ndarray:
    """Single bootstrap iteration for parallel execution."""
    np.random.seed(seed)
    indices = np.random.choice(len(X), size=len(X), replace=True)
    X_boot = X[indices]
    y_boot = y[indices]

    model = lgb.LGBMRegressor(**MODEL_PARAMS)
    model.fit(X_boot, y_boot)

    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X_boot)

    return np.mean(np.abs(shap_values), axis=0)


def compute_shap_with_bootstrap(
    X: pd.DataFrame,
    y: np.ndarray,
    n_bootstrap: int = 100,
    n_jobs: int = 20
) -> dict:
    """
    Compute SHAP importance with bootstrap confidence intervals.

    Uses parallel processing for bootstrap iterations.

    Returns: {indicator_id: {'mean': float, 'ci_lower': float, 'ci_upper': float}}
    """
    from joblib import Parallel, delayed

    indicators = list(X.columns)
    X_arr = X.values

    # Parallel bootstrap
    bootstrap_shap = Parallel(n_jobs=n_jobs)(
        delayed(_single_bootstrap_shap)(X_arr, y, indicators, seed=i)
        for i in range(n_bootstrap)
    )

    bootstrap_shap = np.array(bootstrap_shap)

    # Compute statistics
    shap_importance = {}
    for i, ind in enumerate(indicators):
        vals = bootstrap_shap[:, i]
        shap_importance[ind] = {
            'mean': float(np.mean(vals)),
            'ci_lower': float(np.percentile(vals, 2.5)),
            'ci_upper': float(np.percentile(vals, 97.5)),
            'std': float(np.std(vals))
        }

    # Normalize so max mean = 1.0
    max_mean = max(v['mean'] for v in shap_importance.values()) if shap_importance else 1.0
    if max_mean > 0:
        for ind in shap_importance:
            shap_importance[ind]['mean'] /= max_mean
            shap_importance[ind]['ci_lower'] /= max_mean
            shap_importance[ind]['ci_upper'] /= max_mean
            shap_importance[ind]['std'] /= max_mean

    return shap_importance


def compute_shap_case(
    panel: pd.DataFrame,
    country: str,
    target_key: str,
    year: int,
    n_bootstrap: int = 100
) -> tuple:
    """
    Compute SHAP for one (country, target, year) case.

    Returns: (result_dict, failure_reason)
        - On success: (result, None)
        - On failure: (None, reason_string)
    """
    target_config = TARGETS[target_key]

    # Get wide data up to year (use all indicators in panel)
    wide = pivot_country_year_data(panel, country, year, valid_indicators=None)

    if wide is None:
        return None, f"No data for country '{country}'"

    if len(wide) < MIN_SAMPLES:
        return None, f"Insufficient samples: {len(wide)} < {MIN_SAMPLES} (cumulative years)"

    # Compute target composite
    y, components_used, target_quality = compute_target_composite(wide, target_config)

    if y is None or len(components_used) < 2:
        return None, f"Insufficient target components: {len(components_used) if components_used else 0} < 2"

    # Prepare features (all indicators except target outcomes)
    target_indicator_ids = set()
    for outcome in target_config['outcomes']:
        target_indicator_ids.update(outcome['ids'])

    feature_cols = [c for c in wide.columns if c not in target_indicator_ids]

    if len(feature_cols) < MIN_INDICATORS:
        return None, f"Insufficient feature indicators: {len(feature_cols)} < {MIN_INDICATORS}"

    X = wide[feature_cols].copy()

    # Fill NaN with column median
    X = X.fillna(X.median())

    # Remove columns still all NaN
    valid_cols = X.columns[~X.isna().all()]
    X = X[valid_cols]

    if len(X.columns) < MIN_INDICATORS:
        return None, f"Insufficient valid indicators after NaN removal: {len(X.columns)} < {MIN_INDICATORS}"

    # Remove rows with NaN in target
    valid_idx = ~np.isnan(y)
    X_clean = X[valid_idx]
    y_clean = y[valid_idx]

    if len(X_clean) < MIN_SAMPLES:
        return None, f"Insufficient samples after NaN removal: {len(X_clean)} < {MIN_SAMPLES}"

    # Compute SHAP with bootstrap
    start_time = time.time()
    shap_importance = compute_shap_with_bootstrap(X_clean, y_clean, n_bootstrap)
    compute_time = time.time() - start_time

    # Compute mean importance across all indicators
    mean_importance = np.mean([v['mean'] for v in shap_importance.values()])

    # Compute data quality metrics
    ci_widths = [v['ci_upper'] - v['ci_lower'] for v in shap_importance.values()]

    # Build warnings list
    warnings = []
    if len(X_clean) < 20:
        warnings.append(f"Low sample size: {len(X_clean)}")
    if len(components_used) < 3:
        warnings.append(f"Few target components: {len(components_used)}")
    if np.mean(ci_widths) > 0.5:
        warnings.append(f"Wide confidence intervals: mean={np.mean(ci_widths):.2f}")

    # Build result
    result = {
        'country': country,
        'target': target_key,
        'target_name': target_config['name'],
        'year': year,
        'shap_importance': shap_importance,
        'target_quality': target_quality,
        'metadata': {
            'n_samples': len(X_clean),
            'n_indicators': len(X_clean.columns),
            'n_bootstrap': n_bootstrap,
            'mean_importance': float(mean_importance),
            'target_components': components_used,
            'year_range': [int(wide.index.min()), int(wide.index.max())],
            'computation_time_sec': round(compute_time, 2)
        },
        'data_quality': {
            'mean_ci_width': float(np.mean(ci_widths)),
            'median_ci_width': float(np.median(ci_widths)),
            'max_ci_width': float(np.max(ci_widths)),
            'indicators_with_wide_ci': int(sum(1 for w in ci_widths if w > 0.5)),
            'target_coverage': float(np.mean([v['coverage'] for v in target_quality.values()])) if target_quality else 0.0
        },
        'provenance': {
            'computation_date': datetime.now().isoformat(),
            'code_version': 'v3.1.0',
            'git_commit': get_git_commit(),
            'model': 'LGBMRegressor',
            'hyperparameters': MODEL_PARAMS,
            'warnings': warnings
        }
    }

    return result, None


def compute_unified_shap_case(
    panel: pd.DataFrame,
    target_key: str,
    year: int,
    n_bootstrap: int = 100
) -> tuple:
    """
    Compute SHAP for unified (global pooled) data for one (target, year) case.

    Pools all countries together - each observation is a (country, year) pair.

    Returns: (result_dict, failure_reason)
        - On success: (result, None)
        - On failure: (None, reason_string)
    """
    target_config = TARGETS[target_key]

    # Get wide data pooling all countries up to year
    wide = pivot_unified_year_data(panel, year, valid_indicators=None)

    if wide is None:
        return None, "No data available for unified computation"

    if len(wide) < MIN_SAMPLES:
        return None, f"Insufficient samples: {len(wide)} < {MIN_SAMPLES}"

    # Compute target composite
    y, components_used, target_quality = compute_target_composite(wide, target_config)

    if y is None or len(components_used) < 2:
        return None, f"Insufficient target components: {len(components_used) if components_used else 0} < 2"

    # Prepare features (all indicators except target outcomes)
    target_indicator_ids = set()
    for outcome in target_config['outcomes']:
        target_indicator_ids.update(outcome['ids'])

    feature_cols = [c for c in wide.columns if c not in target_indicator_ids]

    if len(feature_cols) < MIN_INDICATORS:
        return None, f"Insufficient feature indicators: {len(feature_cols)} < {MIN_INDICATORS}"

    X = wide[feature_cols].copy()

    # Fill NaN with column median
    X = X.fillna(X.median())

    # Remove columns still all NaN
    valid_cols = X.columns[~X.isna().all()]
    X = X[valid_cols]

    if len(X.columns) < MIN_INDICATORS:
        return None, f"Insufficient valid indicators after NaN removal: {len(X.columns)} < {MIN_INDICATORS}"

    # Remove rows with NaN in target
    valid_idx = ~np.isnan(y)
    X_clean = X[valid_idx]
    y_clean = y[valid_idx]

    if len(X_clean) < MIN_SAMPLES:
        return None, f"Insufficient samples after NaN removal: {len(X_clean)} < {MIN_SAMPLES}"

    # Compute SHAP with bootstrap
    start_time = time.time()
    shap_importance = compute_shap_with_bootstrap(X_clean, y_clean, n_bootstrap)
    compute_time = time.time() - start_time

    # Compute mean importance across all indicators
    mean_importance = np.mean([v['mean'] for v in shap_importance.values()])

    # Count countries in the pooled data
    n_countries = len(wide.index.get_level_values('country').unique())

    # Build result
    result = {
        'country': 'unified',
        'target': target_key,
        'target_name': target_config['name'],
        'year': year,
        'shap_importance': shap_importance,
        'target_quality': target_quality,
        'metadata': {
            'n_samples': len(X_clean),
            'n_countries': n_countries,
            'n_indicators': len(X_clean.columns),
            'n_bootstrap': n_bootstrap,
            'mean_importance': float(mean_importance),
            'target_components': components_used,
            'year_range': [int(wide.index.get_level_values('year').min()),
                          int(wide.index.get_level_values('year').max())],
            'computation_time_sec': round(compute_time, 2)
        },
        'provenance': {
            'computation_date': datetime.now().isoformat(),
            'code_version': 'v3.1.0',
            'git_commit': get_git_commit(),
            'model': 'LGBMRegressor',
            'hyperparameters': MODEL_PARAMS
        }
    }

    return result, None


def save_result(result: dict, is_unified: bool = False):
    """Save result to JSON file."""
    if is_unified:
        out_dir = OUTPUT_DIR / "unified" / result['target']
    else:
        out_dir = OUTPUT_DIR / "countries" / result['country'] / result['target']

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{result['year']}_shap.json"

    with open(out_path, 'w') as f:
        json.dump(result, f, indent=2)


def run_test(panel: pd.DataFrame):
    """Run test on 3 cases to verify functionality."""
    print("\n" + "=" * 60)
    print("TEST MODE: Running 3 test cases")
    print("=" * 60)

    test_cases = [
        ('United States', 'quality_of_life', 2020),
        ('Rwanda', 'health', 2015),
        ('Germany', 'economic', 2010),
    ]

    for country, target, year in test_cases:
        print(f"\nTesting: {country} / {target} / {year}")

        start = time.time()
        result, failure_reason = compute_shap_case(
            panel, country, target, year,
            n_bootstrap=10  # Fewer bootstraps for test
        )
        elapsed = time.time() - start

        if result:
            n_indicators = len(result['shap_importance'])
            top_3 = sorted(
                result['shap_importance'].items(),
                key=lambda x: x[1]['mean'],
                reverse=True
            )[:3]

            print(f"  Success: {n_indicators} indicators, {elapsed:.1f}s")
            print(f"  Top 3: {[t[0][:20] for t in top_3]}")

            # Save test output
            save_result(result)
            print(f"  Saved to: {OUTPUT_DIR}/countries/{country}/{target}/{year}_shap.json")
        else:
            print(f"  Failed: {failure_reason}")

    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)


def run_timing_test(panel: pd.DataFrame):
    """Run timing test to estimate full runtime."""
    print("\n" + "=" * 60)
    print("TIMING TEST: Estimating full runtime")
    print("=" * 60)

    # Test cases with different characteristics
    test_cases = [
        ('United States', 'quality_of_life', 2020),  # Rich data
        ('Rwanda', 'health', 2010),                   # Moderate data
        ('Afghanistan', 'economic', 2005),           # Sparse data
    ]

    times = []

    for country, target, year in test_cases:
        print(f"\nTiming: {country} / {target} / {year}")

        start = time.time()
        result, failure_reason = compute_shap_case(
            panel, country, target, year,
            n_bootstrap=BOOTSTRAP_SAMPLES  # Full bootstrap
        )
        elapsed = time.time() - start

        if result:
            times.append(elapsed)
            print(f"  Time: {elapsed:.1f}s ({result['metadata']['n_samples']} samples, {result['metadata']['n_indicators']} indicators)")
        else:
            print(f"  Skipped: {failure_reason}")

    if times:
        avg_time = np.mean(times)

        # Estimate total
        countries = get_countries()
        n_countries = len(countries) + 1  # +1 for unified
        n_targets = len(TARGETS)
        n_years = len(YEARS)
        total_cases = n_countries * n_targets * n_years

        # Assume 70% success rate (some cases will have insufficient data)
        estimated_cases = int(total_cases * 0.7)
        estimated_hours = (estimated_cases * avg_time) / 3600

        print("\n" + "=" * 60)
        print("TIMING ESTIMATE")
        print("=" * 60)
        print(f"Average time per case: {avg_time:.1f}s")
        print(f"Total possible cases: {total_cases:,}")
        print(f"Estimated successful cases (~70%): {estimated_cases:,}")
        print(f"Estimated total runtime: {estimated_hours:.1f} hours")
        print(f"  With 12-core parallelization: ~{estimated_hours/12:.1f} hours")
        print("=" * 60)

        return avg_time, estimated_hours

    return None, None


def get_completed_cases() -> set:
    """Scan output directory to find already completed cases."""
    completed = set()

    # Check unified
    unified_dir = OUTPUT_DIR / "unified"
    if unified_dir.exists():
        for target_dir in unified_dir.iterdir():
            if target_dir.is_dir():
                for f in target_dir.glob("*_shap.json"):
                    year = int(f.stem.replace("_shap", ""))
                    completed.add(("unified", target_dir.name, year))

    # Check countries
    countries_dir = OUTPUT_DIR / "countries"
    if countries_dir.exists():
        for country_dir in countries_dir.iterdir():
            if country_dir.is_dir():
                for target_dir in country_dir.iterdir():
                    if target_dir.is_dir():
                        for f in target_dir.glob("*_shap.json"):
                            year = int(f.stem.replace("_shap", ""))
                            completed.add((country_dir.name, target_dir.name, year))

    return completed


def save_checkpoint(checkpoint_data: dict):
    """Save checkpoint file."""
    checkpoint_path = OUTPUT_DIR / "checkpoint.json"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(checkpoint_path, 'w') as f:
        json.dump(checkpoint_data, f, indent=2)


def log_failure(entity: str, target: str, year: int, reason: str):
    """Log a failure to the failures log file."""
    log_path = OUTPUT_DIR / "failures.jsonl"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    entry = {
        'timestamp': datetime.now().isoformat(),
        'entity': entity,
        'target': target,
        'year': year,
        'reason': reason
    }

    with open(log_path, 'a') as f:
        f.write(json.dumps(entry) + '\n')


def load_checkpoint() -> dict:
    """Load checkpoint file if exists."""
    checkpoint_path = OUTPUT_DIR / "checkpoint.json"
    if checkpoint_path.exists():
        with open(checkpoint_path) as f:
            return json.load(f)
    return None


def run_production(
    panel: pd.DataFrame,
    resume: bool = False,
    country_filter: str = None,
    target_filter: str = None
):
    """
    Run full production computation.

    Args:
        panel: Panel data
        resume: If True, skip already completed cases
        country_filter: Only process this country (optional)
        target_filter: Only process this target (optional)
    """
    print("\n" + "=" * 60)
    print("PRODUCTION RUN: Temporal SHAP Computation")
    print("=" * 60)

    # Get list of countries
    countries = get_countries()
    if country_filter:
        if country_filter in countries:
            countries = [country_filter]
        else:
            print(f"ERROR: Country '{country_filter}' not found")
            return

    # Add "unified" for global pooled analysis
    all_entities = ["unified"] + countries

    # Get targets
    targets = list(TARGETS.keys())
    if target_filter:
        if target_filter in targets:
            targets = [target_filter]
        else:
            print(f"ERROR: Target '{target_filter}' not found")
            return

    # Build case list
    all_cases = []
    for entity in all_entities:
        for target in targets:
            for year in YEARS:
                all_cases.append((entity, target, year))

    print(f"Total possible cases: {len(all_cases):,}")
    print(f"  Entities: {len(all_entities)} ({len(countries)} countries + unified)")
    print(f"  Targets: {len(targets)}")
    print(f"  Years: {len(YEARS)} ({MIN_YEAR}-{MAX_YEAR})")

    # Check for completed cases if resuming
    completed = set()
    if resume:
        completed = get_completed_cases()
        print(f"  Already completed: {len(completed):,}")

    # Filter to remaining cases
    remaining_cases = [c for c in all_cases if c not in completed]
    print(f"  Remaining: {len(remaining_cases):,}")

    if len(remaining_cases) == 0:
        print("\nAll cases already completed!")
        return

    # Estimate time
    avg_time = 3.1  # seconds per case from timing test
    est_hours = (len(remaining_cases) * 0.67 * avg_time) / 3600  # 67% success rate
    print(f"\nEstimated runtime: {est_hours:.1f} hours")

    # Production loop
    print("\n" + "-" * 60)
    print("Starting computation...")
    print("-" * 60 + "\n")

    start_time = time.time()
    successes = 0
    failures = 0
    skipped = 0

    # Progress tracking
    checkpoint_interval = 100  # Save checkpoint every N cases

    for i, (entity, target, year) in enumerate(tqdm(remaining_cases, desc="Computing SHAP")):
        try:
            # For unified, we'd need to pool all countries - skip for now
            if entity == "unified":
                # Compute unified (pooled) SHAP
                result, failure_reason = compute_unified_shap_case(
                    panel, target, year,
                    n_bootstrap=BOOTSTRAP_SAMPLES
                )
            else:
                # Compute country-specific SHAP
                result, failure_reason = compute_shap_case(
                    panel, entity, target, year,
                n_bootstrap=BOOTSTRAP_SAMPLES
            )

            if result:
                save_result(result, is_unified=(entity == "unified"))
                successes += 1
            else:
                log_failure(entity, target, year, failure_reason)
                failures += 1

            # Checkpoint
            if (i + 1) % checkpoint_interval == 0:
                elapsed = time.time() - start_time
                rate = (successes + failures) / elapsed if elapsed > 0 else 0
                eta = (len(remaining_cases) - i - 1) / rate / 3600 if rate > 0 else 0

                checkpoint_data = {
                    'timestamp': datetime.now().isoformat(),
                    'processed': i + 1,
                    'total': len(remaining_cases),
                    'successes': successes,
                    'failures': failures,
                    'skipped': skipped,
                    'elapsed_hours': elapsed / 3600,
                    'eta_hours': eta,
                    'rate_per_sec': rate
                }
                save_checkpoint(checkpoint_data)

        except Exception as e:
            log_failure(entity, target, year, f"Exception: {str(e)}")
            print(f"\nERROR processing {entity}/{target}/{year}: {e}")
            failures += 1
            continue

    # Final summary
    total_time = time.time() - start_time

    print("\n" + "=" * 60)
    print("PRODUCTION RUN COMPLETE")
    print("=" * 60)
    print(f"Total time: {total_time/3600:.1f} hours")
    print(f"Cases processed: {successes + failures + skipped:,}")
    print(f"  Successes: {successes:,}")
    print(f"  Failures: {failures:,}")
    print(f"  Skipped: {skipped:,}")
    print(f"Success rate: {100*successes/(successes+failures):.1f}%" if (successes+failures) > 0 else "N/A")
    print(f"Output directory: {OUTPUT_DIR}")

    # Save final checkpoint
    save_checkpoint({
        'timestamp': datetime.now().isoformat(),
        'status': 'completed',
        'total_time_hours': total_time / 3600,
        'successes': successes,
        'failures': failures,
        'skipped': skipped
    })


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Compute Temporal SHAP')
    parser.add_argument('--test', action='store_true', help='Run 3 test cases')
    parser.add_argument('--test-timing', action='store_true', help='Run timing estimate')
    parser.add_argument('--resume', action='store_true', help='Resume from checkpoint (skip completed)')
    parser.add_argument('--country', type=str, help='Process specific country only')
    parser.add_argument('--target', type=str, help='Process specific target only')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be computed without running')

    args = parser.parse_args()

    # Load data
    panel = load_panel_data()

    # Report indicator counts
    panel_indicators = set(panel['indicator_id'].unique())
    print(f"Panel indicators: {len(panel_indicators)}")

    if args.test:
        run_test(panel)
        return

    if args.test_timing:
        run_timing_test(panel)
        return

    if args.dry_run:
        # Show what would be computed
        countries = get_countries()
        if args.country:
            if args.country in countries:
                countries = [args.country]
            else:
                print(f"ERROR: Country '{args.country}' not found")
                return

        targets = list(TARGETS.keys())
        if args.target:
            if args.target in targets:
                targets = [args.target]
            else:
                print(f"ERROR: Target '{args.target}' not found")
                return

        completed = get_completed_cases() if args.resume else set()

        all_cases = []
        for entity in ["unified"] + countries:
            for target in targets:
                for year in YEARS:
                    all_cases.append((entity, target, year))

        remaining = [c for c in all_cases if c not in completed]

        print(f"\nDRY RUN:")
        print(f"  Total cases: {len(all_cases):,}")
        print(f"  Completed: {len(completed):,}")
        print(f"  Remaining: {len(remaining):,}")
        print(f"  Est. time: {len(remaining) * 0.67 * 3.1 / 3600:.1f} hours")
        return

    # Run production
    run_production(
        panel,
        resume=args.resume,
        country_filter=args.country,
        target_filter=args.target
    )


if __name__ == "__main__":
    main()
