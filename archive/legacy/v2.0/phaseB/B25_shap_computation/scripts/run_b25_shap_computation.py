#!/usr/bin/env python3
"""
B2.5: SHAP Score Computation for All Indicators
================================================

Computes actual SHAP importance scores for all 3,872 indicators using
LightGBM models trained on validated outcomes.

Features:
- Multi-core parallel processing (10 cores for thermal safety)
- Checkpoint system (saves progress every 10 outcomes)
- Resume capability (detects and loads existing checkpoints)
- Memory-efficient panel construction

Method:
1. Build efficient panel data (country-year × indicators)
2. For each B1 validated outcome + additional proxy outcomes:
   - Train LightGBM regressor
   - Compute TreeSHAP values
   - Store mean |SHAP| per feature
3. Aggregate SHAP across all outcomes
4. Normalize to 0-1 range

Output:
- B25_shap_scores.pkl (raw and normalized SHAP for all indicators)
- B25_shap_summary.json (statistics)
- checkpoints/shap_checkpoint_*.pkl (incremental saves)

Runtime: 2-4 hours (with checkpointing)
Cores: 10 (thermal safe limit)

Author: Phase B2.5
Date: December 2025
"""

import pickle
import json
import sys
import os
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
import warnings
warnings.filterwarnings('ignore')

# Project paths
project_root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(project_root))

output_dir = Path(__file__).parent.parent / "outputs"
checkpoint_dir = Path(__file__).parent.parent / "checkpoints"
output_dir.mkdir(exist_ok=True, parents=True)
checkpoint_dir.mkdir(exist_ok=True, parents=True)

# Configuration
N_CORES = 3  # Reduced for memory - each worker needs ~6GB
CHECKPOINT_INTERVAL = 1  # Save after EVERY outcome for progress tracking
MAX_SAMPLES_PER_OUTCOME = 2000  # Limit samples for SHAP computation
SHAP_BACKGROUND_SIZE = 100  # Background samples for TreeSHAP
PROGRESS_FILE = Path(__file__).parent.parent / "progress.json"  # Real-time progress

def update_progress(status, completed=0, total=0, current_outcome="", message="", error=""):
    """Write real-time progress to JSON file"""
    progress = {
        "status": status,
        "completed": completed,
        "total": total,
        "percent": round(completed / total * 100, 1) if total > 0 else 0,
        "current_outcome": current_outcome,
        "message": message,
        "error": error,
        "timestamp": datetime.now().isoformat(),
        "elapsed_minutes": round((datetime.now() - start_time).total_seconds() / 60, 1) if 'start_time' in globals() else 0
    }
    with open(PROGRESS_FILE, 'w') as f:
        json.dump(progress, f, indent=2)

print("=" * 80)
print("B2.5: SHAP SCORE COMPUTATION FOR ALL INDICATORS")
print("=" * 80)

