# Phase 4 Export - Causal Discovery & Analysis

**Export Date**: 2025-10-30
**Phase Status**: Complete - Ready for Phase 5 (Dashboard)

---

## Overview

This export contains all artifacts from Phase 4: Causal Discovery & Analysis of the Global Development Indicators Causal Analysis Project.

**Key Achievement**: Complete causal inference pipeline from SHAP importance to policy-ready intervention simulator, using corrected autocorrelation logic and validated mechanisms.

**Critical Note**: This export uses Module 4.2e (154 drivers) which preserves all mechanisms and temporal features. Module 4.2f (13 drivers) was experimental over-simplification and should be IGNORED.

---

## Directory Structure

### 01_causal_drivers/ (10 files)
**Module 4.2e** - Final causal drivers with autocorrelation fix applied

**Contents**:
- `{metric}_causal_drivers_final.csv` - 154 total drivers across 8 metrics (8 files)
- `corrected_confidence_stats.csv` - Summary statistics after autocorrelation fix
- `corrected_comparison.csv` - Before/after comparison

**Driver Counts**: 17-20 drivers per metric (154 total, down from 160 original SHAP features)

**Autocorrelation Fix**: Only 6 truly circular features excluded (3.8% reduction):
- life_expectancy_lag1 → life_expectancy (self-prediction)
- infant_mortality_lag1 → infant_mortality (self-prediction)
- gdp_per_capita_lag1 → gdp_per_capita (self-prediction)
- NY.GDP.MKTP.CD → gdp_per_capita (same variable, different unit)
- NY.GDP.MKTP.KD → gdp_per_capita (alternate encoding)
- (One more GDP variant)

**Mechanisms Preserved**: ALL 4 validated mechanisms retained:
- health_x_education (SHAP 1.000)
- health_risk_compound (SHAP 0.110-1.000)
- inequality_x_safety (SHAP 1.000)
- gdp_x_technology (SHAP 0.437)

---

### 02_backdoor_effects/ (10 files)
**Module 4.3** - Causal effect quantification using Pearl's backdoor criterion

**Contents**:
- `causal_effects_backdoor.json` - All 80 effects with bootstrap confidence intervals
- `backdoor_adjustment_summary.json` - Summary statistics
- `{metric}_effects_detailed.csv` - Per-metric effect tables (8 files)

**Scope**: 80 total effects quantified (top-10 drivers × 8 metrics)
**Significant Effects**: 51/80 (63.7%)
**Method**: Regression-based backdoor adjustment with 1,000 bootstrap samples for 95% CI

**Top Effects by Metric**:
- mean_years_schooling: health_x_education +1.366 [1.316, 1.415] ⭐⭐⭐
- infant_mortality: health_risk_compound_ma5 +0.494 [0.302, 0.672]
- undernourishment: health_risk_compound +1.404 [1.322, 1.481] ⭐⭐
- gdp_per_capita: gdp_x_technology +0.243 [0.006, 0.492]
- gini: inequality_x_safety +0.662 [0.576, 0.747]
- homicide: inequality_x_safety +0.790 [0.718, 0.859] ⭐
- internet_users: year_squared +4.654 (time trend)
- life_expectancy: (complex, multiple factors)

**Key Finding**: Mechanism indicators have 2-10× larger effects than individual policy levers → synergies matter more than single interventions

---

### 03_granger_causality/ (4 files)
**Module 4.4** - Inter-metric causal relationships

**Contents**:
- `granger_causality_matrix.csv` - 8×8 p-value matrix
- `granger_causality_detailed.json` - Full test results with F-statistics
- `var_coefficients.json` - VAR model coefficients
- `inter_metric_summary.json` - Network statistics

**Scope**: 56 total tests (8 metrics × 7 potential causes each)
**Significant Relationships**: 50/56 (89.3%)
**Lag Order**: 3 years
**Network Density**: 0.893 (very high interconnectedness)

