# V1 Lessons Learned & Validated Methods

**Source**: V1 Transfer Package (November 11, 2025)
**Status**: ✅ Integrated into V2 pipeline

---

## Executive Summary

V1 agent provided a transfer package with **3 validated utilities**, **5 data collection scripts**, and **8 critical lessons**. All Python code is safe to reuse; only timing differs between V1 (top-down, 8 pre-selected metrics) and V2 (bottom-up, 12-20 discovered factors).

**Key Insight**: V1's utilities are architecturally neutral functions - they don't care about V1 vs V2 approach. We just need to know WHEN to call them in V2's pipeline.

---

## ✅ Validated Utilities (REUSE EXACTLY)

### 1. Saturation Transforms
**File**: `shared_utilities/data_processing/saturation_transforms.py`
**Evidence**: +5.6% mean R² improvement in V1
**V2 Application**: After B1 factor analysis (not A0)

**Functions**:
- `saturate_life_expectancy()` - Cap at 85 years
- `saturate_gdp_per_capita()` - Log transform above $20K
- `saturate_infant_mortality()` - Invert-cap at 100/1000
- `saturate_undernourishment()` - Invert-cap at 50%
- `saturate_homicide()` - Invert-cap at 50/100K

**⚠️ V2 TIMING CRITICAL**:
- V1: Applied at Phase 0 (knew which 8 were deficiency needs)
- V2: Apply at B1 (after factor analysis discovers which are deficiency needs)
- DON'T saturate at A0 - we don't know which variables are outcomes yet

---

### 2. Imputation Weighting
**File**: `shared_utilities/data_processing/imputation_weighting.py`
**Evidence**: +0.92pp mean R² improvement, 8/8 metrics improved
**V2 Application**: A2 (SHAP downweighting), A4 (effect downweighting), B1 (factor validation)

**Tier Weights** (VALIDATED - DO NOT CHANGE):
```python
Tier 1 (Observed): 1.0
Tier 2 (Linear Interpolation/KNN): 0.85
Tier 3 (MICE <40% missing): 0.70
Tier 4 (MICE >40% missing): 0.50
```

**V2 Integration Points**:
1. A2: Downweight Granger test statistics by observed rate
2. A4: Downweight backdoor coefficients by observed rate
3. B1: Reject factors if top variables <80% observed

---

### 3. Backdoor Adjustment
**File**: `shared_utilities/causal_methods/backdoor_adjustment.py`
**Evidence**: 51/80 edges significant (63.7%), stable under 1000 bootstrap iterations
**V2 Application**: A4 effect quantification

**Parameters** (VALIDATED):
- `n_bootstrap = 1000` (use 100 for intermediate steps due to V2 scale)
- Significance: CI doesn't cross zero
- Alpha: 0.05 (two-tailed)

**V2 Scaling Note**:
- V1: 1000 iterations × 80 edges = 80K fits (30 min)
- V2: 1000 iterations × 2K-8K edges = 2M-8M fits (hours)
- Solution: Use n_bootstrap=100 for A4, n_bootstrap=1000 for final validation

---

## ❌ Critical Failures to Avoid (8 Mistakes)

### 1. NEVER Normalize Before Saturation
**V1 Mistake**: Early experiments normalized first
**Result**: Destroyed saturation curves, wrong functional forms
**V2 Rule**: ALWAYS `saturate(raw) → normalize(saturated)`

**Detection**:
```python
if 'normalized' in df.columns and not 'saturated' in df.columns:
    raise ValueError("❌ Must saturate before normalizing!")
```

---

### 2. NEVER Use Global Coverage for Panel Data
**V1 Mistake**: Phase 2.0 used `(1 - missing_rate) >= 0.40` globally
**Result**: 80-94% sample dropout
**V2 Rule**: 80% per-country temporal coverage

**Right Logic**:
```python
country_coverage = df.groupby('country')['value'].apply(
    lambda x: 1 - x.isna().mean()
)
if country_coverage.mean() >= 0.80:
    keep_variable()
```

---

### 3. NEVER Apply Domain-Balanced Selection
**V1 Mistake**: Forced 20 features per domain
**Result**: 0/8 metrics improved, many regressed
**V2 Rule**: Pure statistical selection, domain tagging post-hoc

