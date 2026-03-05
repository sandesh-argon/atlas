"""
Map Router — QoL V1 score endpoints for choropleth world map.
"""

from fastapi import APIRouter, HTTPException, Query

from ..services.map_service import map_service

router = APIRouter(prefix="/map", tags=["map"])


@router.get("/qol-scores")
async def get_qol_scores(year: int = Query(2020)):
    """
    Get QoL V1 (HDI-calibrated) scores for all countries in a given year.

    Returns { year, definition_id, scale_min, scale_max, scores: { country: { qol, iso3 } } }
    """
    meta = map_service.get_qol_metadata()
    year_min = meta.get("year_min")
    year_max = meta.get("year_max")
    if year_min is not None and year_max is not None and not (year_min <= year <= year_max):
        raise HTTPException(
            status_code=400,
            detail=f"year must be between {year_min} and {year_max} for precomputed QoL scores"
        )

    scores = map_service.get_scores_for_year(year)
    return {
        "year": year,
        "definition_id": meta.get("definition_id", "unknown"),
        "year_min": year_min,
        "year_max": year_max,
        "scale_min": 0,
        "scale_max": 1,
        "calibrated_to": "undp_hdi",
        "scores": scores,
    }


@router.get("/qol-scores/all")
async def get_qol_scores_all():
    """
    Get QoL V1 scores for all countries across all years.

    Returns envelope with metadata + scores for frontend timeline scrubbing.
    """
    scores = map_service.get_all_scores()
    meta = map_service.get_qol_metadata()
    return {
        "definition_id": meta.get("definition_id", "unknown"),
        "year_min": meta.get("year_min"),
        "year_max": meta.get("year_max"),
        "scale_min": 0,
        "scale_max": 1,
        "calibrated_to": "undp_hdi",
        "scores": scores,
    }


@router.get("/gap-index/all")
async def get_gap_index_all():
    """
    Legacy endpoint: gap_index scores for all countries across all years.

    Returns { scores: { country: { iso3, by_year: { year: value } } } }
    """
    scores = map_service.get_gap_index_scores()
    return {"scores": scores}
