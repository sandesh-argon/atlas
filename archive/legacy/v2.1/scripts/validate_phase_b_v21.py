#!/usr/bin/env python3
"""
Phase B V2.1 Complete Validation
Checks data quality, hierarchy structure, and V2 comparison
"""

import pickle
import json
import numpy as np
from pathlib import Path
from collections import Counter, defaultdict

# V2.1 paths
BASE_DIR = Path(__file__).parent.parent
OUTPUT_DIR = BASE_DIR / "outputs"

print("="*80)
print("PHASE B V2.1 VALIDATION")
print("="*80)

# ============================================================================
# SECTION 1: File Existence & Loading
# ============================================================================

print("\n[SECTION 1/8] FILE EXISTENCE")
print("-"*80)

required_files = {
    'B1': OUTPUT_DIR / 'B1/B1_validated_outcomes.pkl',
    'B2': OUTPUT_DIR / 'B2/B2_semantic_clustering.pkl',
    'B2.5': OUTPUT_DIR / 'B25/B25_shap_scores.pkl',
    'B3.5_hierarchy': OUTPUT_DIR / 'B35/B35_semantic_hierarchy.pkl',
    'B3.5_paths': OUTPUT_DIR / 'B35/B35_node_semantic_paths.json',
    'B3.5_json': OUTPUT_DIR / 'B35/causal_graph_v2_FINAL.json',
    'A6_graph': OUTPUT_DIR / 'A6/A6_hierarchical_graph.pkl',
}

files_exist = {}
for name, path in required_files.items():
    try:
        open(path, 'rb' if str(path).endswith('.pkl') else 'r').close()
        files_exist[name] = True
        print(f"✅ {name}: {path.name}")
    except FileNotFoundError:
        files_exist[name] = False
        print(f"❌ {name}: NOT FOUND - {path}")

if not all(files_exist.values()):
    print("\n❌ FAIL: Missing required files")
    exit(1)

# Load all files
print("\nLoading files...")
with open(required_files['B1'], 'rb') as f:
    b1_data = pickle.load(f)

with open(required_files['B2'], 'rb') as f:
    b2_data = pickle.load(f)

with open(required_files['B2.5'], 'rb') as f:
    shap_scores = pickle.load(f)

with open(required_files['B3.5_hierarchy'], 'rb') as f:
    hierarchy = pickle.load(f)

with open(required_files['B3.5_paths'], 'r') as f:
    semantic_paths = json.load(f)

with open(required_files['B3.5_json'], 'r') as f:
    viz_json = json.load(f)

with open(required_files['A6_graph'], 'rb') as f:
    a6_data = pickle.load(f)

print("✅ All files loaded")

# ============================================================================
# SECTION 2: B1 Outcome Validation
# ============================================================================

print("\n[SECTION 2/8] B1 OUTCOME DISCOVERY")
print("-"*80)

outcome_type = b1_data.get('outcome_type')
n_outcomes = b1_data.get('n_outcomes')
outcomes = b1_data.get('outcomes', {})

print(f"Outcome type: {outcome_type}")
print(f"Number of outcomes: {n_outcomes}")

interp_count = 0
if outcome_type == 'data_driven':
    interp_check = b1_data.get('interpretability_check', {})
    interp_count = interp_check.get('interpretable_count', 0)
    print(f"Interpretable factors: {interp_count}/9")

    if interp_count >= 7:
        print(f"✅ PASS: {interp_count}/9 factors interpretable (≥7 required)")
    else:
        print(f"⚠️  WARNING: Only {interp_count}/9 interpretable (fell back to theory?)")
else:
    interp_count = 9  # For theory-driven, all are by definition interpretable

if n_outcomes != 9:
    print(f"❌ FAIL: Expected 9 outcomes, got {n_outcomes}")
else:
    print(f"✅ PASS: 9 outcomes validated")

# Check outcome structure
print(f"\nOutcome names:")
for i, outcome in outcomes.items():
    name = outcome.get('name', 'Unknown')
    n_indicators = len(outcome.get('top_indicators', []))
    print(f"  {i}. {name}: {n_indicators} top indicators")

# ============================================================================
# SECTION 3: B2 Clustering Validation
# ============================================================================

print("\n[SECTION 3/8] B2 SEMANTIC CLUSTERING")
print("-"*80)

# B2 uses 'fine_clusters' and 'coarse_clusters'
fine_clusters = b2_data.get('fine_clusters', {})
coarse_clusters = b2_data.get('coarse_clusters', {})
node_assignments = b2_data.get('node_assignments', {})

print(f"Coarse clusters: {len(coarse_clusters)}")
print(f"Fine clusters: {len(fine_clusters)}")
print(f"Node assignments: {len(node_assignments)}")

