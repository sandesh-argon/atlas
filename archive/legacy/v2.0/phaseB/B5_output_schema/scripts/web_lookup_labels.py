#!/usr/bin/env python3
"""
Web Lookup for Unknown Indicator Labels
========================================

Fetches labels from online sources for remaining unknown indicators.

Sources:
1. World Bank API
2. WID pattern decoding
3. UN World Population Prospects patterns
4. Penn World Tables patterns
5. Other known dataset patterns

Output:
- Updates indicator_labels_comprehensive.json
- Exports unfound_indicators.json for manual curation

Author: B5 Label Generation
Date: November 2025
"""

import json
import requests
import time
import re
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# ============================================================================
# Setup
# ============================================================================

project_root = Path(__file__).resolve().parents[3]
b5_dir = project_root / 'phaseB/B5_output_schema'
outputs_dir = b5_dir / 'outputs'

print("="*80)
print("WEB LOOKUP FOR UNKNOWN INDICATORS")
print("="*80)
print(f"\nTimestamp: {datetime.now().isoformat()}")

# ============================================================================
# Load Current Labels
# ============================================================================

print("\n" + "="*80)
print("LOADING CURRENT LABELS")
print("="*80)

labels_path = outputs_dir / 'indicator_labels_comprehensive.json'

with open(labels_path, 'r') as f:
    labels = json.load(f)

# Get unknown indicators
unknown = {k: v for k, v in labels.items() if v['source'] == 'Unknown'}
print(f"Total labels: {len(labels):,}")
print(f"Unknown labels to look up: {len(unknown):,}")

# Track updates
updated = 0
still_unknown = []

# ============================================================================
# Source 1: World Bank API
# ============================================================================

print("\n" + "="*80)
print("WORLD BANK API LOOKUP")
print("="*80)

# World Bank indicator codes typically follow patterns like:
# SP.POP.TOTL, NY.GDP.MKTP.CD, etc.

wb_style_codes = [k for k in unknown.keys() if re.match(r'^[A-Z]{2}\.[A-Z0-9.]+', k)]
print(f"Found {len(wb_style_codes)} World Bank-style codes")

wb_found = 0
wb_cache = {}

def fetch_wb_indicator(indicator_id):
    """Fetch indicator metadata from World Bank API."""
    if indicator_id in wb_cache:
        return wb_cache[indicator_id]

    try:
        url = f"https://api.worldbank.org/v2/indicator/{indicator_id}?format=json"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if len(data) > 1 and data[1]:
                info = data[1][0]
                result = {
                    'name': info.get('name', ''),
                    'source': info.get('source', {}).get('value', 'World Bank'),
                    'description': info.get('sourceNote', '')[:200] if info.get('sourceNote') else ''
                }
                wb_cache[indicator_id] = result
                return result
    except Exception as e:
        pass

    wb_cache[indicator_id] = None
    return None

# Batch lookup (with rate limiting)
print("Fetching from World Bank API (this may take a few minutes)...")
for i, code in enumerate(wb_style_codes[:100]):  # Limit to first 100 to avoid rate limiting
    if i % 20 == 0:
        print(f"  Progress: {i}/{min(100, len(wb_style_codes))}")

    result = fetch_wb_indicator(code)
    if result and result['name']:
        labels[code] = {
            'label': result['name'],
            'source': result['source'],
            'description': result['description']
        }
        wb_found += 1

    time.sleep(0.1)  # Rate limiting

print(f"✅ Found {wb_found} labels from World Bank API")

# ============================================================================
# Source 2: Extended WID Pattern Decoding
# ============================================================================

print("\n" + "="*80)
print("EXTENDED WID PATTERN DECODING")
print("="*80)

# WID codes follow specific patterns:
# [concept][population][age][unit]
# e.g., sptinc992j = share of pre-tax income, adults, equal-split

wid_concepts = {
    'sh': 'Share of',
    'av': 'Average',
    'th': 'Threshold',
    'gp': 'Gini',
    'dp': 'Top Decile',
    'sp': 'Share Pre-tax',
    'sd': 'Share Post-tax',
    'mp': 'Middle',
    'tp': 'Top',
    'bp': 'Bottom',
    'mg': 'Market',
    'ag': 'Average Government',
    'wg': 'Wealth Government',
    'ap': 'Average Pre-tax',
    'at': 'Average Total',
    'mt': 'Market Total',
    'an': 'Average Net',
    'mn': 'Market Net',
    'as': 'Average Social',
    'ms': 'Market Social',
    'ac': 'Average Consumption',
    'mc': 'Market Consumption',
    'af': 'Average Factor',
    'mf': 'Market Factor',
    'eo': 'External Output',
    'ao': 'Average Operating',
}

