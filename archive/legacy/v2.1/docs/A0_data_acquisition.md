# A0: Data Acquisition and Stratified Sampling

## Overview

**Phase**: A0 (Data Preparation)
**Purpose**: Create a balanced subset of indicators through research-grade stratified sampling
**Input**: V2 preprocessed data (6,368 indicators across 4 domains)
**Output**: V2.1 sampled data (3,122 indicators with balanced domain distribution)
**Runtime**: ~5 minutes

## Rationale

V2.1 implements stratified sampling to address severe domain imbalance in the V2 dataset:

| Domain | V2 Count | V2 % | V2.1 Target | V2.1 % |
|--------|----------|------|-------------|--------|
| Governance | 2,633 | 41.3% | 1,000 | 32% |
| Education | 1,557 | 24.5% | 1,000 | 32% |
| Economic | 2,056 | 32.3% | 1,000 | 32% |
| Health | 122 | 1.9% | 122 | 4% |

**Key Benefit**: Granger testing scales quadratically with indicator count. Reducing from 6,368 to 3,122 indicators reduces candidate pairs from ~20.3M to ~4.9M, cutting runtime from 7 hours to 2-3 hours.

## Architecture

### Input Sources

V2.1 does NOT re-scrape data from external sources. Instead, it samples from V2's already-collected data:

**V2 Data Sources** (referenced but not re-fetched):
- World Bank WDI + Poverty (~2,040 indicators)
- WHO GHO (~2,000 indicators)
- UNESCO UIS (~200 indicators)
- UNICEF (~300 indicators)
- V-Dem (~450 indicators)
- QoG Institute (~2,000 indicators)
- IMF IFS (~800 indicators)

**Domain Mapping**:
```python
DOMAIN_MAP = {
    'vdem': 'Governance',
    'qog': 'Governance',
    'unesco': 'Education',
    'wid': 'Economic',
    'world_bank': 'Economic',
    'imf': 'Economic',
    'penn': 'Economic',
    'who': 'Health'
}
```

### Sampling Algorithm

V2.1 uses **outcome-aware coverage sampling** to ensure retained indicators are relevant to quality-of-life outcomes:

#### Step 1: Composite Score Calculation

Each indicator receives a research-grade composite score:

```python
composite_score = (
    0.50 * shap_score +          # Predicts QoL outcomes (CRITICAL)
    0.25 * outcome_betweenness + # Shortest paths to outcome nodes
    0.15 * quality_score +       # Data quality (1 - missingness)
    0.10 * diversity_score       # Cluster diversity (1 / log1p(cluster_size))
)
```

**Score Components**:

1. **SHAP Score (50%)**: Importance for predicting outcomes from V2's factor analysis
   - Fallback: Betweenness centrality if SHAP not available

2. **Outcome Betweenness (25%)**: Sum of inverse shortest path lengths to outcome nodes
   - Outcome keywords: `lifexp`, `gdp`, `mort`, `enrol`, `pov`, `health`, `democracy`, etc.
   - Formula: `Σ 1/(path_length + 1)` for all outcomes reachable from node

3. **Quality Score (15%)**: `1 - missing_rate` from metadata

4. **Diversity Score (10%)**: `1 / log1p(cluster_size)` to avoid redundancy within semantic clusters

#### Step 2: Coverage-Based Sampling Within Domains

For each domain:

1. **If current count ≤ target**: Keep all indicators (e.g., Health: 122 → 122)

2. **If current count > target**:
   - Identify semantic clusters in domain (from V2 B2 clustering)
   - Allocate samples proportionally to cluster sizes
   - From each cluster, take top N by composite score
   - If under target, add top remaining by composite score across all clusters
   - If over target, trim lowest composite scores

**Example (Governance: 2,633 → 1,000)**:
- 52 semantic clusters identified in Governance
- Allocate ~19 indicators per cluster (proportional to cluster size)
- Select top 19 from each cluster by composite score
- Total: 988 indicators (fill remaining 12 from top unselected)

### Output Data Structure

