# Phase B: Interpretability Layer - Technical Documentation

## Overview

**Phase B** transforms the statistical causal network from Phase A into an interpretable, visualization-ready system through semantic clustering, importance scoring, and hierarchical organization.

**Goal**: Enable researchers and policymakers to understand complex causal relationships through progressive disclosure and domain-organized visualization.

**Location**: `<repo-root>/v2.0/v2.1/scripts/B*/`

**Total Runtime**: 2-3 hours (V2.1)

---

## Architecture Overview

```
Phase A Output (A6_hierarchical_graph.pkl)
    │
    ├──> B1: Outcome Discovery (Factor Analysis)
    │         │
    │         ├──> Identifies 9 validated outcome factors
    │         └──> Determines data-driven vs theory-driven approach
    │
    ├──> B2: Semantic Clustering (Keyword + Embedding)
    │         │
    │         ├──> 73 coarse clusters (domain-based)
    │         ├──> 168 fine clusters (sub-clustering)
    │         └──> 100% coverage (no unclassified nodes)
    │
    ├──> B2.5: SHAP Computation (LightGBM TreeSHAP)
    │         │
    │         ├──> Trains LightGBM on B1 outcomes
    │         ├──> Computes feature importance for each indicator
    │         └──> Aggregates across all outcomes
    │
    └──> B3.5: Semantic Hierarchy Builder
              │
              ├──> 7-level hierarchy (Root → Indicators)
              ├──> Composite scoring (SHAP + centrality)
              ├──> Edge moderator metadata integration
              └──> Visualization-ready JSON export
```

---

# B1: Outcome Discovery

## Purpose

Identify 9-12 validated outcome dimensions that represent quality-of-life constructs, using a **hybrid approach** that tries data-driven factor analysis first and falls back to theory-driven selection if factors are uninterpretable.

**Location**: `<repo-root>/v2.0/v2.1/scripts/B1/run_b1_outcome_discovery.py`

**Runtime**: 10-15 minutes

---

## Algorithm: Hybrid Outcome Discovery

### Strategy

```
1. Run factor analysis on ALL indicators (not just top layer)
2. Check interpretability of each factor
3. Decision:
   - IF ≥7/9 factors interpretable → Use data-driven outcomes
   - ELSE → Fallback to theory-driven outcomes (HDI-style)
```

### Interpretability Criteria

A factor is **interpretable** if it satisfies BOTH:

1. **Domain Coherence**: ≥70% of top 10 indicators from same domain
2. **Loading Strength**: ≥50% of top 10 loadings have |loading| > 0.5

```python
def check_interpretability(factor_idx, loadings, node_names):
    # Get top 10 indicators by absolute loading
    top_10_idx = np.argsort(np.abs(loadings[factor_idx]))[-10:][::-1]
    top_10_indicators = [node_names[i] for i in top_10_idx]
    top_10_loadings = [loadings[factor_idx][i] for i in top_10_idx]

    # Check 1: Domain coherence
    domains = [classify_indicator_domain(ind) for ind in top_10_indicators]
    max_domain_pct = max(Counter(domains).values()) / len(domains)

    # Check 2: High loadings
    high_loading_pct = sum(1 for l in top_10_loadings if abs(l) > 0.5) / 10

    # Both must pass
    is_interpretable = (max_domain_pct >= 0.7) and (high_loading_pct >= 0.5)

    return is_interpretable
```

---

## Input Data

### A6 Hierarchical Graph
**Source**: `<repo-root>/v2.0/v2.1/outputs/A6/A6_hierarchical_graph.pkl`

**Used for**: Node list (all 1,962 indicators)

### A1 Preprocessed Data
**Source**: `<repo-root>/v2.0/v2.1/outputs/A2_preprocessed_data_V21.pkl`

**Structure**:
```python
{
    'imputed_data': {
        'indicator_id': pd.DataFrame(countries × years),
        ...
    }
}
```

**Used for**: Building country × indicator matrix for factor analysis

---

## Factor Analysis Methodology

### Data Preparation

```python
# 1. Build indicator matrix
indicator_matrix = []  # Countries × Indicators
for node in all_nodes:
    df = imputed_data[node]
    country_avg = df.mean(axis=1)  # Average across years
    indicator_matrix.append(country_avg)

indicator_matrix = pd.DataFrame(indicator_matrix).T

# 2. Standardize
scaler = StandardScaler()
X_filled = indicator_matrix.fillna(indicator_matrix.mean())
X_scaled = scaler.fit_transform(X_filled)

# 3. Run factor analysis
from sklearn.decomposition import FactorAnalysis
fa = FactorAnalysis(n_components=9, random_state=42, max_iter=1000)
factor_scores = fa.fit_transform(X_scaled)
factor_loadings = fa.components_  # Shape: (9, n_indicators)
```

### Domain Classification

```python
DOMAIN_KEYWORDS = {
    'Education': ['SE.', 'education', 'school', 'literacy', 'enrollment'],
    'Health': ['SH.', 'health', 'mortality', 'life.expect', 'disease'],
    'Economic': ['NY.', 'gdp', 'gni', 'income', 'trade'],
    'Governance': ['v2', 'democracy', 'corruption', 'polity', 'electoral'],
    'Infrastructure': ['EG.', 'IT.', 'electricity', 'internet', 'mobile'],
    'Environment': ['EN.', 'emission', 'forest', 'pollution', 'climate'],
    'Social': ['SP.', 'population', 'gender', 'poverty', 'inequality'],
    'Security': ['VC.', 'conflict', 'homicide', 'violence', 'crime']
}

def classify_indicator_domain(indicator_name):
    indicator_lower = indicator_name.lower()
    for domain, keywords in DOMAIN_KEYWORDS.items():
        for kw in keywords:
            if kw.lower() in indicator_lower:
                return domain
    return 'Other'
```

---

## Theory-Driven Fallback

If <7/9 factors are interpretable, use predefined outcomes:

```python
THEORY_OUTCOMES = {
    1: {
        'name': 'Health',
        'keywords': ['life_expectancy', 'mortality', 'health', 'SH.', 'death']
    },
    2: {
        'name': 'Education',
        'keywords': ['education', 'school', 'literacy', 'SE.', 'enrollment']
    },
    3: {
        'name': 'Income',
        'keywords': ['gdp', 'income', 'gni', 'NY.GDP', 'capita']
    },
    4: {
        'name': 'Inequality',
        'keywords': ['gini', 'inequality', 'palma', 'share', 'poverty']
    },
    5: {
        'name': 'Safety',
        'keywords': ['homicide', 'crime', 'violence', 'conflict', 'security']
    },
    6: {
        'name': 'Governance',
        'keywords': ['democracy', 'corruption', 'v2x', 'rule_of_law']
    },
    7: {
        'name': 'Infrastructure',
        'keywords': ['internet', 'electricity', 'water', 'sanitation']
    },
    8: {
        'name': 'Employment',
        'keywords': ['unemployment', 'labor', 'employment', 'SL.']
    },
    9: {
        'name': 'Environment',
        'keywords': ['air', 'pollution', 'forest', 'emission', 'EN.', 'co2']
    }
}
```

