# Phase 3 Quick Start Guide

**Global Development Indicators Causal Analysis Project**
**Phase:** 3 - Model Training & Causal Preparation
**Version:** 1.0
**Date:** 2025-10-23

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Quick Start (5 Minutes)](#quick-start-5-minutes)
3. [Training Single Models](#training-single-models)
4. [Training All Models (Three Approaches)](#training-all-models-three-approaches)
5. [Verifying Results](#verifying-results)
6. [Understanding Outputs](#understanding-outputs)
7. [Common Issues](#common-issues)
8. [Next Steps](#next-steps)

---

## Prerequisites

### Required Software
- Python 3.8+
- CUDA 11.8+ (optional, for GPU acceleration)
- 16GB+ RAM (32GB recommended)
- 10GB free disk space

### Required Python Packages
```bash
pip install pandas numpy scikit-learn xgboost lightgbm torch
```

Or use the project environment:
```bash
source <repo-root>/v1.0/phase2_env/bin/activate
```

### Required Data Files
Ensure Phase 2 output files exist:
- `/Data/Processed/normalized/train_normalized.csv`
- `/Data/Processed/normalized/val_normalized.csv`
- `/Data/Processed/feature_selection/phase3/features_causal_{metric}.csv` (8 files)
- `/Data/Processed/feature_selection/imputation_adjusted/final_features_imputation_adjusted_{metric}.csv` (8 files)

---

## Quick Start (5 Minutes)

**Objective:** Train your first Phase 3 model in under 5 minutes.

### Step 1: Navigate to Training Directory
```bash
cd <repo-root>/v1.0/Data/Scripts/phase3_modules/STEP_3B_PREDICTIVE_TRAINING
```

### Step 2: Train a Single Model (XGBoost + Approach C)
```bash
python train_xgboost.py --metric gini
```

**Expected Output:**
```
======================================================================
TRAINING XGBOOST: GINI
======================================================================
Loading 23 features for gini
Using temporal_enhanced dataset (includes MA3/MA5/accel features)
Loaded training data: 6840 rows
Loaded validation data: 1482 rows

Sample Weight Distribution (Train):
  Tier 1 (0-10% imputed):   3420 samples (50.0%)
  Tier 2 (10-30% imputed):  2052 samples (30.0%)
  Tier 3 (30-70% imputed):  1026 samples (15.0%)
  Tier 4 (70-100% imputed): 342 samples (5.0%)

Using GPU acceleration: tree_method=hist, device=cuda

Training XGBoost (max 1000 iterations, early stopping after 50)...
  Iteration    0: train_rmse=0.8234, val_rmse=0.8567, train_r2=0.3214, val_r2=0.2987
  Iteration   50: train_rmse=0.4521, val_rmse=0.5123, train_r2=0.7512, val_r2=0.6999
  ...
✓ Training complete in 45.2 seconds (234 iterations)
✓ Loss curve saved: /Data/Processed/feature_selection/phase3/loss_curves/loss_curve_xgboost_gini.csv

Final Performance:
  Train R²: 0.7510, RMSE: 0.4521
  Val R²:   0.6999, RMSE: 0.5123

✓ Results saved: /models/causal/results_xgboost_gini.json
✓ Feature importance saved: /models/causal/feature_importance_xgboost_gini.csv
✓ Model saved: /models/causal/model_xgboost_gini.pkl
```

### Step 3: Verify the Model
```bash
ls <repo-root>/v1.0/models/causal/
```

You should see:
- `model_xgboost_gini.pkl`
- `results_xgboost_gini.json`
- `feature_importance_xgboost_gini.csv`

**Congratulations!** You've trained your first Phase 3 model.

---

## Training Single Models

### Train with Different Model Types

#### XGBoost (GPU-accelerated)
```bash
python train_xgboost.py --metric life_expectancy
```
**Speed:** 30-60 seconds per metric (with GPU)
**Best for:** Balanced performance, GPU available

#### LightGBM (CPU-optimized)
```bash
python train_lightgbm.py --metric infant_mortality
```
**Speed:** 20-40 seconds per metric (CPU)
**Best for:** Fastest training, best overall performance

#### Neural Network (GPU-accelerated)
```bash
python train_neural_net.py --metric mean_years_schooling --max-epochs 200
```
**Speed:** 15-25 seconds per metric (with GPU), 5-10 minutes (CPU)
**Best for:** Non-linear patterns, GPU available

#### ElasticNet (CPU-only)
```bash
python train_elasticnet.py --metric gdp_per_capita --n-alphas 100
```
**Speed:** 10-20 seconds per metric
**Best for:** Linear relationships, interpretable coefficients

---

### Train with Different Feature Approaches

#### Approach A: Pure Statistical (40 features)
**Purpose:** Maximum predictive power
```bash
python train_xgboost.py --metric gini --use-phase2
```

#### Approach B: Relaxed Causal (25-30 features)
**Purpose:** Balance prediction and causality
```bash
python train_xgboost.py --metric homicide --use-relaxed
```

#### Approach C: Strict Causal (23-52 features)
**Purpose:** Maximum causal interpretability (default)
```bash
python train_xgboost.py --metric undernourishment
```

---

## Training All Models (Three Approaches)

### Approach A: Pure Statistical (Recommended for Baselines)

**Trains:** 8 metrics × 4 model types = 32 models
**Duration:** ~30 minutes
**Output:** `/models/phase2_retrain/`

```bash
python train_all_phase2_features.py
```

**Expected Results:**
- 31/32 models successful (neural_net/gdp_per_capita fails due to BatchNorm issue)
- Best infant_mortality: R² = 0.907 (LightGBM)
- Best mean_years_schooling: R² = 0.924 (LightGBM)

---

### Approach B: Relaxed Causal (Recommended for Feature Efficiency)

**Trains:** 8 metrics × 4 model types = 32 models
**Duration:** ~1-1.5 hours
**Output:** `/models/relaxed/`

```bash
python train_all_relaxed_features.py
```

**Expected Results:**
- 31/32 models successful
- Best feature efficiency (R² per feature)
- <10pp degradation from Approach A for all metrics

---

### Approach C: Strict Causal (Recommended for Phase 4 Causal Discovery)

**Trains:** 8 metrics × 4 model types = 32 models
**Duration:** ~35-40 minutes
**Output:** `/models/causal/`

```bash
python train_all_models.py
```

**Expected Results:**
- 31/32 models successful
- **Wins 6/8 metrics** (life_expectancy, gdp_per_capita, gini, homicide, undernourishment, internet_users)
- Causal filtering improves 3 metrics: gini (+0.035), homicide (+0.151), internet_users (+0.151)

---

## Verifying Results

### Verify Single Approach

#### Verify Approach A
```bash
python verify_approach_a_results.py
```

**Output:**
- Success rate: 31/32 (96.9%)
- Best model per metric
- Comparison to Phase 2 baselines
- Full results table

#### Verify Approach B
```bash
python verify_approach_b_results.py
```

#### Verify Approach C
Approach C results are automatically summarized after training completion.

---

### Three-Way Comparison

**Compare all three approaches:**
```bash
python generate_three_way_comparison.py
```

**Output:**
- `/Documentation/phase_reports/phase3_three_way_comparison.csv`
- Best model performance by metric
- Feature count comparison
- Model type performance
- Winner counts by approach
- Recommendations

---

## Understanding Outputs

### Model Artifacts

**Location:** `/models/{causal|phase2_retrain|relaxed}/`

**Files:**
- `model_{model_type}_{metric}.pkl` - Trained model (XGBoost/LightGBM/ElasticNet)
- `model_neural_net_{metric}.pth` - Neural network state dict (PyTorch)

**Load model:**
```python
import pickle
with open('models/causal/model_xgboost_gini.pkl', 'rb') as f:
    model = pickle.load(f)
```

---

### Performance Metrics

**Location:** `results_{model_type}_{metric}.json`

**Example:**
```json
{
  "model_name": "xgboost",
  "metric_name": "gini",
  "timestamp": "2025-10-23T14:30:00",
  "feature_count": 23,
  "train_metrics": {
    "r2": 0.7510,
    "rmse": 0.4521,
    "mae": 0.3456,
    "mape": 12.5
  },
  "val_metrics": {
    "r2": 0.6999,
    "rmse": 0.5123,
    "mae": 0.4012,
    "mape": 15.2
  }
}
```

**Key Metrics:**
- **R²:** 1.0 = perfect, 0.0 = mean baseline, <0 = worse than mean
- **RMSE:** Root mean squared error (lower is better)
- **MAE:** Mean absolute error (interpretable in target units)
- **MAPE:** Mean absolute percentage error (0-100 scale)

---

### Feature Importance

**Location:** `feature_importance_{model_type}_{metric}.csv`

**Example (XGBoost):**
```csv
feature,importance_gain,importance_weight
SH.XPD.CHEX.GD.ZS,245.3,45
NY.GDP.PCAP.CD,189.7,38
SE.XPD.TOTL.GD.ZS,156.2,32
...
```

**Interpretation:**
- **importance_gain:** Total information gain from feature splits (higher = more important)
- **importance_weight:** Number of times feature used in splits

**Top-10 features:**
```bash
head -11 feature_importance_xgboost_gini.csv
```

---

### Loss Curves

**Location:** `/Data/Processed/feature_selection/phase3/loss_curves/loss_curve_{model_type}_{metric}.csv`

**Example:**
```csv
model_name,metric_name,iteration,epoch,train_loss,val_loss,timestamp,train_r2,val_r2,learning_rate
xgboost,gini,0,0,0.8234,0.8567,2025-10-23T14:30:00,0.3214,0.2987,0.05
xgboost,gini,10,10,0.6234,0.6789,2025-10-23T14:30:15,0.5432,0.5123,0.05
...
```

**Visualize:**
```python
import pandas as pd
import matplotlib.pyplot as plt

df = pd.read_csv('loss_curves/loss_curve_xgboost_gini.csv')
plt.plot(df['iteration'], df['val_r2'])
plt.xlabel('Iteration')
plt.ylabel('Validation R²')
plt.title('XGBoost Convergence: Gini Coefficient')
plt.savefig('convergence.png')
```

---

## Common Issues

### Issue 1: GPU Not Found (XGBoost/Neural Networks)

**Error:**
```
RuntimeError: CUDA not available
```

**Solution:**
Scripts automatically fall back to CPU. To verify CUDA:
```python
import torch
print(torch.cuda.is_available())  # Should return True
```

If False, install CUDA-enabled PyTorch:
```bash
pip install torch --index-url https://download.pytorch.org/whl/cu121
```

---

### Issue 2: Neural Network BatchNorm Error

**Error:**
```
RuntimeError: batch_size must be at least 2 for BatchNorm
```

**Cause:** Last batch has size 1 (dataset size % batch_size == 1)

**Solution:**
This is a known issue for `neural_net/gdp_per_capita`. Use LightGBM or XGBoost instead (better performance anyway).

**Workaround:**
```bash
# Increase batch size to avoid remainder of 1
python train_neural_net.py --metric gdp_per_capita --batch-size 128
```

---

### Issue 3: FileNotFoundError for Feature Lists

**Error:**
```
FileNotFoundError: Feature file not found: /Data/Processed/feature_selection/phase3/features_causal_gini.csv
```

**Solution:**
Ensure Phase 2 and Phase 3A completed successfully. Re-run causal classification:
```bash
cd /Data/Scripts/phase3_modules/STEP_3A_CAUSAL_FILTERING
python classify_causal_features.py
python create_filtered_sets.py
```

---

### Issue 4: Out of Memory (Neural Networks)

**Error:**
```
RuntimeError: CUDA out of memory
```

**Solution:**
Reduce batch size:
```bash
python train_neural_net.py --metric life_expectancy --batch-size 32
```

Or use CPU:
```bash
# Disable GPU
export CUDA_VISIBLE_DEVICES=""
python train_neural_net.py --metric life_expectancy
```

---

### Issue 5: Slow Training (No GPU)

**Problem:** Neural networks train for 5-10 minutes instead of 15-25 seconds

**Solution:**
1. Verify GPU availability (see Issue 1)
2. Use LightGBM instead (fastest on CPU):
```bash
python train_lightgbm.py --metric gini
```

---

## Next Steps

### After Training Completion

#### 1. Analyze Results
```bash
# Three-way comparison
python generate_three_way_comparison.py

# View summary CSV
head -20 <repo-root>/v1.0/Documentation/phase_reports/phase3_three_way_comparison.csv
```

#### 2. Select Best Models for Phase 4

**Recommendation:** Use Approach C (strict causal) for 6/8 metrics:
- life_expectancy
- gdp_per_capita
- gini
- homicide
- undernourishment
- internet_users

**Use Approach A (pure statistical) for 2/8 metrics:**
- infant_mortality
- mean_years_schooling

#### 3. Export Feature Importance

```python
import pandas as pd

# Load top-10 features for each metric
metrics = ['life_expectancy', 'infant_mortality', 'mean_years_schooling',
           'gdp_per_capita', 'gini', 'homicide', 'undernourishment', 'internet_users']

for metric in metrics:
    df = pd.read_csv(f'models/causal/feature_importance_lightgbm_{metric}.csv')
    print(f"\n{metric.upper()} - Top 10 Features:")
    print(df.head(10))
```

#### 4. Visualize Convergence

```python
import pandas as pd
import matplotlib.pyplot as plt

metrics = ['gini', 'homicide', 'internet_users']  # Metrics improved by causal filtering
fig, axes = plt.subplots(1, 3, figsize=(15, 5))

for idx, metric in enumerate(metrics):
    df = pd.read_csv(f'loss_curves/loss_curve_lightgbm_{metric}.csv')
    axes[idx].plot(df['iteration'], df['val_r2'], label='Validation R²')
    axes[idx].set_title(f'{metric.replace("_", " ").title()}')
    axes[idx].set_xlabel('Iteration')
    axes[idx].set_ylabel('R²')
    axes[idx].grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig('causal_improvements.png', dpi=300)
```

#### 5. Prepare for Phase 4 (Causal Discovery)

**Copy best models to Phase 4 directory:**
```bash
mkdir -p /Data/Scripts/phase4_causal_discovery/models

# Copy Approach C models (6 metrics)
cp models/causal/model_lightgbm_life_expectancy.pkl /Data/Scripts/phase4_causal_discovery/models/
cp models/causal/model_lightgbm_gdp_per_capita.pkl /Data/Scripts/phase4_causal_discovery/models/
cp models/causal/model_lightgbm_gini.pkl /Data/Scripts/phase4_causal_discovery/models/
cp models/causal/model_lightgbm_homicide.pkl /Data/Scripts/phase4_causal_discovery/models/
cp models/causal/model_lightgbm_undernourishment.pkl /Data/Scripts/phase4_causal_discovery/models/
cp models/causal/model_lightgbm_internet_users.pkl /Data/Scripts/phase4_causal_discovery/models/

# Copy Approach A models (2 metrics)
cp models/phase2_retrain/model_lightgbm_infant_mortality.pkl /Data/Scripts/phase4_causal_discovery/models/
cp models/phase2_retrain/model_lightgbm_mean_years_schooling.pkl /Data/Scripts/phase4_causal_discovery/models/
```

---

## Advanced Usage

### Custom Imputation Weights

```python
# Edit training_utils.py
tier_weights = {
    1: 1.0,   # 0-10% imputed
    2: 0.8,   # 10-30% imputed (more aggressive)
    3: 0.5,   # 30-70% imputed
    4: 0.2    # 70-100% imputed (heavily penalized)
}
```

### Custom Hyperparameters

**Edit XGBoost parameters in `train_xgboost.py`:**
```python
params = {
    'objective': 'reg:squarederror',
    'eta': 0.01,              # Lower learning rate (slower, more accurate)
    'max_depth': 8,           # Deeper trees
    'subsample': 0.7,
    'colsample_bytree': 0.7,
    'reg_alpha': 0.5,         # Stronger L1 regularization
    'reg_lambda': 2.0,        # Stronger L2 regularization
}
```

### Parallel Training (Multiple Metrics)

```bash
# Train 4 metrics in parallel (4 cores)
parallel -j 4 python train_lightgbm.py --metric {} ::: life_expectancy infant_mortality gdp_per_capita gini
```

---

## Resources

### Documentation
- **Phase 3 Report:** `/Documentation/phase_reports/phase3_report.md`
- **API Reference:** `/Documentation/phase3_api_reference.md`
- **Three-Way Comparison:** `/Documentation/phase_reports/phase3_three_pronged_summary.md`

### Code
- **Training Scripts:** `/Data/Scripts/phase3_modules/STEP_3B_PREDICTIVE_TRAINING/`
- **Phase 3 README:** `/Data/Scripts/phase3_modules/STEP_3B_PREDICTIVE_TRAINING/README.md`

### Support
- **Project Documentation:** `/CLAUDE.md`
- **Phase Planning:** `/plan.md`

---

**Document Version:** 1.0
**Last Updated:** 2025-10-23
**Maintained By:** Claude Code (Sonnet 4.5)
