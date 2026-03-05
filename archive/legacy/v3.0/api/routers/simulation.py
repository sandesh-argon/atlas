"""
Simulation Router

Endpoints for instant and temporal simulations with timeout protection.
"""

import asyncio
import logging
from fastapi import APIRouter, HTTPException

from ..services import simulation_service
from ..models import (
    SimulationRequest,
    SimulationResponse,
    TemporalSimulationRequest,
    TemporalSimulationResponse
)
from ..config import SIMULATION_TIMEOUT, TEMPORAL_TIMEOUT

router = APIRouter(prefix="/simulate", tags=["simulation"])
logger = logging.getLogger("api.simulation")


@router.post("", response_model=SimulationResponse)
async def run_instant_simulation(request: SimulationRequest):
    """
    Run instant (single-timestep) simulation.

    Applies interventions and propagates effects through the causal graph
    until convergence. Returns immediate effects on all indicators.

    **Timeout:** 10 seconds
    **Rate Limit:** Subject to global rate limits (100/min, 1000/hr)

    Never cache - always compute fresh.
    """
    try:
        # Convert interventions to dict format
        interventions = [
            {
                'indicator': i.indicator,
                'change_percent': i.change_percent
            }
            for i in request.interventions
        ]

        # Run simulation with timeout
        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(
                    simulation_service.run_instant_simulation,
                    country=request.country,
                    interventions=interventions,
                    year=request.year
                ),
                timeout=SIMULATION_TIMEOUT
            )
        except asyncio.TimeoutError:
            logger.warning(f"Simulation timeout: {request.country} with {len(interventions)} interventions")
            raise HTTPException(
                status_code=504,
                detail={
                    "error": "simulation_timeout",
                    "message": f"Simulation exceeded {SIMULATION_TIMEOUT}s limit",
                    "suggestion": "Try reducing number of interventions"
                }
            )

        return SimulationResponse(**result)

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Simulation error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Simulation error: {str(e)}"
        )


@router.post("/temporal", response_model=TemporalSimulationResponse)
async def run_temporal_simulation(request: TemporalSimulationRequest):
    """
    Run temporal (multi-year) simulation with lag effects.

    Projects interventions forward through time, accounting for
    estimated lag effects between indicators. Returns year-by-year
    indicator values.

    **Timeout:** 15 seconds
    **Rate Limit:** Subject to global rate limits (100/min, 1000/hr)

    Never cache - always compute fresh.
    """
    try:
        # Convert interventions to dict format
        interventions = [
            {
                'indicator': i.indicator,
                'change_percent': i.change_percent
            }
            for i in request.interventions
        ]

        # Run temporal simulation with timeout
        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(
                    simulation_service.run_temporal_simulation,
                    country=request.country,
                    interventions=interventions,
                    horizon_years=request.horizon_years,
                    year=request.year,
                    use_significant_lags_only=request.use_significant_lags_only
                ),
                timeout=TEMPORAL_TIMEOUT
            )
        except asyncio.TimeoutError:
            logger.warning(
                f"Temporal simulation timeout: {request.country}, "
                f"horizon={request.horizon_years}, interventions={len(interventions)}"
            )
            raise HTTPException(
                status_code=504,
                detail={
                    "error": "temporal_simulation_timeout",
                    "message": f"Temporal simulation exceeded {TEMPORAL_TIMEOUT}s limit",
                    "suggestion": "Try reducing horizon_years or number of interventions"
                }
            )

        return TemporalSimulationResponse(**result)

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Temporal simulation error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Temporal simulation error: {str(e)}"
        )
