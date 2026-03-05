#!/usr/bin/env python3
"""
B5 Task 1: Load & Integrate B1-B4 Outputs (CORRECTED)
======================================================

Loads all Phase B outputs using ACTUAL file paths.

Inputs:
- B1: B1_validated_outcomes.pkl
- B4: B4_prepared_data.pkl (contains B2+B3 data), B4_*_schema.json, B4_shap_scores.pkl

Outputs:
- outputs/B5_task1_integrated_data.pkl

Author: B5 Schema Generation
Date: November 2025
"""

import pickle
import json
from pathlib import Path
from datetime import datetime

# ============================================================================
# Setup
# ============================================================================

project_root = Path(__file__).resolve().parents[3]
b5_dir = project_root / 'phaseB/B5_output_schema'
outputs_dir = b5_dir / 'outputs'
outputs_dir.mkdir(exist_ok=True)

print("="*80)
print("B5 TASK 1: LOAD & INTEGRATE B1-B4 OUTPUTS (CORRECTED)")
print("="*80)
print(f"\nTimestamp: {datetime.now().isoformat()}")

# ============================================================================
# Load B1: Validated Outcomes
# ============================================================================

print("\n" + "="*80)
print("LOADING B1 OUTCOMES")
print("="*80)

b1_path = project_root / 'phaseB/B1_outcome_discovery/outputs/B1_validated_outcomes.pkl'
print(f"Loading: {b1_path}")

with open(b1_path, 'rb') as f:
    b1_data = pickle.load(f)

print(f"✅ B1 Loaded:")
print(f"   - Outcomes: {len(b1_data['outcomes'])}")
print(f"   - Keys: {list(b1_data.keys())}")

# ============================================================================
# Load B4: Prepared Data (contains B2+B3)
# ============================================================================

print("\n" + "="*80)
print("LOADING B4 PREPARED DATA (contains B2+B3)")
print("="*80)

b4_prepared_path = project_root / 'phaseB/B4_multi_level_pruning/outputs/B4_prepared_data.pkl'
print(f"Loading: {b4_prepared_path}")

with open(b4_prepared_path, 'rb') as f:
    b4_prepared = pickle.load(f)

print(f"✅ B4 Prepared Data Loaded:")
print(f"   - B3 Mechanisms: {len(b4_prepared['b3_data']['mechanisms'])}")
print(f"   - B3 Clusters: {len(b4_prepared['b3_data']['classified_clusters'])}")
print(f"   - Graph nodes: {len(b4_prepared['graph']['subgraph'].nodes())}")
print(f"   - Graph edges: {len(b4_prepared['graph']['subgraph'].edges())}")

# ============================================================================
# Load B4: Graph Schemas (3 versions)
# ============================================================================

print("\n" + "="*80)
print("LOADING B4 GRAPH SCHEMAS")
print("="*80)

b4_outputs_dir = project_root / 'phaseB/B4_multi_level_pruning/outputs'

b4_graphs = {}
for level in ['full', 'professional', 'simplified']:
    graph_path = b4_outputs_dir / f'B4_{level}_schema.json'
    print(f"Loading: {graph_path}")

    with open(graph_path, 'r') as f:
        b4_graphs[level] = json.load(f)

    print(f"  ✅ {level}: {len(b4_graphs[level]['nodes'])} nodes, {len(b4_graphs[level]['edges'])} edges")

# ============================================================================
# Load B4: SHAP Scores
# ============================================================================

print("\n" + "="*80)
print("LOADING B4 SHAP SCORES")
print("="*80)

b4_shap_path = b4_outputs_dir / 'B4_shap_scores.pkl'
print(f"Loading: {b4_shap_path}")

with open(b4_shap_path, 'rb') as f:
    shap_data = pickle.load(f)

print(f"✅ SHAP Scores Loaded:")
print(f"   - Mechanism SHAP scores: {len(shap_data['mechanism_shap_scores'])}")

