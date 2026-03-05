"""
Canonical Regional Mapping for V3.1 Simulation.

Provides deterministic mapping from countries with temporal graph data
(178 canonical country directories) to the 11-region hybrid taxonomy used
by regional spillovers and regional simulation views.
"""

from __future__ import annotations

import json
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional

# Paths
VIZ_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = VIZ_ROOT / "data"
TEMPORAL_COUNTRIES_DIR = DATA_ROOT / "v31" / "temporal_graphs" / "countries"
SPILLOVERS_FILE = DATA_ROOT / "v31" / "regional_spillovers.json"
WB_REGIONAL_GROUPS_FILE = DATA_ROOT / "v31" / "metadata" / "regional_groups.json"

# Supported 11-region hybrid keys (order matches regional_spillovers.json)
REGION_KEYS_11 = (
    "east_asia_pacific",
    "europe_central_asia",
    "latin_america_caribbean",
    "middle_east_north_africa",
    "north_america",
    "south_asia",
    "sub_saharan_africa",
    "western_europe",
    "eastern_europe",
    "central_asia",
    "southeast_asia",
)

# Geographic regions from WB groups before hybrid splitting.
WB_GEOGRAPHIC_KEYS = (
    "sub_saharan_africa",
    "east_asia_pacific",
    "europe_central_asia",
    "latin_america_caribbean",
    "middle_east_north_africa",
    "south_asia",
    "north_america",
)

# Canonicalization aliases used while ingesting WB regional groups.
COUNTRY_ALIASES = {
    "burma myanmar": "Myanmar",
    "cape verde": "Cape Verde",
    "czechia": "Czech Republic",
    "czech republic": "Czech Republic",
    "egypt arab rep": "Egypt, Arab Rep.",
    "gambia the": "Gambia",
    "hong kong": "Hong Kong",
    "iran islamic rep": "Iran, Islamic Rep.",
    "korea rep": "South Korea",
    "kyrgyz republic": "Kyrgyzstan",
    "lao pdr": "Laos",
    "macao": "Macao",
    "micronesia fed sts": "Micronesia",
    "north macedonia": "Macedonia",
    "russian federation": "Russia",
    "slovak republic": "Slovakia",
    "syrian arab republic": "Syria",
    "timor leste": "Timor-Leste",
    "turkiye": "Turkey",
    "usa": "United States",
    "united states of america": "United States",
    "venezuela rb": "Venezuela, RB",
    "viet nam": "Vietnam",
    "yemen rep": "Yemen",
}

# Split rules for 11-key hybrid model.
SOUTHEAST_ASIA_COUNTRIES = {
    "Brunei",
    "Cambodia",
    "Indonesia",
    "Laos",
    "Malaysia",
    "Myanmar",
    "Philippines",
    "Singapore",
    "Thailand",
    "Timor-Leste",
    "Vietnam",
}

CENTRAL_ASIA_COUNTRIES = {
    "Kazakhstan",
    "Kyrgyzstan",
    "Tajikistan",
    "Turkmenistan",
    "Uzbekistan",
}

WESTERN_EUROPE_COUNTRIES = {
    "Austria",
    "Belgium",
    "Cyprus",
    "Denmark",
    "Finland",
    "France",
    "Germany",
    "Greece",
    "Iceland",
    "Ireland",
    "Italy",
    "Luxembourg",
    "Malta",
    "Netherlands",
    "Norway",
    "Portugal",
    "Spain",
    "Sweden",
    "Switzerland",
    "United Kingdom",
}

EASTERN_EUROPE_COUNTRIES = {
    "Albania",
    "Belarus",
    "Bosnia and Herzegovina",
    "Bulgaria",
    "Croatia",
    "Czech Republic",
    "Hungary",
    "Macedonia",
    "Moldova",
    "Montenegro",
    "Poland",
    "Romania",
    "Serbia",
    "Slovakia",
    "Slovenia",
}