```python
v21_data = {
    'imputed_data': {...},      # Filtered indicator DataFrames
    'tier_data': {...},         # Imputation tier metadata
    'metadata': {...},          # Indicator metadata
    'preprocessing_info': {...},
    'v21_sampling_info': {
        'version': 'V2.1_RESEARCH_GRADE',
        'method': 'outcome_aware_coverage_sampling',
        'scoring_weights': {
            'shap': 0.50,
            'outcome_betweenness': 0.25,
            'quality': 0.15,
            'diversity': 0.10
        },
        'targets': {...},
        'total_indicators': 3122,
        'domain_distribution': {...},
        'top_100_retention': 87.5,  # % of top 100 V2 indicators retained
        'critical_dropped': 8,       # Count of critical indicators dropped
        'sampling_details': {...}
    }
}
```

## Implementation

### Main Script

**Location**: `<repo-root>/v2.0/v2.1/scripts/step0_stratified_sampling.py`

**Key Functions**:

#### `compute_outcome_betweenness(G, outcome_nodes)`

Computes path-based importance scores to quality-of-life outcome nodes.

```python
def compute_outcome_betweenness(G, outcome_nodes):
    """
    For each node, compute sum of inverse path lengths to all outcomes.
    Higher score = more central to reaching QoL outcomes.
    """
    outcome_betweenness = {}
    for node in G.nodes():
        path_score = 0.0
        for outcome in outcome_nodes:
            if nx.has_path(G, node, outcome):
                path_len = nx.shortest_path_length(G, node, outcome)
                path_score += 1.0 / (path_len + 1)
        outcome_betweenness[node] = path_score

    # Normalize to [0, 1]
    max_score = max(outcome_betweenness.values())
    return {k: v/max_score for k, v in outcome_betweenness.items()}
```

**Parameters**:
- `G`: NetworkX graph from V2 A6 hierarchical layering
- `outcome_nodes`: List of indicator names matching outcome keywords

**Returns**: Dict mapping each indicator to normalized betweenness score (0-1)

#### `coverage_based_sampling(domain_indicators, clusters, scores, target_count)`

Ensures semantic cluster diversity within each domain.

```python
def coverage_based_sampling(domain_indicators, clusters, scores, target_count):
    """
    Proportionally sample from each cluster to maintain diversity.
    """
    # Step 1: Group indicators by cluster
    domain_clusters = defaultdict(list)
    for ind in domain_indicators:
        cluster = clusters.get(ind, 'Unclassified')
        domain_clusters[cluster].append(ind)

    # Step 2: Allocate proportionally
    total_in_clusters = sum(len(inds) for inds in domain_clusters.values())
    cluster_allocations = {}
    for cluster, inds in domain_clusters.items():
        proportion = len(inds) / total_in_clusters
        allocation = max(1, int(target_count * proportion))
        cluster_allocations[cluster] = allocation

    # Step 3: Sample top N from each cluster
    selected = []
    for cluster, allocation in cluster_allocations.items():
        cluster_inds = domain_clusters[cluster]
        cluster_scores = [(ind, scores[ind]) for ind in cluster_inds]
        cluster_scores.sort(key=lambda x: x[1], reverse=True)
        selected.extend([ind for ind, _ in cluster_scores[:allocation]])

    # Step 4: Fill/trim to target
    if len(selected) < target_count:
        remaining = set(domain_indicators) - set(selected)
        remaining_scores = [(ind, scores[ind]) for ind in remaining]
        remaining_scores.sort(key=lambda x: x[1], reverse=True)
        selected.extend([ind for ind, _ in remaining_scores[:target_count-len(selected)]])
    elif len(selected) > target_count:
        selected_scores = [(ind, scores[ind]) for ind in selected]
        selected_scores.sort(key=lambda x: x[1], reverse=True)
        selected = [ind for ind, _ in selected_scores[:target_count]]

    return selected
```

**Parameters**:
- `domain_indicators`: List of indicator names in this domain
- `clusters`: Dict mapping indicator → cluster name
- `scores`: Dict mapping indicator → composite score
- `target_count`: Number of indicators to sample

**Returns**: List of selected indicator names

### Configuration

Sampling targets (in `step0_stratified_sampling.py`):

```python
SAMPLING_TARGETS = {
    'Governance': 1000,
    'Education': 1000,
    'Economic': 1000,
    'Health': 122  # Keep all Health indicators
}
```

**Why 3,122 total?**
- Governance: 1,000 (32%)
- Education: 1,000 (32%)
- Economic: 1,000 (32%)
- Health: 122 (4%, all retained)
- Total: 3,122 indicators

### Validation

The script performs automatic quality checks:

#### Critical Indicator Retention

