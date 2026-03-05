# Feature Selection (Phase 2)

This directory implements a triple-method approach for selecting the most relevant features for each QOL metric.

## Three Selection Methods

### 01_Statistical/
**Method 1: Statistical Importance**
- Correlation analysis
- XGBoost feature importance
- SHAP values
- Outputs: Top 50-100 features per metric based on statistical relationships

### 02_Thematic/
**Method 2: Domain-Based Selection**
- Classifies all 2,500+ variables into 15-20 thematic domains
- Selects representative features from each domain
- Ensures comprehensive coverage across different aspects of development
- Outputs: 30-50 features per metric based on domain diversity

### 03_Hybrid/
**Method 3: Synthesis Approach**
- Combines statistical and thematic methods
- Identifies intersection of both approaches
- Strategic additions to fill gaps
- Outputs: 40-60 features per metric (balanced approach)

## Final Selection

`Final_Selection/` contains:
- `selected_features_master.csv` - Deduplicated list of ~100-150 unique features
- `feature_metadata.csv` - Descriptions, sources, and domain classifications
- `feature_selection_report.md` - Comprehensive methodology documentation

## Per-Metric Organization

Each method produces outputs for 8 QOL metrics:
1. Life Expectancy
2. Mean Years of Schooling
3. GDP per Capita
4. Infant Mortality
5. Gini Coefficient
6. Homicide Rate
7. Undernourishment
8. Internet Users
