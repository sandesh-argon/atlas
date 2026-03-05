# A1 Missingness Sensitivity Analysis

**Status**: 🔄 Ready to Start
**Input Data**: `../A0_data_acquisition/raw_data_standardized/` (40,881 indicators)
**Timeline**: 3-5 days on AWS p3.8xlarge instance

---

## Objective

Determine the optimal imputation strategy and missingness threshold for causal discovery by testing **25 parallel configurations** and selecting the configuration that maximizes:
1. Edge retention (Granger causality validation)
2. Model predictive power (R²)
3. Computational efficiency

---

## Input Data

**Location**: `phaseA/A0_data_acquisition/raw_data_standardized/`

**Contents**:
- **Indicators**: 40,881 clean, standardized indicators
- **Countries**: 220 (pre-standardized, zero preprocessing needed)
- **Format**: CSV (Country, Year, Value) - ready to use
- **Temporal Span**: 1800-2024 (224 years)

**Quality Assurance (from A0)**:
- ✅ Country names already standardized (711 → 220 variants)
- ✅ Duplicates already removed (66 highly-correlated indicators)
- ✅ V-Dem confidence intervals already filtered (4,587 → 2,260)
- ✅ Data in 100% consistent format

**NO PREPROCESSING NEEDED** - load and analyze directly.

---

## A1 Tasks

### 1. Load Data
```python
# Load all 40,881 indicators from standardized directory
import pandas as pd
from pathlib import Path

STANDARDIZED_DIR = Path("../A0_data_acquisition/raw_data_standardized")

all_files = list(STANDARDIZED_DIR.rglob("*.csv"))
print(f"Found {len(all_files):,} indicator files")

# Expected: 40,881 files
```

### 2. Apply Initial Filters

**Before imputation testing**, apply these filters to reduce computational load:

```python
# Filter 1: Country coverage ≥ 80 countries
# Filter 2: Temporal span ≥ 10 years
# Filter 3: Per-country temporal coverage ≥ 0.80
# Filter 4: Missing rate ≤ 0.70
```

**Expected Reduction**: 40,881 → ~25,000-30,000 indicators

**Why filter first?**
- Reduces computational cost by 30-40%
- Eliminates indicators that would fail missingness threshold anyway
- Still tests imputation quality on realistic subset

### 3. Design Experimental Matrix (25 Configurations)

Test **5 imputation methods × 5 missingness thresholds**:

#### Imputation Methods
1. **MICE (Multivariate Imputation by Chained Equations)**
   - Most robust for MAR (Missing At Random) data
   - Uses iterative regression
   - Expected best performance

2. **KNN Imputation (k=5)**
   - Uses k-nearest neighbors in feature space
   - Fast, non-parametric
   - Good for non-linear patterns

3. **Random Forest Imputation**
   - Captures complex non-linear relationships
   - Handles mixed data types well
   - Slower but powerful

4. **Linear Interpolation**
   - Time-series focused
   - Assumes smooth trends
   - Fast but limited to temporal patterns

5. **Forward Fill**
   - Carries last observation forward
   - Simple baseline
   - Assumes temporal stability

#### Missingness Thresholds
- **0.30**: Keep indicators with ≤30% missing data (most restrictive)
- **0.40**: Keep indicators with ≤40% missing data
- **0.50**: Keep indicators with ≤50% missing data (balanced)
- **0.60**: Keep indicators with ≤60% missing data
- **0.70**: Keep indicators with ≤70% missing data (most permissive)

### 4. Run 25 Parallel Configurations

```python
import joblib
from itertools import product

imputation_methods = ['MICE', 'KNN', 'RandomForest', 'LinearInterpolation', 'ForwardFill']
missingness_thresholds = [0.30, 0.40, 0.50, 0.60, 0.70]

configs = list(product(imputation_methods, missingness_thresholds))
# 25 configurations total

# Parallel execution
results = joblib.Parallel(n_jobs=25)(
    joblib.delayed(test_config)(method, threshold, data)
    for method, threshold in configs
)
```

### 5. Evaluation Metrics

For each configuration, compute:

#### Edge Retention (Primary Metric)
```python
# Run Granger causality tests on sample (1000 pairs)
# Count: How many edges remain significant?
edge_retention = n_significant_edges / n_total_edges
```

**Target**: >75% edge retention vs. fully observed data

#### Model R² (Secondary Metric)
```python
# Train LightGBM on 100 random indicators
# Cross-validation R² (5-fold)
mean_r2 = np.mean([r2_indicator1, r2_indicator2, ..., r2_indicator100])
```

