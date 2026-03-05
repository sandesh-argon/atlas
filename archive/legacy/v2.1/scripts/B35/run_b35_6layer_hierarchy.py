#!/usr/bin/env python3
"""
B3.5: Semantic Hierarchy with Flexible Bounds (6-Layer Structure)

Target: 3-5 children per node
Acceptable: 2-8 children
Flag: >8 children (needs attention)

Layer 0: Root                    →     1 node
Layer 1: Outcomes (B1)           →     9 nodes
Layer 2: Coarse Domains          →    ~36 nodes (adaptive)
Layer 3: Fine Domains            →    ~144 nodes (adaptive)
Layer 4: Indicator Groups        →    ~500 nodes (3-5 indicators each)
Layer 5: Indicators              → 1,962 nodes
"""

import pickle
import json
import numpy as np
from sklearn.cluster import KMeans
from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import SentenceTransformer
from pathlib import Path
from collections import defaultdict
from datetime import datetime
import warnings

warnings.filterwarnings('ignore')

print("=" * 80)
print("B3.5: FLEXIBLE SEMANTIC HIERARCHY (6-LAYER)")
print("=" * 80)
print(f"Timestamp: {datetime.now().isoformat()}")

# Paths
BASE_DIR = Path('<repo-root>/v2.0/v2.1')
OUTPUT_DIR = BASE_DIR / 'outputs' / 'B35'
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================================
# STEP 1: LOAD DATA
# ============================================================================

print("\n[STEP 1] Loading data...")

# Load B1 outcomes
b1_path = BASE_DIR / 'outputs' / 'B1' / 'B1_validated_outcomes.pkl'
with open(b1_path, 'rb') as f:
    b1_data = pickle.load(f)
outcomes = b1_data['outcomes']
print(f"   Loaded {len(outcomes)} outcomes from B1")

# Load SHAP scores
shap_path = BASE_DIR / 'outputs' / 'B25' / 'B25_shap_scores.pkl'
with open(shap_path, 'rb') as f:
    shap_scores = pickle.load(f)
print(f"   Loaded SHAP scores for {len(shap_scores)} indicators")

# Load A6 graph for all indicators
a6_path = BASE_DIR / 'outputs' / 'A6' / 'A6_hierarchical_graph.pkl'
with open(a6_path, 'rb') as f:
    a6_data = pickle.load(f)
all_indicators = list(a6_data['graph'].nodes())
print(f"   Loaded {len(all_indicators)} indicators from A6")

# Load indicator labels
labels_path = BASE_DIR / 'outputs' / 'B1' / 'indicator_labels_comprehensive.json'
with open(labels_path, 'r') as f:
    indicator_labels = json.load(f)
print(f"   Loaded {len(indicator_labels)} indicator labels")

# ============================================================================
# STEP 2: LOAD EMBEDDING MODEL & COMPUTE EMBEDDINGS
# ============================================================================

print("\n[STEP 2] Loading embedding model...")
model = SentenceTransformer('all-MiniLM-L6-v2')
print("   Loaded all-MiniLM-L6-v2")


def get_label(ind):
    """Get label string from indicator labels dict"""
    label_data = indicator_labels.get(ind, {})
    if isinstance(label_data, dict):
        return label_data.get('label', ind)
    return str(label_data) if label_data else ind


# Pre-compute embeddings for all indicators
print("   Computing embeddings for all indicators...")
indicator_texts = [get_label(ind) for ind in all_indicators]
all_embeddings = model.encode(indicator_texts, show_progress_bar=True)
embedding_dict = {ind: emb for ind, emb in zip(all_indicators, all_embeddings)}
print(f"   Computed embeddings for {len(embedding_dict)} indicators")

# ============================================================================
# STEP 3: ASSIGN ALL INDICATORS TO OUTCOMES (SEMANTIC ASSIGNMENT)
# ============================================================================

print("\n[STEP 3] Assigning all indicators to outcomes...")

