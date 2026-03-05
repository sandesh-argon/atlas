"""
Indicator Statistics for Proper Unit Conversion

Country-specific betas are standardized within each country's own time series:
    X_std = (X - X.mean()) / X.std()   # within-country temporal z-score
    y_std = (y - y.mean()) / y.std()
    beta = Ridge(X_std, y_std).coef_

To convert propagated effects back to raw units, we need the SAME std
that was used during estimation — the country's own temporal std:
    effect_raw = beta * (source_delta / source_temporal_std) * target_temporal_std

IMPORTANT: Do NOT use cross-country std for this conversion. Cross-country
std can be 1000-5000x larger than within-country temporal std (e.g., wealth
indicators: cross-country std=209M vs India temporal std=48K). Using
cross-country std amplifies effects by that ratio, causing explosions.
"""

import json
from pathlib import Path
from typing import Dict, Optional, Tuple
import pandas as pd
import numpy as np

DATA_ROOT = Path(__file__).parent.parent / "data"
PANEL_PATH = DATA_ROOT / "raw" / "v21_panel_data_for_v3.parquet"
STATS_CACHE_PATH = DATA_ROOT / "v31" / "indicator_stats.json"
COUNTRY_STATS_CACHE_DIR = DATA_ROOT / "v31" / "country_indicator_stats"
BASELINE_CACHE_DIR = DATA_ROOT / "v31" / "baselines"

# Module-level caches
_stats_cache: Optional[Dict[int, Dict[str, Dict[str, float]]]] = None
_country_stats_cache: Dict[str, Dict[str, Dict[str, float]]] = {}


def compute_indicator_stats(panel_path: Optional[Path] = None) -> Dict[int, Dict[str, Dict[str, float]]]:
    """
    Compute per-indicator, per-year statistics (mean, std) across all countries.

    Returns:
        {year: {indicator_id: {"mean": float, "std": float, "count": int}}}
    """
    path = panel_path or PANEL_PATH
    df = pd.read_parquet(path)

    grouped = df.groupby(["indicator_id", "year"])["value"].agg(["mean", "std", "count"])
    grouped = grouped.reset_index()

    result: Dict[int, Dict[str, Dict[str, float]]] = {}
    for _, row in grouped.iterrows():
        year = int(row["year"])
        ind = row["indicator_id"]
        if year not in result:
            result[year] = {}
        std_val = float(row["std"]) if pd.notna(row["std"]) else 0.0
        result[year][ind] = {
            "mean": float(row["mean"]) if pd.notna(row["mean"]) else 0.0,
            "std": std_val if std_val > 0 else 1e-8,
            "count": int(row["count"]),
        }

    return result


def save_stats_cache(stats: Dict[int, Dict[str, Dict[str, float]]], cache_path: Optional[Path] = None) -> None:
    """Save stats to JSON cache for fast loading."""
    path = cache_path or STATS_CACHE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    # Convert int keys to str for JSON
    serializable = {str(year): indicators for year, indicators in stats.items()}
    with open(path, "w") as f:
        json.dump(serializable, f)
    print(f"Saved indicator stats to {path} ({path.stat().st_size / 1024 / 1024:.1f} MB)")


def load_stats_cache(cache_path: Optional[Path] = None) -> Optional[Dict[int, Dict[str, Dict[str, float]]]]:
    """Load stats from JSON cache."""
    path = cache_path or STATS_CACHE_PATH
    if not path.exists():
        return None
    with open(path) as f:
        data = json.load(f)
    # Convert str keys back to int
    return {int(year): indicators for year, indicators in data.items()}


def get_indicator_stats(year: int, panel_path: Optional[Path] = None) -> Dict[str, Dict[str, float]]:
    """
    Get indicator statistics for a given year. Uses cache.

    Returns:
        {indicator_id: {"mean": float, "std": float, "count": int}}
    """
    global _stats_cache
    if _stats_cache is None:
        _stats_cache = load_stats_cache()
        if _stats_cache is None:
            print("Computing indicator stats from panel data (first time)...")
            _stats_cache = compute_indicator_stats(panel_path)
            save_stats_cache(_stats_cache)

    return _stats_cache.get(year, {})


def get_indicator_std(indicator: str, year: int) -> float:
    """Get standard deviation for an indicator in a given year."""
    stats = get_indicator_stats(year)
    ind_stats = stats.get(indicator)
    if ind_stats is None:
        return 1e-8  # Fallback: will effectively pass through raw beta
    return ind_stats.get("std", 1e-8)