**Target**: >0.55 mean R²

#### Computational Cost (Tertiary Metric)
```python
# Track imputation runtime
runtime_minutes = (end_time - start_time) / 60
```

**Target**: <6 hours for full imputation on 30K indicators

### 6. Select Optimal Configuration

```python
# Multi-criteria decision
# Priority: Edge retention (50%), R² (35%), Runtime (15%)

score = (0.50 * edge_retention) + (0.35 * mean_r2) + (0.15 * (1 - runtime_normalized))

optimal_config = configs[np.argmax(scores)]
```

**Expected Winner**: MICE with 0.45-0.55 threshold

---

## A1 Expected Outputs

### 1. Optimal Configuration Selection
- **Best imputation method**: Likely MICE or KNN
- **Best missingness threshold**: Likely 0.45-0.55
- **Justification**: Edge retention, R², computational cost trade-off

### 2. Filtered Indicator Set
- **Input**: 40,881 indicators (from A0)
- **After initial filters**: ~25,000-30,000 indicators
- **After missingness filter**: ~4,000-6,000 indicators
- **Format**: Same CSV (Country, Year, Value), imputed where missing

### 3. Validation Report
```
A1_MISSINGNESS_REPORT.md:
- Configuration comparison table (25 rows)
- Edge retention analysis
- R² distribution plots
- Computational cost analysis
- Final recommendation with justification
```

### 4. Checkpoint for A2
```python
# Save filtered and imputed dataset
optimal_data.to_pickle("A1_optimal_imputed_data.pkl")

# Save configuration metadata
config_metadata = {
    'imputation_method': 'MICE',
    'missingness_threshold': 0.50,
    'edge_retention': 0.82,
    'mean_r2': 0.61,
    'runtime_hours': 4.2,
    'n_indicators_final': 4872,
    'imputation_weights_applied': True  # V1 lesson learned
}

with open('A1_optimal_config.json', 'w') as f:
    json.dump(config_metadata, f, indent=2)
```

---

## V1 Lessons Integrated

### 1. Imputation Weighting (CRITICAL)
From V1: Imputation weighting improved 8/8 metrics (+0.92pp mean R²)

**Apply tier weights**:
- Tier 1 (observed): 1.0
- Tier 2 (interpolation): 0.85
- Tier 3 (MICE <40% missing): 0.70
- Tier 4 (MICE >40% missing): 0.50

**Use weights in**:
- A2: SHAP downweighting for variable selection
- A4: Effect size downweighting
- B1: Factor analysis validation

**Implementation**:
```python
# Tag each value with imputation tier
data['imputation_tier'] = assign_tier(data['imputed'], data['original'], data['missing_rate'])

# Apply weights in downstream analysis
shap_values_weighted = shap_values * data['imputation_tier']
```

### 2. Per-Country Temporal Coverage (CRITICAL)
From V1: Global coverage filter caused 80-94% data loss

**Use per-country filter**:
- ❌ DON'T: Require 80% global temporal coverage
- ✅ DO: Require 80% per-country temporal coverage

**Example**:
```python
# BAD (V1 mistake)
keep = (data.notna().sum() / len(data)) >= 0.80

# GOOD (V2 approach)
keep = data.groupby('Country').apply(
    lambda x: (x.notna().sum() / len(x)) >= 0.80
).mean() >= 0.80
```

### 3. Saturation Transforms (DO NOT APPLY YET)
From V1: Saturation transforms improved R² by +5.6%

**⚠️ IMPORTANT**: Do NOT apply saturation in A1.

