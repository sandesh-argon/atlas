# Phase 3 API Reference

**Global Development Indicators Causal Analysis Project**
**Phase:** 3 - Model Training & Causal Preparation
**Version:** 1.0
**Date:** 2025-10-23
**Status:** Complete (93/96 models, 96.9% success rate)

---

## Table of Contents

1. [Overview](#overview)
2. [Core Modules](#core-modules)
   - [training_utils.py](#training_utilspy)
3. [Model Training Scripts](#model-training-scripts)
   - [train_xgboost.py](#train_xgboostpy)
   - [train_lightgbm.py](#train_lightgbmpy)
   - [train_neural_net.py](#train_neural_netpy)
   - [train_elasticnet.py](#train_elasticnetpy)
4. [Orchestrator Scripts](#orchestrator-scripts)
5. [Verification Scripts](#verification-scripts)
6. [Configuration & Hyperparameters](#configuration--hyperparameters)
7. [Output Files](#output-files)
8. [Examples](#examples)

---

## Overview

Phase 3 implements a three-pronged model training strategy for predicting quality of life metrics:

- **Approach A (Pure Statistical):** 40 Phase 2 imputation-adjusted features per metric
- **Approach B (Relaxed Causal):** 25-30 features with relaxed causal constraints
- **Approach C (Strict Causal):** 23-52 features with aggressive proxy removal

All training scripts share a common infrastructure (`training_utils.py`) ensuring:
- Imputation-aware sample weighting (4-tier system)
- Standardized evaluation metrics (R², RMSE, MAE, MAPE)
- Loss curve tracking for convergence visualization
- Consistent output formats (JSON, CSV, PKL/PTH)

---

## Core Modules

### training_utils.py

**Location:** `/Data/Scripts/phase3_modules/STEP_3B_PREDICTIVE_TRAINING/training_utils.py`

Core infrastructure module providing shared utilities for all training scripts.

#### Classes

##### `LossCurveTracker`

Track and export training/validation loss curves for model visualization.

**Attributes:**
- `model_name` (str): Model type identifier
- `metric_name` (str): Target metric being predicted
- `output_dir` (Path): Directory for CSV output files
- `history` (list): Accumulated loss entries

**Methods:**

```python
__init__(model_name, metric_name, output_dir)
```
Initialize loss curve tracker.

**Parameters:**
- `model_name` (str): Model type ('xgboost', 'lightgbm', 'neural_net', 'elasticnet')
- `metric_name` (str): QOL metric ('life_expectancy', etc.)
- `output_dir` (str|Path): Output directory for CSV files

---

```python
log(iteration, train_loss, val_loss, timestamp=None, **kwargs)
```
Log metrics for a single iteration/epoch.

**Parameters:**
- `iteration` (int): Zero-indexed iteration number
- `train_loss` (float): Training set loss (RMSE/MSE)
- `val_loss` (float): Validation set loss
- `timestamp` (datetime, optional): Logging time (auto-generated if None)
- `**kwargs`: Additional metrics (train_r2, val_r2, learning_rate, etc.)

**Example:**
```python
tracker = LossCurveTracker('xgboost', 'gini', '/output/curves')
for epoch in range(100):
    tracker.log(epoch, train_loss=0.5, val_loss=0.6, train_r2=0.7, val_r2=0.65)
tracker.save()
```

---

```python
save()
```
Export accumulated loss history to CSV.

**Returns:**
- `Path`: Full path to saved CSV file, or None if no history

**Output CSV Columns:**
- `model_name`, `metric_name`, `iteration`, `epoch`
- `train_loss`, `val_loss`, `timestamp`
- Additional logged metrics (R², learning rate, etc.)

---

##### `ImputationWeighter`

Calculate sample weights based on data quality (imputation percentage).

**Scientific Rationale:**
Implements a tiered weighting scheme where samples with more observed data receive
higher weights during training. This prioritizes real observations over model-generated
imputations, preventing overfitting to synthetic patterns (Little & Rubin, 2002).

**Default Tier System:**
- **Tier 1 (0-10% imputed):** weight = 1.0 (nearly complete, full trust)
- **Tier 2 (10-30% imputed):** weight = 1.0 (acceptable quality)
- **Tier 3 (30-70% imputed):** weight = 0.7 (moderate imputation, down-weight)
- **Tier 4 (70-100% imputed):** weight = 0.5 (heavily synthetic, minimal trust)

**Methods:**

```python
__init__(tier_weights=None)
```
Initialize imputation weighter.

**Parameters:**
- `tier_weights` (dict, optional): Custom weight mapping {tier: weight}.
  Default: `{1: 1.0, 2: 1.0, 3: 0.7, 4: 0.5}`

---

```python
calculate_weights(imputation_flags)
```
Compute sample weights from binary imputation indicator matrix.

**Parameters:**
- `imputation_flags` (pd.DataFrame): Binary matrix (n_samples × n_metrics)
  where 1 = imputed, 0 = observed

**Returns:**
- `tuple`: (weights, tiers, imputation_pct)
  - `weights` (np.ndarray): Sample weights, shape (n_samples,)
  - `tiers` (np.ndarray): Quality tiers (1-4), shape (n_samples,)
  - `imputation_pct` (pd.Series): Imputation percentage per sample (0-100)

**Example:**
```python
weighter = ImputationWeighter()
flags = pd.DataFrame({'m1_imputed': [0, 1, 1], 'm2_imputed': [0, 0, 1]})
weights, tiers, pcts = weighter.calculate_weights(flags)
print(weights)  # array([1.0, 1.0, 1.0])
```

---

#### Functions

##### `load_training_data()`

Load training/validation data for Phase 3 three-pronged strategy.

**Signature:**
```python
load_training_data(metric, use_causal=True, use_phase2=False,
                  use_relaxed=False, base_path='<home>/...')
```

**Parameters:**
- `metric` (str): QOL metric name
- `use_causal` (bool): Use Approach C strict causal features (default: True)
- `use_phase2` (bool): Use Approach A Phase 2 statistical features (default: False)
- `use_relaxed` (bool): Use Approach B relaxed causal features (default: False)
- `base_path` (str): Project root directory

**Returns:**
- `tuple`: (X_train, y_train, X_val, y_val, imputation_flags_train, imputation_flags_val, feature_names)

**Example:**
```python
# Load Approach C features for life expectancy
X_tr, y_tr, X_val, y_val, flags_tr, flags_val, feats = load_training_data('life_expectancy')
print(X_tr.shape)  # (7200, 52) - 52 causal features
```

---

##### `evaluate_model()`

Calculate standard regression performance metrics.

**Signature:**
```python
evaluate_model(y_true, y_pred)
```

**Parameters:**
- `y_true` (array-like): Ground truth values, shape (n_samples,)
- `y_pred` (array-like): Model predictions, shape (n_samples,)

**Returns:**
- `dict`: Metrics dictionary with keys:
  - `'r2'` (float): R² score (1.0 = perfect, 0.0 = mean baseline)
  - `'rmse'` (float): Root mean squared error
  - `'mae'` (float): Mean absolute error
  - `'mape'` (float): Mean absolute percentage error (0-100 scale)

**Example:**
```python
metrics = evaluate_model(y_true, y_pred)
print(f"R² = {metrics['r2']:.3f}, RMSE = {metrics['rmse']:.3f}")
```

---

##### `save_model_results()`

Save trained model, performance metrics, and feature importance to disk.

**Signature:**
```python
save_model_results(model, model_name, metric_name, feature_names,
                  train_metrics, val_metrics, output_dir, feature_importance=None)
```

**Parameters:**
- `model`: Trained model object (XGBoost/LightGBM/ElasticNet/PyTorch)
- `model_name` (str): Model type ('xgboost', 'lightgbm', etc.)
- `metric_name` (str): Target metric name
- `feature_names` (list): Feature names used for training
- `train_metrics` (dict): Training set metrics from `evaluate_model()`
- `val_metrics` (dict): Validation set metrics
- `output_dir` (Path|str): Output directory
- `feature_importance` (pd.DataFrame, optional): Feature importance scores

**Returns:**
- `Path`: Full path to saved results JSON file

**Output Files:**
- `model_{model_name}_{metric_name}.pkl` - Model artifact
- `results_{model_name}_{metric_name}.json` - Performance metrics
- `feature_importance_{model_name}_{metric_name}.csv` - Feature importance

---

## Model Training Scripts

### train_xgboost.py

**Location:** `/Data/Scripts/phase3_modules/STEP_3B_PREDICTIVE_TRAINING/train_xgboost.py`

Trains XGBoost gradient boosting models with GPU acceleration.

**Key Features:**
- GPU acceleration via CUDA (30-40× speedup)
- Imputation-aware sample weighting
- Early stopping (50 rounds patience)
- Feature importance extraction (gain + weight metrics)

**Function:**
```python
train_xgboost_with_tracking(metric, use_causal=True, use_phase2=False,
                            use_relaxed=False, max_workers=19)
```

**Parameters:**
- `metric` (str): QOL metric to predict
- `use_causal` (bool): Use Approach C features
- `use_phase2` (bool): Use Approach A features
- `use_relaxed` (bool): Use Approach B features
- `max_workers` (int): CPU threads (if GPU unavailable)

**Returns:**
- `tuple`: (model, results)
  - `model` (xgb.Booster): Trained XGBoost model
  - `results` (dict): Training metadata (metrics, iterations, duration)

**Hyperparameters:**
```python
{
    'objective': 'reg:squarederror',
    'eta': 0.05,              # Learning rate
    'max_depth': 6,
    'subsample': 0.8,
    'colsample_bytree': 0.8,
    'reg_alpha': 0.1,         # L1 regularization
    'reg_lambda': 1.0,        # L2 regularization
    'tree_method': 'hist',
    'device': 'cuda',         # GPU acceleration
    'seed': 42
}
```

**Usage:**
```bash
# Train single metric
python train_xgboost.py --metric life_expectancy

# Train with Approach A
python train_xgboost.py --metric gini --use-phase2

# Train all 8 metrics
python train_xgboost.py
```

---

### train_lightgbm.py

**Location:** `/Data/Scripts/phase3_modules/STEP_3B_PREDICTIVE_TRAINING/train_lightgbm.py`

Trains LightGBM gradient boosting models with CPU multi-threading.

**Key Features:**
- CPU multi-threading (19 threads, 80% utilization)
- Leaf-wise tree growth (faster than XGBoost)
- Native early stopping callback
- Gain + split feature importance

**Function:**
```python
train_lightgbm_with_tracking(metric, use_causal=True, use_phase2=False,
                             use_relaxed=False, max_workers=19)
```

**Parameters:** Same as `train_xgboost_with_tracking()`

**Hyperparameters:**
```python
{
    'objective': 'regression',
    'metric': 'rmse',
    'boosting_type': 'gbdt',
    'learning_rate': 0.05,
    'num_leaves': 31,
    'max_depth': 6,
    'subsample': 0.8,
    'colsample_bytree': 0.8,
    'reg_alpha': 0.1,
    'reg_lambda': 1.0,
    'num_threads': 19,
    'seed': 42
}
```

**Performance:** Best model type across all approaches (7/8 metrics)

---

### train_neural_net.py

**Location:** `/Data/Scripts/phase3_modules/STEP_3B_PREDICTIVE_TRAINING/train_neural_net.py`

Trains PyTorch neural networks with GPU acceleration.

**Architecture:**
- 3 hidden layers: 128 → 64 → 32 neurons
- BatchNorm1d after each hidden layer
- ReLU activation
- Dropout (p=0.2)
- Single output neuron (regression)

**Function:**
```python
train_neural_net_with_tracking(metric, use_causal=True, use_phase2=False,
                               use_relaxed=False, max_epochs=200, batch_size=64)
```

**Parameters:**
- Same as XGBoost, plus:
  - `max_epochs` (int): Maximum training epochs (default: 200)
  - `batch_size` (int): Batch size (default: 64)

**Hyperparameters:**
```python
{
    'hidden_sizes': [128, 64, 32],
    'dropout': 0.2,
    'lr': 0.001,
    'optimizer': 'Adam',
    'weight_decay': 1e-5,
    'scheduler': 'ReduceLROnPlateau(factor=0.5, patience=10)',
    'early_stopping_patience': 20,
    'device': 'cuda' if available else 'cpu'
}
```

**Known Issue:**
BatchNorm requires batch_size ≥ 2. Last batch may cause failure if dataset size % batch_size == 1.

---

### train_elasticnet.py

**Location:** `/Data/Scripts/phase3_modules/STEP_3B_PREDICTIVE_TRAINING/train_elasticnet.py`

Trains ElasticNet linear regression with L1+L2 regularization.

**Function:**
```python
train_elasticnet_with_tracking(metric, use_causal=True, use_phase2=False,
                               use_relaxed=False, n_alphas=100)
```

**Parameters:**
- Same as XGBoost, plus:
  - `n_alphas` (int): Number of alphas to test in CV (default: 100)

**Hyperparameters:**
```python
{
    'l1_ratios': [0.1, 0.3, 0.5, 0.7, 0.9],  # Tested via grid search
    'alphas': None,                          # Automatic selection
    'n_alphas': 100,
    'cv': 5,                                 # 5-fold cross-validation
    'max_iter': 10000,
    'tol': 1e-4,
    'n_jobs': 4
}
```

**Feature Importance:** Absolute coefficient values

---

## Orchestrator Scripts

### train_all_models.py (Approach C)

Train all 32 models (8 metrics × 4 model types) for Approach C (strict causal).

**Usage:**
```bash
python train_all_models.py
```

**Execution:**
- Parallel execution: 8 workers
- Timeout: 10 minutes per model (except neural nets)
- Output: `/models/causal/`

---

### train_all_phase2_features.py (Approach A)

Train all 32 models for Approach A (pure statistical).

**Usage:**
```bash
python train_all_phase2_features.py
```

**Output:** `/models/phase2_retrain/`

---

### train_all_relaxed_features.py (Approach B)

Train all 32 models for Approach B (relaxed causal).

**Usage:**
```bash
python train_all_relaxed_features.py
```

**Output:** `/models/relaxed/`

---

## Verification Scripts

### verify_approach_a_results.py

Verify Approach A training completion and compare to Phase 2 baselines.

**Usage:**
```bash
python verify_approach_a_results.py
```

**Output:**
- Success rate (31/32 = 96.9%)
- Best model per metric
- Comparison to Phase 2 R² baselines
- Full results table

---

### verify_approach_b_results.py

Verify Approach B training completion.

**Usage:**
```bash
python verify_approach_b_results.py
```

---

### generate_three_way_comparison.py

Comprehensive three-way comparison analysis across all approaches.

**Usage:**
```bash
python generate_three_way_comparison.py
```

**Output:**
- `/Documentation/phase_reports/phase3_three_way_comparison.csv`
- Best model performance by metric
- Feature count comparison
- Model type performance
- Winner counts (A: 2/8, B: 0/8, C: 6/8)

---

## Configuration & Hyperparameters

### Imputation Weighting

**Tier System:**
```python
tier_weights = {
    1: 1.0,  # 0-10% imputed (high quality)
    2: 1.0,  # 10-30% imputed (good quality)
    3: 0.7,  # 30-70% imputed (moderate quality)
    4: 0.5   # 70-100% imputed (low quality)
}
```

### Early Stopping

- **Tree models (XGBoost, LightGBM):** 50 rounds patience
- **Neural Networks:** 20 epochs patience
- **ElasticNet:** No early stopping (cross-validation selects alpha)

### Hardware Acceleration

- **XGBoost:** CUDA GPU (`device='cuda'`, `tree_method='hist'`)
- **LightGBM:** CPU (19 threads on Ryzen 9 7900X)
- **Neural Net:** CUDA GPU if available (RTX 4080)
- **ElasticNet:** CPU (4 jobs)

---

## Output Files

### Model Artifacts
- **XGBoost/LightGBM/ElasticNet:** `model_{model_type}_{metric}.pkl` (pickle)
- **Neural Networks:** `model_neural_net_{metric}.pth` (PyTorch state dict)

### Performance Metrics
**File:** `results_{model_type}_{metric}.json`

**Structure:**
```json
{
  "model_name": "xgboost",
  "metric_name": "life_expectancy",
  "timestamp": "2025-10-23T14:30:00",
  "feature_count": 52,
  "train_metrics": {
    "r2": 0.8652,
    "rmse": 0.1234,
    "mae": 0.0987,
    "mape": 5.6
  },
  "val_metrics": {
    "r2": 0.6633,
    "rmse": 0.1567,
    "mae": 0.1234,
    "mape": 7.2
  }
}
```

### Feature Importance
**File:** `feature_importance_{model_type}_{metric}.csv`

**Columns (XGBoost):**
- `feature` (str): Feature name
- `importance_gain` (float): Total gain contribution
- `importance_weight` (int): Number of times feature used in splits

**Columns (LightGBM):**
- `feature` (str): Feature name
- `importance_gain` (float): Total gain contribution
- `importance_split` (int): Number of splits using feature

**Columns (ElasticNet):**
- `feature` (str): Feature name
- `coefficient` (float): Regression coefficient
- `abs_coefficient` (float): Absolute coefficient value

**Columns (Neural Net):**
- `feature` (str): Feature name
- `importance_permutation` (float): Permutation importance (MSE increase)

### Loss Curves
**File:** `loss_curve_{model_type}_{metric}.csv`

**Columns:**
- `model_name`, `metric_name`, `iteration`, `epoch`
- `train_loss`, `val_loss`, `timestamp`
- `train_r2`, `val_r2` (logged every 10 iterations)
- `learning_rate` (for neural nets with schedulers)

---

## Examples

### Example 1: Train Single Model (Approach C)

```python
from train_xgboost import train_xgboost_with_tracking

# Train XGBoost for life expectancy with strict causal features
model, results = train_xgboost_with_tracking('life_expectancy', use_causal=True)

print(f"Validation R²: {results['val_metrics']['r2']:.4f}")
print(f"Features used: {results['feature_count']}")
print(f"Training duration: {results['duration_seconds']:.1f} seconds")
```

**Output:**
```
TRAINING XGBOOST: LIFE_EXPECTANCY
======================================================================
Loading 52 features for life_expectancy
Using temporal_enhanced dataset (includes MA3/MA5/accel features)
...
✓ Training complete in 45.2 seconds (234 iterations)
Validation R²: 0.6633
Features used: 52
Training duration: 45.2 seconds
```

---

### Example 2: Train All Models for One Metric

```bash
#!/bin/bash
# Train all 4 model types for gini coefficient

python train_xgboost.py --metric gini
python train_lightgbm.py --metric gini
python train_neural_net.py --metric gini
python train_elasticnet.py --metric gini

# Verify results
ls <repo-root>/v1.0/models/causal/results_*_gini.json
```

---

### Example 3: Load and Evaluate Saved Model

```python
import pickle
import pandas as pd
from training_utils import load_training_data, evaluate_model

# Load trained model
with open('models/causal/model_xgboost_gini.pkl', 'rb') as f:
    model = pickle.load(f)

# Load test data
X_test = pd.read_csv('Data/Processed/normalized/test_normalized.csv')
y_test = X_test['gini']
feature_list = pd.read_csv('Data/Processed/feature_selection/phase3/features_causal_gini.csv')
X_test = X_test[feature_list['feature']]

# Make predictions
y_pred = model.predict(X_test)

# Evaluate
metrics = evaluate_model(y_test, y_pred)
print(f"Test R²: {metrics['r2']:.4f}")
print(f"Test RMSE: {metrics['rmse']:.4f}")
```

---

### Example 4: Custom Imputation Weights

```python
from training_utils import ImputationWeighter
import pandas as pd

# Define custom tier weights (more aggressive down-weighting)
custom_weights = {
    1: 1.0,   # 0-10% imputed
    2: 0.8,   # 10-30% imputed
    3: 0.5,   # 30-70% imputed
    4: 0.2    # 70-100% imputed (heavily penalized)
}

weighter = ImputationWeighter(tier_weights=custom_weights)

# Calculate weights
imputation_flags = pd.DataFrame({
    'metric1_imputed': [0, 1, 1, 1],
    'metric2_imputed': [0, 0, 1, 1]
})
weights, tiers, pcts = weighter.calculate_weights(imputation_flags)

print(f"Weights: {weights}")  # array([1.0, 0.8, 0.5, 0.5])
print(f"Tiers: {tiers}")      # array([1, 2, 3, 3])
```

---

### Example 5: Analyze Loss Curves

```python
import pandas as pd
import matplotlib.pyplot as plt

# Load loss curve
df = pd.read_csv('Data/Processed/feature_selection/phase3/loss_curves/loss_curve_xgboost_gini.csv')

# Plot convergence
plt.figure(figsize=(10, 6))
plt.plot(df['iteration'], df['train_r2'], label='Train R²', linewidth=2)
plt.plot(df['iteration'], df['val_r2'], label='Validation R²', linewidth=2)
plt.xlabel('Iteration')
plt.ylabel('R² Score')
plt.title('XGBoost Training Convergence: Gini Coefficient')
plt.legend()
plt.grid(True, alpha=0.3)
plt.savefig('xgboost_gini_convergence.png', dpi=300)
```

---

## References

1. **Chen, T. & Guestrin, C. (2016).** XGBoost: A Scalable Tree Boosting System. *KDD '16*. https://doi.org/10.1145/2939672.2939785

2. **Ke, G., et al. (2017).** LightGBM: A Highly Efficient Gradient Boosting Decision Tree. *NIPS 2017*.

3. **Little, R.J.A. & Rubin, D.B. (2002).** Statistical Analysis with Missing Data. *Wiley Series in Probability and Statistics*.

4. **Zou, H. & Hastie, T. (2005).** Regularization and Variable Selection via the Elastic Net. *Journal of the Royal Statistical Society: Series B*, 67(2), 301-320.

---

**Document Version:** 1.0
**Last Updated:** 2025-10-23
**Maintained By:** Claude Code (Sonnet 4.5)
**Contact:** See `/CLAUDE.md` for project documentation
