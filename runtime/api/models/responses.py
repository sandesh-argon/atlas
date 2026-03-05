"""
Response Models

Pydantic schemas for API responses.
"""

from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any


# --- Country Models ---

class CountryInfo(BaseModel):
    """Basic country information."""
    name: str
    n_edges: int
    n_edges_with_data: int
    coverage: float = Field(..., description="Data coverage (0-1)")


class CountryListResponse(BaseModel):
    """Response for GET /api/countries."""
    total: int
    countries: List[CountryInfo]


# --- Graph Models ---

class EdgeInfo(BaseModel):
    """Single edge in a graph."""
    source: str
    target: str
    beta: float
    ci_lower: float
    ci_upper: float
    global_beta: float
    data_available: bool
    lag: Optional[int] = None
    lag_pvalue: Optional[float] = None
    lag_significant: Optional[bool] = None


class GraphResponse(BaseModel):
    """Response for GET /api/graph/{country}."""
    country: str
    n_edges: int
    n_edges_with_data: int
    edges: List[Dict[str, Any]]
    baseline: Dict[str, float] = Field(
        ...,
        description="Current indicator values"
    )
    shap_importance: Dict[str, float] = Field(
        default_factory=dict,
        description="Country-specific SHAP importance for node sizing (0-1 normalized)"
    )
    metadata: Dict[str, Any]


# --- Indicator Models ---

class IndicatorInfo(BaseModel):
    """Basic indicator information."""
    id: str
    label: Optional[str] = None
    domain: Optional[str] = None
    importance: Optional[float] = Field(None, description="SHAP importance score for sorting")


class IndicatorDetailResponse(BaseModel):
    """Response for GET /api/indicators/{id}."""
    id: str
    label: Optional[str] = None
    description: Optional[str] = None
    domain: Optional[str] = None
    ring: Optional[int] = None
    shap_importance: Optional[float] = None
    in_degree: Optional[int] = None
    out_degree: Optional[int] = None
    data_available: bool = True


class IndicatorListResponse(BaseModel):
    """Response for GET /api/indicators."""
    total: int
    indicators: List[IndicatorInfo]


# --- Metadata Models ---

class MetadataResponse(BaseModel):
    """Response for GET /api/metadata."""
    version: str
    total_countries: int
    total_indicators: int
    total_edges: int
    graphs_with_lags: int
    significant_lags: int


# --- Error Models ---

class ErrorResponse(BaseModel):
    """Error response schema."""
    error: str
    message: str
    details: Optional[Dict[str, Any]] = None


# =============================================================================
# V3.1 Response Models - Year-specific temporal graphs
# =============================================================================

class IncomeClassification(BaseModel):
    """Income classification for a country at a specific year."""
    group_4tier: Optional[str] = Field(None, description="World Bank 4-tier: Low/Lower-middle/Upper-middle/High")
    group_3tier: Optional[str] = Field(None, description="V3.1 3-tier: Developing/Emerging/Advanced")
    gni_per_capita: Optional[float] = Field(None, description="GNI per capita (Atlas method)")


class RegionInfo(BaseModel):
    """Regional spillover information."""
    region_key: Optional[str] = Field(None, description="Region identifier")
    name: Optional[str] = Field(None, description="Human-readable region name")
    spillover_strength: Optional[float] = Field(None, description="Regional spillover coefficient (0-1)")
    dominant_economy: Optional[str] = Field(None, description="Dominant economy in region")
    regional_leaders: Optional[List[str]] = Field(None, description="Regional economic leaders")


class SpilloverEffect(BaseModel):
    """Spillover effect for an indicator."""
    effect: float = Field(..., description="Spillover effect magnitude")
    spillover_strength: float = Field(..., description="Spillover coefficient used")
    direct_effect: float = Field(..., description="Original direct effect")
    region: Optional[str] = Field(None, description="Region (for regional spillovers)")


class SpilloverResults(BaseModel):
    """Regional and global spillover effects."""
    regional: Dict[str, SpilloverEffect] = Field(default_factory=dict)
    global_effects: Dict[str, SpilloverEffect] = Field(default_factory=dict, alias="global")
    region_info: Optional[RegionInfo] = None
    is_global_power: bool = Field(False, description="Whether country is a global power (USA, CHN, DEU)")


class EnsembleStats(BaseModel):
    """Ensemble simulation statistics."""
    n_runs: int = Field(..., description="Number of ensemble runs")
    converged_runs: int = Field(..., description="Number of runs that converged")
    convergence_rate: float = Field(..., description="Fraction of runs that converged")


class EffectDetailV31(BaseModel):
    """
    Details of effect on a single indicator (V3.1 with optional CIs).

    In percentage mode: only percent_change is populated.
    In absolute mode: all fields are populated.

    Near-zero baseline handling:
    - When |baseline| < eps, percent_change uses epsilon denominator
    - display_percent is always a stable number for UI display
    - near_zero_baseline flags when raw percent is unreliable
    """
    # Always present — raw or epsilon-based when near-zero
    percent_change: float

    # Display-safe percent (uses epsilon denominator when baseline ≈ 0)
    display_percent: Optional[float] = Field(None, description="Display-safe percent change (stable for near-zero baselines)")
    near_zero_baseline: Optional[bool] = Field(None, description="True when |baseline| < eps (percent is approximate)")

    # Only in absolute mode
    baseline: Optional[float] = Field(None, description="Baseline value (absolute mode only)")
    simulated: Optional[float] = Field(None, description="Simulated value (absolute mode only)")
    absolute_change: Optional[float] = Field(None, description="Absolute change (absolute mode only)")

    # Ensemble mode (optional)
    ci_lower: Optional[float] = Field(None, description="95% CI lower bound (if ensemble)")
    ci_upper: Optional[float] = Field(None, description="95% CI upper bound (if ensemble)")
    std: Optional[float] = Field(None, description="Standard deviation (if ensemble)")


