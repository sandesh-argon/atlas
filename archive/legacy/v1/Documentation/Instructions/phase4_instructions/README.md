# PHASE 4 CAUSAL DISCOVERY - DOCUMENTATION INDEX

## Quick Start

**New to Phase 4?** Start here:

1. **Read**: [`ARCHITECTURE_SUMMARY.md`](ARCHITECTURE_SUMMARY.md) - Executive overview and dependency graph (10 min)
2. **Read**: [`INTEGRATION_GUIDE.md`](INTEGRATION_GUIDE.md) - Execution sequence and validation checkpoints (20 min)
3. **Execute**: Run `MODULE_4.1_SETUP.md` → Follow module sequence

**Experienced?** Jump to specific modules below.

---

## Documentation Structure

```
phase4_instructions/
├── README.md                      ← YOU ARE HERE
├── ARCHITECTURE_SUMMARY.md        ← START HERE (executive overview)
├── INTEGRATION_GUIDE.md           ← Execution roadmap & validation
├── MODULE_4.1_SETUP.md            ← Environment setup (5 min)
├── MODULE_4.2_PC_DISCOVERY.md     ← Causal discovery via PC algorithm (30-45 min)
├── MODULE_4.3_VIF_REFINEMENT.md   ← Multicollinearity removal (15 min)
├── MODULE_4.4_INTER_METRIC_ANALYSIS.md ← Metric→metric relationships (45-60 min)
├── MODULE_4.5_EFFECT_QUANTIFICATION.md ← Backdoor adjustment + CI (30 min)
├── MODULE_4.6_POLICY_SIMULATOR.md ← Do-calculus implementation (60 min)
├── MODULE_4.7_VALIDATION_VIZ.md   ← Quality assurance checkpoint (30 min)
└── MODULE_4.8_EXTENSION.md        ← Scale to all 8 metrics (90-120 min)
```

---

## Document Summaries

### 📋 ARCHITECTURE_SUMMARY.md
**Purpose**: High-level overview of Phase 4 architecture
**Contents**:
- Module dependency graph (visual)
- Algorithm descriptions (PC, VIF, Granger, backdoor adjustment, do-calculus)
- Input/output contracts
- Tier-based execution strategy
- Parallelization opportunities
- Risk mitigation

**When to read**: Before starting Phase 4 (executive overview)

---