---

### 4. NEVER Use Neural Networks for n<5K
**V1 Mistake**: Applied DNNs to n=3,742 samples
**Result**: Val R² = -2.35 (catastrophic overfitting)
**V2 Rule**: LightGBM/XGBoost for n<5K, reserve NNs for n>50K

---

### 5. NEVER Exclude Disaggregations as "Autocorrelation"
**V1 Mistake**: Excluded `male_life_expectancy` as autocorrelated with `life_expectancy`
**Result**: Lost 87.5% of drivers (14 → 2 features)
**V2 Rule**: Only exclude self-lagged (e.g., `life_expectancy_lag1`)

**Right Logic**:
```python
def is_autocorrelation(driver, target):
    # WRONG
    if target in driver:  # ❌ Too broad
        return True

    # RIGHT
    if f"{target}_lag" in driver:  # ✅ Only self-lagged
        return True
    return False  # Keep disaggregations
```

---

### 6-8. Additional Warnings
- ❌ Imputation without weighting (V1 fixed with tier system)
- ❌ Granger testing all pairs (V2 MUST implement 5-stage prefiltering)
- ❌ PC-Stable on dense graphs (V2 early stopping: switch to GES if >50K edges)

---

## 📊 V1 Performance Benchmarks (V2 Targets)

| Metric | V1 Val R² | V2 Target | Notes |
|--------|-----------|-----------|-------|
| Mean Years Schooling | 0.9244 | >0.90 | V1 best metric |
| Infant Mortality | 0.9072 | >0.85 | V1 strong |
| Undernourishment | 0.8057 | >0.75 | Improved via temporal features |
| GDP per Capita | 0.7785 | >0.70 | V1 stable |
| Gini | 0.6999 | >0.60 | V1 challenging |
| Internet Users | 0.6887 | >0.60 | V1 challenging |
| Life Expectancy | 0.6633 | >0.60 | Weak generalization |
| Homicide | 0.3577 | >0.35 | V1 worst metric |

