#!/usr/bin/env python3
"""
V2.1 Methodology Feasibility Test for V3.1

Tests if we can run V2.1's multi-dimensional SHAP methodology for temporal analysis.
Checks data availability, computes sample SHAP, estimates runtime.
"""

import json
import time
import warnings
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
import shap

warnings.filterwarnings('ignore')

# === PATHS ===
PROJECT_ROOT = Path(__file__).parent.parent.parent
V21_VIZ_PATH = Path("<repo-root>/v2.1/outputs/B5/v2_1_visualization.json")
PANEL_PATH = PROJECT_ROOT / "data" / "raw" / "v21_panel_data_for_v3.parquet"
OUTPUT_PATH = PROJECT_ROOT / "data" / "v3_1_feasibility_report.json"

# === CONFIGURATION ===
SAMPLE_COUNTRIES = ["United States", "Rwanda", "China"]
SAMPLE_YEARS = [2000, 2010, 2020]
N_BOOTSTRAP = 10  # Reduced for speed test
N_JOBS = 12


def load_v21_hierarchy():
    """Load V2.1 visualization JSON and extract outcome domains."""
    print("Loading V2.1 hierarchy...")

    with open(V21_VIZ_PATH) as f:
        data = json.load(f)

    nodes = {n['id']: n for n in data['nodes']}

    # Find outcome nodes (layer 1)
    outcome_domains = {}

    for node in data['nodes']:
        if node.get('layer') == 1 and node.get('node_type') == 'outcome_category':
            outcome_id = node['id']
            outcome_name = node['label']

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

            outcome_domains[outcome_name] = {
                'id': outcome_id,
                'indicators': indicators,
                'n_indicators': len(indicators)
            }

    print(f"  Found {len(outcome_domains)} outcome domains")
    for name, info in outcome_domains.items():
        print(f"    {name}: {info['n_indicators']} indicators")

    return outcome_domains


def check_data_availability(outcome_domains, panel):
    """Check how many domain indicators exist in panel data."""
    print("\nChecking data availability...")

    panel_indicators = set(panel['indicator_id'].unique())
    panel_countries = set(panel['country'].unique())

    print(f"  Panel has {len(panel_indicators)} unique indicators")
    print(f"  Panel has {len(panel_countries)} unique countries")

    availability = {}

    for domain_name, domain_info in outcome_domains.items():
        domain_indicators = set(domain_info['indicators'])
        available = domain_indicators & panel_indicators

        availability[domain_name] = {
            'n_mapped': len(domain_indicators),
            'n_in_panel': len(available),
            'coverage': len(available) / len(domain_indicators) if domain_indicators else 0,
            'available_indicators': list(available)[:20],  # Sample
            'missing_sample': list(domain_indicators - panel_indicators)[:10]
        }

        print(f"  {domain_name}: {len(available)}/{len(domain_indicators)} ({availability[domain_name]['coverage']:.1%})")

    return availability