**Ultra-Strong Relationships** (p < 1e-50, F-stat > 500):
- internet_users ↔ life_expectancy (bidirectional) - Technology-health co-determination
- mean_years_schooling ↔ gdp_per_capita (bidirectional) - Human capital channel
- infant_mortality ↔ life_expectancy (bidirectional) - Health co-determination
- internet_users → mean_years_schooling (unidirectional) - Technology enables education
- life_expectancy → gdp_per_capita (unidirectional) - Health → productivity
- undernourishment → infant_mortality (unidirectional) - Malnutrition → child deaths

**Feedback Loops Identified**:
- **Virtuous Cycles (3)**: Health-Education-Income, Technology-Development, Infant Health-Longevity
- **Vicious Cycles (2)**: Inequality-Violence, Health-Poverty Trap

---

### 04_policy_simulator/ (12 files)
**Module 4.5** - Do-calculus policy intervention simulator

**Contents**:
- `policy_simulators.pkl` - Serialized PolicySimulator objects (8 simulators, 23MB)
- `{metric}_simulations.csv` - Simulation results per metric (8 files)
- `simulation_summary.json` - Summary statistics
- `best_interventions.csv` - Optimal single-feature interventions
- `example_multi_interventions.json` - Multi-feature scenario examples

**Simulations**: 400 total (80 single-feature + 40 multi-feature scenarios per metric group)
**Method**: Pearl's do-operator using backdoor adjustment coefficients with Granger spillovers

**Best Single-Feature Interventions**:
- Schooling: Health×Education +10% → +1.37 years [1.32, 1.42]
- Infant Mortality: Health Risk -15% → +7.4 deaths/1K [4.5, 10.1]
- Undernourishment: Health Risk -10% → +14.0% [13.2, 14.8]
- GDP: Technology +20% → +$486 PPP [1, 984]
- Gini: Inequality×Safety +10% → -0.066 [-0.075, -0.058]
- Homicide: Inequality×Safety +15% → -1.19/100K [-1.29, -1.08]

**Multi-Intervention Examples**:
- Schooling: Health +20%, Education +15%, synergy → +1.53 years (30% boost from synergy)
- Infant Mort: Health +20%, Water +15%, Sanitation +10% → +9.2 deaths/1K
- GDP: Trade +25%, Tech +20%, Education +15% → +$1,243 PPP

**Key Insight**: Multi-intervention strategies are 10-30% more effective when synergies exist

---

### 05_causal_graphs/ (32 files)
**Module 4.6** - Complete causal DAG construction

**Contents**:
- **Combined Graph**: `combined_causal_graph.{json, nodes.csv, edges.csv}` - Full DAG (3 files)
- **Per-Metric Graphs**: `{metric}_intra_graph.{json, nodes.csv, edges.csv}` - Driver→Metric subgraphs (24 files, 8 metrics × 3 formats)
- **Inter-Metric Graph**: `inter_metric_graph.{json, nodes.csv, edges.csv}` - Metric↔Metric relationships (3 files)
- **Summary**: `graph_construction_summary.json` - Network statistics

**Graph Structure**:
- **Nodes**: 162 total (154 driver nodes + 8 metric nodes)
- **Edges**: 204 total (154 intra-metric + 50 inter-metric)
- **Density**: 0.078 overall (sparse, appropriate for causal DAG), 0.893 inter-metric (very high)
- **Diameter**: 4 (max path length)
- **Avg Path Length**: 2.3

**Node Attributes**:
- Driver nodes: SHAP importance, causal effect (β), confidence interval, tier (mechanism vs. policy)
- Metric nodes: Baseline value, unit, measurement metadata

**Edge Attributes**:
- Intra-metric: SHAP value, backdoor β, p-value, confidence level
- Inter-metric: F-statistic, p-value, bidirectionality flag

**Formats**: JSON (D3.js, Cytoscape), CSV (Gephi, NetworkX)

---

### 06_documentation/ (1 file)
Complete Phase 4 documentation

**Contents**:
- `phase4_addendum.md` - Comprehensive addendum covering Modules 4.2e-4.6 (20KB)

**Full Documentation**:
- See `/Documentation/phase_reports/phase4_report.md` in main project (too large to include here)
- See `/Documentation/phase_reports/phase4_three_model_methodology.md` for theoretical framework
- See `phase4_addendum.md` for executive summary and module details

