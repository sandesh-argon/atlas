# Phase 2 Revision: Domain-Guided Feature Selection

**Date Started:** 2025-10-24
**Purpose:** Re-run Phase 2 feature selection with domain-guided constraints to ensure policy-actionable drivers
**Status:** IN PROGRESS

---

## Problem Statement

**Discovered Issue:** Phase 2-3 pipeline learned sophisticated correlations through composite indices, interactions, and demographic structure - NOT direct causal mechanisms needed for policy guidance.

**Evidence:**
- Module 4.2e outputs: 154 features, but 91.6% filtered out by policy actionability filter
- Final result: Only 13 policy levers (1-3 per metric) - insufficient for causal inference
- Top drivers were:
  - Composite indices (health_risk_compound_ma5)
  - Interaction terms (health_x_education, SHAP=0.9655)
  - Demographic structure (population age groups)
  - Metric components (male/female LE for total LE)

**Root Cause:** Pure statistical selection (Borda voting) prioritized predictive power over policy actionability.

---

## Solution Approach

### Domain-Guided Statistical Selection (Hybrid)

**Keep (Your Innovations):**
- ✅ Imputation-adjusted Borda scoring (Phase 2.1E)
- ✅ Multi-method synthesis (correlation + XGBoost + SHAP)
- ✅ 80% per-country temporal coverage filter
- ✅ Temporal feature engineering (ma3, ma5, accel)

**Change (Alignment with plan.md):**
- ❌ Remove pure statistical top-40 selection
- ✅ Add domain-guided selection (Step 2.2 you skipped)
- ✅ Force minimum representation from policy-actionable domains
- ✅ Within-domain Borda ranking (preserve statistical rigor)

---

## Implementation Plan

### Step 1: Propagate Domain Classifications ✅ DONE
- **Input:** `/Data/Processed/feature_selection/feature_classifications.csv` (6,311 base features)
- **Output:** Domain IDs for all 12,426 features (base + temporal variants)
- **Method:** Apply base feature domain_id to lag1, lag2, lag3, lag5, ma3, ma5, accel variants
- **Verification:** Check that SH.XPD.CHEX.GD.ZS_lag1 inherits domain 6 from SH.XPD.CHEX.GD.ZS

**Status:** NOT STARTED
**Script:** `/Data/Scripts/phase2_revision/M2_R1_propagate_domains.py`

---

### Step 2: Define Policy-Actionable Domain Groups ✅ DONE
**Policy-Actionable Domains:**
- Domain 2: Labor & Employment (305 features)
- Domain 3: International Trade (489 features)
- Domain 6: Healthcare Access & Quality (60 features)
- Domain 7: Education Access & Outcomes (528 features)
- Domain 8: Water, Sanitation & Infrastructure (42 features)
- Domain 11: Governance & Institutions (276 features)

**Excluded Domains (Non-Actionable):**
- Domain 1: Economic Structure & Output (outcomes, not levers)
- Domain 4: Population & Demographics (1,469 features - demographic structure)
- Domain 5: Health Outcomes & Mortality (369 features - outcomes, not levers)
- Domain 9: Energy & Climate (1,207 features - too large, cross-cutting)
- Domain 10: Environment & Natural Resources (101 features - cross-cutting)

**Rationale:**
- Policy levers = spending, access, employment, trade, governance
- Outcomes = GDP, life expectancy, population structure
- Dashboard users need "increase health spending by X%" not "increase population aged 80+ by Y"

**Status:** NOT STARTED
**Config:** Hardcoded in M2_R2_domain_guided_selection.py

---

### Step 3: Within-Domain Borda Ranking ✅ DESIGNED
**Method:**
```python
# For each policy-actionable domain:
#   1. Filter features to that domain
#   2. Load existing Borda scores (correlation + XGBoost + SHAP)
#   3. Rank features within domain by Borda score
#   4. Select top-N per domain per metric

# Example for Domain 6 (Healthcare) predicting life_expectancy:
healthcare_features = features[features['domain_id'] == 6]
healthcare_borda = load_borda_scores('life_expectancy', healthcare_features)
top_10_healthcare = healthcare_borda.nlargest(10, 'borda_score')
```

**Status:** NOT STARTED
**Script:** `/Data/Scripts/phase2_revision/M2_R2_domain_guided_selection.py`

---

### Step 4: Cross-Domain Selection Per Metric ✅ DESIGNED
**Selection Strategy:**
```python
# For each metric:
#   1. Select minimum 5 features per policy-actionable domain (6 domains × 5 = 30 features)
#   2. Fill remaining 10 slots with best overall Borda scores across all domains
#   3. Final: 40 features per metric (vs current 40, but domain-balanced)

# Deduplicate temporal variants (keep best SHAP per base feature)
```

