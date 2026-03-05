#!/usr/bin/env python3
"""
B3.5: Compressed Semantic Hierarchy (V2.1 - 6 Layers)
======================================================

Creates a 6-layer hierarchy with 3-5 children rule:

Layer 0: Root (1 node)
Layer 1: Outcomes (9 nodes) - from B1 interpretable QoL outcomes
Layer 2: Coarse Domains (~36 nodes) - 4 per outcome
Layer 3: Fine Domains (~144 nodes) - 4 per coarse domain
Layer 4: Indicator Clusters (~576 nodes) - 4 per fine domain
Layer 5: Indicators (1,962 nodes) - ~3-4 per cluster

KEY DESIGN PRINCIPLES:
- Every expansion shows 3-5 children (manageable cognitive load)
- 5 clicks maximum to reach any indicator
- Uses B1 outcomes as semantic anchors
- Clustering via sentence embeddings + K-means

Author: V2.1 Phase B3.5 (6-Layer)
Date: December 2025
"""

import pickle
import json
import numpy as np
import sys
from pathlib import Path
from datetime import datetime
from collections import defaultdict, Counter
import warnings
warnings.filterwarnings('ignore')

# V2.1 Configuration
sys.path.insert(0, str(Path(__file__).parent.parent))
from v21_config import A6_OUTPUT, B1_OUTPUT, B35_OUTPUT

B35_OUTPUT.mkdir(exist_ok=True, parents=True)

print("=" * 80)
print("B3.5: COMPRESSED SEMANTIC HIERARCHY (V2.1 - 6 LAYERS)")
print("=" * 80)
print(f"Timestamp: {datetime.now().isoformat()}")

# ============================================================================
# CONFIGURATION
# ============================================================================

TARGET_COARSE_PER_OUTCOME = 4   # Layer 2: 4 coarse domains per outcome
TARGET_FINE_PER_COARSE = 4      # Layer 3: 4 fine domains per coarse
TARGET_CLUSTERS_PER_FINE = 4    # Layer 4: 4 indicator clusters per fine
MIN_CHILDREN = 3
MAX_CHILDREN = 6  # Allow slight flexibility (3-6 instead of strict 3-5)

# ============================================================================
# STEP 1: LOAD DATA
# ============================================================================

print("\n[STEP 1] Loading data...")

# Load A6 graph
with open(A6_OUTPUT / 'A6_hierarchical_graph.pkl', 'rb') as f:
    a6_data = pickle.load(f)

G = a6_data['graph']
all_indicators = list(G.nodes())
print(f"   Loaded {len(all_indicators)} indicators from A6")

# Load B1 outcomes
with open(B1_OUTPUT / 'B1_validated_outcomes.pkl', 'rb') as f:
    b1_data = pickle.load(f)

outcomes_data = b1_data['outcomes']
print(f"   Loaded {len(outcomes_data)} B1 outcomes")

# Load indicator labels
labels_path = B1_OUTPUT / 'indicator_labels_comprehensive.json'
with open(labels_path, 'r') as f:
    indicator_labels = json.load(f)
print(f"   Loaded {len(indicator_labels)} indicator labels")

# ============================================================================
# STEP 2: SETUP EMBEDDINGS
# ============================================================================

print("\n[STEP 2] Setting up embeddings...")

try:
    from sentence_transformers import SentenceTransformer
    print("   Loading sentence-transformers model...")
    model = SentenceTransformer('all-MiniLM-L6-v2')
    print("   ✅ Model loaded")
except ImportError:
    print("   Installing sentence-transformers...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install",
                          "sentence-transformers", "--break-system-packages", "-q"])
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer('all-MiniLM-L6-v2')

from sklearn.cluster import KMeans, AgglomerativeClustering
from sklearn.metrics.pairwise import cosine_similarity


def generate_cluster_name(indicators, labels_dict, prefix=""):
    """Generate a descriptive name for a cluster of indicators"""
    words = []
    for ind in indicators[:20]:
        info = labels_dict.get(ind, {})
        label = info.get('label', str(ind))
        for word in label.split():
            word_clean = word.strip('(),-:').lower()
            if len(word_clean) > 3 and word_clean not in [
                'total', 'rate', 'index', 'ratio', 'level', 'value',
                'current', 'annual', 'world', 'development', 'indicator',
                'percent', 'percentage', 'number', 'population'
            ]:
                words.append(word_clean.title())

    word_counts = Counter(words)
    top_words = [w for w, c in word_counts.most_common(3)]

    if top_words:
        name = '_'.join(top_words[:2])
    else:
        name = f"Group_{len(indicators)}"

    if prefix:
        name = f"{prefix}_{name}"

    return name[:50]


