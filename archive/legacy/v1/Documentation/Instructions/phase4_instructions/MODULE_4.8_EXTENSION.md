# MODULE 4.8: Extension to All 8 Metrics

## OBJECTIVE
Extend validated causal discovery pipeline from Tier 1 (3 metrics) to all 8 QOL metrics, generating complete causal knowledge base for policy simulation and Phase 6 dashboard integration.

## CONTEXT
Modules 4.1-4.7 established methodology and validated results on Tier 1 high-confidence metrics (mean_years_schooling, infant_mortality, undernourishment). Module 4.8 applies this validated pipeline to remaining 5 metrics (Tier 2: internet_users, gini, gdp_per_capita; Tier 3: life_expectancy, homicide). Tier 3 metrics (lower R²) may have weaker causal signals, requiring sensitivity analysis and possible alpha relaxation.

## INPUTS

### From Module 4.1
- **Loaded Models**: `<repo-root>/v1.0/models/causal_graphs/loaded_models.pkl`
- **Training Data**: `<repo-root>/v1.0/models/causal_graphs/loaded_training_data.pkl`
- **SHAP Importance**: `<repo-root>/v1.0/models/causal_graphs/loaded_shap_importance.pkl`

### From Module 4.7
- **Validation Report**: `<repo-root>/v1.0/models/causal_graphs/validation_report.json`
  - Must show PASS status before proceeding

### Metric Tiers
```python
TIER1_METRICS = ['mean_years_schooling', 'infant_mortality', 'undernourishment']  # DONE
TIER2_METRICS = ['internet_users', 'gini', 'gdp_per_capita']  # Medium confidence
TIER3_METRICS = ['life_expectancy', 'homicide']  # Lower confidence
```

## TASK DIRECTIVE

### Step 1: Verify Tier 1 Validation

**Script**: `phase4_extension_prerequisite.py`

```python
import json

# Check validation report
with open('<repo-root>/v1.0/models/causal_graphs/validation_report.json') as f:
    validation = json.load(f)

if validation['overall_status'] != 'PASS':
    print("✗ ERROR: Tier 1 validation failed. Fix issues before extending.")
    print("Review: /models/causal_graphs/validation_report.json")
    exit(1)

print("✓ Tier 1 validation passed. Proceeding with extension to all 8 metrics.")
```

### Step 2: Extend PC Discovery to Tier 2 & 3

**Script**: `phase4_extend_pc_all_metrics.py`

Reuse Module 4.2 pipeline for remaining 5 metrics:

