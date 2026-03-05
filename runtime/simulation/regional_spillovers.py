"""
Regional Spillover Effects Module

Computes regional spillover effects based on proxy coefficients.
Real bilateral spillovers deferred to V3.2.

Formula: regional_effect = direct_effect * spillover_strength
"""

import json
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Set

from .region_mapping import (
    get_region_for_country as get_region_for_country_canonical,
    get_countries_in_region as get_countries_in_region_canonical,
    get_region_metadata as get_region_metadata_canonical,
    validate_region_mapping,
    clear_cache as clear_region_mapping_cache,
)

# Project paths
DATA_ROOT = Path(__file__).parent.parent / "data"
SPILLOVERS_FILE = DATA_ROOT / "v31" / "regional_spillovers.json"

@lru_cache(maxsize=1)
def load_regional_spillovers() -> dict:
    """
    Load regional spillover coefficients.

    Returns:
        Dict with 'regions', 'global_powers', and 'usage' keys
    """
    if not SPILLOVERS_FILE.exists():
        raise FileNotFoundError(f"Spillovers file not found: {SPILLOVERS_FILE}")

    with open(SPILLOVERS_FILE) as f:
        return json.load(f)


def get_country_region(country: str) -> Optional[str]:
    """
    Map country to its primary region.

    Args:
        country: Country name

    Returns:
        Region key (e.g., 'east_asia_pacific') or None if not mapped

    Example:
        >>> get_country_region('Australia')
        'east_asia_pacific'
    """
    return get_region_for_country_canonical(country, strict=False)


def get_spillover_coefficient(country: str) -> float:
    """
    Get regional spillover coefficient for a country.

    Args:
        country: Country name

    Returns:
        Spillover strength (0-1), or 0.0 if country not mapped
    """
    region = get_country_region(country)
    if region is None:
        return 0.0

    data = load_regional_spillovers()
    region_data = data.get('regions', {}).get(region)

    if region_data is None:
        return 0.0

    return region_data.get('spillover_strength', 0.0)


def get_region_info(country: str) -> Optional[dict]:
    """
    Get full region information for a country.

    Args:
        country: Country name

    Returns:
        Dict with region details or None
    """
    region = get_country_region(country)
    if region is None:
        return None

    metadata = get_region_metadata_canonical(region)
    if metadata is None:
        return None

    data = load_regional_spillovers()
    rationale = data.get('regions', {}).get(region, {}).get('rationale')

    return {
        'region_key': metadata.get('region_key'),
        'name': metadata.get('name'),
        'spillover_strength': metadata.get('spillover_strength'),
        'dominant_economy': metadata.get('dominant_economy'),
        'regional_leaders': metadata.get('regional_leaders', []),
        'rationale': rationale,
        'country_count': metadata.get('country_count'),
    }


def is_global_power(country: str) -> bool:
    """Check if country is a global power with extra-regional spillovers."""
    # Map country names to ISO codes
    country_to_iso = {
        'United States': 'USA',
        'United States of America': 'USA',
        'China': 'CHN',
        'Germany': 'DEU'
    }

    iso = country_to_iso.get(country)
    if iso is None:
        return False

    data = load_regional_spillovers()
    return iso in data.get('global_powers', {}).get('countries', {})


def get_global_power_spillover(country: str) -> Optional[dict]:
    """
    Get global spillover info for a global power country.

    Returns:
        Dict with global_spillover_strength and channels, or None
    """
    country_to_iso = {
        'United States': 'USA',
        'United States of America': 'USA',
        'China': 'CHN',
        'Germany': 'DEU'
    }

    iso = country_to_iso.get(country)
    if iso is None:
        return None

    data = load_regional_spillovers()
    return data.get('global_powers', {}).get('countries', {}).get(iso)


