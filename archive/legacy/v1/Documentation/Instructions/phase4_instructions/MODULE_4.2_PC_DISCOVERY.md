# MODULE 4.2: Single-Metric Causal Discovery (PC Algorithm)

## OBJECTIVE
Execute the PC (Peter-Clark) constraint-based causal discovery algorithm on Tier 1 metrics (mean_years_schooling, infant_mortality, undernourishment) using SHAP values as edge priors to identify true causal drivers of quality-of-life outcomes.

## CONTEXT
The PC algorithm learns causal graph structure by testing conditional independence relationships between variables. Unlike correlation or predictive modeling, PC identifies directed causal relationships (A → B) based on the principle that if A causes B, then A and B are correlated, but conditioning on A's causes should render A and B independent. SHAP importance from Phase 3 provides edge priors—features with high SHAP values are more likely to have causal edges. Starting with Tier 1 metrics (highest validation R²: 0.821-0.905) validates methodology before extending to all metrics.

## INPUTS

### From Module 4.1
- **Loaded Training Data**: `<repo-root>/v1.0/models/causal_graphs/loaded_training_data.pkl`
  - Dictionary: {metric: DataFrame[features + target]}
  - Expected shapes: 6,500-7,000 rows × 24-43 columns (after dropna)
- **SHAP Importance**: `<repo-root>/v1.0/models/causal_graphs/loaded_shap_importance.pkl`
  - Dictionary: {metric: DataFrame[feature, shap_value]}
- **Configuration**: `<repo-root>/v1.0/models/causal_graphs/phase4_config.json`

### Tier 1 Metrics (Priority Execution)
1. **mean_years_schooling** (38 features, Val R²=0.905)
2. **infant_mortality** (42 features, Val R²=0.853)
3. **undernourishment** (40 features, Val R²=0.830)

## TASK DIRECTIVE

### Step 1: Implement PC Algorithm with SHAP Priors

**Script**: `run_pc_algorithm.py`

Create the core PC execution function:

```python
def run_pc_with_shap_priors(X, feature_names, shap_values, alpha=0.05):
    """
    Run PC algorithm with SHAP-weighted edge priors.

    Parameters:
    -----------
    X : numpy.ndarray
        Feature matrix (n_samples × n_features)
    feature_names : List[str]
        Feature names corresponding to X columns
    shap_values : numpy.ndarray
        SHAP importance scores (length = n_features)
    alpha : float
        Significance level for conditional independence tests (default 0.05)

    Returns:
    --------
    cg : CausalGraph
        Discovered causal graph with directed edges
    edge_weights : Dict[Tuple[str, str], float]
        Edge weights based on SHAP importance
    num_edges : int
        Total discovered edges
    """
    from causallearn.search.ConstraintBased.PC import pc
    from causallearn.utils.cit import fisherz

    # Normalize SHAP values to [0, 1] for edge weighting
    shap_normalized = (shap_values - shap_values.min()) / (shap_values.max() - shap_values.min())

    # Run PC algorithm
    # Fisher-Z test: Uses partial correlations for continuous data
    # Stable PC: Order-independent variant (deterministic results)
    # uc_rule=0: Use Meek's orientation rules for edge direction
    cg = pc(
        X,
        alpha=alpha,              # 0.05 = 95% confidence for independence
        indep_test=fisherz,       # Partial correlation test
        stable=True,              # Stable PC (order-independent)
        uc_rule=0,                # Meek's rules for orientation
        uc_priority=2,            # Prioritize by statistical significance
        background_knowledge=None # No manual constraints
    )

    # Extract edges and compute weights
    edge_weights = {}
    edges_list = cg.G.get_graph_edges()

    for i, j in edges_list:
        # Average SHAP importance of both nodes as edge weight
        weight = (shap_normalized[i] + shap_normalized[j]) / 2
        edge_weights[(feature_names[i], feature_names[j])] = float(weight)

    return cg, edge_weights, len(edges_list)
```

**Key Parameters**:
- **alpha=0.05**: 95% confidence threshold for independence tests
  - Lower alpha (0.01) = stricter, fewer edges, higher confidence
  - Higher alpha (0.10) = more permissive, more edges, lower confidence
- **indep_test=fisherz**: Fisher-Z test for continuous data (partial correlation)
- **stable=True**: Guarantees deterministic results (order-independent)

### Step 2: Execute PC on Tier 1 Metrics

**Script**: `phase4_pc_tier1.py`

