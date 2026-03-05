# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**V3.1 Research: Complete Temporal System - COMPLETE**

**Status:** PRODUCTION_READY (Certified 2026-01-15)
**Total Files:** 9,926

This project pre-computes ALL temporal data needed for the visualization platform. The frontend NEVER needs backend recomputation for core features.

**Final Outputs:**
- Temporal SHAP importance (Phase 2A): 4,767 files
  - Unified (global average): 35 files
  - Stratified (3 income groups): 104 files
  - Country-specific (178 countries): 4,628 files
- Temporal Causal Graphs (Phase 2B): 4,768 files
  - Unified: 35 files
  - Stratified (3 income groups): 105 files
  - Country-specific: 4,628 files
- Feedback Loops (Phase 3A): 178 files
- Development Clusters (Phase 3B): 213 files
- Dynamic Income Classifications: Countries move between Developing/Emerging/Advanced over time

**Dependencies:**
- V3.0: Country graphs (217), country SHAP (174), panel data
- V2.1: Unified graph structure, node hierarchy

## Project Structure

```
v3.1/
├── data/
│   ├── raw/                          # Symlinked from v3.0
│   │   ├── v21_panel_data_for_v3.parquet
│   │   ├── v21_nodes.csv
│   │   └── v21_causal_edges.csv
│   ├── country_graphs/               # Symlinked from v3.0 (217 files)
│   ├── country_shap/                 # Symlinked from v3.0 (174 files)
│   ├── metadata/
│   │   └── income_classifications.json  # Dynamic income groups 1990-2024
│   ├── v3_1_temporal_shap/
│   │   ├── unified/
│   │   │   └── quality_of_life/      # 35 files (1990-2024)
│   │   ├── stratified/
│   │   │   ├── developing/           # 35 files
│   │   │   ├── emerging/             # 35 files
│   │   │   └── advanced/             # 35 files
│   │   └── countries/                # 178 countries × ~30 years
│   │       └── {country}/
│   │           └── quality_of_life/
│   ├── v3_1_temporal_graphs/
│   │   ├── unified/                  # 35 year files (global average)
│   │   ├── stratified/               # NEW (after 2A): By development stage
│   │   │   ├── developing/           # 35 files
│   │   │   ├── emerging/             # 35 files
│   │   │   └── advanced/             # 35 files
│   │   └── countries/                # 178 countries × 35 years
│   ├── v3_1_feedback_loops/          # Phase 3A: 178 country files
│   │   └── {country}_feedback_loops.json
│   ├── v3_1_development_clusters/    # Phase 3B: 213 files
│   │   ├── countries/                # 178 country files
│   │   │   └── {country}_clusters.json
│   │   └── unified/                  # 35 year files
│   │       └── {year}_clusters.json
│   └── regional_spillovers.json      # Spillover proxy (skipped full computation)
├── scripts/
│   ├── phase2_compute/
│   │   ├── phase2A/
│   │   │   └── compute_stratified_shap.py
│   │   └── phase2B/
│   │       └── compute_stratified_graphs.py
│   ├── phase3_analysis/
│   │   ├── detect_feedback_loops.py      # Phase 3A
│   │   └── detect_development_clusters.py # Phase 3B
│   └── phase4_validation/
├── outputs/                          # Validation reports
├── docs/
│   └── METHODOLOGY.md
├── CLAUDE.md                         # This file
├── PROGRESS.md                       # Progress tracking
└── requirements.txt
```

## Computation Categories

### Category 1: Temporal SHAP (Importance Evolution) - V2.1 Methodology

**Purpose:** Track how indicator importance changes over time for different outcome domains.

**V2.1 Outcome Domains (9 total):**
1. Health & Longevity (143 indicators)
2. Education & Knowledge (491 indicators)
3. Income & Living Standards (191 indicators)
4. Equality & Fairness (126 indicators)
5. Safety & Security (36 indicators)
6. Governance & Democracy (357 indicators)
7. Infrastructure & Access (229 indicators)
8. Employment & Work (96 indicators)
9. Environment & Sustainability (300 indicators)

**Dimensions:**
- Unified: 35 files (1990-2024)
- Stratified: 3 groups × 35 years = 105 files
- Countries: 178 × 30 years = ~5,340 files
- **Total: ~5,480 files**

**CRITICAL: V2.1 Methodology (Correct Implementation)**

### SHAP Computation (Single Model per Entity/Year)

