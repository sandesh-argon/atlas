# PHASE 4 CAUSAL DISCOVERY - INTEGRATION GUIDE

## Overview

This guide provides the execution roadmap for Phase 4: Causal Discovery & Policy Simulation Framework. Phase 4 transforms Phase 3's predictive models into causal knowledge using constraint-based causal discovery (PC algorithm), quantifies causal effects, and builds a policy simulation framework for "what-if" scenario testing.

---

## Execution Sequence

### **Critical Path** (Sequential Execution Required)

```
MODULE 4.1 (Setup)
    ↓
MODULE 4.2 (PC Discovery - Tier 1)
    ↓
MODULE 4.3 (VIF Refinement)
    ↓
MODULE 4.4 (Inter-Metric) ←→ MODULE 4.5 (Effect Quantification)
    ↓                                  ↓
    └──────────→ MODULE 4.6 (Policy Simulator)
                        ↓
                MODULE 4.7 (Validation)
                        ↓
                MODULE 4.8 (Extension to All Metrics)
```

### **Parallelization Opportunities**

1. **Module 4.2**: PC algorithm can run in parallel for 3 Tier 1 metrics
   ```bash
   # Terminal 1
   python phase4_pc_tier1.py --metric mean_years_schooling

   # Terminal 2
   python phase4_pc_tier1.py --metric infant_mortality

   # Terminal 3
   python phase4_pc_tier1.py --metric undernourishment
   ```

2. **Modules 4.4 & 4.5**: Independent, can run simultaneously
   ```bash
   # Terminal 1
   python phase4_granger_causality.py &

   # Terminal 2
   python phase4_run_effect_quantification.py &
   wait
   ```

3. **Module 4.8**: Extension can parallelize by metric (5 processes)

---

## Module Execution Details

### MODULE 4.1: Environment Setup (5 minutes)

**Purpose**: Install libraries, load Phase 3 outputs, verify data integrity

**Input Requirements**:
- Phase 3 complete (93 models trained)
- All files in `/models/causal_optimized/`

**Commands**:
```bash
cd <repo-root>/v1.0/Data/Scripts/phase4_modules

# Activate environment
source ../../phase2_env/bin/activate

# Install causal discovery libraries
pip install causal-learn==0.1.3.5 pgmpy==0.1.23 networkx==3.2 graphviz==0.20.1 statsmodels==0.14.1

# Run setup
python phase4_setup.py
```

**Success Criteria**:
- [ ] All 8 models load successfully
- [ ] SHAP importance files present
- [ ] Feature counts match Phase 3 (23-52 per metric)
- [ ] `setup_verification.json` shows all checks passed

**Output**: `/models/causal_graphs/setup_verification.json`

---

### MODULE 4.2: PC Causal Discovery - Tier 1 (30-45 minutes)

**Purpose**: Discover causal DAGs for high-confidence metrics using PC algorithm

**Input Requirements**:
- Module 4.1 complete
- Tier 1 metrics: mean_years_schooling, infant_mortality, undernourishment

**Commands** (Sequential):
```bash
python phase4_pc_tier1.py
```

**Commands** (Parallel - faster):
```bash
# Run 3 processes simultaneously
python phase4_pc_tier1.py --metric mean_years_schooling &
python phase4_pc_tier1.py --metric infant_mortality &
python phase4_pc_tier1.py --metric undernourishment &
wait
```

**Success Criteria**:
- [ ] PC completes for all 3 metrics without errors
- [ ] Each metric: 10-50 edges discovered
- [ ] Each metric: 8-25 causal drivers identified
- [ ] DAGs are acyclic (verify with `nx.is_directed_acyclic_graph`)

**Output**:
- `/models/causal_graphs/tier1/{metric}_pc_graph.pkl` (3 files)
- `/models/causal_graphs/tier1/tier1_summary.json`

---

### MODULE 4.3: VIF Filtering & Refinement (15 minutes)

**Purpose**: Remove multicollinearity from discovered drivers, re-run PC on cleaned features

**Input Requirements**:
- Module 4.2 complete
- Top 20 drivers per metric from PC

**Commands**:
```bash
python phase4_vif_filter.py
python phase4_apply_vif.py
```

**Success Criteria**:
- [ ] VIF filtering removes 1-5 features per metric
- [ ] All retained features have VIF < 10
- [ ] Re-running PC succeeds for all 3 metrics
- [ ] Refined graphs have 5-20% fewer edges (cleaner)

**Output**:
- `/models/causal_graphs/tier1/vif_filtering_results.json`
- `/models/causal_graphs/tier1/{metric}_pc_refined.pkl` (3 files)
- `/models/causal_graphs/tier1/{metric}_vif_report.csv` (3 files)

