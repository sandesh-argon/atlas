# PHASE 4 CAUSAL DISCOVERY - ARCHITECTURE SUMMARY

## Executive Overview

Phase 4 transforms Phase 3's predictive models (93 trained models, R²: 0.358-0.924) into causal knowledge using constraint-based causal discovery, enabling policy simulations that answer "what-if" questions for development interventions.

**Core Innovation**: Operationalizing Pearl's causal hierarchy—moving from association (correlation) to intervention (causation) through PC algorithm + do-calculus implementation.

---

## Module Dependency Graph

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         PHASE 4 EXECUTION FLOW                              │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ MODULE 4.1: ENVIRONMENT SETUP (5 min)                                │  │
│  │ - Install causal-learn, pgmpy, networkx                              │  │
│  │ - Load Phase 3 models (8 LightGBM) + SHAP importance                 │  │
│  │ - Verify data integrity                                               │  │
│  └────────────────────────┬─────────────────────────────────────────────┘  │
│                           ↓                                                  │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ MODULE 4.2: PC CAUSAL DISCOVERY - TIER 1 (30-45 min)                 │  │
│  │ - Run PC algorithm on 3 high-R² metrics                              │  │
│  │ - SHAP-weighted edge priors                                           │  │
│  │ - Discover 10-50 edges per metric                                     │  │
│  │ - Identify 8-25 causal drivers per metric                             │  │
│  │ ⚡ PARALLELIZABLE: 3 processes (→ 15 min)                             │  │
│  └────────────────────────┬─────────────────────────────────────────────┘  │
│                           ↓                                                  │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ MODULE 4.3: VIF FILTERING & REFINEMENT (15 min)                      │  │
│  │ - Calculate VIF for top 20 drivers                                    │  │
│  │ - Remove multicollinearity (VIF > 10)                                 │  │
│  │ - Re-run PC on VIF-filtered features                                  │  │
│  │ - Retain 15-18 non-collinear drivers                                  │  │
│  └────────────────────────┬─────────────────────────────────────────────┘  │
│                           ↓                                                  │
│          ┌────────────────┴────────────────┐                                │
│          ↓                                  ↓                                │
│  ┌──────────────────────┐          ┌──────────────────────┐                │
│  │ MODULE 4.4:          │          │ MODULE 4.5:          │                │
│  │ INTER-METRIC         │          │ EFFECT               │                │
│  │ ANALYSIS (45-60 min) │          │ QUANTIFICATION       │                │
│  │                      │          │ (30 min)             │                │
│  │ - Granger causality  │          │ - Backdoor           │                │
│  │ - VAR modeling       │          │   adjustment         │                │
│  │ - SEM (optional)     │          │ - Bootstrap CI       │                │
│  │ - Build inter-metric │          │   (1,000 iter)       │                │
│  │   graph (8 nodes)    │          │ - Literature         │                │
│  │                      │          │   validation         │                │
│  │ ⚡ Can run parallel  │          │ ⚡ Can run parallel  │                │
│  │    with 4.5          │          │    with 4.4          │                │
│  └──────────┬───────────┘          └──────────┬───────────┘                │
│             └────────────────┬─────────────────┘                            │
│                              ↓                                               │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ MODULE 4.6: POLICY SIMULATION FRAMEWORK (60 min)                     │  │
│  │ - Implement PolicySimulator class                                     │  │
│  │ - Do-calculus for interventions                                       │  │
│  │ - Direct + spillover effects                                          │  │
│  │ - Counterfactual queries                                              │  │
│  │ - Export API specification for Phase 6                                │  │
│  └────────────────────────┬─────────────────────────────────────────────┘  │
│                           ↓                                                  │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ MODULE 4.7: VALIDATION & VISUALIZATION (30 min)                      │  │
│  │ - 5 automated tests (DAG acyclicity, effect consistency, etc.)        │  │
│  │ - Generate DAG visualizations (3 PNG)                                 │  │
│  │ - Generate effect plots with CI (3 PNG)                               │  │
│  │ - Generate inter-metric graph (1 PNG)                                 │  │
│  │ - DECISION POINT: PASS → Module 4.8 | FAIL → Fix issues               │  │
│  └────────────────────────┬─────────────────────────────────────────────┘  │
│                           ↓                                                  │
│                  [VALIDATION PASS REQUIRED]                                  │
│                           ↓                                                  │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │ MODULE 4.8: EXTENSION TO ALL 8 METRICS (90-120 min)                  │  │
│  │ - Apply validated pipeline to Tier 2 (3 metrics) + Tier 3 (2)        │  │
│  │ - PC discovery with adaptive alpha (0.05 → 0.10 for Tier 3)          │  │
│  │ - VIF filtering for all metrics                                       │  │
│  │ - Effect quantification for all metrics                               │  │
│  │ - Update simulator with all 8 metrics                                 │  │
│  │ - Generate visualizations (16 PNG total)                              │  │
│  │ ⚡ PARALLELIZABLE: 5 processes (→ 30-40 min)                          │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘

TOTAL RUNTIME:
  Sequential: 5-7 hours
  Parallelized: 3-4 hours (recommended)
```

---

## Module Breakdown Table

| # | Module Name | Purpose | Inputs | Outputs | Runtime | Priority | Dependencies |
|---|-------------|---------|--------|---------|---------|----------|--------------|
| **4.1** | Setup | Install libraries, load Phase 3 | Phase 3 models, SHAP | Loaded data, config | 5 min | HIGH | None |
| **4.2** | PC Discovery (Tier 1) | Discover causal graphs | Training data, SHAP | DAGs, drivers | 30-45 min | HIGH | 4.1 |
| **4.3** | VIF Refinement | Remove multicollinearity | Top 20 drivers | Refined DAGs | 15 min | HIGH | 4.2 |
| **4.4** | Inter-Metric Analysis | Metric→metric relationships | All QOL metrics | Inter-metric graph | 45-60 min | HIGH | 4.1 |
| **4.5** | Effect Quantification | Backdoor adjustment + CI | VIF-filtered drivers | Effect sizes | 30 min | HIGH | 4.3 |
| **4.6** | Policy Simulator | Do-calculus implementation | DAGs, effects, inter-metric | Simulator class | 60 min | HIGH | 4.3, 4.4, 4.5 |
| **4.7** | Validation & Viz | QA checkpoint | All previous outputs | Validation report, PNGs | 30 min | MED | 4.1-4.6 |
| **4.8** | Extension | Apply to all 8 metrics | Validated pipeline | Full causal knowledge | 90-120 min | MED | 4.7 (PASS) |

---

## Data Flow Architecture

```
INPUT (Phase 3)                      PROCESSING (Phase 4)                    OUTPUT (Phase 6)
┌──────────────┐                     ┌─────────────────────┐                ┌────────────────┐
│ 8 LightGBM   │──┐                  │                     │                │ Flask API      │
│ Models       │  │                  │  PC Algorithm       │                │ /api/simulate_ │
│ (.txt)       │  │                  │  (causal-learn)     │                │ intervention   │
└──────────────┘  │                  │                     │                └────────────────┘
                  │                  │  ↓                  │                         ↑
┌──────────────┐  │                  │                     │                         │
│ SHAP         │──┼──→ Module 4.1 ──→│  Causal DAGs        │──┐                      │
│ Importance   │  │   (Setup)        │  (8 metrics)        │  │                      │
│ (.csv)       │  │                  │                     │  │                      │
└──────────────┘  │                  │  ↓                  │  │                      │
                  │                  │                     │  │                      │
┌──────────────┐  │                  │  VIF Filtering      │  │                      │
│ Training     │──┘                  │  (remove collinear) │  │                      │
│ Data         │                     │                     │  │                      │
│ (normalized) │                     │  ↓                  │  │                      │
└──────────────┘                     │                     │  │                      │
                                     │  Causal Effects     │  │                      │
                                     │  (backdoor adj.)    │  │                      │
                                     │                     │  │                      │
                                     │  ↓                  │  │                      │
                                     │                     │  │                      │
                                     │  PolicySimulator    │  │                      │
                                     │  (do-calculus)      │  │                      │
                                     └─────────────────────┘  │                      │
                                              │               │                      │
                                              ↓               ↓                      │
                                     ┌─────────────────────────────────┐             │
                                     │ OUTPUTS                         │             │
                                     │ - policy_simulator_full.pkl ────┼─────────────┘
                                     │ - api_specification_full.json   │
                                     │ - causal_effects_all_metrics.json│
                                     │ - 16 visualization PNGs         │
                                     └─────────────────────────────────┘
```

---

## Key Algorithms & Techniques

### 1. PC (Peter-Clark) Algorithm (Module 4.2)

**Purpose**: Discover causal graph structure from observational data

**Theory**: Constraint-based causal discovery
- Tests conditional independence: If A ⊥ B | Z, then no direct edge A—B
- Orients edges using Meek's rules and v-structures
- Returns partially directed acyclic graph (PDAG)

**Implementation**:
```python
from causallearn.search.ConstraintBased.PC import pc
from causallearn.utils.cit import fisherz

