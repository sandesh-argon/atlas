#!/usr/bin/env python3
"""
B2 Airtight Validation Checklist
=================================

Runs 8 critical validations before proceeding to B3:
1. Cluster count & size distribution
2. Domain coherence
3. Coverage (all 329 mechanisms assigned)
4. Domain distribution balance
5. Embedding quality
6. Top variables per cluster (manual inspection)
7. Centrality preservation
8. Reproducibility

Author: Phase B2 Final Validation
Date: November 2025
"""

import pickle
import json
import sys
from pathlib import Path
import pandas as pd
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.cluster import AgglomerativeClustering
from sklearn.metrics import silhouette_score, adjusted_rand_score

# Add project root to path
project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

print("="*80)
print("B2 AIRTIGHT VALIDATION CHECKLIST")
print("="*80)

# Directories
output_dir = Path(__file__).parent / "outputs"

# Load semantic clustering results
checkpoint_path = output_dir / "B2_semantic_clustering_checkpoint.pkl"
print(f"\nLoading semantic clustering checkpoint...")

with open(checkpoint_path, 'rb') as f:
    checkpoint = pickle.load(f)

final_clusters = checkpoint['clusters']
cluster_metadata = checkpoint['cluster_metadata']
embeddings = checkpoint['embeddings']
centrality_scores = checkpoint['centrality_scores']
results_metadata = checkpoint['results']

# Get original mechanism candidates from bridging checkpoint
bridging_checkpoint_path = output_dir / "B2_bridging_subgraph_checkpoint.pkl"
with open(bridging_checkpoint_path, 'rb') as f:
    bridging_checkpoint = pickle.load(f)

mechanism_candidates_bridging = bridging_checkpoint['mechanism_candidates']

print(f"✅ Loaded checkpoint:")
print(f"   Final clusters: {len(final_clusters)}")
print(f"   Mechanism candidates: {len(mechanism_candidates_bridging)}")

# Domain inference function (from script)
def infer_domain(variable_name):
    """Classify variable by domain based on name patterns"""
    name_lower = variable_name.lower()

    if any(x in name_lower for x in ['v2ju', 'v2cl', 'v2ps', 'v2ex', 'v2sm', 'v2cs', 'v2el', 'v2dl', 'v2me', 'v2sv', 'v3pe']):
        return 'Governance'
    elif any(x in name_lower for x in ['wdi_mortu', 'repr', 'health', 'mortality', 'life_exp']):
        return 'Health'
    elif any(x in name_lower for x in ['ger', 'oaep', 'nert', 'educ', 'school', 'enroll']):
        return 'Education'
    elif any(x in name_lower for x in ['gdp', 'income', 'tax', 'debt', 'trade', 'econ', 'pwt_', 'bx', 'nw']):
        return 'Economic'
    elif any(x in name_lower for x in ['birth', 'fertility', 'population', 'demog', 'br']):
        return 'Demographic'
    elif any(x in name_lower for x in ['atop_', 'e_cow_', 'alliance', 'war', 'conflict']):
        return 'International'
    elif any(x in name_lower for x in ['transfer', 'spending', 'investment', 'ygsm', 'wgsm', 'yptf', 'aptd']):
        return 'Fiscal'
    else:
        return 'Mixed'

# Initialize validation results
validation_results = {}

# ============================================================================
# VALIDATION 1: Cluster Count & Size Distribution
# ============================================================================

print("\n" + "="*80)
print("VALIDATION 1: CLUSTER COUNT & SIZE DISTRIBUTION")
print("="*80)

n_clusters = len(final_clusters)
cluster_sizes = [len(nodes) for nodes in final_clusters.values()]
min_size = min(cluster_sizes)
mean_size = np.mean(cluster_sizes)
median_size = np.median(cluster_sizes)
max_size = max(cluster_sizes)

print(f"\nCluster count: {n_clusters}")
print(f"Cluster sizes: Min={min_size}, Mean={mean_size:.1f}, Median={median_size:.1f}, Max={max_size}")

# Validate
val1_pass = True
if not (15 <= n_clusters <= 30):
    print(f"❌ Cluster count {n_clusters} outside target range (15-30)")
    val1_pass = False
else:
    print(f"✅ Cluster count: {n_clusters} (target: 15-30)")

if min_size < 10:
    print(f"❌ Smallest cluster has {min_size} nodes (<10 minimum)")
    val1_pass = False
else:
    print(f"✅ Minimum cluster size: {min_size} (target: ≥10)")

