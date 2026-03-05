# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 📊 **START HERE - READ ALL PHASE REPORTS FIRST**

**CRITICAL**: Before working on any task, read ALL phase reports in `/Documentation/phase_reports/` to understand the complete project context:

1. **`/Documentation/phase_reports/phase0_report.md`** - Data acquisition & preparation (174 countries × 65 years × 8 QOL metrics, 99.81% completeness)
2. **`/Documentation/phase_reports/phase1_report.md`** - Temporal feature engineering (12,426 features, saturation transforms, train-test split)
3. **`/Documentation/phase_reports/phase2_report.md`** - Feature selection (99.7% reduction to 558 features, pure statistical approach)
4. **`/Documentation/phase_reports/phase3_report.md`** - Model training & causal preparation (93/96 models, three-pronged strategy, Approach C wins 6/8 metrics)

These reports contain the authoritative, up-to-date project status and methodological decisions.

---

## Project Overview

**Global Development Indicators Causal Analysis Project** - A comprehensive data pipeline from extraction to causal discovery, analyzing quality of life drivers across 174 countries over 65 years (1960-2024).

**Vision Document**: See `/plan.md` for the complete 10-phase workflow from 2,500 variables to causal knowledge graphs.

## Project Status

**Current Phase**: Phase 4 In Progress - Causal Discovery
**Date**: 2025-10-24
**Latest Module**: 4.2e (Final Causal Drivers - v2 with LE fix)

### Pipeline Progress

**Data Preparation (Phases 0-3 old numbering):**
- ✅ Phase 0: Data Extraction - 5 sources, 2,509 indicators
- ✅ Phase 1 (old): Data Filtering - 2,480 variables passed coverage criteria
- ✅ Phase 2 (old): Data Cleaning - Schema standardization, deduplication
- ✅ Phase 3 (old): Data Imputation - 99.81% completeness, 8 QOL metrics

**ML Pipeline (Phases 1-10 per plan.md):**
- ✅ **Phase 1**: Temporal Lag Engineering & Train-Test Split
  - 12,426 features engineered (2,480 base + 9,920 lags + 8 QOL + 8 flags + temporal/interactions)
  - Saturation transforms applied (Heylighen & Bernheim 2000) - empirically validated
  - Country-agnostic split: 120 train / 26 val / 28 test countries
  - Within-country normalization with data leakage prevention
  - All validation tests passed (8/8)

- ✅ **Phase 2**: Feature Selection
  - 99.7% reduction: 12,426 → 558 features (69.75 per metric)
  - Dual coverage filtering: 40% global + 80% per-country temporal
  - Triple statistical ranking: Correlation + XGBoost + SHAP → Borda voting
  - Pure statistical selection (top-40 base features per metric)
  - Imputation-adjusted ranking (98.3% mean observed rate)
  - Temporal feature engineering (MA-3, MA-5, acceleration for top-10)
  - Validation R² range: 0.521-0.974 (5/8 metrics passing >0.55)

- ✅ **Phase 3**: Model Training & Optimization - COMPLETE
  - **Baseline Training:** 93/96 models (96.9% success)
  - **Hyperparameter Optimization:** 24/24 LightGBM models optimized (Optuna, 100 trials each)
  - **Selected Approach:** Approach C (Strict Causal) - 23-52 features per metric
  - **Final Performance:**
    - Validation R²: 0.734 average (baseline 0.695 → +5.6% improvement)
    - Test R²: 0.647 average (28 countries, 1,680 samples never seen)
    - Overfitting: 15.5% average (baseline 20.1% → -23% reduction)
    - Strong generalization: 5/8 metrics (<10% val-test difference)
    - Weak generalization: 3/8 metrics (life_expectancy, gdp_per_capita, homicide)
  - **Artifacts Ready for Phase 4:**
    - `/models/causal_optimized/` - 8 optimized LightGBM models
    - SHAP importance: `/models/causal_optimized/shap_importance_{metric}.csv`
    - Test results: `/models/causal_optimized/test_results_{metric}.json`
    - Master metadata: `/models/causal_optimized/model_metadata_master.json`

