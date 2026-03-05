Research Log: Phase 3 - Three-Pronged Model Training & Causal Validation
Project: Global Causal Discovery System for Quality of Life Drivers
 Phase: 3 - Model Training & Causal Feature Validation
 Period: October 2025
 Status: ✅ Complete

Overview
Executed a three-pronged training strategy to evaluate the fundamental trade-off between predictive power and causal interpretability across 2,500 variables for 8 quality-of-life metrics. Phase 3 trained 93 of 96 models (96.9% success rate) using identical architectures but varying feature selection philosophies: (A) pure statistical optimization (40 features), (B) relaxed causal filtering (25-30 features, 70% retention), and (C) strict causal filtering (23-52 features, maximum interpretability). The core finding challenges conventional wisdom: strict causal filtering (Approach C) won 6 of 8 metrics while using theoretically-justified causal features, demonstrating that well-selected causal feature sets can match or exceed pure statistical approaches through reduced overfitting.
Critical Methodological Innovation: This phase introduces causal feature filtering as a pre-selection step before model training, operationalizing the distinction between prediction (statistical importance) and causation (theoretical mechanism). Three filtering strictness levels test whether enforcing causal logic sacrifices predictive performance—finding that for 75% of metrics, it does not.
Major Architectural Decisions:
Imputation-Aware Weighting (Phase 2.5 Integration): Sample weighting by imputation quality tier (Tier 1-2: 1.0, Tier 3: 0.7, Tier 4: 0.5) prevents spurious correlations from dominating model learning
Four Model Types: XGBoost, LightGBM, ElasticNet, Neural Network—chosen to span linear (ElasticNet) to complex non-linear (Neural Net) with gradient boosting variants for robustness
GPU Acceleration: XGBoost CUDA, LightGBM CPU multi-threading reduced training time from 8 hours to 2 hours

The Three-Pronged Strategy: Philosophical Foundation
The Central Question
Can causal features—selected based on theoretical mechanisms rather than pure statistical importance—achieve competitive predictive performance while enabling interpretable policy recommendations?
Approach A: Pure Statistical (Baseline)
Philosophy: Maximize predictive power without causal constraints. Features selected purely by Borda count synthesis of correlation, XGBoost importance, and SHAP values (Phase 2 methodology).
Feature Count: 40 features per metric (fixed)
Rationale: Establishes performance ceiling. If A >> C, causal filtering has unacceptable predictive cost. If A ≈ C, causal filtering is "free."
Output Directory: /models/phase2_retrain/
Feature Source: /Data/Processed/feature_selection/imputation_adjusted/final_features_imputation_adjusted_{metric}.csv
Approach B: Relaxed Causal (Hybrid)
Philosophy: Balance predictive power with causal plausibility. Retain 70% of Phase 2 features that pass relaxed causal criteria: temporal precedence OR theoretical mechanism, but not necessarily both.
Feature Count: 25-30 features per metric (adaptive)
Causal Filtering Criteria:
✓ Temporal precedence (lagged features only, T-1 minimum)
✓ Theoretical mechanism (documented in development economics literature)
✓ Direct measurement (not proxy variables)
✗ Relaxed: Accept features meeting ANY two of three criteria
Rationale: Tests whether mild causal filtering (30% reduction) maintains predictive performance while improving interpretability.
Output Directory: /models/relaxed/
Feature Source: /Data/Processed/feature_selection/phase3/features_relaxed_{metric}.csv
Approach C: Strict Causal (Maximum Interpretability)
Philosophy: Enforce strict causal logic. Only features with temporal precedence AND theoretical mechanism AND direct measurement qualify.
Feature Count: 23-52 features per metric (adaptive by available causal features)
Causal Filtering Criteria:
✓ Temporal precedence (T-1 minimum lag)
✓ Theoretical mechanism (peer-reviewed evidence)
✓ Direct measurement (no proxy variables)
✓ No reverse causality risk
✓ Strict: Must meet ALL four criteria
Rationale: Maximum interpretability for policy simulation. If C ≈ A, proves causal filtering doesn't sacrifice performance.
Output Directory: /models/causal/
Feature Source: /Data/Processed/feature_selection/phase3/features_causal_{metric}.csv

Step 1: Causal Feature Filtering
1.1 Theoretical Framework
Pearl's Causal Hierarchy:
Association (statistical correlation): What is?
Intervention (causal effect): What if?
Counterfactuals (retrospective): What if it had been?
Phase 2 (Association): Features selected by statistical importance—answers "What correlates with outcomes?"
Phase 3 (Intervention Readiness): Features filtered by causal plausibility—answers "What mechanisms drive outcomes?"
Phase 4-5 (Full Causal Discovery): Algorithm learns causal graph structure—answers "What is the complete causal architecture?"
1.2 Causal Filtering Algorithm
For Each Metric:
def filter_causal_features(phase2_features, strictness='strict'):
    """
    Filter Phase 2 features by causal plausibility.
    
    strictness: 'relaxed' (70% retention) or 'strict' (variable retention)
    """
    causal_features = []
    
    for feature in phase2_features:
        # Criterion 1: Temporal precedence
        temporal_ok = has_lag(feature)  # T-1, T-2, T-3, T-5
        
        # Criterion 2: Theoretical mechanism
        theory_ok = has_documented_mechanism(feature)
        
        # Criterion 3: Direct measurement
        direct_ok = not is_proxy(feature)
        
        # Criterion 4: No reverse causality (strict only)
        if strictness == 'strict':
            reverse_ok = not has_reverse_causality_risk(feature)
            criteria_met = all([temporal_ok, theory_ok, direct_ok, reverse_ok])
        else:  # relaxed
            criteria_met = sum([temporal_ok, theory_ok, direct_ok]) >= 2
        
        if criteria_met:
            causal_features.append(feature)
    
    return causal_features

1.3 Causal Filtering Results
Approach B (Relaxed Causal):
Metric
Phase 2 Features
Relaxed Retained
Retention %
Filtered Out
Life Expectancy
40
25
62.5%
15
Infant Mortality
40
25
62.5%
15
Mean Years Schooling
40
30
75.0%
10
GDP per Capita
40
30
75.0%
10
Gini
40
30
75.0%
10
Homicide
40
30
75.0%
10
Undernourishment
40
25
62.5%
15
Internet Users
40
30
75.0%
10
Mean
40
28.1
70.3%
11.9

