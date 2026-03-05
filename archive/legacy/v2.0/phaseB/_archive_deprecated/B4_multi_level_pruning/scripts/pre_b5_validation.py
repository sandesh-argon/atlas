#!/usr/bin/env python3
"""
Pre-B5 Validation Checks
========================

3 critical validations before launching B5:
1. JSON schema integrity
2. SHAP score distribution
3. Cross-level consistency

Author: B4→B5 Handoff
Date: November 2025
"""

import json
import pickle
import numpy as np
from pathlib import Path

# ============================================================================
# Setup
# ============================================================================

project_root = Path(__file__).resolve().parents[3]
b4_dir = project_root / 'phaseB/B4_multi_level_pruning'
outputs_dir = b4_dir / 'outputs'

print("="*80)
print("PRE-B5 VALIDATION CHECKS")
print("="*80)
print("\nValidating B4 outputs before B5 integration...\n")

passed_checks = 0
total_checks = 3

# ============================================================================
# CHECK 1: JSON Schema Integrity
# ============================================================================

print("="*80)
print("CHECK 1: JSON SCHEMA INTEGRITY")
print("="*80)

try:
    # Load all 3 schemas
    schemas = {}
    for level in ['full', 'professional', 'simplified']:
        path = outputs_dir / f'B4_{level}_schema.json'
        with open(path, 'r') as f:
            schemas[level] = json.load(f)
        print(f"   ✅ Loaded {level} schema")

    # Verify structure
    for level, schema in schemas.items():
        assert 'nodes' in schema, f"{level}: Missing 'nodes' key"
        assert 'edges' in schema, f"{level}: Missing 'edges' key"
        assert 'metadata' in schema, f"{level}: Missing 'metadata' key"

        # Verify node metadata
        for node in schema['nodes']:
            assert 'id' in node, f"{level}: Node missing 'id'"
            assert 'domain' in node, f"{level}: Node missing 'domain'"
            assert 'shap_score' in node, f"{level}: Node missing 'shap_score'"
            assert 'label' in node, f"{level}: Node missing 'label'"

        # Verify edge metadata
        for edge in schema['edges']:
            assert 'source' in edge, f"{level}: Edge missing 'source'"
            assert 'target' in edge, f"{level}: Edge missing 'target'"

    print(f"\n✅ CHECK 1 PASSED: All 3 JSON schemas valid")
    print(f"   - full: {len(schemas['full']['nodes'])} nodes, {len(schemas['full']['edges'])} edges")
    print(f"   - professional: {len(schemas['professional']['nodes'])} nodes, {len(schemas['professional']['edges'])} edges")
    print(f"   - simplified: {len(schemas['simplified']['nodes'])} nodes, {len(schemas['simplified']['edges'])} edges")

    passed_checks += 1
    check1_pass = True

except Exception as e:
    print(f"\n❌ CHECK 1 FAILED: {e}")
    check1_pass = False

# ============================================================================
# CHECK 2: SHAP Score Distribution
# ============================================================================

print("\n" + "="*80)
print("CHECK 2: SHAP SCORE DISTRIBUTION")
print("="*80)

try:
    # Load SHAP scores
    shap_path = outputs_dir / 'B4_shap_scores.pkl'
    with open(shap_path, 'rb') as f:
        shap_data = pickle.load(f)

    scores = list(shap_data['mechanism_shap_scores'].values())

    print(f"\n📊 SHAP score distribution:")
    print(f"   - Count: {len(scores)}")
    print(f"   - Min: {min(scores):.6f}")
    print(f"   - Median: {np.median(scores):.6f}")
    print(f"   - Mean: {np.mean(scores):.6f}")
    print(f"   - Max: {max(scores):.6f}")
    print(f"   - Sum: {sum(scores):.6f} (should be ~1.0 for RF importance)")

    # Verify separation
    top_10pct = np.percentile(scores, 90)
    median = np.median(scores)
    separation = top_10pct / median if median > 0 else 0

    print(f"\n📊 Separation Analysis:")
    print(f"   - Top 10%: {top_10pct:.6f}")
    print(f"   - Median: {median:.6f}")
    print(f"   - Separation: {separation:.2f}×")

    assert separation >= 1.5, f"Separation {separation:.2f}× too low (<1.5×)"

    print(f"\n✅ CHECK 2 PASSED: Separation {separation:.2f}× ≥ 1.5× threshold")
    passed_checks += 1
    check2_pass = True

