#!/usr/bin/env python3
"""
B3 Part 2: Domain Classification Refinement
============================================

Classifies 15 semantic clusters into primary domains using:
1. TF-IDF matching against literature constructs
2. Source distribution analysis (V-Dem → Governance, UNESCO → Education)
3. Category hints from metadata

Goals:
- Reduce "Mixed" labels from 80% (B2) to <50%
- Assign primary domain + confidence score to each cluster
- Improve domain coherence from 90.6% to maintain or improve

Author: B3 Part 2
Date: November 2025
Runtime: ~1-2 hours
"""

import pickle
import json
import pandas as pd
import numpy as np
from pathlib import Path
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from collections import Counter
import sys

project_root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(project_root))

print("="*80)
print("B3 PART 2: DOMAIN CLASSIFICATION REFINEMENT")
print("="*80)

# ============================================================================
# STEP 1: Load Part 1 Enriched Checkpoint
# ============================================================================

print("\n" + "="*80)
print("STEP 1: LOAD PART 1 ENRICHED CHECKPOINT")
print("="*80)

checkpoint_path = project_root / 'phaseB/B3_domain_classification/outputs/B3_task1_metadata_enriched.pkl'

print(f"\nLoading: {checkpoint_path}")

with open(checkpoint_path, 'rb') as f:
    checkpoint = pickle.load(f)

enriched_df = checkpoint['enriched_dataframe']
enriched_cluster_metadata = checkpoint['enriched_cluster_metadata']
unified_metadata = checkpoint['unified_metadata']

print(f"\n✅ Loaded enriched checkpoint:")
print(f"   Mechanisms: {len(enriched_df)}")
print(f"   Clusters: {len(enriched_cluster_metadata)}")
print(f"   Metadata coverage: {checkpoint['metadata_coverage']*100:.1f}%")
print(f"   High-quality metadata: {checkpoint['high_quality_pct']:.1f}%")

# ============================================================================
# STEP 2: Load Literature Constructs
# ============================================================================

print("\n" + "="*80)
print("STEP 2: LOAD LITERATURE CONSTRUCTS")
print("="*80)

literature_path = project_root / 'literature_db/literature_constructs.json'

print(f"\nLoading: {literature_path}")

with open(literature_path, 'r') as f:
    literature_constructs = json.load(f)

print(f"\n✅ Loaded {len(literature_constructs)} literature constructs")

# Extract domains from literature
literature_domains = set()
for construct_name, construct_info in literature_constructs.items():
    domain = construct_info.get('domain', 'Unknown')
    literature_domains.add(domain)

print(f"\n📊 Literature Domains ({len(literature_domains)}):")
for domain in sorted(literature_domains):
    constructs_in_domain = [name for name, info in literature_constructs.items() if info.get('domain') == domain]
    print(f"   {domain:>20}: {len(constructs_in_domain)} constructs")

# ============================================================================
# STEP 3: Build TF-IDF Vectors for Clusters
# ============================================================================

print("\n" + "="*80)
print("STEP 3: BUILD TF-IDF VECTORS FOR CLUSTERS")
print("="*80)

# Prepare cluster text representations
cluster_texts = []
cluster_ids_ordered = []

for cluster_info in enriched_cluster_metadata:
    cluster_id = cluster_info['cluster_id']
    cluster_ids_ordered.append(cluster_id)

    # Get all indicators in this cluster
    cluster_indicators = enriched_df[enriched_df['cluster_id'] == cluster_id]

    # Combine full names and descriptions
    text_parts = []
    for _, row in cluster_indicators.iterrows():
        if pd.notna(row['full_name']) and row['full_name'] != row['node']:
            text_parts.append(row['full_name'])
        if pd.notna(row['description']) and row['description']:
            text_parts.append(row['description'])

    cluster_text = ' '.join(text_parts)
    cluster_texts.append(cluster_text)

    print(f"   Cluster {cluster_id}: {len(text_parts)} text parts, {len(cluster_text)} chars")

print(f"\n✅ Prepared {len(cluster_texts)} cluster text representations")

# Prepare literature construct text representations
literature_texts = []
literature_names_ordered = []

for construct_name, construct_info in literature_constructs.items():
    literature_names_ordered.append(construct_name)

    # Combine keywords and source
    text_parts = []

    if 'keywords' in construct_info:
        text_parts.extend(construct_info['keywords'])

    if 'source' in construct_info:
        text_parts.append(construct_info['source'])

    # Add indicators if available
    if 'indicators' in construct_info:
        text_parts.extend(construct_info['indicators'])

    literature_text = ' '.join(text_parts)
    literature_texts.append(literature_text)

print(f"✅ Prepared {len(literature_texts)} literature construct representations")

