# V3.0 Implementation Checklist

**Project:** Global Causal Discovery System - V3.0 Temporal Dynamics & Policy Simulation
**Timeline:** 7-9 weeks (part-time) or 3-4 weeks (full-time)
**Output:** REST API + 217 country-specific graphs + intervention simulator

---

## Prerequisites

Before starting, verify access to V2.0 and V2.1 outputs:

- [x] V2.1 unified graph (2,583 nodes, 7,368 causal edges)
- [x] V2.1 node metadata (SHAP values, domain assignments)
- [x] V2.0 country-year panel data (217 countries × 34 years × 2,500 variables)
- [x] V2.0 data quality metadata (missingness, imputation flags)

**Data Files (from V2.1 exports):**
- `v21_nodes.csv` - 2,583 nodes with hierarchy
- `v21_causal_edges.csv` - 7,368 edges (standardized weights 0-1)
- `v21_panel_data_for_v3.parquet` - Panel data (68MB)
- `v21_data_quality.csv` - 202 countries with coverage stats

---

## Schema Compatibility (V2.1 Visualization)

V3.0 outputs MUST be compatible with V2.1 visualization JSON schema.

### Required Node Fields
| Field | Type | Description |
|-------|------|-------------|
| id | string | Unique identifier |
| label | string | Human-readable name |
| description | string | Plain English description |
| layer | int | 0=root, 1-5=hierarchy levels |
| node_type | string | root/outcome_category/domain/indicator |
| domain | string | One of 9 QoL domains |
| shap_importance | float | ML importance score |
| in_degree / out_degree | int | Edge counts |
| parent / children | string/array | Hierarchy links |

### Required Edge Fields
| Field | Type | Description |
|-------|------|-------------|
| source | string | Source node ID |
| target | string | Target node ID |
| weight | float | Standardized beta (compatibility alias) |
| relationship | string | "causal" or "hierarchical" |

### V3.0 Additional Edge Fields
| Field | Type | Description |
|-------|------|-------------|
| beta | float | Country-specific coefficient |
| ci_lower / ci_upper | float | Bootstrap confidence interval |
| global_beta | float | V2.1 global weight (fallback) |
| data_available | bool | Whether country had data |

**See:** `docs/SCHEMA_COMPATIBILITY.md` for full mapping

---

## Phase 0: Project Setup (Day 1) ✅ COMPLETE

### Task 0.1: Create Directory Structure
- [x] Create `v3.0/` workspace
- [x] Create `data/raw/`, `data/processed/`, `data/country_graphs/`
- [x] Create `scripts/phaseA/`, `scripts/phaseB/`, etc. (organized by phase)
- [x] Create `outputs/validation/`, `outputs/figures/`, `outputs/reports/`
- [x] Create `api/endpoints/`, `api/models/`, `api/utils/`
- [x] Create `docs/` for additional documentation

---

### Task 0.2: Environment Setup
- [x] Create `requirements.txt` with dependencies
- [x] Create Python virtual environment (`venv/`)
- [x] Install dependencies (numpy, pandas, scikit-learn, statsmodels, fastapi, etc.)
- [x] Verify imports work

---

### Task 0.3: Import V2.0 and V2.1 Data
- [x] Import V2.1 exports from `v2.1/outputs/v3_exports/`
- [x] `data/raw/v21_nodes.csv` - 2,583 nodes
- [x] `data/raw/v21_causal_edges.csv` - 7,368 edges (standardized weights)
- [x] `data/raw/v21_panel_data_for_v3.parquet` - 68MB panel data
- [x] `data/raw/v21_data_quality.csv` - 202 countries

---

## Phase A: Country-Specific Graph Estimation (Weeks 1-2)

### Task A.1: Split Panel Data by Country ✅
- [x] Create `scripts/phaseA/A1_split_panel/split_by_country.py`
- [x] Load panel data (18.3M rows, 893 country codes, 3,122 indicators)
- [x] Filter to 202 modern countries with sufficient data
- [x] Split into 202 country-specific parquet files
- [x] Save to `data/processed/countries/`
- [x] Handle "/" in country names (Burma/Myanmar → Burma_Myanmar)

**Verification:**
- [x] 202 `.parquet` files in `data/processed/countries/`
- [x] USA.parquet, Rwanda.parquet exist

---

### Task A.2: Country-Specific Graph Estimation
- [x] Create `scripts/phaseA/A2_estimate_graphs/estimate_country_graphs.py`
- [x] Implement Ridge regression for V2.1 edge re-estimation
- [x] Add bootstrap confidence intervals (100 samples)
- [x] Parallel processing with joblib (10 cores)
- [x] Checkpointing every 20 countries
- [x] Resume capability (skip already processed)

**Runtime:** ~50 minutes with 10 cores, 100 bootstrap samples

**Verification:**
- [x] 202 `.json` files in `data/country_graphs/`
- [x] Each JSON has: country_code, n_edges, n_edges_with_data, edges[]
- [x] Each edge has: source, target, beta, ci_lower, ci_upper, global_beta, data_available

