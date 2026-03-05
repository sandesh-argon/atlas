#!/usr/bin/env python
"""
Phase A.4: Compute country-specific SHAP importance.

For each country:
1. Load country graph (edges) and panel data (time series)
2. Pivot panel data to wide format (years × indicators)
3. Train GradientBoostingRegressor on QoL composite
4. Compute SHAP values for all indicators
5. Save to data/country_shap/{country}_shap.json

Runtime: ~1-2 hours for 205 countries (30-60 sec per country)
"""

import sys
import json
import warnings
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
import shap
from tqdm import tqdm

warnings.filterwarnings('ignore')

# === CONFIGURATION ===

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
GRAPHS_DIR = DATA_DIR / "country_graphs"
OUTPUT_DIR = DATA_DIR / "country_shap"
PANEL_PATH = DATA_DIR / "raw" / "v21_panel_data_for_v3.parquet"
NODES_PATH = DATA_DIR / "raw" / "v21_nodes.csv"

# QoL outcome indicators with fallback alternatives
# Different countries may use different indicator codes for the same concept
QOL_OUTCOMES = [
    {
        'name': 'Life Expectancy',
        'ids': ['wdi_lifexp', 'SP.DYN.LE00.IN', 'ihme_lifexp_0204t'],
        'negative': False
    },
    {
        'name': 'Male Life Expectancy',
        'ids': ['wdi_lifexpm', 'SP.DYN.LE00.MA.IN', 'ihme_lifexp_0204m'],
        'negative': False
    },
    {
        'name': 'Female Life Expectancy',
        'ids': ['wdi_lifexpf', 'SP.DYN.LE00.FE.IN'],
        'negative': False
    },
    {
        'name': 'GDP per Capita',
        'ids': ['NY.GDP.PCAP.KD', 'NY.GDP.PCAP.PP.KD', 'NY.GDP.PCAP.CD'],
        'negative': False
    },
    {
        'name': 'Infant Mortality',
        'ids': ['SP.DYN.IMRT.IN', 'SH.DYN.MORT', 'CHILDMORT_MORTALITY_10TO14'],
        'negative': True
    },
    {
        'name': 'Homicide Rate',
        'ids': ['wdi_homicides', 'VC.IHR.PSRC.P5'],
        'negative': True
    },
    {
        'name': 'Gini Index',
        'ids': ['SI.POV.GINI', 'gini_disp'],
        'negative': True
    },
    {
        'name': 'Adult Literacy',
        'ids': ['SE.ADT.LITR.ZS', 'SE.ADT.1524.LT.ZS'],
        'negative': False
    },
    {
        'name': 'Internet Users',
        'ids': ['IT.NET.USER.ZS', 'IT.NET.BBND.P2'],
        'negative': False
    },
]

# Country name mapping: graph file name -> panel data names (with QoL data)
# Maps countries where graph file uses different name than panel data
COUNTRY_NAME_MAPPING = {
    'Burma_Myanmar': ['Myanmar', 'Burma/Myanmar'],
    'Cape Verde': ['Cabo Verde', 'Cape Verde'],
    'Hong Kong': ['Hong Kong SAR, China', 'China, Hong Kong Special Administrative Region', 'Hong Kong'],
    'Taiwan': ['Taiwan (Province of China)', 'Taiwan, China', 'Taiwan'],
    'The Gambia': ['Gambia', 'Gambia (the)', 'The Gambia'],
    'Türkiye': ['Turkey', 'Türkiye'],
    'Ivory Coast': ["Cote d'Ivoire", "Côte d'Ivoire", 'Ivory Coast'],
    'Republic of the Congo': ['Congo, Rep.', 'Congo (the)', 'Republic of the Congo'],
    'Congo, Dem. Rep.': ['Congo, Dem. Rep.', 'Congo (the Democratic Republic of the)', 'DR Congo'],
}

# === HELPER FUNCTIONS ===

def load_panel_data():
    """Load full panel data (long format)."""
    print("Loading panel data...")
    df = pd.read_parquet(PANEL_PATH)
    print(f"  Loaded {len(df):,} rows")
    return df


def load_country_graph(country: str) -> dict:
    """Load country causal graph."""
    path = GRAPHS_DIR / f"{country}.json"
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)


def load_hierarchy() -> pd.DataFrame:
    """Load V2.1 node hierarchy."""
    return pd.read_csv(NODES_PATH)


def get_indicators_from_graph(graph: dict) -> set:
    """Extract unique indicator IDs from graph edges."""
    indicators = set()
    for edge in graph.get('edges', []):
        indicators.add(edge['source'])
        indicators.add(edge['target'])
    return indicators


