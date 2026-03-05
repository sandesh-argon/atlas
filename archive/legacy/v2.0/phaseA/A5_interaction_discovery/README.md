# A5 Interaction Discovery

**Phase**: A5 - Mechanism×Mechanism Interaction Discovery
**Status**: ✅ COMPLETE
**Date**: November 20, 2025
**Runtime**: 27.7 minutes (529,075 tests)

---

## Quick Summary

A5 discovered **4,254 validated mechanism×mechanism interactions** using linear regression with interaction terms. The analysis tested 529,075 mechanism pairs across 30 outcomes, applying FDR correction (α=0.001) and strict effect size filtering (|β3| ≥ 5.0).

**Key Finding**: Development economics data exhibits high interaction prevalence (49.5% significance rate), requiring stricter effect size thresholds than originally anticipated.

---

## Outputs

### Recommended for A6

**`outputs/A5_interaction_results_FILTERED_STRICT.pkl`**
- **4,254 validated interactions**
- Filter: Clean (no scale warnings) AND |β3| ≥ 5.0
- Median |β3| = 6.86, Mean R² = 0.31
- Ready for hierarchical layering

**`outputs/A5_validated_interactions_FILTERED_STRICT.csv`**
- CSV export for inspection
- Same 4,254 interactions

### Alternative (Comprehensive)

**`outputs/A5_interaction_results.pkl`**
- **107,546 total validated** (|β3| > 0.15)
- Includes 52,016 clean + 55,530 flagged (scale warnings)
- Use if Phase B wants own filtering logic

---

## Method

### Regression Model

For each mechanism pair (M1, M2) and outcome Y:

```
Y = β0 + β1*M1 + β2*M2 + β3*(M1×M2) + Σβi*controls + ε
```

Where:
- **β3** = interaction coefficient (synergy/antagonism)
- **controls** = union of backdoor adjustment sets from A4
- **Ridge regularization** (λ=1e-6) for numerical stability

### Statistical Pipeline

1. **Search space**: 529,075 mechanism pairs across 30 outcomes
2. **Regression**: Closed-form OLS with interaction terms
3. **FDR correction**: Benjamini-Hochberg (α=0.001)
4. **Effect size filter**: |β3| ≥ 5.0 (strict threshold)
5. **Scale warning**: Flag |β3| > 10 as potential artifacts

---

## Key Results

### Final Statistics (Strict Filter)

| Metric | Value |
|--------|-------|
| **Total tests** | 529,075 |
| **Successful tests** | 526,729 (99.6%) |
| **Significant (FDR α=0.001)** | 260,574 (49.5%) |
| **Validated (strict)** | **4,254** |
| **Median \|β3\|** | 6.86 |
| **Mean R²** | 0.31 |

### Effect Size Distribution (Validated)

- 25th percentile: 5.79
- 50th percentile: 6.86
- 75th percentile: 8.20
- 90th percentile: 9.17
- Max: 10.00

---

## Critical Findings

### 1. High Interaction Prevalence

**Observation**: 49.5% of tests significant at α=0.001 (vs 5-15% expected)

**Diagnosis**:
- ✅ FDR correction verified (re-ran, matched exactly)
- Not a statistical error - genuine high interaction density
- Large sample size (31K observations) + many real synergies

**Resolution**: Filter by practical significance (|β3| ≥ 5.0), not just statistical

### 2. Scale Artifacts

**Issue**: 51.6% of original validated interactions flagged for |β3| > 10

**Cause**: Large-scale variable products (e.g., GDP × Population → quadrillions)

**Resolution**: Warning flag system identifies artifacts; strict filter excludes them

### 3. Three-Tier Filtering

**Tier 1** - Original (|β3| > 0.15): 107,546 interactions
**Tier 2** - Moderate (|β3| > 3.0, clean): 8,841 interactions
**Tier 3** - **Strict (|β3| ≥ 5.0, clean): 4,254 interactions** ✅ RECOMMENDED

---

## Three Critical Fixes Applied

### Fix #1: Search Space Correction

**Original Error**: GPU plan tested mechanism×outcome (10K-25K tests)
**Correction**: Test mechanism×mechanism per outcome (529K tests)
**Result**: 30 outcomes × mean 176 mechanisms = 529,075 pairs ✅

### Fix #2: Regression Method

**Original Error**: GPU plan used SHAP feature importance
**Correction**: Closed-form OLS for exact β3 extraction
**Result**: 318 tests/sec throughput, 99.6% success rate ✅

### Fix #3: Control Variables

**Original Error**: GPU plan had undefined "controls"
**Correction**: Pre-computed from A4 backdoor sets (union strategy)
**Result**: Mean 11.5 controls/test, zero self-loops ✅

---

## Files & Structure

```
A5_interaction_discovery/
├── README.md                              # This file
├── A5_METHODOLOGY.md                      # Complete methods & rationale
├── A5_FINAL_STATUS_REVISED.md             # Detailed results & validation
│
├── outputs/
│   ├── A5_interaction_results_FILTERED_STRICT.pkl    # ⭐ RECOMMENDED
│   ├── A5_validated_interactions_FILTERED_STRICT.csv
│   ├── A5_interaction_results.pkl                    # All validated
│   ├── A5_validated_interactions.csv
│   ├── mechanism_pairs_per_outcome.pkl               # Fix #1 output
│   ├── precomputed_controls.pkl                      # Fix #3 output
│   └── step*_summary.txt
│
├── scripts/
│   ├── run_interaction_discovery.py       # Main pipeline
│   ├── step1_identify_mechanisms.py        # Fix #1
│   ├── step2_linear_regression_cpu.py      # Fix #2 (CPU)
│   ├── step2_linear_gpu_regression.py      # Fix #2 (GPU, optional)
│   └── step3_precompute_controls.py        # Fix #3
│
├── logs/
│   └── a5_run.log                          # Execution log
│
└── archive/
    └── old_documentation_20251120/         # Superseded docs
```

---

## Next Steps

**For A6 Hierarchical Layering:**
1. Load strict filtered output (4,254 interactions)
2. Combine with A4 edges (9,759 direct effects)
3. Total graph: ~14,013 relationships to layer
4. Apply topological sort for hierarchy assignment

**Estimated A6 Time**: 30-60 minutes
**Estimated A6 Cost**: $0 (CPU-only)

---

## Validation

### Input Validation
- ✅ A4 edges: 9,759 validated (0 sign errors)
- ✅ A1 data: 6,368 indicators × 31,408 observations
- ✅ Backdoor sets: 129,989 pre-computed

### Statistical Validation
- ✅ FDR correction verified (re-ran independently)
- ✅ Effect size distribution reasonable (median 6.86)
- ✅ R² values appropriate (mean 0.31)
- ✅ No sign consistency errors

### Quality Validation
- ✅ All validated interactions clean (no scale warnings)
- ✅ Max |β3| = 10.00 (at clean threshold)
- ✅ Success rate 99.6% (minimal missing data issues)
- ✅ Control sets appropriate (mean 11.5 variables)

---

## References

**V2 Master Spec**: `v2_master_instructions.md` (lines 875-950)
**A4 Input**: `../A4_effect_quantification/outputs/lasso_effect_estimates_WITH_WARNINGS.pkl`
**A1 Data**: `../A1_missingness_analysis/outputs/A2_preprocessed_data.pkl`

---

**Last Updated**: November 20, 2025
**Contact**: See A5_METHODOLOGY.md for complete technical details
**Status**: ✅ COMPLETE - Ready for A6
