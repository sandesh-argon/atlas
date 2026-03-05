"""
V3.1 Temporal Graph Loader

Loads year-specific causal graphs with fallback chain:
country/{country}/{year} -> stratified/{stratum}/{year} -> unified/{year}
"""

import json
from collections import defaultdict
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Literal, Set

from .income_classifier import get_stratum_for_country

# Project paths
V31_ROOT = Path(__file__).parent.parent
DATA_DIR = V31_ROOT / "data"
GRAPHS_DIR = DATA_DIR / "v3_1_temporal_graphs"

# Type definitions
ViewType = Literal['country', 'stratified', 'unified']
Stratum = Literal['developing', 'emerging', 'advanced']

# Valid year range
MIN_YEAR = 1990
MAX_YEAR = 2024


def _get_graph_path(
    view_type: ViewType,
    year: int,
    country: Optional[str] = None,
    stratum: Optional[Stratum] = None
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

    else:
        raise ValueError(f"Invalid view_type: {view_type}")


def _load_graph_file(path: Path) -> Optional[dict]:
    """Load a single graph file."""
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)


def load_temporal_graph(
    country: str,
    year: int,
    view_type: ViewType = 'country',
    p_value_threshold: float = 0.05,
    graphs_dir: Optional[Path] = None
) -> Optional[dict]:
    """
    Load year-specific graph with fallback chain.

    Fallback: country/{country}/{year} -> stratified/{stratum}/{year} -> unified/{year}

    Args:
        country: Country name (e.g., 'Australia')
        year: Year (1990-2024)
        view_type: Starting view type to try
        p_value_threshold: Filter edges by p-value (only keep p < threshold)
        graphs_dir: Override default graphs directory

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
    year = max(MIN_YEAR, min(MAX_YEAR, year))

    # Determine stratum for fallback (skip if unified or no country)
    stratum = get_stratum_for_country(country, year) if country and view_type != 'unified' else None

    # Define fallback chain
    if view_type == 'country':
        fallback_chain = [
            ('country', country, None),
            ('stratified', None, stratum) if stratum else None,
            ('unified', None, None)
        ]
    elif view_type == 'stratified':
        fallback_chain = [
            ('stratified', None, stratum) if stratum else None,
            ('unified', None, None)
        ]
    else:  # unified
        fallback_chain = [
            ('unified', None, None)
        ]

    # Remove None entries
    fallback_chain = [x for x in fallback_chain if x is not None]

    # Try each in chain
    for vtype, c, s in fallback_chain:
        if vtype == 'country':
            path = search_dir / "countries" / c / f"{year}_graph.json"
        elif vtype == 'stratified':
            path = search_dir / "stratified" / s / f"{year}_graph.json"
        else:  # unified
            path = search_dir / "unified" / f"{year}_graph.json"

        graph = _load_graph_file(path)
        if graph is not None:
            # Filter edges by p-value
            filtered_edges = [
                e for e in graph.get('edges', [])
                if e.get('p_value', 0) < p_value_threshold
            ]

            # Return with metadata
            return {
                **graph,
                'edges': filtered_edges,
                'view_used': vtype,
                'view_requested': view_type,
                'p_value_threshold': p_value_threshold,
                'n_edges_original': len(graph.get('edges', [])),
                'n_edges_filtered': len(filtered_edges)
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
            'marginal_effects': edge.get('marginal_effects'),
            'nonlinearity_metadata': edge.get('nonlinearity_metadata')
        }

        adjacency[source].append(edge_info)

    return dict(adjacency)


def get_available_years(
    country: Optional[str] = None,
    view_type: ViewType = 'unified'
) -> List[int]:
    """
    Get list of years with available graph data.

    Args:
        country: Country name (if checking country-specific availability)
        view_type: Which view to check

    Returns:
        Sorted list of available years
    """
    if view_type == 'country' and country is not None:
        search_path = GRAPHS_DIR / "countries" / country
    elif view_type == 'stratified':
        # Check all strata
        years = set()
        for stratum in ['developing', 'emerging', 'advanced']:
            stratum_path = GRAPHS_DIR / "stratified" / stratum
            if stratum_path.exists():
                for f in stratum_path.glob("*_graph.json"):
                    try:
                        year = int(f.stem.split('_')[0])
                        years.add(year)
                    except ValueError:
                        pass
        return sorted(years)
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
