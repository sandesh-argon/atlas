#!/usr/bin/env python3
"""
Phase 1: Generate Indicator Metadata

Creates metadata for all indicators including:
- Directionality: positive (higher is better) or negative (lower is better)
- Saturation thresholds: diminishing returns above certain values
- Units and bounds
- Domain classification

Output: data/metadata/indicator_properties.json
"""

import json
import re
from pathlib import Path
from datetime import datetime

import pandas as pd
import numpy as np

# Paths
PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
NODES_PATH = DATA_DIR / "raw" / "v21_nodes.csv"
PANEL_PATH = DATA_DIR / "raw" / "v21_panel_data_for_v3.parquet"
OUTPUT_PATH = DATA_DIR / "metadata" / "indicator_properties.json"


# === DIRECTIONALITY PATTERNS ===
# Keywords that indicate NEGATIVE direction (lower is better)

NEGATIVE_KEYWORDS = [
    # Mortality and death
    'mortality', 'death', 'deaths', 'dying', 'fatal',
    'imrt', 'mort', 'dth',  # Common codes

    # Poverty and deprivation
    'poverty', 'poor', 'deprivation', 'deprived',
    'undernourish', 'malnutrition', 'hunger', 'starv',

    # Violence and conflict
    'homicide', 'murder', 'violence', 'conflict', 'war',
    'crime', 'assault', 'abuse', 'torture',
    'refugee', 'displaced', 'idp',

    # Disease and illness
    'disease', 'illness', 'sick', 'morbidity',
    'hiv', 'aids', 'tuberculosis', 'malaria',
    'infection', 'epidemic', 'pandemic',

    # Inequality and unfairness
    'inequality', 'gini', 'disparity',

    # Pollution and environmental harm
    'pollution', 'emission', 'co2', 'carbon',
    'deforest', 'degradation',

    # Unemployment and economic hardship
    'unemployment', 'unemployed', 'jobless',
    'debt', 'deficit',

    # Corruption and bad governance
    'corruption', 'bribery', 'fraud',

    # Other negative outcomes
    'dropout', 'illiteracy', 'illiterate',
    'infant_mort', 'child_mort', 'maternal_mort',
    'stunting', 'wasting', 'underweight',
]

# Keywords that indicate POSITIVE direction (higher is better)
POSITIVE_KEYWORDS = [
    # Life and health
    'life_expectancy', 'lifexp', 'longevity',
    'survival', 'healthy',

    # Education
    'literacy', 'literate', 'education', 'school',
    'enrollment', 'completion', 'graduation',
    'years_schooling', 'attainment',

    # Economic prosperity
    'gdp', 'income', 'wealth', 'prosperity',
    'growth', 'productivity',
    'savings', 'investment',

    # Access and coverage
    'access', 'coverage', 'availability',
    'internet', 'electricity', 'water', 'sanitation',
    'healthcare', 'immunization', 'vaccination',

    # Freedom and rights
    'freedom', 'liberty', 'rights', 'democracy',
    'participation', 'representation',
    'press_freedom', 'civil_liberties',

    # Equality and inclusion
    'equality', 'inclusion', 'empowerment',
    'gender_parity',

    # Development
    'hdi', 'development', 'progress',

    # Safety and security
    'safety', 'security', 'stability', 'peace',
]

# Specific indicator patterns with known directions
KNOWN_INDICATORS = {
    # World Bank codes - Negative
    'SP.DYN.IMRT.IN': 'negative',      # Infant mortality rate
    'SP.DYN.IMRT.MA.IN': 'negative',   # Male infant mortality
    'SP.DYN.IMRT.FE.IN': 'negative',   # Female infant mortality
    'SH.DYN.MORT': 'negative',         # Under-5 mortality
    'SH.STA.MMRT': 'negative',         # Maternal mortality
    'SI.POV.GINI': 'negative',         # Gini coefficient
    'SI.POV.DDAY': 'negative',         # Poverty headcount
    'SL.UEM.TOTL.ZS': 'negative',      # Unemployment rate
    'VC.IHR.PSRC.P5': 'negative',      # Homicide rate
    'EN.ATM.CO2E.PC': 'negative',      # CO2 emissions per capita

    # World Bank codes - Positive
    'SP.DYN.LE00.IN': 'positive',      # Life expectancy
    'SP.DYN.LE00.MA.IN': 'positive',   # Male life expectancy
    'SP.DYN.LE00.FE.IN': 'positive',   # Female life expectancy
    'NY.GDP.PCAP.KD': 'positive',      # GDP per capita
    'NY.GDP.PCAP.PP.KD': 'positive',   # GDP per capita PPP
    'SE.ADT.LITR.ZS': 'positive',      # Adult literacy rate
    'SE.PRM.NENR': 'positive',         # Primary enrollment
    'SE.SEC.NENR': 'positive',         # Secondary enrollment
    'IT.NET.USER.ZS': 'positive',      # Internet users
    'EG.ELC.ACCS.ZS': 'positive',      # Electricity access
    'SH.H2O.BASW.ZS': 'positive',      # Water access
    'SH.STA.BASS.ZS': 'positive',      # Sanitation access

    # V-Dem codes - varies
    'v2x_polyarchy': 'positive',       # Electoral democracy
    'v2x_libdem': 'positive',          # Liberal democracy
    'v2x_partipdem': 'positive',       # Participatory democracy
    'v2x_freexp_altinf': 'positive',   # Freedom of expression
    'v2x_rule': 'positive',            # Rule of law
    'v2x_corr': 'negative',            # Corruption (V-Dem)
}