def pivot_country_data(panel: pd.DataFrame, country: str) -> pd.DataFrame:
    """
    Pivot country's long-format data to wide format.

    Tries alternate country names if primary name doesn't have data.
    Returns DataFrame with years as rows, indicators as columns.
    """
    # Get list of names to try (primary name + alternates from mapping)
    names_to_try = [country]
    if country in COUNTRY_NAME_MAPPING:
        names_to_try = COUNTRY_NAME_MAPPING[country]

    # Try each name until we find one with data
    for name in names_to_try:
        country_data = panel[panel['country'] == name]
        if len(country_data) > 0:
            # Pivot: rows = year, columns = indicator_id, values = value
            wide = country_data.pivot_table(
                index='year',
                columns='indicator_id',
                values='value',
                aggfunc='mean'  # In case of duplicates
            )
            return wide

    return None


def compute_qol_composite(wide_data: pd.DataFrame) -> np.ndarray:
    """
    Compute QoL composite from outcome indicators.

    Uses fallback indicator IDs - tries each alternative until one is found.

    Returns: Array of QoL scores (one per year), list of components used
    """
    qol_components = []
    components_used = []

    for outcome in QOL_OUTCOMES:
        # Try each fallback indicator ID until one is found
        values = None
        for indicator_id in outcome['ids']:
            if indicator_id in wide_data.columns:
                values = wide_data[indicator_id].values.astype(float)
                # Skip if mostly NaN
                if np.sum(~np.isnan(values)) >= 5:
                    break
                values = None

        if values is None:
            continue

        # Normalize to [0, 1] using min-max scaling
        min_val = np.nanmin(values)
        max_val = np.nanmax(values)

        if max_val > min_val:
            normalized = (values - min_val) / (max_val - min_val)
        else:
            normalized = np.ones_like(values) * 0.5

        # Invert negative outcomes (higher is worse)
        if outcome['negative']:
            normalized = 1 - normalized

        qol_components.append(normalized)
        components_used.append(outcome['name'])

    if len(qol_components) < 2:
        return None, []

    # Mean across available outcomes
    qol = np.nanmean(qol_components, axis=0)

    return qol, components_used


def compute_shap_for_country(
    country: str,
    wide_data: pd.DataFrame,
    graph_indicators: set,
    n_estimators: int = 100,
    max_depth: int = 5
) -> dict:
    """
    Compute SHAP importance for one country.

    Args:
        country: Country name
        wide_data: Pivoted data (years × indicators)
        graph_indicators: Set of indicator IDs in country graph
        n_estimators: Number of trees in gradient boosting
        max_depth: Max tree depth

    Returns: Dict {indicator_id: importance_score}
    """
    # 1. Compute QoL target
    qol, components_used = compute_qol_composite(wide_data)

    if qol is None:
        return None, "Insufficient QoL outcomes"

    # 2. Filter to indicators in graph AND in data
    available_indicators = [
        ind for ind in graph_indicators
        if ind in wide_data.columns
    ]

    if len(available_indicators) < 20:
        return None, f"Only {len(available_indicators)} indicators available"

    # 3. Prepare features
    X = wide_data[available_indicators].copy()

    # Fill missing values with column median
    X = X.fillna(X.median())

    # Remove columns that are still all NaN
    valid_cols = X.columns[~X.isna().all()]
    X = X[valid_cols]
    available_indicators = list(valid_cols)

    if len(available_indicators) < 20:
        return None, f"Only {len(available_indicators)} valid indicators after NaN removal"

    # 4. Remove rows with NaN in target
    valid_idx = ~np.isnan(qol)
    X_clean = X[valid_idx]
    y_clean = qol[valid_idx]

    if len(X_clean) < 10:
        return None, f"Only {len(X_clean)} valid samples"

    # 5. Train gradient boosting model
    model = GradientBoostingRegressor(
        n_estimators=n_estimators,
        max_depth=max_depth,
        learning_rate=0.1,
        random_state=42,
        subsample=0.8
    )
    model.fit(X_clean, y_clean)

    # 6. Compute SHAP values
    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X_clean)

    # 7. Aggregate: mean absolute SHAP per indicator
    shap_importance = {}
    for i, indicator in enumerate(available_indicators):
        shap_importance[indicator] = float(np.mean(np.abs(shap_values[:, i])))

    # 8. Normalize: max = 1.0
    max_shap = max(shap_importance.values()) if shap_importance else 1.0
    if max_shap > 0:
        shap_importance = {
            k: v / max_shap
            for k, v in shap_importance.items()
        }

    return {
        'shap_importance': shap_importance,
        'qol_components': components_used,
        'n_samples': len(X_clean),
        'n_indicators': len(available_indicators)
    }, None


