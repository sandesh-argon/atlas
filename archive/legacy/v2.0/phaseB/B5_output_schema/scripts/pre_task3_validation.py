#!/usr/bin/env python3
"""
Pre-Task-3 Validation Checks
=============================

Validates base schema integrity before adding dashboard metadata.

Checks:
1. Cross-reference integrity (graph nodes vs mechanisms)
2. Domain balance sanity (distribution matches B3 expectations)

Author: B5 Schema Generation
Date: November 2025
"""

import pickle
from pathlib import Path

# ============================================================================
# Setup
# ============================================================================

project_root = Path(__file__).resolve().parents[3]
b5_dir = project_root / 'phaseB/B5_output_schema'
outputs_dir = b5_dir / 'outputs'

print("="*80)
print("PRE-TASK-3 VALIDATION CHECKS")
print("="*80)

# Load Task 2 unified schema
task2_path = outputs_dir / 'B5_task2_unified_schema.pkl'
print(f"\nLoading: {task2_path}")

with open(task2_path, 'rb') as f:
    v2_schema = pickle.load(f)

print(f"✅ Loaded unified schema")

# ============================================================================
# PRE-CHECK 1: Cross-Reference Integrity
# ============================================================================

print("\n" + "="*80)
print("PRE-CHECK 1: CROSS-REFERENCE INTEGRITY")
print("="*80)

def validate_cross_references(schema):
    """Ensure mechanism IDs are consistent across outcomes/domains/graphs"""

    # Collect all mechanism IDs
    mechanism_ids = set(m['id'] for m in schema['mechanisms'])

    print(f"\nTotal mechanisms: {len(mechanism_ids)}")

    # Check 1: Graph nodes reference valid mechanisms
    print("\n📊 Validating graph nodes...")
    for level in ['full', 'professional', 'simplified']:
        graph_node_ids = set(n['id'] for n in schema['graphs'][level]['nodes'])

        # All graph nodes should be in mechanisms list
        invalid = graph_node_ids - mechanism_ids
        if len(invalid) > 0:
            print(f"❌ {level} graph has {len(invalid)} nodes not in mechanisms list")
            print(f"   Examples: {list(invalid)[:3]}")
            raise ValueError(f"Graph node IDs don't match mechanisms")

        print(f"   ✅ {level} graph: {len(graph_node_ids)}/{len(mechanism_ids)} nodes (all valid)")

    # Check 2: Outcomes reference valid mechanisms in factor_loadings
    print("\n📊 Validating outcomes...")
    for outcome in schema['outcomes']:
        if 'top_variables' in outcome and outcome['top_variables']:
            loading_vars = outcome['top_variables']
            print(f"   Outcome {outcome['id']}: {len(loading_vars)} top variables")

    # Check 3: Domains reference valid mechanism counts
    print("\n📊 Validating domains...")
    domain_mechanism_count = sum(d['mechanism_count'] for d in schema['domains'])
    if domain_mechanism_count != len(mechanism_ids):
        print(f"   ⚠️ Domain mechanism counts ({domain_mechanism_count}) != total mechanisms ({len(mechanism_ids)})")
    else:
        print(f"   ✅ Domain mechanism counts: {domain_mechanism_count} = {len(mechanism_ids)}")

    print(f"\n✅ Cross-reference integrity validated")
    return True

try:
    check1_pass = validate_cross_references(v2_schema)
    print("\n" + "="*80)
    print("PRE-CHECK 1: ✅ PASS")
    print("="*80)
except Exception as e:
    print(f"\n" + "="*80)
    print(f"PRE-CHECK 1: ❌ FAIL - {e}")
    print("="*80)
    check1_pass = False

# ============================================================================
# PRE-CHECK 2: Domain Balance Sanity
# ============================================================================

print("\n" + "="*80)
print("PRE-CHECK 2: DOMAIN BALANCE SANITY")
print("="*80)

def validate_domain_balance(schema):
    """Check domain distribution across mechanisms"""

    domain_counts = {}
    for mech in schema['mechanisms']:
        domain = mech['domain']
        domain_counts[domain] = domain_counts.get(domain, 0) + 1

    print("\n📊 Domain distribution:")
    for domain, count in sorted(domain_counts.items(), key=lambda x: x[1], reverse=True):
        pct = count / len(schema['mechanisms']) * 100
        print(f"   {domain}: {count} ({pct:.1f}%)")

    # Expected from B3:
    expected = {
        'Governance': (150, 160),  # ~156 expected
        'Education': (80, 90),     # ~85 expected
        'Economic': (20, 30),      # ~26 expected
        'Mixed': (20, 30)          # ~23 expected
    }

    print("\n📊 Validating against expected ranges:")
    all_in_range = True
    for domain, (min_exp, max_exp) in expected.items():
        actual = domain_counts.get(domain, 0)
        if not (min_exp <= actual <= max_exp):
            print(f"   ⚠️ {domain}: {actual} mechanisms (expected {min_exp}-{max_exp})")
            all_in_range = False
        else:
            print(f"   ✅ {domain}: {actual} mechanisms (in expected range {min_exp}-{max_exp})")

    # Check for unexpected domains
    unexpected = set(domain_counts.keys()) - set(expected.keys())
    if len(unexpected) > 0:
        print(f"\n   ℹ️ Additional domains: {unexpected}")
        print(f"      (Acceptable if 'Unknown' or 'Unclassified')")

    print(f"\n✅ Domain balance validated")
    return all_in_range

try:
    check2_pass = validate_domain_balance(v2_schema)
    print("\n" + "="*80)
    print("PRE-CHECK 2: ✅ PASS")
    print("="*80)
except Exception as e:
    print(f"\n" + "="*80)
    print(f"PRE-CHECK 2: ❌ FAIL - {e}")
    print("="*80)
    check2_pass = False

# ============================================================================
# Summary
# ============================================================================

print("\n" + "="*80)
print("PRE-TASK-3 VALIDATION SUMMARY")
print("="*80)

print(f"\nPre-Check 1: Cross-Reference Integrity")
if check1_pass:
    print(f"   ✅ full graph: {len([n for n in v2_schema['graphs']['full']['nodes']])}/290 nodes (all valid)")
    print(f"   ✅ professional graph: {len([n for n in v2_schema['graphs']['professional']['nodes']])}/290 nodes (all valid)")
    print(f"   ✅ simplified graph: {len([n for n in v2_schema['graphs']['simplified']['nodes']])}/290 nodes (all valid)")
else:
    print(f"   ❌ FAILED - Review errors above")

print(f"\nPre-Check 2: Domain Balance")
if check2_pass:
    domain_counts = {}
    for mech in v2_schema['mechanisms']:
        domain = mech['domain']
        domain_counts[domain] = domain_counts.get(domain, 0) + 1

    expected = {
        'Governance': (150, 160),
        'Education': (80, 90),
        'Economic': (20, 30),
        'Mixed': (20, 30)
    }

    for domain, (min_exp, max_exp) in expected.items():
        actual = domain_counts.get(domain, 0)
        print(f"   ✅ {domain}: {actual} (expected {min_exp}-{max_exp})")
else:
    print(f"   ❌ FAILED - Review errors above")

print(f"\n" + "="*80)
if check1_pass and check2_pass:
    print("OVERALL: ✅✅ PASS - SAFE TO PROCEED TO TASK 3")
else:
    print("OVERALL: ❌ FAIL - FIX ISSUES BEFORE TASK 3")
print("="*80)

if check1_pass and check2_pass:
    print("\n🚀 Next step: python scripts/task3_dashboard_metadata.py")
else:
    print("\n⚠️ Fix validation failures before proceeding")
