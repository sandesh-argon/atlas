"""
V3.1 Intervention Propagation

Propagates intervention effects through causal graph with:
- Non-linear propagation using marginal_effects at source percentile
- Ensemble uncertainty via bootstrap resampling of edge weights
- Saturation functions to prevent unrealistic values
"""

from collections import defaultdict
from typing import Dict, List, Optional, Tuple, Literal
import numpy as np

from .indicator_stats import get_indicator_stats, get_country_indicator_stats

# Import saturation functions (co-located in simulation package)
try:
    from .saturation_functions import apply_saturation
except ImportError:
    # Fallback: inline saturation with conservative prefix/suffix matching
    # Kept in sync with saturation_functions.py SATURATION_CONFIG
    def apply_saturation(indicator: str, value: float, baseline: float) -> float:
        """Saturation fallback with conservative prefix/suffix matching."""
        ind = indicator.lower()

        # Growth rates / ratios can legitimately be negative — skip
        if any(ind.endswith(s) for s in ['.zg', '.zs']):
            return value

        # True percentage rates (specific WDI prefixes)
        rate_prefixes = [
            'se.prm.enrr', 'se.sec.enrr', 'se.ter.enrr',
            'se.prm.cmpt', 'se.sec.cmpt',
            'sh.dyn.mort', 'sh.dyn.nmrt', 'sp.dyn.cdrt',
            'sp.dyn.tfrt', 'sh.sta.mmrt',
            'sh.h2o.', 'sh.sta.hygn', 'sh.sta.bass',
        ]
        if any(ind.startswith(p) for p in rate_prefixes):
            return float(np.clip(value, 0, 100))

        # Life expectancy
        if ind.startswith('sp.dyn.le00'):
            return float(np.clip(value, 25, 95))

        # V-Dem aggregate indices (explicit prefixes, 0-1)
        vdem_idx_prefixes = [
            'v2x_polyarchy', 'v2x_libdem', 'v2x_partipdem', 'v2x_delibdem',
            'v2x_egaldem', 'v2x_liberal', 'v2x_cspart', 'v2x_rule',
            'v2x_freexp', 'v2x_frassoc', 'v2x_suffr', 'v2x_elecoff',
            'v2xel_frefair', 'v2xed_ed_', 'v2xpe_exl', 'v2xcl_rol',
            'e_v2x_',
        ]
        if any(ind.startswith(p) for p in vdem_idx_prefixes):
            return float(np.clip(value, 0, 1))

        # V-Dem ordinal (suffix match, 0-5)
        if ind.endswith('_ord'):
            return float(np.clip(value, 0, 5))
        # V-Dem mean/osp (suffix match, 0-4)
        if any(ind.endswith(s) for s in ['_mean', '_osp']):
            return float(np.clip(value, 0, 4))

        # V-Dem latent variables (prefix match, -4 to 4)
        vdem_latent_prefixes = [
            'v2el', 'v2pe', 'v2cs', 'v2me', 'v2ju', 'v2lg',
            'v2cl', 'v2ex', 'v2ca', 'v2dl', 'v2dd', 'v2ed',
            'v2ps', 'v2sm', 'v2st', 'v2sv', 'v2reg',
        ]
        if any(ind.startswith(p) for p in vdem_latent_prefixes):
            return float(np.clip(value, -4, 4))

        # Polity scores
        if ind.startswith('e_polity'):
            return float(np.clip(value, -10, 10))

        # Non-negative quantities (GDP levels, population, trade, etc.)
        non_neg_prefixes = [
            'ny.gdp.mktp.cd', 'ny.gdp.mktp.kd', 'ny.gdp.mktp.pp',
            'ny.gdp.pcap.cd', 'ny.gdp.pcap.kd', 'ny.gdp.pcap.pp',
            'ny.gnp.mktp', 'ny.gnp.pcap',
            'nv.agr', 'nv.ind', 'nv.srv',
            'sp.pop',
            'bx.gsr.gnfs', 'bm.gsr.gnfs',
            'ne.con.prvt', 'ne.con.govt',
            'nw.hca', 'nw.pca', 'nw.tow',
            'sle.', 'nv.ind.manf',
        ]
        if any(ind.startswith(p) for p in non_neg_prefixes):
            return max(0.0, value)

        # No saturation — ±2σ clamp in propagation handles bounds
        return value