def save_country_shap(country: str, result: dict):
    """Save SHAP importance to JSON."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    output_path = OUTPUT_DIR / f"{country}_shap.json"

    shap_importance = result['shap_importance']

    output_data = {
        'country': country,
        'shap_importance': shap_importance,
        'metadata': {
            'n_indicators': result['n_indicators'],
            'n_samples': result['n_samples'],
            'qol_components': result['qol_components'],
            'mean_importance': float(np.mean(list(shap_importance.values()))),
            'max_importance': float(max(shap_importance.values())) if shap_importance else 0.0,
            'computation_date': datetime.now().isoformat()
        }
    }

    with open(output_path, 'w') as f:
        json.dump(output_data, f, indent=2)


def process_single_country(country: str, panel: pd.DataFrame, verbose: bool = True):
    """Process SHAP for a single country."""
    if verbose:
        print(f"\n  Processing {country}...")

    # Load country graph
    graph = load_country_graph(country)
    if graph is None:
        return {'status': 'error', 'message': 'No graph file'}

    graph_indicators = get_indicators_from_graph(graph)
    if len(graph_indicators) < 50:
        return {'status': 'error', 'message': f'Only {len(graph_indicators)} indicators in graph'}

    # Pivot country data
    wide_data = pivot_country_data(panel, country)
    if wide_data is None or len(wide_data) < 10:
        return {'status': 'error', 'message': 'Insufficient time series data'}

    # Compute SHAP
    result, error = compute_shap_for_country(country, wide_data, graph_indicators)

    if result is None:
        return {'status': 'error', 'message': error}

    # Save results
    save_country_shap(country, result)

    return {
        'status': 'success',
        'n_indicators': result['n_indicators'],
        'n_samples': result['n_samples'],
        'qol_components': len(result['qol_components'])
    }


def main(test_mode: bool = False, test_countries: list = None):
    """
    Compute SHAP for all countries.

    Args:
        test_mode: If True, only process a few countries for timing
        test_countries: List of specific countries to process
    """
    print("=" * 60)
    print("Phase A.4: Country-Specific SHAP Analysis")
    print("=" * 60)

    # Load panel data
    panel = load_panel_data()

    # Get country list from graph files
    graph_files = sorted(list(GRAPHS_DIR.glob('*.json')))
    countries = [f.stem for f in graph_files if f.stem != '_lag_checkpoint']

    print(f"\nFound {len(countries)} country graphs")

    # Filter countries if test mode
    if test_mode:
        if test_countries:
            countries = [c for c in test_countries if c in countries]
        else:
            countries = countries[:3]  # Default: first 3
        print(f"TEST MODE: Processing only {len(countries)} countries: {countries}")

    # Ensure output directory exists
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Process each country
    print("\nComputing SHAP for each country...")

    results = []
    errors = []

    start_time = datetime.now()

    for i, country in enumerate(tqdm(countries, desc="Countries")):
        country_start = datetime.now()

        result = process_single_country(country, panel, verbose=test_mode)

        country_duration = (datetime.now() - country_start).total_seconds()

        if result['status'] == 'success':
            results.append({
                'country': country,
                'n_indicators': result['n_indicators'],
                'n_samples': result['n_samples'],
                'qol_components': result['qol_components'],
                'duration_sec': country_duration
            })
            if test_mode:
                print(f"    ✓ {result['n_indicators']} indicators, {result['n_samples']} samples, {country_duration:.1f}s")
        else:
            errors.append({
                'country': country,
                'error': result['message']
            })
            if test_mode:
                print(f"    ✗ {result['message']}")

    total_duration = (datetime.now() - start_time).total_seconds()

    # Summary
    print(f"\n{'=' * 60}")
    print("SUMMARY")
    print(f"{'=' * 60}")
    print(f"Countries processed successfully: {len(results)} / {len(countries)}")
    print(f"Countries with errors: {len(errors)}")
    print(f"Total duration: {total_duration:.1f} seconds ({total_duration/60:.1f} minutes)")

    if results:
        avg_duration = np.mean([r['duration_sec'] for r in results])
        print(f"Average per country: {avg_duration:.1f} seconds")

        if test_mode:
            estimated_total = avg_duration * 205 / 60
            print(f"\nESTIMATED TOTAL RUNTIME: {estimated_total:.0f} minutes ({estimated_total/60:.1f} hours)")

    if errors and test_mode:
        print(f"\nErrors:")
        for e in errors:
            print(f"  - {e['country']}: {e['error']}")

    # Save summary
    summary_path = OUTPUT_DIR / 'computation_summary.json'
    summary = {
        'computation_date': datetime.now().isoformat(),
        'total_countries': len(countries),
        'successful': len(results),
        'failed': len(errors),
        'total_duration_sec': total_duration,
        'results': results,
        'errors': errors
    }

    with open(summary_path, 'w') as f:
        json.dump(summary, f, indent=2)

    print(f"\nOutput directory: {OUTPUT_DIR}")
    print(f"Summary saved to: {summary_path}")

    if not test_mode:
        print("\n✓ Phase A.4 complete!")

    return len(results), len(errors)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Compute country-specific SHAP importance')
    parser.add_argument('--test', action='store_true', help='Test mode: process only 3 countries')
    parser.add_argument('--countries', nargs='+', help='Specific countries to process')

    args = parser.parse_args()

    if args.test or args.countries:
        main(test_mode=True, test_countries=args.countries)
    else:
        main(test_mode=False)
