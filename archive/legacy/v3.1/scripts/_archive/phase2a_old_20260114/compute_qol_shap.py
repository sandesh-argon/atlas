#!/usr/bin/env python3
"""
Phase 2A: Quality of Life SHAP - Single Model Approach

Creates ONE model predicting composite quality of life from all 9 domain aggregates.
SHAP directly answers: "How important is this indicator to OVERALL quality of life?"

Methodology:
1. For each of 9 V2.1 domains, create domain aggregate:
   - Get ALL indicators in domain from hierarchy
   - Normalize each to [0, 1]
   - INVERT negative outcomes (mortality, inequality, disease)
   - domain_agg = mean(normalized indicators)
2. Composite target = mean(all 9 domain aggregates)
3. Train SINGLE model: X = all indicators → y = composite
4. SHAP tells us importance to overall quality of life

Output: data/v3_1_temporal_shap/{unified|countries}/{entity}/quality_of_life/{year}_shap.json
"""

import argparse
import json
import warnings
import time
import os
from pathlib import Path
from datetime import datetime
# Note: Using sequential processing with LightGBM n_jobs=-1 for full CPU utilization

import numpy as np
import pandas as pd
import lightgbm as lgb
import shap

warnings.filterwarnings('ignore')

# === PATHS ===
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
PANEL_PATH = DATA_DIR / "raw" / "v21_panel_data_for_v3.parquet"
V21_HIERARCHY_PATH = Path.home() / "v2.1/outputs/B5/v2_1_visualization.json"
_LOCAL_V21 = Path("<repo-root>/v2.1/outputs/B5/v2_1_visualization.json")
if _LOCAL_V21.exists():
    V21_HIERARCHY_PATH = _LOCAL_V21
INDICATOR_PROPS_PATH = DATA_DIR / "metadata" / "indicator_properties.json"
OUTPUT_DIR = DATA_DIR / "v3_1_temporal_shap"
CANONICAL_COUNTRIES_DIR = DATA_DIR / "v3_1_temporal_graphs" / "countries"

# === CONFIGURATION ===
MIN_YEAR = 1995
MAX_YEAR = 2024
YEARS = list(range(MIN_YEAR, MAX_YEAR + 1))

BOOTSTRAP_SAMPLES = 100
MIN_SAMPLES = 10
MIN_INDICATORS = 20
MIN_DOMAIN_INDICATORS = 3

MODEL_PARAMS = {
    'n_estimators': 100,
    'max_depth': 5,
    'learning_rate': 0.1,
    'subsample': 0.8,
    'random_state': 42,
    'verbose': -1,
    'n_jobs': -1  # Use all cores per model (bootstrap is sequential)
}


def load_indicator_directions():
    """Load indicator directions from properties file."""
    if not INDICATOR_PROPS_PATH.exists():
        return {}
    with open(INDICATOR_PROPS_PATH) as f:
        props = json.load(f)

    # Handle nested structure
    indicators = props.get('indicators', props)

    directions = {}
    neg_count = 0
    for ind_id, info in indicators.items():
        if isinstance(info, dict):
            direction = info.get('direction', 'positive')
            directions[ind_id] = direction
            if direction == 'negative':
                neg_count += 1
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

            safe_name = domain_name.lower().replace(' & ', '_').replace(' ', '_')
            domains[safe_name] = {
                'id': domain_id,
                'name': domain_name,
                'indicators': set(indicators)
            }

    print(f"  Loaded {len(domains)} domains")
    return domains


def _single_bootstrap(X, y, seed):
    """Single bootstrap iteration (sequential)."""
    np.random.seed(seed)
    idx = np.random.choice(len(X), size=len(X), replace=True)
    X_boot = X.iloc[idx]
    y_boot = y.iloc[idx]

    model = lgb.LGBMRegressor(**MODEL_PARAMS)
    model.fit(X_boot, y_boot)

    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X)

    return np.abs(shap_values).mean(axis=0)


