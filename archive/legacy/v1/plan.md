# COMPREHENSIVE WORKFLOW: FROM 2,500 VARIABLES TO CAUSAL KNOWLEDGE GRAPH

---

## PHASE 1: DATA PREPARATION & PREPROCESSING

### Step 1.1: Create Lag Features
- Generate lagged versions of all 2,500 variables (T-1, T-2, T-3, T-5 years)
- This allows model to capture: "Education spending in 2010 → Life Expectancy in 2015"
- Store both contemporaneous (same year) and lagged features
- **Output**: ~12,500 features (2,500 original + 10,000 lagged)

### Step 1.2: Split Data (Country-Agnostic)
- Randomly assign 70% of countries (152) to training set
- Remaining 30% (65 countries) to test set
- Ensure all years (1990-2023) included for each country
- **Output**: Train dataset (~3.5M rows), Test dataset (~1.5M rows)

### Step 1.3: Handle Temporal Trends
- Calculate year-over-year changes (deltas) for all variables
- Normalize/standardize features within each country to remove country-specific baselines
- Option: Detrend data to isolate relationships independent of global trends
- **Output**: Trend-adjusted feature set

---

## PHASE 2: FEATURE SELECTION (TRIPLE APPROACH)

You'll run **three parallel analyses** for each of the 8 QOL metrics, then synthesize results.

### Step 2.1: Statistical Importance (Per Metric)

**For EACH of the 8 QOL metrics:**

#### 2.1a: Correlation Analysis
- Calculate Pearson correlation (linear relationships)
- Calculate Spearman correlation (monotonic relationships)  
- Calculate Mutual Information (captures non-linear dependencies)
- Test both contemporaneous and lagged features
- **Output**: Correlation matrix ranked by absolute strength

#### 2.1b: Tree-Based Feature Importance
- Train XGBoost model: `X (all 12,500 features) → Y (single QOL metric)`
- Use L1/L2 regularization to penalize redundant features
- Extract feature importance scores
- **Output**: Top 100 features by importance score

#### 2.1c: SHAP Values
- Calculate SHAP values on trained XGBoost model
- SHAP shows marginal contribution of each feature
- Captures non-linear effects and interactions
- **Output**: Top 100 features by mean absolute SHAP value

#### 2.1d: Synthesis
- Combine rankings from correlation, importance, and SHAP
- Use voting system: feature gets +1 point for appearing in any top-100 list
- Select top 50 features with highest votes
- **Output per metric**: Top 50 statistically significant features

---

### Step 2.2: Interpretable Thematic Grouping

#### 2.2a: Domain Classification
Manually or semi-automatically classify all 2,500 variables into ~15-20 thematic domains:

**Example domains:**
- Healthcare Infrastructure (hospital beds, physicians, facilities)
- Healthcare Spending (public/private expenditure, per capita)
- Disease Burden (prevalence of HIV, TB, malaria, NCDs)
- Preventive Health (vaccination rates, WASH)
- Education Investment (spending, expenditure per student)
- Education Quality (teacher ratios, completion rates)
- Labor Market (employment, unemployment, participation)
- Economic Structure (industry, agriculture, services %)
- Trade & Openness (exports, imports, FDI)
- Governance (rule of law, corruption, democracy)
- Infrastructure (roads, electricity, telecommunications)
- Demographics (population growth, age structure, urbanization)
- Nutrition & Food (caloric supply, malnutrition, food security)
- Climate & Environment (temperature, precipitation, disasters)
- Social Protection (safety nets, social spending)

#### 2.2b: Within-Domain Selection
For each domain:
- Calculate average correlation with each QOL metric
- Select top 1-3 representatives per domain
- Ensure domain representatives are minimally correlated with each other
- **Output**: ~30-50 interpretable features per metric

---

### Step 2.3: Hybrid Selection (Statistical + Thematic)

#### 2.3a: Intersection Analysis
- Take features that appear in BOTH statistical top-50 AND thematic selection
- These are high-importance features that are also interpretable
- **Output**: ~20-30 features per metric

#### 2.3b: Strategic Addition
- From statistical top-50: Add any features NOT covered by thematic domains
- From thematic selection: Add domain representatives even if low statistical rank (for completeness)
- Ensure each domain has at least 1 representative if correlation > 0.3
- **Output per metric**: **Final 40-60 hybrid features**

