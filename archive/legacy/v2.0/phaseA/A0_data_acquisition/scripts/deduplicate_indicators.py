#!/usr/bin/env python3
"""
Indicator Deduplication Script
===============================
Identifies and removes highly correlated duplicate indicators (r > 0.95).

Keeps the indicator with:
1. Longest temporal span
2. Lowest missingness
3. Best data quality

Runtime: ~30-60 minutes for 41,050 indicators
"""

import pandas as pd
import numpy as np
from pathlib import Path
import json
from datetime import datetime
from collections import defaultdict
import warnings
warnings.filterwarnings('ignore')

# Paths
BASE_DIR = Path(__file__).parent.parent
STANDARDIZED_DIR = BASE_DIR / "raw_data_standardized"
LOG_FILE = BASE_DIR / "validation_logs" / f"deduplication_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

# Deduplication parameters
CORRELATION_THRESHOLD = 0.95
MIN_OVERLAP_COUNTRIES = 20  # Require 20+ overlapping countries for comparison


def load_indicator(file_path):
    """
    Load single indicator CSV

    Returns:
        DataFrame with Country, Year, Value
    """
    try:
        df = pd.read_csv(file_path)
        if 'Country' in df.columns and 'Year' in df.columns and 'Value' in df.columns:
            return df[['Country', 'Year', 'Value']].dropna()
        return None
    except Exception:
        return None


def calculate_indicator_quality(df):
    """
    Calculate quality metrics for an indicator

    Returns:
        dict with temporal_span, missingness, coverage, row_count
    """
    if df is None or len(df) == 0:
        return {
            'temporal_span': 0,
            'temporal_start': None,
            'temporal_end': None,
            'country_count': 0,
            'row_count': 0,
            'avg_years_per_country': 0
        }

    temporal_span = df['Year'].max() - df['Year'].min()
    country_count = df['Country'].nunique()
    avg_years_per_country = len(df) / country_count if country_count > 0 else 0

    return {
        'temporal_span': temporal_span,
        'temporal_start': int(df['Year'].min()),
        'temporal_end': int(df['Year'].max()),
        'country_count': country_count,
        'row_count': len(df),
        'avg_years_per_country': avg_years_per_country
    }


def calculate_correlation(df1, df2):
    """
    Calculate Pearson correlation between two indicators

    Merges on Country-Year pairs and computes correlation.

    Returns:
        float: Correlation coefficient (or None if insufficient overlap)
    """
    if df1 is None or df2 is None:
        return None

    # Merge on Country-Year
    merged = pd.merge(df1, df2, on=['Country', 'Year'], suffixes=('_1', '_2'))

    if len(merged) < MIN_OVERLAP_COUNTRIES:
        return None  # Insufficient overlap

    # Calculate correlation
    try:
        corr = merged['Value_1'].corr(merged['Value_2'])
        return corr if not np.isnan(corr) else None
    except Exception:
        return None


def select_best_indicator(indicators):
    """
    Select best indicator from a group of highly correlated indicators

    Priority:
    1. Longest temporal span
    2. Most countries covered
    3. Highest row count (lowest missingness proxy)

    Args:
        indicators: list of dicts with 'file', 'quality', 'df'

    Returns:
        dict: Best indicator
    """
    # Sort by quality (temporal_span desc, country_count desc, row_count desc)
    sorted_indicators = sorted(
        indicators,
        key=lambda x: (
            x['quality']['temporal_span'],
            x['quality']['country_count'],
            x['quality']['row_count']
        ),
        reverse=True
    )

    return sorted_indicators[0]


def find_name_based_duplicates():
    """
    Quick pass: identify potential duplicates by name patterns

    Returns:
        dict: {pattern: [file_paths]}
    """
    print("\n🔍 Phase 1: Name-based duplicate detection...")

    all_files = list(STANDARDIZED_DIR.rglob("*.csv"))
    print(f"Scanning {len(all_files):,} files...")

    # Known duplicate patterns
    patterns = {
        'inflation': [],
        'cpi': [],
        'unemployment': [],
        'gdp': [],
        'life_expectancy': [],
        'mortality': []
    }

    for file in all_files:
        filename_lower = file.stem.lower()
        for pattern in patterns.keys():
            if pattern in filename_lower:
                patterns[pattern].append(file)

    # Filter to patterns with 2+ files
    duplicates = {k: v for k, v in patterns.items() if len(v) >= 2}

    print(f"Found {len(duplicates)} potential duplicate patterns:")
    for pattern, files in duplicates.items():
        print(f"  - {pattern}: {len(files)} files")

    return duplicates


