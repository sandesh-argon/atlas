#!/usr/bin/env python3
"""
Pre-compute 54 graph permutations for visualization exploration
Generates static JSONs covering all meaningful scale/method/balance combinations

Uses the fully classified causal_graph_v2_FULL.json (all 8,126 nodes have domains)
"""

import json
import pickle
import numpy as np
import networkx as nx
from pathlib import Path
from collections import defaultdict, Counter
from tqdm import tqdm

# ============================================================================
# CONFIGURATION - 54 Graph Permutations
# ============================================================================

GRAPH_CONFIGS = [
    # ========================================================================
    # GROUP 1: SCALE EXPLORATION (18 graphs)
    # Node count × Layer compression (governance dominance assessment)
    # ========================================================================
    {'nodes': 30, 'layers': 2, 'method': 'composite', 'balance': False, 'gov_cap': None},
    {'nodes': 30, 'layers': 5, 'method': 'composite', 'balance': False, 'gov_cap': None},

    {'nodes': 50, 'layers': 2, 'method': 'composite', 'balance': False, 'gov_cap': None},
    {'nodes': 50, 'layers': 3, 'method': 'composite', 'balance': False, 'gov_cap': None},
    {'nodes': 50, 'layers': 5, 'method': 'composite', 'balance': False, 'gov_cap': None},

    {'nodes': 100, 'layers': 2, 'method': 'composite', 'balance': False, 'gov_cap': None},
    {'nodes': 100, 'layers': 3, 'method': 'composite', 'balance': False, 'gov_cap': None},
    {'nodes': 100, 'layers': 5, 'method': 'composite', 'balance': False, 'gov_cap': None},
    {'nodes': 100, 'layers': 21, 'method': 'composite', 'balance': False, 'gov_cap': None},

    {'nodes': 200, 'layers': 3, 'method': 'composite', 'balance': False, 'gov_cap': None},
    {'nodes': 200, 'layers': 5, 'method': 'composite', 'balance': False, 'gov_cap': None},
    {'nodes': 200, 'layers': 21, 'method': 'composite', 'balance': False, 'gov_cap': None},

    {'nodes': 290, 'layers': 5, 'method': 'composite', 'balance': False, 'gov_cap': None},
    {'nodes': 290, 'layers': 21, 'method': 'composite', 'balance': False, 'gov_cap': None},

    {'nodes': 500, 'layers': 5, 'method': 'composite', 'balance': False, 'gov_cap': None},
    {'nodes': 500, 'layers': 21, 'method': 'composite', 'balance': False, 'gov_cap': None},

    {'nodes': 1000, 'layers': 21, 'method': 'composite', 'balance': False, 'gov_cap': None},
    {'nodes': 8126, 'layers': 21, 'method': 'composite', 'balance': False, 'gov_cap': None},

    # ========================================================================
    # GROUP 2: PRUNING METHOD COMPARISON (15 graphs)
    # Different importance metrics at key node counts
    # ========================================================================
    {'nodes': 100, 'layers': 5, 'method': 'shap', 'balance': False, 'gov_cap': None},
    {'nodes': 100, 'layers': 5, 'method': 'betweenness', 'balance': False, 'gov_cap': None},
    {'nodes': 100, 'layers': 5, 'method': 'pagerank', 'balance': False, 'gov_cap': None},
    {'nodes': 100, 'layers': 5, 'method': 'degree', 'balance': False, 'gov_cap': None},

    {'nodes': 200, 'layers': 5, 'method': 'shap', 'balance': False, 'gov_cap': None},
    {'nodes': 200, 'layers': 5, 'method': 'betweenness', 'balance': False, 'gov_cap': None},
    {'nodes': 200, 'layers': 5, 'method': 'pagerank', 'balance': False, 'gov_cap': None},

    {'nodes': 290, 'layers': 5, 'method': 'shap', 'balance': False, 'gov_cap': None},
    {'nodes': 290, 'layers': 5, 'method': 'betweenness', 'balance': False, 'gov_cap': None},

    {'nodes': 500, 'layers': 5, 'method': 'shap', 'balance': False, 'gov_cap': None},
    {'nodes': 500, 'layers': 5, 'method': 'betweenness', 'balance': False, 'gov_cap': None},

    {'nodes': 1000, 'layers': 21, 'method': 'shap', 'balance': False, 'gov_cap': None},
    {'nodes': 1000, 'layers': 21, 'method': 'betweenness', 'balance': False, 'gov_cap': None},

    {'nodes': 8126, 'layers': 21, 'method': 'shap', 'balance': False, 'gov_cap': None},
    {'nodes': 8126, 'layers': 21, 'method': 'betweenness', 'balance': False, 'gov_cap': None},

    # ========================================================================
    # GROUP 3: DOMAIN BALANCING (12 graphs)
    # Test governance cap vs domain-balanced selection
    # ========================================================================
    # Balanced domains (equal representation)
    {'nodes': 100, 'layers': 5, 'method': 'composite', 'balance': True, 'gov_cap': None},
    {'nodes': 200, 'layers': 5, 'method': 'composite', 'balance': True, 'gov_cap': None},
    {'nodes': 290, 'layers': 5, 'method': 'composite', 'balance': True, 'gov_cap': None},
    {'nodes': 500, 'layers': 5, 'method': 'composite', 'balance': True, 'gov_cap': None},

    # Governance capped at 30%
    {'nodes': 100, 'layers': 5, 'method': 'composite', 'balance': False, 'gov_cap': 0.30},
    {'nodes': 200, 'layers': 5, 'method': 'composite', 'balance': False, 'gov_cap': 0.30},
    {'nodes': 290, 'layers': 5, 'method': 'composite', 'balance': False, 'gov_cap': 0.30},

    # Governance capped at 40%
    {'nodes': 100, 'layers': 5, 'method': 'composite', 'balance': False, 'gov_cap': 0.40},
    {'nodes': 200, 'layers': 5, 'method': 'composite', 'balance': False, 'gov_cap': 0.40},
    {'nodes': 290, 'layers': 5, 'method': 'composite', 'balance': False, 'gov_cap': 0.40},

    # Governance capped at 50%
    {'nodes': 200, 'layers': 5, 'method': 'composite', 'balance': False, 'gov_cap': 0.50},
    {'nodes': 290, 'layers': 5, 'method': 'composite', 'balance': False, 'gov_cap': 0.50},

    # ========================================================================
    # GROUP 4: EXTREME CASES (9 graphs)
    # Test edge cases for visualization limits
    # ========================================================================
    # Maximum compression (2 layers)
    {'nodes': 100, 'layers': 2, 'method': 'shap', 'balance': False, 'gov_cap': None},
    {'nodes': 200, 'layers': 2, 'method': 'composite', 'balance': False, 'gov_cap': None},
    {'nodes': 290, 'layers': 2, 'method': 'composite', 'balance': False, 'gov_cap': None},

    # Full granularity (21 layers)
    {'nodes': 100, 'layers': 21, 'method': 'shap', 'balance': False, 'gov_cap': None},
    {'nodes': 200, 'layers': 21, 'method': 'shap', 'balance': False, 'gov_cap': None},
    {'nodes': 290, 'layers': 21, 'method': 'shap', 'balance': False, 'gov_cap': None},

    # Tiny graphs (mobile-scale)
    {'nodes': 20, 'layers': 2, 'method': 'composite', 'balance': False, 'gov_cap': None},
    {'nodes': 30, 'layers': 2, 'method': 'shap', 'balance': True, 'gov_cap': None},
    {'nodes': 30, 'layers': 2, 'method': 'composite', 'balance': False, 'gov_cap': 0.30},
]

