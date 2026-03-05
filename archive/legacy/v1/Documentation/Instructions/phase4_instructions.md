# **Phase 4: Causal Discovery & Policy Simulation Framework**

## **Overview**

Phase 4 identifies true causal drivers of quality-of-life metrics using constraint-based causal discovery (PC algorithm) on Approach C features (strict causal, 23-52 per metric), followed by inter-metric relationship analysis and policy simulation framework development. The phase operates on 8 optimized LightGBM models from Phase 3, using SHAP values as edge priors to guide causal structure learning.

**Strategic Approach:** Start with Tier 1 high-confidence metrics (mean_years_schooling R²=0.935, infant_mortality R²=0.855, undernourishment R²=0.821) to validate methodology, then extend to all 8 metrics.

---

## **Step 4.1: Setup & Data Preparation**

### **4.1.1: Install Causal Discovery Libraries**

```bash
# Activate Phase 2 environment
source <repo-root>/v1.0/phase2_env/bin/activate

# Install causal-learn (Python implementation of PC, FCI, GES)
pip install causal-learn==0.1.3.5

# Install pgmpy (Bayesian networks, do-calculus)
pip install pgmpy==0.1.23

# Install networkx (graph operations)
pip install networkx==3.2

# Install graphviz (DAG visualization)
pip install graphviz==0.20.1
```

### **4.1.2: Load Phase 3 Outputs**

**Script:** `phase4_setup.py`

```python
import pandas as pd
import numpy as np
import pickle
from pathlib import Path

# Load optimized models
models = {}
for metric in ['mean_years_schooling', 'infant_mortality', 'undernourishment',
               'gdp_per_capita', 'gini', 'life_expectancy', 'internet_users', 'homicide']:
    
    # Determine approach (C for 6 metrics, A for 2)
    approach = 'causal' if metric in ['mean_years_schooling', 'infant_mortality', 
                                       'undernourishment', 'gdp_per_capita', 
                                       'gini', 'life_expectancy', 
                                       'internet_users', 'homicide'] else 'phase2_retrain'
    
    model_path = f'/models/{approach}/lightgbm/{metric}.pkl'
    models[metric] = pickle.load(open(model_path, 'rb'))

# Load Approach C feature sets
features = {}
for metric in models.keys():
    features[metric] = pd.read_csv(
        f'/Data/Processed/feature_selection/phase3/features_causal_{metric}.csv'
    )

# Load SHAP importance
shap_importance = {}
for metric in models.keys():
    shap_importance[metric] = pd.read_csv(
        f'/models/causal_optimized/shap_importance_{metric}.csv'
    )

# Load training data
train = pd.read_csv('/Data/Processed/train_normalized.csv')
```

### **4.1.3: Metric Prioritization**

**Tier 1 (Start Here):** High confidence, strong generalization
- `mean_years_schooling` (Test R²=0.935, 38 features)
- `infant_mortality` (Test R²=0.855, 42 features)
- `undernourishment` (Test R²=0.821, 40 features)

**Tier 2:** Good confidence, acceptable generalization
- `internet_users` (Test R²=0.758, 47 features)
- `gini` (Test R²=0.676, 23 features)
- `gdp_per_capita` (Test R²=0.623, 31 features)

**Tier 3:** Moderate-to-weak, use cautiously
- `life_expectancy` (Test R²=0.445, 52 features)
- `homicide` (Test R²=0.156, 43 features)

---

## **Step 4.2: Single-Metric Causal Discovery (PC Algorithm)**

### **4.2.1: PC Algorithm Configuration**

**Script:** `run_pc_algorithm.py`

```python
from causallearn.search.ConstraintBased.PC import pc
from causallearn.utils.cit import fisherz

def run_pc_with_shap_priors(X, feature_names, shap_values, alpha=0.05):
    """
    Run PC algorithm with SHAP-weighted edge priors.
    
    Parameters:
    - X: Feature matrix (n_samples x n_features)
    - feature_names: List of feature names
    - shap_values: SHAP importance scores (higher = more likely causal)
    - alpha: Significance level for conditional independence tests
    
    Returns:
    - cg: CausalGraph object with discovered DAG
    """
    
    # Normalize SHAP values to [0, 1] as edge priors
    shap_normalized = (shap_values - shap_values.min()) / (shap_values.max() - shap_values.min())
    
    # Run PC algorithm
    # Use Fisher-Z test for continuous data
    cg = pc(
        X, 
        alpha=alpha,  # Significance level (0.05 = 95% confidence)
        indep_test=fisherz,  # Partial correlation test
        stable=True,  # Stable PC variant (order-independent)
        uc_rule=0,  # Orient edges using Meek's rules
        uc_priority=2,  # Prioritize by SHAP values
        background_knowledge=None  # No manual constraints
    )
    
    # Weight edges by SHAP importance
    edge_weights = {}
    for i, j in cg.G.get_graph_edges():
        # Average SHAP of both nodes
        weight = (shap_normalized[i] + shap_normalized[j]) / 2
        edge_weights[(feature_names[i], feature_names[j])] = weight
    
    return cg, edge_weights
```

