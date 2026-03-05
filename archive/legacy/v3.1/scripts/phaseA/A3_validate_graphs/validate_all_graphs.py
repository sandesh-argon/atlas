"""
A3: Comprehensive validation of all country graphs.

Checks:
1. DAG validation (no cycles)
2. Data quality assessment
3. Beta distribution analysis
4. Graph similarity computation
5. Country clustering

Output:
- outputs/validation/PHASE_A_VALIDATION_REPORT.md
- outputs/validation/country_graph_validation.csv
- outputs/validation/country_clusters.csv
- outputs/figures/beta_distribution.png
- outputs/figures/country_similarity_heatmap.png
"""

import json
import pandas as pd
import numpy as np
from pathlib import Path
from collections import defaultdict, deque
from sklearn.cluster import KMeans
import matplotlib.pyplot as plt
import seaborn as sns


def load_all_graphs(graphs_dir: str = 'data/country_graphs') -> dict:
    """Load all country graphs (excluding progress.json and other non-graph files)."""
    graph_dir = Path(graphs_dir)
    graph_files = list(graph_dir.glob('*.json'))

    graphs = {}
    for graph_file in graph_files:
        # Skip non-graph files
        if graph_file.stem in ['progress', 'estimation_progress']:
            continue

        with open(graph_file) as f:
            data = json.load(f)
            # Verify it's a valid graph file
            if 'edges' in data:
                graphs[graph_file.stem] = data

    print(f"Loaded {len(graphs)} country graphs")
    return graphs


def check_dag(edges: list) -> bool:
    """Check if graph is acyclic (DAG) using Kahn's algorithm."""
    adj = defaultdict(list)
    in_degree = defaultdict(int)
    nodes = set()

    for edge in edges:
        source, target = edge['source'], edge['target']
        adj[source].append(target)
        in_degree[target] += 1
        nodes.add(source)
        nodes.add(target)

    # Initialize in_degree for nodes with no incoming edges
    for node in nodes:
        if node not in in_degree:
            in_degree[node] = 0

    # Kahn's algorithm
    queue = deque([n for n in nodes if in_degree[n] == 0])
    sorted_count = 0

    while queue:
        node = queue.popleft()
        sorted_count += 1

        for neighbor in adj[node]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    return sorted_count == len(nodes)


def validate_dags(graphs: dict) -> pd.DataFrame:
    """Check all graphs for cycles."""
    print("\n1. Checking DAG property (no cycles)...")

    results = []
    for country, graph in graphs.items():
        is_dag = check_dag(graph['edges'])
        n_nodes = len(set(
            [e['source'] for e in graph['edges']] +
            [e['target'] for e in graph['edges']]
        ))

        results.append({
            'country': country,
            'is_dag': is_dag,
            'n_nodes': n_nodes,
            'n_edges': graph['n_edges']
        })

    df = pd.DataFrame(results)
    n_dags = df['is_dag'].sum()
    cycles_found = df[~df['is_dag']]['country'].tolist()

    print(f"  DAGs: {n_dags} / {len(df)}")
    if cycles_found:
        print(f"  ⚠️  Cycles detected in: {cycles_found[:5]}")

    return df


def analyze_data_quality(graphs: dict) -> pd.DataFrame:
    """Analyze data availability per country."""
    print("\n2. Analyzing data quality...")

    results = []
    for country, graph in graphs.items():
        n_edges = graph['n_edges']
        n_with_data = graph['n_edges_with_data']
        coverage = n_with_data / n_edges if n_edges > 0 else 0

        results.append({
            'country': country,
            'n_edges': n_edges,
            'n_with_data': n_with_data,
            'coverage': coverage
        })

    df = pd.DataFrame(results).sort_values('coverage', ascending=False)

    print(f"  Mean coverage: {df['coverage'].mean():.1%}")
    print(f"  Countries >80% coverage: {(df['coverage'] > 0.8).sum()}")
    print(f"  Countries <50% coverage: {(df['coverage'] < 0.5).sum()}")

    return df