# Build TF-IDF vectorizer
print(f"\nBuilding TF-IDF vectorizer...")

all_texts = cluster_texts + literature_texts
vectorizer = TfidfVectorizer(
    max_features=500,
    stop_words='english',
    ngram_range=(1, 2),  # Unigrams and bigrams
    min_df=1
)

tfidf_matrix = vectorizer.fit_transform(all_texts)

# Split back into cluster and literature vectors
n_clusters = len(cluster_texts)
cluster_vectors = tfidf_matrix[:n_clusters]
literature_vectors = tfidf_matrix[n_clusters:]

print(f"✅ TF-IDF matrix: {tfidf_matrix.shape}")
print(f"   Cluster vectors: {cluster_vectors.shape}")
print(f"   Literature vectors: {literature_vectors.shape}")
print(f"   Vocabulary size: {len(vectorizer.vocabulary_)}")

# ============================================================================
# STEP 4: Compute Similarity to Literature Constructs
# ============================================================================

print("\n" + "="*80)
print("STEP 4: COMPUTE SIMILARITY TO LITERATURE CONSTRUCTS")
print("="*80)

# Compute cosine similarity
similarity_matrix = cosine_similarity(cluster_vectors, literature_vectors)

print(f"\n✅ Computed similarity matrix: {similarity_matrix.shape}")
print(f"   (15 clusters × {len(literature_constructs)} constructs)")

# Find best matching construct for each cluster
cluster_literature_matches = []

for i, cluster_id in enumerate(cluster_ids_ordered):
    similarities = similarity_matrix[i]
    best_match_idx = np.argmax(similarities)
    best_match_score = similarities[best_match_idx]
    best_match_name = literature_names_ordered[best_match_idx]
    best_match_domain = literature_constructs[best_match_name].get('domain', 'Unknown')

    # Get top 3 matches
    top_3_indices = np.argsort(similarities)[-3:][::-1]
    top_3_matches = [
        {
            'construct': literature_names_ordered[idx],
            'domain': literature_constructs[literature_names_ordered[idx]].get('domain', 'Unknown'),
            'similarity': float(similarities[idx])
        }
        for idx in top_3_indices
    ]

    cluster_literature_matches.append({
        'cluster_id': cluster_id,
        'best_match_construct': best_match_name,
        'best_match_domain': best_match_domain,
        'best_match_similarity': float(best_match_score),
        'top_3_matches': top_3_matches
    })

    print(f"\n   Cluster {cluster_id:>2}: Best match = {best_match_name} ({best_match_domain}, similarity={best_match_score:.3f})")
    print(f"      Top 3:")
    for match in top_3_matches:
        print(f"        - {match['construct']:30} ({match['domain']:20}, {match['similarity']:.3f})")

# ============================================================================
# STEP 5: Source-Based Domain Hints
# ============================================================================

print("\n" + "="*80)
print("STEP 5: SOURCE-BASED DOMAIN HINTS")
print("="*80)

# Source → Domain mapping
source_domain_mapping = {
    'V-Dem Institute': 'Governance',
    'UNESCO Institute for Statistics': 'Education',
    'World Bank World Development Indicators': 'Economic',
    'World Bank': 'Economic',
    'Penn World Table': 'Economic',
    'Penn World Table 10.0': 'Economic',
    'WHO': 'Health',
    'UNICEF': 'Health',
    'IMF': 'Economic',
    'Political Regime Dataset': 'Governance',
    'International Relations Dataset': 'International',
    'Quality of Government Institute': 'Governance'
}

# Compute source-based domain hints for each cluster
cluster_source_hints = []

for cluster_info in enriched_cluster_metadata:
    cluster_id = cluster_info['cluster_id']
    source_dist = cluster_info.get('source_distribution', {})

    # Map sources to domains
    domain_votes = {}
    total_votes = 0

    for source, count in source_dist.items():
        domain = source_domain_mapping.get(source, 'Unknown')
        domain_votes[domain] = domain_votes.get(domain, 0) + count
        total_votes += count

    # Get dominant domain
    if domain_votes:
        dominant_domain = max(domain_votes.items(), key=lambda x: x[1])
        dominant_pct = dominant_domain[1] / total_votes * 100

        cluster_source_hints.append({
            'cluster_id': cluster_id,
            'source_hint_domain': dominant_domain[0],
            'source_hint_confidence': dominant_pct / 100,
            'domain_votes': domain_votes
        })

        print(f"\n   Cluster {cluster_id:>2}: Source hint = {dominant_domain[0]} ({dominant_pct:.1f}% confidence)")
        print(f"      Vote breakdown: {domain_votes}")
    else:
        cluster_source_hints.append({
            'cluster_id': cluster_id,
            'source_hint_domain': 'Unknown',
            'source_hint_confidence': 0.0,
            'domain_votes': {}
        })
        print(f"\n   Cluster {cluster_id:>2}: No source hints available")