cg = pc(
    X,                    # Feature matrix (n × p)
    alpha=0.05,           # Significance level (95% confidence)
    indep_test=fisherz,   # Fisher-Z test (partial correlation)
    stable=True,          # Order-independent variant
    uc_rule=0             # Meek's orientation rules
)
```

**SHAP-Weighted Edge Priors**:
- Normalize SHAP values to [0, 1]
- Weight edges by average SHAP of connected nodes
- Prioritizes high-importance features in causal search

**Expected Output**: 10-50 edges per metric, 8-25 drivers

### 2. VIF (Variance Inflation Factor) Filtering (Module 4.3)

**Purpose**: Remove multicollinearity from causal drivers

**Theory**: VIF measures how much variance of regression coefficient inflates due to multicollinearity
- VIF < 5: No multicollinearity
- VIF 5-10: Moderate
- VIF > 10: High (remove feature)

**Iterative Algorithm**:
1. Calculate VIF for all features
2. Remove feature with max VIF if VIF > 10
3. Recalculate VIF for remaining features
4. Repeat until all VIF < 10

**Tiebreaker**: Remove feature with lowest SHAP importance (preserve signal)

**Expected Removals**: 1-5 features per metric (lag variants, correlated pairs)

### 3. Granger Causality Testing (Module 4.4)

**Purpose**: Test if metric A temporally precedes metric B

**Theory**: A Granger-causes B if past values of A improve prediction of current B beyond what past B alone provides

**Implementation**:
```python
from statsmodels.tsa.stattools import grangercausalitytests

# Test lags 1-5 years
result = grangercausalitytests(
    data[[metric_a, metric_b]],
    maxlag=5,
    verbose=False
)

# Extract p-value from F-test
p_value = result[best_lag][0]['ssr_ftest'][1]
```

**Aggregation**: Median p-value across countries (robust to outliers)

**Expected Findings**: 8-15 significant relationships (p < 0.01)

### 4. Backdoor Adjustment (Module 4.5)

**Purpose**: Estimate causal effect of X on Y, controlling for confounders

**Theory**: Pearl's backdoor criterion
- Identify confounders Z that affect both X and Y
- Regress Y ~ X + Z
- Coefficient of X is causal effect

**Implementation**:
```python
from sklearn.linear_model import LinearRegression

# Prepare data: [treatment, confounders]
X_adjusted = X[[treatment_feature] + confounders]

# Fit regression
model = LinearRegression()
model.fit(X_adjusted, y)

# Causal effect = coefficient of treatment
causal_effect = model.coef_[0]
```

**Bootstrap Confidence Intervals**:
- Resample data 1,000 times with replacement
- Fit model on each sample
- CI = [2.5th percentile, 97.5th percentile]

**Expected Outcomes**: 60-80% significant effects (CI doesn't cross zero)

### 5. Do-Calculus (Module 4.6)

**Purpose**: Predict outcomes under intervention (not just observation)

**Theory**: Pearl's do-operator
- P(Y | do(X=x)) ≠ P(Y | X=x) in presence of confounding
- Do-calculus removes confounding edges, simulates forced intervention

**Simplified Implementation** (Linear case):
```python
def simulate_intervention(treatment, change_pct):
    # Direct effect
    effect = causal_effects[treatment]['effect'] * change_pct

    # Propagate through DAG (topological order)
    # (Full version: Multi-step propagation)

    # Spillover to other metrics
    for other_metric in inter_metric_graph.successors(target_metric):
        spillover = effect * inter_metric_coef[target_metric][other_metric]

    return {'direct_effect': effect, 'spillover': spillover}
