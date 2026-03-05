"""
Precompute Regional Temporal SHAP.

Aggregates existing country-level SHAP outputs into regional SHAP outputs.

Output:
  data/v31/temporal_shap/regional/{region_key}/{target}/{year}_shap.json
  data/v31/metadata/regional_shap_coverage.json
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np

from .region_mapping import get_all_region_keys, get_countries_in_region, get_region_metadata

DATA_ROOT = Path(__file__).parent.parent / "data"
COUNTRY_SHAP_DIR = DATA_ROOT / "v31" / "temporal_shap" / "countries"
UNIFIED_SHAP_DIR = DATA_ROOT / "v31" / "temporal_shap" / "unified"
REGIONAL_SHAP_DIR = DATA_ROOT / "v31" / "temporal_shap" / "regional"
COVERAGE_REPORT_PATH = DATA_ROOT / "v31" / "metadata" / "regional_shap_coverage.json"

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


def _discover_targets() -> List[str]:
    if UNIFIED_SHAP_DIR.exists():
        targets = sorted([d.name for d in UNIFIED_SHAP_DIR.iterdir() if d.is_dir()])
        if targets:
            return targets

    if COUNTRY_SHAP_DIR.exists():
        for country_dir in sorted(COUNTRY_SHAP_DIR.iterdir()):
            if not country_dir.is_dir():
                continue
            targets = sorted([d.name for d in country_dir.iterdir() if d.is_dir()])
            if targets:
                return targets

    return ["quality_of_life"]


def _load_country_shap(country: str, target: str, year: int) -> dict | None:
    path = COUNTRY_SHAP_DIR / country / target / f"{year}_shap.json"
    if not path.exists():
        return None
    try:
        with open(path) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


def _extract_shap_mean(value) -> float | None:
    if value is None:
        return None
    if isinstance(value, dict):
        if value.get("mean") is None:
            return None
        return float(value.get("mean"))
    return float(value)


def _aggregate_shap(region_key: str, target: str, year: int) -> tuple[dict | None, List[str]]:
    countries = get_countries_in_region(region_key)
    contributors: List[str] = []

    indicator_values: Dict[str, List[float]] = defaultdict(list)
    for country in countries:
        payload = _load_country_shap(country, target, year)
        if payload is None:
            continue
        contributors.append(country)

        for indicator, value in (payload.get("shap_importance") or {}).items():
            mean_value = _extract_shap_mean(value)
            if mean_value is not None:
                indicator_values[indicator].append(mean_value)

    if len(contributors) < _required_countries_per_year(region_key):
        return None, contributors

    shap_importance = {}
    indicator_floor = min(_required_countries_per_indicator(region_key), len(contributors))
    for indicator, values in indicator_values.items():
        if len(values) < indicator_floor:
            continue
        arr = np.array(values)
        shap_importance[indicator] = {
            "mean": float(np.median(arr)),
            "std": float(np.std(arr)),
            "ci_lower": float(np.percentile(arr, 2.5)),
            "ci_upper": float(np.percentile(arr, 97.5)),
        }

    if not shap_importance:
        return None, contributors

    region_meta = get_region_metadata(region_key) or {"name": region_key}
    payload = {
        "region": region_key,
        "region_name": region_meta.get("name", region_key),
        "target": target,
        "year": year,
        "shap_importance": shap_importance,
        "metadata": {
            "n_countries": len(contributors),
            "countries_in_region": contributors,
            "n_indicators": len(shap_importance),
            "aggregation": "median",
        },
        "provenance": {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "method": "aggregate_country_shap",
            "source": "data/v31/temporal_shap/countries",
            "min_countries_per_year": _required_countries_per_year(region_key),
        },
    }
    return payload, contributors


def precompute_regional_shap() -> dict:
    REGIONAL_SHAP_DIR.mkdir(parents=True, exist_ok=True)
    COVERAGE_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)

    targets = _discover_targets()
    coverage = {
        "targets": targets,
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

        for target in targets:
            target_rows = {}
            years_written = 0

            for year in YEARS:
                payload, contributors = _aggregate_shap(region_key, target, year)
                target_rows[str(year)] = {
                    "n_countries_total": len(get_countries_in_region(region_key)),
                    "n_countries_contributing": len(contributors),
                    "n_countries_required": _required_countries_per_year(region_key),
                    "n_countries_required_per_indicator": _required_countries_per_indicator(region_key),
                    "written": payload is not None,
                    "n_indicators": len((payload or {}).get("shap_importance", {})),
                }

                if payload is None:
                    continue

                target_dir = REGIONAL_SHAP_DIR / region_key / target
                target_dir.mkdir(parents=True, exist_ok=True)
                with open(target_dir / f"{year}_shap.json", "w") as f:
                    json.dump(payload, f)

                years_written += 1
                files_written += 1

            region_rows[target] = {
                "years_written": years_written,
                "by_year": target_rows,
            }

        coverage["regions"][region_key] = region_rows

    coverage["files_written"] = files_written
    with open(COVERAGE_REPORT_PATH, "w") as f:
        json.dump(coverage, f, indent=2)

    print(f"Regional SHAP precompute complete: {files_written} files")
    print(f"Coverage report: {COVERAGE_REPORT_PATH}")
    return coverage


if __name__ == "__main__":
    precompute_regional_shap()