# Get outcome centroids from their descriptions
outcome_centroids = {}
for oid, odata in outcomes.items():
    text_parts = [odata['name'], odata.get('description', '')]
    for ind in odata.get('all_indicators', [])[:20]:
        text_parts.append(get_label(ind))
    centroid_text = ' '.join(text_parts)
    outcome_centroids[oid] = model.encode(centroid_text)

# Assign each indicator to closest outcome
indicator_to_outcome = {}
outcome_indicators = defaultdict(list)

for ind in all_indicators:
    ind_emb = embedding_dict[ind]
    best_outcome = None
    best_sim = -1

    for oid, centroid in outcome_centroids.items():
        sim = cosine_similarity([ind_emb], [centroid])[0][0]
        if sim > best_sim:
            best_sim = sim
            best_outcome = oid

    indicator_to_outcome[ind] = best_outcome
    outcome_indicators[best_outcome].append(ind)

print("   Outcome distribution:")
for oid in sorted(outcomes.keys()):
    name = outcomes[oid]['name']
    count = len(outcome_indicators[oid])
    print(f"      {oid}: {name} ({count} indicators)")

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def generate_cluster_name(indicators, max_words=3):
    """Generate descriptive name from indicator labels"""
    labels = [get_label(ind) for ind in indicators[:10]]
    words = []
    for label in labels:
        words.extend(str(label).replace('_', ' ').replace('-', ' ').split())

    from collections import Counter
    stop_words = ['total', 'rate', 'index', 'ratio', 'number', 'percent', 'value',
                  'current', 'constant', 'annual', 'average', 'gross', 'net',
                  'share', 'growth', 'population', 'world', 'development', 'data']
    word_counts = Counter(w.title() for w in words if len(w) > 3 and w.lower() not in stop_words)
    top_words = [w for w, _ in word_counts.most_common(max_words)]
    return '_'.join(top_words) if top_words else 'Group'


