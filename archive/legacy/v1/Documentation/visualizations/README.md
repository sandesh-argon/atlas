# Visualization Data for Phase 2 Feature Selection

**Created**: October 2025
**Source**: Phase 2 Feature Selection Results
**Purpose**: Visualization-ready datasets for bar chart creation

---

## Contents

### 1. Feature Importance Data (`/feature_importance/`)

**8 CSV files** - One per Quality of Life metric, each containing top 25 features:

- `life_expectancy_top25_features.csv`
- `infant_mortality_top25_features.csv`
- `gdp_per_capita_top25_features.csv`
- `mean_years_schooling_top25_features.csv`
- `gini_top25_features.csv`
- `homicide_top25_features.csv`
- `undernourishment_top25_features.csv`
- `internet_users_top25_features.csv`

**CSV Structure:**
```
rank                    - Feature rank (1-25)
feature_code            - World Bank indicator code (e.g., SP.POP.TOTL)
feature_name            - Human-readable name
feature_type            - base / lag_1 / lag_2 / lag_3 / lag_5 / temporal
domain                  - Thematic domain classification (18 categories)
relative_importance_pct - Normalized importance (0-100 scale)
borda_score             - Raw Borda count score (voting synthesis)
observed_data_rate      - Percentage of real (non-imputed) data
description             - Full indicator description
```

**Key Metrics:**
- **Relative Importance**: Normalized to 100 (top feature = 100%, others scaled proportionally)
- **Borda Score**: Voting synthesis across 3 methods (Correlation, XGBoost, SHAP)
- **Observed Rate**: Data quality indicator (98.3% mean across all features)

### 2. QOL Metric Importance Ranking

**File**: `QOL_METRIC_IMPORTANCE_RANKING.md`

Comprehensive ranking of 8 QOL metrics by:
- Predictability (validation R²)
- Policy leverage (causal tractability)
- Data quality (imputation rates)

**Tier 1 (Highest Priority):**
1. Mean Years of Schooling (R² = 0.974)
2. Infant Mortality (R² = 0.954)
3. Undernourishment (R² = 0.903)

**Tier 2 (Good Confidence):**
4. Life Expectancy (R² = 0.958)
5. GDP per Capita (R² = 0.859)

**Tier 3 (Exploratory):**
6. Internet Users (R² = 0.941)
7. Gini Coefficient (R² = 0.765)
8. Homicide Rate (R² = 0.521)

### 3. Dataset Metadata

**File**: `feature_importance/dataset_metadata.json`

Technical metadata including:
- Domain taxonomy (18 categories)
- Feature type definitions
- Importance calculation methodology
- Data quality indicators

---

## Visualization Guidelines

### Bar Chart Recommendations

**Primary Charts (Tier 1 Metrics):**
- **Mean Years Schooling**: Strongest signal; emphasize economic capacity + infrastructure
- **Infant Mortality**: Clear causal pathways; highlight health systems + sanitation
- **Undernourishment**: Agricultural determinism; show crop production + climate

**Secondary Charts (Tier 2 Metrics):**
- **Life Expectancy**: Long-term development trends; note saturation effects
- **GDP per Capita**: Economic mediator; show structural diversity

**Exploratory Charts (Tier 3 Metrics):**
- **Internet Users**: Technology adoption dynamics; temporal patterns
- **Gini**: Policy-dependent; flag data quality (51.7% imputed)
- **Homicide**: Low confidence; governance variables missing

### Color Coding by Domain

Suggested palette for 18 thematic domains:

```
Economic Structure & Output:   #2563EB (Blue)
Energy & Climate:              #DC2626 (Red)
International Trade:           #059669 (Green)
Population & Demographics:     #7C3AED (Purple)
Agriculture & Food:            #CA8A04 (Gold)
Infrastructure & Transport:    #0891B2 (Cyan)
Health Systems:                #DB2777 (Pink)
Urban Development:             #EA580C (Orange)
Education:                     #4F46E5 (Indigo)
Labor & Employment:            #0D9488 (Teal)
Technology & Innovation:       #8B5CF6 (Violet)
Government & Institutions:     #6366F1 (Blue-Violet)
Financial Services:            #10B981 (Emerald)
Environment & Resources:       #059669 (Forest Green)
Social Protection:             #EC4899 (Hot Pink)
Gender & Social Inclusion:     #F59E0B (Amber)
Water & Sanitation:            #06B6D4 (Sky Blue)
Communication Systems:         #3B82F6 (Light Blue)
```

### Feature Type Indicators

Use symbols or patterns to distinguish:
- **Base features**: Solid bars
- **Lag features**: Hatched/striped bars
- **Temporal features**: Dotted bars

### Importance Scale