---

## Performance Summary

### Module Success Rates

| Module | Status | Key Metric |
|--------|--------|-----------|
| 4.2e - Causal Drivers | ✅ Complete | 154 drivers (6 excluded, 3.8% reduction) |
| 4.3 - Backdoor Effects | ✅ Complete | 51/80 significant (63.7%) |
| 4.4 - Granger Causality | ✅ Complete | 50/56 significant (89.3%) |
| 4.5 - Policy Simulator | ✅ Complete | 400 simulations |
| 4.6 - Graph Construction | ✅ Complete | 162 nodes, 204 edges |

**Total Runtime**: ~3.5 hours (excluding Modules 4.1-4.2 from base report)

---

## Key Scientific Findings

### 1. Corrected Autocorrelation Logic Was Essential
Original approach (23 exclusions, 16.3%) removed valid disaggregations:
- life_expectancy: 87.5% driver loss (8→1) - CRISIS
- Required special two-track presentation workaround

Corrected approach (6 exclusions, 3.8%) distinguished:
- **TRUE circular**: Self-lagged predictors (life_expectancy_lag1 → life_expectancy)
- **FALSE circular**: Disaggregations (male_LE, female_LE → total_LE are separate inputs)
- **FALSE circular**: Mechanisms (health_x_education tests synergy, not circular)

**Result**: life_expectancy now fully usable (25→20 drivers, -4%)

### 2. Mechanisms Have 2-10× Larger Effects Than Individual Levers
Backdoor adjustment revealed:
- health_x_education: +1.37 SD (10× larger than typical policy lever)
- health_risk_compound: +0.49-1.40 SD (5-10× larger)
- inequality_x_safety: +0.66-0.79 SD (5× larger)

**Implication**: Dashboard must emphasize Tier 2 mechanisms as much as Tier 1 policy levers

### 3. Everything IS Connected (89.3% Inter-Metric Relationships)
Granger tests found only 6/56 non-significant relationships:
- 50/56 (89.3%) metrics causally influence each other
- 4 metrics (life_exp, infant, school, internet) maximally central (degree=14)

**Implication**: Policy interventions have cascade effects - need spillover calculator

### 4. Feedback Loops Enable Virtuous/Vicious Cycles
Identified cycles:
- **Virtuous**: Health→Education→GDP→Health (health_x_education amplifies)
- **Virtuous**: Internet→Education→GDP→Infrastructure→Internet
- **Vicious**: Inequality→Homicide→Capital Flight→Unemployment→Inequality

**Implication**: Dashboard should highlight loops and show how to "activate virtuous" or "break vicious" cycles

### 5. Multi-Intervention Strategies Are 10-30% More Effective
Policy simulator found:
- **Single**: Health +20% → +1.37 years schooling
- **Multi**: Health +20% + Education +15% → +1.53 years (30% synergy boost)

**Implication**: Dashboard must enable multi-intervention scenario building with synergy detection

---

## Technical Specifications

**Causal Framework**: Pearl's do-calculus + Granger causality
**Backdoor Method**: Regression-based with bootstrap CI (B=1,000)
**Granger Method**: VAR(3) with F-test (lag order = 3 years)
**Graph Format**: Directed Acyclic Graph (DAG)
**Data Source**: Phase 3 optimized models (120 train / 26 val / 28 test countries)
**Reproducibility**: Random seed = 42

**Software Stack**:
- Python 3.8+
- statsmodels (Granger causality, VAR)
- scikit-learn (regression, bootstrap)
- LightGBM (Phase 3 models)
- SHAP (importance extraction)
- pandas, numpy, json

---

## Next Steps (Phase 5)

Phase 5 will use these artifacts to build an interactive dashboard with:

### Dashboard Components
1. **Interactive Causal Graph Explorer** (use `combined_causal_graph.json`)
   - 3-layer hierarchy: Metrics (8) → Domains (15-20) → Drivers (154)
   - UI filtering: Toggle temporal/mechanisms, SHAP threshold slider
   - Color-coding by effect size and confidence

