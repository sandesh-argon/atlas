"""
Temporal Data Router

API endpoints for V3.1 temporal data:
- Temporal SHAP (importance over time)
- Temporal Graphs (beta coefficients over time)
- Development Clusters
"""

from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query

from ..services.temporal_service import temporal_service
from ..config import TEMPORAL_YEAR_MIN, TEMPORAL_YEAR_MAX, TEMPORAL_TARGETS, INCOME_STRATA, ENABLE_REGIONAL_VIEW

router = APIRouter(prefix="/api/temporal", tags=["Temporal Data"])


# ==================== Status Endpoint ====================

@router.get("/status")
async def get_temporal_data_status():
    """
    Get status of available V3.1 temporal data.

    Returns information about what data is available (mock vs real),
    how many countries have data, and available years/targets.
    """
    return temporal_service.get_data_status()


# ==================== SHAP Endpoints ====================

@router.get("/shap/targets")
async def get_available_targets():
    """Get list of available target outcomes for SHAP."""
    return {
        "targets": TEMPORAL_TARGETS,
        "default": "quality_of_life"
    }


@router.get("/shap/countries")
async def get_shap_countries():
    """Get list of countries with SHAP data available."""
    countries = temporal_service.get_available_shap_countries()
    return {
        "total": len(countries),
        "countries": countries
    }


@router.get("/shap/{target}/timeline")
async def get_unified_shap_timeline(
    target: str,
    start_year: Optional[int] = Query(None, ge=TEMPORAL_YEAR_MIN, le=TEMPORAL_YEAR_MAX),
    end_year: Optional[int] = Query(None, ge=TEMPORAL_YEAR_MIN, le=TEMPORAL_YEAR_MAX)
):
    """
    Get unified SHAP importance for all years (preload for timeline animation).

    - **target**: Target outcome
    - **start_year**: Optional start year (default: 1990)
    - **end_year**: Optional end year (default: 2024)

    Returns all years' SHAP in a single response for smooth client-side animation.
    """
    if target not in TEMPORAL_TARGETS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid target. Must be one of: {TEMPORAL_TARGETS}"
        )

    timeline = temporal_service.get_temporal_shap_timeline(None, target, start_year, end_year)

    if not timeline['years']:
        raise HTTPException(
            status_code=404,
            detail=f"No SHAP timeline data found for unified/{target}"
        )

    return timeline


@router.get("/shap/{target}/{year}")
async def get_unified_shap(
    target: str,
    year: int
):
    """
    Get unified (global) SHAP importance for a specific target and year.

    - **target**: Target outcome (quality_of_life, health, education, etc.)
    - **year**: Year (1990-2024)
    """
    if target not in TEMPORAL_TARGETS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid target. Must be one of: {TEMPORAL_TARGETS}"
        )

    if not TEMPORAL_YEAR_MIN <= year <= TEMPORAL_YEAR_MAX:
        raise HTTPException(
            status_code=400,
            detail=f"Year must be between {TEMPORAL_YEAR_MIN} and {TEMPORAL_YEAR_MAX}"
        )

    data = temporal_service.get_temporal_shap(None, target, year)
    if not data:
        raise HTTPException(
            status_code=404,
            detail=f"SHAP data not found for unified/{target}/{year}"
        )

    return data


@router.get("/shap/region/{region}/{target}/timeline")
async def get_regional_shap_timeline(
    region: str,
    target: str,
    start_year: Optional[int] = Query(None, ge=TEMPORAL_YEAR_MIN, le=TEMPORAL_YEAR_MAX),
    end_year: Optional[int] = Query(None, ge=TEMPORAL_YEAR_MIN, le=TEMPORAL_YEAR_MAX)
):
    """
    Get regional SHAP importance for all years (preload for timeline animation).

    - **region**: Region key (e.g., "sub_saharan_africa", "north_america")
    - **target**: Target outcome (quality_of_life, health, etc.)
    """
    if not ENABLE_REGIONAL_VIEW:
        raise HTTPException(status_code=403, detail="Regional views are disabled")

    if target not in TEMPORAL_TARGETS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid target. Must be one of: {TEMPORAL_TARGETS}"
        )

    timeline = temporal_service.get_regional_shap_timeline(region, target, start_year, end_year)

    if not timeline['years']:
        raise HTTPException(
            status_code=404,
            detail=f"No SHAP timeline data found for region {region}/{target}"
        )

    return timeline


