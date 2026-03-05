"""
V3.1 Temporal Simulation

Multi-year simulation with:
- Year-specific graph loading for each projection year
- Lag-aware propagation with proper standardized-to-raw unit conversion
- Multi-hop propagation within each year (iterative convergence)
- Dynamic income classification tracking
- Non-linear effects
- Optional ensemble uncertainty

Unit conversion note:
    Our betas are standardized coefficients (fit on z-scored data).
    A beta of 0.5 means "1 SD increase in X -> 0.5 SD increase in Y".
    To propagate in raw units:
        effect_raw = beta * (source_delta / source_std) * target_std
"""

from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Literal
from collections import defaultdict
import numpy as np

from .graph_loader_v31 import load_temporal_graph, build_adjacency_v31
from .income_classifier import get_country_classification, get_stratum_for_country
from .regional_spillovers import compute_regional_spillover, get_region_info
from .region_mapping import get_region_for_country
from .propagation_v31 import (
    propagate_intervention_v31,
    propagate_intervention_ensemble,
    compute_effects,
    get_top_effects,
    apply_saturation
)
from .simulation_runner_v31 import load_baseline_values, load_precomputed_baseline, BASELINE_DIR, _compute_qol_delta
from .indicator_stats import (
    get_country_indicator_stats,
    get_stratum_indicator_stats,
    get_regional_indicator_stats,
)

# Project paths
DATA_ROOT = Path(__file__).parent.parent / "data"

# Constants
MIN_YEAR = 1990
MAX_YEAR = 2024

# Clamp propagated effects to ±MAX_SIGMA_CLAMP temporal standard deviations.
# Effects beyond this threshold are outside the model's training distribution
# and should not be presented as confident predictions. 2σ covers ~95% of
# historically observed within-country variance for each indicator.
MAX_SIGMA_CLAMP = 2.0


def _clamp_to_sigma(
    raw_increment: float,
    indicator: str,
    country_stats: Dict[str, Dict[str, float]],
) -> float:
    """
    Clamp propagated raw increment to ±MAX_SIGMA_CLAMP * temporal_std.

    Any effect larger than 2σ of what the indicator has historically done
    within this country is outside the model's training distribution.
    """
    stat = country_stats.get(indicator, {})
    temporal_std = stat.get('std', 0.0)
    if temporal_std <= 0:
        return raw_increment  # No stats → can't clamp
    max_delta = MAX_SIGMA_CLAMP * temporal_std
    return float(np.clip(raw_increment, -max_delta, max_delta))


def _get_indicator_std(
    indicator: str,
    country_stats: Dict[str, Dict[str, float]],
    baseline_values: Optional[Dict[str, float]] = None
) -> float:
    """
    Get the correct std for unit conversion of a country-specific beta.

    Priority:
    1. Country temporal std (matches how betas were estimated)
    2. Absolute baseline value as scale proxy (for indicators missing from panel)
    3. 1.0 as last resort (effectively passes through raw beta)

    NEVER use cross-country std — it's 1000-5000x larger than within-country
    temporal std for developing countries, causing massive amplification.
    """
    stat = country_stats.get(indicator, {})
    temporal_std = stat.get('std', 0.0)
    if temporal_std > 0:
        return temporal_std

    # Fallback: use baseline value magnitude as scale proxy
    if baseline_values:
        base_val = abs(baseline_values.get(indicator, 0))
        if base_val > 0:
            return base_val

    return 1.0


# Type definitions
ViewType = Literal['country', 'stratified', 'unified', 'regional']