```python
# Create composite target from ALL 9 domain aggregates
For each (entity, year):  # entity = unified/stratified/country
  1. For EACH of the 9 domains:
     a. Get ALL indicators in domain from V2.1 hierarchy
     b. Normalize each to [0, 1]: (value - min) / (max - min)
     c. INVERT negative outcomes (mortality, inequality, disease)
     d. domain_aggregate = mean(all normalized indicators)

  2. Create COMPOSITE target:
     quality_of_life = mean(health_agg, education_agg, ..., environment_agg)

  3. Train SINGLE model:
     X = ALL indicators
     y = quality_of_life

  4. SHAP directly answers:
     "How important is this indicator to OVERALL quality of life?"

  5. Save SHAP file
```

**Key Insight:** Single model predicting composite quality of life. Directly answers "how important is this indicator to overall development?"

### Dynamic Income Stratification (Critical Finding)

**Validation Results (2026-01-14):**
- Cross-income-group SHAP correlation: **r = 0.25-0.30**
- This means what matters in low-income countries is fundamentally different from high-income
- A unified global model would produce misleading "averaged" importance

**Architecture: 4 Global Views**
1. **Unified** - Global average (all countries pooled) - for high-level overview
2. **Developing** - Low + Lower-middle income countries
3. **Emerging** - Upper-middle income countries
4. **Advanced** - High income countries

**Dynamic Classification:**
- Countries move between groups over time based on World Bank GNI per capita thresholds
- 76 countries transitioned between groups from 1990-2024
- Example: China (Developing → Emerging in 2010), Korea (Emerging → Advanced in 1992)
- Classification data: `data/metadata/income_classifications.json`

**UI Behavior:**
- As user scrubs timeline, country counts in each tab update
- Countries "graduate" between tabs dynamically
- No data drops out - it reorganizes by year-specific membership

**Why Both Unified AND Stratified:**
- Unified: High-level exploration, "what matters on average"
- Stratified: Accurate context-specific insights, "what matters for YOUR development stage"
- The unified view explicitly notes it's an average that may not apply to specific contexts

**Canonical Country List:** 178 countries from `v3_1_temporal_graphs/countries/` (full names like "Afghanistan", not ISO codes)

**V2.1 Hierarchy Source:**
```
<repo-root>/v2.1/outputs/B5/v2_1_visualization.json
```

**Model:** LightGBM (consistent with V2.1, ~6x faster than sklearn)

**Runtime Estimate:** ~6-8 hours on 12-core machine for unified, ~24-48 hours for all countries

### Category 2: Temporal Causal Graphs (Beta Evolution)

**Purpose:** Track how causal relationships strengthen/weaken over time.

**Architecture (same as SHAP - unified + stratified + country):**
- **Unified:** Global average causal graph (35 files)
- **Stratified:** 3 income groups × 35 years = 105 files (after Phase 2A)
- **Country-specific:** 178 countries × 35 years = 6,230 files

**Why Stratified Causal Graphs:**
Given SHAP heterogeneity (r=0.25), causal relationships likely differ by income group too:
- Developing: Education → GDP might be weak (structural constraints)
- Advanced: Education → GDP might be strong (knowledge economy)

**Method:**
```python
For each (group/country, year):
  1. Get countries in this group for this year (dynamic classification)
  2. Load panel data up to `year`
  3. For each V2.1 edge (source → target):
     a. Run Lasso regression (target ~ source + controls)
     b. Extract beta coefficient
     c. Bootstrap confidence interval
  4. Save graph JSON
```

**Runtime:** ~24 hours on 16-core machine (including stratified)

### Category 3: Cross-Country Spillovers - SKIPPED (V3.1)

**Status:** Deferred to V3.2 - Using regional proxy instead

**Why Skipped:**
- Requires bilateral trade/migration data not available in panel
- Would need 10-20 hours data sourcing + 35 hours compute
- Regional proxy provides 70% of user value with minimal effort

**Alternative (V3.1):** Regional spillover coefficients in `data/regional_spillovers.json`

```python
# Example: Regional spillover proxy
REGIONAL_SPILLOVER = {
    'east_asia_pacific': {
        'dominant_economy': 'CHN',
        'regional_leaders': ['CHN', 'JPN', 'KOR'],
        'spillover_strength': 0.45  # 45% of direct effect spills to region
    }
}

# In simulation: regional_effect = direct_effect * spillover_strength
```

