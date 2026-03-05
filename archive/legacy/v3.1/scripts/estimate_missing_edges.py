#!/usr/bin/env python3
"""
Diagnostic: Are We Missing Country-Specific Edges?

For a sample of countries, run FULL causal discovery and compare
to V2.1 structure. How many extra edges do we find?

This helps decide between:
- Option A: V2.1 structure only (fast, conservative)
- Option B: Hybrid approach (V2.1 + country-specific discovery)
- Option C: Full discovery per country (slow, comprehensive)
"""

import pandas as pd
import numpy as np
from pathlib import Path
from sklearn.linear_model import LassoCV
from sklearn.preprocessing import StandardScaler
import json
import warnings
from tqdm import tqdm

warnings.filterwarnings('ignore')

# Paths
DATA_DIR = Path('data/processed/countries')
GRAPH_DIR = Path('data/country_graphs')


def count_potential_edges_for_country(country_name: str,
                                       n_targets: int = 50,
                                       alpha_threshold: float = 0.01) -> dict:
    """
    Run full Lasso on one country to find ALL significant edges.
    Compare to V2.1 edges to see how many we're missing.

    Args:
        country_name: Full country name (e.g., "Brazil")
        n_targets: Number of target indicators to test (sample)
        alpha_threshold: Lasso alpha for edge detection

    Returns:
        Dictionary with edge counts and comparison metrics
    """

    # Load country data
    parquet_path = DATA_DIR / f'{country_name}.parquet'
    if not parquet_path.exists():
        raise FileNotFoundError(f"Country data not found: {parquet_path}")

    country_data = pd.read_parquet(parquet_path)

    # Get indicator columns (exclude year)
    indicator_cols = [c for c in country_data.columns if c != 'year']

    # Drop columns with >50% missing
    valid_cols = []
    for c in indicator_cols:
        if country_data[c].notna().mean() > 0.5:
            valid_cols.append(c)
    indicator_cols = valid_cols

    print(f"\n{country_name}: Testing {len(indicator_cols)} valid indicators (of {country_data.shape[1]-1} total)")

    # Load V2.1 edges for comparison
    graph_path = GRAPH_DIR / f'{country_name}.json'
    if not graph_path.exists():
        raise FileNotFoundError(f"Country graph not found: {graph_path}")

    with open(graph_path) as f:
        v21_graph = json.load(f)

    # Build V2.1 edge set
    v21_edges = set()
    for edge in v21_graph['edges']:
        v21_edges.add((edge['source'], edge['target']))

    print(f"  V2.1 total edges: {len(v21_edges)}")

    # Sample targets for discovery (random but deterministic)
    np.random.seed(42)
    sample_targets = np.random.choice(
        indicator_cols,
        size=min(n_targets, len(indicator_cols)),
        replace=False
    )

    # Run full Lasso discovery
    discovered_edges = set()
    successful_targets = 0

    for target in tqdm(sample_targets, desc=f"  Discovery", leave=False):
        y = country_data[target].dropna()
        if len(y) < 10:
            continue

        # Predictors (all other indicators)
        predictors = [c for c in indicator_cols if c != target]
        X = country_data.loc[y.index, predictors]

        # Filter columns with enough data
        X = X.loc[:, X.notna().sum() >= 10]

        if X.shape[1] < 5:
            continue

        # Fill missing with column mean
        X = X.fillna(X.mean())

        # Standardize
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        y_scaled = (y - y.mean()) / y.std() if y.std() > 0 else y

        try:
            # Lasso with cross-validation
            lasso = LassoCV(
                cv=min(5, len(y) - 1),  # Adjust CV folds for small samples
                max_iter=2000,
                n_alphas=10,
                random_state=42
            )
            lasso.fit(X_scaled, y_scaled)

            # Find non-zero coefficients
            for i, coef in enumerate(lasso.coef_):
                if abs(coef) > 0.001:  # Threshold for significance
                    source = X.columns[i]
                    discovered_edges.add((source, target))

            successful_targets += 1

        except Exception as e:
            continue

    print(f"  Successfully tested {successful_targets}/{len(sample_targets)} targets")

    # Compare to V2.1 (only edges where target is in our sample)
    v21_edges_in_sample = {e for e in v21_edges if e[1] in sample_targets}

    # Edges discovered but NOT in V2.1
    missing_in_v21 = discovered_edges - v21_edges

    # Edges in V2.1 but NOT discovered (for reference)
    not_discovered = v21_edges_in_sample - discovered_edges

    # Overlap
    overlap = discovered_edges & v21_edges_in_sample

    print(f"  V2.1 edges (in sample): {len(v21_edges_in_sample)}")
    print(f"  Discovered edges: {len(discovered_edges)}")
    print(f"  Overlap with V2.1: {len(overlap)}")
    print(f"  NEW edges (not in V2.1): {len(missing_in_v21)}")

    percent_more = (len(missing_in_v21) / len(v21_edges_in_sample) * 100
                   if len(v21_edges_in_sample) > 0 else 0)
    print(f"  --> {percent_more:.1f}% additional edges")

    # Sample of new edges
    if missing_in_v21:
        print(f"  Sample new edges:")
        for edge in list(missing_in_v21)[:5]:
            print(f"    {edge[0]} -> {edge[1]}")

    return {
        'country': country_name,
        'indicators_tested': successful_targets,
        'v21_edges_total': len(v21_edges),
        'v21_edges_in_sample': len(v21_edges_in_sample),
        'discovered_edges': len(discovered_edges),
        'overlap': len(overlap),
        'new_edges_not_in_v21': len(missing_in_v21),
        'v21_edges_not_discovered': len(not_discovered),
        'percent_more': percent_more,
        'sample_new_edges': list(missing_in_v21)[:10]
    }


