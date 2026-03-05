#!/usr/bin/env python3
"""
Match V2 Indicators Against V1.0 Metadata
==========================================

V1.0 has comprehensive indicator metadata from actual API downloads:
- world_bank_indicators.csv: 30,878 indicators
- UISIndicators.csv (UNESCO): 4,638 indicators
- unicef_indicators_list.csv: 135 indicators
- WHO GHO.csv: WHO indicators
- IMFIndicators.csv: IMF indicators

Match V2's 329 mechanism candidates against these to get high-quality metadata.

Author: B3 Metadata Enhancement
Date: November 2025
"""

import pandas as pd
import json
import pickle
from pathlib import Path
import sys

project_root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(project_root))

print("="*80)
print("MATCHING V2 INDICATORS AGAINST V1.0 METADATA")
print("="*80)

# Load B2 mechanism candidates
b2_checkpoint_path = project_root / 'phaseB/B2_mechanism_identification/outputs/B2_bridging_subgraph_checkpoint.pkl'
with open(b2_checkpoint_path, 'rb') as f:
    b2_data = pickle.load(f)
mechanism_candidates = b2_data['mechanism_candidates']

print(f"\n✅ Loaded {len(mechanism_candidates)} mechanism candidates from V2")

# V1.0 metadata directory
v1_indicators_dir = Path.home() / 'Documents/Global_Project/v1.0/Indicators'

# Load existing V2 metadata
metadata_dir = project_root / 'phaseA/A0_data_acquisition/metadata'

existing_metadata = {}
for source in ['wdi', 'vdem', 'unesco', 'pwt']:
    suffix = 'codebook' if source == 'vdem' else 'metadata'
    path = metadata_dir / f'{source}_{suffix}.json'
    if path.exists():
        with open(path, 'r') as f:
            existing_metadata.update(json.load(f))

print(f"✅ Existing V2 metadata: {len(existing_metadata)} indicators")

# ============================================================================
# 1. WORLD BANK INDICATORS
# ============================================================================

print("\n" + "="*80)
print("MATCHING WORLD BANK INDICATORS")
print("="*80)

wb_path = v1_indicators_dir / 'world_bank_indicators.csv'
if wb_path.exists():
    print(f"\nLoading {wb_path}")
    wb_df = pd.read_csv(wb_path)
    print(f"✅ Loaded {len(wb_df)} World Bank indicators from V1.0")

    # Create lookup by indicator code
    wb_lookup = {}
    for _, row in wb_df.iterrows():
        code = str(row['id']).lower()
        wb_lookup[code] = {
            'full_name': row['name'] if pd.notna(row['name']) else code,
            'description': row['sourceNote'] if pd.notna(row['sourceNote']) else '',
            'source': row['sourceOrganization'] if pd.notna(row['sourceOrganization']) else 'World Bank',
            'topics': row['topics'] if pd.notna(row['topics']) else '',
            'code': row['id']
        }

    # Match WDI indicators
    wdi_indicators = [m for m in mechanism_candidates if m.lower().startswith('wdi_')]
    matched = 0

    for indicator in wdi_indicators:
        if indicator in existing_metadata and existing_metadata[indicator].get('source') != 'Unknown':
            continue  # Already have good metadata

        # Try exact match
        search_code = indicator.replace('wdi_', '').lower()

        if search_code in wb_lookup:
            existing_metadata[indicator] = wb_lookup[search_code]
            existing_metadata[indicator]['code'] = indicator
            matched += 1
            print(f"  ✅ {indicator}: {existing_metadata[indicator]['full_name'][:60]}...")

        # Try with dots instead of underscores
        elif search_code.replace('_', '.') in wb_lookup:
            search_code_dots = search_code.replace('_', '.')
            existing_metadata[indicator] = wb_lookup[search_code_dots]
            existing_metadata[indicator]['code'] = indicator
            matched += 1
            print(f"  ✅ {indicator}: {existing_metadata[indicator]['full_name'][:60]}...")

    print(f"\n✅ Matched {matched}/{len(wdi_indicators)} WDI indicators against V1.0")

else:
    print(f"⚠️  World Bank indicators file not found at {wb_path}")

# ============================================================================
# 2. UNESCO UIS INDICATORS
# ============================================================================

print("\n" + "="*80)
print("MATCHING UNESCO UIS INDICATORS")
print("="*80)

