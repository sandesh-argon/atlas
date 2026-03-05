"""
Temporal Data Service

Handles loading and caching of V3.1 temporal data:
- Temporal SHAP (importance over time)
- Temporal Graphs (beta coefficients over time)
- Development Clusters
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from functools import lru_cache
from collections import OrderedDict

from ..config import (
    V31_TEMPORAL_SHAP_DIR,
    V31_TEMPORAL_GRAPHS_DIR,
    V31_CLUSTERS_DIR,
    V31_FEEDBACK_LOOPS_DIR,
    V31_INCOME_CLASSIFICATIONS,
    V31_COUNTRY_TRANSITIONS,
    V31_COUNTRY_DATA_QUALITY,
    TEMPORAL_YEAR_MIN,
    TEMPORAL_YEAR_MAX,
    TEMPORAL_TARGETS,
    INCOME_STRATA,
    TEMPORAL_SERVICE_SHAP_CACHE_MAX,
    TEMPORAL_SERVICE_GRAPH_CACHE_MAX,
    TEMPORAL_SERVICE_CLUSTER_CACHE_MAX,
)


class TemporalService:
    """Service for loading V3.1 temporal data."""

    def __init__(self):
        self._shap_cache: "OrderedDict[str, dict]" = OrderedDict()
        self._graph_cache: "OrderedDict[str, dict]" = OrderedDict()
        self._cluster_cache: "OrderedDict[str, dict]" = OrderedDict()
        self._income_classifications: Optional[dict] = None
        self._country_transitions: Optional[dict] = None
        self._country_data_quality: Optional[dict] = None
        self._available_countries: Optional[List[str]] = None
        self._available_shap_countries: Optional[List[str]] = None
        self._shap_cache_max = TEMPORAL_SERVICE_SHAP_CACHE_MAX
        self._graph_cache_max = TEMPORAL_SERVICE_GRAPH_CACHE_MAX
        self._cluster_cache_max = TEMPORAL_SERVICE_CLUSTER_CACHE_MAX

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

    def get_available_years(self) -> List[int]:
        """Get list of available years."""
        return list(range(TEMPORAL_YEAR_MIN, TEMPORAL_YEAR_MAX + 1))

    def get_available_targets(self) -> List[str]:
        """Get list of available targets."""
        return TEMPORAL_TARGETS.copy()

    def get_available_shap_countries(self) -> List[str]:
        """Get list of countries with SHAP data (may be subset if mock)."""
        if self._available_shap_countries is None:
            countries_dir = V31_TEMPORAL_SHAP_DIR / "countries"
            if countries_dir.exists():
                self._available_shap_countries = sorted([
                    d.name for d in countries_dir.iterdir() if d.is_dir()
                ])
            else:
                self._available_shap_countries = []
        return self._available_shap_countries

    def get_available_graph_countries(self) -> List[str]:
        """Get list of countries with temporal graph data."""
        if self._available_countries is None:
            countries_dir = V31_TEMPORAL_GRAPHS_DIR / "countries"
            if countries_dir.exists():
                self._available_countries = sorted([
                    d.name for d in countries_dir.iterdir() if d.is_dir()
                ])
            else:
                self._available_countries = []
        return self._available_countries

    # ==================== SHAP Methods ====================

    def get_temporal_shap(
        self,
        country: Optional[str],
        target: str,
        year: int
    ) -> Optional[dict]:
        """
        Get SHAP importance for a specific country/target/year.

        Args:
            country: Country name or None for unified
            target: Target outcome (e.g., 'quality_of_life')
            year: Year (1990-2024)

        Returns:
            SHAP data dict or None if not found
        """
        cache_key = f"{country or 'unified'}_{target}_{year}"

        cached = self._cache_get(self._shap_cache, cache_key)
        if cached is not None:
            return cached

        if cache_key not in self._shap_cache:
            if country is None:
                path = V31_TEMPORAL_SHAP_DIR / "unified" / target / f"{year}_shap.json"
            else:
                path = V31_TEMPORAL_SHAP_DIR / "countries" / country / target / f"{year}_shap.json"

            if not path.exists():
                return None

            with open(path) as f:
                self._cache_set(self._shap_cache, cache_key, json.load(f), self._shap_cache_max)

        return self._shap_cache[cache_key]

    def get_temporal_shap_timeline(
        self,
        country: Optional[str],
        target: str,
        start_year: Optional[int] = None,
        end_year: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Get SHAP importance for all years (for preloading timeline).

        Args:
            country: Country name or None for unified
            target: Target outcome
            start_year: Start year (default: TEMPORAL_YEAR_MIN)
            end_year: End year (default: TEMPORAL_YEAR_MAX)

        Returns:
            {
                'country': str or None,
                'target': str,
                'years': [1990, 1991, ...],
                'shap_by_year': { '1990': { node_id: importance, ... }, ... },
                'is_mock': bool
            }
        """
        start_year = start_year or TEMPORAL_YEAR_MIN
        end_year = end_year or TEMPORAL_YEAR_MAX

        years = []
        shap_by_year = {}
        is_mock = False

        for year in range(start_year, end_year + 1):
            data = self.get_temporal_shap(country, target, year)
            if data:
                years.append(year)
                shap_by_year[str(year)] = data.get('shap_importance', {})
                if data.get('metadata', {}).get('is_mock_data'):
                    is_mock = True

        return {
            'country': country,
            'target': target,
            'years': years,
            'shap_by_year': shap_by_year,
            'is_mock': is_mock
        }

    # ==================== Regional SHAP Methods ====================

    def get_regional_shap(
        self,
        region: str,
        target: str,
        year: int
    ) -> Optional[dict]:
        """Get regional SHAP importance for a specific region/target/year."""
        cache_key = f"regional_{region}_{target}_{year}"

        cached = self._cache_get(self._shap_cache, cache_key)
        if cached is not None:
            return cached

        if cache_key not in self._shap_cache:
            path = V31_TEMPORAL_SHAP_DIR / "regional" / region / target / f"{year}_shap.json"

            if not path.exists():
                return None

            with open(path) as f:
                self._cache_set(self._shap_cache, cache_key, json.load(f), self._shap_cache_max)

        return self._shap_cache[cache_key]

    def get_regional_shap_timeline(
        self,
        region: str,
        target: str,
        start_year: Optional[int] = None,
        end_year: Optional[int] = None
    ) -> Dict[str, Any]:
        """Get regional SHAP importance for all years (preload for timeline)."""
        start_year = start_year or TEMPORAL_YEAR_MIN
        end_year = end_year or TEMPORAL_YEAR_MAX

        years = []
        shap_by_year = {}
        is_mock = False

        for year in range(start_year, end_year + 1):
            data = self.get_regional_shap(region, target, year)
            if data:
                years.append(year)
                shap_by_year[str(year)] = data.get('shap_importance', {})
                if data.get('metadata', {}).get('is_mock_data'):
                    is_mock = True

        return {
            'country': None,
            'region': region,
            'target': target,
            'years': years,
            'shap_by_year': shap_by_year,
            'is_mock': is_mock
        }

    # ==================== Stratified SHAP Methods ====================

    def get_stratified_shap(
        self,
        stratum: str,
        target: str,
        year: int
    ) -> Optional[dict]:
        """
        Get stratified SHAP importance for a specific income stratum/target/year.

        Args:
            stratum: Income stratum ('developing', 'emerging', 'advanced')
            target: Target outcome (e.g., 'quality_of_life')
            year: Year (1990-2024)

        Returns:
            SHAP data dict or None if not found
        """
        if stratum not in INCOME_STRATA:
            return None

        cache_key = f"stratified_{stratum}_{target}_{year}"

        cached = self._cache_get(self._shap_cache, cache_key)
        if cached is not None:
            return cached

        if cache_key not in self._shap_cache:
            path = V31_TEMPORAL_SHAP_DIR / "stratified" / stratum / target / f"{year}_shap.json"

            if not path.exists():
                return None

            with open(path) as f:
                self._cache_set(self._shap_cache, cache_key, json.load(f), self._shap_cache_max)

        return self._shap_cache[cache_key]

    def get_stratified_shap_timeline(
        self,
        stratum: str,
        target: str,
        start_year: Optional[int] = None,
        end_year: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Get stratified SHAP importance for all years (for preloading timeline).

        Args:
            stratum: Income stratum ('developing', 'emerging', 'advanced')
            target: Target outcome
            start_year: Start year (default: TEMPORAL_YEAR_MIN)
            end_year: End year (default: TEMPORAL_YEAR_MAX)

        Returns:
            {
                'stratum': str,
                'target': str,
                'years': [1990, 1991, ...],
                'shap_by_year': { '1990': { node_id: { mean, std, ci_lower, ci_upper }, ... }, ... },
                'countries_by_year': { '1990': [...], '1991': [...], ... }
            }
        """
        start_year = start_year or TEMPORAL_YEAR_MIN
        end_year = end_year or TEMPORAL_YEAR_MAX

        years = []
        shap_by_year = {}
        countries_by_year = {}

        for year in range(start_year, end_year + 1):
            data = self.get_stratified_shap(stratum, target, year)
            if data:
                years.append(year)
                shap_by_year[str(year)] = data.get('shap_importance', {})
                # Include country list per year for dynamic membership
                stratification = data.get('stratification', {})
                countries_by_year[str(year)] = stratification.get('countries_in_stratum', [])

        return {
            'stratum': stratum,
            'target': target,
            'years': years,
            'shap_by_year': shap_by_year,
            'countries_by_year': countries_by_year
        }

    def get_available_strata(self) -> List[str]:
        """Get list of available income strata."""
        return INCOME_STRATA.copy()

    # ==================== Income Classification Methods ====================

    def get_income_classifications(self) -> dict:
        """
        Load income classifications for all countries/years.

        Returns the 'countries' dict from the income_classifications.json file:
        {
            'Afghanistan': {
                'wb_name': 'Afghanistan',
                'iso3': 'AFG',
                'current_classification_3tier': 'Developing',
                'by_year': {
                    '1990': {'gni_per_capita': None, 'classification_4tier': 'Low income', 'classification_3tier': 'Developing'},
                    ...
                }
            },
            ...
        }
        """
        if self._income_classifications is None:
            if V31_INCOME_CLASSIFICATIONS.exists():
                with open(V31_INCOME_CLASSIFICATIONS) as f:
                    data = json.load(f)
                    # Extract the 'countries' section
                    self._income_classifications = data.get('countries', {})
            else:
                self._income_classifications = {}

        return self._income_classifications

    def get_country_income_classification(
        self,
        country: str,
        year: int
    ) -> Optional[dict]:
        """
        Get income classification for a specific country/year.

        Returns:
            {'group_4tier': 'Low income', 'group_3tier': 'Developing', 'gni_per_capita': 500}
            or None if not found
        """
        classifications = self.get_income_classifications()
        country_data = classifications.get(country, {})
        by_year = country_data.get('by_year', {})
        year_data = by_year.get(str(year))

        if year_data:
            # Map to expected format
            return {
                'group_4tier': year_data.get('classification_4tier', ''),
                'group_3tier': year_data.get('classification_3tier', ''),
                'gni_per_capita': year_data.get('gni_per_capita')
            }
        return None

    def get_stratum_countries(self, stratum: str, year: int) -> List[str]:
        """
        Get list of countries in a specific stratum for a given year.

        Args:
            stratum: Income stratum ('developing', 'emerging', 'advanced')
            year: Year

        Returns:
            List of country names in that stratum for that year
        """
        classifications = self.get_income_classifications()
        countries = []

        for country, country_data in classifications.items():
            by_year = country_data.get('by_year', {})
            year_data = by_year.get(str(year))
            if year_data:
                stratum_raw = year_data.get('classification_3tier')
                if stratum_raw and stratum_raw.lower() == stratum.lower():
                    countries.append(country)

        return sorted(countries)

    def get_stratum_counts(self, year: int) -> Dict[str, int]:
        """
        Get count of countries in each stratum for a given year.

        Returns:
            {'developing': 71, 'emerging': 45, 'advanced': 55}
        """
        counts = {stratum: 0 for stratum in INCOME_STRATA}
        classifications = self.get_income_classifications()

        for country, country_data in classifications.items():
            by_year = country_data.get('by_year', {})
            year_data = by_year.get(str(year))
            if year_data:
                stratum_raw = year_data.get('classification_3tier')
                if stratum_raw:
                    stratum = stratum_raw.lower()
                    if stratum in counts:
                        counts[stratum] += 1

        return counts

    # ==================== Country Transition Methods ====================

    def get_country_transitions(self) -> dict:
        """
        Load country income transition data.

        Returns full transitions data with summary and per-country transitions:
        {
            'summary': {'countries_with_transitions': 76, 'total_transitions': 141, ...},
            'transitions': {
                'China': {
                    'iso3': 'CHN',
                    'current_stratum': 'emerging',
                    'transitions': [
                        {'year': 2010, 'from': 'developing', 'to': 'emerging', 'gni_at_transition': 4500}
                    ]
                },
                ...
            }
        }
        """
        if self._country_transitions is None:
            if V31_COUNTRY_TRANSITIONS.exists():
                with open(V31_COUNTRY_TRANSITIONS) as f:
                    self._country_transitions = json.load(f)
            else:
                self._country_transitions = {'summary': {}, 'transitions': {}}

        return self._country_transitions

    def get_country_transition(self, country: str) -> Optional[dict]:
        """
        Get transition history for a specific country.

        Returns:
            {
                'iso3': 'CHN',
                'current_stratum': 'emerging',
                'transitions': [
                    {'year': 2010, 'from': 'developing', 'to': 'emerging', 'gni_at_transition': 4500}
                ]
            }
            or None if country has no transitions
        """
        data = self.get_country_transitions()
        return data.get('transitions', {}).get(country)

    # ==================== Country Data Quality Methods ====================

    def get_country_data_quality(self) -> dict:
        """
        Load country data quality information.

        Returns full data quality metadata and per-country quality metrics:
        {
            'metadata': {
                'total_indicators_in_dataset': 3122,
                'quality_thresholds': {'complete': '>=50%', 'partial': '>=25%', 'sparse': '<25%'},
                'confidence_thresholds': {'high': '>=50%', 'medium': '>=30%', 'low': '<30%'}
            },
            'countries': {
                'Rwanda': {
                    'total_indicators': 2661,
                    'coverage_pct': 76.9,
                    'observed_pct': 77.8,
                    'imputed_pct': 22.2,
                    'confidence': 'high',
                    'by_year': {
                        '1990': {'quality': 'complete', 'indicators': 1777, ...},
                        ...
                    }
                },
                ...
            }
        }
        """
        if self._country_data_quality is None:
            if V31_COUNTRY_DATA_QUALITY.exists():
                with open(V31_COUNTRY_DATA_QUALITY) as f:
                    self._country_data_quality = json.load(f)
            else:
                self._country_data_quality = {'metadata': {}, 'countries': {}}

        return self._country_data_quality

    def get_country_quality(self, country: str) -> Optional[dict]:
        """
        Get data quality for a specific country.

        Args:
            country: Country name

        Returns:
            Country quality data dict or None if not found:
            {
                'total_indicators': 2661,
                'coverage_pct': 76.9,
                'observed_pct': 77.8,
                'imputed_pct': 22.2,
                'confidence': 'high',
                'by_year': {
                    '1990': {'quality': 'complete', 'indicators': 1777, 'observed': 1463, 'observed_pct': 82.3, 'imputed_pct': 17.7},
                    ...
                }
            }
        """
        data = self.get_country_data_quality()
        return data.get('countries', {}).get(country)

    def get_data_quality_metadata(self) -> dict:
        """Get data quality metadata (thresholds, total indicators)."""
        data = self.get_country_data_quality()
        return data.get('metadata', {})

    def get_unified_data_quality(self) -> dict:
        """
        Get aggregated data quality for unified (all countries) view.

        Returns:
            {
                'view': 'unified',
                'n_countries': 178,
                'total_indicators': 3122,
                'avg_coverage_pct': 74.2,
                'avg_observed_pct': 78.5,
                'avg_imputed_pct': 21.5,
                'confidence': 'high',
                'by_year': { '1990': {...}, ... }
            }
        """
        data = self.get_country_data_quality()
        metadata = data.get('metadata', {})
        countries = data.get('countries', {})

        if not countries:
            return {
                'view': 'unified',
                'n_countries': 0,
                'total_indicators': metadata.get('total_indicators_in_dataset', 0),
                'avg_coverage_pct': 0,
                'avg_observed_pct': 0,
                'avg_imputed_pct': 0,
                'confidence': 'low',
                'by_year': {}
            }

        # Aggregate across all countries
        n_countries = len(countries)
        total_coverage = sum(c.get('coverage_pct', 0) for c in countries.values())
        total_observed = sum(c.get('observed_pct', 0) for c in countries.values())
        total_imputed = sum(c.get('imputed_pct', 0) for c in countries.values())

        avg_coverage = total_coverage / n_countries
        avg_observed = total_observed / n_countries
        avg_imputed = total_imputed / n_countries

        # Aggregate by year
        years = metadata.get('years', [])
        by_year = {}
        for year in years:
            year_key = str(year)
            year_coverages = []
            year_observed = []
            year_imputed = []
            year_indicators = []

            for country_data in countries.values():
                year_data = country_data.get('by_year', {}).get(year_key)
                if year_data:
                    year_observed.append(year_data.get('observed_pct', 0))
                    year_imputed.append(year_data.get('imputed_pct', 0))
                    year_indicators.append(year_data.get('indicators', 0))
                    year_coverages.append(year_data.get('coverage_pct', 0))

            if year_observed:
                avg_obs = sum(year_observed) / len(year_observed)
                avg_imp = sum(year_imputed) / len(year_imputed)
                avg_ind = sum(year_indicators) / len(year_indicators)

                # Determine quality level
                if avg_obs >= 50:
                    quality = 'complete'
                elif avg_obs >= 25:
                    quality = 'partial'
                else:
                    quality = 'sparse'

                by_year[year_key] = {
                    'quality': quality,
                    'n_countries': len(year_observed),
                    'avg_indicators': round(avg_ind),
                    'observed_pct': round(avg_obs, 1),
                    'imputed_pct': round(avg_imp, 1)
                }

        # Determine confidence
        if avg_observed >= 50:
            confidence = 'high'
        elif avg_observed >= 30:
            confidence = 'medium'
        else:
            confidence = 'low'

        return {
            'view': 'unified',
            'n_countries': n_countries,
            'total_indicators': metadata.get('total_indicators_in_dataset', 0),
            'avg_coverage_pct': round(avg_coverage, 1),
            'avg_observed_pct': round(avg_observed, 1),
            'avg_imputed_pct': round(avg_imputed, 1),
            'confidence': confidence,
            'by_year': by_year
        }

    def get_stratified_data_quality(self, stratum: str, year: int = 2020) -> Optional[dict]:
        """
        Get aggregated data quality for a specific income stratum.

        Args:
            stratum: Income stratum ('developing', 'emerging', 'advanced')
            year: Reference year for stratum membership (default 2020)

        Returns:
            {
                'view': 'stratified',
                'stratum': 'developing',
                'n_countries': 76,
                'countries': [...],
                'total_indicators': 3122,
                'avg_coverage_pct': 68.5,
                'avg_observed_pct': 72.1,
                'avg_imputed_pct': 27.9,
                'confidence': 'high',
                'by_year': { '1990': {...}, ... }
            }
        """
        if stratum not in INCOME_STRATA:
            return None

        # Get countries in this stratum for the given year
        classifications = self.get_income_classifications()
        stratum_countries = []

        for country, country_data in classifications.items():
            # Structure: country_data = {'by_year': {'2020': {'classification_3tier': 'Developing', ...}}}
            by_year = country_data.get('by_year', {})
            year_class = by_year.get(str(year))
            if year_class:
                # Get 3-tier classification (Developing, Emerging, Advanced)
                classification_3tier = year_class.get('classification_3tier') or ''
                if classification_3tier.lower() == stratum:
                    stratum_countries.append(country)

        if not stratum_countries:
            return None

        # Get quality data
        data = self.get_country_data_quality()
        metadata = data.get('metadata', {})
        all_countries = data.get('countries', {})

        # Filter to stratum countries
        countries = {k: v for k, v in all_countries.items() if k in stratum_countries}

        if not countries:
            return {
                'view': 'stratified',
                'stratum': stratum,
                'n_countries': len(stratum_countries),
                'countries': stratum_countries,
                'total_indicators': metadata.get('total_indicators_in_dataset', 0),
                'avg_coverage_pct': 0,
                'avg_observed_pct': 0,
                'avg_imputed_pct': 0,
                'confidence': 'low',
                'by_year': {}
            }

        # Aggregate across stratum countries
        n_countries = len(countries)
        total_coverage = sum(c.get('coverage_pct', 0) for c in countries.values())
        total_observed = sum(c.get('observed_pct', 0) for c in countries.values())
        total_imputed = sum(c.get('imputed_pct', 0) for c in countries.values())

        avg_coverage = total_coverage / n_countries
        avg_observed = total_observed / n_countries
        avg_imputed = total_imputed / n_countries

        # Aggregate by year
        years = metadata.get('years', [])
        by_year = {}
        for yr in years:
            year_key = str(yr)
            year_observed = []
            year_imputed = []
            year_indicators = []

            for country_data in countries.values():
                year_data = country_data.get('by_year', {}).get(year_key)
                if year_data:
                    year_observed.append(year_data.get('observed_pct', 0))
                    year_imputed.append(year_data.get('imputed_pct', 0))
                    year_indicators.append(year_data.get('indicators', 0))

            if year_observed:
                avg_obs = sum(year_observed) / len(year_observed)
                avg_imp = sum(year_imputed) / len(year_imputed)
                avg_ind = sum(year_indicators) / len(year_indicators)

                if avg_obs >= 50:
                    quality = 'complete'
                elif avg_obs >= 25:
                    quality = 'partial'
                else:
                    quality = 'sparse'

                by_year[year_key] = {
                    'quality': quality,
                    'n_countries': len(year_observed),
                    'avg_indicators': round(avg_ind),
                    'observed_pct': round(avg_obs, 1),
                    'imputed_pct': round(avg_imp, 1)
                }

        # Determine confidence
        if avg_observed >= 50:
            confidence = 'high'
        elif avg_observed >= 30:
            confidence = 'medium'
        else:
            confidence = 'low'

        return {
            'view': 'stratified',
            'stratum': stratum,
            'n_countries': n_countries,
            'countries': list(countries.keys()),
            'total_indicators': metadata.get('total_indicators_in_dataset', 0),
            'avg_coverage_pct': round(avg_coverage, 1),
            'avg_observed_pct': round(avg_observed, 1),
            'avg_imputed_pct': round(avg_imputed, 1),
            'confidence': confidence,
            'by_year': by_year
        }

    # ==================== Stratified Graph Methods ====================

    def get_stratified_graph(
        self,
        stratum: str,
        year: int
    ) -> Optional[dict]:
        """
        Get stratified causal graph for a specific income stratum/year.

        Args:
            stratum: Income stratum ('developing', 'emerging', 'advanced')
            year: Year (1990-2024)

        Returns:
            Graph data dict or None if not found
        """
        if stratum not in INCOME_STRATA:
            return None

        cache_key = f"stratified_graph_{stratum}_{year}"

        cached = self._cache_get(self._graph_cache, cache_key)
        if cached is not None:
            return cached

        if cache_key not in self._graph_cache:
            path = V31_TEMPORAL_GRAPHS_DIR / "stratified" / stratum / f"{year}_graph.json"

            if not path.exists():
                return None

            with open(path) as f:
                self._cache_set(self._graph_cache, cache_key, json.load(f), self._graph_cache_max)

        return self._graph_cache[cache_key]

    # ==================== Feedback Loop Methods ====================

    def get_feedback_loops(self, country: str) -> Optional[dict]:
        """
        Get feedback loops for a specific country.

        Args:
            country: Country name

        Returns:
            Feedback loop data dict or None if not found
        """
        cache_key = f"feedback_{country}"

        cached = self._cache_get(self._cluster_cache, cache_key)
        if cached is not None:
            return cached

        if cache_key not in self._cluster_cache:  # Reusing cluster cache
            path = V31_FEEDBACK_LOOPS_DIR / f"{country}_feedback_loops.json"

            if not path.exists():
                return None

            with open(path) as f:
                self._cache_set(self._cluster_cache, cache_key, json.load(f), self._cluster_cache_max)

        return self._cluster_cache[cache_key]

    # ==================== Graph Methods ====================

    def get_temporal_graph(
        self,
        country: Optional[str],
        year: int
    ) -> Optional[dict]:
        """
        Get causal graph for a specific country/year.

        Args:
            country: Country name or None for unified
            year: Year (1990-2024)

        Returns:
            Graph data dict or None if not found
        """
        cache_key = f"{country or 'unified'}_{year}"

        cached = self._cache_get(self._graph_cache, cache_key)
        if cached is not None:
            return cached

        if cache_key not in self._graph_cache:
            if country is None:
                path = V31_TEMPORAL_GRAPHS_DIR / "unified" / f"{year}_graph.json"
            else:
                path = V31_TEMPORAL_GRAPHS_DIR / "countries" / country / f"{year}_graph.json"

            if not path.exists():
                return None

            with open(path) as f:
                self._cache_set(self._graph_cache, cache_key, json.load(f), self._graph_cache_max)

        return self._graph_cache[cache_key]

    def get_temporal_graph_years(
        self,
        country: Optional[str]
    ) -> List[int]:
        """Get list of years with graph data for a country."""
        if country is None:
            graph_dir = V31_TEMPORAL_GRAPHS_DIR / "unified"
        else:
            graph_dir = V31_TEMPORAL_GRAPHS_DIR / "countries" / country

        if not graph_dir.exists():
            return []

        years = []
        for f in graph_dir.glob("*_graph.json"):
            try:
                year = int(f.stem.split("_")[0])
                years.append(year)
            except ValueError:
                continue

        return sorted(years)

    # ==================== Cluster Methods ====================

    def get_clusters(
        self,
        country: Optional[str],
        year: Optional[int] = None
    ) -> Optional[dict]:
        """
        Get development clusters for a country/year.

        Args:
            country: Country name or None for unified
            year: Year (only for unified, countries have single file)

        Returns:
            Cluster data dict or None if not found
        """
        if country is None:
            if year is None:
                year = TEMPORAL_YEAR_MAX
            cache_key = f"unified_{year}"
            path = V31_CLUSTERS_DIR / "unified" / f"{year}_clusters.json"
        else:
            cache_key = f"{country}"
            path = V31_CLUSTERS_DIR / "countries" / f"{country}_clusters.json"

        cached = self._cache_get(self._cluster_cache, cache_key)
        if cached is not None:
            return cached

        if cache_key not in self._cluster_cache:
            if not path.exists():
                return None

            with open(path) as f:
                self._cache_set(self._cluster_cache, cache_key, json.load(f), self._cluster_cache_max)

        return self._cluster_cache[cache_key]

    # ==================== Utility Methods ====================

    def clear_cache(self):
        """Clear all caches."""
        self._shap_cache.clear()
        self._graph_cache.clear()
        self._cluster_cache.clear()

    def get_data_status(self) -> Dict[str, Any]:
        """Get status of available V3.1 data."""
        # Check SHAP
        shap_countries = self.get_available_shap_countries()
        shap_unified_exists = (V31_TEMPORAL_SHAP_DIR / "unified").exists()

        # Check if mock
        sample_shap = self.get_temporal_shap(None, "quality_of_life", 2024)
        is_mock = sample_shap.get('metadata', {}).get('is_mock_data', False) if sample_shap else True

        # Check graphs
        graph_countries = self.get_available_graph_countries()
        graph_unified_exists = (V31_TEMPORAL_GRAPHS_DIR / "unified").exists()

        # Check clusters
        clusters_unified_exists = (V31_CLUSTERS_DIR / "unified").exists()
        clusters_countries_dir = V31_CLUSTERS_DIR / "countries"
        cluster_countries = len(list(clusters_countries_dir.glob("*.json"))) if clusters_countries_dir.exists() else 0

        return {
            'temporal_shap': {
                'status': 'mock' if is_mock else 'real',
                'unified': shap_unified_exists,
                'countries': len(shap_countries),
                'country_list': shap_countries[:10]  # First 10
            },
            'temporal_graphs': {
                'status': 'real',
                'unified': graph_unified_exists,
                'countries': len(graph_countries)
            },
            'development_clusters': {
                'status': 'real',
                'unified': clusters_unified_exists,
                'countries': cluster_countries
            },
            'years': {
                'min': TEMPORAL_YEAR_MIN,
                'max': TEMPORAL_YEAR_MAX
            },
            'targets': TEMPORAL_TARGETS
        }

    # ==================== Stratum Distribution Methods ====================

    def _load_income_thresholds(self) -> dict:
        """Load income classification thresholds by year."""
        if V31_INCOME_CLASSIFICATIONS.exists():
            with open(V31_INCOME_CLASSIFICATIONS) as f:
                data = json.load(f)
                return data.get('thresholds', {})
        return {}

    def get_stratum_distribution(self, year: int) -> dict:
        """
        Get detailed stratum distribution for a given year.

        Returns distribution of countries across strata with GNI details
        and positional information (how close to next tier).

        Args:
            year: Year (1990-2024)

        Returns:
            {
                'year': 2020,
                'thresholds': {
                    'developing_to_emerging': 4045,  # GNI threshold
                    'emerging_to_advanced': 12535
                },
                'distribution': {
                    'developing': {'count': 76, 'percentage': 43.2},
                    'emerging': {'count': 55, 'percentage': 31.2},
                    'advanced': {'count': 45, 'percentage': 25.6}
                },
                'total_countries': 176,
                'countries': {
                    'developing': [
                        {
                            'name': 'Afghanistan',
                            'gni_per_capita': 500,
                            'position_in_stratum': 0.12,  # 0-1 (how far through the tier)
                            'distance_to_next': 3545,     # GNI gap to next tier
                            'progress_pct': 12.4          # % toward next tier
                        },
                        ...
                    ],
                    'emerging': [...],
                    'advanced': [...]
                }
            }
        """
        classifications = self.get_income_classifications()
        thresholds_data = self._load_income_thresholds()

        year_str = str(year)
        year_thresholds = thresholds_data.get(year_str, [610, 2465, 7620])  # Default 1990 thresholds

        # Thresholds array: [low/lower-middle, lower-middle/upper-middle, upper-middle/high]
        # For 3-tier: developing (<t1 or t1-t2), emerging (t2-t3), advanced (>t3)
        # Actually looking at the metadata: Developing = Low + Lower-middle, Emerging = Upper-middle, Advanced = High
        # So: developing < t2, emerging: t2 <= gni < t3, advanced >= t3
        t_dev_to_emerg = year_thresholds[1] if len(year_thresholds) > 1 else 2465  # Lower-middle to Upper-middle
        t_emerg_to_adv = year_thresholds[2] if len(year_thresholds) > 2 else 7620  # Upper-middle to High

        distribution = {
            'developing': {'count': 0, 'percentage': 0},
            'emerging': {'count': 0, 'percentage': 0},
            'advanced': {'count': 0, 'percentage': 0}
        }

        countries_by_stratum: Dict[str, List[dict]] = {
            'developing': [],
            'emerging': [],
            'advanced': []
        }

        for country, country_data in classifications.items():
            by_year = country_data.get('by_year', {})
            year_data = by_year.get(year_str)

            if not year_data:
                continue

            classification_3tier = year_data.get('classification_3tier') or ''
            stratum = classification_3tier.lower() if classification_3tier else None
            gni = year_data.get('gni_per_capita')

            if stratum not in distribution:
                continue

            distribution[stratum]['count'] += 1

            # Calculate position within stratum
            country_info = {
                'name': country,
                'gni_per_capita': gni,
                'position_in_stratum': 0.5,  # Default midpoint
                'distance_to_next': None,
                'progress_pct': 50  # Default
            }

            if gni is not None:
                if stratum == 'developing':
                    # Position: 0 at bottom, 1 at threshold
                    # Assume floor of ~200 GNI for visualization
                    floor = 200
                    country_info['position_in_stratum'] = min(1.0, max(0, (gni - floor) / (t_dev_to_emerg - floor)))
                    country_info['distance_to_next'] = max(0, t_dev_to_emerg - gni)
                    country_info['progress_pct'] = round(country_info['position_in_stratum'] * 100, 1)
                elif stratum == 'emerging':
                    # Position: 0 at developing threshold, 1 at advanced threshold
                    range_size = t_emerg_to_adv - t_dev_to_emerg
                    if range_size > 0:
                        country_info['position_in_stratum'] = min(1.0, max(0, (gni - t_dev_to_emerg) / range_size))
                    country_info['distance_to_next'] = max(0, t_emerg_to_adv - gni)
                    country_info['progress_pct'] = round(country_info['position_in_stratum'] * 100, 1)
                else:  # advanced
                    # Position: based on how far above threshold
                    # Use ceiling of ~100,000 for normalization
                    ceiling = 100000
                    country_info['position_in_stratum'] = min(1.0, max(0, (gni - t_emerg_to_adv) / (ceiling - t_emerg_to_adv)))
                    country_info['distance_to_next'] = None  # No next tier
                    country_info['progress_pct'] = round(country_info['position_in_stratum'] * 100, 1)

            countries_by_stratum[stratum].append(country_info)

        # Sort each stratum by GNI (highest first)
        for stratum in countries_by_stratum:
            countries_by_stratum[stratum].sort(
                key=lambda x: x['gni_per_capita'] if x['gni_per_capita'] is not None else -1,
                reverse=True
            )

        # Calculate percentages
        total = sum(d['count'] for d in distribution.values())
        if total > 0:
            for stratum in distribution:
                distribution[stratum]['percentage'] = round(distribution[stratum]['count'] / total * 100, 1)

        return {
            'year': year,
            'thresholds': {
                'developing_to_emerging': t_dev_to_emerg,
                'emerging_to_advanced': t_emerg_to_adv
            },
            'distribution': distribution,
            'total_countries': total,
            'countries': countries_by_stratum
        }


# Singleton instance
temporal_service = TemporalService()