**Matching Logic**:
```python
for outcome_def in THEORY_OUTCOMES.values():
    matching = []
    for node in valid_nodes:
        node_lower = node.lower()
        if any(kw.lower() in node_lower for kw in outcome_def['keywords']):
            matching.append(node)

    # Also add high-layer nodes from this domain
    for node in valid_nodes:
        layer = layers.get(node, 0)
        if layer >= 15:  # Top 30% of layers
            node_domain = classify_indicator_domain(node)
            if node_domain == outcome_def['name']:
                matching.append(node)
```

---

## Output Schema

### Primary Output: `B1_validated_outcomes.pkl`

```python
{
    'outcome_type': 'data_driven',  # or 'theory_driven'
    'n_outcomes': 9,
    'outcomes': {
        1: {
            'name': 'Factor_1_Health',
            'type': 'factor_analysis',
            'interpretable': True,
            'dominant_domain': 'Health',
            'domain_coherence': 0.82,  # 82% from Health domain
            'top_indicators': [
                'wdi_life_expectancy',
                'wdi_infant_mortality',
                'who_immunization_dpt',
                ...
            ],
            'loadings': [
                ('wdi_life_expectancy', 0.87),
                ('wdi_infant_mortality', -0.79),
                ...
            ]
        },
        ...
    },
    'outcome_indicators': [
        'wdi_life_expectancy',
        'wdi_years_schooling',
        'wdi_gdp_per_capita',
        ...  # Top 5 from each factor = ~45 indicators total
    ],
    'interpretability_check': {
        'fa_success': True,
        'interpretable_count': 7,  # 7/9 interpretable
        'total_factors': 9,
        'threshold': 7,
        'results': [...]
    },
    'metadata': {
        'timestamp': '2025-12-05T12:48:00',
        'total_graph_nodes': 1962,
        'valid_nodes_for_fa': 1962,
        'indicator_matrix_shape': [160, 1962]  # 160 countries
    }
}
```

### JSON Summary: `B1_outcome_summary.json`

```json
{
  "outcome_type": "data_driven",
  "interpretable_count": 7,
  "threshold": 7,
  "n_outcomes": 9,
  "total_outcome_indicators": 45,
  "outcomes": {
    "1": {
      "name": "Factor_1_Health",
      "type": "factor_analysis",
      "top_5_indicators": [
        "wdi_life_expectancy",
        "wdi_infant_mortality",
        "who_immunization_dpt",
        "wdi_maternal_mortality",
        "wdi_physicians_per_1000"
      ]
    },
    ...
  }
}
```

---

## Success Criteria

| Criterion | Target | V2.1 Result |
|-----------|--------|-------------|
| Interpretable factors | ≥7/9 | 7/9 (78%) |
| Domain coherence (avg) | ≥0.70 | 0.76 |
| Loading strength (avg) | ≥0.50 | 0.58 |
| Outcome indicators | 30-50 | 45 |

---

# B2: Semantic Clustering

## Purpose

Assign ALL 1,962 indicators to semantic clusters with **100% coverage** (no unclassified nodes) using a two-stage approach:
1. Keyword-based coarse clustering (~55-60% coverage)
2. Embedding-based assignment for remaining (~40-45%)
3. Sub-clustering within each coarse cluster

**Location**: `<repo-root>/v2.0/v2.1/scripts/B2/run_b2_semantic_clustering.py`

**Runtime**: 15-20 minutes

---

## Two-Stage Clustering Strategy

### Stage 1: Keyword-Based Coarse Clustering

**Coverage**: 55-60% of indicators

**Method**: Regex pattern matching against indicator IDs and labels

```python
KEYWORD_PATTERNS = {
    # Governance clusters
    'Governance_Judicial': [r'judic', r'court', r'legal', r'\blaw\b', r'v2ju'],
    'Governance_Executive': [r'execut', r'presid', r'v2ex', r'cabinet'],
    'Governance_Legislative': [r'legislat', r'parliament', r'v2lg'],
    'Governance_Electoral': [r'elect', r'voting', r'campaign', r'v2el'],
    'Governance_Corruption': [r'corrupt', r'bribe', r'transparency'],

    # Education clusters
    'Education_Primary': [r'primary', r'GER\.1', r'NER\.1', r'elementary'],
    'Education_Secondary': [r'secondary', r'GER\.2', r'high.?school'],
    'Education_Tertiary': [r'tertiary', r'university', r'college'],
    'Education_Literacy': [r'literacy', r'literate', r'reading'],

    # Health clusters
    'Health_Mortality': [r'mortality', r'death', r'survival', r'life.?expectancy'],
    'Health_Disease': [r'disease', r'epidemic', r'HIV', r'malaria'],
    'Health_Maternal': [r'maternal', r'pregnancy', r'birth', r'antenatal'],
    'Health_Child': [r'child.?health', r'infant', r'immunization'],

    # Economic clusters (most numerous)
    'Economic_GDP': [r'GDP', r'gross.?domestic', r'economic.?growth'],
    'Economic_Trade': [r'\btrade\b', r'export', r'import', r'tariff'],
    'Economic_Employment': [r'employment', r'unemployment', r'labor.?force'],
    'Economic_Finance': [r'credit', r'\bbank', r'financial', r'lending'],

    # ... 73 total coarse clusters
}

def assign_coarse_cluster(indicator_id, indicator_label, indicator_desc=""):
    text = f"{indicator_id} {indicator_label} {indicator_desc}".lower()

    matches = []
    for cluster_name, patterns in KEYWORD_PATTERNS.items():
        score = sum(1 for pattern in patterns if re.search(pattern, text, re.I))
        if score > 0:
            matches.append((cluster_name, score))

    if matches:
        matches.sort(key=lambda x: x[1], reverse=True)
        return matches[0][0]

    return None  # Will be handled by embedding stage
```

### Stage 2: Embedding-Based Assignment

**Coverage**: Remaining 40-45% (unclassified from Stage 1)

**Method**: Semantic similarity to cluster representatives

```python
from sentence_transformers import SentenceTransformer

model = SentenceTransformer('all-MiniLM-L6-v2')  # Fast, 80M params

# Get representative texts for each coarse cluster
cluster_representatives = {}
for cluster_name, node_ids in coarse_cluster_nodes.items():
    # Take up to 10 samples
    sample_texts = []
    for node_id in node_ids[:10]:
        label = indicator_labels.get(node_id, {}).get('label', node_id)
        desc = indicator_labels.get(node_id, {}).get('description', '')[:100]
        sample_texts.append(f"{node_id} {label} {desc}")
    cluster_representatives[cluster_name] = ' | '.join(sample_texts)

# Embed cluster representatives
cluster_embeddings = model.encode(cluster_texts, show_progress_bar=False)

# For each unassigned node, find best matching cluster
for node_id in unassigned_nodes:
    label = indicator_labels.get(node_id, {}).get('label', node_id)
    desc = indicator_labels.get(node_id, {}).get('description', '')[:100]
    node_text = f"{node_id} {label} {desc}"

    node_embedding = model.encode([node_text])[0]

    # Find best cluster by cosine similarity
    similarities = cosine_similarity([node_embedding], cluster_embeddings)[0]
    best_cluster_idx = np.argmax(similarities)
    best_cluster = cluster_names[best_cluster_idx]

    coarse_assignments[node_id] = best_cluster
```

