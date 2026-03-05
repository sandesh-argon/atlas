"""
Precompute Stratum-Level and Unified Baselines

Generates aggregated baselines (median across member countries) for:
- Stratified: developing, emerging, advanced (per year)
- Unified: all countries (per year)

Uses existing per-country baselines from v3_1_baselines/{country}/{year}.json
and dynamic income classifications from income_classifications.json.

Usage:
    python -m simulation.precompute_strata_baselines
"""

import json
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional
from collections import defaultdict

from .income_classifier import get_countries_in_stratum

DATA_ROOT = Path(__file__).parent.parent / "data"
BASELINE_DIR = DATA_ROOT / "v31" / "baselines"

STRATA = ['developing', 'emerging', 'advanced']
YEARS = list(range(1990, 2025))


def load_country_baseline(country: str, year: int) -> Dict[str, float]:
    """Load precomputed baseline for a country/year. Returns empty dict if missing."""
    path = BASELINE_DIR / country / f"{year}.json"
    if not path.exists():
        # Try nearest year within ±2
        country_dir = BASELINE_DIR / country
        if not country_dir.exists():
            return {}
        for offset in [0, -1, 1, -2, 2]:
            alt = country_dir / f"{year + offset}.json"
            if alt.exists():
                path = alt
                break
        else:
            return {}

    try:
        with open(path) as f:
            data = json.load(f)
            return data.get("values", {})
    except (json.JSONDecodeError, IOError):
        return {}


def compute_stratum_baseline(
    stratum: str,
    year: int,
) -> Dict[str, float]:
    """
    Compute median baseline across all countries in a stratum for a given year.

    Uses median (not mean) to be robust to outliers — a single extreme GDP
    shouldn't dominate the stratum aggregate.

    Returns:
        {indicator_id: median_value}
    """
    countries = get_countries_in_stratum(stratum, year)
    if not countries:
        return {}

    # Collect all indicator values
    indicator_values: Dict[str, List[float]] = defaultdict(list)
    n_loaded = 0

    for country in countries:
        baseline = load_country_baseline(country, year)
        if baseline:
            n_loaded += 1
            for ind, val in baseline.items():
                if val is not None and not (isinstance(val, float) and np.isnan(val)):
                    indicator_values[ind].append(val)

    if n_loaded == 0:
        return {}

    # Compute median for each indicator
    result = {}
    for ind, values in indicator_values.items():
        if len(values) >= 3:  # Require at least 3 countries for a stable median
            result[ind] = float(np.median(values))

    return result


def compute_unified_baseline(year: int) -> Dict[str, float]:
    """
    Compute median baseline across ALL countries for a given year.

    Returns:
        {indicator_id: median_value}
    """
    indicator_values: Dict[str, List[float]] = defaultdict(list)
    n_loaded = 0

    # Iterate all country directories
    if not BASELINE_DIR.exists():
        return {}

    for country_dir in sorted(BASELINE_DIR.iterdir()):
        if not country_dir.is_dir():
            continue
        # Skip aggregate directories.
        if country_dir.name in ['stratified', 'unified', 'regional']:
            continue

        baseline = load_country_baseline(country_dir.name, year)
        if baseline:
            n_loaded += 1
            for ind, val in baseline.items():
                if val is not None and not (isinstance(val, float) and np.isnan(val)):
                    indicator_values[ind].append(val)

    if n_loaded == 0:
        return {}

    result = {}
    for ind, values in indicator_values.items():
        if len(values) >= 5:  # Require at least 5 countries for unified median
            result[ind] = float(np.median(values))

    return result


def save_baseline(path: Path, baseline: Dict[str, float], label: str, year: int, n_countries: int):
    """Save baseline JSON in same format as country baselines."""
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "label": label,
        "year": year,
        "n_countries": n_countries,
        "n_indicators": len(baseline),
        "values": baseline,
    }
    with open(path, 'w') as f:
        json.dump(data, f)


def precompute_all():
    """Precompute all stratum and unified baselines."""
    print("Precomputing stratum and unified baselines...")
    print(f"  Source: {BASELINE_DIR}")
    print(f"  Years: {YEARS[0]}-{YEARS[-1]}")
    print()

    # Stratified baselines
    for stratum in STRATA:
        out_dir = BASELINE_DIR / "stratified" / stratum
        out_dir.mkdir(parents=True, exist_ok=True)
        n_years = 0

        for year in YEARS:
            countries = get_countries_in_stratum(stratum, year)
            baseline = compute_stratum_baseline(stratum, year)
            if baseline:
                save_baseline(
                    out_dir / f"{year}.json",
                    baseline,
                    label=f"{stratum.title()} Countries ({len(countries)} members)",
                    year=year,
                    n_countries=len(countries),
                )
                n_years += 1

        print(f"  {stratum}: {n_years} years, saved to {out_dir}")

    # Unified baselines
    out_dir = BASELINE_DIR / "unified"
    out_dir.mkdir(parents=True, exist_ok=True)
    n_years = 0

    for year in YEARS:
        baseline = compute_unified_baseline(year)
        if baseline:
            save_baseline(
                out_dir / f"{year}.json",
                baseline,
                label=f"Global Median (all countries)",
                year=year,
                n_countries=0,  # will be filled in
            )
            n_years += 1

    print(f"  unified: {n_years} years, saved to {out_dir}")
    print("\nDone.")


if __name__ == "__main__":
    precompute_all()
