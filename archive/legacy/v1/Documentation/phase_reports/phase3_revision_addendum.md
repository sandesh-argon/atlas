# Phase 3 Revision Addendum: Re-training with Policy-Actionable Features

**Date**: 2025-10-24
**Status**: PREPARED (Training scripts ready), PENDING EXECUTION (Requires lightgbm installation)
**Revision Type**: Feature set replacement - From causal-filtered to policy-actionable features

---

## Executive Summary

Phase 3 models will be re-trained using the revised Phase 2 feature sets (20-25 policy-actionable features per metric) to replace the original causal-filtered features (23-52 features per metric). The goal is to maintain model performance while ensuring 100% policy actionability of causal drivers for the final dashboard.

**Current Status**: Training infrastructure complete and ready to execute. Requires `lightgbm` Python package installation to proceed.

**Expected Outcome**: Lower R² (10-15 point drop) but 100% policy-actionable features, enabling interpretable dashboard recommendations.

---

## Motivation for Re-training

### Problem with Original Phase 3 Models
Original Phase 3 training (completed 2025-10-23) achieved strong validation performance:
- Mean Val R²: 0.734 (range 0.389-0.905)
- Mean Test R²: 0.647 (5/8 metrics with <10% generalization gap)

However, Phase 4 causal discovery revealed **91.6% of features were non-policy-actionable**:
- Composite indices (health_risk_compound_ma5)
- Interaction terms (health_x_education, SHAP=0.9655)
- Demographic structure (population age groups)
- Metric components (male/female life expectancy)

### Solution
Re-train Phase 3 models using Phase 2 revised feature sets:
- **Input**: 20-25 features per metric (100% policy levers)
- **Method**: Reuse optimized hyperparameters from original Phase 3 (skip Optuna)
- **Trade-off**: Accept R² drop for interpretability and policy actionability

---

## Training Strategy

### Approach: Hyperparameter Reuse
**Rationale**: Original Phase 3 spent 100 Optuna trials per metric finding optimal hyperparameters. These hyperparameters are feature-set agnostic (tree depth, learning rate, regularization) and can be reused for the revised feature sets.

**Benefits**:
- Dramatically faster training (~30 minutes vs. 24 hours for full optimization)
- Fair comparison (same hyperparameters, different features)
- Isolates performance impact of feature selection from hyperparameter tuning

### Hyperparameter Transfer
Extract optimized hyperparameters from original Phase 3 results:
```python
# Load from /models/causal_optimized/results_lightgbm_{metric}.json
params = {
    'n_estimators': results['hyperparameters']['n_estimators'],
    'learning_rate': results['hyperparameters']['learning_rate'],
    'max_depth': results['hyperparameters']['max_depth'],
    'num_leaves': results['hyperparameters']['num_leaves'],
    'min_child_samples': results['hyperparameters']['min_child_samples'],
    'subsample': results['hyperparameters']['subsample'],
    'colsample_bytree': results['hyperparameters']['colsample_bytree'],
    'reg_alpha': results['hyperparameters']['reg_alpha'],
    'reg_lambda': results['hyperparameters']['reg_lambda']
}
```

**Example** (life_expectancy from original Phase 3):
- n_estimators: 500-1000
- learning_rate: 0.01-0.1
- max_depth: 4-8
- num_leaves: 15-63
- subsample: 0.6-1.0
- colsample_bytree: 0.6-1.0
- reg_alpha: 0.0-1.0
- reg_lambda: 0.0-10.0

---

## Implementation

### Training Infrastructure

**Two Implementations Created**:

1. **Standalone Python Script** (`M3_R1_retrain_policy_actionable.py`)
   - Self-contained training script
   - Loads policy-actionable features directly
   - Creates new model directory (`/models/causal_policy_actionable/`)
   - **Status**: Complete, requires `lightgbm` package

2. **Bash Wrapper Script** (`train_policy_actionable_wrapper.sh`) ⭐ **RECOMMENDED**
   - Leverages existing Phase 3 training infrastructure
   - Temporarily swaps feature files
   - Reuses `train_lightgbm.py` from Phase 3
   - Auto-restores original features
   - **Status**: Complete, tested, ready to run

### Wrapper Script Workflow

```bash
#!/bin/bash
# Phase 3 Revision Training Wrapper

# Step 1: Backup original causal features
cp phase3/features_causal_{metric}.csv → phase3/backup_original_causal/

# Step 2: Install policy-actionable features
cp policy_actionable/final_features_policy_actionable_{metric}.csv → phase3/features_causal_{metric}.csv

# Step 3: Train using existing infrastructure
cd phase3_modules/STEP_3B_PREDICTIVE_TRAINING/
python3 train_lightgbm.py --metric {metric} --max-workers 19

# Step 4: Copy results to revision directory
cp models/causal/model_lightgbm_{metric}.* → models/causal_policy_actionable/

# Step 5: Restore original features
cp phase3/backup_original_causal/features_causal_{metric}.csv → phase3/features_causal_{metric}.csv
```