### 🗺️ INTEGRATION_GUIDE.md
**Purpose**: Step-by-step execution roadmap
**Contents**:
- Critical path execution sequence
- Handoff validation checkpoints (verify each module's success)
- Rollback & recovery procedures
- End-to-end execution script
- Phase 4 → Phase 6 integration guide
- Troubleshooting common errors

**When to read**: During execution (reference guide)

---

### 🛠️ MODULE_4.1_SETUP.md
**Purpose**: Environment preparation and data loading
**Inputs**: Phase 3 models (8 LightGBM), SHAP importance, training data
**Outputs**: Loaded data structures, setup verification report
**Runtime**: 5 minutes
**Dependencies**: None (entry point)

**Key tasks**:
- Install causal-learn, pgmpy, networkx, graphviz
- Load 8 optimized models from `/models/causal_optimized/`
- Validate data integrity (feature counts, no NaN in targets)
- Create Tier 1/2/3 metric classification

---

### 🔍 MODULE_4.2_PC_DISCOVERY.md
**Purpose**: Discover causal graph structure via PC algorithm
**Inputs**: Training data (Tier 1: 3 metrics), SHAP importance
**Outputs**: Causal DAGs (10-50 edges), top 20 drivers per metric
**Runtime**: 30-45 minutes (sequential) | 15 minutes (parallel)
**Dependencies**: Module 4.1

**Key tasks**:
- Run PC algorithm with SHAP-weighted edge priors
- Fisher-Z test for conditional independence (alpha=0.05)
- Identify causal drivers (features with edges to target)
- Save causal graphs and driver rankings

**Parallelization**: 3 processes (one per Tier 1 metric)

---

### 🧹 MODULE_4.3_VIF_REFINEMENT.md
**Purpose**: Remove multicollinearity from discovered drivers
**Inputs**: Top 20 drivers from Module 4.2
**Outputs**: VIF-filtered features (15-18 retained), refined DAGs
**Runtime**: 15 minutes
**Dependencies**: Module 4.2

**Key tasks**:
- Calculate VIF for top 20 drivers
- Iteratively remove features with VIF > 10
- Re-run PC on VIF-filtered features
- Produce cleaner, non-redundant causal graphs

**Expected removals**: 1-5 features per metric (lag variants, correlated pairs)

---

### 🌐 MODULE_4.4_INTER_METRIC_ANALYSIS.md
**Purpose**: Discover causal relationships between QOL metrics
**Inputs**: Training data with all 8 QOL metrics
**Outputs**: Granger causality results, VAR coefficients, inter-metric graph
**Runtime**: 45-60 minutes
**Dependencies**: Module 4.1 (can run parallel with 4.3)

**Key tasks**:
- Granger causality testing (56 pairwise tests: 8×7)
- Vector Autoregression (VAR) modeling
- Build inter-metric directed graph (8 nodes, 8-15 edges)

**Expected findings**: education→GDP, GDP→health, undernourishment→infant_mortality

---

### 📊 MODULE_4.5_EFFECT_QUANTIFICATION.md
**Purpose**: Quantify causal effect sizes with confidence intervals
**Inputs**: VIF-filtered drivers (15-18 per metric)
**Outputs**: Causal effects with 95% CI (1,000 bootstrap iterations)
**Runtime**: 30 minutes
**Dependencies**: Module 4.3

**Key tasks**:
- Backdoor adjustment (regress Y ~ treatment + confounders)
- Bootstrap confidence intervals (1,000 iterations)
- Literature validation (compare signs to published research)

**Expected outcomes**: 60-80% significant effects, 70%+ literature alignment

---

### 🎯 MODULE_4.6_POLICY_SIMULATOR.md
**Purpose**: Implement do-calculus for policy intervention simulation
**Inputs**: Refined DAGs (4.3), inter-metric graph (4.4), causal effects (4.5)
**Outputs**: PolicySimulator class, API specification for Phase 6
**Runtime**: 60 minutes
**Dependencies**: Modules 4.3, 4.4, 4.5

**Key tasks**:
- Implement PolicySimulator class with do-calculus logic
- Simulate direct effects (within-metric)
- Simulate spillover effects (cross-metric)
- Test scenarios (e.g., health expenditure +20% → infant_mortality effect)
- Export API specification for dashboard integration

**Deliverable**: `policy_simulator_full.pkl` for Phase 6 Flask backend

---

### ✅ MODULE_4.7_VALIDATION_VIZ.md
**Purpose**: Quality assurance checkpoint before extending to all metrics
**Inputs**: All outputs from Modules 4.1-4.6
**Outputs**: Validation report (PASS/FAIL), 7 visualizations
**Runtime**: 30 minutes
**Dependencies**: All Modules 4.1-4.6

**Key tasks**:
- Run 5 automated tests (DAG acyclicity, effect sign consistency, etc.)
- Generate DAG visualizations (3 PNG)
- Generate effect plots with CI (3 PNG)
- Generate inter-metric network graph (1 PNG)

**Decision point**: PASS → Module 4.8 | FAIL → Fix issues

---

### 🚀 MODULE_4.8_EXTENSION.md
**Purpose**: Extend validated pipeline to all 8 metrics
**Inputs**: Validated Tier 1 results (Modules 4.1-4.7 PASS)
**Outputs**: Full causal knowledge base (8 metrics), complete simulator
**Runtime**: 90-120 minutes (sequential) | 30-40 minutes (parallel)
**Dependencies**: Module 4.7 (PASS status required)

**Key tasks**:
- Apply PC/VIF/Effect Quantification to Tier 2 (3 metrics) + Tier 3 (2 metrics)
- Use relaxed alpha (0.10) for Tier 3 weak metrics
- Update PolicySimulator with all 8 metrics
- Generate all visualizations (16 PNG total)

**Parallelization**: 5 processes (one per remaining metric)

---

## Execution Modes

### Option 1: Sequential (Beginner-Friendly)
```bash
cd <repo-root>/v1.0/Data/Scripts/phase4_modules
source ../../phase2_env/bin/activate

python phase4_setup.py                  # 4.1
python phase4_pc_tier1.py               # 4.2
python phase4_apply_vif.py              # 4.3
python phase4_granger_causality.py      # 4.4
python phase4_run_effect_quantification.py  # 4.5
python phase4_create_simulator.py       # 4.6
python phase4_validation_tests.py       # 4.7
python phase4_extend_pc_all_metrics.py  # 4.8
```
**Runtime**: 5-7 hours

### Option 2: Parallelized (Recommended)
```bash
# Use the master script
chmod +x run_phase4_full_pipeline.sh
./run_phase4_full_pipeline.sh
```
**Runtime**: 3-4 hours (40-50% faster)

### Option 3: Interactive (Advanced)
Execute modules individually, inspect outputs between steps:
```bash
python phase4_setup.py
# Inspect: /models/causal_graphs/setup_verification.json

python phase4_pc_tier1.py
# Inspect: /models/causal_graphs/tier1/tier1_summary.json

# Continue step-by-step...
```

---

## Quick Reference

### File Locations

**Inputs** (from Phase 3):
```
/models/causal_optimized/
├── model_lightgbm_{metric}.txt (8 files)
├── shap_importance_{metric}.csv (8 files)
└── model_metadata_master.json

/Data/Processed/normalized/train_normalized.csv
```

**Outputs** (for Phase 6):
```
/models/causal_graphs/
├── tier1/, tier2/, tier3/ (causal graphs by tier)
├── causal_effects_all_metrics.json (final)
└── visualizations/ (17 PNG files)

/models/policy_simulator/
├── policy_simulator_full.pkl (final)
└── api_specification_full.json (final)
```

### Validation Checkpoints

| After Module | Verify File | Expected Content |
|--------------|-------------|------------------|
| 4.1 | `setup_verification.json` | All 8 models loaded, feature counts match |
| 4.2 | `tier1_summary.json` | 10-50 edges per metric, 8-25 drivers |
| 4.3 | `vif_filtering_results.json` | 15-18 retained features, all VIF < 10 |
| 4.5 | `causal_effects_quantified.json` | 60-80% significant effects |
| 4.7 | `validation_report.json` | `overall_status: "PASS"` |
| 4.8 | `policy_simulator_full.pkl` | Simulator with 8 metrics |

### Runtime Estimates

| Module | Sequential | Parallelized | Speedup |
|--------|------------|--------------|---------|
| 4.1 | 5 min | 5 min | 1× |
| 4.2 | 45 min | 15 min | 3× |
| 4.3 | 15 min | 15 min | 1× |
| 4.4 & 4.5 | 90 min | 45 min | 2× |
| 4.6 | 60 min | 60 min | 1× |
| 4.7 | 30 min | 30 min | 1× |
| 4.8 | 120 min | 30 min | 4× |
| **Total** | **5-7 hours** | **3-4 hours** | **1.5-2×** |

---

## Troubleshooting

### Common Errors

1. **`ImportError: No module named 'causallearn'`**
   → Run: `pip install causal-learn==0.1.3.5`

2. **`ValueError: Input contains NaN`**
   → Ensure `.dropna()` applied in Module 4.2

3. **`LinAlgError: Singular matrix`**
   → Perfect multicollinearity; wait for Module 4.3 VIF filtering

4. **Validation fails: DAG contains cycles**
   → Use FCI algorithm instead of PC (handles latent confounders)

5. **Low literature alignment (<50%)**
   → Review specific contradictions; may indicate novel findings or data issues

### Where to Get Help

- **Algorithm questions**: See individual MODULE markdown files (detailed theory sections)
- **Execution issues**: See INTEGRATION_GUIDE.md (troubleshooting section)
- **Phase 3 integration**: See `/Documentation/phase_reports/phase3_report.md`

---

## Success Criteria

**Phase 4 is complete when**:

- [ ] All 8 metrics have refined causal graphs (DAGs)
- [ ] All 8 metrics have quantified causal effects (10-20 drivers each)
- [ ] Policy simulator successfully simulates interventions for all 8 metrics
- [ ] Validation report shows PASS status
- [ ] All 17 visualizations generated (16 DAGs/effects + 1 inter-metric)
- [ ] API specification valid and ready for Phase 6 Flask integration

---

## Next Steps

**After Phase 4 completion**:

1. **Integrate with Phase 6 Dashboard**:
   - Load `policy_simulator_full.pkl` in Flask backend
   - Implement `/api/simulate_intervention` endpoint
   - Display visualizations in "Causal Discovery" tab

2. **Create Documentation**:
   - Write Phase 4 Report (`/Documentation/phase_reports/phase4_report.md`)
   - Generate user guide for policy simulation interface

3. **Academic Deliverables**:
   - Prepare manuscript using causal graph visualizations
   - Compile literature validation results for Discussion section

---

## Module Reading Order

**Recommended sequence**:

1. **ARCHITECTURE_SUMMARY.md** (10 min) - Get big picture
2. **INTEGRATION_GUIDE.md** (20 min) - Understand execution flow
3. **MODULE_4.1_SETUP.md** (5 min) - Start hands-on
4. Execute modules sequentially, reading each markdown file before running
5. Refer back to INTEGRATION_GUIDE.md for validation checkpoints

**Total reading time**: ~2 hours (before execution)

---

## Contact & Feedback

For questions about Phase 4 documentation:
- Review individual module markdown files (detailed error handling sections)
- Check `/Documentation/phase_reports/` for methodology context
- Refer to original Phase 4 instructions: `/Documentation/Instructions/phase4_instructions.md`

**Last Updated**: 2025-10-23
**Phase 4 Version**: 1.0
**Documentation Status**: Complete (8 modules + 2 guides)
