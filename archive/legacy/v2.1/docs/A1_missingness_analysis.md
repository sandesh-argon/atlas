# A1: Missingness Analysis

## Overview

**Phase**: A1 (Data Preprocessing)
**Purpose**: Handle missing data and select optimal imputation configuration
**Input**: Raw indicator data from 11 external sources (from V2 A0)
**Output**: Preprocessed, imputed dataset ready for causal analysis
**Status in V2.1**: **REUSED FROM V2** (no changes)

## Important Note for V2.1

**V2.1 does NOT re-run A1**. Instead, it:

1. Uses V2's already-preprocessed data as input
2. Applies stratified sampling in A0 (step0_stratified_sampling.py)
3. The sampled data already includes A1's imputation work

Therefore, this document serves as a **reference** to understand the preprocessing that was done in V2, which V2.1 inherits.

## V2 A1 Pipeline (For Reference)

### Purpose

Handle missing data in development economics indicators, where missingness can exceed 70% for some variables. The goal is to:

1. Quantify missingness patterns
2. Test multiple imputation strategies
3. Select the optimal configuration via sensitivity analysis
4. Preserve imputation quality metadata (tier system)

### Imputation Strategies Tested in V2

V2 ran 25 parallel configurations testing:

1. **MICE (Multiple Imputation by Chained Equations)**
   - Variants: 5, 10, 20 iterations
   - Algorithms: PMM (Predictive Mean Matching), Random Forest

2. **KNN Imputation**
   - k values: 3, 5, 10, 20
   - Distance metrics: Euclidean, Manhattan

3. **Temporal interpolation**
   - Linear interpolation for time series
   - Spline interpolation (cubic)

4. **Hybrid strategies**
   - Temporal first, then MICE for remaining gaps
   - Temporal first, then KNN

### V2 Tier System

To preserve imputation quality metadata, V2 assigned each imputed value a tier:

| Tier | Method | Weight | Description |
|------|--------|--------|-------------|
| 0 | Observed | 1.00 | Original data point (no imputation) |
| 1 | Temporal Interpolation | 0.85 | Linear/spline interpolation between observed years |
| 2 | MICE (<40% missing) | 0.70 | MICE imputation when variable has <40% missingness |
| 3 | MICE (>40% missing) | 0.50 | MICE imputation when variable has >40% missingness |
| 4 | KNN | 0.60 | K-nearest neighbors imputation |

**Usage in V2.1**: These tier weights are used in:
- A2: SHAP-based downweighting during Granger causality
- A4: Effect size downweighting during backdoor adjustment
- B1: Factor validation (R² penalization for high-tier values)

### V2 Optimal Configuration (Selected)

After running 25 configurations, V2 selected:

**Winner**: Hybrid temporal + MICE (PMM, 10 iterations)

**Performance**:
- Mean R² improvement: +5.6% over baseline
- Cross-validation score: 0.84
- Coverage: 94.2% of all country-year pairs
- Tier 0 (observed): 47.8%
- Tier 1 (temporal): 28.3%
- Tier 2-3 (MICE): 23.9%

### V2 Preprocessing Steps

1. **Raw data collection** (A0)
   - 11 sources: World Bank, WHO, UNESCO, UNICEF, V-Dem, QoG, IMF, OECD, Penn, WID, Transparency
   - Initial: ~9,500 indicators

2. **Coverage filter**
   - Country coverage ≥ 80 countries
   - Temporal span ≥ 10 years
   - Per-country temporal coverage ≥ 0.80 (V1 lesson: avoid global coverage)
   - After filter: ~6,400 indicators

3. **Temporal alignment**
   - Golden window: 1990-2024 (35 years)
   - Align all indicators to this window
   - Pad with NaN for missing years

4. **Variance filter**
   - Remove constant indicators (variance = 0)
   - Remove near-constant (variance < 0.01)
   - After filter: 6,368 indicators

