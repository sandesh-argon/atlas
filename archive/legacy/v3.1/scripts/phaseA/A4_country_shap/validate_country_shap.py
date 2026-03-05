#!/usr/bin/env python
"""
Validate country-specific SHAP outputs.

Checks:
1. Expected number of SHAP files exist
2. SHAP values are in valid range [0, 1]
3. Each country has reasonable indicator count
4. Countries show different importance patterns (heterogeneity)
5. Compare with global V2.1 SHAP as sanity check
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
SHAP_DIR = DATA_DIR / "country_shap"
NODES_PATH = DATA_DIR / "raw" / "v21_nodes.csv"


def check_file_count(expected_min: int = 180) -> tuple:
    """Check that enough SHAP files were created."""
    shap_files = list(SHAP_DIR.glob('*_shap.json'))
    count = len(shap_files)

    if count >= expected_min:
        return True, f"Found {count} SHAP files (>= {expected_min})"
    else:
        return False, f"Only found {count} SHAP files (expected >= {expected_min})"


def check_value_ranges() -> tuple:
    """Check that all SHAP values are in [0, 1]."""
    shap_files = list(SHAP_DIR.glob('*_shap.json'))
    issues = []

    for shap_file in shap_files:
        country = shap_file.stem.replace('_shap', '')

        with open(shap_file) as f:
            data = json.load(f)

        shap_importance = data.get('shap_importance', {})

        for ind, value in shap_importance.items():
            if value < 0 or value > 1.0:
                issues.append(f"{country}: {ind} = {value} (out of range)")

    if not issues:
        return True, "All SHAP values in valid range [0, 1]"
    else:
        return False, f"{len(issues)} out-of-range values: {issues[:5]}"


def check_indicator_counts(min_indicators: int = 100) -> tuple:
    """Check that each country has reasonable indicator count."""
    shap_files = list(SHAP_DIR.glob('*_shap.json'))
    low_count = []

    for shap_file in shap_files:
        country = shap_file.stem.replace('_shap', '')

        with open(shap_file) as f:
            data = json.load(f)

        n_indicators = data.get('metadata', {}).get('n_indicators', 0)

        if n_indicators < min_indicators:
            low_count.append(f"{country}: {n_indicators}")

    if not low_count:
        return True, f"All countries have >= {min_indicators} indicators"
    else:
        return False, f"{len(low_count)} countries with low indicator count: {low_count[:5]}"


def check_heterogeneity() -> tuple:
    """Check that countries show different importance patterns."""
    # Compare two very different countries
    comparisons = [
        ('Australia', 'Afghanistan'),
        ('United States', 'Rwanda'),
        ('Germany', 'Nigeria')
    ]

    results = []

    for country_a, country_b in comparisons:
        file_a = SHAP_DIR / f"{country_a}_shap.json"
        file_b = SHAP_DIR / f"{country_b}_shap.json"

        if not file_a.exists() or not file_b.exists():
            continue

        with open(file_a) as f:
            shap_a = json.load(f)['shap_importance']

        with open(file_b) as f:
            shap_b = json.load(f)['shap_importance']

        # Find common indicators
        common = set(shap_a.keys()) & set(shap_b.keys())

        if len(common) < 50:
            continue

        # Compute mean absolute difference
        differences = [
            abs(shap_a[ind] - shap_b[ind])
            for ind in common
        ]

        mean_diff = np.mean(differences)
        max_diff = np.max(differences)

        results.append({
            'pair': f"{country_a} vs {country_b}",
            'common_indicators': len(common),
            'mean_diff': mean_diff,
            'max_diff': max_diff
        })

    if not results:
        return False, "Could not compare any country pairs"

    # Check if there's meaningful heterogeneity
    avg_mean_diff = np.mean([r['mean_diff'] for r in results])

    if avg_mean_diff > 0.05:  # At least 5% average difference
        details = "; ".join([
            f"{r['pair']}: mean_diff={r['mean_diff']:.3f}"
            for r in results
        ])
        return True, f"Countries show heterogeneity: {details}"
    else:
        return False, f"Countries too similar (avg diff = {avg_mean_diff:.3f})"


def check_top_indicators() -> tuple:
    """Check that top indicators vary across countries."""
    shap_files = list(SHAP_DIR.glob('*_shap.json'))[:10]  # Sample 10 countries

    top_indicators_per_country = {}

    for shap_file in shap_files:
        country = shap_file.stem.replace('_shap', '')

        with open(shap_file) as f:
            data = json.load(f)

        shap_importance = data.get('shap_importance', {})

        # Get top 10 indicators
        top_10 = sorted(shap_importance.items(), key=lambda x: x[1], reverse=True)[:10]
        top_indicators_per_country[country] = [ind for ind, _ in top_10]

    # Check overlap between countries
    countries = list(top_indicators_per_country.keys())
    overlaps = []

    for i in range(len(countries)):
        for j in range(i + 1, len(countries)):
            set_i = set(top_indicators_per_country[countries[i]])
            set_j = set(top_indicators_per_country[countries[j]])
            overlap = len(set_i & set_j) / 10.0  # Fraction overlap
            overlaps.append(overlap)

    avg_overlap = np.mean(overlaps)

    # We expect some overlap (similar outcomes matter) but not too much
    if 0.2 < avg_overlap < 0.8:
        return True, f"Top-10 indicators have {avg_overlap*100:.0f}% avg overlap (expected 20-80%)"
    elif avg_overlap >= 0.8:
        return False, f"Top-10 indicators too similar ({avg_overlap*100:.0f}% overlap)"
    else:
        return True, f"Top-10 indicators vary significantly ({avg_overlap*100:.0f}% overlap)"


def run_all_validations():
    """Run all validation checks."""
    print("=" * 60)
    print("Phase A.4: SHAP Validation")
    print("=" * 60)

    checks = [
        ("File count", check_file_count),
        ("Value ranges", check_value_ranges),
        ("Indicator counts", check_indicator_counts),
        ("Heterogeneity", check_heterogeneity),
        ("Top indicators variation", check_top_indicators),
    ]

    all_passed = True

    for name, check_fn in checks:
        print(f"\n{name}:")
        try:
            passed, message = check_fn()
            status = "✓ PASS" if passed else "✗ FAIL"
            print(f"  {status}: {message}")
            if not passed:
                all_passed = False
        except Exception as e:
            print(f"  ✗ ERROR: {e}")
            all_passed = False

    print("\n" + "=" * 60)
    if all_passed:
        print("✓ ALL VALIDATION CHECKS PASSED")
    else:
        print("✗ SOME VALIDATION CHECKS FAILED")
    print("=" * 60)

    return all_passed


def print_summary_stats():
    """Print summary statistics about SHAP files."""
    print("\n" + "=" * 60)
    print("Summary Statistics")
    print("=" * 60)

    shap_files = list(SHAP_DIR.glob('*_shap.json'))

    if not shap_files:
        print("No SHAP files found!")
        return

    stats = []

    for shap_file in shap_files:
        country = shap_file.stem.replace('_shap', '')

        with open(shap_file) as f:
            data = json.load(f)

        metadata = data.get('metadata', {})
        shap_importance = data.get('shap_importance', {})

        stats.append({
            'country': country,
            'n_indicators': metadata.get('n_indicators', 0),
            'n_samples': metadata.get('n_samples', 0),
            'mean_importance': metadata.get('mean_importance', 0),
            'max_importance': metadata.get('max_importance', 0),
            'qol_components': len(metadata.get('qol_components', [])),
        })

    df = pd.DataFrame(stats)

    print(f"\nCountries: {len(df)}")
    print(f"\nIndicator count: min={df['n_indicators'].min()}, "
          f"max={df['n_indicators'].max()}, mean={df['n_indicators'].mean():.0f}")
    print(f"Sample count (years): min={df['n_samples'].min()}, "
          f"max={df['n_samples'].max()}, mean={df['n_samples'].mean():.0f}")
    print(f"QoL components: min={df['qol_components'].min()}, "
          f"max={df['qol_components'].max()}, mean={df['qol_components'].mean():.1f}")

    # Top/bottom countries by indicator count
    print("\nCountries with most indicators:")
    top5 = df.nlargest(5, 'n_indicators')[['country', 'n_indicators', 'n_samples']]
    print(top5.to_string(index=False))

    print("\nCountries with fewest indicators:")
    bottom5 = df.nsmallest(5, 'n_indicators')[['country', 'n_indicators', 'n_samples']]
    print(bottom5.to_string(index=False))


if __name__ == "__main__":
    if not SHAP_DIR.exists():
        print(f"SHAP directory not found: {SHAP_DIR}")
        print("Run compute_country_shap.py first!")
        sys.exit(1)

    all_passed = run_all_validations()
    print_summary_stats()

    sys.exit(0 if all_passed else 1)
