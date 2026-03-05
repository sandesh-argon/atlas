"""
Graph Service

Handles loading and caching of country graphs.
"""

import json
import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional
from functools import lru_cache

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'scripts' / 'phaseB' / 'B3_simulation'))

from ..config import GRAPHS_DIR, PANEL_PATH, COUNTRY_SHAP_DIR


class GraphService:
    """Service for loading country graphs and baseline data."""

    def __init__(self):
        self._graph_cache: Dict[str, dict] = {}
        self._shap_cache: Dict[str, Dict[str, float]] = {}
        self._panel_df: Optional[pd.DataFrame] = None
        self._countries: Optional[List[str]] = None

    def get_available_countries(self) -> List[dict]:
        """Get list of all countries with graph metadata."""
        if self._countries is None:
            self._countries = []
            for graph_file in GRAPHS_DIR.glob("*.json"):
                if graph_file.name.startswith("_"):
                    continue
                try:
                    with open(graph_file) as f:
                        graph = json.load(f)
                    self._countries.append({
                        "name": graph_file.stem,
                        "n_edges": graph.get("n_edges", 0),
                        "n_edges_with_data": graph.get("n_edges_with_data", 0),
                        "coverage": graph.get("n_edges_with_data", 0) / max(graph.get("n_edges", 1), 1)
                    })
                except Exception:
                    continue

            self._countries.sort(key=lambda x: x["name"])

        return self._countries

    def get_country_graph(self, country: str) -> Optional[dict]:
        """Load country graph (cached)."""
        if country not in self._graph_cache:
            graph_path = GRAPHS_DIR / f"{country}.json"
            if not graph_path.exists():
                return None

            with open(graph_path) as f:
                self._graph_cache[country] = json.load(f)

        return self._graph_cache[country]

    def get_baseline_values(self, country: str, year: Optional[int] = None) -> Dict[str, float]:
        """Get baseline indicator values for a country."""
        if self._panel_df is None:
            self._panel_df = pd.read_parquet(PANEL_PATH)

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
        return (GRAPHS_DIR / f"{country}.json").exists()

    def get_country_shap(self, country: str) -> Dict[str, float]:
        """Get country-specific SHAP importance values (cached).

        Returns indicator_id -> importance (0-1 normalized).
        Falls back to empty dict if country SHAP file doesn't exist.
        """
        if country not in self._shap_cache:
            shap_path = COUNTRY_SHAP_DIR / f"{country}_shap.json"
            if not shap_path.exists():
                # No country SHAP available, return empty
                self._shap_cache[country] = {}
            else:
                try:
                    with open(shap_path) as f:
                        data = json.load(f)
                    self._shap_cache[country] = data.get('shap_importance', {})
                except Exception:
                    self._shap_cache[country] = {}

        return self._shap_cache[country]

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

                # Check for lag data
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
