#!/usr/bin/env python3
"""
B3 Part 3: Literature Alignment
================================

Deep investigation of domain classifications using:
1. Expanded TF-IDF analysis with variable-level matching
2. Keyword frequency analysis against literature constructs
3. Cross-construct validation for classified clusters
4. Narrative generation for each cluster

Goals:
- Investigate 7 "Unknown" clusters (46.7% of total)
- Validate 8 classified clusters (Governance, Economic, Education, Mixed)
- Generate interpretable cluster descriptions
- Create final validated domain assignments

Author: B3 Part 3
Date: November 2025
Runtime: ~30-60 minutes
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
print("B3 PART 3: LITERATURE ALIGNMENT")
print("="*80)

# ============================================================================
# STEP 1: Load Part 2 Domain-Classified Checkpoint
# ============================================================================

print("\n" + "="*80)
print("STEP 1: LOAD PART 2 DOMAIN-CLASSIFIED CHECKPOINT")
print("="*80)

checkpoint_path = project_root / 'phaseB/B3_domain_classification/outputs/B3_part2_domain_classified.pkl'

print(f"\nLoading: {checkpoint_path}")

with open(checkpoint_path, 'rb') as f:
    checkpoint = pickle.load(f)

enriched_df = checkpoint['enriched_dataframe']
enriched_cluster_metadata = checkpoint['enriched_cluster_metadata']
final_domain_classifications = checkpoint['final_domain_classifications']

print(f"\n✅ Loaded Part 2 checkpoint:")
print(f"   Mechanisms: {len(enriched_df)}")
print(f"   Clusters: {len(enriched_cluster_metadata)}")
print(f"   Mixed clusters: {checkpoint['mixed_pct']:.1f}%")
print(f"   Mean confidence: {checkpoint['mean_domain_confidence']:.3f}")

# Load literature constructs
literature_path = project_root / 'literature_db/literature_constructs.json'
with open(literature_path, 'r') as f:
    literature_constructs = json.load(f)

print(f"\n✅ Loaded {len(literature_constructs)} literature constructs")

# Identify Unknown clusters
unknown_clusters = [c for c in final_domain_classifications if c['primary_domain'] == 'Unknown']
classified_clusters = [c for c in final_domain_classifications if c['primary_domain'] != 'Unknown']

print(f"\n📊 Classification Status:")
print(f"   Unknown clusters: {len(unknown_clusters)} ({len(unknown_clusters)/len(final_domain_classifications)*100:.1f}%)")
print(f"   Classified clusters: {len(classified_clusters)} ({len(classified_clusters)/len(final_domain_classifications)*100:.1f}%)")

# ============================================================================
# STEP 2: Variable-Level TF-IDF Analysis for Unknown Clusters
# ============================================================================

print("\n" + "="*80)
print("STEP 2: VARIABLE-LEVEL TF-IDF ANALYSIS FOR UNKNOWN CLUSTERS")
print("="*80)

print(f"\nAnalyzing {len(unknown_clusters)} Unknown clusters individually...")

unknown_cluster_analyses = []

for classification in unknown_clusters:
    cluster_id = classification['cluster_id']

    print(f"\n{'='*60}")
    print(f"Cluster {cluster_id} Analysis")
    print(f"{'='*60}")

    # Get all variables in this cluster
    cluster_vars = enriched_df[enriched_df['cluster_id'] == cluster_id]

    print(f"   Size: {len(cluster_vars)} mechanisms")

    # Sample top variables
    sample_vars = cluster_vars.head(10)
    print(f"\n   Sample variables:")
    for idx, row in sample_vars.iterrows():
        quality = "✓" if row['metadata_quality'] == 'high' else "~"
        print(f"      {quality} {row['node']:30} | {row['full_name'][:40]}")

    # Build text representation from all variables
    var_texts = []
    for _, row in cluster_vars.iterrows():
        text_parts = []
        if pd.notna(row['full_name']) and row['full_name'] != row['node']:
            text_parts.append(row['full_name'])
        if pd.notna(row['description']) and row['description']:
            text_parts.append(row['description'])
        if text_parts:
            var_texts.append(' '.join(text_parts))

    combined_text = ' '.join(var_texts)

    print(f"\n   Combined text: {len(combined_text)} chars from {len(var_texts)} variables")

    # Extract keywords (most common words after stopwords)
    if combined_text:
        vectorizer = TfidfVectorizer(
            max_features=20,
            stop_words='english',
            ngram_range=(1, 2)
        )

        try:
            tfidf_matrix = vectorizer.fit_transform([combined_text])
            feature_names = vectorizer.get_feature_names_out()
            tfidf_scores = tfidf_matrix.toarray()[0]

            # Get top keywords
            top_indices = np.argsort(tfidf_scores)[-10:][::-1]
            top_keywords = [(feature_names[i], tfidf_scores[i]) for i in top_indices if tfidf_scores[i] > 0]

            print(f"\n   Top keywords:")
            for keyword, score in top_keywords[:5]:
                print(f"      - {keyword:30} (score: {score:.3f})")

            # Match against literature constructs
            lit_texts = []
            lit_names = []
            for construct_name, construct_info in literature_constructs.items():
                keywords = construct_info.get('keywords', [])
                source = construct_info.get('source', '')
                lit_text = ' '.join(keywords + [source])
                lit_texts.append(lit_text)
                lit_names.append(construct_name)

            # Re-vectorize with cluster + literature
            all_texts = [combined_text] + lit_texts
            vectorizer2 = TfidfVectorizer(
                max_features=200,
                stop_words='english',
                ngram_range=(1, 2)
            )
            tfidf_all = vectorizer2.fit_transform(all_texts)

            cluster_vec = tfidf_all[0:1]
            lit_vecs = tfidf_all[1:]

            similarities = cosine_similarity(cluster_vec, lit_vecs)[0]

            # Get top 3 construct matches
            top_3_indices = np.argsort(similarities)[-3:][::-1]

            print(f"\n   Top 3 literature matches:")
            for idx in top_3_indices:
                construct_name = lit_names[idx]
                domain = literature_constructs[construct_name].get('domain', 'Unknown')
                sim = similarities[idx]
                print(f"      - {construct_name:30} ({domain:20}, sim={sim:.3f})")

            # Store analysis
            unknown_cluster_analyses.append({
                'cluster_id': cluster_id,
                'size': len(cluster_vars),
                'top_keywords': [kw for kw, _ in top_keywords[:5]],
                'top_construct_match': lit_names[top_3_indices[0]],
                'top_construct_domain': literature_constructs[lit_names[top_3_indices[0]]].get('domain'),
                'top_construct_similarity': float(similarities[top_3_indices[0]]),
                'top_3_matches': [
                    {
                        'construct': lit_names[i],
                        'domain': literature_constructs[lit_names[i]].get('domain'),
                        'similarity': float(similarities[i])
                    }
                    for i in top_3_indices
                ]
            })

        except Exception as e:
            print(f"\n   ⚠️  TF-IDF analysis failed: {str(e)}")
            unknown_cluster_analyses.append({
                'cluster_id': cluster_id,
                'size': len(cluster_vars),
                'error': str(e)
            })
    else:
        print(f"\n   ⚠️  No text available for analysis")

print(f"\n✅ Analyzed {len(unknown_cluster_analyses)} Unknown clusters")

# ============================================================================
# STEP 3: Keyword Frequency Analysis
# ============================================================================

print("\n" + "="*80)
print("STEP 3: KEYWORD FREQUENCY ANALYSIS")
print("="*80)

# For each Unknown cluster, count keyword matches with literature constructs

keyword_match_results = []

for analysis in unknown_cluster_analyses:
    cluster_id = analysis['cluster_id']

    if 'error' in analysis:
        continue

    print(f"\nCluster {cluster_id} keyword matching:")

    # Get cluster variables
    cluster_vars = enriched_df[enriched_df['cluster_id'] == cluster_id]

    # Collect all text
    all_text = []
    for _, row in cluster_vars.iterrows():
        if pd.notna(row['full_name']):
            all_text.append(row['full_name'].lower())
        if pd.notna(row['description']):
            all_text.append(row['description'].lower())

    combined_text = ' '.join(all_text)

    # Count keyword matches for each construct
    construct_matches = {}

    for construct_name, construct_info in literature_constructs.items():
        keywords = construct_info.get('keywords', [])
        domain = construct_info.get('domain', 'Unknown')

        # Count how many keywords appear in cluster text
        matches = sum(1 for kw in keywords if kw.lower() in combined_text)

        if matches > 0:
            construct_matches[construct_name] = {
                'domain': domain,
                'keyword_matches': matches,
                'total_keywords': len(keywords),
                'match_pct': matches / len(keywords) if keywords else 0
            }

    if construct_matches:
        # Sort by match percentage
        sorted_matches = sorted(
            construct_matches.items(),
            key=lambda x: (x[1]['keyword_matches'], x[1]['match_pct']),
            reverse=True
        )

        print(f"   Top 3 keyword matches:")
        for construct_name, match_info in sorted_matches[:3]:
            print(f"      - {construct_name:30} ({match_info['domain']:20}): {match_info['keyword_matches']}/{match_info['total_keywords']} keywords ({match_info['match_pct']*100:.1f}%)")

        keyword_match_results.append({
            'cluster_id': cluster_id,
            'best_keyword_match': sorted_matches[0][0],
            'best_keyword_domain': sorted_matches[0][1]['domain'],
            'best_keyword_count': sorted_matches[0][1]['keyword_matches'],
            'all_matches': dict(sorted_matches)
        })
    else:
        print(f"   No keyword matches found")

print(f"\n✅ Completed keyword analysis for {len(keyword_match_results)} clusters")

# ============================================================================
# STEP 4: Refined Domain Assignment for Unknown Clusters
# ============================================================================

print("\n" + "="*80)
print("STEP 4: REFINED DOMAIN ASSIGNMENT FOR UNKNOWN CLUSTERS")
print("="*80)

refined_classifications = []

for classification in final_domain_classifications:
    cluster_id = classification['cluster_id']

    if classification['primary_domain'] != 'Unknown':
        # Keep existing classification
        refined_classifications.append(classification)
        print(f"\nCluster {cluster_id:>2}: {classification['primary_domain']:>20} (unchanged, conf={classification['confidence']:.3f})")
    else:
        # Try to refine Unknown classification
        print(f"\nCluster {cluster_id:>2}: Refining Unknown classification...")

        # Get analysis results
        analysis = next((a for a in unknown_cluster_analyses if a['cluster_id'] == cluster_id), None)
        keyword_match = next((k for k in keyword_match_results if k['cluster_id'] == cluster_id), None)

        # Decision logic for refinement
        refined_domain = 'Unknown'
        refined_confidence = 0.0
        refinement_method = 'none'

        if analysis and 'top_construct_similarity' in analysis:
            tfidf_sim = analysis['top_construct_similarity']
            tfidf_domain = analysis['top_construct_domain']

            if keyword_match:
                keyword_domain = keyword_match['best_keyword_domain']
                keyword_count = keyword_match['best_keyword_count']

                # Both methods agree and have reasonable evidence
                if tfidf_domain == keyword_domain and tfidf_sim >= 0.05 and keyword_count >= 2:
                    refined_domain = tfidf_domain
                    refined_confidence = min(tfidf_sim * 2, 0.70)  # Cap at 0.70 for Unknown refinements
                    refinement_method = 'tfidf_keyword_agreement'
                    print(f"      → {refined_domain} (TF-IDF + keywords agree, conf={refined_confidence:.3f})")

                # Strong TF-IDF evidence alone
                elif tfidf_sim >= 0.10:
                    refined_domain = tfidf_domain
                    refined_confidence = min(tfidf_sim * 1.5, 0.60)
                    refinement_method = 'tfidf_strong'
                    print(f"      → {refined_domain} (strong TF-IDF, conf={refined_confidence:.3f})")

                # Moderate keyword evidence
                elif keyword_count >= 3:
                    refined_domain = keyword_domain
                    refined_confidence = min(keyword_count / 10, 0.50)
                    refinement_method = 'keywords_moderate'
                    print(f"      → {refined_domain} (keyword count={keyword_count}, conf={refined_confidence:.3f})")

                else:
                    print(f"      → Remains Unknown (weak evidence: TF-IDF={tfidf_sim:.3f}, keywords={keyword_count})")

            elif tfidf_sim >= 0.10:
                refined_domain = tfidf_domain
                refined_confidence = min(tfidf_sim * 1.5, 0.60)
                refinement_method = 'tfidf_only'
                print(f"      → {refined_domain} (TF-IDF only, conf={refined_confidence:.3f})")
            else:
                print(f"      → Remains Unknown (TF-IDF too weak: {tfidf_sim:.3f})")
        else:
            print(f"      → Remains Unknown (no analysis data)")

        # Create refined classification
        refined_classification = classification.copy()
        refined_classification['primary_domain'] = refined_domain
        refined_classification['confidence'] = refined_confidence
        refined_classification['refinement_method'] = refinement_method
        refined_classification['original_domain'] = 'Unknown'

        if analysis:
            refined_classification['tfidf_analysis'] = analysis
        if keyword_match:
            refined_classification['keyword_analysis'] = keyword_match

        refined_classifications.append(refined_classification)

print(f"\n✅ Refined {len([c for c in refined_classifications if c.get('refinement_method')])} Unknown clusters")

# ============================================================================
# STEP 5: Final Domain Distribution
# ============================================================================

print("\n" + "="*80)
print("STEP 5: FINAL DOMAIN DISTRIBUTION")
print("="*80)

# Count final domains
final_domain_counts = {}
for classification in refined_classifications:
    domain = classification['primary_domain']
    final_domain_counts[domain] = final_domain_counts.get(domain, 0) + 1

print(f"\n📊 Final Domain Distribution (After Refinement):")
print(f"{'Domain':<20} {'Clusters':<10} {'Percentage'}")
print("-" * 50)

for domain in sorted(final_domain_counts.keys(), key=lambda x: final_domain_counts[x], reverse=True):
    count = final_domain_counts[domain]
    pct = count / len(refined_classifications) * 100
    cluster_ids = [c['cluster_id'] for c in refined_classifications if c['primary_domain'] == domain]
    print(f"{domain:<20} {count:<10} {pct:>5.1f}%  {cluster_ids}")

# Comparison
original_unknown = len(unknown_clusters)
final_unknown = final_domain_counts.get('Unknown', 0)
refined_count = original_unknown - final_unknown

print(f"\n📈 Refinement Impact:")
print(f"   Original Unknown: {original_unknown}/15 ({original_unknown/15*100:.1f}%)")
print(f"   Final Unknown: {final_unknown}/15 ({final_unknown/15*100:.1f}%)")
print(f"   Successfully refined: {refined_count} clusters")

# ============================================================================
# STEP 6: Validate Classified Clusters
# ============================================================================

print("\n" + "="*80)
print("STEP 6: VALIDATE CLASSIFIED CLUSTERS")
print("="*80)

validation_results = []

for classification in refined_classifications:
    cluster_id = classification['cluster_id']
    domain = classification['primary_domain']
    confidence = classification['confidence']

    if domain not in ['Unknown', 'Mixed']:
        print(f"\nValidating Cluster {cluster_id} ({domain}, conf={confidence:.3f}):")

        # Get cluster indicators
        cluster_vars = enriched_df[enriched_df['cluster_id'] == cluster_id]

        # Check domain coherence (% of indicators that match primary domain)
        source_dist = cluster_vars['source'].value_counts()
        category_dist = cluster_vars['category'].value_counts()

        # Source-based validation
        source_domain_map = {
            'V-Dem Institute': 'Governance',
            'UNESCO Institute for Statistics': 'Education',
            'World Bank World Development Indicators': 'Economic',
            'Penn World Table': 'Economic',
            'Penn World Table 10.0': 'Economic',
        }

        matching_sources = 0
        total_sources = 0
        for source, count in source_dist.items():
            mapped_domain = source_domain_map.get(source, 'Unknown')
            total_sources += count
            if mapped_domain == domain or mapped_domain == 'Unknown':
                matching_sources += count

        source_coherence = matching_sources / total_sources if total_sources > 0 else 0

        # Category-based validation
        category_coherence = category_dist.get(domain, 0) / len(cluster_vars) if len(cluster_vars) > 0 else 0

        print(f"   Source coherence: {source_coherence*100:.1f}% ({matching_sources}/{total_sources})")
        print(f"   Category coherence: {category_coherence*100:.1f}%")

        # Overall validation
        overall_coherence = (source_coherence + category_coherence) / 2

        if overall_coherence >= 0.70:
            validation_status = 'STRONG'
        elif overall_coherence >= 0.50:
            validation_status = 'MODERATE'
        else:
            validation_status = 'WEAK'

        print(f"   Overall coherence: {overall_coherence*100:.1f}% → {validation_status}")

        validation_results.append({
            'cluster_id': cluster_id,
            'primary_domain': domain,
            'confidence': confidence,
            'source_coherence': source_coherence,
            'category_coherence': category_coherence,
            'overall_coherence': overall_coherence,
            'validation_status': validation_status
        })

print(f"\n✅ Validated {len(validation_results)} classified clusters")

# Summary
validation_summary = {
    'STRONG': sum(1 for v in validation_results if v['validation_status'] == 'STRONG'),
    'MODERATE': sum(1 for v in validation_results if v['validation_status'] == 'MODERATE'),
    'WEAK': sum(1 for v in validation_results if v['validation_status'] == 'WEAK')
}

print(f"\n📊 Validation Summary:")
print(f"   STRONG (≥70%): {validation_summary['STRONG']} clusters")
print(f"   MODERATE (50-70%): {validation_summary['MODERATE']} clusters")
print(f"   WEAK (<50%): {validation_summary['WEAK']} clusters")

# ============================================================================
# STEP 7: Generate Cluster Narratives
# ============================================================================

print("\n" + "="*80)
print("STEP 7: GENERATE CLUSTER NARRATIVES")
print("="*80)

cluster_narratives = []

for classification in refined_classifications:
    cluster_id = classification['cluster_id']
    domain = classification['primary_domain']
    confidence = classification['confidence']

    cluster_vars = enriched_df[enriched_df['cluster_id'] == cluster_id]

    # Sample indicators
    sample_indicators = cluster_vars.head(5)['full_name'].tolist()

    # Generate narrative
    if domain == 'Unknown':
        narrative = f"Cluster {cluster_id} contains {len(cluster_vars)} mechanisms with unclear domain classification. "
        narrative += f"Primary indicators include: {', '.join(sample_indicators[:3])}. "
        narrative += "Further investigation or expert review recommended."

    elif domain == 'Mixed':
        narrative = f"Cluster {cluster_id} is a multi-domain cluster with {len(cluster_vars)} mechanisms. "
        narrative += f"Represents cross-cutting themes. Key indicators: {', '.join(sample_indicators[:3])}."

    else:
        narrative = f"Cluster {cluster_id} represents {domain} mechanisms ({len(cluster_vars)} indicators, {confidence*100:.1f}% confidence). "
        narrative += f"Key indicators include: {', '.join(sample_indicators[:3])}."

        if classification.get('literature_match'):
            narrative += f" Aligned with '{classification['literature_match']}' literature construct."

    cluster_narratives.append({
        'cluster_id': cluster_id,
        'narrative': narrative,
        'sample_indicators': sample_indicators
    })

    print(f"\nCluster {cluster_id}:")
    print(f"   {narrative}")

print(f"\n✅ Generated narratives for {len(cluster_narratives)} clusters")

# ============================================================================
# STEP 8: Save Part 3 Checkpoint
# ============================================================================

print("\n" + "="*80)
print("STEP 8: SAVE PART 3 CHECKPOINT")
print("="*80)

# Create Part 3 checkpoint
part3_checkpoint = {
    # Previous data
    **checkpoint,

    # Part 3 data
    'refined_classifications': refined_classifications,
    'unknown_cluster_analyses': unknown_cluster_analyses,
    'keyword_match_results': keyword_match_results,
    'validation_results': validation_results,
    'cluster_narratives': cluster_narratives,

    # Update enriched dataframe with refined domains
    'enriched_dataframe': enriched_df,
    'enriched_cluster_metadata': enriched_cluster_metadata,

    # Metadata
    'part_3_complete': True,
    'final_unknown_count': final_unknown,
    'refinement_count': refined_count,
    'validation_summary': validation_summary
}

# Update dataframe with refined domains
for classification in refined_classifications:
    cluster_id = classification['cluster_id']
    domain = classification['primary_domain']
    enriched_df.loc[enriched_df['cluster_id'] == cluster_id, 'primary_domain'] = domain
    enriched_df.loc[enriched_df['cluster_id'] == cluster_id, 'domain_confidence'] = classification['confidence']

part3_checkpoint['enriched_dataframe'] = enriched_df

# Update cluster metadata
for cluster_info in enriched_cluster_metadata:
    cluster_id = cluster_info['cluster_id']
    classification = next(c for c in refined_classifications if c['cluster_id'] == cluster_id)

    cluster_info['primary_domain'] = classification['primary_domain']
    cluster_info['domain_confidence'] = classification['confidence']
    cluster_info['refinement_method'] = classification.get('refinement_method', 'original')

part3_checkpoint['enriched_cluster_metadata'] = enriched_cluster_metadata

# Save checkpoint
checkpoint_path = project_root / 'phaseB/B3_domain_classification/outputs/B3_part3_literature_aligned.pkl'

with open(checkpoint_path, 'wb') as f:
    pickle.dump(part3_checkpoint, f)

print(f"\n✅ Saved Part 3 checkpoint: {checkpoint_path}")
print(f"   File size: {checkpoint_path.stat().st_size / (1024**2):.2f} MB")

# Save refined classifications as JSON
refined_path = project_root / 'phaseB/B3_domain_classification/outputs/B3_refined_classifications.json'

with open(refined_path, 'w') as f:
    # Convert numpy types to native Python for JSON serialization
    refined_for_json = []
    for c in refined_classifications:
        c_clean = {k: (float(v) if isinstance(v, (np.floating, np.integer)) else v)
                   for k, v in c.items()
                   if k not in ['tfidf_analysis', 'keyword_analysis']}  # Exclude complex nested structures
        refined_for_json.append(c_clean)
    json.dump(refined_for_json, f, indent=2)

print(f"✅ Saved refined classifications: {refined_path}")

# Save cluster narratives
narratives_path = project_root / 'phaseB/B3_domain_classification/outputs/B3_cluster_narratives.json'

with open(narratives_path, 'w') as f:
    json.dump(cluster_narratives, f, indent=2)

print(f"✅ Saved cluster narratives: {narratives_path}")

# Save updated assignments CSV
csv_path = project_root / 'phaseB/B3_domain_classification/outputs/B3_literature_aligned_assignments.csv'
enriched_df.to_csv(csv_path, index=False)

print(f"✅ Saved literature-aligned assignments: {csv_path}")

# ============================================================================
# PART 3 COMPLETION SUMMARY
# ============================================================================

print("\n" + "="*80)
print("PART 3 COMPLETION SUMMARY")
print("="*80)

print(f"\n✅ Literature alignment complete:")
print(f"   Original Unknown: {original_unknown}/15 ({original_unknown/15*100:.1f}%)")
print(f"   Final Unknown: {final_unknown}/15 ({final_unknown/15*100:.1f}%)")
print(f"   Successfully refined: {refined_count} clusters")

print(f"\n📊 Final Domain Distribution:")
for domain in sorted(final_domain_counts.keys(), key=lambda x: final_domain_counts[x], reverse=True):
    count = final_domain_counts[domain]
    pct = count / len(refined_classifications) * 100
    print(f"   {domain:>20}: {count} clusters ({pct:.1f}%)")

print(f"\n📊 Validation Status:")
for status, count in validation_summary.items():
    print(f"   {status:>10}: {count} clusters")

print(f"\n📁 Outputs Created:")
print(f"   1. B3_part3_literature_aligned.pkl - Complete checkpoint")
print(f"   2. B3_refined_classifications.json - Refined domain labels")
print(f"   3. B3_cluster_narratives.json - Interpretable descriptions")
print(f"   4. B3_literature_aligned_assignments.csv - Final assignments")

print(f"\n🎯 Ready for Part 4: Cluster Metadata Enrichment")
print(f"   Will add detailed cluster descriptions and hierarchical labels")

print("\n" + "="*80)
print("✅ PART 3 COMPLETE")
print("="*80)
