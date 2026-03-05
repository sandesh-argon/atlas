#!/usr/bin/env python3
"""
B5 Task 4: Validate Schema Completeness
========================================

Validates complete V2 schema before final export:
- ADDITION 1: Schema size validation (<5 MB browser limit)
- Node/outcome coverage validation
- Metadata completeness validation
- Cross-reference validation

Inputs:
- outputs/B5_task3_dashboard_schema.pkl

Outputs:
- Validation report (console)
- outputs/B5_validation_report.txt

Author: B5 Schema Generation
Date: November 2025
"""

import pickle
import json
import numpy as np
from pathlib import Path
from datetime import datetime

# JSON serializer for numpy types
def json_serializer(obj):
    """Convert numpy types to native Python types for JSON serialization"""
    if isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.bool_):
        return bool(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

# ============================================================================
# Setup
# ============================================================================

project_root = Path(__file__).resolve().parents[3]
b5_dir = project_root / 'phaseB/B5_output_schema'
outputs_dir = b5_dir / 'outputs'

print("="*80)
print("B5 TASK 4: VALIDATE SCHEMA COMPLETENESS")
print("="*80)
print(f"\nTimestamp: {datetime.now().isoformat()}")

# ============================================================================
# Load Task 3 Dashboard Schema
# ============================================================================

print("\n" + "="*80)
print("LOADING TASK 3 DASHBOARD SCHEMA")
print("="*80)

task3_path = outputs_dir / 'B5_task3_dashboard_schema.pkl'
print(f"Loading: {task3_path}")

with open(task3_path, 'rb') as f:
    dashboard_schema = pickle.load(f)

print(f"✅ Loaded dashboard schema")
print(f"   - Outcomes: {len(dashboard_schema['outcomes'])}")
print(f"   - Mechanisms: {len(dashboard_schema['mechanisms'])}")
print(f"   - Domains: {len(dashboard_schema['domains'])}")
print(f"   - Graphs: {len(dashboard_schema['graphs'])}")
print(f"   - Dashboard metadata: {'dashboard_metadata' in dashboard_schema}")

# ============================================================================
# ADDITION 1: Schema Size Validation
# ============================================================================

print("\n" + "="*80)
print("ADDITION 1: SCHEMA SIZE VALIDATION")
print("="*80)

def validate_schema_size(schema, max_size_mb=5.0):
    """
    Validate schema size to prevent browser memory issues

    ADDITION 1: <5 MB browser limit for smooth rendering
    """

    # Calculate JSON size (what browser will receive)
    schema_json = json.dumps(schema, default=json_serializer)
    size_bytes = len(schema_json)
    size_mb = size_bytes / (1024 * 1024)

    print(f"\n📊 Schema size analysis:")
    print(f"   Total size: {size_mb:.2f} MB")
    print(f"   Target limit: {max_size_mb:.2f} MB")
    print(f"   Headroom: {max_size_mb - size_mb:.2f} MB ({(max_size_mb - size_mb)/max_size_mb*100:.1f}%)")

    # Component breakdown
    component_sizes = {}
    for key in schema.keys():
        component_json = json.dumps(schema[key], default=json_serializer)
        component_size_mb = len(component_json) / (1024 * 1024)
        component_sizes[key] = component_size_mb

    print(f"\n📊 Component sizes (top 5):")
    for key, size in sorted(component_sizes.items(), key=lambda x: x[1], reverse=True)[:5]:
        print(f"   {key}: {size:.2f} MB ({size/size_mb*100:.1f}%)")

    # Check if within limit
    if size_mb > max_size_mb:
        print(f"\n❌ FAIL: Schema size ({size_mb:.2f} MB) exceeds {max_size_mb:.2f} MB limit")
        print(f"   Browser may experience memory issues")
        return False
    else:
        print(f"\n✅ PASS: Schema size within {max_size_mb:.2f} MB limit")
        return True

size_valid = validate_schema_size(dashboard_schema)

# ============================================================================
# Validation 2: Node/Outcome Coverage
# ============================================================================

print("\n" + "="*80)
print("VALIDATION 2: NODE/OUTCOME COVERAGE")
print("="*80)

def validate_coverage(schema):
    """Validate all nodes/outcomes are properly represented"""

    issues = []

    # Check 1: All mechanisms have required fields
    print(f"\n📊 Check 1: Mechanism completeness")
    required_mech_fields = ['id', 'label', 'domain', 'subdomain', 'cluster_id', 'shap_score', 'visible_in']

    for i, mech in enumerate(schema['mechanisms']):
        missing_fields = [f for f in required_mech_fields if f not in mech]
        if missing_fields:
            issues.append({
                'type': 'mechanism_missing_fields',
                'id': mech.get('id', f'mechanism_{i}'),
                'missing': missing_fields
            })

    print(f"   Mechanisms checked: {len(schema['mechanisms'])}")
    print(f"   Missing fields: {len([i for i in issues if i['type'] == 'mechanism_missing_fields'])}")

    # Check 2: All outcomes have required fields
    print(f"\n📊 Check 2: Outcome completeness")
    required_outcome_fields = ['id', 'factor_name', 'primary_domain', 'r_squared', 'validation']

    for i, outcome in enumerate(schema['outcomes']):
        missing_fields = [f for f in required_outcome_fields if f not in outcome]
        if missing_fields:
            issues.append({
                'type': 'outcome_missing_fields',
                'id': outcome.get('id', f'outcome_{i}'),
                'missing': missing_fields
            })

    print(f"   Outcomes checked: {len(schema['outcomes'])}")
    print(f"   Missing fields: {len([i for i in issues if i['type'] == 'outcome_missing_fields'])}")

    # Check 3: All graph nodes exist in mechanisms list
    print(f"\n📊 Check 3: Graph node coverage")
    mechanism_ids = set(m['id'] for m in schema['mechanisms'])

    for level, graph_data in schema['graphs'].items():
        for node in graph_data['nodes']:
            if node['id'] not in mechanism_ids:
                issues.append({
                    'type': 'graph_node_orphan',
                    'id': node['id'],
                    'graph_level': level
                })

    print(f"   Graph nodes checked: {sum(len(g['nodes']) for g in schema['graphs'].values())}")
    print(f"   Orphan nodes: {len([i for i in issues if i['type'] == 'graph_node_orphan'])}")

    # Check 4: All mechanisms visible in at least one graph
    print(f"\n📊 Check 4: Mechanism visibility")
    for mech in schema['mechanisms']:
        if not mech.get('visible_in') or len(mech['visible_in']) == 0:
            issues.append({
                'type': 'mechanism_invisible',
                'id': mech['id']
            })

    print(f"   Invisible mechanisms: {len([i for i in issues if i['type'] == 'mechanism_invisible'])}")

    return issues

coverage_issues = validate_coverage(dashboard_schema)

print(f"\n" + "="*80)
print(f"COVERAGE VALIDATION RESULTS")
print(f"="*80)

if len(coverage_issues) == 0:
    print(f"✅ PERFECT - No coverage issues detected")
else:
    print(f"⚠️ {len(coverage_issues)} coverage issues detected")
    print(f"\nIssue breakdown:")
    issue_types = {}
    for issue in coverage_issues:
        issue_type = issue['type']
        issue_types[issue_type] = issue_types.get(issue_type, 0) + 1

    for issue_type, count in sorted(issue_types.items(), key=lambda x: x[1], reverse=True):
        print(f"   {issue_type}: {count}")

    if len(coverage_issues) <= 10:
        print(f"\nDetails:")
        for i, issue in enumerate(coverage_issues, 1):
            print(f"   {i}. {issue}")

# ============================================================================
# Validation 3: Metadata Completeness
# ============================================================================

print("\n" + "="*80)
print("VALIDATION 3: METADATA COMPLETENESS")
print("="*80)

def validate_metadata(schema):
    """Validate dashboard metadata is complete"""

    missing = []

    # Check 1: Dashboard metadata exists
    if 'dashboard_metadata' not in schema:
        missing.append('dashboard_metadata')
        print(f"❌ CRITICAL: dashboard_metadata missing")
        return missing

    dm = schema['dashboard_metadata']

    # Check 2: Required sections
    required_sections = ['filters', 'tooltips', 'citations', 'interactive_features', 'validation']

    for section in required_sections:
        if section not in dm:
            missing.append(f'dashboard_metadata.{section}')

    print(f"📊 Dashboard metadata sections: {len([s for s in required_sections if s in dm])}/{len(required_sections)}")

    # Check 3: Filter types
    if 'filters' in dm:
        expected_filters = ['domains', 'subdomains', 'layers', 'shap_range', 'graph_level']
        actual_filters = list(dm['filters'].keys())
        missing_filters = set(expected_filters) - set(actual_filters)
        if missing_filters:
            missing.extend([f'filters.{f}' for f in missing_filters])
        print(f"📊 Filters: {len(actual_filters)}/{len(expected_filters)}")

    # Check 4: Tooltips
    if 'tooltips' in dm:
        has_mechanisms = 'mechanisms' in dm['tooltips']
        has_outcomes = 'outcomes' in dm['tooltips']
        print(f"📊 Tooltips: mechanisms={has_mechanisms}, outcomes={has_outcomes}")

        if not has_mechanisms:
            missing.append('tooltips.mechanisms')
        if not has_outcomes:
            missing.append('tooltips.outcomes')

    # Check 5: Citations
    if 'citations' in dm:
        has_project = 'project' in dm['citations']
        has_sources = 'data_sources' in dm['citations']
        has_methods = 'methodology' in dm['citations']
        print(f"📊 Citations: project={has_project}, sources={has_sources}, methods={has_methods}")

        if not has_project:
            missing.append('citations.project')
        if not has_sources:
            missing.append('citations.data_sources')
        if not has_methods:
            missing.append('citations.methodology')

    return missing

metadata_missing = validate_metadata(dashboard_schema)

print(f"\n" + "="*80)
print(f"METADATA COMPLETENESS RESULTS")
print(f"="*80)

if len(metadata_missing) == 0:
    print(f"✅ PERFECT - All metadata sections present")
else:
    print(f"⚠️ {len(metadata_missing)} metadata sections missing:")
    for item in metadata_missing:
        print(f"   - {item}")

# ============================================================================
# Validation 4: Cross-Reference Validation
# ============================================================================

print("\n" + "="*80)
print("VALIDATION 4: CROSS-REFERENCE VALIDATION")
print("="*80)

def validate_cross_references(schema):
    """Validate cross-references are consistent"""

    issues = []

    # Build ID sets
    mechanism_ids = set(m['id'] for m in schema['mechanisms'])
    outcome_ids = set(o['id'] for o in schema['outcomes'])

    # Check 1: Tooltip IDs match mechanisms/outcomes
    print(f"\n📊 Check 1: Tooltip cross-references")
    if 'dashboard_metadata' in schema and 'tooltips' in schema['dashboard_metadata']:
        tooltips = schema['dashboard_metadata']['tooltips']

        if 'mechanisms' in tooltips:
            tooltip_mech_ids = set(tooltips['mechanisms'].keys())
            missing = mechanism_ids - tooltip_mech_ids
            extra = tooltip_mech_ids - mechanism_ids

            if missing:
                issues.append({
                    'type': 'tooltip_missing_mechanisms',
                    'count': len(missing),
                    'examples': list(missing)[:3]
                })
            if extra:
                issues.append({
                    'type': 'tooltip_extra_mechanisms',
                    'count': len(extra),
                    'examples': list(extra)[:3]
                })

            print(f"   Mechanism tooltips: {len(tooltip_mech_ids)}/{len(mechanism_ids)} ({len(missing)} missing, {len(extra)} extra)")

        if 'outcomes' in tooltips:
            tooltip_outcome_ids = set(tooltips['outcomes'].keys())
            missing = outcome_ids - tooltip_outcome_ids
            extra = tooltip_outcome_ids - outcome_ids

            if missing:
                issues.append({
                    'type': 'tooltip_missing_outcomes',
                    'count': len(missing),
                    'examples': list(missing)[:3]
                })
            if extra:
                issues.append({
                    'type': 'tooltip_extra_outcomes',
                    'count': len(extra),
                    'examples': list(extra)[:3]
                })

            print(f"   Outcome tooltips: {len(tooltip_outcome_ids)}/{len(outcome_ids)} ({len(missing)} missing, {len(extra)} extra)")

    # Check 2: Domain references
    print(f"\n📊 Check 2: Domain references")
    domain_names = set(d['name'] for d in schema['domains'])
    mechanism_domains = set(m['domain'] for m in schema['mechanisms'])

    domain_mismatch = mechanism_domains - domain_names
    if domain_mismatch:
        issues.append({
            'type': 'mechanism_domain_undefined',
            'count': len(domain_mismatch),
            'domains': list(domain_mismatch)
        })

    print(f"   Domain consistency: {len(mechanism_domains)} unique domains, {len(domain_mismatch)} undefined")

    return issues

xref_issues = validate_cross_references(dashboard_schema)

print(f"\n" + "="*80)
print(f"CROSS-REFERENCE VALIDATION RESULTS")
print(f"="*80)

if len(xref_issues) == 0:
    print(f"✅ PERFECT - All cross-references valid")
else:
    print(f"⚠️ {len(xref_issues)} cross-reference issues detected")
    for i, issue in enumerate(xref_issues, 1):
        print(f"   {i}. {issue['type']}: {issue.get('count', 'N/A')}")

# ============================================================================
# Final Validation Summary
# ============================================================================

print("\n" + "="*80)
print("FINAL VALIDATION SUMMARY")
print("="*80)

all_validations = [
    ("Schema Size (Addition 1)", size_valid),
    ("Node/Outcome Coverage", len(coverage_issues) == 0),
    ("Metadata Completeness", len(metadata_missing) == 0),
    ("Cross-Reference Validation", len(xref_issues) == 0)
]

passed = sum(1 for _, result in all_validations if result)
total = len(all_validations)

print(f"\n📊 Validation Results: {passed}/{total} passed")
for name, result in all_validations:
    status = "✅ PASS" if result else "❌ FAIL"
    print(f"   {status} - {name}")

print(f"\n" + "="*80)
if passed == total:
    print("OVERALL: ✅✅✅✅ ALL VALIDATIONS PASS")
    print("Schema ready for export!")
else:
    print(f"OVERALL: ⚠️ {total - passed}/{total} validations failed")
    print("Review failures before exporting")
print("="*80)

# ============================================================================
# Save Validation Report
# ============================================================================

print("\n" + "="*80)
print("SAVING VALIDATION REPORT")
print("="*80)

report_lines = [
    "="*80,
    "B5 TASK 4: SCHEMA VALIDATION REPORT",
    "="*80,
    f"\nTimestamp: {datetime.now().isoformat()}",
    f"\n{passed}/{total} validations passed\n"
]

# Addition 1: Schema Size
report_lines.append("\n" + "="*80)
report_lines.append("ADDITION 1: SCHEMA SIZE VALIDATION")
report_lines.append("="*80)
schema_json = json.dumps(dashboard_schema, default=json_serializer)
size_mb = len(schema_json) / (1024 * 1024)
report_lines.append(f"\nSchema size: {size_mb:.2f} MB (limit: 5.00 MB)")
report_lines.append(f"Result: {'✅ PASS' if size_valid else '❌ FAIL'}")

# Coverage
report_lines.append("\n" + "="*80)
report_lines.append("VALIDATION 2: NODE/OUTCOME COVERAGE")
report_lines.append("="*80)
report_lines.append(f"\nIssues detected: {len(coverage_issues)}")
if len(coverage_issues) > 0:
    issue_types = {}
    for issue in coverage_issues:
        issue_type = issue['type']
        issue_types[issue_type] = issue_types.get(issue_type, 0) + 1
    for issue_type, count in sorted(issue_types.items()):
        report_lines.append(f"  - {issue_type}: {count}")
report_lines.append(f"\nResult: {'✅ PASS' if len(coverage_issues) == 0 else '❌ FAIL'}")

# Metadata
report_lines.append("\n" + "="*80)
report_lines.append("VALIDATION 3: METADATA COMPLETENESS")
report_lines.append("="*80)
report_lines.append(f"\nMissing sections: {len(metadata_missing)}")
for item in metadata_missing:
    report_lines.append(f"  - {item}")
report_lines.append(f"\nResult: {'✅ PASS' if len(metadata_missing) == 0 else '❌ FAIL'}")

# Cross-references
report_lines.append("\n" + "="*80)
report_lines.append("VALIDATION 4: CROSS-REFERENCE VALIDATION")
report_lines.append("="*80)
report_lines.append(f"\nIssues detected: {len(xref_issues)}")
for issue in xref_issues:
    report_lines.append(f"  - {issue['type']}: {issue.get('count', 'N/A')}")
report_lines.append(f"\nResult: {'✅ PASS' if len(xref_issues) == 0 else '❌ FAIL'}")

# Final summary
report_lines.append("\n" + "="*80)
report_lines.append("OVERALL RESULT")
report_lines.append("="*80)
if passed == total:
    report_lines.append("\n✅✅✅✅ ALL VALIDATIONS PASS - SCHEMA READY FOR EXPORT")
else:
    report_lines.append(f"\n⚠️ {total - passed}/{total} VALIDATIONS FAILED - REVIEW BEFORE EXPORT")
report_lines.append("\n" + "="*80)

report_path = outputs_dir / 'B5_validation_report.txt'
with open(report_path, 'w') as f:
    f.write('\n'.join(report_lines))

print(f"✅ Saved validation report to: {report_path}")

print(f"\nNext step: python scripts/task5_export_schema.py")
print("="*80)
