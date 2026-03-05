"""
V3.1 Temporal Graph Loader

Loads year-specific causal graphs with fallback chains:
- country/{country}/{year} -> stratified/{stratum}/{year} -> unified/{year}
- regional/{region}/{year} -> unified/{year}
"""

import json
from collections import defaultdict
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Literal, Set, Tuple

from .income_classifier import get_stratum_for_country
from .region_mapping import get_region_for_country

# Project paths
DATA_ROOT = Path(__file__).parent.parent / "data"
GRAPHS_DIR = DATA_ROOT / "v31" / "temporal_graphs"

# Type definitions
ViewType = Literal['country', 'stratified', 'unified', 'regional']
Stratum = Literal['developing', 'emerging', 'advanced']

# Valid year range
MIN_YEAR = 1990
MAX_YEAR = 2024


def _get_graph_path(
    view_type: ViewType,
    year: int,
    country: Optional[str] = None,
    stratum: Optional[Stratum] = None,
    region: Optional[str] = None,
) -> Path:
    """Get path to graph file based on view type."""
    if view_type == 'country':
        if country is None:
            raise ValueError("country required for view_type='country'")
        return GRAPHS_DIR / "countries" / country / f"{year}_graph.json"

    elif view_type == 'stratified':
        if stratum is None:
            raise ValueError("stratum required for view_type='stratified'")
        return GRAPHS_DIR / "stratified" / stratum / f"{year}_graph.json"

    elif view_type == 'unified':
        return GRAPHS_DIR / "unified" / f"{year}_graph.json"

    elif view_type == 'regional':
        if region is None:
            raise ValueError("region required for view_type='regional'")
        return GRAPHS_DIR / "regional" / region / f"{year}_graph.json"

    else:
        raise ValueError(f"Invalid view_type: {view_type}")


def _load_graph_file(path: Path) -> Optional[dict]:
    """Load a single graph file."""
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)


def _find_nearest_year(requested_year: int, available_years: List[int]) -> Optional[int]:
    """Find nearest available year for adaptive-year fallback."""
    if not available_years:
        return None
    return min(available_years, key=lambda y: abs(y - requested_year))


def load_temporal_graph(
    country: Optional[str],
    year: int,
    view_type: ViewType = 'country',
    p_value_threshold: float = 0.05,
    graphs_dir: Optional[Path] = None,
    region: Optional[str] = None,
) -> Optional[dict]:
    """
    Load year-specific graph with fallback chain.

    Fallback: country/{country}/{year} -> stratified/{stratum}/{year} -> unified/{year}

    Args:
        country: Country name (e.g., 'Australia') or None for unified/regional
        year: Year (1990-2024)
        view_type: Starting view type to try
        p_value_threshold: Filter edges by p-value (only keep p < threshold)
        graphs_dir: Override default graphs directory
        region: Region key for regional view (optional if derivable from country)

    Returns:
        Graph dict with edges filtered by p_value_threshold, or None if not found.
        Includes 'view_used' field indicating which view was actually loaded.

    Example:
        >>> graph = load_temporal_graph('Australia', 2020)
        >>> graph['view_used']
        'country'
        >>> len(graph['edges'])  # After p-value filtering
        1500
    """
    global GRAPHS_DIR
    if graphs_dir is not None:
        search_dir = graphs_dir
    else:
        search_dir = GRAPHS_DIR

    # Clamp year to valid range
    requested_year = max(MIN_YEAR, min(MAX_YEAR, year))

    # Determine stratum/region for fallback
    stratum = get_stratum_for_country(country, requested_year) if country and view_type in ('country', 'stratified') else None
    region_used = region or (get_region_for_country(country) if country else None)

    if view_type == 'regional' and not region_used:
        raise ValueError("region required for view_type='regional' when country cannot be mapped")

    # Define fallback chain: (view_type, country, stratum, region)
    if view_type == 'country':
        fallback_chain: List[Tuple[ViewType, Optional[str], Optional[Stratum], Optional[str]]] = [
            ('country', country, None, None),
            ('stratified', None, stratum, None) if stratum else None,
            ('unified', None, None, None),
        ]
    elif view_type == 'stratified':
        fallback_chain = [
            ('stratified', None, stratum, None) if stratum else None,
            ('unified', None, None, None),
        ]
    elif view_type == 'regional':
        fallback_chain = [
            ('regional', None, None, region_used),
            ('unified', None, None, None),
        ]
    else:  # unified
        fallback_chain = [
            ('unified', None, None, None),
        ]

    fallback_chain = [x for x in fallback_chain if x is not None]
    warnings: List[str] = []

    # Try each scope in fallback chain and adaptively choose nearest available year.
    for vtype, c, s, r in fallback_chain:
        available_years = get_available_years(country=c, view_type=vtype, stratum=s, region=r)
        year_to_load = _find_nearest_year(requested_year, available_years)
        if year_to_load is None:
            continue

        if vtype == 'country':
            if c is None:
                continue
            path = search_dir / "countries" / c / f"{year_to_load}_graph.json"
        elif vtype == 'stratified':
            if s is None:
                continue
            path = search_dir / "stratified" / s / f"{year_to_load}_graph.json"
        elif vtype == 'regional':
            if r is None:
                continue
            path = search_dir / "regional" / r / f"{year_to_load}_graph.json"
        else:
            path = search_dir / "unified" / f"{year_to_load}_graph.json"

        graph = _load_graph_file(path)
        if graph is None:
            continue

        # Filter edges by p-value
        filtered_edges = [
            e for e in graph.get('edges', [])
            if e.get('p_value', 0) < p_value_threshold
        ]

        if year_to_load != requested_year:
            warnings.append(
                f"Requested year {requested_year} unavailable for '{vtype}', used nearest year {year_to_load}"
            )
        if vtype != view_type:
            warnings.append(
                f"Requested view '{view_type}' unavailable for year {requested_year}, fell back to '{vtype}'"
            )

        # Return with metadata
        return {
            **graph,
            'edges': filtered_edges,
            'view_used': vtype,
            'view_requested': view_type,
            'year_requested': requested_year,
            'year_used': year_to_load,
            'region_requested': region,
            'region_used': r if vtype == 'regional' else None,
            'p_value_threshold': p_value_threshold,
            'n_edges_original': len(graph.get('edges', [])),
            'n_edges_filtered': len(filtered_edges),
            'warnings': warnings or None,
        }

    return None