**V3.2 Roadmap:** Real bilateral spillovers if user demand justifies 58+ hours investment

## Common Commands

```bash
# Setup
cd <repo-root>/v3.1
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run individual computations
python scripts/compute/compute_temporal_shap.py --test  # Test 3 cases
python scripts/compute/compute_temporal_shap.py        # Full run

python scripts/compute/compute_temporal_graphs.py --test
python scripts/compute/compute_temporal_graphs.py

python scripts/compute/compute_spillovers.py --test
python scripts/compute/compute_spillovers.py

# Run all (master orchestrator)
python scripts/compute/run_all.py

# Validation
python scripts/validation/validate_shap.py
python scripts/validation/validate_graphs.py
python scripts/validation/validate_spillovers.py
```

## Output Schemas

### Temporal SHAP File (Stratified View)

For stratified views (developing/emerging/advanced), files include dynamic membership:

```json
{
  "stratum": "developing",
  "stratum_name": "Developing Countries",
  "target": "quality_of_life",
  "target_name": "Quality of Life",
  "year": 2010,
  "stratification": {
    "classification_source": "World Bank GNI per capita",
    "wb_groups_included": ["Low income", "Lower middle income"],
    "countries_in_stratum": ["Afghanistan", "Bangladesh", "India", ...],
    "n_countries": 88,
    "dynamic_note": "Country membership changes by year based on income classification"
  },
  "shap_importance": {
    "indicator_id_1": {
      "mean": 1.0,
      "ci_lower": 0.85,
      "ci_upper": 1.12,
      "std": 0.08
    },
    "indicator_id_2": {
      "mean": 0.52,
      "ci_lower": 0.41,
      "ci_upper": 0.63,
      "std": 0.06
    }
  },
  "metadata": {
    "n_samples": 2640,
    "n_countries": 88,
    "n_indicators": 2979,
    "n_bootstrap": 100,
    "year_range": [1990, 2010],
    "computation_time_sec": 32.1
  },
  "data_quality": {
    "mean_ci_width": 0.15,
    "target_coverage": 0.82
  },
  "provenance": {
    "computation_date": "2026-01-14T12:00:00Z",
    "code_version": "v3.1.0",
    "model": "LightGBM",
    "hyperparameters": {"n_estimators": 100, "max_depth": 5}
  }
}
```

### Temporal SHAP File (Country-Specific)

```json
{
  "country": "USA",
  "target": "quality_of_life",
  "target_name": "Quality of Life",
  "year": 2010,
  "income_classification": {
    "group_4tier": "High income",
    "group_3tier": "Advanced",
    "gni_per_capita": 48350.0
  },
  "shap_importance": {
    "indicator_id_1": {
      "mean": 1.0,
      "ci_lower": 0.85,
      "ci_upper": 1.12,
      "std": 0.08
    }
  },
  "metadata": {
    "n_samples": 21,
    "n_indicators": 2979,
    "n_bootstrap": 100,
    "year_range": [1990, 2010],
    "computation_time_sec": 2.8
  },
  "provenance": {
    "computation_date": "2026-01-14T12:00:00Z",
    "code_version": "v3.1.0",
    "model": "LightGBM"
  }
}
```

### Temporal SHAP File (Unified Global)

```json
{
  "stratum": "unified",
  "stratum_name": "Global Average (All Countries)",
  "target": "quality_of_life",
  "target_name": "Quality of Life",
  "year": 2010,
  "stratification": {
    "countries_in_stratum": ["Afghanistan", "Albania", ..., "Zimbabwe"],
    "n_countries": 178,
    "note": "Global average - may not reflect context-specific patterns. See stratified views for income-appropriate insights."
  },
  "shap_importance": {
    "indicator_id_1": {
      "mean": 0.78,
      "ci_lower": 0.65,
      "ci_upper": 0.91,
      "std": 0.08
    }
  },
  "metadata": {
    "n_samples": 5340,
    "n_countries": 178,
    "n_indicators": 2979,
    "n_bootstrap": 100
  }
}
```

### Temporal Graph File (Stratified View)

