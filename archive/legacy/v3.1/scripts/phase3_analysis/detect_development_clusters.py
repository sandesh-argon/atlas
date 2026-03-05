#!/usr/bin/env python3
"""
Phase 3B: Development Cluster Detection

Identifies groups of indicators connected through causal pathways using
community detection (Louvain algorithm). The causal graph is a DAG, so
traditional feedback loops don't exist - instead we find "indicator ecosystems"
that are tightly connected through causal relationships.

Why this matters:
- Shows which indicators tend to move together
- Identifies domain interactions (e.g., Education-Economic clusters)
- Helps users understand the causal structure

Input: Phase 2B temporal graphs (4,663 files)
Output: 178 country cluster files + 35 unified year files
"""

import json
import sys
import time
import argparse
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Dict, List, Optional
import pandas as pd

try:
    import networkx as nx
    from networkx.algorithms import community
    HAS_NETWORKX = True
except ImportError:
    HAS_NETWORKX = False
    print("WARNING: networkx not installed. Install with: pip install networkx")

# Configuration
BASE_DIR = Path("<repo-root>/v3.1")
GRAPHS_DIR = BASE_DIR / "data" / "v3_1_temporal_graphs"
OUTPUT_DIR = BASE_DIR / "data" / "v3_1_development_clusters"
NODES_FILE = BASE_DIR / "data" / "raw" / "v21_nodes.csv"

# Parameters
P_VALUE_THRESHOLD = 0.05
MIN_CLUSTER_SIZE = 5

# Global node metadata (loaded once)
NODE_DOMAINS = {}
NODE_LABELS = {}


class NumpyEncoder(json.JSONEncoder):
    """Handle numpy types in JSON serialization."""
    def default(self, obj):
        try:
            import numpy as np
            if isinstance(obj, (np.integer, np.int64, np.int32)):
                return int(obj)
            if isinstance(obj, (np.floating, np.float64, np.float32)):
                return float(obj)
            if isinstance(obj, np.ndarray):
                return obj.tolist()
        except ImportError:
            pass
        return super().default(obj)


def load_node_metadata():
    """Load node domains and labels from v21_nodes.csv."""
    global NODE_DOMAINS, NODE_LABELS

    if NODES_FILE.exists():
        df = pd.read_csv(NODES_FILE)
        NODE_DOMAINS = dict(zip(df['id'], df['domain'].fillna('other')))
        NODE_LABELS = dict(zip(df['id'], df['label'].fillna('')))
        print(f"Loaded metadata for {len(NODE_DOMAINS)} nodes")
    else:
        print(f"WARNING: Node metadata file not found: {NODES_FILE}")


def get_domain(node_id: str) -> str:
    """Get domain for a node."""
    domain = NODE_DOMAINS.get(node_id, 'other')
    if pd.isna(domain) or domain == '':
        return 'other'
    return domain


def get_label(node_id: str) -> str:
    """Get human-readable label for a node."""
    label = NODE_LABELS.get(node_id, '')
    if pd.isna(label) or label == '':
        return node_id
    return label


def load_graph(graph_path: Path) -> Optional[dict]:
    """Load a single graph file."""
    try:
        with open(graph_path) as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return None