def build_adjacency_v31(
    graph: dict,
    p_value_threshold: Optional[float] = None,
    include_insignificant: bool = False
) -> Dict[str, List[dict]]:
    """
    Build adjacency list from V3.1 graph edges.

    Args:
        graph: Graph dict with 'edges' list
        p_value_threshold: Additional p-value filter (if not already filtered)
        include_insignificant: If True, include all edges regardless of p-value

    Returns:
        Adjacency dict: {source: [{target, beta, std, p_value, lag, relationship_type, ...}, ...]}

    Example:
        >>> adj = build_adjacency_v31(graph)
        >>> adj['education_spending'][0]
        {'target': 'gdp', 'beta': 0.42, 'std': 0.05, 'p_value': 0.001, 'lag': 2, ...}
    """
    adjacency = defaultdict(list)

    for edge in graph.get('edges', []):
        # Apply p-value filter if specified
        if not include_insignificant and p_value_threshold is not None:
            if edge.get('p_value', 1.0) >= p_value_threshold:
                continue

        source = edge.get('source')
        if source is None:
            continue

        # Extract edge properties
        nonlinearity = edge.get('nonlinearity') if isinstance(edge.get('nonlinearity'), dict) else None
        marginal_effects = edge.get('marginal_effects')
        if marginal_effects is None and nonlinearity:
            marginal_effects = nonlinearity.get('marginal_effects')

        edge_info = {
            'target': edge.get('target'),
            'beta': edge.get('beta', 0),
            'std': edge.get('std', 0),
            'ci_lower': edge.get('ci_lower'),
            'ci_upper': edge.get('ci_upper'),
            'p_value': edge.get('p_value', 1.0),
            'lag': edge.get('lag', 0),
            'r_squared': edge.get('r_squared'),
            'n_samples': edge.get('n_samples'),
            'n_bootstrap': edge.get('n_bootstrap'),
            'relationship_type': edge.get('relationship_type', 'linear'),
            # V3.1 v2 fields (may not exist in v1 data)
            'marginal_effects': marginal_effects,
            'nonlinearity': nonlinearity,
            'nonlinearity_metadata': edge.get('nonlinearity_metadata')
        }

        adjacency[source].append(edge_info)

    return dict(adjacency)