**Why?**
- Saturation requires knowing which variables are "deficiency needs" (life expectancy, mortality, etc.)
- V2 discovers outcomes in B1 (we don't know them yet!)
- Apply saturation at B1, AFTER factor analysis identifies deficiency needs

**Bookmark for B1**:
- Saturation functions in `shared_utilities/data_processing/saturation_transforms.py`
- Apply AFTER outcome discovery, BEFORE factor validation

---

## Success Criteria

### Minimum Acceptable
- ✅ Edge retention: >75%
- ✅ Mean R²: >0.55
- ✅ Runtime: <8 hours on p3.8xlarge
- ✅ Final indicator count: 4,000-6,000

### Target (Ideal)
- ✅ Edge retention: >80%
- ✅ Mean R²: >0.60
- ✅ Runtime: <6 hours
- ✅ Final indicator count: ~5,000

### Failure Conditions (Abort A1)
- ❌ Edge retention: <60% (imputation too aggressive)
- ❌ Mean R²: <0.45 (poor predictive power)
- ❌ Runtime: >12 hours (computational bottleneck)
- ❌ Final indicator count: <3,000 (insufficient data for causal discovery)

---

## Computational Environment

### AWS EC2 Instance
- **Instance Type**: p3.8xlarge
- **vCPUs**: 32
- **Memory**: 244 GB RAM
- **GPUs**: 4x NVIDIA V100 (16 GB each)
- **Storage**: 500 GB SSD

### Software Requirements
```bash
# Python 3.10+
pip install pandas numpy scikit-learn lightgbm statsmodels shap joblib

# Imputation libraries
pip install scikit-learn  # KNN, RF imputation
pip install fancyimpute    # MICE implementation
```

### Parallelization Strategy
```python
# 25 configurations → 25 parallel jobs
# Each job: 1 vCPU, 9 GB RAM
# Expected runtime: 3-5 hours per config
# Total wall time: 3-5 hours (parallelized)
```

---

## Timeline

| Day | Task | Duration |
|-----|------|----------|
| **Day 1** | Setup, load data, apply initial filters | 4 hours |
| **Day 2** | Run 25 parallel configurations | 6-8 hours |
| **Day 3** | Evaluate results, select optimal config | 4 hours |
| **Day 4** | Apply optimal config to full dataset | 4 hours |
| **Day 5** | Validation, checkpoint generation | 4 hours |

**Total**: 3-5 days (includes buffer for debugging)

---

## Next Phase: A2 Granger Causality Testing

**Input from A1**: ~4,000-6,000 imputed indicators
**A2 Task**: Prefilter (6.2M → 200K pairs) → Granger tests → Validated edges

**A2 Prefiltering Stages** (from master instructions):
1. Correlation threshold (0.10 < |r| < 0.95)
2. Domain compatibility matrix (13×13 plausibility map)
3. Temporal precedence (exclude self-lagged)
4. Literature plausibility check
5. Theoretical plausibility

**A2 Expected Outputs**:
- 2,000-10,000 validated causal edges
- Mean effect size |β| > 0.15
- Bootstrap retention >75%

---

## Start Command

```bash
cd phaseA/A1_missingness_analysis/

python run_a1_missingness_analysis.py \
  --input ../A0_data_acquisition/raw_data_standardized/ \
  --n_configs 25 \
  --n_jobs 25 \
  --output A1_optimal_imputed_data.pkl
```

---

## File Organization

```
A1_missingness_analysis/
├── A1_INSTRUCTIONS.md              # This file
├── run_a1_missingness_analysis.py  # Main script
├── imputation_utils.py             # MICE, KNN, RF implementations
├── evaluation_metrics.py           # Edge retention, R², runtime
├── config_selection.py             # Multi-criteria decision
├── A1_MISSINGNESS_REPORT.md       # Results report (generated)
├── A1_optimal_config.json         # Selected configuration (generated)
├── A1_optimal_imputed_data.pkl    # Final imputed dataset (generated)
└── validation/
    ├── edge_retention_results.csv
    ├── r2_distribution.png
    └── runtime_comparison.png
```

---

## ✅ A1 CHECKLIST

- [ ] Load 40,881 indicators from A0 standardized directory
- [ ] Apply initial filters (coverage, temporal, missingness)
- [ ] Reduce to ~25,000-30,000 indicators
- [ ] Design 25 configuration matrix (5 methods × 5 thresholds)
- [ ] Run parallel imputation experiments
- [ ] Evaluate: Edge retention, R², computational cost
- [ ] Select optimal configuration (multi-criteria)
- [ ] Apply optimal config to full filtered dataset
- [ ] Generate A1_MISSINGNESS_REPORT.md
- [ ] Save A1_optimal_config.json
- [ ] Save A1_optimal_imputed_data.pkl
- [ ] Validate final dataset quality
- [ ] Ready for A2 (Granger Causality Testing)

---

## 🚀 START A1 - DATA IS READY

**Input**: 40,881 standardized indicators (zero preprocessing needed)
**Output**: ~4,000-6,000 imputed indicators + optimal configuration
**Timeline**: 3-5 days
**Status**: READY TO START

Run: `python run_a1_missingness_analysis.py --input ../A0_data_acquisition/raw_data_standardized/`

---

**Prepared by**: Claude Code (V2 Research Specification)
**Date**: November 13, 2025
**Previous Phase**: A0 (COMPLETE & CLOSED)
**Current Phase**: A1 (READY TO START)
**Next Phase**: A2 (Granger Causality Testing)
