"""
Precompute Regional Indicator Stats.

Builds cached regional indicator temporal stats used for standardized-to-raw
unit conversion in temporal regional simulations.

Output:
  data/v31/regional_indicator_stats/{region_key}.json
  data/v31/metadata/regional_indicator_stats_coverage.json
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from .indicator_stats import compute_regional_temporal_stats, save_regional_stats_cache
from .region_mapping import get_all_region_keys, get_countries_in_region

DATA_ROOT = Path(__file__).parent.parent / "data"
COVERAGE_REPORT_PATH = DATA_ROOT / "v31" / "metadata" / "regional_indicator_stats_coverage.json"


def precompute_regional_stats(panel_path: Optional[Path] = None) -> dict:
    COVERAGE_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)

    coverage = {
        "regions": {},
        "files_written": 0,
    }

    for region_key in get_all_region_keys():
        countries = get_countries_in_region(region_key)
        stats = compute_regional_temporal_stats(region_key, panel_path=panel_path)
        written = bool(stats)
        if written:
            save_regional_stats_cache(region_key, stats)
            coverage["files_written"] += 1

        coverage["regions"][region_key] = {
            "n_countries_total": len(countries),
            "n_indicators": len(stats),
            "written": written,
        }

    with open(COVERAGE_REPORT_PATH, "w") as f:
        json.dump(coverage, f, indent=2)

    print(f"Regional stats precompute complete: {coverage['files_written']} files")
    print(f"Coverage report: {COVERAGE_REPORT_PATH}")
    return coverage


if __name__ == "__main__":
    precompute_regional_stats()
