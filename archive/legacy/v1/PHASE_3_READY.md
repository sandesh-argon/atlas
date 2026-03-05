# Phase 3 Ready Checklist

**Date**: 2025-10-22
**Status**: ✅ ALL INPUTS READY

---

## Phase 2 Completion Status

### M2.4: Feature Selection ✅
- **Method**: Pure statistical (top-40 by Borda score)
- **Files**: 8 × `final_features_{metric}.csv`
- **Validation**: 5/8 metrics pass R² ≥ 0.55 threshold

### M2.5: Validation ✅
- **Performance**: 5/8 passing (62.5% pass rate)
- **Top performers**: mean_years_schooling (0.94), infant_mortality (0.89), undernourishment (0.79)
- **Domain coverage**: 5-9 domains per metric (informational)

---

## Required Inputs for Phase 3

### 1. Feature Lists ✅
**Location**: `/Data/Processed/feature_selection/`

```bash
final_features_life_expectancy.csv       # 40 features
final_features_infant_mortality.csv      # 40 features
final_features_gdp_per_capita.csv        # 40 features
final_features_mean_years_schooling.csv  # 40 features
final_features_gini.csv                  # 40 features
final_features_homicide.csv              # 40 features
final_features_undernourishment.csv      # 40 features
final_features_internet_users.csv        # 40 features
```

**Verified**: All files exist ✓

### 2. Normalized Datasets ✅
**Location**: `/Data/Processed/normalized/`

```bash
train_normalized.csv   # 7,200 rows × 12,426 features (120 countries)
val_normalized.csv     # 1,560 rows × 12,426 features (26 countries)
test_normalized.csv    # 1,680 rows × 12,426 features (28 countries)
```

**Verified**: All datasets from Phase 1 ✓

### 3. Domain Metadata ✅
**Location**: `/Data/Processed/feature_selection/`

```bash
feature_classifications.csv        # 1,976 features with domain tags
domain_taxonomy_validated.json     # 18 domain definitions
```

**Verified**: Available for post-hoc analysis ✓

---

## Phase 3 Workflow

### Step 1: Load Feature Lists
```python
import pandas as pd

metric = "life_expectancy"
features_df = pd.read_csv(f"final_features_{metric}.csv")
feature_list = features_df['feature'].tolist()  # 40 features
```

### Step 2: Load Training Data
```python
train = pd.read_csv("train_normalized.csv")
val = pd.read_csv("val_normalized.csv")

# Extract features + target
X_train = train[feature_list]
y_train = train[metric]

X_val = val[feature_list]
y_val = val[metric]
```

### Step 3: Handle Missing Data
```python
# Remove rows with NaN in target
train_clean = train.dropna(subset=[metric])

# For features: median imputation or complete-case analysis
# (decision point for Phase 3)
```

### Step 4: Train Model
```python
from sklearn.ensemble import RandomForestRegressor

model = RandomForestRegressor(
    n_estimators=200,
    max_depth=10,
    random_state=42
)

model.fit(X_train, y_train)
```

### Step 5: Validate
```python
from sklearn.metrics import r2_score

y_pred = model.predict(X_val)
r2 = r2_score(y_val, y_pred)

# Target: R² ≥ 0.50 for validation success
```

---

## Expected Phase 3 Outcomes

### Success Criteria
- ✅ 6/8 metrics achieve R² ≥ 0.50 on validation set
- ✅ SHAP explanations generated for all models
- ✅ Feature importance rankings extracted
- ✅ Model artifacts saved for Phase 4 causal discovery

### Predicted Performance (based on M2.5 validation)
| Metric | Expected R² | Confidence |
|--------|-------------|------------|
| mean_years_schooling | 0.90+ | Very High |
| infant_mortality | 0.85+ | Very High |
| undernourishment | 0.75+ | High |
| gdp_per_capita | 0.60+ | High |
| life_expectancy | 0.55+ | Moderate |
| internet_users | 0.45+ | Moderate (may need tuning) |
| gini | 0.15+ | Low (difficult metric) |
| homicide | 0.05+ | Low (difficult metric) |

### Difficult Metrics Strategy
For gini, homicide, internet_users (if below threshold):
1. Try alternative algorithms (XGBoost, LightGBM, Neural Networks)
2. Hyperparameter tuning
3. If still below threshold: Document as "inherently difficult to predict"
4. Proceed with causal discovery anyway (Phase 4-5 may reveal why)

---

## Phase 3 Timeline

**Estimated Duration**: 2-3 weeks

### Week 1: Model Selection & Training
- Days 1-2: Set up training pipeline
- Days 3-5: Train all 8 models
- Days 6-7: Hyperparameter tuning for difficult metrics

### Week 2: Validation & Explanation
- Days 8-10: Validate on validation set
- Days 11-12: Generate SHAP explanations
- Days 13-14: Feature importance analysis

### Week 3: Documentation & Handoff
- Days 15-17: Performance reports
- Days 18-19: Model artifacts packaging
- Day 20: Phase 3 report + Phase 4 planning

---

## Open Questions for Phase 3

### 1. Imputation Strategy
**Question**: How to handle missing values in features?
**Options**:
- A) Median imputation (simple, may introduce bias)
- B) Complete-case analysis (reduces sample size)
- C) Iterative imputation (MICE, more accurate but slower)

**Recommendation**: Start with (A), use (C) if performance is poor

### 2. Model Selection
**Question**: Which algorithm(s) to use?
**Options**:
- Random Forest (interpretable, robust)
- XGBoost (high performance)
- LightGBM (fast, comparable to XGBoost)
- Neural Networks (flexible, may overfit)

**Recommendation**: Random Forest as baseline, XGBoost for difficult metrics

### 3. Evaluation Protocol
**Question**: How to evaluate beyond R²?
**Metrics to track**:
- R² (primary)
- RMSE (interpretable error)
- MAE (robust to outliers)
- Feature importance rankings
- SHAP values

---

## Phase 3 Deliverables

### Model Artifacts
```
/Data/Processed/models/
  ├── life_expectancy_model.pkl
  ├── infant_mortality_model.pkl
  ├── gdp_per_capita_model.pkl
  ├── mean_years_schooling_model.pkl
  ├── gini_model.pkl
  ├── homicide_model.pkl
  ├── undernourishment_model.pkl
  └── internet_users_model.pkl
```

### Performance Reports
```
/Data/Processed/reports/
  ├── phase3_performance_report.json
  ├── shap_explanations_{metric}.pkl (8 files)
  ├── feature_importance_{metric}.csv (8 files)
  └── validation_predictions_{metric}.csv (8 files)
```

### Documentation
```
/Documentation/phase_reports/
  └── phase3_report.md
```

---

**Status**: ✅ READY TO START PHASE 3

**Next Action**: Implement Phase 3 training pipeline

**Contact**: Phase 2 complete - all inputs validated and ready
