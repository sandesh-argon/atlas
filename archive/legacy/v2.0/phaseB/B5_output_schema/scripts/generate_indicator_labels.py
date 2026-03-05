#!/usr/bin/env python3
"""
Generate Human-Readable Labels for All Indicators
==================================================

Creates comprehensive label mappings for all 8,126 nodes in the causal graph.

Sources:
1. World Bank indicators (30K+ entries)
2. V-Dem codebook patterns
3. UNESCO UIS indicator patterns
4. WID (World Inequality Database) patterns
5. A5 interaction terms (generated)
6. Pattern-based inference for remaining

Output:
- indicator_labels_comprehensive.json
- coverage_report.txt

Author: B5 Label Generation
Date: November 2025
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

project_root = Path(__file__).resolve().parents[3]
b5_dir = project_root / 'phaseB/B5_output_schema'
outputs_dir = b5_dir / 'outputs'

print("="*80)
print("INDICATOR LABEL GENERATION")
print("="*80)
print(f"\nTimestamp: {datetime.now().isoformat()}")

# ============================================================================
# Load All Node IDs
# ============================================================================

print("\n" + "="*80)
print("LOADING NODE IDS")
print("="*80)

with open(outputs_dir / 'exports/causal_graph_v2_FULL.json', 'r') as f:
    graph_data = json.load(f)

all_node_ids = set(n['id'] for n in graph_data['nodes'])
print(f"Total nodes to label: {len(all_node_ids):,}")

# Initialize label storage
labels = {}  # id -> {label, source, description}

# ============================================================================
# Source 1: World Bank Indicators (30K+)
# ============================================================================

print("\n" + "="*80)
print("LOADING WORLD BANK INDICATORS")
print("="*80)

wb_path = project_root / 'indicators/world_bank_indicators.csv'
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
            'description': row.get('sourceNote', '')[:200] if row.get('sourceNote') else ''
        }

print(f"Loaded {len(wb_labels):,} World Bank indicators")

# Create lowercase lookup for fuzzy matching
wb_labels_lower = {k.lower(): (k, v) for k, v in wb_labels.items()}

# Common WDI code abbreviations
wdi_abbreviations = {
    'lfp': 'labor force participation',
    'gdp': 'GDP',
    'gni': 'GNI',
    'pop': 'population',
    'mort': 'mortality',
    'fert': 'fertility',
    'life': 'life expectancy',
    'inf': 'infant',
    'emp': 'employment',
    'unemp': 'unemployment',
    'exp': 'expenditure',
    'imp': 'imports',
    'edu': 'education',
    'lit': 'literacy',
    'enr': 'enrollment',
    'ger': 'gross enrollment rate',
    'ner': 'net enrollment rate',
}

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
            'description': f'V-Dem indicator {node_id}'
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
    indicator_name = unesco_codes.get(base_code, base_code)

    label_parts = [indicator_name]

    # Parse remaining parts
    rest = '.'.join(parts[1:]) if len(parts) > 1 else ''

    # Education level
    for level_code, level_name in edu_levels.items():
        if level_code in rest:
            label_parts.append(level_name)
            break

    # Age group
    for age_code, age_name in age_groups.items():
        if age_code in rest:
            label_parts.append(age_name)
            break

    # Location
    for loc_code, loc_name in location_codes.items():
        if loc_code in rest or loc_code.strip('.') in rest:
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
                    'description': f'UNESCO UIS education indicator'
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
}

wid_suffixes = {
    'i999': ' (Individual)',
    'i992': ' (Household)',
    'm999': ' (Male)',
    'f999': ' (Female)',
    'j999': ' (Joint)',
    'j992': ' (Household Joint)',
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
        label_base = f'WID: {code[:4].title()}'
        code_rest = code[4:]

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
                    'description': 'WID economic indicator'
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
            if node_id.startswith(prefix):
                labels[node_id] = {
                    'label': generate_qog_label(node_id),
                    'source': 'Quality of Government',
                    'description': 'QoG dataset indicator'
                }
                qog_matched += 1
                break

print(f"Generated {qog_matched} QoG/Polity labels")

# ============================================================================
# Source 6: A5 Interaction Terms
# ============================================================================

print("\n" + "="*80)
print("GENERATING INTERACTION LABELS")
print("="*80)

# Load A5 interactions to get proper labels
a5_path = project_root / 'phaseA/A5_interaction_discovery/outputs/A5_interaction_results_FILTERED_STRICT.pkl'

with open(a5_path, 'rb') as f:
    a5_data = pickle.load(f)

# Create lookup for mechanism labels (use what we have so far)
def get_mechanism_label(mech_id):
    if mech_id in labels:
        return labels[mech_id]['label']
    else:
        return mech_id.replace('_', ' ').title()[:30]

# Match interaction nodes
interact_matched = 0
for node_id in all_node_ids:
    if node_id not in labels and node_id.startswith('INTERACT_'):
        # Parse: INTERACT_{mech1}_X_{mech2}_TO_{outcome}
        try:
            parts = node_id.split('_X_')
            if len(parts) == 2:
                mech1 = parts[0].replace('INTERACT_', '')
                rest = parts[1].split('_TO_')
                if len(rest) == 2:
                    mech2, outcome = rest

                    # Get short labels
                    m1_label = get_mechanism_label(mech1)[:25]
                    m2_label = get_mechanism_label(mech2)[:25]
                    out_label = get_mechanism_label(outcome)[:20]

                    labels[node_id] = {
                        'label': f"Interaction: {m1_label} × {m2_label} → {out_label}",
                        'source': 'A5 Interaction Discovery',
                        'description': f'Moderating effect of {mech1} and {mech2} on {outcome}'
                    }
                    interact_matched += 1
        except:
            pass

print(f"Generated {interact_matched} interaction labels")

# ============================================================================
# Source 7: Penn World Tables
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
# Source 8: WHO Indicators
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
# Source 9: Fallback Pattern-Based Generation
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
            return f"{name}: {rest}", source

    # Handle numeric-only codes
    if code.isdigit():
        return f"ICP Category {code}", "International Comparison Program"

    # Additional known dataset patterns
    additional_patterns = {
        'wdi_': ('World Development Indicator', 'World Bank'),
        'ciri_': ('CIRI Human Rights', 'CIRI Human Rights Data'),
        'fao_': ('FAO', 'FAO Statistics'),
        'ross_': ('Ross Oil & Gas', 'Ross Resources Data'),
        'cbi_': ('Central Bank', 'Central Bank Data'),
        'gain_': ('ND-GAIN', 'Notre Dame GAIN Index'),
        'fh_': ('Freedom House', 'Freedom House'),
        'wef_': ('World Economic Forum', 'WEF Global Competitiveness'),
        'afdi': ('Average FDI', 'World Inequality Database'),
        'aprg': ('Average Property Gains', 'World Inequality Database'),
        'apri': ('Average Private Income', 'World Inequality Database'),
        'ansr': ('Average Net Surplus', 'World Inequality Database'),
        'assc': ('Average Social Security', 'World Inequality Database'),
        'asec': ('Average Sector', 'World Inequality Database'),
        'AIR.': ('Adjusted Intake Rate', 'UNESCO Institute for Statistics'),
        'NART.': ('Net Adjusted Rate Tertiary', 'UNESCO Institute for Statistics'),
        'FOSGP.': ('First-time Outbound Students', 'UNESCO Institute for Statistics'),
        'FRESP.': ('Freshmen Response', 'UNESCO Institute for Statistics'),
        'MOR.': ('Mobility Rate', 'UNESCO Institute for Statistics'),
        'XGDP.': ('GDP Expenditure Component', 'International Comparison Program'),
        'X.PPP.': ('PPP Component', 'International Comparison Program'),
    }

    for pattern, (name, source) in additional_patterns.items():
        if code.startswith(pattern) or code.lower().startswith(pattern.lower()):
            rest = code[len(pattern):].replace('_', ' ').replace('.', ' ')
            # Parse rest for common codes
            rest = rest.replace('GPIA', 'Gender Parity').replace('WPIA', 'Wealth Parity')
            rest = rest.replace('URB', 'Urban').replace('RUR', 'Rural')
            rest = rest.replace(' M ', ' Male ').replace(' F ', ' Female ')
            rest = rest.replace(' Q1', ' Quintile 1').replace(' Q2', ' Quintile 2')
            rest = rest.title().strip()
            return f"{name}: {rest}" if rest else name, source

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
    }
    for abbr, full in abbrevs.items():
        label = label.replace(abbr, full)

    # Title case
    label = ' '.join(word.capitalize() if word.islower() else word for word in label.split())

    return label.strip() + suffix_str, 'Unknown'

# Apply fallback for remaining
fallback_matched = 0
for node_id in all_node_ids:
    if node_id not in labels:
        label, source = generate_fallback_label(node_id)
        labels[node_id] = {
            'label': label,
            'source': source,
            'description': f'Indicator code: {node_id}'
        }
        fallback_matched += 1

print(f"Generated {fallback_matched} fallback labels")

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

# Check for bad labels (label == id)
bad_labels = sum(1 for nid, info in labels.items() if info['label'] == nid or info['label'] == nid.replace('_', ' '))
print(f"\nLabels needing improvement: {bad_labels}")

# ============================================================================
# Save Labels
# ============================================================================

print("\n" + "="*80)
print("SAVING LABELS")
print("="*80)

output_path = outputs_dir / 'indicator_labels_comprehensive.json'

with open(output_path, 'w') as f:
    json.dump(labels, f, indent=2)

print(f"Saved to: {output_path}")
print(f"File size: {output_path.stat().st_size / 1024:.1f} KB")

# Sample output
print("\nSample labels:")
for i, (node_id, info) in enumerate(list(labels.items())[:10]):
    print(f"  {node_id}: {info['label']}")

print("\n" + "="*80)
print("LABEL GENERATION COMPLETE")
print("="*80)