---

## PHASE 3: BUILD INDIVIDUAL METRIC MODELS (8 SEPARATE MODELS)

**For EACH of the 8 QOL metrics, build a dedicated model:**

### Step 3.1: Model Architecture Per Metric

#### Option A: Regularized Neural Network
```
Input Layer: 40-60 hybrid features
Hidden Layer 1: 128 neurons, ReLU, Dropout(0.3)
Hidden Layer 2: 64 neurons, ReLU, Dropout(0.2)
Hidden Layer 3: 32 neurons, ReLU
Output Layer: 1 neuron (predicted QOL metric)

Regularization: L1 + L2 (Elastic Net penalty)
Loss: Mean Squared Error
Optimizer: Adam
```

**Why regularization?**: Forces model to learn sparse, interpretable weights. Features with near-zero weights are unimportant.

#### Option B: XGBoost (Alternative)
- More interpretable
- Built-in feature importance
- Can extract exact contribution curves
- **Recommended if interpretability > accuracy**

### Step 3.2: Training Protocol Per Model

1. **Train on 70% countries** (152 countries, all years)
2. **Validate on held-out 15% countries** during training for early stopping
3. **Test on final 15% countries** for performance reporting
4. **Cross-validation**: 5-fold CV within training countries
5. **Hyperparameter tuning**: Grid search for learning rate, dropout, regularization strength

### Step 3.3: Extract Feature Weights Per Model

After training each model:
- **Neural Network**: Extract weights from Input → Hidden Layer 1
- Calculate importance score: `|weight| × std(feature)` 
- Normalize to sum to 1.0
- **Output**: Feature importance vector (40-60 values summing to 1.0)

**These weights become the edge strengths in your hierarchical visual**

### Step 3.4: Evaluate Per Model

Calculate on test set (30% countries):
- R² score
- RMSE
- Mean Absolute Error
- Correlation between predicted and actual

**Output**: 8 trained models with performance metrics

---

## PHASE 4: INTER-METRIC RELATIONSHIP ANALYSIS

Now analyze how the 8 QOL metrics relate to **each other**.

### Step 4.1: Contemporaneous Correlation Matrix

- Calculate 8×8 correlation matrix between all QOL metrics
- Use training set (70% countries)
- Test statistical significance (p < 0.01)
- **Output**: Correlation matrix showing which metrics co-move

### Step 4.2: Granger Causality Testing

For each pair of metrics (A, B):
- Test if "A at time T-k predicts B at time T" (controlling for past B)
- Test both directions (A→B and B→A)
- Use lags k = 1, 2, 3, 5 years
- **Output**: Directed graph of temporal precedence

### Step 4.3: Structural Equation Modeling (SEM)

- Specify hypothesized causal structure based on domain knowledge:
  - Example: `GDP → Education → Life Expectancy`
  - Example: `Healthcare Spending → Infant Mortality`
- Fit SEM to estimate path coefficients
- Compare multiple structural hypotheses (AIC/BIC)
- **Output**: Best-fit causal DAG (Directed Acyclic Graph) between 8 metrics

### Step 4.4: Regularized VAR Model (Vector Autoregression)

- Treat 8 QOL metrics as multivariate time series
- Each metric predicted by lagged values of ALL 8 metrics
- Use Lasso regularization to zero-out weak relationships
- **Output**: 8×8 matrix of inter-metric influence weights

---

## PHASE 5: BUILD MASTER INTEGRATED MODEL

### Step 5.1: Multi-Output Neural Network

**Architecture:**
```
Input Layer: All ~60 selected features (deduplicated across metrics)

Shared Layers:
  Hidden 1: 256 neurons, ReLU, Dropout(0.3)
  Hidden 2: 128 neurons, ReLU, Dropout(0.2)

Metric-Specific Branches (8 parallel):
  Branch 1 (Life Expectancy): 64 → 32 → 1 neuron
  Branch 2 (Education): 64 → 32 → 1 neuron
  ...
  Branch 8 (Internet): 64 → 32 → 1 neuron

Loss: Sum of MSE across all 8 outputs
Regularization: L1 on shared layers, L2 on branches
```

**Why this architecture?**:
- Shared layers learn common patterns affecting all metrics
- Branches specialize for each metric
- Captures inter-dependencies implicitly

### Step 5.2: Training Protocol