# ============================================================================
# STEP 6: Combine Evidence for Final Domain Classification
# ============================================================================

print("\n" + "="*80)
print("STEP 6: COMBINE EVIDENCE FOR FINAL DOMAIN CLASSIFICATION")
print("="*80)

# Combine TF-IDF literature match + source hints
final_domain_classifications = []

for i, cluster_id in enumerate(cluster_ids_ordered):
    # Get literature match
    lit_match = cluster_literature_matches[i]
    lit_domain = lit_match['best_match_domain']
    lit_similarity = lit_match['best_match_similarity']

    # Get source hint
    source_hint = next((h for h in cluster_source_hints if h['cluster_id'] == cluster_id), None)
    source_domain = source_hint['source_hint_domain'] if source_hint else 'Unknown'
    source_confidence = source_hint['source_hint_confidence'] if source_hint else 0.0

    # Decision logic
    if lit_similarity >= 0.30 and source_domain != 'Unknown' and lit_domain == source_domain:
        # Strong agreement: both methods agree
        final_domain = lit_domain
        confidence = (lit_similarity + source_confidence) / 2
        decision_method = 'agreement'
    elif lit_similarity >= 0.30:
        # Trust literature match
        final_domain = lit_domain
        confidence = lit_similarity
        decision_method = 'literature'
    elif source_confidence >= 0.70:
        # Trust source hint
        final_domain = source_domain
        confidence = source_confidence
        decision_method = 'source'
    elif lit_similarity >= 0.15:
        # Weak literature match
        final_domain = lit_domain
        confidence = lit_similarity
        decision_method = 'literature_weak'
    elif source_confidence >= 0.50:
        # Moderate source hint
        final_domain = source_domain
        confidence = source_confidence
        decision_method = 'source_moderate'
    else:
        # No strong evidence - mark as Mixed
        final_domain = 'Mixed'
        confidence = max(lit_similarity, source_confidence)
        decision_method = 'mixed'

    final_domain_classifications.append({
        'cluster_id': cluster_id,
        'primary_domain': final_domain,
        'confidence': float(confidence),
        'decision_method': decision_method,
        'literature_match': lit_domain,
        'literature_similarity': lit_similarity,
        'source_hint': source_domain,
        'source_confidence': source_confidence,
        'best_construct': lit_match['best_match_construct']
    })

    print(f"\n   Cluster {cluster_id:>2}: {final_domain:>20} (conf={confidence:.3f}, method={decision_method})")
    print(f"      Literature: {lit_domain} ({lit_similarity:.3f})")
    print(f"      Source: {source_domain} ({source_confidence:.3f})")

# ============================================================================
# STEP 7: Domain Distribution Analysis
# ============================================================================

print("\n" + "="*80)
print("STEP 7: DOMAIN DISTRIBUTION ANALYSIS")
print("="*80)

# Count clusters per domain
domain_counts = {}
for classification in final_domain_classifications:
    domain = classification['primary_domain']
    domain_counts[domain] = domain_counts.get(domain, 0) + 1

print(f"\n📊 Final Domain Distribution:")
print(f"{'Domain':<20} {'Clusters':<10} {'Percentage'}")
print("-" * 50)

for domain in sorted(domain_counts.keys(), key=lambda x: domain_counts[x], reverse=True):
    count = domain_counts[domain]
    pct = count / len(final_domain_classifications) * 100
    print(f"{domain:<20} {count:<10} {pct:>5.1f}%")

# Check if we reduced Mixed from 80%
mixed_pct = domain_counts.get('Mixed', 0) / len(final_domain_classifications) * 100

print(f"\n📈 Comparison to B2:")
print(f"   B2 Mixed clusters: 80.0% (12/15)")
print(f"   B3 Mixed clusters: {mixed_pct:.1f}% ({domain_counts.get('Mixed', 0)}/15)")

if mixed_pct < 50:
    print(f"   ✅ SUCCESS: Reduced Mixed below 50% target")
elif mixed_pct < 80:
    print(f"   ⚠️  PARTIAL: Reduced Mixed from 80% to {mixed_pct:.1f}%")
else:
    print(f"   ❌ WARNING: Mixed still at {mixed_pct:.1f}%")

# ============================================================================
# STEP 8: Update Cluster Metadata with Domains
# ============================================================================

print("\n" + "="*80)
print("STEP 8: UPDATE CLUSTER METADATA WITH DOMAINS")
print("="*80)

