#!/usr/bin/env python3
"""
Part 4: Cluster Metadata Enrichment
====================================

Add hierarchical domain labels, detailed descriptions, and cross-references.

Inputs:
- B3_part3_manual_overrides.pkl (from Part 3 + manual overrides)
- metadata/unified_metadata.json (from Part 1)
- literature_db/literature_constructs.json

Outputs:
- B3_part4_enriched.pkl (enriched cluster metadata)
- B3_cluster_reports/ (individual cluster reports)
- B3_hierarchical_domains.json (domain taxonomy)

Author: B3 Part 4
Date: November 2025
"""

import pickle
import json
from pathlib import Path
from collections import defaultdict
import pandas as pd
import numpy as np

project_root = Path(__file__).resolve().parents[3]

print("="*80)
print("PART 4: CLUSTER METADATA ENRICHMENT")
print("="*80)

# ============================================================================
# Load Part 3 Checkpoint
# ============================================================================

print("\n" + "="*80)
print("LOADING PART 3 CHECKPOINT")
print("="*80)

checkpoint_path = project_root / 'phaseB/B3_domain_classification/outputs/B3_part3_manual_overrides.pkl'

print(f"\nLoading: {checkpoint_path}")

with open(checkpoint_path, 'rb') as f:
    checkpoint = pickle.load(f)

enriched_df = checkpoint['enriched_dataframe']
enriched_cluster_metadata = checkpoint['enriched_cluster_metadata']
refined_classifications = checkpoint['refined_classifications']

print(f"✅ Loaded Part 3 checkpoint")
print(f"   Clusters: {len(enriched_cluster_metadata)}")
print(f"   Mechanisms: {len(enriched_df)}")
print(f"   Classifications: {len(refined_classifications)}")

# Load unified metadata from checkpoint (was created in Part 1)
if 'unified_metadata' in checkpoint:
    unified_metadata = checkpoint['unified_metadata']
    print(f"✅ Loaded unified metadata from checkpoint: {len(unified_metadata)} indicators")
else:
    # Fallback: Try loading from file
    metadata_path = project_root / 'phaseB/B3_domain_classification/metadata/unified_metadata.json'

    if metadata_path.exists():
        with open(metadata_path, 'r') as f:
            unified_metadata = json.load(f)
        print(f"✅ Loaded unified metadata from file: {len(unified_metadata)} indicators")
    else:
        # Last resort: Extract from enriched_df
        print("⚠️  Creating unified metadata from enriched_df...")
        unified_metadata = {}
        for _, row in enriched_df.iterrows():
            unified_metadata[row['node']] = {
                'full_name': row.get('full_name', row['node']),
                'description': row.get('description', ''),
                'source': row.get('source', ''),
                'domain': row.get('domain', 'Unknown'),
                'metadata_quality': row.get('metadata_quality', 'inferred')
            }
        print(f"✅ Created unified metadata from enriched_df: {len(unified_metadata)} indicators")

# Load literature constructs
lit_path = project_root / 'literature_db/literature_constructs.json'

with open(lit_path, 'r') as f:
    literature_constructs = json.load(f)

print(f"✅ Loaded literature constructs: {len(literature_constructs)} constructs")

# ============================================================================
# Task 4.1: Define Hierarchical Domain Structure
# ============================================================================

print("\n" + "="*80)
print("TASK 4.1: HIERARCHICAL DOMAIN STRUCTURE")
print("="*80)

