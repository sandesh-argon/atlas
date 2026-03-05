#!/usr/bin/env python3
"""
Phase 3B: Feedback Loop Detection

Identifies bidirectional causal relationships (A↔B) from temporal graphs.
Classifies as virtuous (reinforcing), vicious (negative spiral), or dampening.

Input: Phase 2B temporal graphs (4,628 country files)
Output: 178 feedback loop files (one per country)
"""

import json
import os
import sys
import time
import argparse
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Dict, List, Tuple, Optional
import math

# Configuration
BASE_DIR = Path("<repo-root>/v3.1")
GRAPHS_DIR = BASE_DIR / "data" / "v3_1_temporal_graphs" / "countries"
OUTPUT_DIR = BASE_DIR / "data" / "v3_1_feedback_loops"

# Parameters
P_VALUE_THRESHOLD = 0.05  # Significance threshold for edges
MIN_YEARS_ACTIVE = 3      # Minimum years loop must be present
MIN_LOOP_STRENGTH = 0.01  # Minimum beta_forward * beta_reverse


class NumpyEncoder(json.JSONEncoder):
    """Handle numpy types in JSON serialization."""
    def default(self, obj):
        import numpy as np
        if isinstance(obj, (np.integer, np.int64, np.int32)):
            return int(obj)
        if isinstance(obj, (np.floating, np.float64, np.float32)):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)


def load_country_graphs(country_dir: Path) -> Dict[int, dict]:
    """Load all temporal graphs for a country."""
    graphs = {}

    for graph_file in country_dir.glob("*_graph.json"):
        try:
            year = int(graph_file.stem.split("_")[0])
            with open(graph_file) as f:
                graphs[year] = json.load(f)
        except (ValueError, json.JSONDecodeError) as e:
            continue

    return graphs


def build_edge_index(graphs: Dict[int, dict]) -> Dict[Tuple[str, str], List[dict]]:
    """
    Build index of edges across all years.
    Returns: {(source, target): [{year, beta, lag, p_value, ci_lower, ci_upper}, ...]}
    """
    edge_index = defaultdict(list)

    for year, graph in graphs.items():
        for edge in graph.get("edges", []):
            key = (edge["source"], edge["target"])
            edge_index[key].append({
                "year": year,
                "beta": edge.get("beta", 0),
                "lag": edge.get("lag", 0),
                "p_value": edge.get("p_value", 1.0),
                "ci_lower": edge.get("ci_lower"),
                "ci_upper": edge.get("ci_upper"),
                "r_squared": edge.get("r_squared", 0)
            })

    return edge_index