def detect_communities(graph: dict) -> List[dict]:
    """
    Detect communities using Louvain algorithm.
    Returns list of cluster dicts with metadata.
    """
    if not HAS_NETWORKX:
        return []

    # Build undirected graph with edge weights
    G = nx.Graph()
    for e in graph.get('edges', []):
        if e.get('p_value', 1.0) >= P_VALUE_THRESHOLD:
            continue
        G.add_edge(e['source'], e['target'], weight=abs(e.get('beta', 0.1)))

    if G.number_of_nodes() < MIN_CLUSTER_SIZE:
        return []

    # Run Louvain community detection
    try:
        communities_list = community.louvain_communities(G, weight='weight', seed=42)
    except Exception as e:
        print(f"Community detection failed: {e}")
        return []

    # Sort by size
    communities_list = sorted(communities_list, key=len, reverse=True)

    # Analyze each community
    results = []
    for i, comm in enumerate(communities_list):
        if len(comm) < MIN_CLUSTER_SIZE:
            continue

        # Count domains
        domain_counts = defaultdict(int)
        for node in comm:
            domain_counts[get_domain(node)] += 1

        # Get sample labels
        sample_labels = []
        for node in list(comm)[:10]:
            label = get_label(node)
            if label and len(label) > 3:
                sample_labels.append(label[:60])

        top_domains = sorted(domain_counts.items(), key=lambda x: x[1], reverse=True)

        # Name the cluster based on dominant domain
        primary = top_domains[0] if top_domains else ('other', 0)
        secondary = top_domains[1] if len(top_domains) > 1 else ('', 0)

        if primary[0] != 'other' and primary[1] > len(comm) * 0.25:
            if secondary[0] and secondary[0] != 'other' and secondary[1] > len(comm) * 0.15:
                name = f"{primary[0].title()}-{secondary[0].title()} Cluster"
            else:
                name = f"{primary[0].title()} Cluster"
        else:
            name = f"Mixed Cluster {i+1}"

        # Compute cluster density (internal edge ratio)
        subgraph = G.subgraph(comm)
        n_internal = subgraph.number_of_edges()
        max_edges = len(comm) * (len(comm) - 1) / 2
        density = n_internal / max_edges if max_edges > 0 else 0

        # Get mean edge weight
        weights = [d['weight'] for _, _, d in subgraph.edges(data=True)]
        mean_weight = sum(weights) / len(weights) if weights else 0

        results.append({
            'cluster_id': i,
            'name': name,
            'size': len(comm),
            'domain_composition': dict(top_domains),
            'primary_domain': primary[0],
            'secondary_domain': secondary[0] if secondary[1] > 0 else None,
            'density': round(density, 4),
            'mean_edge_strength': round(mean_weight, 4),
            'n_internal_edges': n_internal,
            'sample_indicators': sample_labels[:5],
            'nodes': sorted(comm)
        })

    return results


def process_country(country_name: str) -> dict:
    """Process all years for a country and return cluster analysis."""
    start_time = time.time()

    country_dir = GRAPHS_DIR / "countries" / country_name
    if not country_dir.exists():
        return {'country': country_name, 'error': 'Directory not found'}

    # Find all graph files
    graph_files = sorted(country_dir.glob("*_graph.json"))
    if not graph_files:
        return {'country': country_name, 'error': 'No graph files found'}

    # Process most recent year (most complete data)
    latest_graph_path = graph_files[-1]
    year = int(latest_graph_path.stem.split('_')[0])

    graph = load_graph(latest_graph_path)
    if not graph:
        return {'country': country_name, 'error': 'Failed to load graph'}

    clusters = detect_communities(graph)

    elapsed = time.time() - start_time

    # Summary stats
    total_nodes = sum(c['size'] for c in clusters)
    domain_summary = defaultdict(int)
    for c in clusters:
        domain_summary[c['primary_domain']] += 1

    return {
        'country': country_name,
        'year_analyzed': year,
        'n_years_available': len(graph_files),
        'clusters': clusters,
        'summary': {
            'n_clusters': len(clusters),
            'total_nodes_in_clusters': total_nodes,
            'largest_cluster': max((c['size'] for c in clusters), default=0),
            'mean_cluster_size': round(total_nodes / len(clusters), 1) if clusters else 0,
            'clusters_by_domain': dict(domain_summary)
        },
        'metadata': {
            'computation_time_sec': round(elapsed, 2),
            'graph_file': str(latest_graph_path.name),
            'n_edges_in_graph': len(graph.get('edges', []))
        },
        'provenance': {
            'computation_date': datetime.now().isoformat(),
            'code_version': 'v3.1.0',
            'algorithm': 'louvain',
            'p_value_threshold': P_VALUE_THRESHOLD,
            'min_cluster_size': MIN_CLUSTER_SIZE
        }
    }