@router.get("/shap/{country}/{target}/timeline")
async def get_country_shap_timeline(
    country: str,
    target: str,
    start_year: Optional[int] = Query(None, ge=TEMPORAL_YEAR_MIN, le=TEMPORAL_YEAR_MAX),
    end_year: Optional[int] = Query(None, ge=TEMPORAL_YEAR_MIN, le=TEMPORAL_YEAR_MAX)
):
    """
    Get country-specific SHAP importance for all years.

    Returns all years' SHAP in a single response for smooth client-side animation.
    """
    if target not in TEMPORAL_TARGETS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid target. Must be one of: {TEMPORAL_TARGETS}"
        )

    available = temporal_service.get_available_shap_countries()
    if country not in available:
        raise HTTPException(
            status_code=404,
            detail=f"Country '{country}' not found. Available: {available[:10]}..."
        )

    timeline = temporal_service.get_temporal_shap_timeline(country, target, start_year, end_year)

    if not timeline['years']:
        raise HTTPException(
            status_code=404,
            detail=f"No SHAP timeline data found for {country}/{target}"
        )

    return timeline


@router.get("/shap/{country}/{target}/{year}")
async def get_country_shap(
    country: str,
    target: str,
    year: int
):
    """
    Get country-specific SHAP importance for a specific target and year.

    - **country**: Country name (e.g., "United States", "Japan")
    - **target**: Target outcome
    - **year**: Year (1990-2024)
    """
    if target not in TEMPORAL_TARGETS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid target. Must be one of: {TEMPORAL_TARGETS}"
        )

    if not TEMPORAL_YEAR_MIN <= year <= TEMPORAL_YEAR_MAX:
        raise HTTPException(
            status_code=400,
            detail=f"Year must be between {TEMPORAL_YEAR_MIN} and {TEMPORAL_YEAR_MAX}"
        )

    available = temporal_service.get_available_shap_countries()
    if country not in available:
        raise HTTPException(
            status_code=404,
            detail=f"Country '{country}' not found. Available: {available[:10]}..."
        )

    data = temporal_service.get_temporal_shap(country, target, year)
    if not data:
        raise HTTPException(
            status_code=404,
            detail=f"SHAP data not found for {country}/{target}/{year}"
        )

    return data


# ==================== Stratified SHAP Endpoints ====================

@router.get("/shap/strata")
async def get_available_strata():
    """Get list of available income strata for stratified SHAP."""
    return {
        "strata": INCOME_STRATA,
        "descriptions": {
            "developing": "Low + Lower-middle income countries",
            "emerging": "Upper-middle income countries",
            "advanced": "High income countries"
        }
    }


@router.get("/shap/stratified/{stratum}/{target}/timeline")
async def get_stratified_shap_timeline(
    stratum: str,
    target: str,
    start_year: Optional[int] = Query(None, ge=TEMPORAL_YEAR_MIN, le=TEMPORAL_YEAR_MAX),
    end_year: Optional[int] = Query(None, ge=TEMPORAL_YEAR_MIN, le=TEMPORAL_YEAR_MAX)
):
    """
    Get stratified SHAP importance for all years (preload for timeline animation).

    - **stratum**: Income stratum (developing, emerging, advanced)
    - **target**: Target outcome (quality_of_life, health, etc.)
    - **start_year**: Optional start year (default: 1990)
    - **end_year**: Optional end year (default: 2024)

    Returns all years' SHAP with dynamic country membership per year.
    """
    if stratum not in INCOME_STRATA:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid stratum. Must be one of: {INCOME_STRATA}"
        )

    if target not in TEMPORAL_TARGETS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid target. Must be one of: {TEMPORAL_TARGETS}"
        )

    timeline = temporal_service.get_stratified_shap_timeline(stratum, target, start_year, end_year)

    if not timeline['years']:
        raise HTTPException(
            status_code=404,
            detail=f"No stratified SHAP data found for {stratum}/{target}"
        )

    return timeline