def propagate_temporal_v31(
    country: Optional[str],
    intervention: Optional[Dict[str, float]] = None,
    baseline_values: Dict[str, float] = None,
    base_year: int = 2024,
    horizon_years: int = 10,
    view_type: ViewType = 'country',
    region: Optional[str] = None,
    p_value_threshold: float = 0.05,
    use_nonlinear: bool = True,
    use_dynamic_graphs: bool = True,
    interventions_by_year: Optional[Dict[int, Dict[str, float]]] = None,
    max_iterations_per_year: int = 10,
    convergence_threshold: float = 0.001,
    debug: bool = False,
    resample_edges: bool = False,
    rng_seed: Optional[int] = None,
    uncertainty_multiplier: float = 1.0,
) -> dict:
    """
    Propagate intervention across multiple years using year-specific graphs.

    Uses proper unit conversion for standardized betas:
        effect_raw = beta * (source_delta / source_std) * target_std

    Within each year, iterates multi-hop until convergence (like instant
    simulation) so effects cascade through the full graph, not just one hop.

    Args:
        country: Country name (optional for unified/regional)
        intervention: {indicator: absolute_delta} — all applied at base_year (legacy)
        baseline_values: {indicator: baseline_value}
        base_year: Starting year (intervention year)
        horizon_years: Years to project forward
        view_type: Graph view type
        region: Region key for regional view
        p_value_threshold: Edge significance filter
        use_nonlinear: Use marginal effects
        use_dynamic_graphs: Load year-specific graph for each year
        interventions_by_year: {year: {indicator: absolute_delta}} — staggered interventions
        max_iterations_per_year: Max multi-hop iterations within each year
        convergence_threshold: Stop iterating when max delta change < this

    Returns:
        Dict with:
        - timeline: {year: {indicator: value}}
        - deltas: {year: {indicator: delta_from_baseline}}
        - graphs_used: {year: view_type_used}
        - converged_years: List of years that converged
    """
    rng = np.random.default_rng(rng_seed) if resample_edges else None

    def _maybe_resample_beta(edge: dict, beta: float) -> float:
        """Resample beta from edge std when ensemble mode is enabled."""
        if rng is None or beta == 0:
            return beta
        edge_std = edge.get('std', 0.0) or 0.0
        if edge_std <= 0:
            return beta
        return float(rng.normal(beta, edge_std * uncertainty_multiplier))

    timeline = {}
    deltas_timeline = {}
    graphs_used = {}
    converged_years = []
    warnings = []
    convergence_info = {}  # {year: {iterations, max_update, l1_norm}}

    # Causal path tracking: first-write-wins for shortest hop distance.
    # causal_paths[indicator] = {hop, source, beta}
    # source = immediate causal parent selected by max |beta * source_pct_change|
    causal_paths: Dict[str, dict] = {}

    # Debug trace: saturation/clamp events (only collected when debug=True)
    debug_trace = {
        'saturation_events': [],
        'clamp_events': [],
        'graph_fallbacks': [],
    } if debug else None

    # Build interventions_by_year from legacy param if not provided
    if interventions_by_year is None:
        interventions_by_year = {}
        if intervention:
            interventions_by_year[base_year] = intervention

    # Initialize year 0 (base year)
    current_values = dict(baseline_values) if baseline_values else {}
    current_deltas = defaultdict(float)

    # Apply interventions scheduled for the base year
    if base_year in interventions_by_year:
        for indicator, delta in interventions_by_year[base_year].items():
            # Seed causal path: intervention nodes are hop 0
            causal_paths[indicator] = {'hop': 0, 'source': indicator, 'beta': 0.0}

            base = baseline_values.get(indicator) if baseline_values else None
            if base is not None:
                new_val = base + delta
                saturated = apply_saturation(indicator, new_val, base)
                if debug_trace and saturated != new_val:
                    debug_trace['saturation_events'].append({
                        'year': base_year, 'indicator': indicator,
                        'proposed': new_val, 'clamped_to': saturated,
                        'baseline': base, 'source': 'intervention',
                    })
                current_values[indicator] = saturated
                current_deltas[indicator] = saturated - base
            else:
                # No baseline — record raw delta, track the indicator
                current_deltas[indicator] = delta

    timeline[base_year] = dict(current_values)
    deltas_timeline[base_year] = dict(current_deltas)

    # Track incremental changes per year in STANDARDIZED units.
    # Betas are within-country standardized coefficients:
    #   target_delta_std = beta * source_delta_std
    # We convert: intervention raw -> std at entry, std -> raw at exit.
    # Use temporal std that matches the graph level (country/stratum/unified).
    increments_std_timeline: Dict[int, Dict[str, float]] = {}

    # Load temporal stats matching the simulation level
    if view_type == 'country':
        country_stats = get_country_indicator_stats(country) if country else {}
    elif view_type == 'stratified':
        stratum = get_stratum_for_country(country, base_year)
        country_stats = get_stratum_indicator_stats(stratum) if stratum else {}
    elif view_type == 'regional':
        country_stats = get_regional_indicator_stats(region) if region else {}
    else:  # unified
        # Use median temporal std across ALL countries (same approach as stratum)
        country_stats = get_stratum_indicator_stats('unified')

    # Convert base year deltas to standardized units
    base_increments_std = {}
    for ind, delta in current_deltas.items():
        ind_std = _get_indicator_std(ind, country_stats, baseline_values)
        base_increments_std[ind] = delta / ind_std

    # ---- Multi-hop propagation for base year (lag=0 edges) ----
    # Without this, lag=0 edges from base-year interventions are never processed
    # because the year loop starts at offset=1.
    if base_increments_std:
        graph_year_base = min(MAX_YEAR, base_year)
        base_graph = load_temporal_graph(
            country=country,
            year=graph_year_base,
            view_type=view_type,
            p_value_threshold=p_value_threshold,
            region=region,
        )
        if base_graph is not None:
            base_adj = build_adjacency_v31(base_graph)
            view_used = base_graph.get('view_used', view_type)
            graphs_used[base_year] = view_used
            for warn in base_graph.get('warnings') or []:
                if warn not in warnings:
                    warnings.append(warn)
            if view_used != view_type:
                msg = f"Year {base_year}: requested '{view_type}', fell back to '{view_used}'"
                warnings.append(msg)
                if debug_trace:
                    debug_trace['graph_fallbacks'].append({
                        'year': base_year, 'requested': view_type,
                        'used': view_used,
                    })

            # Warn if intervention indicators have no outgoing edges in this year's graph
            for ind in base_increments_std:
                if ind in (interventions_by_year.get(base_year, {})):
                    out_edges = base_adj.get(ind, [])
                    if len(out_edges) == 0:
                        warnings.append(
                            f"'{ind}' has no outgoing causal edges in the {graph_year_base} "
                            f"temporal graph. Try a later base year (this indicator may not "
                            f"have been measured or connected in {graph_year_base})."
                        )

            changed_nodes_base = set(base_increments_std.keys())
            for _iter in range(max_iterations_per_year):
                new_impulses = defaultdict(float)
                # Track best contributor per target for causal_paths:
                # best_contributor[target] = (|contribution|, source, beta)
                best_contributor: Dict[str, tuple] = {}
                for source in changed_nodes_base:
                    inc_std = base_increments_std.get(source, 0)
                    if inc_std == 0:
                        continue
                    for edge in base_adj.get(source, []):
                        target = edge.get('target')
                        if target is None:
                            continue
                        if edge.get('lag', 1) > 0:
                            continue  # Only lag=0 for same-year multi-hop
                        beta = edge.get('beta', 0)
                        if use_nonlinear and edge.get('marginal_effects'):
                            beta = edge['marginal_effects'].get('p50', beta)
                        beta = _maybe_resample_beta(edge, beta)
                        if beta == 0:
                            continue
                        contribution = beta * inc_std
                        new_impulses[target] += contribution

                        # Track highest |contribution| source for path recording
                        abs_contrib = abs(contribution)
                        prev = best_contributor.get(target)
                        if prev is None or abs_contrib > prev[0]:
                            best_contributor[target] = (abs_contrib, source, beta)

                if not new_impulses:
                    break
                newly_changed = set()
                for target, effect_std in new_impulses.items():
                    if abs(effect_std) > convergence_threshold:
                        base_increments_std[target] = base_increments_std.get(target, 0) + effect_std
                        newly_changed.add(target)
                        # First-write-wins: only record path if not already known
                        if target not in causal_paths:
                            contrib = best_contributor.get(target)
                            if contrib:
                                src = contrib[1]
                                src_hop = causal_paths.get(src, {}).get('hop', 0)
                                causal_paths[target] = {
                                    'hop': src_hop + 1,
                                    'source': src,
                                    'beta': round(contrib[2], 6),
                                }
                if not newly_changed:
                    break
                changed_nodes_base = newly_changed

            # Convert new standardized increments to raw and apply
            for indicator, inc_std in base_increments_std.items():
                if indicator in current_deltas and current_deltas[indicator] != 0:
                    # Already applied as direct intervention — skip re-application
                    # but keep the std increment for lagged propagation
                    continue
                if inc_std == 0:
                    continue
                tgt_std = _get_indicator_std(indicator, country_stats, baseline_values)
                raw_delta = inc_std * tgt_std
                raw_delta_pre_clamp = raw_delta
                raw_delta = _clamp_to_sigma(raw_delta, indicator, country_stats)
                if debug_trace and raw_delta != raw_delta_pre_clamp:
                    debug_trace['clamp_events'].append({
                        'year': base_year, 'indicator': indicator,
                        'pre_clamp': raw_delta_pre_clamp, 'post_clamp': raw_delta,
                        'source': 'base_year_multihop',
                    })
                base = baseline_values.get(indicator) if baseline_values else None
                if base is not None:
                    new_val = base + raw_delta
                    saturated = apply_saturation(indicator, new_val, base)
                    if debug_trace and saturated != new_val:
                        debug_trace['saturation_events'].append({
                            'year': base_year, 'indicator': indicator,
                            'proposed': new_val, 'clamped_to': saturated,
                            'baseline': base, 'source': 'base_year_multihop',
                        })
                    actual_delta = saturated - base
                    current_values[indicator] = saturated
                    current_deltas[indicator] = actual_delta
                    # Update the std increment to reflect saturation
                    if tgt_std > 0:
                        base_increments_std[indicator] = actual_delta / tgt_std
                else:
                    current_deltas[indicator] = raw_delta

    increments_std_timeline[base_year] = base_increments_std
    # Update base year timeline with multi-hop effects
    timeline[base_year] = dict(current_values)
    deltas_timeline[base_year] = dict(current_deltas)

    # Propagate year by year
    for year_offset in range(1, horizon_years + 1):
        actual_year = base_year + year_offset

        # Clamp to data range
        graph_year = min(MAX_YEAR, actual_year)

        # Load graph for this year
        if use_dynamic_graphs:
            graph = load_temporal_graph(
                country=country,
                year=graph_year,
                view_type=view_type,
                p_value_threshold=p_value_threshold,
                region=region,
            )
        else:
            graph = load_temporal_graph(
                country=country,
                year=base_year,
                view_type=view_type,
                p_value_threshold=p_value_threshold,
                region=region,
            )

        if graph is None:
            timeline[actual_year] = dict(current_values)
            deltas_timeline[actual_year] = dict(current_deltas)
            increments_std_timeline[actual_year] = {}
            graphs_used[actual_year] = 'none'
            warnings.append(f"Year {actual_year}: no graph available")
            continue

        view_used = graph.get('view_used', view_type)
        graphs_used[actual_year] = view_used
        for warn in graph.get('warnings') or []:
            if warn not in warnings:
                warnings.append(warn)
        if view_used != view_type:
            msg = f"Year {actual_year}: requested '{view_type}', fell back to '{view_used}'"
            warnings.append(msg)
            if debug_trace:
                debug_trace['graph_fallbacks'].append({
                    'year': actual_year, 'requested': view_type,
                    'used': view_used,
                })
        adjacency = build_adjacency_v31(graph)

        # Year's increments in standardized units
        year_increments_std = defaultdict(float)

        # Track best contributor for lagged impulses arriving this year
        lagged_best_contributor: Dict[str, tuple] = {}

        # Inject any staggered interventions scheduled for this year
        if actual_year in interventions_by_year:
            for indicator, delta in interventions_by_year[actual_year].items():
                # Seed causal path for staggered intervention nodes
                if indicator not in causal_paths:
                    causal_paths[indicator] = {'hop': 0, 'source': indicator, 'beta': 0.0}

                base = baseline_values.get(indicator) if baseline_values else None
                if base is not None:
                    new_val = base + delta
                    saturated = apply_saturation(indicator, new_val, base)
                    new_delta = saturated - base
                    raw_increment = new_delta - current_deltas.get(indicator, 0)
                    current_values[indicator] = saturated
                    current_deltas[indicator] = new_delta
                else:
                    raw_increment = delta - current_deltas.get(indicator, 0)
                    current_deltas[indicator] = delta

                ind_std = _get_indicator_std(indicator, country_stats, baseline_values)
                year_increments_std[indicator] += raw_increment / ind_std

        # ---- Collect lagged impulses arriving this year ----
        # Use STANDARDIZED incremental changes from the source year.
        for source, edges in adjacency.items():
            for edge in edges:
                target = edge.get('target')
                if target is None:
                    continue

                lag = edge.get('lag', 1)
                source_year = actual_year - lag
                if source_year < base_year:
                    continue

                # Standardized increment from the lagged year
                source_inc_std = increments_std_timeline.get(source_year, {}).get(source, 0)
                if source_inc_std == 0:
                    continue

                if use_nonlinear and edge.get('marginal_effects'):
                    beta = edge['marginal_effects'].get('p50', edge.get('beta', 0))
                else:
                    beta = edge.get('beta', 0)
                beta = _maybe_resample_beta(edge, beta)

                if beta == 0:
                    continue

                contribution = beta * source_inc_std
                # In standardized space: target_delta_std = beta * source_delta_std
                # Betas naturally attenuate (|beta| < 1 typically), so propagation
                # is safe even for indicators missing from panel stats.
                year_increments_std[target] += contribution

                # Track highest |contribution| source for causal path (first-write-wins)
                if target not in causal_paths:
                    abs_contrib = abs(contribution)
                    prev = lagged_best_contributor.get(target)
                    if prev is None or abs_contrib > prev[0]:
                        lagged_best_contributor[target] = (abs_contrib, source, beta)

        # Commit lagged best contributors to causal_paths (first-write-wins)
        for target, (abs_c, src, beta_val) in lagged_best_contributor.items():
            if target not in causal_paths:
                src_hop = causal_paths.get(src, {}).get('hop', 0)
                causal_paths[target] = {
                    'hop': src_hop + 1,
                    'source': src,
                    'beta': round(beta_val, 6),
                }

        if not year_increments_std:
            timeline[actual_year] = dict(current_values)
            deltas_timeline[actual_year] = dict(current_deltas)
            increments_std_timeline[actual_year] = {}
            converged_years.append(actual_year)
            convergence_info[actual_year] = {'iterations': 0, 'max_update': 0.0, 'l1_norm': 0.0}
            continue

        # ---- Multi-hop within this year (lag=0 edges) ----
        changed_nodes = set(year_increments_std.keys())
        year_iterations = 0
        year_max_update = 0.0
        year_l1_norm = 0.0

        for iteration in range(1, max_iterations_per_year):
            new_impulses_std = defaultdict(float)
            multihop_best_contributor: Dict[str, tuple] = {}
            for source in changed_nodes:
                inc_std = year_increments_std.get(source, 0)
                if inc_std == 0:
                    continue

                for edge in adjacency.get(source, []):
                    target = edge.get('target')
                    if target is None:
                        continue
                    if edge.get('lag', 1) > 0:
                        continue  # Only same-year edges for multi-hop

                    if use_nonlinear and edge.get('marginal_effects'):
                        beta = edge['marginal_effects'].get('p50', edge.get('beta', 0))
                    else:
                        beta = edge.get('beta', 0)
                    beta = _maybe_resample_beta(edge, beta)

                    if beta == 0:
                        continue

                    contribution = beta * inc_std
                    new_impulses_std[target] += contribution

                    # Track highest |contribution| source for path recording
                    abs_contrib = abs(contribution)
                    prev = multihop_best_contributor.get(target)
                    if prev is None or abs_contrib > prev[0]:
                        multihop_best_contributor[target] = (abs_contrib, source, beta)

            if not new_impulses_std:
                year_iterations = iteration
                break

            max_change = 0.0
            l1_norm = 0.0
            newly_changed = set()
            for target, effect_std in new_impulses_std.items():
                l1_norm += abs(effect_std)
                if abs(effect_std) > convergence_threshold:
                    year_increments_std[target] = year_increments_std.get(target, 0) + effect_std
                    newly_changed.add(target)
                    max_change = max(max_change, abs(effect_std))
                    # First-write-wins: only record path if not already known
                    if target not in causal_paths:
                        contrib = multihop_best_contributor.get(target)
                        if contrib:
                            src = contrib[1]
                            src_hop = causal_paths.get(src, {}).get('hop', 0)
                            causal_paths[target] = {
                                'hop': src_hop + 1,
                                'source': src,
                                'beta': round(contrib[2], 6),
                            }

            year_iterations = iteration
            year_max_update = max_change
            year_l1_norm = l1_norm

            if max_change < convergence_threshold or not newly_changed:
                break
            changed_nodes = newly_changed

        convergence_info[actual_year] = {
            'iterations': year_iterations,
            'max_update': round(year_max_update, 6),
            'l1_norm': round(year_l1_norm, 6),
        }

        # ---- Convert standardized increments to raw and apply ----
        converged = True
        year_increments_std_final = {}

        for indicator, inc_std in year_increments_std.items():
            if inc_std == 0:
                continue

            # Convert from standardized to raw using country temporal std
            tgt_std = _get_indicator_std(indicator, country_stats, baseline_values)
            raw_increment = inc_std * tgt_std

            old_delta = current_deltas.get(indicator, 0)
            proposed_delta = old_delta + raw_increment

            # Clamp CUMULATIVE delta to ±2σ of target's historical variance.
            # Effects beyond 2σ are outside the model's training distribution.
            proposed_delta_pre_clamp = proposed_delta
            proposed_delta = _clamp_to_sigma(proposed_delta, indicator, country_stats)
            if debug_trace and proposed_delta != proposed_delta_pre_clamp:
                debug_trace['clamp_events'].append({
                    'year': actual_year, 'indicator': indicator,
                    'pre_clamp': round(proposed_delta_pre_clamp, 6),
                    'post_clamp': round(proposed_delta, 6),
                    'source': 'yearly_propagation',
                })

            base = baseline_values.get(indicator) if baseline_values else None
            if base is not None:
                new_val = base + proposed_delta
                saturated = apply_saturation(indicator, new_val, base)
                if debug_trace and saturated != new_val:
                    debug_trace['saturation_events'].append({
                        'year': actual_year, 'indicator': indicator,
                        'proposed': round(new_val, 6), 'clamped_to': round(saturated, 6),
                        'baseline': base, 'source': 'yearly_propagation',
                    })
                actual_delta = saturated - base
                current_values[indicator] = saturated
            else:
                actual_delta = proposed_delta

            if abs(actual_delta - old_delta) > convergence_threshold:
                converged = False

            current_deltas[indicator] = actual_delta

            # Record the actual standardized increment (may differ due to saturation)
            actual_raw_increment = actual_delta - old_delta
            year_increments_std_final[indicator] = actual_raw_increment / tgt_std

        if converged:
            converged_years.append(actual_year)

        timeline[actual_year] = dict(current_values)
        deltas_timeline[actual_year] = dict(current_deltas)
        increments_std_timeline[actual_year] = year_increments_std_final

    result = {
        'timeline': timeline,
        'deltas': deltas_timeline,
        'graphs_used': graphs_used,
        'converged_years': converged_years,
        'warnings': warnings if warnings else None,
        'convergence_info': convergence_info,
        'causal_paths': causal_paths,
    }
    if debug_trace is not None:
        result['debug_trace'] = debug_trace
    return result


