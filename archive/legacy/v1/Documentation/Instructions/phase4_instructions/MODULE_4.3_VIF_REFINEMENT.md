# MODULE 4.3: VIF Filtering & Causal Graph Refinement

## OBJECTIVE
Calculate Variance Inflation Factors (VIF) for top causal drivers discovered in Module 4.2, iteratively remove high-multicollinearity features (VIF > 10), and re-run PC algorithm on VIF-filtered feature sets to obtain refined, interpretable causal graphs.

## CONTEXT
The PC algorithm can discover edges between highly collinear features (e.g., GDP_lag1 and GDP_lag3), creating redundant causal paths that complicate interpretation. VIF filtering removes multicollinearity while preserving causal signal—retain the feature with highest SHAP importance among collinear pairs. Re-running PC on VIF-filtered features produces cleaner DAGs with non-redundant causal drivers, improving both interpretability and statistical robustness of effect quantification (Module 4.5).

## INPUTS

### From Module 4.2
- **Tier 1 Summary**: `<repo-root>/v1.0/models/causal_graphs/tier1/tier1_summary.json`
  - Contains `top_20_drivers` for each metric (features with edges to target)
- **Original Causal Graphs**: `<repo-root>/v1.0/models/causal_graphs/tier1/{metric}_pc_graph.pkl`

### From Module 4.1
- **Training Data**: `<repo-root>/v1.0/models/causal_graphs/loaded_training_data.pkl`
- **SHAP Importance**: `<repo-root>/v1.0/models/causal_graphs/loaded_shap_importance.pkl`

### Configuration
- **VIF Threshold**: 10 (standard threshold for multicollinearity)
  - VIF < 5: No multicollinearity
  - VIF 5-10: Moderate multicollinearity
  - VIF > 10: High multicollinearity (remove feature)

## TASK DIRECTIVE

### Step 1: Implement Iterative VIF Filtering

**Script**: `phase4_vif_filter.py`

Create VIF calculation and iterative removal function:

```python
from statsmodels.stats.outliers_influence import variance_inflation_factor
import pandas as pd
import numpy as np

def calculate_vif_iterative(X, feature_names, shap_values, threshold=10):
    """
    Calculate VIF for features and iteratively remove high-VIF variables.

    Algorithm:
    1. Calculate VIF for all features
    2. Identify max VIF
    3. If max VIF > threshold:
       - Remove feature with max VIF
       - Recalculate VIF for remaining features
       - Repeat
    4. Return retained features

    Tiebreaker: If multiple features have VIF > threshold, remove the one
                with LOWEST SHAP importance (preserve signal).

    Parameters:
    -----------
    X : pd.DataFrame
        Feature matrix
    feature_names : List[str]
        Feature names
    shap_values : Dict[str, float]
        SHAP importance {feature: value}
    threshold : float
        VIF threshold (default 10)

    Returns:
    --------
    retained : List[str]
        Features with VIF < threshold
    removed : List[Tuple[str, float]]
        Removed features with their VIF values
    final_vif : Dict[str, float]
        Final VIF scores for retained features
    """
    X_current = X[feature_names].copy()
    removed = []

    while True:
        # Calculate VIF for current feature set
        vif_data = pd.DataFrame()
        vif_data["Feature"] = X_current.columns
        vif_data["VIF"] = [
            variance_inflation_factor(X_current.values, i)
            for i in range(X_current.shape[1])
        ]

        # Check if any VIF exceeds threshold
        max_vif = vif_data["VIF"].max()
        if max_vif <= threshold:
            break  # All features below threshold

        # Find feature with max VIF
        # If multiple have same VIF, remove one with lowest SHAP
        high_vif = vif_data[vif_data["VIF"] > threshold]
        if len(high_vif) > 0:
            # Tiebreaker: Remove lowest SHAP importance
            high_vif["SHAP"] = high_vif["Feature"].map(shap_values)
            to_remove = high_vif.sort_values(["VIF", "SHAP"], ascending=[False, True]).iloc[0]
            removed_feature = to_remove["Feature"]
            removed_vif = to_remove["VIF"]

            # Remove feature
            removed.append((removed_feature, removed_vif))
            X_current = X_current.drop(columns=[removed_feature])

            print(f"  Removed: {removed_feature} (VIF={removed_vif:.2f})")

    # Final VIF scores
    final_vif = dict(zip(vif_data["Feature"], vif_data["VIF"]))
    retained = list(X_current.columns)

    return retained, removed, final_vif
```

### Step 2: Apply VIF Filtering to Tier 1 Drivers

