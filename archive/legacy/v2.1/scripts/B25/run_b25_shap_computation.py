#!/usr/bin/env python3
"""
B2.5: SHAP Score Computation for All Indicators (V2.1)
======================================================

Computes SHAP importance scores for all 1,962 V2.1 indicators using
LightGBM models trained on B1 validated outcomes.

V2.1 MODIFICATIONS:
- Uses v21_config for paths
- Adjusted for smaller graph (1,962 vs 3,872 nodes)
- Uses B1 outcomes from V2.1

Method:
1. Build efficient panel data (country-year × indicators)
2. For each B1 validated outcome:
   - Train LightGBM regressor
   - Compute TreeSHAP values
   - Store mean |SHAP| per feature
3. Aggregate SHAP across all outcomes
4. Normalize to 0-1 range

Runtime: 30-60 minutes (V2.1 is smaller)

Author: Phase B2.5 V2.1
Date: December 2025
"""

import pickle
import json
import sys
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime
from collections import defaultdict
import warnings
warnings.filterwarnings('ignore')

# V2.1 Configuration
sys.path.insert(0, str(Path(__file__).parent.parent))
from v21_config import A6_OUTPUT, B1_OUTPUT, B25_OUTPUT, get_input_path

output_dir = B25_OUTPUT
checkpoint_dir = B25_OUTPUT / "checkpoints"
output_dir.mkdir(exist_ok=True, parents=True)
checkpoint_dir.mkdir(exist_ok=True, parents=True)

# Configuration
MAX_SAMPLES_PER_OUTCOME = 2000
SHAP_BACKGROUND_SIZE = 100
PROGRESS_FILE = output_dir / "progress.json"

def update_progress(status, completed=0, total=0, current_outcome="", message="", error=""):
    """Write real-time progress to JSON file"""
    global start_time
    elapsed_min = (datetime.now() - start_time).total_seconds() / 60 if 'start_time' in globals() else 0
    progress = {
        "status": status,
        "completed": completed,
        "total": total,
        "percent": round(completed / total * 100, 1) if total > 0 else 0,
        "current_outcome": current_outcome,
        "message": message,
        "error": error,
        "timestamp": datetime.now().isoformat(),
        "elapsed_minutes": round(elapsed_min, 1)
    }
    with open(PROGRESS_FILE, 'w') as f:
        json.dump(progress, f, indent=2)

print("=" * 80)
print("B2.5: SHAP SCORE COMPUTATION (V2.1)")
print("=" * 80)

start_time = datetime.now()
print(f"Start time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")

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
input_path = get_input_path()
with open(input_path, 'rb') as f:
    a1_data = pickle.load(f)

imputed_dict = a1_data['imputed_data']
print(f"   ✅ Loaded {len(imputed_dict)} indicator DataFrames")

# Load A6 graph to get indicator list
a6_path = A6_OUTPUT / "A6_hierarchical_graph.pkl"
with open(a6_path, 'rb') as f:
    a6_data = pickle.load(f)

G = a6_data['graph']
all_indicators = list(G.nodes())
print(f"   ✅ Loaded {len(all_indicators)} indicators from A6 graph")

# Load B1 validated outcomes
b1_path = B1_OUTPUT / "B1_validated_outcomes.pkl"
with open(b1_path, 'rb') as f:
    b1_data = pickle.load(f)

outcomes_data = b1_data['outcomes']

# Extract outcome indicators from new B1 format (theory-driven interpretable)
outcome_indicators = []
for outcome_id, outcome_info in outcomes_data.items():
    # Get top indicators for each outcome (priority indicators)
    top_inds = outcome_info.get('top_indicators', [])[:3]  # Top 3 per outcome
    outcome_indicators.extend(top_inds)

outcome_indicators = list(set(outcome_indicators))  # Remove duplicates
print(f"   ✅ Loaded {len(outcomes_data)} B1 outcome factors")
print(f"   ✅ Total outcome indicators: {len(outcome_indicators)}")

# ============================================================================
# STEP 3: BUILD PANEL DATA
# ============================================================================

print("\n[STEP 3] Building panel data...")

melted_dfs = []
indicator_names = []

target_indicators = [ind for ind in all_indicators if ind in imputed_dict]
print(f"   Target indicators (in graph AND imputed): {len(target_indicators)}")

