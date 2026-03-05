# LightGBM Hyperparameter Optimization - Ready to Run

## Quick Start

**To run the full optimization (8-12 hours):**

```bash
cd <repo-root>/v1.0/Data/Scripts/phase3_modules/STEP_3B_PREDICTIVE_TRAINING
./RUN_OPTIMIZATION.sh
```

This will optimize all 24 models (8 metrics × 3 approaches) with 100 trials each.

---

## What This Does

**Problem Being Solved:**
- Current LightGBM models have 20% average overfitting (train R² - val R²)
- Some metrics performing poorly (homicide: 0.15-0.33 R²)
- Need better regularization to improve generalization

**Optimization Strategy:**
- Uses Optuna (Bayesian optimization)
- 100 trials per metric (24 metrics total = ~2,400 model fits)
- Searches 12 hyperparameters (regularization, tree structure, sampling)
- Maximizes validation R²
- Includes early stopping and trial pruning for efficiency

**Expected Improvements:**
- Reduce overfitting from 20% → <10%
- Improve validation R²: 0.674 → ~0.69
- Fix weak metrics (homicide, life_expectancy, internet_users)

---

## Files Created

### Core Scripts

1. **`optimize_lightgbm.py`** - Single metric optimizer with Optuna
   - Usage: `python optimize_lightgbm.py --metric gdp_per_capita --use-phase2 --n-trials 100`
   - Runs Bayesian hyperparameter search
   - Saves optimized model + results + history

2. **`optimize_all_approaches.py`** - Orchestrator for all 24 optimizations
   - Runs all 8 metrics across 3 approaches sequentially
   - Tracks progress and success/failure
   - Saves summary JSON

3. **`RUN_OPTIMIZATION.sh`** - Convenience launcher
   - One-command execution
   - Logs output to `/tmp/lightgbm_optimization_full.log`
   - Activates virtual environment automatically

### Analysis Scripts (Already Run)

4. **`compare_neural_net_improvements.py`** - Neural network comparison
   - Result: Neural nets underperform by 50pp → skip NN optimization

5. **`analyze_lightgbm_optimization_potential.py`** - Optimization analysis
   - Result: Recommend full optimization due to 20% overfitting

---

## Outputs

### Optimized Models

**Directories:**
- `/models/phase2_retrain_optimized/` - Approach A (Phase 2 features)
- `/models/relaxed_optimized/` - Approach B (Relaxed causal)
- `/models/causal_optimized/` - Approach C (Strict causal)

**Files per metric:**
- `model_lightgbm_{metric}.txt` - Trained LightGBM model
- `results_lightgbm_{metric}.json` - Performance + best hyperparameters
- `feature_importance_lightgbm_{metric}.csv` - Feature importances
- `optimization_history_lightgbm_{metric}.csv` - All 100 trials

### Summary

- `/Data/Processed/feature_selection/phase3/optimization_summary.json`
  - Total optimizations run
  - Success/failure counts
  - Total duration
  - Per-metric results

---

## Hyperparameters Being Optimized

### Tree Structure (Reduce Overfitting)
- `num_leaves`: [10, 100] - Smaller = less overfit
- `max_depth`: [3, 12] - Shallower = less overfit
- `min_child_samples`: [5, 100] - Higher = less overfit
- `min_child_weight`: [1e-5, 10.0] - Higher = less overfit

### Regularization (Critical)
- `reg_alpha`: [1e-8, 10.0] - L1 regularization
- `reg_lambda`: [1e-8, 10.0] - L2 regularization

### Learning
- `learning_rate`: [0.005, 0.1] - Lower = slower, more careful
- `n_estimators`: [100, 2000] - More trees (with early stopping)

### Sampling (Prevent Overfitting)
- `feature_fraction`: [0.4, 1.0] - Random feature sampling
- `bagging_fraction`: [0.4, 1.0] - Random row sampling
- `bagging_freq`: [1, 7] - How often to bag

### Other
- `max_bin`: [63, 511] - Feature binning resolution
- `min_data_in_bin`: [1, 10] - Minimum data per bin

---

## Monitoring Progress

**View live output:**
```bash
tail -f /tmp/lightgbm_optimization_full.log
```

**Check optimization progress:**
- Each trial takes ~2-5 minutes
- 100 trials per metric = ~3-8 hours per metric
- 24 metrics total = ~8-12 hours overall
- Pruning will stop unpromising trials early (saves time)

**Example output:**
```
[I 2025-10-23 16:53:22] Trial 10 finished with value: 0.4523
  Best trial: #7 with value: 0.4621
  Train R²: 0.6234, Val R²: 0.4621, Overfit: 0.1613
```

---

## After Optimization Completes

### 1. Compare Results

Run comparison analysis:
```bash
python compare_optimized_vs_baseline.py
```

This will show:
- Baseline vs optimized validation R²
- Overfitting reduction
- Which metrics improved most

### 2. Update Documentation

Update `/Documentation/phase_reports/phase3_optimization_addendum.md` with:
- Final performance metrics
- Best hyperparameters discovered
- Decision on which approach to use for Phase 4

### 3. Proceed to Phase 4

With optimized models:
- Inter-metric relationship analysis
- Causal discovery
- Multi-output integrated models

---

## Troubleshooting

### If optimization fails:

**Check log file:**
```bash
tail -100 /tmp/lightgbm_optimization_full.log
```

**Common issues:**
1. **Out of memory** - Reduce `n_trials` to 50
2. **GPU errors** - Already using CPU (fixed)
3. **Missing dependencies** - Check virtual environment activated

### If you want to stop early:

Press `Ctrl+C` - Optuna will save progress from completed trials.

---

## Manual Single-Metric Testing

**Test on one metric first (5-10 min):**
```bash
cd <repo-root>/v1.0/Data/Scripts/phase3_modules/STEP_3B_PREDICTIVE_TRAINING

python optimize_lightgbm.py --metric homicide --n-trials 20
```

This runs 20 trials on homicide (weakest metric) to validate setup.

---

## Success Criteria

**Primary Goals:**
- ✅ Reduce overfitting: 20% → <10%
- ✅ Improve validation R²: 0.674 → >0.69

**Secondary Goals:**
- Fix homicide: 0.15-0.33 → >0.40 R²
- Improve life_expectancy: 0.66 → >0.70 R²
- Stabilize internet_users: 39% overfit → <15%

**Minimum Acceptable:**
- No degradation in strong metrics (mean_years_schooling, infant_mortality)
- At least 15% reduction in overfitting

---

## Technical Notes

- **CPU-based**: Uses all available CPU cores (`n_jobs=-1`)
- **Reproducible**: `seed=42` for all trials
- **Early stopping**: 50-round patience prevents overfitting
- **Pruning**: MedianPruner stops bad trials early
- **Weights**: Imputation-aware sample weights applied (observed: 1.0, imputed: 0.5-0.9)
- **Validation**: Uses same train/val split as baseline (26 validation countries)

---

## Quick Reference

**Main command:**
```bash
./RUN_OPTIMIZATION.sh
```

**Monitor:**
```bash
tail -f /tmp/lightgbm_optimization_full.log
```

**Estimated time:** 8-12 hours

**Output:** 24 optimized models + hyperparameters + optimization histories

---

**Ready to run!** Just execute `./RUN_OPTIMIZATION.sh` when you're ready to start the long training session.
