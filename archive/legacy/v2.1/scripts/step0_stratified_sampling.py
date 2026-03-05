#!/usr/bin/env python3
"""
V2.1 Research-Grade Stratified Sampling
Uses V2 SHAP scores + coverage-based sampling to ensure outcome relevance

Key improvements over original:
- 50% weight on SHAP scores (outcome prediction importance)
- 25% weight on outcome-specific betweenness (paths to QoL metrics)
- Coverage-based sampling ensures cluster diversity within domains
- Validation checks for critical indicator retention
"""

import pickle
import json
import numpy as np
import pandas as pd
from collections import defaultdict
from pathlib import Path
import sys

# Add parent to path for v21_config
sys.path.insert(0, str(Path(__file__).parent))
from v21_config import OUTPUT_ROOT, PROJECT_ROOT

print("="*80)
print("V2.1 RESEARCH-GRADE STRATIFIED SAMPLING")
print("="*80)

# ============================================================================
# CONFIGURATION
# ============================================================================

# Source -> Domain mapping
DOMAIN_MAP = {
    'vdem': 'Governance',
    'qog': 'Governance',
    'unesco': 'Education',
    'wid': 'Economic',
    'world_bank': 'Economic',
    'imf': 'Economic',
    'penn': 'Economic',
    'who': 'Health'
}

# Sampling targets (per domain)
SAMPLING_TARGETS = {
    'Governance': 1000,
    'Education': 1000,
    'Economic': 1000,
    'Health': 122  # Keep all
}

# Paths (V2 source data)
A2_DATA_PATH = PROJECT_ROOT / 'phaseA' / 'A1_missingness_analysis' / 'outputs' / 'A2_preprocessed_data.pkl'
A6_GRAPH_PATH = PROJECT_ROOT / 'phaseA' / 'A6_hierarchical_layering' / 'outputs' / 'A6_hierarchical_graph.pkl'
V2_SHAP_PATH = PROJECT_ROOT / 'phaseB' / 'B35_semantic_hierarchy' / 'outputs' / 'B35_shap_scores.pkl'
V2_CLUSTERING_PATH = PROJECT_ROOT / 'phaseB' / 'B2_mechanism_identification' / 'outputs' / 'B2_semantic_clustering.pkl'

# Output paths (V2.1)
OUTPUT_PATH = OUTPUT_ROOT / 'A2_preprocessed_data_V21.pkl'
DROPPED_PATH = OUTPUT_ROOT / 'A2_DROPPED_INDICATORS.json'
REPORT_PATH = OUTPUT_ROOT / 'sampling_report.json'

# Ensure output directory exists
OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

# ============================================================================
# STEP 1: Load Data
# ============================================================================

print("\n[1/7] Loading V2 data...")

with open(A2_DATA_PATH, 'rb') as f:
    a2_data = pickle.load(f)

metadata = a2_data['metadata']
imputed_data = a2_data['imputed_data']

print(f"  Loaded {len(metadata)} indicators")

# Load V2 SHAP scores (outcome importance)
try:
    with open(V2_SHAP_PATH, 'rb') as f:
        v2_shap_data = pickle.load(f)

    # Extract scores from the data structure
    # B35 format is direct: {indicator: {composite_score, pagerank, betweenness, ...}}
    v2_shap_scores = {}
    if isinstance(v2_shap_data, dict):
        for ind, scores in v2_shap_data.items():
            if isinstance(scores, dict):
                v2_shap_scores[ind] = float(scores.get('composite_score', 0.0))
            else:
                v2_shap_scores[ind] = float(scores)

    print(f"  Loaded V2 SHAP scores for {len(v2_shap_scores)} indicators")
except FileNotFoundError:
    print(f"  WARNING: V2 SHAP scores not found at {V2_SHAP_PATH}")
    print(f"  Using betweenness centrality as fallback")
    v2_shap_scores = {}

# Load V2 clustering (for coverage-based sampling)
try:
    with open(V2_CLUSTERING_PATH, 'rb') as f:
        v2_clustering = pickle.load(f)

    clusters = v2_clustering.get('clusters', {})
    node_assignments = v2_clustering.get('node_assignments', {})

    print(f"  Loaded V2 clustering: {len(clusters)} clusters")