def find_feedback_loops(edge_index: Dict[Tuple[str, str], List[dict]]) -> List[dict]:
    """
    Find all bidirectional relationships (feedback loops).
    A loop exists when both A→B and B→A are significant.
    """
    loops = []
    checked_pairs = set()

    # Get all unique nodes
    nodes = set()
    for (src, tgt) in edge_index.keys():
        nodes.add(src)
        nodes.add(tgt)

    # Check all node pairs
    for node_a in nodes:
        for node_b in nodes:
            if node_a >= node_b:  # Avoid duplicates and self-loops
                continue

            pair_key = (min(node_a, node_b), max(node_a, node_b))
            if pair_key in checked_pairs:
                continue
            checked_pairs.add(pair_key)

            # Get edges in both directions
            forward_edges = edge_index.get((node_a, node_b), [])
            reverse_edges = edge_index.get((node_b, node_a), [])

            # Filter to significant edges only
            sig_forward = [e for e in forward_edges if e["p_value"] < P_VALUE_THRESHOLD]
            sig_reverse = [e for e in reverse_edges if e["p_value"] < P_VALUE_THRESHOLD]

            if not sig_forward or not sig_reverse:
                continue

            # Find years where both directions are present
            forward_years = set(e["year"] for e in sig_forward)
            reverse_years = set(e["year"] for e in sig_reverse)
            common_years = forward_years & reverse_years

            if len(common_years) < MIN_YEARS_ACTIVE:
                continue

            # Compute average betas and lags across common years
            forward_in_common = [e for e in sig_forward if e["year"] in common_years]
            reverse_in_common = [e for e in sig_reverse if e["year"] in common_years]

            avg_beta_forward = sum(e["beta"] for e in forward_in_common) / len(forward_in_common)
            avg_beta_reverse = sum(e["beta"] for e in reverse_in_common) / len(reverse_in_common)
            avg_lag_forward = sum(e["lag"] for e in forward_in_common) / len(forward_in_common)
            avg_lag_reverse = sum(e["lag"] for e in reverse_in_common) / len(reverse_in_common)

            # Compute loop strength
            loop_strength = abs(avg_beta_forward * avg_beta_reverse)

            if loop_strength < MIN_LOOP_STRENGTH:
                continue

            # Classify loop type
            if avg_beta_forward > 0 and avg_beta_reverse > 0:
                loop_type = "virtuous"  # Both positive = reinforcing
            elif avg_beta_forward < 0 and avg_beta_reverse < 0:
                loop_type = "vicious"   # Both negative = negative spiral
            else:
                loop_type = "dampening"  # Mixed signs = self-correcting

            # Compute equilibrium time (simplified)
            # Time to reach 90% of equilibrium: t = ln(0.1) / ln(loop_strength)
            if loop_strength < 1:
                equilibrium_years = round(abs(math.log(0.1) / math.log(1 - loop_strength + 1e-10)))
                equilibrium_years = min(equilibrium_years, 50)  # Cap at 50 years
            else:
                equilibrium_years = 1  # Immediate if strength >= 1

            # Get CI ranges
            ci_forward = {
                "mean": avg_beta_forward,
                "min": min(e["ci_lower"] for e in forward_in_common if e["ci_lower"] is not None) if any(e["ci_lower"] for e in forward_in_common) else None,
                "max": max(e["ci_upper"] for e in forward_in_common if e["ci_upper"] is not None) if any(e["ci_upper"] for e in forward_in_common) else None
            }
            ci_reverse = {
                "mean": avg_beta_reverse,
                "min": min(e["ci_lower"] for e in reverse_in_common if e["ci_lower"] is not None) if any(e["ci_lower"] for e in reverse_in_common) else None,
                "max": max(e["ci_upper"] for e in reverse_in_common if e["ci_upper"] is not None) if any(e["ci_upper"] for e in reverse_in_common) else None
            }

            loops.append({
                "node_1": node_a,
                "node_2": node_b,
                "beta_forward": round(avg_beta_forward, 4),
                "beta_reverse": round(avg_beta_reverse, 4),
                "lag_forward": round(avg_lag_forward, 1),
                "lag_reverse": round(avg_lag_reverse, 1),
                "loop_strength": round(loop_strength, 4),
                "type": loop_type,
                "years_active": sorted(common_years),
                "n_years_active": len(common_years),
                "equilibrium_years": equilibrium_years,
                "ci_forward": ci_forward,
                "ci_reverse": ci_reverse
            })

    # Sort by loop strength (strongest first)
    loops.sort(key=lambda x: x["loop_strength"], reverse=True)

    return loops


def process_country(country_name: str) -> dict:
    """Process a single country and return feedback loop analysis."""
    start_time = time.time()

    country_dir = GRAPHS_DIR / country_name
    if not country_dir.exists():
        return {"country": country_name, "error": "Directory not found"}

    # Load all graphs
    graphs = load_country_graphs(country_dir)
    if not graphs:
        return {"country": country_name, "error": "No graph files found"}

    # Build edge index
    edge_index = build_edge_index(graphs)

    # Find feedback loops
    loops = find_feedback_loops(edge_index)

    # Compute summary
    n_virtuous = sum(1 for l in loops if l["type"] == "virtuous")
    n_vicious = sum(1 for l in loops if l["type"] == "vicious")
    n_dampening = sum(1 for l in loops if l["type"] == "dampening")

    strongest = loops[0] if loops else None
    strongest_desc = f"{strongest['node_1']} <-> {strongest['node_2']}" if strongest else None

    elapsed = time.time() - start_time

    return {
        "country": country_name,
        "feedback_loops": loops,
        "summary": {
            "n_loops": len(loops),
            "n_virtuous": n_virtuous,
            "n_vicious": n_vicious,
            "n_dampening": n_dampening,
            "strongest_loop": strongest_desc,
            "strongest_strength": strongest["loop_strength"] if strongest else None
        },
        "metadata": {
            "years_analyzed": sorted(graphs.keys()),
            "n_years": len(graphs),
            "n_edges_total": sum(len(g.get("edges", [])) for g in graphs.values()),
            "computation_time_sec": round(elapsed, 2)
        },
        "provenance": {
            "computation_date": datetime.now().isoformat(),
            "code_version": "v3.1.0",
            "p_value_threshold": P_VALUE_THRESHOLD,
            "min_years_active": MIN_YEARS_ACTIVE,
            "min_loop_strength": MIN_LOOP_STRENGTH
        }
    }


def save_result(result: dict):
    """Save feedback loop result to JSON file."""
    country = result["country"]
    out_path = OUTPUT_DIR / f"{country}_feedback_loops.json"

    with open(out_path, 'w') as f:
        json.dump(result, f, indent=2, cls=NumpyEncoder)


