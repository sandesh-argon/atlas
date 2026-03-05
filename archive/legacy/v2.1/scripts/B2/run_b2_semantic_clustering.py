#!/usr/bin/env python3
"""
Phase B2: Two-Stage Semantic Clustering (V2.1) - 100% COVERAGE VERSION
======================================================================

Assigns ALL indicators to semantic clusters - NO UNCLASSIFIED ALLOWED.

Strategy:
1. Keyword-based coarse clustering (catch ~55-60%)
2. Embedding-based assignment for unclassified (catch remaining 40-45%)
3. Sub-clustering within each coarse cluster

This ensures 0% unclassified.

Author: Phase B2 V2.1
Date: December 2025
"""

import pickle
import json
import sys
import re
from pathlib import Path
from datetime import datetime
from collections import defaultdict, Counter
import numpy as np

# V2.1 Configuration
sys.path.insert(0, str(Path(__file__).parent.parent))
from v21_config import A6_OUTPUT, B2_OUTPUT, B1_OUTPUT

output_dir = B2_OUTPUT
output_dir.mkdir(exist_ok=True, parents=True)

print("=" * 80)
print("PHASE B2: SEMANTIC CLUSTERING (V2.1) - 100% COVERAGE")
print("=" * 80)

start_time = datetime.now()
print(f"Start time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")

# ============================================================================
# EXPANDED KEYWORD PATTERNS FOR BETTER COVERAGE
# ============================================================================