def compute_regional_spillover(
    country: str,
    effects: Dict[str, float],
    affected_indicators: Optional[Set[str]] = None
) -> Dict[str, dict]:
    """
    Compute regional spillover effects from a country's intervention effects.

    Formula: regional_effect = direct_effect * spillover_strength

    Args:
        country: Country where intervention occurred
        effects: Dict mapping indicator to absolute change
        affected_indicators: Optional set to filter which indicators have spillovers

    Returns:
        Dict with:
        - 'regional': {indicator: {effect, spillover_strength, region}}
        - 'global': {indicator: {effect, spillover_strength}} (if global power)
        - 'metadata': {region, spillover_strength, is_global_power}

    Example:
        >>> effects = {'gdp_per_capita': 500, 'life_expectancy': 0.5}
        >>> spillovers = compute_regional_spillover('United States', effects)
        >>> spillovers['regional']['gdp_per_capita']['effect']
        275.0  # 500 * 0.55 (North America spillover)
    """
    result = {
        'regional': {},
        'global': {},
        'metadata': {
            'country': country,
            'region': None,
            'spillover_strength': 0.0,
            'is_global_power': False,
            'global_spillover_strength': 0.0
        }
    }

    # Get regional info
    region = get_country_region(country)
    spillover_coef = get_spillover_coefficient(country)

    result['metadata']['region'] = region
    result['metadata']['spillover_strength'] = spillover_coef

    # Compute regional spillovers
    for indicator, direct_effect in effects.items():
        if affected_indicators is not None and indicator not in affected_indicators:
            continue

        if spillover_coef > 0 and direct_effect != 0:
            regional_effect = direct_effect * spillover_coef
            result['regional'][indicator] = {
                'effect': regional_effect,
                'spillover_strength': spillover_coef,
                'region': region,
                'direct_effect': direct_effect
            }

    # Check for global power spillovers (additional to regional)
    if is_global_power(country):
        result['metadata']['is_global_power'] = True
        global_info = get_global_power_spillover(country)

        if global_info:
            global_coef = global_info.get('global_spillover_strength', 0)
            result['metadata']['global_spillover_strength'] = global_coef
            result['metadata']['global_channels'] = global_info.get('channels', [])

            for indicator, direct_effect in effects.items():
                if affected_indicators is not None and indicator not in affected_indicators:
                    continue

                if global_coef > 0 and direct_effect != 0:
                    global_effect = direct_effect * global_coef
                    result['global'][indicator] = {
                        'effect': global_effect,
                        'spillover_strength': global_coef,
                        'direct_effect': direct_effect
                    }

    return result


def get_all_regions() -> List[str]:
    """Get list of all region keys."""
    data = load_regional_spillovers()
    return list(data.get('regions', {}).keys())


def get_region_countries(region: str) -> List[str]:
    """Get all canonical countries in a region."""
    return get_countries_in_region_canonical(region)


def clear_cache():
    """Clear the LRU cache (useful for testing)."""
    load_regional_spillovers.cache_clear()
    clear_region_mapping_cache()


# =============================================================================
# TESTS
# =============================================================================

def _run_tests():
    """Run basic tests."""
    print("\nRunning regional spillovers tests...")
    print("-" * 40)

    # Test loading
    data = load_regional_spillovers()
    assert 'regions' in data
    assert 'global_powers' in data
    print("  load_regional_spillovers: PASS")

    # Test mapping coverage
    mapping_report = validate_region_mapping(strict=True)
    assert mapping_report['mapped_countries'] == mapping_report['total_countries']
    print(f"  validate_region_mapping: PASS ({mapping_report['mapped_countries']} countries)")

    # Test region mapping
    region = get_country_region('Australia')
    assert region == 'east_asia_pacific'
    print("  get_country_region: PASS")

    # Test spillover coefficient
    coef = get_spillover_coefficient('United States')
    assert coef == 0.55  # North America
    print(f"  get_spillover_coefficient (USA): {coef} PASS")

    # Test global power detection
    assert is_global_power('United States') is True
    assert is_global_power('Australia') is False
    print("  is_global_power: PASS")

    # Test spillover computation
    effects = {'gdp': 100, 'education': 50}
    spillovers = compute_regional_spillover('United States', effects)
    assert spillovers['regional']['gdp']['effect'] == 55.0  # 100 * 0.55
    assert spillovers['metadata']['is_global_power'] is True
    print("  compute_regional_spillover: PASS")

    # Test region info
    info = get_region_info('Australia')
    assert info is not None
    assert info['spillover_strength'] == 0.45
    print("  get_region_info: PASS")

    print("-" * 40)
    print("All regional spillovers tests PASSED\n")


if __name__ == "__main__":
    _run_tests()