def run_test(n_countries: int = 5):
    """Run test on a few countries."""
    print("=" * 60)
    print("PHASE 3B TEST: Feedback Loop Detection")
    print("=" * 60)
    print(f"Testing on {n_countries} countries...")
    print()

    # Get sample countries
    countries = sorted([d.name for d in GRAPHS_DIR.iterdir() if d.is_dir()])[:n_countries]

    total_time = 0
    results = []

    for country in countries:
        print(f"Processing {country}...", end=" ", flush=True)
        result = process_country(country)
        total_time += result.get("metadata", {}).get("computation_time_sec", 0)

        if "error" in result:
            print(f"ERROR: {result['error']}")
        else:
            n_loops = result["summary"]["n_loops"]
            elapsed = result["metadata"]["computation_time_sec"]
            print(f"{n_loops} loops found ({elapsed:.2f}s)")
            results.append(result)

            # Save test result
            save_result(result)

    # Summary
    print()
    print("-" * 60)
    print("TEST SUMMARY")
    print("-" * 60)

    avg_time = total_time / len(countries)
    total_countries = len([d for d in GRAPHS_DIR.iterdir() if d.is_dir()])

    print(f"Countries tested: {len(countries)}")
    print(f"Average time per country: {avg_time:.2f}s")
    print(f"Total countries available: {total_countries}")

    # ETA calculation
    eta_seconds = avg_time * total_countries / 8  # 8 cores
    eta_minutes = eta_seconds / 60

    print()
    print(f"ESTIMATED RUNTIME (8 cores): {eta_minutes:.1f} minutes ({eta_seconds/3600:.2f} hours)")

    # Sample output
    if results:
        print()
        print("-" * 60)
        print("SAMPLE OUTPUT")
        print("-" * 60)
        sample = results[0]
        print(f"Country: {sample['country']}")
        print(f"Total loops: {sample['summary']['n_loops']}")
        print(f"  Virtuous: {sample['summary']['n_virtuous']}")
        print(f"  Vicious: {sample['summary']['n_vicious']}")
        print(f"  Dampening: {sample['summary']['n_dampening']}")

        if sample["feedback_loops"]:
            print()
            print("Top 3 strongest loops:")
            for i, loop in enumerate(sample["feedback_loops"][:3]):
                print(f"  {i+1}. {loop['node_1']} <-> {loop['node_2']}")
                print(f"     β_fwd={loop['beta_forward']:.3f}, β_rev={loop['beta_reverse']:.3f}")
                print(f"     Strength={loop['loop_strength']:.4f}, Type={loop['type']}")
                print(f"     Active years: {loop['years_active'][0]}-{loop['years_active'][-1]}")

    return avg_time, total_countries


def run_production(n_jobs: int = 8, resume: bool = False):
    """Run full production on all countries."""
    print("=" * 60)
    print("PHASE 3B PRODUCTION: Feedback Loop Detection")
    print("=" * 60)
    print(f"Workers: {n_jobs}")
    print(f"Started: {datetime.now().isoformat()}")
    print()

    # Get all countries
    countries = sorted([d.name for d in GRAPHS_DIR.iterdir() if d.is_dir()])

    # Filter if resuming
    if resume:
        existing = set(f.stem.replace("_feedback_loops", "") for f in OUTPUT_DIR.glob("*.json"))
        countries = [c for c in countries if c not in existing]
        print(f"Resuming: {len(existing)} already done, {len(countries)} remaining")

    if not countries:
        print("All countries already processed!")
        return

    print(f"Countries to process: {len(countries)}")
    print()

    # Process in parallel
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

                if "error" in result:
                    errors += 1
                    print(f"[{completed}/{len(countries)}] {country}: ERROR - {result['error']}")
                else:
                    save_result(result)
                    n_loops = result["summary"]["n_loops"]
                    elapsed = result["metadata"]["computation_time_sec"]
                    print(f"[{completed}/{len(countries)}] {country}: {n_loops} loops ({elapsed:.1f}s)")

            except Exception as e:
                errors += 1
                print(f"[{completed}/{len(countries)}] {country}: EXCEPTION - {e}")

    # Final summary
    total_time = time.time() - start_time

    print()
    print("=" * 60)
    print("PRODUCTION COMPLETE")
    print("=" * 60)
    print(f"Total countries: {len(countries)}")
    print(f"Successful: {completed - errors}")
    print(f"Errors: {errors}")
    print(f"Total time: {total_time/60:.1f} minutes")
    print(f"Completed: {datetime.now().isoformat()}")


def main():
    parser = argparse.ArgumentParser(description="Phase 3B: Feedback Loop Detection")
    parser.add_argument("--test", action="store_true", help="Run test on 5 countries")
    parser.add_argument("--test-n", type=int, default=5, help="Number of countries for test")
    parser.add_argument("--jobs", "-j", type=int, default=8, help="Number of parallel workers")
    parser.add_argument("--resume", action="store_true", help="Resume interrupted run")

    args = parser.parse_args()

    # Ensure output directory exists
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if args.test:
        run_test(args.test_n)
    else:
        run_production(n_jobs=args.jobs, resume=args.resume)


if __name__ == "__main__":
    main()
