#!/usr/bin/env python3
"""
Comprehensive validation before B3.5 semantic hierarchy construction
Validates A5→A6→B2 pipeline after interaction node removal
"""

import pickle
import json
import numpy as np
import networkx as nx
from pathlib import Path
from collections import defaultdict, Counter
import random

# Project paths
project_root = Path(__file__).resolve().parents[3]

print("="*80)
print("PRE-B3.5 VALIDATION SUITE")
print("="*80)

# ============================================================================
# LOAD DATA
# ============================================================================

print("\n[1/10] Loading data...")

# A5 interactions (reprocessed)
a5_path = project_root / 'phaseA/A5_interaction_discovery/outputs/A5_interaction_results_FILTERED_STRICT.pkl'
with open(a5_path, 'rb') as f:
    a5_data = pickle.load(f)

# A6 graph (reprocessed without interaction nodes)
a6_path = project_root / 'phaseA/A6_hierarchical_layering/outputs/A6_hierarchical_graph.pkl'
with open(a6_path, 'rb') as f:
    a6_data = pickle.load(f)

# B2 clustering (reprocessed)
b2_path = project_root / 'phaseB/B2_mechanism_identification/outputs/B2_semantic_clustering.pkl'
with open(b2_path, 'rb') as f:
    b2_data = pickle.load(f)

G = a6_data['graph']
layers = a6_data['layers']
node_assignments = b2_data['node_assignments']
clusters = b2_data['fine_clusters']  # Use fine_clusters from B2