for i, indicator in enumerate(target_indicators):
    try:
        df = imputed_dict[indicator]

        if df is None or df.empty:
            continue

        melted = df.reset_index()
        melted = melted.melt(
            id_vars=[melted.columns[0]],
            var_name='year',
            value_name='value'
        )
        melted.columns = ['country', 'year', 'value']
        melted['indicator'] = indicator
        melted['year'] = melted['year'].astype(str)
        melted = melted.dropna(subset=['value'])

        if len(melted) > 0:
            melted_dfs.append(melted)
            indicator_names.append(indicator)

        if (i + 1) % 500 == 0:
            print(f"      Processed {i + 1}/{len(target_indicators)} indicators...")

    except Exception as e:
        continue

print(f"   ✅ Collected {len(melted_dfs)} indicator DataFrames")

print("   Concatenating into long format...")
long_data = pd.concat(melted_dfs, ignore_index=True)
print(f"   Long data shape: {long_data.shape}")

print("   Pivoting to wide format...")
panel_data = long_data.pivot_table(
    index=['country', 'year'],
    columns='indicator',
    values='value',
    aggfunc='first'
).reset_index()

print(f"   ✅ Panel data shape: {panel_data.shape}")
print(f"   Memory usage: {panel_data.memory_usage(deep=True).sum() / 1e6:.1f} MB")

panel_data.columns = [str(c) for c in panel_data.columns]
feature_columns = [c for c in panel_data.columns if c not in ['country', 'year']]
print(f"   Feature columns: {len(feature_columns)}")

# ============================================================================
# STEP 4: IDENTIFY OUTCOME COLUMNS
# ============================================================================

print("\n[STEP 4] Identifying outcome columns...")

# Use outcome indicators from B1
outcome_columns = []

for ind in outcome_indicators:
    if ind in feature_columns:
        outcome_columns.append(ind)

# Remove duplicates
outcome_columns = list(set(outcome_columns))

# If B1 didn't produce enough outcomes, use theory-driven fallback
if len(outcome_columns) < 5:
    print(f"   ⚠️ Only {len(outcome_columns)} outcomes found, adding fallback outcomes...")

    fallback_keywords = {
        'life_expectancy': ['life.expect', 'SP.DYN.LE'],
        'gdp_per_capita': ['gdp.*capita', 'NY.GDP.PCAP'],
        'education': ['school', 'literacy', 'SE.'],
        'health': ['mortality', 'immunization', 'SH.'],
        'governance': ['v2x', 'democracy', 'corruption']
    }

    for name, keywords in fallback_keywords.items():
        for col in feature_columns:
            col_lower = col.lower()
            if any(kw.lower() in col_lower for kw in keywords):
                if col not in outcome_columns:
                    outcome_columns.append(col)
                    break

print(f"\n   ✅ Using {len(outcome_columns)} outcome columns for SHAP")

remaining_outcomes = [o for o in outcome_columns if o not in completed_outcomes]
print(f"   Remaining to process: {len(remaining_outcomes)}")

# ============================================================================
# STEP 5: SETUP SHAP AND LIGHTGBM
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

try:
    import lightgbm as lgb
    print(f"   ✅ LightGBM version: {lgb.__version__}")