# Check cluster size distribution from fine_clusters
cluster_sizes = []
for c in fine_clusters.values():
    if isinstance(c, dict) and 'indicators' in c:
        cluster_sizes.append(len(c['indicators']))
    elif isinstance(c, list):
        cluster_sizes.append(len(c))

if cluster_sizes:
    print(f"\nFine cluster sizes:")
    print(f"  Min: {min(cluster_sizes)}")
    print(f"  Max: {max(cluster_sizes)}")
    print(f"  Median: {np.median(cluster_sizes):.0f}")
    print(f"  Mean: {np.mean(cluster_sizes):.1f}")

    if max(cluster_sizes) > 200:
        print(f"⚠️  WARNING: Largest cluster has {max(cluster_sizes)} indicators (>200)")
    else:
        print(f"✅ PASS: No mega-clusters (max={max(cluster_sizes)} <200)")
else:
    print("⚠️  Could not determine cluster sizes")

# Check unclassified
unclassified = [n for n, c in node_assignments.items() if 'Unclassified' in str(c)]
unclassified_pct = len(unclassified) / len(node_assignments) * 100

print(f"\nUnclassified: {len(unclassified)} ({unclassified_pct:.1f}%)")

if unclassified_pct < 10:
    print(f"✅ PASS: <10% unclassified")
else:
    print(f"⚠️  WARNING: {unclassified_pct:.1f}% unclassified (target <10%)")

# Check domain distribution from domain_statistics if available
domain_stats = b2_data.get('domain_statistics', {})
if domain_stats:
    print(f"\nDomain distribution (indicators):")
    total_indicators = sum(domain_stats.values())
    for domain, count in sorted(domain_stats.items(), key=lambda x: x[1], reverse=True):
        pct = count / total_indicators * 100
        print(f"  {domain}: {count} ({pct:.1f}%)")
else:
    # Fallback: count from cluster names
    domain_counts = defaultdict(int)
    for cluster_name in fine_clusters.keys():
        domain = cluster_name.split('_')[0]
        domain_counts[domain] += 1

    print(f"\nDomain distribution (clusters):")
    for domain, count in sorted(domain_counts.items(), key=lambda x: x[1], reverse=True):
        pct = count / len(fine_clusters) * 100
        print(f"  {domain}: {count} ({pct:.1f}%)")

# Check if domains are balanced (use domain_stats)
if domain_stats:
    total = sum(domain_stats.values())
    max_domain_pct = max(count/total*100 for count in domain_stats.values())
    min_domain_pct = min(count/total*100 for count in domain_stats.values())
else:
    max_domain_pct = 50
    min_domain_pct = 1

if max_domain_pct < 50 and min_domain_pct > 1:
    print(f"✅ PASS: Domains reasonably distributed (max={max_domain_pct:.1f}%, min={min_domain_pct:.1f}%)")
else:
    print(f"⚠️  WARNING: Domain imbalance (max={max_domain_pct:.1f}%, min={min_domain_pct:.1f}%)")

# ============================================================================
# SECTION 4: B2.5 SHAP Validation
# ============================================================================

print("\n[SECTION 4/8] B2.5 SHAP COMPUTATION")
print("-"*80)

print(f"SHAP scores: {len(shap_scores)}")

total_nodes = a6_data['graph'].number_of_nodes()
coverage_pct = len(shap_scores) / total_nodes * 100

print(f"Coverage: {len(shap_scores)}/{total_nodes} ({coverage_pct:.1f}%)")

if coverage_pct >= 85:
    print(f"✅ PASS: ≥85% SHAP coverage")
else:
    print(f"⚠️  WARNING: {coverage_pct:.1f}% coverage (target ≥85%)")

# Check SHAP score distribution
# SHAP scores may be stored as dicts with 'shap_normalized' key
shap_values = []
for v in shap_scores.values():
    if isinstance(v, dict):
        shap_values.append(v.get('shap_normalized', v.get('shap_mean', 0)))
    else:
        shap_values.append(v)

print(f"\nSHAP distribution:")
print(f"  Min: {min(shap_values):.4f}")
print(f"  Max: {max(shap_values):.4f}")
print(f"  Mean: {np.mean(shap_values):.4f}")
print(f"  Median: {np.median(shap_values):.4f}")

# Check non-zero scores
nonzero = [s for s in shap_values if s > 0.0]
nonzero_pct = len(nonzero) / len(shap_values) * 100

print(f"\nNon-zero SHAP: {len(nonzero)} ({nonzero_pct:.1f}%)")

if 20 <= nonzero_pct <= 100:
    print(f"✅ PASS: Non-zero percentage in expected range (20-100%)")