```python
import pickle
import json
import pandas as pd
import numpy as np
from datetime import datetime
from phase4_pc_tier1 import run_pc_with_shap_priors  # Reuse function

# Load data
with open('<repo-root>/v1.0/models/causal_graphs/loaded_training_data.pkl', 'rb') as f:
    training_data = pickle.load(f)

with open('<repo-root>/v1.0/models/causal_graphs/loaded_shap_importance.pkl', 'rb') as f:
    shap_importance = pickle.load(f)

TIER2_METRICS = ['internet_users', 'gini', 'gdp_per_capita']
TIER3_METRICS = ['life_expectancy', 'homicide']
ALL_REMAINING = TIER2_METRICS + TIER3_METRICS

# Configuration
ALPHA_TIER2 = 0.05  # Same as Tier 1
ALPHA_TIER3 = 0.10  # Relaxed for weaker metrics (more permissive)

results_all = {}

# Process Tier 2 (medium confidence)
print("\n" + "="*60)
print("TIER 2 METRICS (Medium Confidence)")
print("="*60)

for metric in TIER2_METRICS:
    print(f"\nRunning PC: {metric}")

    # Prepare data
    df = training_data[metric].dropna()
    feature_cols = [col for col in df.columns if col != metric]
    X = df[feature_cols].values

    # Get SHAP values
    shap_df = shap_importance[metric]
    shap_vals = shap_df.set_index('feature')['shap_importance'].reindex(feature_cols).values

    # Run PC
    start_time = datetime.now()
    cg, edge_weights, num_edges = run_pc_with_shap_priors(
        X, feature_cols, shap_vals, alpha=ALPHA_TIER2
    )
    runtime = (datetime.now() - start_time).total_seconds()

    # Extract drivers
    target_idx = feature_cols.index(metric) if metric in feature_cols else -1
    drivers = []
    if target_idx >= 0:
        for (feat_i, feat_j), weight in edge_weights.items():
            if feat_j == feature_cols[target_idx]:
                drivers.append((feat_i, weight))

    drivers_sorted = sorted(drivers, key=lambda x: x[1], reverse=True)

    print(f"  Edges: {num_edges}, Drivers: {len(drivers_sorted)}, Runtime: {runtime:.1f}s")

    # Save
    results_all[metric] = {
        'tier': 2,
        'alpha': ALPHA_TIER2,
        'num_features': len(feature_cols),
        'num_edges': num_edges,
        'num_drivers': len(drivers_sorted),
        'top_20_drivers': [(feat, float(weight)) for feat, weight in drivers_sorted[:20]],
        'runtime_seconds': runtime
    }

    with open(f'<repo-root>/v1.0/models/causal_graphs/tier2/{metric}_pc_graph.pkl', 'wb') as f:
        pickle.dump(cg, f)

# Process Tier 3 (lower confidence, relaxed alpha)
print("\n" + "="*60)
print("TIER 3 METRICS (Lower Confidence - Relaxed Alpha=0.10)")
print("="*60)

for metric in TIER3_METRICS:
    print(f"\nRunning PC: {metric}")

    # Same as Tier 2, but with alpha=0.10
    df = training_data[metric].dropna()
    feature_cols = [col for col in df.columns if col != metric]
    X = df[feature_cols].values

    shap_df = shap_importance[metric]
    shap_vals = shap_df.set_index('feature')['shap_importance'].reindex(feature_cols).values

    start_time = datetime.now()
    cg, edge_weights, num_edges = run_pc_with_shap_priors(
        X, feature_cols, shap_vals, alpha=ALPHA_TIER3  # Relaxed
    )
    runtime = (datetime.now() - start_time).total_seconds()

    # Extract drivers
    target_idx = feature_cols.index(metric) if metric in feature_cols else -1
    drivers = []
    if target_idx >= 0:
        for (feat_i, feat_j), weight in edge_weights.items():
            if feat_j == feature_cols[target_idx]:
                drivers.append((feat_i, weight))

    drivers_sorted = sorted(drivers, key=lambda x: x[1], reverse=True)

    print(f"  Edges: {num_edges}, Drivers: {len(drivers_sorted)}, Runtime: {runtime:.1f}s")

    # Save
    results_all[metric] = {
        'tier': 3,
        'alpha': ALPHA_TIER3,
        'num_features': len(feature_cols),
        'num_edges': num_edges,
        'num_drivers': len(drivers_sorted),
        'top_20_drivers': [(feat, float(weight)) for feat, weight in drivers_sorted[:20]],
        'runtime_seconds': runtime
    }

    with open(f'<repo-root>/v1.0/models/causal_graphs/tier3/{metric}_pc_graph.pkl', 'wb') as f:
        pickle.dump(cg, f)

# Save combined summary
with open('<repo-root>/v1.0/models/causal_graphs/all_metrics_summary.json', 'w') as f:
    json.dump(results_all, f, indent=2)

print("\n" + "="*60)
print(f"PC Discovery Complete: {len(results_all)} metrics")
print("="*60)
```

### Step 3: Apply VIF Filtering to All Metrics

**Script**: `phase4_extend_vif_all_metrics.py`

Reuse Module 4.3 VIF filtering logic:

```python
from phase4_vif_filter import calculate_vif_iterative

vif_results_all = {}

for metric in ALL_REMAINING:
    print(f"\nVIF Filtering: {metric}")

    # Load top 20 drivers
    with open(f'<repo-root>/v1.0/models/causal_graphs/all_metrics_summary.json') as f:
        summary = json.load(f)

    top_20_drivers = [feat for feat, _ in summary[metric]['top_20_drivers']]

    # Prepare data
    df = training_data[metric].dropna()
    X = df[top_20_drivers]

    # Get SHAP values
    shap_dict = dict(zip(
        shap_importance[metric]['feature'],
        shap_importance[metric]['shap_importance']
    ))

    # Run VIF
    retained, removed, final_vif = calculate_vif_iterative(
        X, top_20_drivers, shap_dict, threshold=10
    )

    vif_results_all[metric] = {
        'retained_features': retained,
        'removed_features': [(feat, float(vif)) for feat, vif in removed],
        'final_vif_scores': {k: float(v) for k, v in final_vif.items()}
    }

    print(f"  Retained: {len(retained)}, Removed: {len(removed)}")

    # Re-run PC on VIF-filtered features
    df_vif = training_data[metric].dropna()
    X_vif = df_vif[retained].values
    shap_vals = shap_dict.reindex(retained).values

    tier = summary[metric]['tier']
    alpha = 0.05 if tier <= 2 else 0.10

    cg_refined, edge_weights_refined, num_edges = run_pc_with_shap_priors(
        X_vif, retained, shap_vals, alpha=alpha
    )

    # Save refined graph
    tier_dir = f'tier{tier}'
    with open(f'<repo-root>/v1.0/models/causal_graphs/{tier_dir}/{metric}_pc_refined.pkl', 'wb') as f:
        pickle.dump(cg_refined, f)

# Merge with Tier 1 VIF results
with open('<repo-root>/v1.0/models/causal_graphs/tier1/vif_filtering_results.json') as f:
    tier1_vif = json.load(f)

vif_results_all.update(tier1_vif)

# Save combined VIF results
with open('<repo-root>/v1.0/models/causal_graphs/vif_filtering_all_metrics.json', 'w') as f:
    json.dump(vif_results_all, f, indent=2)
```