```python
# Check: Retain at least 80% of top 100 V2 indicators
top_100_ids = [ind for ind, _ in sorted_scores[:100]]
retained = [ind for ind in top_100_ids if ind in selected_indicators]
retention_rate = len(retained) / 100

if retention_rate < 0.80:
    print(f"WARNING: Only {retention_rate:.1%} of top indicators retained")
```

#### Critical Keywords Check

```python
CRITICAL_KEYWORDS = {
    'democracy', 'corruption', 'judicial', 'electoral', 'civil_liberties',
    'enrollment', 'literacy', 'schooling', 'education_years',
    'mortality', 'life_expectancy', 'immunization', 'health_expenditure',
    'poverty', 'inequality', 'unemployment', 'gdp'
}

# Flag high-scoring indicators with critical keywords that were dropped
critical_dropped = []
for ind in dropped_indicators:
    if any(kw in ind.lower() for kw in CRITICAL_KEYWORDS):
        if composite_scores[ind] > 0.10:
            critical_dropped.append((ind, composite_scores[ind]))
```

**Success Criteria**:
- Top 100 retention ≥ 80%
- Critical dropped < 20

## Execution

### Command

```bash
cd <repo-root>/v2.0/v2.1
python scripts/step0_stratified_sampling.py
```

### Expected Output

```
================================================================================
V2.1 RESEARCH-GRADE STRATIFIED SAMPLING
================================================================================

[1/7] Loading V2 data...
  Loaded 6368 indicators
  Loaded V2 SHAP scores for 3872 indicators
  Loaded V2 clustering: 168 clusters
  Loaded graph: 3872 nodes, 11003 edges

[2/7] Computing outcome-specific betweenness...
  Identified 487 outcome nodes
  Computed outcome-specific betweenness for 3872 nodes

[3/7] Mapping indicators to domains and clusters...
  Mapped to 4 domains:
    Economic: 2056
    Education: 1557
    Governance: 2633
    Health: 122
  Mapped to 168 semantic clusters

[4/7] Computing research-grade composite scores...
  Scored 6368 indicators

[5/7] Coverage-based sampling within domains...

  Governance: 2633 -> 1000
    Found 52 clusters in Governance
    Sampled 1000/2633 (38.0%)
    Clusters covered: 52/52

  Education: 1557 -> 1000
    Found 26 clusters in Education
    Sampled 1000/1557 (64.2%)
    Clusters covered: 26/26

  Economic: 2056 -> 1000
    Found 49 clusters in Economic
    Sampled 1000/2056 (48.6%)
    Clusters covered: 49/49

  Health: 122 -> 122
    Keeping all 122 indicators
    Clusters covered: 11/11

  Total selected: 3122 indicators

[6/7] Validating critical indicator coverage...

  Top 100 composite score indicators: 87/100 retained (87.0%)

  Critical indicators dropped: 8

  Top 10 critical dropped (by composite score):
    - vdem_v2x_liberal_lag3: 0.142
    - unesco_ger_tertiary_f: 0.128
    - ...

[7/7] Creating V2.1 dataset...

  Saved to: <home>/.../v2.1/outputs/A2_preprocessed_data_V21.pkl
  Saved dropped indicators to: .../A2_DROPPED_INDICATORS.json
  Saved report to: .../sampling_report.json

================================================================================
RESEARCH-GRADE VALIDATION
================================================================================

V2.1 Domain Distribution:
  Economic: 1000 (32.0%)
  Education: 1000 (32.0%)
  Governance: 1000 (32.0%)
  Health: 122 (3.9%)

Scoring Method:
  SHAP/Composite importance: 50% (outcome prediction)
  Outcome betweenness: 25% (paths to QoL)
  Data quality: 15%
  Cluster diversity: 10%

Quality Metrics:
  Total indicators: 3122
  Reduction: 6368 -> 3122 (49.0%)
  Top 100 retention: 87.0%
  Critical indicators dropped: 8

================================================================================
RESEARCH-GRADE SAMPLING COMPLETE - QUALITY VALIDATED
================================================================================
```

## Output Files

### Primary Output

**File**: `<repo-root>/v2.0/v2.1/outputs/A2_preprocessed_data_V21.pkl`

**Format**: Python pickle containing dict with keys:
- `imputed_data`: Dict[str, pd.DataFrame] - 3,122 indicator DataFrames
- `tier_data`: Dict[str, pd.DataFrame] - Imputation tier metadata
- `metadata`: Dict[str, dict] - Indicator metadata
- `v21_sampling_info`: Dict - Sampling metadata