# Define hierarchical taxonomy
hierarchical_domains = {
    "Governance": {
        "description": "Institutions, rule of law, democracy, human rights, and government effectiveness",
        "sub_domains": {
            "Judicial": ["courts", "legal", "independence", "judiciary"],
            "Legislative": ["parliament", "legislature", "lawmaking"],
            "Executive": ["government", "executive", "administration"],
            "Electoral": ["elections", "voting", "democracy", "electoral"],
            "Civil Liberties": ["rights", "freedom", "civil liberties", "human rights"],
            "Transparency": ["transparency", "corruption", "accountability"],
            "Tax & Revenue": ["tax", "revenue", "fiscal", "ictd"]
        },
        "keywords": ["polity", "democracy", "governance", "institutional", "rule of law", "corruption", "transparency", "vdem"]
    },
    "Education": {
        "description": "Educational access, quality, attainment, enrollment, and outcomes",
        "sub_domains": {
            "Primary": ["primary", "elementary", "basic education"],
            "Secondary": ["secondary", "high school"],
            "Tertiary": ["tertiary", "university", "higher education"],
            "Enrollment": ["enrollment", "attendance", "participation", "ner", "ger"],
            "Attainment": ["completion", "attainment", "graduation", "literacy"],
            "Quality": ["teachers", "trained", "quality", "learning outcomes"],
            "Finance": ["expenditure", "spending", "finance", "budget"]
        },
        "keywords": ["education", "school", "literacy", "enrollment", "unesco", "attainment", "completion"]
    },
    "Economic": {
        "description": "Economic development, trade, investment, technology, and growth",
        "sub_domains": {
            "Development": ["gdp", "growth", "development", "income"],
            "Trade": ["trade", "exports", "imports", "commerce"],
            "Investment": ["investment", "capital", "fdi"],
            "Technology": ["technology", "innovation", "digital", "mobile", "internet"],
            "Labor": ["employment", "labor", "workforce", "unemployment"],
            "Fiscal": ["fiscal", "budget", "spending"]
        },
        "keywords": ["economic", "gdp", "trade", "investment", "technology", "mobile", "internet", "wdi"]
    },
    "Health": {
        "description": "Health outcomes, healthcare access, disease burden, and vital statistics",
        "sub_domains": {
            "Maternal": ["maternal", "pregnancy", "childbirth"],
            "Child": ["child", "infant", "neonatal", "under-5"],
            "Life Expectancy": ["life expectancy", "mortality", "longevity"],
            "Disease": ["disease", "morbidity", "illness", "epidemic"],
            "Healthcare": ["healthcare", "doctors", "physicians", "hospitals"]
        },
        "keywords": ["health", "mortality", "life expectancy", "disease", "maternal", "who"]
    },
    "Environment": {
        "description": "Environmental quality, natural resources, and sustainability",
        "sub_domains": {
            "Climate": ["climate", "temperature", "emissions"],
            "Resources": ["resources", "natural", "extraction", "gas", "oil"],
            "Pollution": ["pollution", "air quality", "environmental"],
            "Conservation": ["conservation", "biodiversity", "protected areas"]
        },
        "keywords": ["environment", "climate", "emissions", "resources", "gas", "oil"]
    },
    "Unclassified": {
        "description": "Variables with no discernible pattern or interpretable meaning",
        "sub_domains": {},
        "keywords": ["999", "unknown", "random"]
    },
    "Mixed": {
        "description": "Cross-cutting themes spanning multiple domains",
        "sub_domains": {
            "Human Capital": ["human capital", "development"],
            "Inequality": ["inequality", "disparity", "gap", "quintile"],
            "Conflict": ["conflict", "violence", "fragility"]
        },
        "keywords": ["multi-domain", "cross-cutting", "composite"]
    }
}

print(f"\n✅ Defined hierarchical taxonomy:")
for domain, info in hierarchical_domains.items():
    print(f"   {domain}: {len(info['sub_domains'])} sub-domains")

# ============================================================================
# Task 4.2: Assign Sub-Domains to Each Cluster
# ============================================================================

print("\n" + "="*80)
print("TASK 4.2: ASSIGN SUB-DOMAINS")
print("="*80)