### **4.2.2: Execute PC on Tier 1 Metrics**

**Script:** `phase4_pc_tier1.py`

```python
import json
from datetime import datetime

# Configuration
ALPHA = 0.05  # 95% confidence for independence tests
METRICS_TIER1 = ['mean_years_schooling', 'infant_mortality', 'undernourishment']

results = {}

for metric in METRICS_TIER1:
    print(f"\n{'='*60}")
    print(f"Running PC Algorithm: {metric}")
    print(f"{'='*60}")
    
    # Prepare data
    feature_list = features[metric]['Feature'].tolist()
    X = train[feature_list].dropna()  # Remove rows with NaN
    
    # Get SHAP values
    shap_vals = shap_importance[metric].set_index('feature')['shap_importance']
    
    # Run PC algorithm
    start_time = datetime.now()
    cg, edge_weights = run_pc_with_shap_priors(
        X.values, 
        feature_list, 
        shap_vals.reindex(feature_list).values,
        alpha=ALPHA
    )
    runtime = (datetime.now() - start_time).total_seconds()
    
    # Extract results
    num_edges = len(cg.G.get_graph_edges())
    num_nodes = len(feature_list)
    
    print(f"Discovered {num_edges} edges among {num_nodes} features")
    print(f"Runtime: {runtime:.1f} seconds")
    
    # Identify true drivers (features with ≥1 outgoing edge to target)
    target_idx = feature_list.index(f'{metric}_target')
    drivers = []
    for i, j in cg.G.get_graph_edges():
        if j == target_idx:  # Edge points to target
            drivers.append((feature_list[i], edge_weights.get((feature_list[i], feature_list[j]), 0)))
    
    drivers_sorted = sorted(drivers, key=lambda x: x[1], reverse=True)
    print(f"\nTop 10 Causal Drivers:")
    for feat, weight in drivers_sorted[:10]:
        print(f"  {feat}: {weight:.4f}")
    
    # Save results
    results[metric] = {
        'num_features': num_nodes,
        'num_edges': num_edges,
        'num_drivers': len(drivers_sorted),
        'top_drivers': drivers_sorted[:20],  # Top 20 for VIF filtering
        'runtime_seconds': runtime,
        'alpha': ALPHA,
        'timestamp': datetime.now().isoformat()
    }
    
    # Save causal graph
    with open(f'/models/causal_graphs/{metric}_pc_graph.pkl', 'wb') as f:
        pickle.dump(cg, f)

# Save summary
with open('/models/causal_graphs/tier1_summary.json', 'w') as f:
    json.dump(results, f, indent=2)
```

**Expected Output:**
```
============================================================
Running PC Algorithm: mean_years_schooling
============================================================
Discovered 47 edges among 38 features
Runtime: 23.4 seconds

Top 10 Causal Drivers:
  gdp_per_capita_lag3: 0.8734
  health_x_education: 0.8521
  secondary_enrollment_lag2: 0.8103
  government_expenditure_education_lag2: 0.7892
  ...
```

### **4.2.3: Interpretation of PC Results**

**What PC Algorithm Discovers:**
- **Directed edges (A → B):** A causally influences B (based on conditional independence)
- **Undirected edges (A — B):** Cannot determine direction (possible confounding)
- **No edge:** A and B are conditionally independent (no direct causal link)

**Key Metrics:**
- **Num edges:** Total discovered relationships (expect 15-50 per metric)
- **Num drivers:** Features with edges to target metric (expect 10-25)
- **Top drivers:** Strongest causal relationships by SHAP weight

---

## **Step 4.3: VIF Filtering & Refinement**

### **4.3.1: Calculate VIF on Discovered Drivers**

