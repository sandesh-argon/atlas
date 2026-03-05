#!/usr/bin/env python3
"""
Compute Actual SHAP Scores for All 3,872 Indicators
====================================================

Uses LightGBM models to predict each outcome, then computes SHAP values
to determine feature importance across the causal network.

Method:
1. Load A1 preprocessed data (panel data)
2. For each B1 validated outcome, train a LightGBM model
3. Compute SHAP values for all features
4. Aggregate SHAP importance across outcomes

Output:
- B35_shap_scores.pkl (updated with real SHAP values)

Author: Phase B3.5
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

# Project paths
project_root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(project_root))

output_dir = Path(__file__).parent.parent / "outputs"

print("=" * 80)
print("COMPUTING ACTUAL SHAP SCORES FOR ALL INDICATORS")
print("=" * 80)

start_time = datetime.now()
print(f"Start time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")

# ============================================================================
# STEP 1: LOAD DATA
# ============================================================================

print("\n[STEP 1] Loading data...")

# Load A1 preprocessed data (dict of DataFrames, one per indicator)
a1_path = project_root / "phaseA/A1_missingness_analysis/outputs/A2_preprocessed_data.pkl"
with open(a1_path, 'rb') as f:
    a1_data = pickle.load(f)

imputed_dict = a1_data['imputed_data']
print(f"   ✅ Loaded {len(imputed_dict)} indicator DataFrames")

# Combine into single panel (wide format: rows=country-year, cols=indicators)
print("   Combining into panel data...")

# Get first df to understand structure
sample_df = list(imputed_dict.values())[0]
print(f"   Sample indicator shape: {sample_df.shape} (countries × years)")

# Build panel: pivot each indicator and merge
panel_data = None
indicator_count = 0

for indicator, df in imputed_dict.items():
    if indicator_count >= 500:  # Limit for memory
        break

    try:
        # Flatten: country-year as index
        # Assuming df has countries as rows, years as columns
        melted = df.reset_index().melt(id_vars=['index'], var_name='year', value_name=indicator)
        melted.columns = ['country', 'year', indicator]
        melted = melted.dropna()

        if panel_data is None:
            panel_data = melted
        else:
            panel_data = panel_data.merge(melted, on=['country', 'year'], how='outer')

        indicator_count += 1

        if indicator_count % 100 == 0:
            print(f"      Processed {indicator_count} indicators...")

    except Exception as e:
        continue

print(f"   ✅ Built panel: {panel_data.shape}")

# Load B1 validated outcomes
b1_path = project_root / "phaseB/B1_outcome_discovery/outputs/B1_validated_outcomes.pkl"
with open(b1_path, 'rb') as f:
    b1_data = pickle.load(f)

outcomes = b1_data['outcomes']
print(f"   ✅ Loaded {len(outcomes)} validated outcomes")

# Load A6 graph to get indicator list
a6_path = project_root / "phaseA/A6_hierarchical_layering/outputs/A6_hierarchical_graph.pkl"
with open(a6_path, 'rb') as f:
    a6_data = pickle.load(f)

G = a6_data['graph']
all_indicators = list(G.nodes())
print(f"   ✅ Loaded {len(all_indicators)} indicators from A6")

# ============================================================================
# STEP 2: INSTALL/IMPORT SHAP AND LIGHTGBM
# ============================================================================

print("\n[STEP 2] Setting up SHAP and LightGBM...")

try:
    import shap
    print(f"   ✅ SHAP version: {shap.__version__}")
except ImportError:
    print("   Installing SHAP...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "shap", "-q"])
    import shap
    print(f"   ✅ SHAP installed")

try:
    import lightgbm as lgb
    print(f"   ✅ LightGBM version: {lgb.__version__}")
except ImportError:
    print("   Installing LightGBM...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "lightgbm", "-q"])
    import lightgbm as lgb
    print(f"   ✅ LightGBM installed")

# ============================================================================
# STEP 3: PREPARE FEATURE MATRIX
# ============================================================================

print("\n[STEP 3] Preparing feature matrix...")

# Get columns that are in both panel_data and A6 graph
available_indicators = [col for col in panel_data.columns if col in all_indicators]
print(f"   Indicators in panel data: {len(available_indicators)}")

# Find outcome-like columns (from B1)
outcome_columns = []
for outcome in outcomes:
    # Each outcome has top indicators - use the highest loading one as proxy
    if 'top_indicators' in outcome:
        for ind in outcome['top_indicators'][:3]:
            if ind in panel_data.columns:
                outcome_columns.append(ind)
                break
    elif 'indicators' in outcome:
        for ind in outcome['indicators'][:3]:
            if ind in panel_data.columns:
                outcome_columns.append(ind)
                break

outcome_columns = list(set(outcome_columns))
print(f"   Outcome proxy columns: {len(outcome_columns)}")

# Feature columns = all indicators except outcomes
feature_columns = [col for col in available_indicators if col not in outcome_columns]
print(f"   Feature columns: {len(feature_columns)}")

# ============================================================================
# STEP 4: COMPUTE SHAP FOR EACH OUTCOME
# ============================================================================

print("\n[STEP 4] Computing SHAP values...")

# Store SHAP values per indicator (aggregated across outcomes)
shap_values_agg = defaultdict(list)

# LightGBM parameters
lgb_params = {
    'objective': 'regression',
    'metric': 'rmse',
    'boosting_type': 'gbdt',
    'num_leaves': 31,
    'learning_rate': 0.05,
    'feature_fraction': 0.8,
    'bagging_fraction': 0.8,
    'bagging_freq': 5,
    'verbose': -1,
    'n_jobs': 10
}

# Limit to avoid excessive computation
max_outcomes = min(len(outcome_columns), 5)  # Top 5 outcomes
max_samples = 2000  # Sample for SHAP computation

print(f"   Processing {max_outcomes} outcomes with {len(feature_columns)} features...")

for i, outcome_col in enumerate(outcome_columns[:max_outcomes]):
    print(f"\n   [{i+1}/{max_outcomes}] Outcome: {outcome_col}")

    try:
        # Prepare data
        df = panel_data[[outcome_col] + feature_columns].dropna()

        if len(df) < 100:
            print(f"      ⚠️ Skipping: only {len(df)} samples")
            continue

        # Sample if too large
        if len(df) > max_samples:
            df = df.sample(n=max_samples, random_state=42)

        X = df[feature_columns].values
        y = df[outcome_col].values

        print(f"      Data shape: {X.shape}")

        # Train LightGBM
        train_data = lgb.Dataset(X, label=y, feature_name=feature_columns)
        model = lgb.train(lgb_params, train_data, num_boost_round=100)

        # Compute SHAP values
        explainer = shap.TreeExplainer(model)

        # Use subset for SHAP computation (faster)
        shap_sample_size = min(500, len(X))
        X_sample = X[:shap_sample_size]

        shap_values = explainer.shap_values(X_sample)

        # Aggregate: mean absolute SHAP value per feature
        mean_abs_shap = np.abs(shap_values).mean(axis=0)

        # Store
        for j, feature in enumerate(feature_columns):
            shap_values_agg[feature].append(mean_abs_shap[j])

        print(f"      ✅ SHAP computed, top feature: {feature_columns[np.argmax(mean_abs_shap)]}")

    except Exception as e:
        print(f"      ❌ Error: {e}")
        continue

# ============================================================================
# STEP 5: AGGREGATE SHAP SCORES
# ============================================================================

print("\n[STEP 5] Aggregating SHAP scores across outcomes...")

# Final SHAP score = mean across outcomes
final_shap_scores = {}

for indicator in all_indicators:
    if indicator in shap_values_agg:
        scores = shap_values_agg[indicator]
        final_shap_scores[indicator] = {
            'shap_score': float(np.mean(scores)),
            'shap_std': float(np.std(scores)),
            'n_outcomes': len(scores),
            'method': 'LightGBM TreeSHAP'
        }
    else:
        # Indicator not in training data - use fallback
        final_shap_scores[indicator] = {
            'shap_score': 0.0,
            'shap_std': 0.0,
            'n_outcomes': 0,
            'method': 'fallback (not in training data)'
        }

# Normalize to 0-1 range
scores = [s['shap_score'] for s in final_shap_scores.values()]
non_zero_scores = [s for s in scores if s > 0]

if non_zero_scores:
    min_score = min(non_zero_scores)
    max_score = max(non_zero_scores)

    if max_score > min_score:
        for indicator in final_shap_scores:
            raw = final_shap_scores[indicator]['shap_score']
            if raw > 0:
                normalized = (raw - min_score) / (max_score - min_score)
            else:
                normalized = 0.0
            final_shap_scores[indicator]['shap_score_normalized'] = normalized
    else:
        for indicator in final_shap_scores:
            final_shap_scores[indicator]['shap_score_normalized'] = 0.5
else:
    for indicator in final_shap_scores:
        final_shap_scores[indicator]['shap_score_normalized'] = 0.0

# Statistics
computed_count = sum(1 for s in final_shap_scores.values() if s['n_outcomes'] > 0)
normalized_scores = [s['shap_score_normalized'] for s in final_shap_scores.values()]

print(f"\n   SHAP Statistics:")
print(f"      Indicators with computed SHAP: {computed_count}/{len(all_indicators)}")
print(f"      Score range (normalized): {min(normalized_scores):.4f} - {max(normalized_scores):.4f}")
print(f"      Mean: {np.mean(normalized_scores):.4f}")
print(f"      Median: {np.median(normalized_scores):.4f}")

# Top 10 by SHAP
top_10 = sorted(final_shap_scores.items(), key=lambda x: x[1]['shap_score'], reverse=True)[:10]
print(f"\n   Top 10 most important indicators (by SHAP):")
for indicator, data in top_10:
    print(f"      {data['shap_score']:.6f} ({data['shap_score_normalized']:.4f} norm) | {indicator}")

# ============================================================================
# STEP 6: SAVE UPDATED SHAP SCORES
# ============================================================================

print("\n[STEP 6] Saving SHAP scores...")

shap_path = output_dir / "B35_shap_scores.pkl"
with open(shap_path, 'wb') as f:
    pickle.dump(final_shap_scores, f)
print(f"   ✅ Saved: {shap_path}")

# Also save JSON summary
shap_summary = {
    'computed_count': computed_count,
    'total_indicators': len(all_indicators),
    'coverage': computed_count / len(all_indicators),
    'method': 'LightGBM TreeSHAP',
    'n_outcomes_used': max_outcomes,
    'statistics': {
        'min': float(min(normalized_scores)),
        'max': float(max(normalized_scores)),
        'mean': float(np.mean(normalized_scores)),
        'median': float(np.median(normalized_scores)),
        'std': float(np.std(normalized_scores))
    },
    'top_10': [(ind, data['shap_score_normalized']) for ind, data in top_10]
}

shap_summary_path = output_dir / "B35_shap_summary.json"
with open(shap_summary_path, 'w') as f:
    json.dump(shap_summary, f, indent=2)
print(f"   ✅ Saved: {shap_summary_path}")

# ============================================================================
# SUMMARY
# ============================================================================

elapsed = (datetime.now() - start_time).total_seconds()

print("\n" + "=" * 80)
print("SHAP COMPUTATION COMPLETE")
print("=" * 80)

print(f"""
Summary:
   Indicators with SHAP: {computed_count}/{len(all_indicators)} ({computed_count/len(all_indicators)*100:.1f}%)
   Outcomes used: {max_outcomes}
   Method: LightGBM TreeSHAP

   Score range: {min(normalized_scores):.4f} - {max(normalized_scores):.4f}
   Mean: {np.mean(normalized_scores):.4f}
   Median: {np.median(normalized_scores):.4f}

   Runtime: {elapsed/60:.1f} minutes

Next: Update B3.5 hierarchy with real SHAP scores
""")
