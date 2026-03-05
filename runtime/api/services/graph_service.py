"""
Graph Service

Handles loading and caching of country graphs from V3.1 temporal data.
"""

import json
import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional
from functools import lru_cache
from collections import OrderedDict

from ..config import (
    GRAPHS_DIR, PANEL_PATH, COUNTRY_SHAP_DIR,
    DEFAULT_GRAPH_YEAR, V31_TEMPORAL_SHAP_DIR, V31_BASELINES_DIR,
    V31_TEMPORAL_GRAPHS_DIR,
    GRAPH_SERVICE_GRAPH_CACHE_MAX, GRAPH_SERVICE_SHAP_CACHE_MAX
)


class GraphService:
    """Service for loading country graphs and baseline data from V3.1."""

    def __init__(self):
        self._graph_cache: "OrderedDict[str, dict]" = OrderedDict()
        self._shap_cache: "OrderedDict[str, Dict[str, float]]" = OrderedDict()
        self._panel_df: Optional[pd.DataFrame] = None
        self._countries: Optional[List[str]] = None
        self._graph_cache_max = GRAPH_SERVICE_GRAPH_CACHE_MAX
        self._shap_cache_max = GRAPH_SERVICE_SHAP_CACHE_MAX

    @staticmethod
    def _cache_get(cache: "OrderedDict[str, dict]", key: str):
        value = cache.get(key)
        if value is not None:
            cache.move_to_end(key)
        return value

    @staticmethod
    def _cache_set(cache: "OrderedDict[str, dict]", key: str, value: dict, max_entries: int):
        cache[key] = value
        cache.move_to_end(key)
        while len(cache) > max_entries:
            cache.popitem(last=False)

    def _get_latest_year_for_country(self, country: str) -> Optional[int]:
        """Find the latest available year for a country's graph."""
        country_dir = GRAPHS_DIR / country
        if not country_dir.exists():
            return None

        years = []
        for graph_file in country_dir.glob("*_graph.json"):
            try:
                year = int(graph_file.stem.split("_")[0])
                years.append(year)
            except ValueError:
                continue

        return max(years) if years else None

    def _convert_v31_edge(self, edge: dict) -> dict:
        """Convert V3.1 edge format to API format expected by frontend."""
        return {
            "source": edge.get("source"),
            "target": edge.get("target"),
            "beta": edge.get("beta", 0),
            "ci_lower": edge.get("ci_lower", 0),
            "ci_upper": edge.get("ci_upper", 0),
            "global_beta": edge.get("beta", 0),  # V3.1 doesn't have separate global_beta
            "data_available": True,  # All V3.1 edges have data
            "lag": edge.get("lag", 0),
            "lag_pvalue": edge.get("p_value", 1.0),
            "lag_significant": edge.get("p_value", 1.0) < 0.05,
            # Additional V3.1 fields
            "p_value": edge.get("p_value"),
            "r_squared": edge.get("r_squared"),
            "n_samples": edge.get("n_samples"),
            "relationship_type": edge.get("relationship_type"),
            "nonlinearity": edge.get("nonlinearity")
        }

    def get_available_countries(self) -> List[dict]:
        """Get list of all countries with graph metadata."""
        if self._countries is None:
            self._countries = []

            if not GRAPHS_DIR.exists():
                return self._countries

            for country_dir in GRAPHS_DIR.iterdir():
                if not country_dir.is_dir() or country_dir.name.startswith("_"):
                    continue

                country_name = country_dir.name
                latest_year = self._get_latest_year_for_country(country_name)

                if latest_year is None:
                    continue

                # Load latest graph to get edge count
                graph = self._load_graph_for_year(country_name, latest_year)
                if graph:
                    n_edges = len(graph.get("edges", []))
                    self._countries.append({
                        "name": country_name,
                        "n_edges": n_edges,
                        "n_edges_with_data": n_edges,  # All V3.1 edges have data
                        "coverage": 1.0,
                        "latest_year": latest_year
                    })

            self._countries.sort(key=lambda x: x["name"])

        return self._countries

    def _load_graph_for_year(self, country: str, year: int) -> Optional[dict]:
        """Load a country graph for a specific year."""
        graph_path = GRAPHS_DIR / country / f"{year}_graph.json"
        if not graph_path.exists():
            return None

        with open(graph_path) as f:
            return json.load(f)

    def get_country_graph(self, country: str, year: Optional[int] = None) -> Optional[dict]:
        """Load country graph (cached). Uses latest year if not specified."""
        cache_key = f"{country}_{year}" if year else country

        cached = self._cache_get(self._graph_cache, cache_key)
        if cached is not None:
            return cached

        if cache_key not in self._graph_cache:
            # Determine which year to use
            if year is None:
                year = self._get_latest_year_for_country(country)
                if year is None:
                    # Try default year
                    year = DEFAULT_GRAPH_YEAR

            raw_graph = self._load_graph_for_year(country, year)
            if raw_graph is None:
                return None

            # Convert to API format
            edges = [self._convert_v31_edge(e) for e in raw_graph.get("edges", [])]

            self._cache_set(self._graph_cache, cache_key, {
                "country": country,
                "year": year,
                "n_edges": len(edges),
                "n_edges_with_data": len(edges),
                "edges": edges
            }, self._graph_cache_max)

        return self._graph_cache[cache_key]

    def get_baseline_values(self, country: str, year: Optional[int] = None) -> Dict[str, float]:
        """Get baseline indicator values for a country.

        First tries V3.1 baselines, falls back to panel data.
        """
        # Try V3.1 baselines first
        if V31_BASELINES_DIR.exists():
            # Preferred format: baselines/{country}/{year}.json
            country_dir = V31_BASELINES_DIR / country
            if country_dir.exists() and country_dir.is_dir():
                available_years = sorted(
                    int(file.stem)
                    for file in country_dir.glob("*.json")
                    if file.stem.isdigit()
                )

                if available_years:
                    target_year = year if year in available_years else available_years[-1]
                    baseline_path = country_dir / f"{target_year}.json"
                    if baseline_path.exists():
                        with open(baseline_path) as f:
                            data = json.load(f)
                        values = data.get("values") if isinstance(data, dict) else None
                        if isinstance(values, dict):
                            return values

            # Backward compatibility format: baselines/{country}_baseline.json
            legacy_baseline_path = V31_BASELINES_DIR / f"{country}_baseline.json"
            if legacy_baseline_path.exists():
                with open(legacy_baseline_path) as f:
                    data = json.load(f)
                    if year and str(year) in data:
                        return data[str(year)]
                    # Return latest year
                    years = sorted([int(y) for y in data.keys() if y.isdigit()])
                    if years:
                        return data[str(years[-1])]

        # Fall back to panel data
        if self._panel_df is None:
            try:
                self._panel_df = pd.read_parquet(PANEL_PATH)
            except Exception:
                return {}

        # Handle long format panel data
        if 'indicator_id' in self._panel_df.columns:
            country_data = self._panel_df[self._panel_df['country'] == country]
            if country_data.empty:
                return {}

            if year is None:
                year = country_data['year'].max()

            year_data = country_data[country_data['year'] == year]
            return dict(zip(year_data['indicator_id'], year_data['value']))

        # Handle wide format
        country_data = self._panel_df[self._panel_df['country'] == country]
        if country_data.empty:
            return {}

        if year is None:
            year = country_data['year'].max()

        row = country_data[country_data['year'] == year]
        if row.empty:
            return {}

        return row.drop(columns=['country', 'year'], errors='ignore').iloc[0].to_dict()

    def country_exists(self, country: str) -> bool:
        """Check if country graph exists."""
        country_dir = GRAPHS_DIR / country
        return country_dir.exists() and any(country_dir.glob("*_graph.json"))

    def get_country_shap(self, country: str, year: Optional[int] = None) -> Dict[str, float]:
        """Get country-specific SHAP importance values (cached).

        Returns indicator_id -> importance (0-1 normalized).
        Falls back to empty dict if country SHAP file doesn't exist.

        V3.1 file structure: countries/{country}/quality_of_life/{year}_shap.json
        """
        cache_key = f"{country}_{year}" if year else country

        cached = self._cache_get(self._shap_cache, cache_key)
        if cached is not None:
            return cached

        if cache_key not in self._shap_cache:
            # V3.1 path: countries/{country}/quality_of_life/{year}_shap.json
            qol_dir = COUNTRY_SHAP_DIR / country / "quality_of_life"

            if not qol_dir.exists():
                self._shap_cache[cache_key] = {}
            else:
                # Find appropriate year
                if year is None:
                    # Use latest available year
                    shap_files = list(qol_dir.glob("*_shap.json"))
                    if shap_files:
                        years = []
                        for f in shap_files:
                            try:
                                y = int(f.stem.split("_")[0])
                                years.append(y)
                            except ValueError:
                                continue
                        year = max(years) if years else DEFAULT_GRAPH_YEAR
                    else:
                        year = DEFAULT_GRAPH_YEAR

                shap_path = qol_dir / f"{year}_shap.json"

                if not shap_path.exists():
                    self._cache_set(self._shap_cache, cache_key, {}, self._shap_cache_max)
                else:
                    try:
                        with open(shap_path) as f:
                            data = json.load(f)
                        # V3.1 format has shap_importance dict with mean/ci values
                        raw_shap = data.get('shap_importance', {})
                        # Extract mean values
                        shap_values = {}
                        for ind_id, val in raw_shap.items():
                            if isinstance(val, dict) and 'mean' in val:
                                shap_values[ind_id] = val['mean']
                            elif isinstance(val, (int, float)):
                                shap_values[ind_id] = val
                        self._cache_set(self._shap_cache, cache_key, shap_values, self._shap_cache_max)
                    except Exception:
                        self._cache_set(self._shap_cache, cache_key, {}, self._shap_cache_max)

        return self._shap_cache[cache_key]

    # ==================== Regional Methods ====================

    def region_exists(self, region: str) -> bool:
        """Check if regional graph data exists."""
        region_dir = V31_TEMPORAL_GRAPHS_DIR / "regional" / region
        return region_dir.exists() and any(region_dir.glob("*_graph.json"))

    def get_regional_graph(self, region: str, year: Optional[int] = None) -> Optional[dict]:
        """Load regional graph (cached). Uses latest year if not specified."""
        cache_key = f"regional_{region}_{year}" if year else f"regional_{region}"

        cached = self._cache_get(self._graph_cache, cache_key)
        if cached is not None:
            return cached

        if cache_key not in self._graph_cache:
            region_dir = V31_TEMPORAL_GRAPHS_DIR / "regional" / region
            if not region_dir.exists():
                return None

            if year is None:
                years = []
                for graph_file in region_dir.glob("*_graph.json"):
                    try:
                        y = int(graph_file.stem.split("_")[0])
                        years.append(y)
                    except ValueError:
                        continue
                year = max(years) if years else DEFAULT_GRAPH_YEAR

            graph_path = region_dir / f"{year}_graph.json"
            if not graph_path.exists():
                return None

            with open(graph_path) as f:
                raw_graph = json.load(f)

            edges = [self._convert_v31_edge(e) for e in raw_graph.get("edges", [])]

            self._cache_set(self._graph_cache, cache_key, {
                "country": region,  # reuse field for compatibility
                "region": region,
                "year": year,
                "n_edges": len(edges),
                "n_edges_with_data": len(edges),
                "edges": edges
            }, self._graph_cache_max)

        return self._graph_cache[cache_key]

    def get_regional_baseline(self, region: str, year: Optional[int] = None) -> Dict[str, float]:
        """Get baseline indicator values for a region."""
        region_dir = V31_BASELINES_DIR / "regional" / region
        if not region_dir.exists() or not region_dir.is_dir():
            return {}

        available_years = sorted(
            int(file.stem)
            for file in region_dir.glob("*.json")
            if file.stem.isdigit()
        )
        if not available_years:
            return {}

        target_year = year if year in available_years else available_years[-1]
        baseline_path = region_dir / f"{target_year}.json"
        if not baseline_path.exists():
            return {}

        with open(baseline_path) as f:
            data = json.load(f)
        values = data.get("values") if isinstance(data, dict) else None
        return values if isinstance(values, dict) else {}

    def get_regional_shap(self, region: str, year: Optional[int] = None) -> Dict[str, float]:
        """Get region-specific SHAP importance values (cached)."""
        cache_key = f"regional_shap_{region}_{year}" if year else f"regional_shap_{region}"

        cached = self._cache_get(self._shap_cache, cache_key)
        if cached is not None:
            return cached

        if cache_key not in self._shap_cache:
            qol_dir = V31_TEMPORAL_SHAP_DIR / "regional" / region / "quality_of_life"

            if not qol_dir.exists():
                self._cache_set(self._shap_cache, cache_key, {}, self._shap_cache_max)
            else:
                if year is None:
                    shap_files = list(qol_dir.glob("*_shap.json"))
                    if shap_files:
                        years = []
                        for f in shap_files:
                            try:
                                y = int(f.stem.split("_")[0])
                                years.append(y)
                            except ValueError:
                                continue
                        year = max(years) if years else DEFAULT_GRAPH_YEAR
                    else:
                        year = DEFAULT_GRAPH_YEAR

                shap_path = qol_dir / f"{year}_shap.json"

                if not shap_path.exists():
                    self._cache_set(self._shap_cache, cache_key, {}, self._shap_cache_max)
                else:
                    try:
                        with open(shap_path) as f:
                            data = json.load(f)
                        raw_shap = data.get('shap_importance', {})
                        shap_values = {}
                        for ind_id, val in raw_shap.items():
                            if isinstance(val, dict) and 'mean' in val:
                                shap_values[ind_id] = val['mean']
                            elif isinstance(val, (int, float)):
                                shap_values[ind_id] = val
                        self._cache_set(self._shap_cache, cache_key, shap_values, self._shap_cache_max)
                    except Exception:
                        self._cache_set(self._shap_cache, cache_key, {}, self._shap_cache_max)

        return self._shap_cache[cache_key]

    def get_regional_timeline(
        self,
        region: str,
        start_year: Optional[int] = None,
        end_year: Optional[int] = None
    ) -> Dict:
        """Build historical timeline for a region from baseline files."""
        region_dir = V31_BASELINES_DIR / "regional" / region
        if not region_dir.exists():
            return {'years': [], 'values': {}, 'indicators': []}

        available_years = sorted(
            int(file.stem)
            for file in region_dir.glob("*.json")
            if file.stem.isdigit()
        )
        if not available_years:
            return {'years': [], 'values': {}, 'indicators': []}

        if end_year is None:
            end_year = available_years[-1]
        if start_year is None:
            start_year = available_years[0]

        years = [y for y in available_years if start_year <= y <= end_year]

        raw_values = {}
        all_indicators: set = set()
        indicator_stats: Dict[str, Dict[str, float]] = {}

        for year in years:
            baseline_path = region_dir / f"{year}.json"
            if not baseline_path.exists():
                continue
            with open(baseline_path) as f:
                data = json.load(f)
            values = data.get("values") if isinstance(data, dict) else None
            if not isinstance(values, dict):
                continue
            raw_values[str(year)] = values
            all_indicators.update(values.keys())
            for ind, val in values.items():
                if val is None:
                    continue
                if ind not in indicator_stats:
                    indicator_stats[ind] = {'min': val, 'max': val}
                else:
                    indicator_stats[ind]['min'] = min(indicator_stats[ind]['min'], val)
                    indicator_stats[ind]['max'] = max(indicator_stats[ind]['max'], val)

        # Normalize
        normalized_values = {}
        for year_str, year_vals in raw_values.items():
            normalized_year = {}
            for ind, val in year_vals.items():
                if val is None or ind not in indicator_stats:
                    continue
                stats = indicator_stats[ind]
                val_range = stats['max'] - stats['min']
                normalized_year[ind] = (val - stats['min']) / val_range if val_range > 0 else 0.5
            normalized_values[year_str] = normalized_year

        return {
            'years': years,
            'values': normalized_values,
            'indicators': sorted(list(all_indicators))
        }

    def get_historical_timeline(
        self,
        country: str,
        start_year: Optional[int] = None,
        end_year: Optional[int] = None
    ) -> Dict:
        """
        Get historical indicator values across multiple years.
        """
        if self._panel_df is None:
            try:
                self._panel_df = pd.read_parquet(PANEL_PATH)
            except Exception:
                return {'years': [], 'values': {}, 'indicators': []}

        country_data = self._panel_df[self._panel_df['country'] == country]
        if country_data.empty:
            return {'years': [], 'values': {}, 'indicators': []}

        # Determine year range
        available_years = sorted(country_data['year'].unique())
        if not available_years:
            return {'years': [], 'values': {}, 'indicators': []}

        if end_year is None:
            end_year = int(available_years[-1])
        if start_year is None:
            start_year = max(int(available_years[0]), end_year - 10)

        # Filter to year range
        years = [int(y) for y in available_years if start_year <= y <= end_year]

        # Build raw values dict and collect per-indicator stats
        raw_values = {}
        indicator_stats: Dict[str, Dict[str, float]] = {}
        all_indicators = set()

        for year in years:
            year_data = country_data[country_data['year'] == year]
            year_values = dict(zip(year_data['indicator_id'], year_data['value']))
            raw_values[str(year)] = year_values
            all_indicators.update(year_values.keys())

            for ind, val in year_values.items():
                if val is None or pd.isna(val):
                    continue
                if ind not in indicator_stats:
                    indicator_stats[ind] = {'min': val, 'max': val}
                else:
                    indicator_stats[ind]['min'] = min(indicator_stats[ind]['min'], val)
                    indicator_stats[ind]['max'] = max(indicator_stats[ind]['max'], val)

        # Normalize values
        normalized_values = {}
        for year_str, year_vals in raw_values.items():
            normalized_year = {}
            for ind, val in year_vals.items():
                if val is None or pd.isna(val) or ind not in indicator_stats:
                    continue
                stats = indicator_stats[ind]
                val_range = stats['max'] - stats['min']
                if val_range > 0:
                    normalized_year[ind] = (val - stats['min']) / val_range
                else:
                    normalized_year[ind] = 0.5
            normalized_values[year_str] = normalized_year

        return {
            'years': years,
            'values': normalized_values,
            'indicators': sorted(list(all_indicators))
        }

    def get_graph_stats(self) -> dict:
        """Get aggregate statistics across all graphs."""
        countries = self.get_available_countries()

        total_edges = 0
        graphs_with_lags = 0
        total_significant_lags = 0

        for country_info in countries:
            graph = self.get_country_graph(country_info["name"])
            if graph:
                total_edges += graph.get("n_edges", 0)
                has_lags = any("lag" in e for e in graph.get("edges", []))
                if has_lags:
                    graphs_with_lags += 1
                    sig_lags = sum(1 for e in graph["edges"]
                                   if e.get("lag_significant", False))
                    total_significant_lags += sig_lags

        return {
            "total_countries": len(countries),
            "total_edges": total_edges,
            "graphs_with_lags": graphs_with_lags,
            "significant_lags": total_significant_lags
        }


# Singleton instance
graph_service = GraphService()