if mean_size < 10:
    print(f"❌ Mean cluster size {mean_size:.1f} too small")
    val1_pass = False
else:
    print(f"✅ Mean cluster size: {mean_size:.1f} (target: ≥10)")

if max_size > 50:
    print(f"⚠️  Largest cluster has {max_size} nodes (>50 suggests under-clustering)")
else:
    print(f"✅ Maximum cluster size: {max_size} (target: ≤50)")

validation_results['cluster_count'] = int(n_clusters)
validation_results['min_cluster_size'] = int(min_size)
validation_results['mean_cluster_size'] = float(mean_size)
validation_results['validation_1_pass'] = val1_pass

# ============================================================================
# VALIDATION 2: Domain Coherence
# ============================================================================

print("\n" + "="*80)
print("VALIDATION 2: DOMAIN COHERENCE")
print("="*80)

coherence_scores = []

print(f"\nDomain coherence per cluster:")
for cid, metadata in cluster_metadata.items():
    coherence = metadata['coherence']
    coherence_scores.append(coherence)

    primary_domain = metadata['primary_domain']
    size = metadata['size']

    if coherence < 0.60:
        print(f"⚠️  Cluster {cid} ({primary_domain}): {coherence:.1%} coherence (below 60% threshold)")
    else:
        print(f"✅ Cluster {cid} ({primary_domain}): {coherence:.1%} coherence, {size} nodes")

mean_coherence = np.mean(coherence_scores)
failed_coherence = sum(1 for c in coherence_scores if c < 0.60)

# Validate
val2_pass = True
if mean_coherence < 0.60:
    print(f"\n❌ Mean coherence {mean_coherence:.1%} below 60%")
    val2_pass = False
else:
    print(f"\n✅ Mean coherence: {mean_coherence:.1%} (target: ≥60%)")

if failed_coherence > 3:
    print(f"❌ {failed_coherence} clusters failed coherence (max 3 allowed)")
    val2_pass = False
else:
    print(f"✅ Failed coherence: {failed_coherence}/{n_clusters} (max 3)")

validation_results['mean_coherence'] = float(mean_coherence)
validation_results['failed_coherence'] = int(failed_coherence)
validation_results['validation_2_pass'] = val2_pass

# ============================================================================
# VALIDATION 3: Coverage
# ============================================================================

print("\n" + "="*80)
print("VALIDATION 3: COVERAGE (ALL 329 MECHANISMS ASSIGNED)")
print("="*80)

all_assigned = set()
duplicates = []

for cid, nodes in final_clusters.items():
    for node in nodes:
        if node in all_assigned:
            duplicates.append(node)
        all_assigned.add(node)

# Validate
val3_pass = True
if len(duplicates) > 0:
    print(f"❌ {len(duplicates)} nodes assigned to multiple clusters")
    val3_pass = False
else:
    print(f"✅ No duplicates: 0 nodes in multiple clusters")

if len(all_assigned) != len(mechanism_candidates_bridging):
    print(f"❌ Only {len(all_assigned)}/{len(mechanism_candidates_bridging)} mechanisms assigned")
    val3_pass = False
else:
    print(f"✅ Coverage: {len(all_assigned)}/{len(mechanism_candidates_bridging)} mechanisms (100%)")

validation_results['coverage'] = float(len(all_assigned) / len(mechanism_candidates_bridging))
validation_results['duplicates'] = int(len(duplicates))
validation_results['validation_3_pass'] = val3_pass

# ============================================================================
# VALIDATION 4: Domain Distribution Balance
# ============================================================================

print("\n" + "="*80)
print("VALIDATION 4: DOMAIN DISTRIBUTION BALANCE")
print("="*80)

all_domains = []
for metadata in cluster_metadata.values():
    all_domains.append(metadata['primary_domain'])

domain_counts = {}
for domain in all_domains:
    domain_counts[domain] = domain_counts.get(domain, 0) + 1

print("\nDomain distribution:")
for domain, count in sorted(domain_counts.items(), key=lambda x: x[1], reverse=True):
    pct = count / len(all_domains) * 100
    print(f"   {domain}: {count} clusters ({pct:.1f}%)")

# Validate
val4_pass = True
max_domain_pct = max(domain_counts.values()) / len(all_domains)
unknown_pct = domain_counts.get('Unknown', 0) / len(all_domains)

if max_domain_pct > 0.50:
    print(f"\n⚠️  One domain dominates {max_domain_pct:.1%} of clusters (max 50%)")
    val4_pass = False
