# Phase B: Validated Interpretability Layer

**Timeline**: Week 5 (6-8 days)

## Purpose

Apply validated clustering and pruning to create human-interpretable, multi-level visualizations while maintaining explanatory power.

## Steps Overview

### B1: Outcome Discovery with Validation (6-8 hours)
**Input**: Causal DAG from Phase A
**Output**: 12-20 validated outcome dimensions
**Key Operations**:
- Start with V1's 8 validated QOL metrics (life expectancy, years schooling, GDP per capita, etc.)
- Exploratory Factor Analysis on leaf nodes (Kaiser criterion: eigenvalue > 1)
- **Critical 3-part validation** for each factor:
  1. Domain coherence: ≤3 unique domains
  2. Literature alignment: TF-IDF similarity > 0.60 with known constructs
  3. Predictability: RF cross-val R² > 0.40
- Select 1-2 representative metrics per factor (highest loading × (1 - missingness))
- Merge with V1 outcomes (union, remove duplicates)

### B2: Mechanism Identification (2-4 hours)
**Input**: Node metadata from A6 (centrality scores)
**Output**: 20-40 mechanism clusters
**Key Operations**:
- Composite centrality score: 0.40×betweenness + 0.30×PageRank + 0.30×out_degree
- Top 10% = mechanism candidates
- Community detection using Louvain method (modularity optimization)
- Identify lead mechanism per community (highest composite score)

### B3: Domain Classification (4-6 hours)
**Input**: All nodes with variable descriptions
**Output**: 12-18 coherent domain labels
**Key Operations**:
- Semantic embedding using `SentenceTransformer('all-MiniLM-L6-v2')`
- Hierarchical clustering (distance_threshold=0.7, linkage='ward')
- LLM-suggested domain labels from candidate list: Health, Education, Economic Development, Infrastructure, Governance, Social Equity, Environment, Security, Technology, Demographics, Nutrition, Energy, Trade
- Human validation if confidence < 0.80

### B4: Multi-Level Pruning (6-8 hours)
**Input**: Full graph from Phase A
**Output**: 3 graph versions (Full, Professional, Simplified)
**Key Operations**:
- **Level 1-2 (Expert/Researcher)**: Full graph (2K-8K nodes)
  - All nodes, all edges, statistical details visible
- **Level 3 (Professional)**: Pruned graph (300-800 nodes)
  - Keep: All outcomes + top 20% mechanisms by score + strong outcome effects (|β|>0.20) + high betweenness (>85th percentile)
  - Keep: Top-5 incoming edges + top-10 outgoing edges per node
- **Level 4-5 (Public)**: Simplified graph (30-50 nodes)
  - Keep: All outcomes + lead mechanism per cluster only
  - Keep: Only strongest direct edges to outcomes (|β|>0.25)
- **SHAP Mass Validation**: Assert ≥85% explanatory power retention for Level 3

### B5: Output Schema Generation (2-3 hours)
**Input**: All Phase A + B artifacts
**Output**: Unified JSON with dashboard metadata
**Key Operations**:
- Generate unified JSON schema with:
  - Metadata (version, dates, validation scores)
  - 3 graph levels with target audience tags
  - Node objects (id, label, layer, type, domain, centrality, stats, visibility)
  - Edge objects (source, target, lag, effect, tests, interpretation)
  - Interaction mechanisms
  - Mechanism clusters
  - Validated outcomes
  - Dashboard configuration (5-level progressive disclosure)
  - Credibility features (citation generator, methodology links, data download)

## Success Criteria

- ✅ Outcomes: 12-25 validated dimensions (reproduce ≥6 V1 outcomes)
- ✅ Mechanisms: 20-50 clusters with domain labels
- ✅ Domains: 12-20 coherent labels
- ✅ Professional graph: 300-800 nodes
- ✅ Simplified graph: 30-50 nodes
- ✅ SHAP retention: >85% for Level 3 vs Full
- ✅ All nodes have domain labels and visibility tags

## Checkpoints

Save after each step:
- `B1_validated_outcomes.pkl` (12-20 outcome dimensions with validation scores)
- `B2_mechanism_clusters.pkl` (20-40 clusters with lead mechanisms)
- `B3_domain_assignments.pkl` (node-to-domain mapping)
- `B4_pruned_graphs.pkl` (3 graph versions with SHAP validation results)
- `B5_dashboard_schema.json` (final unified output)

## Progressive Disclosure Mapping

| Level | Graph | Nodes | Target Audience | Features |
|-------|-------|-------|----------------|----------|
| 1 (Expert) | Full | 2K-8K | Researchers | Download data, methodology docs, citation generator, statistical details |
| 2 (Researcher) | Full | 2K-8K | Grad students | Interactive filtering, layer exploration, mechanism clusters |
| 3 (Professional) | Pruned | 300-800 | Policy analysts | Scenario testing, policy simulator, country pathways |
| 4 (Engaged Public) | Simplified | 30-50 | Journalists | Storytelling mode, guided tour, plain language |
| 5 (Casual) | Simplified | 30-50 | Social media | Pre-built narratives, single-click insights, video explainers |

## Critical V1 Lessons

**DON'T**:
- ❌ Accept factors without validation → Use 3-part check (domain, literature, R²)
- ❌ Force domain-balanced selection → Pure statistical, domain tagging post-hoc
- ❌ Prune arbitrarily → Validate with SHAP mass retention ≥85%

**DO**:
- ✅ Start with V1's 8 validated outcomes as anchor
- ✅ Use composite centrality (not single metric) for mechanism selection
- ✅ Create warning banners for simplified modes ("Showing only strongest relationships")
- ✅ Include academic credibility features (citations, methodology transparency)