# Output directory
OUTPUT_DIR = Path('precompute_permutations/outputs')
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================================
# LOAD DATA
# ============================================================================

print("="*70)
print("LOADING DATA")
print("="*70)

# Load the full classified graph
print("\nLoading causal_graph_v2_FULL.json...")
with open('outputs/causal_graph_v2_FULL.json', 'r') as f:
    full_graph_data = json.load(f)

nodes_list = full_graph_data['nodes']
edges_list = full_graph_data['edges']

print(f"  Nodes: {len(nodes_list)}")
print(f"  Edges: {len(edges_list)}")

# Build NetworkX graph
print("\nBuilding NetworkX graph...")
G = nx.DiGraph()

for node in nodes_list:
    G.add_node(node['id'], **node)

for edge in edges_list:
    G.add_edge(edge['source'], edge['target'], **edge)

print(f"  Graph nodes: {G.number_of_nodes()}")
print(f"  Graph edges: {G.number_of_edges()}")

# Extract node attributes
node_domains = {n['id']: n['domain'] for n in nodes_list}
node_layers = {n['id']: n.get('causal_layer', 0) for n in nodes_list}
node_labels = {n['id']: n.get('label', n['id']) for n in nodes_list}

# Load SHAP scores from B4
print("\nLoading B4 SHAP scores...")
shap_path = Path('phaseB/B4_multi_level_pruning/outputs/B4_shap_scores.pkl')
with open(shap_path, 'rb') as f:
    shap_data = pickle.load(f)