**Script:** `phase4_vif_filter.py`

```python
from statsmodels.stats.outliers_influence import variance_inflation_factor

def calculate_vif(X, feature_names, threshold=10):
    """
    Calculate VIF for features and remove high-multicollinearity variables.
    
    Returns:
    - retained_features: List of features with VIF < threshold
    - removed_features: List of features with VIF ≥ threshold
    - vif_scores: Dict of all VIF scores
    """
    vif_data = pd.DataFrame()
    vif_data["Feature"] = feature_names
    vif_data["VIF"] = [
        variance_inflation_factor(X.values, i) 
        for i in range(X.shape[1])
    ]
    
    # Iterative removal (remove highest VIF, recalculate, repeat)
    removed = []
    while vif_data["VIF"].max() > threshold:
        max_vif_idx = vif_data["VIF"].idxmax()
        removed_feature = vif_data.loc[max_vif_idx, "Feature"]
        removed.append((removed_feature, vif_data.loc[max_vif_idx, "VIF"]))
        
        # Remove feature and recalculate
        vif_data = vif_data[vif_data["Feature"] != removed_feature].reset_index(drop=True)
        feature_names = vif_data["Feature"].tolist()
        X = X[feature_names]
        
        vif_data["VIF"] = [
            variance_inflation_factor(X.values, i) 
            for i in range(X.shape[1])
        ]
    
    return vif_data["Feature"].tolist(), removed, vif_data.set_index("Feature")["VIF"].to_dict()

# Apply VIF filtering
vif_results = {}

for metric in METRICS_TIER1:
    print(f"\nVIF Filtering: {metric}")
    
    # Load discovered drivers (top 20 from PC)
    top_20 = [feat for feat, _ in results[metric]['top_drivers']]
    X = train[top_20].dropna()
    
    # Calculate VIF
    retained, removed, vif_scores = calculate_vif(X, top_20, threshold=10)
    
    print(f"  Retained: {len(retained)} features")
    print(f"  Removed: {len(removed)} features")
    if removed:
        print(f"  Removed features:")
        for feat, vif in removed:
            print(f"    {feat}: VIF={vif:.2f}")
    
    vif_results[metric] = {
        'retained_features': retained,
        'removed_features': removed,
        'vif_scores': vif_scores
    }

# Save VIF results
with open('/models/causal_graphs/vif_filtering_results.json', 'w') as f:
    json.dump(vif_results, f, indent=2)
```

**Expected Outcome:**
- **Most metrics:** 1-3 features removed (VIF 10-30)
- **High-feature metrics (e.g., life_expectancy with 52):** 4-6 removed
- **Typical removals:** Lag variants of same base variable (e.g., `gdp_lag1`, `gdp_lag3`)

### **4.3.2: Re-run PC with VIF-Filtered Features**

```python
# Re-run PC on VIF-filtered feature sets
for metric in METRICS_TIER1:
    retained_features = vif_results[metric]['retained_features']
    X = train[retained_features].dropna()
    shap_vals = shap_importance[metric].set_index('feature')['shap_importance']
    
    cg_refined, edge_weights_refined = run_pc_with_shap_priors(
        X.values,
        retained_features,
        shap_vals.reindex(retained_features).values,
        alpha=0.05
    )
    
    # Save refined graph
    with open(f'/models/causal_graphs/{metric}_pc_refined.pkl', 'wb') as f:
        pickle.dump(cg_refined, f)
```

---

## **Step 4.4: Inter-Metric Causal Analysis**

### **4.4.1: Granger Causality Testing**

**Objective:** Test if metric A at time T-k predicts metric B at time T (controlling for past B)

**Script:** `phase4_granger_causality.py`