### Stage 3: Sub-Clustering Within Coarse Clusters

**Purpose**: Create fine-grained clusters (~168 total) from coarse clusters (~73)

**Method**: Agglomerative clustering on embeddings

```python
from sklearn.cluster import AgglomerativeClustering

for coarse_cluster, node_ids in coarse_cluster_nodes.items():
    # Skip if too small
    if len(node_ids) < 3:
        continue

    # Embed all nodes in this coarse cluster
    labels_for_embedding = [get_label(node_id) for node_id in node_ids]
    embeddings = model.encode(labels_for_embedding)

    # Determine number of sub-clusters
    n_subclusters = max(2, min(8, len(node_ids) // 15))

    # Cluster
    clustering = AgglomerativeClustering(
        n_clusters=n_subclusters,
        linkage='ward'
    )
    subcluster_labels = clustering.fit_predict(embeddings)

    # Assign to fine clusters
    for node_id, sublabel in zip(node_ids, subcluster_labels):
        fine_cluster = f"{coarse_cluster}_{sublabel}"
        fine_assignments[node_id] = fine_cluster
```

---

## Super-Domain Mapping

```python
SUPER_DOMAIN_MAP = {
    'Social': ['Governance', 'Education', 'Health', 'Security', 'Development'],
    'Economic': ['Economic', 'Demographics', 'Research'],
    'Environmental': ['Environment']
}
```

**Hierarchy Example**:
```
Super-domain: Social
  ├── Domain: Governance
  │     ├── Subdomain: Governance_Judicial
  │     │     ├── Coarse: Governance_Judicial
  │     │     │     ├── Fine: Governance_Judicial_0
  │     │     │     ├── Fine: Governance_Judicial_1
  │     │     │     └── Fine: Governance_Judicial_2
  │     ├── Subdomain: Governance_Executive
  │     └── ...
  ├── Domain: Education
  └── Domain: Health
```

---

## Output Schema

### Primary Output: `B2_semantic_clustering.pkl`

```python
{
    'fine_clusters': {
        'Governance_Judicial_0': {
            'indicators': ['v2juhcind', 'v2juhccomp', ...],
            'coarse_cluster': 'Governance_Judicial',
            'representative_label': 'Judicial Independence Court',
            'size': 18,
            'domain': 'Governance',
            'super_domain': 'Social',
            'sample_indicators': ['v2juhcind', 'v2juhccomp', ...],
            'sample_labels': ['Judicial independence', 'Judicial compliance', ...]
        },
        ...  # 168 fine clusters total
    },
    'node_assignments': {
        'indicator_id': 'Governance_Judicial_0',
        ...  # All 1,962 nodes
    },
    'coarse_clusters': {
        'Governance_Judicial': ['v2juhcind', 'v2juhccomp', ...],
        ...  # 73 coarse clusters
    },
    'coarse_assignments': {
        'indicator_id': 'Governance_Judicial',
        ...
    },
    'metadata': {
        'total_indicators': 1962,
        'total_fine_clusters': 168,
        'total_coarse_clusters': 73,
        'unclassified_count': 0,  # ZERO!
        'unclassified_pct': 0.0,
        'keyword_classified': 1142,  # 58.2%
        'embedding_classified': 820,  # 41.8%
        'timestamp': '2025-12-05T13:17:00',
        'method': 'Keyword + Embedding assignment + Sub-clustering',
        'embedding_model': 'all-MiniLM-L6-v2'
    },
    'domain_statistics': {
        'Governance': 52,  # clusters
        'Economic': 49,
        'Education': 26,
        'Demographics': 15,
        'Health': 11,
        'Environment': 8,
        'Security': 5,
        'Research': 2
    },
    'domain_indicator_counts': {
        'Governance': 687,  # indicators
        'Economic': 589,
        'Education': 298,
        ...
    }
}
```

### JSON Summary: `B2_semantic_clustering_summary.json`

```json
{
  "total_indicators": 1962,
  "total_fine_clusters": 168,
  "total_coarse_clusters": 73,
  "unclassified_count": 0,
  "coverage": "100%",
  "cluster_sizes": {
    "Governance_Judicial_0": 18,
    "Governance_Judicial_1": 14,
    ...
  },
  "cluster_domains": {
    "Governance_Judicial_0": "Governance",
    ...
  },
  "cluster_labels": {
    "Governance_Judicial_0": "Judicial Independence Court",
    ...
  },
  "domain_distribution": {
    "Governance": 52,
    "Economic": 49,
    ...
  },
  "timestamp": "2025-12-05T13:17:00"
}
```

---

## Success Criteria

| Criterion | Target | V2.1 Result |
|-----------|--------|-------------|
| Coverage | 100% | 100% (0 unclassified) |
| Keyword coverage | 55-65% | 58.2% |
| Embedding coverage | 35-45% | 41.8% |
| Fine clusters | 150-200 | 168 |
| Coarse clusters | 60-80 | 73 |
| Cluster size (median) | 8-15 | 11 |

---

# B2.5: SHAP Score Computation

## Purpose

Compute feature importance scores for all 1,962 indicators using **LightGBM TreeSHAP**, measuring how predictive each indicator is of the B1 validated outcomes.

**Location**: `<repo-root>/v2.0/v2.1/scripts/B25/run_b25_shap_computation.py`

**Runtime**: 30-60 minutes

---

## Algorithm: LightGBM TreeSHAP

### Conceptual Flow

```
1. Build panel data: (country, year) × indicators
2. For each B1 outcome:
   a. Train LightGBM regressor: outcome ~ all_other_indicators
   b. Compute TreeSHAP values
   c. Store mean |SHAP| per feature
3. Aggregate SHAP across all outcomes
4. Normalize to [0, 1] range
```

### Implementation

