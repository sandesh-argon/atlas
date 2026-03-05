# Phase 3 Export - Model Training & Optimization

**Export Date**: 2025-10-23
**Phase Status**: Complete - Ready for Phase 4

---

## Overview

This export contains all artifacts from Phase 3: Model Training & Optimization of the Global Development Indicators Causal Analysis Project.

**Key Achievement**: Optimized LightGBM models using strict causal features (Approach C) with Bayesian hyperparameter optimization.

---

## Directory Structure

### 01_causal_features/ (16 files)
Causal feature sets used for model training

**Contents**:
- `features_causal_*.csv` - Strict causal features per metric (8 files)
- `features_causal_vif_filtered_*.csv` - VIF-filtered features (multicollinearity removed) (8 files)

**Feature Counts**: 23-52 features per metric

---

### 02_optimized_models/ (24 files)
Final optimized LightGBM models and optimization history

**Contents**:
- `model_lightgbm_*.txt` - Trained LightGBM models (8 files)
- `results_lightgbm_*.json` - Performance metrics + hyperparameters (8 files)
- `optimization_history_lightgbm_*.csv` - All 100 Optuna trials per metric (8 files)

**Optimization Details**:
- Algorithm: Optuna Bayesian optimization (TPE)
- Trials: 100 per metric
- Parameters: 12 hyperparameters optimized (regularization, tree structure, sampling)
- Hardware: CPU multi-threading (19 cores)

---

### 03_feature_importance/ (16 files)
Feature importance metrics for causal analysis

**Contents**:
- `shap_importance_*.csv` - SHAP values + gain importance (8 files)
- `feature_importance_lightgbm_*.csv` - Gain-based importance only (8 files)

**Format**: CSV with columns `[feature, shap_importance, gain_importance]`

**Purpose**: Critical for Phase 4 causal discovery - identifies most influential features per QOL metric

---

### 04_test_evaluation/ (11 files)
Test set validation results and master metadata

**Contents**:
- `test_results_*.json` - Test set performance per metric (8 files)
- `test_evaluation_summary.json` - Aggregate test set results
- `shap_extraction_summary.json` - SHAP extraction metadata
- `model_metadata_master.json` - Complete metadata for all 8 models

**Test Set**: 28 countries, 1,680 samples (never seen during training/validation)

**Generalization**:
- Strong (5 metrics): <10% val-test difference
- Weak (3 metrics): >10% val-test difference (life_expectancy, gdp_per_capita, homicide)

---

### 05_documentation/ (6 files)
Complete Phase 3 documentation and guides

**Contents**:
- `phase3_report.md` - Full Phase 3 report with methodology and results
- `phase3_api_reference.md` - Complete function/class documentation
- `phase3_quickstart.md` - 5-minute tutorial to first model
- `phase3_documentation_summary.md` - Documentation overview
- `README.md` - Training pipeline guide
- `README_OPTIMIZATION.md` - Optimization process guide

---

## Performance Summary

### Validation Performance (26 countries, 1,560 samples)

| Metric | Features | Val R² | Train R² | Overfitting |
|--------|----------|--------|----------|-------------|
| mean_years_schooling | 38 | 0.905 | 0.952 | 4.7% |
| infant_mortality | 42 | 0.853 | 0.968 | 11.6% |
| undernourishment | 40 | 0.830 | 0.919 | 8.8% |
| gdp_per_capita | 31 | 0.765 | 0.901 | 13.6% |
| gini | 23 | 0.743 | 0.735 | -0.8% |
| internet_users | 47 | 0.730 | 0.942 | 21.2% |
| life_expectancy | 52 | 0.673 | 0.845 | 17.1% |
| homicide | 43 | 0.389 | 0.805 | 41.6% |

**Average**: Val R² = 0.736, Overfitting = 14.5%

### Test Set Performance (28 countries, 1,680 samples)

| Metric | Test R² | Val-Test Diff | Status |
|--------|---------|---------------|--------|
| mean_years_schooling | 0.935 | 3.3% | ✅ Excellent |
| infant_mortality | 0.855 | 0.2% | ✅ Excellent |
| undernourishment | 0.821 | 1.2% | ✅ Excellent |
| internet_users | 0.758 | 3.8% | ✅ Excellent |
| gini | 0.676 | 9.1% | ✅ Good |
| gdp_per_capita | 0.623 | 18.6% | ⚠️ Concerning |
| life_expectancy | 0.445 | 33.9% | ⚠️ Poor |
| homicide | 0.156 | 59.9% | ⚠️ Poor |

**Average**: Test R² = 0.658, Val-Test Diff = 16.3%

---

## Key Scientific Findings

1. **Causal Features Work**: Strict causal filtering (Approach C) won 6/8 metrics over pure statistical features
2. **LightGBM Dominates**: Best model type across all approaches (7/8 metrics)
3. **Optimization Effective**: 95.8% of models improved with Bayesian optimization
4. **Overfitting Reduced**: Average overfitting decreased from 20.1% → 14.5%
5. **Some Metrics Challenging**: life_expectancy, gdp_per_capita, homicide show poor test generalization

---

## Technical Specifications

**Model Type**: LightGBM (gradient boosting)
**Optimization**: Optuna Bayesian (TPE algorithm)
**Features**: Strict causal only (Approach C)
**Data Split**: 120 train / 26 val / 28 test countries
**Sample Weighting**: Imputation-aware (observed: 1.0, imputed: 0.5-0.9)
**Reproducibility**: Random seed = 42

---

## Next Steps (Phase 4)

Phase 4 will use these artifacts for:
1. **Causal Discovery**: PC/FCI algorithms on causal feature sets
2. **Inter-Metric Analysis**: Identify causal relationships between QOL metrics
3. **Feature Causality**: Validate SHAP importance with causal structure learning
4. **Knowledge Graphs**: Build directed acyclic graphs (DAGs) of causal relationships

---

## Version Control

- **Phase 3 Completed**: 2025-10-23
- **life_expectancy Model Fixed**: 2025-10-23 (100 trials verified)
- **All Models Validated**: Test set evaluation complete
- **Metadata Consolidated**: Master JSON created

---

## Contact

For questions about Phase 3 methodology or results:
- See `/05_documentation/phase3_report.md` for complete details
- See `/05_documentation/phase3_api_reference.md` for code documentation