wid_income_types = {
    'ptin': 'Pre-tax Income',
    'diin': 'Disposable Income',
    'fain': 'Factor Income',
    'prin': 'Primary Income',
    'cain': 'Capital Income',
    'lain': 'Labor Income',
    'weal': 'Wealth',
    'hous': 'Housing',
    'finc': 'Financial Income',
    'nfin': 'Non-Financial',
    'mixd': 'Mixed Income',
    'comp': 'Compensation',
    'self': 'Self-Employment',
    'prop': 'Property',
    'rent': 'Rent',
    'intr': 'Interest',
    'divd': 'Dividends',
    'govt': 'Government',
    'taxe': 'Taxes',
    'tran': 'Transfers',
    'soci': 'Social',
    'priv': 'Private',
    'cons': 'Consumption',
    'save': 'Savings',
    'gsr': 'Government Spending Revenue',
    'gdp': 'GDP',
    'gnp': 'GNP',
    'gni': 'GNI',
    'pop': 'Population',
    'fdi': 'Foreign Direct Investment',
    'ptf': 'Pre-tax Factor',
    'con': 'Consumption',
    'pri': 'Private',
    'sec': 'Sector',
    'ssc': 'Social Security',
    'scr': 'Credit',
    'sav': 'Savings',
    'tst': 'Total Stock',
    'tax': 'Tax',
    'pol': 'Political',
    'seg': 'Segment',
    'cfc': 'Final Consumption',
    'ssb': 'Social Benefits',
    'ter': 'Territory',
    'gov': 'Government',
    'cor': 'Corporate',
    'hoi': 'Households',
    'nfi': 'Net Financial',
    'goi': 'Gross',
    'coi': 'Corporate',
    'npi': 'Net Private',
    'rxi': 'Revenue',
    'pxi': 'Public',
    'xai': 'External Assets',
    'opi': 'Operating',
    'fci': 'Final Consumption',
    'hni': 'Household Net',
    'igi': 'Investment Gross',
}

wid_units = {
    '999': '(All)',
    '992': '(Adults)',
    '996': '(Working Age)',
    'j': '(Equal-split)',
    'i': '(Individual)',
    'm': '(Male)',
    'f': '(Female)',
}

def decode_wid_code(code):
    """Decode WID indicator code to human-readable label."""
    original = code

    # Try to match the first 2-4 characters as concept
    concept = ''
    for length in [4, 3, 2]:
        prefix = code[:length].lower()
        if prefix in wid_concepts:
            concept = wid_concepts[prefix]
            code = code[length:]
            break

    # Try to match income type (next 3-4 chars)
    income_type = ''
    for length in [4, 3]:
        if len(code) >= length:
            infix = code[:length].lower()
            if infix in wid_income_types:
                income_type = wid_income_types[infix]
                code = code[length:]
                break

    # Check for unit at end
    unit = ''
    for suffix, desc in wid_units.items():
        if code.endswith(suffix):
            unit = desc
            code = code[:-len(suffix)]
            break

    # Build label
    if concept or income_type:
        label = f"{concept} {income_type}".strip()
        if unit:
            label += f" {unit}"
        return label

    return None

# Apply to WID-like codes
wid_patterns = ['mprg', 'mcfc', 'mgsr', 'acon', 'mtax', 'mssc', 'assb', 'asav',
                'mfdi', 'mptf', 'ascr', 'mcon', 'msec', 'atst', 'mpri', 'msav',
                'apol', 'agwd', 'eofg', 'aexc', 'mptf', 'wgov', 'ater', 'mgdp']

wid_found = 0
for code, info in list(unknown.items()):
    if info['source'] == 'Unknown':
        # Check if it matches WID pattern
        code_lower = code.lower()
        for pattern in wid_patterns:
            if code_lower.startswith(pattern):
                label = decode_wid_code(code)
                if label:
                    labels[code] = {
                        'label': f"WID: {label}",
                        'source': 'World Inequality Database',
                        'description': f'WID economic indicator: {code}'
                    }
                    wid_found += 1
                break
        else:
            # Try generic WID decoding for codes with numeric suffixes
            if re.match(r'^[a-z]+[0-9]{3}[a-z]?$', code_lower):
                label = decode_wid_code(code)
                if label:
                    labels[code] = {
                        'label': f"WID: {label}",
                        'source': 'World Inequality Database',
                        'description': f'WID economic indicator: {code}'
                    }
                    wid_found += 1

