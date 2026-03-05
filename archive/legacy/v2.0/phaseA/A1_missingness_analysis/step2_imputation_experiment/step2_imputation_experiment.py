#!/usr/bin/env python3
"""
A1 Step 2: Imputation Sensitivity Experiment
============================================
Tests 25 configurations (5 methods × 5 thresholds) to find optimal imputation strategy.

Imputation Methods:
1. MICE (Multivariate Imputation by Chained Equations)
2. KNN (K-Nearest Neighbors)
3. Linear Interpolation (temporal)
4. Forward Fill (temporal)
5. Random Forest

Missingness Thresholds:
- Keep indicators with ≤ 30%, 40%, 50%, 60%, 70% missing data

Evaluation Criteria:
- Edge Retention (50% weight): % of edges preserved after imputation
- Predictive Quality (35% weight): Mean R² from cross-validation
- Runtime (15% weight): Time to impute (normalized, inverted)

Expected runtime: 3-5 hours on current machine (85% utilization)
"""

import pandas as pd
import numpy as np
from pathlib import Path
import json
from datetime import datetime
from tqdm import tqdm
import warnings
warnings.filterwarnings('ignore')

from sklearn.experimental import enable_iterative_imputer
from sklearn.impute import IterativeImputer, KNNImputer
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import cross_val_score
from joblib import Parallel, delayed
import time

# Paths
BASE_DIR = Path(__file__).parent
FILTERED_DATA = BASE_DIR / "filtered_data"
OUTPUT_DIR = BASE_DIR / "imputation_results"
OUTPUT_DIR.mkdir(exist_ok=True)

# Experimental design
IMPUTATION_METHODS = ['mice', 'knn', 'linear_interp', 'forward_fill', 'random_forest']
MISSING_THRESHOLDS = [0.30, 0.40, 0.50, 0.60, 0.70]

# Sample size for experiment (to speed up testing)
SAMPLE_INDICATORS = 100  # Test on 100 indicators to evaluate methods (faster)

# Evaluation weights
WEIGHTS = {
    'edge_retention': 0.50,
    'r2_quality': 0.35,
    'runtime': 0.15,
}


def load_sample_indicators(n_samples=200):
    """Load a stratified sample of indicators for testing"""
    print(f"Loading {n_samples} sample indicators for testing...")

    all_files = list(FILTERED_DATA.rglob("*.csv"))

    # Stratified sampling by source
    sources = {}
    for f in all_files:
        source = f.parent.name
        if source not in sources:
            sources[source] = []
        sources[source].append(f)

    # Sample proportionally from each source
    sample_files = []
    total_files = len(all_files)

    for source, files in sources.items():
        n_from_source = max(1, int(len(files) / total_files * n_samples))
        sample_files.extend(np.random.choice(files, min(n_from_source, len(files)), replace=False))

    # Load all sampled indicators
    indicators_data = {}

    for csv_file in tqdm(sample_files[:n_samples], desc="Loading samples"):
        try:
            df = pd.read_csv(csv_file)
            if list(df.columns) == ['Country', 'Year', 'Value']:
                # Pivot to wide format (countries × years)
                pivot = df.pivot(index='Country', columns='Year', values='Value')
                indicators_data[csv_file.stem] = pivot
        except Exception:
            continue

    print(f"✅ Loaded {len(indicators_data)} indicators")
    return indicators_data


def compute_baseline_edges(indicators_data, threshold=0.15):
    """Compute baseline edges from raw data (for edge retention metric)"""
    # Simple correlation-based edges
    # In reality, A2 will use Granger causality, but this is a proxy

    # Convert to single dataframe
    all_data = pd.DataFrame()
    for name, data in indicators_data.items():
        # Take temporal mean for each country
        all_data[name] = data.mean(axis=1)

    # Drop rows with all NaN
    all_data = all_data.dropna(how='all')

    # Compute correlations
    corr_matrix = all_data.corr()

    # Count significant edges (|r| > threshold)
    edges = (corr_matrix.abs() > threshold) & (corr_matrix.abs() < 1.0)
    n_edges = edges.sum().sum() // 2  # Divide by 2 for undirected

    return n_edges


def impute_mice(data, max_iter=10):
    """MICE imputation"""
    imputer = IterativeImputer(max_iter=max_iter, random_state=42, verbose=0)
    imputed = imputer.fit_transform(data)
    return pd.DataFrame(imputed, index=data.index, columns=data.columns)


def impute_knn(data, n_neighbors=5):
    """KNN imputation"""
    imputer = KNNImputer(n_neighbors=n_neighbors)
    imputed = imputer.fit_transform(data)
    return pd.DataFrame(imputed, index=data.index, columns=data.columns)


def impute_linear_interp(data):
    """Linear interpolation (temporal)"""
    # Interpolate along time axis (columns)
    return data.interpolate(axis=1, method='linear', limit_direction='both')


def impute_forward_fill(data):
    """Forward fill (temporal)"""
    return data.fillna(method='ffill', axis=1).fillna(method='bfill', axis=1)


