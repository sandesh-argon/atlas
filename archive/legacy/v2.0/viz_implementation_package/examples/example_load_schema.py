#!/usr/bin/env python3
"""
Python Example: Loading and Using the Causal Graph Schema

This example demonstrates how to load and work with the causal graph schema
using Python for data analysis and visualization.

Author: V2.0 Global Causal Discovery Team
Date: November 21, 2025
"""

import json
import pandas as pd
import networkx as nx
from pathlib import Path
from typing import List, Dict, Tuple


# ============================================================================
# Example 1: Loading the Schema
# ============================================================================

def load_schema(schema_path: str = '../data/causal_graph_v2_final.json') -> Dict:
    """Load the causal graph schema from JSON."""
    with open(schema_path) as f:
        schema = json.load(f)

    print('✅ Schema loaded successfully')
    print(f'   Mechanisms: {len(schema["mechanisms"])}')
    print(f'   Outcomes: {len(schema["outcomes"])}')
    print(f'   Graph levels: {", ".join(schema["graphs"].keys())}')

    return schema


# ============================================================================
# Example 2: Converting to Pandas DataFrames
# ============================================================================

def convert_to_dataframes(schema: Dict) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Convert schema to pandas DataFrames."""
    # Mechanisms DataFrame
    mechanisms_df = pd.DataFrame(schema['mechanisms'])
    print(f'\n📊 Mechanisms DataFrame: {mechanisms_df.shape}')
    print(mechanisms_df.head())

    # Outcomes DataFrame
    outcomes_df = pd.DataFrame(schema['outcomes'])
    print(f'\n📊 Outcomes DataFrame: {outcomes_df.shape}')
    print(outcomes_df.head())

    # Edges DataFrame (full graph)
    edges_df = pd.DataFrame(schema['graphs']['full']['edges'])
    print(f'\n📊 Edges DataFrame: {edges_df.shape}')
    print(edges_df.head())

    return mechanisms_df, outcomes_df, edges_df


# ============================================================================
# Example 3: Filtering and Analysis
# ============================================================================

def filter_by_domain(mechanisms_df: pd.DataFrame, domain: str) -> pd.DataFrame:
    """Filter mechanisms by domain."""
    filtered = mechanisms_df[mechanisms_df['domain'] == domain]

    print(f'\n🔍 {domain} mechanisms: {len(filtered)}')

    # Top 5 by SHAP score
    shap_available = filtered[filtered['shap_available'] == True]
    top_by_shap = shap_available.nlargest(5, 'shap_score')

    print(f'\nTop 5 {domain} mechanisms by SHAP:')
    for i, (idx, row) in enumerate(top_by_shap.iterrows(), 1):
        print(f'  {i}. {row["label"]} (SHAP: {row["shap_score"]:.4f})')

    return filtered


def analyze_by_cluster(mechanisms_df: pd.DataFrame) -> pd.DataFrame:
    """Analyze mechanisms by cluster."""
    cluster_summary = mechanisms_df.groupby('cluster_name').agg({
        'id': 'count',
        'shap_score': ['mean', 'std'],
        'centrality': ['mean', 'max']
    }).round(4)

    cluster_summary.columns = ['count', 'shap_mean', 'shap_std', 'centrality_mean', 'centrality_max']
    cluster_summary = cluster_summary.sort_values('shap_mean', ascending=False)

    print('\n📈 Cluster Analysis:')
    print(cluster_summary)

    return cluster_summary


# ============================================================================
# Example 4: NetworkX Integration
# ============================================================================

def build_networkx_graph(schema: Dict, graph_level: str = 'full') -> nx.DiGraph:
    """Build NetworkX directed graph from schema."""
    G = nx.DiGraph()

    # Add nodes with attributes
    for node in schema['graphs'][graph_level]['nodes']:
        G.add_node(node['id'], **node)

    # Add edges with attributes
    for edge in schema['graphs'][graph_level]['edges']:
        G.add_edge(edge['source'], edge['target'],
                   effect=edge['effect'], lag=edge['lag'])

    print(f'\n🕸️  NetworkX Graph ({graph_level}):')
    print(f'   Nodes: {G.number_of_nodes()}')
    print(f'   Edges: {G.number_of_edges()}')
    print(f'   Is DAG: {nx.is_directed_acyclic_graph(G)}')

    return G


def compute_network_metrics(G: nx.DiGraph) -> pd.DataFrame:
    """Compute network centrality metrics."""
    metrics = pd.DataFrame({
        'degree_centrality': nx.degree_centrality(G),
        'in_degree_centrality': nx.in_degree_centrality(G),
        'out_degree_centrality': nx.out_degree_centrality(G),
        'betweenness_centrality': nx.betweenness_centrality(G),
        'pagerank': nx.pagerank(G)
    })

    # Sort by PageRank
    metrics = metrics.sort_values('pagerank', ascending=False)

    print('\n📊 Top 10 Nodes by PageRank:')
    print(metrics.head(10))

    return metrics


# ============================================================================
# Example 5: Finding Causal Paths
# ============================================================================

def find_all_paths(G: nx.DiGraph, source: str, target: str, cutoff: int = 5) -> List[List[str]]:
    """Find all simple paths from source to target."""
    try:
        paths = list(nx.all_simple_paths(G, source, target, cutoff=cutoff))
        print(f'\n🔗 Found {len(paths)} paths from {source} to {target}:')

        for i, path in enumerate(paths[:5], 1):  # Show first 5
            path_str = ' → '.join(path)
            print(f'   {i}. {path_str}')

        if len(paths) > 5:
            print(f'   ... and {len(paths) - 5} more')

        return paths
    except nx.NetworkXNoPath:
        print(f'\n🔗 No path found from {source} to {target}')
        return []


# ============================================================================
# Example 6: SHAP Analysis
# ============================================================================

def analyze_shap_distribution(mechanisms_df: pd.DataFrame):
    """Analyze SHAP score distribution."""
    shap_available = mechanisms_df[mechanisms_df['shap_available'] == True]

    baseline = 1 / len(mechanisms_df)
    above_baseline = shap_available[shap_available['shap_score'] > baseline]
    below_baseline = shap_available[shap_available['shap_score'] < baseline]

    print(f'\n📊 SHAP Score Distribution:')
    print(f'   Total mechanisms: {len(mechanisms_df)}')
    print(f'   SHAP available: {len(shap_available)} ({len(shap_available)/len(mechanisms_df)*100:.1f}%)')
    print(f'   Baseline: {baseline:.6f}')
    print(f'   Above baseline: {len(above_baseline)} ({len(above_baseline)/len(shap_available)*100:.1f}%)')
    print(f'   Below baseline: {len(below_baseline)} ({len(below_baseline)/len(shap_available)*100:.1f}%)')
    print(f'   Mean SHAP: {shap_available["shap_score"].mean():.6f}')
    print(f'   Std SHAP: {shap_available["shap_score"].std():.6f}')
    print(f'   Max SHAP: {shap_available["shap_score"].max():.6f}')


# ============================================================================
# Example 7: Export to CSV
# ============================================================================

def export_filtered_data(mechanisms_df: pd.DataFrame, domain: str, output_path: str):
    """Export filtered data to CSV."""
    filtered = mechanisms_df[mechanisms_df['domain'] == domain]
    filtered.to_csv(output_path, index=False)
    print(f'\n💾 Exported {len(filtered)} {domain} mechanisms to {output_path}')


# ============================================================================
# Example 8: Visualization with matplotlib (pseudocode)
# ============================================================================

"""
# Requires: pip install matplotlib networkx

