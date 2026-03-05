#!/usr/bin/env python3
"""
Phase 2A: Unified Temporal SHAP using V2.1 Methodology (CORRECT)

CRITICAL: Uses ALL domain indicators as aggregate target, NOT top 5 by coverage.

V2.1 Methodology:
1. For each domain, get ALL indicators from V2.1 hierarchy
2. Normalize each indicator to [0, 1]
3. INVERT negative outcomes (mortality, inequality, disease) → (1 - normalized)
4. domain_score = mean(all normalized indicators)  ← THIS IS THE TARGET
5. Train LightGBM: X = all 1,763 indicators, y = domain_score
6. SHAP tells us: "What predicts this domain's aggregate?"

Output: data/v3_1_temporal_shap/unified/{domain}/{year}_shap.json
"""

import argparse
import json
import warnings
import time
import subprocess
from pathlib import Path
from datetime import datetime
from joblib import Parallel, delayed

import numpy as np
import pandas as pd
import lightgbm as lgb
import shap

warnings.filterwarnings('ignore')

# === PATHS ===
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
PANEL_PATH = DATA_DIR / "raw" / "v21_panel_data_for_v3.parquet"
V21_HIERARCHY_PATH = Path("<repo-root>/v2.1/outputs/B5/v2_1_visualization.json")
INDICATOR_PROPS_PATH = DATA_DIR / "metadata" / "indicator_properties.json"
OUTPUT_DIR = DATA_DIR / "v3_1_temporal_shap" / "unified"

# === CONFIGURATION ===
MIN_YEAR = 1995
MAX_YEAR = 2024
YEARS = list(range(MIN_YEAR, MAX_YEAR + 1))

BOOTSTRAP_SAMPLES = 100
MIN_SAMPLES = 50  # Need more for unified (pooled)
MIN_INDICATORS = 20
MIN_DOMAIN_INDICATORS = 5  # At least 5 domain indicators to form aggregate
N_JOBS = 12  # Cores for bootstrap parallelization

MODEL_PARAMS = {
    'n_estimators': 100,
    'max_depth': 5,
    'learning_rate': 0.1,
    'subsample': 0.8,
    'random_state': 42,
    'verbose': -1,
    'n_jobs': 1  # Single-threaded per model (parallelized at bootstrap level)
}


def get_git_commit():
    """Get current git commit hash."""
    try:
        result = subprocess.run(
            ['git', 'rev-parse', '--short', 'HEAD'],
            capture_output=True, text=True, cwd=PROJECT_ROOT
        )
        return result.stdout.strip() if result.returncode == 0 else "unknown"
    except:
        return "unknown"


def load_indicator_directions():
    """Load indicator direction (positive/negative) from metadata."""
    if not INDICATOR_PROPS_PATH.exists():
        print("  WARNING: indicator_properties.json not found, assuming all positive")
        return {}

    with open(INDICATOR_PROPS_PATH) as f:
        data = json.load(f)

    directions = {}
    for ind_id, props in data.get('indicators', {}).items():
        directions[ind_id] = props.get('direction', 'positive')

    neg_count = sum(1 for d in directions.values() if d == 'negative')
    print(f"  Loaded {len(directions)} indicator directions ({neg_count} negative)")
    return directions


def load_v21_domains():
    """Load V2.1 outcome domains from hierarchy."""
    print("Loading V2.1 hierarchy...")

    with open(V21_HIERARCHY_PATH) as f:
        data = json.load(f)

    nodes = {n['id']: n for n in data['nodes']}

    domains = {}
    for node in data['nodes']:
        if node.get('layer') == 1 and node.get('node_type') == 'outcome_category':
            domain_id = node['id']
            domain_name = node['label']

            # Recursively find all indicator descendants
            indicators = []
            to_visit = node.get('children', [])[:]

            while to_visit:
                child_id = to_visit.pop(0)
                child = nodes.get(child_id)
                if child:
                    if child.get('node_type') == 'indicator' or child.get('is_indicator'):
                        indicators.append(child_id)
                    else:
                        to_visit.extend(child.get('children', []))

            # Create safe filename from domain name
            safe_name = domain_name.lower().replace(' & ', '_').replace(' ', '_')

            domains[safe_name] = {
                'id': domain_id,
                'name': domain_name,
                'indicators': set(indicators)
            }

    print(f"  Loaded {len(domains)} domains")
    for name, info in domains.items():
        print(f"    {name}: {len(info['indicators'])} indicators")
    return domains


def _single_bootstrap(X, y, seed):
    """Single bootstrap iteration."""
    np.random.seed(seed)
    idx = np.random.choice(len(X), size=len(X), replace=True)

    model = lgb.LGBMRegressor(**MODEL_PARAMS)
    model.fit(X[idx], y[idx])

    explainer = shap.TreeExplainer(model)
    shap_vals = explainer.shap_values(X[idx])

    return np.mean(np.abs(shap_vals), axis=0)


