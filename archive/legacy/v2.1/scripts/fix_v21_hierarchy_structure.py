#!/usr/bin/env python3
"""
Fix V2.1 hierarchy structure to match V2 format
Rebuilds nested hierarchy from semantic_path data
"""

import pickle
import json
import shutil
from collections import defaultdict
from pathlib import Path

print("="*80)
print("FIXING V2.1 HIERARCHY STRUCTURE")
print("="*80)

# Paths
BASE_DIR = Path('<repo-root>/v2.0/v2.1')
B35_DIR = BASE_DIR / 'outputs' / 'B35'
B25_DIR = BASE_DIR / 'outputs' / 'B25'

# ============================================================================
# STEP 1: Load V2.1 Data
# ============================================================================

print("\n[1/4] Loading V2.1 data...")

# Load hierarchy (broken)
with open(B35_DIR / 'B35_semantic_hierarchy.pkl', 'rb') as f:
    v21_hierarchy = pickle.load(f)

# Load semantic paths (this has the actual structure)
with open(B35_DIR / 'B35_node_semantic_paths.json', 'r') as f:
    semantic_paths = json.load(f)

# Load viz JSON
viz_json_path = B35_DIR / 'causal_graph_v2_FINAL.json'
if viz_json_path.exists():
    with open(viz_json_path, 'r') as f:
        viz_json = json.load(f)
else:
    # Fallback
    viz_json = {'nodes': list(semantic_paths.keys()), 'edges': []}

# Load SHAP scores
shap_path = B25_DIR / 'B25_shap_scores_V21.pkl'
if shap_path.exists():
    with open(shap_path, 'rb') as f:
        shap_scores = pickle.load(f)
else:
    shap_scores = {}

print(f"✓ Loaded {len(semantic_paths)} semantic paths")
print(f"✓ Loaded {len(viz_json.get('nodes', []))} nodes from viz JSON")
print(f"✓ Loaded {len(shap_scores)} SHAP scores")

# ============================================================================
# STEP 2: Build Nested Hierarchy from Semantic Paths
# ============================================================================

print("\n[2/4] Building nested hierarchy from semantic paths...")

# Initialize hierarchy structure (V2 format)
fixed_hierarchy = {
    'super_domains': {},
    'domains': {},
    'subdomains': {},
    'coarse_clusters': {},
    'fine_clusters': {},
    'indicators': {},
    'metadata': {
        'version': 'V2.1_FIXED',
        'total_nodes': len(semantic_paths),
        'layer_structure': {}
    }
}