def impute_random_forest(data):
    """Random Forest imputation"""
    imputer = IterativeImputer(
        estimator=RandomForestRegressor(n_estimators=10, random_state=42, max_depth=5),
        max_iter=10,
        random_state=42,
        verbose=0
    )
    imputed = imputer.fit_transform(data)
    return pd.DataFrame(imputed, index=data.index, columns=data.columns)


def apply_imputation_method(method, data):
    """Apply specified imputation method"""
    if method == 'mice':
        return impute_mice(data)
    elif method == 'knn':
        return impute_knn(data)
    elif method == 'linear_interp':
        return impute_linear_interp(data)
    elif method == 'forward_fill':
        return impute_forward_fill(data)
    elif method == 'random_forest':
        return impute_random_forest(data)
    else:
        raise ValueError(f"Unknown method: {method}")


def evaluate_configuration(method, threshold, indicators_data, baseline_edges, progress_file):
    """Evaluate a single configuration"""

    start_time = time.time()

    # Write progress
    with open(progress_file, 'a') as f:
        f.write(f"STARTED: {method} @ {threshold:.0%}\n")
        f.flush()

    # Filter indicators by missingness threshold
    filtered_data = {}
    for name, data in indicators_data.items():
        missing_rate = data.isna().mean().mean()
        if missing_rate <= threshold:
            filtered_data[name] = data

    n_indicators_kept = len(filtered_data)

    if n_indicators_kept < 10:
        # Too few indicators, skip
        return {
            'method': method,
            'threshold': threshold,
            'n_indicators': n_indicators_kept,
            'edge_retention': 0.0,
            'mean_r2': 0.0,
            'runtime_seconds': 0.0,
            'composite_score': 0.0,
            'status': 'skipped_too_few_indicators'
        }

    # Apply imputation to each indicator
    imputed_data = {}
    imputation_times = []

    for name, data in filtered_data.items():
        try:
            imp_start = time.time()
            imputed = apply_imputation_method(method, data)
            imputed_data[name] = imputed
            imputation_times.append(time.time() - imp_start)
        except Exception as e:
            # If imputation fails, skip this indicator
            continue

    if len(imputed_data) < 10:
        return {
            'method': method,
            'threshold': threshold,
            'n_indicators': len(imputed_data),
            'edge_retention': 0.0,
            'mean_r2': 0.0,
            'runtime_seconds': 0.0,
            'composite_score': 0.0,
            'status': 'failed_imputation'
        }

    # Compute edge retention
    all_imputed = pd.DataFrame()
    for name, data in imputed_data.items():
        all_imputed[name] = data.mean(axis=1)

    all_imputed = all_imputed.dropna(how='all')
    corr_matrix = all_imputed.corr()
    edges = (corr_matrix.abs() > 0.15) & (corr_matrix.abs() < 1.0)
    n_edges_after = edges.sum().sum() // 2

    edge_retention = n_edges_after / baseline_edges if baseline_edges > 0 else 0.0

    # Compute predictive quality (R² from cross-validation)
    # Use a subset of indicators to predict each other
    r2_scores = []
    sample_size = min(20, len(imputed_data))
    sample_indicators = np.random.choice(list(imputed_data.keys()), sample_size, replace=False)

    for target_name in sample_indicators[:5]:  # Test 5 targets
        target_data = imputed_data[target_name].mean(axis=1).values

        # Features: other indicators
        feature_names = [n for n in sample_indicators if n != target_name][:10]
        features = pd.DataFrame({n: imputed_data[n].mean(axis=1) for n in feature_names})

        # Align data
        common_idx = features.index.intersection(pd.Index(range(len(target_data))))
        if len(common_idx) < 20:
            continue

        X = features.loc[common_idx].values
        y = target_data[common_idx]

        # Cross-validation
        try:
            rf = RandomForestRegressor(n_estimators=10, random_state=42, max_depth=5)
            scores = cross_val_score(rf, X, y, cv=3, scoring='r2')
            r2_scores.append(scores.mean())
        except Exception:
            continue

    mean_r2 = np.mean(r2_scores) if r2_scores else 0.0

    # Runtime
    runtime_seconds = time.time() - start_time

    # Composite score
    # Normalize runtime (lower is better, so invert)
    runtime_normalized = 1.0 / (1.0 + runtime_seconds / 60.0)  # Normalize by minutes

    composite_score = (
        WEIGHTS['edge_retention'] * edge_retention +
        WEIGHTS['r2_quality'] * max(0.0, mean_r2) +
        WEIGHTS['runtime'] * runtime_normalized
    )

    # Write completion progress
    with open(progress_file, 'a') as f:
        f.write(f"COMPLETED: {method} @ {threshold:.0%} | Score: {composite_score:.3f} | Time: {runtime_seconds:.1f}s\n")
        f.flush()

    return {
        'method': method,
        'threshold': threshold,
        'n_indicators': len(imputed_data),
        'edge_retention': edge_retention,
        'mean_r2': mean_r2,
        'runtime_seconds': runtime_seconds,
        'composite_score': composite_score,
        'status': 'success'
    }