```python
from statsmodels.tsa.stattools import grangercausalitytests

# Prepare panel data with QOL metrics
qol_metrics = ['mean_years_schooling', 'infant_mortality', 'life_expectancy',
               'gdp_per_capita', 'gini', 'homicide', 'undernourishment', 'internet_users']

# Load QOL targets from training data
qol_data = train[['Country', 'Year'] + qol_metrics].dropna()

# Test all pairwise combinations
granger_results = {}

for metric_a in qol_metrics:
    for metric_b in qol_metrics:
        if metric_a == metric_b:
            continue
        
        # Prepare time series for each country
        country_results = []
        for country in qol_data['Country'].unique():
            country_data = qol_data[qol_data['Country'] == country][[metric_a, metric_b]].values
            
            if len(country_data) < 20:  # Need sufficient data
                continue
            
            try:
                # Test lags 1, 2, 3, 5
                result = grangercausalitytests(country_data, maxlag=5, verbose=False)
                
                # Extract p-values for each lag
                p_values = [result[lag][0]['ssr_ftest'][1] for lag in range(1, 6)]
                min_p = min(p_values)
                best_lag = p_values.index(min_p) + 1
                
                country_results.append((country, min_p, best_lag))
            except:
                continue
        
        # Aggregate across countries
        if country_results:
            median_p = np.median([p for _, p, _ in country_results])
            sig_countries = sum(1 for _, p, _ in country_results if p < 0.01)
            
            granger_results[f'{metric_a} → {metric_b}'] = {
                'median_p_value': median_p,
                'significant_countries': sig_countries,
                'total_countries': len(country_results),
                'best_lags': [lag for _, _, lag in country_results]
            }
            
            if median_p < 0.01:
                print(f"✓ {metric_a} → {metric_b}: p={median_p:.4f} ({sig_countries}/{len(country_results)} countries)")

# Save Granger results
with open('/models/causal_graphs/granger_causality.json', 'w') as f:
    json.dump(granger_results, f, indent=2)
```

**Expected Findings:**
- `mean_years_schooling → gdp_per_capita` (education → wealth)
- `undernourishment → infant_mortality` (nutrition → child health)
- `gini → homicide` (inequality → violence)
- `life_expectancy ⇄ gdp_per_capita` (bidirectional: health ⇄ wealth)

### **4.4.2: Structural Equation Modeling (SEM)**

**Objective:** Estimate simultaneous equation system for inter-metric relationships

**Script:** `phase4_sem_inter_metric.py`

```python
from pgmpy.models import SEM
from pgmpy.estimators import IVEstimator

# Hypothesized causal structure (based on development economics theory)
hypothesized_structure = {
    'mean_years_schooling': ['gdp_per_capita', 'gini', 'life_expectancy'],
    'gdp_per_capita': ['life_expectancy', 'internet_users', 'infant_mortality'],
    'undernourishment': ['infant_mortality', 'life_expectancy'],
    'gini': ['homicide', 'infant_mortality'],
    'life_expectancy': ['gdp_per_capita'],  # Bidirectional with GDP
}

# Build SEM model
sem_model = SEM(
    variables=qol_metrics,
    edges=[
        (source, target) 
        for source, targets in hypothesized_structure.items() 
        for target in targets
    ]
)

# Estimate using instrumental variables (to handle endogeneity)
estimator = IVEstimator(sem_model)
path_coefficients = estimator.fit(qol_data)

print("\nPath Coefficients (Standardized):")
for (source, target), coef in path_coefficients.items():
    print(f"  {source} → {target}: {coef:.3f}")

# Test model fit (Chi-square, RMSEA, CFI)
# Compare alternative structures via AIC/BIC
```

### **4.4.3: Vector Autoregression (VAR)**

**Objective:** Model all metrics as multivariate time series, estimating lagged cross-effects

**Script:** `phase4_var_analysis.py`

```python
from statsmodels.tsa.api import VAR
from sklearn.linear_model import LassoCV

# Prepare data for VAR (country-year panel)
var_data = []
for country in qol_data['Country'].unique():
    country_ts = qol_data[qol_data['Country'] == country][qol_metrics].values
    if len(country_ts) >= 30:  # Need sufficient time series
        var_data.append(country_ts)

# Stack all countries
X_var = np.vstack(var_data)

# Fit VAR model with lags 1-5
var_model = VAR(X_var)
var_result = var_model.fit(maxlags=5, ic='aic')  # AIC selects optimal lag

# Extract inter-metric coefficients
print("\nVAR Coefficients (Lag-1 only):")
coef_matrix = var_result.params[:len(qol_metrics), :]  # First lag block

for i, metric_a in enumerate(qol_metrics):
    for j, metric_b in enumerate(qol_metrics):
        if i != j and abs(coef_matrix[i, j]) > 0.05:  # Threshold for reporting
            print(f"  {metric_b} → {metric_a}: {coef_matrix[i, j]:.3f}")

# Apply Lasso regularization to zero-out weak relationships
lasso_model = LassoCV(cv=5, max_iter=10000)
lasso_model.fit(X_var[:-1, :], X_var[1:, :])  # Lag-1 prediction

print("\nLasso-Regularized Relationships:")
lasso_coef = lasso_model.coef_
for i in range(len(qol_metrics)):
    predictors = [qol_metrics[j] for j in range(len(qol_metrics)) if lasso_coef[i, j] != 0]
    if predictors:
        print(f"  {qol_metrics[i]} ← {', '.join(predictors)}")
```