```

**Example**:
- Intervention: health_expenditure +20%
- Direct effect: infant_mortality -5.8% [95% CI: -7.2%, -4.4%]
- Spillover: life_expectancy +2.1% [95% CI: +1.0%, +3.2%]

---

## Input/Output Contracts

### Module Handoffs

| From Module | To Module | Handoff Artifact | Schema |
|-------------|-----------|------------------|--------|
| **4.1** → **4.2** | Loaded data | `loaded_training_data.pkl` | `Dict[metric, DataFrame]` |
| **4.2** → **4.3** | Top drivers | `tier1_summary.json` | `{metric: {top_20_drivers: [(feat, weight)]}}` |
| **4.3** → **4.5** | VIF-filtered features | `vif_filtering_results.json` | `{metric: {retained_features: [str]}}` |
| **4.3** → **4.6** | Refined DAGs | `{metric}_pc_refined.pkl` | `CausalGraph` object |
| **4.4** → **4.6** | Inter-metric graph | `inter_metric_graph.pkl` | `nx.DiGraph` with edge weights |
| **4.5** → **4.6** | Causal effects | `causal_effects_quantified.json` | `{metric: {driver: {effect, ci_lower, ci_upper}}}` |
| **4.6** → **Phase 6** | Policy simulator | `policy_simulator_full.pkl` | `PolicySimulator` class |
| **4.7** → **4.8** | Validation status | `validation_report.json` | `{overall_status: "PASS/FAIL"}` |

### File Locations

**Primary Outputs**:
```
/models/
├── causal_graphs/
│   ├── tier1/
│   │   ├── mean_years_schooling_pc_refined.pkl
│   │   ├── infant_mortality_pc_refined.pkl
│   │   ├── undernourishment_pc_refined.pkl
│   │   ├── tier1_summary.json
│   │   ├── vif_filtering_results.json
│   │   └── causal_effects_quantified.json
│   ├── tier2/  # (Module 4.8)
│   ├── tier3/  # (Module 4.8)
│   ├── inter_metric_graph.pkl
│   ├── granger_causality.json
│   ├── var_results.json
│   ├── validation_report.json
│   ├── causal_effects_all_metrics.json  # Final
│   └── visualizations/
│       ├── mean_years_schooling_dag.png
│       ├── mean_years_schooling_effects.png
│       ├── ... (16 total PNG files)
│       └── inter_metric_graph.png
└── policy_simulator/
    ├── policy_simulator_full.pkl  # Final
    └── api_specification_full.json  # Final