```python
import shap
import lightgbm as lgb

# Step 1: Build panel data (country-year × indicators)
panel_data = build_panel_data(imputed_dict, all_indicators)
# Shape: (n_country_years, n_indicators)
# Example: (5600, 1962) for 160 countries × 35 years

# Step 2: For each B1 outcome
shap_values_agg = defaultdict(list)

for outcome_col in outcome_columns:
    # Filter to rows where outcome is non-null
    df = panel_data[panel_data[outcome_col].notna()].copy()

    # Select features with >50% coverage
    feature_cols = [c for c in feature_columns if c != outcome_col]
    feature_coverage = df[feature_cols].notna().mean()
    good_features = feature_coverage[feature_coverage > 0.5].index.tolist()

    # Prepare data
    X = df[good_features].fillna(df[good_features].median())
    y = df[outcome_col]

    # Train LightGBM
    lgb_params = {
        'objective': 'regression',
        'metric': 'rmse',
        'boosting_type': 'gbdt',
        'num_leaves': 31,
        'learning_rate': 0.05,
        'feature_fraction': 0.8,
        'verbose': -1
    }
    train_data = lgb.Dataset(X, label=y, feature_name=good_features)
    model = lgb.train(lgb_params, train_data, num_boost_round=100)

    # Compute SHAP
    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X[:100])  # Sample 100 for speed

    # Mean absolute SHAP per feature
    mean_abs_shap = np.abs(shap_values).mean(axis=0)

    # Aggregate
    for feat, shap_val in zip(good_features, mean_abs_shap):
        shap_values_agg[feat].append(float(shap_val))

# Step 3: Aggregate across outcomes
final_shap_scores = {}
for indicator in all_indicators:
    if indicator in shap_values_agg:
        scores = shap_values_agg[indicator]
        final_shap_scores[indicator] = {
            'shap_mean': float(np.mean(scores)),
            'shap_std': float(np.std(scores)),
            'shap_max': float(np.max(scores)),
            'n_outcomes': len(scores)
        }
    else:
        final_shap_scores[indicator] = {
            'shap_mean': 0.0,
            'n_outcomes': 0
        }

# Step 4: Normalize to [0, 1]
raw_scores = [s['shap_mean'] for s in final_shap_scores.values()]
min_score = min(s for s in raw_scores if s > 0)
max_score = max(raw_scores)

for indicator in final_shap_scores:
    raw = final_shap_scores[indicator]['shap_mean']
    if raw > 0:
        normalized = (raw - min_score) / (max_score - min_score)
    else:
        normalized = 0.0
    final_shap_scores[indicator]['shap_normalized'] = normalized
```

---

## Panel Data Construction

```python
def build_panel_data(imputed_dict, all_indicators):
    """
    Convert imputed data to panel format.

    Input: {
        'indicator_A': DataFrame(countries × years),
        'indicator_B': DataFrame(countries × years),
        ...
    }

    Output: DataFrame(country-year rows × indicator columns)
    """
    melted_dfs = []

    for indicator in all_indicators:
        df = imputed_dict[indicator]

        # Melt to long format
        melted = df.reset_index().melt(
            id_vars=['country'],
            var_name='year',
            value_name='value'
        )
        melted['indicator'] = indicator
        melted = melted.dropna(subset=['value'])

        melted_dfs.append(melted)

    # Concatenate and pivot
    long_data = pd.concat(melted_dfs, ignore_index=True)
    panel_data = long_data.pivot_table(
        index=['country', 'year'],
        columns='indicator',
        values='value'
    ).reset_index()

    return panel_data
    # Shape: (n_country_years, 2 + n_indicators)
```

---

## Output Schema

### Primary Output: `B25_shap_scores.pkl`

```python
{
    'indicator_id': {
        'shap_mean': 0.0234,  # Mean SHAP across outcomes
        'shap_std': 0.0087,   # Std deviation
        'shap_max': 0.0412,   # Max SHAP across outcomes
        'n_outcomes': 9,      # Number of outcomes this was computed for
        'shap_normalized': 0.67,  # Normalized to [0, 1]
        'method': 'LightGBM TreeSHAP'
    },
    ...  # All 1,962 indicators
}
```

### JSON Summary: `B25_shap_summary.json`

```json
{
  "computed_count": 1847,
  "total_indicators": 1962,
  "coverage_pct": 94.1,
  "outcomes_processed": 45,
  "method": "LightGBM TreeSHAP",
  "statistics": {
    "min": 0.0,
    "max": 1.0,
    "mean": 0.342,
    "median": 0.298,
    "std": 0.187
  },
  "top_20": [
    {
      "indicator": "wdi_life_expectancy",
      "shap_normalized": 0.9823
    },
    {
      "indicator": "wdi_gdp_per_capita",
      "shap_normalized": 0.9467
    },
    ...
  ],
  "timestamp": "2025-12-05T12:56:00",
  "runtime_minutes": 42.3
}
```

---

## SHAP Interpretation

### What SHAP Measures

**SHAP (SHapley Additive exPlanations)** values measure:
- How much each feature (indicator) contributes to predicting an outcome
- Based on cooperative game theory (Shapley values)
- Additive: SHAP values sum to prediction

**High SHAP Score** = Indicator is highly predictive of outcomes → Likely an important outcome itself or strong mechanism

**Low SHAP Score** = Indicator is not predictive of outcomes → Likely a driver or unimportant

### Example SHAP Values

```python
# Predicting wdi_life_expectancy
{
    'wdi_physicians_per_1000': 0.087,    # Strong positive contributor
    'wdi_infant_mortality': -0.064,      # Strong negative contributor
    'wdi_gdp_per_capita': 0.053,
    'wdi_random_economic_var': 0.002,    # Weak contributor
    'wdi_governance_metric': 0.011
}
```

---

## Performance Optimization

### Checkpointing

```python
# Save checkpoint after each outcome
checkpoint_path = checkpoint_dir / f"shap_checkpoint_{len(completed_outcomes):04d}.pkl"
checkpoint_data = {
    'completed_outcomes': list(completed_outcomes),
    'shap_values_agg': dict(shap_values_agg),
    'timestamp': datetime.now().isoformat()
}
with open(checkpoint_path, 'wb') as f:
    pickle.dump(checkpoint_data, f)
```

**Resume Logic**:
```python
# On restart, load latest checkpoint
if checkpoint_files:
    latest_checkpoint = checkpoint_files[-1]
    with open(latest_checkpoint, 'rb') as f:
        checkpoint_data = pickle.load(f)
    completed_outcomes = set(checkpoint_data['completed_outcomes'])
    shap_values_agg = checkpoint_data['shap_values_agg']
```

### Sampling Strategies

```python
# Sample data if too large
MAX_SAMPLES_PER_OUTCOME = 2000
if len(df_subset) > MAX_SAMPLES_PER_OUTCOME:
    df_subset = df_subset.sample(n=MAX_SAMPLES_PER_OUTCOME, random_state=42)

# Sample for SHAP computation
SHAP_BACKGROUND_SIZE = 100
X_shap = X_filtered[:SHAP_BACKGROUND_SIZE]
shap_values = explainer.shap_values(X_shap)
```

---

## Success Criteria

| Criterion | Target | V2.1 Result |
|-----------|--------|-------------|
| Coverage | ≥90% | 94.1% |
| Outcomes processed | ≥30 | 45 |
| Runtime | <90 min | 42 min |
| Non-zero scores | ≥80% | 87.2% |

---

# B3.5: Semantic Hierarchy Builder

## Purpose

Build a **7-level semantic hierarchy** from B2 clusters for progressive disclosure visualization, integrate SHAP scores with centrality metrics, add edge moderator metadata, and export visualization-ready JSON.

**Location**: `<repo-root>/v2.0/v2.1/scripts/B35/run_b35_semantic_hierarchy.py`

**Runtime**: 2-3 minutes

---

## Hierarchy Structure

### 7-Level Architecture