except ImportError:
    print("   Installing LightGBM...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "lightgbm", "--break-system-packages", "-q"])
    import lightgbm as lgb

# ============================================================================
# STEP 6: COMPUTE SHAP VALUES
# ============================================================================

print("\n[STEP 6] Computing SHAP values...")

total_outcomes = len(outcome_columns)
update_progress("computing", len(completed_outcomes), total_outcomes, message="Starting SHAP computation...")

panel_subset = panel_data[['country', 'year'] + feature_columns].copy()

for i, outcome_col in enumerate(remaining_outcomes):
    outcome_num = len(completed_outcomes) + 1

    update_progress(
        "computing",
        len(completed_outcomes),
        total_outcomes,
        current_outcome=outcome_col,
        message=f"Processing {outcome_col} ({outcome_num}/{total_outcomes})..."
    )

    print(f"\n   [{outcome_num}/{total_outcomes}] Processing: {outcome_col}")

    try:
        # Filter to rows where outcome is non-null
        df = panel_subset[panel_subset[outcome_col].notna()].copy()

        if len(df) < 100:
            print(f"      ⚠️ Too few samples: {len(df)}")
            continue

        # Select features with sufficient data overlap (>50% non-null)
        feature_cols_no_outcome = [c for c in feature_columns if c != outcome_col]
        feature_coverage = df[feature_cols_no_outcome].notna().mean()
        good_features = feature_coverage[feature_coverage > 0.5].index.tolist()

        if len(good_features) < 50:
            print(f"      ⚠️ Too few features with >50% coverage: {len(good_features)}")
            continue

        # Prepare data
        df_subset = df[[outcome_col] + good_features].copy()

        # Impute remaining NaN values with column median
        for col in good_features:
            col_data = df_subset[col]
            na_count = col_data.isna().sum()
            if na_count > 0:
                median_val = col_data.median()
                if pd.notna(median_val):
                    df_subset[col] = col_data.fillna(median_val)
                else:
                    df_subset[col] = col_data.fillna(0)

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
            print(f"      ⚠️ Too few non-constant features: {len(filtered_features)}")
            continue

        # Train LightGBM
        lgb_params = {
            'objective': 'regression',
            'metric': 'rmse',
            'boosting_type': 'gbdt',
            'num_leaves': 31,
            'learning_rate': 0.05,
            'feature_fraction': 0.8,
            'verbose': -1,
            'n_jobs': 1
        }

        train_data = lgb.Dataset(X_filtered, label=y, feature_name=filtered_features)
        model = lgb.train(lgb_params, train_data, num_boost_round=100)

        # Compute SHAP
        explainer = shap.TreeExplainer(model)
        shap_sample_size = min(SHAP_BACKGROUND_SIZE, len(X_filtered))
        X_shap = X_filtered[:shap_sample_size]
        shap_values = explainer.shap_values(X_shap)

        # Mean absolute SHAP per feature
        mean_abs_shap = np.abs(shap_values).mean(axis=0)

        # Aggregate
        for feat, shap_val in zip(filtered_features, mean_abs_shap):
            shap_values_agg[feat].append(float(shap_val))

        completed_outcomes.add(outcome_col)
        print(f"      ✅ {len(filtered_features)} features scored")

        # Save checkpoint
        checkpoint_path = checkpoint_dir / f"shap_checkpoint_{len(completed_outcomes):04d}.pkl"
        checkpoint_data = {
            'completed_outcomes': list(completed_outcomes),
            'shap_values_agg': dict(shap_values_agg),
            'timestamp': datetime.now().isoformat()
        }
        with open(checkpoint_path, 'wb') as f:
            pickle.dump(checkpoint_data, f)

        update_progress(
            "computing",
            len(completed_outcomes),
            total_outcomes,
            current_outcome=outcome_col,
            message=f"Completed {outcome_col}"
        )

    except Exception as e:
        print(f"      ❌ Error: {e}")

print(f"\n   ✅ Completed {len(completed_outcomes)}/{total_outcomes} outcomes")

# ============================================================================
# STEP 7: AGGREGATE FINAL SHAP SCORES
# ============================================================================

print("\n[STEP 7] Aggregating final SHAP scores...")

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
print(f"      Score range: {min(normalized_scores):.4f} - {max(normalized_scores):.4f}")

# Top 10 by SHAP
top_10 = sorted(final_shap_scores.items(), key=lambda x: x[1]['shap_mean'], reverse=True)[:10]
print(f"\n   Top 10 most important indicators:")
for indicator, data in top_10:
    print(f"      {data['shap_normalized']:.4f} | {indicator[:50]}")

# ============================================================================
# STEP 8: SAVE OUTPUTS
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
        {'indicator': ind, 'shap_normalized': data['shap_normalized']}
        for ind, data in sorted(final_shap_scores.items(), key=lambda x: x[1]['shap_mean'], reverse=True)[:20]
    ],
    'timestamp': datetime.now().isoformat(),
    'runtime_minutes': (datetime.now() - start_time).total_seconds() / 60
}

summary_path = output_dir / "B25_shap_summary.json"
with open(summary_path, 'w') as f:
    json.dump(summary, f, indent=2)
print(f"   ✅ Saved: {summary_path}")

# Also copy to B35 output for B3.5 to find
b35_shap_path = Path(__file__).parent.parent / "B35" / "B25_shap_scores.pkl"
b35_shap_path.parent.mkdir(exist_ok=True, parents=True)
with open(b35_shap_path, 'wb') as f:
    pickle.dump(final_shap_scores, f)
print(f"   ✅ Copied to: {b35_shap_path}")

# Update final progress
update_progress("complete", total_outcomes, total_outcomes, message="SHAP computation complete!")

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

   Score range: {min(normalized_scores):.4f} - {max(normalized_scores):.4f}
   Mean: {np.mean(normalized_scores):.4f}

   Runtime: {elapsed/60:.1f} minutes

Output files:
   - {shap_path}
   - {summary_path}
   - {b35_shap_path}

Next step: Run B3.5 (semantic hierarchy)
""")
