# V3.1 Frontend Integration Guide

**Status:** PRODUCTION_READY (Certified 2026-01-15)
**Total Files:** 9,926

---

## Research Summary

**Goal:** Pre-compute ALL temporal data needed for the development economics visualization platform. The frontend NEVER needs backend recomputation for core features.

### What We Computed

**1. Temporal SHAP Importance (Phase 2A)**
- Tracks how indicator importance changes over time
- Answers: "What matters most for quality of life in 2010 vs 2020?"
- Uses composite Quality of Life target from 9 domains (health, education, income, etc.)
- 100 bootstrap iterations for confidence intervals

**2. Temporal Causal Graphs (Phase 2B)**
- Tracks how causal relationships strengthen/weaken over time
- Answers: "Does education → GDP get stronger over time?"
- Beta coefficients with confidence intervals and p-values
- Lag detection (effects can take 0-5 years to manifest)

**3. Feedback Loops (Phase 3A)**
- Identifies bidirectional causal relationships (A↔B)
- Result: 0 loops found (strict criteria - this is valid)
- Means no strong bidirectional causation in the data

**4. Development Clusters (Phase 3B)**
- Groups indicators into "ecosystems" using Louvain community detection
- Answers: "What indicators move together?"
- ~16 clusters per country (e.g., Education-Health cluster, Economic-Governance cluster)

### Key Innovation: Income Stratification

Cross-income SHAP correlation is only r=0.25-0.30, meaning what matters in developing countries is fundamentally different from advanced economies. We provide 4 global views:

| View | Description | Use Case |
|------|-------------|----------|
| **Unified** | All countries pooled | High-level overview |
| **Developing** | Low + Lower-middle income | Policy for poor countries |
| **Emerging** | Upper-middle income | Transition economies |
| **Advanced** | High income | Mature economy insights |

Countries move between groups over time (e.g., China: Developing → Emerging in 2010).

---

## Output Files

### Directory Structure

```
data/
├── v3_1_temporal_shap/           # Phase 2A
│   ├── unified/
│   │   └── quality_of_life/      # 35 files
│   ├── stratified/
│   │   ├── developing/           # 35 files
│   │   ├── emerging/             # 35 files
│   │   └── advanced/             # 35 files
│   └── countries/                # 178 countries × ~30 years
│       └── {CountryName}/
│           └── quality_of_life/
├── v3_1_temporal_graphs/         # Phase 2B
│   ├── unified/                  # 35 files
│   ├── stratified/
│   │   ├── developing/           # 35 files
│   │   ├── emerging/             # 35 files
│   │   └── advanced/             # 35 files
│   └── countries/                # 178 countries × ~30 years
│       └── {CountryName}/
├── v3_1_feedback_loops/          # Phase 3A
│   └── {CountryName}_feedback_loops.json  # 178 files
├── v3_1_development_clusters/    # Phase 3B
│   ├── countries/                # 178 files
│   │   └── {CountryName}_clusters.json
│   └── unified/                  # 35 files
│       └── {year}_clusters.json
├── metadata/
│   └── income_classifications.json  # Dynamic income groups 1990-2024
└── regional_spillovers.json      # Regional spillover proxy
```

---

## Data Schemas

### 1. Temporal SHAP (Unified/Stratified)

**File:** `v3_1_temporal_shap/unified/quality_of_life/{year}_shap.json`

```json
{
  "stratum": "unified",
  "stratum_name": "Global Average (All Countries)",
  "target": "quality_of_life",
  "target_name": "Quality of Life",
  "year": 2000,
  "stratification": {
    "countries_in_stratum": ["Afghanistan", "Albania", ...],
    "n_countries": 178,
    "note": "Global average - may not reflect context-specific patterns."
  },
  "shap_importance": {
    "indicator_id": {
      "mean": 0.032,
      "std": 0.042,
      "ci_lower": 0.0,
      "ci_upper": 0.16
    }
  },
  "metadata": {
    "n_samples": 1958,
    "n_countries": 178,
    "n_indicators": 2905,
    "n_bootstrap": 100,
    "r2_mean": 0.989,
    "r2_std": 0.003,
    "year_range": [1990, 2000],
    "computation_time_sec": 671.0
  },
  "data_quality": {
    "mean_ci_width": 0.018
  },
  "provenance": {
    "computation_date": "2026-01-14T19:32:38",
    "code_version": "v3.1.0",
    "model": "LightGBM",
    "hyperparameters": {
      "n_estimators": 100,
      "max_depth": 5,
      "learning_rate": 0.1
    }
  }
}
```

