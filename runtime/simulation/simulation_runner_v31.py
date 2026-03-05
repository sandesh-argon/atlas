"""
V3.1 Simulation Runner

End-to-end instant simulation with:
- Year-specific graph loading
- Non-linear propagation
- Regional spillover effects
- Optional ensemble uncertainty
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Literal
import pandas as pd

from .graph_loader_v31 import (
    load_temporal_graph,
    build_adjacency_v31,
    get_available_countries,
)
from .income_classifier import get_country_classification, get_stratum_for_country
from .regional_spillovers import compute_regional_spillover, get_region_info
from .region_mapping import get_region_for_country
from .propagation_v31 import (
    propagate_intervention_v31,
    propagate_intervention_ensemble,
    propagate_intervention_percentage,
    compute_effects,
    get_top_effects,
    get_top_percent_effects
)
from .qol_definition import compute_qol, load_indicator_metadata

# Project paths
DATA_ROOT = Path(__file__).parent.parent / "data"
PANEL_PATH = DATA_ROOT / "raw" / "v21_panel_data_for_v3.parquet"
BASELINE_DIR = DATA_ROOT / "v31" / "baselines"
METADATA_DIR = DATA_ROOT / "v31" / "metadata"

# Module-level QoL computation cache
_qol_metadata: Optional[Dict] = None
_qol_norm_stats: Optional[Dict] = None
_qol_calibration: Optional[Dict] = None
_qol_direction_overrides: Optional[Dict] = None


def _get_qol_assets() -> tuple:
    """Load and cache QoL computation assets (metadata, norm_stats, calibration, direction_overrides)."""
    global _qol_metadata, _qol_norm_stats, _qol_calibration, _qol_direction_overrides

    if _qol_metadata is None:
        _qol_metadata = load_indicator_metadata(
            DATA_ROOT / "raw" / "v21_nodes.csv",
            METADATA_DIR / "indicator_properties.json",
        )
    if _qol_norm_stats is None:
        norm_path = METADATA_DIR / "qol_normalization_stats_v1.json"
        if norm_path.exists():
            with open(norm_path) as f:
                _qol_norm_stats = json.load(f)
        else:
            _qol_norm_stats = {}
    if _qol_calibration is None:
        cal_path = METADATA_DIR / "qol_calibration_v1.json"
        if cal_path.exists():
            with open(cal_path) as f:
                _qol_calibration = json.load(f).get("calibration", {})
        else:
            _qol_calibration = {}
    if _qol_direction_overrides is None:
        dir_path = METADATA_DIR / "qol_direction_overrides_v1.json"
        if dir_path.exists():
            with open(dir_path) as f:
                _qol_direction_overrides = json.load(f)
        else:
            _qol_direction_overrides = {}

    return _qol_metadata, _qol_norm_stats, _qol_calibration, _qol_direction_overrides


def _get_norm_stats_for_year(norm_stats_asset: Dict, year: Optional[int]) -> Dict:
    """Resolve per-year normalization stats with global fallback."""
    if not norm_stats_asset:
        return {}

    # Backward compatibility: flat indicator->stats mapping
    if "by_year" not in norm_stats_asset:
        return norm_stats_asset

    if year is not None:
        year_stats = norm_stats_asset.get("by_year", {}).get(str(year))
        if year_stats:
            return year_stats

    return norm_stats_asset.get("global", {})


def _compute_qol_delta(
    baseline_values: Dict[str, float],
    simulated_values: Dict[str, float],
    year: Optional[int] = None,
) -> Optional[Dict[str, float]]:
    """Compute QoL for baseline and simulated indicator sets, return delta."""
    meta, norm_stats_asset, calibration, dir_overrides = _get_qol_assets()
    norm_stats = _get_norm_stats_for_year(norm_stats_asset, year)
    if not norm_stats or not calibration or not calibration.get("breakpoints"):
        return None

    base_qol = compute_qol(baseline_values, meta, norm_stats, calibration, dir_overrides)
    if base_qol is None:
        return None

    sim_qol = compute_qol(simulated_values, meta, norm_stats, calibration, dir_overrides)
    if sim_qol is None:
        return None

    return {
        "baseline": round(base_qol["calibrated"], 4),
        "simulated": round(sim_qol["calibrated"], 4),
        "delta": round(sim_qol["calibrated"] - base_qol["calibrated"], 4),
        "n_indicators": base_qol["n_indicators"],
        "n_domains": base_qol["n_domains"],
    }

# Type definitions
ViewType = Literal['country', 'stratified', 'unified', 'regional']
SimulationMode = Literal['percentage', 'absolute']


def load_baseline_values(
    country: str,
    year: Optional[int] = None,
    panel_path: Optional[Path] = None
) -> tuple:
    """
    Load baseline indicator values for a country from panel data.

    Args:
        country: Country name
        year: Year to get values for (default: most recent)
        panel_path: Override default panel data path

    Returns:
        (baseline_dict, year_used, percentiles_dict)
    """
    path = panel_path or PANEL_PATH

    if not path.exists():
        raise FileNotFoundError(f"Panel data not found: {path}")

    df = pd.read_parquet(path)

    # Handle different column formats
    if 'indicator_id' in df.columns:
        # Long format
        country_data = df[df['country'] == country]
        if country_data.empty:
            # Try case-insensitive
            country_lower = country.lower()
            country_data = df[df['country'].str.lower() == country_lower]

        if country_data.empty:
            return {}, None, {}

        if year is None:
            year = country_data['year'].max()

        year_data = country_data[country_data['year'] == year]
        baseline = dict(zip(year_data['indicator_id'], year_data['value']))

        # Compute percentiles for non-linear propagation
        # Percentile of each indicator value across all countries for that year
        all_year = df[df['year'] == year]
        percentiles = {}
        for indicator in baseline:
            ind_values = all_year[all_year['indicator_id'] == indicator]['value'].dropna()
            if len(ind_values) > 1:
                value = baseline[indicator]
                pct = (ind_values < value).sum() / len(ind_values)
                percentiles[indicator] = pct

        return baseline, year, percentiles
    else:
        # Wide format (each column is an indicator)
        # This is less common for v21 data
        if 'country' in df.columns:
            country_data = df[df['country'] == country]
        else:
            return {}, None, {}

        if country_data.empty:
            return {}, None, {}

        if year is None and 'year' in df.columns:
            year = country_data['year'].max()

        if 'year' in df.columns:
            year_data = country_data[country_data['year'] == year]
        else:
            year_data = country_data

        if year_data.empty:
            return {}, None, {}

        # Get indicator columns (everything except metadata)
        meta_cols = {'country', 'year', 'iso3', 'region'}
        ind_cols = [c for c in year_data.columns if c not in meta_cols]

        baseline = year_data[ind_cols].iloc[0].to_dict()
        baseline = {k: v for k, v in baseline.items() if pd.notna(v)}

        return baseline, year, {}


def load_precomputed_baseline(
    country: str,
    year: int,
    baseline_dir: Optional[Path] = None
) -> Dict[str, float]:
    """
    Load pre-computed baseline from JSON file.

    Falls back to nearest available year if exact year not found.
    This is much faster than loading from 65MB parquet (~50ms vs ~30s).

    Args:
        country: Country name
        year: Year to get values for
        baseline_dir: Override default baseline directory

    Returns:
        Dict of indicator_id -> value, or empty dict if not found
    """
    base_dir = baseline_dir or BASELINE_DIR
    baseline_file = base_dir / country / f"{year}.json"

    if not baseline_file.exists():
        # Try nearest year
        country_dir = base_dir / country
        if not country_dir.exists():
            return {}

        available = []
        for f in country_dir.glob("*.json"):
            try:
                y = int(f.stem)
                available.append(y)
            except ValueError:
                pass

        if not available:
            return {}

        nearest = min(available, key=lambda y: abs(y - year))
        baseline_file = country_dir / f"{nearest}.json"

    try:
        with open(baseline_file) as f:
            data = json.load(f)
            return data.get("values", {})
    except (json.JSONDecodeError, IOError):
        return {}


def run_simulation_v31(
    country: Optional[str],
    interventions: List[dict],
    year: int,
    view_type: ViewType = 'country',
    mode: SimulationMode = 'percentage',
    p_value_threshold: float = 0.05,
    use_nonlinear: bool = True,
    n_ensemble_runs: int = 0,
    include_spillovers: bool = True,
    top_n_effects: int = 20,
    panel_path: Optional[Path] = None,
    baseline_dir: Optional[Path] = None,
    region: Optional[str] = None,
    debug: bool = False,
) -> dict:
    """
    Run instant simulation with V3.1 year-specific graph.

    Args:
        country: Country name (optional for unified/regional requests)
        interventions: List of {indicator: str, change_percent: float}
        year: Year for graph and baseline (1990-2024)
        view_type: 'country', 'stratified', 'unified', or 'regional'
        mode: 'percentage' (fast, no baselines) or 'absolute' (real values)
        p_value_threshold: Filter edges by p-value
        use_nonlinear: Use marginal_effects when available
        n_ensemble_runs: 0 = point estimate, >0 = bootstrap ensemble
        include_spillovers: Include regional spillover effects
        top_n_effects: Number of top effects to return
        panel_path: Override panel data path (for absolute mode legacy)
        baseline_dir: Override baseline JSON directory (for absolute mode)
        region: Region key for regional view (optional if derivable from country)
        debug: Include extra debug fields in metadata

    Returns:
        Dict with:
        - status: 'success' or 'error'
        - mode: 'percentage' or 'absolute'
        - country, base_year, view_type
        - income_classification
        - interventions (with applied status)
        - effects (top N)
        - spillovers (if enabled and mode='absolute')
        - propagation metadata
        - ensemble (if n_ensemble_runs > 0)
    """
    try:
        warnings: List[str] = []
        region_used = region or (get_region_for_country(country) if country else None)

        # Validate scope requirements
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

        # Load graph (always needed)
        graph = load_temporal_graph(
            country=country,
            year=year,
            view_type=view_type,
            p_value_threshold=p_value_threshold,
            region=region_used,
        )

        if graph is None:
            scope_label = region_used if view_type == 'regional' else (country or 'global')
            return {
                'status': 'error',
                'message': f"No graph available for '{scope_label}' in year {year}"
            }

        # Build adjacency
        adjacency = build_adjacency_v31(graph)
        view_used = graph.get('view_used', view_type)
        year_used = int(graph.get('year_used', year))
        region_used = graph.get('region_used') or region_used
        scope_used = view_used

        if graph.get('warnings'):
            warnings.extend(graph.get('warnings') or [])

        # Get income classification
        income_class = get_country_classification(country, year_used) if country else None

        # =====================================================================
        # PERCENTAGE MODE - Fast path, no baseline loading
        # =====================================================================
        if mode == 'percentage':
            # Convert interventions to percentage dict
            intervention_pct = {}
            intervention_details = []

            for intv in interventions:
                indicator = intv.get('indicator')
                change_percent = intv.get('change_percent', 0)

                intervention_pct[indicator] = change_percent
                intervention_details.append({
                    'indicator': indicator,
                    'change_percent': change_percent,
                    'status': 'applied'
                })

            if not intervention_pct:
                return {
                    'status': 'error',
                    'message': 'No interventions to apply'
                }

            # Run percentage propagation
            result = propagate_intervention_percentage(
                adjacency=adjacency,
                intervention=intervention_pct,
                use_nonlinear=use_nonlinear
            )

            # Get top effects
            top_effects = get_top_percent_effects(
                result['percent_changes'],
                top_n=top_n_effects
            )

            return {
                'status': 'success',
                'mode': 'percentage',
                'country': country,
                'base_year': year_used,
                'view_type': view_type,
                'view_used': view_used,
                'scope_used': scope_used,
                'region_used': region_used,
                'income_classification': income_class,
                'interventions': intervention_details,
                'effects': {
                    'total_affected': len([v for v in result['percent_changes'].values() if abs(v) > 0.001]),
                    'top_effects': top_effects
                },
                'propagation': {
                    'iterations': result.get('iterations', 0),
                    'converged': result.get('converged', True),
                },
                'metadata': {
                    'n_edges_original': graph.get('n_edges_original', 0),
                    'n_edges_filtered': graph.get('n_edges_filtered', 0),
                    'p_value_threshold': p_value_threshold,
                    'use_nonlinear': use_nonlinear,
                    'timestamp': datetime.now().isoformat()
                },
                'warnings': warnings or None,
            }

        # =====================================================================
        # ABSOLUTE MODE - Uses baseline values for real-world units
        # =====================================================================
        # Try pre-computed JSON baseline first by scope (fast), fall back when possible.
        baseline_scope = None
        baseline = {}
        percentiles = {}

        if view_used == 'country':
            baseline_scope = country
            baseline = load_precomputed_baseline(country, year_used, baseline_dir) if country else {}
            if not baseline and country:
                # Fall back to parquet loading for country scope
                baseline, loaded_year, percentiles = load_baseline_values(country, year_used, panel_path)
                if loaded_year is not None:
                    year_used = int(loaded_year)
        elif view_used == 'stratified':
            stratum = get_stratum_for_country(country, year_used) if country else None
            if not stratum:
                return {
                    'status': 'error',
                    'message': f"Cannot determine stratum for '{country}' in year {year_used}"
                }
            baseline_scope = f"stratified/{stratum}"
            baseline = load_precomputed_baseline(baseline_scope, year_used, baseline_dir)
        elif view_used == 'regional':
            if not region_used:
                return {
                    'status': 'error',
                    'message': "Cannot determine region for regional simulation baseline"
                }
            baseline_scope = f"regional/{region_used}"
            baseline = load_precomputed_baseline(baseline_scope, year_used, baseline_dir)
        else:  # unified
            baseline_scope = "unified"
            baseline = load_precomputed_baseline(baseline_scope, year_used, baseline_dir)

        if not baseline:
            return {
                'status': 'error',
                'message': (
                    f"No baseline data for '{baseline_scope}' in year {year_used}. "
                    "Run regional/strata/unified baseline precompute jobs."
                )
            }

        # Convert interventions to absolute deltas
        intervention_dict = {}
        intervention_details = []

        for intv in interventions:
            indicator = intv.get('indicator')
            change_percent = intv.get('change_percent', 0)

            if indicator not in baseline:
                intervention_details.append({
                    'indicator': indicator,
                    'change_percent': change_percent,
                    'status': 'skipped',
                    'reason': 'not_in_baseline'
                })
                continue

            base_val = baseline[indicator]
            delta = base_val * (change_percent / 100)
            intervention_dict[indicator] = delta

            intervention_details.append({
                'indicator': indicator,
                'baseline': base_val,
                'change_percent': change_percent,
                'change_absolute': delta,
                'status': 'applied'
            })

        if not intervention_dict:
            return {
                'status': 'error',
                'message': 'No valid interventions to apply'
            }

        # Run propagation
        if n_ensemble_runs > 0:
            # Ensemble simulation
            result = propagate_intervention_ensemble(
                adjacency=adjacency,
                intervention=intervention_dict,
                baseline_values=baseline,
                indicator_percentiles=percentiles if use_nonlinear else None,
                n_runs=n_ensemble_runs,
                use_nonlinear=use_nonlinear,
                year=year_used,
                country=country if view_used == 'country' else None,
            )
            is_ensemble = True
        else:
            # Point estimate
            result = propagate_intervention_v31(
                adjacency=adjacency,
                intervention=intervention_dict,
                baseline_values=baseline,
                indicator_percentiles=percentiles if use_nonlinear else None,
                use_nonlinear=use_nonlinear,
                year=year_used,
                country=country if view_used == 'country' else None,
            )
            is_ensemble = False

        # Compute effects
        effects = compute_effects(baseline, result['values'])
        top_effects = get_top_effects(effects, top_n=top_n_effects)

        # Build response
        response = {
            'status': 'success',
            'mode': 'absolute',
            'country': country,
            'base_year': year_used or year,
            'view_type': view_type,
            'view_used': view_used,
            'scope_used': scope_used,
            'region_used': region_used,
            'income_classification': income_class,
            'interventions': intervention_details,
            'effects': {
                'total_affected': len([e for e in effects.values() if e.get('absolute_change', 0) != 0]),
                'top_effects': top_effects
            },
            'propagation': {
                'iterations': result.get('iterations', 0),
                'converged': result.get('converged', True),
            },
            'metadata': {
                'n_edges_original': graph.get('n_edges_original', 0),
                'n_edges_filtered': graph.get('n_edges_filtered', 0),
                    'p_value_threshold': p_value_threshold,
                    'use_nonlinear': use_nonlinear,
                    'timestamp': datetime.now().isoformat()
            },
            'warnings': warnings or None,
        }

        # Compute QoL delta
        try:
            qol = _compute_qol_delta(baseline, result['values'], year_used or year)
            if qol is not None:
                response['qol'] = qol
        except Exception:
            pass  # QoL is non-critical; don't fail the simulation

        # Add ensemble stats if applicable
        if is_ensemble:
            response['ensemble'] = {
                'n_runs': result.get('n_runs', n_ensemble_runs),
                'converged_runs': result.get('converged_runs', 0),
                'convergence_rate': result.get('convergence_rate', 0)
            }
            # Add CI bounds to top effects
            for ind in top_effects:
                if ind in result.get('ci_lower', {}):
                    top_effects[ind]['ci_lower'] = result['ci_lower'][ind]
                    top_effects[ind]['ci_upper'] = result['ci_upper'][ind]
                if ind in result.get('std', {}):
                    top_effects[ind]['std'] = result['std'][ind]

        # Compute regional spillovers if enabled (country scope only)
        if include_spillovers and country and view_used == 'country':
            # Get absolute changes for spillover computation
            abs_effects = {ind: eff.get('absolute_change', 0) for ind, eff in effects.items()}
            spillovers = compute_regional_spillover(country, abs_effects)

            response['spillovers'] = {
                'regional': spillovers.get('regional', {}),
                'global': spillovers.get('global', {}),
                'region_info': get_region_info(country),
                'is_global_power': spillovers.get('metadata', {}).get('is_global_power', False)
            }

        if debug:
            response.setdefault('metadata', {})['debug'] = {
                'requested_region': region,
                'resolved_region': region_used,
                'year_requested': year,
                'year_used': year_used,
                'baseline_scope': baseline_scope,
            }

        return response

    except Exception as e:
        return {
            'status': 'error',
            'message': str(e)
        }


def validate_country(country: str) -> bool:
    """Check if country has available data."""
    available = get_available_countries()
    return country in available or country.lower() in [c.lower() for c in available]


def format_simulation_results(result: dict) -> str:
    """Format simulation result for CLI display."""
    if result.get('status') == 'error':
        return f"Error: {result.get('message', 'Unknown error')}"

    lines = [
        f"\n{'='*60}",
        f"Simulation Results: {result['country']} ({result['base_year']})",
        f"{'='*60}",
        f"\nView: {result['view_used']} (requested: {result['view_type']})",
        f"Income: {result.get('income_classification', {}).get('group_3tier', 'Unknown')}",
        f"\nInterventions:"
    ]

    for intv in result.get('interventions', []):
        status = "✓" if intv['status'] == 'applied' else "✗"
        lines.append(f"  {status} {intv['indicator']}: {intv.get('change_percent', 0):+.1f}%")

    lines.append(f"\nTop Effects ({result['effects']['total_affected']} total affected):")
    for ind, eff in result.get('effects', {}).get('top_effects', {}).items():
        pct = eff.get('percent_change', 0)
        lines.append(f"  {ind}: {pct:+.2f}%")

    if result.get('propagation'):
        prop = result['propagation']
        status = "converged" if prop.get('converged') else "max iterations"
        lines.append(f"\nPropagation: {prop.get('iterations')} iterations ({status})")

    if result.get('spillovers'):
        sp = result['spillovers']
        if sp.get('region_info'):
            ri = sp['region_info']
            lines.append(f"\nRegional Spillovers ({ri.get('name')}):")
            lines.append(f"  Strength: {ri.get('spillover_strength', 0):.0%}")
            if sp.get('is_global_power'):
                lines.append("  Note: Global power - extra-regional effects included")

    lines.append(f"\n{'='*60}\n")

    return "\n".join(lines)


# =============================================================================
# CLI
# =============================================================================

def _run_tests():
    """Run basic tests."""
    print("\nRunning simulation runner tests...")
    print("-" * 40)

    # Check available countries
    countries = get_available_countries()
    print(f"  Available countries: {len(countries)}")

    if countries:
        # Test simulation
        test_country = 'Australia' if 'Australia' in countries else countries[0]
        result = run_simulation_v31(
            country=test_country,
            interventions=[{'indicator': 'v2pehealth', 'change_percent': 20}],
            year=2020,
            n_ensemble_runs=0  # Point estimate for speed
        )

        if result['status'] == 'success':
            print(f"  Simulation test: SUCCESS")
            print(f"    Country: {result['country']}")
            print(f"    View used: {result['view_used']}")
            print(f"    Effects: {result['effects']['total_affected']} indicators")
        else:
            print(f"  Simulation test: {result.get('message', 'FAILED')}")

    print("-" * 40)
    print("Simulation runner tests completed\n")


if __name__ == "__main__":
    _run_tests()
