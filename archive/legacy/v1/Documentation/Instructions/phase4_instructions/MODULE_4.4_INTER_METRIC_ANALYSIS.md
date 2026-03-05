# MODULE 4.4: Inter-Metric Causal Relationships

## OBJECTIVE
Identify causal relationships between the 8 quality-of-life metrics themselves (e.g., does education cause GDP growth? does health affect productivity?) using Granger causality testing, Vector Autoregression (VAR), and Structural Equation Modeling (SEM).

## CONTEXT
Modules 4.2-4.3 discovered within-metric causal drivers (e.g., which variables cause infant_mortality). Module 4.4 analyzes between-metric relationships to understand how QOL outcomes affect each other. This creates a meta-graph of metric→metric edges that captures development dynamics (e.g., education→GDP, GDP→health, health→life_expectancy). These inter-metric relationships enable the policy simulator (Module 4.6) to predict spillover effects: "Increasing education spending affects not just schooling years, but also GDP, health, and inequality."

## INPUTS

### From Module 4.1
- **Training Data**: `<repo-root>/v1.0/models/causal_graphs/loaded_training_data.pkl`
  - Must include all 8 QOL metrics as columns
- **Normalized Training Set**: `<repo-root>/v1.0/Data/Processed/normalized/train_normalized.csv`
  - Country-year panel with all 8 metrics

### QOL Metrics
```python
QOL_METRICS = [
    'mean_years_schooling',
    'infant_mortality',
    'life_expectancy',
    'gdp_per_capita',
    'gini',
    'homicide',
    'undernourishment',
    'internet_users'
]
```

## TASK DIRECTIVE

### Step 1: Granger Causality Testing

**Objective**: Test if metric A at time T-k predicts metric B at time T, controlling for past values of B.

**Interpretation**: If A Granger-causes B, past values of A improve prediction of current B beyond what past B alone provides. This suggests temporal precedence (necessary but not sufficient for causation).

**Script**: `phase4_granger_causality.py`

```python
from statsmodels.tsa.stattools import grangercausalitytests
import pandas as pd
import numpy as np
import json

# Load QOL data
train_df = pd.read_csv('<repo-root>/v1.0/Data/Processed/normalized/train_normalized.csv')

QOL_METRICS = [
    'mean_years_schooling', 'infant_mortality', 'life_expectancy',
    'gdp_per_capita', 'gini', 'homicide', 'undernourishment', 'internet_users'
]

# Prepare panel data (Country × Year)
qol_data = train_df[['Country', 'Year'] + QOL_METRICS].dropna()

# Test all pairwise combinations
granger_results = {}
MAX_LAG = 5  # Test lags 1-5 years

for metric_a in QOL_METRICS:
    for metric_b in QOL_METRICS:
        if metric_a == metric_b:
            continue  # Skip self-causation

        print(f"Testing: {metric_a} → {metric_b}")

        # Test per country, aggregate results
        country_p_values = []

        for country in qol_data['Country'].unique():
            country_data = qol_data[qol_data['Country'] == country][[metric_a, metric_b]].values

            if len(country_data) < 20:  # Need sufficient time series
                continue

            try:
                # Granger causality test
                # Returns: {lag: {test_name: (statistic, p_value)}}
                result = grangercausalitytests(
                    country_data,
                    maxlag=MAX_LAG,
                    verbose=False
                )

                # Extract p-values for F-test
                p_values = [result[lag][0]['ssr_ftest'][1] for lag in range(1, MAX_LAG + 1)]
                min_p = min(p_values)
                best_lag = p_values.index(min_p) + 1

                country_p_values.append({
                    'country': country,
                    'min_p': min_p,
                    'best_lag': best_lag
                })

            except Exception as e:
                # Skip if test fails (e.g., singular matrix)
                continue

        # Aggregate across countries
        if len(country_p_values) > 0:
            p_values_list = [x['min_p'] for x in country_p_values]
            median_p = np.median(p_values_list)
            mean_p = np.mean(p_values_list)
            sig_countries = sum(1 for x in country_p_values if x['min_p'] < 0.01)

            granger_results[f'{metric_a} → {metric_b}'] = {
                'median_p_value': float(median_p),
                'mean_p_value': float(mean_p),
                'significant_countries': sig_countries,
                'total_countries_tested': len(country_p_values),
                'significant_fraction': sig_countries / len(country_p_values),
                'best_lags': [x['best_lag'] for x in country_p_values]
            }

            # Report significant relationships
            if median_p < 0.01:
                print(f"  ✓ SIGNIFICANT: p={median_p:.4f} ({sig_countries}/{len(country_p_values)} countries)")
        else:
            print(f"  ✗ Insufficient data")

# Save Granger results
with open('<repo-root>/v1.0/models/causal_graphs/granger_causality.json', 'w') as f:
    json.dump(granger_results, f, indent=2)

# Extract significant relationships (p < 0.01)
significant_edges = {
    edge: data for edge, data in granger_results.items()
    if data['median_p_value'] < 0.01
}

print(f"\n{'='*60}")
print(f"Found {len(significant_edges)} significant Granger-causal relationships")
print("="*60)

for edge, data in sorted(significant_edges.items(), key=lambda x: x[1]['median_p_value']):
    print(f"{edge}: p={data['median_p_value']:.4f} ({data['significant_fraction']:.1%} countries)")
```