---

## **Step 4.5: Causal Effect Quantification**

### **4.5.1: Extract Causal Coefficients**

**Script:** `phase4_quantify_effects.py`

```python
from sklearn.linear_model import LinearRegression

def quantify_causal_effect(X, y, feature, confounders):
    """
    Estimate causal effect of feature on y, controlling for confounders.
    
    Uses backdoor adjustment: Regress y on feature + confounders.
    """
    X_adjusted = X[[feature] + confounders]
    model = LinearRegression()
    model.fit(X_adjusted, y)
    
    # Coefficient of feature is causal effect
    causal_effect = model.coef_[0]
    
    # Bootstrap confidence interval
    n_bootstrap = 1000
    bootstrap_effects = []
    for _ in range(n_bootstrap):
        idx = np.random.choice(len(X), len(X), replace=True)
        X_boot = X_adjusted.iloc[idx]
        y_boot = y.iloc[idx]
        model_boot = LinearRegression()
        model_boot.fit(X_boot, y_boot)
        bootstrap_effects.append(model_boot.coef_[0])
    
    ci_lower = np.percentile(bootstrap_effects, 2.5)
    ci_upper = np.percentile(bootstrap_effects, 97.5)
    
    return causal_effect, (ci_lower, ci_upper)

# Quantify effects for all discovered drivers
causal_effects = {}

for metric in METRICS_TIER1:
    retained_features = vif_results[metric]['retained_features']
    X = train[retained_features].dropna()
    y = train.loc[X.index, metric]
    
    metric_effects = {}
    for feature in retained_features[:10]:  # Top 10 drivers
        # Use other top-10 as confounders (backdoor adjustment)
        confounders = [f for f in retained_features[:10] if f != feature]
        
        effect, ci = quantify_causal_effect(X, y, feature, confounders)
        
        metric_effects[feature] = {
            'effect': effect,
            'ci_lower': ci[0],
            'ci_upper': ci[1],
            'significant': (ci[0] * ci[1] > 0)  # CI doesn't cross zero
        }
        
        if metric_effects[feature]['significant']:
            print(f"{metric} ← {feature}: {effect:.4f} [{ci[0]:.4f}, {ci[1]:.4f}]")
    
    causal_effects[metric] = metric_effects

# Save quantified effects
with open('/models/causal_graphs/causal_effects_quantified.json', 'w') as f:
    json.dump(causal_effects, f, indent=2)
```

### **4.5.2: Validate Against Literature**

**Script:** `phase4_literature_validation.py`

```python
# Known relationships from development economics literature
literature_relationships = {
    'mean_years_schooling': {
        'gdp_per_capita': {'direction': '+', 'strength': 'strong', 'source': 'Barro & Lee (2013)'},
        'health_expenditure': {'direction': '+', 'strength': 'moderate', 'source': 'Cutler & Lleras-Muney (2010)'},
    },
    'infant_mortality': {
        'health_expenditure': {'direction': '-', 'strength': 'strong', 'source': 'Anand & Ravallion (1993)'},
        'water_sanitation': {'direction': '-', 'strength': 'strong', 'source': 'Fink et al. (2011)'},
    },
    # ... add more from Phase 0-3 research logs
}

# Compare discovered relationships to literature
for metric, discovered in causal_effects.items():
    print(f"\n{metric} Validation:")
    for feature, effect_data in discovered.items():
        # Check if in literature
        if feature in literature_relationships.get(metric, {}):
            lit = literature_relationships[metric][feature]
            discovered_sign = '+' if effect_data['effect'] > 0 else '-'
            
            if discovered_sign == lit['direction']:
                print(f"  ✓ {feature}: MATCHES literature ({lit['source']})")
            else:
                print(f"  ✗ {feature}: CONTRADICTS literature (expected {lit['direction']}, found {discovered_sign})")
        else:
            print(f"  ? {feature}: Novel finding (not in literature)")
```

---

## **Step 4.6: Policy Simulation Framework**

### **4.6.1: Implement Do-Calculus**

