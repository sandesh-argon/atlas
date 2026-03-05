"""
Income Classification Module

Provides dynamic income classification lookup for countries by year.
Uses World Bank GNI per capita thresholds.
"""

import json
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Literal

# Project paths
DATA_ROOT = Path(__file__).parent.parent / "data"
INCOME_FILE = DATA_ROOT / "v31" / "metadata" / "income_classifications.json"

# Type definitions
Stratum = Literal['developing', 'emerging', 'advanced']


@lru_cache(maxsize=1)
def load_income_classifications() -> dict:
    """
    Load income classifications from metadata file.

    Cached to avoid repeated file reads.

    Returns:
        Dict with 'metadata', 'thresholds', and 'countries' keys
    """
    if not INCOME_FILE.exists():
        raise FileNotFoundError(f"Income classifications file not found: {INCOME_FILE}")

    with open(INCOME_FILE) as f:
        return json.load(f)


def get_country_classification(country: str, year: int) -> Optional[dict]:
    """
    Get country's income classification for a specific year.

    Args:
        country: Country name (e.g., 'Australia', 'Rwanda')
        year: Year (1990-2024)

    Returns:
        Dict with:
        - group_4tier: 'Low income'|'Lower middle income'|'Upper middle income'|'High income'
        - group_3tier: 'Developing'|'Emerging'|'Advanced'
        - gni_per_capita: GNI per capita value (may be None if interpolated)

        Returns None if country not found

    Example:
        >>> get_country_classification('Australia', 2020)
        {'group_4tier': 'High income', 'group_3tier': 'Advanced', 'gni_per_capita': 53770.0}
    """
    data = load_income_classifications()

    # Handle country name variations
    country_data = data.get('countries', {}).get(country)
    if country_data is None:
        # Try case-insensitive match
        for name, info in data.get('countries', {}).items():
            if name.lower() == country.lower():
                country_data = info
                break

    if country_data is None:
        return None

    # Get year-specific classification
    year_str = str(year)
    year_data = country_data.get('by_year', {}).get(year_str)

    if year_data is None:
        # Fall back to current classification if year not found
        return {
            'group_4tier': country_data.get('current_classification_4tier', 'Unknown'),
            'group_3tier': country_data.get('current_classification_3tier', 'Unknown'),
            'gni_per_capita': None
        }

    return {
        'group_4tier': year_data.get('classification_4tier', 'Unknown'),
        'group_3tier': year_data.get('classification_3tier', 'Unknown'),
        'gni_per_capita': year_data.get('gni_per_capita')
    }


def get_stratum_for_country(country: str, year: int) -> Optional[Stratum]:
    """
    Map country to its 3-tier stratum (developing/emerging/advanced) for a year.

    Args:
        country: Country name
        year: Year (1990-2024)

    Returns:
        'developing', 'emerging', or 'advanced' (lowercase)
        Returns None if country not found

    Example:
        >>> get_stratum_for_country('Rwanda', 2020)
        'developing'
        >>> get_stratum_for_country('China', 2015)
        'emerging'
    """
    classification = get_country_classification(country, year)
    if classification is None:
        return None

    group_3tier = (classification.get('group_3tier') or '').lower()

    if group_3tier in ['developing', 'emerging', 'advanced']:
        return group_3tier

    # Map from 4-tier if 3-tier not available
    group_4tier = (classification.get('group_4tier') or '').lower()
    tier_mapping = {
        'low income': 'developing',
        'lower middle income': 'developing',
        'upper middle income': 'emerging',
        'high income': 'advanced'
    }
    return tier_mapping.get(group_4tier)


def get_countries_in_stratum(stratum: Stratum, year: int) -> List[str]:
    """
    Get all countries in a stratum for a specific year.

    Args:
        stratum: 'developing', 'emerging', or 'advanced'
        year: Year (1990-2024)

    Returns:
        List of country names in that stratum for that year

    Example:
        >>> countries = get_countries_in_stratum('advanced', 2020)
        >>> 'Australia' in countries
        True
    """
    data = load_income_classifications()

    # Normalize stratum name
    stratum_mapping = {
        'developing': 'Developing',
        'emerging': 'Emerging',
        'advanced': 'Advanced'
    }
    target_stratum = stratum_mapping.get(stratum.lower(), stratum)

    countries = []
    year_str = str(year)

    for country_name, country_data in data.get('countries', {}).items():
        year_data = country_data.get('by_year', {}).get(year_str)

        if year_data:
            if year_data.get('classification_3tier') == target_stratum:
                countries.append(country_name)
        else:
            # Fall back to current classification
            if country_data.get('current_classification_3tier') == target_stratum:
                countries.append(country_name)

    return sorted(countries)


def get_stratum_counts(year: int) -> Dict[str, int]:
    """
    Get count of countries in each stratum for a year.

    Args:
        year: Year (1990-2024)

    Returns:
        Dict mapping stratum to country count

    Example:
        >>> get_stratum_counts(2020)
        {'developing': 72, 'emerging': 44, 'advanced': 62}
    """
    return {
        'developing': len(get_countries_in_stratum('developing', year)),
        'emerging': len(get_countries_in_stratum('emerging', year)),
        'advanced': len(get_countries_in_stratum('advanced', year))
    }


def get_available_years() -> List[int]:
    """Get list of years with income classification data."""
    data = load_income_classifications()
    years = data.get('metadata', {}).get('years', [])
    return sorted(years)


def clear_cache():
    """Clear the LRU cache (useful for testing)."""
    load_income_classifications.cache_clear()


# =============================================================================
# TESTS
# =============================================================================

def _run_tests():
    """Run basic tests."""
    print("\nRunning income classifier tests...")
    print("-" * 40)

    # Test loading
    data = load_income_classifications()
    assert 'countries' in data
    assert 'thresholds' in data
    print("  load_income_classifications: PASS")

    # Test country classification
    aus = get_country_classification('Australia', 2020)
    assert aus is not None
    assert aus['group_3tier'] == 'Advanced'
    print("  get_country_classification: PASS")

    # Test stratum lookup
    stratum = get_stratum_for_country('Australia', 2020)
    assert stratum == 'advanced'
    print("  get_stratum_for_country: PASS")

    # Test countries in stratum
    advanced = get_countries_in_stratum('advanced', 2020)
    assert 'Australia' in advanced
    print("  get_countries_in_stratum: PASS")

    # Test counts
    counts = get_stratum_counts(2020)
    assert counts['developing'] > 0
    assert counts['emerging'] > 0
    assert counts['advanced'] > 0
    print("  get_stratum_counts: PASS")

    print("-" * 40)
    print("All income classifier tests PASSED\n")


if __name__ == "__main__":
    _run_tests()