# Process each node's semantic path
for node_id, path_data in semantic_paths.items():
    # Extract hierarchy levels from path_data
    super_domain = path_data.get('super_domain', 'Unknown')
    domain = path_data.get('domain', 'Unknown')
    subdomain = path_data.get('subdomain', 'Unknown')
    coarse_cluster = path_data.get('coarse_cluster', None)
    fine_cluster = path_data.get('fine_cluster', None)

    # Get SHAP score
    shap_val = path_data.get('shap_score', 0.0)
    if not shap_val and node_id in shap_scores:
        score_data = shap_scores[node_id]
        if isinstance(score_data, dict):
            shap_val = score_data.get('shap_normalized', score_data.get('shap_mean', 0.0))
        else:
            shap_val = float(score_data) if score_data else 0.0

    # Build super_domain entry
    if super_domain not in fixed_hierarchy['super_domains']:
        fixed_hierarchy['super_domains'][super_domain] = {
            'id': super_domain,
            'label': super_domain,
            'type': 'super_domain',
            'layer': 1,
            'children': set(),
            'parent': 'Root'
        }

    # Build domain entry
    if domain not in fixed_hierarchy['domains']:
        fixed_hierarchy['domains'][domain] = {
            'id': domain,
            'label': domain,
            'type': 'domain',
            'layer': 2,
            'children': set(),
            'parent': super_domain
        }
    fixed_hierarchy['super_domains'][super_domain]['children'].add(domain)

    # Build subdomain entry
    if subdomain not in fixed_hierarchy['subdomains']:
        fixed_hierarchy['subdomains'][subdomain] = {
            'id': subdomain,
            'label': subdomain,
            'type': 'subdomain',
            'layer': 3,
            'children': set(),
            'parent': domain
        }
    fixed_hierarchy['domains'][domain]['children'].add(subdomain)

    # Build coarse cluster entry (if exists)
    if coarse_cluster:
        if coarse_cluster not in fixed_hierarchy['coarse_clusters']:
            fixed_hierarchy['coarse_clusters'][coarse_cluster] = {
                'id': coarse_cluster,
                'label': coarse_cluster,
                'type': 'coarse_cluster',
                'layer': 4,
                'children': set(),
                'parent': subdomain
            }
        fixed_hierarchy['subdomains'][subdomain]['children'].add(coarse_cluster)

        # Build fine cluster entry (if exists)
        if fine_cluster:
            if fine_cluster not in fixed_hierarchy['fine_clusters']:
                fixed_hierarchy['fine_clusters'][fine_cluster] = {
                    'id': fine_cluster,
                    'label': fine_cluster,
                    'type': 'fine_cluster',
                    'layer': 5,
                    'children': set(),
                    'parent': coarse_cluster
                }
            fixed_hierarchy['coarse_clusters'][coarse_cluster]['children'].add(fine_cluster)

            # Add indicator to fine cluster
            parent_cluster = fine_cluster
        else:
            # Add indicator to coarse cluster
            parent_cluster = coarse_cluster
    else:
        # Add indicator to subdomain
        parent_cluster = subdomain

    # Build indicator entry
    fixed_hierarchy['indicators'][node_id] = {
        'id': node_id,
        'label': path_data.get('indicator_label', node_id),
        'type': 'indicator',
        'layer': path_data.get('hierarchy_level', 6),
        'causal_layer': path_data.get('causal_layer', 0),
        'parent': parent_cluster,
        'shap': shap_val,
        'full_path': path_data.get('full_path', ''),
        'super_domain': super_domain,
        'domain': domain,
        'subdomain': subdomain,
        'coarse_cluster': coarse_cluster,
        'fine_cluster': fine_cluster
    }

    # Add indicator to parent's children
    if fine_cluster and fine_cluster in fixed_hierarchy['fine_clusters']:
        fixed_hierarchy['fine_clusters'][fine_cluster]['children'].add(node_id)
    elif coarse_cluster and coarse_cluster in fixed_hierarchy['coarse_clusters']:
        fixed_hierarchy['coarse_clusters'][coarse_cluster]['children'].add(node_id)
    elif subdomain in fixed_hierarchy['subdomains']:
        fixed_hierarchy['subdomains'][subdomain]['children'].add(node_id)

# Convert sets to lists for JSON serialization
for level in ['super_domains', 'domains', 'subdomains', 'coarse_clusters', 'fine_clusters']:
    for item in fixed_hierarchy[level].values():
        if 'children' in item:
            item['children'] = sorted(list(item['children']))

print(f"✓ Built hierarchy:")
print(f"  Super-domains: {len(fixed_hierarchy['super_domains'])}")
print(f"  Domains: {len(fixed_hierarchy['domains'])}")
print(f"  Subdomains: {len(fixed_hierarchy['subdomains'])}")
print(f"  Coarse clusters: {len(fixed_hierarchy['coarse_clusters'])}")
print(f"  Fine clusters: {len(fixed_hierarchy['fine_clusters'])}")
print(f"  Indicators: {len(fixed_hierarchy['indicators'])}")

# ============================================================================
# STEP 3: Add Metadata
# ============================================================================

print("\n[3/4] Adding metadata...")

# Layer structure
fixed_hierarchy['metadata']['layer_structure'] = {
    0: {'name': 'Root', 'count': 1},
    1: {'name': 'Super-domains', 'count': len(fixed_hierarchy['super_domains'])},
    2: {'name': 'Domains', 'count': len(fixed_hierarchy['domains'])},
    3: {'name': 'Subdomains', 'count': len(fixed_hierarchy['subdomains'])},
    4: {'name': 'Coarse Clusters', 'count': len(fixed_hierarchy['coarse_clusters'])},
    5: {'name': 'Fine Clusters', 'count': len(fixed_hierarchy['fine_clusters'])},
    6: {'name': 'Indicators', 'count': len(fixed_hierarchy['indicators'])}
}

# Add node/edge counts
fixed_hierarchy['metadata']['node_count'] = len(fixed_hierarchy['indicators'])
fixed_hierarchy['metadata']['edge_count'] = len(viz_json.get('edges', []))

# Domain distribution
domain_node_counts = defaultdict(int)
for node_id, path in semantic_paths.items():
    domain = path.get('domain', 'Unknown')
    domain_node_counts[domain] += 1

fixed_hierarchy['metadata']['domain_distribution'] = dict(domain_node_counts)

# Super-domain distribution
super_domain_counts = defaultdict(int)
for node_id, path in semantic_paths.items():
    sd = path.get('super_domain', 'Unknown')
    super_domain_counts[sd] += 1
