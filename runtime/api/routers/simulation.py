"""
Simulation Router

V3.1 endpoints for instant and temporal simulations with timeout protection.
Uses year-specific temporal graphs (4,768 pre-computed files).
"""

import asyncio
import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field

from ..services import simulation_service
from ..config import (
    DEFAULT_GRAPH_YEAR,
    SIMULATION_TIMEOUT as CONFIG_SIMULATION_TIMEOUT,
    TEMPORAL_TIMEOUT as CONFIG_TEMPORAL_TIMEOUT,
    ENABLE_REGIONAL_VIEW,
)
from ..models import (
    InterventionInput,
    SimulationRequestV31,
    SimulationResponseV31,
    TemporalSimulationRequestV31,
    TemporalSimulationResponseV31,
)

router = APIRouter(prefix="/simulate", tags=["simulation"])
logger = logging.getLogger("api.simulation")

# Timeouts (wired from environment-configured settings)
SIMULATION_TIMEOUT = CONFIG_SIMULATION_TIMEOUT
TEMPORAL_TIMEOUT = CONFIG_TEMPORAL_TIMEOUT


class LegacySimulationRequest(BaseModel):
    """Deprecated /api/simulate request model retained for compatibility."""
    country: str = Field(..., description="Country name")
    interventions: List[InterventionInput] = Field(..., min_length=1, max_length=20)
    year: Optional[int] = Field(
        None,
        ge=1990,
        le=2024,
        description="Optional simulation year. Defaults to latest available year."
    )


class LegacyTemporalSimulationRequest(BaseModel):
    """Deprecated /api/simulate/temporal request model retained for compatibility."""
    country: str = Field(..., description="Country name")
    interventions: List[InterventionInput] = Field(..., min_length=1, max_length=20)
    base_year: Optional[int] = Field(
        None,
        ge=1990,
        le=2024,
        description="Optional base year. Defaults to latest available year."
    )
    horizon_years: int = Field(
        10,
        ge=1,
        le=40,
        description="Projection horizon in years."
    )


def _set_deprecation_headers(response: Response, replacement_path: str) -> None:
    response.headers["Deprecation"] = "true"
    response.headers["X-API-Deprecated"] = "true"
    response.headers["Link"] = f"<{replacement_path}>; rel=\"successor-version\""

@router.post("/v31", response_model=SimulationResponseV31, tags=["simulation-v31"])
async def run_instant_simulation_v31(request: SimulationRequestV31):
    """
    Run V3.1 instant simulation with year-specific temporal graph.

    **V3.1 Features:**
    - Year-specific causal graphs (4,768 pre-computed files)
    - P-value filtering for statistical significance
    - Non-linear propagation using marginal effects
    - Optional ensemble uncertainty quantification
    - Regional spillover effects

    **Simulation Modes:**
    - `percentage` (default): Fast, no baseline loading (~<1s). Returns percent_change only.
    - `absolute`: Full baseline values from pre-computed JSON (~<2s). Returns baseline, simulated, absolute_change, percent_change.

    **View Types:**
    - `country`: Country-specific graph (most accurate)
    - `stratified`: Income-group graph (fallback if country unavailable)
    - `unified`: Global average graph (least specific)
    - `regional`: Region-level aggregate graph (feature-flagged)

    **Timeout:** 30 seconds (60s for ensemble runs)
    """
    try:
        if request.view_type == "regional" and not ENABLE_REGIONAL_VIEW:
            raise HTTPException(status_code=403, detail="Regional simulation view is disabled")

        interventions = [
            {
                'indicator': i.indicator,
                'change_percent': i.change_percent
            }
            for i in request.interventions
        ]

        # Adjust timeout based on ensemble runs
        timeout = SIMULATION_TIMEOUT
        if request.n_ensemble_runs > 0:
            # Add extra time for ensemble runs
            timeout = min(120, timeout + request.n_ensemble_runs // 10)

        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(
                    simulation_service.run_instant_simulation_v31,
                    country=request.country,
                    interventions=interventions,
                    year=request.year,
                    mode=request.mode,
                    view_type=request.view_type,
                    region=request.region,
                    p_value_threshold=request.p_value_threshold,
                    use_nonlinear=request.use_nonlinear,
                    n_ensemble_runs=request.n_ensemble_runs,
                    include_spillovers=request.include_spillovers,
                    top_n_effects=request.top_n_effects,
                    debug=request.debug,
                ),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            logger.warning(
                f"V3.1 simulation timeout: {request.country}, year={request.year}, "
                f"ensemble={request.n_ensemble_runs}"
            )
            raise HTTPException(
                status_code=504,
                detail={
                    "error": "v31_simulation_timeout",
                    "message": f"V3.1 simulation exceeded {timeout}s limit",
                    "suggestion": "Try reducing n_ensemble_runs or using view_type='unified'"
                }
            )

        return SimulationResponseV31(**result)

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"V3.1 simulation error: {e}")
        raise HTTPException(
            status_code=500,
            detail="Simulation failed due to an internal error"
        )