def sample_countries_test(n_countries: int = 5):
    """
    Test N diverse countries representing different development levels and regions.
    """

    # Diverse sample: developed, emerging, developing, different regions
    test_countries = [
        'United States',     # Developed, North America
        'Rwanda',            # Developing, Africa
        'China',             # Emerging, Asia
        'Brazil',            # Emerging, South America
        'India'              # Emerging, South Asia
    ][:n_countries]

    # Check which countries exist
    available = []
    for country in test_countries:
        parquet_path = DATA_DIR / f'{country}.parquet'
        graph_path = GRAPH_DIR / f'{country}.json'
        if parquet_path.exists() and graph_path.exists():
            available.append(country)
        else:
            print(f"Warning: {country} not found, skipping")

    if not available:
        # Fallback to any available countries
        available_files = list(DATA_DIR.glob('*.parquet'))
        available = [f.stem for f in available_files[:n_countries]]
        print(f"Using fallback countries: {available}")

    results = []

    print("="*70)
    print("DIAGNOSTIC: Missing Country-Specific Edges")
    print("="*70)

    for country in available:
        try:
            result = count_potential_edges_for_country(country)
            results.append(result)
        except Exception as e:
            print(f"  Error with {country}: {e}")

    if not results:
        print("No results generated!")
        return None

    # Summary
    df = pd.DataFrame(results)

    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)

    # Display key metrics
    summary_cols = ['country', 'v21_edges_in_sample', 'discovered_edges',
                   'new_edges_not_in_v21', 'percent_more']
    print(df[summary_cols].to_string(index=False))

    mean_percent = df['percent_more'].mean()
    std_percent = df['percent_more'].std()

    print(f"\n{'='*70}")
    print(f"MEAN additional edges: {mean_percent:.1f}% (+/- {std_percent:.1f}%)")
    print(f"{'='*70}")

    # Recommendation
    print("\nRECOMMENDATION:")
    if mean_percent < 20:
        print("  < 20% extra edges --> V2.1 structure is SUFFICIENT")
        print("  --> Proceed with Phase B as-is")
        print("  --> Country-specific edges are rare")
    elif mean_percent < 50:
        print("  20-50% extra edges --> HYBRID APPROACH recommended")
        print("  --> Keep V2.1 structure as base")
        print("  --> Add country-specific discovery for strong effects only")
        print("  --> Timeline: +1 week")
    else:
        print("  > 50% extra edges --> FULL DISCOVERY needed")
        print("  --> V2.1 structure is too restrictive")
        print("  --> Consider full causal discovery per country")
        print("  --> Timeline: +2-4 weeks")

    # Save results
    output_path = Path('outputs/validation/missing_edges_diagnostic.json')
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Convert to serializable format
    output_data = {
        'summary': {
            'mean_percent_more': mean_percent,
            'std_percent_more': std_percent,
            'recommendation': 'V2.1_SUFFICIENT' if mean_percent < 20
                            else ('HYBRID' if mean_percent < 50 else 'FULL_DISCOVERY')
        },
        'country_results': results
    }

    with open(output_path, 'w') as f:
        json.dump(output_data, f, indent=2)

    print(f"\nResults saved to: {output_path}")

    return df


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Diagnostic for missing country-specific edges')
    parser.add_argument('--countries', type=int, default=5, help='Number of countries to test')
    parser.add_argument('--targets', type=int, default=50, help='Number of target indicators per country')

    args = parser.parse_args()

    sample_countries_test(n_countries=args.countries)