```
Layer 0: Root QoL Target (1 node)
   │
   ├─ Layer 1: Super-domains (3 nodes)
   │     ├─ Social
   │     ├─ Economic
   │     └─ Environmental
   │
   ├─ Layer 2: Domains (9 nodes)
   │     ├─ Governance
   │     ├─ Education
   │     ├─ Health
   │     ├─ Economic
   │     ├─ Demographics
   │     ├─ Environment
   │     ├─ Security
   │     ├─ Development
   │     └─ Research
   │
   ├─ Layer 3: Subdomains (71 nodes)
   │     ├─ Governance_Judicial
   │     ├─ Governance_Executive
   │     ├─ Education_Primary
   │     ├─ Education_Secondary
   │     └─ ...
   │
   ├─ Layer 4: Coarse Clusters (73 nodes)
   │     ├─ Governance_Judicial
   │     ├─ Governance_Executive
   │     └─ ...
   │
   ├─ Layer 5: Fine Clusters (168 nodes from B2)
   │     ├─ Governance_Judicial_0
   │     ├─ Governance_Judicial_1
   │     ├─ Governance_Judicial_2
   │     └─ ...
   │
   └─ Layer 6: Indicators (1,962 real variables)
        ├─ v2juhcind (Judicial independence)
        ├─ v2juhccomp (Judicial compliance)
        └─ ...

(Optional Layer 7: Split Layer 6 if >500 nodes)
```

### Node Hierarchy Example

```
Quality_of_Life_Index (L0)
  └─ Social (L1)
      └─ Governance (L2)
          └─ Governance_Judicial (L3 subdomain)
              └─ Governance_Judicial (L4 coarse cluster)
                  ├─ Governance_Judicial_0 (L5 fine cluster)
                  │   ├─ v2juhcind (L6 indicator)
                  │   ├─ v2juhccomp (L6 indicator)
                  │   └─ v2juhcout (L6 indicator)
                  ├─ Governance_Judicial_1 (L5 fine cluster)
                  │   └─ ...
                  └─ Governance_Judicial_2 (L5 fine cluster)
                      └─ ...
```

---

## Composite SHAP Scoring

### Motivation

Not all indicators have real SHAP scores (94.1% coverage), so we use a **composite score** that combines:
- Real SHAP (50% weight if available)
- Betweenness centrality (25%)
- Layer position (15%)
- Degree centrality (10%)

### Algorithm

```python
def compute_composite_score(node_id, b25_shap_data, centrality, layers, G):
    # Get real SHAP if available
    b25_data = b25_shap_data.get(node_id, {})
    real_shap = b25_data.get('shap_normalized', 0.0)
    shap_n_outcomes = b25_data.get('n_outcomes', 0)

    # Normalize centrality metrics
    pr_score = normalize(centrality['pagerank'].get(node_id, 0))
    bw_score = normalize(centrality['betweenness'].get(node_id, 0))

    # Layer score (higher layer = higher importance)
    layer = layers.get(node_id, max_layer)
    layer_score = 1.0 - (layer / max_layer)

    # Degree score
    degree = G.degree(node_id)
    degree_score = degree / max_degree

    # Composite score
    if shap_n_outcomes > 0:
        # Have real SHAP - weight it heavily
        composite = (
            0.50 * real_shap +
            0.25 * bw_score +
            0.15 * layer_score +
            0.10 * degree_score
        )
    else:
        # No SHAP - use centrality-based fallback
        composite = (
            0.30 * bw_score +
            0.25 * layer_score +
            0.25 * pr_score +
            0.20 * degree_score
        )

    return {
        'composite_score': composite,
        'shap_real': real_shap,
        'shap_n_outcomes': shap_n_outcomes,
        'betweenness': bw_score,
        'pagerank': pr_score,
        'layer_score': layer_score,
        'degree_score': degree_score
    }
```

---

## Output Schema

### Primary Output: `B35_semantic_hierarchy.pkl`

```python
{
    'metadata': {
        'version': '2.1-B35',
        'timestamp': '2025-12-05T13:21:00',
        'total_indicators': 1962,
        'total_fine_clusters': 168,
        'total_coarse_clusters': 73,
        'total_subdomains': 71,
        'total_domains': 9,
        'total_super_domains': 3,
        'layers': 7,
        'layer_split': False,  # True if Layer 7 created
        'shap_method': 'LightGBM TreeSHAP',
        'shap_real_coverage': '1847/1962 (94.1%)'
    },
    'levels': {
        0: {  # Root
            'Quality_of_Life_Index': {
                'id': 'L0_QoL',
                'label': 'Quality of Life Index',
                'children': ['Social', 'Economic', 'Environmental'],
                'level': 0,
                'type': 'root'
            }
        },
        1: {  # Super-domains
            'Social': {
                'id': 'L1_Social',
                'label': 'Social',
                'parent': 'Quality_of_Life_Index',
                'children': ['Governance', 'Education', 'Health', 'Security', 'Development'],
                'level': 1,
                'type': 'super_domain'
            },
            ...
        },
        2: {  # Domains
            'Governance': {
                'id': 'L2_Governance',
                'label': 'Governance',
                'parent': 'Social',
                'children': ['Governance_Judicial', 'Governance_Executive', ...],
                'level': 2,
                'type': 'domain'
            },
            ...
        },
        3: {  # Subdomains
            'Governance_Judicial': {
                'id': 'L3_Governance_Judicial',
                'label': 'Judicial',
                'full_name': 'Governance_Judicial',
                'parent': 'Governance',
                'children': ['Governance_Judicial'],  # Coarse cluster(s)
                'level': 3,
                'type': 'subdomain'
            },
            ...
        },
        4: {  # Coarse clusters
            'Governance_Judicial': {
                'id': 'L4_Governance_Judicial',
                'label': 'Governance → Judicial',
                'parent': 'Governance_Judicial',  # Subdomain
                'children': ['Governance_Judicial_0', 'Governance_Judicial_1', ...],
                'total_indicators': 45,
                'level': 4,
                'type': 'coarse_cluster'
            },
            ...
        },
        5: {  # Fine clusters
            'Governance_Judicial_0': {
                'id': 'L5_Governance_Judicial_0',
                'label': 'Judicial Independence Court',
                'parent': 'Governance_Judicial',  # Coarse cluster
                'indicators': ['v2juhcind', 'v2juhccomp', ...],
                'size': 18,
                'mean_importance': 0.456,
                'level': 5,
                'type': 'fine_cluster'
            },
            ...
        },
        6: {  # Indicators
            'v2juhcind': {
                'id': 'v2juhcind',
                'label': 'High Court independence',
                'description': 'When the High Court (or equivalent) is ruling on cases...',
                'parent': 'Governance_Judicial_0',  # Fine cluster
                'causal_layer': 12,  # From A6
                'shap_score': 0.456,  # Composite score
                'pagerank': 0.0008,
                'degree': 7,
                'level': 6,
                'type': 'indicator'
            },
            ...
        }
    }
}
```

### Semantic Paths: `B35_node_semantic_paths.json`

**Purpose**: Fast lookup of semantic path for any indicator

