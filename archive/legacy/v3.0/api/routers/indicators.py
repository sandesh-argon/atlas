"""
Indicators Router

Endpoints for indicator metadata and lookups.
"""

from typing import Optional
from fastapi import APIRouter, HTTPException, Query

from ..services import indicator_service
from ..models import (
    IndicatorInfo,
    IndicatorListResponse,
    IndicatorDetailResponse
)

router = APIRouter(prefix="/indicators", tags=["indicators"])


@router.get("", response_model=IndicatorListResponse)
async def list_indicators(
    domain: Optional[str] = Query(None, description="Filter by domain"),
    search: Optional[str] = Query(None, description="Search by ID or label"),
    limit: int = Query(100, ge=1, le=1000, description="Max results")
):
    """
    Get list of all indicators.

    Optionally filter by domain or search by ID/label.
    This endpoint is cacheable client-side.
    """
    if search:
        # Search mode
        indicators = indicator_service.search_indicators(search, limit=limit)
    elif domain:
        # Filter by domain
        indicators = indicator_service.get_indicators_by_domain(domain)[:limit]
    else:
        # All indicators
        indicators = indicator_service.get_all_indicators()[:limit]

    return IndicatorListResponse(
        total=len(indicators),
        indicators=[IndicatorInfo(**i) for i in indicators]
    )


@router.get("/domains")
async def list_domains():
    """
    Get list of all indicator domains.

    Returns sorted list of domain names for filtering.
    """
    domains = indicator_service.get_domains()
    return {"domains": domains, "total": len(domains)}


@router.get("/{indicator_id}", response_model=IndicatorDetailResponse)
async def get_indicator_detail(indicator_id: str):
    """
    Get detailed indicator information.

    Returns full metadata for rich tooltips including:
    - Label and description
    - Domain and ring (hierarchy position)
    - SHAP importance score
    - In/out degree across all graphs
    - Data availability status

    This endpoint supports rich tooltips on indicator hover.
    """
    detail = indicator_service.get_indicator_detail(indicator_id)

    if detail is None:
        raise HTTPException(
            status_code=404,
            detail=f"Indicator '{indicator_id}' not found"
        )

    return IndicatorDetailResponse(**detail)