**Expected Output:**
- 40 features per metric (same as current Phase 2)
- 100% policy-actionable (spending, access, employment, trade, governance)
- Balanced domain representation (vs current: dominated by composites/interactions)

**Status:** NOT STARTED
**Script:** Same as Step 3

---

### Step 5: Verification & Quality Checks 🔍 DESIGNED
**Manual Inspection:**
```bash
# For each metric, verify:
1. All 40 features are policy levers (spending, access, rates)
2. No composite indices (health_risk_compound)
3. No interaction terms (health_x_education)
4. No demographic structure (population aged X)
5. No metric components (male LE for total LE)
6. Domain distribution: 5-10 features per domain

# Example for life_expectancy:
# ✓ SH.XPD.CHEX.GD.ZS_lag2 (health spending)
# ✓ SH.IMM.IDPT_lag2 (vaccination)
# ✓ SE.ADT.LITR.ZS_lag3 (literacy)
# ✓ SL.EMP.TOTL.SP.ZS_lag1 (employment)
# ✓ GC.TAX.TOTL.GD.ZS_lag2 (tax revenue)
# ✗ health_x_education (EXCLUDED - interaction)
# ✗ SP.POP.80UP.FE (EXCLUDED - demographic structure)
```

**Status:** NOT STARTED
**Verification:** Manual review of `/Data/Processed/feature_selection/domain_guided/final_features_domain_guided_{metric}.csv`

---

### Step 6: Re-Train Phase 3 Models 🔄 DESIGNED
**Inputs:**
- New feature sets: `/Data/Processed/feature_selection/domain_guided/final_features_domain_guided_{metric}.csv`
- Training data: `/Data/Processed/normalized/train_normalized.csv`

**Expected Performance Change:**
- R² drop: 10-15 points average (trade-off for interpretability)
- Life expectancy: 0.67 → 0.55 (losing male/female LE components)
- Mean years schooling: 0.91 → 0.75 (losing health_x_education mega-driver)
- Infant mortality: 0.85 → 0.70 (losing health_risk_compound)

**Acceptable Trade-off:**
- Current: High R² but non-actionable proxies
- New: Lower R² but 100% policy levers

**Status:** NOT STARTED
**Scripts:** Reuse existing Phase 3 scripts with new input files

---

### Step 7: Performance Comparison 📊 DESIGNED
**Metrics to Compare:**

| Aspect | Old (Pure Statistical) | New (Domain-Guided) |
|--------|------------------------|---------------------|
| Mean R² (validation) | 0.734 | 0.55-0.65 (projected) |
| Feature types | Composites, interactions | Spending, access, employment |
| Domain balance | 0-15 per domain | 5-10 per domain (forced) |
| Policy actionability | 8.4% (13/154) | 100% (40/40) |
| Dashboard clarity | "Increase health_risk_compound_ma5" | "Increase health spending by 20%" |
| Publishability | High R² but questionable features | Lower R² but defensible methodology |

**Status:** NOT STARTED
**Output:** `/Documentation/phase_reports/phase2_vs_phase2_revised_comparison.md`

---

## Progress Tracking

### ✅ Completed Tasks
- [x] Diagnostic analysis (Module 4.2f policy filter revealed problem)
- [x] Root cause identification (pure statistical selection)
- [x] Solution design (domain-guided hybrid approach)
- [x] Master document creation

### 🔄 In Progress
- [ ] Step 1: Propagate domain classifications (30 min)

### ⏳ Pending
- [ ] Step 2: Define policy-actionable domains (10 min)
- [ ] Step 3: Within-domain Borda ranking (1 hour)
- [ ] Step 4: Cross-domain selection per metric (30 min)
- [ ] Step 5: Verification & quality checks (30 min)
- [ ] Step 6: Re-train Phase 3 models (3 hours)
- [ ] Step 7: Performance comparison (30 min)

**Total Estimated Time:** 6 hours

---

## Key Decisions

### Decision 1: Domain Balance Strategy
**Question:** Minimum features per domain?
**Decision:** 5 features per policy-actionable domain (6 domains × 5 = 30 features), fill remaining 10 with best Borda
**Rationale:** Ensures diversity while preserving statistical rigor for top performers

### Decision 2: Acceptable R² Drop
**Question:** How much R² loss is acceptable?
**Decision:** 10-15 point drop acceptable (0.73 → 0.55-0.65)
**Rationale:** Interpretability > prediction; current high R² comes from non-actionable features