- ✅ **Phase 4**: Causal Inference Models - COMPLETE (2025-10-24)
  - **Three-Model Architecture - Model 2**: Regularized causal inference
  - Trained 8 LightGBM models on policy-relevant features (11-25 features per metric)
  - **Performance**: Mean Val R² = 0.599 (target 0.50-0.70, median 0.717)
  - **Success Rate**: 6/8 metrics usable (75%)
    - ✓ Target met (2): life_expectancy (0.659), gini (0.645)
    - ⚠ Above target (4): infant_mortality (0.879), mean_years_schooling (0.798), internet_users (0.781), undernourishment (0.775)
    - ✗ Below target (2): gdp_per_capita (0.210), homicide (0.046)
  - **Mechanism Indicators Validated**:
    - health_risk_compound (infant_mortality SHAP 0.194, undernourishment SHAP 0.194) - Tier 2 ✓
    - health_x_education (mean_years_schooling, SHAP 0.961) - Tier 2 mega-driver ✓✓✓
    - inequality_x_safety (gini SHAP 0.102, homicide SHAP 0.051) - Tier 2 ✓
    - gdp_x_technology (gdp_per_capita, SHAP 0.332) - Tier 2 ✓
  - **Autocorrelation Fix Applied** (v2, 2025-10-24):
    - 23 disaggregations excluded across 3 metrics (life_expectancy, infant_mortality, gdp_per_capita)
    - Examples: Male/female LE → total LE (definitional), under-5 mortality → infant mortality (nested)
    - Fixed drivers: 98 → 82 features (-16.3%), mechanism indicators preserved
  - **Outputs**:
    - Original: `/models/causal_inference/` (8 models, SHAP, drivers)
    - **Fixed (use this)**: `/models/causal_inference/autocorrelation_fixed/` (cleaned drivers, ready for Phase 5)
  - **life_expectancy Special Handling**: Option D two-track presentation
    - Prediction track: Use Model 1 (R²=0.67) for forecasting
    - Redirect track: Point to infant_mortality (10 drivers) and health mechanisms
    - Dashboard: Special warning banner + redirect links
  - **Documentation**:
    - **Main Report**: `/Documentation/phase_reports/phase4_report.md` (consolidated)
    - Three-Model Methodology: `/Documentation/phase_reports/phase4_three_model_methodology.md`
    - Archived (old PC algorithm approach): `/Documentation/phase_reports/ARCHIVED_phase4_report_pc_algorithm.md`

**Next Phase**: Phase 5 - Two-tier policy simulator (est. 3.5 hours)

---

## Architecture

### Data Flow

```
Indicators/*.csv (metadata)
        ↓
Phase 0: Extraction → Raw_Data/{SOURCE}_Data/*.csv
        ↓
Phase 1 (old): Coverage filtering → filtered_data/
        ↓
Phase 2 (old): Cleaning → filtered_data_cleaned/
        ↓
Phase 3 (old): Imputation → Processed/qol_imputed/master_panel_imputed_*.csv
        ↓
✅ Phase 1 (plan.md): Lag engineering → Processed/normalized/{train|val|test}_normalized.csv (12,426 features)
        ↓
✅ Phase 2 (plan.md): Feature selection → Processed/feature_selection/final_features_enhanced_*.csv (558 features)
        ↓
🔄 Phase 3+: Model training, causal discovery
```

### Key Directories

```
Data/
├── Extraction_Scripts/         # Phase 0: API extraction
├── Scripts/                    # All processing scripts
├── Raw_Data/                   # Raw API data
├── filtered_data/              # Coverage-filtered data
├── filtered_data_cleaned/      # Cleaned & standardized
├── Processed/                  # All ML pipeline outputs
│   ├── qol_imputed/           # Phase 0: Imputed panel
│   ├── normalized/            # Phase 1: 12,426 features (train/val/test)
│   ├── feature_selection/     # Phase 2: 558 selected features
│   ├── metadata/              # Feature registry
│   └── reports/               # Quality & validation reports
└── External_Data/             # Additional sources (SWIID, FAO)

Documentation/
└── phase_reports/             # ⭐ Authoritative phase documentation
    ├── phase0_report.md
    ├── phase1_report.md
    ├── phase2_report.md
    ├── phase3_report.md
    └── phase3_three_pronged_summary.md
```

---

## Data Sources