def compute_domain_shap(panel, domain_name, indicators, country, year):
    """Compute SHAP for one (domain, country, year) case."""

    # Filter panel data
    mask = (panel['country'] == country) & (panel['year'] <= year)
    country_data = panel[mask]

    if len(country_data) == 0:
        return None, "No data for country"

    # Pivot to wide format
    wide = country_data.pivot_table(
        index='year',
        columns='indicator_id',
        values='value',
        aggfunc='mean'
    )

    if len(wide) < 10:
        return None, f"Insufficient samples: {len(wide)}"

    # Find available domain indicators
    available_domain_inds = [i for i in indicators if i in wide.columns]

    if len(available_domain_inds) < 2:
        return None, f"Insufficient domain indicators: {len(available_domain_inds)}"

    # Create target composite from top 3 domain indicators (by data completeness)
    ind_coverage = {i: wide[i].notna().sum() for i in available_domain_inds}
    top_inds = sorted(ind_coverage.keys(), key=lambda x: ind_coverage[x], reverse=True)[:3]

    # Normalize and average
    target_parts = []
    for ind in top_inds:
        vals = wide[ind].values.astype(float)
        if np.nanstd(vals) > 0:
            normalized = (vals - np.nanmin(vals)) / (np.nanmax(vals) - np.nanmin(vals) + 1e-10)
            target_parts.append(normalized)

    if len(target_parts) < 2:
        return None, "Could not normalize enough indicators"

    y = np.nanmean(target_parts, axis=0)

    # Prepare features (all other indicators)
    feature_cols = [c for c in wide.columns if c not in indicators]
    if len(feature_cols) < 20:
        return None, f"Insufficient features: {len(feature_cols)}"

    X = wide[feature_cols].fillna(wide[feature_cols].median())
    X = X.loc[:, ~X.isna().all()]

    # Remove NaN rows
    valid_idx = ~np.isnan(y)
    X_clean = X[valid_idx].values
    y_clean = y[valid_idx]

    if len(X_clean) < 10:
        return None, f"Insufficient clean samples: {len(X_clean)}"

    # Train model and compute SHAP
    start_time = time.time()

    model = GradientBoostingRegressor(
        n_estimators=100,
        max_depth=5,
        random_state=42
    )
    model.fit(X_clean, y_clean)

    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X_clean)

    runtime = time.time() - start_time

    # Get top 5 SHAP
    mean_shap = np.mean(np.abs(shap_values), axis=0)
    top_idx = np.argsort(mean_shap)[-5:][::-1]
    top_shap = {X.columns[i]: float(mean_shap[i]) for i in top_idx}

    result = {
        'country': country,
        'year': year,
        'target_composite_valid': True,
        'n_features': len(X.columns),
        'n_samples': len(X_clean),
        'domain_indicators_used': top_inds,
        'shap_runtime_sec': round(runtime, 2),
        'top_5_shap': top_shap
    }

    return result, None


def estimate_runtime(test_results, outcome_domains):
    """Estimate full runtime based on test results."""

    # Calculate average runtime from successful tests
    runtimes = [r['sample_test']['shap_runtime_sec']
                for r in test_results
                if r['sample_test'] and r['sample_test'].get('shap_runtime_sec')]

    if not runtimes:
        return None

    avg_runtime = np.mean(runtimes)

    # Total cases
    n_domains = len(outcome_domains)
    n_countries = 166
    n_years = 26  # 1995-2020
    total_cases = n_domains * n_countries * n_years

    # Estimate success rate from coverage
    coverages = [r['coverage'] for r in test_results]
    avg_coverage = np.mean(coverages) if coverages else 0.5
    estimated_success_rate = min(avg_coverage, 0.7)  # Cap at 70%

    expected_successes = int(total_cases * estimated_success_rate)

    # Total runtime (single-threaded)
    total_sec = expected_successes * avg_runtime
    total_hours = total_sec / 3600

    # With parallelization
    cores = 16
    parallel_hours = total_hours / cores
    parallel_days = parallel_hours / 24

    return {
        'cases_total': total_cases,
        'success_rate_estimated': round(estimated_success_rate, 2),
        'cases_expected_success': expected_successes,
        'runtime_per_case_sec': round(avg_runtime, 2),
        'total_runtime_hours_single': round(total_hours, 1),
        'total_runtime_hours_parallel': round(parallel_hours, 1),
        'total_runtime_days': round(parallel_days, 2),
        'cores_assumed': cores
    }


def identify_blocking_issues(test_results):
    """Identify any blocking issues."""
    issues = []

    for result in test_results:
        domain = result['name']
        coverage = result['coverage']

        if coverage < 0.1:
            issues.append(f"{domain}: <10% indicator coverage - CRITICAL")
        elif coverage < 0.3:
            issues.append(f"{domain}: <30% indicator coverage - may need indicator remapping")

        if result.get('n_in_panel', 0) < 5:
            issues.append(f"{domain}: only {result.get('n_in_panel', 0)} indicators available")

    return issues