def get_available_years(
    country: Optional[str] = None,
    view_type: ViewType = 'unified',
    stratum: Optional[Stratum] = None,
    region: Optional[str] = None,
) -> List[int]:
    """
    Get list of years with available graph data.

    Args:
        country: Country name (if checking country-specific availability)
        view_type: Which view to check

    Returns:
        Sorted list of available years
    """
    if view_type == 'country':
        if country is None:
            return []
        search_path = GRAPHS_DIR / "countries" / country
    elif view_type == 'stratified':
        if stratum is not None:
            search_path = GRAPHS_DIR / "stratified" / stratum
        else:
            # Check all strata
            years = set()
            for stratum_name in ['developing', 'emerging', 'advanced']:
                stratum_path = GRAPHS_DIR / "stratified" / stratum_name
                if stratum_path.exists():
                    for f in stratum_path.glob("*_graph.json"):
                        try:
                            year = int(f.stem.split('_')[0])
                            years.add(year)
                        except ValueError:
                            pass
            return sorted(years)
    elif view_type == 'regional':
        if region is None:
            return []
        search_path = GRAPHS_DIR / "regional" / region
    else:  # unified
        search_path = GRAPHS_DIR / "unified"

    if not search_path.exists():
        return []

    years = []
    for f in search_path.glob("*_graph.json"):
        try:
            year = int(f.stem.split('_')[0])
            years.append(year)
        except ValueError:
            pass

    return sorted(years)


def get_available_countries() -> List[str]:
    """Get list of countries with graph data."""
    countries_dir = GRAPHS_DIR / "countries"
    if not countries_dir.exists():
        return []

    countries = []
    for d in countries_dir.iterdir():
        if d.is_dir() and any(d.glob("*_graph.json")):
            countries.append(d.name)

    return sorted(countries)


def get_available_regions() -> List[str]:
    """Get list of regions with temporal graph data."""
    regions_dir = GRAPHS_DIR / "regional"
    if not regions_dir.exists():
        return []

    regions = []
    for d in regions_dir.iterdir():
        if d.is_dir() and any(d.glob("*_graph.json")):
            regions.append(d.name)

    return sorted(regions)


def get_all_indicators(graph: dict) -> Set[str]:
    """Get set of all indicators (sources and targets) in a graph."""
    indicators = set()
    for edge in graph.get('edges', []):
        indicators.add(edge.get('source'))
        indicators.add(edge.get('target'))
    indicators.discard(None)
    return indicators


def get_edge_statistics(graph: dict) -> dict:
    """
    Get summary statistics for a graph's edges.

    Returns:
        Dict with edge count, relationship type distribution, significance stats
    """
    edges = graph.get('edges', [])

    if not edges:
        return {
            'n_edges': 0,
            'relationship_types': {},
            'significant_p01': 0,
            'significant_p05': 0,
            'mean_beta': None,
            'mean_r_squared': None
        }

    # Relationship type distribution
    rel_types = defaultdict(int)
    for e in edges:
        rel_types[e.get('relationship_type', 'linear')] += 1

    # Significance counts
    sig_01 = sum(1 for e in edges if e.get('p_value', 1) < 0.01)
    sig_05 = sum(1 for e in edges if e.get('p_value', 1) < 0.05)

    # Mean values
    betas = [e.get('beta', 0) for e in edges if e.get('beta') is not None]
    r2s = [e.get('r_squared', 0) for e in edges if e.get('r_squared') is not None]

    return {
        'n_edges': len(edges),
        'relationship_types': dict(rel_types),
        'significant_p01': sig_01,
        'significant_p05': sig_05,
        'mean_beta': sum(betas) / len(betas) if betas else None,
        'mean_r_squared': sum(r2s) / len(r2s) if r2s else None
    }


# =============================================================================
# TESTS
# =============================================================================

def _run_tests():
    """Run basic tests."""
    print("\nRunning graph loader tests...")
    print("-" * 40)

    # Test available years
    years = get_available_years(view_type='unified')
    assert len(years) > 0, "No unified years found"
    print(f"  Available unified years: {len(years)} (e.g., {years[:3]}...)")

    # Test available countries
    countries = get_available_countries()
    print(f"  Available countries: {len(countries)}")

    # Test loading a graph
    if countries and years:
        graph = load_temporal_graph(countries[0], years[-1])
        if graph:
            print(f"  Loaded {countries[0]} {years[-1]}: {graph.get('n_edges_filtered')} edges")
            print(f"    View used: {graph.get('view_used')}")

            # Test adjacency building
            adj = build_adjacency_v31(graph)
            print(f"    Adjacency nodes: {len(adj)}")

            # Test edge statistics
            stats = get_edge_statistics(graph)
            print(f"    Relationship types: {stats['relationship_types']}")

    print("-" * 40)
    print("Graph loader tests completed\n")


if __name__ == "__main__":
    _run_tests()
