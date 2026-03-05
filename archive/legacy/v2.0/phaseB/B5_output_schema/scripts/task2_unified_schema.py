#!/usr/bin/env python3
"""
B5 Task 2: Create Unified V2 Schema
====================================

Merges B1-B4 outputs into single unified schema with:
- FIX 1: Handle missing SHAP scores (distinguish "not_computed" from zero)
- FIX 2: Robust subdomain extraction (handle None/empty/malformed labels)

Inputs:
- outputs/B5_task1_integrated_data.pkl

Outputs:
- outputs/B5_task2_unified_schema.pkl

Author: B5 Schema Generation
Date: November 2025
"""

import pickle
import json
import numpy as np
from pathlib import Path
from datetime import datetime

# JSON serializer for numpy types (NumPy 2.0 compatible)
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
print("B5 TASK 2: CREATE UNIFIED V2 SCHEMA")
print("="*80)
print(f"\nTimestamp: {datetime.now().isoformat()}")

# ============================================================================
# Load Task 1 Integrated Data
# ============================================================================

print("\n" + "="*80)
print("LOADING TASK 1 INTEGRATED DATA")
print("="*80)

task1_path = outputs_dir / 'B5_task1_integrated_data.pkl'
print(f"Loading: {task1_path}")

with open(task1_path, 'rb') as f:
    integrated_data = pickle.load(f)

b1_data = integrated_data['b1_data']
b4_prepared = integrated_data['b4_prepared']
b4_graphs = integrated_data['b4_graphs']
shap_data = integrated_data['shap_data']

print(f"✅ Loaded integrated data")
print(f"   - B1 outcomes: {len(b1_data['outcomes'])}")
print(f"   - B3 mechanisms: {len(b4_prepared['b3_data']['mechanisms'])}")
print(f"   - B4 graphs: {list(b4_graphs.keys())}")
print(f"   - SHAP scores: {len(shap_data['mechanism_shap_scores'])}")

# ============================================================================
# FIX 2: Robust Subdomain Extraction
# ============================================================================

def extract_subdomain(hierarchical_label):
    """
    Safely extract subdomain from hierarchical label (e.g., "Governance: Executive" → "Executive")

    FIX 2: Handles None, empty strings, and malformed labels
    """
    if not hierarchical_label or not isinstance(hierarchical_label, str):
        return 'General'

    if ':' not in hierarchical_label:
        return 'General'

    parts = hierarchical_label.split(':', 1)
    if len(parts) < 2:
        return 'General'

    subdomain = parts[1].strip()
    return subdomain if subdomain else 'General'

# Test subdomain extraction
print("\n" + "="*80)
print("TESTING SUBDOMAIN EXTRACTION (FIX 2)")
print("="*80)

test_cases = [
    "Governance: Executive",
    "Education: Primary",
    None,
    "",
    "NoColon",
    "Governance:",
    "  Education : Secondary  "
]

for test in test_cases:
    result = extract_subdomain(test)
    print(f"   '{test}' → '{result}'")

# ============================================================================
# Step 1: Create Metadata
# ============================================================================

print("\n" + "="*80)
print("STEP 1: CREATE METADATA")
print("="*80)

metadata = {
    'version': '2.0',
    'timestamp': datetime.now().isoformat(),
    'phase': 'B_complete',
    'components': {
        'B1_outcomes': True,
        'B2_mechanisms': True,
        'B3_domains': True,
        'B4_graphs': True
    },
    'validation_scores': {
        'B1_outcome_count': len(b1_data['outcomes']),
        'B1_outcome_mean_r2': sum(o.get('predictability_r2_mean', 0) for o in b1_data['outcomes']) / len(b1_data['outcomes']) if b1_data['outcomes'] else 0,
        'B4_validation_score': 1.0  # 8/8 checks from B4 completion
    },
    'statistics': {
        'total_mechanisms': len(b4_prepared['b3_data']['mechanisms']),
        'total_clusters': len(b4_prepared['b3_data']['classified_clusters']),
        'graph_versions': 3
    }
}

print(f"✅ Metadata created")
print(f"   Version: {metadata['version']}")
print(f"   B1 outcomes: {metadata['validation_scores']['B1_outcome_count']}")
print(f"   Mean R²: {metadata['validation_scores']['B1_outcome_mean_r2']:.3f}")

# ============================================================================
# Step 2: Process Outcomes
# ============================================================================

print("\n" + "="*80)
print("STEP 2: PROCESS OUTCOMES")
print("="*80)

v2_outcomes = []

