"""
Map Service — QoL V1 scores (HDI-calibrated) for choropleth world map.

Reads precomputed scores from data/v31/qol_scores/country_year_qol_v1.json.
Falls back to gap_index from panel data for legacy endpoint.
"""

import json
import logging
from pathlib import Path
from typing import Optional

import pandas as pd

from ..config import DATA_ROOT, PANEL_PATH

logger = logging.getLogger("api.map")

QOL_SCORES_PATH = DATA_ROOT / "v31" / "qol_scores" / "country_year_qol_v1.json"


class MapService:
    def __init__(self) -> None:
        self._qol_cache: Optional[dict] = None
        self._qol_meta: Optional[dict] = None
        self._qol_year_min: Optional[int] = None
        self._qol_year_max: Optional[int] = None
        self._gap_cache: Optional[dict] = None

    # ---- QoL V1 (precomputed, HDI-calibrated) ----

    def _load_qol(self) -> None:
        """Load precomputed QoL V1 scores."""
        if self._qol_cache is not None:
            return

        try:
            with open(QOL_SCORES_PATH) as f:
                data = json.load(f)
        except Exception as e:
            logger.error("Failed to load QoL scores from %s: %s", QOL_SCORES_PATH, e)
            self._qol_cache = {}
            self._qol_meta = {}
            self._qol_year_min = None
            self._qol_year_max = None
            return

        self._qol_meta = {
            "definition_id": data.get("definition_id", "unknown"),
            "calibration": data.get("calibration", {}),
        }
        self._qol_cache = data.get("scores", {})
        years = []
        for country_data in self._qol_cache.values():
            by_year = country_data.get("by_year", {})
            for year_str in by_year.keys():
                try:
                    years.append(int(year_str))
                except (TypeError, ValueError):
                    continue
        if years:
            self._qol_year_min = min(years)
            self._qol_year_max = max(years)
            self._qol_meta["year_min"] = self._qol_year_min
            self._qol_meta["year_max"] = self._qol_year_max
        else:
            self._qol_year_min = None
            self._qol_year_max = None
        logger.info("Loaded QoL V1 scores for %d countries", len(self._qol_cache))

    def get_qol_metadata(self) -> dict:
        """Return QoL definition metadata."""
        self._load_qol()
        return self._qol_meta or {}

    def get_all_scores(self) -> dict:
        """Return all QoL V1 scores: { country: { iso3, by_year } }."""
        self._load_qol()
        return self._qol_cache or {}

    def get_scores_for_year(self, year: int) -> dict:
        """Return QoL V1 scores for a single year: { country: { qol, iso3 } }."""
        self._load_qol()
        if not self._qol_cache:
            return {}

        result: dict = {}
        year_str = str(year)
        for country, data in self._qol_cache.items():
            value = data["by_year"].get(year_str)
            if value is not None:
                result[country] = {
                    "qol": value,
                    "iso3": data["iso3"],
                }
        return result

    # ---- Legacy gap_index ----

    def _load_gap_index(self) -> None:
        """Load gap_index from panel data (legacy)."""
        if self._gap_cache is not None:
            return

        from ..services.temporal_service import temporal_service

        _ISO3_FALLBACKS: dict[str, str] = {
            "Burma/Myanmar": "MMR",
            "Somalia": "SOM",
            "Taiwan": "TWN",
            "Somaliland": "SOM",
            "Palestine/West Bank": "PSE",
            "Palestine/Gaza": "PSE",
        }

        classifications = temporal_service.get_income_classifications()
        iso3_map: dict[str, str] = {}
        for country, info in classifications.items():
            iso3 = info.get("iso3")
            if iso3:
                iso3_map[country] = iso3
        for name, iso3 in _ISO3_FALLBACKS.items():
            if name not in iso3_map:
                iso3_map[name] = iso3

        try:
            df = pd.read_parquet(PANEL_PATH)
        except Exception as e:
            logger.error("Failed to load panel data from %s: %s", PANEL_PATH, e)
            self._gap_cache = {}
            return

        gap_df = df[df["indicator_id"] == "gap_index"].copy()
        if gap_df.empty:
            logger.warning("No gap_index rows found in panel data")
            self._gap_cache = {}
            return

        result: dict = {}
        for _, row in gap_df.iterrows():
            country = row.get("country", "")
            year = row.get("year")
            value = row.get("value")
            if not country or year is None or value is None:
                continue
            if country not in result:
                iso3 = iso3_map.get(country, "")
                if not iso3:
                    continue
                result[country] = {"iso3": iso3, "by_year": {}}
            try:
                result[country]["by_year"][str(int(year))] = float(value)
            except (ValueError, TypeError):
                continue

        logger.info("Loaded gap_index scores for %d countries", len(result))
        self._gap_cache = result

    def get_gap_index_scores(self) -> dict:
        """Return all gap_index scores (legacy): { country: { iso3, by_year } }."""
        self._load_gap_index()
        return self._gap_cache or {}


map_service = MapService()