mechanism_shap = shap_data.get('mechanism_shap_scores', {})
print(f"  SHAP scores for {len(mechanism_shap)} mechanisms")

# Load B1 outcomes
print("\nLoading B1 outcomes...")
with open('phaseB/B1_outcome_discovery/outputs/B1_validated_outcomes.pkl', 'rb') as f:
    b1_data = pickle.load(f)

outcome_variables = set()
for outcome in b1_data.get('outcomes', []):
    outcome_variables.update(outcome.get('top_variables', []))
print(f"  Outcome variables: {len(outcome_variables)}")

# ============================================================================
# COMPUTE IMPORTANCE SCORES (Once for all configs)
# ============================================================================

print("\n" + "="*70)
print("COMPUTING IMPORTANCE SCORES")
print("="*70)

# Betweenness centrality
print("\nComputing betweenness centrality...")
betweenness = nx.betweenness_centrality(G, normalized=True)

# PageRank
print("Computing PageRank...")
pagerank = nx.pagerank(G, alpha=0.85)

# Degree centrality (normalized)
print("Computing degree centrality...")
max_degree = max(dict(G.degree()).values()) if G.number_of_nodes() > 0 else 1
degree_scores = {n: G.degree(n) / max_degree for n in G.nodes()}

# SHAP scores (extend to all nodes, default 0)
print("Processing SHAP scores...")
shap_scores = {}
for n in G.nodes():
    shap_scores[n] = mechanism_shap.get(n, 0.0)

# Normalize SHAP
max_shap = max(shap_scores.values()) if shap_scores and max(shap_scores.values()) > 0 else 1.0
shap_scores = {k: v / max_shap for k, v in shap_scores.items()}

# Composite score
print("Computing composite scores...")
composite_scores = {}
for n in G.nodes():
    layer = node_layers.get(n, 10)
    layer_weight = 1.0 / (1 + layer)  # Earlier layers weighted higher

    composite_scores[n] = (
        0.40 * shap_scores.get(n, 0.0) +
        0.25 * betweenness.get(n, 0.0) +
        0.15 * pagerank.get(n, 0.0) +
        0.10 * degree_scores.get(n, 0.0) +
        0.10 * layer_weight
    )

ALL_SCORES = {
    'composite': composite_scores,
    'shap': shap_scores,
    'betweenness': betweenness,
    'pagerank': pagerank,
    'degree': degree_scores
}

print("✓ All importance scores computed")

# Domain distribution in full graph
domain_dist = Counter(node_domains.values())
print("\nFull graph domain distribution:")
for domain, count in domain_dist.most_common():
    print(f"  {domain}: {count} ({100*count/len(nodes_list):.1f}%)")

# ============================================================================
# PRUNING FUNCTIONS
# ============================================================================

def get_layer_bands(layer_mode):
    """Get layer compression bands."""
    if layer_mode == 2:
        return [[i for i in range(11)], [i for i in range(11, 21)]]
    elif layer_mode == 3:
        return [[i for i in range(7)], [i for i in range(7, 14)], [i for i in range(14, 21)]]
    elif layer_mode == 5:
        return [[0], [1,2,3,4,5], [6,7,8,9,10,11,12,13,14], [15,16,17,18], [19,20]]
    else:  # 21 layers (full)
        return [[i] for i in range(21)]


def compress_layers(nodes, layer_mode):
    """Apply layer compression to nodes."""
    bands = get_layer_bands(layer_mode)

    for node in nodes:
        layer = node.get('causal_layer', 0)
        band_idx = -1
        for i, band in enumerate(bands):
            if layer in band:
                band_idx = i
                break
        node['display_layer'] = band_idx if band_idx >= 0 else 0
        node['band_size'] = len(bands[band_idx]) if band_idx >= 0 and band_idx < len(bands) else 1

    return nodes