else:
    print(f"\n✅ Domain balance: Largest domain is {max_domain_pct:.1%} (max 50%)")

if unknown_pct > 0.20:
    print(f"⚠️  {unknown_pct:.1%} clusters are 'Unknown' domain (max 20%)")
    val4_pass = False
else:
    print(f"✅ Unknown domain: {unknown_pct:.1%} (max 20%)")

# Note: "Mixed" domain is acceptable (multi-domain clusters)
mixed_pct = domain_counts.get('Mixed', 0) / len(all_domains)
print(f"   Mixed domain: {mixed_pct:.1%} (multi-domain clusters, acceptable)")

validation_results['max_domain_pct'] = float(max_domain_pct)
validation_results['unknown_pct'] = float(unknown_pct)
validation_results['mixed_pct'] = float(mixed_pct)
validation_results['validation_4_pass'] = val4_pass

# ============================================================================
# VALIDATION 5: Embedding Quality
# ============================================================================

print("\n" + "="*80)
print("VALIDATION 5: EMBEDDING QUALITY (SANITY CHECK)")
print("="*80)

# Get final labels for silhouette calculation
final_labels = []
for node in mechanism_candidates_bridging:
    for cid, nodes in final_clusters.items():
        if node in nodes:
            final_labels.append(cid)
            break

final_labels = np.array(final_labels)

# Compute silhouette score
silhouette = silhouette_score(embeddings, final_labels)

print(f"\nSilhouette score: {silhouette:.3f}")

# Check embedding diversity
embedding_stds = np.std(embeddings, axis=0)
mean_std = np.mean(embedding_stds)

print(f"Embedding diversity (mean std): {mean_std:.4f}")

# Validate
val5_pass = True
if silhouette < 0.20:
    print(f"❌ Silhouette score {silhouette:.3f} too low (<0.20)")
    val5_pass = False
else:
    print(f"✅ Silhouette score: {silhouette:.3f} (≥0.20 indicates meaningful clusters)")

if mean_std < 0.01:
    print(f"❌ Embeddings have low variance (mean std={mean_std:.4f})")
    val5_pass = False
else:
    print(f"✅ Embedding diversity: Mean std={mean_std:.4f} (sufficient variation)")

validation_results['silhouette_score'] = float(silhouette)
validation_results['embedding_mean_std'] = float(mean_std)
validation_results['validation_5_pass'] = val5_pass

# ============================================================================
# VALIDATION 6: Top Variables per Cluster Make Sense (Manual Inspection)
# ============================================================================

print("\n" + "="*80)
print("VALIDATION 6: TOP VARIABLES PER CLUSTER (MANUAL INSPECTION)")
print("="*80)

print("\n=== CLUSTER INSPECTION (First 5 clusters) ===")

for cid in sorted(cluster_metadata.keys())[:5]:
    metadata = cluster_metadata[cid]
    print(f"\nCluster {cid}: {metadata['cluster_name']}")
    print(f"   Domain: {metadata['primary_domain']} ({metadata['coherence']:.1%} coherence)")
    print(f"   Size: {metadata['size']} nodes")
    print(f"   Top 5 variables:")
    for i, var in enumerate(metadata['top_variables'][:5], 1):
        domain = infer_domain(var)
        print(f"      {i}. {var} ({domain})")

print("\n⚠️  MANUAL CHECK REQUIRED:")
print("Do the top 5 variables in each cluster make semantic sense together?")
print("\nExamples of GOOD clusters:")
print("  - All judicial/legal variables (v2jucomp, v2jucorrdc, v2juhcind)")
print("  - All health/mortality variables (wdi_mortu5, REPR.1.G2.CP, infant_mortality)")
print("\nExamples of BAD clusters:")
print("  - Mix of unrelated domains (v2jucomp, wdi_gdp, birth_rate)")
print("  - Random variable codes with no pattern (41924, 20063, 83742)")

# For automated validation, check if top 3 variables have same domain
coherent_clusters = 0
for cid, metadata in cluster_metadata.items():
    top3 = metadata['top_variables'][:3]
    top3_domains = [infer_domain(var) for var in top3]

    # Check if at least 2/3 have same domain
    domain_counts_top3 = {}
    for d in top3_domains:
        domain_counts_top3[d] = domain_counts_top3.get(d, 0) + 1

    max_domain_count = max(domain_counts_top3.values())
    if max_domain_count >= 2:
        coherent_clusters += 1