KEYWORD_PATTERNS = {
    # Governance clusters - EXPANDED
    'Governance_Judicial': [r'judic', r'court', r'legal', r'\blaw\b', r'v2ju', r'rule.*law', r'justice'],
    'Governance_Executive': [r'execut', r'presid', r'prime.?minister', r'v2ex', r'cabinet', r'minister', r'head.*state'],
    'Governance_Legislative': [r'legislat', r'parliament', r'congress', r'v2lg', r'senate', r'assembly', r'lawmak'],
    'Governance_Electoral': [r'elect', r'voting', r'campaign', r'v2el', r'ballot', r'poll', r'referendum'],
    'Governance_Civil_Liberties': [r'civil', r'freedom', r'rights', r'liberty', r'v2cl', r'human.?rights', r'association'],
    'Governance_Media': [r'media', r'press', r'journalism', r'censorship', r'v2me', r'broadcast', r'v2sm', r'news'],
    'Governance_Corruption': [r'corrupt', r'bribe', r'embezzle', r'transparency', r'v2x.*corr', r'integrity'],
    'Governance_Taxation': [r'\btax', r'revenue', r'fiscal', r'budget', r'yprin', r'tariff', r'excise'],
    'Governance_Political_Equality': [r'v2pe', r'political.?equality', r'v2p[ea]', r'equal.*right'],
    'Governance_Deliberation': [r'v2dl', r'deliberat', r'consult', r'dialogue'],
    'Governance_State': [r'v2st', r'state.?capacity', r'bureauc', r'public.*admin'],
    'Governance_Parties': [r'v2ps', r'party', r'parties', r'partisan', r'v2pa'],
    'Governance_Constitutional': [r'ccp_', r'constitutional', r'constit', r'charter'],
    'Governance_Sovereignty': [r'v2sv', r'v2dd', r'sovereignty', r'autonomy', r'self.*govern'],
    'Governance_Direct_Democracy': [r'v2dd', r'direct.*democra', r'plebiscite', r'initiative'],
    'Governance_Quality': [r'qar_', r'qog', r'wbgi_', r'governance.?quality', r'regulat.*quality', r'rule.*law'],
    'Governance_Barometer': [r'br_', r'barometer', r'survey.*trust'],
    'Governance_Suffrage': [r'v2[afm]suffrage', r'suffrage', r'enfranch'],
    'Governance_Monitoring': [r'v2te', r'monitor', r'oversight'],
    'Governance_Polyarchy': [r'vanhanen', r'polyarchy', r'v2x_polyarchy'],
    'Governance_General': [r'polity', r'democra', r'autocra', r'regime', r'v2x', r'vdem', r'institu', r'gol_', r'v2reg', r'v2ca', r'v2[a-z]{2}[a-z_]'],

    # Education clusters - EXPANDED
    'Education_Primary': [r'primary', r'GER\.1', r'NER\.1', r'grade.?[1-6]', r'elementary', r'isced.?1'],
    'Education_Secondary': [r'secondary', r'GER\.2', r'NER\.2', r'grade.?[7-9]', r'high.?school', r'isced.?[23]'],
    'Education_Tertiary': [r'tertiary', r'university', r'college', r'higher.?education', r'GER\.3', r'isced.?[5678]'],
    'Education_Quality': [r'pupil.*teacher', r'PTR', r'education.*quality', r'test.?score', r'PISA', r'qualified.*teacher'],
    'Education_Access': [r'enrollment', r'attendance', r'dropout', r'completion', r'ROFST', r'out.?of.?school', r'enrol'],
    'Education_Literacy': [r'literacy', r'literate', r'illiteracy', r'reading', r'LR\.', r'adult.*read'],
    'Education_Mobility': [r'MOR\.', r'mobility.?rate', r'FOSGP', r'outbound.?student', r'international.*student'],
    'Education_Intake': [r'AIR\.', r'intake.?rate', r'adjusted.?intake', r'gross.*intake'],
    'Education_Freshmen': [r'FRESP', r'freshmen', r'first.*year'],
    'Education_Expenditure': [r'education.*expend', r'SE\.XPD', r'spending.*education'],
    'Education_General': [r'v2ed', r'education', r'school', r'learn', r'SE\.', r'UIS\.', r'teach'],

    # Health clusters - EXPANDED
    'Health_Mortality': [r'mortality', r'death', r'survival', r'life.?expectancy', r'dying', r'SH\.DTH', r'lifexp'],
    'Health_Disease': [r'disease', r'epidemic', r'infectious', r'HIV', r'malaria', r'tuberculosis', r'COVID', r'illness'],
    'Health_Maternal': [r'maternal', r'pregnancy', r'birth', r'REPR', r'antenatal', r'postnatal', r'obstetric'],
    'Health_Child': [r'child.?health', r'infant', r'immunization', r'vaccination', r'neonatal', r'under.?5', r'pediatric'],
    'Health_Access': [r'physician', r'hospital', r'health.?facility', r'medical', r'doctor', r'nurse', r'SH\.', r'clinic'],
    'Health_Nutrition': [r'nutrition', r'malnutrition', r'stunting', r'wasting', r'obesity', r'underweight', r'diet'],
    'Health_Metrics': [r'ihme_', r'health.?metric', r'hle_', r'daly', r'qaly', r'disability'],
    'Health_Contraception': [r'WHS', r'contracept', r'family.?planning', r'reproductive'],
    'Health_General': [r'health', r'SH\.', r'wellbeing', r'sanit'],

    # Economic clusters - EXPANDED
    'Economic_GDP': [r'GDP', r'gross.?domestic', r'economic.?growth', r'GNI', r'national.?income', r'NY\.GDP', r'NY\.GNP', r'output'],
    'Economic_Trade': [r'\btrade\b', r'export', r'import', r'tariff', r'merchandise', r'goods.?services', r'NE\.IMP', r'NE\.EXP', r'BX\.', r'BM\.'],
    'Economic_Employment': [r'employment', r'unemployment', r'labor.?force', r'workforce', r'jobless', r'wdi_unemp', r'wdi_emp', r'wdi_lfp', r'SL\.', r'work'],
    'Economic_Technology': [r'technology', r'internet', r'mobile', r'digital', r'broadband', r'ICT', r'wdi_mobile', r'IT\.'],
    'Economic_Finance': [r'credit', r'\bbank', r'financial', r'lending', r'loan', r'interest.?rate', r'cbi_', r'monetary'],
    'Economic_Infrastructure': [r'infrastructure', r'transport', r'electricity', r'power', r'energy', r'road', r'rail'],
    'Economic_Agriculture': [r'agriculture', r'crop', r'\bfarm', r'livestock', r'food.?production', r'arable', r'AG\.', r'harvest'],
    'Economic_Industry': [r'industry', r'manufacturing', r'factory', r'industrial', r'mining', r'NV\.IND', r'construct'],
    'Economic_Consumption': [r'consumption', r'expenditure', r'NE\.CON', r'household.*expend', r'ICP', r'spend'],
    'Economic_Wealth': [r'wealth', r'income.*distribution', r'WID', r'NW\.', r'inequality', r'gini', r'decile', r'quintile'],
    'Economic_Investment': [r'invest', r'capital', r'FDI', r'saving', r'gross.*fixed', r'NE\.GDI'],
    'Economic_National_Accounts': [r'pwt_', r'rtfp', r'ctfp', r'rda', r'cda', r'tfp', r'penn.?world', r'rgdp'],
    'Economic_Aid': [r'DC\.', r'aid.?flow', r'donor', r'oda', r'bilateral', r'grant'],
    'Economic_Remittances': [r'remittance', r'rd_inw', r'rd_outw', r'BX\.TRF', r'BM\.TRF', r'transfer'],
    'Economic_Reserves': [r'FI\.RES', r'reserve', r'gold', r'foreign.*asset'],
    'Economic_Price_Levels': [r'pl_', r'X\.PPP', r'X\.P', r'ppp', r'price.?level', r'ICP', r'CPTOTSAX', r'inflation', r'deflat'],
    'Economic_Shadow': [r'ied_', r'shadow.?econom', r'informal', r'unreported'],
    'Economic_Complexity': [r'gpcr_', r'eci', r'complexity', r'diversif'],
    'Economic_Exchange': [r'\bxr\b', r'exchange.?rate', r'currency', r'fx'],
    'Economic_Telecom': [r'IT\.MLT', r'telephone', r'telecom', r'subscri'],
    'Economic_Services': [r'service', r'NV\.SRV', r'tertiary.*sector'],
    'Economic_Debt': [r'debt', r'DT\.', r'GC\.DOD', r'liability', r'borrow'],
    'Economic_General': [r'econom', r'NY\.', r'NE\.', r'NV\.', r'market', r'sector'],

    # Demographics - EXPANDED
    'Demographics_Population': [r'population', r'demographic', r'age.?structure', r'fertility.?rate', r'SP\.POP', r'npopul', r'birth.*rate', r'death.*rate'],
    'Demographics_Migration': [r'migration', r'refugee', r'emigration', r'immigration', r'asylum', r'displaced', r'migrant'],
    'Demographics_Urbanization': [r'urban', r'rural', r'\bcity', r'metropolitan', r'slum', r'agglomerat'],
    'Demographics_Gender': [r'gender', r'female', r'women', r'male', r'\bmen\b', r'SG\.', r'sex.*ratio'],
    'Demographics_Age': [r'age.*group', r'cohort', r'elderly', r'youth', r'child.*pop', r'working.*age', r'depend.*ratio'],
    'Demographics_Historical': [r'^h_', r'historical.?database', r'mad_'],

    # Environment - EXPANDED
    'Environment_Climate': [r'climate', r'temperature', r'precipitation', r'CO2', r'emission', r'greenhouse', r'EN\.GHG', r'carbon'],
    'Environment_Resources': [r'natural.?resource', r'mineral', r'forest', r'water.?resource', r'land.?use', r'AG\.LND', r'timber'],
    'Environment_Pollution': [r'pollution', r'air.?quality', r'waste', r'contamination', r'toxic'],
    'Environment_Resources_Extended': [r'ross_', r'oil', r'gas.?prod', r'gas.?value', r'fao_', r'petrol', r'fuel'],
    'Environment_Vulnerability': [r'gain_', r'nd-gain', r'vulnerab', r'adaptation', r'resilience'],
    'Environment_Biodiversity': [r'biodivers', r'species', r'ecosystem', r'habitat'],
    'Environment_Water': [r'water', r'sanitation', r'SH\.H2O', r'EG\.ELC', r'drinking'],
    'Environment_General': [r'environ', r'EN\.', r'EG\.', r'green', r'sustainab'],

    # Security - EXPANDED
    'Security_Military': [r'bicc_', r'militar', r'weapon', r'army', r'defense', r'atop_', r'alliance', r'armed.*force'],
    'Security_Terrorism': [r'terror', r'gted_', r'violence', r'conflict', r'war'],
    'Security_Human_Rights': [r'chisol', r'child.?soldier', r'dr_sg', r'dr_pg', r'dr_ig', r'political.?terror', r'torture'],
    'Security_Crime': [r'crime', r'homicide', r'murder', r'theft', r'prison'],
    'Security_General': [r'security', r'peace', r'VC\.', r'safety'],

    # Development - EXPANDED
    'Development_Index': [r'undp_', r'hdi', r'human.?development', r'mpi', r'poverty.*index'],
    'Development_Poverty': [r'poverty', r'poor', r'SI\.POV', r'depriv', r'hardship'],
    'Development_General': [r'develop', r'progress', r'wellbeing'],

    # Research - EXPANDED
    'Research_Development': [r'RESDEN', r'research', r'r&d', r'patent', r'innovation', r'scientif'],

    # Economic wealth aggregates (specific patterns)
    'Economic_Wealth_Aggregates': [r'^a[a-z]{3}[ghnc]', r'average.*income', r'average.*property', r'median.*income', r'mean.*income'],
}