ECA_CORE_COUNTRIES = {
    "Armenia",
    "Azerbaijan",
    "Georgia",
    "Russia",
    "Turkey",
    "Ukraine",
}

# Deterministic overrides for historical/alias entities in the 178 set.
MANUAL_REGION_OVERRIDES = {
    "Congo": "sub_saharan_africa",
    "Democratic Republic of Congo": "sub_saharan_africa",
    "Egypt, Arab Rep.": "middle_east_north_africa",
    "German Democratic Republic": "eastern_europe",
    "Iran, Islamic Rep.": "middle_east_north_africa",
    "Ivory Coast": "sub_saharan_africa",
    "Somaliland": "sub_saharan_africa",
    "South Yemen": "middle_east_north_africa",
    "Swaziland": "sub_saharan_africa",
    "Venezuela, RB": "latin_america_caribbean",
    "Zanzibar": "sub_saharan_africa",
}


def _normalize_country_name(name: str) -> str:
    s = (name or "").strip().lower()
    s = s.replace("&", "and")
    s = s.replace("_", " ")
    s = s.replace("'", "")
    s = s.replace(".", "")
    s = s.replace(",", "")
    s = s.replace("-", " ")
    return " ".join(s.split())


def _list_canonical_countries() -> List[str]:
    if not TEMPORAL_COUNTRIES_DIR.exists():
        return []
    return sorted([d.name for d in TEMPORAL_COUNTRIES_DIR.iterdir() if d.is_dir()])


def _load_spillover_regions() -> Dict[str, dict]:
    if not SPILLOVERS_FILE.exists():
        return {}
    with open(SPILLOVERS_FILE) as f:
        data = json.load(f)
    return data.get("regions", {})


def _load_wb_geographic_groups() -> Dict[str, List[str]]:
    if not WB_REGIONAL_GROUPS_FILE.exists():
        return {}

    with open(WB_REGIONAL_GROUPS_FILE) as f:
        data = json.load(f)

    regions = data.get("regions", {})
    out: Dict[str, List[str]] = {}
    for key in WB_GEOGRAPHIC_KEYS:
        out[key] = regions.get(key, {}).get("countries", [])
    return out


def _canonicalize_country(raw_name: str, canonical_by_norm: Dict[str, str]) -> Optional[str]:
    normalized = _normalize_country_name(raw_name)
    # Direct normalized lookup
    canonical = canonical_by_norm.get(normalized)
    if canonical:
        return canonical

    # Alias lookup
    alias_target = COUNTRY_ALIASES.get(normalized)
    if alias_target:
        return canonical_by_norm.get(_normalize_country_name(alias_target))

    return None


def _split_hybrid_region(base_region: str, country: str) -> str:
    if base_region == "east_asia_pacific":
        if country in SOUTHEAST_ASIA_COUNTRIES:
            return "southeast_asia"
        return "east_asia_pacific"

    if base_region == "europe_central_asia":
        if country in WESTERN_EUROPE_COUNTRIES:
            return "western_europe"
        if country in EASTERN_EUROPE_COUNTRIES:
            return "eastern_europe"
        if country in CENTRAL_ASIA_COUNTRIES:
            return "central_asia"
        if country in ECA_CORE_COUNTRIES:
            return "europe_central_asia"
        return "europe_central_asia"

    return base_region


@lru_cache(maxsize=2)
def _build_country_region_map(strict: bool = True) -> Dict[str, str]:
    canonical_countries = _list_canonical_countries()
    canonical_by_norm = {_normalize_country_name(c): c for c in canonical_countries}

    wb_groups = _load_wb_geographic_groups()

    mapping: Dict[str, str] = {}

    # Base WB geographic assignment (7 regions)
    for region_key, raw_countries in wb_groups.items():
        for raw_country in raw_countries:
            canonical = _canonicalize_country(raw_country, canonical_by_norm)
            if canonical is None:
                continue
            mapping[canonical] = _split_hybrid_region(region_key, canonical)

    # Deterministic historical/manual overrides for the 178 canonical set.
    for country, region in MANUAL_REGION_OVERRIDES.items():
        if country in canonical_by_norm.values():
            mapping[country] = region

    # Validation
    invalid_regions = sorted({r for r in mapping.values() if r not in REGION_KEYS_11})
    if invalid_regions:
        raise ValueError(f"Invalid region keys in mapping: {invalid_regions}")

    missing = sorted([c for c in canonical_countries if c not in mapping])
    if strict and missing:
        raise ValueError(
            "Region mapping incomplete. Missing "
            f"{len(missing)} countries: {', '.join(missing[:20])}"
            + (" ..." if len(missing) > 20 else "")
        )

    return mapping


