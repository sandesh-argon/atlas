#!/usr/bin/env python3
"""
Generate Human-Readable Labels for All V2.1 Indicators
=======================================================

Creates comprehensive label mappings for all 1,962 nodes in the V2.1 causal graph.

Sources (same as V2.0):
1. World Bank indicators (30K+ entries)
2. V-Dem codebook patterns
3. UNESCO UIS indicator patterns
4. WID (World Inequality Database) patterns
5. QoG/Polity patterns
6. Penn World Tables
7. WHO indicators
8. Pattern-based inference for remaining

Output:
- indicator_labels_comprehensive.json (in outputs/B1/)
- coverage_report.txt

Author: V2.1 Label Generation (adapted from V2.0)
Date: December 2025
"""

import json
import csv
import re
import pickle
from pathlib import Path
from collections import defaultdict
from datetime import datetime

# ============================================================================
# Setup
# ============================================================================

V21_ROOT = Path('<repo-root>/v2.0/v2.1')
V20_ROOT = Path('<repo-root>/v2.0')
INDICATORS_DIR = V20_ROOT / 'indicators'
OUTPUT_DIR = V21_ROOT / 'outputs/B1'
OUTPUT_DIR.mkdir(exist_ok=True, parents=True)

print("="*80)
print("V2.1 INDICATOR LABEL GENERATION")
print("="*80)
print(f"\nTimestamp: {datetime.now().isoformat()}")

# ============================================================================
# Load All Node IDs from V2.1
# ============================================================================

print("\n" + "="*80)
print("LOADING V2.1 NODE IDS")
print("="*80)

# Load from A6 graph
with open(V21_ROOT / 'outputs/A6/A6_hierarchical_graph.pkl', 'rb') as f:
    a6_data = pickle.load(f)

all_node_ids = set(a6_data['graph'].nodes())
print(f"Total V2.1 nodes to label: {len(all_node_ids):,}")

# Initialize label storage
labels = {}  # id -> {label, source, description}

# ============================================================================
# Source 1: World Bank Indicators (30K+)
# ============================================================================

print("\n" + "="*80)
print("LOADING WORLD BANK INDICATORS")
print("="*80)

wb_path = INDICATORS_DIR / 'world_bank_indicators.csv'
wb_labels = {}

