"""
Graphs Router

Endpoints for country and regional graph data.
"""

from typing import Optional
from fastapi import APIRouter, HTTPException, Query

from ..services import graph_service
from ..models import GraphResponse
from ..config import ENABLE_REGIONAL_VIEW

router = APIRouter(prefix="/graph", tags=["graphs"])


@router.get("/region/{region}/timeline")
async def get_regional_timeline(
    region: str,
    start_year: Optional[int] = Query(None, description="Start year"),
    end_year: Optional[int] = Query(None, description="End year")
):
    """Get historical timeline of indicator values for a region (from baselines)."""
    if not ENABLE_REGIONAL_VIEW:
        raise HTTPException(status_code=403, detail="Regional views are disabled")

    if not graph_service.region_exists(region):
        raise HTTPException(status_code=404, detail=f"Region '{region}' not found")

    timeline = graph_service.get_regional_timeline(region, start_year, end_year)

    if not timeline['years']:
        raise HTTPException(status_code=404, detail=f"No timeline data found for region '{region}'")

    return {
        'country': None,
        'region': region,
        'start_year': timeline['years'][0] if timeline['years'] else None,
        'end_year': timeline['years'][-1] if timeline['years'] else None,
        'years': timeline['years'],
        'values': timeline['values'],
        'n_indicators': len(timeline['indicators'])
    }


@router.get("/region/{region}")
async def get_regional_graph(
    region: str,
    year: Optional[int] = Query(None, description="Baseline year for indicator values")
):
    """
    Get full graph data for a region.

    Returns all edges with coefficients, baseline values, and SHAP importance.
    """
    if not ENABLE_REGIONAL_VIEW:
        raise HTTPException(status_code=403, detail="Regional views are disabled")

    if not graph_service.region_exists(region):
        raise HTTPException(status_code=404, detail=f"Region '{region}' not found")

    graph = graph_service.get_regional_graph(region, year)
    if not graph:
        raise HTTPException(status_code=500, detail=f"Error loading graph for region '{region}'")

    graph_year = graph.get('year')
    baseline = graph_service.get_regional_baseline(region, graph_year)
    shap_importance = graph_service.get_regional_shap(region, graph_year)

    return {
        'country': region,  # compatibility with CountryGraph type on frontend
        'region': region,
        'n_edges': graph.get('n_edges', 0),
        'n_edges_with_data': graph.get('n_edges_with_data', 0),
        'edges': graph.get('edges', []),
        'baseline': baseline,
        'shap_importance': shap_importance,
        'metadata': {
            'year': graph_year,
            'is_regional': True,
            'has_lag_data': any('lag' in e for e in graph.get('edges', [])),
            'n_significant_lags': sum(
                1 for e in graph.get('edges', [])
                if e.get('lag_significant', False)
            ),
            'has_country_shap': len(shap_importance) > 0,
            'n_shap_indicators': len(shap_importance)
        }
    }


@router.get("/{country}/timeline")
async def get_country_timeline(
    country: str,
    start_year: Optional[int] = Query(None, description="Start year (default: 10 years before end)"),
    end_year: Optional[int] = Query(None, description="End year (default: most recent)")
):
    """
    Get historical timeline of indicator values for a country.

    Returns multi-year panel data for historical playback visualization.
    Default returns last 10 years of data.
    """
    if not graph_service.country_exists(country):
        raise HTTPException(
            status_code=404,
            detail=f"Country '{country}' not found"
        )

    timeline = graph_service.get_historical_timeline(country, start_year, end_year)

    if not timeline['years']:
        raise HTTPException(
            status_code=404,
            detail=f"No timeline data found for '{country}'"
        )

    return {
        'country': country,
        'start_year': timeline['years'][0] if timeline['years'] else None,
        'end_year': timeline['years'][-1] if timeline['years'] else None,
        'years': timeline['years'],
        'values': timeline['values'],
        'n_indicators': len(timeline['indicators'])
    }


@router.get("/{country}", response_model=GraphResponse)
async def get_country_graph(
    country: str,
    year: Optional[int] = Query(None, description="Baseline year for indicator values")
):
    """
    Get full graph data for a country.

    Returns all edges with coefficients, confidence intervals, and lag data.
    Also includes current baseline values for all indicators.

    Cache this per-session on client side.
    """
    # Verify country exists
    if not graph_service.country_exists(country):
        raise HTTPException(
            status_code=404,
            detail=f"Country '{country}' not found"
        )

    # Load graph (with year-specific data from V3.1)
    graph = graph_service.get_country_graph(country, year)
    if not graph:
        raise HTTPException(
            status_code=500,
            detail=f"Error loading graph for '{country}'"
        )

    # Get the actual year from the loaded graph
    graph_year = graph.get('year')

    # Get baseline values
    baseline = graph_service.get_baseline_values(country, graph_year)

    # Get country-specific SHAP importance for node sizing
    shap_importance = graph_service.get_country_shap(country, graph_year)

    return GraphResponse(
        country=country,
        n_edges=graph.get('n_edges', 0),
        n_edges_with_data=graph.get('n_edges_with_data', 0),
        edges=graph.get('edges', []),
        baseline=baseline,
        shap_importance=shap_importance,
        metadata={
            'year': graph_year,
            'has_lag_data': any('lag' in e for e in graph.get('edges', [])),
            'n_significant_lags': sum(
                1 for e in graph.get('edges', [])
                if e.get('lag_significant', False)
            ),
            'has_country_shap': len(shap_importance) > 0,
            'n_shap_indicators': len(shap_importance)
        }
    )