def compute_qol_shap(data, year, domains, indicator_directions, n_bootstrap=100):
    """
    Compute Quality of Life SHAP for a single (entity, year) case.

    Returns dict with SHAP importance or None if failed.
    """
    # Filter data up to year
    mask = data['year'] <= year
    subset = data[mask]

    if len(subset) == 0:
        return None, "No data"

    # Pivot to wide format
    wide = subset.pivot_table(
        index=['country', 'year'] if 'country' in subset.columns else 'year',
        columns='indicator_id',
        values='value',
        aggfunc='first'
    )

    if len(wide) < MIN_SAMPLES:
        return None, f"Insufficient samples: {len(wide)}"

    # Compute domain aggregates
    domain_aggregates = {}
    domain_quality = {}

    for domain_key, domain_info in domains.items():
        domain_indicators = domain_info['indicators']
        available = [i for i in domain_indicators if i in wide.columns]

        if len(available) < MIN_DOMAIN_INDICATORS:
            continue

        # Normalize and aggregate
        normalized_parts = []
        domain_details = {}
        n_inverted = 0

        for ind in available:
            vals = wide[ind].values.astype(float)
            non_nan = np.sum(~np.isnan(vals))

            if non_nan < 3:
                continue

            min_val, max_val = np.nanmin(vals), np.nanmax(vals)
            if max_val <= min_val:
                continue

            normalized = (vals - min_val) / (max_val - min_val)

            # Invert negative outcomes
            direction = indicator_directions.get(ind, 'positive')
            if direction == 'negative':
                normalized = 1.0 - normalized
                n_inverted += 1

            normalized_parts.append(normalized)
            domain_details[ind] = {
                'n_observations': int(non_nan),
                'direction': direction,
                'inverted': direction == 'negative'
            }

        if len(normalized_parts) < MIN_DOMAIN_INDICATORS:
            continue

        # Stack and compute mean
        stacked = np.column_stack(normalized_parts)
        domain_agg = np.nanmean(stacked, axis=1)

        domain_aggregates[domain_key] = domain_agg
        domain_quality[domain_key] = {
            'n_indicators': len(normalized_parts),
            'n_inverted': n_inverted,
            'mean_value': float(np.nanmean(domain_agg)),
            'indicators': domain_details
        }

    if len(domain_aggregates) < 3:
        return None, f"Insufficient domains: {len(domain_aggregates)}"

    # Create composite target: mean of all domain aggregates
    domain_matrix = np.column_stack(list(domain_aggregates.values()))
    composite_target = np.nanmean(domain_matrix, axis=1)

    # Create target Series
    y = pd.Series(composite_target, index=wide.index, name='quality_of_life')

    # Features: all available indicators
    feature_cols = [c for c in wide.columns if wide[c].notna().sum() >= MIN_SAMPLES]
    if len(feature_cols) < MIN_INDICATORS:
        return None, f"Insufficient features: {len(feature_cols)}"

    X = wide[feature_cols].copy()

    # Remove rows with NaN target
    valid_mask = ~np.isnan(y.values)
    X = X[valid_mask]
    y = y[valid_mask]

    # Fill remaining NaN features with column median
    X = X.fillna(X.median())

    # Drop columns that are all NaN
    X = X.dropna(axis=1, how='all')

    if len(X) < MIN_SAMPLES:
        return None, f"Insufficient clean samples: {len(X)}"

    if len(X.columns) < MIN_INDICATORS:
        return None, f"Insufficient clean features: {len(X.columns)}"

    # Bootstrap SHAP (sequential within case, cases parallelized outside)
    start_time = time.time()

    results = []
    for seed in range(n_bootstrap):
        result = _single_bootstrap(X, y, seed)
        results.append(result)

    shap_matrix = np.array(results)

    # Aggregate
    shap_mean = shap_matrix.mean(axis=0)
    shap_std = shap_matrix.std(axis=0)
    shap_ci_lower = np.percentile(shap_matrix, 2.5, axis=0)
    shap_ci_upper = np.percentile(shap_matrix, 97.5, axis=0)

    # Normalize so max = 1.0
    max_importance = shap_mean.max()
    if max_importance > 0:
        shap_mean_norm = shap_mean / max_importance
        shap_std_norm = shap_std / max_importance
        shap_ci_lower_norm = shap_ci_lower / max_importance
        shap_ci_upper_norm = shap_ci_upper / max_importance
    else:
        shap_mean_norm = shap_mean
        shap_std_norm = shap_std
        shap_ci_lower_norm = shap_ci_lower
        shap_ci_upper_norm = shap_ci_upper

    # Build result
    shap_importance = {}
    for i, col in enumerate(X.columns):
        shap_importance[col] = {
            'mean': float(shap_mean_norm[i]),
            'ci_lower': float(shap_ci_lower_norm[i]),
            'ci_upper': float(shap_ci_upper_norm[i]),
            'std': float(shap_std_norm[i])
        }

    computation_time = time.time() - start_time

    result = {
        'shap_importance': shap_importance,
        'target_quality': domain_quality,
        'metadata': {
            'n_samples': len(X),
            'n_indicators': len(X.columns),
            'n_bootstrap': n_bootstrap,
            'n_domains': len(domain_aggregates),
            'domains_included': list(domain_aggregates.keys()),
            'composite_target_mean': float(np.mean(y)),
            'year_range': [int(subset['year'].min()), int(year)],
            'computation_time_sec': round(computation_time, 2)
        },
        'data_quality': {
            'mean_ci_width': float(np.mean(shap_ci_upper_norm - shap_ci_lower_norm)),
            'median_ci_width': float(np.median(shap_ci_upper_norm - shap_ci_lower_norm)),
            'max_ci_width': float(np.max(shap_ci_upper_norm - shap_ci_lower_norm)),
        }
    }

    return result, computation_time