For each Tier 1 metric:
1. Load training data with causal features only
2. Remove rows with NaN (critical: PC requires complete data)
3. Normalize SHAP values to [0, 1]
4. Run PC algorithm
5. Identify features with edges to target metric (causal drivers)
6. Rank drivers by SHAP-weighted edge strength
7. Save causal graph and results

**Expected Execution Flow**:
```python
import pickle
import json
import pandas as pd
import numpy as np
from datetime import datetime

# Load data from Module 4.1
with open('<repo-root>/v1.0/models/causal_graphs/loaded_training_data.pkl', 'rb') as f:
    training_data = pickle.load(f)

with open('<repo-root>/v1.0/models/causal_graphs/loaded_shap_importance.pkl', 'rb') as f:
    shap_importance = pickle.load(f)

# Configuration
TIER1_METRICS = ['mean_years_schooling', 'infant_mortality', 'undernourishment']
ALPHA = 0.05
results = {}

for metric in TIER1_METRICS:
    print(f"\n{'='*60}")
    print(f"Running PC Algorithm: {metric}")
    print(f"{'='*60}")

    # Prepare data
    df = training_data[metric].dropna()  # CRITICAL: Remove NaN
    feature_cols = [col for col in df.columns if col != metric]
    X = df[feature_cols].values
    y = df[metric].values

    # Get SHAP values
    shap_df = shap_importance[metric]
    shap_vals = shap_df.set_index('feature')['shap_importance'].reindex(feature_cols).values

    # Run PC algorithm
    start_time = datetime.now()
    cg, edge_weights, num_edges = run_pc_with_shap_priors(
        X, feature_cols, shap_vals, alpha=ALPHA
    )
    runtime = (datetime.now() - start_time).total_seconds()

    print(f"Discovered {num_edges} edges among {len(feature_cols)} features")
    print(f"Runtime: {runtime:.1f} seconds")

    # Identify causal drivers (features with edges to target)
    # Target metric should be included in feature_cols for PC
    # Extract edges pointing to target
    target_idx = feature_cols.index(metric) if metric in feature_cols else -1

    drivers = []
    if target_idx >= 0:
        for (feat_i, feat_j), weight in edge_weights.items():
            # Check if edge points to target metric
            if feat_j == feature_cols[target_idx]:
                drivers.append((feat_i, weight))

    # Sort by edge weight (SHAP-based importance)
    drivers_sorted = sorted(drivers, key=lambda x: x[1], reverse=True)

    print(f"\nTop 10 Causal Drivers:")
    for feat, weight in drivers_sorted[:10]:
        print(f"  {feat}: {weight:.4f}")

    # Save results
    results[metric] = {
        'num_features': len(feature_cols),
        'num_edges': num_edges,
        'num_drivers': len(drivers_sorted),
        'top_20_drivers': [(feat, float(weight)) for feat, weight in drivers_sorted[:20]],
        'all_edges': [(f1, f2, float(w)) for (f1, f2), w in edge_weights.items()],
        'runtime_seconds': runtime,
        'alpha': ALPHA,
        'samples_used': len(df),
        'timestamp': datetime.now().isoformat()
    }

    # Save causal graph (pickle)
    with open(f'<repo-root>/v1.0/models/causal_graphs/tier1/{metric}_pc_graph.pkl', 'wb') as f:
        pickle.dump(cg, f)

    # Save edge weights (CSV for inspection)
    edge_df = pd.DataFrame([
        {'source': f1, 'target': f2, 'weight': w}
        for (f1, f2), w in edge_weights.items()
    ])
    edge_df.to_csv(f'<repo-root>/v1.0/models/causal_graphs/tier1/{metric}_edges.csv', index=False)

# Save summary JSON
with open('<repo-root>/v1.0/models/causal_graphs/tier1/tier1_summary.json', 'w') as f:
    json.dump(results, f, indent=2)

print("\n" + "="*60)
print("Tier 1 PC Discovery Complete")
print("="*60)
```

### Step 3: Interpret PC Results

For each metric, analyze:
1. **Edge Count**: Total discovered relationships (expect 15-50 per metric)
2. **Driver Count**: Features with edges to target (expect 10-25)
3. **Edge Types**:
   - Directed (A → B): A causes B
   - Undirected (A — B): Cannot determine direction (possible confounding)
   - No edge: A and B are conditionally independent

**Expected Patterns**:
- **Mean Years Schooling**: Drivers likely include lagged GDP, government education expenditure, secondary enrollment
- **Infant Mortality**: Drivers likely include health expenditure, physician density, water/sanitation access
- **Undernourishment**: Drivers likely include agricultural productivity, food prices, rural development