def deduplicate_group(files, pattern_name):
    """
    Deduplicate a group of similar indicators using correlation

    Args:
        files: list of file paths
        pattern_name: name of the pattern (for logging)

    Returns:
        dict with kept/removed files and correlation matrix
    """
    print(f"\n🔄 Processing '{pattern_name}' group ({len(files)} files)...")

    # Load all indicators
    indicators = []
    for file in files:
        df = load_indicator(file)
        quality = calculate_indicator_quality(df)
        indicators.append({
            'file': file,
            'filename': file.name,
            'df': df,
            'quality': quality
        })

    # Calculate pairwise correlations
    n = len(indicators)
    corr_matrix = {}

    for i in range(n):
        for j in range(i + 1, n):
            corr = calculate_correlation(indicators[i]['df'], indicators[j]['df'])
            if corr is not None and corr >= CORRELATION_THRESHOLD:
                pair = (indicators[i]['filename'], indicators[j]['filename'])
                corr_matrix[pair] = corr

    if len(corr_matrix) == 0:
        print(f"  ✅ No high correlations found (r < {CORRELATION_THRESHOLD})")
        return {'kept': [ind['file'] for ind in indicators], 'removed': [], 'correlations': {}}

    print(f"  ⚠️  Found {len(corr_matrix)} high-correlation pairs (r ≥ {CORRELATION_THRESHOLD})")

    # Build duplicate clusters (connected components)
    clusters = []
    processed = set()

    for (file1, file2), corr in corr_matrix.items():
        # Find which cluster this belongs to
        found_cluster = None
        for cluster in clusters:
            if file1 in cluster or file2 in cluster:
                found_cluster = cluster
                break

        if found_cluster:
            found_cluster.add(file1)
            found_cluster.add(file2)
        else:
            clusters.append({file1, file2})

    # Select best indicator from each cluster
    removed_files = []
    kept_files = []

    for cluster in clusters:
        cluster_indicators = [ind for ind in indicators if ind['filename'] in cluster]
        best = select_best_indicator(cluster_indicators)

        for ind in cluster_indicators:
            if ind['file'] == best['file']:
                kept_files.append(ind['file'])
                print(f"  ✅ KEEP: {ind['filename']}")
                print(f"      Span: {ind['quality']['temporal_start']}-{ind['quality']['temporal_end']} "
                      f"({ind['quality']['temporal_span']} years), "
                      f"{ind['quality']['country_count']} countries, "
                      f"{ind['quality']['row_count']:,} rows")
            else:
                removed_files.append(ind['file'])
                print(f"  ❌ REMOVE: {ind['filename']}")
                print(f"      Span: {ind['quality']['temporal_start']}-{ind['quality']['temporal_end']} "
                      f"({ind['quality']['temporal_span']} years), "
                      f"{ind['quality']['country_count']} countries, "
                      f"{ind['quality']['row_count']:,} rows")

    # Add non-duplicate files to kept
    all_cluster_files = set().union(*clusters)
    for ind in indicators:
        if ind['filename'] not in all_cluster_files:
            kept_files.append(ind['file'])

    return {
        'kept': kept_files,
        'removed': removed_files,
        'correlations': {str(k): v for k, v in corr_matrix.items()}
    }


def main():
    print("="*80)
    print("INDICATOR DEDUPLICATION")
    print("="*80)
    print(f"Correlation threshold: {CORRELATION_THRESHOLD}")
    print(f"Min overlap countries: {MIN_OVERLAP_COUNTRIES}")

    # Phase 1: Name-based detection
    duplicate_patterns = find_name_based_duplicates()

    if len(duplicate_patterns) == 0:
        print("\n✅ No potential duplicates found by name")
        return {'total_removed': 0, 'patterns': {}}

    # Phase 2: Correlation-based deduplication
    print("\n🔬 Phase 2: Correlation-based deduplication...")

    results = {}
    total_removed = 0

    for pattern, files in duplicate_patterns.items():
        result = deduplicate_group(files, pattern)
        results[pattern] = result

        # Delete removed files
        for file in result['removed']:
            if file.exists():
                file.unlink()
                total_removed += 1

    # Summary
    print("\n" + "="*80)
    print("DEDUPLICATION COMPLETE")
    print("="*80)
    print(f"✅ Total indicators removed: {total_removed}")

    # Save log
    log_data = {
        'timestamp': datetime.now().isoformat(),
        'correlation_threshold': CORRELATION_THRESHOLD,
        'min_overlap_countries': MIN_OVERLAP_COUNTRIES,
        'total_removed': total_removed,
        'patterns_processed': len(duplicate_patterns),
        'results': {
            pattern: {
                'kept_count': len(result['kept']),
                'removed_count': len(result['removed']),
                'correlations': result['correlations']
            }
            for pattern, result in results.items()
        }
    }

    with open(LOG_FILE, 'w') as f:
        json.dump(log_data, f, indent=2)

    print(f"\n📝 Log saved to: {LOG_FILE.relative_to(BASE_DIR)}")

    return log_data


if __name__ == "__main__":
    import sys
    result = main()
    sys.exit(0)