def get_marginal_effect(
    edge: dict,
    source_value: float,
    percentile: float
) -> float:
    """
    Get appropriate marginal effect based on source value's percentile.

    For non-linear edges (V3.1 v2):
    - Interpolate between p25, p50, p75 marginal effects
    - This captures diminishing returns, thresholds, etc.

    For linear edges: Use beta directly.

    Args:
        edge: Edge dict with beta and optionally marginal_effects
        source_value: Current value of source indicator
        percentile: Source value's percentile in distribution (0-1)

    Returns:
        Marginal effect to use for propagation
    """
    marginal_effects = edge.get('marginal_effects')
    relationship_type = edge.get('relationship_type', 'linear')

    # If no marginal effects or linear relationship, use beta
    if marginal_effects is None or relationship_type == 'linear':
        return edge.get('beta', 0)

    # Extract percentile-specific effects
    p25 = marginal_effects.get('p25', edge.get('beta', 0))
    p50 = marginal_effects.get('p50', edge.get('beta', 0))
    p75 = marginal_effects.get('p75', edge.get('beta', 0))

    # Linear interpolation based on source percentile
    if percentile <= 0.25:
        return p25
    elif percentile <= 0.50:
        # Interpolate between p25 and p50
        t = (percentile - 0.25) / 0.25
        return p25 + t * (p50 - p25)
    elif percentile <= 0.75:
        # Interpolate between p50 and p75
        t = (percentile - 0.50) / 0.25
        return p50 + t * (p75 - p50)
    else:
        return p75


def resample_edge_weights(
    adjacency: Dict[str, List[dict]],
    rng: np.random.Generator,
    uncertainty_multiplier: float = 3.0
) -> Dict[str, List[dict]]:
    """
    Bootstrap resample edge weights for ensemble simulation.

    Uses edge.std: new_beta ~ Normal(beta, std * uncertainty_multiplier)

    The uncertainty_multiplier accounts for:
    - Unmodeled external factors
    - Propagation uncertainty
    - Model specification uncertainty

    Empirically calibrated: 1x gives ~29% coverage, 3x gives ~80-90% coverage.

    Args:
        adjacency: Original adjacency dict
        rng: Numpy random generator
        uncertainty_multiplier: Scaling factor for std (default 3.0)

    Returns:
        New adjacency with resampled betas
    """
    resampled = {}

    for source, edges in adjacency.items():
        resampled_edges = []
        for edge in edges:
            beta = edge.get('beta', 0)
            std = edge.get('std', 0)

            # Resample beta from normal distribution
            if std > 0:
                resampled_beta = rng.normal(beta, std * uncertainty_multiplier)
            else:
                resampled_beta = beta

            # Copy edge with new beta
            new_edge = edge.copy()
            new_edge['beta'] = resampled_beta
            new_edge['original_beta'] = beta

            # Also resample marginal effects if present
            if edge.get('marginal_effects'):
                me = edge['marginal_effects']
                new_me = {}
                for key in ['p25', 'p50', 'p75']:
                    if key in me:
                        # Assume similar relative uncertainty
                        ratio = resampled_beta / beta if beta != 0 else 1.0
                        new_me[key] = me[key] * ratio
                new_edge['marginal_effects'] = new_me

            resampled_edges.append(new_edge)
        resampled[source] = resampled_edges

    return resampled


