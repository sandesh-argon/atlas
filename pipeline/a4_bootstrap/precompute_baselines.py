"""
Pre-compute Country Baselines

Extracts baseline indicator values from panel data and saves them
as lightweight JSON files for fast loading during simulation.

Output structure:
  data/v3_1_baselines/
    Australia/
      2000.json  # {"indicator_id": value, ...}
      2001.json
      ...
    Brazil/
      ...

Each file is ~50-200KB instead of loading 65MB parquet.
"""

import json
import sys
from pathlib import Path
from typing import Dict, Set
import pandas as pd

# Paths
DATA_ROOT = Path(__file__).parent.parent / "data"
PANEL_PATH = DATA_ROOT / "raw" / "v21_panel_data_for_v3.parquet"
OUTPUT_DIR = DATA_ROOT / "v31" / "baselines"


def get_available_countries_from_graphs() -> Set[str]:
    """Get list of countries that have temporal graph data."""
    graphs_dir = DATA_ROOT / "v31" / "temporal_graphs" / "countries"
    if not graphs_dir.exists():
        return set()
    return {d.name for d in graphs_dir.iterdir() if d.is_dir()}


def get_available_years_for_country(country: str) -> Set[int]:
    """Get years that have graph data for a country."""
    country_dir = DATA_ROOT / "v31" / "temporal_graphs" / "countries" / country
    if not country_dir.exists():
        return set()
    years = set()
    for f in country_dir.glob("*_graph.json"):
        try:
            year = int(f.stem.split("_")[0])
            years.add(year)
        except ValueError:
            pass
    return years


def precompute_baselines(
    panel_path: Path = None,
    output_dir: Path = None,
    countries: Set[str] = None,
    verbose: bool = True
) -> Dict[str, int]:
    """
    Extract baselines from panel data and save as JSON files.

    Args:
        panel_path: Path to panel parquet file
        output_dir: Where to save baseline JSON files
        countries: Specific countries to process (None = all with graph data)
        verbose: Print progress

    Returns:
        Dict with stats: {files_created, countries_processed, errors}
    """
    # Find panel data
    panel_path = panel_path or PANEL_PATH
    if not panel_path.exists():
        raise FileNotFoundError(f"Panel data not found at {PANEL_PATH}")

    output_dir = output_dir or OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    # Get countries with graph data
    graph_countries = get_available_countries_from_graphs()
    if countries:
        countries = countries & graph_countries
    else:
        countries = graph_countries

    if verbose:
        print(f"Loading panel data from {panel_path}...")

    # Load panel data
    df = pd.read_parquet(panel_path)

    if verbose:
        print(f"Panel data: {len(df):,} rows")
        print(f"Countries in panel: {df['country'].nunique()}")
        print(f"Countries with graphs: {len(graph_countries)}")
        print(f"Processing: {len(countries)} countries")

    stats = {"files_created": 0, "countries_processed": 0, "errors": 0}

    for i, country in enumerate(sorted(countries)):
        if verbose and (i + 1) % 20 == 0:
            print(f"  Progress: {i + 1}/{len(countries)} countries...")

        # Get years with graph data for this country
        years_needed = get_available_years_for_country(country)
        if not years_needed:
            continue

        # Filter panel data for this country
        country_data = df[df['country'] == country]
        if country_data.empty:
            # Try case-insensitive match
            country_lower = country.lower()
            country_data = df[df['country'].str.lower() == country_lower]

        if country_data.empty:
            if verbose:
                print(f"  Warning: No panel data for {country}")
            stats["errors"] += 1
            continue

        # Create country directory
        country_dir = output_dir / country
        country_dir.mkdir(exist_ok=True)

        # Process each year
        available_panel_years = sorted(country_data['year'].unique())
        for year in sorted(years_needed):
            year_data = country_data[country_data['year'] == year]

            if year_data.empty:
                # Use nearest year
                if len(available_panel_years) == 0:
                    continue
                nearest_year = min(available_panel_years, key=lambda y: abs(y - year))
                year_data = country_data[country_data['year'] == nearest_year]

            if year_data.empty:
                continue

            # Extract baseline values
            baseline = {}
            for _, row in year_data.iterrows():
                indicator_id = row.get('indicator_id')
                value = row.get('value')
                if indicator_id and pd.notna(value):
                    baseline[indicator_id] = float(value)

            # Backfill missing indicators from nearest available years
            # (e.g. PWT data ends at 2019 but graphs exist for 2020+)
            all_indicators = country_data['indicator_id'].unique()
            missing = set(all_indicators) - set(baseline.keys())
            if missing:
                for ind in missing:
                    ind_data = country_data[country_data['indicator_id'] == ind].dropna(subset=['value'])
                    if ind_data.empty:
                        continue
                    nearest_yr = min(ind_data['year'].values, key=lambda y: abs(y - year))
                    val = ind_data[ind_data['year'] == nearest_yr]['value'].iloc[0]
                    if pd.notna(val):
                        baseline[ind] = float(val)

            if not baseline:
                continue

            # Save to JSON
            output_file = country_dir / f"{year}.json"
            with open(output_file, 'w') as f:
                json.dump({
                    "country": country,
                    "year": year,
                    "n_indicators": len(baseline),
                    "values": baseline
                }, f)

            stats["files_created"] += 1

        stats["countries_processed"] += 1

    if verbose:
        print(f"\nComplete!")
        print(f"  Countries processed: {stats['countries_processed']}")
        print(f"  Files created: {stats['files_created']}")
        print(f"  Errors: {stats['errors']}")
        print(f"  Output: {output_dir}")

    return stats


def load_precomputed_baseline(country: str, year: int) -> Dict[str, float]:
    """
    Load pre-computed baseline for a country/year.

    Args:
        country: Country name
        year: Year

    Returns:
        Dict of indicator_id -> value, or empty dict if not found
    """
    baseline_file = OUTPUT_DIR / country / f"{year}.json"

    if not baseline_file.exists():
        # Try to find nearest year
        country_dir = OUTPUT_DIR / country
        if not country_dir.exists():
            return {}

        available = []
        for f in country_dir.glob("*.json"):
            try:
                y = int(f.stem)
                available.append(y)
            except ValueError:
                pass

        if not available:
            return {}

        nearest_year = min(available, key=lambda y: abs(y - year))
        baseline_file = country_dir / f"{nearest_year}.json"

    try:
        with open(baseline_file) as f:
            data = json.load(f)
            return data.get("values", {})
    except (json.JSONDecodeError, IOError):
        return {}


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Pre-compute country baselines")
    parser.add_argument("--countries", nargs="+", help="Specific countries to process")
    parser.add_argument("--quiet", action="store_true", help="Suppress output")
    args = parser.parse_args()

    countries = set(args.countries) if args.countries else None
    precompute_baselines(countries=countries, verbose=not args.quiet)