```json
{
  "v2juhcind": {
    "indicator_id": "v2juhcind",
    "indicator_label": "High Court independence",
    "fine_cluster": "Governance_Judicial_0",
    "coarse_cluster": "Governance_Judicial",
    "subdomain": "Governance_Judicial",
    "domain": "Governance",
    "super_domain": "Social",
    "semantic_parent": "Governance_Judicial_0",
    "full_path": "Social > Governance > Judicial > Governance_Judicial_0",
    "shap_score": 0.456,
    "causal_layer": 12,
    "hierarchy_level": 6
  },
  ...
}
```

### Visualization-Ready JSON: `causal_graph_v2_FINAL.json`

**Purpose**: Complete graph export with all metadata for D3.js/Cytoscape.js visualization

**Structure**:
```json
{
  "metadata": {
    "version": "2.1-B35-FINAL",
    "timestamp": "2025-12-05T13:21:00",
    "node_count": 1962,
    "edge_count": 5487,
    "layers": 21,
    "hierarchy_levels": 7,
    "statistics": {
      "n_drivers": 245,
      "n_outcomes": 128,
      "n_mechanisms": 1589,
      "n_edges_with_moderators": 487,
      "total_moderator_effects": 1243
    },
    "shap_metrics": {
      "computed_coverage": 0.941,
      "nonzero_rate": 0.872,
      "nodes_with_shap": 1710,
      "interpretation": "1710 of 1962 indicators (87.2%) have non-zero outcome-predictive importance"
    },
    "domain_distribution": {
      "Governance": 687,
      "Economic": 589,
      "Education": 298,
      ...
    }
  },
  "nodes": [
    {
      "id": "v2juhcind",
      "label": "High Court independence",
      "description": "When the High Court is ruling...",
      "semantic_path": {
        "super_domain": "Social",
        "domain": "Governance",
        "subdomain": "Governance_Judicial",
        "fine_cluster": "Governance_Judicial_0",
        "full_path": "Social > Governance > Judicial > Governance_Judicial_0"
      },
      "causal_layer": 12,
      "is_driver": false,
      "is_outcome": false,
      "scores": {
        "shap": 0.456,
        "betweenness": 0.0142,
        "pagerank": 0.0008,
        "composite": 0.398,
        "degree": 7
      }
    },
    ...
  ],
  "edges": [
    {
      "source": "v2juhcind",
      "target": "wdi_corruption_index",
      "weight": 0.34,
      "beta": 0.34,
      "source_layer": 12,
      "target_layer": 18,
      "moderators": [
        {
          "variable": "v2juaccnt",
          "label": "Judicial accountability",
          "interaction_beta": 0.12,
          "t_statistic": 3.8,
          "p_value": 0.0002,
          "significant": true
        }
      ]
    },
    ...
  ],
  "layer_compression_presets": {
    "minimal_2": {
      "bands": [[0, 1, ..., 14], [15, 16, ..., 20]],
      "labels": ["Mechanisms", "Outcomes"],
      "description": "Binary view: everything is either a mechanism or an outcome",
      "band_counts": [1834, 128]
    },
    "standard_5": {
      "bands": [...],
      "labels": ["Drivers", "Early Mechanisms", "Middle Mechanisms", "Late Mechanisms", "Outcomes"],
      "description": "Balanced 5-band view for general exploration"
    },
    ...
  },
  "top_lists": {
    "by_shap": [
      {"id": "wdi_life_expectancy", "score": 0.9823, "label": "Life expectancy at birth", "layer": 20},
      {"id": "wdi_gdp_per_capita", "score": 0.9467, "label": "GDP per capita", "layer": 19},
      ...
    ],
    "by_betweenness": [...],
    "by_degree": [...],
    "drivers": [...],
    "outcomes": [...]
  },
  "hierarchy": {
    "super_domains": {...},
    "domains": {...},
    "subdomains": {...},
    "coarse_clusters": {...},
    "fine_clusters": {...}
  }
}
```

---

## Layer Compression Presets

**Purpose**: Enable visualization at different detail levels

### Preset Types

```python
layer_compression_presets = {
    'minimal_2': {
        'bands': [
            list(range(0, 15)),  # Mechanisms (layers 0-14)
            list(range(15, 21))  # Outcomes (layers 15+)
        ],
        'labels': ['Mechanisms', 'Outcomes'],
        'description': 'Binary view',
        'band_counts': [1834, 128]
    },
    'standard_5': {
        'bands': [
            [0],                 # Drivers
            list(range(1, 6)),   # Early mechanisms
            list(range(6, 15)),  # Middle mechanisms
            list(range(15, 19)), # Late mechanisms
            list(range(19, 21))  # Outcomes
        ],
        'labels': ['Drivers', 'Early', 'Middle', 'Late', 'Outcomes']
    },
    'detailed_7': {
        'bands': [...],  # 7 bands for detailed analysis
        'labels': ['Root Drivers', 'Early', 'Early-Mid', 'Middle', 'Late-Mid', 'Late', 'Outcomes']
    },
    'full': {
        'bands': [[i] for i in range(21)],  # All 21 layers
        'labels': [f'Layer {i}' for i in range(21)]
    }
}
```

### Visualization Use

```javascript
// Load preset
const preset = viz_data.layer_compression_presets.standard_5;

// Filter nodes
const visible_nodes = viz_data.nodes.filter(node => {
    const band_idx = preset.bands.findIndex(band => band.includes(node.causal_layer));
    return band_idx >= 0;
});

// Color by band
node.color = color_scale[band_idx];
node.band_label = preset.labels[band_idx];
```

---

## Top-K Lists

**Purpose**: Highlight important nodes by different criteria

### List Types

```python
top_lists = {
    'by_shap': [
        # Top 20 most outcome-predictive
        {'id': 'wdi_life_expectancy', 'score': 0.9823, 'layer': 20},
        ...
    ],
    'by_betweenness': [
        # Top 20 bridge nodes (mediate many paths)
        {'id': 'wdi_gdp_per_capita', 'score': 0.0842, 'layer': 19},
        ...
    ],
    'by_composite': [
        # Top 20 by composite importance score
        {'id': 'wdi_life_expectancy', 'score': 0.8934, 'layer': 20},
        ...
    ],
    'by_degree': [
        # Top 20 most connected
        {'id': 'wdi_governance_index', 'degree': 47, 'layer': 15},
        ...
    ],
    'drivers': [
        # Top 20 root drivers (layer 0)
        {'id': 'v2regendtype', 'score': 0.234},
        ...
    ],
    'outcomes': [
        # Top 20 outcomes (layer 19+)
        {'id': 'wdi_life_expectancy', 'score': 0.8934, 'layer': 20},
        ...
    ]
}
```

---

## Success Criteria

| Criterion | Target | V2.1 Result |
|-----------|--------|-------------|
| Hierarchy levels | 6-7 | 7 |
| Node coverage | 100% | 100% |
| SHAP coverage | ≥90% | 94.1% |
| Edges with moderators | ≥5% | 8.9% (487/5487) |
| JSON file size | <50 MB | 38 MB |
| Runtime | <5 min | 2-3 min |

---

# Pipeline Integration

## Complete Phase B Flow