### Step 4: Quantify Effects for All Metrics

**Script**: `phase4_extend_effects_all_metrics.py`

Reuse Module 4.5 effect quantification:

```python
from phase4_quantify_effects import estimate_causal_effect_backdoor

causal_effects_all = {}

for metric in ALL_REMAINING:
    print(f"\nQuantifying Effects: {metric}")

    # Get VIF-retained drivers
    retained_features = vif_results_all[metric]['retained_features']

    # Load data
    df = training_data[metric].dropna()
    y = df[metric]

    metric_effects = {}

    for treatment_feature in retained_features[:10]:
        confounders = [f for f in retained_features[:10] if f != treatment_feature]

        effect, ci_lower, ci_upper, p_value = estimate_causal_effect_backdoor(
            df, y, treatment_feature, confounders, n_bootstrap=1000
        )

        metric_effects[treatment_feature] = {
            'causal_effect': float(effect),
            'ci_lower': float(ci_lower),
            'ci_upper': float(ci_upper),
            'p_value': float(p_value),
            'significant': (ci_lower * ci_upper > 0)
        }

    causal_effects_all[metric] = metric_effects

# Merge with Tier 1 effects
with open('<repo-root>/v1.0/models/causal_graphs/tier1/causal_effects_quantified.json') as f:
    tier1_effects = json.load(f)

causal_effects_all.update(tier1_effects)

# Save combined effects
with open('<repo-root>/v1.0/models/causal_graphs/causal_effects_all_metrics.json', 'w') as f:
    json.dump(causal_effects_all, f, indent=2)
```

### Step 5: Update Policy Simulator with All Metrics

**Script**: `phase4_extend_simulator.py`

```python
from policy_simulator import PolicySimulator
import networkx as nx

# Load all refined causal graphs
all_metrics = TIER1_METRICS + TIER2_METRICS + TIER3_METRICS
causal_graphs_all = {}

for metric in all_metrics:
    # Determine tier
    if metric in TIER1_METRICS:
        tier_dir = 'tier1'
    elif metric in TIER2_METRICS:
        tier_dir = 'tier2'
    else:
        tier_dir = 'tier3'

    with open(f'<repo-root>/v1.0/models/causal_graphs/{tier_dir}/{metric}_pc_refined.pkl', 'rb') as f:
        cg = pickle.load(f)
        causal_graphs_all[metric] = nx.DiGraph(cg.G.get_graph_edges())

# Load causal effects
with open('<repo-root>/v1.0/models/causal_graphs/causal_effects_all_metrics.json') as f:
    causal_effects_all = json.load(f)

# Load inter-metric graph
inter_metric_graph = nx.read_gpickle(
    '<repo-root>/v1.0/models/causal_graphs/inter_metric_graph.pkl'
)

# Create full simulator
simulator_full = PolicySimulator(
    causal_graphs=causal_graphs_all,
    causal_effects=causal_effects_all,
    inter_metric_graph=inter_metric_graph
)

# Save
with open('<repo-root>/v1.0/models/policy_simulator/policy_simulator_full.pkl', 'wb') as f:
    pickle.dump(simulator_full, f)

# Export API spec
api_spec = simulator_full.export_for_dashboard()
with open('<repo-root>/v1.0/models/policy_simulator/api_specification_full.json', 'w') as f:
    json.dump(api_spec, f, indent=2)

print("\nFull PolicySimulator created:")
print(f"  Metrics: {len(causal_graphs_all)}")
print(f"  Total causal drivers: {sum(len(effects) for effects in causal_effects_all.values())}")
```