fixed_hierarchy['metadata']['super_domain_distribution'] = dict(super_domain_counts)

print(f"✓ Metadata added")

# ============================================================================
# STEP 4: Save Fixed Hierarchy
# ============================================================================

print("\n[4/4] Saving fixed hierarchy...")

# Backup original
backup_path = B35_DIR / 'B35_semantic_hierarchy_BROKEN_BACKUP.pkl'
shutil.copy(B35_DIR / 'B35_semantic_hierarchy.pkl', backup_path)
print(f"✓ Backed up original to: {backup_path}")

# Save as pickle (replaces original)
output_pkl = B35_DIR / 'B35_semantic_hierarchy.pkl'
with open(output_pkl, 'wb') as f:
    pickle.dump(fixed_hierarchy, f)
print(f"✓ Saved: {output_pkl}")

# Save as JSON (for inspection) - with indicators truncated
output_json = B35_DIR / 'B35_semantic_hierarchy_FIXED.json'

json_hierarchy = {
    'super_domains': fixed_hierarchy['super_domains'],
    'domains': fixed_hierarchy['domains'],
    'subdomains': fixed_hierarchy['subdomains'],
    'coarse_clusters': fixed_hierarchy['coarse_clusters'],
    'fine_clusters': fixed_hierarchy['fine_clusters'],
    'indicators_sample': dict(list(fixed_hierarchy['indicators'].items())[:20]),
    'indicators_count': len(fixed_hierarchy['indicators']),
    'metadata': fixed_hierarchy['metadata']
}

with open(output_json, 'w') as f:
    json.dump(json_hierarchy, f, indent=2)
print(f"✓ Saved JSON preview: {output_json}")

# ============================================================================
# VALIDATION
# ============================================================================

print("\n" + "="*80)
print("VALIDATION")
print("="*80)

# Check structure matches V2 format
required_keys = ['super_domains', 'domains', 'subdomains', 'coarse_clusters', 'fine_clusters', 'indicators', 'metadata']
missing = [k for k in required_keys if k not in fixed_hierarchy]

if not missing:
    print("✅ All required keys present (V2 format)")
else:
    print(f"❌ Missing keys: {missing}")

# Check hierarchy integrity
print("\nHierarchy integrity:")

# Check all domains have super_domain parent
orphan_domains = []
for domain_id, domain in fixed_hierarchy['domains'].items():
    parent = domain['parent']
    if parent not in fixed_hierarchy['super_domains']:
        orphan_domains.append(domain_id)

if not orphan_domains:
    print("✅ All domains have valid super_domain parents")
else:
    print(f"⚠️  {len(orphan_domains)} orphan domains: {orphan_domains[:5]}")

# Check all subdomains have domain parent
orphan_subdomains = []
for sd_id, sd in fixed_hierarchy['subdomains'].items():
    parent = sd['parent']
    if parent not in fixed_hierarchy['domains']:
        orphan_subdomains.append(sd_id)

if not orphan_subdomains:
    print("✅ All subdomains have valid domain parents")
else:
    print(f"⚠️  {len(orphan_subdomains)} orphan subdomains: {orphan_subdomains[:5]}")

# Check all indicators have valid parents
orphan_indicators = []
for ind_id, ind in fixed_hierarchy['indicators'].items():
    parent = ind['parent']
    valid_parent = (
        parent in fixed_hierarchy['subdomains'] or
        parent in fixed_hierarchy['coarse_clusters'] or
        parent in fixed_hierarchy['fine_clusters']
    )
    if not valid_parent:
        orphan_indicators.append(ind_id)

if not orphan_indicators:
    print("✅ All indicators have valid parents")
else:
    print(f"⚠️  {len(orphan_indicators)} orphan indicators: {orphan_indicators[:5]}")

# Print hierarchy summary
print("\n" + "="*80)
print("HIERARCHY SUMMARY")
print("="*80)

print("\nSuper-domains:")
for sd_id, sd in fixed_hierarchy['super_domains'].items():
    count = super_domain_counts.get(sd_id, 0)
    print(f"  {sd_id}: {count} indicators, {len(sd['children'])} domains")

print("\nDomains:")
for d_id, d in fixed_hierarchy['domains'].items():
    count = domain_node_counts.get(d_id, 0)
    print(f"  {d_id}: {count} indicators, {len(d['children'])} subdomains")

print("\n✅ HIERARCHY STRUCTURE FIXED")
print("✅ Ready for visualization (V2 format)")
