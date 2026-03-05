#!/usr/bin/env python3
"""
B5 Task 3: Add Dashboard Metadata
==================================

Adds interactive dashboard metadata to unified schema:
- FIX 3: Tooltip truncation (80-char limit for readability)
- ADDITION 2: Label consistency validation (≤20 mismatches)

Inputs:
- outputs/B5_task2_unified_schema.pkl

Outputs:
- outputs/B5_task3_dashboard_schema.pkl

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
print("B5 TASK 3: ADD DASHBOARD METADATA")
print("="*80)
print(f"\nTimestamp: {datetime.now().isoformat()}")

# ============================================================================
# Load Task 2 Unified Schema
# ============================================================================

print("\n" + "="*80)
print("LOADING TASK 2 UNIFIED SCHEMA")
print("="*80)

task2_path = outputs_dir / 'B5_task2_unified_schema.pkl'
print(f"Loading: {task2_path}")

with open(task2_path, 'rb') as f:
    v2_schema = pickle.load(f)

print(f"✅ Loaded unified schema")
print(f"   - Outcomes: {len(v2_schema['outcomes'])}")
print(f"   - Mechanisms: {len(v2_schema['mechanisms'])}")
print(f"   - Domains: {len(v2_schema['domains'])}")
print(f"   - Graphs: {len(v2_schema['graphs'])}")

# ============================================================================
# FIX 3: Tooltip Truncation Function
# ============================================================================

def truncate_tooltip(text, max_length=80):
    """
    Truncate text to max_length characters for tooltip readability

    FIX 3: 80-char limit prevents UI overflow
    """
    if not text or not isinstance(text, str):
        return ""

    if len(text) <= max_length:
        return text

    # Truncate at word boundary
    truncated = text[:max_length].rsplit(' ', 1)[0]
    return truncated + "..."

# Test truncation
print("\n" + "="*80)
print("TESTING TOOLTIP TRUNCATION (FIX 3)")
print("="*80)

test_cases = [
    "Short text",
    "This is a much longer piece of text that should be truncated at around 80 characters to prevent overflow in tooltips",
    "Exactly eighty characters long text for testing the truncation boundary here ok",
    None,
    ""
]

for test in test_cases:
    result = truncate_tooltip(test)
    print(f"   Input length: {len(test) if test else 0} → Output: '{result}' ({len(result)} chars)")

# ============================================================================
# Step 1: Create Filter Metadata
# ============================================================================

print("\n" + "="*80)
print("STEP 1: CREATE FILTER METADATA")
print("="*80)

# Extract unique values for filters
domains = sorted(set(m['domain'] for m in v2_schema['mechanisms']))
subdomains = sorted(set(m['subdomain'] for m in v2_schema['mechanisms'] if m['subdomain'] != 'General'))
layers = sorted(set(n['layer'] for graph in v2_schema['graphs'].values() for n in graph['nodes'] if 'layer' in n))

# SHAP score ranges (for slider)
shap_scores = [m['shap_score'] for m in v2_schema['mechanisms'] if isinstance(m['shap_score'], (int, float))]
shap_min = min(shap_scores) if shap_scores else 0.0
shap_max = max(shap_scores) if shap_scores else 1.0

filter_metadata = {
    'domains': {
        'options': domains,
        'type': 'multiselect',
        'label': 'Filter by Domain',
        'default': domains  # All selected by default
    },
    'subdomains': {
        'options': subdomains,
        'type': 'multiselect',
        'label': 'Filter by Subdomain',
        'default': []  # None selected by default
    },
    'layers': {
        'options': layers,
        'type': 'multiselect',
        'label': 'Filter by Layer',
        'default': layers  # All selected by default
    },
    'shap_range': {
        'min': float(shap_min),
        'max': float(shap_max),
        'type': 'slider',
        'label': 'SHAP Score Range',
        'default': [float(shap_min), float(shap_max)]
    },
    'graph_level': {
        'options': ['full', 'professional', 'simplified'],
        'type': 'radio',
        'label': 'Graph Complexity',
        'default': 'professional'
    }
}

print(f"✅ Filter metadata created")
print(f"   - Domains: {len(domains)}")
print(f"   - Subdomains: {len(subdomains)}")
print(f"   - Layers: {len(layers) if layers else 0}")
print(f"   - SHAP range: [{shap_min:.4f}, {shap_max:.4f}]")

# ============================================================================
# Step 2: Create Tooltips (WITH FIX 3)
# ============================================================================

print("\n" + "="*80)
print("STEP 2: CREATE TOOLTIPS (WITH FIX 3)")
print("="*80)

tooltips_mechanisms = {}
truncation_count = 0

for mechanism in v2_schema['mechanisms']:
    mech_id = mechanism['id']

    # Build full tooltip text
    full_text = f"{mech_id} | {mechanism['domain']}"
    if mechanism['subdomain'] != 'General':
        full_text += f": {mechanism['subdomain']}"

    # Add SHAP score if available
    if mechanism['shap_available']:
        full_text += f" | SHAP: {mechanism['shap_score']:.4f}"

    # Add cluster info
    full_text += f" | Cluster: {mechanism['cluster_name']}"

    # FIX 3: Truncate to 80 chars
    truncated_text = truncate_tooltip(full_text, max_length=80)

    if len(truncated_text) < len(full_text):
        truncation_count += 1

    tooltips_mechanisms[mech_id] = {
        'text': truncated_text,
        'full_text': full_text,  # Keep full text for detail panel
        'truncated': len(truncated_text) < len(full_text)
    }

print(f"✅ Created {len(tooltips_mechanisms)} mechanism tooltips")
print(f"   ⚠️ Truncated: {truncation_count}/{len(tooltips_mechanisms)} ({truncation_count/len(tooltips_mechanisms)*100:.1f}%)")

# Create outcome tooltips
tooltips_outcomes = {}
for outcome in v2_schema['outcomes']:
    outcome_id = outcome['id']

    full_text = f"{outcome['factor_name']} | {outcome['primary_domain']} | R²: {outcome['r_squared']:.3f}"
    truncated_text = truncate_tooltip(full_text, max_length=80)

    tooltips_outcomes[outcome_id] = {
        'text': truncated_text,
        'full_text': full_text,
        'truncated': len(truncated_text) < len(full_text)
    }

print(f"✅ Created {len(tooltips_outcomes)} outcome tooltips")

# ============================================================================
# Step 3: Create Citations
# ============================================================================

print("\n" + "="*80)
print("STEP 3: CREATE CITATIONS")
print("="*80)

citations = {
    'project': {
        'title': 'Global Causal Discovery System V2.0',
        'authors': ['Global Development Economics Research Team'],
        'year': 2025,
        'version': '2.0',
        'url': 'https://github.com/your-repo/global-causal-discovery',
        'description': 'Bottom-up causal network reconstruction for development economics'
    },
    'data_sources': [
        {'name': 'World Bank WDI', 'url': 'https://data.worldbank.org/'},
        {'name': 'WHO GHO', 'url': 'https://www.who.int/data/gho'},
        {'name': 'UNESCO UIS', 'url': 'http://data.uis.unesco.org/'},
        {'name': 'UNICEF', 'url': 'https://data.unicef.org/'},
        {'name': 'V-Dem Institute', 'url': 'https://www.v-dem.net/'},
        {'name': 'QoG Institute', 'url': 'https://www.gu.se/en/quality-government'}
    ],
    'methodology': [
        {'step': 'Granger Causality', 'reference': 'Granger (1969)'},
        {'step': 'PC-Stable', 'reference': 'Zhang (2008)'},
        {'step': 'Backdoor Adjustment', 'reference': 'Pearl (1995)'},
        {'step': 'Factor Analysis', 'reference': 'Cattell (1966)'}
    ],
    'bibtex': """@misc{global_causal_v2,
  title={Global Causal Discovery System V2.0},
  author={Global Development Economics Research Team},
  year={2025},
  version={2.0},
  url={https://github.com/your-repo/global-causal-discovery}
}"""
}

print(f"✅ Citations created")
print(f"   - Data sources: {len(citations['data_sources'])}")
print(f"   - Methodology references: {len(citations['methodology'])}")

# ============================================================================
# Step 4: Add Interactive Features
# ============================================================================

print("\n" + "="*80)
print("STEP 4: ADD INTERACTIVE FEATURES")
print("="*80)

interactive_features = {
    'expand_collapse': {
        'enabled': True,
        'default_state': 'collapsed',
        'levels': ['domain', 'subdomain', 'cluster']
    },
    'search': {
        'enabled': True,
        'fields': ['id', 'label', 'domain', 'subdomain', 'cluster_name'],
        'fuzzy_matching': True
    },
    'highlight': {
        'enabled': True,
        'triggers': ['hover', 'click', 'search_result'],
        'highlight_paths': True  # Highlight full causal paths
    },
    'detail_panel': {
        'enabled': True,
        'sections': ['overview', 'statistics', 'connections', 'evidence']
    },
    'export': {
        'formats': ['json', 'graphml', 'csv', 'png'],
        'enabled': True
    }
}

print(f"✅ Interactive features configured")
print(f"   - Search: {interactive_features['search']['enabled']}")
print(f"   - Highlight paths: {interactive_features['highlight']['highlight_paths']}")
print(f"   - Export formats: {len(interactive_features['export']['formats'])}")

# ============================================================================
# ADDITION 2: Label Consistency Validation
# ============================================================================

print("\n" + "="*80)
print("ADDITION 2: LABEL CONSISTENCY VALIDATION")
print("="*80)

def validate_label_consistency(schema):
    """
    Validate label consistency across B3 domains, B4 graphs, and tooltips

    ADDITION 2: Detect mismatches to prevent UI confusion
    """

    mismatches = []

    # Build mechanism ID → domain mapping from mechanisms list
    mech_domain_map = {m['id']: m['domain'] for m in schema['mechanisms']}

    print(f"\n📊 Validating label consistency...")
    print(f"   Total mechanisms: {len(mech_domain_map)}")

    # Check 1: Graph node domains match mechanism domains
    print(f"\n📊 Check 1: Graph nodes vs mechanisms")
    for level, graph_data in schema['graphs'].items():
        for node in graph_data['nodes']:
            node_id = node['id']

            # Graph nodes should have same domain as mechanism list
            if node_id in mech_domain_map:
                mech_domain = mech_domain_map[node_id]

                # Check if node has domain attribute
                if 'domain' in node:
                    node_domain = node['domain']
                    if node_domain != mech_domain:
                        mismatches.append({
                            'type': 'graph_vs_mechanism',
                            'node_id': node_id,
                            'graph_level': level,
                            'graph_domain': node_domain,
                            'mechanism_domain': mech_domain
                        })

    print(f"   Graph vs mechanism: {len([m for m in mismatches if m['type'] == 'graph_vs_mechanism'])} mismatches")

    # Check 2: Tooltip labels match mechanism labels
    print(f"\n📊 Check 2: Tooltips vs mechanisms")
    for mech_id, tooltip_data in tooltips_mechanisms.items():
        if mech_id in mech_domain_map:
            mech_domain = mech_domain_map[mech_id]
            tooltip_text = tooltip_data['full_text']

            # Check if tooltip contains correct domain
            if mech_domain not in tooltip_text:
                mismatches.append({
                    'type': 'tooltip_vs_mechanism',
                    'node_id': mech_id,
                    'mechanism_domain': mech_domain,
                    'tooltip_text': tooltip_text
                })

    print(f"   Tooltips vs mechanism: {len([m for m in mismatches if m['type'] == 'tooltip_vs_mechanism'])} mismatches")

    # Check 3: Domain counts consistency
    print(f"\n📊 Check 3: Domain counts")
    domain_counts_mech = {}
    for m in schema['mechanisms']:
        domain = m['domain']
        domain_counts_mech[domain] = domain_counts_mech.get(domain, 0) + 1

    domain_counts_schema = {d['name']: d['mechanism_count'] for d in schema['domains']}

    for domain in domain_counts_mech:
        if domain in domain_counts_schema:
            if domain_counts_mech[domain] != domain_counts_schema[domain]:
                mismatches.append({
                    'type': 'domain_count_mismatch',
                    'domain': domain,
                    'mechanism_count': domain_counts_mech[domain],
                    'schema_count': domain_counts_schema[domain]
                })
        else:
            mismatches.append({
                'type': 'domain_missing_in_schema',
                'domain': domain,
                'mechanism_count': domain_counts_mech[domain]
            })

    print(f"   Domain counts: {len([m for m in mismatches if 'domain_count' in m['type'] or 'domain_missing' in m['type']])} mismatches")

    return mismatches

mismatches = validate_label_consistency(v2_schema)

print(f"\n" + "="*80)
print(f"LABEL CONSISTENCY RESULTS")
print(f"="*80)

if len(mismatches) == 0:
    print(f"✅ PERFECT - 0 label mismatches detected")
elif len(mismatches) <= 20:
    print(f"✅ PASS - {len(mismatches)} label mismatches (≤20 threshold)")
    print(f"\nMismatch details:")
    for i, mismatch in enumerate(mismatches[:10], 1):
        print(f"   {i}. {mismatch['type']}: {mismatch.get('node_id', mismatch.get('domain', 'N/A'))}")
    if len(mismatches) > 10:
        print(f"   ... and {len(mismatches) - 10} more")
else:
    print(f"⚠️ WARNING - {len(mismatches)} label mismatches (>20 threshold)")
    print(f"\nTop 10 mismatches:")
    for i, mismatch in enumerate(mismatches[:10], 1):
        print(f"   {i}. {mismatch}")

# ============================================================================
# Step 5: Assemble Dashboard Schema
# ============================================================================

print("\n" + "="*80)
print("STEP 5: ASSEMBLE DASHBOARD SCHEMA")
print("="*80)

dashboard_schema = v2_schema.copy()

dashboard_schema['dashboard_metadata'] = {
    'filters': filter_metadata,
    'tooltips': {
        'mechanisms': tooltips_mechanisms,
        'outcomes': tooltips_outcomes
    },
    'citations': citations,
    'interactive_features': interactive_features,
    'validation': {
        'label_consistency': {
            'total_mismatches': len(mismatches),
            'mismatches': mismatches if len(mismatches) <= 20 else mismatches[:20],
            'passes_threshold': len(mismatches) <= 20
        }
    }
}

print(f"✅ Dashboard metadata added")
print(f"   - Filters: {len(filter_metadata)} types")
print(f"   - Tooltips: {len(tooltips_mechanisms) + len(tooltips_outcomes)} total")
print(f"   - Label mismatches: {len(mismatches)} (threshold: ≤20)")

# ============================================================================
# Calculate Final Schema Size
# ============================================================================

print("\n" + "="*80)
print("FINAL SCHEMA SIZE CHECK")
print("="*80)

import sys

schema_json = json.dumps(dashboard_schema, default=json_serializer)
size_mb = len(schema_json) / (1024 * 1024)

print(f"📊 Schema size (with dashboard metadata): {size_mb:.2f} MB")

if size_mb > 5.0:
    print(f"⚠️ WARNING: Schema exceeds 5 MB!")
    print(f"   This may cause browser memory issues")

    # Diagnose large components
    component_sizes = {}
    for key in dashboard_schema.keys():
        component_json = json.dumps(dashboard_schema[key], default=json_serializer)
        component_sizes[key] = len(component_json) / (1024 * 1024)

    print(f"\n📊 Component sizes:")
    for key, size in sorted(component_sizes.items(), key=lambda x: x[1], reverse=True):
        print(f"   {key}: {size:.2f} MB ({size/size_mb*100:.1f}%)")
else:
    print(f"✅ Schema size acceptable (< 5 MB)")

# ============================================================================
# Save Dashboard Schema
# ============================================================================

print("\n" + "="*80)
print("SAVING DASHBOARD SCHEMA")
print("="*80)

output_path = outputs_dir / 'B5_task3_dashboard_schema.pkl'

with open(output_path, 'wb') as f:
    pickle.dump(dashboard_schema, f)

print(f"✅ Saved dashboard schema to: {output_path}")

# Also save as JSON (with dashboard metadata)
json_path = outputs_dir / 'causal_graph_v2_dashboard.json'

try:
    with open(json_path, 'w') as f:
        json.dump(dashboard_schema, f, indent=2, default=json_serializer)
    print(f"✅ Saved dashboard JSON to: {json_path}")
except Exception as e:
    print(f"⚠️ WARNING: Could not save JSON: {e}")
    print(f"   (PKL saved successfully - JSON is optional)")

# ============================================================================
# TASK 3 CHECKPOINT REPORT
# ============================================================================

print("\n" + "="*80)
print("TASK 3 CHECKPOINT REPORT")
print("="*80)

print(f"\n1. Schema Size: {size_mb:.2f} MB (target: <5 MB)")
if size_mb <= 5.0:
    print(f"   ✅ PASS")
else:
    print(f"   ❌ FAIL: Exceeds target")

print(f"\n2. Tooltip Truncation (Fix 3): {truncation_count}/{len(tooltips_mechanisms)} truncated")
if truncation_count > 0:
    print(f"   ✅ PASS - Truncation working ({truncation_count/len(tooltips_mechanisms)*100:.1f}%)")
else:
    print(f"   ℹ️ No tooltips needed truncation (all <80 chars)")

print(f"\n3. Label Consistency (Addition 2): {len(mismatches)} mismatches (threshold: ≤20)")
if len(mismatches) <= 20:
    print(f"   ✅ PASS")
else:
    print(f"   ❌ FAIL: Exceeds threshold")

print(f"\n" + "="*80)
if size_mb <= 5.0 and len(mismatches) <= 20:
    print("TASK 3 COMPLETE: ✅✅ ALL CHECKS PASS")
else:
    print("TASK 3 COMPLETE: ⚠️ WARNINGS - REVIEW ABOVE")
print("="*80)

print(f"\n✅ Dashboard Metadata Added:")
print(f"   - Filters: {len(filter_metadata)} types")
print(f"   - Mechanism tooltips: {len(tooltips_mechanisms)}")
print(f"   - Outcome tooltips: {len(tooltips_outcomes)}")
print(f"   - Truncated tooltips: {truncation_count} (Fix 3 applied)")
print(f"   - Label mismatches: {len(mismatches)} (Addition 2 validated)")
print(f"   - Schema size: {size_mb:.2f} MB")

print(f"\nNext step: python scripts/task4_validate_completeness.py")
print("="*80)