**V2 Success Criteria**:
- At least 8 of 12-20 discovered factors meet R² > 0.55 (match V1's 8/8 rate)
- Mean factor R² ≥ V1's mean outcome R² (0.73)

**Causal Validation Targets**:
- Bootstrap stability: >75% edge retention
- Backdoor significant edges: >60%
- Holdout R²: >0.55 mean
- Literature reproduction: >70% (NEW in V2)

---

## 🔄 V1↔V2 Phase Mapping

| V1 Phase | V1 Output | V2 Phase(s) | V2 Output | Reusable? |
|----------|-----------|-------------|-----------|-----------|
| Phase 0 (Extract) | 5,340 indicators | A0 | 9,350 indicators | ✅ Scrapers + 6 new |
| Phase 1 (Filter) | 2,480 variables | A0 | 4,000-5,000 variables | ✅ 80% per-country logic |
| Phase 1 (Lags) | T-1,T-2,T-3,T-5 | A2 | In Granger tests | ⚠️ Concept, different use |
| Phase 2 (Select) | 558 features | A2 | 200K candidate pairs | ❌ Different approach |
| Phase 3 (Train) | 8 LightGBM models | B1 | 12-20 factor scores | ❌ Different method |
| Phase 4 (Causal) | 162 nodes, 204 edges | A3-A6 | 2K-8K nodes, edges | ⚠️ Backdoor reusable |

---

## ⚠️ Critical Architecture Differences

### Scale: V2 is 10-50× Larger Than V1

| Dimension | V1 | V2 | Ratio |
|-----------|----|----|-------|
| Input Variables | 5,340 → 2,480 | 9,350 → 4,000-5,000 | 1.6-2.0× |
| Outcomes | 8 pre-selected | 12-20 discovered | 1.5-2.5× |
| Graph Nodes | 162 | 2,000-8,000 | 12-50× |
| Graph Edges | 204 | 2,000-8,000 | 10-40× |
| Granger Tests | 56 pairs | 200,000 pairs | 3,571× |

### Approach: V2 Discovers What V1 Assumed

| Aspect | V1 | V2 |
|--------|----|----|
| **Outcomes** | Pre-selected by experts | Discovered via factor analysis (B1) |
| **Saturation** | Applied at Phase 0 | Applied at B1 (after discovery) |
| **Models** | End product (deployable) | Validation tool (factor R² check) |
| **Graph** | Small by design (162) | Large by necessity (2K-8K) |

---

## 📁 V1 Utilities Location in V2

```
v2.0/
├── shared_utilities/
│   ├── data_processing/
│   │   ├── saturation_transforms.py        ✅ Copied from V1
│   │   └── imputation_weighting.py         ✅ Copied from V1
│   ├── causal_methods/
│   │   └── backdoor_adjustment.py          ✅ Copied from V1
│   └── README.md                            📝 To create
│
├── phaseA/A0_data_acquisition/
│   ├── world_bank_wdi.py                    ✅ Copied from V1
│   ├── who_gho.py                           ✅ Copied from V1
│   ├── unesco_uis.py                        ✅ Copied from V1
│   ├── imf_ifs.py                           ✅ Copied from V1
│   ├── unicef.py                            ✅ Copied from V1
│   └── [6 NEW: vdem, qog, oecd, pwt, wid, transparency]  📝 To write
```

---

## 🚀 V2 Integration Checklist

### Week 0-1: Setup & Data Collection
- [x] Copy saturation_transforms.py
- [x] Copy imputation_weighting.py
- [x] Copy backdoor_adjustment.py
- [x] Copy 5 V1 data scrapers
- [ ] Write 6 new data scrapers (V-Dem, QoG, OECD, Penn, WID, Transparency)
- [ ] Test all 11 scrapers (expect 20-28 hours runtime)

### Week 2-4: Phase A (Statistical Discovery)
- [ ] A0: Apply V1 coverage filter (80% per-country)
- [ ] A1: Select optimal imputation config (25 parallel)
- [ ] A2: Apply V1 imputation weighting (tier system)
- [ ] A2: Implement Granger prefiltering (6.2M → 200K)
- [ ] A4: Apply V1 backdoor adjustment (n_bootstrap=100)
- [ ] **DON'T** apply saturation yet (wait for B1)

### Week 5: Phase B (Interpretability)
- [ ] B1: Factor analysis discovers 12-20 outcomes
- [ ] B1: **NOW** apply V1 saturation transforms (to identified deficiency factors)
- [ ] B1: Validate factors using V1 R² thresholds
- [ ] B1: Reproduce ≥6 of V1's 8 outcomes (validation anchor)
- [ ] B4: Multi-level pruning with SHAP validation (>85%)

---

## 🎯 Key Takeaways

### What V1 Taught Us

1. **Saturation transforms are CRITICAL** (+5.6% R²) but timing matters
2. **Imputation weighting prevents false signal** (+0.92pp R²)
3. **Per-country coverage is non-negotiable** (5× sample increase)
4. **Domain balancing destroys causal signal** (0/8 metrics improved)
5. **Disaggregations are valid drivers** (only exclude self-lagged)

### What V2 Must Add

1. **Granger prefiltering** (5-stage, reduces 6.2M → 200K tests)
2. **Factor validation** (3-part: domain, literature, R² > 0.40)
3. **Multi-level pruning** (3 graphs: full, professional, simplified)
4. **Literature reproduction test** (>70% target, NEW validation)

### What V2 Agents Must Remember

1. ⚠️ V2 is 10-50× larger than V1 (scale matters)
2. ⚠️ V2 discovers what V1 assumed (different approach)
3. ⚠️ V2 saturation at B1, not A0 (timing critical)
4. ⚠️ V2 models for validation, not deployment (different purpose)
5. ✅ V1 utilities are safe to reuse (architecturally neutral)

---

## 📖 References

- **V1 Transfer Package**: `/v2_transfer_package/` (archived, not deleted per safety audit)
- **V1 Failures**: 8 critical mistakes documented
- **V1 Successes**: 5 validated approaches documented
- **Safety Audit**: All Python code verified safe, only docs needed clarification

---

**Last Updated**: November 11, 2025
**Integration Status**: ✅ Utilities copied, lessons documented
**Next Step**: Write 6 new data scrapers for A0