def compute_unified_domain(panel, domain_key, domain_info, year, panel_indicators, indicator_directions):
    """
    Compute unified SHAP for one (domain, year) case.

    CORRECT V2.1 METHODOLOGY:
    - Target = aggregate of ALL domain indicators (not top 5)
    - Negative outcomes are inverted
    """

    out_dir = OUTPUT_DIR / domain_key
    out_path = out_dir / f"{year}_shap.json"

    # Skip if exists
    if out_path.exists():
        return 'skip', domain_key, year, None

    domain_name = domain_info['name']
    domain_indicators = domain_info['indicators'] & panel_indicators

    if len(domain_indicators) < MIN_DOMAIN_INDICATORS:
        return 'fail', domain_key, year, f"Insufficient domain indicators: {len(domain_indicators)}"

    # Filter data up to year - pool all countries
    mask = panel['year'] <= year
    data = panel[mask]

    if len(data) == 0:
        return 'fail', domain_key, year, "No data"

    # Pivot to wide format (country, year) as index
    wide = data.pivot_table(
        index=['country', 'year'],
        columns='indicator_id',
        values='value',
        aggfunc='mean'
    )

    if len(wide) < MIN_SAMPLES:
        return 'fail', domain_key, year, f"Insufficient samples: {len(wide)}"

    # Find available domain indicators in this data
    available_domain = [i for i in domain_indicators if i in wide.columns]

    if len(available_domain) < MIN_DOMAIN_INDICATORS:
        return 'fail', domain_key, year, f"Insufficient available domain indicators: {len(available_domain)}"

    # =========================================================================
    # CORRECT V2.1: Use ALL domain indicators as aggregate target
    # =========================================================================
    target_parts = []
    target_quality = {}
    n_inverted = 0

    for ind in available_domain:
        vals = wide[ind].values.astype(float)
        non_nan = np.sum(~np.isnan(vals))

        # Skip if insufficient data
        if non_nan < 10:
            continue

        min_val, max_val = np.nanmin(vals), np.nanmax(vals)
        if max_val <= min_val:
            continue  # No variation

        # Normalize to [0, 1]
        normalized = (vals - min_val) / (max_val - min_val)

        # INVERT negative outcomes (mortality, inequality, disease)
        # So higher = better for all indicators
        direction = indicator_directions.get(ind, 'positive')
        if direction == 'negative':
            normalized = 1.0 - normalized
            n_inverted += 1

        target_parts.append(normalized)
        target_quality[ind] = {
            'indicator_id': ind,
            'n_observations': int(non_nan),
            'coverage': float(non_nan / len(vals)),
            'direction': direction,
            'inverted': direction == 'negative'
        }

    if len(target_parts) < MIN_DOMAIN_INDICATORS:
        return 'fail', domain_key, year, f"Could not create target composite: {len(target_parts)} valid indicators (need {MIN_DOMAIN_INDICATORS})"

    # Domain aggregate = mean of ALL normalized (and inverted) indicators
    y = np.nanmean(target_parts, axis=0)

    # =========================================================================
    # Features = ALL indicators (not just non-domain)
    # This is what V2.1 actually does - predict domain from everything
    # =========================================================================
    feature_cols = list(wide.columns)

    if len(feature_cols) < MIN_INDICATORS:
        return 'fail', domain_key, year, f"Insufficient features: {len(feature_cols)}"

    X = wide[feature_cols].fillna(wide[feature_cols].median())
    X = X.loc[:, ~X.isna().all()]

    if len(X.columns) < MIN_INDICATORS:
        return 'fail', domain_key, year, f"Insufficient valid features: {len(X.columns)}"

    # Remove rows with NaN in target
    valid_idx = ~np.isnan(y)
    X_clean = X[valid_idx].values
    y_clean = y[valid_idx]
    feature_names = list(X.columns)

    if len(X_clean) < MIN_SAMPLES:
        return 'fail', domain_key, year, f"Insufficient clean samples: {len(X_clean)}"

    # Bootstrap SHAP - parallelized
    start_time = time.time()

    bootstrap_results = Parallel(n_jobs=N_JOBS)(
        delayed(_single_bootstrap)(X_clean, y_clean, seed)
        for seed in range(BOOTSTRAP_SAMPLES)
    )

    bootstrap_shap = np.array(bootstrap_results)
    compute_time = time.time() - start_time

    # Compute statistics
    shap_importance = {}
    for i, ind in enumerate(feature_names):
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

    mean_importance = np.mean([v['mean'] for v in shap_importance.values()])
    ci_widths = [v['ci_upper'] - v['ci_lower'] for v in shap_importance.values()]
    n_countries = len(wide.index.get_level_values('country').unique())

    # Build warnings
    warnings_list = []
    if len(X_clean) < 100:
        warnings_list.append(f"Low sample size: {len(X_clean)}")
    if len(target_quality) < 20:
        warnings_list.append(f"Few target components: {len(target_quality)}")
    if np.mean(ci_widths) > 0.5:
        warnings_list.append(f"Wide CIs: mean={np.mean(ci_widths):.2f}")

    # Build result matching existing schema
    result = {
        'country': 'unified',
        'target': domain_key,
        'target_name': domain_name,
        'year': year,
        'shap_importance': shap_importance,
        'target_quality': target_quality,
        'metadata': {
            'n_samples': len(X_clean),
            'n_countries': n_countries,
            'n_indicators': len(feature_names),
            'n_bootstrap': BOOTSTRAP_SAMPLES,
            'mean_importance': float(mean_importance),
            'n_target_indicators': len(target_quality),
            'n_target_inverted': n_inverted,
            'target_components': list(target_quality.keys()),
            'year_range': [int(wide.index.get_level_values('year').min()),
                          int(wide.index.get_level_values('year').max())],
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
            'code_version': 'v3.1.0-v21methodology-correct',
            'git_commit': get_git_commit(),
            'model': 'LGBMRegressor',
            'hyperparameters': MODEL_PARAMS,
            'methodology': 'V2.1: ALL domain indicators as aggregate target (not top 5)',
            'warnings': warnings_list
        }
    }

    # Save
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_path, 'w') as f:
        json.dump(result, f, indent=2)

    return 'success', domain_key, year, compute_time