---

### MODULE 4.4: Inter-Metric Causal Analysis (45-60 minutes)

**Purpose**: Discover causal relationships between QOL metrics (e.g., education→GDP)

**Input Requirements**:
- Module 4.1 complete (can run in parallel with 4.3)
- Training data with all 8 QOL metrics

**Commands**:
```bash
python phase4_granger_causality.py    # 30 min
python phase4_var_analysis.py         # 15 min
python phase4_build_inter_metric_graph.py  # 5 min
```

**Success Criteria**:
- [ ] Granger tests complete for all 56 pairwise combinations (8×7)
- [ ] VAR model converges with optimal lag 1-3
- [ ] Find 8-15 significant Granger-causal relationships (p < 0.01)
- [ ] Key relationships confirmed: education→GDP, GDP→health, undernourishment→infant_mortality

**Output**:
- `/models/causal_graphs/granger_causality.json`
- `/models/causal_graphs/var_results.json`
- `/models/causal_graphs/var_lag1_coefficients.csv`
- `/models/causal_graphs/inter_metric_graph.pkl`
- `/models/causal_graphs/inter_metric_edges.csv`

---

### MODULE 4.5: Causal Effect Quantification (30 minutes)

**Purpose**: Quantify causal effect sizes with bootstrapped confidence intervals

**Input Requirements**:
- Module 4.3 complete (VIF-filtered drivers)
- Module 4.1 complete (training data)

**Commands**:
```bash
python phase4_quantify_effects.py
python phase4_run_effect_quantification.py  # Main execution
python phase4_literature_validation.py
```