def process_case(args):
    """Process a single case (for parallel execution)."""
    entity, year, data, domains, indicator_directions, output_dir, is_unified, n_bootstrap = args

    # Data is already pre-filtered by main process
    entity_name = "global" if is_unified else entity

    # Check output path
    if is_unified:
        out_path = output_dir / "unified" / "quality_of_life" / f"{year}_shap.json"
    else:
        out_path = output_dir / "countries" / entity / "quality_of_life" / f"{year}_shap.json"

    if out_path.exists():
        return ('skip', entity_name, year, "Already exists")

    # Compute
    result, info = compute_qol_shap(
        data, year, domains, indicator_directions,
        n_bootstrap=n_bootstrap
    )

    if result is None:
        return ('fail', entity_name, year, info)

    # Build output
    output = {
        'country': entity_name if is_unified else entity,
        'target': 'quality_of_life',
        'target_name': 'Overall Quality of Life',
        'year': year,
        'shap_importance': result['shap_importance'],
        'target_quality': result['target_quality'],
        'metadata': result['metadata'],
        'data_quality': result['data_quality'],
        'provenance': {
            'computation_date': datetime.now().isoformat(),
            'code_version': 'v3.1.0-qol-single-model',
            'model': 'LGBMRegressor',
            'hyperparameters': MODEL_PARAMS,
            'methodology': 'Single model predicting composite QoL from 9 domain aggregates',
            'warnings': []
        }
    }

    # Save
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, 'w') as f:
        json.dump(output, f, indent=2)

    return ('success', entity_name, year, info)