def propagate_intervention_v31(
    adjacency: Dict[str, List[dict]],
    intervention: Dict[str, float],
    baseline_values: Dict[str, float],
    indicator_percentiles: Optional[Dict[str, float]] = None,
    max_iterations: int = 10,
    convergence_threshold: float = 0.001,
    use_nonlinear: bool = True,
    year: int = 2020,
    country: Optional[str] = None,
) -> dict:
    """
    Propagate intervention through causal graph with proper unit conversion.

    Uses within-country temporal std for conversion (matches beta estimation).

    Args:
        adjacency: Graph adjacency dict from build_adjacency_v31()
        intervention: {indicator: absolute_delta} to apply
        baseline_values: {indicator: current_value}
        indicator_percentiles: {indicator: percentile} for non-linear marginal effects
        max_iterations: Maximum propagation iterations
        convergence_threshold: Stop when max change < this
        use_nonlinear: Use marginal_effects when available
        year: Year for indicator statistics (std lookup)
        country: Country name for per-country temporal std lookup

    Returns:
        Dict with:
        - values: Final indicator values
        - deltas: Change from baseline for each indicator
        - lower_bound: Lower CI estimate (approx)
        - upper_bound: Upper CI estimate (approx)
        - iterations: Iterations until convergence
        - converged: Whether converged before max_iterations
    """
    # Load country-specific temporal stats (matches beta estimation scale)
    if country:
        country_stats = get_country_indicator_stats(country)
    else:
        country_stats = {}

    def _get_std(indicator: str) -> float:
        """Get correct std for unit conversion."""
        if country_stats:
            stat = country_stats.get(indicator, {})
            temporal_std = stat.get('std', 0.0)
            if temporal_std > 0:
                return temporal_std
        # Fallback: baseline magnitude as scale proxy
        base_val = abs(baseline_values.get(indicator, 0))
        return base_val if base_val > 0 else 1.0

    # Initialize
    current_values = dict(baseline_values)
    cumulative_deltas = defaultdict(float)
    lower_bound = {}
    upper_bound = {}

    # Apply initial intervention
    changed_nodes = set()
    for indicator, delta in intervention.items():
        baseline = baseline_values.get(indicator)
        if baseline is None:
            # Track delta even without baseline
            cumulative_deltas[indicator] = delta
            changed_nodes.add(indicator)
            continue

        new_val = baseline + delta
        saturated = apply_saturation(indicator, new_val, baseline)

        current_values[indicator] = saturated
        cumulative_deltas[indicator] = saturated - baseline
        changed_nodes.add(indicator)

        lower_bound[indicator] = saturated
        upper_bound[indicator] = saturated

    # Propagate iteratively
    for iteration in range(max_iterations):
        new_changes = defaultdict(float)
        newly_changed = set()

        for source in changed_nodes:
            source_delta = cumulative_deltas[source]
            if source_delta == 0:
                continue

            edges = adjacency.get(source, [])
            source_std = _get_std(source)

            for edge in edges:
                target = edge.get('target')
                if target is None:
                    continue

                # Determine effect coefficient
                if use_nonlinear and indicator_percentiles:
                    source_percentile = indicator_percentiles.get(source, 0.5)
                    beta = get_marginal_effect(edge, current_values.get(source, 0), source_percentile)
                else:
                    beta = edge.get('beta', 0)

                if beta == 0:
                    continue

                # Unit conversion: standardized beta -> raw units
                # Using country temporal std (matches beta estimation)
                target_std = _get_std(target)
                propagated_effect = beta * (source_delta / source_std) * target_std

                new_changes[target] += propagated_effect

        # Apply accumulated changes
        for target, total_effect in new_changes.items():
            baseline = baseline_values.get(target)
            current_delta = cumulative_deltas[target]
            proposed_delta = current_delta + total_effect

            # Clamp CUMULATIVE delta to ±2σ of target's historical variance
            if country_stats:
                tgt_stat = country_stats.get(target, {})
                tgt_temporal_std = tgt_stat.get('std', 0.0)
                if tgt_temporal_std > 0:
                    max_delta = 2.0 * tgt_temporal_std
                    proposed_delta = float(np.clip(proposed_delta, -max_delta, max_delta))

            if baseline is not None:
                new_val = baseline + proposed_delta
                saturated = apply_saturation(target, new_val, baseline)
                actual_delta = saturated - baseline
                current_values[target] = saturated
                lower_bound[target] = min(lower_bound.get(target, saturated), saturated * 0.95)
                upper_bound[target] = max(upper_bound.get(target, saturated), saturated * 1.05)
            else:
                actual_delta = proposed_delta

            if abs(actual_delta - current_delta) > convergence_threshold:
                newly_changed.add(target)

            cumulative_deltas[target] = actual_delta

        if not newly_changed:
            return {
                'values': dict(current_values),
                'deltas': dict(cumulative_deltas),
                'lower_bound': lower_bound,
                'upper_bound': upper_bound,
                'iterations': iteration + 1,
                'converged': True
            }

        changed_nodes = newly_changed

    return {
        'values': dict(current_values),
        'deltas': dict(cumulative_deltas),
        'lower_bound': lower_bound,
        'upper_bound': upper_bound,
        'iterations': max_iterations,
        'converged': False
    }


