# Global Causal Discovery System for Quality of Life Drivers

**Research Domain**: Development Economics + Causal Inference + Machine Learning
**Status**: Phase 0-2 Complete (Data Acquisition → Feature Selection)
**Data Scope**: 174 countries × 65 years (1960-2024) × 2,480 socioeconomic indicators
**Achievement**: 99.7% dimensionality reduction (12,426 → 320 features) with strong predictive validation (5/8 metrics R² > 0.55)
**Date**: 2025-10-22

---

## Overview

This project implements a rigorous data pipeline identifying causal drivers of quality of life across 174 countries using 2,480 socioeconomic indicators from five international organizations (World Bank, WHO, UNESCO UIS, IMF, UNICEF). Through novel methodologies combining full-dataset multiple imputation, saturation transforms grounded in deficiency needs theory, and hybrid statistical-thematic feature selection, we transform raw API data into analysis-ready features suitable for causal discovery algorithms.

**Key Innovation**: Resolution of 80-94% sample dropout crisis through strict per-country temporal coverage filtering, demonstrating necessity of panel-specific quality metrics.

**Final Deliverables**:
- **ML-Ready Datasets**: Train (7,200 × 12,426), Val (1,560 × 12,426), Test (1,680 × 12,426)
- **Selected Features**: 40 features per QOL metric (320 total, 99.7% reduction)
- **Data Completeness**: 99.81% after tiered imputation
- **Validation**: 5/8 metrics pass R² > 0.55 threshold on held-out data

---

## Quick Start

### Access Final Datasets

```python
import pandas as pd

# Load ML-ready training data (PRIMARY USE)
train = pd.read_csv('Data/Processed/normalized/train_normalized.csv')
# Shape: (7200, 12426) - 120 countries × 60 years

# Load selected features for Life Expectancy
features = pd.read_csv('Data/Processed/feature_selection/hybrid_features_life_expectancy.csv')
feature_list = features.iloc[:, 0].tolist()  # 40 features

# Subset to selected features
X_train = train[feature_list]
y_train = train['life_expectancy']

# Train model
from sklearn.ensemble import RandomForestRegressor
model = RandomForestRegressor(n_estimators=100, random_state=42)
model.fit(X_train, y_train)
```

### Key Results

**Phase 0** (Data Preparation):
- 2,509 indicators extracted → 2,517 passed coverage filter (99.6%)
- 8 QOL metrics imputed to 99.81% completeness
- Tiered imputation: Cubic Spline → MICE → K-NN

**Phase 1** (Temporal Engineering):
- 12,426 features engineered (2,480 base + 9,920 lags + 16 other)
- Saturation transforms applied to 5 deficiency needs (Heylighen & Bernheim 2000)
- Within-country normalization with data leakage prevention
- 8/8 validation tests passed

**Phase 2** (Feature Selection):
- Critical fix: 80% per-country temporal coverage filter (5-10× sample recovery)
- Hybrid selection: Statistical (correlation + XGBoost + SHAP) + thematic (18 domains)
- Final: 40 features × 8 metrics = 320 total features
- Validation: 5/8 metrics R² > 0.55 (MYS: 0.93, IM: 0.77, LE: 0.62, GDP: 0.59, Internet: 0.57)

---

## Quality of Life Metrics (8 Targets)

| Metric | Missing % | Imputation Method | Validation R² | Status |
|--------|-----------|-------------------|---------------|--------|
| **Mean Years of Schooling** | 86.9%† | Real data + K-NN | 0.93 | ✅ Excellent |
| **Infant Mortality** | 23.5% | MICE + Random Forest | 0.77 | ✅ Strong |
| **Life Expectancy** | 2.1% | Cubic Spline | 0.62 | ✅ Strong |
| **GDP per Capita** | 51.1% | Time-series + MICE | 0.59 | ✅ Strong |
| **Internet Users** | 61.0% | Time-series + MICE | 0.57 | ✅ Strong |
| **Gini Coefficient** | 51.7% | MICE | 0.06 | ⚠️ Weak (policy-driven) |
| **Homicide Rate** | 74.4% | K-NN | -0.03 | ⚠️ Weak (conflict-driven) |
| **Undernourishment** | 72.2% | MICE | -0.11 | ⚠️ Weak (climate/conflict) |