def assign_sub_domain(cluster_id, primary_domain, cluster_metadata_row, enriched_df_subset):
    """Assign sub-domain based on variable names and descriptions"""

    if primary_domain not in hierarchical_domains:
        return "General"

    domain_info = hierarchical_domains[primary_domain]
    sub_domains = domain_info['sub_domains']

    if not sub_domains:
        return "General"

    # Get all text for this cluster
    cluster_variables = enriched_df_subset['node'].tolist()
    cluster_texts = []

    for var in cluster_variables:
        if var in unified_metadata:
            meta = unified_metadata[var]
            text = f"{meta.get('full_name', '')} {meta.get('description', '')} {var}".lower()
            cluster_texts.append(text)
        else:
            cluster_texts.append(var.lower())

    combined_text = " ".join(cluster_texts)

    # Score each sub-domain
    sub_domain_scores = {}

    for sub_name, keywords in sub_domains.items():
        score = sum(1 for kw in keywords if kw in combined_text)
        sub_domain_scores[sub_name] = score

    # Assign best match
    if sub_domain_scores and max(sub_domain_scores.values()) > 0:
        best_sub_domain = max(sub_domain_scores.items(), key=lambda x: x[1])[0]
        return best_sub_domain
    else:
        return "General"

# Assign sub-domains
print("\n📋 Assigning sub-domains to clusters:")

for cluster_info in enriched_cluster_metadata:
    cluster_id = cluster_info['cluster_id']
    primary_domain = cluster_info['primary_domain']

    # Get cluster data
    cluster_df = enriched_df[enriched_df['cluster_id'] == cluster_id]

    # Assign sub-domain
    sub_domain = assign_sub_domain(cluster_id, primary_domain, cluster_info, cluster_df)

    cluster_info['sub_domain'] = sub_domain
    cluster_info['hierarchical_label'] = f"{primary_domain}: {sub_domain}"

    print(f"   Cluster {cluster_id:>2}: {cluster_info['hierarchical_label']}")

print(f"\n✅ Assigned sub-domains to all {len(enriched_cluster_metadata)} clusters")

# ============================================================================
# Task 4.3: Create Detailed Cluster Descriptions
# ============================================================================

print("\n" + "="*80)
print("TASK 4.3: CLUSTER DESCRIPTIONS")
print("="*80)

def create_cluster_description(cluster_id, cluster_info, enriched_df_subset, unified_metadata):
    """Generate human-readable cluster description"""

    primary_domain = cluster_info['primary_domain']
    sub_domain = cluster_info.get('sub_domain', 'General')
    size = len(enriched_df_subset)

    # Get top variables
    cluster_vars = enriched_df_subset['node'].tolist()

    # Sample 3-5 representative variables
    sample_size = min(5, len(cluster_vars))
    sample_vars = cluster_vars[:sample_size]

    examples = []
    for var in sample_vars:
        if var in unified_metadata:
            full_name = unified_metadata[var].get('full_name', var)
            examples.append(full_name)
        else:
            examples.append(var)

    # Build description
    if primary_domain == "Unclassified":
        description = f"A collection of {size} variables with no discernible pattern or interpretable meaning. These are likely data quality issues or deprecated indicators."
    elif primary_domain == "Mixed":
        description = f"A cross-cutting cluster of {size} mechanisms spanning multiple domains ({sub_domain}). "
        description += f"Examples include: {', '.join(examples[:3])}."
    else:
        description = f"A cluster of {size} mechanisms related to {primary_domain.lower()} ({sub_domain.lower()}). "
        description += f"Representative indicators include: {', '.join(examples[:3])}."

    return description

# Add descriptions
print("\n📝 Creating cluster descriptions:")

for cluster_info in enriched_cluster_metadata:
    cluster_id = cluster_info['cluster_id']
    cluster_df = enriched_df[enriched_df['cluster_id'] == cluster_id]

    description = create_cluster_description(cluster_id, cluster_info, cluster_df, unified_metadata)

    cluster_info['description'] = description

    print(f"\n   Cluster {cluster_id}: {cluster_info['hierarchical_label']}")
    print(f"   {description[:150]}...")

print(f"\n✅ Created descriptions for all {len(enriched_cluster_metadata)} clusters")

# ============================================================================
# Task 4.4: Add Top Variables by Metadata Quality
# ============================================================================

print("\n" + "="*80)
print("TASK 4.4: TOP VARIABLES")
print("="*80)