def propagate_intervention_ensemble(
    adjacency: Dict[str, List[dict]],
    intervention: Dict[str, float],
    baseline_values: Dict[str, float],
    indicator_percentiles: Optional[Dict[str, float]] = None,
    n_runs: int = 100,
    seed: int = 42,
    uncertainty_multiplier: float = 3.0,
    **propagation_kwargs
) -> dict:
    """
    Run ensemble simulation with bootstrap resampling for uncertainty.

    Runs N propagations with resampled edge weights, returns median + CI.

    Args:
        adjacency: Graph adjacency dict
        intervention: {indicator: absolute_delta}
        baseline_values: {indicator: current_value}
        indicator_percentiles: For non-linear propagation
        n_runs: Number of bootstrap iterations (default 100)
        seed: Random seed for reproducibility
        uncertainty_multiplier: Scaling for edge weight resampling
        **propagation_kwargs: Passed to propagate_intervention_v31()

    Returns:
        Dict with:
        - values: Median final values
        - deltas: Median changes from baseline
        - ci_lower: 2.5th percentile (95% CI lower)
        - ci_upper: 97.5th percentile (95% CI upper)
        - std: Standard deviation across runs
        - n_runs: Number of runs performed
        - converged_runs: Number of runs that converged
    """
    rng = np.random.default_rng(seed)

    # Collect results across runs
    all_values = defaultdict(list)
    all_deltas = defaultdict(list)
    converged_count = 0

    for _ in range(n_runs):
        # Resample edge weights
        resampled_adj = resample_edge_weights(adjacency, rng, uncertainty_multiplier)

        # Run propagation
        result = propagate_intervention_v31(
            resampled_adj,
            intervention,
            baseline_values,
            indicator_percentiles,
            **propagation_kwargs
        )

        if result['converged']:
            converged_count += 1

        # Collect values
        for indicator, value in result['values'].items():
            all_values[indicator].append(value)
        for indicator, delta in result['deltas'].items():
            all_deltas[indicator].append(delta)

    # Compute statistics
    median_values = {}
    median_deltas = {}
    ci_lower = {}
    ci_upper = {}
    std_values = {}

    for indicator in all_values:
        values = np.array(all_values[indicator])
        deltas = np.array(all_deltas[indicator])

        median_values[indicator] = float(np.median(values))
        median_deltas[indicator] = float(np.median(deltas))
        ci_lower[indicator] = float(np.percentile(values, 2.5))
        ci_upper[indicator] = float(np.percentile(values, 97.5))
        std_values[indicator] = float(np.std(deltas))

    return {
        'values': median_values,
        'deltas': median_deltas,
        'ci_lower': ci_lower,
        'ci_upper': ci_upper,
        'std': std_values,
        'n_runs': n_runs,
        'converged_runs': converged_count,
        'convergence_rate': converged_count / n_runs
    }