coherent_pct = coherent_clusters / len(cluster_metadata)

print(f"\n📊 Automated check: {coherent_clusters}/{len(cluster_metadata)} clusters ({coherent_pct:.1%}) have coherent top 3 variables")
print(f"   (At least 2/3 top variables share same domain)")

val6_pass = coherent_pct >= 0.60  # 60% threshold

if val6_pass:
    print(f"✅ Manual inspection: {coherent_pct:.1%} clusters coherent (≥60%)")
else:
    print(f"❌ Manual inspection: {coherent_pct:.1%} clusters coherent (<60%)")

validation_results['top_variables_coherence'] = float(coherent_pct)
validation_results['validation_6_pass'] = val6_pass

# ============================================================================
# VALIDATION 7: Centrality Preservation
# ============================================================================

print("\n" + "="*80)
print("VALIDATION 7: CENTRALITY PRESERVATION")
print("="*80)

# For each cluster, compute mean centrality
cluster_centralities = {}
for cid, nodes in final_clusters.items():
    centralities = [centrality_scores.get(node, 0) for node in nodes]
    cluster_centralities[cid] = {
        'mean': np.mean(centralities),
        'max': max(centralities),
        'size': len(nodes)
    }

# Sort by mean centrality
sorted_clusters = sorted(cluster_centralities.items(), key=lambda x: x[1]['mean'], reverse=True)

print("\nTop 5 clusters by mean centrality:")
for cid, stats in sorted_clusters[:5]:
    domain = cluster_metadata[cid]['primary_domain']
    print(f"   Cluster {cid} ({domain}): mean={stats['mean']:.4f}, max={stats['max']:.4f}, size={stats['size']}")

# Check balance
total_centrality = sum(centrality_scores.values())
top_cluster_centrality = sum(
    centrality_scores.get(node, 0)
    for node in final_clusters[sorted_clusters[0][0]]
)
top_cluster_pct = top_cluster_centrality / total_centrality

print(f"\nTop cluster centrality: {top_cluster_pct:.1%} of total")

# Validate
val7_pass = True
if top_cluster_pct > 0.35:
    print(f"⚠️  Top cluster has {top_cluster_pct:.1%} of total centrality (max 35%)")
    val7_pass = False
else:
    print(f"✅ Centrality balance: Top cluster has {top_cluster_pct:.1%} of total (max 35%)")

validation_results['top_cluster_centrality_pct'] = float(top_cluster_pct)
validation_results['validation_7_pass'] = val7_pass

# ============================================================================
# VALIDATION 8: Reproducibility Check
# ============================================================================

print("\n" + "="*80)
print("VALIDATION 8: REPRODUCIBILITY CHECK")
print("="*80)

# Load model and re-embed (should get same results)
print(f"\nRe-embedding to test reproducibility...")

# Enhance variable names (same as in script)
def enhance_variable_name(node):
    domain_hints = {
        'v2ju': 'judicial',
        'v2ps': 'political participation',
        'v2cl': 'civil liberties',
        'v2cs': 'civil society',
        'v2ex': 'executive',
        'v2el': 'elections',
        'v2dl': 'deliberation',
        'v2sm': 'social media',
        'v2me': 'media',
        'v2sv': 'sovereignty',
        'v3pe': 'political equality',
        'wdi_': 'world development indicator',
        'REPR': 'reproductive health',
        'GER': 'gross enrollment rate',
        'OAEP': 'over-age enrollment',
        'NERT': 'net enrollment rate',
        'BR': 'birth rate',
        'NW': 'natural wealth',
        'BX': 'balance of payments',
        'pwt_': 'penn world table',
        'INTERACT_': 'interaction term',
        'atop_': 'alliance treaty',
        'e_cow_': 'correlates of war',
        'opri_': 'organizational power',
        'yptf': 'youth transfer',
        'aptd': 'adult transfer',
        'wcom': 'wage compensation',
        'ygsm': 'youth government spending',
        'wgsm': 'adult government spending',
        'wpinn': 'private investment',
        'ypinn': 'youth private investment',
        'yprn': 'youth private income',
        'wprn': 'adult private income',
        'eofgh': 'economic freedom',
    }

    text = node
    for prefix, hint in domain_hints.items():
        if node.lower().startswith(prefix.lower()):
            text = f"{hint} {node}"
            break
    return text

mechanism_texts_enhanced = [enhance_variable_name(node) for node in mechanism_candidates_bridging]