**Frontend Usage:**
- `shap_importance[indicator_id].mean` → Bar chart height
- `ci_lower`, `ci_upper` → Error bars
- Sort by `mean` descending for "Top 10 indicators"
- Compare across years for temporal trends

---

### 2. Temporal SHAP (Stratified - Income Groups)

**File:** `v3_1_temporal_shap/stratified/developing/{year}_shap.json`

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
    "countries_in_stratum": ["Afghanistan", "Bangladesh", ...],
    "n_countries": 88,
    "dynamic_note": "Country membership changes by year based on income classification"
  },
  "shap_importance": { ... },
  "metadata": { ... },
  "provenance": { ... }
}
```

**Frontend Usage:**
- Tab UI: Unified | Developing | Emerging | Advanced
- `n_countries` updates as user scrubs timeline
- Show `dynamic_note` as tooltip

---

### 3. Temporal SHAP (Country-Specific)

**File:** `v3_1_temporal_shap/countries/{CountryName}/quality_of_life/{year}_shap.json`

```json
{
  "country": "Rwanda",
  "target": "quality_of_life",
  "target_name": "Quality of Life",
  "year": 2015,
  "shap_importance": {
    "indicator_id": {
      "mean": 0.45,
      "std": 0.08,
      "ci_lower": 0.32,
      "ci_upper": 0.58
    }
  },
  "metadata": {
    "n_samples": 26,
    "n_indicators": 1850,
    "n_bootstrap": 100,
    "r2_mean": 0.92,
    "r2_std": 0.04,
    "year_range": [1990, 2015],
    "computation_time_sec": 3.2
  },
  "data_quality": {
    "mean_ci_width": 0.15
  },
  "provenance": { ... }
}
```

**Frontend Usage:**
- Country detail view
- Compare to global/stratified averages
- Wider CIs (fewer samples) - show user data quality

---

### 4. Temporal Causal Graphs (Unified/Stratified)

**File:** `v3_1_temporal_graphs/unified/{year}_graph.json`

```json
{
  "stratum": "unified",
  "stratum_name": "Global Average (All Countries)",
  "year": 2020,
  "stratification": {
    "countries_in_stratum": [...],
    "n_countries": 178
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
      "lag": 3
    }
  ],
  "metadata": {
    "n_edges_computed": 7365,
    "n_edges_total": 7368,
    "coverage": 0.9996,
    "mean_beta": 0.207,
    "significant_edges_p05": 7208,
    "computation_time_sec": 32.0
  },
  "provenance": {
    "computation_date": "2026-01-14T17:15:46",
    "code_version": "v3.1.0",
    "n_bootstrap": 100
  }
}
```

**Frontend Usage:**
- `edges` → Graph visualization (nodes + directed edges)
- `beta` → Edge thickness/color
- `lag` → Tooltip "Effect takes 3 years"
- `p_value` → Filter significant edges (p < 0.05)

---

### 5. Temporal Causal Graphs (Country-Specific)

**File:** `v3_1_temporal_graphs/countries/{CountryName}/{year}_graph.json`

```json
{
  "country": "Rwanda",
  "year": 2020,
  "income_classification": {
    "group_4tier": "Low income",
    "group_3tier": "Developing",
    "gni_per_capita": 820.0
  },
  "edges": [...],
  "metadata": {
    "n_edges_computed": 1200,
    "coverage": 0.61
  },
  "provenance": { ... }
}
```

**Frontend Usage:**
- Country-specific causal structure
- `income_classification` for context badge
- Lower coverage (fewer edges) - data availability varies

---

### 6. Feedback Loops

**File:** `v3_1_feedback_loops/{CountryName}_feedback_loops.json`

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

**Frontend Usage:**
- Most countries have 0 loops (strict detection criteria)
- If loops exist: visualize as bidirectional edges
- Loop types: virtuous (reinforcing good), vicious (reinforcing bad), dampening

---

### 7. Development Clusters (Country)

**File:** `v3_1_development_clusters/countries/{CountryName}_clusters.json`

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
    "algorithm": "louvain",
    "p_value_threshold": 0.05,
    "min_cluster_size": 5
  }
}
```

**Frontend Usage:**
- Cluster visualization (grouped nodes)
- `domain_composition` → Pie chart per cluster
- `sample_indicators` → Cluster label/tooltip
- Click cluster → Expand to show all indicators

---

### 8. Development Clusters (Unified/Year)