# ============================================================================
# Validate Consistency
# ============================================================================

print("\n" + "="*80)
print("VALIDATING CONSISTENCY")
print("="*80)

# Check 1: B1 outcomes count
print(f"\n📊 Check 1: B1 Outcomes")
print(f"   Expected: 9, Actual: {len(b1_data['outcomes'])}")
if len(b1_data['outcomes']) == 9:
    print(f"   ✅ PASS")
else:
    print(f"   ⚠️ WARNING: Expected 9 outcomes")

# Check 2: B4 prepared data has B3 mechanisms
print(f"\n📊 Check 2: B3 Mechanisms in B4")
print(f"   Expected: 290, Actual: {len(b4_prepared['b3_data']['mechanisms'])}")
if len(b4_prepared['b3_data']['mechanisms']) == 290:
    print(f"   ✅ PASS")
else:
    print(f"   ⚠️ WARNING: Expected 290 mechanisms")

# Check 3: B4 graph schemas consistency
print(f"\n📊 Check 3: B4 Graph Schemas")
print(f"   Full: {len(b4_graphs['full']['nodes'])} nodes (expected 290)")
print(f"   Professional: {len(b4_graphs['professional']['nodes'])} nodes")
print(f"   Simplified: {len(b4_graphs['simplified']['nodes'])} nodes")

if len(b4_graphs['full']['nodes']) == 290:
    print(f"   ✅ PASS")
else:
    print(f"   ⚠️ WARNING: Full graph should have 290 nodes")

# Check 4: SHAP coverage
print(f"\n📊 Check 4: SHAP Coverage")
print(f"   Mechanisms: {len(b4_prepared['b3_data']['mechanisms'])}")
print(f"   SHAP scores: {len(shap_data['mechanism_shap_scores'])}")

num_mechanisms = len(b4_prepared['b3_data']['mechanisms'])
num_shap = len(shap_data['mechanism_shap_scores'])

if num_shap == num_mechanisms:
    print(f"   ✅ PASS - 100% coverage")
else:
    coverage_pct = num_shap / num_mechanisms * 100
    print(f"   ⚠️ WARNING: {coverage_pct:.1f}% coverage")

# ============================================================================
# Save Integrated Data
# ============================================================================

print("\n" + "="*80)
print("SAVING INTEGRATED DATA")
print("="*80)

integrated_data = {
    'b1_data': b1_data,
    'b4_prepared': b4_prepared,  # Contains B2+B3 data
    'b4_graphs': b4_graphs,
    'shap_data': shap_data,
    'metadata': {
        'timestamp': datetime.now().isoformat(),
        'source_files': {
            'b1': str(b1_path),
            'b4_prepared': str(b4_prepared_path),
            'b4_shap': str(b4_shap_path)
        }
    }
}

output_path = outputs_dir / 'B5_task1_integrated_data.pkl'

with open(output_path, 'wb') as f:
    pickle.dump(integrated_data, f)

print(f"✅ Saved integrated data to: {output_path}")

# ============================================================================
# Summary
# ============================================================================

print("\n" + "="*80)
print("TASK 1 COMPLETE")
print("="*80)

print(f"\n✅ Data Summary:")
print(f"   - B1 Outcomes: {len(b1_data['outcomes'])}")
print(f"   - B3 Mechanisms (from B4): {len(b4_prepared['b3_data']['mechanisms'])}")
print(f"   - B3 Clusters (from B4): {len(b4_prepared['b3_data']['classified_clusters'])}")
print(f"   - B4 Full Graph: {len(b4_graphs['full']['nodes'])} nodes")
print(f"   - B4 SHAP Scores: {len(shap_data['mechanism_shap_scores'])} mechanisms")

print(f"\n✅ ALL DATA LOADED AND VALIDATED")
print(f"\nNext step: python scripts/task2_unified_schema.py")
print("="*80)
