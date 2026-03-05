"""
Precompute Regional Temporal Graphs.

Aggregates existing country-year graphs into regional-year graphs by taking
robust medians of edge weights and uncertainty terms.

Output:
  data/v31/temporal_graphs/regional/{region_key}/{year}_graph.json
  data/v31/metadata/regional_graph_coverage.json
"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np

from .region_mapping import get_all_region_keys, get_countries_in_region, get_region_metadata

DATA_ROOT = Path(__file__).parent.parent / "data"
COUNTRY_GRAPHS_DIR = DATA_ROOT / "v31" / "temporal_graphs" / "countries"
REGIONAL_GRAPHS_DIR = DATA_ROOT / "v31" / "temporal_graphs" / "regional"
COVERAGE_REPORT_PATH = DATA_ROOT / "v31" / "metadata" / "regional_graph_coverage.json"

YEARS = list(range(1990, 2025))
MIN_COUNTRIES_PER_YEAR = 3
# Keep broad quality floor, but allow North America's 2-country membership.
REGION_MIN_COUNTRIES_PER_YEAR = {
    "north_america": 1,
}

# Edge must be supported by enough member-country graphs to be retained.
# This avoids union inflation where one-country edges dominate large regions.
MIN_EDGE_COUNTRY_COVERAGE_RATIO = 0.30
MIN_EDGE_COUNTRY_COVERAGE_ABS = 2

EDGE_NUMERIC_FIELDS = [
    "beta",
    "std",
    "ci_lower",
    "ci_upper",
    "p_value",
    "r_squared",
    "n_samples",
    "n_bootstrap",
]


def _load_country_graph(country: str, year: int) -> dict | None:
    path = COUNTRY_GRAPHS_DIR / country / f"{year}_graph.json"
    if not path.exists():
        return None
    try:
        with open(path) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


def _edge_key(edge: dict) -> Tuple[str, str, int]:
    return (
        str(edge.get("source")),
        str(edge.get("target")),
        int(edge.get("lag", 0) or 0),
    )


def _required_countries_per_year(region_key: str) -> int:
    return int(REGION_MIN_COUNTRIES_PER_YEAR.get(region_key, MIN_COUNTRIES_PER_YEAR))


def _extract_marginal_effects(edge: dict) -> dict | None:
    me = edge.get("marginal_effects")
    if isinstance(me, dict):
        return me
    nonlinearity = edge.get("nonlinearity")
    if isinstance(nonlinearity, dict) and isinstance(nonlinearity.get("marginal_effects"), dict):
        return nonlinearity.get("marginal_effects")
    return None


def _median_dict(values: List[dict]) -> dict:
    merged: Dict[str, List[float]] = defaultdict(list)
    for row in values:
        for key, val in row.items():
            if val is not None:
                try:
                    merged[key].append(float(val))
                except (TypeError, ValueError):
                    continue
    return {k: float(np.median(vs)) for k, vs in merged.items() if vs}


def _aggregate_nonlinearity(edges: List[dict], fallback_marginal_effects: dict | None = None) -> dict | None:
    blocks = [e.get("nonlinearity") for e in edges if isinstance(e.get("nonlinearity"), dict)]
    if not blocks and fallback_marginal_effects is None:
        return None

    detected_votes = [bool(b.get("detected")) for b in blocks if b.get("detected") is not None]
    detected = (sum(detected_votes) >= math.ceil(len(detected_votes) / 2)) if detected_votes else bool(fallback_marginal_effects)

    types = [b.get("type") for b in blocks if b.get("type")]
    nonlinearity_type = max(set(types), key=types.count) if types else ("nonlinear" if detected else "linear")

    out: dict = {
        "type": nonlinearity_type,
        "detected": detected,
    }

    numeric_fields = [
        "r2_linear",
        "r2_nonlinear",
        "improvement",
        "aic_linear",
        "aic_nonlinear",
        "aic_improvement",
        "ceiling",
        "saturation_point",
        "vertex_x",
        "threshold",
    ]
    for field in numeric_fields:
        vals = []
        for block in blocks:
            value = block.get(field)
            if value is None:
                continue
            try:
                vals.append(float(value))
            except (TypeError, ValueError):
                continue
        if vals:
            out[field] = float(np.median(vals))

    models_tested = []
    for block in blocks:
        mt = block.get("models_tested")
        if isinstance(mt, list):
            models_tested.extend([m for m in mt if m])
    if models_tested:
        out["models_tested"] = sorted(set(models_tested))

    shapes = [b.get("shape") for b in blocks if b.get("shape")]
    if shapes:
        out["shape"] = max(set(shapes), key=shapes.count)

    interpretations = [b.get("interpretation") for b in blocks if b.get("interpretation")]
    if interpretations:
        out["interpretation"] = max(set(interpretations), key=interpretations.count)

    params = [b.get("params") for b in blocks if isinstance(b.get("params"), dict)]
    if params:
        out["params"] = _median_dict(params)

    marginal_effects = []
    for block in blocks:
        me = block.get("marginal_effects")
        if isinstance(me, dict):
            marginal_effects.append(me)
    if not marginal_effects and fallback_marginal_effects:
        marginal_effects = [fallback_marginal_effects]
    if marginal_effects:
        out["marginal_effects"] = _median_dict(marginal_effects)

    return out


def _aggregate_edges(
    edge_groups: Dict[Tuple[str, str, int], Dict[str, dict]],
    n_contributing_countries: int,
) -> tuple[List[dict], dict]:
    out: List[dict] = []
    total_edge_keys = len(edge_groups)
    dropped_below_coverage = 0
    kept_edges_with_marginal_effects = 0
    kept_edges_with_nonlinearity = 0

    required_edge_countries = max(
        1,
        min(
            n_contributing_countries,
            max(MIN_EDGE_COUNTRY_COVERAGE_ABS, math.ceil(n_contributing_countries * MIN_EDGE_COUNTRY_COVERAGE_RATIO)),
        ),
    )

    for (source, target, lag), country_edges in edge_groups.items():
        edges = list(country_edges.values())
        if not edges:
            continue
        if len(edges) < required_edge_countries:
            dropped_below_coverage += 1
            continue

        row = {
            "source": source,
            "target": target,
            "lag": lag,
            "n_countries_support": len(edges),
        }

        for field in EDGE_NUMERIC_FIELDS:
            values = [e.get(field) for e in edges if e.get(field) is not None]
            if not values:
                continue
            row[field] = float(np.median(values))

        # Relationship type: most common value
        relationship_types = [e.get("relationship_type") for e in edges if e.get("relationship_type")]
        if relationship_types:
            row["relationship_type"] = max(set(relationship_types), key=relationship_types.count)

        # Aggregate marginal effects from either top-level schema or nonlinearity block.
        marginal_effects = [_extract_marginal_effects(e) for e in edges]
        marginal_effects = [me for me in marginal_effects if isinstance(me, dict)]
        if marginal_effects:
            row["marginal_effects"] = _median_dict(marginal_effects)
            kept_edges_with_marginal_effects += 1

        nonlinearity = _aggregate_nonlinearity(edges, row.get("marginal_effects"))
        if nonlinearity:
            row["nonlinearity"] = nonlinearity
            kept_edges_with_nonlinearity += 1

        # Keep nonlinearity metadata from first valid edge for schema compatibility.
        for e in edges:
            if e.get("nonlinearity_metadata"):
                row["nonlinearity_metadata"] = e["nonlinearity_metadata"]
                break

        out.append(row)

    stats = {
        "total_edge_keys": total_edge_keys,
        "required_edge_countries": required_edge_countries,
        "dropped_below_coverage": dropped_below_coverage,
        "kept_edge_keys": len(out),
        "kept_with_marginal_effects": kept_edges_with_marginal_effects,
        "kept_with_nonlinearity": kept_edges_with_nonlinearity,
    }
    return out, stats


def _aggregate_saturation_thresholds(graphs: List[dict]) -> Dict[str, float]:
    merged: Dict[str, List[float]] = defaultdict(list)
    for graph in graphs:
        thresholds = graph.get("saturation_thresholds") or {}
        for indicator, value in thresholds.items():
            if value is not None:
                merged[indicator].append(float(value))
    return {indicator: float(np.median(values)) for indicator, values in merged.items() if values}


def _build_regional_graph(region_key: str, year: int) -> tuple[dict | None, List[str], dict]:
    countries = get_countries_in_region(region_key)
    contributing: List[str] = []
    graphs: List[dict] = []

    for country in countries:
        graph = _load_country_graph(country, year)
        if graph is None:
            continue
        contributing.append(country)
        graphs.append(graph)

    min_countries_required = _required_countries_per_year(region_key)
    if len(contributing) < min_countries_required:
        return None, contributing, {
            "required_countries": min_countries_required,
            "total_edge_keys": 0,
            "required_edge_countries": 0,
            "dropped_below_coverage": 0,
            "kept_edge_keys": 0,
            "kept_with_marginal_effects": 0,
            "kept_with_nonlinearity": 0,
        }

    edge_groups: Dict[Tuple[str, str, int], Dict[str, dict]] = defaultdict(dict)
    for country, graph in zip(contributing, graphs):
        for edge in graph.get("edges", []):
            key = _edge_key(edge)
            # Keep one edge per country per key (deterministic, first-write-wins).
            edge_groups[key].setdefault(country, edge)

    edges, edge_stats = _aggregate_edges(edge_groups, len(contributing))
    saturation_thresholds = _aggregate_saturation_thresholds(graphs)
    region_meta = get_region_metadata(region_key) or {"name": region_key}

    payload = {
        "year": year,
        "region": region_key,
        "region_name": region_meta.get("name", region_key),
        "edges": edges,
        "saturation_thresholds": saturation_thresholds,
        "metadata": {
            "view": "regional",
            "n_edges": len(edges),
            "n_countries": len(contributing),
            "countries_in_region": contributing,
            "n_source_graphs": len(graphs),
            "aggregation": "median",
            "edge_coverage": {
                "required_countries": edge_stats["required_edge_countries"],
                "dropped_below_coverage": edge_stats["dropped_below_coverage"],
                "kept_edge_keys": edge_stats["kept_edge_keys"],
                "total_edge_keys": edge_stats["total_edge_keys"],
            },
        },
        "provenance": {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "method": "aggregate_country_graphs",
            "source": "data/v31/temporal_graphs/countries",
            "min_countries_per_year": min_countries_required,
            "min_edge_country_coverage_ratio": MIN_EDGE_COUNTRY_COVERAGE_RATIO,
            "min_edge_country_coverage_abs": MIN_EDGE_COUNTRY_COVERAGE_ABS,
        },
    }
    edge_stats["required_countries"] = min_countries_required
    return payload, contributing, edge_stats


def precompute_regional_graphs() -> dict:
    REGIONAL_GRAPHS_DIR.mkdir(parents=True, exist_ok=True)
    COVERAGE_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)

    coverage = {
        "years": YEARS,
        "min_countries_per_year": MIN_COUNTRIES_PER_YEAR,
        "region_min_countries_per_year": REGION_MIN_COUNTRIES_PER_YEAR,
        "min_edge_country_coverage_ratio": MIN_EDGE_COUNTRY_COVERAGE_RATIO,
        "min_edge_country_coverage_abs": MIN_EDGE_COUNTRY_COVERAGE_ABS,
        "regions": {},
    }
    files_written = 0

    for region_key in get_all_region_keys():
        region_dir = REGIONAL_GRAPHS_DIR / region_key
        region_dir.mkdir(parents=True, exist_ok=True)

        rows = {}
        years_written = 0
        countries_total = len(get_countries_in_region(region_key))

        for year in YEARS:
            graph, contributors, edge_stats = _build_regional_graph(region_key, year)
            rows[str(year)] = {
                "n_countries_total": countries_total,
                "n_countries_contributing": len(contributors),
                "n_countries_required": edge_stats.get("required_countries", _required_countries_per_year(region_key)),
                "written": graph is not None,
                "n_edges": len(graph.get("edges", [])) if graph else 0,
                "n_edge_keys_total": edge_stats.get("total_edge_keys", 0),
                "n_edge_keys_dropped_below_coverage": edge_stats.get("dropped_below_coverage", 0),
                "edge_countries_required": edge_stats.get("required_edge_countries", 0),
                "n_edges_with_marginal_effects": edge_stats.get("kept_with_marginal_effects", 0),
                "n_edges_with_nonlinearity": edge_stats.get("kept_with_nonlinearity", 0),
            }

            if graph is None:
                continue

            with open(region_dir / f"{year}_graph.json", "w") as f:
                json.dump(graph, f)
            years_written += 1
            files_written += 1

        coverage["regions"][region_key] = {
            "years_written": years_written,
            "by_year": rows,
        }

    coverage["files_written"] = files_written
    with open(COVERAGE_REPORT_PATH, "w") as f:
        json.dump(coverage, f, indent=2)

    print(f"Regional graph precompute complete: {files_written} files")
    print(f"Coverage report: {COVERAGE_REPORT_PATH}")
    return coverage


if __name__ == "__main__":
    precompute_regional_graphs()