def main():
    parser = argparse.ArgumentParser(description='Quality of Life SHAP (Single Model)')
    parser.add_argument('--test', action='store_true', help='Run test with 3 cases')
    parser.add_argument('--unified-only', action='store_true', help='Only compute unified (global pooled)')
    parser.add_argument('--countries-only', action='store_true', help='Only compute country-specific')
    parser.add_argument('--country', type=str, help='Single country to process')
    args = parser.parse_args()

    print("=" * 60)
    print("QUALITY OF LIFE SHAP - Single Model Approach")
    print("=" * 60)
    print(f"Bootstrap iterations: {BOOTSTRAP_SAMPLES}")
    print(f"LightGBM n_jobs: -1 (all cores)")
    print()
    print("METHODOLOGY: Composite target = mean(9 domain aggregates)")
    print("             SHAP directly measures importance to overall QoL")
    print()

    # Load data
    indicator_directions = load_indicator_directions()
    domains = load_v21_domains()

    print("\nLoading panel data...")
    panel = pd.read_parquet(PANEL_PATH)
    print(f"  Loaded {len(panel):,} rows")

    # Get canonical countries
    if CANONICAL_COUNTRIES_DIR.exists():
        countries = sorted([d.name for d in CANONICAL_COUNTRIES_DIR.iterdir() if d.is_dir()])
        print(f"  Loaded {len(countries)} canonical countries")
    else:
        countries = sorted([c for c in panel['country'].unique()
                          if not c.replace('.', '').isdigit()])
        print(f"  WARNING: Using panel countries ({len(countries)})")

    # Build case list
    cases = []

    if not args.countries_only:
        # Unified cases
        for year in YEARS:
            cases.append(('global', year, True))

    if not args.unified_only:
        # Country cases
        if args.country:
            if args.country in countries:
                countries = [args.country]
            else:
                print(f"ERROR: Country '{args.country}' not found")
                return

        for country in countries:
            for year in YEARS:
                cases.append((country, year, False))

    if args.test:
        cases = cases[:3]
        print(f"\nTEST MODE: Running {len(cases)} cases")
    else:
        print(f"\nTotal cases: {len(cases)}")

    # Check existing
    existing = 0
    for entity, year, is_unified in cases:
        if is_unified:
            path = OUTPUT_DIR / "unified" / "quality_of_life" / f"{year}_shap.json"
        else:
            path = OUTPUT_DIR / "countries" / entity / "quality_of_life" / f"{year}_shap.json"
        if path.exists():
            existing += 1

    print(f"Already completed: {existing}")
    print(f"Remaining: {len(cases) - existing}")

    print("\n" + "-" * 60)
    print("Starting computation (sequential - LightGBM uses all cores)...")
    print("-" * 60)

    start_time = time.time()
    successes = 0
    skips = 0
    failures = 0

    # Process sequentially (LightGBM n_jobs=-1 uses all cores per model)
    for i, (entity, year, is_unified) in enumerate(cases):
        # Pre-filter data to avoid passing 18M rows
        if is_unified:
            data = panel.copy()
        else:
            data = panel[panel['country'] == entity].copy()

        # Prepare args
        case_args = (entity, year, data, domains, indicator_directions, OUTPUT_DIR,
                     is_unified, BOOTSTRAP_SAMPLES)

        try:
            status, entity_name, year_out, info = process_case(case_args)

            if status == 'success':
                successes += 1
                print(f"[{i+1}/{len(cases)}] {entity_name}/{year_out}: SUCCESS ({info:.1f}s)")
            elif status == 'skip':
                skips += 1
                print(f"[{i+1}/{len(cases)}] {entity_name}/{year_out}: SKIP")
            else:
                failures += 1
                if failures <= 10:
                    print(f"[{i+1}/{len(cases)}] {entity_name}/{year_out}: FAIL - {info}")

            # Progress checkpoint
            if (i + 1) % 5 == 0:
                elapsed = time.time() - start_time
                rate = (i + 1) / elapsed if elapsed > 0 else 0
                remaining = len(cases) - i - 1
                eta = remaining / rate / 3600 if rate > 0 else 0
                print(f"  --- Checkpoint: {i+1}/{len(cases)}, {successes} success, ETA: {eta:.1f}h ---")

        except Exception as e:
            failures += 1
            print(f"[{i+1}/{len(cases)}] ERROR: {e}")

    elapsed = time.time() - start_time

    print("\n" + "=" * 60)
    print("COMPLETE")
    print("=" * 60)
    print(f"Time: {elapsed/60:.1f} minutes ({elapsed/3600:.2f} hours)")
    print(f"Success: {successes}, Skip: {skips}, Fail: {failures}")
    print(f"Output: {OUTPUT_DIR}")


if __name__ == '__main__':
    main()