print(f"✓ Loaded: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
print(f"✓ B2 clusters: {len(clusters)}")

# ============================================================================
# VALIDATION 1: NO INTERACTION NODES IN GRAPH
# ============================================================================

print("\n[2/10] Checking for interaction nodes...")

# Check for both patterns: _x_ and INTERACT_
interaction_nodes = [n for n in G.nodes() if '_x_' in str(n).lower() or 'INTERACT_' in str(n)]

if len(interaction_nodes) > 0:
    print(f"❌ FAIL: Found {len(interaction_nodes)} interaction nodes still in graph")
    print(f"   Examples: {interaction_nodes[:5]}")
    print(f"   These should be edge metadata, not nodes")
else:
    print(f"✅ PASS: No interaction nodes in graph (correct)")

# ============================================================================
# VALIDATION 2: INTERACTION METADATA ON EDGES
# ============================================================================

print("\n[3/10] Checking interaction metadata on edges...")

edges_with_moderators = [
    (s, t) for s, t in G.edges()
    if 'moderators' in G.edges[s, t] and len(G.edges[s, t]['moderators']) > 0
]

total_moderators = sum(len(G.edges[s, t]['moderators']) for s, t in edges_with_moderators)

print(f"   Edges with moderators: {len(edges_with_moderators)}")
print(f"   Total moderator relationships: {total_moderators}")

# Expected: Should match A5 interaction count
a5_interaction_count = len(a5_data.get('validated_interactions', []))
print(f"   A5 interactions discovered: {a5_interaction_count}")

if abs(total_moderators - a5_interaction_count) > 100:  # Allow 100 discrepancy
    print(f"⚠️  WARNING: Moderator count mismatch")
    print(f"   A5 discovered: {a5_interaction_count}")
    print(f"   A6 encoded: {total_moderators}")
    print(f"   Difference: {abs(total_moderators - a5_interaction_count)}")
else:
    print(f"✅ PASS: Moderator count matches A5 interactions (±100)")

# Sample check
sample_edge = edges_with_moderators[0] if edges_with_moderators else None
if sample_edge:
    print(f"\n   Sample edge with moderators:")
    s, t = sample_edge
    print(f"   {s} → {t}")
    for mod in G.edges[s, t]['moderators'][:3]:
        print(f"     Moderated by: {mod.get('moderator_variable', 'unknown')}")
        print(f"     Interaction beta: {mod.get('beta_interaction', 0.0):.4f}")

# ============================================================================
# VALIDATION 3: NODE COUNT REDUCTION
# ============================================================================

print("\n[4/10] Checking node count reduction...")

# Expected: ~3,872 nodes (after removing 4,254 interaction nodes from 8,126)
expected_min = 3500
expected_max = 4500

node_count = G.number_of_nodes()

if expected_min <= node_count <= expected_max:
    print(f"✅ PASS: Node count in expected range")
    print(f"   Actual: {node_count}")
    print(f"   Expected: {expected_min}-{expected_max}")
else:
    print(f"⚠️  WARNING: Node count outside expected range")
    print(f"   Actual: {node_count}")
    print(f"   Expected: {expected_min}-{expected_max}")

# ============================================================================
# VALIDATION 4: B2 CLUSTER COVERAGE
# ============================================================================

print("\n[5/10] Validating B2 cluster coverage...")

# All nodes should be assigned to clusters
nodes_in_graph = set(G.nodes())
nodes_in_b2 = set(node_assignments.keys())

missing_in_b2 = nodes_in_graph - nodes_in_b2
extra_in_b2 = nodes_in_b2 - nodes_in_graph

if len(missing_in_b2) > 0:
    print(f"❌ FAIL: {len(missing_in_b2)} nodes in graph but not in B2")
    print(f"   Examples: {list(missing_in_b2)[:5]}")
elif len(extra_in_b2) > 0:
    print(f"⚠️  WARNING: {len(extra_in_b2)} nodes in B2 but not in graph (stale references)")
    print(f"   Examples: {list(extra_in_b2)[:5]}")
else:
    print(f"✅ PASS: Perfect B2 coverage ({len(nodes_in_b2)} nodes)")

# Check for unclassified
unclassified = [n for n, c in node_assignments.items() if 'Unclassified' in c]
unclassified_pct = len(unclassified) / len(node_assignments) * 100

print(f"   Unclassified nodes: {len(unclassified)} ({unclassified_pct:.1f}%)")

if unclassified_pct > 10:
    print(f"⚠️  WARNING: >10% unclassified nodes")
else:
    print(f"✅ PASS: <10% unclassified")

# ============================================================================
# VALIDATION 5: B2 CLUSTER SIZE DISTRIBUTION
# ============================================================================

print("\n[6/10] Validating B2 cluster sizes...")

cluster_sizes = [len(c['indicators']) for c in clusters.values()]

stats = {
    'min': int(np.min(cluster_sizes)),
    'max': int(np.max(cluster_sizes)),
    'median': float(np.median(cluster_sizes)),
    'mean': float(np.mean(cluster_sizes)),
    'std': float(np.std(cluster_sizes))
}

print(f"   Cluster size statistics:")
print(f"     Min: {stats['min']}")
print(f"     Max: {stats['max']}")
print(f"     Median: {stats['median']:.1f}")
print(f"     Mean: {stats['mean']:.1f}")
print(f"     Std dev: {stats['std']:.1f}")

# Check for mega-clusters (>500 nodes)
mega_clusters = [(name, c) for name, c in clusters.items() if len(c['indicators']) > 500]

if len(mega_clusters) > 0:
    print(f"\n⚠️  WARNING: {len(mega_clusters)} mega-clusters (>500 nodes)")
    for name, c in mega_clusters:
        print(f"     {name}: {len(c['indicators'])} nodes")
    print(f"   These may need sub-clustering in B3.5")
else:
    print(f"✅ PASS: No mega-clusters (all <500 nodes)")

# Check median cluster size
if 5 <= stats['median'] <= 100:
    print(f"✅ PASS: Median cluster size in target range (5-100)")
else:
    print(f"⚠️  WARNING: Median cluster size outside target (5-100)")

# ============================================================================
# VALIDATION 6: DOMAIN DISTRIBUTION
# ============================================================================

print("\n[7/10] Validating domain distribution...")

domain_counts = defaultdict(int)
for cluster_name in clusters.keys():
    # Extract domain from cluster name (e.g., "Governance_Judicial_0" -> "Governance")
    parts = cluster_name.split('_')
    domain = parts[0] if parts else 'Unknown'
    domain_counts[domain] += 1

print(f"   Clusters per domain:")
for domain, count in sorted(domain_counts.items(), key=lambda x: x[1], reverse=True):
    pct = count / len(clusters) * 100
    print(f"     {domain}: {count} ({pct:.1f}%)")

# Check governance dominance
gov_pct = domain_counts.get('Governance', 0) / len(clusters) * 100

if gov_pct > 50:
    print(f"\n⚠️  WARNING: Governance >50% of clusters ({gov_pct:.1f}%)")
    print(f"   This is expected given V-Dem dataset dominance")
elif gov_pct < 20:
    print(f"\n⚠️  WARNING: Governance <20% of clusters ({gov_pct:.1f}%)")
    print(f"   This seems too low - check keyword patterns")
else:
    print(f"\n✅ PASS: Governance in reasonable range (20-50%)")

# ============================================================================
# VALIDATION 7: CLUSTER SEMANTIC COHERENCE (SAMPLE CHECK)
# ============================================================================

print("\n[8/10] Checking cluster semantic coherence (sample)...")

# Sample 5 random clusters, inspect their contents
sample_clusters = random.sample(list(clusters.keys()), min(5, len(clusters)))

coherence_issues = []

for cluster_name in sample_clusters:
    cluster_data = clusters[cluster_name]
    indicators = cluster_data['indicators'][:5]  # First 5

    print(f"\n   {cluster_name} ({len(cluster_data['indicators'])} nodes):")

    labels = []
    for ind in indicators:
        # Use indicator ID as label
        label = str(ind)
        print(f"     - {ind}")
        labels.append(label.lower())

    # Simple coherence check: Do all labels share common keywords?
    # Extract words from cluster name
    cluster_keywords = [k.lower() for k in cluster_name.split('_') if len(k) > 2]

    matches = sum(
        any(keyword in label for keyword in cluster_keywords)
        for label in labels
    )

    coherence_score = matches / len(labels) if labels else 0

    if coherence_score < 0.3:  # <30% match
        coherence_issues.append(cluster_name)
        print(f"     ⚠️  Low coherence: {coherence_score:.1%}")

if len(coherence_issues) > 0:
    print(f"\n⚠️  WARNING: {len(coherence_issues)}/5 sampled clusters have low coherence")
    print(f"   This may indicate keyword pattern issues")
else:
    print(f"\n✅ PASS: All sampled clusters show reasonable coherence")

# ============================================================================
# VALIDATION 8: DAG STRUCTURE (NO CYCLES)
# ============================================================================

print("\n[9/10] Validating DAG structure...")

cycles = []
try:
    # Use is_directed_acyclic_graph for efficiency
    is_dag = nx.is_directed_acyclic_graph(G)

    if not is_dag:
        cycles = list(nx.simple_cycles(G))
        print(f"❌ FAIL: Found {len(cycles)} cycles in graph")
        if cycles:
            print(f"   Example cycle: {cycles[0]}")
    else:
        print(f"✅ PASS: Graph is a valid DAG (no cycles)")
except Exception as e:
    print(f"⚠️  WARNING: Could not check cycles: {e}")

# Check topological ordering
try:
    topo_order = list(nx.topological_sort(G))
    print(f"✅ PASS: Topological sort succeeded ({len(topo_order)} nodes)")
except nx.NetworkXError as e:
    print(f"❌ FAIL: Cannot perform topological sort (graph has cycles)")

# ============================================================================
# VALIDATION 9: LAYER DISTRIBUTION
# ============================================================================

print("\n[10/10] Validating layer distribution...")

layer_counts = Counter(layers.values())

print(f"   Nodes per causal layer:")
for layer in sorted(layer_counts.keys()):
    count = layer_counts[layer]
    pct = count / len(layers) * 100
    bar = '█' * int(pct / 2)  # Visual bar
    print(f"     Layer {layer:2d}: {count:4d} nodes ({pct:5.1f}%) {bar}")

# Check for reasonable distribution
max_layer = max(layers.values())
min_layer = min(layers.values())

if max_layer > 25:
    print(f"\n⚠️  WARNING: Max layer {max_layer} > 25 (very deep causal chain)")
elif max_layer < 10:
    print(f"\n⚠️  WARNING: Max layer {max_layer} < 10 (shallow causal chain)")
else:
    print(f"\n✅ PASS: Causal chain depth reasonable ({min_layer}-{max_layer} layers)")

# ============================================================================
# SUMMARY REPORT
# ============================================================================

print("\n" + "="*80)
print("VALIDATION SUMMARY")
print("="*80)

validations = {
    'No interaction nodes': len(interaction_nodes) == 0,
    'Moderator metadata present': len(edges_with_moderators) > 0,
    'Node count in range': expected_min <= node_count <= expected_max,
    'B2 coverage complete': len(missing_in_b2) == 0,
    'Unclassified <10%': unclassified_pct < 10,
    'No mega-clusters': len(mega_clusters) == 0,
    'Governance % reasonable': 20 <= gov_pct <= 50,
    'DAG structure valid': len(cycles) == 0,
    'Layer depth reasonable': 10 <= max_layer <= 25
}

passed = sum(validations.values())
total = len(validations)

print(f"\nPassed: {passed}/{total} checks ({passed/total*100:.0f}%)")
print()

for check, result in validations.items():
    status = "✅" if result else "❌"
    print(f"{status} {check}")

# Critical failures
critical_failures = [
    check for check, result in validations.items()
    if not result and check in [
        'No interaction nodes',
        'B2 coverage complete',
        'DAG structure valid'
    ]
]

if critical_failures:
    print("\n" + "="*80)
    print("❌ CRITICAL FAILURES - DO NOT PROCEED TO B3.5")
    print("="*80)
    for failure in critical_failures:
        print(f"  - {failure}")
    print("\nFix these issues before running B3.5")
else:
    print("\n" + "="*80)
    print("✅ READY FOR B3.5 SEMANTIC HIERARCHY CONSTRUCTION")
    print("="*80)

    # Provide B3.5 input summary
    print(f"\nB3.5 will receive:")
    print(f"  - {node_count} real indicator nodes (no interactions)")
    print(f"  - {len(clusters)} B2 semantic clusters")
    print(f"  - {len(edges_with_moderators)} edges with moderator metadata")
    print(f"  - {total_moderators} total moderator relationships")

# ============================================================================
# EXPORT VALIDATION REPORT
# ============================================================================

report = {
    'timestamp': str(np.datetime64('now')),
    'validations': {k: bool(v) for k, v in validations.items()},
    'statistics': {
        'node_count': node_count,
        'edge_count': G.number_of_edges(),
        'cluster_count': len(clusters),
        'edges_with_moderators': len(edges_with_moderators),
        'total_moderators': total_moderators,
        'unclassified_pct': float(unclassified_pct),
        'governance_pct': float(gov_pct),
        'cluster_size_median': float(stats['median']),
        'cluster_size_max': int(stats['max']),
        'max_layer': int(max_layer)
    },
    'domain_distribution': dict(domain_counts),
    'warnings': {
        'mega_clusters': [name for name, _ in mega_clusters] if mega_clusters else [],
        'coherence_issues': coherence_issues
    },
    'critical_failures': critical_failures
}

output_path = project_root / 'phaseB/B2_mechanism_identification/outputs/PRE_B35_VALIDATION_REPORT.json'
with open(output_path, 'w') as f:
    json.dump(report, f, indent=2)

print(f"\n✅ Validation report exported to: {output_path}")