def apply_governance_cap(nodes, cap_pct, scores):
    """Limit governance nodes to cap_pct of total."""
    if cap_pct is None:
        return nodes

    target_count = len(nodes)
    gov_nodes = [n for n in nodes if n['domain'] == 'Governance']
    non_gov_nodes = [n for n in nodes if n['domain'] != 'Governance']

    max_gov = int(target_count * cap_pct)

    if len(gov_nodes) <= max_gov:
        return nodes  # Already under cap

    # Sort governance nodes by score, keep top ones
    gov_nodes_sorted = sorted(gov_nodes, key=lambda n: scores.get(n['id'], 0), reverse=True)
    kept_gov = gov_nodes_sorted[:max_gov]

    # Need to add more non-gov nodes to reach target
    needed = target_count - len(kept_gov) - len(non_gov_nodes)

    result = kept_gov + non_gov_nodes
    return result[:target_count]


def balance_domains(all_nodes, target_count, scores):
    """Select nodes with equal representation across domains."""
    # Group by domain
    by_domain = defaultdict(list)
    for node in all_nodes:
        by_domain[node['domain']].append(node)

    # Sort each domain by score
    for domain in by_domain:
        by_domain[domain].sort(key=lambda n: scores.get(n['id'], 0), reverse=True)

    domains = list(by_domain.keys())
    per_domain = target_count // len(domains)
    remainder = target_count % len(domains)

    balanced = []
    for i, domain in enumerate(sorted(domains)):
        take = per_domain + (1 if i < remainder else 0)
        balanced.extend(by_domain[domain][:take])

    return balanced[:target_count]


def prune_graph(config):
    """Main pruning function for a configuration."""
    max_nodes = config['nodes']
    layer_mode = config['layers']
    method = config['method']
    balance = config['balance']
    gov_cap = config['gov_cap']

    # Get scores for this method
    scores = ALL_SCORES[method]

    # Create node list with all attributes
    node_list = []
    for n in nodes_list:
        node_list.append({
            'id': n['id'],
            'label': n.get('label', n['id']),
            'causal_layer': n.get('causal_layer', 0),
            'domain': n.get('domain', 'Unknown'),
            'score': scores.get(n['id'], 0.0),
            'is_outcome': n['id'] in outcome_variables,
            'in_degree': n.get('in_degree', 0),
            'out_degree': n.get('out_degree', 0),
        })

    # Sort by score
    node_list.sort(key=lambda n: n['score'], reverse=True)

    # Apply selection strategy
    if balance:
        selected_nodes = balance_domains(node_list, max_nodes, scores)
    else:
        # Top-N by score
        selected_nodes = node_list[:max_nodes]

        # Then apply governance cap if specified
        if gov_cap:
            selected_nodes = apply_governance_cap(selected_nodes, gov_cap, scores)

    # Apply layer compression
    selected_nodes = compress_layers(selected_nodes, layer_mode)

    # Filter edges to only those between selected nodes
    node_ids = set(n['id'] for n in selected_nodes)
    selected_edges = []
    for edge in edges_list:
        if edge['source'] in node_ids and edge['target'] in node_ids:
            selected_edges.append({
                'source': edge['source'],
                'target': edge['target'],
                'weight': edge.get('weight', 1.0),
                'lag': edge.get('lag', 0),
            })

    # Compute domain distribution
    domain_counts = Counter(n['domain'] for n in selected_nodes)
    total = len(selected_nodes)
    domain_pct = {d: round((count/total)*100, 1) for d, count in domain_counts.items()}

    return {
        'metadata': {
            'config': config,
            'node_count': len(selected_nodes),
            'edge_count': len(selected_edges),
            'domain_distribution': dict(domain_counts),
            'domain_percentages': domain_pct,
            'governance_pct': domain_pct.get('Governance', 0.0),
            'layer_bands': get_layer_bands(layer_mode),
        },
        'nodes': selected_nodes,
        'edges': selected_edges
    }


# ============================================================================
# GENERATE ALL GRAPHS
# ============================================================================

print("\n" + "="*70)
print(f"GENERATING {len(GRAPH_CONFIGS)} GRAPHS")
print("="*70)

summary_stats = []

