#!/usr/bin/env python3
"""
B4 Task 3: Multi-Level Pruning
===============================

Create 3 graph versions using SHAP-based pruning:
- Full (L1-2): All 290 mechanisms (academic/expert)
- Professional (L3): Top 40% by SHAP (~116 mechanisms)
- Simplified (L4-5): Top 3-4 sub-domains (~50 mechanisms)

Maintain domain balance: 40% Gov, 40% Edu, 20% Other

Author: B4 Task 3
Date: November 2025
"""

import pickle
import json
from pathlib import Path
import numpy as np
import pandas as pd
import networkx as nx
from datetime import datetime
from collections import defaultdict

# ============================================================================
# Setup
# ============================================================================

project_root = Path(__file__).resolve().parents[3]
b4_dir = project_root / 'phaseB/B4_multi_level_pruning'
outputs_dir = b4_dir / 'outputs'

print("="*80)
print("B4 TASK 3: MULTI-LEVEL PRUNING")
print("="*80)
print(f"\nTimestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"Estimated duration: 1-2 hours")

# ============================================================================
# Step 1: Load SHAP Scores and Prepared Data
# ============================================================================

print("\n" + "="*80)
print("STEP 1: LOAD SHAP SCORES AND DATA")
print("="*80)

# Load SHAP scores
shap_path = outputs_dir / 'B4_shap_scores.pkl'
print(f"\nLoading SHAP scores: {shap_path}")

with open(shap_path, 'rb') as f:
    shap_data = pickle.load(f)

mechanism_shap_scores = shap_data['mechanism_shap_scores']
cluster_shap_scores = shap_data['cluster_shap_scores']

print(f"✅ Loaded SHAP scores:")
print(f"   - Mechanisms: {len(mechanism_shap_scores)}")
print(f"   - Clusters: {len(cluster_shap_scores)}")
print(f"   - Mean SHAP: {np.mean(list(mechanism_shap_scores.values())):.4f}")

# Load prepared data
prepared_path = outputs_dir / 'B4_prepared_data.pkl'
print(f"\nLoading prepared data: {prepared_path}")

with open(prepared_path, 'rb') as f:
    prepared_data = pickle.load(f)

# Extract nested structure
b3_clusters = prepared_data['b3_data']['classified_clusters']
subgraph = prepared_data['graph']['subgraph']
effects_df = prepared_data['effects']['subgraph_effects']

print(f"✅ Loaded prepared data:")
print(f"   - B3 clusters: {len(b3_clusters)}")
print(f"   - Subgraph nodes: {subgraph.number_of_nodes()}")
print(f"   - Subgraph edges: {subgraph.number_of_edges()}")

# ============================================================================
# Step 2: Create Mechanism Metadata with SHAP and Domain
# ============================================================================

print("\n" + "="*80)
print("STEP 2: CREATE MECHANISM METADATA")
print("="*80)

# Build mechanism -> cluster mapping
mechanism_to_cluster = {}
cluster_to_mechanisms = defaultdict(list)

for cluster in b3_clusters:
    cluster_id = cluster['cluster_id']
    for mechanism in cluster['nodes']:
        mechanism_to_cluster[mechanism] = cluster_id
        cluster_to_mechanisms[cluster_id].append(mechanism)

# Create mechanism metadata table
mechanism_metadata = []

for mechanism, shap_score in mechanism_shap_scores.items():
    cluster_id = mechanism_to_cluster.get(mechanism)

    if cluster_id is not None:
        # Find cluster info
        cluster_info = next((c for c in b3_clusters if c['cluster_id'] == cluster_id), None)

        if cluster_info:
            hierarchical_label = cluster_info['hierarchical_label']

            # Parse domain from hierarchical label
            if ':' in hierarchical_label:
                domain = hierarchical_label.split(':')[0].strip()
                subdomain = hierarchical_label.split(':')[1].strip()
            else:
                domain = hierarchical_label
                subdomain = 'General'

            mechanism_metadata.append({
                'mechanism': mechanism,
                'shap_score': shap_score,
                'cluster_id': cluster_id,
                'domain': domain,
                'subdomain': subdomain,
                'hierarchical_label': hierarchical_label
            })

# Convert to DataFrame and sort by SHAP
mech_df = pd.DataFrame(mechanism_metadata)
mech_df = mech_df.sort_values('shap_score', ascending=False).reset_index(drop=True)

print(f"\n✅ Mechanism Metadata Created:")
print(f"   - Total mechanisms: {len(mech_df)}")
print(f"\n📊 Domain Distribution:")
print(mech_df['domain'].value_counts())

print(f"\n📊 Top 10 Mechanisms by SHAP:")
print(mech_df[['mechanism', 'shap_score', 'domain', 'subdomain']].head(10).to_string(index=False))

# ============================================================================
# Step 3: Create Full Graph (L1-2)
# ============================================================================

print("\n" + "="*80)
print("STEP 3: CREATE FULL GRAPH (L1-2)")
print("="*80)

# Full graph = all 290 mechanisms
full_mechanisms = set(mech_df['mechanism'].tolist())

# Extract subgraph with only these mechanisms
full_graph = subgraph.subgraph(full_mechanisms).copy()

print(f"\n✅ Full Graph Created:")
print(f"   - Nodes: {full_graph.number_of_nodes()}")
print(f"   - Edges: {full_graph.number_of_edges()}")
print(f"   - Target audience: Academic/Expert")
print(f"   - Use case: Research, methodology transparency")

# Domain balance
full_domains = mech_df['domain'].value_counts(normalize=True)
print(f"\n📊 Full Graph Domain Balance:")
for domain, pct in full_domains.items():
    print(f"   - {domain}: {pct:.1%}")

# ============================================================================
# Step 4: Create Professional Graph (L3) - Top 40% by SHAP
# ============================================================================

print("\n" + "="*80)
print("STEP 4: CREATE PROFESSIONAL GRAPH (L3)")
print("="*80)

# Target: Top 40% of mechanisms
target_count_professional = int(len(mech_df) * 0.40)
print(f"\nTarget: {target_count_professional} mechanisms (40% of {len(mech_df)})")

# Strategy: Domain-balanced selection
# Target balance: 40% Gov, 40% Edu, 20% Other

# Count mechanisms by domain
domain_counts = mech_df['domain'].value_counts()
print(f"\n📊 Available Mechanisms by Domain:")
for domain, count in domain_counts.items():
    print(f"   - {domain}: {count}")

# Calculate target counts per domain (40/40/20 balance)
gov_target = int(target_count_professional * 0.40)
edu_target = int(target_count_professional * 0.40)
other_target = target_count_professional - gov_target - edu_target

print(f"\n📊 Target Allocation (40/40/20):")
print(f"   - Governance: {gov_target} (40%)")
print(f"   - Education: {edu_target} (40%)")
print(f"   - Other: {other_target} (20%)")

# Select top mechanisms per domain
selected_professional = []

# Governance
gov_mechs = mech_df[mech_df['domain'] == 'Governance'].head(gov_target)
selected_professional.append(gov_mechs)
print(f"\n✅ Selected Governance: {len(gov_mechs)} mechanisms")

# Education
edu_mechs = mech_df[mech_df['domain'] == 'Education'].head(edu_target)
selected_professional.append(edu_mechs)
print(f"✅ Selected Education: {len(edu_mechs)} mechanisms")

# Other (Economic, Mixed, etc.)
other_mechs = mech_df[~mech_df['domain'].isin(['Governance', 'Education'])].head(other_target)
selected_professional.append(other_mechs)
print(f"✅ Selected Other: {len(other_mechs)} mechanisms")

# Combine
professional_df = pd.concat(selected_professional, ignore_index=True)
professional_mechanisms = set(professional_df['mechanism'].tolist())

# Extract subgraph
professional_graph = subgraph.subgraph(professional_mechanisms).copy()

print(f"\n✅ Professional Graph Created:")
print(f"   - Nodes: {professional_graph.number_of_nodes()}")
print(f"   - Edges: {professional_graph.number_of_edges()}")
print(f"   - Target audience: Policy analysts, practitioners")
print(f"   - Use case: Scenario testing, policy simulation")

# Domain balance
prof_domains = professional_df['domain'].value_counts(normalize=True)
print(f"\n📊 Professional Graph Domain Balance:")
for domain, pct in prof_domains.items():
    print(f"   - {domain}: {pct:.1%}")

# SHAP retention
professional_shap_sum = professional_df['shap_score'].sum()
full_shap_sum = mech_df['shap_score'].sum()
shap_retention_professional = professional_shap_sum / full_shap_sum

print(f"\n📊 SHAP Retention:")
print(f"   - Professional SHAP: {professional_shap_sum:.4f}")
print(f"   - Full SHAP: {full_shap_sum:.4f}")
print(f"   - Retention: {shap_retention_professional:.1%}")

# ============================================================================
# Step 5: Create Simplified Graph (L4-5) - Top 3-4 Sub-Domains
# ============================================================================

print("\n" + "="*80)
print("STEP 5: CREATE SIMPLIFIED GRAPH (L4-5)")
print("="*80)

# Strategy: Select top 3-4 sub-domains by aggregate SHAP
# Target: ~50 mechanisms total

# Calculate aggregate SHAP by sub-domain
subdomain_shap = mech_df.groupby('hierarchical_label')['shap_score'].agg(['sum', 'count']).reset_index()
subdomain_shap = subdomain_shap.sort_values('sum', ascending=False)

print(f"\n📊 Top 10 Sub-Domains by Aggregate SHAP:")
print(subdomain_shap.head(10).to_string(index=False))

# Strategy: Select top sub-domains while maintaining some domain diversity
# Aim for 3-4 sub-domains across different domains
selected_subdomains = []
selected_count = 0
target_count_simplified = 50
min_subdomains = 3

# Track domains already selected
selected_domains = set()

for _, row in subdomain_shap.iterrows():
    # Stop if we have enough mechanisms and at least min_subdomains
    if selected_count >= target_count_simplified and len(selected_subdomains) >= min_subdomains:
        break

    # Parse domain from hierarchical label
    domain = row['hierarchical_label'].split(':')[0].strip()

    # Prefer diversity: skip if domain already represented unless we need more mechanisms
    if domain in selected_domains and selected_count >= target_count_simplified * 0.6:
        continue

    selected_subdomains.append(row['hierarchical_label'])
    selected_domains.add(domain)
    selected_count += row['count']

    print(f"\n✅ Selected: {row['hierarchical_label']}")
    print(f"   - Aggregate SHAP: {row['sum']:.4f}")
    print(f"   - Mechanisms: {int(row['count'])}")
    print(f"   - Cumulative: {selected_count}")

# Extract mechanisms from selected sub-domains
simplified_df = mech_df[mech_df['hierarchical_label'].isin(selected_subdomains)]
simplified_mechanisms = set(simplified_df['mechanism'].tolist())

# Extract subgraph
simplified_graph = subgraph.subgraph(simplified_mechanisms).copy()

print(f"\n✅ Simplified Graph Created:")
print(f"   - Sub-domains: {len(selected_subdomains)}")
print(f"   - Nodes: {simplified_graph.number_of_nodes()}")
print(f"   - Edges: {simplified_graph.number_of_edges()}")
print(f"   - Target audience: General public, engaged citizens")
print(f"   - Use case: Storytelling, plain language explanations")

# Domain balance
simp_domains = simplified_df['domain'].value_counts(normalize=True)
print(f"\n📊 Simplified Graph Domain Balance:")
for domain, pct in simp_domains.items():
    print(f"   - {domain}: {pct:.1%}")

# SHAP retention
simplified_shap_sum = simplified_df['shap_score'].sum()
shap_retention_simplified = simplified_shap_sum / full_shap_sum

print(f"\n📊 SHAP Retention:")
print(f"   - Simplified SHAP: {simplified_shap_sum:.4f}")
print(f"   - Full SHAP: {full_shap_sum:.4f}")
print(f"   - Retention: {shap_retention_simplified:.1%}")

# ============================================================================
# Step 6: Save Pruned Graphs
# ============================================================================

print("\n" + "="*80)
print("STEP 6: SAVE PRUNED GRAPHS")
print("="*80)

pruned_graphs = {
    'metadata': {
        'timestamp': datetime.now().isoformat(),
        'task': 'B4_task3_multi_level_pruning',
        'version': '2.0',
        'method': 'SHAP-based pruning with domain balance'
    },
    'full_graph': {
        'graph': full_graph,
        'mechanisms': list(full_mechanisms),
        'mechanism_df': mech_df,
        'node_count': full_graph.number_of_nodes(),
        'edge_count': full_graph.number_of_edges(),
        'domain_balance': full_domains.to_dict(),
        'shap_sum': float(full_shap_sum),
        'target_audience': 'Academic/Expert',
        'level': 'L1-2'
    },
    'professional_graph': {
        'graph': professional_graph,
        'mechanisms': list(professional_mechanisms),
        'mechanism_df': professional_df,
        'node_count': professional_graph.number_of_nodes(),
        'edge_count': professional_graph.number_of_edges(),
        'domain_balance': prof_domains.to_dict(),
        'shap_sum': float(professional_shap_sum),
        'shap_retention': float(shap_retention_professional),
        'target_audience': 'Policy Analysts',
        'level': 'L3'
    },
    'simplified_graph': {
        'graph': simplified_graph,
        'mechanisms': list(simplified_mechanisms),
        'mechanism_df': simplified_df,
        'selected_subdomains': selected_subdomains,
        'node_count': simplified_graph.number_of_nodes(),
        'edge_count': simplified_graph.number_of_edges(),
        'domain_balance': simp_domains.to_dict(),
        'shap_sum': float(simplified_shap_sum),
        'shap_retention': float(shap_retention_simplified),
        'target_audience': 'General Public',
        'level': 'L4-5'
    }
}

# Save to pickle
pruned_path = outputs_dir / 'B4_pruned_graphs.pkl'
with open(pruned_path, 'wb') as f:
    pickle.dump(pruned_graphs, f)

print(f"\n✅ Saved pruned graphs: {pruned_path}")
print(f"   - File size: {pruned_path.stat().st_size / 1024:.1f} KB")

# Save summary to JSON (without graph objects)
summary = {
    'metadata': pruned_graphs['metadata'],
    'full_graph': {k: v for k, v in pruned_graphs['full_graph'].items() if k not in ['graph', 'mechanism_df']},
    'professional_graph': {k: v for k, v in pruned_graphs['professional_graph'].items() if k not in ['graph', 'mechanism_df']},
    'simplified_graph': {k: v for k, v in pruned_graphs['simplified_graph'].items() if k not in ['graph', 'mechanism_df']}
}

summary_path = outputs_dir / 'B4_pruning_summary.json'
with open(summary_path, 'w') as f:
    json.dump(summary, f, indent=2)

print(f"✅ Saved pruning summary: {summary_path}")

# ============================================================================
# Summary
# ============================================================================

print("\n" + "="*80)
print("TASK 3 COMPLETE - MULTI-LEVEL PRUNING SUMMARY")
print("="*80)

print(f"\n📊 Graph Statistics:")
print(f"\n{'Graph':<15} {'Nodes':<8} {'Edges':<8} {'SHAP Retention':<15} {'Audience':<20}")
print(f"{'-'*15} {'-'*8} {'-'*8} {'-'*15} {'-'*20}")
print(f"{'Full':<15} {full_graph.number_of_nodes():<8} {full_graph.number_of_edges():<8} {'100.0%':<15} {'Academic/Expert':<20}")
print(f"{'Professional':<15} {professional_graph.number_of_nodes():<8} {professional_graph.number_of_edges():<8} {f'{shap_retention_professional:.1%}':<15} {'Policy Analysts':<20}")
print(f"{'Simplified':<15} {simplified_graph.number_of_nodes():<8} {simplified_graph.number_of_edges():<8} {f'{shap_retention_simplified:.1%}':<15} {'General Public':<20}")

print(f"\n📊 Domain Balance:")
print(f"\n{'Graph':<15} {'Governance':<12} {'Education':<12} {'Other':<12}")
print(f"{'-'*15} {'-'*12} {'-'*12} {'-'*12}")
print(f"{'Full':<15} {full_domains.get('Governance', 0):.1%}         {full_domains.get('Education', 0):.1%}         {full_domains.get('Economic', 0) + full_domains.get('Mixed', 0):.1%}")
print(f"{'Professional':<15} {prof_domains.get('Governance', 0):.1%}         {prof_domains.get('Education', 0):.1%}         {prof_domains.get('Economic', 0) + prof_domains.get('Mixed', 0):.1%}")
print(f"{'Simplified':<15} {simp_domains.get('Governance', 0):.1%}         {simp_domains.get('Education', 0):.1%}         {simp_domains.get('Economic', 0) + simp_domains.get('Mixed', 0):.1%}")

print(f"\n✅ All 3 graph versions created successfully")
print(f"🎯 Next Step: Task 3.5 - Domain Balance & Edge Integrity Validation (20 min)")

print("\n" + "="*80)
print("✅ TASK 3 COMPLETE")
print("="*80)