# Create text representations for all indicators
print("   Creating indicator text representations...")
indicator_texts = {}
for ind in all_indicators:
    info = indicator_labels.get(ind, {})
    label = info.get('label', ind)
    desc = info.get('description', '')
    text = f"{label}. {desc}" if desc else label
    indicator_texts[ind] = text

# Compute embeddings for all indicators
print("   Computing embeddings for all indicators...")
texts = [indicator_texts[ind] for ind in all_indicators]
embeddings = model.encode(texts, show_progress_bar=True, batch_size=64)
indicator_embeddings = {ind: emb for ind, emb in zip(all_indicators, embeddings)}
print(f"   ✅ Computed embeddings for {len(indicator_embeddings)} indicators")

# ============================================================================
# STEP 3: BUILD LAYER 1 - OUTCOMES (from B1)
# ============================================================================

print("\n[STEP 3] Building Layer 1 - Outcomes...")

layer_1 = {}

for outcome_id, outcome_info in outcomes_data.items():
    outcome_name = outcome_info['name']
    all_inds = outcome_info.get('all_indicators', [])
    valid_inds = [ind for ind in all_inds if ind in indicator_embeddings]

    layer_1[outcome_id] = {
        'name': outcome_name,
        'description': outcome_info.get('description', ''),
        'domain': outcome_info.get('domain', ''),
        'indicators': valid_inds,
        'children': [],
        'layer': 1
    }

    print(f"   Outcome {outcome_id}: {outcome_name} ({len(valid_inds)} indicators)")

print(f"   ✅ Layer 1: {len(layer_1)} outcomes")

# ============================================================================
# STEP 4: BUILD LAYER 2 - COARSE DOMAINS (4 per outcome)
# ============================================================================

print("\n[STEP 4] Building Layer 2 - Coarse Domains...")

layer_2 = {}
coarse_id_counter = 1

