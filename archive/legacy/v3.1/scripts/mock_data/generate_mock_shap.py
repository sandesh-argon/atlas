#!/usr/bin/env python3
"""
Generate Mock Temporal SHAP Data for Frontend Development

Creates realistic mock SHAP importance data while real computation runs on AWS.
Mock data follows the exact schema expected by frontend and has realistic:
- Temporal evolution (gradual year-to-year changes)
- Cross-country variation
- Domain-specific patterns

Output: data/v3_1_temporal_shap_mock/
"""

import json
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# Configuration
BASE_DIR = Path("<repo-root>/v3.1")
NODES_FILE = BASE_DIR / "data" / "raw" / "v21_nodes.csv"
OUTPUT_DIR = BASE_DIR / "data" / "v3_1_temporal_shap_mock"

# Targets (9 total)
TARGETS = [
    "quality_of_life",
    "health",
    "education",
    "economic",
    "governance",
    "environment",
    "demographics",
    "security",
    "development"
]

# Target to root node mapping
TARGET_ROOTS = {
    "quality_of_life": "root",
    "health": "1",
    "education": "2",
    "economic": "3",
    "governance": "6",
    "environment": "9",
    "demographics": "coarse_5",
    "security": "5",
    "development": "7"
}

# Representative countries for mock data (key economies + regional diversity)
MOCK_COUNTRIES = [
    # G7
    "United States", "United Kingdom", "Germany", "France", "Italy", "Canada", "Japan",
    # BRICS
    "Brazil", "Russia", "India", "China", "South Africa",
    # Other major economies
    "Australia", "South Korea", "Mexico", "Indonesia", "Turkey", "Saudi Arabia",
    # European
    "Spain", "Netherlands", "Sweden", "Poland", "Switzerland",
    # African
    "Nigeria", "Kenya", "Ethiopia", "Rwanda", "Egypt",
    # Asian
    "Thailand", "Vietnam", "Philippines", "Pakistan", "Bangladesh",
    # Latin American
    "Argentina", "Colombia", "Chile", "Peru",
    # Small states
    "Singapore", "New Zealand", "Ireland"
]

# Years
YEARS = list(range(1990, 2025))

# Seed for reproducibility
np.random.seed(42)


def load_nodes():
    """Load node hierarchy from v21_nodes.csv."""
    df = pd.read_csv(NODES_FILE)
    return df


def generate_base_importance(nodes_df, target: str) -> dict:
    """
    Generate base SHAP importance values for a target.
    Higher layers have higher importance (following hierarchy).
    """
    importance = {}

    # Root always = 1.0
    root_node = TARGET_ROOTS.get(target, "root")
    importance[root_node] = 1.0

    # Layer-based decay
    layer_decay = {
        0: 1.0,      # Root
        1: 0.7,      # Outcome categories
        2: 0.4,      # Coarse domains
        3: 0.15,     # Fine-grained
        4: 0.05      # Leaf nodes
    }

    for _, row in nodes_df.iterrows():
        node_id = str(row['id'])
        layer = row.get('layer', 4)
        domain = row.get('domain', 'other')

        if node_id in importance:
            continue

        # Base importance from layer
        base = layer_decay.get(layer, 0.02)

        # Domain bonus for target-relevant domains
        domain_bonus = 0
        if target == "health" and domain == "Health":
            domain_bonus = 0.1
        elif target == "education" and domain == "Education":
            domain_bonus = 0.1
        elif target == "economic" and domain == "Economic":
            domain_bonus = 0.1
        elif target == "governance" and domain == "Governance":
            domain_bonus = 0.1
        elif target == "security" and domain == "Security":
            domain_bonus = 0.1
        elif target == "environment" and domain == "Environment":
            domain_bonus = 0.1
        elif target == "development" and domain == "Development":
            domain_bonus = 0.1

        # Add noise
        noise = np.random.uniform(-0.05, 0.05)

        value = max(0.001, min(1.0, base + domain_bonus + noise))
        importance[node_id] = round(value, 6)

    return importance


def evolve_importance(base_importance: dict, year: int, country: str = None) -> dict:
    """
    Evolve importance values over time with realistic temporal dynamics.
    """
    evolved = {}

    # Year-based evolution factor (gradual improvement over time)
    year_factor = (year - 1990) / 35  # 0 to 1

    # Country-specific modifier
    country_modifier = 1.0
    if country:
        # Developed countries have more stable, higher importance
        developed = ["United States", "United Kingdom", "Germany", "France",
                    "Japan", "Canada", "Australia", "Sweden", "Switzerland"]
        if country in developed:
            country_modifier = 1.1
        # Emerging economies show more change over time
        emerging = ["China", "India", "Brazil", "Indonesia", "Vietnam"]
        if country in emerging:
            country_modifier = 0.9 + 0.3 * year_factor  # Catch-up effect

    for node_id, base_value in base_importance.items():
        if node_id in TARGET_ROOTS.values():
            # Root nodes stay at 1.0
            evolved[node_id] = 1.0
            continue

        # Temporal evolution
        evolution = 0.05 * year_factor * (np.random.random() - 0.3)

        # Apply country modifier
        value = base_value * country_modifier + evolution

        # Add small year-specific noise for realism
        noise = np.random.normal(0, 0.01)
        value += noise

        # Clamp to valid range
        value = max(0.001, min(0.99, value))
        evolved[node_id] = round(value, 6)

    return evolved


