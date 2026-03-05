"""
Request Models

Pydantic schemas for API request validation.
"""

from pydantic import BaseModel, Field, ConfigDict, model_validator
from typing import List, Optional


class InterventionInput(BaseModel):
    """Single intervention specification."""
    indicator: str = Field(..., description="Indicator ID to modify")
    change_percent: float = Field(
        ...,
        description="Percent change to apply (-100 to +1000)",
        ge=-100,
        le=1000
    )
    year: Optional[int] = Field(
        None,
        description="Year to apply this intervention (1990-2024). If None, uses request-level base_year.",
        ge=1990,
        le=2024
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "indicator": "v2elvotbuy",
                "change_percent": 20.0,
                "year": 2024
            }
        }
    )


# =============================================================================
# V3.1 Request Models - Year-specific temporal graphs
# =============================================================================

from typing import Literal

ViewType = Literal['country', 'stratified', 'unified', 'regional']
SimulationMode = Literal['percentage', 'absolute']


class SimulationRequestV31(BaseModel):
    """
    Request for V3.1 instant simulation with year-specific graphs.

    Uses pre-computed temporal causal graphs (4,768 files) with:
    - P-value filtering for statistical significance
    - Non-linear propagation using marginal effects
    - Optional ensemble uncertainty quantification
    - Regional spillover effects
    """
    country: Optional[str] = Field(None, description="Country name (e.g., 'Australia'), or null for unified")
    region: Optional[str] = Field(None, description="Region key for regional view (e.g., 'sub_saharan_africa')")
    interventions: List[InterventionInput] = Field(
        ...,
        description="List of interventions to apply",
        min_length=1,
        max_length=20
    )
    year: int = Field(
        ...,
        description="Year for graph and baseline data (1990-2024)",
        ge=1990,
        le=2024
    )
    mode: SimulationMode = Field(
        'percentage',
        description="Simulation mode: 'percentage' (fast, no baselines) or 'absolute' (includes real values)"
    )
    view_type: ViewType = Field(
        'country',
        description="Graph view type: 'country' (specific), 'stratified' (income group), 'unified' (global), 'regional' (region aggregate)"
    )
    p_value_threshold: float = Field(
        0.05,
        description="Filter edges by p-value (lower = stricter)",
        ge=0.001,
        le=0.10
    )
    use_nonlinear: bool = Field(
        True,
        description="Use non-linear marginal effects when available"
    )
    n_ensemble_runs: int = Field(
        0,
        description="Number of ensemble runs (0 = point estimate, 100 recommended for CIs)",
        ge=0,
        le=500
    )
    include_spillovers: bool = Field(
        True,
        description="Include regional spillover effects"
    )
    top_n_effects: int = Field(
        20,
        description="Number of top effects to return",
        ge=1,
        le=500
    )
    debug: bool = Field(
        False,
        description="Return debug diagnostics in metadata"
    )

    @model_validator(mode="after")
    def _validate_scope_requirements(self):
        if self.view_type in ("country", "stratified") and not self.country:
            raise ValueError(f"country is required for view_type='{self.view_type}'")
        if self.view_type == "regional" and not (self.region or self.country):
            raise ValueError("region or country is required for view_type='regional'")
        return self

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "country": "Australia",
                "interventions": [
                    {"indicator": "v2pehealth", "change_percent": 20}
                ],
                "year": 2020,
                "mode": "percentage",
                "view_type": "country",
                "p_value_threshold": 0.05,
                "use_nonlinear": True,
                "n_ensemble_runs": 0,
                "include_spillovers": True,
                "debug": False,
            }
        }
    )


class TemporalSimulationRequestV31(BaseModel):
    """
    Request for V3.1 temporal simulation with year-specific graphs.

    Projects interventions forward using DIFFERENT causal graphs
    for each year (evolving relationships over time).
    """
    country: Optional[str] = Field(None, description="Country name (e.g., 'Australia'), or null for unified")
    region: Optional[str] = Field(None, description="Region key for regional view (e.g., 'sub_saharan_africa')")
    interventions: List[InterventionInput] = Field(
        ...,
        description="List of interventions to apply",
        min_length=1,
        max_length=20
    )
    base_year: int = Field(
        ...,
        description="Starting year for simulation (1990-2024)",
        ge=1990,
        le=2024
    )
    horizon_years: int = Field(
        10,
        description="Years to project forward (1-40)",
        ge=1,
        le=40
    )
    view_type: ViewType = Field(
        'country',
        description="Graph view type: 'country', 'stratified', 'unified', or 'regional'"
    )
    p_value_threshold: float = Field(
        0.05,
        description="Filter edges by p-value",
        ge=0.001,
        le=0.10
    )
    use_nonlinear: bool = Field(
        True,
        description="Use non-linear marginal effects when available"
    )
    use_dynamic_graphs: bool = Field(
        True,
        description="Load year-specific graph for each projection year (V3.1 feature)"
    )
    n_ensemble_runs: int = Field(
        0,
        description="Number of ensemble runs (0 = point estimate)",
        ge=0,
        le=500
    )
    include_spillovers: bool = Field(
        True,
        description="Include regional spillover effects for final year"
    )
    top_n_effects: int = Field(
        20,
        description="Number of top effects per year",
        ge=1,
        le=500
    )
    debug: bool = Field(
        False,
        description="Return debug trace (saturation, clamp, graph fallback details)"
    )

    @model_validator(mode="after")
    def _validate_scope_requirements(self):
        if self.view_type in ("country", "stratified") and not self.country:
            raise ValueError(f"country is required for view_type='{self.view_type}'")
        if self.view_type == "regional" and not (self.region or self.country):
            raise ValueError("region or country is required for view_type='regional'")
        return self

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "country": "Australia",
                "interventions": [
                    {"indicator": "v2pehealth", "change_percent": 20}
                ],
                "base_year": 2015,
                "horizon_years": 10,
                "view_type": "country",
                "use_dynamic_graphs": True
            }
        }
    )