# Super-domain mapping
SUPER_DOMAIN_MAP = {
    'Social': ['Governance', 'Education', 'Health', 'Security', 'Development'],
    'Economic': ['Economic', 'Demographics', 'Research'],
    'Environmental': ['Environment'],
}

def get_domain_from_cluster(cluster_name):
    """Extract domain from cluster name like 'Governance_Judicial'"""
    if '_' in cluster_name:
        return cluster_name.split('_')[0]
    return cluster_name

def get_super_domain(domain):
    """Get super-domain for a domain"""
    for super_domain, domains in SUPER_DOMAIN_MAP.items():
        if domain in domains:
            return super_domain
    return 'Economic'  # Default fallback

# ============================================================================
# STEP 1: Load Data
# ============================================================================

print("\n[STEP 1] Loading data...")

# Load A6 graph
a6_path = A6_OUTPUT / "A6_hierarchical_graph.pkl"
with open(a6_path, 'rb') as f:
    a6_data = pickle.load(f)

G = a6_data['graph']
all_nodes = list(G.nodes())

print(f"   ✅ Loaded {len(all_nodes)} nodes from A6")

# Try to load indicator labels
labels_path = B1_OUTPUT / "indicator_labels_comprehensive.json"
if labels_path.exists():
    with open(labels_path, 'r') as f:
        indicator_labels = json.load(f)
    print(f"   ✅ Loaded labels for {len(indicator_labels)} indicators")