†Sparse temporal distribution (avg 9.6 observed years per country), not true missingness.

---

## Project Structure

```
Global_Project/v1.0/
├── README.md                          # This file
├── plan.md                            # Vision: 10-phase workflow
├── CLAUDE.md                          # AI assistant instructions
│
├── Data/
│   ├── Scripts/                       # Pipeline implementation
│   │   ├── README.md                 # COMPLETE execution guide (5-7 pages)
│   │   ├── filter_data_by_coverage.py
│   │   ├── data_cleaner.py
│   │   ├── qol_imputation_orchestrator.py
│   │   ├── impute_agent_1-8_*.py    # Tiered imputation
│   │   ├── combine_all_variables.py
│   │   ├── create_lag_features.py
│   │   ├── train_test_split.py
│   │   ├── apply_saturation_transforms.py  # ⭐ Methodologically critical
│   │   ├── normalize_features.py
│   │   └── phase2_modules/           # Feature selection pipeline
│   │       ├── README.md             # Phase 2 documentation
│   │       ├── run_module_2_0b_coverage_filter.py  # ⭐ Crisis resolution
│   │       └── [13 modules...]
│   │
│   ├── Processed/                     # PRIMARY OUTPUTS ⭐
│   │   ├── README.md                 # Data catalog (3-4 pages)
│   │   ├── qol_imputed/              # Phase 0 final
│   │   │   └── master_panel_imputed_wide.csv (11,310 × 18)
│   │   ├── normalized/               # Phase 1 final (ML-READY)
│   │   │   ├── train_normalized.csv  (7,200 × 12,426, 697 MB)
│   │   │   ├── val_normalized.csv    (1,560 × 12,426, 143 MB)
│   │   │   └── test_normalized.csv   (1,680 × 12,426, 158 MB)
│   │   └── feature_selection/        # Phase 2 final
│   │       ├── hybrid_features_*.csv  (8 files, 40 features each)
│   │       └── validation_results.csv
│   │
│   ├── Raw_Data/                      # API extractions
│   ├── filtered_data/                 # Coverage-filtered
│   ├── filtered_data_cleaned/         # Standardized
│   └── Extraction_Scripts/            # API scripts
│
├── Documentation/
│   ├── METHODOLOGY_SUMMARY.md         # COMPLETE methodology (8-10 pages)
│   └── phase_reports/                 # Detailed phase reports
│       ├── phase0_report.md          # Data acquisition & preparation
│       ├── phase1_report.md          # Temporal engineering + extension
│       └── phase2_report.md          # Feature selection + validation
│
└── Indicators/
    ├── world_bank_indicators.csv      # Input manifests
    ├── WHO Global Health Observatory.csv
    └── [other source lists]
```

---

## Methodological Innovations

### 1. Full-Dataset Multiple Imputation

**Innovation**: Use ALL 174 countries for imputation, defer train-test split to post-feature-engineering
**Rationale**: Maximizes imputation quality (more stable correlations, better K-NN neighbors) while preserving out-of-sample validation capability
**Impact**: 99.81% completeness achieved
**Reference**: Little & Rubin (2002) - "Multiple imputation should use all available data"

### 2. Saturation Transforms for Deficiency Needs

**Innovation**: Explicit mathematical transforms grounded in Heylighen's theory
**Transforms Applied**:
- Life Expectancy: Cap at 85 years (biological ceiling)
- GDP: Log transform at $20K (Easterlin paradox)
- Infant Mortality: Saturate at 2/1000 (measurement noise floor)
- Undernourishment: Saturate at 2.5% (WHO low prevalence)
- Homicide: Saturate at 1/100K (definitional noise threshold)

**Validation**: GDP shows 78% slope reduction beyond $20K (R² 0.61 → 0.23) ✓
**Reference**: Heylighen & Bernheim (2000) - "Global Progress I"

