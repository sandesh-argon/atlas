"""
Precompute Regional Baselines.

Builds median indicator baselines for each hybrid region/year using existing
country baseline JSON files.

Output:
  data/v31/baselines/regional/{region_key}/{year}.json
  data/v31/metadata/regional_baseline_coverage.json
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Dict, List

import numpy as np

from .region_mapping import get_all_region_keys, get_countries_in_region, get_region_metadata

DATA_ROOT = Path(__file__).parent.parent / "data"
BASELINE_DIR = DATA_ROOT / "v31" / "baselines"
REGIONAL_BASELINE_DIR = BASELINE_DIR / "regional"
COVERAGE_REPORT_PATH = DATA_ROOT / "v31" / "metadata" / "regional_baseline_coverage.json"

YEARS = list(range(1990, 2025))
MIN_COUNTRIES_PER_YEAR = 3
MIN_COUNTRIES_PER_INDICATOR = 3
REGION_MIN_COUNTRIES_PER_YEAR = {
    "north_america": 1,
}
REGION_MIN_COUNTRIES_PER_INDICATOR = {
    "north_america": 1,
}


def _required_countries_per_year(region_key: str) -> int:
    return int(REGION_MIN_COUNTRIES_PER_YEAR.get(region_key, MIN_COUNTRIES_PER_YEAR))


def _required_countries_per_indicator(region_key: str) -> int:
    return int(REGION_MIN_COUNTRIES_PER_INDICATOR.get(region_key, MIN_COUNTRIES_PER_INDICATOR))


def _load_country_baseline(country: str, year: int) -> Dict[str, float]:
    path = BASELINE_DIR / country / f"{year}.json"
    if not path.exists():
        return {}
    try:
        with open(path) as f:
            payload = json.load(f)
        return payload.get("values", {})
    except (json.JSONDecodeError, IOError):
        return {}


def _compute_regional_baseline(region_key: str, year: int) -> tuple[Dict[str, float], List[str]]:
    countries = get_countries_in_region(region_key)

    indicator_values: Dict[str, List[float]] = defaultdict(list)
    contributors: List[str] = []

    for country in countries:
        baseline = _load_country_baseline(country, year)
        if not baseline:
            continue
        contributors.append(country)
        for indicator, value in baseline.items():
            if value is None:
                continue
            indicator_values[indicator].append(float(value))

    if len(contributors) < _required_countries_per_year(region_key):
        return {}, contributors

    aggregated = {}
    indicator_floor = min(_required_countries_per_indicator(region_key), len(contributors))
    for indicator, values in indicator_values.items():
        if len(values) < indicator_floor:
            continue
        aggregated[indicator] = float(np.median(values))

    return aggregated, contributors


def _save_regional_baseline(region_key: str, year: int, baseline: Dict[str, float], contributors: List[str]) -> None:
    region_dir = REGIONAL_BASELINE_DIR / region_key
    region_dir.mkdir(parents=True, exist_ok=True)

    metadata = get_region_metadata(region_key) or {"name": region_key}
    payload = {
        "label": metadata.get("name", region_key),
        "region": region_key,
        "year": year,
        "n_countries": len(contributors),
        "countries_in_region": contributors,
        "n_indicators": len(baseline),
        "values": baseline,
    }

    with open(region_dir / f"{year}.json", "w") as f:
        json.dump(payload, f)


def precompute_regional_baselines() -> dict:
    REGIONAL_BASELINE_DIR.mkdir(parents=True, exist_ok=True)
    COVERAGE_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)

    coverage = {
        "years": YEARS,
        "min_countries_per_year": MIN_COUNTRIES_PER_YEAR,
        "region_min_countries_per_year": REGION_MIN_COUNTRIES_PER_YEAR,
        "min_countries_per_indicator": MIN_COUNTRIES_PER_INDICATOR,
        "region_min_countries_per_indicator": REGION_MIN_COUNTRIES_PER_INDICATOR,
        "regions": {},
    }
    files_written = 0

    for region_key in get_all_region_keys():
        region_rows = {}
        years_written = 0

        for year in YEARS:
            baseline, contributors = _compute_regional_baseline(region_key, year)

            region_rows[str(year)] = {
                "n_countries_total": len(get_countries_in_region(region_key)),
                "n_countries_contributing": len(contributors),
                "n_countries_required": _required_countries_per_year(region_key),
                "n_countries_required_per_indicator": _required_countries_per_indicator(region_key),
                "n_indicators": len(baseline),
                "written": bool(baseline),
            }

            if not baseline:
                continue

            _save_regional_baseline(region_key, year, baseline, contributors)
            years_written += 1
            files_written += 1

        coverage["regions"][region_key] = {
            "years_written": years_written,
            "by_year": region_rows,
        }

    coverage["files_written"] = files_written
    with open(COVERAGE_REPORT_PATH, "w") as f:
        json.dump(coverage, f, indent=2)

    print(f"Regional baseline precompute complete: {files_written} files")
    print(f"Coverage report: {COVERAGE_REPORT_PATH}")
    return coverage


if __name__ == "__main__":
    precompute_regional_baselines()