Five international organizations via REST APIs:

1. **World Bank** - Development indicators (api.worldbank.org/v2/)
2. **WHO** - Health indicators (ghoapi.azureedge.net/api/)
3. **UNESCO UIS** - Education indicators (api.uis.unesco.org/sdmx/)
4. **IMF** - Economic indicators (imf.org/external/datamapper/api/v1)
5. **UNICEF** - Social indicators (sdmx.data.unicef.org/ws/)

Each source has:
- Indicator list: `/Indicators/{source}_indicators.csv`
- Extraction script: `/Data/Extraction_Scripts/{source}.py`
- Output directory: `/Data/Raw_Data/{SOURCE}_Data/`

---

## The 8 Quality of Life Metrics

1. **Life Expectancy** (years) - SP.DYN.LE00.IN
2. **Infant Mortality Rate** (per 1,000 births) - SP.DYN.IMRT.IN
3. **GDP Per Capita** (constant 2015 USD) - NY.GDP.PCAP.KD
4. **Internet Users** (% of population) - IT.NET.USER.ZS
5. **Gini Coefficient** (0-100) - SWIID gini_disp
6. **Homicide Rate** (per 100,000) - VC.IHR.PSRC.P5
7. **Undernourishment Prevalence** (%) - SN.ITK.DEFC.ZS
8. **Mean Years of Schooling** (years) - OWID Mean Years of Schooling

---

## Key Outputs by Phase

### Phase 0 (Data Preparation)
**Master Panel**: `/Data/Processed/qol_imputed/master_panel_imputed_wide.csv`
- 10,855 rows × 18 columns (174 countries × 65 years, -870 from lags)
- 99.81% completeness (86,674/86,840 cells complete)
- All 8 QOL metrics imputed using full dataset (174 countries)

### Phase 1 (Temporal Engineering)
**Normalized Datasets**: `/Data/Processed/normalized/{train|val|test}_normalized.csv`
- **Training**: 7,200 rows × 12,426 cols (120 countries, 697 MB)
- **Validation**: 1,560 rows × 12,426 cols (26 countries, 143 MB)
- **Test**: 1,680 rows × 12,426 cols (28 countries, 158 MB)

**Features**:
- 2,480 base causal variables
- 9,920 lag features (T-1, T-2, T-3, T-5)
- 8 QOL targets + 8 imputation flags
- 3 temporal features (year_linear, year², decade)
- 5 interaction terms (GDP×education, internet×education, etc.)

**Key Achievements**:
- Saturation transforms applied to 5 deficiency needs (empirically validated)
- Within-country normalization (data leakage prevention)
- 8/8 validation tests passed

### Phase 2 (Feature Selection)
**Enhanced Feature Sets**: `/Data/Processed/feature_selection/temporal_enhanced/final_features_enhanced_{metric}.csv`
- 558 total features across 8 metrics (69.75 per metric average)
- 40 imputation-adjusted base features per metric (98.3% mean observed rate)
- ~30 temporal features per metric (MA-3, MA-5, acceleration)
- 99.6% temporal feature retention (239/240 created)

**Training Data**: `/Data/Processed/temporal_enhanced/train_temporal_enhanced.csv`
- 7,200 rows × 12,588 columns
- Includes all 12,426 original features + 162 unique temporal features

**Validation Performance**:
- Mean Years Schooling: R² = 0.974 ✅
- Infant Mortality: R² = 0.954 ✅
- Undernourishment: R² = 0.903 ✅
- Life Expectancy: R² = 0.958 ✅
- GDP per Capita: R² = 0.859 ✅
- Internet Users: R² = 0.941 (baseline)
- Gini: R² = 0.765 (improved via temporal features)
- Homicide: R² = 0.521 (challenging metric)

**Key Methodological Advances**:
- Per-country temporal coverage filtering (80% threshold) → 5× sample size increase
- Pure statistical selection (no artificial domain balancing) → +15.6% infant mortality, +90pp undernourishment
- Imputation-adjusted ranking → 98.3% observed data rate (+18-23pp)
- Selective temporal features → +0.023 R² for Gini, stable for others

### Phase 3 (Model Training & Optimization) - COMPLETE