import matplotlib.pyplot as plt

def visualize_graph(G: nx.DiGraph, layout='spring'):
    '''Visualize graph with matplotlib.'''
    plt.figure(figsize=(12, 8))

    # Compute layout
    if layout == 'spring':
        pos = nx.spring_layout(G, k=0.5, iterations=50)
    elif layout == 'kamada_kawai':
        pos = nx.kamada_kawai_layout(G)
    else:
        pos = nx.circular_layout(G)

    # Draw nodes
    nx.draw_networkx_nodes(G, pos, node_size=300, node_color='lightblue', alpha=0.9)

    # Draw edges
    nx.draw_networkx_edges(G, pos, edge_color='gray', alpha=0.5, arrows=True,
                          arrowsize=10, width=0.5)

    # Draw labels
    nx.draw_networkx_labels(G, pos, font_size=8, font_family='sans-serif')

    plt.title('Causal Graph Visualization')
    plt.axis('off')
    plt.tight_layout()
    plt.savefig('causal_graph.png', dpi=300, bbox_inches='tight')
    plt.show()
"""


# ============================================================================
# Main Usage Example
# ============================================================================

def main():
    print('=' * 80)
    print('CAUSAL GRAPH SCHEMA - PYTHON EXAMPLE')
    print('=' * 80)

    # Load schema
    schema = load_schema()

    # Convert to DataFrames
    mechanisms_df, outcomes_df, edges_df = convert_to_dataframes(schema)

    # Filter by domain
    education_df = filter_by_domain(mechanisms_df, 'Education')

    # Cluster analysis
    cluster_summary = analyze_by_cluster(mechanisms_df)

    # Build NetworkX graph
    G = build_networkx_graph(schema, graph_level='full')

    # Compute network metrics
    metrics = compute_network_metrics(G)

    # Find causal paths (example)
    # paths = find_all_paths(G, 'SE.PRM.ENRR', 'Factor_2')

    # SHAP analysis
    analyze_shap_distribution(mechanisms_df)

    # Export example
    # export_filtered_data(mechanisms_df, 'Governance', 'governance_mechanisms.csv')

    print('\n' + '=' * 80)
    print('✅ Example complete!')
    print('=' * 80)


if __name__ == '__main__':
    main()