```json
{
  "stratum": "emerging",
  "stratum_name": "Emerging Countries",
  "year": 2010,
  "stratification": {
    "classification_source": "World Bank GNI per capita",
    "wb_groups_included": ["Upper middle income"],
    "countries_in_stratum": ["Brazil", "China", "Mexico", ...],
    "n_countries": 42,
    "dynamic_note": "Country membership changes by year based on income classification"
  },
  "edges": [
    {
      "source": "education_spending",
      "target": "gdp_per_capita",
      "beta": 0.38,
      "ci_lower": 0.31,
      "ci_upper": 0.45,
      "std": 0.04,
      "p_value": 0.0001,
      "lag": 3,
      "n_samples": 840,
      "n_bootstrap": 100
    }
  ],
  "metadata": {
    "n_edges_computed": 4500,
    "n_edges_total": 7368,
    "coverage": 0.61,
    "n_countries": 42,
    "year_range": [1990, 2010],
    "computation_time_sec": 45.2
  },
  "provenance": {
    "computation_date": "2026-01-14T10:00:00Z",
    "code_version": "v3.1.0",
    "n_bootstrap": 100
  }
}
```

### Temporal Graph File (Country-Specific)

```json
{
  "country": "USA",
  "year": 2010,
  "income_classification": {
    "group_4tier": "High income",
    "group_3tier": "Advanced",
    "gni_per_capita": 48350.0
  },
  "edges": [
    {
      "source": "education_spending",
      "target": "gdp_per_capita",
      "beta": 0.38,
      "ci_lower": 0.31,
      "ci_upper": 0.45,
      "std": 0.04,
      "p_value": 0.0001,
      "lag": 3,
      "r_squared": 0.42,
      "n_samples": 21,
      "n_bootstrap": 100,
      "relationship_type": "linear",
      "source_saturation": {"has_saturation": true, "threshold": 50000},
      "target_saturation": null
    }
  ],
  "metadata": {
    "n_edges_computed": 4500,
    "n_edges_skipped": 2868,
    "n_edges_total": 7368,
    "coverage": 0.61,
    "mean_beta": 0.186,
    "std_beta": 0.45,
    "median_p_value": 0.08,
    "significant_edges_p05": 1200,
    "significant_edges_p01": 450,
    "mean_lag": 1.2,
    "lag_distribution": {"0": 2000, "1": 1500, "2": 600, "3": 300, "4": 80, "5": 20},
    "nonlinear_edges": 45,
    "dag_validated": true,
    "dag_cycles": [],
    "n_samples": 21,
    "year_range": [1990, 2010],
    "computation_time_sec": 8.5
  },
  "saturation_thresholds": {
    "literacy_rate": 80,
    "gdp_per_capita": 50000,
    "life_expectancy": 78
  },
  "provenance": {
    "computation_date": "2026-01-14T10:00:00Z",
    "code_version": "v3.1.0",
    "git_commit": "abc123",
    "n_bootstrap": 100,
    "max_lag_tested": 5,
    "nonlinearity_threshold": 0.10,
    "top_n_nonlinear_tested": 500
  }
}
```

### Phase 3A: Feedback Loop File

**Purpose:** Identifies bidirectional causal relationships (A↔B) from temporal graphs.

```json
{
  "country": "Afghanistan",
  "feedback_loops": [],
  "summary": {
    "total_loops": 0,
    "virtuous_loops": 0,
    "vicious_loops": 0,
    "dampening_loops": 0
  },
  "metadata": {
    "years_analyzed": [1990, 2024],
    "n_years": 35,
    "n_edges_total": 42500,
    "computation_time_sec": 1.72
  },
  "provenance": {
    "computation_date": "2026-01-14T19:05:31",
    "code_version": "v3.1.0",
    "p_value_threshold": 0.05,
    "min_years_active": 3,
    "min_loop_strength": 0.01
  }
}
```

### Phase 3B: Development Cluster File (Country)

**Purpose:** Identifies indicator ecosystems using Louvain community detection.

```json
{
  "country": "Afghanistan",
  "year_analyzed": "composite",
  "n_years_available": 26,
  "clusters": [
    {
      "cluster_id": 0,
      "name": "Education-Governance Cluster",
      "size": 194,
      "domain_composition": {
        "education_knowledge": 0.45,
        "governance_democracy": 0.32,
        "income_living_standards": 0.15
      },
      "primary_domain": "education_knowledge",
      "secondary_domain": "governance_democracy",
      "density": 0.081,
      "mean_edge_strength": 0.34,
      "n_internal_edges": 1523,
      "sample_indicators": ["literacy_rate", "school_enrollment", "gov_effectiveness"]
    }
  ],
  "summary": {
    "n_clusters": 14,
    "largest_cluster_size": 194,
    "smallest_cluster_size": 12,
    "mean_cluster_size": 86.8
  },
  "metadata": {
    "n_nodes_total": 1215,
    "n_edges_used": 4500,
    "computation_time_sec": 0.06
  },
  "provenance": {
    "computation_date": "2026-01-14T19:13:44",
    "code_version": "v3.1.0",
    "algorithm": "louvain",
    "p_value_threshold": 0.05,
    "min_cluster_size": 5
  }
}
```