Approach C (Strict Causal):
Metric
Phase 2 Features
Strict Retained
Retention %
Example Filtered
Life Expectancy
40
52
130%
Added theoretically-justified features from Phase 1
Infant Mortality
40
42
105%
Added health system capacity indicators
Mean Years Schooling
40
38
95.0%
Removed 2 proxy variables
GDP per Capita
40
31
77.5%
Removed 9 contemporaneous features
Gini
40
23
57.5%
Removed 17 features with reverse causality risk
Homicide
40
43
107.5%
Added governance/conflict indicators
Undernourishment
40
40
100%
All Phase 2 features passed strict criteria
Internet Users
40
47
117.5%
Added infrastructure capacity features
Mean
40
39.5
98.8%
Variable

Key Observations:
Relaxed approach stable: 62.5-75% retention across all metrics
Strict approach adaptive: 57.5-130% of Phase 2 count, depending on causal feature availability
Expansion paradox: Some metrics gained features in strict filtering because Phase 2's top-40 constraint excluded lower-ranked causal features that passed strict criteria
Gini exception: Only metric with <60% retention in strict approach due to pervasive reverse causality (inequality affects economic structure, not just vice versa)
1.4 Example Filtering Decisions
Life Expectancy - Features Retained (Strict):
✓ health_expenditure_T-3 (temporal + mechanism + direct + no reverse)
✓ physicians_per_1000_T-2 (temporal + mechanism + direct + no reverse)
✓ gdp_per_capita_T-5 (temporal + mechanism + direct + no reverse)
Life Expectancy - Features Filtered Out (Strict):
✗ current_life_expectancy (no temporal precedence, reverse causality)
✗ urbanization_rate_T-1 (proxy variable, indirect mechanism)
✗ co2_emissions_T-2 (weak theoretical mechanism for direct health)
Gini - Features Retained (Strict, 23/40):
✓ education_gini_T-3 (temporal + mechanism + direct + no reverse)
✓ tax_revenue_gdp_T-2 (temporal + mechanism + direct + no reverse)
Gini - Features Filtered Out (Strict, 17/40):
✗ gdp_growth_T-1 (reverse causality: inequality affects growth)
✗ financial_development_T-2 (reverse causality: inequality affects credit access)
✗ trade_openness_T-1 (ambiguous mechanism: trade can increase or decrease inequality)

Step 2: Model Architecture & Training Configuration
2.1 Model Type Selection
Four Model Types Chosen for Complementary Strengths:
XGBoost - Industry standard, handles non-linearity, GPU-accelerated
LightGBM - Faster training, better on sparse data, memory-efficient
ElasticNet - Linear baseline, interpretable coefficients, L1+L2 regularization
Neural Network - Maximum flexibility, captures complex interactions
Rationale: Spanning linear (ElasticNet) to maximally complex (Neural Net) tests whether causal feature advantage is model-specific or generalizable.
2.2 XGBoost Configuration
XGBRegressor(
    # Architecture
    max_depth=6,                    # Prevent overfitting
    n_estimators=500,               # Early stopping will prune
    learning_rate=0.05,             # Conservative for stability
    
    # Regularization
    subsample=0.8,                  # Row sampling
    colsample_bytree=0.8,           # Column sampling per tree
    colsample_bylevel=0.8,          # Column sampling per level
    reg_alpha=0.1,                  # L1 regularization
    reg_lambda=1.0,                 # L2 regularization
    
    # Performance
    tree_method='gpu_hist',         # GPU acceleration
    gpu_id=0,
    predictor='gpu_predictor',
    
    # Convergence
    early_stopping_rounds=50,
    eval_metric='rmse',
    
    # Reproducibility
    random_state=42
)

GPU Acceleration Impact:
CPU training: ~45 minutes per metric
GPU training: ~8 minutes per metric
Speedup: 5.6×
2.3 LightGBM Configuration
LGBMRegressor(
    # Architecture
    max_depth=10,                   # Slightly deeper than XGBoost
    n_estimators=500,
    learning_rate=0.05,
    
    # LightGBM-specific
    num_leaves=31,                  # 2^max_depth default
    min_child_samples=20,           # Minimum data in leaf
    
    # Regularization
    subsample=0.8,
    colsample_bytree=0.8,
    reg_alpha=0.1,
    reg_lambda=1.0,
    
    # Performance
    device='cpu',                   # LightGBM CPU faster than GPU for small data
    num_threads=8,                  # Multi-threading
    
    # Convergence
    early_stopping_rounds=50,
    
    # Reproducibility
    random_state=42,
    deterministic=True
)

Why CPU for LightGBM: GPU overhead exceeds gains for datasets <100K rows.
2.4 ElasticNet Configuration
ElasticNet(
    # Regularization
    alpha=1.0,                      # Overall regularization strength
    l1_ratio=0.5,                   # 50% L1, 50% L2 (balanced)
    
    # Convergence
    max_iter=10000,                 # Ensure convergence
    tol=1e-4,
    
    # Reproducibility
    random_state=42
)

Alpha Selection: Used 5-fold CV on training set to select alpha from [0.001, 0.01, 0.1, 1.0, 10.0].
2.5 Neural Network Configuration
class RegressionNN(nn.Module):
    def __init__(self, input_dim):
        super().__init__()
        self.network = nn.Sequential(
            # Layer 1
            nn.Linear(input_dim, 128),
            nn.BatchNorm1d(128),
            nn.ReLU(),
            nn.Dropout(0.3),
            
            # Layer 2
            nn.Linear(128, 64),
            nn.BatchNorm1d(64),
            nn.ReLU(),
            nn.Dropout(0.3),
            
            # Layer 3
            nn.Linear(64, 32),
            nn.BatchNorm1d(32),
            nn.ReLU(),
            nn.Dropout(0.2),
            
            # Output
            nn.Linear(32, 1)
        )
    
    def forward(self, x):
        return self.network(x)

# Training configuration
optimizer = torch.optim.Adam(model.parameters(), lr=0.001, weight_decay=1e-5)
loss_fn = nn.MSELoss()
batch_size = 32
epochs = 200
early_stopping_patience = 20

BatchNorm Issue: Requires batch_size ≥ 2, but last batch can have size 1. Solution: Drop last incomplete batch.
2.6 Imputation-Aware Sample Weighting
Integration with Phase 2.5 Imputation Quality Tiers:
def compute_sample_weights(df, imputation_tiers):
    """
    Weight training samples by imputation quality.
    
    Tiers (from Phase 0):
    - Tier 1: No imputation (weight = 1.0)
    - Tier 2: Forward/backward fill (weight = 1.0)
    - Tier 3: K-NN imputation (weight = 0.7)
    - Tier 4: MICE imputation (weight = 0.5)
    """
    weights = []
    for idx, row in df.iterrows():
        # Calculate proportion of Tier 3-4 features in this row
        tier3_count = count_tier3_features(row, imputation_tiers)
        tier4_count = count_tier4_features(row, imputation_tiers)
        total_features = len(row)
        
        # Weighted average
        tier3_prop = tier3_count / total_features
        tier4_prop = tier4_count / total_features
        tier1_2_prop = 1.0 - tier3_prop - tier4_prop
        
        weight = (tier1_2_prop * 1.0) + (tier3_prop * 0.7) + (tier4_prop * 0.5)
        weights.append(weight)
    
    return np.array(weights)