def adaptive_cluster(indicators, layer_name=""):
    """
    Cluster indicators with adaptive target based on size

    Rules:
    - < 6 indicators: 2 clusters (or 1 if < 3)
    - 6-15 indicators: 2-3 clusters
    - 15-40 indicators: 3-5 clusters
    - 40-80 indicators: 4-6 clusters
    - > 80 indicators: 5-8 clusters (cap at 8)
    """
    n = len(indicators)

    if n < 3:
        return {0: indicators}
    elif n < 6:
        n_clusters = 2
    elif n < 15:
        n_clusters = max(2, min(3, n // 5))
    elif n < 40:
        n_clusters = max(3, min(5, n // 8))
    elif n < 80:
        n_clusters = max(4, min(6, n // 12))
    else:
        n_clusters = max(5, min(8, n // 15))

    n_clusters = min(n_clusters, n)  # Can't have more clusters than items

    # Get embeddings
    embeddings = np.array([embedding_dict.get(ind, np.zeros(384)) for ind in indicators])

    # Cluster
    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    labels = kmeans.fit_predict(embeddings)

    # Group by cluster
    clusters = defaultdict(list)
    for ind, label in zip(indicators, labels):
        clusters[label].append(ind)

    return dict(clusters)


def split_for_groups(indicators, target_size=4):
    """
    Split indicators into groups of ~target_size for Layer 4
    Ensures each group has 2-5 indicators (no more than 5)
    """
    n = len(indicators)
    if n <= 5:
        return [indicators]

    # Calculate number of groups needed
    n_groups = max(2, (n + target_size - 1) // target_size)

    # Ensure no group has more than 5
    while n / n_groups > 5:
        n_groups += 1

    # Distribute evenly
    groups = []
    base_size = n // n_groups
    remainder = n % n_groups

    idx = 0
    for i in range(n_groups):
        size = base_size + (1 if i < remainder else 0)
        groups.append(indicators[idx:idx+size])
        idx += size

    return groups


# ============================================================================
# BUILD 6-LAYER HIERARCHY
# ============================================================================

print("\n[LAYER 0] Creating root node...")

hierarchy = {
    'root': {
        'id': 'root',
        'name': 'Quality of Life',
        'layer': 0,
        'type': 'root',
        'parent': None,
        'children': []
    },
    'nodes': {},
    'layer_counts': {0: 1, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
}

# ============================================================================
# LAYER 1: OUTCOMES
# ============================================================================

print("\n[LAYER 1] Creating outcome nodes...")

layer_1_nodes = {}

for outcome_id, outcome_data in outcomes.items():
    node_name = outcome_data['name']

    layer_1_nodes[outcome_id] = {
        'id': outcome_id,
        'name': node_name,
        'layer': 1,
        'type': 'outcome',
        'description': outcome_data.get('description', ''),
        'domain': node_name.split(' & ')[0] if ' & ' in node_name else node_name.split()[0],
        'indicators': outcome_indicators[outcome_id],
        'parent': 'root',
        'children': []
    }

    hierarchy['root']['children'].append(outcome_id)

hierarchy['nodes'].update(layer_1_nodes)
hierarchy['layer_counts'][1] = len(layer_1_nodes)

print(f"   Created {len(layer_1_nodes)} outcome nodes")
for oid, odata in layer_1_nodes.items():
    print(f"      {oid}: {odata['name']} ({len(odata['indicators'])} indicators)")

# ============================================================================
# LAYER 2: COARSE DOMAINS (Adaptive clustering)
# ============================================================================

print("\n[LAYER 2] Creating coarse domain nodes (adaptive)...")

layer_2_nodes = {}
coarse_counter = 1

for outcome_id, outcome_node in layer_1_nodes.items():
    indicators = outcome_node['indicators']
    outcome_name = outcome_node['name'].replace(' & ', '_').replace(' ', '_')

    # Adaptive clustering
    clusters = adaptive_cluster(indicators, outcome_node['name'])

    for cluster_idx, cluster_indicators in clusters.items():
        if len(cluster_indicators) == 0:
            continue

        coarse_id = f"coarse_{coarse_counter}"
        coarse_counter += 1

        cluster_name = generate_cluster_name(cluster_indicators)

        layer_2_nodes[coarse_id] = {
            'id': coarse_id,
            'name': f"{outcome_name}_{cluster_name}",
            'layer': 2,
            'type': 'coarse_domain',
            'domain': outcome_node['domain'],
            'indicators': cluster_indicators,
            'parent': outcome_id,
            'children': []
        }

        outcome_node['children'].append(coarse_id)

hierarchy['nodes'].update(layer_2_nodes)
hierarchy['layer_counts'][2] = len(layer_2_nodes)

print(f"   Created {len(layer_2_nodes)} coarse domain nodes")

# ============================================================================
# LAYER 3: FINE DOMAINS (Adaptive clustering)
# ============================================================================

print("\n[LAYER 3] Creating fine domain nodes (adaptive)...")

layer_3_nodes = {}
fine_counter = 1

for coarse_id, coarse_node in layer_2_nodes.items():
    indicators = coarse_node['indicators']

    # Adaptive clustering
    clusters = adaptive_cluster(indicators, coarse_node['name'])

    for cluster_idx, cluster_indicators in clusters.items():
        if len(cluster_indicators) == 0:
            continue

        fine_id = f"fine_{fine_counter}"
        fine_counter += 1

        cluster_name = generate_cluster_name(cluster_indicators)

        layer_3_nodes[fine_id] = {
            'id': fine_id,
            'name': f"{coarse_node['name']}_{cluster_name}",
            'layer': 3,
            'type': 'fine_domain',
            'domain': coarse_node['domain'],
            'indicators': cluster_indicators,
            'parent': coarse_id,
            'children': []
        }

        coarse_node['children'].append(fine_id)

hierarchy['nodes'].update(layer_3_nodes)
hierarchy['layer_counts'][3] = len(layer_3_nodes)

print(f"   Created {len(layer_3_nodes)} fine domain nodes")

# ============================================================================
# LAYER 4: INDICATOR GROUPS (3-5 indicators each)
# ============================================================================

print("\n[LAYER 4] Creating indicator group nodes (3-5 indicators each)...")

layer_4_nodes = {}
group_counter = 1

for fine_id, fine_node in layer_3_nodes.items():
    indicators = fine_node['indicators']

    # Split into groups of 3-5
    groups = split_for_groups(indicators, target_size=4)

    for group_indicators in groups:
        if len(group_indicators) == 0:
            continue

        group_id = f"group_{group_counter}"
        group_counter += 1

        group_name = generate_cluster_name(group_indicators)

        layer_4_nodes[group_id] = {
            'id': group_id,
            'name': f"{fine_node['name']}_{group_name}",
            'layer': 4,
            'type': 'indicator_group',
            'domain': fine_node['domain'],
            'indicators': group_indicators,
            'parent': fine_id,
            'children': []
        }

        fine_node['children'].append(group_id)

hierarchy['nodes'].update(layer_4_nodes)
hierarchy['layer_counts'][4] = len(layer_4_nodes)

print(f"   Created {len(layer_4_nodes)} indicator group nodes")

# ============================================================================
# LAYER 5: INDICATORS
# ============================================================================

print("\n[LAYER 5] Creating indicator nodes...")

layer_5_nodes = {}

for group_id, group_node in layer_4_nodes.items():
    for indicator in group_node['indicators']:
        shap_data = shap_scores.get(indicator, {})
        shap_value = shap_data.get('shap_normalized', 0.0) if isinstance(shap_data, dict) else 0.0

        layer_5_nodes[indicator] = {
            'id': indicator,
            'name': get_label(indicator),
            'layer': 5,
            'type': 'indicator',
            'domain': group_node['domain'],
            'shap_importance': shap_value,
            'parent': group_id,
            'children': []
        }

        group_node['children'].append(indicator)

hierarchy['nodes'].update(layer_5_nodes)
hierarchy['layer_counts'][5] = len(layer_5_nodes)

print(f"   Created {len(layer_5_nodes)} indicator nodes")

# ============================================================================
# VALIDATION: FLEXIBLE BOUNDS (Target 3-5, Allow 2-8)
# ============================================================================

print("\n" + "=" * 80)
print("VALIDATION: FLEXIBLE BOUNDS (Target: 3-5, Allow: 2-8)")
print("=" * 80)


def validate_flexible(hierarchy):
    """Validate children distribution with flexible bounds"""
    results = {}

    # Check root
    root_children = len(hierarchy['root']['children'])
    results['root'] = {'count': root_children, 'status': 'ok' if root_children <= 10 else 'over'}

    # Check each layer
    for layer in range(1, 5):
        layer_nodes = [n for n in hierarchy['nodes'].values() if n['layer'] == layer]

        stats = {
            'total': 0,
            'ideal_3_5': 0,
            'acceptable_2_8': 0,
            'under_2': 0,
            'over_8': 0,
            'children_dist': []
        }

        for node in layer_nodes:
            n_children = len(node.get('children', []))
            if n_children == 0:
                continue

            stats['total'] += 1
            stats['children_dist'].append(n_children)

            if 3 <= n_children <= 5:
                stats['ideal_3_5'] += 1
                stats['acceptable_2_8'] += 1
            elif 2 <= n_children <= 8:
                stats['acceptable_2_8'] += 1
            elif n_children < 2:
                stats['under_2'] += 1
            else:
                stats['over_8'] += 1

        results[f'layer_{layer}'] = stats

    return results


validation = validate_flexible(hierarchy)

print(f"\n   Root: {validation['root']['count']} children (9 outcomes)")

for layer in range(1, 5):
    stats = validation[f'layer_{layer}']
    if stats['total'] > 0:
        pct_ideal = stats['ideal_3_5'] / stats['total'] * 100
        pct_acceptable = stats['acceptable_2_8'] / stats['total'] * 100

        layer_names = {1: 'Outcomes→Coarse', 2: 'Coarse→Fine', 3: 'Fine→Groups', 4: 'Groups→Indicators'}

        print(f"\n   Layer {layer} ({layer_names[layer]}):")
        print(f"      Total non-leaf: {stats['total']}")
        print(f"      Ideal (3-5): {stats['ideal_3_5']} ({pct_ideal:.1f}%)")
        print(f"      Acceptable (2-8): {stats['acceptable_2_8']} ({pct_acceptable:.1f}%)")

        if stats['children_dist']:
            print(f"      Range: [{min(stats['children_dist'])}-{max(stats['children_dist'])}], "
                  f"avg={np.mean(stats['children_dist']):.1f}")

        if stats['under_2'] > 0:
            print(f"      ⚠️  Under 2: {stats['under_2']}")
        if stats['over_8'] > 0:
            print(f"      ⚠️  Over 8: {stats['over_8']}")

# ============================================================================
# SUMMARY
# ============================================================================

print("\n" + "=" * 80)
print("6-LAYER HIERARCHY SUMMARY")
print("=" * 80)

print("\nLayer Counts:")
layer_names = ['Root', 'Outcomes', 'Coarse Domains', 'Fine Domains', 'Indicator Groups', 'Indicators']
for layer in range(6):
    count = hierarchy['layer_counts'][layer]
    print(f"   Layer {layer} ({layer_names[layer]}): {count:,} nodes")

total_nodes = sum(hierarchy['layer_counts'].values())
print(f"\nTotal hierarchy nodes: {total_nodes:,}")

# ============================================================================
# BUILD SEMANTIC PATHS
# ============================================================================

print("\n[STEP 4] Building semantic paths...")

semantic_paths = {}


def get_path(node_id, hierarchy):
    """Build semantic path from root to node"""
    path_parts = []
    current_id = node_id

    while current_id:
        if current_id == 'root':
            break

        node = hierarchy['nodes'].get(current_id)
        if node:
            path_parts.append(node['name'])
            current_id = node['parent']
        else:
            break

    path_parts.reverse()
    return ' > '.join(path_parts)


for node_id in hierarchy['nodes']:
    if hierarchy['nodes'][node_id]['layer'] == 5:
        semantic_paths[node_id] = get_path(node_id, hierarchy)

print(f"   Built {len(semantic_paths)} semantic paths")

# ============================================================================
# SAVE OUTPUTS
# ============================================================================

print("\n[STEP 5] Saving outputs...")

# Save hierarchy pickle
hierarchy_path = OUTPUT_DIR / 'B35_semantic_hierarchy_6layer.pkl'
with open(hierarchy_path, 'wb') as f:
    pickle.dump(hierarchy, f)
print(f"   Saved: {hierarchy_path}")

# Save semantic paths JSON
paths_path = OUTPUT_DIR / 'B35_node_semantic_paths.json'
with open(paths_path, 'w') as f:
    json.dump(semantic_paths, f, indent=2)
print(f"   Saved: {paths_path}")

# Save SHAP scores with hierarchy info
shap_output = {
    ind: {
        'shap_normalized': shap_scores.get(ind, {}).get('shap_normalized', 0.0) if isinstance(shap_scores.get(ind), dict) else 0.0,
        'layer': hierarchy['nodes'].get(ind, {}).get('layer', 5),
        'parent': hierarchy['nodes'].get(ind, {}).get('parent', None)
    }
    for ind in all_indicators
}
shap_path = OUTPUT_DIR / 'B35_shap_scores.pkl'
with open(shap_path, 'wb') as f:
    pickle.dump(shap_output, f)
print(f"   Saved: {shap_path}")

print("\n" + "=" * 80)
print("B3.5 FLEXIBLE HIERARCHY COMPLETE")
print("=" * 80)
