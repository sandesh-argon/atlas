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

# Project paths
V31_ROOT = Path(__file__).parent.parent
DATA_DIR = V31_ROOT / "data"
SPILLOVERS_FILE = DATA_DIR / "regional_spillovers.json"

# Country to region mapping (derived from World Bank regions)
# This is a simplified mapping - full mapping could be loaded from metadata
COUNTRY_REGION_MAP = {
    # East Asia & Pacific
    'Australia': 'east_asia_pacific',
    'China': 'east_asia_pacific',
    'Japan': 'east_asia_pacific',
    'South Korea': 'east_asia_pacific',
    'Korea, Rep.': 'east_asia_pacific',
    'Indonesia': 'southeast_asia',
    'Thailand': 'southeast_asia',
    'Vietnam': 'southeast_asia',
    'Malaysia': 'southeast_asia',
    'Singapore': 'southeast_asia',
    'Philippines': 'southeast_asia',
    'Myanmar': 'southeast_asia',
    'Cambodia': 'southeast_asia',
    'New Zealand': 'east_asia_pacific',

    # Europe & Central Asia
    'Germany': 'western_europe',
    'France': 'western_europe',
    'United Kingdom': 'western_europe',
    'Italy': 'western_europe',
    'Spain': 'western_europe',
    'Netherlands': 'western_europe',
    'Belgium': 'western_europe',
    'Switzerland': 'western_europe',
    'Austria': 'western_europe',
    'Sweden': 'western_europe',
    'Norway': 'western_europe',
    'Denmark': 'western_europe',
    'Finland': 'western_europe',
    'Ireland': 'western_europe',
    'Portugal': 'western_europe',
    'Greece': 'western_europe',
    'Poland': 'eastern_europe',
    'Czech Republic': 'eastern_europe',
    'Czechia': 'eastern_europe',
    'Hungary': 'eastern_europe',
    'Romania': 'eastern_europe',
    'Bulgaria': 'eastern_europe',
    'Slovakia': 'eastern_europe',
    'Croatia': 'eastern_europe',
    'Slovenia': 'eastern_europe',
    'Russia': 'europe_central_asia',
    'Russian Federation': 'europe_central_asia',
    'Ukraine': 'europe_central_asia',
    'Turkey': 'europe_central_asia',
    'Kazakhstan': 'central_asia',
    'Uzbekistan': 'central_asia',
    'Turkmenistan': 'central_asia',
    'Kyrgyzstan': 'central_asia',
    'Tajikistan': 'central_asia',

    # Latin America & Caribbean
    'Brazil': 'latin_america_caribbean',
    'Mexico': 'latin_america_caribbean',
    'Argentina': 'latin_america_caribbean',
    'Chile': 'latin_america_caribbean',
    'Colombia': 'latin_america_caribbean',
    'Peru': 'latin_america_caribbean',
    'Venezuela': 'latin_america_caribbean',
    'Ecuador': 'latin_america_caribbean',
    'Bolivia': 'latin_america_caribbean',
    'Paraguay': 'latin_america_caribbean',
    'Uruguay': 'latin_america_caribbean',

    # Middle East & North Africa
    'Saudi Arabia': 'middle_east_north_africa',
    'United Arab Emirates': 'middle_east_north_africa',
    'Egypt': 'middle_east_north_africa',
    'Iran': 'middle_east_north_africa',
    'Iraq': 'middle_east_north_africa',
    'Israel': 'middle_east_north_africa',
    'Jordan': 'middle_east_north_africa',
    'Lebanon': 'middle_east_north_africa',
    'Morocco': 'middle_east_north_africa',
    'Algeria': 'middle_east_north_africa',
    'Tunisia': 'middle_east_north_africa',
    'Libya': 'middle_east_north_africa',
    'Kuwait': 'middle_east_north_africa',
    'Qatar': 'middle_east_north_africa',
    'Oman': 'middle_east_north_africa',
    'Bahrain': 'middle_east_north_africa',

    # North America
    'United States': 'north_america',
    'United States of America': 'north_america',
    'Canada': 'north_america',

    # South Asia
    'India': 'south_asia',
    'Pakistan': 'south_asia',
    'Bangladesh': 'south_asia',
    'Sri Lanka': 'south_asia',
    'Nepal': 'south_asia',
    'Afghanistan': 'south_asia',
    'Bhutan': 'south_asia',
    'Maldives': 'south_asia',

    # Sub-Saharan Africa
    'South Africa': 'sub_saharan_africa',
    'Nigeria': 'sub_saharan_africa',
    'Kenya': 'sub_saharan_africa',
    'Ethiopia': 'sub_saharan_africa',
    'Ghana': 'sub_saharan_africa',
    'Tanzania': 'sub_saharan_africa',
    'Uganda': 'sub_saharan_africa',
    'Rwanda': 'sub_saharan_africa',
    'Senegal': 'sub_saharan_africa',
    'Ivory Coast': 'sub_saharan_africa',
    "Cote d'Ivoire": 'sub_saharan_africa',
    'Cameroon': 'sub_saharan_africa',
    'Zimbabwe': 'sub_saharan_africa',
    'Zambia': 'sub_saharan_africa',
    'Mozambique': 'sub_saharan_africa',
    'Angola': 'sub_saharan_africa',
    'Democratic Republic of Congo': 'sub_saharan_africa',
    'Congo, Dem. Rep.': 'sub_saharan_africa',
}


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
    # Direct lookup
    region = COUNTRY_REGION_MAP.get(country)
    if region:
        return region

    # Try case-insensitive match
    country_lower = country.lower()
    for name, reg in COUNTRY_REGION_MAP.items():
        if name.lower() == country_lower:
            return reg

    return None


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

    data = load_regional_spillovers()
    region_data = data.get('regions', {}).get(region)

    if region_data is None:
        return None

    return {
        'region_key': region,
        'name': region_data.get('name'),
        'spillover_strength': region_data.get('spillover_strength'),
        'dominant_economy': region_data.get('dominant_economy'),
        'regional_leaders': region_data.get('regional_leaders', []),
        'rationale': region_data.get('rationale')
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
    """Get all countries in a region (from the mapping)."""
    return [
        country for country, reg in COUNTRY_REGION_MAP.items()
        if reg == region
    ]


def clear_cache():
    """Clear the LRU cache (useful for testing)."""
    load_regional_spillovers.cache_clear()


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
