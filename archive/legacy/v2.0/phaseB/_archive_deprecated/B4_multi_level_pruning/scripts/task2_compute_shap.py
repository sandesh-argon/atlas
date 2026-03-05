#!/usr/bin/env python3
"""
B4 Task 2: Compute SHAP Scores
================================

Computes importance scores for all 290 B3 mechanisms using feature importance
from Random Forest models (proxy for SHAP when SHAP library unavailable).

This determines which mechanisms have the highest explanatory power for outcomes,
enabling intelligent multi-level pruning in Task 3.

Outputs:
- B4_shap_scores.pkl: Importance scores for all mechanisms

Author: B4 Task 2
Date: November 2025
"""

import pickle
import json
from pathlib import Path
import pandas as pd
import numpy as np
import networkx as nx
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

# ML libraries
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.metrics import r2_score, mean_squared_error

# ============================================================================
# Setup
# ============================================================================

project_root = Path(__file__).resolve().parents[3]
b4_dir = project_root / 'phaseB/B4_multi_level_pruning'
outputs_dir = b4_dir / 'outputs'

print("="*80)
print("B4 TASK 2: COMPUTE FEATURE IMPORTANCE (SHAP PROXY)")
print("="*80)
print(f"\nTimestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"Estimated duration: 2-3 hours")
print(f"\n⚡ Using Random Forest feature importance as SHAP proxy")
print(f"   (SHAP library not available - RF importance highly correlated)")

# ============================================================================
# Step 1: Load Prepared Data
# ============================================================================

print("\n" + "="*80)
print("STEP 1: LOAD PREPARED DATA")
print("="*80)

prepared_path = outputs_dir / 'B4_prepared_data.pkl'
print(f"\nLoading: {prepared_path}")

with open(prepared_path, 'rb') as f:
    prepared_data = pickle.load(f)

# Extract components
b3_clusters = prepared_data['b3_data']['classified_clusters']
b3_mechanisms = prepared_data['b3_data']['mechanisms']
G_subgraph = prepared_data['graph']['subgraph']
effects_df = prepared_data['effects']['subgraph_effects']
beta_col = prepared_data['effects']['beta_column']

print(f"\n✅ Data Loaded:")
print(f"   - B3 clusters: {len(b3_clusters)}")
print(f"   - B3 mechanisms: {len(b3_mechanisms)}")
print(f"   - Subgraph nodes: {G_subgraph.number_of_nodes():,}")
print(f"   - Subgraph edges: {G_subgraph.number_of_edges():,}")
print(f"   - Effects: {len(effects_df):,}")

# ============================================================================
# Step 2: Load A0 Data for Feature Matrix Construction
# ============================================================================

print("\n" + "="*80)
print("STEP 2: LOAD A0 PREPROCESSED DATA")
print("="*80)

# Load A1/A2 preprocessed data
a1_path = project_root / 'phaseA/A1_missingness_analysis/outputs/A2_preprocessed_data.pkl'
print(f"\nLoading: {a1_path}")

with open(a1_path, 'rb') as f:
    a1_data = pickle.load(f)

# Extract the data matrix
if 'imputed_data' in a1_data:
    data_dict = a1_data['imputed_data']
elif 'preprocessed_data' in a1_data:
    data_dict = a1_data['preprocessed_data']
else:
    raise KeyError(f"No data matrix found. Available keys: {list(a1_data.keys())}")

# data_dict is {indicator: DataFrame(countries × years)}
# We need to convert to DataFrame(country-years × indicators)
if isinstance(data_dict, dict):
    indicators = list(data_dict.keys())

    # Stack all indicators into a single DataFrame
    # Each indicator DataFrame is (countries × years), we want (country-year samples × indicators)
    dfs = []
    for indicator in indicators:
        df_ind = data_dict[indicator]
        # Flatten to 1D series (country-year samples)
        series = df_ind.stack()
        dfs.append(series)

    # Combine into DataFrame
    df_full = pd.concat(dfs, axis=1, keys=indicators)
    df_full.columns = indicators

elif isinstance(data_dict, pd.DataFrame):
    df_full = data_dict.copy()
    indicators = list(df_full.columns)
else:
    raise TypeError(f"Unknown data type: {type(data_dict)}")

print(f"\n✅ A0 Data Loaded:")
print(f"   - Indicators: {len(indicators)}")
print(f"   - Data shape: {df_full.shape}")

print(f"   - Countries: {len(df_full):,}")
print(f"   - Features: {len(df_full.columns):,}")

# ============================================================================
# Step 3: Identify Target Variables (Layer 0 Outcomes)
# ============================================================================

print("\n" + "="*80)
print("STEP 3: IDENTIFY TARGET VARIABLES")
print("="*80)

# Get layer assignments
layer_assignments = prepared_data['graph']['layer_assignments']

# Find Layer 0 nodes (outcomes)
layer_0_nodes = [node for node, layer in layer_assignments.items() if layer == 0]

# Filter to nodes in subgraph and data
layer_0_in_subgraph = [node for node in layer_0_nodes if node in G_subgraph.nodes()]
layer_0_targets = [node for node in layer_0_in_subgraph if node in df_full.columns]

print(f"\n📊 Target Variables (Layer 0):")
print(f"   - Layer 0 nodes: {len(layer_0_nodes)}")
print(f"   - In subgraph: {len(layer_0_in_subgraph)}")
print(f"   - In data: {len(layer_0_targets)}")

if len(layer_0_targets) == 0:
    print("\n⚠️  WARNING: No Layer 0 targets found in data")
    print("   Using top 10 most central nodes as proxy targets...")

    # Compute PageRank centrality
    pagerank = nx.pagerank(G_subgraph)
    central_nodes = sorted(pagerank.items(), key=lambda x: -x[1])[:20]

    # Filter to nodes in data
    layer_0_targets = [node for node, _ in central_nodes if node in df_full.columns][:10]

    print(f"   - Selected {len(layer_0_targets)} proxy targets based on centrality")

for i, target in enumerate(layer_0_targets[:5], 1):
    print(f"   {i}. {target}")
if len(layer_0_targets) > 5:
    print(f"   ... and {len(layer_0_targets) - 5} more")

# ============================================================================
# Step 4: Build Feature Matrix
# ============================================================================

print("\n" + "="*80)
print("STEP 4: BUILD FEATURE MATRIX")
print("="*80)

# Filter mechanisms that exist in data
b3_mechanisms_in_data = [m for m in b3_mechanisms if m in df_full.columns]

print(f"\n📊 Feature Selection:")
print(f"   - B3 mechanisms: {len(b3_mechanisms)}")
print(f"   - In data: {len(b3_mechanisms_in_data)}")
print(f"   - Coverage: {len(b3_mechanisms_in_data)/len(b3_mechanisms):.1%}")

if len(b3_mechanisms_in_data) < 50:
    print(f"\n⚠️  WARNING: Only {len(b3_mechanisms_in_data)} mechanisms in data")
    print("   Expanding feature set to include all subgraph nodes...")

    # Use all subgraph nodes in data as features
    subgraph_nodes_in_data = [n for n in G_subgraph.nodes() if n in df_full.columns]
    b3_mechanisms_in_data = list(set(b3_mechanisms_in_data) | set(subgraph_nodes_in_data))[:500]  # Cap at 500

    print(f"   - Expanded to {len(b3_mechanisms_in_data)} features")

# Extract feature matrix
X = df_full[b3_mechanisms_in_data].copy()

print(f"\n✅ Feature Matrix Built:")
print(f"   - Shape: {X.shape}")
print(f"   - Features: {X.shape[1]}")
print(f"   - Samples: {X.shape[0]}")

# Handle missing values (fill with median)
X_filled = X.fillna(X.median())
missing_pct = (X.isna().sum().sum()) / (X.shape[0] * X.shape[1])
print(f"   - Missing values: {missing_pct:.1%} (filled with median)")

# ============================================================================
# Step 5: Compute Feature Importance for Each Target
# ============================================================================

print("\n" + "="*80)
print("STEP 5: COMPUTE FEATURE IMPORTANCE SCORES")
print("="*80)

# Storage for importance scores
importance_scores_per_target = {}
feature_importance_aggregate = {feat: [] for feat in b3_mechanisms_in_data}

print(f"\nComputing importance for {len(layer_0_targets)} targets...")
print(f"Using Random Forest with 100 trees, 12-core parallelization")

for target_idx, target in enumerate(layer_0_targets, 1):
    print(f"\n{'='*60}")
    print(f"Target {target_idx}/{len(layer_0_targets)}: {target}")
    print(f"{'='*60}")

    # Get target variable
    y = df_full[target].copy()

    # Filter to valid samples
    valid_mask = ~y.isna()
    X_valid = X_filled[valid_mask]
    y_valid = y[valid_mask]

    print(f"   - Valid samples: {len(y_valid):,} / {len(y):,} ({len(y_valid)/len(y):.1%})")

    if len(y_valid) < 100:
        print(f"   ⚠️  Skipping (insufficient samples)")
        continue

    # Split data
    X_train, X_test, y_train, y_test = train_test_split(
        X_valid, y_valid, test_size=0.2, random_state=42
    )

    print(f"   - Train: {len(X_train):,}, Test: {len(X_test):,}")

    # Train Random Forest
    print(f"   - Training Random Forest...")

    rf_model = RandomForestRegressor(
        n_estimators=100,
        max_depth=10,
        min_samples_split=10,
        min_samples_leaf=5,
        max_features='sqrt',
        n_jobs=12,  # 12 cores for thermal safety
        random_state=42,
        verbose=0
    )

    rf_model.fit(X_train, y_train)

    # Evaluate
    y_pred = rf_model.predict(X_test)
    r2 = r2_score(y_test, y_pred)
    rmse = np.sqrt(mean_squared_error(y_test, y_pred))

    print(f"   - Model R²: {r2:.3f}")
    print(f"   - Model RMSE: {rmse:.3f}")

    if r2 < 0.05:
        print(f"   ⚠️  WARNING: Low R² ({r2:.3f}) - importance scores may be unreliable")

    # Get feature importance
    feature_importances = rf_model.feature_importances_

    # Store per-target importance
    importance_scores_per_target[target] = {
        'importance_values': feature_importances,
        'features': list(X_train.columns),
        'model_r2': float(r2),
        'model_rmse': float(rmse),
        'samples': len(X_train)
    }

    # Accumulate for aggregate
    for feat_idx, feat in enumerate(X_train.columns):
        feature_importance_aggregate[feat].append(feature_importances[feat_idx])

    print(f"   ✅ Importance computed: {len(feature_importances)} features")

    # Show top 5 features
    top_features = sorted(zip(X_train.columns, feature_importances), key=lambda x: -x[1])[:5]
    print(f"   - Top 5 features:")
    for feat, imp_val in top_features:
        print(f"      {feat}: {imp_val:.4f}")

# ============================================================================
# Step 6: Aggregate Importance Across Targets
# ============================================================================

print("\n" + "="*80)
print("STEP 6: AGGREGATE IMPORTANCE SCORES")
print("="*80)

# Compute mean importance across all targets
aggregated_importance = {}
for feat, imp_list in feature_importance_aggregate.items():
    if len(imp_list) > 0:
        aggregated_importance[feat] = np.mean(imp_list)
    else:
        aggregated_importance[feat] = 0.0

print(f"\n📊 Importance Aggregation:")
print(f"   - Features with scores: {len([v for v in aggregated_importance.values() if v > 0])}")
print(f"   - Features without scores: {len([v for v in aggregated_importance.values() if v == 0])}")

# Sort by importance
sorted_importance = sorted(aggregated_importance.items(), key=lambda x: -x[1])

print(f"\n📊 Top 10 Mechanisms by Importance:")
for i, (feat, imp_val) in enumerate(sorted_importance[:10], 1):
    print(f"   {i:2d}. {feat}: {imp_val:.4f}")

print(f"\n📊 Bottom 10 Mechanisms by Importance:")
for i, (feat, imp_val) in enumerate(sorted_importance[-10:], 1):
    print(f"   {i:2d}. {feat}: {imp_val:.4f}")

# ============================================================================
# Step 7: Map Importance to B3 Mechanisms
# ============================================================================

print("\n" + "="*80)
print("STEP 7: MAP IMPORTANCE TO B3 MECHANISMS")
print("="*80)

# Create mechanism-level scores
mechanism_shap_scores = {}

for mech in b3_mechanisms:
    if mech in aggregated_importance:
        mechanism_shap_scores[mech] = aggregated_importance[mech]
    else:
        mechanism_shap_scores[mech] = 0.0

print(f"\n📊 B3 Mechanism Coverage:")
print(f"   - Total mechanisms: {len(b3_mechanisms)}")
print(f"   - With importance scores: {len([v for v in mechanism_shap_scores.values() if v > 0])}")
print(f"   - Without scores: {len([v for v in mechanism_shap_scores.values() if v == 0])}")

# Compute cluster-level importance
cluster_shap_scores = {}

for cluster in b3_clusters:
    cluster_id = cluster['cluster_id']
    cluster_mechanisms = [m for m in cluster['nodes'] if m in mechanism_shap_scores]

    if len(cluster_mechanisms) > 0:
        cluster_shap = np.mean([mechanism_shap_scores[m] for m in cluster_mechanisms])
        max_shap = max([mechanism_shap_scores.get(m, 0) for m in cluster['nodes']])
        min_shap = min([mechanism_shap_scores.get(m, 0) for m in cluster['nodes']] + [0])
    else:
        cluster_shap = 0.0
        max_shap = 0.0
        min_shap = 0.0

    cluster_shap_scores[cluster_id] = {
        'mean_shap': cluster_shap,
        'max_shap': max_shap,
        'min_shap': min_shap,
        'mechanism_count': len(cluster['nodes']),
        'mechanisms_with_shap': len(cluster_mechanisms)
    }

print(f"\n📊 Top 5 Clusters by Mean Importance:")
sorted_clusters = sorted(cluster_shap_scores.items(), key=lambda x: -x[1]['mean_shap'])
for cluster_id, stats in sorted_clusters[:5]:
    cluster_info = next(c for c in b3_clusters if c['cluster_id'] == cluster_id)
    print(f"   Cluster {cluster_id} ({cluster_info['hierarchical_label']}):")
    print(f"      Mean: {stats['mean_shap']:.4f}, Max: {stats['max_shap']:.4f}")
    print(f"      Mechanisms: {stats['mechanism_count']} ({stats['mechanisms_with_shap']} scored)")

# ============================================================================
# Step 8: Save Importance Scores (as SHAP proxy)
# ============================================================================

print("\n" + "="*80)
print("STEP 8: SAVE IMPORTANCE SCORES")
print("="*80)

shap_output = {
    'metadata': {
        'timestamp': datetime.now().isoformat(),
        'task': 'B4_task2_compute_shap',
        'version': '2.0',
        'method': 'RandomForest_feature_importance',
        'note': 'Using RF importance as SHAP proxy (SHAP library unavailable)',
        'targets': layer_0_targets,
        'n_targets': len(layer_0_targets),
        'n_mechanisms': len(b3_mechanisms),
        'n_features': len(b3_mechanisms_in_data)
    },
    'mechanism_shap_scores': mechanism_shap_scores,
    'cluster_shap_scores': cluster_shap_scores,
    'per_target_shap': importance_scores_per_target,
    'aggregated_shap': aggregated_importance,
    'statistics': {
        'total_mechanisms': len(b3_mechanisms),
        'mechanisms_with_shap': len([v for v in mechanism_shap_scores.values() if v > 0]),
        'mechanisms_without_shap': len([v for v in mechanism_shap_scores.values() if v == 0]),
        'mean_shap': float(np.mean(list(mechanism_shap_scores.values()))),
        'median_shap': float(np.median(list(mechanism_shap_scores.values()))),
        'max_shap': float(max(mechanism_shap_scores.values())),
        'min_shap': float(min(mechanism_shap_scores.values())),
        'shap_range': float(max(mechanism_shap_scores.values()) - min(mechanism_shap_scores.values()))
    }
}

shap_path = outputs_dir / 'B4_shap_scores.pkl'
with open(shap_path, 'wb') as f:
    pickle.dump(shap_output, f, protocol=pickle.HIGHEST_PROTOCOL)

print(f"\n✅ Saved importance scores: {shap_path}")
print(f"   - File size: {shap_path.stat().st_size / (1024**2):.1f} MB")

# ============================================================================
# Summary
# ============================================================================

print("\n" + "="*80)
print("TASK 2 COMPLETE - SUMMARY")
print("="*80)

print(f"\n📊 Importance Computation:")
print(f"   - Method: Random Forest feature importance (SHAP proxy)")
print(f"   - Targets analyzed: {len(importance_scores_per_target)}")
print(f"   - Mechanisms scored: {len(mechanism_shap_scores)}")
print(f"   - Clusters scored: {len(cluster_shap_scores)}")

print(f"\n📊 Importance Statistics:")
print(f"   - Mean: {shap_output['statistics']['mean_shap']:.4f}")
print(f"   - Median: {shap_output['statistics']['median_shap']:.4f}")
print(f"   - Range: {shap_output['statistics']['shap_range']:.4f}")
print(f"   - Max: {shap_output['statistics']['max_shap']:.4f}")

print(f"\n✅ Output:")
print(f"   - {shap_path.name} ({shap_path.stat().st_size / (1024**2):.1f} MB)")

print(f"\n🎯 Next Step: Task 2.5 - SHAP Validation (15 min)")
print(f"   - Validate SHAP baseline (range, separation, mass)")
print(f"   - Validate novel cluster SHAP (≥70% target)")

print("\n" + "="*80)
print("✅ TASK 2 COMPLETE")
print("="*80)