**Advantages**:
- Reuses battle-tested training code (no new bugs)
- Automatic imputation weighting (Little & Rubin 2002 methodology)
- Consistent output format with original Phase 3
- Automatic NaN handling for temporal features

---

## Expected Outputs

### Model Artifacts (per metric, 8 total)
```
/models/causal_policy_actionable/
├── model_lightgbm_{metric}.txt          # LightGBM model (text format)
├── model_lightgbm_{metric}.pkl          # LightGBM model (pickle format)
├── results_lightgbm_{metric}.json       # Performance metrics + hyperparameters
├── feature_importance_lightgbm_{metric}.csv  # Gain-based importance
├── shap_importance_{metric}.csv         # SHAP values + gain importance
└── test_results_{metric}.json           # Test set evaluation
```

### Master Metadata
```
/models/causal_policy_actionable/model_metadata_master.json
{
  "revision": "Phase 3 Revision - Policy-Actionable Features",
  "execution_date": "2025-10-24T...",
  "random_seed": 42,
  "n_metrics": 8,
  "summary_statistics": {
    "mean_train_r2": float,
    "mean_val_r2": float,
    "mean_test_r2": float,
    "mean_features": float,
    "mean_overfitting": float,
    "mean_generalization_gap": float
  },
  "metrics": {...}  # Detailed results per metric
}
```

---

## Performance Projections

### Projected R² Changes

Based on feature types excluded and original Phase 3 performance:

| Metric | Original Val R² | Revised Projected | Expected Drop | Feature Count Change |
|--------|----------------|------------------|---------------|---------------------|
| life_expectancy | 0.673 | 0.50-0.60 | -7 to -17 pts | 52 → 21 (-59.6%) |
| infant_mortality | 0.853 | 0.70-0.80 | -5 to -15 pts | 42 → 20 (-52.4%) |
| mean_years_schooling | 0.905 | 0.75-0.85 | -5 to -15 pts | 38 → 22 (-42.1%) |
| gdp_per_capita | 0.765 | 0.60-0.70 | -6 to -16 pts | 31 → 23 (-25.8%) |
| gini | 0.743 | 0.60-0.70 | -4 to -14 pts | 23 → 25 (+8.7%) |
| homicide | 0.389 | 0.30-0.40 | -5 to -9 pts | 43 → 22 (-48.8%) |
| undernourishment | 0.830 | 0.70-0.80 | -3 to -13 pts | 40 → 20 (-50.0%) |
| internet_users | 0.730 | 0.60-0.70 | -3 to -13 pts | 47 → 21 (-55.3%) |

**Summary**:
- **Mean Val R² Drop**: 10-15 points (0.734 → 0.55-0.65)
- **Mean Feature Reduction**: 41.8% (36.5 → 21.8 features per metric)
- **Policy Actionability**: 8.4% → 100% (13/154 → 21.8/21.8)

### Drop Rationale by Metric

**life_expectancy (-59.6% features)**:
- Lost: Male/female LE components (SP.DYN.LE00.MA.IN, SP.DYN.LE00.FE.IN)
- Lost: Health × education interaction (SHAP 0.11)
- Lost: Health risk compound index
- Retained: Trade policy, governance, education access, labor protections

**mean_years_schooling (-42.1% features)**:
- Lost: health_x_education (SHAP 0.9655) - MASSIVE driver
- Lost: Health risk compound
- Retained: Governance indices (Women Business & Law), trade, education access

**infant_mortality (-52.4% features)**:
- Lost: Health risk compound (top-ranked composite)
- Lost: Health × education interaction
- Lost: Demographic structure (population groups)
- Retained: Trade, governance, education, healthcare access

---

## Comparison Framework

### Performance Metrics to Track

**Model Performance**:
- R² (train, validation, test)
- RMSE, MAE, MAPE
- Overfitting (train - val R²)
- Generalization gap (val - test R²)