**HUMAN VERIFICATION STEP:** Review sample country graphs (5-10 countries) before proceeding.

---

### Task A.3: Validate Country Graphs
- [x] Create `scripts/phaseA/A3_validate_graphs/validate_all_graphs.py`
- [x] Check all graphs are DAGs (no cycles)
- [x] Compute graph similarity across countries
- [x] Cluster countries by causal structure
- [x] Generate similarity matrix plot

**Verification:**
- [x] `outputs/validation/country_graph_validation.csv` exists
- [x] All countries show `is_dag = True`
- [x] `outputs/validation/country_clusters.csv` exists
- [x] `outputs/figures/country_similarity_matrix.png` created

---

### Task A.4: Critical Validations ✅
Run these 4 critical validations before proceeding:

- [x] **#1 Edge Sign Consistency** - ✅ PASS
- [x] **#2 Indicator Coverage** - ⚠️ 46 indicators <30% (acceptable)
- [x] **#3 Extreme Beta Audit** - ✅ PASS (0 edges with |β| > 5)
- [x] **#4 Beta Variance** - ⚠️ Mean CV 9.15 (expected for political indicators)

**See:** `outputs/validation/PHASE_A_VALIDATION_REPORT.md`

---

### Task A.5: Export V2.1-Compatible Format (DEFERRED)
Deferred to Phase D (API Development) - will implement as API endpoint.

**PHASE A COMPLETE** - Ready for Phase B

---

## Phase B: Intervention Propagation Algorithm ✅ COMPLETE

### Task B.1: Implement Saturation Functions ✅
- [x] `scripts/phaseB/B1_saturation/saturation_functions.py`
- [x] `sigmoid_saturation()` - GDP-like indicators
- [x] `hard_cap_saturation()` - Rates (0-100%)
- [x] `linear_diminishing_returns()` - Spending effectiveness
- [x] Indicator-specific config mapping
- [x] All tests pass

---

### Task B.2: Implement Intervention Propagation ✅
- [x] `scripts/phaseB/B2_propagation/intervention_propagation.py`
- [x] `propagate_intervention()` - Core algorithm
- [x] Saturation applied at each step
- [x] Convergence detection (threshold-based)
- [x] Uncertainty propagation (CI bounds)
- [x] All tests pass

---

### Task B.3: Build Simulation Runner ✅
- [x] `scripts/phaseB/B3_simulation/simulation_runner.py`
- [x] `load_country_data()` - Loads graph + baseline values
- [x] `run_simulation()` - End-to-end pipeline
- [x] Pretty-printed output formatting
- [x] JSON export for results

**Test Results:**
- Australia simulation: 98 indicators affected, 10 iterations, converged
- Rwanda simulation: Results saved to `outputs/simulations/`

**PHASE B COMPLETE** - Ready for Phase C (Temporal Dynamics) or Phase D (API)

---

## Phase C: Temporal Dynamics ✅ COMPLETE

### Task C.1: Estimate Lag Structures ✅
- [x] Create `scripts/phaseC/C1_lag_estimation/estimate_lags.py`
- [x] Implement Granger causality tests for lag estimation
- [x] Parallel processing (10 cores)
- [x] Checkpointing every 10 countries
- [x] Run lag estimation for all 204 countries

**Runtime:** ~6 minutes with 10 cores

**Results:**
- 198/203 graphs have lag data (97.5%)
- 1,458,864 edges with lags
- 304,305 significant lags (20.9%)
- Lag distribution: 1yr (35.5%), 2yr (19.1%), 3yr (13.7%), 4yr (13.7%), 5yr (17.9%)

**Note:** Lag data stored directly in country graphs (not separate files)

---

### Task C.2: Temporal Simulation ✅
- [x] Create `scripts/phaseC/C2_temporal_simulation/temporal_simulation.py`
- [x] `propagate_temporal()` - Year-by-year propagation with lags
- [x] `run_temporal_simulation()` - End-to-end pipeline
- [x] 10-year horizon projections
- [x] Effects grow over time due to lagged propagation

**Test Results:**
- Australia: Year 0 → 1 affected, Year 10 → 9 affected
- Rwanda: Year 0 → 1 affected, Year 10 → 20 affected
- Mean simulation time: 0.82s (target <5s)

---

### Task C.3: Airtight Validation ✅
- [x] `validate_lag_reasonableness.py` - Domain knowledge check
- [x] `validate_temporal_consistency.py` - No spikes/crashes
- [x] `validate_lag_consistency.py` - Cross-country CV ≤ 1.0
- [x] `validate_zero_lag_edges.py` - Fast/slow effect patterns
- [x] `validate_temporal_edge_cases.py` - Boundary conditions
- [x] `benchmark_temporal_performance.py` - All <5s target