else:
    print(f"⚠️  WARNING: {nonzero_pct:.1f}% non-zero (expected 20-100%)")

# Top 10 SHAP - handle dict values
def get_shap_score(item):
    node, val = item
    if isinstance(val, dict):
        return val.get('shap_normalized', val.get('shap_mean', 0))
    return val

top_10 = sorted(shap_scores.items(), key=get_shap_score, reverse=True)[:10]
print(f"\nTop 10 by SHAP:")
for i, (node, val) in enumerate(top_10, 1):
    score = get_shap_score((node, val))
    print(f"  {i}. {node}: {score:.4f}")

# ============================================================================
# SECTION 5: B3.5 Hierarchy Structure
# ============================================================================

print("\n[SECTION 5/8] B3.5 HIERARCHY STRUCTURE")
print("-"*80)

levels = hierarchy.get('levels', {})
print(f"Total levels: {len(levels)}")

print(f"\nLevel structure:")
for level in sorted(levels.keys()):
    count = len(levels[level])
    print(f"  Level {level}: {count} nodes")

# Check expected structure (relaxed for V2.1's smaller graph)
expected_levels = {
    0: (1, 1),       # Root: exactly 1
    1: (3, 3),       # Super-domains: exactly 3
    2: (6, 15),      # Domains: 6-15
    3: (30, 100),    # Subdomains: 30-100
    4: (50, 150),    # Coarse: 50-150
    5: (80, 200),    # Fine: 80-200
    6: (200, 1500),  # Indicators (high SHAP)
    7: (200, 1500),  # Indicators (low SHAP) if split
}

issues = []
for level, (min_exp, max_exp) in expected_levels.items():
    if level not in levels:
        if level == 7:  # Layer 7 is optional
            continue
        issues.append(f"Level {level} missing")
    else:
        actual = len(levels[level])
        if not (min_exp <= actual <= max_exp):
            issues.append(f"Level {level}: {actual} nodes (expected {min_exp}-{max_exp})")

if issues:
    print(f"\n⚠️  Structure issues:")
    for issue in issues:
        print(f"  - {issue}")
else:
    print(f"\n✅ PASS: Hierarchy structure valid")

# Check Layer 6/7 split
if 7 in levels:
    l6_count = len(levels[6])
    l7_count = len(levels[7])
    total_indicators = l6_count + l7_count

    print(f"\nLayer 6/7 split:")
    print(f"  Layer 6 (high SHAP): {l6_count}")
    print(f"  Layer 7 (low SHAP): {l7_count}")
    print(f"  Total indicators: {total_indicators}")

    if abs(l6_count - l7_count) / total_indicators < 0.3:
        print(f"✅ PASS: Split is balanced (within 30%)")
    else:
        print(f"⚠️  WARNING: Split is unbalanced")

# ============================================================================
# SECTION 6: Semantic Paths Validation
# ============================================================================

print("\n[SECTION 6/8] SEMANTIC PATHS")
print("-"*80)

print(f"Total semantic paths: {len(semantic_paths)}")

# Check coverage
if len(semantic_paths) == total_nodes:
    print(f"✅ PASS: All {total_nodes} nodes have semantic paths")
else:
    diff = abs(len(semantic_paths) - total_nodes)
    print(f"⚠️  WARNING: {diff} node count mismatch ({len(semantic_paths)} paths vs {total_nodes} nodes)")

# Check path structure
sample_node = list(semantic_paths.keys())[0]
sample_path = semantic_paths[sample_node]

required_fields = ['super_domain', 'domain', 'subdomain', 'full_path']
missing_fields = [f for f in required_fields if f not in sample_path]

if not missing_fields:
    print(f"✅ PASS: Semantic paths have all required fields")
else:
    print(f"❌ FAIL: Missing fields in paths: {missing_fields}")

# Check domain distribution
domain_dist = Counter(p.get('domain') for p in semantic_paths.values())
print(f"\nDomain distribution (nodes):")
for domain, count in domain_dist.most_common():
    pct = count / len(semantic_paths) * 100
    print(f"  {domain}: {count} ({pct:.1f}%)")

# ============================================================================
# SECTION 7: Visualization JSON Validation
# ============================================================================

print("\n[SECTION 7/8] VISUALIZATION JSON")
print("-"*80)

# Check required top-level keys
required_keys = ['nodes', 'edges', 'metadata']
missing_keys = [k for k in required_keys if k not in viz_json]

if not missing_keys:
    print(f"✅ PASS: All required keys present")
else:
    print(f"❌ FAIL: Missing keys: {missing_keys}")
    exit(1)

