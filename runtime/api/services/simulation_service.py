"""
Simulation Service

V3.1 simulation using pre-computed year-specific temporal graphs.

Features:
- Non-linear propagation (marginal effects)
- Ensemble uncertainty quantification
- Regional spillover effects
- Year-specific causal graphs (1990-2024)
"""

import sys
from pathlib import Path
from typing import Dict, List, Optional, Any, Literal

# Add viz/ root to path so `from simulation import ...` works
_VIZ_ROOT = str(Path(__file__).parent.parent.parent)
if _VIZ_ROOT not in sys.path:
    sys.path.insert(0, _VIZ_ROOT)

# V3.1 type aliases
ViewType = Literal['country', 'stratified', 'unified', 'regional']
SimulationMode = Literal['percentage', 'absolute']


class SimulationService:
    """Service for running instant and temporal simulations using V3.1."""

    def __init__(self):
        self._v31_simulation_runner = None
        self._v31_temporal_runner = None

    def _get_v31_simulation_runner(self):
        """Lazy load V3.1 instant simulation module."""
        if self._v31_simulation_runner is None:
            from simulation import run_simulation_v31
            self._v31_simulation_runner = run_simulation_v31
        return self._v31_simulation_runner

    def _get_v31_temporal_runner(self):
        """Lazy load V3.1 temporal simulation module."""
        if self._v31_temporal_runner is None:
            from simulation import run_temporal_simulation_v31
            self._v31_temporal_runner = run_temporal_simulation_v31
        return self._v31_temporal_runner

    def run_instant_simulation_v31(
        self,
        country: Optional[str],
        interventions: List[Dict[str, Any]],
        year: int,
        mode: SimulationMode = 'percentage',
        view_type: ViewType = 'country',
        region: Optional[str] = None,
        p_value_threshold: float = 0.05,
        use_nonlinear: bool = True,
        n_ensemble_runs: int = 0,
        include_spillovers: bool = True,
        top_n_effects: int = 20,
        debug: bool = False,
    ) -> Dict[str, Any]:
        """
        Run V3.1 instant simulation with year-specific graph.

        Args:
            country: Country name (optional for unified/regional)
            interventions: List of {"indicator": str, "change_percent": float}
            year: Year for graph and baseline (1990-2024)
            mode: 'percentage' (fast, no baselines) or 'absolute' (real values)
            view_type: 'country', 'stratified', 'unified', or 'regional'
            region: Region key when using regional view
            p_value_threshold: Filter edges by p-value
            use_nonlinear: Use marginal effects when available
            n_ensemble_runs: 0 = point estimate, >0 = bootstrap ensemble
            include_spillovers: Include regional spillover effects
            top_n_effects: Number of top effects to return

        Returns:
            V3.1 simulation results with effects, spillovers, and metadata
        """
        run_simulation = self._get_v31_simulation_runner()

        result = run_simulation(
            country=country,
            interventions=interventions,
            year=year,
            mode=mode,
            view_type=view_type,
            p_value_threshold=p_value_threshold,
            use_nonlinear=use_nonlinear,
            n_ensemble_runs=n_ensemble_runs,
            include_spillovers=include_spillovers,
            top_n_effects=top_n_effects,
            region=region,
            debug=debug,
        )

        # Check for simulation errors
        if result.get('status') == 'error':
            raise ValueError(result.get('message', 'V3.1 simulation failed'))

        return result

    def run_temporal_simulation_v31(
        self,
        country: Optional[str],
        interventions: List[Dict[str, Any]],
        base_year: int,
        horizon_years: int = 10,
        view_type: ViewType = 'country',
        region: Optional[str] = None,
        p_value_threshold: float = 0.05,
        use_nonlinear: bool = True,
        use_dynamic_graphs: bool = True,
        n_ensemble_runs: int = 0,
        include_spillovers: bool = True,
        top_n_effects: int = 20,
        debug: bool = False
    ) -> Dict[str, Any]:
        """
        Run V3.1 temporal simulation with year-by-year graphs.

        Key V3.1 feature: Loads a DIFFERENT graph for each projection year,
        capturing evolving causal relationships over time.

        Args:
            country: Country name
            interventions: List of {"indicator": str, "change_percent": float}
            base_year: Starting year (1990-2024)
            horizon_years: Years to project forward (1-30)
            view_type: Graph view type
            region: Region key when using regional view
            p_value_threshold: Edge significance filter
            use_nonlinear: Use marginal effects when available
            use_dynamic_graphs: Load year-specific graph for each year
            n_ensemble_runs: 0 = point estimate, >0 = bootstrap
            include_spillovers: Include regional spillovers for final year
            top_n_effects: Number of top effects per year

        Returns:
            Temporal simulation results with timeline, effects, and spillovers
        """
        run_temporal = self._get_v31_temporal_runner()

        # Inject per-intervention year into each intervention dict
        enriched_interventions = []
        for intv in interventions:
            enriched = dict(intv)
            # If intervention has a 'year' field, pass it as 'intervention_year'
            if 'year' in enriched and enriched['year'] is not None:
                enriched['intervention_year'] = enriched.pop('year')
            enriched_interventions.append(enriched)

        result = run_temporal(
            country=country,
            interventions=enriched_interventions,
            base_year=base_year,
            horizon_years=horizon_years,
            view_type=view_type,
            region=region,
            p_value_threshold=p_value_threshold,
            use_nonlinear=use_nonlinear,
            use_dynamic_graphs=use_dynamic_graphs,
            n_ensemble_runs=n_ensemble_runs,
            include_spillovers=include_spillovers,
            top_n_effects=top_n_effects,
            debug=debug,
        )

        # Check for simulation errors
        if result.get('status') == 'error':
            raise ValueError(result.get('message', 'V3.1 temporal simulation failed'))

        return result


# Singleton instance
simulation_service = SimulationService()