**Results (6/6 PASSED):**
| Validation | Status |
|------------|--------|
| Lag Reasonableness | PASS (0.0% suspicious) |
| Temporal Consistency | PASS |
| Cross-Country Consistency | PASS (all CV ≤ 1.0) |
| Zero-Lag Edges | PASS |
| Temporal Edge Cases | PASS (all 5 tests) |
| Performance Benchmark | PASS (mean 0.80s) |

**Performance Highlights:**
- 19 simulations tested
- Mean: 0.80s, Max: 0.82s
- Stress test (20yr, 10 interventions): 0.82s

**See:** `outputs/validation/PHASE_C_AIRTIGHT_VALIDATION.md`

**PHASE C COMPLETE** - Ready for Phase D (API Development)

---

## Phase D: API Development (Week 7)

### Task D.1: Create FastAPI Backend
- [ ] Create `api/main.py`
- [ ] Implement `GET /api/countries` endpoint
- [ ] Implement `GET /api/graph/{country_code}` endpoint
- [ ] Implement `POST /api/simulate` endpoint
- [ ] Implement `GET /api/metadata` endpoint
- [ ] Add CORS middleware
- [ ] Add error handling

**Verification:**
```bash
# Start server
python api/main.py

# Test endpoints
curl http://localhost:8000/
curl http://localhost:8000/api/countries
curl http://localhost:8000/api/graph/RWA
curl -X POST http://localhost:8000/api/simulate \
  -H "Content-Type: application/json" \
  -d '{"country": "RWA", "interventions": [{"indicator": "health_expenditure_per_capita", "change_percent": 20}]}'
```

---

### Task D.2: API Documentation
- [ ] Create `documentation/API_SPEC.md`
- [ ] Document all endpoints with examples
- [ ] Document request/response schemas
- [ ] Document error codes

**Verification:**
- [ ] `documentation/API_SPEC.md` is complete and accurate

**HUMAN VERIFICATION STEP:** Review API documentation for completeness.

---

## Phase E: Validation & Documentation (Weeks 8-9)

### Task E.1: Historical Validation
- [ ] Create `scripts/historical_validation.py`
- [ ] Define historical policy database (known interventions + outcomes)
- [ ] Implement `validate_historical_case()` function
- [ ] Run validation for all historical cases
- [ ] Compute correlation metrics (predicted vs observed)

**Verification:**
- [ ] `outputs/validation/historical_validation.json` exists
- [ ] Mean r² > 0.5 (or document why lower)

---

### Task E.2: Write Methodology Documentation
- [ ] Create `documentation/METHODOLOGY.md`
- [ ] Document country graph estimation method
- [ ] Document saturation function choices
- [ ] Document propagation algorithm
- [ ] Document temporal lag estimation
- [ ] Document validation approach

**Verification:**
- [ ] `documentation/METHODOLOGY.md` is complete

---

### Task E.3: Write Validation Report
- [ ] Create `documentation/VALIDATION_REPORT.md`
- [ ] Summarize historical validation results
- [ ] Document model limitations
- [ ] Provide recommendations for use

**Verification:**
- [ ] `documentation/VALIDATION_REPORT.md` is complete

**HUMAN VERIFICATION STEP:** Final review of all deliverables.

---

## Final Deliverables Checklist

### Data Files
- [ ] `data/raw/v21_nodes.csv`
- [ ] `data/raw/v21_causal_edges.csv`
- [ ] `data/raw/v20_panel_data.parquet`
- [ ] `data/raw/data_quality_by_country.csv`
- [ ] `data/processed/countries/` (217 files)
- [ ] `data/country_graphs/` (217 JSON files)
- [ ] `data/country_graphs_with_lags/` (217 JSON files)

### Scripts
- [ ] `scripts/import_v2_data.py`
- [ ] `scripts/split_countries.py`
- [ ] `scripts/estimate_country_graphs.py`
- [ ] `scripts/validate_country_graphs.py`
- [ ] `scripts/saturation_functions.py`
- [ ] `scripts/intervention_propagation.py`
- [ ] `scripts/simulation_runner.py`
- [ ] `scripts/temporal_analysis.py`
- [ ] `scripts/historical_validation.py`

### API
- [ ] `api/main.py`
- [ ] All endpoints functional

### Outputs
- [ ] `outputs/validation/country_graph_validation.csv`
- [ ] `outputs/validation/country_clusters.csv`
- [ ] `outputs/validation/historical_validation.json`
- [ ] `outputs/figures/country_similarity_matrix.png`

### Documentation
- [ ] `CLAUDE.md`
- [ ] `documentation/API_SPEC.md`
- [ ] `documentation/METHODOLOGY.md`
- [ ] `documentation/VALIDATION_REPORT.md`

---

## Notes

- See `project_brief.md` for detailed code templates for each script
- Use `depreceated/` folder in case of missing files from V2.0/V2.1
- Long-running tasks (A.2, C.1) require checkpointing and monitoring
- Human verification steps are REQUIRED between phases