### 3. Country-Agnostic Train-Test Split

**Innovation**: Test on unseen **countries**, not future time periods
**Rationale**: Project goal is generalizing to new nations (e.g., "What policies improve Myanmar's life expectancy?"), not time-series forecasting
**Split**: Train 120 countries (69%), Val 26 (15%), Test 28 (16%)
**Stratification**: World Bank Region × Income Level (20 strata)

### 4. Per-Country Temporal Coverage Filtering ⭐

**Innovation**: Calculate mean temporal coverage across countries, not global coverage
**Problem Solved**: Multivariate missingness cascade (40 features × 15% missing → 99.85% dropout)
**Implementation**: Require ≥80% temporal density within each country
**Impact**: 5-10× sample recovery (200-600 → 2,769-3,280 observations)
**Key Lesson**: Panel data quality metrics must assess within-entity temporal density

### 5. Hybrid Statistical-Thematic Selection

**Innovation**: Combine statistical importance (correlation + XGBoost + SHAP) with domain-balanced interpretability
**Methods**:
- Statistical: Borda voting across 3 ranking methods (top-200 per metric)
- Thematic: 18-domain taxonomy, LLM classification, balanced selection (35-50 per metric)
- Hybrid: Intersection + strategic additions (final 40 per metric)

**Impact**: 99.7% dimensionality reduction (12,426 → 320) with validation success

---

## Documentation Map

### Essential Reading

1. **Project README** (this file) - Overview, quick start, key results
2. **Data/Scripts/README.md** - Complete pipeline execution guide (5-7 pages)
3. **Documentation/METHODOLOGY_SUMMARY.md** - Academic methodology (8-10 pages)

### Detailed Phase Reports

- **Phase 0**: `/Documentation/phase_reports/phase0_report.md` - Data acquisition & preparation
- **Phase 1**: `/Documentation/phase_reports/phase1_report.md` - Temporal engineering + extension
- **Phase 2**: `/Documentation/phase_reports/phase2_report.md` - Feature selection + validation

### Data Catalogs

- **All Processed Data**: `/Data/Processed/README.md` - File formats, schemas, usage patterns
- **Phase 2 Modules**: `/Data/Scripts/phase2_modules/README.md` - Feature selection pipeline

### Historical Documentation

- **Phase-Specific Docs**: `/Data/PHASE_*.md` - Original implementation notes
- **Planning Docs**: `/Data/PHASE_*_PLAN.md` - VIF filtering, imputation weighting, validation

---

## Execution Guide

### Full Pipeline (16-20 hours)

```bash
# Prerequisites
cd <repo-root>/v1.0/Data
source venv/bin/activate  # Python 3.9+

# Phase 0: Data Preparation (8-14h)
python Scripts/filter_data_by_coverage.py  # 30-60 min
python Scripts/data_cleaner.py             # 15-30 min
python Scripts/qol_imputation_orchestrator.py
# Run 8 imputation agents (parallel: 2min, sequential: 6h)

# Phase 1: Temporal Engineering (4h)
python Scripts/combine_all_variables.py          # 2 min
python Scripts/create_lag_features.py            # 1 min
python Scripts/train_test_split.py               # 1 min
python Scripts/apply_saturation_transforms.py    # 5 min ⭐ BEFORE normalization
python Scripts/normalize_features.py             # 90 min
python Scripts/add_temporal_features.py          # 2 min
python Scripts/add_interaction_features.py       # 2 min

# Phase 2: Feature Selection (4h)
cd Scripts/phase2_modules
python run_module_2_0a_prefilter.py              # 2 min
python run_module_2_0b_coverage_filter.py        # 15 min ⭐ CRITICAL
# Run M2_1A-C in parallel (90 min total)
python run_module_2_1d_voting.py                 # 10 sec
python run_module_2_2b_api_classification.py     # 120 min
python run_module_2_3_thematic_selection.py      # 10 min
python run_module_2_4_hybrid_synthesis.py        # 5 min
python run_module_2_5_validation.py              # 15 min
```