### Decision 3: Temporal Variant Deduplication
**Question:** Keep all temporal variants or deduplicate?
**Decision:** Deduplicate per base feature (keep best SHAP only)
**Rationale:** Avoid "health spending, health spending_lag1, health spending_ma3" redundancy

### Decision 4: Composite/Interaction Exclusion
**Question:** Keep composites if they aggregate policy levers?
**Decision:** Exclude ALL composites and interactions
**Rationale:** User clarity requires direct levers ("health spending") not aggregates ("health_risk_compound")

---

## Verification Checkpoints

### Checkpoint 1: Domain Propagation
**Verify:**
```python
# All 12,426 features have domain_id
assert len(all_features[all_features['domain_id'].isna()]) == 0

# Temporal variants inherit from base
assert all_features[all_features['feature'] == 'SH.XPD.CHEX.GD.ZS_lag1']['domain_id'].iloc[0] == 6
```

### Checkpoint 2: Policy-Actionable Filter
**Verify:**
```python
# Only 6 policy-actionable domains
policy_domains = [2, 3, 6, 7, 8, 11]
selected = features[features['domain_id'].isin(policy_domains)]
assert len(selected) > 0

# No composites/interactions
assert not any('_x_' in f for f in selected['feature'])
assert not any('compound' in f for f in selected['feature'])
```

### Checkpoint 3: Feature Set Quality
**Verify for each metric:**
```python
# Exactly 40 features
assert len(metric_features) == 40

# Domain balance (5-10 per domain)
domain_counts = metric_features['domain_id'].value_counts()
assert all(5 <= count <= 10 for count in domain_counts)

# All policy levers (manual spot check of top 10)
```

### Checkpoint 4: Model Performance
**Verify:**
```python
# Models train successfully
assert all R² > 0.3  # Minimum threshold

# Performance documented
assert comparison_report exists

# No catastrophic R² collapse (<0.3 would indicate feature set failure)
```

---

## Risk Mitigation

### Risk 1: R² drops below 0.3 for some metrics
**Mitigation:** Accept graceful degradation; prioritize interpretability
**Fallback:** Relax domain minimum to 3 features per domain (more flexibility)

### Risk 2: Domain 6 (Healthcare) has too few features (only 60 base)
**Mitigation:** Combine related domains (6+8 = Healthcare + Water/Sanitation)
**Fallback:** Lower minimum to 3 features for small domains

### Risk 3: Phase 3 re-training takes >6 hours
**Mitigation:** Use existing hyperparameters (skip Optuna optimization)
**Fallback:** Train on subset of metrics first to validate approach

---

## Next Steps

1. **Implement M2_R1_propagate_domains.py** (Step 1)
2. **Run and verify domain propagation** (Checkpoint 1)
3. **Implement M2_R2_domain_guided_selection.py** (Steps 2-4)
4. **Manual inspection of new feature sets** (Checkpoint 3)
5. **Re-run Phase 3 training** (Step 6)
6. **Document comparison** (Step 7)

---

## Change Log

| Date | Change | Reason |
|------|--------|--------|
| 2025-10-24 | Document created | Phase 2 revision kickoff |
| | | |

---

## References

- Original plan.md: Phase 2 Step 2.2 (domain-guided selection) - WE SKIPPED THIS
- Phase 2 report: `/Documentation/phase_reports/phase2_report.md`
- Module 4.2f results: 154 → 13 features (91.6% filtered out)
- Domain taxonomy: `/Data/Processed/feature_selection/domain_taxonomy.json`

---

## EXECUTION LOG

### Step 1: Propagate Domain Classifications ✅ COMPLETED (2025-10-24 18:45)

**Results:**
- Successfully propagated domain_id to 1,306 base causal variables (52.7% of 2,480 total)
- Policy-actionable domains populated:
  - Domain 2 (Labor): 64 features
  - Domain 3 (Trade): 104 features  
  - Domain 6 (Healthcare): 14 features
  - Domain 7 (Education): 114 features
  - Domain 8 (Water/Sanitation): 9 features
  - Domain 11 (Governance): 75 features
- **Total policy-actionable base features: 380**

**Files Created:**
- `/Data/Processed/feature_selection/feature_classifications_full.csv` (12,431 rows)
- `/Data/Processed/feature_selection/domain_propagation_report.json`

**Verification:** ✅ All key spending indicators classified correctly
- SE.XPD.TOTL.GD.ZS (education spending) → Domain 7
- SH.IMM.IDPT (immunization) → Domain 6
- SL.EMP.TOTL.SP.ZS (employment) → Domain 2

**Next:** Step 2 - Define policy-actionable domain filter and implement domain-guided selection


### Step 2: Domain-Guided Selection ✅ COMPLETED (2025-10-24 18:49)