else:
    indicator_labels = {node: {'label': node, 'description': ''} for node in all_nodes}
    print(f"   ⚠️ No labels file, using node IDs as labels")

# ============================================================================
# STEP 2: Stage 1 - Keyword-Based Coarse Clustering
# ============================================================================

print("\n[STEP 2] Stage 1: Keyword-based coarse clustering...")

def assign_coarse_cluster(indicator_id, indicator_label, indicator_desc=""):
    """Assign to coarse cluster based on keyword matching"""
    text = f"{indicator_id} {indicator_label} {indicator_desc}".lower()

    matches = []
    for cluster_name, patterns in KEYWORD_PATTERNS.items():
        score = 0
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                score += 1
        if score > 0:
            matches.append((cluster_name, score))

    if matches:
        matches.sort(key=lambda x: x[1], reverse=True)
        return matches[0][0]

    return None  # Will be handled by embedding assignment

# Apply coarse clustering
coarse_assignments = {}
coarse_cluster_nodes = defaultdict(list)
unassigned_nodes = []

for node_id in all_nodes:
    label_data = indicator_labels.get(node_id, {})
    label = label_data.get('label', node_id)
    desc = label_data.get('description', '')

    coarse_cluster = assign_coarse_cluster(node_id, label, desc)
    if coarse_cluster:
        coarse_assignments[node_id] = coarse_cluster
        coarse_cluster_nodes[coarse_cluster].append(node_id)
    else:
        unassigned_nodes.append(node_id)