def analyze_betas(graphs: dict) -> dict:
    """Analyze beta coefficient distributions."""
    print("\n3. Analyzing beta distributions...")

    all_betas = []
    country_betas = {}

    for country, graph in graphs.items():
        betas = [e['beta'] for e in graph['edges'] if e.get('data_available', True)]
        all_betas.extend(betas)
        country_betas[country] = betas

    all_betas = np.array(all_betas)
    all_betas = all_betas[~np.isnan(all_betas) & ~np.isinf(all_betas)]

    print(f"  Total betas: {len(all_betas):,}")
    print(f"  Mean: {np.mean(all_betas):.4f}")
    print(f"  Median: {np.median(all_betas):.4f}")
    print(f"  Std: {np.std(all_betas):.4f}")
    print(f"  Range: [{np.min(all_betas):.4f}, {np.max(all_betas):.4f}]")

    # Plot distribution
    output_dir = Path('outputs/figures')
    output_dir.mkdir(parents=True, exist_ok=True)

    plt.figure(figsize=(10, 6))
    plt.hist(all_betas, bins=100, edgecolor='black', alpha=0.7)
    plt.xlabel('Beta Coefficient')
    plt.ylabel('Frequency')
    plt.title('Distribution of Beta Coefficients (All Countries)')
    plt.axvline(0, color='red', linestyle='--', label='Zero')
    plt.axvline(np.mean(all_betas), color='green', linestyle='-', label=f'Mean: {np.mean(all_betas):.3f}')
    plt.legend()
    plt.tight_layout()
    plt.savefig(output_dir / 'beta_distribution.png', dpi=150)
    plt.close()

    return {
        'mean': float(np.mean(all_betas)),
        'median': float(np.median(all_betas)),
        'std': float(np.std(all_betas)),
        'min': float(np.min(all_betas)),
        'max': float(np.max(all_betas))
    }


def compute_similarity(graphs: dict, sample_size: int = 30) -> np.ndarray:
    """Compute pairwise Jaccard similarity between country graphs."""
    print("\n4. Computing graph similarity...")

    countries = sorted(list(graphs.keys()))[:sample_size]
    n = len(countries)

    # Convert to significant edge sets (|beta| > threshold)
    def get_significant_edges(graph, threshold=0.05):
        edges = set()
        for e in graph['edges']:
            if abs(e['beta']) > threshold:
                edges.add((e['source'], e['target']))
        return edges

    edge_sets = {c: get_significant_edges(graphs[c]) for c in countries}

    # Compute Jaccard similarity matrix
    similarity = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            if i == j:
                similarity[i, j] = 1.0
            else:
                set_i = edge_sets[countries[i]]
                set_j = edge_sets[countries[j]]
                intersection = len(set_i & set_j)
                union = len(set_i | set_j)
                similarity[i, j] = intersection / union if union > 0 else 0

    # Plot heatmap
    output_dir = Path('outputs/figures')
    output_dir.mkdir(parents=True, exist_ok=True)

    plt.figure(figsize=(14, 12))
    sns.heatmap(
        similarity,
        xticklabels=countries,
        yticklabels=countries,
        cmap='viridis',
        vmin=0, vmax=1,
        square=True,
        cbar_kws={'label': 'Jaccard Similarity'}
    )
    plt.title(f'Country Graph Similarity (Sample of {n})')
    plt.tight_layout()
    plt.savefig(output_dir / 'country_similarity_heatmap.png', dpi=150)
    plt.close()

    mean_sim = similarity[np.triu_indices(n, k=1)].mean()
    print(f"  Mean pairwise similarity: {mean_sim:.3f}")

    return similarity


def cluster_countries(graphs: dict, n_clusters: int = 5) -> pd.DataFrame:
    """Cluster countries by causal structure similarity."""
    print("\n5. Clustering countries...")

    # Build feature matrix (edge presence/strength)
    all_edge_keys = set()
    for graph in graphs.values():
        for e in graph['edges']:
            all_edge_keys.add((e['source'], e['target']))

    all_edge_keys = sorted(list(all_edge_keys))
    edge_to_idx = {e: i for i, e in enumerate(all_edge_keys)}

    countries = sorted(list(graphs.keys()))
    feature_matrix = np.zeros((len(countries), len(all_edge_keys)))

    for i, country in enumerate(countries):
        for e in graphs[country]['edges']:
            key = (e['source'], e['target'])
            if key in edge_to_idx and abs(e['beta']) > 0.05:
                feature_matrix[i, edge_to_idx[key]] = 1

    # K-means clustering
    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    clusters = kmeans.fit_predict(feature_matrix)

    cluster_df = pd.DataFrame({
        'country': countries,
        'cluster': clusters
    })

    print(f"\n  Clusters (k={n_clusters}):")
    for i in range(n_clusters):
        cluster_countries = cluster_df[cluster_df['cluster'] == i]['country'].tolist()
        print(f"    Cluster {i}: {len(cluster_countries)} countries")
        print(f"      Examples: {', '.join(cluster_countries[:5])}")

    return cluster_df