model = SentenceTransformer('all-MiniLM-L6-v2')
embeddings_test = model.encode(mechanism_texts_enhanced, show_progress_bar=False)

# Check embedding similarity
embedding_diff = np.abs(embeddings - embeddings_test).max()

print(f"Max embedding difference: {embedding_diff:.2e}")

# Re-run clustering
best_n_clusters = results_metadata['optimal_n_clusters']
test_clustering = AgglomerativeClustering(n_clusters=best_n_clusters, linkage='ward')
test_labels = test_clustering.fit_predict(embeddings_test)

# Check if labels match (using Adjusted Rand Index)
# Get labels for test clustering
test_cluster_map = {}
for node, label in zip(mechanism_candidates_bridging, test_labels):
    test_cluster_map[node] = label

# Get original labels
orig_labels = []
test_labels_ordered = []
for node in mechanism_candidates_bridging:
    # Original
    for cid, nodes in final_clusters.items():
        if node in nodes:
            orig_labels.append(cid)
            break
    # Test
    test_labels_ordered.append(test_cluster_map[node])

ari = adjusted_rand_score(orig_labels, test_labels_ordered)

print(f"Adjusted Rand Index: {ari:.3f}")

# Validate
val8_pass = True
if embedding_diff > 1e-6:
    print(f"⚠️  Embeddings differ by {embedding_diff:.2e} (>1e-6)")
else:
    print(f"✅ Embeddings reproducible (max diff: {embedding_diff:.2e})")

if ari < 0.95:
    print(f"⚠️  Clustering ARI {ari:.3f} < 0.95 (some instability)")
    val8_pass = False
else:
    print(f"✅ Clustering reproducible (ARI: {ari:.3f}, 1.0 = perfect match)")

validation_results['embedding_diff'] = float(embedding_diff)
validation_results['reproducibility_ari'] = float(ari)
validation_results['validation_8_pass'] = val8_pass

# ============================================================================
# OVERALL VALIDATION SCORECARD
# ============================================================================

print("\n" + "="*80)
print("B2 VALIDATION SCORECARD")
print("="*80)

validation_pass = (
    val1_pass and
    val2_pass and
    val3_pass and
    val4_pass and
    val5_pass and
    val6_pass and
    val7_pass and
    val8_pass
)

validation_results['overall_pass'] = validation_pass

print(f"\n📊 Validation Results:")
print(f"   1. Cluster count & size:     {'✅ PASS' if val1_pass else '❌ FAIL'}")
print(f"   2. Domain coherence:          {'✅ PASS' if val2_pass else '❌ FAIL'}")
print(f"   3. Coverage:                  {'✅ PASS' if val3_pass else '❌ FAIL'}")
print(f"   4. Domain balance:            {'✅ PASS' if val4_pass else '❌ FAIL'}")
print(f"   5. Embedding quality:         {'✅ PASS' if val5_pass else '❌ FAIL'}")
print(f"   6. Top variables coherence:   {'✅ PASS' if val6_pass else '❌ FAIL'}")
print(f"   7. Centrality preservation:   {'✅ PASS' if val7_pass else '❌ FAIL'}")
print(f"   8. Reproducibility:           {'✅ PASS' if val8_pass else '❌ FAIL'}")

if validation_pass:
    print("\n" + "="*60)
    print("✅ B2 VALIDATION PASSED - READY FOR B3")
    print("="*60)
else:
    print("\n" + "="*60)
    print("❌ B2 VALIDATION FAILED - FIX ISSUES BEFORE B3")
    print("="*60)

    failed_validations = []
    if not val1_pass:
        failed_validations.append("1. Cluster count & size")
    if not val2_pass:
        failed_validations.append("2. Domain coherence")
    if not val3_pass:
        failed_validations.append("3. Coverage")
    if not val4_pass:
        failed_validations.append("4. Domain balance")
    if not val5_pass:
        failed_validations.append("5. Embedding quality")
    if not val6_pass:
        failed_validations.append("6. Top variables coherence")
    if not val7_pass:
        failed_validations.append("7. Centrality preservation")
    if not val8_pass:
        failed_validations.append("8. Reproducibility")

    print(f"\nFailed validations ({len(failed_validations)}/8):")
    for val in failed_validations:
        print(f"   - {val}")

# Save validation results
with open(output_dir / 'B2_validation_results.json', 'w') as f:
    json.dump(validation_results, f, indent=2)

print(f"\n✅ Validation results saved: {output_dir}/B2_validation_results.json")

print(f"\n{'='*80}")