1. Train on 70% countries, all years
2. Multi-task loss: weighted sum of 8 MSE losses
3. Weight each metric equally OR by inverse variance (to balance scales)
4. Early stopping on validation set (15% countries)
5. **Output**: Single unified model predicting all 8 metrics

### Step 5.3: Extract Cross-Metric Interactions

**Method 1: Attention Weights**
- Add attention mechanism between metric-specific branches
- Attention scores show how much each metric "attends to" others
- **Output**: 8×8 attention matrix

**Method 2: Partial Derivatives**
- For each metric Y_i, calculate ∂Y_i/∂Y_j for all j≠i
- Shows sensitivity of metric i to changes in metric j
- **Output**: 8×8 Jacobian matrix of sensitivities

**Method 3: Ablation Study**
- Predict all 8 metrics with full model
- Mask/zero-out one metric's branch, re-predict others
- Difference = influence of masked metric on others
- **Output**: 8×8 influence matrix

---

## PHASE 6: DEDUPLICATION & HIERARCHICAL STRUCTURE

### Step 6.1: Feature Deduplication Across Metrics

- Identify features selected for multiple QOL metrics
- Example: "Healthcare Spending" appears for Life Expectancy, Infant Mortality, GDP
- Create master list of unique features (~100-150 unique)
- **Output**: Deduplicated feature list with multi-metric connections

### Step 6.2: Build Hierarchical Levels

**Level 1: Causal Features** (inputs)
- ~100-150 unique causal variables
- Group by domain for visual clarity

**Level 2: QOL Metrics** (intermediates/outputs)
- The 8 target metrics
- Both predicted by Level 1 and influencing each other

**Level 3: Inter-Metric Relationships**
- Connections BETWEEN the 8 metrics
- From Phase 4 analysis (Granger, SEM, VAR)

### Step 6.3: Edge Weight Assignment

**For Causal Features → QOL Metrics:**
- Use normalized weights from Phase 3 individual models
- Scale by model R²: `final_weight = raw_weight × R²`
- This downweights features from poorly-performing models

**For QOL Metric → QOL Metric:**
- Use coefficients from VAR model OR SEM path coefficients
- Only include if statistically significant (p < 0.01)
- Directionality from Granger causality

---

## PHASE 7: CREATE MATHEMATICAL MODEL FILES

### Step 7.1: Model Weights Export

**For each of 8 individual models:**
```
File: model_weights_life_expectancy.json
{
  "features": ["healthcare_spending", "education_years", ...],
  "weights": [0.35, 0.22, ...],
  "intercept": 45.2,
  "r_squared": 0.87,
  "architecture": {...}
}
```

**For master integrated model:**
```
File: master_model_weights.h5 (or .pkl)
Contains:
- Full neural network architecture
- Trained weights for all layers
- Feature normalization parameters (mean, std)
- Input feature list
- Output metric order
```

### Step 7.2: Relationship Matrices Export

**File: causal_feature_to_metric_weights.csv**
```csv
feature,life_expectancy,education,gdp_per_capita,...,internet_users
healthcare_spending,0.35,0.12,0.28,...,0.05
education_spending,0.18,0.42,0.31,...,0.09
...
```

**File: inter_metric_relationships.csv**
```csv
source_metric,target_metric,weight,lag,p_value
gdp_per_capita,life_expectancy,0.45,0,0.001
education,gdp_per_capita,0.38,1,0.003
life_expectancy,gdp_per_capita,0.22,0,0.008
...
```

**File: metric_correlations.csv**
```csv
metric_1,metric_2,pearson_r,spearman_rho,granger_p_value,direction
life_expectancy,gdp_per_capita,0.78,0.82,0.001,bidirectional
education,life_expectancy,0.65,0.71,0.012,education→life
...
```

### Step 7.3: Feature Metadata Export

**File: feature_metadata.csv**
```csv
feature_id,feature_name,domain,unit,source,affects_metrics
F001,healthcare_spending_gdp_pct,Healthcare Spending,%,World Bank,"life_expectancy,infant_mortality,gdp_per_capita"
F002,mean_years_schooling,Education Quality,years,UNESCO,"education,gdp_per_capita,life_expectancy"
...
```

### Step 7.4: Prediction API Script