def get_top_variables(cluster_id, enriched_df_subset, unified_metadata, n=5):
    """Get top N variables for this cluster"""

    cluster_vars = enriched_df_subset['node'].tolist()

    # Score variables by metadata quality + position
    var_scores = []

    for i, var in enumerate(cluster_vars):
        # Metadata quality score
        quality_score = 0
        if var in unified_metadata:
            meta = unified_metadata[var]
            if meta.get('metadata_quality') == 'high':
                quality_score = 3
            elif meta.get('metadata_quality') == 'inferred':
                quality_score = 1

        # Position score (earlier variables are more central in cluster)
        position_score = len(cluster_vars) - i

        # Combined score
        total_score = quality_score * 10 + position_score

        var_scores.append({
            'code': var,
            'name': unified_metadata.get(var, {}).get('full_name', var),
            'description': unified_metadata.get(var, {}).get('description', ''),
            'source': unified_metadata.get(var, {}).get('source', ''),
            'score': total_score
        })

    # Sort by score
    var_scores.sort(key=lambda x: x['score'], reverse=True)

    return var_scores[:n]

# Add top variables
print("\n🔝 Identifying top variables per cluster:")

for cluster_info in enriched_cluster_metadata:
    cluster_id = cluster_info['cluster_id']
    cluster_df = enriched_df[enriched_df['cluster_id'] == cluster_id]

    top_vars = get_top_variables(cluster_id, cluster_df, unified_metadata, n=5)

    cluster_info['top_variables'] = top_vars

    print(f"\n   Cluster {cluster_id}: {cluster_info['hierarchical_label']}")
    for i, var in enumerate(top_vars[:3], 1):
        print(f"      {i}. {var['name'][:60]}")

print(f"\n✅ Identified top variables for all {len(enriched_cluster_metadata)} clusters")

# ============================================================================
# Task 4.5: Add Domain Distribution per Cluster
# ============================================================================

print("\n" + "="*80)
print("TASK 4.5: DOMAIN DISTRIBUTION")
print("="*80)

print("\n📊 Computing domain distribution per cluster:")

for cluster_info in enriched_cluster_metadata:
    cluster_id = cluster_info['cluster_id']
    cluster_df = enriched_df[enriched_df['cluster_id'] == cluster_id]

    # Count domains from metadata
    domain_counts = defaultdict(int)

    for var in cluster_df['node']:
        if var in unified_metadata:
            domain = unified_metadata[var].get('domain', 'Unknown')
            domain_counts[domain] += 1
        else:
            domain_counts['Unknown'] += 1

    # Convert to dict
    cluster_info['domain_distribution'] = dict(domain_counts)

    # Calculate diversity
    total = sum(domain_counts.values())
    if total > 0:
        diversity = len([d for d, c in domain_counts.items() if c/total >= 0.20])
        cluster_info['domain_diversity'] = diversity
    else:
        cluster_info['domain_diversity'] = 0

    print(f"   Cluster {cluster_id:>2}: {dict(domain_counts)} (diversity={cluster_info['domain_diversity']})")

print(f"\n✅ Computed domain distributions")

# ============================================================================
# Task 4.6: Add Literature Cross-References
# ============================================================================

print("\n" + "="*80)
print("TASK 4.6: LITERATURE CROSS-REFERENCES")
print("="*80)

print("\n📚 Adding literature cross-references:")

for cluster_info in enriched_cluster_metadata:
    cluster_id = cluster_info['cluster_id']

    # Find classification
    classification = next((c for c in refined_classifications if c['cluster_id'] == cluster_id), None)

    if classification:
        # Add literature match info
        cluster_info['literature_match'] = {
            'construct': classification.get('best_construct', 'None'),
            'similarity': classification.get('literature_similarity', 0.0),
            'confidence': 'high' if classification.get('literature_similarity', 0) > 0.70
                         else 'moderate' if classification.get('literature_similarity', 0) > 0.40
                         else 'low'
        }

        # Add source from literature DB
        construct_name = classification.get('best_construct', '')
        if construct_name in literature_constructs:
            lit_info = literature_constructs[construct_name]
            cluster_info['literature_match']['source'] = lit_info.get('source', '')
            cluster_info['literature_match']['citation'] = lit_info.get('citation', '')
    else:
        cluster_info['literature_match'] = {
            'construct': 'None',
            'similarity': 0.0,
            'confidence': 'none'
        }

    print(f"   Cluster {cluster_id:>2}: {cluster_info['literature_match']['construct']} "
          f"(sim={cluster_info['literature_match']['similarity']:.3f}, "
          f"conf={cluster_info['literature_match']['confidence']})")