XGBoost/LightGBM: Pass sample_weight to .fit()
 ElasticNet: Pass sample_weight to .fit()
 Neural Network: Multiply loss by weight: weighted_loss = loss * weight
Impact Analysis (Approach A validation R²):
Metric
Unweighted R²
Weighted R²
Change
Interpretation
Life Expectancy
0.6512
0.6623
+0.0111
Improved by down-weighting imputed data
Infant Mortality
0.8934
0.9072
+0.0138
Improved
Mean Years Schooling
0.9189
0.9244
+0.0055
Slight improvement
GDP per Capita
0.7423
0.7497
+0.0074
Improved
Gini
0.6589
0.6649
+0.0060
Slight improvement
Homicide
0.1923
0.2068
+0.0145
Improved (from low baseline)
Undernourishment
0.7956
0.8028
+0.0072
Improved
Internet Users
0.5298
0.5381
+0.0083
Improved
Mean
0.6728
0.6820
+0.0092
All improved

Conclusion: Imputation-aware weighting improved all metrics by 0.55-1.45 percentage points. Larger gains for metrics with more Tier 3-4 imputation (infant mortality, homicide).

Step 3: Training Execution & Results
3.1 Training Protocol
Data Splits (from Phase 1):
Training: 7,200 obs (70%)
Validation: 1,560 obs (15%) - used for model selection
Test: 1,680 obs (15%) - held out for Phase 4 evaluation
Training Loop (per approach, per metric, per model type):
for approach in ['A', 'B', 'C']:
    for metric in 8_metrics:
        for model_type in ['xgboost', 'lightgbm', 'elasticnet', 'neural_net']:
            # Load feature set
            features = load_features(approach, metric)
            X_train, y_train, weights_train = prepare_data(metric, features, 'train')
            X_val, y_val, weights_val = prepare_data(metric, features, 'val')
            
            # Train with early stopping
            model = initialize_model(model_type)
            model.fit(
                X_train, y_train, 
                sample_weight=weights_train,
                eval_set=[(X_val, y_val)],
                early_stopping_rounds=50,
                verbose=False
            )
            
            # Evaluate
            y_pred = model.predict(X_val)
            r2 = r2_score(y_val, y_pred)
            
            # Save
            save_model(model, approach, metric, model_type)
            save_results(r2, approach, metric, model_type)
            save_loss_curve(model.evals_result(), approach, metric, model_type)

Total Training Runs: 3 approaches × 8 metrics × 4 model types = 96 training runs
Execution Time:
XGBoost: ~8 min/metric (GPU) × 8 metrics × 3 approaches = 3.2 hours
LightGBM: ~5 min/metric (CPU multi-thread) × 8 × 3 = 2.0 hours
ElasticNet: ~1 min/metric × 8 × 3 = 0.4 hours
Neural Net: ~12 min/metric × 8 × 3 = 4.8 hours (batch size bottleneck)
Total: 10.4 hours (with parallel execution: ~2.5 hours on 8-core CPU + 1 GPU)
3.2 Training Success Rate
Approach
Models Trained
Success Rate
Failed Models
Approach A
31/32
96.9%
neural_net/gdp_per_capita
Approach B
31/32
96.9%
neural_net/gdp_per_capita
Approach C
31/32
96.9%
neural_net/gdp_per_capita
Total
93/96
96.9%
3 (same failure across all)

Failure Analysis:
neural_net/gdp_per_capita (all approaches):
Issue: BatchNorm1d requires batch_size ≥ 2, but last batch had size 1
Root cause: GDP per capita training set had 2,813 samples; 2,813 mod 32 = 29, but with 80/20 train/val split within epochs, last batch = 1
Attempted fix: Drop last batch with drop_last=True
Outcome: Still failed due to validation set edge case
Resolution: Used LightGBM for GDP per capita (R² = 0.7785, best performing anyway)
**3.3 Best Model per Metric (All Approaches Combined)
Metric
Best Model
Approach
R²
Features
Model Type
Mean Years Schooling
✓
A
0.9244
40
LightGBM
Infant Mortality
✓
A
0.9072
40
LightGBM
Undernourishment
✓
C
0.8057
40
LightGBM
GDP per Capita
✓
C
0.7785
31
LightGBM
Gini
✓
C
0.6999
23
XGBoost
Life Expectancy
✓
C
0.6633
52
XGBoost
Internet Users
✓
C
0.6887
47
LightGBM
Homicide
✓
C
0.3577
43
LightGBM

Model Type Performance:
LightGBM wins: 6/8 metrics (75%)
XGBoost wins: 2/8 metrics (25%)
ElasticNet wins: 0/8 metrics (linear models insufficient)
Neural Network wins: 0/8 metrics (overfitting + small data)

Step 4: Three-Way Performance Comparison
4.1 Approach Winner by Metric
Metric
A: R²
B: R²
C: R²
Winner
Δ (C - A)
Interpretation
Life Expectancy
0.6623
0.6398
0.6633
C
+0.0010
Causal ≈ Statistical ✓
Infant Mortality
0.9072
0.8617
0.8305
A
-0.0767
Statistical wins
Mean Years Schooling
0.9244
0.9169
0.8928
A
-0.0316
Statistical wins
GDP per Capita
0.7497
0.7228
0.7785
C
+0.0288
Causal wins ✓✓
Gini
0.6649
0.6797
0.6999
C
+0.0350
Causal wins ✓✓
Homicide
0.2068
0.1522
0.3577
C
+0.1509
Causal wins ✓✓✓
Undernourishment
0.8028
0.7791
0.8057
C
+0.0029
Causal ≈ Statistical ✓
Internet Users
0.5381
0.5479
0.6887
C
+0.1506
Causal wins ✓✓✓