print(f"✅ Decoded {wid_found} WID labels")

# ============================================================================
# Source 3: UN World Population Prospects
# ============================================================================

print("\n" + "="*80)
print("UN WORLD POPULATION PROSPECTS PATTERNS")
print("="*80)

wpp_labels = {
    'wpp_pop': 'UN Population Estimate',
    'wpp_sexratio': 'UN Sex Ratio at Birth',
    'wpp_tfr': 'UN Total Fertility Rate',
    'wpp_cbr': 'UN Crude Birth Rate',
    'wpp_cdr': 'UN Crude Death Rate',
    'wpp_imr': 'UN Infant Mortality Rate',
    'wpp_le': 'UN Life Expectancy',
    'wpp_growth': 'UN Population Growth Rate',
    'wpp_density': 'UN Population Density',
    'wpp_median': 'UN Median Age',
}

wpp_found = 0
for code, info in list(unknown.items()):
    if info['source'] == 'Unknown' and code.startswith('wpp_'):
        if code in wpp_labels:
            labels[code] = {
                'label': wpp_labels[code],
                'source': 'UN World Population Prospects',
                'description': 'UN demographic indicator'
            }
        else:
            base = code[4:].replace('_', ' ').title()
            labels[code] = {
                'label': f"UN Population: {base}",
                'source': 'UN World Population Prospects',
                'description': 'UN demographic indicator'
            }
        wpp_found += 1

print(f"✅ Found {wpp_found} UN WPP labels")

# ============================================================================
# Source 4: Penn World Tables Extended
# ============================================================================

print("\n" + "="*80)
print("PENN WORLD TABLES EXTENDED")
print("="*80)

csh_labels = {
    'csh_c': 'PWT: Share of Consumption',
    'csh_g': 'PWT: Share of Government',
    'csh_i': 'PWT: Share of Investment',
    'csh_x': 'PWT: Share of Exports',
    'csh_m': 'PWT: Share of Imports',
    'csh_r': 'PWT: Share of Residual',
}

csh_found = 0
for code, info in list(unknown.items()):
    if info['source'] == 'Unknown' and code.startswith('csh_'):
        if code in csh_labels:
            labels[code] = {
                'label': csh_labels[code],
                'source': 'Penn World Table 10.0',
                'description': 'PWT expenditure share component'
            }
        else:
            labels[code] = {
                'label': f"PWT Share: {code[4:].upper()}",
                'source': 'Penn World Table 10.0',
                'description': 'PWT expenditure share component'
            }
        csh_found += 1

print(f"✅ Found {csh_found} PWT share labels")

# ============================================================================
# Source 5: Other Known Datasets
# ============================================================================

print("\n" + "="*80)
print("OTHER KNOWN DATASETS")
print("="*80)

other_patterns = {
    'h_': ('Historical Database', 'Historical Database of the Global Environment'),
    'ipu_': ('Inter-Parliamentary Union', 'IPU Parline Database'),
    'une_': ('UNESCO Education', 'UNESCO Institute for Statistics'),
    'qar_': ('QoG Administrative', 'Quality of Government'),
    'undp_': ('UNDP', 'UN Development Programme'),
    'ucdp_': ('UCDP Conflict', 'Uppsala Conflict Data Program'),
    'wvs_': ('World Values Survey', 'World Values Survey'),
    'gle_': ('Global Leadership', 'Global Leadership Project'),
    'gea_': ('Gender Equality', 'Gender Equality Assessment'),
    'dpi_': ('Database of Political Institutions', 'World Bank DPI'),
    'ti_': ('Transparency International', 'Transparency International'),
    'rsf_': ('Press Freedom', 'Reporters Without Borders'),
    'hf_': ('Heritage Foundation', 'Heritage Foundation Index'),
    'wef_': ('World Economic Forum', 'WEF Competitiveness'),
    'oecd_': ('OECD', 'OECD Statistics'),
    'imf_': ('IMF', 'International Monetary Fund'),
    'bis_': ('BIS', 'Bank for International Settlements'),
    'iea_': ('IEA Energy', 'International Energy Agency'),
    'eurostat_': ('Eurostat', 'European Statistical Office'),
    'wgi_': ('Worldwide Governance', 'World Bank Governance Indicators'),
    'ef_': ('Economic Freedom', 'Fraser Institute'),
    'X.': ('ICP Expenditure', 'International Comparison Program'),
    'XGDP.': ('ICP GDP Component', 'International Comparison Program'),
}