@router.post("/v31/temporal", response_model=TemporalSimulationResponseV31, tags=["simulation-v31"])
async def run_temporal_simulation_v31(request: TemporalSimulationRequestV31):
    """
    Run V3.1 temporal simulation with year-by-year graphs.

    **Key V3.1 Feature:** Uses a DIFFERENT causal graph for each projection year,
    capturing how causal relationships evolve over time.

    **Parameters:**
    - `use_dynamic_graphs`: If True (default), loads year-specific graph for each
      projection year. If False, uses base_year graph for all years (V3.0 behavior).
    - `view_type`: Graph source - 'country', 'stratified', 'unified', or 'regional'
    - `include_spillovers`: Add regional spillover effects for final year

    **Timeline Output:**
    Returns indicator values at each year from base_year to base_year + horizon_years.

    **Timeout:** 60 seconds (more for ensemble runs)
    """
    try:
        if request.view_type == "regional" and not ENABLE_REGIONAL_VIEW:
            raise HTTPException(status_code=403, detail="Regional simulation view is disabled")

        interventions = [
            {
                'indicator': i.indicator,
                'change_percent': i.change_percent,
                **(({'year': i.year} if i.year is not None else {}))
            }
            for i in request.interventions
        ]

        # Adjust timeout based on horizon and ensemble
        timeout = TEMPORAL_TIMEOUT
        if request.n_ensemble_runs > 0:
            timeout = min(180, timeout + request.n_ensemble_runs // 5)
        if request.horizon_years > 15:
            timeout += 30

        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(
                    simulation_service.run_temporal_simulation_v31,
                    country=request.country,
                    interventions=interventions,
                    base_year=request.base_year,
                    horizon_years=request.horizon_years,
                    view_type=request.view_type,
                    region=request.region,
                    p_value_threshold=request.p_value_threshold,
                    use_nonlinear=request.use_nonlinear,
                    use_dynamic_graphs=request.use_dynamic_graphs,
                    n_ensemble_runs=request.n_ensemble_runs,
                    include_spillovers=request.include_spillovers,
                    top_n_effects=request.top_n_effects,
                    debug=request.debug
                ),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            logger.warning(
                f"V3.1 temporal simulation timeout: {request.country}, "
                f"base_year={request.base_year}, horizon={request.horizon_years}"
            )
            raise HTTPException(
                status_code=504,
                detail={
                    "error": "v31_temporal_timeout",
                    "message": f"V3.1 temporal simulation exceeded {timeout}s limit",
                    "suggestion": "Try reducing horizon_years, n_ensemble_runs, or use view_type='unified'"
                }
            )

        return TemporalSimulationResponseV31(**result)

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"V3.1 temporal simulation error: {e}")
        raise HTTPException(
            status_code=500,
            detail="Temporal simulation failed due to an internal error"
        )


@router.post("", response_model=SimulationResponseV31, deprecated=True, tags=["simulation-compat"])
async def run_instant_simulation_legacy(
    request: LegacySimulationRequest,
    response: Response
):
    """
    Deprecated compatibility wrapper for /api/simulate.

    Adapts legacy payloads to canonical V3.1 instant simulation defaults:
    - mode=percentage
    - view_type=country
    - year defaults to latest available year
    """
    _set_deprecation_headers(response, "/api/simulate/v31")
    normalized = SimulationRequestV31(
        country=request.country,
        interventions=request.interventions,
        year=request.year or DEFAULT_GRAPH_YEAR,
        mode="percentage",
        view_type="country",
    )
    return await run_instant_simulation_v31(normalized)


@router.post("/temporal", response_model=TemporalSimulationResponseV31, deprecated=True, tags=["simulation-compat"])
async def run_temporal_simulation_legacy(
    request: LegacyTemporalSimulationRequest,
    response: Response
):
    """
    Deprecated compatibility wrapper for /api/simulate/temporal.

    Adapts legacy payloads to canonical V3.1 temporal simulation defaults:
    - view_type=country
    - base_year defaults to latest available year
    """
    _set_deprecation_headers(response, "/api/simulate/v31/temporal")
    normalized = TemporalSimulationRequestV31(
        country=request.country,
        interventions=request.interventions,
        base_year=request.base_year or DEFAULT_GRAPH_YEAR,
        horizon_years=request.horizon_years,
        view_type="country",
    )
    return await run_temporal_simulation_v31(normalized)