# Statistics
classified_count = len(all_nodes) - len(unassigned_nodes)
print(f"\n   Keyword-based assignment:")
print(f"      Classified: {classified_count} ({classified_count/len(all_nodes)*100:.1f}%)")
print(f"      Unassigned: {len(unassigned_nodes)} ({len(unassigned_nodes)/len(all_nodes)*100:.1f}%)")

# ============================================================================
# STEP 3: Embedding-Based Assignment for Unassigned Nodes
# ============================================================================

print("\n[STEP 3] Assigning unclassified nodes via embeddings...")

from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

# Load model
print("   Loading embedding model...")
model = SentenceTransformer('all-MiniLM-L6-v2')

# Get representative texts for each coarse cluster
cluster_representatives = {}
for cluster_name, node_ids in coarse_cluster_nodes.items():
    # Take up to 10 representative samples
    sample_texts = []
    for node_id in node_ids[:10]:
        label_data = indicator_labels.get(node_id, {})
        label = label_data.get('label', node_id)
        desc = label_data.get('description', '')[:100]
        sample_texts.append(f"{node_id} {label} {desc}")
    cluster_representatives[cluster_name] = ' | '.join(sample_texts)

# Embed cluster representatives
print("   Embedding cluster representatives...")
cluster_names = list(cluster_representatives.keys())
cluster_texts = [cluster_representatives[c] for c in cluster_names]
cluster_embeddings = model.encode(cluster_texts, show_progress_bar=False)

# Embed unassigned nodes and find best match
print(f"   Assigning {len(unassigned_nodes)} unclassified nodes...")

if unassigned_nodes:
    # Get texts for unassigned nodes
    unassigned_texts = []
    for node_id in unassigned_nodes:
        label_data = indicator_labels.get(node_id, {})
        label = label_data.get('label', node_id)
        desc = label_data.get('description', '')[:100]
        unassigned_texts.append(f"{node_id} {label} {desc}")

    # Embed in batches
    batch_size = 256
    for i in range(0, len(unassigned_nodes), batch_size):
        batch_nodes = unassigned_nodes[i:i+batch_size]
        batch_texts = unassigned_texts[i:i+batch_size]

        batch_embeddings = model.encode(batch_texts, show_progress_bar=False)

        # Find best matching cluster for each
        similarities = cosine_similarity(batch_embeddings, cluster_embeddings)

        for j, node_id in enumerate(batch_nodes):
            best_cluster_idx = np.argmax(similarities[j])
            best_cluster = cluster_names[best_cluster_idx]
            best_score = similarities[j][best_cluster_idx]

            coarse_assignments[node_id] = best_cluster
            coarse_cluster_nodes[best_cluster].append(node_id)

        if i % 500 == 0 and i > 0:
            print(f"      Processed {i}/{len(unassigned_nodes)}...")

print(f"   ✅ All {len(unassigned_nodes)} unclassified nodes assigned via embedding similarity")

# Verify 100% coverage
assert len(coarse_assignments) == len(all_nodes), "Not all nodes assigned!"

# Updated statistics
coarse_counts = {k: len(v) for k, v in coarse_cluster_nodes.items()}
print(f"\n   Final coarse clustering:")
print(f"      Total clusters: {len(coarse_counts)}")
print(f"      Coverage: 100% ({len(coarse_assignments)}/{len(all_nodes)})")