For each Tier 1 metric:
1. Load top 20 drivers from Module 4.2
2. Extract training data for those 20 features
3. Run iterative VIF filtering (threshold=10)
4. Save retained features and VIF report

**Script**: `phase4_apply_vif.py`

```python
import pickle
import json
import pandas as pd

# Load data
with open('<repo-root>/v1.0/models/causal_graphs/tier1/tier1_summary.json') as f:
    tier1_summary = json.load(f)

with open('<repo-root>/v1.0/models/causal_graphs/loaded_training_data.pkl', 'rb') as f:
    training_data = pickle.load(f)

with open('<repo-root>/v1.0/models/causal_graphs/loaded_shap_importance.pkl', 'rb') as f:
    shap_importance = pickle.load(f)

TIER1_METRICS = ['mean_years_schooling', 'infant_mortality', 'undernourishment']
VIF_THRESHOLD = 10

vif_results = {}

for metric in TIER1_METRICS:
    print(f"\n{'='*60}")
    print(f"VIF Filtering: {metric}")
    print(f"{'='*60}")

    # Get top 20 drivers from PC
    top_20_drivers = [feat for feat, _ in tier1_summary[metric]['top_20_drivers']]

    # Prepare data
    df = training_data[metric].dropna()
    X = df[top_20_drivers]

    # Get SHAP values
    shap_dict = dict(zip(
        shap_importance[metric]['feature'],
        shap_importance[metric]['shap_importance']
    ))

    # Run VIF filtering
    retained, removed, final_vif = calculate_vif_iterative(
        X, top_20_drivers, shap_dict, threshold=VIF_THRESHOLD
    )

    print(f"  Retained: {len(retained)} features")
    print(f"  Removed: {len(removed)} features")

    # Save results
    vif_results[metric] = {
        'original_features': top_20_drivers,
        'retained_features': retained,
        'removed_features': [(feat, float(vif)) for feat, vif in removed],
        'final_vif_scores': {k: float(v) for k, v in final_vif.items()},
        'num_retained': len(retained),
        'num_removed': len(removed)
    }

    # Save VIF report (CSV)
    vif_df = pd.DataFrame([
        {
            'feature': feat,
            'vif': final_vif.get(feat, 'removed'),
            'shap_importance': shap_dict.get(feat, 0),
            'status': 'retained' if feat in retained else 'removed'
        }
        for feat in top_20_drivers
    ])
    vif_df.to_csv(
        f'<repo-root>/v1.0/models/causal_graphs/tier1/{metric}_vif_report.csv',
        index=False
    )

# Save VIF results JSON
with open('<repo-root>/v1.0/models/causal_graphs/tier1/vif_filtering_results.json', 'w') as f:
    json.dump(vif_results, f, indent=2)

print("\n" + "="*60)
print("VIF Filtering Complete")
print("="*60)
```

### Step 3: Re-run PC Algorithm on VIF-Filtered Features

For each metric, run PC algorithm again using only VIF-retained features:

```python
# Re-run PC on VIF-filtered features
from phase4_pc_tier1 import run_pc_with_shap_priors

refined_results = {}

for metric in TIER1_METRICS:
    print(f"\nRe-running PC on VIF-filtered features: {metric}")

    # Get VIF-retained features
    retained_features = vif_results[metric]['retained_features']

    # Prepare data
    df = training_data[metric].dropna()
    X = df[retained_features].values

    # Get SHAP values for retained features
    shap_df = shap_importance[metric]
    shap_vals = shap_df.set_index('feature')['shap_importance'].reindex(retained_features).values

    # Run PC
    cg_refined, edge_weights_refined, num_edges = run_pc_with_shap_priors(
        X, retained_features, shap_vals, alpha=0.05
    )

    # Identify drivers again
    # (same logic as Module 4.2)
    target_idx = retained_features.index(metric) if metric in retained_features else -1
    drivers = []
    if target_idx >= 0:
        for (feat_i, feat_j), weight in edge_weights_refined.items():
            if feat_j == retained_features[target_idx]:
                drivers.append((feat_i, weight))

    drivers_sorted = sorted(drivers, key=lambda x: x[1], reverse=True)

    print(f"  Refined graph: {num_edges} edges, {len(drivers_sorted)} drivers")

    # Save refined results
    refined_results[metric] = {
        'num_features': len(retained_features),
        'num_edges': num_edges,
        'num_drivers': len(drivers_sorted),
        'top_drivers': [(feat, float(w)) for feat, w in drivers_sorted]
    }

    # Save refined causal graph
    with open(f'<repo-root>/v1.0/models/causal_graphs/tier1/{metric}_pc_refined.pkl', 'wb') as f:
        pickle.dump(cg_refined, f)

# Save refined summary
with open('<repo-root>/v1.0/models/causal_graphs/tier1/tier1_refined_summary.json', 'w') as f:
    json.dump(refined_results, f, indent=2)
```