other_found = 0
for code, info in list(unknown.items()):
    if info['source'] == 'Unknown':
        for pattern, (name, source) in other_patterns.items():
            if code.startswith(pattern) or code.lower().startswith(pattern.lower()):
                rest = code[len(pattern):].replace('_', ' ').replace('.', ' ').title()
                labels[code] = {
                    'label': f"{name}: {rest}" if rest else name,
                    'source': source,
                    'description': f'{source} indicator'
                }
                other_found += 1
                break

print(f"✅ Found {other_found} other dataset labels")

# ============================================================================
# Source 6: UNESCO Extended Patterns
# ============================================================================

print("\n" + "="*80)
print("UNESCO EXTENDED PATTERNS")
print("="*80)

unesco_extended = {
    'ASTAFF': 'Academic Staff',
    'EV1524P': 'Education Vocational 15-24',
    'FOSIP': 'First-time Outbound Students',
    'FOSGP': 'First-time Outbound Students Graduate',
    'GRAD': 'Graduates',
    'MOB': 'Mobility',
    'MOR': 'Mobility Rate',
    'NART': 'Net Adjusted Rate Tertiary',
    'AIR': 'Adjusted Intake Rate',
    'FRESP': 'Freshman Response',
}

unesco_found = 0
for code, info in list(unknown.items()):
    if info['source'] == 'Unknown':
        for pattern, name in unesco_extended.items():
            if code.startswith(pattern + '.') or code.startswith(pattern + '_'):
                rest = code[len(pattern)+1:].replace('.', ' ').replace('_', ' ')
                # Parse common codes
                rest = rest.replace('F', 'Female').replace('M', 'Male')
                rest = rest.replace('URB', 'Urban').replace('RUR', 'Rural')
                rest = rest.replace('GPIA', 'Gender Parity')
                rest = rest.title()
                labels[code] = {
                    'label': f"UNESCO: {name} - {rest}" if rest else f"UNESCO: {name}",
                    'source': 'UNESCO Institute for Statistics',
                    'description': 'UNESCO education indicator'
                }
                unesco_found += 1
                break

print(f"✅ Found {unesco_found} UNESCO extended labels")

# ============================================================================
# Summary and Export
# ============================================================================

print("\n" + "="*80)
print("SUMMARY")
print("="*80)

# Count remaining unknown
remaining_unknown = [k for k, v in labels.items() if v['source'] == 'Unknown']
print(f"\nTotal labels: {len(labels):,}")
print(f"Remaining unknown: {len(remaining_unknown)}")

# Save updated labels
print("\n" + "="*80)
print("SAVING UPDATED LABELS")
print("="*80)

with open(labels_path, 'w') as f:
    json.dump(labels, f, indent=2)

print(f"✅ Saved updated labels to: {labels_path}")

# Export unfound list for manual curation
unfound_path = outputs_dir / 'unfound_indicators.json'

unfound_list = []
for code in remaining_unknown:
    unfound_list.append({
        'id': code,
        'current_label': labels[code]['label'],
        'suggested_label': '',  # For manual fill-in
        'source': '',  # For manual fill-in
        'description': ''  # For manual fill-in
    })

with open(unfound_path, 'w') as f:
    json.dump(unfound_list, f, indent=2)

print(f"✅ Exported {len(unfound_list)} unfound indicators to: {unfound_path}")

# Also create a simple CSV for easier editing
csv_path = outputs_dir / 'unfound_indicators.csv'
with open(csv_path, 'w') as f:
    f.write("id,current_label,suggested_label,source,description\n")
    for item in unfound_list:
        f.write(f'"{item["id"]}","{item["current_label"]}","","",""\n')

print(f"✅ Exported CSV for manual editing: {csv_path}")

print("\n" + "="*80)
print("WEB LOOKUP COMPLETE")
print("="*80)
print(f"\nRemaining unknown indicators: {len(remaining_unknown)}")
print(f"These have been exported to:")
print(f"  - {unfound_path}")
print(f"  - {csv_path}")
print("\nYou can manually fill in the suggested_label, source, and description")
print("fields in the CSV, then re-run the import script.")