class QoLDelta(BaseModel):
    """QoL summary for baseline vs simulated state."""
    baseline: float = Field(..., description="Baseline QoL score")
    simulated: float = Field(..., description="Simulated QoL score")
    delta: float = Field(..., description="Simulated - baseline QoL score")
    n_indicators: int = Field(..., description="Number of indicators used in QoL computation")
    n_domains: int = Field(..., description="Number of domains used in QoL computation")


class SimulationResponseV31(BaseModel):
    """
    Response for POST /api/simulate/v31.

    V3.1 instant simulation with year-specific graph, non-linear effects,
    regional spillovers, and optional ensemble uncertainty.
    """
    status: str
    mode: str = Field('percentage', description="Simulation mode: 'percentage' or 'absolute'")
    country: Optional[str] = Field(None, description="Country name or null for unified")
    base_year: int = Field(..., description="Year used for graph and baseline")
    view_type: str = Field(..., description="Requested view type")
    view_used: str = Field(..., description="Actual view used (may differ due to fallback)")
    scope_used: str = Field(..., description="Effective simulation scope used")
    region_used: Optional[str] = Field(None, description="Resolved region key for regional scope")
    income_classification: Optional[IncomeClassification] = Field(
        None, description="Country's income classification for this year"
    )
    interventions: List[Dict[str, Any]]
    effects: Dict[str, Any] = Field(
        ..., description="Effects with total_affected and top_effects"
    )
    propagation: Dict[str, Any] = Field(
        ..., description="Propagation metadata (iterations, converged)"
    )
    spillovers: Optional[SpilloverResults] = Field(
        None, description="Regional and global spillover effects"
    )
    ensemble: Optional[EnsembleStats] = Field(
        None, description="Ensemble statistics (if n_ensemble_runs > 0)"
    )
    qol: Optional[QoLDelta] = Field(
        None, description="QoL baseline/simulated/delta summary for this simulation"
    )
    warnings: Optional[List[str]] = Field(
        None, description="Adaptive-year and fallback warnings"
    )
    metadata: Dict[str, Any] = Field(
        ..., description="Additional metadata (n_edges, p_value_threshold, etc.)"
    )


class CausalPathEntry(BaseModel):
    """Causal path entry for a single affected indicator."""
    hop: int = Field(..., description="Distance from intervention node (0=intervention, 1=direct effect, etc.)")
    source: str = Field(..., description="Immediate causal parent node ID (highest |beta * source_change| contributor)")
    beta: float = Field(..., description="Beta coefficient on the edge from source to this node")


class TemporalSimulationResponseV31(BaseModel):
    """
    Response for POST /api/simulate/v31/temporal.

    V3.1 temporal simulation using year-by-year graphs.
    """
    status: str
    country: Optional[str] = Field(None, description="Country name or null for unified")
    base_year: int = Field(..., description="Starting year")
    horizon_years: int = Field(..., description="Years projected forward")
    view_type: str = Field(..., description="Requested view type")
    scope_used: str = Field(..., description="Effective simulation scope used")
    region_used: Optional[str] = Field(None, description="Resolved region key for regional scope")
    income_classification_evolution: Optional[Dict[int, IncomeClassification]] = Field(
        None, description="Income classification at each year"
    )
    interventions: List[Dict[str, Any]]
    timeline: Dict[int, Dict[str, float]] = Field(
        ..., description="Indicator values at each year"
    )
    effects: Dict[int, Dict[str, EffectDetailV31]] = Field(
        ..., description="Top effects at each year"
    )
    causal_paths: Optional[Dict[str, CausalPathEntry]] = Field(
        None,
        description="Causal path for each affected indicator: hop distance, immediate source, and edge beta. "
                    "First-write-wins (shortest path). Source selected by max |beta * source_percent_change|."
    )
    affected_per_year: Dict[int, int] = Field(
        ..., description="Number of affected indicators per year"
    )
    graphs_used: Dict[int, str] = Field(
        ..., description="Which graph view was used for each year"
    )
    risk_flags: Optional[List[str]] = Field(
        None,
        description="Risk flags: large_shock, extreme_shock, long_horizon, multiple_interventions, near_clamp_saturation"
    )
    simulation_stress_score: Optional[float] = Field(
        None,
        description="Fraction of effects hitting saturation or ±2σ clamp (0=relaxed, 1=all clamped)"
    )
    qol_timeline: Optional[Dict[int, QoLDelta]] = Field(
        None,
        description="QoL baseline/simulated/delta by year for temporal simulations"
    )
    warnings: Optional[List[str]] = Field(
        None, description="Warnings about graph fallbacks, missing data, risk flags, etc."
    )
    spillovers: Optional[Dict[str, Any]] = Field(
        None, description="Spillover effects for final year"
    )
    debug_trace: Optional[Dict[str, Any]] = Field(
        None, description="Debug trace (saturation, clamp, convergence details). Only present when debug=true."
    )
    metadata: Dict[str, Any] = Field(
        ..., description="Propagation and computation metadata"
    )