def generate_mock_shap_file(target: str, year: int, country: str = None,
                           base_importance: dict = None, nodes_df: pd.DataFrame = None):
    """
    Generate a single mock SHAP file.
    """
    # Evolve importance for this year/country
    shap_importance = evolve_importance(base_importance, year, country)

    # Ensure root is 1.0
    root_node = TARGET_ROOTS.get(target, "root")
    shap_importance[root_node] = 1.0

    # Compute metadata
    values = list(shap_importance.values())

    result = {
        "target": target,
        "year": year,
        "shap_importance": shap_importance,
        "metadata": {
            "n_samples": max(5, year - 1990 + 1),  # Cumulative samples
            "n_features": len(shap_importance),
            "mean_importance": round(np.mean(values), 6),
            "std_importance": round(np.std(values), 6),
            "max_importance": 1.0,
            "computation_date": datetime.now().strftime("%Y-%m-%d"),
            "is_mock_data": True
        },
        "provenance": {
            "code_version": "v3.1.0-mock",
            "algorithm": "mock_generation",
            "note": "Mock data for frontend development while real SHAP computes on AWS"
        }
    }

    if country:
        result["country"] = country
    else:
        result["source"] = "unified"

    return result


def main():
    print("=" * 60)
    print("MOCK TEMPORAL SHAP DATA GENERATOR")
    print("=" * 60)
    print(f"Started: {datetime.now().isoformat()}")

    # Load nodes
    print("\nLoading node hierarchy...")
    nodes_df = load_nodes()
    print(f"  Loaded {len(nodes_df)} nodes")

    # Create output directories
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "unified").mkdir(exist_ok=True)
    (OUTPUT_DIR / "countries").mkdir(exist_ok=True)

    # Generate base importance for each target
    print("\nGenerating base importance patterns...")
    base_patterns = {}
    for target in TARGETS:
        base_patterns[target] = generate_base_importance(nodes_df, target)
        print(f"  {target}: {len(base_patterns[target])} nodes")

    # Generate unified (global) data
    print(f"\nGenerating unified data ({len(TARGETS)} targets × {len(YEARS)} years)...")
    unified_count = 0

    for target in TARGETS:
        target_dir = OUTPUT_DIR / "unified" / target
        target_dir.mkdir(exist_ok=True)

        for year in YEARS:
            data = generate_mock_shap_file(
                target=target,
                year=year,
                country=None,
                base_importance=base_patterns[target],
                nodes_df=nodes_df
            )

            output_file = target_dir / f"{year}_shap.json"
            with open(output_file, 'w') as f:
                json.dump(data, f, indent=2)

            unified_count += 1

    print(f"  Generated {unified_count} unified files")

    # Generate country data
    print(f"\nGenerating country data ({len(MOCK_COUNTRIES)} countries × {len(TARGETS)} targets × {len(YEARS)} years)...")
    country_count = 0

    for country in MOCK_COUNTRIES:
        country_dir = OUTPUT_DIR / "countries" / country
        country_dir.mkdir(exist_ok=True)

        for target in TARGETS:
            target_dir = country_dir / target
            target_dir.mkdir(exist_ok=True)

            for year in YEARS:
                data = generate_mock_shap_file(
                    target=target,
                    year=year,
                    country=country,
                    base_importance=base_patterns[target],
                    nodes_df=nodes_df
                )

                output_file = target_dir / f"{year}_shap.json"
                with open(output_file, 'w') as f:
                    json.dump(data, f, indent=2)

                country_count += 1

        # Progress indicator
        if country_count % 1000 == 0:
            print(f"  Progress: {country_count} files...")

    print(f"  Generated {country_count} country files")

    # Summary
    total_files = unified_count + country_count
    print("\n" + "=" * 60)
    print("GENERATION COMPLETE")
    print("=" * 60)
    print(f"Total files: {total_files}")
    print(f"  Unified: {unified_count}")
    print(f"  Countries: {country_count} ({len(MOCK_COUNTRIES)} countries)")
    print(f"\nOutput directory: {OUTPUT_DIR}")

    # Create manifest
    manifest = {
        "generated": datetime.now().isoformat(),
        "is_mock_data": True,
        "targets": TARGETS,
        "years": YEARS,
        "countries": MOCK_COUNTRIES,
        "unified_files": unified_count,
        "country_files": country_count,
        "total_files": total_files,
        "note": "Mock data for frontend development. Real data computing on AWS."
    }

    with open(OUTPUT_DIR / "MANIFEST.json", 'w') as f:
        json.dump(manifest, f, indent=2)

    print(f"\nManifest written to: {OUTPUT_DIR / 'MANIFEST.json'}")


if __name__ == "__main__":
    main()