def get_indicator_stds_pair(source: str, target: str, year: int) -> Tuple[float, float]:
    """Get (source_std, target_std) for unit conversion in propagation."""
    stats = get_indicator_stats(year)
    s = stats.get(source, {}).get("std", 1e-8)
    t = stats.get(target, {}).get("std", 1e-8)
    return s, t


def compute_country_temporal_stats(
    country: str,
    panel_path: Optional[Path] = None
) -> Dict[str, Dict[str, float]]:
    """
    Compute per-indicator temporal statistics for a single country.

    This is the std that matches how betas were estimated: Ridge regression
    on within-country z-scored time series. Each indicator's std is computed
    over that country's ~35 years of data (1990-2024).

    Returns:
        {indicator_id: {"mean": float, "std": float, "count": int}}
    """
    path = panel_path or PANEL_PATH
    df = pd.read_parquet(path)

    country_data = df[df['country'] == country]
    if country_data.empty:
        # Try case-insensitive
        country_lower = country.lower()
        country_data = df[df['country'].str.lower() == country_lower]

    if country_data.empty:
        return {}

    grouped = country_data.groupby('indicator_id')['value'].agg(['mean', 'std', 'count'])

    result: Dict[str, Dict[str, float]] = {}
    for ind, row in grouped.iterrows():
        std_val = float(row['std']) if pd.notna(row['std']) else 0.0
        result[str(ind)] = {
            'mean': float(row['mean']) if pd.notna(row['mean']) else 0.0,
            'std': std_val if std_val > 0 else 0.0,
            'count': int(row['count']),
        }

    return result


def compute_country_temporal_stats_from_baselines(
    country: str,
    baseline_dir: Optional[Path] = None,
) -> Dict[str, Dict[str, float]]:
    """
    Compute per-indicator temporal stats from cached yearly baseline JSON files.

    This fallback avoids parquet runtime dependencies and preserves calibration
    for absolute-mode propagation when panel loading is unavailable.
    """
    base_dir = baseline_dir or BASELINE_CACHE_DIR
    country_dir = base_dir / country
    if not country_dir.exists():
        return {}

    series_by_indicator: Dict[str, list] = {}
    for year_file in sorted(country_dir.glob("*.json")):
        try:
            with open(year_file) as f:
                payload = json.load(f)
            values = payload.get("values", {})
        except (json.JSONDecodeError, OSError):
            continue

        if not isinstance(values, dict):
            continue
        for indicator, value in values.items():
            if value is None:
                continue
            try:
                series_by_indicator.setdefault(str(indicator), []).append(float(value))
            except (TypeError, ValueError):
                continue

    result: Dict[str, Dict[str, float]] = {}
    for indicator, values in series_by_indicator.items():
        if not values:
            continue
        arr = np.array(values, dtype=float)
        result[indicator] = {
            "mean": float(np.mean(arr)),
            "std": float(np.std(arr, ddof=1)) if len(arr) > 1 else 0.0,
            "count": int(len(arr)),
        }
    return result


def save_country_stats_cache(
    country: str,
    stats: Dict[str, Dict[str, float]],
    cache_dir: Optional[Path] = None
) -> None:
    """Save per-country temporal stats to JSON cache."""
    base_dir = cache_dir or COUNTRY_STATS_CACHE_DIR
    base_dir.mkdir(parents=True, exist_ok=True)
    path = base_dir / f"{country}.json"
    with open(path, 'w') as f:
        json.dump(stats, f)


def load_country_stats_cache(
    country: str,
    cache_dir: Optional[Path] = None
) -> Optional[Dict[str, Dict[str, float]]]:
    """Load per-country temporal stats from cache."""
    base_dir = cache_dir or COUNTRY_STATS_CACHE_DIR
    path = base_dir / f"{country}.json"
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)


def get_country_indicator_stats(
    country: str,
    panel_path: Optional[Path] = None
) -> Dict[str, Dict[str, float]]:
    """
    Get per-indicator temporal std for a specific country.

    This is the correct std for unit conversion with country-specific betas.
    Uses file cache + memory cache for performance.

    Returns:
        {indicator_id: {"mean": float, "std": float, "count": int}}
    """
    global _country_stats_cache

    if country in _country_stats_cache:
        return _country_stats_cache[country]

    # Try file cache
    stats = load_country_stats_cache(country)
    if stats is None:
        # Compute from panel data; fallback to baseline JSON cache if parquet
        # dependencies are unavailable in lightweight runtime environments.
        try:
            stats = compute_country_temporal_stats(country, panel_path)
        except Exception:
            stats = {}
        if not stats:
            stats = compute_country_temporal_stats_from_baselines(country)
        if stats:
            save_country_stats_cache(country, stats)

    _country_stats_cache[country] = stats
    return stats


