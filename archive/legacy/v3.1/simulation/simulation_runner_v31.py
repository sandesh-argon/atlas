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

from .graph_loader_v31 import load_temporal_graph, build_adjacency_v31, get_available_countries
from .income_classifier import get_country_classification, get_stratum_for_country
from .regional_spillovers import compute_regional_spillover, get_region_info
from .propagation_v31 import (
    propagate_intervention_v31,
    propagate_intervention_ensemble,
    propagate_intervention_percentage,
    compute_effects,
    get_top_effects,
    get_top_percent_effects
)

# Project paths
V31_ROOT = Path(__file__).parent.parent
V30_ROOT = V31_ROOT.parent / "v3.0"
DATA_DIR = V31_ROOT / "data"
PANEL_PATH = V30_ROOT / "data" / "raw" / "v21_panel_data_for_v3.parquet"
BASELINE_DIR = DATA_DIR / "v3_1_baselines"

# Type definitions
ViewType = Literal['country', 'stratified', 'unified']
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
    country: str,
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
    baseline_dir: Optional[Path] = None
) -> dict:
    """
    Run instant simulation with V3.1 year-specific graph.

    Args:
        country: Country name
        interventions: List of {indicator: str, change_percent: float}
        year: Year for graph and baseline (1990-2024)
        view_type: 'country', 'stratified', or 'unified'
        mode: 'percentage' (fast, no baselines) or 'absolute' (real values)
        p_value_threshold: Filter edges by p-value
        use_nonlinear: Use marginal_effects when available
        n_ensemble_runs: 0 = point estimate, >0 = bootstrap ensemble
        include_spillovers: Include regional spillover effects
        top_n_effects: Number of top effects to return
        panel_path: Override panel data path (for absolute mode legacy)
        baseline_dir: Override baseline JSON directory (for absolute mode)

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
        # Load graph (always needed)
        graph = load_temporal_graph(
            country=country,
            year=year,
            view_type=view_type,
            p_value_threshold=p_value_threshold
        )

        if graph is None:
            return {
                'status': 'error',
                'message': f"No graph available for '{country}' in year {year}"
            }

        # Build adjacency
        adjacency = build_adjacency_v31(graph)

        # Get income classification
        income_class = get_country_classification(country, year) or {}

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
                'base_year': year,
                'view_type': view_type,
                'view_used': graph.get('view_used', view_type),
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
                }
            }

        # =====================================================================
        # ABSOLUTE MODE - Uses baseline values for real-world units
        # =====================================================================
        # Try pre-computed JSON baseline first (fast), fall back to parquet (slow)
        baseline = load_precomputed_baseline(country, year, baseline_dir)
        year_used = year
        percentiles = {}

        if not baseline:
            # Fall back to parquet loading
            baseline, year_used, percentiles = load_baseline_values(country, year, panel_path)

        if not baseline:
            return {
                'status': 'error',
                'message': f"No baseline data for country '{country}' in year {year}. Run precompute_baselines.py first."
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
                year=year,
                country=country
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
                year=year,
                country=country,
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
            'view_used': graph.get('view_used', view_type),
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
            }
        }

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

        # Compute regional spillovers if enabled
        if include_spillovers:
            # Get absolute changes for spillover computation
            abs_effects = {ind: eff.get('absolute_change', 0) for ind, eff in effects.items()}
            spillovers = compute_regional_spillover(country, abs_effects)

            response['spillovers'] = {
                'regional': spillovers.get('regional', {}),
                'global': spillovers.get('global', {}),
                'region_info': get_region_info(country),
                'is_global_power': spillovers.get('metadata', {}).get('is_global_power', False)
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