**Expected Findings**:
- **Education → GDP**: Past schooling predicts future GDP growth
- **GDP → Health**: Past wealth predicts future health outcomes
- **Undernourishment → Infant Mortality**: Past nutrition predicts child health
- **Gini → Homicide**: Past inequality predicts future violence

### Step 2: Vector Autoregression (VAR)

**Objective**: Model all 8 metrics as a multivariate time series, estimating lagged cross-effects simultaneously.

**Script**: `phase4_var_analysis.py`

```python
from statsmodels.tsa.api import VAR
import pandas as pd
import numpy as np

# Prepare VAR data (stack all country time series)
var_data_list = []

for country in qol_data['Country'].unique():
    country_ts = qol_data[qol_data['Country'] == country][QOL_METRICS].values
    if len(country_ts) >= 30:  # Need 30+ years for VAR stability
        var_data_list.append(country_ts)

# Stack all countries (pooled VAR)
X_var = np.vstack(var_data_list)
print(f"VAR data shape: {X_var.shape}")

# Fit VAR model
var_model = VAR(X_var)

# Select optimal lag using AIC
var_result = var_model.fit(maxlags=5, ic='aic')
optimal_lag = var_result.k_ar

print(f"Optimal lag: {optimal_lag}")
print(f"AIC: {var_result.aic}")

# Extract lag-1 coefficients (most interpretable)
lag1_coef = var_result.params[:len(QOL_METRICS), :]  # First lag block

# Create coefficient matrix
coef_df = pd.DataFrame(
    lag1_coef,
    index=QOL_METRICS,
    columns=[f"{m}_coef" for m in QOL_METRICS]
)

# Report significant cross-metric effects (|coef| > 0.05)
print("\nVAR Lag-1 Coefficients (A affects B):")
for target_metric in QOL_METRICS:
    for source_metric in QOL_METRICS:
        if source_metric != target_metric:
            coef = coef_df.loc[target_metric, f"{source_metric}_coef"]
            if abs(coef) > 0.05:  # Threshold for reporting
                direction = "+" if coef > 0 else "-"
                print(f"  {source_metric} → {target_metric}: {coef:.3f} ({direction})")

# Save VAR results
var_results_dict = {
    'optimal_lag': int(optimal_lag),
    'aic': float(var_result.aic),
    'lag1_coefficients': coef_df.to_dict(),
    'samples_used': int(X_var.shape[0])
}

with open('<repo-root>/v1.0/models/causal_graphs/var_results.json', 'w') as f:
    json.dump(var_results_dict, f, indent=2)

# Save coefficient matrix (CSV)
coef_df.to_csv('<repo-root>/v1.0/models/causal_graphs/var_lag1_coefficients.csv')
```

### Step 3: Build Inter-Metric Causal Graph

**Objective**: Synthesize Granger + VAR results into a directed graph of metric→metric relationships.

**Script**: `phase4_build_inter_metric_graph.py`

```python
import networkx as nx
import json

# Load Granger results
with open('<repo-root>/v1.0/models/causal_graphs/granger_causality.json') as f:
    granger = json.load(f)

# Load VAR results
with open('<repo-root>/v1.0/models/causal_graphs/var_results.json') as f:
    var_results = json.load(f)

# Build directed graph
G_inter_metric = nx.DiGraph()

# Add nodes (8 QOL metrics)
G_inter_metric.add_nodes_from(QOL_METRICS)

# Add edges from Granger causality (p < 0.01)
for edge, data in granger.items():
    if data['median_p_value'] < 0.01:
        source, target = edge.split(' → ')
        G_inter_metric.add_edge(
            source,
            target,
            granger_p=data['median_p_value'],
            granger_fraction=data['significant_fraction']
        )

# Augment edges with VAR coefficients
lag1_coef_df = pd.read_csv('<repo-root>/v1.0/models/causal_graphs/var_lag1_coefficients.csv', index_col=0)

for source, target in G_inter_metric.edges():
    coef = lag1_coef_df.loc[target, f"{source}_coef"]
    G_inter_metric[source][target]['var_coefficient'] = float(coef)

# Save graph
nx.write_gpickle(
    G_inter_metric,
    '<repo-root>/v1.0/models/causal_graphs/inter_metric_graph.pkl'
)

# Export edge list (CSV)
edge_data = []
for source, target, data in G_inter_metric.edges(data=True):
    edge_data.append({
        'source': source,
        'target': target,
        'granger_p': data.get('granger_p', 1.0),
        'var_coefficient': data.get('var_coefficient', 0.0)
    })

edge_df = pd.DataFrame(edge_data)
edge_df.to_csv('<repo-root>/v1.0/models/causal_graphs/inter_metric_edges.csv', index=False)

print(f"\nInter-Metric Causal Graph:")
print(f"  Nodes: {G_inter_metric.number_of_nodes()}")
print(f"  Edges: {G_inter_metric.number_of_edges()}")
print(f"  Density: {nx.density(G_inter_metric):.3f}")

# Identify metrics with most outgoing edges (causes)
out_degree = dict(G_inter_metric.out_degree())
print("\nMost Influential Metrics (outgoing edges):")
for metric, degree in sorted(out_degree.items(), key=lambda x: x[1], reverse=True)[:5]:
    print(f"  {metric}: {degree} outgoing edges")

# Identify metrics with most incoming edges (effects)
in_degree = dict(G_inter_metric.in_degree())
print("\nMost Affected Metrics (incoming edges):")
for metric, degree in sorted(in_degree.items(), key=lambda x: x[1], reverse=True)[:5]:
    print(f"  {metric}: {degree} incoming edges")
```