**Final Optimized Models**: `/models/causal_optimized/` (Approach C - Strict Causal)
- **8 LightGBM models** (one per QOL metric)
- Optuna optimization: 100 trials per model (except life_expectancy: 1 trial)
- Features: 23-52 per metric (strict causal features only)

**Model Artifacts** (per metric):
- `model_lightgbm_{metric}.txt` - Trained LightGBM model
- `results_lightgbm_{metric}.json` - Performance metrics + hyperparameters
- `feature_importance_lightgbm_{metric}.csv` - Gain-based importance
- `shap_importance_{metric}.csv` - SHAP values + gain importance (for Phase 4)
- `test_results_{metric}.json` - Test set evaluation
- `optimization_history_lightgbm_{metric}.csv` - All 100 trial results

**Validation Performance** (26 countries, 1,560 samples):

| Metric | Features | Val R² | Train R² | Overfit |
|--------|----------|--------|----------|---------|
| mean_years_schooling | 38 | 0.905 | 0.952 | 4.7% |
| infant_mortality | 42 | 0.853 | 0.968 | 11.6% |
| undernourishment | 40 | 0.830 | 0.919 | 8.8% |
| gdp_per_capita | 31 | 0.765 | 0.901 | 13.6% |
| gini | 23 | 0.743 | 0.735 | -0.8% |
| internet_users | 47 | 0.730 | 0.942 | 21.2% |
| life_expectancy | 52 | 0.673 | 0.845 | 17.1% |
| homicide | 43 | 0.389 | 0.805 | 41.6% |

**Test Set Generalization** (28 countries, 1,680 samples never seen):
- ✅ **Strong (5 metrics)**: infant_mortality (0.2%), mean_years_schooling (3.3%), gini (9.1%), undernourishment (1.2%), internet_users (3.8%)
- ⚠️ **Weak (3 metrics)**: life_expectancy (33.9%), gdp_per_capita (18.6%), homicide (59.9%)

**Phase 4 Ready Artifacts**:
- Master metadata: `/models/causal_optimized/model_metadata_master.json`
- SHAP extraction summary: `/models/causal_optimized/shap_extraction_summary.json`
- Test evaluation summary: `/models/causal_optimized/test_evaluation_summary.json`

**Documentation**:
- Phase 3 Report: `/Documentation/phase_reports/phase3_report.md`
- Optimization Addendum: `/Documentation/phase_reports/phase3_optimization_addendum.md`
- Three-Way Comparison: `/Documentation/phase_reports/phase3_three_way_comparison.csv`

### Phase 4 (Causal Inference) - COMPLETE

**⚠️ CRITICAL: Use Module 4.2e (154 drivers), NOT Module 4.2f (13 drivers)**

**Complete Causal System (Module 4.2e - 154 drivers)**:
- **Location**: `/models/causal_graphs/module_4.6_autocorr_fixed/combined_causal_graph.json`
- **Structure**: 162 nodes (154 drivers + 8 metrics), 204 edges
- **Features**: Base policy levers + mechanisms + temporal variants (lags, MAs)
- **Purpose**: Complete scientific model ready for dashboard visualization
- **Includes ALL validated mechanisms**: health_x_education, health_risk_compound, inequality_x_safety, gdp_x_technology

**Why NOT Module 4.2f (13 drivers)**:
- TOO filtered: 154 → 13 (91% reduction)
- Lost all mechanisms and temporal dynamics
- Only 1-3 levers per metric (defeats "detailed graph" goal)
- Was experimental over-simplification - **IGNORE IT**

