#!/usr/bin/env python3
"""
Fix Labels Direct - Use mechanism IDs directly for indicator lookup

Since B3 mechanism IDs ARE the original indicator IDs, we can look them up directly
in the indicator databases without any transformation.
"""

import json
import pandas as pd
from pathlib import Path
from typing import Dict, Set
import re

# Paths
PROJECT_ROOT = Path("<repo-root>/v2.0")
INDICATORS_DIR = PROJECT_ROOT / "indicators"
VIZ_DIR = PROJECT_ROOT / "viz_implementation_package"
SCHEMA_PATH = VIZ_DIR / "data" / "causal_graph_v2_final.json"

# Load all indicator databases
print("=" * 70)
print("COMPREHENSIVE LABEL IMPROVEMENT - DIRECT LOOKUP")
print("=" * 70)

print("\n[1/4] Loading indicator databases...")

# World Bank WDI
wdi_df = pd.read_csv(INDICATORS_DIR / "world_bank_indicators.csv")
wdi_lookup = dict(zip(wdi_df['id'], wdi_df['name']))
print(f"  ✓ WDI: {len(wdi_lookup):,} indicators")

# UNESCO UIS
unesco_df = pd.read_csv(INDICATORS_DIR / "UISIndicators.csv")
unesco_lookup = dict(zip(unesco_df['indicatorCode'].astype(str), unesco_df['name']))
print(f"  ✓ UNESCO: {len(unesco_lookup):,} indicators")

# WHO GHO
who_df = pd.read_csv(INDICATORS_DIR / "WHO Global Health Observatory (GHO).csv")
who_lookup = dict(zip(who_df['value__IndicatorCode'], who_df['value__IndicatorName']))
print(f"  ✓ WHO: {len(who_lookup):,} indicators")

# IMF
imf_df = pd.read_csv(INDICATORS_DIR / "IMFIndicators.csv")
imf_lookup = dict(zip(imf_df['indicators__|'], imf_df['indicators__|__label']))
print(f"  ✓ IMF: {len(imf_lookup):,} indicators")

# UNICEF
unicef_df = pd.read_csv(INDICATORS_DIR / "unicef_indicators_list.csv")
unicef_lookup = dict(zip(unicef_df['indicator_id'], unicef_df['indicator_name']))
print(f"  ✓ UNICEF: {len(unicef_lookup):,} indicators")

# Combine all lookups
all_lookups = {
    **wdi_lookup,
    **unesco_lookup,
    **who_lookup,
    **imf_lookup,
    **unicef_lookup
}
print(f"\nTotal indicator database: {len(all_lookups):,} indicators")

print("\n[2/4] Loading schema...")
with open(SCHEMA_PATH, 'r') as f:
    schema = json.load(f)
print(f"  ✓ Loaded {len(schema['mechanisms'])} mechanisms")

print("\n[3/4] Updating labels with direct lookups...")

def assess_quality(label: str) -> str:
    """Quick quality assessment"""
    if len(label) < 10:
        return 'poor'
    if ' ' not in label:
        return 'poor'
    if label.isupper() and len(label) < 30:
        return 'poor'
    if re.match(r'^[A-Z0-9._-]+$', label):
        return 'poor'
    return 'good'

improvements = 0
by_source = {}

for i, mech in enumerate(schema['mechanisms']):
    mech_id = mech['id']
    current_label = mech.get('label', mech_id)
    current_quality = mech.get('label_quality', 'unknown')

    # Try direct lookup
    if mech_id in all_lookups:
        new_label = all_lookups[mech_id]
        new_quality = assess_quality(new_label)

        if new_quality == 'good':
            # Determine source
            if mech_id in wdi_lookup:
                source = 'WDI'
            elif mech_id in unesco_lookup:
                source = 'UNESCO'
            elif mech_id in who_lookup:
                source = 'WHO'
            elif mech_id in imf_lookup:
                source = 'IMF'
            elif mech_id in unicef_lookup:
                source = 'UNICEF'
            else:
                source = 'unknown'

            # Update
            mech['label'] = new_label
            mech['label_quality'] = 'good'
            improvements += 1

            # Track by source
            if source not in by_source:
                by_source[source] = 0
            by_source[source] += 1

            if i < 20:  # Show first 20
                print(f"  ✓ [{source}] {mech_id}")
                print(f"      '{current_label}' → '{new_label}'")

print(f"\n  Total improvements: {improvements}/{len(schema['mechanisms'])}")
print(f"\n  By source:")
for source, count in sorted(by_source.items(), key=lambda x: -x[1]):
    print(f"    {source}: {count}")

print("\n[4/4] Generating quality report...")

quality_counts = {'good': 0, 'poor': 0, 'unknown': 0}
for mech in schema['mechanisms']:
    quality = mech.get('label_quality', 'unknown')
    quality_counts[quality] += 1

total = len(schema['mechanisms'])
good_pct = (quality_counts['good'] / total) * 100
poor_pct = (quality_counts['poor'] / total) * 100

print(f"\n{'='*70}")
print("FINAL LABEL QUALITY REPORT")
print(f"{'='*70}")
print(f"  Good labels: {quality_counts['good']}/{total} ({good_pct:.1f}%)")
print(f"  Poor labels: {quality_counts['poor']}/{total} ({poor_pct:.1f}%)")
print(f"  Unknown: {quality_counts['unknown']}/{total}")

if good_pct >= 80:
    print(f"\n  ✅ SUCCESS: Reached {good_pct:.1f}% good label quality!")
    status = "SUCCESS"
elif good_pct >= 60:
    print(f"\n  ⚠️  PARTIAL: {good_pct:.1f}% good labels (target: 80%+)")
    status = "PARTIAL"
else:
    print(f"\n  ❌ FAILED: Only {good_pct:.1f}% good labels (target: 80%+)")
    status = "FAILED"

print("\n[5/5] Saving updated schema...")
with open(SCHEMA_PATH, 'w') as f:
    json.dump(schema, f, indent=2)
print(f"  ✓ Schema saved to {SCHEMA_PATH}")

# Export poor quality labels for review
poor_labels = []
for mech in schema['mechanisms']:
    if mech.get('label_quality') == 'poor':
        poor_labels.append({
            'id': mech['id'],
            'label': mech['label'],
            'domain': mech.get('domain', 'unknown')
        })

if poor_labels:
    poor_labels_path = VIZ_DIR / "data" / "poor_quality_labels.json"
    with open(poor_labels_path, 'w') as f:
        json.dump(poor_labels, f, indent=2)
    print(f"  ✓ Exported {len(poor_labels)} poor labels to poor_quality_labels.json")

print(f"\n{'='*70}")
print(f"COMPLETE - Status: {status}")
print(f"{'='*70}\n")
