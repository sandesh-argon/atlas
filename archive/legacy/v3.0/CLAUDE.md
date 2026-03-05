# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**V3.0 Research: Global Causal Discovery System - Temporal Dynamics & Policy Simulation**

This project builds country-specific causal graphs and policy intervention simulators on top of V2.0 and V2.1 outputs. The goal is to enable "what-if" scenario analysis: given an intervention (e.g., +20% health spending), propagate effects through the causal network with realistic saturation constraints and temporal lags.

**Key Outputs:**
- REST API (FastAPI) for simulation queries
- 217 country-specific causal graphs (JSON)
- Intervention propagation simulator with uncertainty bounds
- Temporal dynamics with lag estimation

**Dependencies:**
- V2.0: Raw country-year panel data (217 countries × 34 years × 2,500 variables)
- V2.1: Unified graph (2,583 nodes, 7,368 causal edges), semantic hierarchy, SHAP scores

## Project Structure

```
V3_temporal_simulation/
├── data/
│   ├── raw/                    # V2.0 and V2.1 imports
│   ├── processed/              # Country-specific splits
│   │   └── countries/          # 217 .parquet files
│   ├── country_graphs/         # 217 .json files (causal graphs)
│   └── country_shap/           # 217 .json files (SHAP importance)
├── scripts/
│   ├── import_v2_data.py       # Phase 0.3
│   ├── phaseA/
│   │   ├── A1_split_panel/     # Split panel by country
│   │   ├── A2_estimate_graphs/ # Country-specific edge weights
│   │   ├── A3_validate_graphs/ # DAG validation
│   │   └── A4_country_shap/    # Country-specific SHAP importance
│   ├── saturation_functions.py     # Phase B.1
│   ├── intervention_propagation.py # Phase B.2
│   ├── simulation_runner.py        # Phase B.3
│   ├── temporal_analysis.py        # Phase C.1
│   └── historical_validation.py    # Phase E.1
├── api/
│   └── main.py                 # FastAPI backend
├── tests/
├── outputs/
│   ├── validation/
│   ├── figures/
│   └── reports/
└── documentation/
    ├── API_SPEC.md
    ├── METHODOLOGY.md
    └── VALIDATION_REPORT.md
```

## Tech Stack

**Core Libraries:**
- `numpy`, `pandas`: Data manipulation
- `scipy`, `statsmodels`: Statistical tests, Granger causality
- `scikit-learn`: Lasso regression for country graph estimation
- `fastapi`, `uvicorn`, `pydantic`: REST API
- `joblib`, `tqdm`: Parallelization and progress

**Install:**
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Key Algorithms

### 1. Saturation Functions (B.1)
Model diminishing returns for realistic intervention effects:
- **Sigmoid saturation**: GDP growth saturates at high income levels
- **Hard cap**: Literacy rate cannot exceed 100%
- **Linear diminishing**: Healthcare spending effectiveness drops after threshold

### 2. Intervention Propagation (B.2)
```
1. Apply intervention to source node(s)
2. Compute direct effects via edge beta coefficients
3. Iteratively propagate to downstream nodes
4. Apply saturation at each step
5. Repeat until convergence (change < threshold)
6. Propagate confidence intervals for uncertainty bounds
```

### 3. Temporal Lag Estimation (C.1)
- Use Granger causality tests to find optimal lag per edge
- Build VAR models to estimate lagged coefficients
- Simulate year-by-year effects accounting for lags

## Common Commands

```bash
# Setup
cd V3_temporal_simulation
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Phase 0: Import data
python scripts/import_v2_data.py

# Phase A: Country graphs
python scripts/phaseA/A1_split_panel/split_by_country.py
python scripts/phaseA/A2_estimate_graphs/estimate_country_graphs.py  # WARNING: 2-3 days
python scripts/phaseA/A3_validate_graphs/validate_all_graphs.py
python scripts/phaseA/A4_country_shap/compute_country_shap.py  # ~1-2 hours
python scripts/phaseA/A4_country_shap/validate_country_shap.py

# Phase B: Intervention
python scripts/saturation_functions.py  # Test saturation
python scripts/intervention_propagation.py  # Test propagation
python scripts/simulation_runner.py  # Full simulation

# Phase C: Temporal
python scripts/temporal_analysis.py  # WARNING: 1-2 days

# Phase D: API
cd api && python main.py  # Starts server on :8000

# Test API
curl http://localhost:8000/api/countries
curl -X POST http://localhost:8000/api/simulate \
  -H "Content-Type: application/json" \
  -d '{"country": "RWA", "interventions": [{"indicator": "health_expenditure_per_capita", "change_percent": 20}]}'
```

## Data Schema

### Input: V2.1 Unified Graph
```json
{
  "nodes": [{"id": "...", "label": "...", "ring": 0-5, "shap_value": 0.0-1.0, "domain": "..."}],
  "edges": [{"source": "...", "target": "...", "weight": 0.0-1.0, "relationship": "causal|hierarchical"}]
}
```

### Input: V2.0 Panel Data
CSV/Parquet with columns: `country_code`, `year`, plus 2,500 indicator columns.

### Output: Country Graph (per country)
```json
{
  "country_code": "RWA",
  "n_nodes": 1763,
  "n_edges": 5243,
  "edges": [
    {"source": "...", "target": "...", "beta": 0.42, "ci_lower": 0.38, "ci_upper": 0.46, "lag": 3}
  ]
}
```

### Output: Country SHAP (per country)
```json
{
  "country": "RWA",
  "shap_importance": {
    "indicator_id_1": 0.234,
    "indicator_id_2": 0.156,
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

### Output: Simulation Response
```json
{
  "country": "RWA",
  "baseline": {"life_expectancy": 69.3, ...},
  "simulated": {"life_expectancy": 71.6, ...},
  "effects": {"life_expectancy": {"change_percent": 3.32, "change_absolute": 2.3}},
  "uncertainty": {"life_expectancy": {"lower_bound": 70.8, "upper_bound": 72.4}},
  "metadata": {"n_indicators_affected": 47, "iterations_taken": 3}
}
```

## System Resources

**Inherited from V2.0 workstation:**
- CPU: AMD Ryzen 9 7900X (12 cores safe, 24 threads)
- RAM: 31 GB total (use 19.5 GB max)
- GPU: NVIDIA RTX 4080 (16 GB VRAM) - not heavily used in V3
- Thermal limit: 12 cores MAX for long operations

**Long-Running Tasks:**
- `estimate_country_graphs.py`: 2-3 days (217 countries × Lasso regression)
- `temporal_analysis.py`: 1-2 days (Granger tests per edge per country)

Use checkpointing and `monitor.sh` scripts for long tasks.

## V2.0/V2.1 Data Paths

```python
# V2.1 unified graph
V21_GRAPH = "../v2.1/outputs/B5/v2_1_visualization_final.json"

# V2.0 panel data (adjust based on actual location)
V20_PANEL = "../v2.0/phaseA/A0_data_acquisition/outputs/merged_panel.parquet"
```

## Validation Targets

- **Phase A.1-A.3**: 217 country graphs, all DAGs (no cycles), edge counts >0
- **Phase A.4**: 180+ country SHAP files, values in [0,1], countries show heterogeneity
- **Phase B**: Saturation tests pass, propagation converges in <10 iterations
- **Phase C**: Significant lags found for >50% of edges
- **Phase E**: Historical validation r² > 0.5 on known policy changes

## References

- **project_brief.md**: Complete implementation instructions with code templates
- **V2.1 CLAUDE.md**: Visualization JSON schema details
- **V2.0 CLAUDE.md**: Full V2 methodology and lessons learned