start_time = datetime.now()
print(f"Start time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
print(f"Cores: {N_CORES}")
print(f"Checkpoint interval: every {CHECKPOINT_INTERVAL} outcomes")

# Initialize progress file
update_progress("initializing", message="Starting SHAP computation...")

# ============================================================================
# STEP 1: CHECK FOR EXISTING CHECKPOINTS
# ============================================================================

print("\n[STEP 1] Checking for existing checkpoints...")

checkpoint_files = sorted(checkpoint_dir.glob("shap_checkpoint_*.pkl"))
completed_outcomes = set()
shap_values_agg = defaultdict(list)

if checkpoint_files:
    latest_checkpoint = checkpoint_files[-1]
    print(f"   Found checkpoint: {latest_checkpoint.name}")

    with open(latest_checkpoint, 'rb') as f:
        checkpoint_data = pickle.load(f)

    completed_outcomes = set(checkpoint_data.get('completed_outcomes', []))
    shap_values_agg = defaultdict(list, checkpoint_data.get('shap_values_agg', {}))

    print(f"   ✅ Resuming from checkpoint: {len(completed_outcomes)} outcomes already processed")
else:
    print(f"   No checkpoint found, starting fresh")

# ============================================================================
# STEP 2: LOAD DATA
# ============================================================================

print("\n[STEP 2] Loading data...")

# Load A1 preprocessed data
a1_path = project_root / "phaseA/A1_missingness_analysis/outputs/A2_preprocessed_data.pkl"
with open(a1_path, 'rb') as f:
    a1_data = pickle.load(f)

imputed_dict = a1_data['imputed_data']
print(f"   ✅ Loaded {len(imputed_dict)} indicator DataFrames")

# Load A6 graph to get indicator list
a6_path = project_root / "phaseA/A6_hierarchical_layering/outputs/A6_hierarchical_graph.pkl"
with open(a6_path, 'rb') as f:
    a6_data = pickle.load(f)

G = a6_data['graph']
all_indicators = list(G.nodes())
print(f"   ✅ Loaded {len(all_indicators)} indicators from A6 graph")

# Load B1 validated outcomes
b1_path = project_root / "phaseB/B1_outcome_discovery/outputs/B1_validated_outcomes.pkl"
with open(b1_path, 'rb') as f:
    b1_data = pickle.load(f)

outcomes_data = b1_data['outcomes']
print(f"   ✅ Loaded {len(outcomes_data)} B1 validated outcomes")

# ============================================================================
# STEP 3: BUILD PANEL DATA (EFFICIENT)
# ============================================================================

print("\n[STEP 3] Building panel data (efficient method)...")

# Use concat instead of merge - much faster
# First, collect all melted DataFrames
melted_dfs = []
indicator_names = []

# Use A6 graph indicators as target (they're all in imputed_dict)
target_indicators = [ind for ind in all_indicators if ind in imputed_dict]
print(f"   Target indicators (in graph AND imputed): {len(target_indicators)}")

for i, indicator in enumerate(target_indicators):
    try:
        df = imputed_dict[indicator]

        # Check if df is valid
        if df is None or df.empty:
            continue

        # Melt: rows=countries (index), cols=years -> long format
        # The index contains country names, columns contain years
        melted = df.reset_index()
        melted = melted.melt(
            id_vars=[melted.columns[0]],  # First column is country (from index)
            var_name='year',
            value_name='value'
        )
        melted.columns = ['country', 'year', 'value']
        melted['indicator'] = indicator

        # Convert year to string for consistency
        melted['year'] = melted['year'].astype(str)

        # Drop NaN values
        melted = melted.dropna(subset=['value'])

        if len(melted) > 0:
            melted_dfs.append(melted)
            indicator_names.append(indicator)

        if (i + 1) % 500 == 0:
            print(f"      Processed {i + 1}/{len(target_indicators)} indicators...")

    except Exception as e:
        if i < 5:
            print(f"      Error on {indicator}: {e}")
        continue

print(f"   ✅ Collected {len(melted_dfs)} indicator DataFrames")

# Concatenate all
print("   Concatenating into long format...")
long_data = pd.concat(melted_dfs, ignore_index=True)
print(f"   Long data shape: {long_data.shape}")

# Pivot to wide format
print("   Pivoting to wide format (this may take a few minutes)...")
panel_data = long_data.pivot_table(
    index=['country', 'year'],
    columns='indicator',
    values='value',
    aggfunc='first'
).reset_index()

print(f"   ✅ Panel data shape: {panel_data.shape}")
print(f"   Memory usage: {panel_data.memory_usage(deep=True).sum() / 1e6:.1f} MB")

# Clean column names
panel_data.columns = [str(c) for c in panel_data.columns]

# Get feature columns (excluding country, year)
feature_columns = [c for c in panel_data.columns if c not in ['country', 'year']]
print(f"   Feature columns: {len(feature_columns)}")

# ============================================================================
# STEP 4: IDENTIFY OUTCOME COLUMNS (FROM B1 DISCOVERED FACTORS - UNBIASED)
# ============================================================================

print("\n[STEP 4] Identifying outcome columns from B1 discovered factors...")

# B1 discovered 9 outcome dimensions via factor analysis
# Use the TOP VARIABLE from each factor as proxy for that dimension
# This is DATA-DRIVEN, not manually curated

outcome_columns = []
print(f"\n   B1 discovered {len(outcomes_data)} outcome dimensions:")

for i, outcome in enumerate(outcomes_data):
    factor_name = outcome.get('primary_domain', f'Factor_{i+1}')
    top_vars = outcome.get('top_variables', [])
    r2 = outcome.get('predictability_r2_mean', 0)

    # Find the first top variable that exists in our panel
    for var in top_vars:
        if var in feature_columns:
            outcome_columns.append(var)
            print(f"   [{i+1}] {factor_name} (R²={r2:.3f}): {var}")
            break
    else:
        print(f"   [{i+1}] {factor_name}: ⚠️ No top variable found in panel")

# Remove duplicates while preserving order
seen = set()
outcome_columns = [x for x in outcome_columns if not (x in seen or seen.add(x))]

# Remove numeric-only codes (unclear what they are)
outcome_columns = [c for c in outcome_columns if not c.isdigit()]

print(f"\n   ✅ Using {len(outcome_columns)} B1-discovered outcome proxies")
print(f"   Method: Top variable from each factor (data-driven, unbiased)")

# Filter out already completed outcomes
remaining_outcomes = [o for o in outcome_columns if o not in completed_outcomes]
print(f"   Remaining to process: {len(remaining_outcomes)}")

# ============================================================================
# STEP 5: INSTALL DEPENDENCIES
# ============================================================================

print("\n[STEP 5] Setting up SHAP and LightGBM...")

try:
    import shap
    print(f"   ✅ SHAP version: {shap.__version__}")
except ImportError:
    print("   Installing SHAP...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "shap", "--break-system-packages", "-q"])
    import shap
    print(f"   ✅ SHAP installed: {shap.__version__}")

try:
    import lightgbm as lgb
    print(f"   ✅ LightGBM version: {lgb.__version__}")
except ImportError:
    print("   Installing LightGBM...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "lightgbm", "--break-system-packages", "-q"])
    import lightgbm as lgb
    print(f"   ✅ LightGBM installed: {lgb.__version__}")

# ============================================================================
# STEP 6: SHAP COMPUTATION FUNCTION
# ============================================================================

def compute_shap_for_outcome(args):
    """
    Compute SHAP values for a single outcome.
    Returns dict of {indicator: mean_abs_shap}

    Handles sparse panel data by:
    1. First filtering rows where outcome is non-null
    2. Then selecting features with sufficient overlap (>50% non-null)
    3. Imputing remaining NaN values with column median
    """
    outcome_col, panel_subset, feature_cols = args

    try:
        import lightgbm as lgb
        import shap
        import numpy as np
        import pandas as pd

        # Step 1: Filter to rows where outcome is non-null
        df = panel_subset[panel_subset[outcome_col].notna()].copy()

        if len(df) < 100:
            return outcome_col, {}, f"Too few samples with outcome: {len(df)}"

        # Step 2: Select features with sufficient data overlap (>50% non-null)
        # Exclude outcome column from features to avoid duplicate columns
        feature_cols_no_outcome = [c for c in feature_cols if c != outcome_col]
        feature_coverage = df[feature_cols_no_outcome].notna().mean()
        good_features = feature_coverage[feature_coverage > 0.5].index.tolist()

        if len(good_features) < 50:
            return outcome_col, {}, f"Too few features with >50% coverage: {len(good_features)}"

        # Step 3: Prepare data with selected features
        df_subset = df[[outcome_col] + good_features].copy()

        # Impute remaining NaN values with column median
        # Use .loc to avoid any ambiguity with numeric column names
        for col in good_features:
            col_data = df_subset.loc[:, col]
            na_count = int(col_data.isna().sum())
            if na_count > 0:
                median_val = col_data.median()
                if pd.notna(median_val):
                    df_subset.loc[:, col] = col_data.fillna(median_val)
                else:
                    # If median is NaN, use 0
                    df_subset.loc[:, col] = col_data.fillna(0)

        # Sample if too large
        if len(df_subset) > MAX_SAMPLES_PER_OUTCOME:
            df_subset = df_subset.sample(n=MAX_SAMPLES_PER_OUTCOME, random_state=42)

        X = df_subset[good_features].values
        y = df_subset[outcome_col].values

        # Remove constant features
        non_const_mask = X.std(axis=0) > 1e-10
        X_filtered = X[:, non_const_mask]
        filtered_features = [f for f, m in zip(good_features, non_const_mask) if m]

        if len(filtered_features) < 10:
            return outcome_col, {}, f"Too few non-constant features: {len(filtered_features)}"

        # Train LightGBM
        lgb_params = {
            'objective': 'regression',
            'metric': 'rmse',
            'boosting_type': 'gbdt',
            'num_leaves': 31,
            'learning_rate': 0.05,
            'feature_fraction': 0.8,
            'verbose': -1,
            'n_jobs': 1  # Single thread per model (parallelism at outcome level)
        }

        train_data = lgb.Dataset(X_filtered, label=y, feature_name=filtered_features)
        model = lgb.train(lgb_params, train_data, num_boost_round=100)

        # Compute SHAP
        explainer = shap.TreeExplainer(model)

        # Use subset for SHAP (faster)
        shap_sample_size = min(SHAP_BACKGROUND_SIZE, len(X_filtered))
        X_shap = X_filtered[:shap_sample_size]

        shap_values = explainer.shap_values(X_shap)

        # Mean absolute SHAP per feature
        mean_abs_shap = np.abs(shap_values).mean(axis=0)

        # Build result dict
        result = {}
        for feat, shap_val in zip(filtered_features, mean_abs_shap):
            result[feat] = float(shap_val)

        return outcome_col, result, None

    except Exception as e:
        return outcome_col, {}, str(e)

# ============================================================================
# STEP 7: SEQUENTIAL SHAP COMPUTATION (memory-safe with real-time progress)
# ============================================================================

print("\n[STEP 6] Computing SHAP values (sequential for memory safety)...")
print(f"   Outcomes to process: {len(remaining_outcomes)}")
total_outcomes = len(outcome_columns)

update_progress("computing", 0, total_outcomes, message="Starting SHAP computation...")

# Prepare panel subset once
panel_subset = panel_data[['country', 'year'] + feature_columns].copy()

for i, outcome_col in enumerate(remaining_outcomes):
    outcome_num = len(completed_outcomes) + 1

    # Update progress BEFORE starting
    update_progress(
        "computing",
        len(completed_outcomes),
        total_outcomes,
        current_outcome=outcome_col,
        message=f"Processing {outcome_col} ({outcome_num}/{total_outcomes})..."
    )

    print(f"\n   [{outcome_num}/{total_outcomes}] Processing: {outcome_col}")

    try:
        # Call the compute function directly (no subprocess)
        args = (outcome_col, panel_subset, feature_columns)
        outcome, shap_dict, error = compute_shap_for_outcome(args)

        if error:
            print(f"      ⚠️ {error}")
            update_progress(
                "computing",
                len(completed_outcomes),
                total_outcomes,
                current_outcome=outcome_col,
                error=error
            )
        else:
            # Aggregate SHAP values
            for indicator, shap_val in shap_dict.items():
                shap_values_agg[indicator].append(shap_val)

            completed_outcomes.add(outcome)
            print(f"      ✅ {len(shap_dict)} features scored")

            # Save checkpoint after each outcome
            checkpoint_path = checkpoint_dir / f"shap_checkpoint_{len(completed_outcomes):04d}.pkl"
            checkpoint_data = {
                'completed_outcomes': list(completed_outcomes),
                'shap_values_agg': dict(shap_values_agg),
                'timestamp': datetime.now().isoformat()
            }
            with open(checkpoint_path, 'wb') as f:
                pickle.dump(checkpoint_data, f)

            # Update progress AFTER completing
            elapsed = (datetime.now() - start_time).total_seconds() / 60
            rate = len(completed_outcomes) / elapsed if elapsed > 0 else 0
            eta = (total_outcomes - len(completed_outcomes)) / rate if rate > 0 else 0

            update_progress(
                "computing",
                len(completed_outcomes),
                total_outcomes,
                current_outcome=outcome_col,
                message=f"Completed {outcome_col}. Rate: {rate:.1f}/min, ETA: {eta:.1f} min"
            )

            print(f"      💾 Checkpoint saved ({len(completed_outcomes)}/{total_outcomes})")

    except Exception as e:
        print(f"      ❌ Error: {e}")
        update_progress(
            "computing",
            len(completed_outcomes),
            total_outcomes,
            current_outcome=outcome_col,
            error=str(e)
        )

print(f"\n   ✅ Completed {len(completed_outcomes)}/{total_outcomes} outcomes")

# ============================================================================
# STEP 8: AGGREGATE FINAL SHAP SCORES
# ============================================================================

print("\n[STEP 7] Aggregating final SHAP scores...")

# Final SHAP score = mean across all outcomes
final_shap_scores = {}

for indicator in all_indicators:
    if indicator in shap_values_agg and len(shap_values_agg[indicator]) > 0:
        scores = shap_values_agg[indicator]
        final_shap_scores[indicator] = {
            'shap_mean': float(np.mean(scores)),
            'shap_std': float(np.std(scores)),
            'shap_max': float(np.max(scores)),
            'n_outcomes': len(scores),
            'method': 'LightGBM TreeSHAP'
        }
    else:
        final_shap_scores[indicator] = {
            'shap_mean': 0.0,
            'shap_std': 0.0,
            'shap_max': 0.0,
            'n_outcomes': 0,
            'method': 'not_computed'
        }

# Normalize to 0-1 range
raw_scores = [s['shap_mean'] for s in final_shap_scores.values()]
non_zero_scores = [s for s in raw_scores if s > 0]

if non_zero_scores:
    min_score = min(non_zero_scores)
    max_score = max(non_zero_scores)

    if max_score > min_score:
        for indicator in final_shap_scores:
            raw = final_shap_scores[indicator]['shap_mean']
            if raw > 0:
                normalized = (raw - min_score) / (max_score - min_score)
            else:
                normalized = 0.0
            final_shap_scores[indicator]['shap_normalized'] = normalized
    else:
        for indicator in final_shap_scores:
            final_shap_scores[indicator]['shap_normalized'] = 0.5
else:
    for indicator in final_shap_scores:
        final_shap_scores[indicator]['shap_normalized'] = 0.0

# Statistics
computed_count = sum(1 for s in final_shap_scores.values() if s['n_outcomes'] > 0)
normalized_scores = [s['shap_normalized'] for s in final_shap_scores.values()]

print(f"\n   SHAP Statistics:")
print(f"      Indicators with SHAP: {computed_count}/{len(all_indicators)} ({computed_count/len(all_indicators)*100:.1f}%)")
print(f"      Outcomes processed: {len(completed_outcomes)}")
print(f"      Score range (normalized): {min(normalized_scores):.4f} - {max(normalized_scores):.4f}")
print(f"      Mean: {np.mean(normalized_scores):.4f}")
print(f"      Median: {np.median(normalized_scores):.4f}")

# Top 10 by SHAP
top_10 = sorted(final_shap_scores.items(), key=lambda x: x[1]['shap_mean'], reverse=True)[:10]
print(f"\n   Top 10 most important indicators (by SHAP):")
for indicator, data in top_10:
    print(f"      {data['shap_mean']:.6f} (norm: {data['shap_normalized']:.4f}) | {indicator}")

# ============================================================================
# STEP 9: SAVE OUTPUTS
# ============================================================================

print("\n[STEP 8] Saving outputs...")

# Primary output
shap_path = output_dir / "B25_shap_scores.pkl"
with open(shap_path, 'wb') as f:
    pickle.dump(final_shap_scores, f)
print(f"   ✅ Saved: {shap_path}")

# JSON summary
summary = {
    'computed_count': computed_count,
    'total_indicators': len(all_indicators),
    'coverage_pct': computed_count / len(all_indicators) * 100,
    'outcomes_processed': len(completed_outcomes),
    'method': 'LightGBM TreeSHAP',
    'statistics': {
        'min': float(min(normalized_scores)),
        'max': float(max(normalized_scores)),
        'mean': float(np.mean(normalized_scores)),
        'median': float(np.median(normalized_scores)),
        'std': float(np.std(normalized_scores))
    },
    'top_20': [
        {'indicator': ind, 'shap_normalized': data['shap_normalized'], 'shap_raw': data['shap_mean']}
        for ind, data in sorted(final_shap_scores.items(), key=lambda x: x[1]['shap_mean'], reverse=True)[:20]
    ],
    'timestamp': datetime.now().isoformat(),
    'runtime_minutes': (datetime.now() - start_time).total_seconds() / 60
}

summary_path = output_dir / "B25_shap_summary.json"
with open(summary_path, 'w') as f:
    json.dump(summary, f, indent=2)
print(f"   ✅ Saved: {summary_path}")

# ============================================================================
# SUMMARY
# ============================================================================

elapsed = (datetime.now() - start_time).total_seconds()

print("\n" + "=" * 80)
print("B2.5 SHAP COMPUTATION COMPLETE")
print("=" * 80)

print(f"""
Summary:
   Indicators with SHAP: {computed_count}/{len(all_indicators)} ({computed_count/len(all_indicators)*100:.1f}%)
   Outcomes processed: {len(completed_outcomes)}
   Method: LightGBM TreeSHAP
   Cores used: {N_CORES}

   Score range (normalized): {min(normalized_scores):.4f} - {max(normalized_scores):.4f}
   Mean: {np.mean(normalized_scores):.4f}
   Median: {np.median(normalized_scores):.4f}

   Runtime: {elapsed/60:.1f} minutes ({elapsed/3600:.2f} hours)

Output files:
   - {shap_path}
   - {summary_path}

Checkpoints saved in: {checkpoint_dir}

Next step: Update B3.5 hierarchy with real SHAP scores
""")