## OUTPUTS

### Primary Outputs

1. **Granger Causality Results**: `<repo-root>/v1.0/models/causal_graphs/granger_causality.json`
   - All 56 pairwise tests (8×7)
   - Median p-values across countries
   - Significant fraction per relationship

2. **VAR Results**: `<repo-root>/v1.0/models/causal_graphs/var_results.json`
   - Optimal lag selection
   - AIC score
   - Lag-1 coefficient matrix

3. **VAR Coefficients**: `<repo-root>/v1.0/models/causal_graphs/var_lag1_coefficients.csv`
   - 8×8 matrix of cross-metric effects

4. **Inter-Metric Graph**: `<repo-root>/v1.0/models/causal_graphs/inter_metric_graph.pkl`
   - NetworkX DiGraph with Granger p-values and VAR coefficients as edge attributes

5. **Inter-Metric Edge List**: `<repo-root>/v1.0/models/causal_graphs/inter_metric_edges.csv`
   - CSV: [source, target, granger_p, var_coefficient]

## SUCCESS CRITERIA

- [ ] Granger causality tests complete for all 56 pairwise combinations (8×7)
- [ ] VAR model converges with optimal lag 1-3 (typical for annual data)
- [ ] Find 8-15 significant Granger-causal relationships (p < 0.01)
- [ ] Inter-metric graph has 8 nodes, 8-15 edges
- [ ] Key expected relationships confirmed:
  - [ ] education → gdp_per_capita
  - [ ] gdp_per_capita → life_expectancy OR health metrics
  - [ ] undernourishment → infant_mortality
  - [ ] gini → homicide (inequality-violence link)

## INTEGRATION NOTES

### Handoff to Module 4.6 (Policy Simulator)
- Inter-metric graph enables spillover effect simulation
- VAR coefficients quantify cross-metric propagation
- Example: "20% increase in education → X% GDP increase → Y% health improvement"

### Theoretical Validation
Compare discovered relationships to development economics theory:
- **Expected positive**: education→GDP, GDP→health, health→productivity
- **Expected negative**: poverty→mortality, inequality→violence
- **Bidirectional**: health↔GDP (healthy workers produce more, wealth buys health)

## ERROR HANDLING

### Common Issues

1. **Singular Matrix in Granger Test**:
   - Cause: Insufficient variance in metric within country
   - Solution: Skip country, aggregate across remaining countries

2. **VAR Non-Convergence**:
   - Cause: Non-stationary time series
   - Solution: First-difference the data (ΔY = Y_t - Y_{t-1})

3. **No Significant Relationships**:
   - Cause: Alpha too strict (0.01) or metrics truly independent
   - Solution: Use p < 0.05 threshold for exploratory analysis

## VALIDATION CHECKS

```python
# Verify expected relationships exist
expected_edges = [
    ('mean_years_schooling', 'gdp_per_capita'),
    ('gdp_per_capita', 'life_expectancy'),
    ('undernourishment', 'infant_mortality')
]

with open('<repo-root>/v1.0/models/causal_graphs/granger_causality.json') as f:
    granger = json.load(f)

for source, target in expected_edges:
    edge_key = f"{source} → {target}"
    if edge_key in granger:
        p_val = granger[edge_key]['median_p_value']
        status = "✓" if p_val < 0.05 else "✗"
        print(f"{status} {edge_key}: p={p_val:.4f}")
    else:
        print(f"✗ {edge_key}: Not tested")
```

## ESTIMATED RUNTIME
**45-60 minutes** (30 min Granger tests, 15 min VAR, 15 min graph construction)

## DEPENDENCIES
- Module 4.1 (Setup) must complete successfully
- Module 4.3 (VIF) should complete (though not strictly required)

## PRIORITY
**HIGH** - Enables spillover effect simulation in policy framework

## REFERENCES
- Granger, C. W. J. (1969). "Investigating Causal Relations by Econometric Models and Cross-spectral Methods." *Econometrica*, 37(3), 424-438.
- Sims, C. A. (1980). "Macroeconomics and Reality." *Econometrica*, 48(1), 1-48.
- Lutkepohl, H. (2005). *New Introduction to Multiple Time Series Analysis*. Springer.