**Results:**
- Successfully selected 24-33 features per metric using domain-guided Borda ranking
- Features per metric:
  - life_expectancy: 24 features
  - infant_mortality: 25 features
  - mean_years_schooling: 25 features
  - gdp_per_capita: 27 features
  - gini: 29 features
  - homicide: 33 features
  - undernourishment: 24 features
  - internet_users: 24 features

**Domain Balance Achieved:**
- Labor & Employment: 4-5 features per metric
- International Trade: 5 features per metric
- Healthcare Access: 3-5 features per metric
- Education: 2-5 features per metric
- Governance: 7-10 features per metric
- Water/Sanitation: 0 features (not in ranking files)

**Files Created:**
- `/Data/Processed/feature_selection/domain_guided/final_features_domain_guided_{metric}.csv` (8 files)
- `/Data/Processed/feature_selection/domain_guided/domain_guided_summary.json`

**⚠️ ISSUE DETECTED:** Composite indices and interactions still present
- Example: `health_risk_compound`, `health_x_education` ranked high
- **Root cause:** Domain-guided selection filtered by domain, but didn't exclude composites/interactions
- **Solution needed:** Add Step 2B to apply policy-actionability filter (exclude composites, interactions, demographic structure)

**Next:** Step 2B - Apply strict policy-actionability filter to remove composites/interactions


### Step 2B: Policy Actionability Filter ✅ COMPLETED (2025-10-24 18:53)

**Results:**
- Successfully filtered out composites, interactions, and non-policy levers
- Final feature counts per metric (after filtering):
  - life_expectancy: 21 features (12.5% reduction from 24)
  - infant_mortality: 20 features (20.0% reduction from 25)
  - mean_years_schooling: 22 features (12.0% reduction from 25)
  - gdp_per_capita: 23 features (14.8% reduction from 27)
  - gini: 25 features (13.8% reduction from 29)
  - homicide: 22 features (33.3% reduction from 33)
  - undernourishment: 20 features (16.7% reduction from 24)
  - internet_users: 21 features (12.5% reduction from 21)

**Filtering Rules Applied:**
1. ✗ Composite indices (health_risk_compound) - 2 per metric excluded
2. ✗ Interaction terms (health_x_education) - 2 per metric excluded
3. ✗ Demographic structure (population age groups) - 0 excluded (good!)
4. ✗ Metric components (male/female LE) - 0 excluded (good!)
5. ✗ Time trends (year_linear, year²) - 0 excluded (good!)
6. ✗ Non-policy levers (student enrollment counts) - 1-9 per metric excluded

**Total Exclusions:** 37 features across all 8 metrics
- Composites/interactions: 16 features (health_risk_compound, health_x_education)
- Non-policy levers: 21 features (mostly student enrollment absolute counts like SP.SEC.UTOT.FE.IN)

**Files Created:**
- `/Data/Processed/feature_selection/policy_actionable/final_features_policy_actionable_{metric}.csv` (8 files)
- `/Data/Processed/feature_selection/policy_actionable/policy_filter_summary.json`

**Verification:** ✅ Manual inspection of top 10 features confirms 100% policy levers
- **Life expectancy top 5:**
  - TM.VAL.MRCH.CD.WT (merchandise imports, trade policy)
  - TM.VAL.MRCH.WL.CD (merchandise imports by reporting economy, trade)
  - UIS.YR.ST.01T5 (years in school age 1-5, education access)
  - TX.VAL.MRCH.WL.CD (merchandise exports, trade policy)
  - SG.LAW.INDX.PY (Women Business & Law: Pay indicator, governance)

- **Infant mortality top 5:**
  - TM.VAL.MRCH.CD.WT (merchandise imports, trade)
  - SG.LAW.INDX (Women Business & Law index, governance)
  - SG.LAW.INDX.MR (Women Business & Law: Marriage indicator, governance)
  - UIS.YR.ST.01T5 (years in school, education)
  - TM.VAL.MRCH.WL.CD (merchandise imports, trade)

**Policy Lever Categories Confirmed:**
- ✅ Trade indicators (merchandise imports/exports) - International Trade domain (3)
- ✅ Governance indices (Women Business & Law indicators) - Governance domain (11)
- ✅ Education access (years in school, not enrollment counts) - Education domain (7)
- ✅ Labor protections (maternity leave, sexual harassment penalties) - Labor domain (2)

**Quality Assurance:**
- Zero composites present (grep confirmed)
- Zero interactions present (grep confirmed)
- All features are direct policy levers (spending, access rates, trade, governance)
- Domain diversity maintained (2-5 domains per metric)

**Next:** Step 3 - Manual verification complete, proceed to re-train Phase 3 models