**File: predict.py**
```python
# Loads trained models
# Input: Dictionary of feature values + country + year
# Output: Predicted 8 QOL metrics + confidence intervals
# Supports scenario testing: "What if feature X increases by 10%?"
```

---

## PHASE 8: TEMPORAL TREND ANALYSIS

### Step 8.1: Relationship Stability Over Time

- Split data into 5-year epochs: 1990-1995, 1995-2000, ..., 2020-2023
- Re-train models for each epoch
- Track how feature weights change over time
- **Output**: Time-series of feature importance

**Insight**: "Healthcare spending was critical for life expectancy in 1990s, but education matters more in 2020s"

### Step 8.2: Regime Change Detection

- Use change-point detection algorithms on relationship matrices
- Identify years when causal structures shifted significantly
- **Output**: List of structural break years with explanations

---

## PHASE 9: VALIDATION & ROBUSTNESS CHECKS

### Step 9.1: Out-of-Sample Testing

- Test on 30% held-out countries
- Report per-country prediction errors
- Identify countries where model fails (outliers)

### Step 9.2: Sensitivity Analysis

- Perturb feature values by ±10%, ±20%
- Measure impact on predictions
- Ensures model is robust, not brittle

### Step 9.3: Counterfactual Validation

- Find historical examples where a causal factor changed dramatically
- Example: Rwanda healthcare spending surge post-2000
- Check if model predictions match actual historical outcomes

---

## PHASE 10: DELIVERABLES PACKAGING

### Step 10.1: Model Files

1. **8 individual models** (H5/PKL format)
2. **1 master integrated model** (H5/PKL format)
3. **Weight matrices** (CSV)
4. **Relationship graphs** (CSV + NetworkX pickle)
5. **Feature metadata** (CSV)
6. **Normalization parameters** (JSON)

### Step 10.2: Documentation

1. **Technical report**: Methodology, hyperparameters, performance metrics
2. **Feature dictionary**: Description of all selected features
3. **API documentation**: How to use predict.py for scenarios
4. **Validation report**: Out-of-sample performance, robustness tests

### Step 10.3: Visualization Data Exports

**For hierarchical flowchart (per metric):**
```json
{
  "metric": "life_expectancy",
  "nodes": [
    {"id": "healthcare_spending", "type": "causal", "domain": "Healthcare", "weight": 0.35},
    {"id": "education_years", "type": "causal", "domain": "Education", "weight": 0.22},
    ...
  ],
  "edges": [
    {"source": "healthcare_spending", "target": "life_expectancy", "weight": 0.35},
    ...
  ]
}
```

**For master web:**
```json
{
  "nodes": [
    {"id": "life_expectancy", "type": "qol_metric", "level": 2},
    {"id": "healthcare_spending", "type": "causal", "level": 1, "domain": "Healthcare"},
    ...
  ],
  "edges": [
    {"source": "healthcare_spending", "target": "life_expectancy", "weight": 0.35, "type": "direct"},
    {"source": "life_expectancy", "target": "gdp_per_capita", "weight": 0.22, "type": "inter_metric"},
    ...
  ]
}
```

---

## SUMMARY WORKFLOW CHECKLIST

```
☐ Phase 1: Data prep (lag features, train/test split, detrending)
☐ Phase 2: Triple feature selection
  ☐ Statistical (correlation, XGBoost, SHAP) → Top 50/metric
  ☐ Thematic (domain grouping) → 30-50/metric  
  ☐ Hybrid (intersection + strategic add) → 40-60/metric
☐ Phase 3: Train 8 individual models
  ☐ Build regularized NN for each metric
  ☐ Extract feature weights
  ☐ Evaluate performance
☐ Phase 4: Inter-metric analysis
  ☐ Correlation matrix
  ☐ Granger causality
  ☐ SEM/VAR models
☐ Phase 5: Master integrated model
  ☐ Multi-output neural network
  ☐ Extract attention/Jacobian
☐ Phase 6: Deduplication & hierarchy
☐ Phase 7: Export model files + weights
☐ Phase 8: Temporal trend analysis
☐ Phase 9: Validation
☐ Phase 10: Package deliverables
```

---

**Key Principle**: Build child models first (individual metrics) for hierarchical accuracy, then master model for inter-metric prediction.

**Timeline Estimate**: 4-6 weeks for complete workflow execution

**Would you like me to detail any specific phase further, or shall I provide the code implementation for Phase 2-3?**