# Saturation thresholds (indicator patterns -> threshold)
SATURATION_PATTERNS = {
    # Percentage indicators (0-100 scale)
    r'\.ZS$': 100,           # World Bank percentage suffix
    r'rate': 100,            # Rates are often percentages
    r'literacy': 100,
    r'enrollment': 100,
    r'access': 100,
    r'coverage': 100,

    # Life expectancy (diminishing returns above ~80)
    r'life.*expect|lifexp': 85,

    # GDP per capita (diminishing returns above $50k)
    r'gdp.*cap|pcap': 50000,

    # Human Development Index (0-1 scale)
    r'hdi': 0.95,

    # Democracy indices (0-1 scale)
    r'v2x_': 0.9,
}


def load_nodes() -> pd.DataFrame:
    """Load node hierarchy."""
    print("Loading nodes...")
    nodes = pd.read_csv(NODES_PATH)
    print(f"  Loaded {len(nodes)} nodes")
    return nodes


def load_panel_stats() -> dict:
    """Load panel data and compute statistics for each indicator."""
    print("Loading panel data for statistics...")
    df = pd.read_parquet(PANEL_PATH)

    # Compute stats per indicator
    stats = df.groupby('indicator_id')['value'].agg(['min', 'max', 'mean', 'std', 'count'])
    stats = stats.to_dict('index')

    print(f"  Computed stats for {len(stats)} indicators")
    return stats


def classify_direction(indicator_id: str, label: str = "") -> tuple:
    """
    Classify indicator directionality.

    Returns: (direction, confidence, reason)
    """
    indicator_lower = indicator_id.lower()
    label_lower = label.lower() if label else ""
    combined = f"{indicator_lower} {label_lower}"

    # Check known indicators first
    if indicator_id in KNOWN_INDICATORS:
        return KNOWN_INDICATORS[indicator_id], 'high', 'known_indicator'

    # Check negative keywords
    for keyword in NEGATIVE_KEYWORDS:
        if keyword in combined:
            return 'negative', 'medium', f'keyword:{keyword}'

    # Check positive keywords
    for keyword in POSITIVE_KEYWORDS:
        if keyword in combined:
            return 'positive', 'medium', f'keyword:{keyword}'

    # Default: assume positive (most development indicators are positive)
    return 'positive', 'low', 'default'


def get_saturation_threshold(indicator_id: str, stats: dict) -> float | None:
    """
    Get saturation threshold for indicator.

    Returns threshold value or None if no saturation.
    """
    indicator_lower = indicator_id.lower()

    # Check patterns
    for pattern, threshold in SATURATION_PATTERNS.items():
        if re.search(pattern, indicator_lower):
            return threshold

    # Use data-driven threshold for percentage-like indicators
    if indicator_id in stats:
        max_val = stats[indicator_id]['max']
        if max_val is not None:
            # If max is around 100, likely a percentage
            if 95 <= max_val <= 105:
                return 100
            # If max is around 1, likely a 0-1 index
            if 0.9 <= max_val <= 1.1:
                return 1.0

    return None


def get_bounds(indicator_id: str, stats: dict) -> tuple:
    """Get min/max bounds for indicator."""
    if indicator_id in stats:
        return stats[indicator_id]['min'], stats[indicator_id]['max']
    return None, None