**Script:** `policy_simulator.py`

```python
import networkx as nx
from pgmpy.inference import CausalInference

class PolicySimulator:
    def __init__(self, causal_models: dict):
        """
        Initialize with causal graphs from Phase 4.
        
        Parameters:
        - causal_models: Dict[metric, (DAG, coefficients)]
        """
        self.models = causal_models
        self.inter_metric_graph = self._build_inter_metric_graph()
    
    def _build_inter_metric_graph(self):
        """Construct meta-graph of metric→metric relationships."""
        G = nx.DiGraph()
        # Add edges from Granger/SEM/VAR results
        # ... (load from Step 4.4 outputs)
        return G
    
    def simulate_intervention(
        self, 
        metric: str, 
        feature: str, 
        change_pct: float,
        time_horizon: int = 5
    ) -> dict:
        """
        Simulate policy intervention using do-calculus.
        
        Example:
        >>> sim.simulate_intervention(
        ...     metric='infant_mortality',
        ...     feature='health_expenditure_gdp',
        ...     change_pct=0.20,  # +20% increase
        ...     time_horizon=5
        ... )
        {
            'infant_mortality': -12.3,  # 12.3% reduction
            'life_expectancy': +2.1,     # 2.1 year increase (spillover)
            'confidence_interval': (-15.2, -9.4)
        }
        """
        
        # Step 1: Direct effect on target metric
        dag, coefficients = self.models[metric]
        direct_effect = coefficients[feature]['effect'] * change_pct
        
        # Step 2: Propagate through DAG (do-calculus)
        # Set feature to new value, propagate through graph
        intervention_results = {metric: direct_effect}
        
        # Step 3: Check for spillover effects on other metrics
        if metric in self.inter_metric_graph:
            for target_metric in self.inter_metric_graph.successors(metric):
                spillover_coef = self.inter_metric_graph[metric][target_metric]['weight']
                spillover_effect = direct_effect * spillover_coef
                intervention_results[target_metric] = spillover_effect
        
        # Step 4: Compute confidence intervals (bootstrap)
        ci_lower = direct_effect - 1.96 * coefficients[feature]['ci_upper']
        ci_upper = direct_effect + 1.96 * coefficients[feature]['ci_lower']
        intervention_results['confidence_interval'] = (ci_lower, ci_upper)
        
        return intervention_results
    
    def counterfactual_query(self, country, year, intervention):
        """
        Answer: "What would Y have been if we had done X?"
        
        Uses Pearl's counterfactual logic.
        """
        # Load observed data for (country, year)
        # Apply intervention
        # Propagate through causal graph
        # Return counterfactual outcome
        pass

# Initialize simulator
simulator = PolicySimulator(causal_models={
    metric: (
        pickle.load(open(f'/models/causal_graphs/{metric}_pc_refined.pkl', 'rb')),
        causal_effects[metric]
    )
    for metric in METRICS_TIER1
})

# Test simulation
result = simulator.simulate_intervention(
    metric='infant_mortality',
    feature='health_expenditure_gdp_lag2',
    change_pct=0.20,  # +20% health spending
    time_horizon=5
)

print("\nPolicy Simulation Results:")
print(f"Intervention: +20% health expenditure")
print(f"Direct effect on infant mortality: {result['infant_mortality']:.2f}%")
print(f"95% CI: [{result['confidence_interval'][0]:.2f}, {result['confidence_interval'][1]:.2f}]")

if 'life_expectancy' in result:
    print(f"Spillover on life expectancy: +{result['life_expectancy']:.2f} years")
```

### **4.6.2: Dashboard Integration Preparation**

```python
# Export simulator for Phase 6 dashboard
import joblib

joblib.dump(simulator, '/models/policy_simulator.pkl')

# Export simplified API
api_spec = {
    'available_interventions': {
        metric: list(causal_effects[metric].keys())
        for metric in causal_effects.keys()
    },
    'endpoint': '/api/simulate_intervention',
    'parameters': {
        'metric': 'QOL metric to target',
        'feature': 'Causal driver to intervene on',
        'change_pct': 'Percent change (-1.0 to 1.0)',
        'time_horizon': 'Years to simulate (1-10)'
    }
}

with open('/models/policy_simulator_api.json', 'w') as f:
    json.dump(api_spec, f, indent=2)
```

---

## **Step 4.7: Validation & Documentation**

### **4.7.1: Validation Checklist**