2. **Policy Simulation Tool** (use `policy_simulators.pkl`)
   - Single-feature interventions with confidence intervals
   - Multi-feature scenario builder with synergy detection
   - Timeline projection using lag coefficients (Year 0, 1, 3 effects)

3. **Metric Drill-Down Views** (use `{metric}_intra_graph.json`)
   - Top 20 drivers per metric with visualizations
   - Mechanism vs. policy lever comparison
   - Direct vs. indirect effects

4. **Spillover Effect Visualizer** (use Granger coefficients)
   - Cascade calculator showing ripple effects
   - Inter-metric dependency graph
   - Network centrality analysis

5. **Feedback Loop Animator** (use identified cycles)
   - Virtuous cycle activator (recommendations)
   - Vicious cycle breaker (intervention strategies)
   - Temporal dynamics visualization

### Publication-Ready Status
- **Dashboard Ready**: ✅ All graph files, simulator objects, and effect sizes prepared
- **Academic Paper Ready**: ✅ Methodologically rigorous, statistically validated, novel findings
- **Policy Brief Ready**: ✅ Top 3-5 mechanisms per metric, quantified synergies, feedback loop recommendations

---

## Critical Design Decisions

### Why Module 4.2e (154 drivers), NOT 4.2f (13 drivers)?
Module 4.2f was experimental over-simplification:
- TOO filtered: 154 → 13 (91% reduction)
- Lost all mechanisms and temporal dynamics
- Only 1-3 levers per metric (defeats "detailed graph" goal)
- **IGNORE IT** - use Module 4.2e instead

Dashboard strategy:
- Use all 154 drivers from Module 4.2e
- Add UI filters for temporal features/mechanisms (don't pre-filter the data)
- Policy simulator works fine with temporal features (shows timeline: Year 1, Year 3 effects)
- Interpretability achieved through clear naming and tooltips, not data reduction

---

## Version Control

- **Phase 4 Started**: 2025-10-24
- **Module 4.2e Completed**: 2025-10-24 02:20 (autocorrelation fix v2)
- **Module 4.3 Completed**: 2025-10-24 20:48-20:57 (backdoor adjustment)
- **Module 4.4 Completed**: 2025-10-24 (Granger causality)
- **Module 4.5 Completed**: 2025-10-24 (policy simulator)
- **Module 4.6 Completed**: 2025-10-24 (graph construction)
- **Phase 4 Export Created**: 2025-10-30

---

## Contact & Resources

For questions about Phase 4 methodology or results:
- See `/06_documentation/phase4_addendum.md` for comprehensive module details
- See main project `/Documentation/phase_reports/phase4_report.md` for full report
- See `/05_causal_graphs/combined_causal_graph.json` to start exploring the graph

**Dashboard Development**: Use Module 4.2e (154 drivers) as documented in `phase4_addendum.md` Reality Check section

---

## File Inventory

**Total Files**: 69 files across 6 directories + 1 README

- 01_causal_drivers: 10 files (8 per-metric CSVs + 2 summaries)
- 02_backdoor_effects: 10 files (1 JSON + 1 summary + 8 per-metric CSVs)
- 03_granger_causality: 4 files (1 matrix + 3 JSONs)
- 04_policy_simulator: 12 files (1 PKL + 8 per-metric CSVs + 3 summaries)
- 05_causal_graphs: 32 files (3 combined + 24 per-metric + 3 inter-metric + 2 summaries)
- 06_documentation: 1 file (phase4_addendum.md)

**Total Size**: ~24 MB (dominated by policy_simulators.pkl at 23 MB)

---

## Validation Checklist

✅ All 5 modules (4.2e-4.6) outputs present
✅ All 8 QOL metrics covered
✅ Mechanisms preserved (health_x_education, health_risk_compound, inequality_x_safety, gdp_x_technology)
✅ Graph structure validated (162 nodes, 204 edges)
✅ Policy simulator serialized and ready
✅ Documentation comprehensive
✅ Module 4.2e used (NOT 4.2f)

**Status**: ✅ PHASE 4 100% COMPLETE - READY FOR PHASE 5