## OUTPUTS

### Primary Outputs

1. **VIF Filtering Results**: `<repo-root>/v1.0/models/causal_graphs/tier1/vif_filtering_results.json`
   - Retained features per metric
   - Removed features with VIF scores
   - Final VIF scores for retained features

2. **VIF Reports** (CSV per metric):
   - `<repo-root>/v1.0/models/causal_graphs/tier1/{metric}_vif_report.csv`
   - Columns: [feature, vif, shap_importance, status]

3. **Refined Causal Graphs**:
   - `<repo-root>/v1.0/models/causal_graphs/tier1/{metric}_pc_refined.pkl`
   - Causal graphs after VIF filtering

4. **Refined Summary**: `<repo-root>/v1.0/models/causal_graphs/tier1/tier1_refined_summary.json`
   - Updated driver counts after VIF filtering
   - Top drivers from refined graphs

## SUCCESS CRITERIA

- [ ] VIF filtering removes 1-5 features per metric (expect ~15-18 retained from top 20)
- [ ] All retained features have VIF < 10
- [ ] Removed features are lag variants or highly correlated pairs (e.g., GDP_lag1 ↔ GDP_lag3)
- [ ] Re-running PC on VIF-filtered features succeeds for all 3 metrics
- [ ] Refined graphs have 5-20% fewer edges (cleaner, less redundant)
- [ ] Top drivers remain theoretically plausible

### Expected VIF Removals

**Typical removals across metrics**:
- GDP per capita lag variants (retain highest SHAP lag)
- Education enrollment levels (primary ↔ secondary correlation)
- Health expenditure variants (public ↔ total health spending)
- Population density ↔ urbanization rate

## INTEGRATION NOTES

### Handoff to Module 4.4 (Inter-Metric Analysis)
- VIF-filtered features are used for Granger causality testing
- Refined causal graphs provide within-metric structure

### Handoff to Module 4.5 (Effect Quantification)
- VIF-filtered drivers used for backdoor adjustment
- Ensures uncorrelated confounders for valid causal effect estimation

## ERROR HANDLING

### Common Issues

1. **VIF = inf (infinite)**:
   - Cause: Perfect multicollinearity (feature is linear combination of others)
   - Solution: Remove feature with VIF=inf immediately

2. **All features removed (VIF filtering too aggressive)**:
   - Cause: Threshold too low or all features highly correlated
   - Solution: Increase threshold to 15 or use PCA for dimensionality reduction

3. **No features removed**:
   - Cause: Features already orthogonal (unusual for development data)
   - Action: Proceed with original feature set

## VALIDATION CHECKS

```python
# Verify VIF thresholds met
with open('<repo-root>/v1.0/models/causal_graphs/tier1/vif_filtering_results.json') as f:
    vif_results = json.load(f)

for metric, data in vif_results.items():
    max_vif = max(data['final_vif_scores'].values())
    assert max_vif < 10, f"{metric} has retained feature with VIF={max_vif}"
    print(f"{metric}: Max VIF = {max_vif:.2f} ✓")

# Verify refined graphs have fewer edges
original_edges = {}
refined_edges = {}

with open('<repo-root>/v1.0/models/causal_graphs/tier1/tier1_summary.json') as f:
    original = json.load(f)
    for metric, data in original.items():
        original_edges[metric] = data['num_edges']

with open('<repo-root>/v1.0/models/causal_graphs/tier1/tier1_refined_summary.json') as f:
    refined = json.load(f)
    for metric, data in refined.items():
        refined_edges[metric] = data['num_edges']

for metric in TIER1_METRICS:
    reduction = (original_edges[metric] - refined_edges[metric]) / original_edges[metric] * 100
    print(f"{metric}: {original_edges[metric]} → {refined_edges[metric]} edges ({reduction:.1f}% reduction)")
```

## ESTIMATED RUNTIME
**15 minutes** (5 min VIF calculation, 10 min re-running PC on 3 metrics)

## DEPENDENCIES
- Module 4.2 (PC Discovery) must complete successfully

## PRIORITY
**HIGH** - Ensures non-redundant causal drivers for downstream effect quantification

## REFERENCES
- Kutner, M. H., et al. (2004). *Applied Linear Statistical Models*. McGraw-Hill. (VIF methodology)
- O'Brien, R. M. (2007). "A Caution Regarding Rules of Thumb for Variance Inflation Factors." *Quality & Quantity*, 41(5), 673-690.