def infer_unit(indicator_id: str, label: str, min_val: float, max_val: float) -> str:
    """Infer unit from indicator patterns."""
    combined = f"{indicator_id} {label}".lower()

    # Common patterns
    if '.zs' in indicator_id.lower() or 'rate' in combined or 'percent' in combined:
        return 'percent'
    if 'gdp' in combined and 'cap' in combined:
        return 'USD'
    if 'population' in combined or 'pop' in indicator_id.lower():
        if max_val and max_val > 1e9:
            return 'persons'
        return 'thousands'
    if 'life' in combined and 'expect' in combined:
        return 'years'
    if 'years' in combined or 'schooling' in combined:
        return 'years'
    if max_val is not None:
        if 0 <= max_val <= 1.1:
            return 'index_0_1'
        if 0 <= max_val <= 10:
            return 'index_0_10'
        if 0 <= max_val <= 100:
            return 'index_0_100'

    return 'unknown'


def generate_metadata():
    """Generate complete indicator metadata."""
    print("=" * 60)
    print("Phase 1: Generate Indicator Metadata")
    print("=" * 60)

    # Load data
    nodes = load_nodes()
    stats = load_panel_stats()

    # Build metadata for each node
    print("\nClassifying indicators...")

    metadata = {}
    direction_counts = {'positive': 0, 'negative': 0}
    confidence_counts = {'high': 0, 'medium': 0, 'low': 0}

    for _, row in nodes.iterrows():
        indicator_id = row['id']
        label = row.get('label', '')
        domain = row.get('domain', '')
        layer = row.get('layer', 0)
        node_type = row.get('node_type', '')

        # Classify direction
        direction, confidence, reason = classify_direction(indicator_id, label)
        direction_counts[direction] += 1
        confidence_counts[confidence] += 1

        # Get saturation
        saturation = get_saturation_threshold(indicator_id, stats)

        # Get bounds
        min_val, max_val = get_bounds(indicator_id, stats)

        # Infer unit
        unit = infer_unit(indicator_id, label, min_val, max_val)

        metadata[indicator_id] = {
            'label': label,
            'domain': domain,
            'layer': int(layer) if pd.notna(layer) else 0,
            'node_type': node_type,
            'direction': direction,
            'direction_confidence': confidence,
            'direction_reason': reason,
            'saturation_threshold': saturation,
            'unit': unit,
            'bounds': {
                'min': float(min_val) if min_val is not None and pd.notna(min_val) else None,
                'max': float(max_val) if max_val is not None and pd.notna(max_val) else None
            },
            'has_data': indicator_id in stats,
            'n_observations': int(stats[indicator_id]['count']) if indicator_id in stats else 0
        }

    # Add indicators from panel data that aren't in nodes
    print("\nChecking for additional indicators in panel data...")
    panel_only = set(stats.keys()) - set(nodes['id'])
    print(f"  Found {len(panel_only)} indicators in panel but not in nodes")

    for indicator_id in panel_only:
        direction, confidence, reason = classify_direction(indicator_id, "")
        saturation = get_saturation_threshold(indicator_id, stats)
        min_val, max_val = get_bounds(indicator_id, stats)
        unit = infer_unit(indicator_id, "", min_val, max_val)

        metadata[indicator_id] = {
            'label': indicator_id,  # Use ID as label
            'domain': 'unknown',
            'layer': -1,  # Not in hierarchy
            'node_type': 'leaf',
            'direction': direction,
            'direction_confidence': confidence,
            'direction_reason': reason,
            'saturation_threshold': saturation,
            'unit': unit,
            'bounds': {
                'min': float(min_val) if min_val is not None and pd.notna(min_val) else None,
                'max': float(max_val) if max_val is not None and pd.notna(max_val) else None
            },
            'has_data': True,
            'n_observations': int(stats[indicator_id]['count'])
        }

        direction_counts[direction] += 1
        confidence_counts[confidence] += 1

    # Build output structure
    output = {
        'generated_date': datetime.now().isoformat(),
        'total_indicators': len(metadata),
        'summary': {
            'direction_counts': direction_counts,
            'confidence_counts': confidence_counts,
            'with_saturation': sum(1 for m in metadata.values() if m['saturation_threshold'] is not None),
            'with_data': sum(1 for m in metadata.values() if m['has_data'])
        },
        'indicators': metadata
    }

    # Save
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, 'w') as f:
        json.dump(output, f, indent=2)

    # Print summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total indicators: {len(metadata)}")
    print(f"Direction breakdown:")
    print(f"  Positive: {direction_counts['positive']}")
    print(f"  Negative: {direction_counts['negative']}")
    print(f"Confidence breakdown:")
    print(f"  High: {confidence_counts['high']}")
    print(f"  Medium: {confidence_counts['medium']}")
    print(f"  Low: {confidence_counts['low']}")
    print(f"With saturation thresholds: {output['summary']['with_saturation']}")
    print(f"With panel data: {output['summary']['with_data']}")
    print(f"\nSaved to: {OUTPUT_PATH}")
    print("=" * 60)

    return output


if __name__ == "__main__":
    generate_metadata()