for i, config in enumerate(tqdm(GRAPH_CONFIGS, desc="Generating graphs"), 1):
    # Generate graph
    graph_data = prune_graph(config)

    # Create filename
    filename = f"graph_{config['nodes']:04d}n_{config['layers']:02d}l_{config['method']}"
    if config['balance']:
        filename += "_balanced"
    if config['gov_cap']:
        filename += f"_govcap{int(config['gov_cap']*100)}"
    filename += ".json"

    # Save
    output_path = OUTPUT_DIR / filename
    with open(output_path, 'w') as f:
        json.dump(graph_data, f, indent=2)

    # Track stats
    summary_stats.append({
        'filename': filename,
        'nodes': graph_data['metadata']['node_count'],
        'edges': graph_data['metadata']['edge_count'],
        'governance_pct': graph_data['metadata']['governance_pct'],
        'config': config
    })

print(f"\n✅ Generated {len(GRAPH_CONFIGS)} graphs in {OUTPUT_DIR}")

# ============================================================================
# SUMMARY REPORT
# ============================================================================

print("\n" + "="*70)
print("GENERATION SUMMARY")
print("="*70)

# Group by governance percentage
gov_ranges = {
    '<30%': [],
    '30-40%': [],
    '40-50%': [],
    '50-60%': [],
    '>60%': []
}

for stat in summary_stats:
    gov_pct = stat['governance_pct']
    if gov_pct < 30:
        gov_ranges['<30%'].append(stat)
    elif gov_pct < 40:
        gov_ranges['30-40%'].append(stat)
    elif gov_pct < 50:
        gov_ranges['40-50%'].append(stat)
    elif gov_pct < 60:
        gov_ranges['50-60%'].append(stat)
    else:
        gov_ranges['>60%'].append(stat)

print("\nGovernance % Distribution Across Generated Graphs:")
for range_label, graphs in gov_ranges.items():
    print(f"  {range_label}: {len(graphs)} graphs")

print("\nSample graphs by governance %:")
for range_label, graphs in gov_ranges.items():
    if graphs:
        example = graphs[0]
        print(f"\n  {range_label} example: {example['filename']}")
        print(f"    Nodes: {example['nodes']}, Edges: {example['edges']}")
        print(f"    Governance: {example['governance_pct']:.1f}%")

# Export summary
summary_path = OUTPUT_DIR / 'SUMMARY.json'
with open(summary_path, 'w') as f:
    json.dump(summary_stats, f, indent=2)

print(f"\n✅ Summary exported to: {summary_path}")

# Create markdown summary
md_summary = """# Pre-Computed Graph Permutations Summary

Generated: {date}
Total graphs: {total}

## Governance % Distribution

| Range | Count | Examples |
|-------|-------|----------|
""".format(date="December 3, 2025", total=len(GRAPH_CONFIGS))

for range_label, graphs in gov_ranges.items():
    examples = ", ".join([g['filename'][:30] for g in graphs[:2]]) if graphs else "None"
    md_summary += f"| {range_label} | {len(graphs)} | {examples}... |\n"

md_summary += """
## Key Files to Examine

### For Governance Assessment:
- `graph_0100n_05l_composite.json` - Baseline 100 nodes
- `graph_0100n_05l_composite_balanced.json` - Domain balanced
- `graph_0100n_05l_composite_govcap30.json` - Gov capped at 30%
- `graph_0290n_05l_composite.json` - B4 scale, uncapped

### For Method Comparison:
- `graph_0100n_05l_shap.json` - SHAP-only ranking
- `graph_0100n_05l_betweenness.json` - Betweenness centrality
- `graph_0100n_05l_pagerank.json` - PageRank

## Decision Matrix

| Observation | Recommended Action |
|-------------|-------------------|
| Governance >60% in most graphs | Re-run pipeline with stratified sampling |
| Governance 50-60%, visually acceptable | Post-prune to 50% cap for dashboard |
| Governance 40-50%, balanced methods work | Use domain-balanced graphs for public dashboard |
| Governance <40% | Current pipeline is fine |
"""

md_path = OUTPUT_DIR / 'README.md'
with open(md_path, 'w') as f:
    f.write(md_summary)

print(f"✅ README exported to: {md_path}")

print("\n" + "="*70)
print("COMPLETE")
print("="*70)
print(f"""
Generated {len(GRAPH_CONFIGS)} graph permutations in:
  {OUTPUT_DIR}/

Key outputs:
  - 54 JSON graph files
  - SUMMARY.json (machine-readable stats)
  - README.md (human-readable summary)

Next steps:
  1. Review governance % across configurations
  2. Compare balanced vs capped vs uncapped
  3. Decide on final pruning strategy
""")