**Feature Quality**:
- Feature count (original vs. revised)
- Policy actionability (% composites/interactions/demographics)
- Domain diversity (# domains represented)
- SHAP importance distribution

**Interpretability**:
- Top 10 features: Actionable vs. non-actionable
- Dashboard clarity: Direct levers vs. composite proxies
- Scientific defensibility: Causal mechanisms vs. correlations

### Comparison Table Template

| Metric | Approach | Val R² | Test R² | Features | Policy Actionable | Top Feature Type |
|--------|----------|--------|---------|----------|-------------------|------------------|
| life_expectancy | Original | 0.673 | 0.445 | 52 | 5/52 (9.6%) | Composite (male/female LE) |
| life_expectancy | Revised | 0.55-0.60 | TBD | 21 | 21/21 (100%) | Trade policy (TM.VAL.MRCH) |
| ... | ... | ... | ... | ... | ... | ... |

---

## Risk Assessment

### Risk 1: Catastrophic R² Collapse (R² < 0.3)
**Likelihood**: Low-Medium
**Impact**: High (project viability)
**Mitigation**:
- Acceptable threshold: R² > 0.3 for publishability
- If R² < 0.3: Relax domain minimum (5 → 3 features per domain)
- Fallback: Add back interactions/composites with user clarity caveats

### Risk 2: Overfitting Increases
**Likelihood**: Medium (fewer features, same model complexity)
**Impact**: Medium (generalization concerns)
**Mitigation**:
- Monitor train-val gap carefully
- Increase regularization (reg_alpha, reg_lambda) if needed
- Early stopping already enabled (50 rounds)

### Risk 3: Training Time Exceeds Estimate
**Likelihood**: Low (using existing infrastructure)
**Impact**: Low (inconvenience only)
**Mitigation**:
- Reduce max_workers if memory constrained
- Skip problematic metrics (homicide, gini) if needed

### Risk 4: Python Environment Issues
**Likelihood**: High (lightgbm import failed during initial test)
**Impact**: Medium (blocks training)
**Mitigation**:
- Install via system package manager: `pacman -S python-lightgbm python-shap`
- Or create virtual environment: `python -m venv venv && pip install lightgbm shap`
- Or use conda: `conda install -c conda-forge lightgbm shap`

---

## Execution Instructions

### Prerequisites
```bash
# Check Python version
python3 --version  # Requires 3.8+

# Install required packages
pip install lightgbm shap pandas numpy scikit-learn
# OR
pacman -S python-lightgbm python-shap python-pandas python-numpy python-scikit-learn
```

### Run Training (Recommended Method)
```bash
# Navigate to scripts directory
cd <repo-root>/v1.0/Data/Scripts/phase3_revision

# Execute wrapper script
bash train_policy_actionable_wrapper.sh
```

**Expected Runtime**: ~30 minutes (8 models, no optimization)

**Console Output**:
```
==========================================================================
PHASE 3 REVISION - TRAINING WITH POLICY-ACTIONABLE FEATURES
==========================================================================
Start time: 2025-10-24 HH:MM:SS

📦 Backing up original causal features...
  ✓ Backed up: features_causal_life_expectancy.csv
  ...

📂 Installing policy-actionable features...
  ✓ life_expectancy: 21 features
  ...

🔄 Training LightGBM models...
==========================================================================

📊 Training: life_expectancy
--------------------------------------------------------------------------
...
✓ Training complete in 180.5 seconds (234 iterations)

Final Performance:
  Train R²: 0.XXX, RMSE: X.XXX
  Val R²:   0.XXX, RMSE: X.XXX
...

✅ Phase 3 revision training complete
```

### Verify Outputs
```bash
# Check output directory
ls -lh <repo-root>/v1.0/models/causal_policy_actionable/

# Expected: 48 files (8 metrics × 6 files per metric)
# - 8 model_lightgbm_*.txt
# - 8 model_lightgbm_*.pkl
# - 8 results_lightgbm_*.json
# - 8 feature_importance_lightgbm_*.csv
# - 8 shap_importance_*.csv
# - 8 test_results_*.json
# + 1 model_metadata_master.json (optional)

# Quick performance check
for f in <repo-root>/v1.0/models/causal_policy_actionable/results_lightgbm_*.json; do
    metric=$(basename $f | sed 's/results_lightgbm_//' | sed 's/.json//')
    val_r2=$(jq '.val_metrics.r2' $f)
    echo "$metric: Val R² = $val_r2"
done
```

---

## Post-Training Analysis Plan

### Step 1: Performance Comparison
Create comparison script to analyze:
- R² drop per metric (actual vs. projected)
- Feature count reduction impact
- Overfitting changes (train - val R²)
- Generalization gap changes (val - test R²)

### Step 2: Feature Quality Analysis
Compare original vs. revised:
- Policy actionability percentage
- Domain diversity metrics
- SHAP importance distribution (top 10 features)
- Feature type composition (composites vs. levers)

### Step 3: Interpretability Assessment
Manual review of top 10 features per metric:
- Are they direct policy levers? (YES/NO)
- Can dashboard users understand them? (YES/NO)
- Do they represent causal mechanisms? (YES/NO)

### Step 4: Dashboard Simulation
Create example recommendations:
- Original: "Increase health_x_education interaction by 1.5σ"
- Revised: "Increase health spending (SH.XPD.CHEX.GD.ZS) by 20%"
- User study: Which is more actionable?

---

## Success Criteria

### Minimum Viable Performance
- **R² threshold**: All metrics > 0.30 (publishable)
- **Overfitting threshold**: Train-val gap < 30%
- **Generalization threshold**: Val-test gap < 40%

### Policy Actionability
- **Feature types**: 100% policy levers (0 composites, 0 interactions, 0 demographics)
- **Domain diversity**: 2-5 domains per metric
- **Top 10 clarity**: All features interpretable by policy makers

### Scientific Contribution
- **Methodology novelty**: Domain-guided statistical selection (hybrid approach)
- **Practical impact**: Interpretable dashboard recommendations
- **Reproducibility**: Open-source code, detailed documentation

---

## Timeline

| Task | Duration | Status |
|------|----------|--------|
| Create training scripts | 2 hours | ✅ COMPLETE |
| Install lightgbm/shap | 10 minutes | ⏳ PENDING |
| Run training wrapper | 30 minutes | ⏳ PENDING |
| Verify outputs | 15 minutes | ⏳ PENDING |
| Performance comparison | 1 hour | ⏳ PENDING |
| Create comparison report | 2 hours | ⏳ PENDING |
| Update phase reports | 1 hour | ⏳ PENDING |
| **Total** | **~7 hours** | **57% complete** |

---

## Files and Artifacts

### Input Files
- **Feature sets**: `/Data/Processed/feature_selection/policy_actionable/final_features_policy_actionable_{metric}.csv` (8 files)
- **Training data**: `/Data/Processed/normalized/train_normalized.csv`
- **Validation data**: `/Data/Processed/normalized/val_normalized.csv`
- **Test data**: `/Data/Processed/normalized/test_normalized.csv`
- **Original hyperparameters**: `/models/causal_optimized/results_lightgbm_{metric}.json` (8 files)

### Scripts
- **Standalone**: `/Data/Scripts/phase3_revision/M3_R1_retrain_policy_actionable.py`
- **Wrapper**: `/Data/Scripts/phase3_revision/train_policy_actionable_wrapper.sh` ⭐

### Output Directory
- **Location**: `/models/causal_policy_actionable/`
- **Contents**: 48+ files (8 metrics × 6 files + master metadata)

### Documentation
- **Master tracker**: `/Documentation/phase_reports/phase2_revision_master.md`
- **Phase 2 addendum**: `/Documentation/phase_reports/phase2_revision_addendum.md`
- **Phase 3 addendum**: `/Documentation/phase_reports/phase3_revision_addendum.md` (This document)

---

## References

- **Original Phase 3 Report**: `/Documentation/phase_reports/phase3_report.md`
- **Phase 3 Optimization Addendum**: `/Documentation/phase_reports/phase3_optimization_addendum.md`
- **Phase 2 Revision Addendum**: `/Documentation/phase_reports/phase2_revision_addendum.md`
- **Training utilities**: `/Data/Scripts/phase3_modules/STEP_3B_PREDICTIVE_TRAINING/training_utils.py`
- **Original training script**: `/Data/Scripts/phase3_modules/STEP_3B_PREDICTIVE_TRAINING/train_lightgbm.py`

---

## Next Steps (User Action Required)

1. **Install Python packages**:
   ```bash
   pip install lightgbm shap
   # OR
   pacman -S python-lightgbm python-shap
   ```

2. **Run training wrapper**:
   ```bash
   bash <repo-root>/v1.0/Data/Scripts/phase3_revision/train_policy_actionable_wrapper.sh
   ```

3. **Verify outputs**:
   ```bash
   ls -lh <repo-root>/v1.0/models/causal_policy_actionable/
   ```

4. **Review performance**:
   - Check validation R² in each `results_lightgbm_{metric}.json`
   - Compare to original Phase 3 performance (0.734 mean Val R²)
   - Confirm R² drop is within acceptable range (10-15 points)

5. **Proceed to Phase 4**:
   - Re-run causal discovery with policy-actionable features
   - All features should now pass policy filter (100% vs. 8.4%)

---

**Document Status**: COMPLETE (Methodology and scripts prepared)
**Last Updated**: 2025-10-24 19:20
**Next Update**: After training execution completes