with open(wb_path, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        indicator_id = row['id']
        name = row['name']
        source = row.get('source', 'World Bank')
        wb_labels[indicator_id] = {
            'label': name,
            'source': source,
            'description': row.get('sourceNote', '')[:500] if row.get('sourceNote') else ''
        }

print(f"Loaded {len(wb_labels):,} World Bank indicators")

# Create lowercase lookup for fuzzy matching
wb_labels_lower = {k.lower(): (k, v) for k, v in wb_labels.items()}

# Match World Bank indicators
wb_matched = 0
for node_id in all_node_ids:
    # Direct match
    if node_id in wb_labels:
        labels[node_id] = wb_labels[node_id]
        wb_matched += 1
    elif node_id.lower() in wb_labels_lower:
        orig_id, wb_info = wb_labels_lower[node_id.lower()]
        labels[node_id] = wb_info
        wb_matched += 1

print(f"Matched {wb_matched} nodes from World Bank")

# ============================================================================
# Source 2: V-Dem Indicator Patterns
# ============================================================================

print("\n" + "="*80)
print("GENERATING V-DEM LABELS")
print("="*80)

# V-Dem naming conventions
vdem_prefixes = {
    'v2x': 'Index',
    'v2ex': 'Executive',
    'v2lg': 'Legislature',
    'v2ju': 'Judiciary',
    'v2cl': 'Civil Liberties',
    'v2ps': 'Political Parties',
    'v2el': 'Elections',
    'v2dl': 'Deliberation',
    'v2ca': 'Civil Society',
    'v2cs': 'Civil Society',
    'v2sm': 'Social Media',
    'v2pe': 'Political Equality',
    'v2me': 'Media',
    'v2ed': 'Education',
    'v2reg': 'Regime',
    'v2st': 'State',
    'v2xnp': 'Neopatrimonialism',
    'v2xel': 'Electoral',
    'v3pe': 'Political Economy',
    'v3st': 'State Capacity',
}

vdem_suffixes = {
    '_ord': ' (Ordinal)',
    '_osp': ' (Original Scale Point)',
    '_mean': ' (Mean)',
    '_nr': ' (Non-Response)',
    '_codehigh': ' (High)',
    '_codelow': ' (Low)',
}

def generate_vdem_label(code):
    """Generate human-readable label for V-Dem indicator."""
    # Handle numbered suffixes like _5, _7
    base = re.sub(r'_\d+$', '', code)
    num_suffix = re.search(r'_(\d+)$', code)

    # Find matching prefix
    label_prefix = 'V-Dem'
    for prefix, desc in vdem_prefixes.items():
        if code.startswith(prefix):
            label_prefix = desc
            base = base[len(prefix):]
            break

    # Apply suffix transformations
    suffix_desc = ''
    for suffix, desc in vdem_suffixes.items():
        if suffix in base:
            suffix_desc = desc
            base = base.replace(suffix, '')
            break

    # Convert camelCase/mixedCase to Title Case
    base = re.sub(r'([a-z])([A-Z])', r'\1 \2', base)
    base = base.replace('_', ' ').title().strip()

    # Add number suffix if present
    if num_suffix:
        base += f" ({num_suffix.group(1)})"

    return f"{label_prefix}: {base}{suffix_desc}"

# Match V-Dem indicators
vdem_matched = 0
for node_id in all_node_ids:
    if node_id not in labels and (node_id.startswith('v2') or node_id.startswith('v3')):
        labels[node_id] = {
            'label': generate_vdem_label(node_id),
            'source': 'V-Dem Institute',
            'description': f'V-Dem indicator measuring {generate_vdem_label(node_id).lower()}'
        }
        vdem_matched += 1
    elif node_id not in labels and node_id.startswith('vdem_'):
        base = node_id[5:]  # Remove 'vdem_' prefix
        labels[node_id] = {
            'label': f"V-Dem: {base.replace('_', ' ').title()}",
            'source': 'V-Dem Institute',
            'description': f'V-Dem indicator {node_id}'
        }
        vdem_matched += 1

print(f"Generated {vdem_matched} V-Dem labels")

# ============================================================================
# Source 3: UNESCO UIS Indicator Patterns
# ============================================================================

print("\n" + "="*80)
print("GENERATING UNESCO UIS LABELS")
print("="*80)

# UNESCO indicator code patterns
unesco_codes = {
    'EA': 'Educational Attainment',
    'CR': 'Completion Rate',
    'SCHBSP': 'School-Based Support Programs',
    'NERT': 'Net Enrollment Rate Tertiary',
    'NERA': 'Net Enrollment Rate Adjusted',
    'NER': 'Net Enrollment Rate',
    'GER': 'Gross Enrollment Rate',
    'QUTP': 'Qualified Teachers (%)',
    'REPR': 'Repetition Rate',
    'LR': 'Literacy Rate',
    'ROFST': 'Rate of Out-of-School',
    'OFST': 'Out-of-School',
    'TRTP': 'Teacher Training',
    'PTRHC': 'Pupil-Teacher Ratio',
    'SLE': 'School Life Expectancy',
    'PRYA': 'Participation Rate Young Adults',
    'FTP': 'Full-Time Teachers',
    'ETOIP': 'Education Teacher Outreach',
    'SAP': 'Standardized Achievement Percentile',
    'GTVP': 'Gross Tertiary Vocational',
    'OAEPG': 'Out of School Age Education Program',
    'OE': 'Out-of-School Estimate',
    'MOGER': 'Modified Gross Enrollment Rate',
    'XSPENDP': 'Expenditure per Pupil',
    'XUNIT': 'Unit Cost',
    'AIR': 'Adjusted Intake Rate',
    'NART': 'Net Adjusted Rate Tertiary',
    'FOSGP': 'First-time Outbound Students',
    'FRESP': 'Freshmen Response',
    'MOR': 'Mobility Rate',
    'CM': 'Completion Monitoring',
}

# Education level codes
edu_levels = {
    '1': 'Primary',
    '2': 'Lower Secondary',
    '3': 'Upper Secondary',
    '2T3': 'Secondary',
    '5T8': 'Tertiary',
    '4': 'Post-Secondary',
    '5': 'Short-Cycle Tertiary',
    '6': 'Bachelor',
    '7': 'Master',
    '8': 'Doctoral',
    'S1T8': 'All Levels',
    '1T3': 'Primary to Upper Secondary',
    '3T8': 'Upper Secondary to Tertiary',
}

# Age groups
age_groups = {
    'AG25T99': 'Age 25+',
    'AG25T64': 'Age 25-64',
    'AG25T54': 'Age 25-54',
    'AG15T24': 'Age 15-24',
    'AG15T99': 'Age 15+',
}

# Gender codes
gender_codes = {
    '.F': ', Female',
    '.M': ', Male',
    '.GPIA': ', Gender Parity Index',
    '.WPIA': ', Wealth Parity Index',
    '.LPIA': ', Location Parity Index',
    '.F.': ' Female,',
    '.M.': ' Male,',
}

# Location codes
location_codes = {
    '.URB': ', Urban',
    '.RUR': ', Rural',
    'URB.': 'Urban ',
    'RUR.': 'Rural ',
}

def generate_unesco_label(code):
    """Generate human-readable label for UNESCO UIS indicator."""
    parts = code.split('.')

    # Get base indicator
    base_code = parts[0]
    # Handle underscore format like CM_03
    if '_' in base_code:
        base_parts = base_code.split('_')
        base_code = base_parts[0]

    indicator_name = unesco_codes.get(base_code, base_code)

    label_parts = [indicator_name]

    # Parse remaining parts
    rest = '.'.join(parts[1:]) if len(parts) > 1 else ''
    rest_full = code  # Use full code for pattern matching

    # Education level
    for level_code, level_name in edu_levels.items():
        if level_code in rest_full:
            label_parts.append(level_name)
            break

    # Age group
    for age_code, age_name in age_groups.items():
        if age_code in rest_full:
            label_parts.append(age_name)
            break

    # Location
    for loc_code, loc_name in location_codes.items():
        if loc_code in rest_full or loc_code.strip('.') in rest_full:
            label_parts.append(loc_name.strip(', '))
            break

    # Gender (add last)
    gender_str = ''
    for gen_code, gen_name in gender_codes.items():
        if gen_code in code:
            gender_str = gen_name.strip(', ')
            break

    label = ' - '.join([p for p in label_parts if p])
    if gender_str:
        label += f', {gender_str}'

    # Handle quintile codes
    for q in ['Q1', 'Q2', 'Q3', 'Q4', 'Q5']:
        if q in code:
            label += f', Quintile {q[1]}'
            break

    # Handle CP (Country Parity)
    if '.CP' in code:
        label += ' (%)'

    return label

# Match UNESCO indicators
unesco_matched = 0
unesco_prefixes = list(unesco_codes.keys())

for node_id in all_node_ids:
    if node_id not in labels:
        for prefix in unesco_prefixes:
            if node_id.startswith(prefix + '.') or node_id.startswith(prefix + '_') or node_id == prefix:
                labels[node_id] = {
                    'label': generate_unesco_label(node_id),
                    'source': 'UNESCO Institute for Statistics',
                    'description': f'UNESCO UIS education indicator measuring {generate_unesco_label(node_id).lower()}'
                }
                unesco_matched += 1
                break

print(f"Generated {unesco_matched} UNESCO UIS labels")

# ============================================================================
# Source 4: WID (World Inequality Database) Patterns
# ============================================================================

print("\n" + "="*80)
print("GENERATING WID LABELS")
print("="*80)

# WID indicator patterns
wid_patterns = {
    'shweal': 'Share of Wealth',
    'sptinc': 'Share of Pre-Tax Income',
    'adiinc': 'Average Disposable Income',
    'aptinc': 'Average Pre-Tax Income',
    'tptinc': 'Total Pre-Tax Income',
    'npopul': 'Population',
    'mgdpro': 'GDP',
    'xlceup': 'Exchange Rate to EUR',
    'xlcusp': 'Exchange Rate to USD',
    'inyixx': 'Income Index',
    'iwealx': 'Wealth Index',
    'gptinc': 'Gini Pre-Tax Income',
    'gpdiinc': 'Gini Post-Tax Income',
    'yprin': 'Pre-Tax Income',
    'ynmx': 'Mixed Income',
    'ycom': 'Compensation Income',
    'knfc': 'Net Fixed Capital',
    'ygmx': 'Gross Mixed Income',
    'ynsm': 'Net Self-Employment Income',
    'wgwf': 'Wealth: Government',
    'wtbx': 'Total Wealth',
    'ynsr': 'Net Surplus',
    'yfkp': 'Capital Income',
    'wfkp': 'Fixed Capital Wealth',
    'ysav': 'Savings',
    'accm': 'Accumulated',
    'egfc': 'Government Final Consumption',
    'atax': 'Tax Revenue',
    'entc': 'Enterprise',
    'mpit': 'Private Investment',
    'enfc': 'Net Factor Cost',
    'apte': 'Average',
    'anmx': 'Average Mixed Income',
    'atiw': 'Average Total Wealth',
    'ysci': 'Social Contributions Income',
    'wtbm': 'Total Wealth Bottom',
    'gdii': 'GDI Index',
    'mcom': 'Mixed Compensation',
    'acom': 'Average Compensation',
    'aopi': 'Average Operating Income',
    'apit': 'Average Investment',
    'mseg': 'Market Segment',
    'wtgn': 'Wealth Gains',
    'wscin': 'Social Capital Income',
    'aptdr': 'Average Pre-Tax Disposable',
    'wptfx': 'Wealth Pre-Tax Fixed',
    'yptfx': 'Income Pre-Tax Fixed',
    'wpinn': 'Wealth Private Income',
    'aptex': 'Average Pre-Tax External',
    'apter': 'Average Pre-Tax',
    'agsr': 'Average Government Spending',
    'aprp': 'Average Property',
    'aptf': 'Average Pre-Tax Factor',
    'aseg': 'Average Segment',
    'acfc': 'Average Final Consumption',
    'mprg': 'Market Property Gains',
    'mhweal': 'Market Housing Wealth',
    'mnweal': 'Market Net Wealth',
}

wid_suffixes = {
    'i999': ' (Individual)',
    'i992': ' (Household)',
    'm999': ' (Male)',
    'f999': ' (Female)',
    'j999': ' (Joint)',
    'j992': ' (Household Joint)',
    'hoi999': ' (Household, Individual)',
    'hni999': ' (Household Net Income)',
}

def generate_wid_label(code):
    """Generate human-readable label for WID indicator."""
    # Find matching pattern
    label_base = 'WID: '
    for pattern, name in wid_patterns.items():
        if code.startswith(pattern):
            label_base = name
            code_rest = code[len(pattern):]
            break
    else:
        label_base = f'WID: {code[:6].title()}'
        code_rest = code[6:]

    # Add suffix descriptions
    suffix_desc = ''
    for suffix, desc in wid_suffixes.items():
        if suffix in code:
            suffix_desc = desc
            break

    return f"{label_base}{suffix_desc}"

# Match WID indicators
wid_matched = 0
wid_prefixes = list(wid_patterns.keys())

for node_id in all_node_ids:
    if node_id not in labels:
        for prefix in wid_prefixes:
            if node_id.startswith(prefix):
                labels[node_id] = {
                    'label': generate_wid_label(node_id),
                    'source': 'World Inequality Database',
                    'description': f'WID economic indicator: {generate_wid_label(node_id)}'
                }
                wid_matched += 1
                break

print(f"Generated {wid_matched} WID labels")

# ============================================================================
# Source 5: QoG/Polity Dataset Patterns
# ============================================================================

print("\n" + "="*80)
print("GENERATING QoG/POLITY LABELS")
print("="*80)

qog_patterns = {
    'e_polity': 'Polity Score',
    'e_democ': 'Democracy Score',
    'e_autoc': 'Autocracy Score',
    'e_p_polity': 'Polity',
    'e_gdppc': 'GDP per Capita',
    'e_gdp': 'GDP',
    'e_pop': 'Population',
    'e_miurbani': 'Urban Population',
    'e_mipopula': 'Population',
    'e_cow': 'Correlates of War',
    'e_v2x': 'V-Dem Index',
    'ht_regtype': 'Regime Type',
    'opri_': 'Political Regime',
    'atop_': 'Alliance Treaty',
    'gol_': 'Governance',
    'warc_': 'Armed Conflict',
    'ictd_': 'Tax Data',
    'ccp_': 'Constitutional',
    'fi_': 'Financial',
    'gea_': 'Gender Equality',
    'cbie_': 'Central Bank',
    'ihme_': 'Health Metrics',
    'hc': 'Human Capital Index',
}

def generate_qog_label(code):
    """Generate human-readable label for QoG indicator."""
    for pattern, name in qog_patterns.items():
        if code.startswith(pattern):
            rest = code[len(pattern):].replace('_', ' ').title()
            return f"{name}: {rest}" if rest else name

    # Default: capitalize and format
    return code.replace('_', ' ').title()

# Match QoG indicators
qog_matched = 0
qog_prefixes = list(qog_patterns.keys())

for node_id in all_node_ids:
    if node_id not in labels:
        for prefix in qog_prefixes:
            if node_id.startswith(prefix) or node_id == prefix.rstrip('_'):
                labels[node_id] = {
                    'label': generate_qog_label(node_id),
                    'source': 'Quality of Government',
                    'description': f'QoG dataset indicator: {generate_qog_label(node_id)}'
                }
                qog_matched += 1
                break

print(f"Generated {qog_matched} QoG/Polity labels")

# ============================================================================
# Source 6: Penn World Tables
# ============================================================================

print("\n" + "="*80)
print("GENERATING PWT LABELS")
print("="*80)

pwt_vars = {
    'pwt_pop': ('Population', 'Total population in millions'),
    'pwt_hci': ('Human Capital Index', 'Based on years of schooling and returns to education'),
    'pwt_shhc': ('Share of Human Capital', 'Share of labor compensation in GDP'),
    'pwt_rt': ('Real GDP', 'Real GDP at constant prices'),
    'pwt_cs': ('Capital Stock', 'Capital stock at current PPPs'),
    'pwt_ck': ('Capital per Worker', 'Capital stock per worker'),
    'pwt_rgdpe': ('Real GDP (Expenditure)', 'Real GDP at chained PPPs'),
    'pwt_rgdpo': ('Real GDP (Output)', 'Real GDP at constant prices'),
    'pwt_cgdpe': ('Current GDP (Expenditure)', 'Current GDP at PPPs'),
    'pwt_cgdpo': ('Current GDP (Output)', 'Current GDP at current prices'),
    'pwt_ctfp': ('TFP Level', 'TFP level at current PPPs'),
    'pwt_rtfpna': ('TFP Growth', 'TFP at constant national prices'),
    'pwt_labsh': ('Labor Share', 'Share of labor compensation in GDP'),
}

pwt_matched = 0
for node_id in all_node_ids:
    if node_id not in labels and node_id.startswith('pwt_'):
        if node_id in pwt_vars:
            name, desc = pwt_vars[node_id]
            labels[node_id] = {
                'label': f"PWT: {name}",
                'source': 'Penn World Table 10.0',
                'description': desc
            }
        else:
            labels[node_id] = {
                'label': f"PWT: {node_id[4:].replace('_', ' ').title()}",
                'source': 'Penn World Table 10.0',
                'description': 'Penn World Table indicator'
            }
        pwt_matched += 1

print(f"Generated {pwt_matched} PWT labels")

# ============================================================================
# Source 7: WHO Indicators
# ============================================================================

print("\n" + "="*80)
print("GENERATING WHO LABELS")
print("="*80)

who_vars = {
    'who_infmortm': ('Infant Mortality Rate, Male', 'Deaths per 1,000 live births, male'),
    'who_infmortt': ('Infant Mortality Rate', 'Deaths per 1,000 live births, total'),
    'who_infmortf': ('Infant Mortality Rate, Female', 'Deaths per 1,000 live births, female'),
    'who_alcohol10': ('Alcohol Consumption', 'Liters of pure alcohol per capita (15+)'),
    'who_matmort': ('Maternal Mortality Ratio', 'Deaths per 100,000 live births'),
    'who_lifexp': ('Life Expectancy', 'Life expectancy at birth'),
}

who_matched = 0
for node_id in all_node_ids:
    if node_id not in labels and node_id.startswith('who_'):
        if node_id in who_vars:
            name, desc = who_vars[node_id]
            labels[node_id] = {
                'label': f"WHO: {name}",
                'source': 'World Health Organization',
                'description': desc
            }
        else:
            labels[node_id] = {
                'label': f"WHO: {node_id[4:].replace('_', ' ').title()}",
                'source': 'World Health Organization',
                'description': 'WHO health indicator'
            }
        who_matched += 1

print(f"Generated {who_matched} WHO labels")

# ============================================================================
# Source 8: Fallback Pattern-Based Generation
# ============================================================================

print("\n" + "="*80)
print("GENERATING FALLBACK LABELS")
print("="*80)

# Additional patterns for remaining unlabeled
fallback_patterns = {
    'NW.': ('Net Wealth', 'World Bank'),
    'br_': ('Barometer', 'Regional Barometer'),
    'unicef_': ('UNICEF', 'UNICEF'),
    'imf_': ('IMF', 'International Monetary Fund'),
}

def generate_fallback_label(code):
    """Generate a human-readable label from the code itself."""
    # Check for known patterns
    for pattern, (name, source) in fallback_patterns.items():
        if code.startswith(pattern):
            rest = code[len(pattern):].replace('_', ' ').replace('.', ' ').title()
            return f"{name}: {rest}", source, f'{name} indicator'

    # Handle numeric-only codes
    if code.isdigit():
        return f"ICP Category {code}", "International Comparison Program", "ICP expenditure category"

    # Additional known dataset patterns
    additional_patterns = {
        'wdi_': ('World Development Indicator', 'World Bank', 'World Development Indicator'),
        'ciri_': ('CIRI Human Rights', 'CIRI Human Rights Data', 'Human rights measure'),
        'fao_': ('FAO', 'FAO Statistics', 'Food and agriculture indicator'),
        'ross_': ('Ross Oil & Gas', 'Ross Resources Data', 'Natural resource indicator'),
        'cbi_': ('Central Bank', 'Central Bank Data', 'Monetary policy indicator'),
        'gain_': ('ND-GAIN', 'Notre Dame GAIN Index', 'Climate vulnerability indicator'),
        'fh_': ('Freedom House', 'Freedom House', 'Political freedom indicator'),
        'wef_': ('World Economic Forum', 'WEF Global Competitiveness', 'Competitiveness indicator'),
        'XGDP.': ('GDP Expenditure Component', 'International Comparison Program', 'GDP expenditure component'),
        'X.PPP.': ('PPP Component', 'International Comparison Program', 'Purchasing power parity component'),
        'X.': ('ICP Component', 'International Comparison Program', 'International comparison indicator'),
    }

    for pattern, (name, source, desc) in additional_patterns.items():
        if code.startswith(pattern) or code.lower().startswith(pattern.lower()):
            rest = code[len(pattern):].replace('_', ' ').replace('.', ' ')
            # Parse rest for common codes
            rest = rest.replace('GPIA', 'Gender Parity').replace('WPIA', 'Wealth Parity')
            rest = rest.replace('URB', 'Urban').replace('RUR', 'Rural')
            rest = rest.replace(' M ', ' Male ').replace(' F ', ' Female ')
            rest = rest.replace(' Q1', ' Quintile 1').replace(' Q2', ' Quintile 2')
            rest = rest.title().strip()
            return f"{name}: {rest}" if rest else name, source, desc

    # Handle suffix patterns (lag, ma3, ma5, accel)
    suffix_labels = {
        '_lag1': ', 1-Year Lag',
        '_lag2': ', 2-Year Lag',
        '_ma3': ', 3-Year Moving Average',
        '_ma5': ', 5-Year Moving Average',
        '_accel': ', Acceleration',
    }

    base_code = code
    suffix_str = ''
    for suffix, label in suffix_labels.items():
        if code.endswith(suffix):
            base_code = code[:-len(suffix)]
            suffix_str = label
            break

    # Clean up the base code
    label = base_code.replace('_', ' ').replace('.', ' ')

    # Handle common abbreviations
    abbrevs = {
        ' M ': ' Male ',
        ' F ': ' Female ',
        ' URB ': ' Urban ',
        ' RUR ': ' Rural ',
        ' ZS': ' (% of total)',
        ' IN': '',
        ' CD': ' (current USD)',
        ' KD': ' (constant USD)',
        ' PC': ' per Capita',
        ' TO': ' Total',
        'GPIA': 'Gender Parity Index',
        'WPIA': 'Wealth Parity Index',
        'LPIA': 'Location Parity Index',
        'GDPCAP': 'GDP per Capita',
        'FSGOV': 'Government',
        'FSHH': 'Household',
        'FFNTR': 'Non-Profit',
    }
    for abbr, full in abbrevs.items():
        label = label.replace(abbr, full)

    # Title case
    label = ' '.join(word.capitalize() if word.islower() else word for word in label.split())

    return label.strip() + suffix_str, 'Derived', f'Indicator code: {code}'

# Apply fallback for remaining
fallback_matched = 0
for node_id in all_node_ids:
    if node_id not in labels:
        label, source, desc = generate_fallback_label(node_id)
        labels[node_id] = {
            'label': label,
            'source': source,
            'description': desc
        }
        fallback_matched += 1

print(f"Generated {fallback_matched} fallback labels")

# ============================================================================
# Try to use V2.0 labels for any remaining missing
# ============================================================================

print("\n" + "="*80)
print("CHECKING V2.0 LABELS FOR IMPROVEMENTS")
print("="*80)

v20_labels_path = V20_ROOT / 'phaseB/B5_output_schema/outputs/indicator_labels_comprehensive.json'
if v20_labels_path.exists():
    with open(v20_labels_path, 'r') as f:
        v20_labels = json.load(f)

    # Improve labels where V2.0 has better info
    improved = 0
    for node_id in all_node_ids:
        if node_id in v20_labels:
            v20_info = v20_labels[node_id]
            current_info = labels.get(node_id, {})

            # Use V2.0 if it has a better description
            v20_desc = v20_info.get('description', '')
            current_desc = current_info.get('description', '')

            if len(v20_desc) > len(current_desc) + 20:  # V2.0 has significantly more detail
                labels[node_id] = v20_info
                improved += 1
            elif current_info.get('source') == 'Derived' and v20_info.get('source') != 'Unknown':
                labels[node_id] = v20_info
                improved += 1

    print(f"Improved {improved} labels from V2.0")
else:
    print("V2.0 labels not found")

# ============================================================================
# Coverage Report
# ============================================================================

print("\n" + "="*80)
print("COVERAGE REPORT")
print("="*80)

# Categorize by source
by_source = defaultdict(int)
for node_id, info in labels.items():
    by_source[info['source']] += 1

print(f"\nTotal nodes labeled: {len(labels):,} / {len(all_node_ids):,}")
print(f"Coverage: {len(labels)/len(all_node_ids)*100:.1f}%")

print("\nLabels by source:")
for source, count in sorted(by_source.items(), key=lambda x: -x[1]):
    pct = count / len(labels) * 100
    print(f"  {source}: {count:,} ({pct:.1f}%)")

# Check for labels with descriptions
with_desc = sum(1 for info in labels.values() if info.get('description', '').strip() and len(info.get('description', '')) > 20)
print(f"\nLabels with meaningful descriptions: {with_desc} ({100*with_desc/len(labels):.1f}%)")

# Check for bad labels (label == id)
bad_labels = sum(1 for nid, info in labels.items() if info['label'] == nid or info['label'] == nid.replace('_', ' '))
print(f"Labels needing improvement: {bad_labels}")

# ============================================================================
# Save Labels
# ============================================================================

print("\n" + "="*80)
print("SAVING LABELS")
print("="*80)

output_path = OUTPUT_DIR / 'indicator_labels_comprehensive.json'

with open(output_path, 'w') as f:
    json.dump(labels, f, indent=2)

print(f"Saved to: {output_path}")
print(f"File size: {output_path.stat().st_size / 1024:.1f} KB")

# Save coverage report
report_path = OUTPUT_DIR / 'label_coverage_report.txt'
with open(report_path, 'w') as f:
    f.write("V2.1 INDICATOR LABEL COVERAGE REPORT\n")
    f.write("="*50 + "\n")
    f.write(f"Generated: {datetime.now().isoformat()}\n\n")
    f.write(f"Total nodes: {len(all_node_ids):,}\n")
    f.write(f"Labels generated: {len(labels):,}\n")
    f.write(f"Coverage: {len(labels)/len(all_node_ids)*100:.1f}%\n\n")
    f.write("By Source:\n")
    for source, count in sorted(by_source.items(), key=lambda x: -x[1]):
        f.write(f"  {source}: {count:,} ({count/len(labels)*100:.1f}%)\n")
    f.write(f"\nWith descriptions: {with_desc} ({100*with_desc/len(labels):.1f}%)\n")
    f.write(f"Needing improvement: {bad_labels}\n")

print(f"Saved report to: {report_path}")

# Sample output
print("\nSample labels:")
for i, (node_id, info) in enumerate(list(labels.items())[:10]):
    print(f"  {node_id}: {info['label'][:60]}")
    if info.get('description'):
        print(f"    → {info['description'][:70]}...")

print("\n" + "="*80)
print("V2.1 LABEL GENERATION COMPLETE")
print("="*80)
