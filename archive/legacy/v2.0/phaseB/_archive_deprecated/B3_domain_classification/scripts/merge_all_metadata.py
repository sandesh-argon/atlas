#!/usr/bin/env python3
"""
Merge All Metadata Sources into Unified File
=============================================

Combines:
1. Enhanced metadata (151 indicators from V1.0 matching + API)
2. Fallback metadata (178 indicators from inference)

Creates single unified_metadata.json with all 329 indicators.

Author: B3 Metadata Preparation
Date: November 2025
"""

import json
import pickle
from pathlib import Path
import sys

project_root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(project_root))

print("="*80)
print("MERGING ALL METADATA SOURCES")
print("="*80)

# Load B2 mechanism candidates
b2_checkpoint_path = project_root / 'phaseB/B2_mechanism_identification/outputs/B2_bridging_subgraph_checkpoint.pkl'
with open(b2_checkpoint_path, 'rb') as f:
    b2_data = pickle.load(f)
mechanism_candidates = b2_data['mechanism_candidates']

print(f"\n✅ Loaded {len(mechanism_candidates)} mechanism candidates")

# Load metadata sources
metadata_dir = project_root / 'phaseA/A0_data_acquisition/metadata'

# 1. Enhanced metadata (from V1.0 matching)
enhanced_path = metadata_dir / 'enhanced_metadata.json'
with open(enhanced_path, 'r') as f:
    enhanced_metadata = json.load(f)

print(f"\n📊 Enhanced metadata: {len(enhanced_metadata)} indicators")

# 2. Fallback metadata
fallback_path = metadata_dir / 'fallback_metadata.json'
with open(fallback_path, 'r') as f:
    fallback_metadata = json.load(f)

print(f"📊 Fallback metadata: {len(fallback_metadata)} indicators")

# Merge: Enhanced takes precedence over fallback
unified_metadata = {}

for indicator in mechanism_candidates:
    if indicator in enhanced_metadata:
        unified_metadata[indicator] = enhanced_metadata[indicator]
        # Mark quality
        if 'metadata_quality' not in unified_metadata[indicator]:
            unified_metadata[indicator]['metadata_quality'] = 'high'
    elif indicator in fallback_metadata:
        unified_metadata[indicator] = fallback_metadata[indicator]
        # Already has 'metadata_quality': 'inferred'
    else:
        # Should never happen, but create basic metadata as safety
        unified_metadata[indicator] = {
            'full_name': indicator.replace('_', ' ').title(),
            'description': f'Indicator: {indicator}',
            'source': 'Unknown',
            'category': 'Mixed',
            'code': indicator,
            'metadata_quality': 'minimal'
        }

# Verify coverage
coverage = len(unified_metadata) / len(mechanism_candidates) * 100
print(f"\n✅ Unified metadata coverage: {len(unified_metadata)}/{len(mechanism_candidates)} ({coverage:.1f}%)")

# Quality breakdown
quality_counts = {}
for meta in unified_metadata.values():
    quality = meta.get('metadata_quality', 'unknown')
    quality_counts[quality] = quality_counts.get(quality, 0) + 1

print(f"\n📊 Quality Breakdown:")
for quality, count in sorted(quality_counts.items(), key=lambda x: x[1], reverse=True):
    pct = count / len(unified_metadata) * 100
    print(f"   {quality:>12}: {count:>3} indicators ({pct:>5.1f}%)")

# Source breakdown
source_counts = {}
for meta in unified_metadata.values():
    source = meta.get('source', 'Unknown')
    source_counts[source] = source_counts.get(source, 0) + 1

print(f"\n📊 Source Breakdown (Top 10):")
for source, count in sorted(source_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
    pct = count / len(unified_metadata) * 100
    print(f"   {source:>40}: {count:>3} ({pct:>5.1f}%)")

# Save unified metadata
unified_path = metadata_dir / 'unified_metadata.json'
with open(unified_path, 'w') as f:
    json.dump(unified_metadata, f, indent=2)

print(f"\n✅ Saved unified metadata: {unified_path}")
print(f"   File size: {unified_path.stat().st_size / 1024:.1f} KB")

# Sample metadata
print(f"\n📋 Sample Metadata (first 3):")
for idx, (indicator, meta) in enumerate(list(unified_metadata.items())[:3], 1):
    print(f"\n  {idx}. {indicator}:")
    print(f"     Full name: {meta['full_name']}")
    print(f"     Source: {meta['source']}")
    print(f"     Category: {meta.get('category', 'N/A')}")
    print(f"     Quality: {meta.get('metadata_quality', 'N/A')}")

print("\n" + "="*80)
print("✅ READY FOR B3 TASK 1.1")
print("="*80)