def generate_recommendation(test_results, runtime_estimate, issues):
    """Generate recommendation."""

    # Check for critical issues
    critical_domains = sum(1 for r in test_results if r['coverage'] < 0.1)
    low_coverage_domains = sum(1 for r in test_results if r['coverage'] < 0.3)

    if critical_domains >= 5:
        return "ABORT", [
            "More than half of domains have critical data coverage issues",
            "Need to remap indicators from V2.1 IDs to panel IDs",
            "Consider using panel-native indicator groupings instead"
        ]

    if runtime_estimate and runtime_estimate['total_runtime_days'] > 5:
        return "MODIFY", [
            f"Runtime too long: {runtime_estimate['total_runtime_days']:.1f} days",
            "Reduce bootstrap iterations",
            "Skip lowest-coverage domains",
            "Use LightGBM instead of sklearn"
        ]

    if low_coverage_domains >= 3:
        return "MODIFY", [
            f"{low_coverage_domains} domains have <30% coverage",
            "Remap indicators for low-coverage domains",
            "Consider merging similar domains"
        ]

    return "PROCEED", [
        "Data coverage acceptable",
        "Runtime within bounds",
        "Recommend using LightGBM for speed"
    ]


def main():
    print("=" * 60)
    print("V2.1 METHODOLOGY FEASIBILITY TEST")
    print("=" * 60)

    # 1. Load V2.1 hierarchy
    outcome_domains = load_v21_hierarchy()

    # 2. Load panel data
    print("\nLoading panel data...")
    panel = pd.read_parquet(PANEL_PATH)
    print(f"  Loaded {len(panel):,} rows")

    # 3. Check data availability
    availability = check_data_availability(outcome_domains, panel)

    # 4. Test SHAP computation for each domain
    print("\nTesting SHAP computation...")
    test_results = []

    for domain_name, domain_info in outcome_domains.items():
        print(f"\n  Testing {domain_name}...")

        domain_result = {
            'name': domain_name,
            'n_indicators_mapped': domain_info['n_indicators'],
            'n_in_panel': availability[domain_name]['n_in_panel'],
            'coverage': availability[domain_name]['coverage'],
            'sample_test': None,
            'error': None
        }

        # Try USA 2020 first
        for country in SAMPLE_COUNTRIES:
            for year in SAMPLE_YEARS:
                result, error = compute_domain_shap(
                    panel, domain_name,
                    availability[domain_name]['available_indicators'],
                    country, year
                )

                if result:
                    domain_result['sample_test'] = result
                    print(f"    SUCCESS: {country}/{year} - {result['shap_runtime_sec']}s, {result['n_samples']} samples")
                    break

            if domain_result['sample_test']:
                break

        if not domain_result['sample_test']:
            domain_result['error'] = error or "All test cases failed"
            print(f"    FAILED: {domain_result['error']}")

        test_results.append(domain_result)

    # 5. Estimate runtime
    print("\nEstimating runtime...")
    runtime_estimate = estimate_runtime(test_results, outcome_domains)

    if runtime_estimate:
        print(f"  Estimated total cases: {runtime_estimate['cases_total']:,}")
        print(f"  Expected success rate: {runtime_estimate['success_rate_estimated']:.0%}")
        print(f"  Runtime per case: {runtime_estimate['runtime_per_case_sec']}s")
        print(f"  Total runtime (16 cores): {runtime_estimate['total_runtime_days']:.1f} days")

    # 6. Identify blocking issues
    print("\nChecking for blocking issues...")
    issues = identify_blocking_issues(test_results)
    for issue in issues:
        print(f"  - {issue}")

    # 7. Generate recommendation
    recommendation, modifications = generate_recommendation(test_results, runtime_estimate, issues)
    print(f"\nRECOMMENDATION: {recommendation}")
    for mod in modifications:
        print(f"  - {mod}")

    # 8. Generate report
    report = {
        'generated': datetime.now().isoformat(),
        'v21_methodology_loaded': True,
        'panel_stats': {
            'total_rows': len(panel),
            'unique_indicators': len(panel['indicator_id'].unique()),
            'unique_countries': len(panel['country'].unique())
        },
        'outcome_domains': test_results,
        'estimated_runtime': runtime_estimate,
        'blocking_issues': issues,
        'recommendation': recommendation,
        'modifications_needed': modifications
    }

    # Save report
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, 'w') as f:
        json.dump(report, f, indent=2)

    print(f"\nReport saved to: {OUTPUT_PATH}")

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    successful = sum(1 for r in test_results if r['sample_test'])
    print(f"Domains tested: {len(test_results)}")
    print(f"Domains with successful SHAP: {successful}/{len(test_results)}")
    print(f"Recommendation: {recommendation}")

    return report


if __name__ == "__main__":
    main()
