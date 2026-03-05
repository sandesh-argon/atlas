"""
V3.1 Simulation Package

Pre-computed temporal simulation using year-specific causal graphs.

Features:
- Year-specific graph loading with fallback chain
- Non-linear propagation using marginal effects
- Regional spillover effects
- Ensemble uncertainty via bootstrap resampling
"""

from .graph_loader_v31 import (
    load_temporal_graph,
    build_adjacency_v31,
    get_available_years,
    get_available_countries,
    get_available_regions,
    get_all_indicators,
    get_edge_statistics,
)
from .income_classifier import (
    get_country_classification,
    get_stratum_for_country,
    get_countries_in_stratum,
    load_income_classifications,
    get_stratum_counts,
)
from .regional_spillovers import (
    load_regional_spillovers,
    get_country_region,
    get_spillover_coefficient,
    get_region_info,
    compute_regional_spillover,
    is_global_power,
)
from .region_mapping import (
    get_country_region_map,
    get_region_for_country,
    get_countries_in_region,
    get_all_region_keys,
    get_region_metadata,
    validate_region_mapping,
)
from .propagation_v31 import (
    propagate_intervention_v31,
    propagate_intervention_ensemble,
    get_marginal_effect,
    resample_edge_weights,
    compute_effects,
    get_top_effects,
)
from .simulation_runner_v31 import (
    run_simulation_v31,
    load_baseline_values,
    validate_country,
    format_simulation_results,
)
from .temporal_simulation_v31 import (
    run_temporal_simulation_v31,
    propagate_temporal_v31,
    format_temporal_results,
)

__all__ = [
    # Graph loading
    'load_temporal_graph',
    'build_adjacency_v31',
    'get_available_years',
    'get_available_countries',
    'get_available_regions',
    'get_all_indicators',
    'get_edge_statistics',
    # Income classification
    'get_country_classification',
    'get_stratum_for_country',
    'get_countries_in_stratum',
    'load_income_classifications',
    'get_stratum_counts',
    # Regional spillovers
    'load_regional_spillovers',
    'get_country_region',
    'get_spillover_coefficient',
    'get_region_info',
    'compute_regional_spillover',
    'is_global_power',
    # Region mapping
    'get_country_region_map',
    'get_region_for_country',
    'get_countries_in_region',
    'get_all_region_keys',
    'get_region_metadata',
    'validate_region_mapping',
    # Propagation
    'propagate_intervention_v31',
    'propagate_intervention_ensemble',
    'get_marginal_effect',
    'resample_edge_weights',
    'compute_effects',
    'get_top_effects',
    # Simulation runners
    'run_simulation_v31',
    'run_temporal_simulation_v31',
    'load_baseline_values',
    'validate_country',
    'format_simulation_results',
    'format_temporal_results',
    'propagate_temporal_v31',
]

__version__ = '3.1.0'
