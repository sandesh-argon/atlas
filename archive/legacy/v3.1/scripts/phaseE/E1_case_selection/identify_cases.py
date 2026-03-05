#!/usr/bin/env python
"""
Phase E.1: Historical Case Identification

Identifies suitable historical policy interventions for validation by finding
significant year-over-year changes in key indicators.

Criteria for good validation cases:
1. Significant change in source indicator (>10% change)
2. Sufficient downstream data available
3. Clear temporal separation (before/after)
4. Country has complete graph data
"""

import json
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple
from collections import defaultdict

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
GRAPHS_DIR = DATA_DIR / "country_graphs"
PANEL_PATH = DATA_DIR / "raw" / "v21_panel_data_for_v3.parquet"
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "phaseE"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# Key indicators for different domains (good intervention candidates)
DOMAIN_INDICATORS = {
    "governance": [
        "v2x_polyarchy",      # Electoral democracy
        "v2x_libdem",         # Liberal democracy
        "v2x_partipdem",      # Participatory democracy
        "v2xcl_rol",          # Rule of law
        "v2x_corr",           # Political corruption
    ],
    "economic": [
        "e_gdppc",            # GDP per capita
        "e_migdppc",          # GDP per capita (Maddison)
        "e_total_resources_income_pc",  # Resource income
    ],
    "health": [
        "e_pelifeex",         # Life expectancy
        "e_peinfmor",         # Infant mortality
    ],
    "education": [
        "e_peaveduc",         # Average education years
        "e_peedgini",         # Education inequality
    ],
    "social": [
        "v2pehealth",         # Health equality
        "v2clacjust",         # Access to justice
    ]
}


def load_panel_data() -> pd.DataFrame:
    """Load panel data."""
    print("Loading panel data...")
    df = pd.read_parquet(PANEL_PATH)
    print(f"  Shape: {df.shape}")
    return df


def get_countries_with_graphs() -> List[str]:
    """Get list of countries that have graph files."""
    countries = []
    for f in GRAPHS_DIR.glob("*.json"):
        if not f.name.startswith("_"):
            countries.append(f.stem)
    return sorted(countries)


def find_significant_changes(
    df: pd.DataFrame,
    indicator: str,
    min_change_pct: float = 10.0,
    min_years_before: int = 3,
    min_years_after: int = 3
) -> List[Dict]:
    """
    Find significant year-over-year changes in an indicator.

    Args:
        df: Panel data (long format)
        indicator: Indicator ID to analyze
        min_change_pct: Minimum percent change to consider significant
        min_years_before: Required years of data before change
        min_years_after: Required years of data after change

    Returns:
        List of change events with metadata
    """
    # Filter to this indicator
    ind_data = df[df['indicator_id'] == indicator].copy()
    if ind_data.empty:
        return []

    changes = []

    # Group by country
    for country, country_data in ind_data.groupby('country'):
        country_data = country_data.sort_values('year')

        if len(country_data) < min_years_before + min_years_after + 1:
            continue

        # Calculate year-over-year changes
        values = country_data.set_index('year')['value']

        for year in values.index[min_years_before:-min_years_after]:
            if year - 1 not in values.index or year not in values.index:
                continue

            before_val = values[year - 1]
            after_val = values[year]

            if before_val == 0 or pd.isna(before_val) or pd.isna(after_val):
                continue

            pct_change = ((after_val - before_val) / abs(before_val)) * 100

            if abs(pct_change) >= min_change_pct:
                # Calculate stability before and after
                pre_years = [y for y in range(year - min_years_before, year) if y in values.index]
                post_years = [y for y in range(year + 1, year + min_years_after + 1) if y in values.index]

                if len(pre_years) >= 2 and len(post_years) >= 2:
                    pre_std = values[pre_years].std()
                    post_std = values[post_years].std()

                    # Good case: stable before and after, but big change at intervention
                    changes.append({
                        'country': country,
                        'indicator': indicator,
                        'year': int(year),
                        'before_value': float(before_val),
                        'after_value': float(after_val),
                        'percent_change': float(pct_change),
                        'pre_stability': float(pre_std) if not pd.isna(pre_std) else 0,
                        'post_stability': float(post_std) if not pd.isna(post_std) else 0,
                        'years_data_before': len(pre_years),
                        'years_data_after': len(post_years)
                    })

    return changes