STRATUM_STATS_CACHE_DIR = DATA_ROOT / "v31" / "stratum_indicator_stats"
_stratum_stats_cache: Dict[str, Dict[str, Dict[str, float]]] = {}


def compute_stratum_temporal_stats(
    stratum: str,
    panel_path: Optional[Path] = None
) -> Dict[str, Dict[str, float]]:
    """
    Compute per-indicator temporal statistics for a stratum (developing/emerging/advanced)
    or for 'unified' (all countries).

    Pools all within-country temporal data for countries in that stratum,
    then computes the median temporal std across countries. This gives a
    representative temporal variability scale for the stratum.

    For unit conversion: the stratum temporal std replaces country temporal std
    when simulating at stratum level (no single country context).

    Returns:
        {indicator_id: {"mean": float, "std": float, "count": int}}
    """
    path = panel_path or PANEL_PATH
    df = pd.read_parquet(path)

    if stratum == 'unified':
        # Use all countries in the panel
        countries = sorted(df['country'].unique().tolist())
    else:
        from .income_classifier import get_countries_in_stratum
        # Use 2020 membership as representative (covers most countries)
        countries = get_countries_in_stratum(stratum, 2020)

    if not countries:
        return {}

    stratum_data = df[df['country'].isin(countries)]
    if stratum_data.empty:
        return {}

    # Compute per-country temporal stats, then take median across countries
    per_country_stats: Dict[str, list] = {}  # indicator -> [std1, std2, ...]
    per_country_means: Dict[str, list] = {}

    for country in countries:
        cdata = stratum_data[stratum_data['country'] == country]
        if cdata.empty:
            continue
        grouped = cdata.groupby('indicator_id')['value'].agg(['mean', 'std', 'count'])
        for ind, row in grouped.iterrows():
            ind_str = str(ind)
            std_val = float(row['std']) if pd.notna(row['std']) and row['std'] > 0 else None
            mean_val = float(row['mean']) if pd.notna(row['mean']) else None
            if std_val is not None:
                per_country_stats.setdefault(ind_str, []).append(std_val)
            if mean_val is not None:
                per_country_means.setdefault(ind_str, []).append(mean_val)

    result: Dict[str, Dict[str, float]] = {}
    for ind in per_country_stats:
        stds = per_country_stats[ind]
        means = per_country_means.get(ind, [])
        if len(stds) >= 3:  # Require at least 3 countries
            result[ind] = {
                'mean': float(np.median(means)) if means else 0.0,
                'std': float(np.median(stds)),
                'count': len(stds),
            }

    return result


def save_stratum_stats_cache(
    stratum: str,
    stats: Dict[str, Dict[str, float]],
    cache_dir: Optional[Path] = None
) -> None:
    """Save per-stratum temporal stats to JSON cache."""
    base_dir = cache_dir or STRATUM_STATS_CACHE_DIR
    base_dir.mkdir(parents=True, exist_ok=True)
    path = base_dir / f"{stratum}.json"
    with open(path, 'w') as f:
        json.dump(stats, f)
    print(f"Saved {stratum} stats to {path} ({path.stat().st_size / 1024:.1f} KB)")


def load_stratum_stats_cache(
    stratum: str,
    cache_dir: Optional[Path] = None
) -> Optional[Dict[str, Dict[str, float]]]:
    """Load per-stratum temporal stats from cache."""
    base_dir = cache_dir or STRATUM_STATS_CACHE_DIR
    path = base_dir / f"{stratum}.json"
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)


def get_stratum_indicator_stats(
    stratum: str,
    panel_path: Optional[Path] = None
) -> Dict[str, Dict[str, float]]:
    """
    Get per-indicator temporal std for a stratum.

    Median temporal std across countries in the stratum — represents
    typical within-country variability for that income group.
    Uses file cache + memory cache for performance.

    Returns:
        {indicator_id: {"mean": float, "std": float, "count": int}}
    """
    global _stratum_stats_cache

    if stratum in _stratum_stats_cache:
        return _stratum_stats_cache[stratum]

    stats = load_stratum_stats_cache(stratum)
    if stats is None:
        print(f"Computing temporal stats for stratum '{stratum}' (first time)...")
        stats = compute_stratum_temporal_stats(stratum, panel_path)
        if stats:
            save_stratum_stats_cache(stratum, stats)

    _stratum_stats_cache[stratum] = stats
    return stats