```
A6_hierarchical_graph.pkl
    │
    ├──> B1 (10-15 min)
    │      └──> B1_validated_outcomes.pkl
    │
    ├──> B2 (15-20 min)
    │      └──> B2_semantic_clustering.pkl
    │
    ├──> B2.5 (30-60 min)
    │      └──> B25_shap_scores.pkl
    │
    └──> B3.5 (2-3 min)
           ├──> B35_semantic_hierarchy.pkl
           ├──> B35_node_semantic_paths.json
           ├──> B35_shap_scores.pkl
           └──> causal_graph_v2_FINAL.json ✅
```

**Total Runtime**: 60-100 minutes

---

## Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    Phase A Outputs                          │
│  • A6_hierarchical_graph.pkl (graph, layers, centrality)   │
│  • A2_preprocessed_data_V21.pkl (imputed data)             │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                         B1                                  │
│  Input: A6 graph + A2 imputed data                         │
│  Process: Factor analysis on 1,962 indicators              │
│  Output: 9 outcome factors (45 outcome indicators)         │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                         B2                                  │
│  Input: A6 graph nodes                                     │
│  Process: Keyword + embedding clustering                   │
│  Output: 73 coarse → 168 fine clusters (100% coverage)    │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                        B2.5                                 │
│  Input: A2 imputed data + B1 outcomes                      │
│  Process: LightGBM TreeSHAP on each outcome               │
│  Output: SHAP scores for 1,847 indicators (94.1%)         │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                        B3.5                                 │
│  Input: B2 clusters + B2.5 SHAP + A6 centrality           │
│  Process:                                                   │
│    1. Build 7-level hierarchy                              │
│    2. Compute composite scores                             │
│    3. Add edge moderators from A5                          │
│    4. Generate layer compression presets                   │
│    5. Create top-K lists                                   │
│  Output: causal_graph_v2_FINAL.json (visualization-ready) │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
                  🎨 VISUALIZATION 🎨
```

---

# Validation and Testing

## B1 Validation

```python
def test_b1_interpretability():
    """Verify ≥7/9 factors interpretable"""
    results = load_b1_results()
    interpretable_count = results['interpretability_check']['interpretable_count']
    assert interpretable_count >= 7, f"Only {interpretable_count}/9 interpretable"

def test_b1_outcome_coverage():
    """Verify 30-50 outcome indicators"""
    results = load_b1_results()
    n_outcomes = len(results['outcome_indicators'])
    assert 30 <= n_outcomes <= 50, f"Got {n_outcomes} outcome indicators"
```

## B2 Validation

```python
def test_b2_coverage():
    """Verify 100% coverage"""
    results = load_b2_results()
    assert results['metadata']['unclassified_count'] == 0
    assert results['metadata']['unclassified_pct'] == 0.0

def test_b2_cluster_counts():
    """Verify cluster count ranges"""
    results = load_b2_results()
    assert 60 <= results['metadata']['total_coarse_clusters'] <= 80
    assert 150 <= results['metadata']['total_fine_clusters'] <= 200
```

## B2.5 Validation

```python
def test_b25_coverage():
    """Verify ≥90% SHAP coverage"""
    results = load_b25_results()
    coverage_pct = results['computed_count'] / results['total_indicators']
    assert coverage_pct >= 0.90, f"SHAP coverage only {coverage_pct:.1%}"

def test_b25_normalized():
    """Verify SHAP scores in [0, 1]"""
    results = load_b25_results()
    for indicator, data in results.items():
        if 'shap_normalized' in data:
            assert 0 <= data['shap_normalized'] <= 1
```

## B3.5 Validation

```python
def test_b35_hierarchy_levels():
    """Verify 7 levels"""
    hierarchy = load_b35_hierarchy()
    assert 6 <= len(hierarchy['levels']) <= 8  # 6 or 7 (optional Layer 7)

def test_b35_node_coverage():
    """Verify all nodes have semantic paths"""
    paths = load_b35_paths()
    G = load_a6_graph()
    assert len(paths) == G.number_of_nodes()

def test_b35_edge_moderators():
    """Verify moderators are lists"""
    viz_data = load_final_json()
    for edge in viz_data['edges']:
        assert isinstance(edge['moderators'], list)
```

---

# Common Issues and Solutions

## Issue 1: B1 Factor Analysis Fails

**Symptom**: `fa_success = False`

**Causes**:
- Insufficient data (too many missing values)
- Matrix not positive definite
- Too few samples

**Solutions**:
```python
# 1. Increase missing value tolerance
X_filled = indicator_matrix.fillna(indicator_matrix.median())  # Use median instead of mean

# 2. Add regularization
fa = FactorAnalysis(n_components=9, noise_variance_init=0.01)

# 3. Use PCA fallback
from sklearn.decomposition import PCA
pca = PCA(n_components=9)
factor_scores = pca.fit_transform(X_scaled)
```

## Issue 2: B2 Unclassified Nodes

**Symptom**: `unclassified_count > 0`

**Cause**: Embedding stage failed or was skipped

**Solution**:
```python
# Force embedding assignment for all unclassified
if unassigned_nodes:
    # Lower similarity threshold
    MIN_SIMILARITY = 0.30  # Default: 0.50
    # Or assign to "Other" cluster
    for node_id in unassigned_nodes:
        coarse_assignments[node_id] = 'Other_General_0'
```

## Issue 3: B2.5 SHAP Timeout

**Symptom**: B2.5 runs >2 hours

**Causes**:
- Too many outcomes (>50)
- Large panel data (>10K rows)
- Too many features (>2000)

**Solutions**:
```python
# 1. Reduce sample size
MAX_SAMPLES_PER_OUTCOME = 1000  # Default: 2000

# 2. Reduce SHAP samples
SHAP_BACKGROUND_SIZE = 50  # Default: 100

# 3. Fewer outcomes
outcome_columns = outcome_columns[:30]  # Top 30 only

# 4. Parallel processing
from joblib import Parallel, delayed
results = Parallel(n_jobs=4)(
    delayed(compute_shap)(outcome) for outcome in outcome_columns
)
```

## Issue 4: B3.5 JSON Too Large

**Symptom**: `causal_graph_v2_FINAL.json` >100 MB

**Causes**:
- Too many edges (>20K)
- Long descriptions
- Uncompressed

**Solutions**:
```python
# 1. Truncate descriptions
description = indicator_labels.get(node_id, {}).get('description', '')[:100]  # Default: 200

# 2. Filter weak edges
edges = [e for e in edges if abs(e['weight']) > 0.05]

# 3. Compress JSON
import gzip
with gzip.open(json_path.with_suffix('.json.gz'), 'wt') as f:
    json.dump(viz_output, f)
```

---

# Configuration Reference

## B1 Configuration

```python
# Factor analysis
N_FACTORS = 9
MAX_ITER = 1000
RANDOM_STATE = 42

# Interpretability thresholds
DOMAIN_COHERENCE_THRESHOLD = 0.70
LOADING_STRENGTH_THRESHOLD = 0.50
INTERPRETABILITY_THRESHOLD = 7  # 7/9 factors

