#!/usr/bin/env python3
"""
Create Fallback Metadata for Remaining Indicators
==================================================

For indicators without API metadata, create reasonable metadata from:
1. Variable name patterns
2. Data source inference
3. Generic descriptions

This ensures 100% coverage with best-effort metadata.

Author: B3 Metadata Completion
Date: November 2025
"""

import json
import pickle
from pathlib import Path
import sys
import re

project_root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(project_root))

print("="*80)
print("CREATING FALLBACK METADATA FOR REMAINING INDICATORS")
print("="*80)

# Load B2 mechanism candidates
b2_checkpoint_path = project_root / 'phaseB/B2_mechanism_identification/outputs/B2_bridging_subgraph_checkpoint.pkl'
with open(b2_checkpoint_path, 'rb') as f:
    b2_data = pickle.load(f)
mechanism_candidates = b2_data['mechanism_candidates']

print(f"\n✅ Loaded {len(mechanism_candidates)} mechanism candidates")

# Load existing metadata
metadata_dir = project_root / 'phaseA/A0_data_acquisition/metadata'

existing_metadata = {}
for source in ['wdi', 'vdem', 'unesco', 'pwt']:
    suffix = 'codebook' if source == 'vdem' else 'metadata'
    path = metadata_dir / f'{source}_{suffix}.json'
    if path.exists():
        with open(path, 'r') as f:
            data = json.load(f)
            existing_metadata.update(data)
            print(f"  Loaded {len(data)} indicators from {source}")

print(f"\n✅ Total existing metadata: {len(existing_metadata)} indicators")

# Identify missing indicators
missing_indicators = [m for m in mechanism_candidates if m not in existing_metadata]
print(f"⚠️  Missing metadata: {len(missing_indicators)} indicators ({len(missing_indicators)/len(mechanism_candidates)*100:.1f}%)")

# Create fallback metadata
def infer_metadata_from_name(indicator: str) -> dict:
    """Infer metadata from variable name patterns"""

    # Clean indicator name
    clean_name = indicator.replace('_', ' ').title()

    # Detect source from prefix
    source = "Unknown"
    category = "Mixed"

    if indicator.lower().startswith('wdi_'):
        source = "World Bank World Development Indicators"
        category = "Economic" if any(x in indicator.lower() for x in ['gdp', 'gni', 'income', 'economy']) else "Mixed"

    elif indicator.startswith('v2') or indicator.startswith('v3'):
        source = "V-Dem Institute"
        category = "Governance"

    elif any(x in indicator for x in ['GER', 'NER', 'REPR', 'OAEP', 'NERT', 'ROFST']):
        source = "UNESCO Institute for Statistics"
        category = "Education"

    elif indicator.lower().startswith('pwt_') or indicator.lower() in ['hc', 'hci']:
        source = "Penn World Table"
        category = "Economic"

    elif any(x in indicator.lower() for x in ['qog', 'icrg', 'wbgi']):
        source = "Quality of Government Institute"
        category = "Governance"

    elif any(x in indicator.lower() for x in ['atop', 'cow', 'igo']):
        source = "International Relations Dataset"
        category = "International"

    elif any(x in indicator.lower() for x in ['opri', 'polity', 'democracy']):
        source = "Political Regime Dataset"
        category = "Governance"

    # Detect category from keywords
    if category == "Mixed":
        if any(x in indicator.lower() for x in ['health', 'mort', 'life', 'disease', 'medical']):
            category = "Health"
        elif any(x in indicator.lower() for x in ['edu', 'school', 'enr', 'literacy']):
            category = "Education"
        elif any(x in indicator.lower() for x in ['gdp', 'income', 'growth', 'employ', 'trade']):
            category = "Economic"
        elif any(x in indicator.lower() for x in ['gov', 'democracy', 'polity', 'judicial', 'corruption']):
            category = "Governance"

    # Generate full name
    full_name = clean_name

    # Better naming for specific patterns
    if indicator.startswith('v2'):
        # V-Dem indicators
        v2_patterns = {
            'v2x_': 'Index: ',
            'v2xcl_': 'Civil Liberties: ',
            'v2xcs_': 'Civil Society: ',
            'v2xel_': 'Electoral: ',
            'v2ju': 'Judicial: ',
            'v2cl': 'Civil Liberties: ',
            'v2reg': 'Regime: ',
            'v2ex': 'Executive: ',
            'v2dl': 'Democracy: ',
        }
        for prefix, label in v2_patterns.items():
            if indicator.startswith(prefix):
                full_name = label + indicator.replace(prefix, '').replace('_', ' ').title()
                break

    elif indicator.lower().startswith('wdi_'):
        # WDI indicators - preserve original formatting
        wdi_code = indicator[4:]  # Remove 'wdi_'
        full_name = wdi_code.replace('_', ' ').title()

    # Generate description
    description = f"{source} indicator: {full_name}"

    return {
        'full_name': full_name,
        'description': description,
        'source': source,
        'category': category,
        'code': indicator,
        'metadata_quality': 'inferred'  # Mark as inferred
    }

# Create fallback metadata for missing indicators
fallback_metadata = {}
for indicator in missing_indicators:
    fallback_metadata[indicator] = infer_metadata_from_name(indicator)

print(f"\n✅ Created fallback metadata for {len(fallback_metadata)} indicators")

# Save fallback metadata separately
fallback_path = metadata_dir / 'fallback_metadata.json'
with open(fallback_path, 'w') as f:
    json.dump(fallback_metadata, f, indent=2)

print(f"✅ Saved: {fallback_path}")

# Calculate final coverage
total_metadata = len(existing_metadata) + len(fallback_metadata)
final_coverage = total_metadata / len(mechanism_candidates) * 100

print(f"\n📊 Metadata Coverage Summary:")
print(f"   API-fetched:  {len(existing_metadata):>3} indicators ({len(existing_metadata)/len(mechanism_candidates)*100:.1f}%)")
print(f"   Inferred:     {len(fallback_metadata):>3} indicators ({len(fallback_metadata)/len(mechanism_candidates)*100:.1f}%)")
print(f"   Total:        {total_metadata:>3} indicators ({final_coverage:.1f}%)")

if final_coverage == 100.0:
    print(f"\n✅ 100% METADATA COVERAGE ACHIEVED")
else:
    print(f"\n⚠️  Coverage {final_coverage:.1f}% (expected 100%)")

# Show sample of fallback metadata
print(f"\n📋 Sample Fallback Metadata (first 5):")
for idx, (indicator, meta) in enumerate(list(fallback_metadata.items())[:5], 1):
    print(f"  {idx}. {indicator}:")
    print(f"     Name: {meta['full_name']}")
    print(f"     Source: {meta['source']}")
    print(f"     Category: {meta['category']}")

print("\n" + "="*80)
print("READY FOR B3 PRE-CHECKS RE-RUN")
print("="*80)