5. **Imputation**
   - Stage 1: Temporal interpolation (within each country's time series)
   - Stage 2: MICE (PMM, 10 iterations) for remaining gaps
   - Track tier for each imputed value

6. **Normalization**
   - Z-score normalization per indicator
   - Formula: `(x - μ) / σ`
   - Computed on full dataset (all countries, all years)

7. **Saturation transforms** (Applied in B1, NOT A1)
   - For deficiency needs (life expectancy, GDP, health, education)
   - Evidence: +5.6% R² improvement in V1
   - Timing: After factor discovery (B1), not at A1 preprocessing

## V2.1 Usage of V2 A1 Output

### Input to V2.1 A0

V2.1's `step0_stratified_sampling.py` loads:

```python
# Load V2 preprocessed data (output of V2 A1)
A2_DATA_PATH = PROJECT_ROOT / 'phaseA' / 'A1_missingness_analysis' / 'outputs' / 'A2_preprocessed_data.pkl'

with open(A2_DATA_PATH, 'rb') as f:
    a2_data = pickle.load(f)

# Structure:
# {
#   'imputed_data': {indicator_name: DataFrame[country × year]},
#   'tier_data': {indicator_name: DataFrame[country × year]},
#   'metadata': {indicator_name: {source, variance, missing_rate, ...}},
#   'preprocessing_info': {timestamp, variance_threshold, initial_count, ...}
# }
```

### What V2.1 Preserves

After sampling 6,368 → 3,122 indicators, V2.1 preserves:

1. **Imputed values**: All imputation work from V2 A1
2. **Tier metadata**: Quality tracking for each value
3. **Metadata**: Source, variance, temporal coverage stats
4. **Preprocessing info**: Timestamp, filters applied

## Data Structure Reference

### imputed_data

```python
imputed_data = {
    'indicator_name': pd.DataFrame(
        index=['USA', 'GBR', 'DEU', ...],  # Countries (ISO3)
        columns=[1990, 1991, ..., 2024],    # Years
        data=[[12.5, 12.8, 13.1, ...],      # Values (normalized)
              [10.2, 10.5, 10.7, ...],
              ...]
    )
}
```

### tier_data

```python
tier_data = {
    'indicator_name': pd.DataFrame(
        index=['USA', 'GBR', 'DEU', ...],
        columns=[1990, 1991, ..., 2024],
        data=[[0, 0, 1, ...],  # 0=observed, 1=temporal, 2-3=MICE
              [0, 1, 1, ...],
              ...]
    )
}
```

### metadata

```python
metadata = {
    'indicator_name': {
        'source': 'world_bank',
        'original_name': 'NY.GDP.PCAP.PP.KD',
        'description': 'GDP per capita, PPP (constant 2017 international $)',
        'n_countries': 189,
        'temporal_window': (1990, 2024),
        'n_years_in_window': 35,
        'original_missing_rate': 0.234,
        'imputed_missing_rate': 0.047,
        'variance': 1.523,
        'tier_distribution': {
            '0': 0.478,  # 47.8% observed
            '1': 0.283,  # 28.3% temporal
            '2': 0.192,  # 19.2% MICE <40%
            '3': 0.047   # 4.7% MICE >40%
        }
    }
}
```

## Validation in V2

### Cross-Validation

V2 A1 used 5-fold cross-validation:

1. Hold out 20% of observed values
2. Impute using candidate configuration
3. Measure R² between imputed and held-out values
4. Repeat 5 times, average R²

**Winner**: Hybrid temporal + MICE (R² = 0.84)

### Domain Coverage

Ensured no domain lost >50% of indicators:

| Domain | Before Filter | After Filter | Retention |
|--------|---------------|--------------|-----------|
| Economic | 3,200 | 2,056 | 64.3% |
| Governance | 3,800 | 2,633 | 69.3% |
| Education | 1,900 | 1,557 | 81.9% |
| Health | 600 | 122 | 20.3% |

**Note**: Health had low retention due to WHO data quality issues (many indicators with >70% missingness).

## Key Differences from V1 (Lessons Applied)

### 1. Per-Country Temporal Coverage (V1 Lesson)

**V1 Mistake**: Used global coverage threshold
- Indicator kept if ≥80% of ALL country-years had data
- Result: Lost 94% of data due to uneven country coverage

**V2 Fix**: Per-country temporal coverage
- Indicator kept if ≥80% of years have data FOR EACH country
- Result: Retained 6,368 indicators (vs ~400 in V1)

### 2. Imputation Weighting (V1 Lesson)

**V1 Mistake**: Treated all imputed values equally
- MICE with 70% missingness weighted same as observed data
- Result: Spurious correlations from low-quality imputations

**V2 Fix**: Tier-based weighting
- Evidence: +0.92pp mean R² improvement in V1 post-hoc test
- Used in A2 (SHAP weights), A4 (effect sizes), B1 (validation)

### 3. No Early Normalization (V1 Lesson)

**V1 Mistake**: Normalized → saturated
- Destroyed saturation curves for deficiency needs
- Result: Lost non-linear relationships (e.g., life expectancy plateaus at 80 years)

**V2 Fix**: Saturate → normalize
- Saturation applied in B1 (after factor discovery)
- Normalization applied in A1 (before causal testing)

## Files and Locations

### V2 A1 Output (Used by V2.1 A0)

**File**: `<repo-root>/v2.0/phaseA/A1_missingness_analysis/outputs/A2_preprocessed_data.pkl`

**Size**: ~530 MB (compressed pickle)

**Contains**:
- 6,368 indicators × 180 countries × 35 years
- Imputed values + tier metadata
- Preprocessing metadata

### V2.1 A0 Output (Input to A2)

**File**: `<repo-root>/v2.0/v2.1/outputs/A2_preprocessed_data_V21.pkl`

**Size**: ~252 MB (compressed pickle)

**Contains**:
- 3,122 indicators (sampled from 6,368)
- Same structure as V2 A1 output
- Additional: `v21_sampling_info` metadata

## References

- V2 A1 Pipeline: `<repo-root>/v2.0/phaseA/A1_missingness_analysis/`
- V1 Lessons: `<repo-root>/v2.0/V1_LESSONS.md`
- Imputation weighting: `<repo-root>/v2.0/shared_utilities/data_processing/imputation_weighting.py`
- CLAUDE.md: Lines 54-133 (Imputation weighting evidence)

## Next Step

After V2.1 A0 (stratified sampling), the sampled dataset proceeds to:

**A2**: Granger Causality Testing
- Input: 3,122 indicators
- Candidate pairs: ~9.7M (down from 40.6M in full V2)
- Runtime: 2-3 hours (vs 7 hours in V2)