@router.get("/shap/stratified/{stratum}/{target}/{year}")
async def get_stratified_shap(
    stratum: str,
    target: str,
    year: int
):
    """
    Get stratified SHAP importance for a specific stratum/target/year.

    - **stratum**: Income stratum (developing, emerging, advanced)
    - **target**: Target outcome
    - **year**: Year (1990-2024)
    """
    if stratum not in INCOME_STRATA:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid stratum. Must be one of: {INCOME_STRATA}"
        )

    if target not in TEMPORAL_TARGETS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid target. Must be one of: {TEMPORAL_TARGETS}"
        )

    if not TEMPORAL_YEAR_MIN <= year <= TEMPORAL_YEAR_MAX:
        raise HTTPException(
            status_code=400,
            detail=f"Year must be between {TEMPORAL_YEAR_MIN} and {TEMPORAL_YEAR_MAX}"
        )

    data = temporal_service.get_stratified_shap(stratum, target, year)
    if not data:
        raise HTTPException(
            status_code=404,
            detail=f"Stratified SHAP data not found for {stratum}/{target}/{year}"
        )

    return data


# ==================== Income Classification Endpoints ====================

@router.get("/classifications")
async def get_all_income_classifications():
    """
    Get income classifications for all countries/years.

    Returns dynamic income group membership from 1990-2024.
    """
    classifications = temporal_service.get_income_classifications()
    return {
        "total_countries": len(classifications),
        "classifications": classifications
    }


@router.get("/classifications/{year}")
async def get_stratum_counts(year: int):
    """
    Get count of countries in each stratum for a specific year.

    - **year**: Year (1990-2024)

    Useful for tab badges showing how many countries are in each group.
    """
    if not TEMPORAL_YEAR_MIN <= year <= TEMPORAL_YEAR_MAX:
        raise HTTPException(
            status_code=400,
            detail=f"Year must be between {TEMPORAL_YEAR_MIN} and {TEMPORAL_YEAR_MAX}"
        )

    counts = temporal_service.get_stratum_counts(year)
    total = sum(counts.values())

    return {
        "year": year,
        "counts": counts,
        "total": total
    }


@router.get("/classifications/{country}/{year}")
async def get_country_classification(country: str, year: int):
    """
    Get income classification for a specific country/year.

    - **country**: Country name
    - **year**: Year (1990-2024)
    """
    if not TEMPORAL_YEAR_MIN <= year <= TEMPORAL_YEAR_MAX:
        raise HTTPException(
            status_code=400,
            detail=f"Year must be between {TEMPORAL_YEAR_MIN} and {TEMPORAL_YEAR_MAX}"
        )

    classification = temporal_service.get_country_income_classification(country, year)
    if not classification:
        raise HTTPException(
            status_code=404,
            detail=f"Classification not found for {country}/{year}"
        )

    return {
        "country": country,
        "year": year,
        "classification": classification
    }


# ==================== Stratum Distribution Endpoint ====================

@router.get("/distribution/{year}")
async def get_stratum_distribution(year: int):
    """
    Get detailed stratum distribution for a given year.

    - **year**: Year (1990-2024)

    Returns:
    - Distribution counts and percentages for each stratum
    - Full list of countries per stratum with GNI and positional info
    - Thresholds used for classification
    - Granular positioning (how close each country is to transitioning)
    """
    if not TEMPORAL_YEAR_MIN <= year <= TEMPORAL_YEAR_MAX:
        raise HTTPException(
            status_code=400,
            detail=f"Year must be between {TEMPORAL_YEAR_MIN} and {TEMPORAL_YEAR_MAX}"
        )

    distribution = temporal_service.get_stratum_distribution(year)
    return distribution