print(f"\n✅ Added literature cross-references")

# ============================================================================
# Task 4.7: Create Cluster Reports
# ============================================================================

print("\n" + "="*80)
print("TASK 4.7: CLUSTER REPORTS")
print("="*80)

reports_dir = project_root / 'phaseB/B3_domain_classification/outputs/B3_cluster_reports'
reports_dir.mkdir(exist_ok=True)

print(f"\n📄 Creating individual cluster reports:")

for cluster_info in enriched_cluster_metadata:
    cluster_id = cluster_info['cluster_id']

    # Create report
    report = f"""# Cluster {cluster_id}: {cluster_info['hierarchical_label']}

## Overview

**Primary Domain**: {cluster_info['primary_domain']}
**Sub-Domain**: {cluster_info.get('sub_domain', 'General')}
**Size**: {cluster_info['size']} mechanisms
**Coherence**: {cluster_info['coherence']:.1%}
**Domain Confidence**: {cluster_info.get('domain_confidence', 0):.1%}

## Description

{cluster_info['description']}

## Top Variables

"""

    for i, var in enumerate(cluster_info['top_variables'], 1):
        report += f"{i}. **{var['name']}**\n"
        report += f"   - Code: `{var['code']}`\n"
        report += f"   - Source: {var['source']}\n"
        if var['description']:
            report += f"   - Description: {var['description'][:100]}...\n"
        report += "\n"

    report += f"""## Domain Distribution

"""

    for domain, count in cluster_info['domain_distribution'].items():
        pct = count / cluster_info['size'] * 100
        report += f"- {domain}: {count} ({pct:.1f}%)\n"

    report += f"""
**Domain Diversity**: {cluster_info['domain_diversity']} (number of domains with ≥20% representation)

## Literature Alignment

**Matched Construct**: {cluster_info['literature_match']['construct']}
**Similarity**: {cluster_info['literature_match']['similarity']:.3f}
**Confidence**: {cluster_info['literature_match']['confidence']}
"""

    if 'source' in cluster_info['literature_match']:
        report += f"**Source**: {cluster_info['literature_match']['source']}\n"
    if 'citation' in cluster_info['literature_match']:
        report += f"**Citation**: {cluster_info['literature_match']['citation']}\n"

    report += f"""
## Classification Method

**Decision Method**: {cluster_info.get('decision_method', 'Unknown')}
"""

    if 'override_method' in cluster_info:
        report += f"""
**Override Applied**: Yes
**Override Method**: {cluster_info['override_method']}
**Override Reason**: {cluster_info['override_reason']}
"""

    # Save report
    report_path = reports_dir / f"cluster_{cluster_id:02d}.md"

    with open(report_path, 'w') as f:
        f.write(report)

    print(f"   ✅ Cluster {cluster_id:>2}: {report_path.name}")

print(f"\n✅ Created {len(enriched_cluster_metadata)} cluster reports in: {reports_dir}")

# ============================================================================
# Task 4.8: Create Hierarchical Domains Summary
# ============================================================================

print("\n" + "="*80)
print("TASK 4.8: HIERARCHICAL DOMAINS SUMMARY")
print("="*80)

# Group clusters by domain
domain_summary = defaultdict(lambda: {
    'clusters': [],
    'n_mechanisms': 0,
    'sub_domains': defaultdict(int)
})

for cluster_info in enriched_cluster_metadata:
    domain = cluster_info['primary_domain']
    sub_domain = cluster_info.get('sub_domain', 'General')

    domain_summary[domain]['clusters'].append(cluster_info['cluster_id'])
    domain_summary[domain]['n_mechanisms'] += cluster_info['size']
    domain_summary[domain]['sub_domains'][sub_domain] += 1

# Add taxonomy info
hierarchical_summary = {}