def main():
    parser = argparse.ArgumentParser(description='Unified Temporal SHAP (V2.1 Methodology - CORRECT)')
    parser.add_argument('--test', action='store_true', help='Test with 3 cases')
    parser.add_argument('--cores', type=int, default=12, help='Number of cores for bootstrap')
    parser.add_argument('--domain', type=str, help='Process specific domain only')
    parser.add_argument('--year', type=int, help='Process specific year only')
    args = parser.parse_args()

    global N_JOBS
    N_JOBS = args.cores

    print("=" * 60)
    print("UNIFIED TEMPORAL SHAP - V2.1 Methodology (CORRECT)")
    print("=" * 60)
    print(f"Cores: {N_JOBS}")
    print(f"Bootstrap iterations: {BOOTSTRAP_SAMPLES}")
    print()
    print("METHODOLOGY: Target = aggregate of ALL domain indicators")
    print("             Negative outcomes (mortality, etc.) are INVERTED")
    print()

    # Load indicator directions
    indicator_directions = load_indicator_directions()

    # Load V2.1 domains
    domains = load_v21_domains()

    # Load panel data
    print("\nLoading panel data...")
    panel = pd.read_parquet(PANEL_PATH)
    panel_indicators = set(panel['indicator_id'].unique())
    print(f"  Loaded {len(panel):,} rows, {len(panel_indicators)} indicators")

    # Filter domains if specified
    if args.domain:
        if args.domain in domains:
            domains = {args.domain: domains[args.domain]}
        else:
            print(f"ERROR: Domain '{args.domain}' not found")
            print(f"Available: {list(domains.keys())}")
            return

    # Filter years if specified
    years = YEARS
    if args.year:
        years = [args.year]

    # Build case list
    cases = [(d, y) for d in domains.keys() for y in years]

    if args.test:
        cases = cases[:3]
        print(f"\nTEST MODE: Running {len(cases)} cases")
    else:
        print(f"\nTotal cases: {len(cases)} ({len(domains)} domains × {len(years)} years)")

    # Check existing
    existing = sum(1 for d, y in cases if (OUTPUT_DIR / d / f"{y}_shap.json").exists())
    print(f"Already completed: {existing}")
    print(f"Remaining: {len(cases) - existing}")

    print("\n" + "-" * 60)
    print("Starting computation...")
    print("-" * 60)

    start_time = time.time()
    successes = 0
    skips = 0
    failures = 0

    for i, (domain_key, year) in enumerate(cases):
        status, d, y, info = compute_unified_domain(
            panel, domain_key, domains[domain_key], year, panel_indicators, indicator_directions
        )

        if status == 'success':
            successes += 1
            print(f"[{i+1}/{len(cases)}] {domain_key}/{year}: SUCCESS ({info:.1f}s) - {domains[domain_key]['name']}")
        elif status == 'skip':
            skips += 1
            if not args.test:
                continue  # Don't print skips unless testing
            print(f"[{i+1}/{len(cases)}] {domain_key}/{year}: SKIP")
        else:
            failures += 1
            print(f"[{i+1}/{len(cases)}] {domain_key}/{year}: FAIL - {info}")

    total_time = time.time() - start_time

    print("\n" + "=" * 60)
    print("COMPLETE")
    print("=" * 60)
    print(f"Time: {total_time/60:.1f} minutes ({total_time/3600:.2f} hours)")
    print(f"Success: {successes}, Skip: {skips}, Fail: {failures}")
    print(f"Output: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