### Quick Validation (5 minutes)

```bash
# Verify Phase 0 completeness
python -c "
import pandas as pd
df = pd.read_csv('Data/Processed/qol_imputed/master_panel_imputed_wide.csv')
completeness = df.notna().sum().sum() / (df.shape[0] * df.shape[1]) * 100
print(f'Data Completeness: {completeness:.2f}% (Target: ≥99%)')
"

# Verify Phase 1 outputs
python -c "
import pandas as pd
train = pd.read_csv('Data/Processed/normalized/train_normalized.csv')
print(f'Training Data: {train.shape} (Expected: 7200 × 12426)')
"

# Verify Phase 2 validation
python -c "
import pandas as pd
results = pd.read_csv('Data/Processed/feature_selection/validation_results.csv')
passed = (results['r_squared'] > 0.55).sum()
print(f'Metrics Passing Validation: {passed}/8 (Target: ≥5)')
"
```

---

## Key Papers & References

**Theoretical Foundations**:
- Heylighen & Bernheim (2000) - Global Progress I: Deficiency vs. growth needs
- Little & Rubin (2002) - Statistical Analysis with Missing Data
- Maslow (1943) - A Theory of Human Motivation

**Methodological**:
- Lundberg & Lee (2017) - SHAP: Unified Model Interpretations
- Chen & Guestrin (2016) - XGBoost: Scalable Tree Boosting
- van Buuren (2018) - Flexible Imputation of Missing Data

**Data Sources**:
- World Bank - World Development Indicators
- WHO - Global Health Observatory
- UNESCO UIS - Education Statistics
- IMF - DataMapper
- UNICEF - Data Warehouse
- Solt (2020) - SWIID Gini Coefficient Database

---

## Next Steps (Phases 3-10)

### Phase 3: Individual Metric Models
- Train 8 separate models with selected features
- Apply imputation weighting (observed=1.0, imputed=0.5-0.9)
- Generate SHAP explanations for interpretability
- VIF filtering for multicollinearity (threshold: 10)

### Phase 4: Inter-Metric Relationship Analysis
- Cross-metric correlation analysis
- Granger causality tests
- Identify bidirectional relationships

### Phase 5: Master Integrated Multi-Output Model
- Single model predicting all 8 QOL metrics simultaneously
- Shared feature representations
- Cross-metric learning

### Phases 6-8: Causal Discovery
- Apply causal discovery algorithms (PC, FCI, GES)
- Validate against known RCT evidence
- Generate causal knowledge graphs

### Phase 9: Validation Studies (Deferred)
- Saturation threshold sensitivity (±20%)
- Imputation method comparison (MICE vs K-NN vs MissForest)
- Bootstrap stability (500 resamples)
- Temporal stability (rolling window)

### Phase 10: Deliverables
- Academic paper
- Interactive web dashboard
- Causal policy simulator
- Open-source code release

---

## Citation

If you use this dataset or methodology, please cite:

```bibtex
@misc{global_causal_qol_2025,
  title={Global Causal Discovery System for Quality of Life Drivers},
  author={[Author Names]},
  year={2025},
  note={Phases 0-2 Complete: Data Acquisition through Feature Selection},
  url={[Repository URL]}
}
```

---

## License & Contact

**License**: [To be determined - suggest MIT or CC-BY-4.0]
**Contact**: [Contact information]
**Contributors**: [List contributors]
**Acknowledgments**: World Bank, WHO, UNESCO, IMF, UNICEF for open data access

---

## Change Log

**v1.0.0** (2025-10-22) - Phase 0-2 Complete
- Data acquisition from 5 sources (2,509 indicators)
- Tiered imputation to 99.81% completeness
- 12,426 features engineered with saturation transforms
- Dimensionality reduction to 320 features (99.7%)
- 5/8 metrics achieve R² > 0.55 on validation
- Resolution of 80-94% sample dropout crisis

---

**Document Version**: 1.0
**Last Updated**: 2025-10-22
**Maintainer**: Phase A Documentation Initiative
**Status**: Production Ready