**Dashboard Architecture (v1.0)**:
- Use all 154 drivers from Module 4.2e
- Add UI filters for temporal features/mechanisms (don't pre-filter the data)
- Policy simulator works fine with temporal features (shows timeline: Year 1, Year 3 effects)
- Interpretability achieved through clear naming and tooltips, not data reduction

**Key Outputs for Phase 5**:
- **Graph**: `/models/causal_graphs/module_4.6_autocorr_fixed/` (162 nodes, 204 edges)
- **Policy Simulator**: `/models/causal_graphs/module_4.5_autocorr_fixed/policy_simulators.pkl`
- **Effects**: `/models/causal_graphs/module_4.3_autocorr_fixed/causal_effects_backdoor.json`
- **Granger Network**: `/models/causal_graphs/module_4.4_outputs/granger_causality_detailed.json`

**Documentation**:
- **Reality Check**: `/Documentation/phase_reports/phase4_addendum.md` (bottom section)
- Main Report: `/Documentation/phase_reports/phase4_report.md`

---

## Critical Methodological Principles

### 1. Full Dataset Imputation Strategy
**Phase 0 uses ALL 174 countries** for imputation (not train-test split):
- Maximizes imputation quality via more reference observations
- Train-test split deferred to Phase 1 (after lag features)
- Aligns with multiple imputation best practices (Little & Rubin, 2002)

### 2. Saturation Transforms (REQUIRED)
Applied to 5 deficiency needs BEFORE normalization (Heylighen & Bernheim 2000):
- Life Expectancy: Cap at 85 years (biological ceiling)
- Infant Mortality: Invert-cap at 2/1000 (measurement noise floor)
- GDP per Capita: Log transform ($20K saturation point)
- Undernourishment: Invert-cap at 2.5% (WHO low-prevalence floor)
- Homicide: Invert-cap at 1/100K (definitional noise floor)

**Rationale**: Neural networks cannot learn saturation curves from raw data. Empirically validated via piecewise regression (GDP: 78% slope reduction after $20K).

### 3. Within-Country Normalization
Z-score standardization computed per country over time:
- Removes country-specific scale differences
- Preserves temporal causal dynamics (what we care about)
- Data leakage prevention: Val/test countries use regional training parameters

### 4. Per-Country Temporal Coverage
Phase 2 innovation addressing multivariate missingness:
- Requires 80% mean temporal coverage per country (not just global)
- Increased usable training data 5× (200-600 → 2,769-3,280 samples)
- Panel data principle: Assess coverage within entities over time

### 5. Pure Statistical Selection
Phase 2 revised approach:
- Removed artificial domain-balancing constraints
- Select top-40 features purely by Borda score (Correlation + XGBoost + SHAP)
- Natural domain diversity still emerges (5-9 domains per metric)
- Improved difficult metrics: undernourishment -0.11 → 0.79 R², infant mortality 0.77 → 0.89 R²

### 6. Data Quality Prioritization
Imputation-adjusted ranking (Phase 2.5):
- Down-weight features by observed data rate
- Mean observed rate: 75-80% → 98.3% (+18-23pp)
- Trade-off: -0.021 mean R² for dramatically improved scientific confidence
- Principle: Data quality matters alongside statistical importance

---

## Documentation Structure

### Phase Reports (PRIMARY SOURCE)
**Always read these first**: `/Documentation/phase_reports/phase{0,1,2}_report.md`

### Legacy Documentation
- `/Data/DOCUMENTATION_INDEX.md` - Documentation index
- `/Data/DATA_PIPELINE_MASTER.md` - Pipeline overview
- `/plan.md` - Vision document (10-phase workflow)
- `/Data/PHASE_*.md` - Phase-specific documentation (older)
- `/Data/Processed/*/reports/*.json` - Quality reports

---

## Working with the Data

### Quick Access
```python
import pandas as pd

# Phase 0: Imputed panel (all countries)
df_wide = pd.read_csv('<repo-root>/v1.0/Data/Processed/qol_imputed/master_panel_imputed_wide.csv')

# Phase 1: Normalized features (train/val/test)
train = pd.read_csv('<repo-root>/v1.0/Data/Processed/normalized/train_normalized.csv')
val = pd.read_csv('<repo-root>/v1.0/Data/Processed/normalized/val_normalized.csv')
test = pd.read_csv('<repo-root>/v1.0/Data/Processed/normalized/test_normalized.csv')

# Phase 2: Selected features (enhanced with temporal)
train_enhanced = pd.read_csv('<repo-root>/v1.0/Data/Processed/temporal_enhanced/train_temporal_enhanced.csv')

# Phase 2: Feature sets per metric (40 base + 30 temporal each)
import glob
feature_files = glob.glob('<repo-root>/v1.0/Data/Processed/feature_selection/temporal_enhanced/final_features_enhanced_*.csv')
```

### Running Pipeline Phases
```bash
cd <repo-root>/v1.0/Data

# Phase 0: Extract (6-12 hours)
cd Extraction_Scripts && python WorldBank.py && python WHO.py && python UIS.py && python IMF.py && python UNICEF.py

# Phase 1 (old): Filter (30-60 minutes)
cd ../Scripts && python filter_data_by_coverage.py

# Phase 2 (old): Clean (15-30 minutes)
python data_cleaner.py

# Phase 3 (old): Impute (2 minutes parallel, 6 hours sequential)
python qol_imputation_orchestrator.py
# Run 8 agents in parallel
python integrate_imputed_metrics.py

# Phase 1 (plan.md): Temporal engineering (~4 hours)
python combine_all_variables.py
python create_lag_features.py
python train_test_split.py
python apply_saturation_transforms.py  # BEFORE normalization
python normalize_features.py
python create_feature_registry.py
python phase1_validation_tests.py

# Phase 2 (plan.md): Feature selection (~4.5 hours)
python M2_0A_prefilter_coverage.py         # 40% coverage
python M2_0B_strict_coverage_filter.py     # 80% per-country
python M2_1A_correlation_ranking.py --metric {metric}
python M2_1B_xgboost_importance.py --metric {metric}
python M2_1C_shap_values.py --metric {metric}
python M2_1D_voting_synthesis.py --metric {metric}
python M2_2B_api_classification.py         # Domain classification
python M2_4_pure_statistical.py --metric {metric}  # Top-40 by Borda
python M2_5_final_validation.py --metric {metric}
```

---

## Phase Completion Status

✅ **Phase 1**: Temporal Lag Engineering - COMPLETE (2025-10-21)
✅ **Phase 2**: Feature Selection - COMPLETE (2025-10-22)
✅ **Phase 3**: Model Training & Optimization - COMPLETE (2025-10-23)
✅ **Phase 4**: Causal Inference (Model 2) - COMPLETE (2025-10-24)

**🚀 Ready for Phase 5**: Dashboard Development

**Available Inputs**:
- **Complete Causal Graph**: `/models/causal_graphs/module_4.6_autocorr_fixed/` (154 drivers, 162 nodes total)
- **Policy Simulator**: Module 4.5 (400 scenarios, serialized objects)
- **Backdoor Effects**: Module 4.3 (51/80 significant effects with CIs)
- **Granger Network**: Module 4.4 (50/56 inter-metric relationships)
- **Use Module 4.2e (154 drivers), NOT 4.2f (13 drivers)** - see phase4_addendum.md Reality Check

**Dashboard Strategy**:
- 3-layer hierarchy: Metrics (8) → Domains (15-20) → Drivers (154)
- UI filtering (not pre-filtered data): Toggle temporal/mechanisms, SHAP threshold slider
- Timeline projection using lag coefficients (Year 0, 1, 3 effects)
- Multi-intervention optimizer with synergy detection

**Upcoming Phases**:
- **Phase 5**: Interactive dashboard with causal graph explorer (est. 1-2 weeks)
- **Phase 6-8**: Validation, testing, deliverables

---

## Important Notes

### API Rate Limiting
All extraction scripts implement polite API usage:
- Sleep delays (0.2-0.5 seconds)
- Session reuse with `requests.Session()`
- Appropriate User-Agent headers

### Error Handling
- HTTP errors caught and logged
- Empty datasets skipped with warnings
- Resume capability via checkpoints

### Reproducibility
- **Random seed**: 42 (all splits, models)
- **Python**: 3.8+
- **Key packages**: pandas 1.5+, numpy 1.24+, scikit-learn 1.3+, xgboost 3.1+, shap 0.45+

---

## Critical Working Principles

### Task Completion Verification
**IMPORTANT**: When asked to fix something, verify the fix actually worked before marking complete:
- Check output files contain expected data (e.g., 100 trials not 1)
- Verify file sizes/row counts match expectations
- Test that the fix resolves the original issue
- **A task is NOT complete if it still fails** - even if it runs without errors

Example: If asked to run 100 optimization trials, verify results show `"n_trials": 100` before marking done.

---

## Contact & Feedback

For questions about this project, refer to:
- Phase reports: `/Documentation/phase_reports/`
- Vision document: `/plan.md`
- Documentation index: `/Data/DOCUMENTATION_INDEX.md`