### Step 6: Generate Final Visualizations

Extend Module 4.7 visualizations to all 8 metrics:

```python
# DAGs for all metrics
for metric in all_metrics:
    # (Same visualization code as Module 4.7)
    # Generate {metric}_dag.png, {metric}_effects.png

print(f"Generated visualizations for all {len(all_metrics)} metrics")
```

## OUTPUTS

### Primary Outputs

1. **All Metrics PC Summary**: `<repo-root>/v1.0/models/causal_graphs/all_metrics_summary.json`
   - PC results for all 8 metrics

2. **VIF Results**: `<repo-root>/v1.0/models/causal_graphs/vif_filtering_all_metrics.json`
   - VIF filtering for all 8 metrics

3. **Causal Effects**: `<repo-root>/v1.0/models/causal_graphs/causal_effects_all_metrics.json`
   - Quantified effects for all 8 metrics

4. **Full Policy Simulator**: `<repo-root>/v1.0/models/policy_simulator/policy_simulator_full.pkl`
   - Simulator with all 8 metrics

5. **Full API Spec**: `<repo-root>/v1.0/models/policy_simulator/api_specification_full.json`
   - Phase 6 integration spec

6. **Visualizations** (16 PNG files):
   - 8 DAG plots: `{metric}_dag.png`
   - 8 Effect plots: `{metric}_effects.png`

## SUCCESS CRITERIA

- [ ] PC discovery completes for all 5 remaining metrics (Tier 2 + Tier 3)
- [ ] VIF filtering applied to all 8 metrics
- [ ] Causal effects quantified for all 8 metrics (top 10 drivers each)
- [ ] Full policy simulator created with 8 metrics
- [ ] 16 visualizations generated (8 DAGs + 8 effect plots)
- [ ] All metrics pass validation tests (DAG acyclicity, effect sign consistency)

### Expected Outcomes by Tier

**Tier 2** (internet_users, gini, gdp_per_capita):
- 10-25 causal drivers per metric
- 50-70% significant effects
- Moderate literature alignment (60-80%)

**Tier 3** (life_expectancy, homicide):
- 5-15 causal drivers per metric (weaker signal)
- 30-50% significant effects (lower due to weak predictive R²)
- Lower literature alignment (40-60%)
- May require alpha=0.10 for sufficient edges

## INTEGRATION NOTES

### Handoff to Phase 6
- Full simulator ready for dashboard integration
- API spec defines all available interventions
- Visualizations for "Causal Discovery Explorer" tab

### Handoff to Phase 5 (if applicable)
- Complete causal knowledge base for multi-output model
- Inter-metric relationships for joint prediction

## ERROR HANDLING

### Common Issues for Tier 3 Metrics

1. **Few Edges Discovered (< 5)**:
   - Cause: Alpha too strict for weak metrics
   - Solution: Already using alpha=0.10 (relaxed)
   - Alternative: Report as "insufficient causal signal"

2. **Low Significant Effects (< 30%)**:
   - Expected for homicide (R²=0.358)
   - Document as limitation rather than failure

3. **Cycles in DAG (Tier 3)**:
   - More likely with alpha=0.10 (more permissive)
   - Solution: Use FCI algorithm instead of PC

## VALIDATION CHECKS

```python
# Verify all 8 metrics processed
assert len(causal_graphs_all) == 8, f"Missing metrics: {8 - len(causal_graphs_all)}"

# Verify simulator has all metrics
available_metrics = simulator_full.export_for_dashboard()['available_metrics']
assert len(available_metrics) == 8, f"Simulator missing metrics"

print("✓ All 8 metrics processed and integrated")

# Check driver counts
for metric, effects in causal_effects_all.items():
    driver_count = len(effects)
    print(f"{metric}: {driver_count} drivers")
    assert driver_count >= 5, f"{metric} has too few drivers ({driver_count})"
```

## ESTIMATED RUNTIME
**90-120 minutes** (Tier 2: 45 min, Tier 3: 30 min, integration: 30 min, viz: 15 min)

Can be parallelized by metric (5 processes → 30-40 minutes total)

## DEPENDENCIES
- Module 4.7 (Validation) must show PASS status
- All Modules 4.1-4.6 completed successfully

## PRIORITY
**MEDIUM** - Extends validated methodology to full dataset

## REFERENCES
- Same as Modules 4.2-4.6 (PC algorithm, VIF, backdoor adjustment, do-calculus)