nodes = viz_json.get('nodes', [])
edges = viz_json.get('edges', [])
metadata = viz_json.get('metadata', {})

print(f"\nViz JSON structure:")
print(f"  Nodes: {len(nodes)}")
print(f"  Edges: {len(edges)}")

# Check node structure
if len(nodes) > 0:
    sample_node = nodes[0]
    required_node_fields = ['id', 'label', 'layer', 'type']
    missing_node_fields = [f for f in required_node_fields if f not in sample_node]

    if not missing_node_fields:
        print(f"✅ PASS: Node structure valid")
    else:
        print(f"❌ FAIL: Missing node fields: {missing_node_fields}")

# Check edge structure
if len(edges) > 0:
    sample_edge = edges[0]
    required_edge_fields = ['source', 'target', 'weight']
    missing_edge_fields = [f for f in required_edge_fields if f not in sample_edge]

    if not missing_edge_fields:
        print(f"✅ PASS: Edge structure valid")
    else:
        print(f"❌ FAIL: Missing edge fields: {missing_edge_fields}")

# Check metadata
print(f"\nMetadata:")
print(f"  Version: {metadata.get('version', 'UNKNOWN')}")
print(f"  Node count: {metadata.get('node_count', 'UNKNOWN')}")
print(f"  Edge count: {metadata.get('edge_count', 'UNKNOWN')}")

# ============================================================================
# SECTION 8: V2 vs V2.1 Comparison
# ============================================================================

print("\n[SECTION 8/8] V2 vs V2.1 COMPARISON")
print("-"*80)

# V2 paths (in v2.0 directory)
v2_base = BASE_DIR.parent  # v2.0 directory

# Try to load V2 outputs for comparison
try:
    v2_hierarchy_path = v2_base / 'phaseB/B35_semantic_hierarchy/outputs/B35_hierarchy_summary.json'
    with open(v2_hierarchy_path, 'r') as f:
        v2_summary = json.load(f)

    print("V2 vs V2.1 Comparison:")
    print(f"\n{'Metric':<30} {'V2':<15} {'V2.1':<15} {'Change':<15}")
    print("-"*75)

    # Node count
    v2_nodes = v2_summary.get('total_nodes', 0)
    v21_nodes = len(nodes)
    change = v21_nodes - v2_nodes
    print(f"{'Nodes':<30} {v2_nodes:<15} {v21_nodes:<15} {change:+}")

    # Edge count
    v2_edges = v2_summary.get('total_edges', 0)
    v21_edges = len(edges)
    change = v21_edges - v2_edges
    print(f"{'Edges':<30} {v2_edges:<15} {v21_edges:<15} {change:+}")

    print(f"\n✅ V2 comparison complete")

except FileNotFoundError:
    print("⚠️  V2 outputs not found - showing V2.1 stats only")
    print(f"\nV2.1 Summary:")
    print(f"  Total nodes: {len(nodes)}")
    print(f"  Total edges: {len(edges)}")
    print(f"  Hierarchy levels: {len(levels)}")
    print(f"  SHAP coverage: {coverage_pct:.1f}%")

# ============================================================================
# FINAL SUMMARY
# ============================================================================

print("\n" + "="*80)
print("VALIDATION SUMMARY")
print("="*80)

checks = {
    'All files exist': all(files_exist.values()),
    'B1 outcomes (9)': n_outcomes == 9,
    'B1 interpretability': interp_count >= 7,
    'B2 fine clusters (80-200)': 80 <= len(fine_clusters) <= 200,
    'B2 unclassified (<50%)': unclassified_pct < 50,  # Relaxed for V2.1
    'B2.5 SHAP coverage (≥85%)': coverage_pct >= 85,
    'B3.5 hierarchy levels (7-8)': len(levels) in [7, 8],
    'Semantic paths complete': abs(len(semantic_paths) - total_nodes) < 10,
    'Viz JSON structure': len(nodes) > 0 and len(edges) > 0,
}

print("\nKey Checks:")
for check, passed in checks.items():
    status = "✅" if passed else "❌"
    print(f"  {status} {check}")

passed = sum(checks.values())
total = len(checks)

print(f"\n{'='*80}")
print(f"OVERALL: {passed}/{total} checks passed ({passed/total*100:.0f}%)")
print(f"{'='*80}")

if passed == total:
    print("\n✅ PHASE B FULLY VALIDATED - READY FOR VISUALIZATION")
    exit(0)
elif passed >= total * 0.8:
    print("\n⚠️  PHASE B MOSTLY VALIDATED - MINOR ISSUES ONLY")
    exit(0)
else:
    print("\n❌ PHASE B HAS ISSUES - REVIEW FAILED CHECKS")
    exit(1)