def process_unified_year(year: int) -> dict:
    """Process a unified (global) graph for one year."""
    start_time = time.time()

    graph_path = GRAPHS_DIR / "unified" / f"{year}_graph.json"
    if not graph_path.exists():
        return {'year': year, 'error': 'Graph file not found'}

    graph = load_graph(graph_path)
    if not graph:
        return {'year': year, 'error': 'Failed to load graph'}

    clusters = detect_communities(graph)

    elapsed = time.time() - start_time

    total_nodes = sum(c['size'] for c in clusters)
    domain_summary = defaultdict(int)
    for c in clusters:
        domain_summary[c['primary_domain']] += 1

    return {
        'source': 'unified',
        'year': year,
        'clusters': clusters,
        'summary': {
            'n_clusters': len(clusters),
            'total_nodes_in_clusters': total_nodes,
            'largest_cluster': max((c['size'] for c in clusters), default=0),
            'mean_cluster_size': round(total_nodes / len(clusters), 1) if clusters else 0,
            'clusters_by_domain': dict(domain_summary)
        },
        'metadata': {
            'computation_time_sec': round(elapsed, 2),
            'n_edges_in_graph': len(graph.get('edges', []))
        },
        'provenance': {
            'computation_date': datetime.now().isoformat(),
            'code_version': 'v3.1.0',
            'algorithm': 'louvain',
            'p_value_threshold': P_VALUE_THRESHOLD,
            'min_cluster_size': MIN_CLUSTER_SIZE
        }
    }