def generate_report(
    dag_df: pd.DataFrame,
    quality_df: pd.DataFrame,
    beta_stats: dict,
    cluster_df: pd.DataFrame
):
    """Generate markdown validation report."""
    output_dir = Path('outputs/validation')
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save CSVs
    dag_df.to_csv(output_dir / 'country_graph_validation.csv', index=False)
    quality_df.to_csv(output_dir / 'country_data_quality.csv', index=False)
    cluster_df.to_csv(output_dir / 'country_clusters.csv', index=False)

    # Generate markdown report
    report = []
    report.append("# Phase A Validation Report\n")
    report.append(f"Generated for {len(dag_df)} country graphs\n")

    report.append("\n## 1. DAG Validation\n")
    n_dags = dag_df['is_dag'].sum()
    report.append(f"- Total graphs: {len(dag_df)}\n")
    report.append(f"- Valid DAGs: {n_dags}\n")
    report.append(f"- Graphs with cycles: {len(dag_df) - n_dags}\n")

    if not dag_df['is_dag'].all():
        cycles = dag_df[~dag_df['is_dag']]['country'].tolist()
        report.append(f"- Countries with cycles: {', '.join(cycles)}\n")

    report.append("\n## 2. Data Quality\n")
    report.append(f"- Mean coverage: {quality_df['coverage'].mean():.1%}\n")
    report.append(f"- Countries >80% coverage: {(quality_df['coverage'] > 0.8).sum()}\n")
    report.append(f"- Countries <50% coverage: {(quality_df['coverage'] < 0.5).sum()}\n")

    report.append("\n## 3. Beta Distribution\n")
    report.append(f"- Mean beta: {beta_stats['mean']:.4f}\n")
    report.append(f"- Median beta: {beta_stats['median']:.4f}\n")
    report.append(f"- Std: {beta_stats['std']:.4f}\n")
    report.append(f"- Range: [{beta_stats['min']:.4f}, {beta_stats['max']:.4f}]\n")

    report.append("\n## 4. Country Clusters\n")
    for i in range(cluster_df['cluster'].max() + 1):
        cluster_countries = cluster_df[cluster_df['cluster'] == i]['country'].tolist()
        report.append(f"- Cluster {i}: {len(cluster_countries)} countries\n")

    report.append("\n## Files Generated\n")
    report.append("- `outputs/validation/country_graph_validation.csv`\n")
    report.append("- `outputs/validation/country_data_quality.csv`\n")
    report.append("- `outputs/validation/country_clusters.csv`\n")
    report.append("- `outputs/figures/beta_distribution.png`\n")
    report.append("- `outputs/figures/country_similarity_heatmap.png`\n")

    with open(output_dir / 'PHASE_A_VALIDATION_REPORT.md', 'w') as f:
        f.write(''.join(report))

    print(f"\n📄 Report saved to {output_dir / 'PHASE_A_VALIDATION_REPORT.md'}")


def validate_all():
    """Run complete Phase A validation."""
    print("=" * 50)
    print("PHASE A VALIDATION")
    print("=" * 50)

    graphs = load_all_graphs()

    dag_df = validate_dags(graphs)
    quality_df = analyze_data_quality(graphs)
    beta_stats = analyze_betas(graphs)
    similarity = compute_similarity(graphs)
    cluster_df = cluster_countries(graphs)

    generate_report(dag_df, quality_df, beta_stats, cluster_df)

    # Final summary
    print("\n" + "=" * 50)
    print("VALIDATION SUMMARY")
    print("=" * 50)

    all_dags = dag_df['is_dag'].all()
    good_coverage = quality_df['coverage'].mean() > 0.5
    reasonable_betas = abs(beta_stats['max']) < 100 and abs(beta_stats['min']) < 100

    print(f"✓ All graphs are DAGs: {'✅' if all_dags else '❌'}")
    print(f"✓ Mean coverage >50%: {'✅' if good_coverage else '❌'}")
    print(f"✓ Betas in reasonable range: {'✅' if reasonable_betas else '❌'}")

    if all_dags and good_coverage and reasonable_betas:
        print("\n✅ Phase A validation PASSED - ready for Phase B")
        return True
    else:
        print("\n❌ Phase A validation FAILED - review issues before Phase B")
        return False


if __name__ == "__main__":
    success = validate_all()
    exit(0 if success else 1)