except Exception as e:
    print(f"\n❌ CHECK 2 FAILED: {e}")
    check2_pass = False

# ============================================================================
# CHECK 3: Cross-Level Consistency
# ============================================================================

print("\n" + "="*80)
print("CHECK 3: CROSS-LEVEL CONSISTENCY")
print("="*80)

try:
    # Verify node IDs consistent across levels
    full_nodes = set(node['id'] for node in schemas['full']['nodes'])
    prof_nodes = set(node['id'] for node in schemas['professional']['nodes'])
    simp_nodes = set(node['id'] for node in schemas['simplified']['nodes'])

    # Professional should be subset of Full
    assert prof_nodes.issubset(full_nodes), "Professional nodes not subset of Full"

    # Simplified should be subset of Full (but not necessarily Professional)
    assert simp_nodes.issubset(full_nodes), "Simplified nodes not subset of Full"

    print(f"\n📊 Node Consistency:")
    print(f"   - Full nodes: {len(full_nodes)}")
    print(f"   - Professional ⊆ Full: {len(prof_nodes)}/{len(full_nodes)} ✅")
    print(f"   - Simplified ⊆ Full: {len(simp_nodes)}/{len(full_nodes)} ✅")

    # Verify edge sources/targets exist in node sets
    for level, schema in schemas.items():
        node_ids = set(n['id'] for n in schema['nodes'])

        for edge in schema['edges']:
            assert edge['source'] in node_ids, f"{level}: Edge source '{edge['source']}' not in nodes"
            assert edge['target'] in node_ids, f"{level}: Edge target '{edge['target']}' not in nodes"

    print(f"\n📊 Edge Consistency:")
    for level in ['full', 'professional', 'simplified']:
        edge_count = len(schemas[level]['edges'])
        print(f"   - {level}: All {edge_count} edge sources/targets valid ✅")

    # Verify SHAP scores match between schema and pkl
    schema_shap_ids = set(n['id'] for n in schemas['full']['nodes'])
    pkl_shap_ids = set(shap_data['mechanism_shap_scores'].keys())

    assert schema_shap_ids == pkl_shap_ids, "SHAP IDs mismatch between schema and pkl"

    print(f"\n📊 SHAP Consistency:")
    print(f"   - Schema SHAP IDs: {len(schema_shap_ids)}")
    print(f"   - PKL SHAP IDs: {len(pkl_shap_ids)}")
    print(f"   - Match: {schema_shap_ids == pkl_shap_ids} ✅")

    print(f"\n✅ CHECK 3 PASSED: All cross-level consistency checks passed")
    passed_checks += 1
    check3_pass = True

except Exception as e:
    print(f"\n❌ CHECK 3 FAILED: {e}")
    check3_pass = False

# ============================================================================
# Summary
# ============================================================================

print("\n" + "="*80)
print("PRE-B5 VALIDATION SUMMARY")
print("="*80)

print(f"\n📊 Results:")
print(f"   - Check 1 (JSON Schema Integrity): {'✅ PASS' if check1_pass else '❌ FAIL'}")
print(f"   - Check 2 (SHAP Distribution): {'✅ PASS' if check2_pass else '❌ FAIL'}")
print(f"   - Check 3 (Cross-Level Consistency): {'✅ PASS' if check3_pass else '❌ FAIL'}")

print(f"\n{'='*60}")
print(f"OVERALL: {passed_checks}/{total_checks} CHECKS PASSED")
print(f"{'='*60}")

if passed_checks == total_checks:
    print(f"\n✅ ALL PRE-B5 VALIDATIONS PASSED")
    print(f"🎯 B4 outputs are valid and ready for B5 integration")
    print(f"\nNext step: Launch B5 Output Schema Generation")
else:
    print(f"\n❌ {total_checks - passed_checks} CHECKS FAILED")
    print(f"⚠️  Fix issues before proceeding to B5")

print("\n" + "="*80)
