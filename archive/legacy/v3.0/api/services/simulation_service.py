"""
Simulation Service

Wraps Phase B (instant) and Phase C (temporal) simulation logic.
"""

import sys
from pathlib import Path
from typing import Dict, List, Optional, Any

# Add simulation modules to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / 'scripts' / 'phaseB' / 'B3_simulation'))
sys.path.insert(0, str(PROJECT_ROOT / 'scripts' / 'phaseC' / 'C2_temporal_simulation'))

from .graph_service import graph_service
from ..config import GRAPHS_DIR, PANEL_PATH


class SimulationService:
    """Service for running instant and temporal simulations."""

    def __init__(self):
        self._simulation_runner = None
        self._temporal_runner = None

    def _get_simulation_runner(self):
        """Lazy load instant simulation module."""
        if self._simulation_runner is None:
            from simulation_runner import run_simulation
            self._simulation_runner = run_simulation
        return self._simulation_runner

    def _get_temporal_runner(self):
        """Lazy load temporal simulation module."""
        if self._temporal_runner is None:
            from temporal_simulation import run_temporal_simulation
            self._temporal_runner = run_temporal_simulation
        return self._temporal_runner

    def run_instant_simulation(
        self,
        country: str,
        interventions: List[Dict[str, Any]],
        year: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Run instant (single-timestep) simulation.

        Args:
            country: Country name
            interventions: List of {"indicator": str, "change_percent": float}
            year: Optional baseline year

        Returns:
            Simulation results with effects and metadata
        """
        # Verify country exists
        if not graph_service.country_exists(country):
            raise ValueError(f"Country '{country}' not found")

        # Get baseline values
        baseline = graph_service.get_baseline_values(country, year)
        if not baseline:
            raise ValueError(f"No baseline data for country '{country}'")

        # Load graph
        graph = graph_service.get_country_graph(country)
        if not graph:
            raise ValueError(f"Could not load graph for '{country}'")

        # Run simulation
        run_simulation = self._get_simulation_runner()
        result = run_simulation(
            country_code=country,
            interventions=interventions,
            graphs_dir=str(GRAPHS_DIR),
            panel_path=str(PANEL_PATH),
            year=year
        )

        # Format response
        return self._format_instant_result(country, interventions, result, baseline)

    def run_temporal_simulation(
        self,
        country: str,
        interventions: List[Dict[str, Any]],
        horizon_years: int = 10,
        year: Optional[int] = None,
        use_significant_lags_only: bool = False
    ) -> Dict[str, Any]:
        """
        Run temporal (multi-year) simulation with lag effects.

        Args:
            country: Country name
            interventions: List of {"indicator": str, "change_percent": float}
            horizon_years: Years to project forward (1-30)
            year: Optional baseline year
            use_significant_lags_only: Only use edges with significant lags

        Returns:
            Temporal simulation results with year-by-year effects
        """
        # Verify country exists
        if not graph_service.country_exists(country):
            raise ValueError(f"Country '{country}' not found")

        # Get baseline values
        baseline = graph_service.get_baseline_values(country, year)
        if not baseline:
            raise ValueError(f"No baseline data for country '{country}'")

        # Run temporal simulation
        run_temporal = self._get_temporal_runner()
        result = run_temporal(
            country_code=country,
            interventions=interventions,
            horizon_years=horizon_years,
            graphs_dir=str(GRAPHS_DIR),
            panel_path=str(PANEL_PATH),
            base_year=year,
            use_significant_lags_only=use_significant_lags_only
        )

        # Format response
        return self._format_temporal_result(
            country, interventions, horizon_years, result, baseline
        )

    def _format_instant_result(
        self,
        country: str,
        interventions: List[Dict[str, Any]],
        result: Dict[str, Any],
        baseline: Dict[str, float]
    ) -> Dict[str, Any]:
        """Format instant simulation result for API response."""
        # Extract effects from simulation result
        # run_simulation returns: effects.top_effects with pre-computed changes
        effects_data = result.get('effects', {})
        top_effects = effects_data.get('top_effects', {})

        # The top_effects already has the proper format with baseline, simulated, etc.
        effects = top_effects

        propagation = result.get('propagation', {})

        return {
            'status': 'success',
            'country': country,
            'interventions': interventions,
            'effects': effects,
            'propagation': {
                'n_affected': effects_data.get('total_affected', len(effects)),
                'iterations': propagation.get('iterations', 0),
                'converged': propagation.get('converged', True)
            }
        }

    def _format_temporal_result(
        self,
        country: str,
        interventions: List[Dict[str, Any]],
        horizon_years: int,
        result: Dict[str, Any],
        baseline: Dict[str, float]
    ) -> Dict[str, Any]:
        """Format temporal simulation result for API response."""
        # run_temporal_simulation returns timeline, effects, affected_per_year
        timeline = result.get('timeline', {})
        effects = result.get('effects', {})
        affected_per_year = result.get('affected_per_year', {})
        metadata = result.get('metadata', {})

        return {
            'status': 'success',
            'country': country,
            'horizon_years': horizon_years,
            'interventions': interventions,
            'timeline': timeline,
            'effects': effects,
            'affected_per_year': affected_per_year,
            'metadata': {
                'total_indicators': len(baseline),
                'n_edges': metadata.get('n_edges', 0),
                'use_significant_lags_only': metadata.get('use_significant_lags_only', False)
            }
        }


# Singleton instance
simulation_service = SimulationService()