## OUTPUTS

### Primary Outputs

1. **Causal Graphs** (pickled CausalGraph objects):
   - `<repo-root>/v1.0/models/causal_graphs/tier1/mean_years_schooling_pc_graph.pkl`
   - `<repo-root>/v1.0/models/causal_graphs/tier1/infant_mortality_pc_graph.pkl`
   - `<repo-root>/v1.0/models/causal_graphs/tier1/undernourishment_pc_graph.pkl`

2. **Edge Lists** (CSV for inspection):
   - `<repo-root>/v1.0/models/causal_graphs/tier1/{metric}_edges.csv`
   - Columns: [source, target, weight]

3. **Tier 1 Summary** (JSON):
   - `<repo-root>/v1.0/models/causal_graphs/tier1/tier1_summary.json`
   - Contains: num_features, num_edges, top_20_drivers, runtime, alpha

### Intermediate Outputs

4. **Console Logs**: Save stdout to log file for debugging
   - `<repo-root>/v1.0/models/causal_graphs/tier1/pc_execution.log`

## SUCCESS CRITERIA

- [ ] PC algorithm completes for all 3 Tier 1 metrics without errors
- [ ] Each metric discovers 10-50 edges (reasonable range for 38-42 features)
- [ ] Each metric identifies 8-25 causal drivers (features with edges to target)
- [ ] Runtime per metric: 5-15 minutes (acceptable for n≈7,000 samples)
- [ ] All discovered DAGs are acyclic (verify with `networkx.is_directed_acyclic_graph`)
- [ ] Top drivers have theoretical plausibility (compare to development economics literature)
- [ ] Edge weights correlate with SHAP importance (Pearson r > 0.6)

## INTEGRATION NOTES

### Handoff to Module 4.3 (VIF Filtering)
- `tier1_summary.json` contains `top_20_drivers` for each metric
- These top 20 drivers will undergo VIF filtering to remove multicollinearity
- Causal graphs will be re-run on VIF-filtered features

### Parallelization Opportunity
- PC algorithm is embarrassingly parallel across metrics
- Can run 3 separate processes for 3 metrics
- Expected speedup: 3× (30-45 min sequential → 10-15 min parallel)

## ERROR HANDLING

### Common Issues

1. **Singular Matrix Error**:
   - Cause: Perfect multicollinearity in features
   - Solution: Remove constant features or perfectly correlated pairs before PC

2. **Memory Error (n > 10,000 samples)**:
   - Cause: PC algorithm quadratic in sample size
   - Solution: Subsample to 8,000 rows if needed

3. **Zero Edges Discovered**:
   - Cause: Alpha too strict (0.01) or features truly independent
   - Solution: Increase alpha to 0.10, verify feature selection

4. **Cycle in DAG**:
   - Cause: PC failed to orient all edges (latent confounder suspected)
   - Solution: Use FCI algorithm (handles latent confounders) instead of PC

## VALIDATION CHECKS

After execution, verify:

```python
# Check DAG acyclicity
import networkx as nx
for metric in TIER1_METRICS:
    with open(f'<repo-root>/v1.0/models/causal_graphs/tier1/{metric}_pc_graph.pkl', 'rb') as f:
        cg = pickle.load(f)
    G = nx.DiGraph(cg.G.get_graph_edges())
    assert nx.is_directed_acyclic_graph(G), f"{metric} has cycles!"
    print(f"{metric}: ✓ Acyclic DAG ({len(G.edges)} edges)")

# Check driver counts
with open('<repo-root>/v1.0/models/causal_graphs/tier1/tier1_summary.json') as f:
    summary = json.load(f)
for metric, data in summary.items():
    assert 5 <= data['num_drivers'] <= 30, f"{metric} has unusual driver count: {data['num_drivers']}"
    print(f"{metric}: {data['num_drivers']} drivers ✓")
```

## ESTIMATED RUNTIME
**30-45 minutes** (10-15 min per metric sequential, or 10-15 min if parallelized)

## DEPENDENCIES
- Module 4.1 (Setup) must complete successfully

## PRIORITY
**HIGH** - Core causal discovery step, blocking all downstream analysis

## REFERENCES
- Spirtes, P., Glymour, C., & Scheines, R. (2000). *Causation, Prediction, and Search*. MIT Press.
- Zhang, K., et al. (2016). "Causal Discovery with Linear Non-Gaussian Models under Measurement Error."
- Phase 4 Original Instructions: `<repo-root>/v1.0/Documentation/Instructions/phase4_instructions.md` (Step 4.2)