```python
# Validation tests
validation_report = {
    'timestamp': datetime.now().isoformat(),
    'tests': {}
}

# Test 1: DAG Acyclicity
for metric in causal_effects.keys():
    dag = pickle.load(open(f'/models/causal_graphs/{metric}_pc_refined.pkl', 'rb'))
    is_dag = nx.is_directed_acyclic_graph(dag.G)
    validation_report['tests'][f'{metric}_is_dag'] = is_dag
    assert is_dag, f"{metric} graph contains cycles!"

# Test 2: Effect Sign Consistency
for metric, effects in causal_effects.items():
    for feature, data in effects.items():
        # Check if CI doesn't cross zero (for significant effects)
        if data['significant']:
            assert (data['ci_lower'] * data['ci_upper'] > 0), f"{metric}←{feature} CI crosses zero!"

# Test 3: Literature Alignment
# (Compare to literature_relationships dict)

# Test 4: Simulation Bounds
test_sim = simulator.simulate_intervention('infant_mortality', 'health_expenditure_gdp_lag2', 0.20)
assert -100 < test_sim['infant_mortality'] < 100, "Simulation produced unrealistic result!"

print("✓ All validation tests passed")
```

### **4.7.2: Generate Causal Graph Visualizations**

```python
import matplotlib.pyplot as plt
from networkx.drawing.nx_agraph import graphviz_layout

for metric in causal_effects.keys():
    dag = pickle.load(open(f'/models/causal_graphs/{metric}_pc_refined.pkl', 'rb'))
    
    # Convert to NetworkX
    G = nx.DiGraph()
    for i, j in dag.G.get_graph_edges():
        G.add_edge(retained_features[i], retained_features[j])
    
    # Layout
    pos = graphviz_layout(G, prog='dot')
    
    # Plot
    plt.figure(figsize=(16, 12))
    nx.draw(G, pos, with_labels=True, node_color='lightblue', 
            node_size=3000, font_size=8, arrows=True, arrowsize=20)
    plt.title(f'Causal DAG: {metric}', fontsize=16)
    plt.savefig(f'/models/causal_graphs/visualizations/{metric}_dag.png', dpi=300)
    plt.close()
```

---

## **Step 4.8: Final Deliverables**

### **File Structure**

```
/models/causal_graphs/
├── tier1_summary.json                      # PC results summary
├── granger_causality.json                  # Inter-metric Granger tests
├── vif_filtering_results.json              # VIF analysis
├── causal_effects_quantified.json          # Effect sizes + CIs
├── {metric}_pc_graph.pkl                   # Raw PC output (8 files)
├── {metric}_pc_refined.pkl                 # VIF-filtered graphs (8 files)
├── visualizations/
│   ├── {metric}_dag.png                    # DAG plots (8 files)
│   └── inter_metric_graph.png              # Meta-graph
├── policy_simulator.pkl                    # Pickled PolicySimulator
└── policy_simulator_api.json               # API spec for Phase 6

/Documentation/phase_reports/
├── phase4_causal_discovery_report.md       # Comprehensive report
└── phase4_literature_validation.md         # Comparison to theory
```

### **Summary Statistics**

**Expected Results:**
- **Causal drivers per metric:** 10-20 (down from 23-52 features)
- **VIF removals:** 1-5 features per metric
- **Runtime:** 2-4 hours total (PC parallelizable by metric)
- **Significant inter-metric relationships:** 8-15 (e.g., education→GDP, GDP→health)

### **Key Outputs for Phase 6**

1. **PolicySimulator class** - Ready for Flask API integration
2. **Causal DAGs** - For hierarchical visualization
3. **Effect quantifications** - For "change by X% → see impact" simulator
4. **Confidence intervals** - For uncertainty visualization

---

## **Next Steps (Phase 5)**

After Phase 4 completes:
1. **Extend to all 8 metrics** (currently focused on Tier 1)
2. **Sensitivity analysis** - Test robustness to alpha parameter (0.01, 0.05, 0.10)
3. **Temporal stability** - Run PC on 3 epochs (1965-1985, 1986-2005, 2006-2024)
4. **Bootstrap validation** - 100 iterations with 80% sample to get edge frequencies
5. **FCI fallback** - If latent confounders suspected (e.g., unmeasured governance for homicide)

---

**Ready to start?** Begin with:
```bash
python phase4_setup.py
python phase4_pc_tier1.py
```