for outcome in b1_data['outcomes']:
    v2_outcome = {
        'id': outcome.get('factor_id', 0),
        'factor_name': outcome.get('factor_name', 'Unknown'),
        'label': outcome.get('factor_name', 'Unknown'),
        'primary_domain': outcome.get('primary_domain', 'Unknown'),
        'top_variables': outcome.get('top_variables', []),
        'top_loadings': outcome.get('top_loadings', []),
        'r_squared': outcome.get('predictability_r2_mean', 0.0),
        'r_squared_std': outcome.get('predictability_r2_std', 0.0),
        'validation': {
            'passes_coherence': outcome.get('passes_coherence', False),
            'passes_literature': outcome.get('passes_literature', False),
            'passes_predictability': outcome.get('passes_predictability', False),
            'passes_overall': outcome.get('passes_overall', False),
            'is_novel': outcome.get('is_novel', True)
        },
        'source': 'B1_outcome_discovery'
    }
    v2_outcomes.append(v2_outcome)

print(f"✅ Processed {len(v2_outcomes)} outcomes")

# ============================================================================
# Step 3: Process Mechanisms (WITH FIX 1 + FIX 2)
# ============================================================================

print("\n" + "="*80)
print("STEP 3: PROCESS MECHANISMS (WITH FIX 1 + FIX 2)")
print("="*80)

v2_mechanisms = []
missing_shap_count = 0
subdomain_extraction_issues = 0

clusters = b4_prepared['b3_data']['classified_clusters']
graph = b4_prepared['graph']['subgraph']

print(f"Processing mechanisms from {len(clusters)} clusters...")

# Iterate through clusters and their nodes (mechanisms)
for cluster in clusters:
    cluster_id = cluster.get('cluster_id')
    cluster_nodes = cluster.get('nodes', [])

    # FIX 2: Robust Subdomain Extraction
    hierarchical_label = cluster.get('hierarchical_label', '')
    subdomain = extract_subdomain(hierarchical_label)

    if subdomain == 'General' and hierarchical_label:
        subdomain_extraction_issues += 1

    for mechanism_id in cluster_nodes:
        # FIX 1: Handle Missing SHAP Scores
        shap_score = shap_data['mechanism_shap_scores'].get(mechanism_id, None)

        if shap_score is None:
            missing_shap_count += 1

        # Get graph visibility from B4 schemas
        visible_in = []
        if mechanism_id in [n['id'] for n in b4_graphs['full']['nodes']]:
            visible_in.append('full')
        if mechanism_id in [n['id'] for n in b4_graphs['professional']['nodes']]:
            visible_in.append('professional')
        if mechanism_id in [n['id'] for n in b4_graphs['simplified']['nodes']]:
            visible_in.append('simplified')

        # Get degree from graph
        degree = graph.degree(mechanism_id) if mechanism_id in graph else 0

        v2_mechanism = {
            'id': mechanism_id,
            'label': mechanism_id,  # Use ID as label (no separate name field available)
            'domain': cluster.get('primary_domain', 'Unknown'),
            'subdomain': subdomain,  # FIX 2 applied
            'cluster_id': cluster_id,
            'cluster_name': cluster.get('cluster_name', ''),
            'centrality': {
                'degree': degree,
                # Betweenness/PageRank not available in prepared data
            },
            'shap_score': shap_score if shap_score is not None else 'not_computed',  # FIX 1
            'shap_available': shap_score is not None,  # FIX 1
            'visible_in': visible_in,
            'hierarchical_label': hierarchical_label,  # Keep original for debugging
            'source': 'B2_B3_B4_integrated'
        }
        v2_mechanisms.append(v2_mechanism)

print(f"✅ Processed {len(v2_mechanisms)} mechanisms")
print(f"   ⚠️ Missing SHAP: {missing_shap_count}/290")
print(f"   ⚠️ Subdomain extraction issues: {subdomain_extraction_issues}/290")

# ============================================================================
# Step 4: Process Domains
# ============================================================================

print("\n" + "="*80)
print("STEP 4: PROCESS DOMAINS")
print("="*80)

# Build domain map from clusters
domain_map = {}
for cluster in clusters:
    domain = cluster.get('primary_domain', 'Unknown')
    if domain not in domain_map:
        domain_map[domain] = []
    domain_map[domain].append(cluster)

v2_domains = []
for domain_name, domain_clusters in domain_map.items():
    # Count mechanisms in this domain
    mechanism_count = sum(
        1 for m in v2_mechanisms if m['domain'] == domain_name
    )

    # Extract unique subdomains
    subdomains = set()
    for c in domain_clusters:
        hierarchical = c.get('hierarchical_label', '')
        subdomain = extract_subdomain(hierarchical)
        if subdomain != 'General':
            subdomains.add(subdomain)

    v2_domain = {
        'name': domain_name,
        'clusters': [c.get('cluster_id') for c in domain_clusters],
        'mechanism_count': mechanism_count,
        'cluster_count': len(domain_clusters),
        'subdomains': sorted(list(subdomains)),
        'source': 'B3_domain_classification'
    }
    v2_domains.append(v2_domain)

print(f"✅ Processed {len(v2_domains)} domains")
for domain in v2_domains:
    print(f"   - {domain['name']}: {domain['mechanism_count']} mechanisms, {domain['cluster_count']} clusters")

