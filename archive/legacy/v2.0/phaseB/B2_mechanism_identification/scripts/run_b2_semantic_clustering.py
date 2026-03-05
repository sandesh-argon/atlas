#!/usr/bin/env python3
"""
Phase B2 (REVISED): Two-Stage Semantic Clustering
==================================================

Assigns ALL 3,872 real indicators to semantic clusters based on meaning.
(Note: A6 was corrected to remove 4,254 virtual INTERACT_ nodes)

Stage 1: Keyword-based coarse clustering (35-50 clusters)
Stage 2: Embedding-based fine clustering (80-120 clusters)

NO PRUNING - all real indicators are preserved.

Author: Phase B2 Revised
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
import pandas as pd

# Project paths
project_root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(project_root))

output_dir = Path(__file__).parent.parent / "outputs"
output_dir.mkdir(exist_ok=True, parents=True)

print("="*80)
print("PHASE B2 (REVISED): TWO-STAGE SEMANTIC CLUSTERING")
print("="*80)

start_time = datetime.now()
print(f"Start time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")

# ============================================================================
# KEYWORD PATTERNS FOR COARSE CLUSTERING
# ============================================================================

KEYWORD_PATTERNS = {
    # Governance clusters
    'Governance_Judicial': [r'judic', r'court', r'legal', r'\blaw\b', r'v2ju', r'rule.*law'],
    'Governance_Executive': [r'execut', r'presid', r'prime.?minister', r'v2ex', r'cabinet', r'minister'],
    'Governance_Legislative': [r'legislat', r'parliament', r'congress', r'v2lg', r'senate', r'assembly'],
    'Governance_Electoral': [r'elect', r'voting', r'campaign', r'v2el', r'ballot', r'poll'],
    'Governance_Civil_Liberties': [r'civil', r'freedom', r'rights', r'liberty', r'v2cl', r'human.?rights'],
    'Governance_Media': [r'media', r'press', r'journalism', r'censorship', r'v2me', r'broadcast', r'v2sm'],
    'Governance_Corruption': [r'corrupt', r'bribe', r'embezzle', r'transparency', r'v2x.*corr'],
    'Governance_Taxation': [r'\btax', r'revenue', r'fiscal', r'budget', r'yprin', r'tariff'],
    'Governance_Political_Equality': [r'v2pe', r'political.?equality', r'v2p[ea]'],  # NEW
    'Governance_Deliberation': [r'v2dl', r'deliberat', r'consult'],  # NEW
    'Governance_State': [r'v2st', r'state.?capacity', r'bureauc'],  # NEW
    'Governance_Parties': [r'v2ps', r'party', r'parties', r'partisan'],  # NEW
    'Governance_General': [r'polity', r'democra', r'autocra', r'regime', r'v2x', r'vdem', r'institu', r'gol_', r'v2reg', r'v2ca'],

    # Education clusters
    'Education_Primary': [r'primary', r'GER\.1', r'NER\.1', r'grade.?[1-6]', r'elementary'],
    'Education_Secondary': [r'secondary', r'GER\.2', r'NER\.2', r'grade.?[7-9]', r'high.?school'],
    'Education_Tertiary': [r'tertiary', r'university', r'college', r'higher.?education', r'GER\.3'],
    'Education_Quality': [r'pupil.*teacher', r'PTR', r'education.*quality', r'test.?score', r'PISA', r'qualified.*teacher'],
    'Education_Access': [r'enrollment', r'attendance', r'dropout', r'completion', r'ROFST', r'out.?of.?school'],
    'Education_Literacy': [r'literacy', r'literate', r'illiteracy', r'reading', r'LR\.'],
    'Education_General': [r'v2ed', r'education', r'school', r'learn'],  # NEW - catch v2ed* patterns

    # Health clusters
    'Health_Mortality': [r'mortality', r'death', r'survival', r'life.?expectancy', r'dying', r'SH\.DTH'],
    'Health_Disease': [r'disease', r'epidemic', r'infectious', r'HIV', r'malaria', r'tuberculosis', r'COVID'],
    'Health_Maternal': [r'maternal', r'pregnancy', r'birth', r'REPR', r'fertility', r'antenatal'],
    'Health_Child': [r'child.?health', r'infant', r'immunization', r'vaccination', r'neonatal', r'under.?5'],
    'Health_Access': [r'physician', r'hospital', r'health.?facility', r'medical', r'doctor', r'nurse', r'SH\.'],
    'Health_Nutrition': [r'nutrition', r'malnutrition', r'stunting', r'wasting', r'obesity', r'underweight'],

    # Economic clusters
    'Economic_GDP': [r'GDP', r'gross.?domestic', r'economic.?growth', r'GNI', r'national.?income', r'NY\.GDP', r'NY\.GNP'],
    'Economic_Trade': [r'\btrade\b', r'export', r'import', r'tariff', r'merchandise', r'goods.?services', r'NE\.IMP', r'NE\.EXP'],
    'Economic_Employment': [r'employment', r'unemployment', r'labor.?force', r'workforce', r'jobless', r'wdi_unemp', r'wdi_emp', r'wdi_lfp', r'SL\.'],
    'Economic_Technology': [r'technology', r'internet', r'mobile', r'digital', r'broadband', r'ICT', r'wdi_mobile'],
    'Economic_Finance': [r'credit', r'\bbank', r'financial', r'lending', r'loan', r'interest.?rate', r'cbi_'],
    'Economic_Infrastructure': [r'infrastructure', r'transport', r'electricity', r'power', r'energy', r'road'],
    'Economic_Agriculture': [r'agriculture', r'crop', r'\bfarm', r'livestock', r'food.?production', r'arable', r'AG\.'],
    'Economic_Industry': [r'industry', r'manufacturing', r'factory', r'industrial', r'mining', r'NV\.IND'],
    'Economic_Consumption': [r'consumption', r'expenditure', r'NE\.CON', r'household.*expend', r'ICP'],  # NEW
    'Economic_Wealth': [r'wealth', r'income.*distribution', r'WID', r'NW\.', r'inequality', r'gini'],  # NEW
    'Economic_Investment': [r'invest', r'capital', r'FDI', r'saving'],  # NEW

    # Demographics
    'Demographics_Population': [r'population', r'demographic', r'age.?structure', r'fertility.?rate', r'SP\.POP', r'npopul'],
    'Demographics_Migration': [r'migration', r'refugee', r'emigration', r'immigration', r'asylum', r'displaced'],
    'Demographics_Urbanization': [r'urban', r'rural', r'\bcity', r'metropolitan', r'slum'],
    'Demographics_Gender': [r'gender', r'female', r'women', r'male', r'\bmen\b', r'SG\.'],  # NEW

    # Environment
    'Environment_Climate': [r'climate', r'temperature', r'precipitation', r'CO2', r'emission', r'greenhouse', r'EN\.GHG'],
    'Environment_Resources': [r'natural.?resource', r'mineral', r'forest', r'water.?resource', r'land.?use', r'AG\.LND'],
    'Environment_Pollution': [r'pollution', r'air.?quality', r'waste', r'contamination'],

    # Interaction terms (from A5)
    'Interaction_Terms': [r'^INT', r'Interaction:', r'×'],

    # Additional patterns for previously unclassified
    'Health_Metrics': [r'ihme_', r'health.?metric', r'lifexp', r'hle_'],  # IHME health data
    'Governance_Constitutional': [r'ccp_', r'constitutional', r'constit'],  # Constitutional provisions
    'Governance_Sovereignty': [r'v2sv', r'v2dd', r'sovereignty', r'autonomy'],  # V-Dem sovereignty/direct democracy
    'Economic_National_Accounts': [r'pwt_', r'rtfp', r'ctfp', r'rda', r'cda', r'tfp', r'penn.?world'],  # Penn World Tables
    'Economic_Aid': [r'DC\.', r'aid.?flow', r'donor', r'oda', r'bilateral'],  # Development aid
    'Economic_Remittances': [r'remittance', r'rd_inw', r'rd_outw', r'BX\.TRF', r'BM\.TRF'],  # Remittances
    'Economic_Reserves': [r'FI\.RES', r'reserve', r'gold'],  # Financial reserves
    'Economic_Price_Levels': [r'pl_', r'X\.PPP', r'X\.P', r'ppp', r'price.?level', r'ICP', r'CPTOTSAX'],  # Price/PPP data
    'Environment_Resources_Extended': [r'ross_', r'oil', r'gas.?prod', r'gas.?value', r'fao_', r'land.?use'],  # Oil/gas/FAO
    'Environment_Vulnerability': [r'gain_', r'nd-gain', r'vulnerab', r'adaptation'],  # ND-GAIN climate vulnerability
    'Security_Military': [r'bicc_', r'militar', r'weapon', r'army', r'defense', r'atop_', r'alliance'],  # Military/security
    'Security_Terrorism': [r'terror', r'gted_', r'violence'],  # Terrorism
    'Security_Human_Rights': [r'chisol', r'child.?soldier', r'dr_sg', r'dr_pg', r'dr_ig', r'political.?terror'],  # Human rights violations
    'Governance_Quality': [r'qar_', r'qog', r'wbgi_', r'governance.?quality', r'regulat.*quality'],  # Governance quality indices
    'Economic_Shadow': [r'ied_', r'shadow.?econom', r'informal'],  # Shadow economy
    'Economic_Complexity': [r'gpcr_', r'eci', r'complexity'],  # Economic complexity
    'Economic_Exchange': [r'\bxr\b', r'exchange.?rate'],  # Exchange rates
    'Demographics_Historical': [r'^h_', r'historical.?database'],  # Historical data
    'Governance_Barometer': [r'br_', r'barometer'],  # Barometer surveys
    'Education_Mobility': [r'MOR\.', r'mobility.?rate', r'FOSGP', r'outbound.?student'],  # Education mobility
    'Education_Intake': [r'AIR\.', r'intake.?rate', r'adjusted.?intake'],  # Education intake rates
    'Education_Freshmen': [r'FRESP', r'freshmen'],  # Freshmen response data
    'Economic_Telecom': [r'IT\.MLT', r'telephone', r'telecom'],  # Telecommunications
    'Governance_Suffrage': [r'v2[afm]suffrage', r'suffrage'],  # Suffrage variables
    'Governance_Monitoring': [r'v2te', r'monitor'],  # Electoral monitoring
    'Development_Index': [r'undp_', r'hdi', r'human.?development'],  # HDI
    'Governance_Polyarchy': [r'vanhanen', r'polyarchy'],  # Vanhanen index
    'Research_Development': [r'RESDEN', r'research'],  # R&D indicators
    'Health_Contraception': [r'WHS', r'contracept', r'family.?planning'],  # Contraception/family planning

    # WDI catchall patterns (for remaining wdi_* indicators)
    'Economic_WDI_Misc': [r'wdi_sva', r'wdi_gert', r'wdi_mort'],  # Misc WDI

    # Average/aggregate patterns (WID wealth data)
    'Economic_Wealth_Aggregates': [r'^a[a-z]{3}[ghnc]', r'average.*income', r'average.*property', r'average.*surplus', r'average.*social', r'average.*sector'],
}

# Super-domain mapping
SUPER_DOMAIN_MAP = {
    'Social': ['Governance', 'Education', 'Health', 'Security', 'Development'],
    'Economic': ['Economic', 'Demographics', 'Research'],
    'Environmental': ['Environment'],
    'Cross_Cutting': ['Interaction']  # Interaction terms span multiple domains
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
    return 'Mixed'

# ============================================================================
# STEP 1: Load Data
# ============================================================================

print("\n[STEP 1] Loading data...")

# Load A6 graph
a6_path = project_root / "phaseA/A6_hierarchical_layering/outputs/A6_hierarchical_graph.pkl"
with open(a6_path, 'rb') as f:
    a6_data = pickle.load(f)

G = a6_data['graph']
layers = a6_data['layers']
all_nodes = list(G.nodes())

print(f"   ✅ Loaded {len(all_nodes)} nodes from A6")

# Load indicator labels
labels_path = project_root / "phaseB/B5_output_schema/outputs/indicator_labels_comprehensive.json"
with open(labels_path, 'r') as f:
    indicator_labels = json.load(f)

print(f"   ✅ Loaded labels for {len(indicator_labels)} indicators")

# ============================================================================
# STEP 2: Stage 1 - Keyword-Based Coarse Clustering
# ============================================================================

print("\n[STEP 2] Stage 1: Keyword-based coarse clustering...")

def assign_coarse_cluster(indicator_id, indicator_label, indicator_desc=""):
    """Assign to coarse cluster based on keyword matching"""
    text = f"{indicator_id} {indicator_label} {indicator_desc}".lower()

    # Track matches with scores
    matches = []

    for cluster_name, patterns in KEYWORD_PATTERNS.items():
        score = 0
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                score += 1
        if score > 0:
            matches.append((cluster_name, score))

    if matches:
        # Return cluster with highest match score
        matches.sort(key=lambda x: x[1], reverse=True)
        return matches[0][0]

    return 'Unclassified'

# Manual fallback assignments for stubborn WDI indicators
MANUAL_FALLBACK = {
    # Education indicators
    'gerp': 'Education_Primary', 'gerpf': 'Education_Primary', 'gerpm': 'Education_Primary',
    'gerppm': 'Education_Primary', 'gerppf': 'Education_Primary', 'gerpp': 'Education_Primary',
    'gers': 'Education_Secondary', 'gersf': 'Education_Secondary', 'gersm': 'Education_Secondary',
    'ners': 'Education_Secondary', 'nersf': 'Education_Secondary', 'nersm': 'Education_Secondary',
    'pte': 'Education_Quality', 'ptef': 'Education_Quality', 'ptem': 'Education_Quality',
    'eduprp': 'Education_Primary', 'eduprs': 'Education_Secondary',
    'expedu': 'Education_General', 'expedup': 'Education_General', 'expedus': 'Education_General',
    'expeduge': 'Education_General', 'expedut': 'Education_General',

    # Demographics
    'pop': 'Demographics_Population', 'popf': 'Demographics_Population', 'pop14': 'Demographics_Population',
    'pop65': 'Demographics_Population', 'popgr': 'Demographics_Population', 'popden': 'Demographics_Population',
    'popurb': 'Demographics_Urbanization', 'poprul': 'Demographics_Urbanization',
    'popurbagr': 'Demographics_Urbanization', 'poprulgr': 'Demographics_Urbanization',
    'refori': 'Demographics_Migration', 'refasy': 'Demographics_Migration',

    # Economic
    'debt': 'Economic_Finance', 'inflation': 'Economic_Finance',
    'tradeserv': 'Economic_Trade', 'interrev': 'Economic_Finance', 'interexp': 'Economic_Finance',
    'semp': 'Economic_Employment', 'sempf': 'Economic_Employment', 'sempm': 'Economic_Employment',
    'wofm15': 'Economic_Employment', 'wip': 'Economic_Employment',
    'incsh20l': 'Economic_Wealth', 'incsh204': 'Economic_Wealth',
    'povgap365': 'Economic_Wealth', 'povgap215': 'Economic_Wealth', 'belmedinc': 'Economic_Wealth',

    # Infrastructure/Energy
    'acel': 'Economic_Infrastructure', 'acelu': 'Economic_Infrastructure', 'acelr': 'Economic_Infrastructure',
    'elerenew': 'Economic_Infrastructure', 'elprodhyd': 'Economic_Infrastructure',
    'enerenew': 'Environment_Climate', 'eneimp': 'Economic_Infrastructure', 'eneuse': 'Economic_Infrastructure',
    'powcon': 'Economic_Infrastructure', 'fossil': 'Environment_Climate',
    'tele': 'Economic_Telecom',

    # Security
    'homicides': 'Security_Human_Rights', 'homicidesm': 'Security_Human_Rights',
    'expmilge': 'Security_Military',

    # Agriculture/Land
    'araland': 'Economic_Agriculture', 'afp': 'Economic_Agriculture',

    # Governance
    'wombuslawi': 'Demographics_Gender',
    'minwage': 'Economic_Employment',

    # Other
    'ane': 'Economic_GDP',
}

def get_fallback_cluster(node_id):
    """Get fallback cluster from manual mapping"""
    # Check for wdi_ prefix and extract key
    if node_id.startswith('wdi_'):
        key = node_id[4:]  # Remove 'wdi_' prefix
        if key in MANUAL_FALLBACK:
            return MANUAL_FALLBACK[key]
    # Check for v3pe prefix (political economy)
    if node_id.startswith('v3pe'):
        return 'Economic_Employment'
    return None

# Apply coarse clustering
coarse_assignments = {}
coarse_cluster_nodes = defaultdict(list)

for node_id in all_nodes:
    label_data = indicator_labels.get(node_id, {})
    label = label_data.get('label', node_id)
    desc = label_data.get('description', '')

    coarse_cluster = assign_coarse_cluster(node_id, label, desc)

    # Apply fallback for unclassified
    if coarse_cluster == 'Unclassified':
        fallback = get_fallback_cluster(node_id)
        if fallback:
            coarse_cluster = fallback

    coarse_assignments[node_id] = coarse_cluster
    coarse_cluster_nodes[coarse_cluster].append(node_id)

# Statistics
coarse_counts = {k: len(v) for k, v in coarse_cluster_nodes.items()}
print(f"\n   Coarse clustering results:")
print(f"      Total clusters: {len(coarse_counts)}")
print(f"      Unclassified: {coarse_counts.get('Unclassified', 0)} ({coarse_counts.get('Unclassified', 0)/len(all_nodes)*100:.1f}%)")

print(f"\n   Top 10 coarse clusters by size:")
for cluster, count in sorted(coarse_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
    print(f"      {cluster}: {count} indicators")

# ============================================================================
# STEP 3: Stage 2 - Embedding-Based Fine Clustering
# ============================================================================

print("\n[STEP 3] Stage 2: Embedding-based fine clustering...")

# Check if sentence-transformers is available
try:
    from sentence_transformers import SentenceTransformer
    USE_EMBEDDINGS = True
    print("   ✅ sentence-transformers available, using embeddings")
except ImportError:
    USE_EMBEDDINGS = False
    print("   ⚠️ sentence-transformers not available, using keyword-only clustering")

fine_assignments = {}
fine_cluster_data = {}

if USE_EMBEDDINGS:
    from sklearn.cluster import AgglomerativeClustering

    # Load model (using GPU if available)
    print("   Loading embedding model...")
    model = SentenceTransformer('all-MiniLM-L6-v2')

    # Process each coarse cluster
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
            desc = label_data.get('description', '')[:200]  # Truncate long descriptions
            labels_for_embedding.append(f"{label}. {desc}" if desc else label)

        # Embed
        embeddings = model.encode(labels_for_embedding, show_progress_bar=False)

        # Determine number of sub-clusters (1 per 30-50 indicators, min 2, max 8)
        n_subclusters = max(2, min(8, len(node_ids) // 40))

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

        print(f"      {coarse_cluster}: {len(node_ids)} → {n_subclusters} sub-clusters")

else:
    # Fallback: Use coarse clusters as fine clusters
    for coarse_cluster, node_ids in coarse_cluster_nodes.items():
        fine_cluster = f"{coarse_cluster}_0"
        fine_cluster_data[fine_cluster] = {
            'indicators': node_ids,
            'coarse_cluster': coarse_cluster
        }
        for node_id in node_ids:
            fine_assignments[node_id] = fine_cluster

# Statistics
print(f"\n   Fine clustering results:")
print(f"      Total fine clusters: {len(fine_cluster_data)}")

fine_sizes = [len(v['indicators']) for v in fine_cluster_data.values()]
print(f"      Cluster size: min={min(fine_sizes)}, max={max(fine_sizes)}, median={np.median(fine_sizes):.0f}, mean={np.mean(fine_sizes):.1f}")

# ============================================================================
# STEP 4: Generate Representative Labels
# ============================================================================

print("\n[STEP 4] Generating representative labels for clusters...")

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

    # Find common words
    words = []
    for label in labels:
        words.extend(label.lower().split())

    word_counts = Counter(words)
    # Remove common stopwords
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
# STEP 5: Validation
# ============================================================================

print("\n[STEP 5] Validation...")

# Check 1: All nodes assigned
assigned_count = len(fine_assignments)
assert assigned_count == len(all_nodes), f"Not all nodes assigned: {assigned_count} vs {len(all_nodes)}"
print(f"   ✅ All {assigned_count} nodes assigned to clusters")

# Check 2: Unclassified rate
unclassified_count = sum(1 for v in fine_assignments.values() if 'Unclassified' in v)
unclassified_pct = unclassified_count / len(all_nodes)
print(f"   {'✅' if unclassified_pct < 0.10 else '⚠️'} Unclassified: {unclassified_count} ({unclassified_pct:.1%})")

# Check 3: Cluster size distribution
sizes = [len(v['indicators']) for v in fine_cluster_data.values()]
median_size = np.median(sizes)
print(f"   {'✅' if 10 <= median_size <= 200 else '⚠️'} Median cluster size: {median_size:.0f}")

# Check 4: Domain distribution
domain_counts = Counter([v['domain'] for v in fine_cluster_data.values()])
print(f"\n   Domain distribution (clusters):")
for domain, count in domain_counts.most_common():
    print(f"      {domain}: {count} clusters")

# ============================================================================
# STEP 6: Save Results
# ============================================================================

print("\n[STEP 6] Saving results...")

# Prepare output
output_data = {
    'fine_clusters': fine_cluster_data,
    'node_assignments': fine_assignments,
    'coarse_clusters': {k: list(v) for k, v in coarse_cluster_nodes.items()},
    'coarse_assignments': coarse_assignments,
    'metadata': {
        'total_indicators': len(all_nodes),
        'total_fine_clusters': len(fine_cluster_data),
        'total_coarse_clusters': len(coarse_cluster_nodes),
        'unclassified_count': unclassified_count,
        'unclassified_pct': unclassified_pct,
        'timestamp': datetime.now().isoformat(),
        'method': 'Two-stage: keyword + embedding clustering',
        'embedding_model': 'all-MiniLM-L6-v2' if USE_EMBEDDINGS else 'none'
    },
    'domain_statistics': dict(domain_counts)
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
    'unclassified_count': unclassified_count,
    'cluster_sizes': {k: v['size'] for k, v in fine_cluster_data.items()},
    'cluster_domains': {k: v['domain'] for k, v in fine_cluster_data.items()},
    'cluster_labels': {k: v['representative_label'] for k, v in fine_cluster_data.items()},
    'domain_distribution': dict(domain_counts),
    'timestamp': datetime.now().isoformat()
}

json_path = output_dir / "B2_semantic_clustering_summary.json"
with open(json_path, 'w') as f:
    json.dump(json_summary, f, indent=2)
print(f"   ✅ Saved: {json_path}")

# Save sample report
report_path = output_dir / "B2_cluster_samples.txt"
with open(report_path, 'w') as f:
    f.write("B2 SEMANTIC CLUSTERING - SAMPLE REPORT\n")
    f.write("="*60 + "\n\n")

    for fine_cluster, data in sorted(fine_cluster_data.items(), key=lambda x: x[1]['size'], reverse=True)[:30]:
        f.write(f"\n{fine_cluster}\n")
        f.write(f"  Domain: {data['domain']} | Size: {data['size']}\n")
        f.write(f"  Representative: {data['representative_label']}\n")
        f.write(f"  Sample indicators:\n")
        for ind, label in zip(data['sample_indicators'], data['sample_labels']):
            f.write(f"    - {ind}: {label[:60]}...\n" if len(label) > 60 else f"    - {ind}: {label}\n")

print(f"   ✅ Saved: {report_path}")

# ============================================================================
# SUMMARY
# ============================================================================

elapsed = (datetime.now() - start_time).total_seconds()
print("\n" + "="*80)
print("B2 SEMANTIC CLUSTERING COMPLETE")
print("="*80)

print(f"""
Summary:
   Total indicators: {len(all_nodes)}
   Coarse clusters: {len(coarse_cluster_nodes)}
   Fine clusters: {len(fine_cluster_data)}
   Unclassified: {unclassified_count} ({unclassified_pct:.1%})

   Cluster size distribution:
      Min: {min(sizes)}
      Max: {max(sizes)}
      Median: {np.median(sizes):.0f}
      Mean: {np.mean(sizes):.1f}

   Runtime: {elapsed/60:.1f} minutes

Output files:
   - {pkl_path}
   - {json_path}
   - {report_path}

Next step: Run B3.5 semantic hierarchy builder
""")
