#!/usr/bin/env python3
"""
Improve WDI Metadata Fetching
==============================

The issue: wdi_mobile, wdi_homicides don't match World Bank API codes.
Solution: Load A1 data to get original WDI column names, fetch metadata.

Author: B3 Metadata Enhancement
Date: November 2025
"""

import requests
import json
import time
import pickle
import pandas as pd
from pathlib import Path
import sys

project_root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(project_root))

print("="*80)
print("IMPROVING WDI METADATA FETCHING")
print("="*80)

# Load A1 preprocessed data to get actual WDI column names
a1_data_path = project_root / 'phaseA/A1_missingness_analysis/outputs/A2_preprocessed_data.pkl'
print(f"\nLoading A1 data from: {a1_data_path}")

with open(a1_data_path, 'rb') as f:
    a1_data = pickle.load(f)

df = a1_data['data']
print(f"✅ Loaded data: {df.shape[0]} rows × {df.shape[1]} columns")

# Load B2 mechanism candidates
b2_checkpoint_path = project_root / 'phaseB/B2_mechanism_identification/outputs/B2_bridging_subgraph_checkpoint.pkl'
with open(b2_checkpoint_path, 'rb') as f:
    b2_data = pickle.load(f)
mechanism_candidates = b2_data['mechanism_candidates']

# Identify WDI indicators in mechanism candidates
wdi_indicators = [m for m in mechanism_candidates if m.lower().startswith('wdi_')]
print(f"\n✅ Found {len(wdi_indicators)} WDI indicators in mechanism candidates")

# Check which ones are actually in the dataframe
wdi_in_data = [w for w in wdi_indicators if w in df.columns]
print(f"✅ {len(wdi_in_data)} are present in A1 data")

# World Bank API
base_url = "https://api.worldbank.org/v2/indicator"
metadata_dir = project_root / 'phaseA/A0_data_acquisition/metadata'

# Load existing metadata
wdi_metadata_path = metadata_dir / 'wdi_metadata.json'
with open(wdi_metadata_path, 'r') as f:
    wdi_metadata = json.load(f)

print(f"\nExisting WDI metadata: {len(wdi_metadata)} indicators")

# Common WDI indicator code mappings (manual corrections)
wdi_code_mappings = {
    'wdi_mobile': 'IT.CEL.SETS.P2',
    'wdi_homicides': 'VC.IHR.PSRC.P5',
    'wdi_homicidesm': 'VC.IHR.PSRC.MA.P5',
    'wdi_internet': 'IT.NET.USER.ZS',
    'wdi_emp': 'SL.EMP.TOTL.SP.ZS',
    'wdi_empf': 'SL.EMP.TOTL.SP.FE.ZS',
    'wdi_empm': 'SL.EMP.TOTL.SP.MA.ZS',
    'wdi_empind': 'SL.IND.EMPL.ZS',
    'wdi_empindm': 'SL.IND.EMPL.MA.ZS',
    'wdi_emppryilo': 'SL.EMP.INSV.FE.ZS',
    'wdi_lfpyilo': 'SL.TLF.CACT.ZS',
    'wdi_lfpedub': 'SL.TLF.BASC.ZS',
    'wdi_lfpeduif': 'SL.TLF.INTM.FE.ZS',
    'wdi_lfpedubm': 'SL.TLF.BASC.MA.ZS',
    'wdi_lfpedui': 'SL.TLF.INTM.ZS',
    'wdi_gertf': 'SE.TER.ENRR.FE',
    'wdi_gertm': 'SE.TER.ENRR.MA',
    'wdi_nersf': 'SE.SEC.NENR.FE',
    'wdi_gniatlcur': 'NY.GNP.ATLS.CD',
    'wdi_gnicon2015': 'NY.GNP.MKTP.KD',
    'wdi_acelr': 'SE.PRM.CMPT.ZS',
    'wdi_expedus': 'SE.XPD.TOTL.GD.ZS',
    'wdi_interrev': 'GC.TAX.INTT.RV.ZS',
    'wdi_refasy': 'SM.POP.REFG',
    'wdi_unempfne': 'SL.UEM.ADVN.FE.ZS',
    'wdi_wombuslawi': 'IC.FRM.FEMO.ZS'
}

print(f"\n🔍 Attempting to fetch {len([w for w in wdi_indicators if w not in wdi_metadata])} missing WDI indicators...")

fetched_count = 0
for indicator in wdi_indicators:
    if indicator in wdi_metadata:
        continue  # Already have it

    # Try mapped code first
    indicator_code = wdi_code_mappings.get(indicator)

    if not indicator_code:
        # Try removing 'wdi_' and converting underscores
        indicator_code = indicator.replace('wdi_', '').upper()

    try:
        url = f"{base_url}/{indicator_code}?format=json"
        response = requests.get(url, timeout=10)

        if response.status_code == 200:
            data = response.json()

            if len(data) > 1 and len(data[1]) > 0:
                info = data[1][0]

                wdi_metadata[indicator] = {
                    'full_name': info.get('name', indicator),
                    'description': info.get('sourceNote', ''),
                    'source': info.get('sourceOrganization', 'World Bank'),
                    'topics': [t.get('value', '') for t in info.get('topics', [])],
                    'unit': info.get('unit', ''),
                    'code': indicator_code
                }
                fetched_count += 1
                print(f"  ✅ {indicator}: {wdi_metadata[indicator]['full_name'][:60]}...")
            else:
                print(f"  ⚠️  {indicator}: No data for code {indicator_code}")
        else:
            print(f"  ⚠️  {indicator}: HTTP {response.status_code} for code {indicator_code}")

        time.sleep(0.1)

    except Exception as e:
        print(f"  ❌ {indicator}: {str(e)}")

print(f"\n✅ Fetched {fetched_count} additional WDI indicators")
print(f"📊 Total WDI metadata: {len(wdi_metadata)} indicators")

# Save updated metadata
with open(wdi_metadata_path, 'w') as f:
    json.dump(wdi_metadata, f, indent=2)

print(f"✅ Updated: {wdi_metadata_path}")

# Calculate new coverage
total_metadata = len(wdi_metadata)
for source in ['vdem', 'unesco', 'pwt']:
    path = metadata_dir / f'{source}_{"codebook" if source == "vdem" else "metadata"}.json'
    if path.exists():
        with open(path, 'r') as f:
            total_metadata += len(json.load(f))

new_coverage = total_metadata / len(mechanism_candidates) * 100
print(f"\n📈 Updated Coverage: {new_coverage:.1f}% (was 45.9%)")

if new_coverage >= 80:
    print("✅ COVERAGE ≥80% - READY FOR B3")
else:
    print(f"⚠️  Coverage {new_coverage:.1f}% < 80%")
    print("   Options:")
    print("   1. Proceed with current coverage (sufficient for most mechanisms)")
    print("   2. Create generic metadata for remaining indicators")

print("="*80)