uis_path = v1_indicators_dir / 'UISIndicators.csv'
if uis_path.exists():
    print(f"\nLoading {uis_path}")
    uis_df = pd.read_csv(uis_path)
    print(f"✅ Loaded {len(uis_df)} UNESCO UIS indicators from V1.0")

    # Create lookup by indicator code
    uis_lookup = {}
    for _, row in uis_df.iterrows():
        code = str(row['indicatorCode']).upper()
        uis_lookup[code] = {
            'full_name': row['name'] if pd.notna(row['name']) else code,
            'description': f"UNESCO {row['theme']}" if pd.notna(row['theme']) else 'UNESCO Indicator',
            'source': 'UNESCO Institute for Statistics',
            'category': row['theme'] if pd.notna(row['theme']) else 'Education',
            'code': row['indicatorCode']
        }

    # Match UNESCO indicators
    unesco_patterns = ['GER', 'REPR', 'NER', 'OAEP', 'NERT', 'ROFST', 'OFST']
    unesco_indicators = [
        m for m in mechanism_candidates
        if any(pattern in m.upper() for pattern in unesco_patterns)
    ]

    matched = 0
    for indicator in unesco_indicators:
        # Try exact match (case-insensitive)
        search_code = indicator.upper()

        if search_code in uis_lookup:
            existing_metadata[indicator] = uis_lookup[search_code]
            existing_metadata[indicator]['code'] = indicator
            matched += 1
            print(f"  ✅ {indicator}: {existing_metadata[indicator]['full_name'][:60]}...")
        elif indicator in existing_metadata and existing_metadata[indicator].get('source') == 'UNESCO Institute for Statistics':
            matched += 1  # Already have UNESCO metadata

    print(f"\n✅ Matched {matched}/{len(unesco_indicators)} UNESCO indicators against V1.0")

else:
    print(f"⚠️  UNESCO UIS indicators file not found at {uis_path}")

# ============================================================================
# 3. UNICEF INDICATORS
# ============================================================================

print("\n" + "="*80)
print("MATCHING UNICEF INDICATORS")
print("="*80)

unicef_path = v1_indicators_dir / 'unicef_indicators_list.csv'
if unicef_path.exists():
    print(f"\nLoading {unicef_path}")
    unicef_df = pd.read_csv(unicef_path)
    print(f"✅ Loaded {len(unicef_df)} UNICEF indicators from V1.0")

    # Create lookup by indicator code
    unicef_lookup = {}
    for _, row in unicef_df.iterrows():
        code = str(row['indicator_id']).lower()
        unicef_lookup[code] = {
            'full_name': row['indicator_name'] if pd.notna(row['indicator_name']) else code,
            'description': row['description'] if pd.notna(row['description']) else '',
            'source': row['agency'] if pd.notna(row['agency']) else 'UNICEF',
            'code': row['indicator_id']
        }

    # Match UNICEF indicators (usually numeric codes or specific patterns)
    matched = 0
    for indicator in mechanism_candidates:
        search_code = indicator.lower()

        if search_code in unicef_lookup and indicator not in existing_metadata:
            existing_metadata[indicator] = unicef_lookup[search_code]
            existing_metadata[indicator]['code'] = indicator
            matched += 1
            print(f"  ✅ {indicator}: {existing_metadata[indicator]['full_name'][:60]}...")

    if matched > 0:
        print(f"\n✅ Matched {matched} UNICEF indicators against V1.0")
    else:
        print(f"\n⚠️  No UNICEF indicators matched (likely different naming conventions)")

else:
    print(f"⚠️  UNICEF indicators file not found at {unicef_path}")

# ============================================================================
# SUMMARY
# ============================================================================

print("\n" + "="*80)
print("V1.0 METADATA MATCHING SUMMARY")
print("="*80)

# Count high-quality vs inferred metadata
high_quality = sum(1 for v in existing_metadata.values() if v.get('metadata_quality') != 'inferred')
inferred = sum(1 for v in existing_metadata.values() if v.get('metadata_quality') == 'inferred')

print(f"\n📊 Final Metadata Quality:")
print(f"   High-quality (API/V1.0): {high_quality:>3} indicators ({high_quality/len(mechanism_candidates)*100:.1f}%)")
print(f"   Inferred (fallback):     {inferred:>3} indicators ({inferred/len(mechanism_candidates)*100:.1f}%)")
print(f"   Total:                   {len(existing_metadata):>3} indicators ({len(existing_metadata)/len(mechanism_candidates)*100:.1f}%)")

# Save enhanced metadata
enhanced_path = metadata_dir / 'enhanced_metadata.json'
with open(enhanced_path, 'w') as f:
    json.dump(existing_metadata, f, indent=2)

print(f"\n✅ Saved enhanced metadata: {enhanced_path}")
print(f"   File size: {enhanced_path.stat().st_size / 1024:.1f} KB")

# Compare before/after
print(f"\n📈 Improvement:")
print(f"   Before V1.0 matching: 151 high-quality (45.9%)")
print(f"   After V1.0 matching:  {high_quality} high-quality ({high_quality/len(mechanism_candidates)*100:.1f}%)")
print(f"   Improvement: +{high_quality - 151} indicators ({(high_quality - 151)/len(mechanism_candidates)*100:.1f}%)")

print("\n" + "="*80)