def save_result(result: dict, output_path: Path):
    """Save result to JSON file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Remove 'nodes' list to save space (can be reconstructed)
    result_slim = result.copy()
    if 'clusters' in result_slim:
        for c in result_slim['clusters']:
            if 'nodes' in c:
                del c['nodes']  # Remove full node list, keep sample_indicators

    with open(output_path, 'w') as f:
        json.dump(result_slim, f, indent=2, cls=NumpyEncoder)


def run_test(n_countries: int = 5):
    """Run test on a few countries."""
    print("=" * 60)
    print("PHASE 3B TEST: Development Cluster Detection")
    print("=" * 60)

    if not HAS_NETWORKX:
        print("ERROR: networkx required. Install with: pip install networkx")
        return 0, 0

    load_node_metadata()
    print()

    countries_dir = GRAPHS_DIR / "countries"
    countries = sorted([d.name for d in countries_dir.iterdir() if d.is_dir()])[:n_countries]

    total_time = 0
    results = []

    for country in countries:
        print(f"Processing {country}...", end=" ", flush=True)
        result = process_country(country)
        elapsed = result.get('metadata', {}).get('computation_time_sec', 0)
        total_time += elapsed

        if 'error' in result:
            print(f"ERROR: {result['error']}")
        else:
            n_clusters = result['summary']['n_clusters']
            largest = result['summary']['largest_cluster']
            print(f"{n_clusters} clusters (largest: {largest} nodes) [{elapsed:.2f}s]")
            results.append(result)

            out_path = OUTPUT_DIR / "countries" / f"{country}_clusters.json"
            save_result(result, out_path)

    # Summary
    print()
    print("-" * 60)
    print("TEST SUMMARY")
    print("-" * 60)

    avg_time = total_time / len(countries) if countries else 0
    total_countries = len([d for d in (GRAPHS_DIR / "countries").iterdir() if d.is_dir()])

    print(f"Countries tested: {len(countries)}")
    print(f"Average time per country: {avg_time:.2f}s")
    print(f"Total countries available: {total_countries}")

    eta_seconds = avg_time * total_countries / 8
    eta_minutes = eta_seconds / 60

    print()
    print(f"ESTIMATED RUNTIME (8 cores): {eta_minutes:.1f} minutes")

    if results:
        print()
        print("-" * 60)
        print("SAMPLE OUTPUT")
        print("-" * 60)
        sample = results[0]
        print(f"Country: {sample['country']}")
        print(f"Clusters: {sample['summary']['n_clusters']}")
        print(f"Nodes in clusters: {sample['summary']['total_nodes_in_clusters']}")

        if sample['clusters']:
            print("\nTop clusters:")
            for c in sample['clusters'][:3]:
                print(f"  {c['name']} ({c['size']} nodes, density={c['density']:.3f})")
                if c['sample_indicators']:
                    print(f"    e.g.: {c['sample_indicators'][0][:50]}")

    return avg_time, total_countries


def run_production(n_jobs: int = 8, resume: bool = False):
    """Run full production."""
    print("=" * 60)
    print("PHASE 3B PRODUCTION: Development Cluster Detection")
    print("=" * 60)

    if not HAS_NETWORKX:
        print("ERROR: networkx required")
        return

    load_node_metadata()

    print(f"Workers: {n_jobs}")
    print(f"Started: {datetime.now().isoformat()}")
    print()

    # Process countries
    countries_dir = GRAPHS_DIR / "countries"
    countries = sorted([d.name for d in countries_dir.iterdir() if d.is_dir()])

    if resume:
        existing = set(f.stem.replace("_clusters", "") for f in (OUTPUT_DIR / "countries").glob("*.json"))
        countries = [c for c in countries if c not in existing]
        print(f"Resuming: {len(existing)} done, {len(countries)} remaining")

    if countries:
        print(f"Processing {len(countries)} countries...")

        completed = 0
        errors = 0
        start_time = time.time()

        with ProcessPoolExecutor(max_workers=n_jobs) as executor:
            futures = {executor.submit(process_country, c): c for c in countries}

            for future in as_completed(futures):
                country = futures[future]
                completed += 1

                try:
                    result = future.result()
                    if 'error' in result:
                        errors += 1
                        print(f"[{completed}/{len(countries)}] {country}: ERROR")
                    else:
                        out_path = OUTPUT_DIR / "countries" / f"{country}_clusters.json"
                        save_result(result, out_path)
                        n_c = result['summary']['n_clusters']
                        print(f"[{completed}/{len(countries)}] {country}: {n_c} clusters")
                except Exception as e:
                    errors += 1
                    print(f"[{completed}/{len(countries)}] {country}: EXCEPTION - {e}")

        country_time = time.time() - start_time
        print(f"\nCountries complete: {completed - errors}/{len(countries)} in {country_time/60:.1f}min")

    # Process unified years
    print("\nProcessing unified (global) graphs...")
    unified_dir = GRAPHS_DIR / "unified"
    years = sorted([int(f.stem.split('_')[0]) for f in unified_dir.glob("*_graph.json")])

    for year in years:
        result = process_unified_year(year)
        if 'error' not in result:
            out_path = OUTPUT_DIR / "unified" / f"{year}_clusters.json"
            save_result(result, out_path)
            print(f"  {year}: {result['summary']['n_clusters']} clusters")

    print()
    print("=" * 60)
    print("PRODUCTION COMPLETE")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Phase 3B: Development Cluster Detection")
    parser.add_argument("--test", action="store_true", help="Run test")
    parser.add_argument("--test-n", type=int, default=5, help="Countries for test")
    parser.add_argument("--jobs", "-j", type=int, default=8, help="Parallel workers")
    parser.add_argument("--resume", action="store_true", help="Resume")

    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "countries").mkdir(exist_ok=True)
    (OUTPUT_DIR / "unified").mkdir(exist_ok=True)

    if args.test:
        run_test(args.test_n)
    else:
        run_production(n_jobs=args.jobs, resume=args.resume)


if __name__ == "__main__":
    main()
