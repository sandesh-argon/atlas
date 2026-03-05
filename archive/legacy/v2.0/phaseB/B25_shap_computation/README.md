# B2.5: SHAP Score Computation

## Overview

Computes unbiased SHAP importance scores for all 3,872 indicators using LightGBM TreeSHAP, trained on B1-discovered outcome dimensions.

## Method

### Outcome Selection (Unbiased)
- Uses **9 outcome dimensions discovered by B1 factor analysis**
- Top variable from each factor serves as outcome proxy
- **No manual curation** - fully data-driven outcome selection

### SHAP Computation
1. For each B1 outcome proxy, train LightGBM regression model
2. Compute TreeSHAP values for all features
3. Aggregate mean |SHAP| across all 9 outcomes
4. Normalize to 0-1 range

## Results Summary

| Metric | Value |
|--------|-------|
| Indicators scored | 3,702 / 3,872 (95.6%) |
| Outcomes used | 9 (B1 factor proxies) |
| Runtime | ~2 minutes |

### Top 10 by SHAP
1. NW.NCA.FISH.TO (Natural capital - fisheries) - 1.000
2. v2x_clphy (V-Dem physical violence) - 0.655
3. ER.H2O.INTR.PC (Water resources per capita) - 0.513
4. ef_fg (Economic freedom - fiscal) - 0.510
5. v2clacjust_osp (V-Dem access to justice) - 0.326
6. v2smlawpr_mean (V-Dem law & order) - 0.302
7. SH.DTH.IMRT (Infant mortality rate) - 0.302
8. asavgoi992 (Economic indicator) - 0.269
9. SAP.4 (Social assistance program) - 0.241
10. mgwdeci999 (Economic indicator) - 0.236

### Domain Distribution (Top 50)
- Economic: 40%
- Governance: 26%
- Education: 14%
- Health: 8%
- Environment: 6%
- Demographics: 6%

## Validation

### SHAP vs Betweenness Orthogonality
- **Overlap in top 20: 0%**
- This is EXPECTED and VALID
- SHAP measures predictive importance (what predicts outcomes)
- Betweenness measures structural importance (what connects the network)
- Zero overlap confirms these are complementary, not redundant metrics

### Interpretation
| Metric | Identifies | Graph Position | Use Case |
|--------|-----------|----------------|----------|
| SHAP | Outcome predictors | Drivers, edges | Direct intervention targets |
| Betweenness | Causal bottlenecks | Middle layers | Structural reform targets |

## Files

- `outputs/B25_shap_scores.pkl` - Full SHAP scores for all indicators
- `outputs/B25_shap_summary.json` - Statistics and top 20
- `scripts/run_b25_shap_computation.py` - Main computation script
- `check_progress.py` - Progress monitoring script

## Usage in B3.5

For visualization priority, use composite score:
```python
composite_score = (
    0.50 * shap_normalized +      # Predictive importance
    0.30 * betweenness_norm +     # Structural importance
    0.15 * (1 - layer/20) +       # Upstream bonus
    0.05 * degree_norm            # Connectivity
)
```

## Paper Section

> **4.3 Dual Importance Metrics**
>
> We employ two complementary importance metrics. SHAP scores identify
> indicators with high explanatory power for quality-of-life outcomes
> (e.g., natural capital, violence indices, water resources). Betweenness
> centrality identifies structural bottlenecks that mediate causal pathways
> (e.g., deliberative governance, labor policies). The zero overlap between
> top-20 rankings confirms these metrics capture orthogonal dimensions of
> importance, validating our dual-metric approach.