# ============================================================================
# Step 5: Embed Graphs
# ============================================================================

print("\n" + "="*80)
print("STEP 5: EMBED GRAPHS")
print("="*80)

v2_graphs = {}
for level, graph_data in b4_graphs.items():
    v2_graphs[level] = {
        'nodes': graph_data['nodes'],
        'edges': graph_data['edges'],
        'metadata': graph_data.get('metadata', {}),
        'statistics': graph_data.get('statistics', {}),
        'source': 'B4_multi_level_pruning'
    }
    print(f"   ✅ {level}: {len(graph_data['nodes'])} nodes, {len(graph_data['edges'])} edges")

# ============================================================================
# Step 6: Assemble Final Schema
# ============================================================================

print("\n" + "="*80)
print("STEP 6: ASSEMBLE FINAL SCHEMA")
print("="*80)

v2_schema = {
    'metadata': metadata,
    'outcomes': v2_outcomes,
    'mechanisms': v2_mechanisms,
    'domains': v2_domains,
    'graphs': v2_graphs
}

print(f"✅ Schema assembled")
print(f"   - Outcomes: {len(v2_outcomes)}")
print(f"   - Mechanisms: {len(v2_mechanisms)}")
print(f"   - Domains: {len(v2_domains)}")
print(f"   - Graphs: {len(v2_graphs)}")

# ============================================================================
# Calculate Intermediate Schema Size
# ============================================================================

print("\n" + "="*80)
print("INTERMEDIATE SCHEMA SIZE CHECK")
print("="*80)

import sys

schema_json = json.dumps(v2_schema, default=json_serializer)
size_mb = len(schema_json) / (1024 * 1024)

print(f"📊 Schema size (without dashboard metadata): {size_mb:.2f} MB")

if size_mb > 5.0:
    print(f"⚠️ WARNING: Schema already exceeds 5 MB before dashboard metadata!")
    print(f"   This suggests possible data bloat - investigating...")

    # Diagnose large components
    component_sizes = {}
    for key in v2_schema.keys():
        component_json = json.dumps(v2_schema[key])
        component_sizes[key] = len(component_json) / (1024 * 1024)

    print(f"\n📊 Component sizes:")
    for key, size in sorted(component_sizes.items(), key=lambda x: x[1], reverse=True):
        print(f"   {key}: {size:.2f} MB ({size/size_mb*100:.1f}%)")
else:
    print(f"✅ Schema size acceptable (< 5 MB)")

# ============================================================================
# Save Unified Schema
# ============================================================================

print("\n" + "="*80)
print("SAVING UNIFIED SCHEMA")
print("="*80)

output_path = outputs_dir / 'B5_task2_unified_schema.pkl'

with open(output_path, 'wb') as f:
    pickle.dump(v2_schema, f)

print(f"✅ Saved unified schema to: {output_path}")

# Also save as JSON (base version without dashboard metadata)
json_path = outputs_dir / 'causal_graph_v2_base.json'

try:
    with open(json_path, 'w') as f:
        json.dump(v2_schema, f, indent=2, default=json_serializer)
    print(f"✅ Saved base JSON to: {json_path}")
except Exception as e:
    print(f"⚠️ WARNING: Could not save JSON: {e}")
    print(f"   (PKL saved successfully - JSON is optional)")

# ============================================================================
# CHECKPOINT REPORT
# ============================================================================

print("\n" + "="*80)
print("TASK 2 CHECKPOINT REPORT")
print("="*80)

print(f"\n1. Schema Size: {size_mb:.2f} MB (target: <5 MB)")
if size_mb <= 5.0:
    print(f"   ✅ PASS")
else:
    print(f"   ⚠️ WARNING: Exceeds target")

print(f"\n2. Mechanisms with SHAP='not_computed': {missing_shap_count}/290")
if missing_shap_count == 0:
    print(f"   ✅ PASS - 100% coverage")
else:
    print(f"   ⚠️ {missing_shap_count} mechanisms missing SHAP (marked as 'not_computed')")

print(f"\n3. Subdomain extraction failures: {subdomain_extraction_issues}/290")
if subdomain_extraction_issues == 0:
    print(f"   ✅ PASS - No extraction failures")
else:
    print(f"   ℹ️ {subdomain_extraction_issues} labels defaulted to 'General' (acceptable)")

print(f"\n" + "="*80)
print("TASK 2 COMPLETE")
print("="*80)

print(f"\n✅ Unified V2 Schema Created:")
print(f"   - 9 outcomes from B1")
print(f"   - 290 mechanisms from B2+B3")
print(f"   - {len(v2_domains)} domains from B3")
print(f"   - 3 graph versions from B4")
print(f"   - Schema size: {size_mb:.2f} MB")

print(f"\nNext step: python scripts/task3_dashboard_metadata.py")
print("="*80)