def run_temporal_simulation_v31(
    country: Optional[str],
    interventions: List[dict],
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
    panel_path: Optional[Path] = None,
    debug: bool = False
) -> dict:
    """
    Run temporal simulation with year-by-year graphs.

    Args:
        country: Country name (optional for unified/regional)
        interventions: List of {indicator: str, change_percent: float}
        base_year: Intervention year
        horizon_years: Years to project forward (1-30)
        view_type: Graph view type
        region: Region key for regional view
        p_value_threshold: Edge significance filter
        use_nonlinear: Use marginal effects when available
        use_dynamic_graphs: Load year-specific graph for each projection year
        n_ensemble_runs: 0 = point estimate, >0 = bootstrap ensemble
        include_spillovers: Include regional spillover effects
        top_n_effects: Number of top effects per year
        panel_path: Override panel data path

    Returns:
        Dict with timeline, effects per year, metadata
    """
    try:
        region_used = region or (get_region_for_country(country) if country else None)

        if view_type in ('country', 'stratified') and not country:
            return {
                'status': 'error',
                'message': f"country is required for view_type='{view_type}'"
            }
        if view_type == 'regional' and not (region_used or country):
            return {
                'status': 'error',
                'message': "region or country is required for view_type='regional'"
            }

        # Load baseline — branch on view_type
        if view_type == 'stratified':
            stratum = get_stratum_for_country(country, base_year)
            if not stratum:
                return {
                    'status': 'error',
                    'message': f"Cannot determine income stratum for '{country}' in year {base_year}"
                }
            baseline = load_precomputed_baseline(
                country=f"stratified/{stratum}",
                year=base_year,
            )
            year_used = base_year
            percentiles = {}
            if not baseline:
                return {
                    'status': 'error',
                    'message': f"No stratified baseline for '{stratum}' in {base_year}. Run precompute_strata_baselines.py."
                }
        elif view_type == 'unified':
            baseline = load_precomputed_baseline(
                country="unified",
                year=base_year,
            )
            year_used = base_year
            percentiles = {}
            if not baseline:
                return {
                    'status': 'error',
                    'message': f"No unified baseline for {base_year}. Run precompute_strata_baselines.py."
                }
        elif view_type == 'regional':
            if not region_used:
                return {
                    'status': 'error',
                    'message': "Could not resolve region for regional simulation"
                }
            baseline = load_precomputed_baseline(
                country=f"regional/{region_used}",
                year=base_year,
            )
            year_used = base_year
            percentiles = {}
            if not baseline:
                return {
                    'status': 'error',
                    'message': f"No regional baseline for '{region_used}' in {base_year}. Run precompute_regional_baselines.py."
                }
        else:
            # Country-specific baseline
            baseline = load_precomputed_baseline(country, base_year)
            year_used = base_year
            percentiles = {}
            if not baseline:
                baseline, loaded_year, percentiles = load_baseline_values(country, base_year, panel_path)
                if loaded_year is not None:
                    year_used = int(loaded_year)
            if not baseline:
                return {
                    'status': 'error',
                    'message': f"No baseline data for '{country}' in year {base_year}"
                }

        # Convert interventions — group by year for staggered support
        interventions_by_year: Dict[int, Dict[str, float]] = defaultdict(dict)
        intervention_details = []

        for intv in interventions:
            indicator = intv.get('indicator')
            change_percent = intv.get('change_percent', 0)
            intervention_year = intv.get('intervention_year', base_year)

            if indicator not in baseline:
                intervention_details.append({
                    'indicator': indicator,
                    'change_percent': change_percent,
                    'intervention_year': intervention_year,
                    'status': 'skipped',
                    'reason': 'not_in_baseline'
                })
                continue

            base_val = baseline[indicator]
            delta = base_val * (change_percent / 100)
            interventions_by_year[intervention_year][indicator] = delta

            intervention_details.append({
                'indicator': indicator,
                'baseline': base_val,
                'change_percent': change_percent,
                'change_absolute': delta,
                'intervention_year': intervention_year,
                'status': 'applied'
            })

        if not interventions_by_year:
            return {
                'status': 'error',
                'message': 'No valid interventions'
            }

        # Compute effective base_year and horizon from staggered interventions
        all_intervention_years = list(interventions_by_year.keys())
        effective_base_year = min(all_intervention_years)
        max_intervention_year = max(all_intervention_years)
        # Ensure horizon covers from earliest intervention to latest + horizon_years
        effective_horizon = max(horizon_years, (max_intervention_year - effective_base_year) + horizon_years)

        def _run_single_temporal(seed: Optional[int], resample_edges: bool) -> dict:
            return propagate_temporal_v31(
                country=country,
                baseline_values=baseline,
                base_year=effective_base_year,
                horizon_years=effective_horizon,
                view_type=view_type,
                region=region_used,
                p_value_threshold=p_value_threshold,
                use_nonlinear=use_nonlinear,
                use_dynamic_graphs=use_dynamic_graphs,
                interventions_by_year=dict(interventions_by_year),
                debug=debug,
                resample_edges=resample_edges,
                rng_seed=seed,
                uncertainty_multiplier=1.0,
            )

        ensemble_runs: List[dict] = []
        if n_ensemble_runs > 0:
            for i in range(n_ensemble_runs):
                ensemble_runs.append(_run_single_temporal(seed=42 + i, resample_edges=True))

            # Aggregate timeline by median across runs.
            timeline_median: Dict[int, Dict[str, float]] = {}
            all_years = sorted({
                y for run in ensemble_runs for y in run.get('timeline', {}).keys()
            })
            for y in all_years:
                by_indicator: Dict[str, List[float]] = defaultdict(list)
                for run in ensemble_runs:
                    for ind, val in run.get('timeline', {}).get(y, {}).items():
                        by_indicator[ind].append(float(val))
                timeline_median[y] = {
                    ind: float(np.median(vals))
                    for ind, vals in by_indicator.items()
                    if vals
                }

            all_warnings: List[str] = []
            for run in ensemble_runs:
                all_warnings.extend(run.get('warnings') or [])

            graphs_used = ensemble_runs[0].get('graphs_used', {}) if ensemble_runs else {}
            causal_paths = ensemble_runs[0].get('causal_paths', {}) if ensemble_runs else {}

            convergence_info: Dict[int, dict] = {}
            for y in all_years:
                per_run_info = [r.get('convergence_info', {}).get(y, {}) for r in ensemble_runs]
                per_run_info = [x for x in per_run_info if x]
                if not per_run_info:
                    continue
                iterations = [float(x.get('iterations', 0)) for x in per_run_info]
                max_updates = [float(x.get('max_update', 0.0)) for x in per_run_info]
                l1_norms = [float(x.get('l1_norm', 0.0)) for x in per_run_info]
                convergence_info[y] = {
                    'iterations_mean': round(float(np.mean(iterations)), 3),
                    'max_update_mean': round(float(np.mean(max_updates)), 6),
                    'l1_norm_mean': round(float(np.mean(l1_norms)), 6),
                }

            converged_counts: Dict[int, int] = defaultdict(int)
            for run in ensemble_runs:
                for y in run.get('converged_years', []):
                    converged_counts[int(y)] += 1

            result = {
                'timeline': timeline_median,
                'deltas': {},  # not used downstream in API response
                'graphs_used': graphs_used,
                'converged_years': sorted([y for y, c in converged_counts.items() if c == n_ensemble_runs]),
                'warnings': list(dict.fromkeys(all_warnings)) or None,
                'convergence_info': convergence_info,
                'causal_paths': causal_paths,
            }
            if debug and ensemble_runs and ensemble_runs[0].get('debug_trace'):
                result['debug_trace'] = ensemble_runs[0]['debug_trace']
        else:
            result = _run_single_temporal(seed=None, resample_edges=False)

        # Load temporal stats for display-safe percent computation
        if view_type == 'country':
            country_stats = get_country_indicator_stats(country)
        elif view_type == 'stratified':
            stratum = get_stratum_for_country(country, base_year)
            country_stats = get_stratum_indicator_stats(stratum) if stratum else {}
        elif view_type == 'regional':
            country_stats = get_regional_indicator_stats(region_used) if region_used else {}
        else:  # unified
            country_stats = get_stratum_indicator_stats('unified')

        # Compute effects for each year (with near-zero baseline handling)
        effects_by_year = {}
        affected_per_year = {}

        for year, values in result['timeline'].items():
            year_effects = compute_effects(baseline, values, country_stats=country_stats)
            top = get_top_effects(year_effects, top_n=top_n_effects)

            if n_ensemble_runs > 0:
                # Attach uncertainty to top effects from ensemble sampled trajectories.
                for ind in list(top.keys()):
                    samples = []
                    for run in ensemble_runs:
                        value = run.get('timeline', {}).get(year, {}).get(ind)
                        if value is not None:
                            samples.append(float(value))
                    if len(samples) >= 2:
                        top[ind]['ci_lower'] = float(np.percentile(samples, 2.5))
                        top[ind]['ci_upper'] = float(np.percentile(samples, 97.5))
                        top[ind]['std'] = float(np.std(samples))

            effects_by_year[year] = top
            affected_per_year[year] = len([e for e in year_effects.values()
                                            if e.get('absolute_change', 0) != 0])

        # Track income classification evolution
        income_evolution = {}
        if view_type == 'country':
            for year in result['timeline'].keys():
                income_evolution[year] = get_country_classification(country, year) or {}
        elif view_type == 'stratified':
            stratum = get_stratum_for_country(country, base_year) or 'unknown'
            for year in result['timeline'].keys():
                income_evolution[year] = {'group_3tier': stratum.title()}
        # unified/regional: no income classification aggregate

        # ---- Risk flags & stress scoring ----
        risk_flags = []
        warnings = list(result.get('warnings') or [])

        # Check intervention magnitudes
        for intv in intervention_details:
            if intv.get('status') != 'applied':
                continue
            pct = abs(intv.get('change_percent', 0))
            if pct > 500:
                risk_flags.append('extreme_shock')
                warnings.append(
                    f"Intervention on '{intv['indicator']}' at {intv['change_percent']:+.0f}% "
                    f"is extreme (>500%). Results are extrapolation beyond training data."
                )
            elif pct > 200:
                risk_flags.append('large_shock')
                warnings.append(
                    f"Intervention on '{intv['indicator']}' at {intv['change_percent']:+.0f}% "
                    f"is large (>200%). Interpret with caution."
                )

        # Check horizon
        if effective_horizon > 15:
            risk_flags.append('long_horizon')
            warnings.append(
                f"Projection horizon of {effective_horizon} years is long. "
                f"Uncertainty compounds; later years are less reliable."
            )

        # Multiple interventions compound
        applied_count = sum(1 for i in intervention_details if i.get('status') == 'applied')
        if applied_count >= 3:
            risk_flags.append('multiple_interventions')

        # Stress score: fraction of final-year effects that hit saturation or ±2σ clamp
        final_year = effective_base_year + effective_horizon
        final_effects = effects_by_year.get(final_year, {})
        n_clamped = 0
        n_total = len(final_effects)
        for ind, eff in final_effects.items():
            base = eff.get('baseline', 0)
            sim = eff.get('simulated', 0)
            if base is None or sim is None:
                continue
            # Check if simulated value is at saturation boundary
            sat_val = apply_saturation(ind, sim, base)
            if sat_val != sim:
                n_clamped += 1
                continue
            # Check if delta is at ±2σ clamp
            stat = country_stats.get(ind, {})
            std = stat.get('std', 0.0)
            if std > 0:
                delta = abs(sim - base)
                if delta >= (MAX_SIGMA_CLAMP * std * 0.99):  # within 1% of clamp
                    n_clamped += 1
        if n_clamped > 0:
            risk_flags.append('near_clamp_saturation')
        stress_score = n_clamped / n_total if n_total > 0 else 0.0

        # Deduplicate risk flags
        risk_flags = list(dict.fromkeys(risk_flags))

        # Build response
        response = {
            'status': 'success',
            'country': country,
            'base_year': year_used or effective_base_year,
            'horizon_years': effective_horizon,
            'view_type': view_type,
            'scope_used': view_type,
            'region_used': region_used,
            'interventions': intervention_details,
            'timeline': result['timeline'],
            'effects': effects_by_year,
            'causal_paths': result.get('causal_paths', {}),
            'affected_per_year': affected_per_year,
            'graphs_used': result['graphs_used'],
            'income_classification_evolution': income_evolution,
            'risk_flags': risk_flags if risk_flags else None,
            'simulation_stress_score': round(stress_score, 3),
            'metadata': {
                'version': 'v3.1.3',
                'engine': 'temporal_propagation_v31',
                'intervention_persistence': 'step',
                'p_value_threshold': p_value_threshold,
                'use_nonlinear': use_nonlinear,
                'use_dynamic_graphs': use_dynamic_graphs,
                'converged_years': result['converged_years'],
                'convergence_info': result.get('convergence_info', {}),
                'timestamp': datetime.now().isoformat(),
                'ensemble': {
                    'enabled': n_ensemble_runs > 0,
                    'n_runs': n_ensemble_runs,
                    'seed_start': 42 if n_ensemble_runs > 0 else None,
                }
            }
        }

        # Compute QoL timeline
        try:
            qol_timeline: Dict = {}
            for year, sim_values in result['timeline'].items():
                year_int = int(year)
                baseline_for_year = baseline

                if view_type == 'stratified':
                    stratum_year = get_stratum_for_country(country, year_int) if country else None
                    if stratum_year:
                        loaded = load_precomputed_baseline(
                            country=f"stratified/{stratum_year}",
                            year=year_int,
                        )
                        if loaded:
                            baseline_for_year = loaded
                elif view_type == 'unified':
                    loaded = load_precomputed_baseline(
                        country="unified",
                        year=year_int,
                    )
                    if loaded:
                        baseline_for_year = loaded
                elif view_type == 'regional':
                    region_year = region_used or (get_region_for_country(country) if country else None)
                    if region_year:
                        loaded = load_precomputed_baseline(
                            country=f"regional/{region_year}",
                            year=year_int,
                        )
                        if loaded:
                            baseline_for_year = loaded
                elif country:
                    loaded = load_precomputed_baseline(country, year_int)
                    if loaded:
                        baseline_for_year = loaded
                    else:
                        loaded_fallback, _, _ = load_baseline_values(country, year_int, panel_path)
                        if loaded_fallback:
                            baseline_for_year = loaded_fallback

                qol = _compute_qol_delta(baseline_for_year, sim_values, year_int)
                if qol is not None:
                    qol_timeline[year_int] = qol
            if qol_timeline:
                response['qol_timeline'] = qol_timeline
        except Exception:
            pass  # QoL is non-critical

        # Include all warnings (graph fallbacks + risk + stress)
        if warnings:
            response['warnings'] = warnings

        # Include debug trace when requested
        if result.get('debug_trace'):
            response['debug_trace'] = result['debug_trace']

        # Add spillovers for final year if enabled (country-level only)
        if include_spillovers and view_type == 'country' and country:
            final_year = effective_base_year + effective_horizon
            final_effects = effects_by_year.get(final_year, {})
            abs_effects = {ind: eff.get('absolute_change', 0) for ind, eff in final_effects.items()}
            spillovers = compute_regional_spillover(country, abs_effects)

            response['spillovers'] = {
                'final_year': final_year,
                'regional': spillovers.get('regional', {}),
                'global': spillovers.get('global', {}),
                'region_info': get_region_info(country)
            }

        return response

    except Exception as e:
        return {
            'status': 'error',
            'message': str(e)
        }