### Phase 3B: Development Cluster File (Unified/Year)

```json
{
  "source": "unified",
  "year": 2020,
  "clusters": [...],
  "summary": {
    "n_clusters": 16,
    "largest_cluster_size": 210,
    "mean_cluster_size": 95.2
  },
  "metadata": {...},
  "provenance": {...}
}
```

### Spillover File (SKIPPED - V3.2)

Regional spillover proxy used instead: `data/regional_spillovers.json`

## System Resources

- CPU: AMD Ryzen 9 7900X (12 cores safe, 24 threads)
- RAM: 31 GB total (use 19.5 GB max)
- Thermal limit: 12 cores MAX for long operations

**Estimated Total Runtime:** ~76.5 hours (~3.2 days on 16-core)
- Temporal SHAP: ~54 hours
- Temporal Graphs: ~18 hours
- Spillovers: ~4.5 hours

## Data Paths

```python
# Input data (symlinked from v3.0)
PANEL_DATA = "data/raw/v21_panel_data_for_v3.parquet"
NODES = "data/raw/v21_nodes.csv"
EDGES = "data/raw/v21_causal_edges.csv"
COUNTRY_GRAPHS = "data/country_graphs/"
COUNTRY_SHAP = "data/country_shap/"

# Output directories
TEMPORAL_SHAP = "data/v3_1_temporal_shap/"
TEMPORAL_GRAPHS = "data/v3_1_temporal_graphs/"
FEEDBACK_LOOPS = "data/v3_1_feedback_loops/"
DEVELOPMENT_CLUSTERS = "data/v3_1_development_clusters/"
REGIONAL_SPILLOVERS = "data/regional_spillovers.json"
```

## Validation Targets

### Phase 2A: Temporal SHAP
- **Unified:** 35 files (1990-2024)
- **Stratified:** 3 groups × 35 years = 105 files
- **Countries:** 178 × 30 years = 5,340 files
- **Total:** ~5,480 files, SHAP values in [0,1]

### Phase 2B: Temporal Graphs ✅ COMPLETE
- **Unified:** 35 files
- **Stratified:** 105 files
- **Countries:** 4,628 files (74% coverage due to data gaps)
- **Total:** 4,768 files

### Phase 3A: Feedback Loops ✅ COMPLETE
- **Files:** 178 country files
- **Result:** 0 loops found (strict criteria: p<0.05, ≥3 years active, min strength 0.01)

### Phase 3B: Development Clusters ✅ COMPLETE
- **Country files:** 178
- **Unified year files:** 35
- **Total:** 213 files
- **Avg clusters per country:** ~16

### Spillovers (SKIPPED - V3.2)
- Using regional proxy: `data/regional_spillovers.json`

## Success Criteria

```
Phase 2A (SHAP) - ✅ COMPLETE:
☑ Unified: 35/35 files
☑ Stratified: 104/105 files
☑ Countries: 4,628 files (74% coverage)
☑ Total: 4,767 files
☑ Bootstrap CIs present (n=100)

Phase 2B (Graphs) - ✅ COMPLETE:
☑ Unified: 35/35 files
☑ Stratified: 105/105 files
☑ Countries: 4,628 files (74% coverage)
☑ Schema validated

Phase 3A (Feedback Loops) - ✅ COMPLETE:
☑ 178 country files generated
☑ 0 loops found (valid result - strict criteria)

Phase 3B (Development Clusters) - ✅ COMPLETE:
☑ 178 country files
☑ 35 unified year files
☑ Avg 16 clusters per country

Phase 4 (Validation) - ✅ CERTIFIED:
☑ SHAP: 99.6% pass rate (4,749/4,767)
☑ Graphs: 98.2% pass rate (4,680/4,768)
☑ Loops: 100% pass rate (178/178)
☑ Clusters: 100% pass rate (213/213)
☑ Overall: PRODUCTION_READY
```