X-axis: 0-100% (relative importance)
- Top feature always = 100%
- Others scaled proportionally
- Include gridlines at 25%, 50%, 75%

---

## Data Quality Notes

### High Quality Features (>95% Observed)
- Most Tier 1 metrics: Mean Years Schooling, Infant Mortality, Undernourishment
- Population demographics features
- Economic structure indicators

### Moderate Quality (90-95% Observed)
- GDP-related features
- Some health system indicators

### Lower Quality (<90% Observed)
- Gini coefficient features (51.7% imputed - SWIID survey data)
- Homicide features (74.4% imputed - K-NN method)
- Note: These appear only in their respective metric charts

---

## Interpretation Guide

### Relative Importance Score

**100%**: Top feature for this metric (highest Borda score)
**75-99%**: Very strong predictor
**50-74%**: Strong predictor
**25-49%**: Moderate predictor
**<25%**: Weak but statistically significant

### Feature Types

**Base Features**: Original Phase 1 feature (no temporal lag)
- Example: `SP.POP.TOTL` (Population, total)

**Lag Features**: Temporal lag of 1, 2, 3, or 5 years
- Example: `SP.DYN.LE00.MA.IN_lag1` (Male life expectancy, 1-year lag)
- Captures delayed causal effects

**Temporal Features**: Time trend variables
- `year_linear`: Linear time trend (0 to 1 scale from 1965-2024)
- `year_squared`: Quadratic time term (captures acceleration)
- `decade`: Categorical decade identifier (1960s-2020s)

### Domain Classifications

**18 thematic domains** assigned via LLM-assisted classification (Claude 3.5 Sonnet):
- 97.6% high confidence classifications
- 94% accuracy on manual validation
- Used for visualization organization, NOT feature selection

---

## Example Visualization Code (Python)

```python
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# Load top 25 features for a metric
df = pd.read_csv('feature_importance/mean_years_schooling_top25_features.csv')

# Create horizontal bar chart
fig, ax = plt.subplots(figsize=(12, 10))
colors = df['domain'].map(DOMAIN_COLOR_MAP)  # Define color palette

ax.barh(df['feature_name'], df['relative_importance_pct'], color=colors)
ax.set_xlabel('Relative Importance (%)')
ax.set_title('Top 25 Features for Mean Years of Schooling')
ax.invert_yaxis()  # Highest importance at top
plt.tight_layout()
plt.show()
```

---

## Methodological Context

### Phase 2 Feature Selection Pipeline

1. **Coverage Filtering** (12,426 → 1,976 features)
   - 40% global coverage threshold
   - 80% per-country temporal coverage (critical innovation)

2. **Statistical Ranking** (1,976 features)
   - Triple methods: Correlation, XGBoost, SHAP
   - Borda count voting synthesis

3. **Pure Statistical Selection** (1,976 → 320 features)
   - Top 40 features per metric by Borda score
   - No artificial domain balancing

4. **Imputation Adjustment** (320 features)
   - Down-weight by observed data rate
   - Mean observed rate: 98.3% (up from 75-80%)

5. **Validation** (Random Forest baseline)
   - 5/8 metrics R² > 0.55
   - Mean Years Schooling: 0.974 (best)
   - Homicide: 0.521 (lowest)

### Key Innovations

**Per-Country Temporal Coverage** (80% threshold):
- Resolved multivariate missingness crisis
- Increased usable data 5× (200-600 → 2,769-3,280 samples)

**Pure Statistical Selection**:
- Improved infant mortality +15.6% R² (domain concentration worked)
- Improved undernourishment +90pp R² (agricultural focus validated)

**Imputation-Adjusted Ranking**:
- Prioritized data quality alongside statistical importance
- Trade-off: -0.021 mean R² for +20pp observed rate

---

## Citation

> Phase 2 feature selection was performed on 12,426 engineered features using dual-threshold coverage filtering (40% global, 80% per-country temporal), triple-method statistical importance ranking (Correlation, XGBoost, SHAP) with Borda count synthesis, pure statistical selection of top-40 features per metric, and imputation-adjusted re-ranking prioritizing observed data quality (98.3% mean observed rate). Validation R² ranged from 0.521 (homicide) to 0.974 (mean years schooling) on held-out data. Top 25 features per metric were extracted for visualization with human-readable descriptions, domain classifications (18 thematic categories), relative importance scores (0-100 scale), and data quality indicators.

---

## Questions?

For technical details, see:
- Phase 2 Report: `/Documentation/phase_reports/phase2_report.md`
- QOL Metric Ranking: `QOL_METRIC_IMPORTANCE_RANKING.md`
- Dataset Metadata: `feature_importance/dataset_metadata.json`

For data generation script:
- Script: `/Data/Scripts/create_visualization_datasets.py`
