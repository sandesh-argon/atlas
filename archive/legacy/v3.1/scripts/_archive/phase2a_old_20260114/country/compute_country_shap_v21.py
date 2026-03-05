#!/usr/bin/env python3
"""
Phase 2A: Country-Specific Temporal SHAP using V2.1 Methodology (CORRECT)

CRITICAL: Uses ALL domain indicators as aggregate target, NOT top 5 by coverage.

V2.1 Methodology (same as unified, but per-country):
1. For each domain, get ALL indicators from V2.1 hierarchy
2. Normalize each indicator to [0, 1]
3. INVERT negative outcomes (mortality, inequality, disease) → (1 - normalized)
4. domain_score = mean(all normalized indicators)  ← THIS IS THE TARGET
5. Train LightGBM: X = all indicators, y = domain_score
6. SHAP tells us: "What predicts this domain's aggregate for THIS country?"

Output: data/v3_1_temporal_shap/countries/{country}/{domain}/{year}_shap.json

PERFORMANCE NOTE:
- Country-specific cases are FASTER than unified (~10-20s vs ~70s)
- Fewer samples per case (single country time series vs all countries pooled)
- But MANY more cases: 165 countries × 9 domains × 30 years = 44,550 cases
- Estimated total: ~150-250 hours on 12 cores (need AWS)
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
V21_HIERARCHY_PATH = Path.home() / "v2.1/outputs/B5/v2_1_visualization.json"
# Local override if exists
_LOCAL_V21 = Path("<repo-root>/v2.1/outputs/B5/v2_1_visualization.json")
if _LOCAL_V21.exists():
    V21_HIERARCHY_PATH = _LOCAL_V21
INDICATOR_PROPS_PATH = DATA_DIR / "metadata" / "indicator_properties.json"
OUTPUT_DIR = DATA_DIR / "v3_1_temporal_shap" / "countries"
# Canonical country list from temporal graphs (178 countries with full names)
CANONICAL_COUNTRIES_DIR = DATA_DIR / "v3_1_temporal_graphs" / "countries"

# === CONFIGURATION ===
MIN_YEAR = 1995
MAX_YEAR = 2024
YEARS = list(range(MIN_YEAR, MAX_YEAR + 1))

BOOTSTRAP_SAMPLES = 100
MIN_SAMPLES = 10  # Lower threshold for single country (time series)
MIN_INDICATORS = 20
MIN_DOMAIN_INDICATORS = 3  # Lower threshold for country-specific
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

# Checkpoint frequency
CHECKPOINT_EVERY = 100


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


def compute_country_domain(country_data, country, domain_key, domain_info, year,
                           panel_indicators, indicator_directions):
    """
    Compute country-specific SHAP for one (country, domain, year) case.

    CORRECT V2.1 METHODOLOGY:
    - Target = aggregate of ALL domain indicators (not top 5)
    - Negative outcomes are inverted
    """

    out_dir = OUTPUT_DIR / country / domain_key
    out_path = out_dir / f"{year}_shap.json"

    # Skip if exists
    if out_path.exists():
        return 'skip', country, domain_key, year, None

    domain_name = domain_info['name']
    domain_indicators = domain_info['indicators'] & panel_indicators

    if len(domain_indicators) < MIN_DOMAIN_INDICATORS:
        return 'fail', country, domain_key, year, f"Insufficient domain indicators: {len(domain_indicators)}"

    # Filter data up to year for this country
    mask = country_data['year'] <= year
    data = country_data[mask]

    if len(data) == 0:
        return 'fail', country, domain_key, year, "No data"

    # Pivot to wide format (year as index for single country)
    wide = data.pivot_table(
        index='year',
        columns='indicator_id',
        values='value',
        aggfunc='mean'
    )

    if len(wide) < MIN_SAMPLES:
        return 'fail', country, domain_key, year, f"Insufficient samples: {len(wide)}"

    # Find available domain indicators in this data
    available_domain = [i for i in domain_indicators if i in wide.columns]

    if len(available_domain) < MIN_DOMAIN_INDICATORS:
        return 'fail', country, domain_key, year, f"Insufficient available domain indicators: {len(available_domain)}"

    # =========================================================================
    # CORRECT V2.1: Use ALL domain indicators as aggregate target
    # =========================================================================
    target_parts = []
    target_quality = {}
    n_inverted = 0

    for ind in available_domain:
        vals = wide[ind].values.astype(float)
        non_nan = np.sum(~np.isnan(vals))

        # Skip if insufficient data (lower threshold for country-specific)
        if non_nan < 3:
            continue

        min_val, max_val = np.nanmin(vals), np.nanmax(vals)
        if max_val <= min_val:
            continue  # No variation

        # Normalize to [0, 1]
        normalized = (vals - min_val) / (max_val - min_val)

        # INVERT negative outcomes (mortality, inequality, disease)
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
        return 'fail', country, domain_key, year, f"Could not create target: {len(target_parts)} valid indicators"

    # Domain aggregate = mean of ALL normalized (and inverted) indicators
    y = np.nanmean(target_parts, axis=0)

    # =========================================================================
    # Features = ALL indicators
    # =========================================================================
    feature_cols = list(wide.columns)

    if len(feature_cols) < MIN_INDICATORS:
        return 'fail', country, domain_key, year, f"Insufficient features: {len(feature_cols)}"

    X = wide[feature_cols].fillna(wide[feature_cols].median())
    X = X.loc[:, ~X.isna().all()]

    if len(X.columns) < MIN_INDICATORS:
        return 'fail', country, domain_key, year, f"Insufficient valid features: {len(X.columns)}"

    # Remove rows with NaN in target
    valid_idx = ~np.isnan(y)
    X_clean = X[valid_idx].values
    y_clean = y[valid_idx]
    feature_names = list(X.columns)

    if len(X_clean) < MIN_SAMPLES:
        return 'fail', country, domain_key, year, f"Insufficient clean samples: {len(X_clean)}"

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

    # Build warnings
    warnings_list = []
    if len(X_clean) < 15:
        warnings_list.append(f"Low sample size: {len(X_clean)}")
    if len(target_quality) < 10:
        warnings_list.append(f"Few target components: {len(target_quality)}")
    if np.mean(ci_widths) > 0.5:
        warnings_list.append(f"Wide CIs: mean={np.mean(ci_widths):.2f}")

    # Build result matching schema
    result = {
        'country': country,
        'target': domain_key,
        'target_name': domain_name,
        'year': year,
        'shap_importance': shap_importance,
        'target_quality': target_quality,
        'metadata': {
            'n_samples': len(X_clean),
            'n_indicators': len(feature_names),
            'n_bootstrap': BOOTSTRAP_SAMPLES,
            'mean_importance': float(mean_importance),
            'n_target_indicators': len(target_quality),
            'n_target_inverted': n_inverted,
            'target_components': list(target_quality.keys()),
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

    return 'success', country, domain_key, year, compute_time


def main():
    parser = argparse.ArgumentParser(description='Country-Specific Temporal SHAP (V2.1 Methodology)')
    parser.add_argument('--test', action='store_true', help='Test with 5 cases')
    parser.add_argument('--cores', type=int, default=12, help='Number of cores for bootstrap')
    parser.add_argument('--country', type=str, help='Process specific country only')
    parser.add_argument('--domain', type=str, help='Process specific domain only')
    parser.add_argument('--resume', action='store_true', help='Resume from checkpoint')
    args = parser.parse_args()

    global N_JOBS
    N_JOBS = args.cores

    print("=" * 60)
    print("COUNTRY-SPECIFIC TEMPORAL SHAP - V2.1 Methodology (CORRECT)")
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

    # Filter domain if specified
    if args.domain:
        if args.domain in domains:
            domains = {args.domain: domains[args.domain]}
        else:
            print(f"ERROR: Domain '{args.domain}' not found")
            print(f"Available: {list(domains.keys())}")
            return

    # Load panel data
    print("\nLoading panel data...")
    panel = pd.read_parquet(PANEL_PATH)
    panel_indicators = set(panel['indicator_id'].unique())
    print(f"  Loaded {len(panel):,} rows, {len(panel_indicators)} indicators")

    # Get canonical country list from temporal graphs (178 countries)
    # This ensures consistency with Phase 2B output
    if CANONICAL_COUNTRIES_DIR.exists():
        all_countries = sorted([d.name for d in CANONICAL_COUNTRIES_DIR.iterdir() if d.is_dir()])
        print(f"  Loaded {len(all_countries)} canonical countries from temporal graphs")
    else:
        # Fallback: filter panel data (less reliable)
        raw_countries = panel['country'].unique()
        all_countries = sorted([c for c in raw_countries if not c.replace('.', '').isdigit()])
        print(f"  WARNING: Using panel countries ({len(all_countries)}) - canonical list not found")

    # Filter country if specified
    if args.country:
        if args.country in all_countries:
            all_countries = [args.country]
        else:
            print(f"ERROR: Country '{args.country}' not found")
            return

    # Build case list: (country, domain, year)
    cases = []
    for country in all_countries:
        for domain_key in domains.keys():
            for year in YEARS:
                cases.append((country, domain_key, year))

    if args.test:
        cases = cases[:5]
        print(f"\nTEST MODE: Running {len(cases)} cases")
    else:
        print(f"\nTotal cases: {len(cases)} ({len(all_countries)} countries × {len(domains)} domains × {len(YEARS)} years)")

    # Check existing
    existing = sum(1 for c, d, y in cases
                   if (OUTPUT_DIR / c / d / f"{y}_shap.json").exists())
    print(f"Already completed: {existing}")
    print(f"Remaining: {len(cases) - existing}")

    print("\n" + "-" * 60)
    print("Starting computation...")
    print("-" * 60)

    start_time = time.time()
    successes = 0
    skips = 0
    failures = 0

    # Process countries one at a time to avoid memory issues
    # Cache current country data to avoid repeated filtering
    current_country = None
    current_country_data = None

    for i, (country, domain_key, year) in enumerate(cases):
        # Load country data only when country changes
        if country != current_country:
            current_country = country
            current_country_data = panel[panel['country'] == country]
            if i > 0 and i % 100 == 0:
                print(f"  Switched to country: {country}")

        status, c, d, y, info = compute_country_domain(
            current_country_data, country, domain_key, domains[domain_key],
            year, panel_indicators, indicator_directions
        )

        if status == 'success':
            successes += 1
            print(f"[{i+1}/{len(cases)}] {country}/{domain_key}/{year}: SUCCESS ({info:.1f}s)")
        elif status == 'skip':
            skips += 1
            # Don't print skips to reduce noise
        else:
            failures += 1
            if args.test or failures <= 10:  # Only print first 10 failures
                print(f"[{i+1}/{len(cases)}] {country}/{domain_key}/{year}: FAIL - {info}")

        # Checkpoint progress
        if (i + 1) % CHECKPOINT_EVERY == 0:
            elapsed = time.time() - start_time
            rate = (i + 1) / elapsed
            remaining = len(cases) - i - 1
            eta_sec = remaining / rate if rate > 0 else 0
            print(f"  --- Checkpoint: {i+1}/{len(cases)} done, {successes} success, ETA: {eta_sec/3600:.1f}h ---")

    total_time = time.time() - start_time

    print("\n" + "=" * 60)
    print("COMPLETE")
    print("=" * 60)
    print(f"Time: {total_time/60:.1f} minutes ({total_time/3600:.2f} hours)")
    print(f"Success: {successes}, Skip: {skips}, Fail: {failures}")
    print(f"Output: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
