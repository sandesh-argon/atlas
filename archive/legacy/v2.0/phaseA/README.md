# Phase A: Statistical Network Discovery

**Timeline**: Weeks 1-4 (14-21 days wall-clock time)

## Purpose

Extract validated causal signal with efficient filtering to create a directed acyclic graph (DAG) representing causal relationships between 4,000-6,000 development indicators.

## Steps Overview

### A0: Data Acquisition (8-12 hours)
**Input**: API access to 11 data sources
**Output**: ~5,000-6,000 variables (after coverage filters)
**Key Operations**:
- Fetch data from World Bank, WHO, UNESCO, UNICEF, V-Dem, QoG, IMF, OECD, PWT, WID, TI
- Apply initial filters: ≥80 countries, ≥10 years span, ≥0.80 per-country coverage, ≤0.70 missing rate
- Select optimal temporal window (likely 1990-2024, 34 years)

### A1: Missingness Sensitivity Analysis (12-18 hours)
**Input**: Raw data with missing values
**Output**: Optimal imputation configuration + 4,000-5,000 clean variables
**Key Operations**:
- Test 25 parallel configs (5 thresholds × 5 strategies)
- Multi-criteria scoring: coverage (25%), stability (30%), interpretability (25%), predictive (20%)
- Apply V1-validated imputation weighting (Tier 1-4 confidence system)

### A2: Granger Causality with Prefiltering (4-6 days)
**Input**: Clean variables from A1
**Output**: 30,000-80,000 temporally validated edges
**Key Operations**:
- **Critical**: Prefilter 6.2M → 200K candidate pairs using:
  - Correlation threshold (0.10 < |r| < 0.95)
  - Domain compatibility matrix (13×13)
  - Temporal precedence checks
  - Literature plausibility
- Run Granger tests at lags [1, 2, 3, 5] with FDR correction (q=0.05)
- Handle bidirectional edges (flag for A3 review)

### A3: Conditional Independence (2-4 days)
**Input**: Granger-validated edges from A2
**Output**: 10,000-30,000 structurally validated edges with backdoor sets
**Key Operations**:
- PC-Stable algorithm (α=0.001, Fisher-z test, temporal tiers as background knowledge)
- Keep edges validated by BOTH Granger AND conditional independence
- Identify backdoor adjustment sets using DoWhy
- Early stopping: Switch to GES if edges >50,000

### A4: Effect Size Quantification (2-3 days)
**Input**: Validated edges + backdoor sets from A3
**Output**: 2,000-8,000 causal edges with effect sizes
**Key Operations**:
- Backdoor adjustment regression (standardized β coefficients)
- Bootstrap 95% confidence intervals (1,000 iterations)
- Filter: Keep only |β| > 0.12 with CI not crossing zero

### A5: Interaction Discovery (3-5 days)
**Input**: Effect estimates from A4
**Output**: 50-200 validated interaction mechanisms
**Key Operations**:
- **Constrained search**: Test only top-25% mechanisms × priority outcomes (2M tests vs 12M)
- Likelihood ratio test: Model with interaction vs without
- Keep: p < 0.001 and |interaction_coef| > 0.15
- Validate against known interactions (e.g., health × education → life expectancy)

### A6: Hierarchical Layer Assignment (4-6 hours)
**Input**: Final causal DAG from A4-A5
**Output**: Nodes with layer labels (0-N), centrality scores
**Key Operations**:
- Topological sort for data-driven depth assignment
- Compute betweenness, PageRank, in/out degree
- Expected: 4-8 layers in hierarchy

## Success Criteria

- ✅ Variables: 4,000-6,000 after filters
- ✅ Edges: 2,000-10,000 with |β| > 0.15
- ✅ DAG validity: `nx.is_directed_acyclic_graph() == True`
- ✅ Bootstrap stability: >75% edge retention
- ✅ Literature reproduction: >70% of known relationships
- ✅ Holdout R²: >0.55 mean across outcomes

## Checkpoints

Save after each step:
- `A0_raw_data.pkl` (5-6K variables)
- `A1_optimal_config.pkl` (imputation strategy + clean data)
- `A2_granger_edges.pkl` (30-80K edges)
- `A3_pc_stable_graph.pkl` (DAG + backdoor sets)
- `A4_effect_estimates.pkl` (2-8K edges with β, CI)
- `A5_interactions.pkl` (50-200 synergies)
- `A6_hierarchy.pkl` (node metadata: layer, centrality)

## Critical V1 Lessons

**DON'T**:
- ❌ Test all 6.2M pairs → Use prefiltering (98% reduction)
- ❌ Accept all significant Granger results → Validate with PC-Stable
- ❌ Use global coverage only → Require within-country temporal density

**DO**:
- ✅ Use imputation confidence weighting (0.50-1.00 based on method)
- ✅ Keep self-disaggregations (female_literacy → literacy is valid)
- ✅ Apply saturation transforms BEFORE normalization
