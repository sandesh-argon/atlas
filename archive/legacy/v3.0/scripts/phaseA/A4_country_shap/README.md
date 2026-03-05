# Phase A.4: Country-Specific SHAP Analysis

## Overview

Computes SHAP importance scores for each country's indicators. This enables country-specific node sizing in the visualization.

## Why This Phase Was Added

V3.0 initially used global SHAP importance (from V2.1) for all countries. This created a data model inconsistency:

| Component | V3.0 Before | V3.0 After |
|-----------|-------------|------------|
| Edge weights | Country-specific | Country-specific |
| Node importance | Global (V2.1) | **Country-specific** |

When selecting a country in the visualization, node sizes should reflect that country's specific indicator importance, not global averages.

## Algorithm

### 1. Quality of Life (QoL) Target

For each country, we compute a composite QoL score from available outcomes:

| Indicator | Name | Direction |
|-----------|------|-----------|
| wdi_lifexp | Life Expectancy | Higher = Better |
| NY.GDP.PCAP.KD | GDP per Capita | Higher = Better |
| SE.ADT.LITR.ZS | Adult Literacy Rate | Higher = Better |
| IT.NET.USER.ZS | Internet Users | Higher = Better |
| wdi_homicides | Homicide Rate | Lower = Better |
| SI.POV.GINI | Gini Index | Lower = Better |
| SP.DYN.IMRT.IN | Infant Mortality | Lower = Better |

Each outcome is normalized to [0, 1] and averaged.

### 2. SHAP Computation

```python
# For each country:
1. Pivot panel data to wide format (years × indicators)
2. Filter to indicators in country's causal graph
3. Train GradientBoostingRegressor: indicators → QoL composite
4. Compute SHAP values using TreeExplainer
5. Aggregate: mean absolute SHAP per indicator
6. Normalize: max = 1.0
```

### 3. Model Parameters

- **Estimators**: 100 trees
- **Max depth**: 5
- **Learning rate**: 0.1
- **Subsample**: 0.8
- **Random state**: 42 (deterministic)

## Output Format

```json
{
  "country": "Australia",
  "shap_importance": {
    "wdi_lifexp": 0.234,
    "NY.GDP.PCAP.KD": 0.891,
    "...": "..."
  },
  "metadata": {
    "n_indicators": 1247,
    "n_samples": 35,
    "qol_components": ["Life Expectancy", "GDP per Capita", "..."],
    "mean_importance": 0.00063,
    "max_importance": 1.0,
    "computation_date": "2025-12-30T..."
  }
}
```

## Runtime

| Mode | Countries | Time |
|------|-----------|------|
| Test (3 countries) | 3 | ~2 minutes |
| Full run | ~205 | ~1-2 hours |

Average per country: 30-60 seconds

## Usage

```bash
cd <repo-root>/v3.0

# Activate environment
source venv/bin/activate

# Test run (estimate runtime)
python scripts/phaseA/A4_country_shap/compute_country_shap.py --test

# Specific countries
python scripts/phaseA/A4_country_shap/compute_country_shap.py --countries Australia Rwanda "United States"

# Full run
python scripts/phaseA/A4_country_shap/compute_country_shap.py

# Validation
python scripts/phaseA/A4_country_shap/validate_country_shap.py
```

## Validation Checks

The validation script checks:

1. **File count**: >= 180 SHAP files created
2. **Value ranges**: All SHAP values in [0, 1]
3. **Indicator counts**: Each country has >= 100 indicators
4. **Heterogeneity**: Different countries show different patterns
5. **Top indicator variation**: Top-10 indicators vary across countries

## Expected Results

### File Output

```
data/country_shap/
├── Afghanistan_shap.json
├── Albania_shap.json
├── ...
├── Zimbabwe_shap.json
└── computation_summary.json
```

### Heterogeneity Example

```
Australia vs Afghanistan: mean_diff=0.15
United States vs Rwanda: mean_diff=0.18
Germany vs Nigeria: mean_diff=0.12
```

Different countries have different indicator importance patterns, reflecting their unique economic and social structures.

## Integration with Visualization

When a user selects a country in the visualization:

```python
# Load country-specific SHAP
with open(f'data/country_shap/{country}_shap.json') as f:
    shap_data = json.load(f)

# Size nodes by country SHAP (not global V2.1 SHAP)
for node in nodes:
    node['radius'] = base_radius + shap_data['shap_importance'].get(node['id'], 0) * scale_factor
```

## Dependencies

- pandas
- numpy
- scikit-learn
- shap
- tqdm

All included in the project's requirements.txt.