REGIONAL_STATS_CACHE_DIR = DATA_ROOT / "v31" / "regional_indicator_stats"
_regional_stats_cache: Dict[str, Dict[str, Dict[str, float]]] = {}


def compute_regional_temporal_stats(
    region: str,
    panel_path: Optional[Path] = None
) -> Dict[str, Dict[str, float]]:
    """
    Compute per-indicator temporal stats for a region.

    Uses median of country-level temporal std across member countries,
    mirroring stratum-level aggregation but with region membership.
    """
    from .region_mapping import get_countries_in_region

    countries = get_countries_in_region(region)
    if not countries:
        return {}

    min_countries_per_indicator = 2 if len(countries) <= 2 else 3

    per_country_stats: Dict[str, list] = {}
    per_country_means: Dict[str, list] = {}

    for country in countries:
        c_stats = load_country_stats_cache(country)
        if c_stats is None:
            try:
                c_stats = get_country_indicator_stats(country, panel_path=panel_path)
            except Exception:
                # In lightweight runtime environments parquet engines may be absent.
                # Skip this country instead of failing the entire region.
                c_stats = {}
        if not c_stats:
            continue
        for ind, stat in c_stats.items():
            std_val = float(stat.get('std', 0.0) or 0.0)
            mean_val = stat.get('mean')
            if std_val > 0:
                per_country_stats.setdefault(ind, []).append(std_val)
            if mean_val is not None:
                per_country_means.setdefault(ind, []).append(float(mean_val))

    result: Dict[str, Dict[str, float]] = {}
    for ind, stds in per_country_stats.items():
        if len(stds) < min_countries_per_indicator:
            continue
        means = per_country_means.get(ind, [])
        result[ind] = {
            'mean': float(np.median(means)) if means else 0.0,
            'std': float(np.median(stds)),
            'count': len(stds),
        }

    return result


def save_regional_stats_cache(
    region: str,
    stats: Dict[str, Dict[str, float]],
    cache_dir: Optional[Path] = None
) -> None:
    """Save per-region temporal stats cache."""
    base_dir = cache_dir or REGIONAL_STATS_CACHE_DIR
    base_dir.mkdir(parents=True, exist_ok=True)
    path = base_dir / f"{region}.json"
    with open(path, 'w') as f:
        json.dump(stats, f)


def load_regional_stats_cache(
    region: str,
    cache_dir: Optional[Path] = None
) -> Optional[Dict[str, Dict[str, float]]]:
    """Load per-region temporal stats cache."""
    base_dir = cache_dir or REGIONAL_STATS_CACHE_DIR
    path = base_dir / f"{region}.json"
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)


def get_regional_indicator_stats(
    region: str,
    panel_path: Optional[Path] = None
) -> Dict[str, Dict[str, float]]:
    """
    Get per-indicator temporal std for a region with file+memory caching.
    """
    global _regional_stats_cache

    if region in _regional_stats_cache:
        return _regional_stats_cache[region]

    stats = load_regional_stats_cache(region)
    if stats is None:
        print(f"Computing temporal stats for region '{region}' (first time)...")
        stats = compute_regional_temporal_stats(region, panel_path)
        if stats:
            save_regional_stats_cache(region, stats)

    _regional_stats_cache[region] = stats
    return stats


def get_country_indicator_std(country: str, indicator: str) -> float:
    """
    Get temporal std for an indicator within a specific country.

    Falls back to baseline value as scale proxy if no temporal data.
    """
    stats = get_country_indicator_stats(country)
    ind_stats = stats.get(indicator)
    if ind_stats is None or ind_stats.get('std', 0) == 0:
        return 0.0  # Caller should handle fallback
    return ind_stats['std']


# CLI: precompute and cache
if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == '--country':
        # Precompute for specific countries or all
        if len(sys.argv) > 2:
            countries = sys.argv[2:]
        else:
            df = pd.read_parquet(PANEL_PATH)
            countries = sorted(df['country'].unique())

        print(f"Computing temporal stats for {len(countries)} countries...")
        for i, country in enumerate(countries):
            stats = compute_country_temporal_stats(country)
            save_country_stats_cache(country, stats)
            if (i + 1) % 20 == 0:
                print(f"  {i+1}/{len(countries)}")
        print("Done.")
    else:
        print("Computing cross-country indicator statistics...")
        stats = compute_indicator_stats()
        save_stats_cache(stats)
        years = sorted(stats.keys())
        print(f"Years: {years[0]}-{years[-1]}")
        print(f"Indicators per year: ~{np.mean([len(v) for v in stats.values()]):.0f}")