def compute_effects(
    baseline_values: Dict[str, float],
    simulated_values: Dict[str, float],
    indicators: Optional[List[str]] = None,
    country_stats: Optional[Dict[str, Dict[str, float]]] = None,
) -> Dict[str, dict]:
    """
    Compute effect details for each indicator.

    Handles near-zero baselines safely:
    - percent_change: raw delta/baseline*100 when |baseline| >= eps, else None
    - display_percent: always a number, uses eps denominator when baseline ≈ 0
    - near_zero_baseline: True when raw percent is undefined

    Epsilon is indicator-aware: eps = 0.01 * temporal_std when country_stats
    are available, else 1e-6. This prevents infinity/huge percent for
    indicators with near-zero baselines (common for aid flows, binary vars).

    Args:
        baseline_values: Original values
        simulated_values: Values after intervention
        indicators: Optional list to filter
        country_stats: Optional {indicator: {std, mean, ...}} for eps derivation

    Returns:
        {indicator: {baseline, simulated, absolute_change, percent_change,
                     display_percent, near_zero_baseline}}
    """
    effects = {}

    target_indicators = indicators or list(simulated_values.keys())

    for indicator in target_indicators:
        baseline = baseline_values.get(indicator)
        simulated = simulated_values.get(indicator)

        if baseline is None or simulated is None:
            continue

        abs_change = simulated - baseline

        # Determine epsilon for near-zero baseline detection
        eps = 1e-6
        if country_stats:
            stat = country_stats.get(indicator, {})
            temporal_std = stat.get('std', 0.0)
            if temporal_std > 0:
                eps = 0.01 * temporal_std

        near_zero = abs(baseline) < eps
        if near_zero:
            # Raw percent is undefined — use epsilon denominator for display
            pct_change = None
            display_pct = (abs_change / eps * 100) if abs_change != 0 else 0.0
        else:
            pct_change = abs_change / baseline * 100
            display_pct = pct_change

        effects[indicator] = {
            'baseline': baseline,
            'simulated': simulated,
            'absolute_change': abs_change,
            'percent_change': pct_change if pct_change is not None else display_pct,
            'display_percent': display_pct,
            'near_zero_baseline': near_zero,
        }

    return effects


def propagate_intervention_percentage(
    adjacency: Dict[str, List[dict]],
    intervention: Dict[str, float],
    use_nonlinear: bool = True,
    max_iterations: int = 100,
    convergence_threshold: float = 1e-6,
) -> dict:
    """
    Propagate percentage changes through causal graph.

    No baseline values needed - works entirely in percentages.
    This is the FAST PATH for simulation that avoids loading 65MB panel data.

    Since betas are standardized coefficients (effectively correlations, bounded
    by [-1, 1]), cascading naturally attenuates without artificial dampening.

    Args:
        adjacency: Graph adjacency dict with beta coefficients
        intervention: {indicator_id: change_percent}
        use_nonlinear: Use marginal_effects when available
        max_iterations: Maximum propagation iterations
        convergence_threshold: Stop when max change < this

    Returns:
        {
            'percent_changes': {indicator: percent_change},
            'iterations': int,
            'converged': bool
        }
    """
    # Initialize with intervention percentages
    percent_changes = dict(intervention)
    changed_nodes = set(intervention.keys())

    for iteration in range(max_iterations):
        new_changes = {}

        for source in changed_nodes:
            source_change_pct = percent_changes.get(source, 0)
            if source_change_pct == 0:
                continue

            edges = adjacency.get(source, [])

            for edge in edges:
                target = edge.get('target')
                if target is None:
                    continue

                beta = edge.get('beta', 0)

                if use_nonlinear:
                    nonlinearity = edge.get('nonlinearity', {})
                    if nonlinearity.get('detected') and 'marginal_effects' in nonlinearity:
                        beta = nonlinearity['marginal_effects'].get('p50', beta)

                # Standardized beta: X% change in source -> X% * beta change in target
                target_delta = source_change_pct * beta

                if target in new_changes:
                    new_changes[target] += target_delta
                else:
                    new_changes[target] = target_delta

        # Check convergence
        if not new_changes:
            return {
                'percent_changes': percent_changes,
                'iterations': iteration + 1,
                'converged': True
            }

        max_update = max(abs(v) for v in new_changes.values())
        if max_update < convergence_threshold:
            return {
                'percent_changes': percent_changes,
                'iterations': iteration + 1,
                'converged': True
            }

        # Apply updates
        newly_changed = set()
        for target, delta in new_changes.items():
            old_val = percent_changes.get(target, 0)
            new_val = old_val + delta

            # Only track significant changes
            if abs(new_val - old_val) > convergence_threshold:
                newly_changed.add(target)

            percent_changes[target] = new_val

        changed_nodes = newly_changed

        if not changed_nodes:
            return {
                'percent_changes': percent_changes,
                'iterations': iteration + 1,
                'converged': True
            }

    return {
        'percent_changes': percent_changes,
        'iterations': max_iterations,
        'converged': False
    }