def score_validation_case(case: Dict, countries_with_graphs: List[str]) -> float:
    """
    Score a validation case for suitability.

    Higher score = better validation case.
    """
    score = 0.0

    # Must have graph data
    if case['country'] not in countries_with_graphs:
        return 0.0

    # Larger changes are better (up to a point)
    change_magnitude = min(abs(case['percent_change']), 100) / 100
    score += change_magnitude * 30

    # More stable before/after is better
    stability_score = 1 / (1 + case['pre_stability'] + case['post_stability'])
    score += stability_score * 20

    # More data years is better
    data_score = min(case['years_data_before'] + case['years_data_after'], 10) / 10
    score += data_score * 20

    # Recent years are better (more complete data)
    recency = max(0, (case['year'] - 1990)) / 34
    score += recency * 15

    # Not too recent (need outcome data)
    if case['year'] > 2020:
        score -= 20

    return score


def identify_validation_cases(
    df: pd.DataFrame,
    countries_with_graphs: List[str],
    n_cases_per_domain: int = 10
) -> Dict[str, List[Dict]]:
    """
    Identify best validation cases across all domains.
    """
    all_cases = defaultdict(list)

    for domain, indicators in DOMAIN_INDICATORS.items():
        print(f"\nAnalyzing {domain} domain...")
        domain_cases = []

        for indicator in indicators:
            if indicator not in df['indicator_id'].values:
                print(f"  Skipping {indicator} (not in data)")
                continue

            print(f"  Scanning {indicator}...")
            changes = find_significant_changes(df, indicator)

            for case in changes:
                case['domain'] = domain
                case['score'] = score_validation_case(case, countries_with_graphs)
                if case['score'] > 0:
                    domain_cases.append(case)

        # Sort by score and take top N
        domain_cases.sort(key=lambda x: x['score'], reverse=True)
        all_cases[domain] = domain_cases[:n_cases_per_domain]

        print(f"  Found {len(domain_cases)} potential cases, keeping top {len(all_cases[domain])}")

    return dict(all_cases)


def generate_case_report(cases: Dict[str, List[Dict]]) -> str:
    """Generate human-readable report of validation cases."""
    lines = [
        "=" * 70,
        "PHASE E: HISTORICAL VALIDATION CASES",
        "=" * 70,
        ""
    ]

    total_cases = sum(len(c) for c in cases.values())
    lines.append(f"Total cases identified: {total_cases}")
    lines.append(f"Domains covered: {len(cases)}")
    lines.append("")

    for domain, domain_cases in cases.items():
        lines.append("-" * 70)
        lines.append(f"DOMAIN: {domain.upper()} ({len(domain_cases)} cases)")
        lines.append("-" * 70)

        for i, case in enumerate(domain_cases[:5], 1):  # Show top 5
            lines.append(f"\n  Case {i}: {case['country']} ({case['year']})")
            lines.append(f"    Indicator: {case['indicator']}")
            lines.append(f"    Change: {case['percent_change']:+.1f}%")
            lines.append(f"    Before: {case['before_value']:.4f} -> After: {case['after_value']:.4f}")
            lines.append(f"    Score: {case['score']:.1f}")

        lines.append("")

    return "\n".join(lines)


def main():
    """Main entry point."""
    print("=" * 60)
    print("Phase E.1: Historical Case Identification")
    print("=" * 60)

    # Load data
    df = load_panel_data()
    countries_with_graphs = get_countries_with_graphs()
    print(f"Countries with graphs: {len(countries_with_graphs)}")

    # Identify cases
    cases = identify_validation_cases(df, countries_with_graphs, n_cases_per_domain=10)

    # Generate report
    report = generate_case_report(cases)
    print("\n" + report)

    # Save cases
    output_file = OUTPUT_DIR / "validation_cases.json"
    with open(output_file, 'w') as f:
        json.dump(cases, f, indent=2)
    print(f"\nCases saved to: {output_file}")

    # Save report
    report_file = OUTPUT_DIR / "validation_cases_report.txt"
    with open(report_file, 'w') as f:
        f.write(report)
    print(f"Report saved to: {report_file}")

    # Summary stats
    total_cases = sum(len(c) for c in cases.values())
    print(f"\n{'=' * 60}")
    print(f"Summary: {total_cases} validation cases across {len(cases)} domains")
    print("=" * 60)

    return cases


if __name__ == "__main__":
    main()