print(f"\n   Top 10 coarse clusters by size:")
for cluster, count in sorted(coarse_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
    print(f"      {cluster}: {count} indicators")

# ============================================================================
# STEP 4: Stage 2 - Embedding-Based Fine Clustering (Sub-clustering)
# ============================================================================

print("\n[STEP 4] Stage 2: Sub-clustering within coarse clusters...")

from sklearn.cluster import AgglomerativeClustering

fine_assignments = {}
fine_cluster_data = {}

for coarse_cluster, node_ids in coarse_cluster_nodes.items():
    if len(node_ids) < 3:
        # Too small for sub-clustering
        for node_id in node_ids:
            fine_cluster = f"{coarse_cluster}_0"
            fine_assignments[node_id] = fine_cluster
            if fine_cluster not in fine_cluster_data:
                fine_cluster_data[fine_cluster] = {
                    'indicators': [],
                    'coarse_cluster': coarse_cluster
                }
            fine_cluster_data[fine_cluster]['indicators'].append(node_id)
        continue

    # Get labels for embedding
    labels_for_embedding = []
    for node_id in node_ids:
        label_data = indicator_labels.get(node_id, {})
        label = label_data.get('label', node_id)
        desc = label_data.get('description', '')[:200]
        labels_for_embedding.append(f"{label}. {desc}" if desc else label)

    # Embed
    embeddings = model.encode(labels_for_embedding, show_progress_bar=False)

    # Determine number of sub-clusters
    # Target ~150 fine clusters total, ~60 coarse → ~2-3 subclusters average
    # But scale with cluster size
    n_subclusters = max(2, min(8, len(node_ids) // 15))

    # Cluster
    if len(node_ids) >= n_subclusters:
        clustering = AgglomerativeClustering(
            n_clusters=n_subclusters,
            linkage='ward'
        )
        subcluster_labels = clustering.fit_predict(embeddings)
    else:
        subcluster_labels = [0] * len(node_ids)

    # Assign to fine clusters
    for node_id, sublabel in zip(node_ids, subcluster_labels):
        fine_cluster = f"{coarse_cluster}_{sublabel}"
        fine_assignments[node_id] = fine_cluster

        if fine_cluster not in fine_cluster_data:
            fine_cluster_data[fine_cluster] = {
                'indicators': [],
                'coarse_cluster': coarse_cluster
            }
        fine_cluster_data[fine_cluster]['indicators'].append(node_id)

    if len(node_ids) > 50:
        print(f"      {coarse_cluster}: {len(node_ids)} → {n_subclusters} sub-clusters")

# Statistics
print(f"\n   Fine clustering results:")
print(f"      Total fine clusters: {len(fine_cluster_data)}")

fine_sizes = [len(v['indicators']) for v in fine_cluster_data.values()]
print(f"      Cluster size: min={min(fine_sizes)}, max={max(fine_sizes)}, median={np.median(fine_sizes):.0f}, mean={np.mean(fine_sizes):.1f}")

# ============================================================================
# STEP 5: Generate Representative Labels
# ============================================================================

print("\n[STEP 5] Generating representative labels for clusters...")

def get_representative_label(node_ids, indicator_labels, max_samples=5):
    """Generate a representative label from cluster members"""
    labels = []
    for node_id in node_ids[:max_samples]:
        label_data = indicator_labels.get(node_id, {})
        label = label_data.get('label', node_id)
        if label and label != node_id:
            labels.append(label)

    if not labels:
        return "Mixed indicators"

    words = []
    for label in labels:
        words.extend(label.lower().split())

    word_counts = Counter(words)
    stopwords = {'the', 'a', 'an', 'of', 'in', 'to', 'and', 'for', 'with', 'on', 'at', 'by', '%', '-', '(', ')'}
    common_words = [w for w, c in word_counts.most_common(5) if w not in stopwords and len(w) > 2]

    if common_words:
        return ' '.join(common_words[:3]).title()
    return labels[0][:50]

for fine_cluster, data in fine_cluster_data.items():
    data['representative_label'] = get_representative_label(
        data['indicators'], indicator_labels
    )
    data['size'] = len(data['indicators'])

    # Add domain info
    domain = get_domain_from_cluster(data['coarse_cluster'])
    data['domain'] = domain
    data['super_domain'] = get_super_domain(domain)

    # Sample indicators
    data['sample_indicators'] = data['indicators'][:5]
    data['sample_labels'] = [
        indicator_labels.get(n, {}).get('label', n)
        for n in data['sample_indicators']
    ]

# ============================================================================
# STEP 6: Validation
# ============================================================================

print("\n[STEP 6] Validation...")

assigned_count = len(fine_assignments)
assert assigned_count == len(all_nodes), f"Not all nodes assigned: {assigned_count} vs {len(all_nodes)}"
print(f"   ✅ All {assigned_count} nodes assigned to clusters (100% coverage)")

# Count by domain
domain_indicator_counts = defaultdict(int)
for fine_cluster, data in fine_cluster_data.items():
    domain_indicator_counts[data['domain']] += data['size']

print(f"\n   Domain distribution (indicators):")
for domain, count in sorted(domain_indicator_counts.items(), key=lambda x: x[1], reverse=True):
    pct = count / len(all_nodes) * 100
    print(f"      {domain}: {count} ({pct:.1f}%)")

# Domain cluster counts
domain_cluster_counts = Counter([v['domain'] for v in fine_cluster_data.values()])
print(f"\n   Domain distribution (clusters):")
for domain, count in domain_cluster_counts.most_common():
    print(f"      {domain}: {count} clusters")

# ============================================================================
# STEP 7: Save Results
# ============================================================================

print("\n[STEP 7] Saving results...")

output_data = {
    'fine_clusters': fine_cluster_data,
    'node_assignments': fine_assignments,
    'coarse_clusters': {k: list(v) for k, v in coarse_cluster_nodes.items()},
    'coarse_assignments': coarse_assignments,
    'metadata': {
        'total_indicators': len(all_nodes),
        'total_fine_clusters': len(fine_cluster_data),
        'total_coarse_clusters': len(coarse_cluster_nodes),
        'unclassified_count': 0,  # ZERO!
        'unclassified_pct': 0.0,
        'keyword_classified': classified_count,
        'embedding_classified': len(unassigned_nodes),
        'timestamp': datetime.now().isoformat(),
        'method': 'Keyword + Embedding assignment + Sub-clustering',
        'embedding_model': 'all-MiniLM-L6-v2'
    },
    'domain_statistics': dict(domain_cluster_counts),
    'domain_indicator_counts': dict(domain_indicator_counts)
}

# Save pickle
pkl_path = output_dir / "B2_semantic_clustering.pkl"
with open(pkl_path, 'wb') as f:
    pickle.dump(output_data, f)
print(f"   ✅ Saved: {pkl_path}")

# Save JSON summary
json_summary = {
    'total_indicators': len(all_nodes),
    'total_fine_clusters': len(fine_cluster_data),
    'total_coarse_clusters': len(coarse_cluster_nodes),
    'unclassified_count': 0,
    'coverage': '100%',
    'cluster_sizes': {k: v['size'] for k, v in fine_cluster_data.items()},
    'cluster_domains': {k: v['domain'] for k, v in fine_cluster_data.items()},
    'cluster_labels': {k: v['representative_label'] for k, v in fine_cluster_data.items()},
    'domain_distribution': dict(domain_cluster_counts),
    'domain_indicator_counts': dict(domain_indicator_counts),
    'timestamp': datetime.now().isoformat()
}

json_path = output_dir / "B2_semantic_clustering_summary.json"
with open(json_path, 'w') as f:
    json.dump(json_summary, f, indent=2)
print(f"   ✅ Saved: {json_path}")

# ============================================================================
# SUMMARY
# ============================================================================

elapsed = (datetime.now() - start_time).total_seconds()

print("\n" + "=" * 80)
print("B2 SEMANTIC CLUSTERING COMPLETE - 100% COVERAGE")
print("=" * 80)

print(f"""
Summary:
   Total indicators: {len(all_nodes)}
   Coarse clusters: {len(coarse_cluster_nodes)}
   Fine clusters: {len(fine_cluster_data)}

   Classification method:
      Keyword-based: {classified_count} ({classified_count/len(all_nodes)*100:.1f}%)
      Embedding-based: {len(unassigned_nodes)} ({len(unassigned_nodes)/len(all_nodes)*100:.1f}%)

   ✅ UNCLASSIFIED: 0 (0.0%)

   Cluster size distribution:
      Min: {min(fine_sizes)}
      Max: {max(fine_sizes)}
      Median: {np.median(fine_sizes):.0f}
      Mean: {np.mean(fine_sizes):.1f}

   Runtime: {elapsed/60:.1f} minutes

Output files:
   - {pkl_path}
   - {json_path}

Next step: Run B2.5 (SHAP computation)
""")