# ==================== Country Transition Endpoints ====================

@router.get("/transitions")
async def get_all_country_transitions():
    """
    Get income bracket transitions for all countries.

    Returns summary statistics and per-country transition history.
    A transition occurs when a country moves between income brackets
    (developing, emerging, advanced).
    """
    data = temporal_service.get_country_transitions()
    return data


@router.get("/transitions/{country}")
async def get_country_transition_history(country: str):
    """
    Get income bracket transition history for a specific country.

    - **country**: Country name

    Returns list of transitions with year, from/to stratum, and GNI at transition.
    """
    transition = temporal_service.get_country_transition(country)
    if not transition:
        # Country exists but has no transitions
        return {
            "country": country,
            "has_transitions": False,
            "transitions": []
        }

    return {
        "country": country,
        "has_transitions": True,
        **transition
    }


# ==================== Data Quality Endpoints ====================

@router.get("/data-quality")
async def get_data_quality_overview():
    """
    Get data quality overview and metadata.

    Returns thresholds and summary of data quality metrics.
    """
    data = temporal_service.get_country_data_quality()
    metadata = data.get('metadata', {})
    countries = data.get('countries', {})

    return {
        "metadata": metadata,
        "total_countries": len(countries),
        "countries_available": list(countries.keys())
    }


@router.get("/data-quality/unified")
async def get_unified_data_quality():
    """
    Get aggregated data quality for unified (all countries) view.

    Returns average coverage, observed, and imputed percentages
    across all 178 countries, plus per-year quality breakdown.
    """
    quality = temporal_service.get_unified_data_quality()
    return quality


@router.get("/data-quality/stratified/{stratum}")
async def get_stratified_data_quality(
    stratum: str,
    year: int = 2020
):
    """
    Get aggregated data quality for a specific income stratum.

    - **stratum**: Income stratum (developing, emerging, advanced)
    - **year**: Reference year for stratum membership (default 2020)

    Returns average coverage, observed, and imputed percentages
    across countries in that stratum, plus per-year quality breakdown.
    """
    if stratum not in INCOME_STRATA:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid stratum. Must be one of: {INCOME_STRATA}"
        )

    quality = temporal_service.get_stratified_data_quality(stratum, year)

    if not quality:
        raise HTTPException(
            status_code=404,
            detail=f"Data quality not found for stratum '{stratum}'"
        )

    return quality


@router.get("/data-quality/{country}")
async def get_country_data_quality(country: str):
    """
    Get data quality metrics for a specific country.

    - **country**: Country name

    Returns:
    - total_indicators: Total indicators with data
    - coverage_pct: Percentage of possible indicators covered
    - observed_pct: Percentage of data that is observed (not imputed)
    - imputed_pct: Percentage of data that is imputed
    - confidence: Overall confidence level (high/medium/low)
    - by_year: Per-year quality breakdown with quality labels (complete/partial/sparse)
    """
    quality = temporal_service.get_country_quality(country)

    if not quality:
        raise HTTPException(
            status_code=404,
            detail=f"Data quality not found for country '{country}'"
        )

    return {
        "country": country,
        **quality
    }


# ==================== Stratified Graph Endpoints ====================