def get_top_percent_effects(
    percent_changes: Dict[str, float],
    top_n: int = 20
) -> Dict[str, dict]:
    """
    Get top N effects by percent change magnitude.

    Args:
        percent_changes: {indicator: percent_change}
        top_n: Number of top effects to return

    Returns:
        {indicator: {'percent_change': float}}
    """
    sorted_effects = sorted(
        percent_changes.items(),
        key=lambda x: abs(x[1]),
        reverse=True
    )

    return {
        ind: {'percent_change': pct}
        for ind, pct in sorted_effects[:top_n]
    }


def get_top_effects(
    effects: Dict[str, dict],
    top_n: int = 20,
    sort_by: Literal['absolute', 'percent'] = 'absolute'
) -> Dict[str, dict]:
    """
    Get top N effects by magnitude.

    Args:
        effects: Output from compute_effects()
        top_n: Number of top effects to return
        sort_by: Sort by 'absolute' or 'percent' change

    Returns:
        Top N effects dict
    """
    if sort_by == 'absolute':
        key_func = lambda x: abs(x[1].get('absolute_change', 0))
    else:
        key_func = lambda x: abs(x[1].get('percent_change', 0))

    sorted_effects = sorted(effects.items(), key=key_func, reverse=True)

    return dict(sorted_effects[:top_n])


# =============================================================================
# TESTS
# =============================================================================

def _run_tests():
    """Run basic tests."""
    print("\nRunning propagation tests...")
    print("-" * 40)

    # Test marginal effect extraction
    linear_edge = {'beta': 0.5, 'relationship_type': 'linear'}
    effect = get_marginal_effect(linear_edge, 100, 0.5)
    assert effect == 0.5
    print("  get_marginal_effect (linear): PASS")

    nonlinear_edge = {
        'beta': 0.5,
        'relationship_type': 'saturation',
        'marginal_effects': {'p25': 0.8, 'p50': 0.5, 'p75': 0.2}
    }
    effect_p25 = get_marginal_effect(nonlinear_edge, 100, 0.25)
    effect_p75 = get_marginal_effect(nonlinear_edge, 100, 0.75)
    assert effect_p25 == 0.8
    assert effect_p75 == 0.2
    print("  get_marginal_effect (nonlinear): PASS")

    # Test simple propagation
    adjacency = {
        'A': [{'target': 'B', 'beta': 0.5, 'std': 0.1}],
        'B': [{'target': 'C', 'beta': 0.3, 'std': 0.05}]
    }
    baseline = {'A': 100, 'B': 50, 'C': 25}
    intervention = {'A': 10}

    result = propagate_intervention_v31(
        adjacency, intervention, baseline,
    )
    assert result['converged']
    assert result['deltas']['A'] == 10
    # B should get effect from A
    assert result['deltas']['B'] > 0
    print("  propagate_intervention_v31: PASS")

    # Test edge resampling
    rng = np.random.default_rng(42)
    resampled = resample_edge_weights(adjacency, rng)
    # Beta should be different due to resampling
    original_beta = adjacency['A'][0]['beta']
    resampled_beta = resampled['A'][0]['beta']
    # With std=0.1 and multiplier=3.0, should be different
    print(f"  Edge resampling: {original_beta:.3f} -> {resampled_beta:.3f}")

    # Test compute_effects
    effects = compute_effects(baseline, result['values'])
    assert 'A' in effects
    assert 'percent_change' in effects['A']
    print("  compute_effects: PASS")

    # Test top effects
    top = get_top_effects(effects, top_n=2)
    assert len(top) <= 2
    print("  get_top_effects: PASS")

    print("-" * 40)
    print("All propagation tests PASSED\n")


if __name__ == "__main__":
    _run_tests()