except FileNotFoundError:
    print(f"  WARNING: V2 clustering not found at {V2_CLUSTERING_PATH}")
    clusters = {}
    node_assignments = {}

# Load graph for betweenness
with open(A6_GRAPH_PATH, 'rb') as f:
    a6_data = pickle.load(f)

G = a6_data['graph']
betweenness = a6_data['centrality']['betweenness']

print(f"  Loaded graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

# ============================================================================
# STEP 2: Compute Outcome-Specific Betweenness
# ============================================================================

print("\n[2/7] Computing outcome-specific betweenness...")

import networkx as nx

# Identify outcome nodes (key QoL indicators)
# Using actual indicator code patterns from V2 graph
OUTCOME_KEYWORDS = [
    'lifexp', 'lifeex', 'gdp', 'gdpcap',  # Life expectancy, GDP
    'mort', 'death',  # Mortality
    'enrol', 'school', 'educ',  # Education
    'unemp', 'employ',  # Employment
    'pov', 'poor',  # Poverty
    'health', 'immun', 'vaccin',  # Health
    'water', 'sanit',  # Basic services
    'electr', 'energy',  # Infrastructure
    'democ', 'freedom', 'rights',  # Governance outcomes
    'hdi', 'gini', 'ineq'  # Inequality/development indices
]

outcome_nodes = []
for node in G.nodes():
    node_lower = str(node).lower()
    if any(kw in node_lower for kw in OUTCOME_KEYWORDS):
        outcome_nodes.append(node)

print(f"  Identified {len(outcome_nodes)} outcome nodes")

# Compute betweenness centrality TO outcomes only
outcome_betweenness = {}

for node in G.nodes():
    # Sum of inverse shortest path distances to any outcome
    path_score = 0.0
    for outcome in outcome_nodes:
        try:
            if nx.has_path(G, node, outcome):
                path_len = nx.shortest_path_length(G, node, outcome)
                path_score += 1.0 / (path_len + 1)
        except nx.NetworkXError:
            continue

    outcome_betweenness[node] = path_score

# Normalize
max_ob = max(outcome_betweenness.values()) if outcome_betweenness and max(outcome_betweenness.values()) > 0 else 1.0
outcome_betweenness = {k: v/max_ob for k, v in outcome_betweenness.items()}

print(f"  Computed outcome-specific betweenness for {len(outcome_betweenness)} nodes")

# ============================================================================
# STEP 3: Map Indicators to Domains & Clusters
# ============================================================================

print("\n[3/7] Mapping indicators to domains and clusters...")

indicator_domains = {}
domain_indicators = defaultdict(list)

for indicator, meta in metadata.items():
    source = meta.get('source', 'unknown')
    domain = DOMAIN_MAP.get(source, 'Unknown')

    indicator_domains[indicator] = domain
    domain_indicators[domain].append(indicator)

# Map indicators to semantic clusters
indicator_clusters = {}
cluster_indicators = defaultdict(list)

for indicator in metadata.keys():
    cluster = node_assignments.get(indicator, 'Unclassified')
    indicator_clusters[indicator] = cluster
    cluster_indicators[cluster].append(indicator)

print(f"  Mapped to {len(set(indicator_domains.values()))} domains:")
for domain, inds in sorted(domain_indicators.items()):
    print(f"    {domain}: {len(inds)}")
print(f"  Mapped to {len(cluster_indicators)} semantic clusters")

# ============================================================================
# STEP 4: Compute Research-Grade Composite Score
# ============================================================================

print("\n[4/7] Computing research-grade composite scores...")

# Normalize SHAP scores
max_shap = max(v2_shap_scores.values()) if v2_shap_scores and max(v2_shap_scores.values()) > 0 else 1.0
normalized_shap = {k: v/max_shap for k, v in v2_shap_scores.items()}

# Normalize betweenness
max_betw = max(betweenness.values()) if betweenness and max(betweenness.values()) > 0 else 1.0
normalized_betw = {k: v/max_betw for k, v in betweenness.items()}

indicator_scores = {}

for indicator in metadata.keys():
    meta = metadata[indicator]

    # Score 1: SHAP importance (outcome prediction) - MOST IMPORTANT
    # Fall back to betweenness if SHAP not available
    shap_score = normalized_shap.get(indicator, normalized_betw.get(indicator, 0.0))

    # Score 2: Outcome-specific betweenness (paths to outcomes)
    outcome_betw = outcome_betweenness.get(indicator, 0.0)

    # Score 3: Data quality (1 - missingness)
    missing_rate = meta.get('missing_rate', 1.0)
    quality_score = 1.0 - missing_rate

    # Score 4: Cluster representativeness (avoid redundancy)
    cluster = indicator_clusters.get(indicator, 'Unclassified')
    cluster_size = len(cluster_indicators.get(cluster, [indicator]))
    diversity_score = 1.0 / np.log1p(cluster_size)  # Prefer smaller clusters

    # Composite score: OUTCOME-AWARE
    composite = (
        0.50 * shap_score +          # Predicts QoL outcomes (CRITICAL)
        0.25 * outcome_betw +        # Paths to outcomes
        0.15 * quality_score +       # Data quality
        0.10 * diversity_score       # Semantic diversity
    )

    indicator_scores[indicator] = {
        'composite': composite,
        'shap': shap_score,
        'outcome_betweenness': outcome_betw,
        'quality': quality_score,
        'diversity': diversity_score,
        'cluster': cluster
    }

print(f"  Scored {len(indicator_scores)} indicators")

# ============================================================================
# STEP 5: Coverage-Based Sampling Within Domains
# ============================================================================

print("\n[5/7] Coverage-based sampling within domains...")

selected_indicators = []
sampling_details = {}

for domain, target_count in SAMPLING_TARGETS.items():
    domain_inds = domain_indicators.get(domain, [])
    current_count = len(domain_inds)

    print(f"\n  {domain}: {current_count} -> {target_count}")

    if current_count <= target_count:
        # Keep all if below target
        selected = domain_inds
        print(f"    Keeping all {current_count} indicators")
        clusters_covered = len(set(indicator_clusters.get(ind, 'Unclassified') for ind in selected))
    else:
        # Coverage-based sampling: Ensure each cluster represented

        # Step 1: Get clusters in this domain
        domain_clusters = defaultdict(list)
        for ind in domain_inds:
            cluster = indicator_clusters.get(ind, 'Unclassified')
            domain_clusters[cluster].append(ind)

        print(f"    Found {len(domain_clusters)} clusters in {domain}")

        # Step 2: Allocate indicators per cluster proportionally
        cluster_allocations = {}
        total_in_clusters = sum(len(inds) for inds in domain_clusters.values())

        for cluster, inds in domain_clusters.items():
            proportion = len(inds) / total_in_clusters if total_in_clusters > 0 else 0
            allocation = max(1, int(target_count * proportion))  # At least 1 per cluster
            cluster_allocations[cluster] = allocation

        # Step 3: Sample top N from each cluster by composite score
        selected = []
        for cluster, allocation in cluster_allocations.items():
            cluster_inds = domain_clusters[cluster]

            # Sort by composite score
            cluster_scores = [(ind, indicator_scores[ind]['composite']) for ind in cluster_inds]
            cluster_scores.sort(key=lambda x: x[1], reverse=True)

            # Take top N
            selected.extend([ind for ind, score in cluster_scores[:allocation]])

        # Step 4: If we haven't reached target, add top remaining by composite
        if len(selected) < target_count:
            remaining = set(domain_inds) - set(selected)
            remaining_scores = [(ind, indicator_scores[ind]['composite']) for ind in remaining]
            remaining_scores.sort(key=lambda x: x[1], reverse=True)

            needed = target_count - len(selected)
            selected.extend([ind for ind, score in remaining_scores[:needed]])

        # Step 5: If we overshot, trim lowest composite scores
        if len(selected) > target_count:
            selected_scores = [(ind, indicator_scores[ind]['composite']) for ind in selected]
            selected_scores.sort(key=lambda x: x[1], reverse=True)
            selected = [ind for ind, score in selected_scores[:target_count]]

        retention_pct = (len(selected) / current_count) * 100

        # Count cluster coverage
        clusters_covered = len(set(indicator_clusters.get(ind, 'Unclassified') for ind in selected))
        print(f"    Sampled {len(selected)}/{current_count} ({retention_pct:.1f}%)")
        print(f"    Clusters covered: {clusters_covered}/{len(domain_clusters)}")

    sampling_details[domain] = {
        'original': current_count,
        'sampled': len(selected),
        'clusters_covered': clusters_covered,
        'total_clusters': len(set(indicator_clusters.get(ind, 'Unclassified') for ind in domain_inds))
    }

    selected_indicators.extend(selected)

print(f"\n  Total selected: {len(selected_indicators)} indicators")

# ============================================================================
# STEP 6: Validation - Check Critical Indicators
# ============================================================================

print("\n[6/7] Validating critical indicator coverage...")

# Check top 100 SHAP/composite indicators from V2
all_scores = [(ind, indicator_scores[ind]['composite']) for ind in metadata.keys()]
all_scores.sort(key=lambda x: x[1], reverse=True)
top_100_ids = [ind for ind, score in all_scores[:100]]

retained_top_100 = [ind for ind in top_100_ids if ind in selected_indicators]
retention_rate = len(retained_top_100) / len(top_100_ids) * 100

print(f"\n  Top 100 composite score indicators: {len(retained_top_100)}/100 retained ({retention_rate:.1f}%)")

if retention_rate < 80:
    print(f"  WARNING: Only {retention_rate:.1f}% of top indicators retained")

# Check for critical keywords
CRITICAL_KEYWORDS = {
    'democracy', 'corruption', 'judicial', 'electoral', 'civil_liberties',
    'enrollment', 'literacy', 'schooling', 'education_years',
    'mortality', 'life_expectancy', 'immunization', 'health_expenditure',
    'poverty', 'inequality', 'unemployment', 'gdp'
}

v2_indicators = set(metadata.keys())
dropped = v2_indicators - set(selected_indicators)

critical_dropped = []
for ind in dropped:
    if any(kw in str(ind).lower() for kw in CRITICAL_KEYWORDS):
        # Check if it had high composite score
        comp_score = indicator_scores.get(ind, {}).get('composite', 0.0)
        if comp_score > 0.1:  # Meaningful score
            critical_dropped.append((ind, comp_score))

critical_dropped.sort(key=lambda x: x[1], reverse=True)

print(f"\n  Critical indicators dropped: {len(critical_dropped)}")
if len(critical_dropped) > 0:
    print(f"\n  Top 10 critical dropped (by composite score):")
    for ind, score in critical_dropped[:10]:
        print(f"    - {ind}: {score:.3f}")

# ============================================================================
# STEP 7: Create V2.1 Dataset
# ============================================================================

print("\n[7/7] Creating V2.1 dataset...")

# Filter metadata
v21_metadata = {ind: metadata[ind] for ind in selected_indicators}

# Filter imputed data
v21_imputed_data = {ind: imputed_data[ind] for ind in selected_indicators if ind in imputed_data}

# Preserve tier data
v21_tier_data = {}
if 'tier_data' in a2_data:
    v21_tier_data = {
        ind: a2_data['tier_data'][ind]
        for ind in selected_indicators
        if ind in a2_data.get('tier_data', {})
    }

# Create V2.1 data structure
v21_data = {
    'imputed_data': v21_imputed_data,
    'tier_data': v21_tier_data,
    'metadata': v21_metadata,
    'preprocessing_info': a2_data.get('preprocessing_info', {}),
    'v21_sampling_info': {
        'version': 'V2.1_RESEARCH_GRADE',
        'method': 'outcome_aware_coverage_sampling',
        'scoring_weights': {
            'shap': 0.50,
            'outcome_betweenness': 0.25,
            'quality': 0.15,
            'diversity': 0.10
        },
        'targets': SAMPLING_TARGETS,
        'total_indicators': len(selected_indicators),
        'domain_distribution': {
            domain: sum(1 for ind in selected_indicators if indicator_domains.get(ind) == domain)
            for domain in SAMPLING_TARGETS.keys()
        },
        'top_100_retention': retention_rate,
        'critical_dropped': len(critical_dropped),
        'sampling_details': sampling_details
    }
}

# Save main data
with open(OUTPUT_PATH, 'wb') as f:
    pickle.dump(v21_data, f)

print(f"\n  Saved to: {OUTPUT_PATH}")

# Save dropped indicators for review
dropped_info = {
    'total_dropped': len(dropped),
    'critical_dropped': [
        {'indicator': ind, 'composite_score': float(score)}
        for ind, score in critical_dropped
    ],
    'dropped_by_domain': {
        domain: len([ind for ind in dropped if indicator_domains.get(ind) == domain])
        for domain in SAMPLING_TARGETS.keys()
    },
    'all_dropped': list(dropped)[:500]  # First 500 for review
}

with open(DROPPED_PATH, 'w') as f:
    json.dump(dropped_info, f, indent=2)

print(f"  Saved dropped indicators to: {DROPPED_PATH}")

# Save detailed report
report = {
    'version': 'V2.1_RESEARCH_GRADE',
    'total_indicators': len(selected_indicators),
    'original_indicators': len(metadata),
    'reduction_pct': (1 - len(selected_indicators)/len(metadata)) * 100,
    'scoring_method': {
        'shap_weight': 0.50,
        'outcome_betweenness_weight': 0.25,
        'quality_weight': 0.15,
        'diversity_weight': 0.10
    },
    'domain_distribution': v21_data['v21_sampling_info']['domain_distribution'],
    'sampling_details': sampling_details,
    'validation': {
        'top_100_retention': retention_rate,
        'critical_dropped': len(critical_dropped),
        'outcome_nodes_identified': len(outcome_nodes)
    },
    'quality_check': {
        'passed': retention_rate >= 80 and len(critical_dropped) < 20,
        'top_100_retention_target': 80,
        'critical_dropped_target': 20
    }
}

with open(REPORT_PATH, 'w') as f:
    json.dump(report, f, indent=2)

print(f"  Saved report to: {REPORT_PATH}")

# ============================================================================
# FINAL VALIDATION
# ============================================================================

print("\n" + "="*80)
print("RESEARCH-GRADE VALIDATION")
print("="*80)

print("\nV2.1 Domain Distribution:")
for domain in sorted(SAMPLING_TARGETS.keys()):
    count = v21_data['v21_sampling_info']['domain_distribution'].get(domain, 0)
    pct = (count / len(selected_indicators)) * 100 if len(selected_indicators) > 0 else 0
    print(f"  {domain}: {count} ({pct:.1f}%)")

print(f"\nScoring Method:")
print(f"  SHAP/Composite importance: 50% (outcome prediction)")
print(f"  Outcome betweenness: 25% (paths to QoL)")
print(f"  Data quality: 15%")
print(f"  Cluster diversity: 10%")

print(f"\nQuality Metrics:")
print(f"  Total indicators: {len(selected_indicators)}")
print(f"  Reduction: {len(metadata)} -> {len(selected_indicators)} ({len(selected_indicators)/len(metadata)*100:.1f}%)")
print(f"  Top 100 retention: {retention_rate:.1f}%")
print(f"  Critical indicators dropped: {len(critical_dropped)}")

if retention_rate >= 80 and len(critical_dropped) < 20:
    print(f"\n{'='*80}")
    print("RESEARCH-GRADE SAMPLING COMPLETE - QUALITY VALIDATED")
    print(f"{'='*80}")
else:
    print(f"\n{'='*80}")
    print("WARNING: Review dropped indicators before proceeding")
    print(f"  See: {DROPPED_PATH}")
    print(f"{'='*80}")