```

---

## Validation Criteria

### Automated Tests (Module 4.7)

1. **DAG Acyclicity** (Mathematical requirement)
   - Test: `nx.is_directed_acyclic_graph(G)` for all 8 metrics
   - Pass: All graphs acyclic
   - Fail: If cycles detected → use FCI algorithm

2. **Effect Sign Consistency** (Statistical requirement)
   - Test: CI crosses zero for significant effects
   - Pass: All significant effects have CI[lower] × CI[upper] > 0
   - Fail: If inconsistencies → review confounders

3. **Effect Magnitude Reasonableness** (Domain knowledge)
   - Test: |effect| < 2.0 for normalized data
   - Pass: All effects within reasonable range
   - Fail: If |effect| > 2.0 → check for outliers/errors

4. **Literature Alignment** (Theoretical validation)
   - Test: Compare discovered signs to published research
   - Pass: ≥70% sign match
   - Fail: If <70% → investigate contradictions

5. **Simulation Reasonableness** (Practical validation)
   - Test: 10% intervention → |effect| < 100%
   - Pass: All simulations produce reasonable outputs
   - Fail: If unrealistic → check effect propagation logic

---

## Tier-Based Execution Strategy

### Why Tiered Approach?

**Rationale**: Phase 3 showed variable predictive performance (R²: 0.358-0.924). Starting with high-confidence metrics validates methodology before extending to weaker metrics.

### Tier Definitions

| Tier | Metrics | Test R² Range | Characteristics | PC Alpha |
|------|---------|---------------|-----------------|----------|
| **Tier 1** | mean_years_schooling, infant_mortality, undernourishment | 0.821-0.905 | Strong signal, high generalization | 0.05 (strict) |
| **Tier 2** | internet_users, gini, gdp_per_capita | 0.647-0.734 | Moderate signal, acceptable generalization | 0.05 |
| **Tier 3** | life_expectancy, homicide | 0.358-0.445 | Weak signal, low generalization | 0.10 (relaxed) |

### Tier-Specific Adjustments

**Tier 3 Modifications**:
- **Alpha relaxation**: 0.05 → 0.10 (more permissive independence tests)
- **Expected outcomes**: Fewer drivers (5-15 vs. 10-25), lower significance rates (30-50% vs. 60-80%)
- **Interpretation**: Flag as "exploratory" rather than "confirmatory"

---

## Parallelization Strategy

### Embarrassingly Parallel Operations

1. **Module 4.2** (PC Discovery):
   ```bash
   # 3 independent processes
   python phase4_pc_tier1.py --metric mean_years_schooling &
   python phase4_pc_tier1.py --metric infant_mortality &
   python phase4_pc_tier1.py --metric undernourishment &
   wait
   ```
   **Speedup**: 3× (45 min → 15 min)

2. **Modules 4.4 & 4.5** (Independent analyses):
   ```bash
   python phase4_granger_causality.py &
   python phase4_run_effect_quantification.py &
   wait
   ```
   **Speedup**: 2× (90 min → 45 min)

3. **Module 4.8** (Extension):
   ```bash
   for metric in internet_users gini gdp_per_capita life_expectancy homicide; do
       python phase4_extend_single_metric.py --metric $metric &
   done
   wait
   ```
   **Speedup**: 5× (120 min → 30 min)

### Total Speedup

- Sequential: 5-7 hours
- Parallelized: 3-4 hours (**40-50% reduction**)

---

## Critical Success Factors

### Must-Have Outcomes

1. **DAG Structure**: All 8 metrics have acyclic causal graphs
2. **Effect Quantification**: 80-160 total causal drivers (10-20 per metric)
3. **Inter-Metric Relationships**: 8-15 significant Granger-causal edges
4. **Policy Simulator**: Successfully simulates interventions for all 8 metrics
5. **Validation**: PASS status on all 5 automated tests
6. **Visualizations**: 17 publication-quality PNGs (16 DAGs/effects + 1 inter-metric)

### Quality Thresholds

- **Tier 1**: ≥70% significant effects, ≥70% literature alignment
- **Tier 2**: ≥60% significant effects, ≥60% literature alignment
- **Tier 3**: ≥30% significant effects, ≥40% literature alignment (exploratory)

---

## Phase 4 → Phase 6 Integration

### Deliverable Checklist

- [ ] **policy_simulator_full.pkl** - Pickled PolicySimulator with all 8 metrics
- [ ] **api_specification_full.json** - API schema for Flask integration
- [ ] **causal_effects_all_metrics.json** - Effect sizes for all drivers
- [ ] **16 visualization PNGs** - DAGs + effect plots for dashboard
- [ ] **inter_metric_graph.pkl** - Spillover network for visualization

### Flask Endpoints to Implement

1. **POST /api/simulate_intervention**
   - Input: `{target_metric, intervention_feature, change_pct, time_horizon, uncertainty}`
   - Output: `{direct_effect, spillover_effects, ci_lower, ci_upper, time_to_full_effect}`

2. **GET /api/available_interventions/<metric>**
   - Output: `{metric, interventions: [list of causal drivers]}`

3. **GET /api/causal_graph/<metric>**
   - Output: DAG visualization PNG

4. **GET /api/inter_metric_network**
   - Output: Inter-metric graph PNG

---

## Risk Mitigation

### Identified Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| PC produces zero edges | LOW | HIGH | Increase alpha to 0.10, verify feature variance |
| VIF removes all features | LOW | MED | Increase VIF threshold to 15 |
| Validation fails (cycles in DAG) | MED | HIGH | Use FCI algorithm (handles latent confounders) |
| Low literature alignment (<50%) | MED | MED | Document as novel findings, verify data quality |
| Simulation unrealistic outputs | LOW | HIGH | Add bounds checking, cap effects at ±200% |

---

## Documentation Artifacts

### For Research Communication

1. **Phase 4 Report** (to be created):
   - `/Documentation/phase_reports/phase4_report.md`
   - Methodology, results, validation outcomes

2. **Causal Graph Atlas**:
   - `/models/causal_graphs/visualizations/`
   - All 17 PNG visualizations

3. **Literature Validation Report**:
   - `/models/causal_graphs/tier1/literature_validation.json`
   - Comparison to published findings

### For Technical Handoff

1. **Module Instruction Files** (completed):
   - `/Documentation/Instructions/phase4_instructions/MODULE_4.*.md` (8 files)

2. **Integration Guide** (completed):
   - `/Documentation/Instructions/phase4_instructions/INTEGRATION_GUIDE.md`

3. **API Documentation** (auto-generated):
   - `/models/policy_simulator/api_specification_full.json`

---

## Contact & Support

**For questions about**:
- **PC algorithm**: See `MODULE_4.2_PC_DISCOVERY.md`
- **VIF filtering**: See `MODULE_4.3_VIF_REFINEMENT.md`
- **Policy simulation**: See `MODULE_4.6_POLICY_SIMULATOR.md`
- **Execution order**: See `INTEGRATION_GUIDE.md`

**Troubleshooting**: Refer to individual module markdown files for error handling sections.

---

**Phase 4 is complete when all 8 success criteria are met and validation_report.json shows PASS status.**