def get_country_region_map(strict: bool = True) -> Dict[str, str]:
    """Return canonical country -> region map for countries with graph data."""
    return dict(_build_country_region_map(strict=strict))


def get_region_for_country(country: str, strict: bool = False) -> Optional[str]:
    """Get hybrid region key for a country name (supports aliases/case-insensitive)."""
    if not country:
        return None

    # Fail fast on coverage regressions in canonical mapping.
    mapping = _build_country_region_map(strict=True)

    # Exact canonical lookup first
    if country in mapping:
        return mapping[country]

    # Normalized lookup against canonical names
    normalized = _normalize_country_name(country)
    for canonical, region in mapping.items():
        if _normalize_country_name(canonical) == normalized:
            return region

    # Alias lookup
    alias_target = COUNTRY_ALIASES.get(normalized)
    if alias_target and alias_target in mapping:
        return mapping[alias_target]

    if strict:
        raise ValueError(f"Country '{country}' is not mapped to a region")
    return None


def get_countries_in_region(region_key: str) -> List[str]:
    """Get sorted canonical countries in a region."""
    mapping = _build_country_region_map(strict=True)
    return sorted([country for country, region in mapping.items() if region == region_key])


def get_all_region_keys() -> List[str]:
    """Get configured region keys in stable order."""
    spillover_regions = _load_spillover_regions()
    if spillover_regions:
        return [key for key in spillover_regions.keys() if key in REGION_KEYS_11]
    return list(REGION_KEYS_11)


def get_region_metadata(region_key: str) -> Optional[dict]:
    """Get metadata for a region: display name, spillover strength, member count."""
    spillover_regions = _load_spillover_regions()
    base = spillover_regions.get(region_key, {})

    if not base and region_key not in REGION_KEYS_11:
        return None

    countries = get_countries_in_region(region_key)
    return {
        "region_key": region_key,
        "name": base.get("name", region_key.replace("_", " ").title()),
        "spillover_strength": base.get("spillover_strength"),
        "dominant_economy": base.get("dominant_economy"),
        "regional_leaders": base.get("regional_leaders", []),
        "country_count": len(countries),
        "countries": countries,
    }


def validate_region_mapping(strict: bool = True) -> dict:
    """Validate mapping coverage and return counts for diagnostics."""
    canonical_countries = _list_canonical_countries()
    mapping = _build_country_region_map(strict=False)

    missing = sorted([c for c in canonical_countries if c not in mapping])
    counts = dict(sorted(Counter(mapping.values()).items()))

    if strict and missing:
        raise ValueError(f"Missing regional mappings for {len(missing)} countries")

    return {
        "total_countries": len(canonical_countries),
        "mapped_countries": len(mapping),
        "missing_countries": missing,
        "region_counts": counts,
    }


def clear_cache() -> None:
    """Clear module caches (useful for tests/dev)."""
    _build_country_region_map.cache_clear()


if __name__ == "__main__":
    report = validate_region_mapping(strict=False)
    print("Region mapping validation")
    print(f"  Total countries: {report['total_countries']}")
    print(f"  Mapped: {report['mapped_countries']}")
    print(f"  Missing: {len(report['missing_countries'])}")
    if report["missing_countries"]:
        print(f"  Missing sample: {report['missing_countries'][:10]}")
    print("  Region counts:")
    for key, count in report["region_counts"].items():
        print(f"    {key}: {count}")
