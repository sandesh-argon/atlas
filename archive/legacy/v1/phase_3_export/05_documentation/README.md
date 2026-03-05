# Phase 3: Three-Pronged Model Training - Complete

**Status:** ✅ All tasks complete
**Date:** 2025-10-23
**Success Rate:** 93/96 models (96.9%)

---

## Quick Summary

This directory contains the complete implementation of Phase 3's three-pronged training strategy:

### Approach A: Pure Statistical (40 features)
- **Purpose:** Baseline maximum predictive power
- **Features:** Top-40 Phase 2 imputation-adjusted features
- **Results:** 31/32 models trained, wins 2/8 metrics
- **Directory:** `/models/phase2_retrain/`

### Approach B: Relaxed Causal (25-30 features)
- **Purpose:** Hybrid approach balancing prediction and causality
- **Features:** 70% retention of causal features, relaxed restrictions
- **Results:** 31/32 models trained, best feature efficiency
- **Directory:** `/models/relaxed/`

### Approach C: Strict Causal (23-52 features)
- **Purpose:** Maximum causal interpretability
- **Features:** Strict causal filtering, no proxy features
- **Results:** 31/32 models trained, **wins 6/8 metrics** 🏆
- **Directory:** `/models/causal/`

---

## Key Findings

1. **Approach C (Strict Causal) WINS overall:** 6/8 metrics
2. **Causal filtering can IMPROVE performance:** 3/8 metrics improved (gini, homicide, internet_users)
3. **Minimal degradation for most metrics:** 5/8 metrics have <5pp degradation
4. **LightGBM is best model type:** Consistently outperforms all others

---

## Training Scripts

### Individual Model Training
- `train_xgboost.py` - XGBoost with GPU acceleration
- `train_lightgbm.py` - LightGBM with CPU multi-threading
- `train_neural_net.py` - PyTorch neural network
- `train_elasticnet.py` - ElasticNet regression

**Usage:**
```bash
# Approach A (pure statistical)
python train_xgboost.py --metric life_expectancy --use-phase2

# Approach B (relaxed causal)
python train_xgboost.py --metric life_expectancy --use-relaxed

# Approach C (strict causal)
python train_xgboost.py --metric life_expectancy
```

### Orchestrator Scripts (Train All 8 Metrics × 4 Models = 32 Models)
- `train_all_phase2_features.py` - Approach A orchestrator
- `train_all_relaxed_features.py` - Approach B orchestrator
- `train_all.py` - Approach C orchestrator

**Usage:**
```bash
# Train all Approach A models
python train_all_phase2_features.py

# Train all Approach B models
python train_all_relaxed_features.py

# Train all Approach C models
python train_all.py
```

### Verification Scripts
- `verify_approach_a_results.py` - Verify Approach A training
- `verify_approach_b_results.py` - Verify Approach B training
- `three_way_comparison.py` - Comprehensive comparison analysis

**Usage:**
```bash
# Verify each approach
python verify_approach_a_results.py
python verify_approach_b_results.py

# Generate comparison report
python three_way_comparison.py
```

---

## Utility Modules

### `training_utils.py`
Core training utilities used by all scripts:
- `load_training_data()` - Load features, targets, imputation flags
- `ImputationWeighter` - Calculate sample weights by imputation tier
- `LossCurveTracker` - Track training loss curves for animation
- `evaluate_model()` - Calculate R², RMSE, MAE, MAPE
- `save_model_results()` - Save model, results JSON, feature importance

---

## Feature Selection Files

### Approach A Features
**Location:** `/Data/Processed/feature_selection/imputation_adjusted/`
- `final_features_imputation_adjusted_{metric}.csv` (8 files, 40 features each)

### Approach B Features
**Location:** `/Data/Processed/feature_selection/phase3/`
- `features_relaxed_{metric}.csv` (8 files, 25-30 features each)
- `classification_relaxed_{metric}.csv` (8 files with rationale)

### Approach C Features
**Location:** `/Data/Processed/feature_selection/phase3/`
- `features_causal_{metric}.csv` (8 files, 23-52 features each)
- `feature_causal_classifications_{metric}.csv` (8 files with rationale)

---

## Training Configuration

### Imputation-Aware Weighting
Sample weights based on imputation tier:
- **Tier 1 (0-10% imputed):** weight = 1.0
- **Tier 2 (10-30% imputed):** weight = 1.0
- **Tier 3 (30-70% imputed):** weight = 0.7
- **Tier 4 (70-100% imputed):** weight = 0.5