**Size**: ~252 MB (compressed pickle)

**Usage**: This becomes the input for A2 Granger causality testing

### Auxiliary Outputs

#### Dropped Indicators Report

**File**: `<repo-root>/v2.0/v2.1/outputs/A2_DROPPED_INDICATORS.json`

```json
{
  "total_dropped": 3246,
  "critical_dropped": [
    {
      "indicator": "vdem_v2x_liberal_lag3",
      "composite_score": 0.142
    }
  ],
  "dropped_by_domain": {
    "Governance": 1633,
    "Education": 557,
    "Economic": 1056,
    "Health": 0
  },
  "all_dropped": ["ind1", "ind2", ...]
}
```

#### Sampling Report

**File**: `<repo-root>/v2.0/v2.1/outputs/sampling_report.json`

```json
{
  "version": "V2.1_RESEARCH_GRADE",
  "total_indicators": 3122,
  "original_indicators": 6368,
  "reduction_pct": 50.97,
  "scoring_method": {
    "shap_weight": 0.50,
    "outcome_betweenness_weight": 0.25,
    "quality_weight": 0.15,
    "diversity_weight": 0.10
  },
  "domain_distribution": {
    "Governance": 1000,
    "Education": 1000,
    "Economic": 1000,
    "Health": 122
  },
  "validation": {
    "top_100_retention": 87.0,
    "critical_dropped": 8,
    "outcome_nodes_identified": 487
  },
  "quality_check": {
    "passed": true,
    "top_100_retention_target": 80,
    "critical_dropped_target": 20
  }
}
```

## Success Criteria

- Total indicators: 3,000-3,500 (Target: 3,122)
- Domain balance: Governance/Education/Economic within 10% of each other
- Health: 122 (100% retained)
- Top 100 retention: ≥80%
- Critical dropped: <20
- Quality check: PASS

## Next Steps

After A0 completes successfully:

1. **Backup V2 data** (optional):
   ```bash
   cp phaseA/A1_missingness_analysis/outputs/A2_preprocessed_data.pkl \
      phaseA/A1_missingness_analysis/outputs/A2_preprocessed_data_V2_BACKUP.pkl
   ```

2. **Copy V2.1 data to pipeline input**:
   ```bash
   cp v2.1/outputs/A2_preprocessed_data_V21.pkl \
      phaseA/A1_missingness_analysis/outputs/A2_preprocessed_data.pkl
   ```

3. **Proceed to A2**: Granger Causality Testing (2-3 hours runtime)

## Troubleshooting

### Issue: Top 100 retention < 80%

**Cause**: Sampling too aggressive, losing high-importance indicators

**Solution**: Adjust composite score weights to prioritize SHAP:
```python
composite = (
    0.60 * shap_score +          # Increase from 0.50
    0.20 * outcome_betweenness + # Decrease from 0.25
    0.15 * quality_score,
    0.05 * diversity_score       # Decrease from 0.10
)
```

### Issue: Critical indicators dropped > 20

**Cause**: Domain-specific critical indicators in over-sampled domains

**Solution**: Add critical indicator whitelist:
```python
CRITICAL_WHITELIST = [
    'life_expectancy_at_birth',
    'gdp_per_capita_ppp',
    'infant_mortality_rate',
    'primary_enrollment_rate',
    'democracy_index'
]

# Force-include whitelisted indicators
selected_indicators.extend(CRITICAL_WHITELIST)
```

### Issue: Cluster coverage < 100%

**Cause**: Some clusters have very few indicators, lost during sampling

**Solution**: Ensure at least 1 indicator per cluster:
```python
cluster_allocations[cluster] = max(1, int(target_count * proportion))
```

## References

- V2 Master Instructions: Lines 1-193 (V2.1 specification)
- V2 A6 Output: `<repo-root>/v2.0/phaseA/A6_hierarchical_layering/outputs/A6_hierarchical_graph.pkl`
- V2 SHAP Scores: `<repo-root>/v2.0/phaseB/B35_semantic_hierarchy/outputs/B35_shap_scores.pkl`
- V2 Clustering: `<repo-root>/v2.0/phaseB/B2_mechanism_identification/outputs/B2_semantic_clustering.pkl`