def main():
    print("=" * 80)
    print("A1 STEP 2: IMPUTATION SENSITIVITY EXPERIMENT")
    print("=" * 80)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    print("EXPERIMENTAL DESIGN:")
    print(f"  Imputation methods: {len(IMPUTATION_METHODS)}")
    print(f"    - {', '.join(IMPUTATION_METHODS)}")
    print(f"  Missingness thresholds: {len(MISSING_THRESHOLDS)}")
    print(f"    - {', '.join([f'{t:.0%}' for t in MISSING_THRESHOLDS])}")
    print(f"  Total configurations: {len(IMPUTATION_METHODS) * len(MISSING_THRESHOLDS)}")
    print()

    print("EVALUATION CRITERIA:")
    print(f"  Edge Retention: {WEIGHTS['edge_retention']:.0%} weight")
    print(f"  R² Quality: {WEIGHTS['r2_quality']:.0%} weight")
    print(f"  Runtime: {WEIGHTS['runtime']:.0%} weight")
    print()

    # Load sample data
    np.random.seed(42)
    indicators_data = load_sample_indicators(n_samples=SAMPLE_INDICATORS)
    print()

    # Compute baseline edges
    print("Computing baseline edges...")
    baseline_edges = compute_baseline_edges(indicators_data)
    print(f"✅ Baseline edges: {baseline_edges:,}")
    print()

    # Generate all configurations
    configs = []
    for method in IMPUTATION_METHODS:
        for threshold in MISSING_THRESHOLDS:
            configs.append((method, threshold))

    print(f"Running {len(configs)} configurations...")
    print(f"Estimated time: {len(configs) * 2} - {len(configs) * 5} minutes")
    print()

    # Create progress file
    progress_file = BASE_DIR / "imputation_progress.log"
    progress_file.write_text(f"STARTED: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\nTOTAL: {len(configs)} configurations\n\n")

    print(f"✅ Progress tracking: {progress_file}")
    print(f"✅ Monitor with: tail -f imputation_progress.log")
    print()

    # Run configurations in parallel (use 22 cores for 92% utilization of 24 cores)
    results = Parallel(n_jobs=22, verbose=0)(
        delayed(evaluate_configuration)(method, threshold, indicators_data, baseline_edges, progress_file)
        for method, threshold in configs
    )

    # Convert to DataFrame
    results_df = pd.DataFrame(results)

    # Summary statistics
    print()
    print("=" * 80)
    print("RESULTS SUMMARY")
    print("=" * 80)
    print()

    # Top 5 configurations
    successful = results_df[results_df['status'] == 'success'].copy()
    if len(successful) > 0:
        successful_sorted = successful.sort_values('composite_score', ascending=False)

        print("TOP 5 CONFIGURATIONS:")
        print()
        for idx, row in successful_sorted.head(5).iterrows():
            print(f"{row['method']:20s} | Threshold: {row['threshold']:.0%} | Score: {row['composite_score']:.3f}")
            print(f"  Indicators: {row['n_indicators']:4,} | Edge Retention: {row['edge_retention']:.1%} | R²: {row['mean_r2']:.3f} | Runtime: {row['runtime_seconds']:.1f}s")
            print()

        # Best configuration
        best = successful_sorted.iloc[0]

        print("=" * 80)
        print("OPTIMAL CONFIGURATION")
        print("=" * 80)
        print(f"Method: {best['method']}")
        print(f"Threshold: {best['threshold']:.0%}")
        print(f"Composite Score: {best['composite_score']:.3f}")
        print()
        print(f"Performance:")
        print(f"  Indicators Retained: {best['n_indicators']:,}")
        print(f"  Edge Retention: {best['edge_retention']:.1%}")
        print(f"  Mean R²: {best['mean_r2']:.3f}")
        print(f"  Runtime: {best['runtime_seconds']:.1f} seconds")
        print()

        # Save optimal config
        optimal_config = {
            'method': best['method'],
            'threshold': float(best['threshold']),
            'composite_score': float(best['composite_score']),
            'edge_retention': float(best['edge_retention']),
            'mean_r2': float(best['mean_r2']),
            'runtime_seconds': float(best['runtime_seconds']),
            'n_indicators_retained': int(best['n_indicators']),
        }

        with open(BASE_DIR / "optimal_imputation_config.json", 'w') as f:
            json.dump(optimal_config, f, indent=2)

        print(f"✅ Optimal config saved to: optimal_imputation_config.json")

    # Save full results
    results_df.to_csv(BASE_DIR / "step2_imputation_experiment_results.csv", index=False)
    print(f"✅ Full results saved to: step2_imputation_experiment_results.csv")
    print()

    print("=" * 80)
    print("STEP 2 COMPLETE - Ready for Step 3 (Apply Optimal Configuration)")
    print("=" * 80)


if __name__ == "__main__":
    main()