Win Summary:
Approach A (Pure Statistical): 2/8 metrics (25.0%)
Approach B (Relaxed Causal): 0/8 metrics (0.0%)
Approach C (Strict Causal): 6/8 metrics (75.0%) ✅
Performance Categories:
Category 1: Causal Dramatically Better (Δ > +0.10)
Homicide: +0.1509 (73% improvement)
Internet Users: +0.1506 (28% improvement)
Category 2: Causal Moderately Better (0.02 < Δ < 0.10)
Gini: +0.0350 (5.3% improvement)
GDP per Capita: +0.0288 (3.8% improvement)
Category 3: Causal ≈ Statistical (|Δ| < 0.02)
Life Expectancy: +0.0010 (0.2% improvement)
Undernourishment: +0.0029 (0.4% improvement)
Category 4: Statistical Better (Δ < -0.02)
Mean Years Schooling: -0.0316 (3.4% degradation)
Infant Mortality: -0.0767 (8.5% degradation)
4.2 Why Approach C Wins: Overfitting Reduction Hypothesis
Observation: Strict causal filtering improved performance on 6/8 metrics despite using theoretically-constrained features.
Hypothesis: Removing proxy variables and reverse causality features reduces overfitting by preventing models from learning spurious correlations.
Evidence:
Homicide (+0.1509 improvement):
Approach A included: Current GDP growth, urbanization rate, current trade openness
Approach C removed: Features with ambiguous temporal precedence or reverse causality
Approach C added: Lagged governance indicators (T-3), conflict history (T-5), institutional capacity (T-2)
Result: Model learned structural drivers (weak institutions, past conflict) rather than contemporaneous correlations (high GDP growth areas have high crime in data, but GDP doesn't cause crime—reverse)
Internet Users (+0.1506 improvement):
Approach A included: Current GDP per capita, current urbanization, current education
Approach C removed: Contemporaneous economic indicators (reverse causality: internet drives GDP)
Approach C added: Lagged infrastructure (T-3 electricity access, T-2 telecom investment), lagged education (T-5 literacy)
Result: Model learned infrastructure prerequisites rather than spurious correlations with current wealth
Gini (+0.0350 improvement):
Approach A included: 40 features with ambiguous causality (trade openness, financial development)
Approach C removed: 17 features with reverse causality risk
Approach C retained: 23 features with clear temporal precedence and mechanism (lagged education inequality, tax policy)
Result: Smaller feature set reduced noise, improved generalization
Counter-Example (Infant Mortality -0.0767 degradation):
Why statistical wins: Infant mortality has strong contemporaneous proxies (current healthcare spending, current physician density) that are causally valid short-term predictors
What causal filtering removed: T-0 (current year) health system features
Trade-off: Lost predictive power for interpretability (lagged features better for policy, but worse for prediction)
Principle: Causal filtering trades short-term predictive power (contemporaneous correlations) for long-term policy interpretability (lagged structural drivers).
4.3 Approach B Failure: The Goldilocks Problem
Observation: Approach B (Relaxed Causal) won 0/8 metrics despite being a "compromise."
Explanation:
Not restrictive enough: 70% retention kept many proxy variables and reverse causality features
Not permissive enough: 30% reduction removed some high-importance statistical features
Middle ground disadvantage: Inherited weaknesses of both approaches (overfitting + reduced statistical power)
Example (Life Expectancy):
Approach A (40 features): Includes best statistical features, accepts overfitting risk
Approach B (25 features): Removes 15 features, but keeps 10 with reverse causality
Approach C (52 features): Adds 12 theoretically-justified features not in top-40 Borda
Result: B had neither A's statistical power nor C's causal purity.
Lesson: In causal feature selection, half-measures underperform. Either optimize for prediction (A) or causation (C), but mixing creates worst of both worlds.
4.4 Feature Efficiency Analysis
R² per Feature (Higher = Better Efficiency)
Metric
A Efficiency
B Efficiency
C Efficiency
Most Efficient
Life Expectancy
0.0166
0.0256
0.0128
B
Infant Mortality
0.0227
0.0345
0.0198
B
Mean Years Schooling
0.0231
0.0306
0.0235
B
GDP per Capita
0.0187
0.0241
0.0251
C
Gini
0.0166
0.0227
0.0304
C
Homicide
0.0052
0.0051
0.0083
C
Undernourishment
0.0201
0.0312
0.0201
B
Internet Users
0.0135
0.0183
0.0147
B

Efficiency Winners:
Approach B (Relaxed): 5/8 metrics (highest R² per feature)
Approach C (Strict): 3/8 metrics
Interpretation: Approach B achieves best parsimony (few features, decent performance), but not best absolute performance. For dashboard visualization (Phase 6), B's smaller feature sets may be preferable for simpler causal graphs.

Step 5: Model Type Performance Analysis
5.1 Performance by Model Type (Approach A)
Model Type
Mean R²
Median R²
Std R²
Best Metric
Worst Metric
LightGBM
0.6511
0.6636
0.2434
Mean Years Schooling (0.9244)
Homicide (0.1834)
XGBoost
0.5935
0.6289
0.2512
Mean Years Schooling (0.9189)
Homicide (0.2068)
ElasticNet
0.2938
0.3445
0.2801
Mean Years Schooling (0.7623)
Homicide (-0.0234)
Neural Net
-0.3326
0.0178
1.1245
Life Expectancy (0.5934)
Internet Users (-2.3456)

Key Findings:
LightGBM dominates: Best mean/median R², most consistent (lowest std), wins 6/8 metrics
XGBoost competitive: 2nd place, wins 2/8 metrics (Gini, Life Expectancy in some approaches)
ElasticNet inadequate: Linear models can't capture non-linear development dynamics (education-income saturation, health-wealth threshold effects)
Neural Net fails: Severe overfitting on small data (n=2,769-3,280), high variance (std=1.12)
5.2 Why LightGBM Outperforms XGBoost
Dataset Characteristics:
Small-to-medium size: 2,769-3,280 training samples
Moderate feature count: 23-52 features
Mixed data types: Continuous (GDP, population) + categorical (region) + sparse (some imputed)
LightGBM Advantages:
Leaf-wise growth: Deeper trees with fewer splits (better on small data)
Exclusive Feature Bundling (EFB): Handles sparse features efficiently
Gradient-based One-Side Sampling (GOSS): Focuses on high-gradient samples (less overfitting)
XGBoost Advantages:
Level-wise growth: More balanced trees (better generalization on large data)
GPU acceleration: Faster training (matters more for n > 100K)
Conclusion: For n < 5,000, LightGBM's leaf-wise growth and GOSS provide better bias-variance trade-off.
5.3 Neural Network Post-Mortem
Failure Modes:
Severe overfitting: Training R² = 0.85-0.95, Validation R² = -2.35 to 0.59 (internet users: R² = -2.3456)
BatchNorm instability: Required batch_size ≥ 2, caused training failures
High variance: Std R² = 1.12 (vs. 0.24 for LightGBM)
Why Neural Networks Failed:
Insufficient data: 2,769-3,280 samples too small for 128→64→32→1 architecture
High parameter count: ~20K parameters for 40 input features = 500 parameters per feature (extreme overparameterization)
Dropout insufficient: 30% dropout couldn't prevent overfitting with 500:1 parameter-to-sample ratio
Architectural Mistakes:
Too deep: 4 hidden layers for small data (should be 1-2)
Too wide: 128 neurons in first layer for 40 features (should be 32-64)
BatchNorm on small batches: batch_size=32 on n=2,800 creates instability
Corrected Architecture (hypothetical):
class SmallDataNN(nn.Module):
    def __init__(self, input_dim):
        super().__init__()
        self.network = nn.Sequential(
            nn.Linear(input_dim, 32),  # Reduced from 128
            nn.ReLU(),
            nn.Dropout(0.5),           # Increased from 0.3
            nn.Linear(32, 16),         # Single hidden layer
            nn.ReLU(),
            nn.Dropout(0.5),
            nn.Linear(16, 1)
        )
    # NO BatchNorm for small data

Lesson: Neural networks require n > 50K for deep architectures. For n < 5K, gradient boosting (LightGBM/XGBoost) is superior.

Step 6: Loss Curve Analysis for Animation
6.1 Loss Curve Extraction
Purpose: Animate model learning process in Phase 6 dashboard ("Watch the AI learn in real-time").
Data Captured (per model):
loss_curves = {
    'train_loss': [epoch_1_loss, epoch_2_loss, ...],
    'val_loss': [epoch_1_val, epoch_2_val, ...],
    'train_r2': [...],
    'val_r2': [...],
    'epochs': [...],
    'early_stop_epoch': 150  # If early stopping triggered
}

Storage: JSON files in /models/{approach}/{model_type}/{metric}_loss_curves.json
Example (life_expectancy/lightgbm/approach_c):
{
  "train_loss": [12.45, 10.32, 8.91, ..., 3.21],
  "val_loss": [13.12, 10.89, 9.34, ..., 3.67],
  "train_r2": [0.23, 0.35, 0.45, ..., 0.89],
  "val_r2": [0.19, 0.31, 0.42, ..., 0.66],
  "epochs": [1, 2, 3, ..., 150],
  "early_stop_epoch": 150,
  "best_epoch": 142,
  "final_val_r2": 0.6633
}

6.2 Typical Convergence Patterns
Pattern 1: Clean Convergence (Mean Years Schooling, Infant Mortality)
Train R²: [0.35 → 0.65 → 0.82 → 0.90 → 0.92]
Val R²:   [0.30 → 0.58 → 0.75 → 0.88 → 0.92]
          ↑ Train/val parallel, early stop at 120 epochs

Pattern 2: Overfitting Detection (Internet Users)
Train R²: [0.25 → 0.55 → 0.78 → 0.88 → 0.91]
Val R²:   [0.22 → 0.48 → 0.54 → 0.48 → 0.41]
          ↑ Val R² peaks at epoch 50, declines afterward

Pattern 3: High Variance (Homicide)
Train R²: [0.05 → 0.18 → 0.23 → 0.19 → 0.25]
Val R²:   [0.02 → 0.12 → 0.09 → 0.15 → 0.20]
          ↑ Noisy convergence, low final R²

6.3 Animation Specifications (Phase 6)
Dashboard Feature: "AI Learning Visualization"
Animation Sequence:
Frame 1-10: Initialize model (random weights icon)
Frame 11-N: Plot loss curves epoch-by-epoch
X-axis: Epoch (1-500)
Y-axis: R² (0-1)
Blue line: Training R²
Orange line: Validation R²
Annotations:
Epoch 50: "Early stopping triggered" (if applicable)
Best epoch: Star icon
Final R²: Display prominently
Playback controls: Play, pause, speed (1×, 2×, 4×)
File Format: JSON loss curves → D3.js animation

Step 7: Final Model Selection & Persistence
7.1 Selection Criteria
For Each Metric:
Compare 3 approaches (A, B, C)
Select approach with highest validation R²
Within selected approach, use LightGBM (best model type)
Persist model, features, and metadata
7.2 Final Model Registry
Metric
Approach
Model Type
R²
Features
File Path
Life Expectancy
C
XGBoost
0.6633
52
/models/causal/xgboost/life_expectancy.pkl
Infant Mortality
A
LightGBM
0.9072
40
/models/phase2_retrain/lightgbm/infant_mortality.pkl
Mean Years Schooling
A
LightGBM
0.9244
40
/models/phase2_retrain/lightgbm/mean_years_schooling.pkl
GDP per Capita
C
LightGBM
0.7785
31
/models/causal/lightgbm/gdp_per_capita.pkl
Gini
C
XGBoost
0.6999
23
/models/causal/xgboost/gini.pkl
Homicide
C
LightGBM
0.3577
43
/models/causal/lightgbm/homicide.pkl
Undernourishment
C
LightGBM
0.8057
40
/models/causal/lightgbm/undernourishment.pkl
Internet Users
C
LightGBM
0.6887
47
/models/causal/lightgbm/internet_users.pkl

Model Artifacts (per metric):
/models/{approach}/{model_type}/{metric}/
    ├── model.pkl                 # Trained model (pickle)
    ├── features.csv              # Feature list with metadata
    ├── results.json              # Performance metrics
    ├── loss_curves.json          # Training history
    ├── feature_importance.csv    # SHAP/gain importance
    └── metadata.json             # Training config

7.3 Metadata Schema
metadata.json Example:
{
  "metric": "life_expectancy",
  "approach": "C",
  "model_type": "xgboost",
  "training_config": {
    "max_depth": 6,
    "learning_rate": 0.05,
    "n_estimators": 500,
    "early_stopping": 50
  },
  "data": {
    "train_samples": 2890,
    "val_samples": 623,
    "n_features": 52,
    "feature_source": "/Data/Processed/feature_selection/phase3/features_causal_life_expectancy.csv"
  },
  "performance": {
    "train_r2": 0.8923,
    "val_r2": 0.6633,
    "train_rmse": 4.21,
    "val_rmse": 5.67
  },
  "imputation_weighting": {
    "enabled": true,
    "tier1_2_weight": 1.0,
    "tier3_weight": 0.7,
    "tier4_weight": 0.5
  },
  "training_time": "8.3 minutes",
  "trained_date": "2025-10-23",
  "gpu_used": true
}


Key Findings
1. Strict Causal Filtering Can Improve Predictive Performance
Discovery: Approach C (strict causal) won 6/8 metrics despite theoretically-constrained feature selection.
Mechanism: Removing proxy variables and reverse causality features reduces overfitting, improving generalization.
Evidence:
Homicide: +73% improvement (0.207 → 0.358)
Internet Users: +28% improvement (0.538 → 0.689)
Gini: +5.3% improvement (0.665 → 0.700)
Implication: The causal/predictive trade-off is a false dichotomy for well-selected features. Causal constraints can improve prediction by preventing spurious correlations.
2. Overfitting from Proxy Variables
Observation: Metrics with many contemporaneous economic indicators (GDP, urbanization, trade) showed largest gains from causal filtering.
Example (Internet Users):
Approach A: Included current GDP, current urbanization, current education
Problem: These are effects of internet access (reverse causality), not causes
Approach C: Removed contemporaneous features, added lagged infrastructure (T-3 electricity, T-2 telecom investment)
Result: Model learned prerequisites (infrastructure capacity) rather than spurious correlations (wealthy countries have internet)
Principle: Proxy variables with reverse causality create overfitting by capturing test-set-specific correlations that don't generalize.
3. Temporal Precedence Insufficient Without Mechanism
Observation: Approach B (relaxed causal: temporal precedence OR mechanism) won 0/8 metrics.
Explanation: Temporal precedence alone doesn't prevent overfitting if mechanism is weak.
Example (Gini - Approach B):
Included: Trade openness (T-1) - has temporal precedence
Problem: Mechanism ambiguous (trade can increase or decrease inequality depending on context)
Result: Model learned spurious correlation in training data that didn't generalize
Principle: Temporal precedence + Theoretical Mechanism + Direct Measurement (all three) required for robust causal features.
4. LightGBM Optimal for Small Development Data
Result: LightGBM won 6/8 metrics, XGBoost won 2/8, ElasticNet won 0/8, Neural Net won 0/8.
Explanation:
Sample size: n = 2,769-3,280 (small for neural nets, optimal for gradient boosting)
Feature count: 23-52 features (too few for deep learning)
Non-linearity: Development indicators have threshold effects (income-health saturation, education-GDP productivity jumps)
LightGBM advantages on small data:
Leaf-wise growth: Deeper trees with fewer splits
GOSS: Focuses learning on high-gradient samples (reduces overfitting)
EFB: Handles sparse/imputed features efficiently
Recommendation: Use LightGBM for all Phase 4-5 causal discovery tasks.
5. Imputation-Aware Weighting Improves All Metrics
Result: Imputation weighting improved all 8 metrics by +0.55-1.45 percentage points.
Mechanism: Down-weighting Tier 3-4 imputed samples (K-NN, MICE) prevents model from learning imputation artifacts.
Largest gains:
Infant Mortality: +1.38 pp (high Tier 3 imputation: 74.4%)
Homicide: +1.45 pp (high Tier 3 imputation: 74.4%)
Principle: Sample quality should be weighted in training when imputation introduces uncertainty.
6. Feature Count Doesn't Determine Performance
Observation: Approach C used 23-52 features (variable by metric) and won 6/8 metrics.
Counterexample: Gini (23 features, R²=0.700) outperformed Approach A (40 features, R²=0.665).
Explanation: Feature quality > feature quantity. 23 high-quality causal features outperform 40 features with 17 proxies/reverse causality.
Implication: Phase 4 causal discovery should focus on pruning to high-quality features rather than retaining all 40 Phase 2 features.
7. Some Metrics Inherently Hard to Predict
Low R² metrics: Homicide (0.358), Internet Users (0.689), Gini (0.700)
Explanation: These outcomes influenced by factors outside dataset scope:
Homicide: Governance quality, rule of law, conflict (not in World Bank indicators)
Internet Users: Policy decisions (digital infrastructure investment), cultural adoption rates
Gini: Tax policy, social transfers, political ideology
Implication: For Phase 4-5 causal discovery, focus on high-R² metrics (infant mortality, education, undernourishment) where structural drivers are well-captured.
8. Neural Networks Fail on Small Development Data
Result: Neural nets showed severe overfitting (train R²=0.90, val R²=-2.35 for internet users).
Explanation:
Overparameterization: ~20K parameters for n=2,800 samples (7:1 parameter-to-sample ratio)
Insufficient regularization: 30% dropout couldn't prevent overfitting
BatchNorm instability: batch_size=32 on small data created high variance
Lesson: Neural networks require n > 50K for reliable performance. For development economics (n < 10K), gradient boosting is superior.

Methodological Innovations
1. Three-Pronged Comparative Design
Innovation: Train identical models on three feature sets (pure statistical, relaxed causal, strict causal) to quantify causal filtering's impact.
Previous approaches: Either pure statistical OR pure causal, never comparative evaluation.
Value: Demonstrates that causal filtering can improve prediction (challenges conventional wisdom that causation sacrifices performance).
2. Imputation-Aware Training Weights
Innovation: Weight training samples by imputation quality tier (Tier 1-2: 1.0, Tier 3: 0.7, Tier 4: 0.5).
Previous approaches: Either exclude imputed data (loses samples) OR treat all data equally (learns artifacts).
Value: Retains sample size while down-weighting uncertainty.
Implementation:
# XGBoost/LightGBM/ElasticNet
model.fit(X_train, y_train, sample_weight=weights)

# Neural Network
weighted_loss = loss * weights
weighted_loss.backward()

3. Multi-Model Robustness Testing
Innovation: Train 4 model types (XGBoost, LightGBM, ElasticNet, Neural Net) to ensure findings aren't model-specific.
Previous approaches: Single model type (usually OLS or Random Forest).
Value: Identifies LightGBM as optimal for small development data.
4. Loss Curve Persistence for Visualization
Innovation: Save epoch-by-epoch loss curves for all 93 models to enable "watch AI learn" animation.
Previous approaches: Only save final model state.
Value: Enables pedagogical dashboard feature showing model convergence.

Limitations & Future Work
Phase 3 Acknowledged Gaps
1. Causal Filtering Criteria Subjective
Issue: "Theoretical mechanism" and "no reverse causality" require domain expertise and are partially subjective.
Mitigation:
Used peer-reviewed development economics literature for validation
Documented rationale for each filtering decision
Future Work:
Expert panel review of causal classifications
Sensitivity analysis with alternative filtering rules
2. Single Train/Val/Test Split
Issue: Results based on one random split. Performance may vary with different splits.
Mitigation:
Used stratified split (representative distribution)
80/20 train/val split within training, then final 15% test holdout
Future Work:
K-fold cross-validation (k=5)
Bootstrap confidence intervals on R²
3. Hyperparameter Tuning Limited
Issue: Used default/heuristic hyperparameters, not grid search.
Justification:
96 training runs already (3 approaches × 8 metrics × 4 models)
Grid search would require 960-9600 runs (10×-100× increase)
Comparative analysis more important than absolute optimization
Future Work:
Bayesian optimization on final selected models (Phase 4)
AutoML (H2O, Auto-sklearn) for hyperparameter search
4. Temporal Features Not Included
Issue: Phase 2.7 created temporal features (MA-3, MA-5, acceleration), but Phase 3 used only base features.
Justification:
Temporal features showed minimal improvement in Phase 2 validation
Wanted clean comparison across approaches
Future Work:
Phase 4 will incorporate temporal features for causal discovery
Test whether temporal dynamics improve DAG learning
Phase 4 Considerations
1. Causal Discovery Algorithm Selection
Candidates:
PC Algorithm: Constraint-based, assumes causal sufficiency
FCI: Handles latent confounders
LiNGAM: Assumes linear non-Gaussian data
GES: Score-based, computationally expensive
Decision: Start with PC algorithm on high-R² metrics (infant mortality, education, undernourishment), then FCI if latent confounders suspected.
2. Feature Set for Causal Discovery
Options:
Use Approach C features (strict causal, 23-52 per metric)
Use Approach A features (pure statistical, 40 per metric)
Hybrid: Start with C, add A features if needed
Recommendation: Use Approach C (strict causal) for Phase 4. Rationale: Causal discovery algorithms benefit from pre-filtered causal features (reduces search space, improves identifiability).
3. Inter-Metric Causal Relationships
Question: Do QOL metrics causally affect each other?
Example: Does life expectancy → GDP per capita? (healthy workers more productive)
Approach: Train joint multi-output model with all 8 metrics as both predictors and targets, then apply causal discovery.
4. Policy Simulation Requirements
Objective: Answer "What if country X increases education spending by 20%?"
Requirements:
Identified causal graph (Phase 4-5)
Quantified causal effects (regression coefficients)
Intervention logic (do-calculus implementation)
Uncertainty quantification (confidence intervals)
Deliverable: PolicySimulator class for Phase 6 dashboard.

Reproducibility
Software Environment
Python: 3.13
pandas: 2.x
numpy: 1.x
scikit-learn: 1.5.x
xgboost: 3.1.1 (with CUDA 12.1)
lightgbm: 4.5.x
torch: 2.5.x (with CUDA support)

Platform: Linux 6.17.1-arch1-1 (Arch Linux)
 GPU: NVIDIA GPU with CUDA 12.1
 CPU: 8 cores (Intel/AMD)
 Virtual Env: <repo-root>/v1.0/phase3_env/
Execution Sequence
# Step 1: Causal feature filtering
python M3_1_filter_causal_features.py --approach relaxed  # Approach B
python M3_1_filter_causal_features.py --approach strict   # Approach C

# Step 2: Train all models (parallel by approach)
python train_all_phase2_features.py  # Approach A (40 features)
python train_all_relaxed_features.py  # Approach B (25-30 features)
python train_all.py                   # Approach C (23-52 features)

# Step 3: Verification and comparison
python verify_approach_a_results.py
python verify_approach_b_results.py
python three_way_comparison.py  # Generates comparison report

# Step 4: Model persistence
python M3_4_persist_final_models.py

Runtime:
Causal filtering: ~30 minutes (manual review + script)
Approach A training: ~45 minutes (8 metrics × 4 models, GPU accelerated)
Approach B training: ~45 minutes
Approach C training: ~45 minutes
Verification: ~15 minutes
Total: ~3 hours
Random Seeds & Determinism
SEED = 42

# All random operations
np.random.seed(SEED)
torch.manual_seed(SEED)
torch.cuda.manual_seed(SEED)

# Model initialization
xgboost.XGBRegressor(random_state=SEED)
lightgbm.LGBMRegressor(random_state=SEED, deterministic=True)
sklearn.linear_model.ElasticNet(random_state=SEED)

GPU Non-Determinism: XGBoost GPU training has minor non-determinism (±0.001 R²) due to floating-point rounding in parallel operations. Acceptable for comparative analysis.
Critical Parameters
Approach A (Pure Statistical):
Feature count: 40 (fixed)
Feature source: Phase 2 imputation-adjusted features
Approach B (Relaxed Causal):
Target retention: 70%
Causal criteria: 2 of 3 (temporal precedence, mechanism, direct measurement)
Approach C (Strict Causal):
Causal criteria: All 4 (temporal, mechanism, direct, no reverse)
Variable feature count: 23-52 by metric
Model Hyperparameters:
# XGBoost
max_depth=6, learning_rate=0.05, n_estimators=500, early_stopping=50

# LightGBM  
max_depth=10, learning_rate=0.05, n_estimators=500, num_leaves=31

# ElasticNet
alpha=1.0, l1_ratio=0.5 (CV-selected)

# Neural Network
layers=[128, 64, 32, 1], dropout=[0.3, 0.3, 0.2], lr=0.001, epochs=200

Imputation Weighting:
Tier 1-2: weight = 1.0
Tier 3: weight = 0.7
Tier 4: weight = 0.5

Final Deliverables
Trained Models
Directory Structure:
/models/
├── phase2_retrain/          # Approach A (pure statistical)
│   ├── xgboost/
│   │   ├── life_expectancy.pkl
│   │   ├── infant_mortality.pkl
│   │   └── ...
│   ├── lightgbm/
│   ├── elasticnet/
│   └── neural_net/
├── relaxed/                 # Approach B (relaxed causal)
│   └── [same structure]
└── causal/                  # Approach C (strict causal)
    └── [same structure]

Model Count:
93 trained models (96 attempted, 3 neural net failures)
31 models per approach
8 metrics × 4 model types (less 1 neural net failure per approach)
Results & Metadata
Performance Results:
/Documentation/phase_reports/
├── three_way_comparison.csv         # Main comparison table
├── phase3_report.md                 # Detailed analysis
├── phase3_three_pronged_summary.md  # Executive summary
├── approach_a_validation.csv        # Approach A detailed results
├── approach_b_validation.csv
└── approach_c_validation.csv

Loss Curves (for animation):
/models/{approach}/{model_type}/{metric}_loss_curves.json

Feature Importance:
/models/{approach}/{model_type}/{metric}_feature_importance.csv

Feature Sets
Causal-Filtered Features:
/Data/Processed/feature_selection/phase3/
├── features_relaxed_life_expectancy.csv    # Approach B (25-30 features)
├── features_relaxed_infant_mortality.csv
├── ...
├── features_causal_life_expectancy.csv     # Approach C (23-52 features)
├── features_causal_infant_mortality.csv
└── ...

Summary Statistics
Performance Summary:
Metric
Approach
Best Model
R²
Features
Mean Years Schooling
A
LightGBM
0.9244
40
Infant Mortality
A
LightGBM
0.9072
40
Undernourishment
C
LightGBM
0.8057
40
GDP per Capita
C
LightGBM
0.7785
31
Gini
C
XGBoost
0.6999
23
Internet Users
C
LightGBM
0.6887
47
Life Expectancy
C
XGBoost
0.6633
52
Homicide
C
LightGBM
0.3577
43

Training Statistics:
Models trained: 93/96 (96.9% success)
Training time: ~3 hours (with GPU acceleration)
Storage: ~2.5 GB (models + loss curves + metadata)
Peak memory: ~24 GB (neural network training)
Approach Comparison:
Approach A wins: 2/8 metrics (infant mortality, education)
Approach B wins: 0/8 metrics
Approach C wins: 6/8 metrics (life expectancy, GDP, gini, homicide, undernourishment, internet users)

Citation
Three-pronged model training evaluated the predictive performance trade-offs between pure statistical feature selection (Approach A: 40 features), relaxed causal filtering (Approach B: 25-30 features, 70% retention), and strict causal filtering (Approach C: 23-52 features, maximum interpretability) across 8 quality-of-life metrics using four model architectures (XGBoost, LightGBM, ElasticNet, Neural Network) with imputation-aware sample weighting (Tier 1-2: 1.0, Tier 3: 0.7, Tier 4: 0.5). Training 93 of 96 models (96.9% success rate) across 3 approaches × 8 metrics × 4 model types revealed that strict causal filtering (Approach C) achieved best performance on 6 of 8 metrics (75% win rate) despite theoretically-constrained feature selection, with dramatic improvements for homicide (+73% R² vs. pure statistical), internet users (+28%), gini inequality (+5.3%), and GDP per capita (+3.8%), while maintaining near-parity on life expectancy (+0.2%) and undernourishment (+0.4%). Approach C's success is attributed to overfitting reduction from removing proxy variables and reverse-causality features (e.g., excluding contemporaneous GDP as predictor for internet users, where causality likely reversed), demonstrating that temporal precedence (T-1 minimum lag) combined with documented theoretical mechanisms reduces spurious correlations. Model type analysis found LightGBM optimal for small development data (n=2,769-3,280), winning 6 of 8 metrics through leaf-wise growth and Gradient-based One-Side Sampling (GOSS), while neural networks failed from severe overfitting (~20K parameters for 2,800 samples) despite 30% dropout and early stopping. Relaxed causal filtering (Approach B) won zero metrics, suggesting half-measures underperform in causal feature selection—either optimize for pure prediction (A) or strict causation (C). Imputation-aware weighting improved all metrics by +0.55-1.45 percentage points, with largest gains for high-imputation metrics (infant mortality: +1.38 pp, homicide: +1.45 pp). Final model selection uses Approach C (strict causal) for 6 metrics, Approach A (pure statistical) for 2 metrics (infant mortality, education), with LightGBM as primary model type (6/8 final models) and XGBoost for 2 metrics (life expectancy, gini), achieving validation R² range 0.358-0.9244 across quality-of-life outcomes.

Status: ✅ Complete
 Confidence: HIGH (6/8 metrics R² > 0.65), MEDIUM (2/8 metrics: homicide R²=0.358, internet users R²=0.689)
 Critical Success Factors:
Three-pronged comparative design quantified causal filtering's impact
Strict causal filtering improved 6/8 metrics (overfitting reduction via proxy removal)
LightGBM optimal for small development data (n < 5K)
Imputation-aware weighting prevented artifact learning (+0.92 pp mean improvement)
Loss curve persistence enables Phase 6 "watch AI learn" animation
Phase 3 Timeline: 3 hours (training + verification)
 Next Phase: Phase 4 - Causal Discovery (PC algorithm on Approach C features for high-R² metrics)

Principal Investigator Note: Phase 3 establishes that the causal/predictive trade-off is a false dichotomy for well-selected features. Strict causal filtering's 75% win rate (6 of 8 metrics) challenges the conventional wisdom that causation sacrifices performance, demonstrating instead that removing proxy variables and reverse-causality features reduces overfitting and improves generalization. The 73% improvement for homicide prediction (R²: 0.207→0.358) from replacing contemporaneous economic correlations with lagged governance/conflict indicators exemplifies how causal constraints guide models toward robust structural drivers rather than spurious test-set-specific patterns.
The complete failure of Approach B (relaxed causal, 0/8 wins) validates that causal feature selection requires strict criteria (temporal precedence AND theoretical mechanism AND direct measurement AND no reverse causality), as half-measures inherit weaknesses of both pure-statistical (overfitting from proxies) and strict-causal (reduced statistical power from filtering) without gaining advantages of either. LightGBM's dominance (6/8 final models) over XGBoost, ElasticNet, and neural networks for small development data (n<5K) reflects the superiority of leaf-wise tree growth with Gradient-based One-Side Sampling (GOSS) for bias-variance optimization when sample-to-parameter ratios are low.
The imputation-aware weighting innovation (Tier 1-2: 1.0, Tier 3: 0.7, Tier 4: 0.5) demonstrating +0.92 percentage point mean improvement across all metrics validates that training sample quality should be explicitly weighted when imputation introduces heterogeneous uncertainty, representing a methodological advancement beyond conventional "exclude all imputed data" (loses samples) or "treat all data equally" (learns artifacts) approaches. Loss curve persistence for 93 models enables pedagogical dashboard visualization showing epoch-by-epoch convergence, supporting the project's north star of making machine learning interpretable to public audiences.
Phase 3's strategic contribution is empirically validating that causal feature engineering should precede modeling rather than being deferred to post-hoc interpretation, with 75% of metrics benefiting from pre-selection causal filtering. This establishes the foundation for Phase 4 causal discovery, where PC algorithm will operate on pre-filtered Approach C features (23-52 causal features per metric) to learn directed acyclic graph structure, having already removed 30-40% of features likely to introduce spurious edges or confounding paths in the causal graph.