# Update enriched_cluster_metadata with domain classifications
for cluster_info in enriched_cluster_metadata:
    cluster_id = cluster_info['cluster_id']

    # Find classification
    classification = next((c for c in final_domain_classifications if c['cluster_id'] == cluster_id), None)

    if classification:
        cluster_info['primary_domain'] = classification['primary_domain']
        cluster_info['domain_confidence'] = classification['confidence']
        cluster_info['domain_method'] = classification['decision_method']
        cluster_info['literature_match'] = classification['best_construct']
        cluster_info['literature_similarity'] = classification['literature_similarity']
        cluster_info['source_hint_domain'] = classification['source_hint']
        cluster_info['source_hint_confidence'] = classification['source_confidence']

        print(f"   ✅ Cluster {cluster_id}: {classification['primary_domain']}")

# Update enriched_df with domain labels
enriched_df['primary_domain'] = enriched_df['cluster_id'].map(
    {c['cluster_id']: c['primary_domain'] for c in final_domain_classifications}
)
enriched_df['domain_confidence'] = enriched_df['cluster_id'].map(
    {c['cluster_id']: c['confidence'] for c in final_domain_classifications}
)

print(f"\n✅ Updated {len(enriched_cluster_metadata)} cluster metadata entries")
print(f"✅ Updated {len(enriched_df)} indicator records with domain labels")

# ============================================================================
# STEP 9: Save Part 2 Checkpoint
# ============================================================================

print("\n" + "="*80)
print("STEP 9: SAVE PART 2 CHECKPOINT")
print("="*80)

# Create Part 2 checkpoint
part2_checkpoint = {
    # Part 1 data
    'mechanism_candidates': checkpoint['mechanism_candidates'],
    'cluster_assignments': checkpoint['cluster_assignments'],
    'unified_metadata': unified_metadata,
    'embeddings': checkpoint.get('embeddings'),
    'centrality_scores': checkpoint.get('centrality_scores'),
    'layers': checkpoint.get('layers'),

    # Part 2 data
    'enriched_dataframe': enriched_df,
    'enriched_cluster_metadata': enriched_cluster_metadata,
    'final_domain_classifications': final_domain_classifications,
    'cluster_literature_matches': cluster_literature_matches,
    'cluster_source_hints': cluster_source_hints,
    'tfidf_vectorizer': vectorizer,
    'similarity_matrix': similarity_matrix,

    # Metadata
    'part_1_complete': True,
    'part_2_complete': True,
    'mixed_pct': mixed_pct,
    'mean_domain_confidence': float(np.mean([c['confidence'] for c in final_domain_classifications]))
}

# Save checkpoint
checkpoint_path = project_root / 'phaseB/B3_domain_classification/outputs/B3_part2_domain_classified.pkl'

with open(checkpoint_path, 'wb') as f:
    pickle.dump(part2_checkpoint, f)

print(f"\n✅ Saved Part 2 checkpoint: {checkpoint_path}")
print(f"   File size: {checkpoint_path.stat().st_size / (1024**2):.2f} MB")

# Save domain classifications as JSON
classifications_path = project_root / 'phaseB/B3_domain_classification/outputs/B3_domain_classifications.json'

with open(classifications_path, 'w') as f:
    json.dump(final_domain_classifications, f, indent=2)

print(f"✅ Saved domain classifications: {classifications_path}")

# Save updated enriched assignments CSV
csv_path = project_root / 'phaseB/B3_domain_classification/outputs/B3_domain_classified_assignments.csv'
enriched_df.to_csv(csv_path, index=False)

print(f"✅ Saved domain-classified assignments: {csv_path}")

# ============================================================================
# PART 2 COMPLETION SUMMARY
# ============================================================================

print("\n" + "="*80)
print("PART 2 COMPLETION SUMMARY")
print("="*80)

print(f"\n✅ Successfully classified 15 clusters into domains:")
print(f"   Mixed clusters: {domain_counts.get('Mixed', 0)} ({mixed_pct:.1f}%)")
print(f"   Mean confidence: {part2_checkpoint['mean_domain_confidence']:.3f}")

print(f"\n📊 Domain Breakdown:")
for domain, count in sorted(domain_counts.items(), key=lambda x: x[1], reverse=True):
    clusters_in_domain = [c['cluster_id'] for c in final_domain_classifications if c['primary_domain'] == domain]
    print(f"   {domain:>20}: {count} clusters {clusters_in_domain}")

print(f"\n📁 Outputs Created:")
print(f"   1. B3_part2_domain_classified.pkl - Complete checkpoint")
print(f"   2. B3_domain_classifications.json - Domain labels with confidence")
print(f"   3. B3_domain_classified_assignments.csv - Updated assignments")

print(f"\n🎯 Ready for Part 3: Literature Alignment")
print(f"   Will validate domain classifications against literature constructs")
print(f"   Expected runtime: 2-3 hours")

print("\n" + "="*80)
print("✅ PART 2 COMPLETE")
print("="*80)