**File:** `v3_1_development_clusters/unified/{year}_clusters.json`

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
  "metadata": { ... },
  "provenance": { ... }
}
```

---

### 9. Income Classifications

**File:** `metadata/income_classifications.json`

```json
{
  "Afghanistan": {
    "1990": {"group_4tier": "Low income", "group_3tier": "Developing", "gni_per_capita": null},
    "2000": {"group_4tier": "Low income", "group_3tier": "Developing", "gni_per_capita": 120},
    "2010": {"group_4tier": "Low income", "group_3tier": "Developing", "gni_per_capita": 410},
    "2020": {"group_4tier": "Low income", "group_3tier": "Developing", "gni_per_capita": 500}
  },
  "China": {
    "1990": {"group_4tier": "Low income", "group_3tier": "Developing", "gni_per_capita": 330},
    "2000": {"group_4tier": "Lower middle income", "group_3tier": "Developing", "gni_per_capita": 940},
    "2010": {"group_4tier": "Upper middle income", "group_3tier": "Emerging", "gni_per_capita": 4340},
    "2020": {"group_4tier": "Upper middle income", "group_3tier": "Emerging", "gni_per_capita": 10550}
  }
}
```

**Frontend Usage:**
- Dynamic tab counts as timeline scrubs
- Country "graduation" animations
- Income badge on country cards

---

### 10. Regional Spillovers (Proxy)

**File:** `regional_spillovers.json`

```json
{
  "East_Asia_Pacific": {
    "regional_leaders": ["China", "Japan", "Korea, Rep."],
    "spillover_strength": 0.45,
    "member_countries": ["Cambodia", "Indonesia", "Vietnam", ...]
  },
  "Sub_Saharan_Africa": {
    "regional_leaders": ["South Africa", "Nigeria", "Kenya"],
    "spillover_strength": 0.35,
    "member_countries": ["Rwanda", "Uganda", "Tanzania", ...]
  }
}
```

**Frontend Usage:**
- Simulation feature: "If China grows 5%, Vietnam gets 0.45 × 5% = 2.25% spillover"
- Regional grouping for map visualization

---

## File Counts Summary

| Dataset | Files | Size Est. |
|---------|-------|-----------|
| SHAP Unified | 35 | ~10 MB |
| SHAP Stratified | 104 | ~30 MB |
| SHAP Countries | 4,628 | ~500 MB |
| Graphs Unified | 35 | ~50 MB |
| Graphs Stratified | 105 | ~150 MB |
| Graphs Countries | 4,628 | ~700 MB |
| Feedback Loops | 178 | ~2 MB |
| Clusters | 213 | ~20 MB |
| **Total** | **9,926** | **~1.5 GB** |

---

## Common Frontend Patterns

### Timeline Scrubbing
```javascript
// User moves slider to 2010
const year = 2010;
const shap = await fetch(`/data/v3_1_temporal_shap/unified/quality_of_life/${year}_shap.json`);
const graph = await fetch(`/data/v3_1_temporal_graphs/unified/${year}_graph.json`);
```

### Income Tab Switching
```javascript
// User clicks "Developing" tab
const stratum = 'developing';
const shap = await fetch(`/data/v3_1_temporal_shap/stratified/${stratum}/${year}_shap.json`);
// Update UI with shap.stratification.n_countries for tab badge
```

### Country Drill-Down
```javascript
// User clicks Rwanda on map
const country = 'Rwanda';
const shap = await fetch(`/data/v3_1_temporal_shap/countries/${country}/quality_of_life/${year}_shap.json`);
const graph = await fetch(`/data/v3_1_temporal_graphs/countries/${country}/${year}_graph.json`);
const clusters = await fetch(`/data/v3_1_development_clusters/countries/${country}_clusters.json`);
```

### Top Indicators
```javascript
// Get top 10 indicators for current view
const indicators = Object.entries(shap.shap_importance)
  .map(([id, val]) => ({ id, ...val }))
  .sort((a, b) => b.mean - a.mean)
  .slice(0, 10);
```

---

## Notes for Frontend

1. **All files are static JSON** - no backend computation needed
2. **Country names are full names** ("United States" not "USA")
3. **Years range 1990-2024** (some countries have gaps)
4. **SHAP values are normalized** - max importance = 1.0 (approximately)
5. **Graph edges are pre-filtered** - only significant (p < 0.05) relationships
6. **Clusters are stable** - computed from composite of all years
7. **Income classification is dynamic** - must be loaded per year for accurate counts