def compute_temporal_effects(
    baseline_values: Dict[str, float],
    timeline: Dict[int, Dict[str, float]],
    top_n: int = 20
) -> Dict[int, Dict[str, dict]]:
    """
    Compute top effects for each year in timeline.

    Returns:
        {year: {indicator: {baseline, value, absolute_change, percent_change}}}
    """
    result = {}
    for year, values in timeline.items():
        effects = compute_effects(baseline_values, values)
        result[year] = get_top_effects(effects, top_n=top_n)
    return result


def format_temporal_results(result: dict) -> str:
    """Format temporal simulation results for CLI display."""
    if result.get('status') == 'error':
        return f"Error: {result.get('message', 'Unknown error')}"

    lines = [
        f"\n{'='*60}",
        f"Temporal Simulation: {result['country']}",
        f"Base Year: {result['base_year']} → {result['base_year'] + result['horizon_years']}",
        f"{'='*60}",
        f"\nInterventions:"
    ]

    for intv in result.get('interventions', []):
        status = "✓" if intv['status'] == 'applied' else "✗"
        lines.append(f"  {status} {intv['indicator']}: {intv.get('change_percent', 0):+.1f}%")

    lines.append(f"\nEffects over time:")
    for year in sorted(result.get('affected_per_year', {}).keys()):
        affected = result['affected_per_year'][year]
        view = result.get('graphs_used', {}).get(year, 'N/A')
        lines.append(f"  Year {year}: {affected} indicators affected (graph: {view})")

    # Show final year top effects
    final_year = result['base_year'] + result['horizon_years']
    if final_year in result.get('effects', {}):
        lines.append(f"\nTop Effects at Year {final_year}:")
        for ind, eff in list(result['effects'][final_year].items())[:5]:
            pct = eff.get('percent_change', 0)
            lines.append(f"  {ind}: {pct:+.2f}%")

    if result.get('spillovers', {}).get('region_info'):
        ri = result['spillovers']['region_info']
        lines.append(f"\nRegional Spillovers ({ri.get('name')}):")
        lines.append(f"  Strength: {ri.get('spillover_strength', 0):.0%}")

    lines.append(f"\n{'='*60}\n")
    return "\n".join(lines)


# =============================================================================
# CLI
# =============================================================================

def _run_tests():
    """Run basic tests."""
    print("\nRunning temporal simulation tests...")
    print("-" * 40)

    from .graph_loader_v31 import get_available_countries

    countries = get_available_countries()
    print(f"  Available countries: {len(countries)}")

    if countries:
        test_country = 'Australia' if 'Australia' in countries else countries[0]
        result = run_temporal_simulation_v31(
            country=test_country,
            interventions=[{'indicator': 'v2pehealth', 'change_percent': 20}],
            base_year=2015,
            horizon_years=5,
            use_dynamic_graphs=True
        )

        if result['status'] == 'success':
            print(f"  Temporal simulation test: SUCCESS")
            print(f"    Country: {result['country']}")
            print(f"    Years: {result['base_year']} to {result['base_year'] + result['horizon_years']}")
            print(f"    Graphs used: {list(result['graphs_used'].values())[:3]}...")
        else:
            print(f"  Temporal simulation test: {result.get('message', 'FAILED')}")

    print("-" * 40)
    print("Temporal simulation tests completed\n")


if __name__ == "__main__":
    _run_tests()
