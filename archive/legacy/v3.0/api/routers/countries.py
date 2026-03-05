"""
Countries Router

Endpoints for country listings.
"""

from fastapi import APIRouter, HTTPException

from ..services import graph_service
from ..models import CountryInfo, CountryListResponse

router = APIRouter(prefix="/countries", tags=["countries"])


@router.get("", response_model=CountryListResponse)
async def list_countries():
    """
    Get list of all available countries.

    Returns country names with graph metadata (edge counts, coverage).
    This endpoint is cacheable client-side.
    """
    countries = graph_service.get_available_countries()

    return CountryListResponse(
        total=len(countries),
        countries=[CountryInfo(**c) for c in countries]
    )