for domain, summary in domain_summary.items():
    hierarchical_summary[domain] = {
        'description': hierarchical_domains.get(domain, {}).get('description', ''),
        'clusters': summary['clusters'],
        'n_clusters': len(summary['clusters']),
        'n_mechanisms': summary['n_mechanisms'],
        'sub_domains': dict(summary['sub_domains']),
        'keywords': hierarchical_domains.get(domain, {}).get('keywords', [])
    }

print(f"\n📊 Hierarchical Domain Summary:")
for domain, info in sorted(hierarchical_summary.items(), key=lambda x: x[1]['n_mechanisms'], reverse=True):
    print(f"\n   {domain}:")
    print(f"      Clusters: {info['n_clusters']} (IDs: {info['clusters']})")
    print(f"      Mechanisms: {info['n_mechanisms']}")
    print(f"      Sub-domains: {list(info['sub_domains'].keys())}")

# Save hierarchical summary
hierarchical_path = project_root / 'phaseB/B3_domain_classification/outputs/B3_hierarchical_domains.json'

with open(hierarchical_path, 'w') as f:
    json.dump(hierarchical_summary, f, indent=2)

print(f"\n✅ Saved hierarchical domains: {hierarchical_path}")

# ============================================================================
# Save Updated Checkpoint
# ============================================================================

print("\n" + "="*80)
print("SAVING PART 4 CHECKPOINT")
print("="*80)

# Update checkpoint
checkpoint['enriched_cluster_metadata'] = enriched_cluster_metadata
checkpoint['hierarchical_summary'] = hierarchical_summary
checkpoint['part4_complete'] = True

# Save checkpoint
output_path = project_root / 'phaseB/B3_domain_classification/outputs/B3_part4_enriched.pkl'

with open(output_path, 'wb') as f:
    pickle.dump(checkpoint, f)

print(f"\n✅ Saved Part 4 checkpoint: {output_path}")
print(f"   File size: {output_path.stat().st_size / (1024**2):.2f} MB")

# Save complete cluster metadata as JSON
metadata_path = project_root / 'phaseB/B3_domain_classification/outputs/B3_cluster_metadata_complete.json'

# Clean for JSON
cluster_metadata_clean = []
for cluster in enriched_cluster_metadata:
    cluster_clean = {k: v for k, v in cluster.items()
                     if k not in ['embeddings', 'tfidf_vectors']}
    # Convert numpy types
    for k, v in cluster_clean.items():
        if isinstance(v, (np.integer, np.floating)):
            cluster_clean[k] = float(v)
    cluster_metadata_clean.append(cluster_clean)

with open(metadata_path, 'w') as f:
    json.dump(cluster_metadata_clean, f, indent=2)

print(f"✅ Saved complete cluster metadata: {metadata_path}")

# ============================================================================
# Summary
# ============================================================================

print("\n" + "="*80)
print("PART 4 COMPLETE")
print("="*80)

print(f"""
✅ Successfully enriched all {len(enriched_cluster_metadata)} clusters with:
   - Hierarchical domain labels (Primary + Sub-domain)
   - Detailed human-readable descriptions
   - Top 5 variables per cluster
   - Domain distribution statistics
   - Literature cross-references
   - Individual cluster reports

📊 Hierarchical Domain Distribution:
""")

for domain, info in sorted(hierarchical_summary.items(), key=lambda x: x[1]['n_mechanisms'], reverse=True):
    print(f"   {domain:<15}: {info['n_clusters']} clusters, {info['n_mechanisms']} mechanisms")

print(f"""
📁 Outputs Created:
   - B3_part4_enriched.pkl (enriched checkpoint)
   - B3_cluster_metadata_complete.json (full metadata)
   - B3_hierarchical_domains.json (domain taxonomy)
   - B3_cluster_reports/ ({len(enriched_cluster_metadata)} individual reports)

🎯 Ready for Part 5: B3 Validation
   All metadata fields populated and ready for final validation checks
""")

print("\n" + "="*80)
print("✅ PART 4 ENRICHMENT COMPLETE")
print("="*80)