## CRITICAL: Output Schema Verification

**MANDATORY: Verify output schema matches documentation BEFORE and AFTER every computation run.**

### Pre-Run Verification
Before starting any computation:
1. Read the Output Schemas section in this CLAUDE.md
2. Compare script output structure against documented schema
3. Ensure all required fields are present
4. Verify field names match exactly (case-sensitive)

### Post-Run Verification
After computation completes (or during via spot-check):
```python
# Example verification script
import json
with open('output_file.json') as f:
    data = json.load(f)

# For SHAP files
required_shap_fields = ['stratum', 'stratum_name', 'target', 'year',
                        'stratification', 'shap_importance', 'metadata', 'provenance']
for field in required_shap_fields:
    assert field in data, f"Missing required field: {field}"

# For Graph files
required_graph_fields = ['stratum', 'stratum_name', 'year',
                         'stratification', 'edges', 'metadata', 'provenance']
for field in required_graph_fields:
    assert field in data, f"Missing required field: {field}"

# For stratified views
assert 'countries_in_stratum' in data['stratification']
assert 'n_countries' in data['stratification']
```

### Schema Mismatch = Recompute
If schema doesn't match documentation:
1. STOP the computation
2. Fix the script
3. Archive invalid outputs
4. Restart computation

**Never ship data with incorrect schema - the frontend depends on exact field names.**

## CRITICAL: AWS Remote Computation Safety Protocol

**LESSON LEARNED (2026-01-14):** 13,193 SHAP files were lost due to accidental `rm -rf` on a symlinked directory during AWS instance recovery. This section prevents future data loss.

### MANDATORY Rules for AWS/Remote Computation

1. **NEVER use `rm -rf` on remote data directories**
   - Always use `ls -la` first to verify what you're deleting
   - If it's a symlink, trace where it points before deleting
   - Prefer `mv` to backup instead of `rm`

2. **ALWAYS run checkpoint sync locally**
   ```bash
   # Start this IMMEDIATELY when computation begins
   ./scripts/phase2a/aws_checkpoint_sync.sh
   ```
   This syncs files to local machine every 10 minutes.

3. **ALWAYS set DeleteOnTermination=false on EBS volumes**
   ```bash
   aws ec2 modify-instance-attribute --instance-id <id> \
     --block-device-mappings '[{"DeviceName":"/dev/sda1","Ebs":{"DeleteOnTermination":false}}]'
   ```

4. **ALWAYS verify data exists BEFORE modifying directories**
   ```bash
   # Count files first
   find /path/to/data -name "*.json" | wc -l
   # Only then proceed
   ```

5. **After spot interruption recovery:**
   - Mount preserved volume as SECONDARY (not replace root)
   - Copy data to new location, don't symlink
   - Verify file counts match before and after
   - Start checkpoint sync before resuming computation

### AWS Quick Reference

```bash
# Current instance (as of 2026-01-14)
Instance ID: i-094506b9f9cab3003
IP: 98.83.114.6
Type: c7i.8xlarge (32 vCPUs, on-demand)
Volume: vol-099bfc7b50f341975 (100GB, DeleteOnTermination=false)

# Monitor
ssh -i ~/Downloads/Final.pem ubuntu@98.83.114.6 "tail -5 ~/v3.1/shap_output.log"

# Sync checkpoints (run locally)
./scripts/phase2a/aws_checkpoint_sync.sh

# Download all results
rsync -avz -e "ssh -i ~/Downloads/Final.pem" ubuntu@98.83.114.6:~/v3.1/data/v3_1_temporal_shap/ ./data/v3_1_temporal_shap/

# Kill job
ssh -i ~/Downloads/Final.pem ubuntu@98.83.114.6 "pkill -f compute_temporal"

# Resume
ssh -i ~/Downloads/Final.pem ubuntu@98.83.114.6 "cd ~/v3.1 && source venv/bin/activate && nohup python scripts/phase2_compute/compute_temporal_shap.py --resume > shap_output.log 2>&1 &"
```

### Data Loss Prevention Checklist

Before ANY filesystem operation on remote compute:
- [ ] Verified current file count
- [ ] Checkpoint sync running locally
- [ ] EBS DeleteOnTermination=false
- [ ] Understand full path (not just symlink)
- [ ] Have local backup of checkpoint.json