**Success Criteria**:
- [ ] Causal effects quantified for top 10 drivers per metric (30 total)
- [ ] Bootstrap iterations: 1,000 per effect
- [ ] 60-80% of effects are statistically significant (CI doesn't cross zero)
- [ ] Effect signs match theoretical expectations
- [ ] Literature validation: 70%+ consistency

**Output**:
- `/models/causal_graphs/tier1/causal_effects_quantified.json`
- `/models/causal_graphs/tier1/{metric}_causal_effects.csv` (3 files)
- `/models/causal_graphs/tier1/literature_validation.json`

---

### MODULE 4.6: Policy Simulation Framework (60 minutes)

**Purpose**: Implement do-calculus for policy intervention simulation

**Input Requirements**:
- Module 4.3 complete (refined causal graphs)
- Module 4.4 complete (inter-metric graph)
- Module 4.5 complete (quantified effects)

**Commands**:
```bash
# Create PolicySimulator class
python policy_simulator.py  # Class definition

# Instantiate and test
python phase4_create_simulator.py
python phase4_test_simulator.py

# Export for Phase 6
python phase4_export_api.py
```

**Success Criteria**:
- [ ] PolicySimulator class implements all core methods
- [ ] Test scenarios run successfully for 3 Tier 1 metrics
- [ ] Simulation results have reasonable magnitudes
- [ ] Confidence intervals are non-empty
- [ ] Spillover effects detected (from inter-metric graph)
- [ ] API specification valid JSON

**Output**:
- `/Data/Scripts/phase4_modules/policy_simulator.py`
- `/models/policy_simulator/policy_simulator.pkl`
- `/models/policy_simulator/api_specification.json`
- `/models/policy_simulator/test_scenarios_results.json`

---

### MODULE 4.7: Validation & Visualization (30 minutes)

**Purpose**: Quality assurance checkpoint before extending to all metrics

**Input Requirements**:
- All Modules 4.1-4.6 complete

**Commands**:
```bash
python phase4_validation_tests.py
python phase4_visualize_dags.py
python phase4_visualize_effects.py
python phase4_visualize_inter_metric.py
```

**Success Criteria**:
- [ ] Validation report shows PASS status
- [ ] All 5 tests pass: DAG acyclicity, effect sign consistency, magnitude reasonableness, literature alignment, simulation bounds
- [ ] 6 visualizations generated (3 DAGs + 3 effect plots + 1 inter-metric)
- [ ] Visualizations are publication-quality (300 DPI)

**Output**:
- `/models/causal_graphs/validation_report.json`
- `/models/causal_graphs/visualizations/{metric}_dag.png` (3 files)
- `/models/causal_graphs/visualizations/{metric}_effects.png` (3 files)
- `/models/causal_graphs/visualizations/inter_metric_graph.png`

**Decision Point**:
- If validation PASS → Proceed to Module 4.8
- If validation FAIL → Review and fix issues before extending

---

### MODULE 4.8: Extension to All 8 Metrics (90-120 minutes)

**Purpose**: Apply validated pipeline to remaining 5 metrics (Tier 2 + Tier 3)

**Input Requirements**:
- Module 4.7 validation PASS
- All previous modules complete

**Commands** (Sequential):
```bash
python phase4_extension_prerequisite.py  # Verify Tier 1 validation
python phase4_extend_pc_all_metrics.py   # PC for Tier 2 & 3
python phase4_extend_vif_all_metrics.py  # VIF filtering
python phase4_extend_effects_all_metrics.py  # Effect quantification
python phase4_extend_simulator.py  # Update simulator
python phase4_extend_visualizations.py  # Generate viz for all metrics
```

**Commands** (Parallel by Metric - faster):
```bash
# Launch 5 processes for Tier 2 & 3 metrics
for metric in internet_users gini gdp_per_capita life_expectancy homicide; do
    python phase4_extend_single_metric.py --metric $metric &
done
wait

# Consolidate results
python phase4_consolidate_all_metrics.py
```

**Success Criteria**:
- [ ] PC discovery completes for all 5 remaining metrics
- [ ] VIF filtering applied to all 8 metrics
- [ ] Causal effects quantified for all 8 metrics
- [ ] Full policy simulator created
- [ ] 16 visualizations generated (8 DAGs + 8 effect plots)

**Output**:
- `/models/causal_graphs/all_metrics_summary.json`
- `/models/causal_graphs/vif_filtering_all_metrics.json`
- `/models/causal_graphs/causal_effects_all_metrics.json`
- `/models/policy_simulator/policy_simulator_full.pkl`
- `/models/policy_simulator/api_specification_full.json`
- `/models/causal_graphs/visualizations/{metric}_dag.png` (8 files)
- `/models/causal_graphs/visualizations/{metric}_effects.png` (8 files)

---

## Handoff Validation Checkpoints

### Checkpoint 1: After Module 4.3 (VIF Refinement)

**Verify**:
```bash
ls <repo-root>/v1.0/models/causal_graphs/tier1/

# Expected files:
# - mean_years_schooling_pc_refined.pkl
# - infant_mortality_pc_refined.pkl
# - undernourishment_pc_refined.pkl
# - vif_filtering_results.json
```

**Validation**:
```python
import json
with open('<repo-root>/v1.0/models/causal_graphs/tier1/vif_filtering_results.json') as f:
    vif = json.load(f)
for metric, data in vif.items():
    print(f"{metric}: {data['num_retained']} retained, {data['num_removed']} removed")
```

### Checkpoint 2: After Module 4.5 (Effect Quantification)

**Verify**:
```bash
cat <repo-root>/v1.0/models/causal_graphs/tier1/causal_effects_quantified.json | head -50
```

**Validation**:
```python
import json
with open('<repo-root>/v1.0/models/causal_graphs/tier1/causal_effects_quantified.json') as f:
    effects = json.load(f)

for metric, drivers in effects.items():
    sig_count = sum(1 for d in drivers.values() if d['significant'])
    print(f"{metric}: {sig_count}/{len(drivers)} significant effects")
```

### Checkpoint 3: After Module 4.7 (Validation)

**Verify**:
```bash
cat <repo-root>/v1.0/models/causal_graphs/validation_report.json
```

**Validation**:
```python
import json
with open('<repo-root>/v1.0/models/causal_graphs/validation_report.json') as f:
    report = json.load(f)

print(f"Overall Status: {report['overall_status']}")
for test, result in report['tests'].items():
    status = "✓" if result else "✗"
    print(f"{status} {test}")
```

**Critical**: Do NOT proceed to Module 4.8 unless status = PASS

### Checkpoint 4: After Module 4.8 (Extension)

**Verify**:
```bash
ls <repo-root>/v1.0/models/policy_simulator/

# Expected files:
# - policy_simulator_full.pkl
# - api_specification_full.json
```

**Validation**:
```python
import pickle
with open('<repo-root>/v1.0/models/policy_simulator/policy_simulator_full.pkl', 'rb') as f:
    simulator = pickle.load(f)

api_spec = simulator.export_for_dashboard()
print(f"Available Metrics: {len(api_spec['available_metrics'])}")
assert len(api_spec['available_metrics']) == 8, "Not all metrics loaded!"

for metric, interventions in api_spec['available_interventions'].items():
    print(f"{metric}: {len(interventions)} interventions")
```

---

## Rollback & Recovery

### Rollback Scenarios

1. **Module 4.2 produces zero edges**:
   - **Cause**: Alpha too strict (0.05) for data
   - **Fix**: Increase alpha to 0.10 in `phase4_pc_tier1.py`
   - **Rollback**: Delete `tier1/*.pkl`, re-run Module 4.2

2. **Module 4.3 removes all features (VIF too aggressive)**:
   - **Cause**: Threshold too low (10)
   - **Fix**: Increase VIF threshold to 15
   - **Rollback**: Delete `vif_filtering_results.json`, re-run Module 4.3

3. **Module 4.5 shows low significant effects (<50%)**:
   - **Cause**: Bootstrap variance too high or weak true effects
   - **Fix**: Increase bootstrap iterations to 5,000
   - **Rollback**: Delete `causal_effects_quantified.json`, re-run Module 4.5

4. **Module 4.7 validation FAILS**:
   - **Investigation**: Review specific failed tests
   - **Fix**: Address root cause (e.g., cycles in DAG → use FCI algorithm)
   - **Rollback**: Re-run failed modules after fixes

### Recovery Commands

```bash
# Clean Tier 1 outputs (start Module 4.2 fresh)
rm <repo-root>/v1.0/models/causal_graphs/tier1/*.pkl
rm <repo-root>/v1.0/models/causal_graphs/tier1/*.json

# Clean VIF outputs (restart Module 4.3)
rm <repo-root>/v1.0/models/causal_graphs/tier1/*vif*

# Clean effect quantification (restart Module 4.5)
rm <repo-root>/v1.0/models/causal_graphs/tier1/causal_effects_quantified.json

# Full Phase 4 reset (CAUTION)
rm -rf <repo-root>/v1.0/models/causal_graphs/*
rm -rf <repo-root>/v1.0/models/policy_simulator/*
# Then re-run from Module 4.1
```

---

## End-to-End Execution Script

**File**: `run_phase4_full_pipeline.sh`

```bash
#!/bin/bash
set -e  # Exit on error

echo "==========================================="
echo "PHASE 4: CAUSAL DISCOVERY - FULL PIPELINE"
echo "==========================================="

cd <repo-root>/v1.0/Data/Scripts/phase4_modules
source ../../phase2_env/bin/activate

# Module 4.1: Setup (5 min)
echo "\n[1/8] Running Module 4.1: Environment Setup"
python phase4_setup.py

# Module 4.2: PC Discovery (30-45 min)
echo "\n[2/8] Running Module 4.2: PC Causal Discovery (Tier 1)"
python phase4_pc_tier1.py

# Module 4.3: VIF Refinement (15 min)
echo "\n[3/8] Running Module 4.3: VIF Filtering"
python phase4_vif_filter.py
python phase4_apply_vif.py

# Module 4.4 & 4.5: Run in parallel (60 min combined)
echo "\n[4-5/8] Running Modules 4.4 & 4.5 in Parallel"
python phase4_granger_causality.py &
PID1=$!
python phase4_run_effect_quantification.py &
PID2=$!
wait $PID1 $PID2

python phase4_var_analysis.py
python phase4_build_inter_metric_graph.py
python phase4_literature_validation.py

# Module 4.6: Policy Simulator (60 min)
echo "\n[6/8] Running Module 4.6: Policy Simulator"
python phase4_create_simulator.py
python phase4_test_simulator.py

# Module 4.7: Validation (30 min)
echo "\n[7/8] Running Module 4.7: Validation & Visualization"
python phase4_validation_tests.py

# Check validation status
VALIDATION_STATUS=$(python -c "
import json
with open('<repo-root>/v1.0/models/causal_graphs/validation_report.json') as f:
    print(json.load(f)['overall_status'])
")

if [ "$VALIDATION_STATUS" != "PASS" ]; then
    echo "✗ ERROR: Validation failed. Review validation_report.json"
    exit 1
fi

python phase4_visualize_dags.py
python phase4_visualize_effects.py
python phase4_visualize_inter_metric.py

# Module 4.8: Extension (90-120 min)
echo "\n[8/8] Running Module 4.8: Extension to All Metrics"
python phase4_extension_prerequisite.py
python phase4_extend_pc_all_metrics.py
python phase4_extend_vif_all_metrics.py
python phase4_extend_effects_all_metrics.py
python phase4_extend_simulator.py

echo "\n==========================================="
echo "✓ PHASE 4 COMPLETE"
echo "==========================================="
echo "Outputs:"
echo "  - Causal graphs: /models/causal_graphs/"
echo "  - Policy simulator: /models/policy_simulator/policy_simulator_full.pkl"
echo "  - API spec: /models/policy_simulator/api_specification_full.json"
echo "  - Visualizations: /models/causal_graphs/visualizations/"
```

**Usage**:
```bash
chmod +x run_phase4_full_pipeline.sh
./run_phase4_full_pipeline.sh
```

---

## Phase 4 → Phase 6 Integration

### Deliverables for Dashboard

1. **Policy Simulator** (pickled Python object):
   - `/models/policy_simulator/policy_simulator_full.pkl`
   - Flask backend loads this for `/api/simulate_intervention` endpoint

2. **API Specification** (JSON):
   - `/models/policy_simulator/api_specification_full.json`
   - Frontend reads this to populate intervention dropdowns

3. **Visualizations** (PNG files):
   - 8 DAG plots: Display in "Causal Discovery" tab
   - 8 Effect plots: Display in "Driver Analysis" tab
   - 1 Inter-metric graph: Display in "Spillover Network" tab

4. **Causal Effects** (JSON):
   - `/models/causal_graphs/causal_effects_all_metrics.json`
   - Frontend uses this for "Effect Size" tooltips

### Flask Integration Example

```python
from flask import Flask, request, jsonify
import pickle

app = Flask(__name__)

# Load simulator on startup
with open('models/policy_simulator/policy_simulator_full.pkl', 'rb') as f:
    simulator = pickle.load(f)

@app.route('/api/simulate_intervention', methods=['POST'])
def simulate():
    data = request.json

    try:
        result = simulator.simulate_intervention(
            target_metric=data['target_metric'],
            intervention_feature=data['intervention_feature'],
            change_pct=float(data['change_pct']),
            time_horizon=int(data.get('time_horizon', 5)),
            uncertainty=data.get('uncertainty', True)
        )
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/api/available_interventions/<metric>', methods=['GET'])
def get_interventions(metric):
    interventions = simulator.get_available_interventions(metric)
    return jsonify({'metric': metric, 'interventions': interventions})

if __name__ == '__main__':
    app.run(debug=True, port=5000)
```

---

## Estimated Total Runtime

| Execution Mode | Runtime |
|----------------|---------|
| **Sequential** | 5-7 hours |
| **Parallelized** | 3-4 hours |

**Parallelization Breakdown**:
- Module 4.2: 3 processes → 15 min (vs. 45 min sequential)
- Modules 4.4 & 4.5: 2 processes → 45 min (vs. 90 min sequential)
- Module 4.8: 5 processes → 30 min (vs. 120 min sequential)

---

## Troubleshooting

### Common Errors & Solutions

1. **`ImportError: No module named 'causallearn'`**:
   - **Fix**: `pip install causal-learn==0.1.3.5`

2. **`ValueError: Input contains NaN`**:
   - **Cause**: Missing data in features
   - **Fix**: Ensure `.dropna()` applied to training data in Module 4.2

3. **`LinAlgError: Singular matrix`**:
   - **Cause**: Perfect multicollinearity in features
   - **Fix**: Run VIF filtering (Module 4.3) before analysis

4. **`AssertionError: Graph contains cycles`**:
   - **Cause**: PC failed to fully orient edges
   - **Fix**: Use FCI algorithm instead of PC (handles latent confounders)

5. **Validation fails: Low literature alignment (<70%)**:
   - **Investigation**: Review specific contradictions
   - **Fix**: May indicate novel findings or data quality issues

---

## Success Metrics

**Phase 4 is complete when**:

- [ ] All 8 QOL metrics have refined causal graphs
- [ ] All 8 metrics have quantified causal effects (top 10 drivers each)
- [ ] Policy simulator successfully simulates interventions for all 8 metrics
- [ ] Validation report shows PASS status
- [ ] All visualizations generated (16 PNGs + 1 inter-metric)
- [ ] API specification valid and ready for Phase 6

**Expected Outputs**:
- ~80-160 total causal drivers across 8 metrics (10-20 per metric)
- 8-15 inter-metric causal relationships
- Policy simulator with 64-80 total intervention options (8 metrics × 8-10 drivers)

---

## Next Steps (Phase 6)

After Phase 4 completion:

1. **Integrate Policy Simulator into Flask Backend**
   - Mount `/api/simulate_intervention` endpoint
   - Add `/api/available_interventions` endpoint

2. **Build Frontend Dashboard**
   - Intervention slider component
   - Effect visualization (bar charts with CI)
   - Spillover network diagram (D3.js)
   - Causal graph explorer (interactive DAG)

3. **Documentation**
   - User guide for policy simulation
   - Interpretation guide for causal effects
   - Technical API documentation

---

**For questions or issues, refer to**:
- Module-specific instruction files: `/Documentation/Instructions/phase4_instructions/MODULE_*.md`
- Phase 4 original instructions: `/Documentation/Instructions/phase4_instructions.md`
- Phase reports: `/Documentation/phase_reports/`