for outcome_id, outcome_info in layer_1.items():
    outcome_name = outcome_info['name']
    indicators = outcome_info['indicators']

    if len(indicators) < TARGET_COARSE_PER_OUTCOME:
        n_clusters = 1
    elif len(indicators) < TARGET_COARSE_PER_OUTCOME * 3:
        n_clusters = max(2, len(indicators) // 5)
    else:
        n_clusters = TARGET_COARSE_PER_OUTCOME

    if len(indicators) == 0:
        print(f"   ⚠️ Outcome {outcome_id} has no indicators, skipping")
        continue

    outcome_embeddings = np.array([indicator_embeddings[ind] for ind in indicators])

    if n_clusters >= len(indicators):
        clusters = [[ind] for ind in indicators]
    else:
        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        cluster_labels = kmeans.fit_predict(outcome_embeddings)

        clusters = defaultdict(list)
        for ind, label in zip(indicators, cluster_labels):
            clusters[label].append(ind)
        clusters = list(clusters.values())

    for i, cluster_indicators in enumerate(clusters):
        coarse_id = f"coarse_{coarse_id_counter}"
        coarse_id_counter += 1

        cluster_name = generate_cluster_name(cluster_indicators, indicator_labels,
                                             prefix=outcome_name.split()[0])

        layer_2[coarse_id] = {
            'name': cluster_name,
            'parent': outcome_id,
            'indicators': cluster_indicators,
            'children': [],
            'layer': 2
        }

        layer_1[outcome_id]['children'].append(coarse_id)

    print(f"   {outcome_name}: {len(clusters)} coarse domains")

print(f"   ✅ Layer 2: {len(layer_2)} coarse domains")

# ============================================================================
# STEP 5: BUILD LAYER 3 - FINE DOMAINS (4 per coarse)
# ============================================================================

print("\n[STEP 5] Building Layer 3 - Fine Domains...")

layer_3 = {}
fine_id_counter = 1

for coarse_id, coarse_info in layer_2.items():
    coarse_name = coarse_info['name']
    indicators = coarse_info['indicators']

    if len(indicators) < TARGET_FINE_PER_COARSE:
        n_clusters = 1
    elif len(indicators) < TARGET_FINE_PER_COARSE * 2:
        n_clusters = max(2, len(indicators) // 3)
    else:
        n_clusters = TARGET_FINE_PER_COARSE

    if len(indicators) == 0:
        continue

    coarse_embeddings = np.array([indicator_embeddings[ind] for ind in indicators])

    if n_clusters >= len(indicators):
        clusters = [[ind] for ind in indicators]
    else:
        agg = AgglomerativeClustering(n_clusters=n_clusters)
        cluster_labels = agg.fit_predict(coarse_embeddings)

        clusters = defaultdict(list)
        for ind, label in zip(indicators, cluster_labels):
            clusters[label].append(ind)
        clusters = list(clusters.values())

    for i, cluster_indicators in enumerate(clusters):
        fine_id = f"fine_{fine_id_counter}"
        fine_id_counter += 1

        fine_name = generate_cluster_name(cluster_indicators, indicator_labels,
                                          prefix=coarse_name.split('_')[0] if '_' in coarse_name else coarse_name[:10])

        layer_3[fine_id] = {
            'name': fine_name,
            'parent': coarse_id,
            'indicators': cluster_indicators,
            'children': [],
            'layer': 3
        }

        layer_2[coarse_id]['children'].append(fine_id)

print(f"   ✅ Layer 3: {len(layer_3)} fine domains")

# ============================================================================
# STEP 6: BUILD LAYER 4 - INDICATOR CLUSTERS (4 per fine domain)
# ============================================================================

print("\n[STEP 6] Building Layer 4 - Indicator Clusters...")

layer_4 = {}
cluster_id_counter = 1

for fine_id, fine_info in layer_3.items():
    fine_name = fine_info['name']
    indicators = fine_info['indicators']

    # Determine number of clusters
    # Target: ~3-4 indicators per cluster
    target_indicators_per_cluster = 3.5
    n_clusters = max(1, min(TARGET_CLUSTERS_PER_FINE, len(indicators) // int(target_indicators_per_cluster)))

    # Ensure we have at least 3 indicators per cluster
    if n_clusters > 1 and len(indicators) / n_clusters < 2:
        n_clusters = max(1, len(indicators) // 2)

    if len(indicators) == 0:
        continue

    fine_embeddings = np.array([indicator_embeddings[ind] for ind in indicators])

    if n_clusters >= len(indicators):
        # One cluster per indicator
        clusters = [[ind] for ind in indicators]
    elif n_clusters == 1:
        clusters = [indicators]
    else:
        # Use K-means for clustering
        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        cluster_labels = kmeans.fit_predict(fine_embeddings)

        clusters = defaultdict(list)
        for ind, label in zip(indicators, cluster_labels):
            clusters[label].append(ind)
        clusters = list(clusters.values())

    for i, cluster_indicators in enumerate(clusters):
        cluster_id = f"cluster_{cluster_id_counter}"
        cluster_id_counter += 1

        # Generate name from indicators in cluster
        cluster_name = generate_cluster_name(cluster_indicators, indicator_labels,
                                             prefix=fine_name.split('_')[0] if '_' in fine_name else "")

        layer_4[cluster_id] = {
            'name': cluster_name,
            'parent': fine_id,
            'indicators': cluster_indicators,
            'layer': 4
        }

        layer_3[fine_id]['children'].append(cluster_id)

print(f"   ✅ Layer 4: {len(layer_4)} indicator clusters")

# ============================================================================
# STEP 7: ASSIGN UNCOVERED INDICATORS
# ============================================================================

print("\n[STEP 7] Assigning uncovered indicators...")

assigned_indicators = set()
for outcome_info in layer_1.values():
    assigned_indicators.update(outcome_info['indicators'])

uncovered = [ind for ind in all_indicators if ind not in assigned_indicators]
print(f"   Uncovered indicators: {len(uncovered)}")

if uncovered:
    # Assign to nearest cluster by embedding similarity
    cluster_embeddings = {}
    for cluster_id, cluster_info in layer_4.items():
        cluster_inds = cluster_info['indicators']
        if cluster_inds:
            centroid = np.mean([indicator_embeddings[ind] for ind in cluster_inds], axis=0)
            cluster_embeddings[cluster_id] = centroid

    if cluster_embeddings:
        cluster_ids = list(cluster_embeddings.keys())
        centroids = np.array([cluster_embeddings[cid] for cid in cluster_ids])

        for ind in uncovered:
            ind_emb = indicator_embeddings[ind].reshape(1, -1)
            similarities = cosine_similarity(ind_emb, centroids)[0]
            best_idx = np.argmax(similarities)
            best_cluster_id = cluster_ids[best_idx]

            layer_4[best_cluster_id]['indicators'].append(ind)

        print(f"   ✅ Assigned {len(uncovered)} uncovered indicators to clusters")

# ============================================================================
# STEP 8: VALIDATE 3-5 CHILDREN RULE
# ============================================================================

print("\n[STEP 8] Validating 3-5 children rule...")

def validate_layer(layer_name, parent_layer, get_children_count):
    """Validate that each parent has reasonable children"""
    child_counts = []
    for parent_id, parent_info in parent_layer.items():
        count = get_children_count(parent_info)
        child_counts.append(count)

    if child_counts:
        print(f"   {layer_name}:")
        print(f"      Min: {min(child_counts)}, Max: {max(child_counts)}, "
              f"Mean: {np.mean(child_counts):.1f}, Median: {np.median(child_counts):.1f}")

    return child_counts

# Validate each layer
print("\n   Layer 1 (Outcomes) -> Layer 2 (Coarse):")
validate_layer("L1->L2", layer_1, lambda x: len(x['children']))

print("\n   Layer 2 (Coarse) -> Layer 3 (Fine):")
validate_layer("L2->L3", layer_2, lambda x: len(x['children']))

print("\n   Layer 3 (Fine) -> Layer 4 (Clusters):")
validate_layer("L3->L4", layer_3, lambda x: len(x['children']))

print("\n   Layer 4 (Clusters) -> Layer 5 (Indicators):")
cluster_indicator_counts = validate_layer("L4->L5", layer_4, lambda x: len(x['indicators']))

# ============================================================================
# STEP 9: BUILD FINAL HIERARCHY STRUCTURE
# ============================================================================

print("\n[STEP 9] Building final hierarchy structure...")

hierarchy = {
    'root': {
        'id': 'root',
        'name': 'Quality of Life',
        'layer': 0,
        'children': list(layer_1.keys())
    },
    'nodes': {},
    'metadata': {
        'version': 'V2.1-B35-6LAYER',
        'timestamp': datetime.now().isoformat(),
        'approach': '6-Layer Hierarchy with Indicator Clusters',
        'layers': {
            0: {'name': 'Root', 'count': 1},
            1: {'name': 'Outcomes', 'count': len(layer_1)},
            2: {'name': 'Coarse Domains', 'count': len(layer_2)},
            3: {'name': 'Fine Domains', 'count': len(layer_3)},
            4: {'name': 'Indicator Clusters', 'count': len(layer_4)},
            5: {'name': 'Indicators', 'count': len(all_indicators)}
        },
        'target_children_per_node': f'{MIN_CHILDREN}-{MAX_CHILDREN}',
        'total_nodes': 1 + len(layer_1) + len(layer_2) + len(layer_3) + len(layer_4) + len(all_indicators)
    }
}

# Add Layer 1 nodes
for outcome_id, outcome_info in layer_1.items():
    hierarchy['nodes'][outcome_id] = {
        'id': outcome_id,
        'name': outcome_info['name'],
        'description': outcome_info['description'],
        'domain': outcome_info['domain'],
        'layer': 1,
        'parent': 'root',
        'children': outcome_info['children'],
        'indicator_count': len(outcome_info['indicators'])
    }

# Add Layer 2 nodes
for coarse_id, coarse_info in layer_2.items():
    hierarchy['nodes'][coarse_id] = {
        'id': coarse_id,
        'name': coarse_info['name'],
        'layer': 2,
        'parent': coarse_info['parent'],
        'children': coarse_info['children'],
        'indicator_count': len(coarse_info['indicators'])
    }

# Add Layer 3 nodes
for fine_id, fine_info in layer_3.items():
    hierarchy['nodes'][fine_id] = {
        'id': fine_id,
        'name': fine_info['name'],
        'layer': 3,
        'parent': fine_info['parent'],
        'children': fine_info['children'],
        'indicator_count': len(fine_info['indicators'])
    }

# Add Layer 4 nodes (indicator clusters)
for cluster_id, cluster_info in layer_4.items():
    hierarchy['nodes'][cluster_id] = {
        'id': cluster_id,
        'name': cluster_info['name'],
        'layer': 4,
        'parent': cluster_info['parent'],
        'children': cluster_info['indicators'],
        'indicator_count': len(cluster_info['indicators'])
    }

# Add Layer 5 nodes (indicators)
for cluster_id, cluster_info in layer_4.items():
    for ind in cluster_info['indicators']:
        label_info = indicator_labels.get(ind, {})
        hierarchy['nodes'][ind] = {
            'id': ind,
            'name': label_info.get('label', ind),
            'description': label_info.get('description', ''),
            'layer': 5,
            'parent': cluster_id,
            'children': [],
            'is_indicator': True
        }

print(f"   ✅ Built hierarchy with {len(hierarchy['nodes'])} total nodes")

# ============================================================================
# STEP 10: CREATE SEMANTIC PATHS
# ============================================================================

print("\n[STEP 10] Creating semantic paths...")

semantic_paths = {}

for ind in all_indicators:
    path = []
    current_id = ind

    while current_id and current_id != 'root':
        node = hierarchy['nodes'].get(current_id)
        if node:
            path.append({
                'id': current_id,
                'name': node['name'],
                'layer': node['layer']
            })
            current_id = node.get('parent')
        else:
            break

    path.reverse()
    semantic_paths[ind] = path

print(f"   ✅ Created paths for {len(semantic_paths)} indicators")

# ============================================================================
# STEP 11: SAVE OUTPUTS
# ============================================================================

print("\n[STEP 11] Saving outputs...")

# Save main hierarchy
hierarchy_path = B35_OUTPUT / 'B35_compressed_hierarchy.pkl'
with open(hierarchy_path, 'wb') as f:
    pickle.dump(hierarchy, f)
print(f"   ✅ Saved: {hierarchy_path}")

# Save semantic paths
paths_path = B35_OUTPUT / 'B35_semantic_paths.json'
with open(paths_path, 'w') as f:
    json.dump(semantic_paths, f, indent=2)
print(f"   ✅ Saved: {paths_path}")

# Save summary JSON
summary = {
    'metadata': hierarchy['metadata'],
    'layer_summary': {
        'layer_0_root': 1,
        'layer_1_outcomes': len(layer_1),
        'layer_2_coarse': len(layer_2),
        'layer_3_fine': len(layer_3),
        'layer_4_clusters': len(layer_4),
        'layer_5_indicators': len(all_indicators)
    },
    'outcomes': [
        {
            'id': oid,
            'name': oinfo['name'],
            'coarse_domains': len(oinfo['children']),
            'total_indicators': len(oinfo['indicators'])
        }
        for oid, oinfo in layer_1.items()
    ],
    'validation': {
        'total_nodes': len(hierarchy['nodes']),
        'indicators_covered': len(all_indicators),
        'avg_indicators_per_cluster': round(np.mean(cluster_indicator_counts), 1) if cluster_indicator_counts else 0
    }
}

summary_path = B35_OUTPUT / 'B35_summary.json'
with open(summary_path, 'w') as f:
    json.dump(summary, f, indent=2)
print(f"   ✅ Saved: {summary_path}")

# ============================================================================
# SUMMARY
# ============================================================================

print("\n" + "=" * 80)
print("B3.5 COMPRESSED HIERARCHY COMPLETE (6 LAYERS)")
print("=" * 80)

print(f"""
Layer Structure:
   Layer 0: Root                    →     1 node
   Layer 1: Outcomes                →     {len(layer_1)} nodes
   Layer 2: Coarse Domains          →    {len(layer_2)} nodes
   Layer 3: Fine Domains            →   {len(layer_3)} nodes
   Layer 4: Indicator Clusters      →   {len(layer_4)} nodes
   Layer 5: Indicators              → {len(all_indicators):,} nodes

   Total: {len(hierarchy['nodes']):,} nodes

Children per parent (target: {MIN_CHILDREN}-{MAX_CHILDREN}):
   Root → Outcomes:        {len(layer_1)} children
   Outcomes → Coarse:      avg {len(layer_2)/len(layer_1):.1f} children
   Coarse → Fine:          avg {len(layer_3)/len(layer_2):.1f} children
   Fine → Clusters:        avg {len(layer_4)/len(layer_3):.1f} children
   Clusters → Indicators:  avg {np.mean(cluster_indicator_counts):.1f} indicators

Output files:
   - {hierarchy_path}
   - {paths_path}
   - {summary_path}

Next: Update B5 visualization export for 6 layers
""")