# Theory-driven fallback
THEORY_OUTCOME_LAYER_THRESHOLD = 15  # Top 30% of layers
```

## B2 Configuration

```python
# Embedding model
EMBEDDING_MODEL = 'all-MiniLM-L6-v2'  # 80M params, fast
BATCH_SIZE = 256

# Sub-clustering
MIN_SUBCLUSTER_SIZE = 3
MAX_SUBCLUSTERS = 8
SUBCLUSTER_SIZE_RATIO = 15  # 1 subcluster per 15 nodes

# Coverage requirement
MIN_COVERAGE = 1.0  # 100% required
```

## B2.5 Configuration

```python
# LightGBM
LGB_PARAMS = {
    'objective': 'regression',
    'metric': 'rmse',
    'num_leaves': 31,
    'learning_rate': 0.05,
    'feature_fraction': 0.8
}
NUM_BOOST_ROUND = 100

# Sampling
MAX_SAMPLES_PER_OUTCOME = 2000
SHAP_BACKGROUND_SIZE = 100
MIN_FEATURE_COVERAGE = 0.50  # 50% non-null

# Progress checkpointing
CHECKPOINT_INTERVAL = 1  # After each outcome
```

## B3.5 Configuration

```python
# Hierarchy
MAX_LAYERS = 7
CROWDING_THRESHOLD = 500  # Split Layer 6 if exceeded

# Composite scoring weights (with SHAP)
WEIGHT_SHAP = 0.50
WEIGHT_BETWEENNESS = 0.25
WEIGHT_LAYER = 0.15
WEIGHT_DEGREE = 0.10

# Composite scoring weights (without SHAP)
WEIGHT_BETWEENNESS_FALLBACK = 0.30
WEIGHT_LAYER_FALLBACK = 0.25
WEIGHT_PAGERANK_FALLBACK = 0.25
WEIGHT_DEGREE_FALLBACK = 0.20

# Classification thresholds
DRIVER_LAYER_THRESHOLD = 0  # Layer 0 only
OUTCOME_SHAP_THRESHOLD = 0.30  # SHAP >0.30
```

---

# Performance Benchmarks

## V2.1 Runtime Breakdown

| Step | Runtime | Memory | Bottleneck |
|------|---------|--------|------------|
| B1 | 10-15 min | 2 GB | Factor analysis |
| B2 | 15-20 min | 1.5 GB | Embedding computation |
| B2.5 | 30-60 min | 4 GB | LightGBM training |
| B3.5 | 2-3 min | 1 GB | JSON serialization |
| **Total** | **60-100 min** | **4 GB peak** | **B2.5 SHAP** |

## Optimization Opportunities

### B2.5 Parallelization

**Current**: Sequential outcome processing

**Optimized**: Parallel processing

```python
from joblib import Parallel, delayed

def compute_shap_for_outcome(outcome_col, panel_data, feature_columns):
    # ... existing logic ...
    return {outcome_col: shap_values_dict}

results = Parallel(n_jobs=4)(
    delayed(compute_shap_for_outcome)(outcome, panel_data, feature_columns)
    for outcome in remaining_outcomes
)
```

**Expected speedup**: 3-4× on 4-core machine

### B3.5 Caching

**Current**: Recompute everything on each run

**Optimized**: Cache expensive operations

```python
import joblib
memory = joblib.Memory('.cache', verbose=0)

@memory.cache
def compute_composite_scores(b25_shap_data, centrality, layers, G):
    # ... expensive computation ...
    return shap_scores
```

---

# Future Enhancements

## 1. Interactive Factor Discovery (B1)

Allow users to tune interpretability thresholds:

```python
def interactive_factor_tuning(loadings, indicators):
    """CLI tool to adjust factor interpretation"""
    for i, factor in enumerate(loadings):
        top_10 = get_top_indicators(factor, indicators)
        print(f"Factor {i+1}:")
        for ind, loading in top_10:
            print(f"  {ind}: {loading:.3f}")

        accept = input("Accept this factor? (y/n): ")
        if accept == 'n':
            # Rotate or adjust
            ...
```

## 2. Hierarchical Clustering Comparison (B2)

Compare different clustering methods:

```python
methods = {
    'agglomerative': AgglomerativeClustering(n_clusters=n, linkage='ward'),
    'spectral': SpectralClustering(n_clusters=n),
    'dbscan': DBSCAN(eps=0.3, min_samples=5)
}

for name, method in methods.items():
    labels = method.fit_predict(embeddings)
    silhouette = silhouette_score(embeddings, labels)
    print(f"{name}: {silhouette:.3f}")
```

## 3. Ensemble SHAP (B2.5)

Use multiple models for robustness:

```python
models = {
    'lgb': LightGBM(...),
    'xgb': XGBoost(...),
    'rf': RandomForest(...)
}

ensemble_shap = {}
for indicator in indicators:
    shap_values = []
    for model_name, model in models.items():
        shap = compute_shap(model, indicator)
        shap_values.append(shap)
    ensemble_shap[indicator] = np.mean(shap_values)
```

## 4. Dynamic Hierarchy Adjustment (B3.5)

Auto-adjust hierarchy levels based on graph size:

```python
def auto_determine_hierarchy_levels(n_nodes):
    if n_nodes < 500:
        return 6  # No Layer 7
    elif n_nodes < 2000:
        return 7
    elif n_nodes < 5000:
        return 8  # Add Layer 8 for very large graphs
    else:
        return 9
```

---

# References

## Academic Papers

1. **Factor Analysis**: Jöreskog, K. G. (1969). "A general approach to confirmatory maximum likelihood factor analysis". Psychometrika.
2. **Semantic Clustering**: Reimers, N. & Gurevych, I. (2019). "Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks". EMNLP.
3. **SHAP**: Lundberg, S. M. & Lee, S.-I. (2017). "A Unified Approach to Interpreting Model Predictions". NeurIPS.
4. **TreeSHAP**: Lundberg, S. M. et al. (2020). "From local explanations to global understanding with explainable AI for trees". Nature Machine Intelligence.
5. **Hierarchical Visualization**: Shneiderman, B. (1996). "The eyes have it: A task by data type taxonomy for information visualizations". IEEE Symposium on Visual Languages.

## Software Documentation

- NetworkX: https://networkx.org/documentation/stable/
- Scikit-learn: https://scikit-learn.org/stable/
- SHAP: https://shap.readthedocs.io/
- LightGBM: https://lightgbm.readthedocs.io/
- Sentence Transformers: https://www.sbert.net/

---

# Contact and Support

**Script Locations**:
- B1: `<repo-root>/v2.0/v2.1/scripts/B1/run_b1_outcome_discovery.py`
- B2: `<repo-root>/v2.0/v2.1/scripts/B2/run_b2_semantic_clustering.py`
- B2.5: `<repo-root>/v2.0/v2.1/scripts/B25/run_b25_shap_computation.py`
- B3.5: `<repo-root>/v2.0/v2.1/scripts/B35/run_b35_semantic_hierarchy.py`

**Output Directory**: `<repo-root>/v2.0/v2.1/outputs/`

**Configuration**: `<repo-root>/v2.0/v2.1/scripts/v21_config.py`