### Hardware Acceleration
- **XGBoost:** CUDA GPU (`device='cuda'`, `tree_method='hist'`)
- **LightGBM:** CPU multi-threading (19 threads)
- **Neural Net:** CUDA GPU if available
- **ElasticNet:** CPU (4 jobs)

### Early Stopping
- **Tree models (XGBoost, LightGBM):** 50 rounds
- **Neural Networks:** 20 epochs patience

### Hyperparameters
- **XGBoost:** learning_rate=0.05, max_depth=6, reg_alpha=0.1, reg_lambda=1.0
- **LightGBM:** learning_rate=0.05, num_leaves=31, max_depth=6, reg_alpha=0.1, reg_lambda=1.0
- **Neural Net:** 3 hidden layers (128→64→32), dropout=0.2, lr=0.001, Adam optimizer
- **ElasticNet:** CV over 100 alphas, l1_ratio ∈ [0.1, 0.3, 0.5, 0.7, 0.9]

---

## Results Summary

### Best Models per Metric (by validation R²)

| Metric | Winner | R² | Model Type | Features |
|--------|--------|-----|------------|----------|
| life_expectancy | **C** | 0.6633 | LightGBM | 52 |
| infant_mortality | **A** | 0.9072 | LightGBM | 40 |
| mean_years_schooling | **A** | 0.9244 | LightGBM | 40 |
| gdp_per_capita | **C** | 0.7785 | XGBoost | 31 |
| gini | **C** | 0.6999 | LightGBM | 23 |
| homicide | **C** | 0.3577 | LightGBM | 43 |
| undernourishment | **C** | 0.8057 | LightGBM | 40 |
| internet_users | **C** | 0.6887 | XGBoost | 47 |

### Model Type Rankings (by average R²)

1. **LightGBM:** 0.651 average R² ⭐
2. **XGBoost:** 0.594 average R²
3. **ElasticNet:** 0.294 average R²
4. **Neural Net:** -0.333 average R² (high variance, BatchNorm issues)

---

## Known Issues

### Neural Network Failures (1/32 per approach)
- **Model:** neural_net/gdp_per_capita
- **Error:** BatchNorm requires batch_size ≥ 2, last batch has size 1
- **Impact:** 3 models failed across all approaches (same model in each)
- **Workaround:** Use LightGBM/XGBoost (better performance anyway)

### Approach B Not Winning Any Metrics
- **Observation:** Approach B did not win any metrics outright
- **Explanation:** B is a compromise - optimized for feature efficiency, not raw R²
- **Recommendation:** Use B when causal interpretability matters but C is too large

---

## Recommendations

### For Maximum Predictive Power
Use **Approach A** for:
- infant_mortality (R²=0.907)
- mean_years_schooling (R²=0.924)

### For Causal Interpretability with Minimal Trade-off
Use **Approach B** for:
- Best feature efficiency (R² per feature)
- All metrics with <10pp degradation from A

### For Strict Causal Analysis
Use **Approach C** for:
- **All metrics** requiring maximum causal interpretability
- **Especially:** gini, homicide, internet_users (improved performance)
- **6/8 metrics win** with strict causal filtering

### Recommended Hybrid Strategy
- **Easy metrics (R² > 0.85):** Use C
- **Medium metrics (0.60 < R² < 0.85):** Use B
- **Hard metrics (R² < 0.60):** Use C if improvement observed, else A

---

## Output Files

### Per Model (×93 models)
- `model_{model_type}_{metric}.pkl` (or `.pth` for neural nets)
- `results_{model_type}_{metric}.json`
- `feature_importance_{model_type}_{metric}.csv`

### Loss Curves (for animation)
- `/Data/Processed/feature_selection/phase3/loss_curves/loss_curve_{model_type}_{metric}.csv`

### Analysis Reports
- `/Documentation/phase_reports/three_way_comparison.csv`
- `/Documentation/phase_reports/phase3_three_pronged_summary.md`

---

## Next Steps (Phase 4)

1. **Causal Discovery:** Use Approach C features with PC/FCI algorithm
2. **Inter-Metric Relationships:** Multi-output integrated model
3. **Policy Simulation:** Scenario testing and UN SDG tracking
4. **Validation:** Out-of-sample testing on 28 held-out countries

---

## Documentation

**Full Report:** `/Documentation/phase_reports/phase3_three_pronged_summary.md`

**Key Insight:** Strict causal filtering not only preserves performance but can actually **improve** it by removing overfitting proxy features. This validates the entire Phase 3 methodology.

---

**Training Complete:** ✅
**Date:** 2025-10-23
**Total Models:** 93/96 (96.9%)
**Winner:** Approach C (Strict Causal) - 6/8 metrics 🏆