@router.get("/graph/stratified/{stratum}/{year}")
async def get_stratified_graph(stratum: str, year: int):
    """
    Get stratified causal graph for a specific stratum/year.

    - **stratum**: Income stratum (developing, emerging, advanced)
    - **year**: Year (1990-2024)
    """
    if stratum not in INCOME_STRATA:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid stratum. Must be one of: {INCOME_STRATA}"
        )

    if not TEMPORAL_YEAR_MIN <= year <= TEMPORAL_YEAR_MAX:
        raise HTTPException(
            status_code=400,
            detail=f"Year must be between {TEMPORAL_YEAR_MIN} and {TEMPORAL_YEAR_MAX}"
        )

    data = temporal_service.get_stratified_graph(stratum, year)
    if not data:
        raise HTTPException(
            status_code=404,
            detail=f"Stratified graph not found for {stratum}/{year}"
        )

    return data


# ==================== Graph Endpoints ====================

@router.get("/graph/countries")
async def get_graph_countries():
    """Get list of countries with temporal graph data."""
    countries = temporal_service.get_available_graph_countries()
    return {
        "total": len(countries),
        "countries": countries
    }


@router.get("/graph/{year}")
async def get_unified_graph(year: int):
    """
    Get unified (global) causal graph for a specific year.

    - **year**: Year (1990-2024)
    """
    if not TEMPORAL_YEAR_MIN <= year <= TEMPORAL_YEAR_MAX:
        raise HTTPException(
            status_code=400,
            detail=f"Year must be between {TEMPORAL_YEAR_MIN} and {TEMPORAL_YEAR_MAX}"
        )

    data = temporal_service.get_temporal_graph(None, year)
    if not data:
        raise HTTPException(
            status_code=404,
            detail=f"Graph data not found for unified/{year}"
        )

    return data


# NOTE: /graph/{country}/years must be BEFORE /graph/{country}/{year} for FastAPI route matching
@router.get("/graph/{country}/years")
async def get_country_graph_years(country: str):
    """Get list of years with graph data for a specific country."""
    if country == "unified":
        years = temporal_service.get_temporal_graph_years(None)
    else:
        available = temporal_service.get_available_graph_countries()
        if country not in available:
            raise HTTPException(
                status_code=404,
                detail=f"Country '{country}' not found"
            )
        years = temporal_service.get_temporal_graph_years(country)

    return {
        "country": country,
        "years": years,
        "total": len(years)
    }


@router.get("/graph/{country}/{year}")
async def get_country_graph(country: str, year: int):
    """
    Get country-specific causal graph for a specific year.

    - **country**: Country name
    - **year**: Year (1990-2024)
    """
    if not TEMPORAL_YEAR_MIN <= year <= TEMPORAL_YEAR_MAX:
        raise HTTPException(
            status_code=400,
            detail=f"Year must be between {TEMPORAL_YEAR_MIN} and {TEMPORAL_YEAR_MAX}"
        )

    available = temporal_service.get_available_graph_countries()
    if country not in available:
        raise HTTPException(
            status_code=404,
            detail=f"Country '{country}' not found in temporal graphs"
        )

    data = temporal_service.get_temporal_graph(country, year)
    if not data:
        raise HTTPException(
            status_code=404,
            detail=f"Graph data not found for {country}/{year}"
        )

    return data


# ==================== Cluster Endpoints ====================

@router.get("/clusters/{year}")
async def get_unified_clusters(year: int):
    """
    Get unified development clusters for a specific year.

    - **year**: Year (1990-2024)
    """
    if not TEMPORAL_YEAR_MIN <= year <= TEMPORAL_YEAR_MAX:
        raise HTTPException(
            status_code=400,
            detail=f"Year must be between {TEMPORAL_YEAR_MIN} and {TEMPORAL_YEAR_MAX}"
        )

    data = temporal_service.get_clusters(None, year)
    if not data:
        raise HTTPException(
            status_code=404,
            detail=f"Cluster data not found for unified/{year}"
        )

    return data


@router.get("/clusters/{country}")
async def get_country_clusters(country: str):
    """
    Get development clusters for a specific country.

    Country clusters are computed from the most recent year with data.
    """
    data = temporal_service.get_clusters(country)
    if not data:
        raise HTTPException(
            status_code=404,
            detail=f"Cluster data not found for {country}"
        )

    return data
