# B5: Output Schema Generation

**Status**: ✅ Complete (v2.1-FULL)
**Duration**: Complete
**Inputs**: A4 (effects), A5 (interactions), A6 (full graph), B1 (outcomes), B2 (mechanisms), B3 (domains), B4 (SHAP scores)

---

## Objective

Integrate all Phase A+B outputs into a unified output schema for flexible visualization.

### Deliverables

1. **Full Graph Schema (v2.1-FULL)** - Complete 8,126 node graph with 21 causal layers
2. **Mechanism Schema (v2.0)** - 290 mechanism subset with 3 pruning levels
3. **Dashboard Metadata** - Filters, tooltips, citations, interactive features
4. **Export Formats** - JSON for different use cases

---

## 🆕 Task 6: Full Graph Export (v2.1-FULL)

**NEW**: Complete causal graph export for flexible frontend visualization.

### Output File
```
outputs/exports/causal_graph_v2_FULL.json (12.24 MB)
```

### What's Included

| Component | Count | Description |
|-----------|-------|-------------|
| **Nodes** | 8,126 | All nodes with 21 causal layers |
| **Edges** | 22,521 | All causal edges with effect sizes |
| **Layers** | 21 | Topological layers (0=drivers, 19-20=outcomes) |
| **Domains** | 5 | Governance, Education, Economic, Health, Mixed |
| **Outcomes** | 9 | B1 validated outcome factors |
| **Interactions** | 4,254 | A5 moderator effects |
| **Clusters** | 15 | B3 domain clusters |

### Node Types

| Type | Count | Layer | Description |
|------|-------|-------|-------------|
| `driver` | 810 | 0 | Causal origins (policy levers) |
| `mechanism` | 329 | 2-18 | B2 identified mechanisms with SHAP |
| `intermediate` | 6,955 | 1-18 | Non-mechanism intermediates |
| `outcome` | 32 | 19-20 | Terminal outcome nodes |

### Schema Structure

```json
{
  "metadata": {
    "version": "2.1-FULL",
    "node_count": 8126,
    "edge_count": 22521,
    "layer_count": 21,
    "statistics": {
      "nodes_by_type": {"driver": 810, "mechanism": 329, "intermediate": 6955, "outcome": 32},
      "edges_with_effects": 9759,
      "interactions_count": 4254
    }
  },
  "nodes": [
    {
      "id": "v2exrescon",
      "label": "Executive respects constitution",
      "causal_layer": 7,
      "domain": "Governance",
      "subdomain": "Executive",
      "cluster_id": 1,
      "shap_score": 0.0089,
      "centrality": {"betweenness": 0.034, "pagerank": 0.003},
      "degree": {"in": 5, "out": 12, "total": 17},
      "is_driver": false,
      "is_outcome": false,
      "is_mechanism": true,
      "node_type": "mechanism",
      "metadata": {"source": "V-Dem", "category": "Governance"}
    }
  ],
  "edges": [
    {
      "source": "wdi_gdp_pc",
      "target": "v2exrescon",
      "source_layer": 3,
      "target_layer": 7,
      "layer_diff": 4,
      "weight": 0.234,
      "ci_lower": 0.18,
      "ci_upper": 0.29,
      "sample_size": 1420,
      "validated": true
    }
  ],
  "hierarchy": {
    "domains": {
      "Governance": {
        "subdomains": ["Executive", "Judicial", "Electoral"],
        "node_count": 156,
        "layers": [2, 3, 4, 5, 6, 7, 8, 9, 10]
      }
    },
    "layer_statistics": {
      "0": {"count": 810, "type": "driver"},
      "10": {"count": 581, "type": "intermediate"},
      "20": {"count": 5, "type": "outcome"}
    }
  },
  "outcomes": [...],
  "interactions": [...],
  "clusters": [...],
  "filters": {
    "by_layer": [0, 1, 2, ..., 20],
    "by_domain": ["Governance", "Education", "Economic", "Health", "Mixed"],
    "by_type": ["driver", "mechanism", "intermediate", "outcome"],
    "by_shap": {"min": 0, "max": 0.013}
  }
}
```

### Frontend Usage

```javascript
// Load full schema
const graph = await fetch('causal_graph_v2_FULL.json').then(r => r.json());

// Desktop: All 21 layers as concentric orbits
const desktopView = graph.nodes;

// Mobile: Compress to 5 bands + filter by SHAP
const mobileNodes = graph.nodes.filter(n =>
  n.shap_score > 0.005 || n.is_driver || n.is_outcome
);

// Layer compression for smaller screens
const layerMapping = {
  0: 'drivers',
  '1-5': 'early',
  '6-14': 'middle',
  '15-18': 'late',
  '19-20': 'outcomes'
};

// Filter by domain
const govNodes = graph.nodes.filter(n => n.domain === 'Governance');

// Get edges with validated effects
const validatedEdges = graph.edges.filter(e => e.validated);
```

### Source Data

| Source | File | Content |
|--------|------|---------|
| A4 | `lasso_effect_estimates_WITH_WARNINGS.pkl` | Effect sizes + CIs |
| A5 | `A5_interaction_results_FILTERED_STRICT.pkl` | Interaction effects |
| A6 | `A6_hierarchical_graph.pkl` | Full graph + layers |
| B1 | `B1_validated_outcomes.pkl` | Outcome factors |
| B3 | `B3_part4_enriched.pkl` | Domain classifications |
| B4 | `B4_shap_scores.pkl` | SHAP importance |

### Run Script

```bash
python phaseB/B5_output_schema/scripts/task6_export_full_graph.py
```

---

## Previous Outputs (v2.0)

### Mechanism-Only Schema

The original v2.0 schema contains only the 290 identified mechanisms:

```
outputs/exports/causal_graph_v2_final.json
```

This is suitable for mechanism-focused views but lacks:
- Driver nodes (Layer 0)
- Outcome nodes (Layer 19-20)
- Intermediate nodes
- Full causal path tracing

---

## Inputs from Phase A+B

### B1: Outcome Discovery ✅
```
B1_outcome_discovery/outputs/
├── B1_validated_outcomes.pkl          # 9 validated outcome factors
├── B1_factor_loadings.pkl             # Variable → factor mappings
└── B1_validation_results.json         # R² scores, coherence metrics
```

**Key Data**:
- 9 validated outcome factors (Health, Education, Economic, etc.)
- 292 target variables with factor loadings
- Validation: R² > 0.40, domain coherence, literature alignment

### B2: Mechanism Identification ✅
```
B2_mechanism_identification/outputs/
├── B2_mechanism_clusters.pkl          # Centrality-based rankings
├── B2_cluster_metadata.json           # Size, composition, metrics
└── B2_validation_results.json         # Centrality validation
```

**Key Data**:
- Top 290 mechanisms (by composite centrality)
- Cluster assignments for each mechanism
- Centrality scores: betweenness, closeness, pagerank

### B3: Domain Classification ✅
```
B3_domain_classification/outputs/
├── B3_part4_enriched.pkl              # 14 classified clusters
├── B3_hierarchical_labels.json        # Domain taxonomy
└── B3_validation_results.json         # Classification confidence
```

**Key Data**:
- 14 clusters → 5 domains (Gov, Edu, Econ, Mixed, Health)
- Hierarchical labels: "Governance: Electoral", "Education: Primary", etc.
- 290 mechanisms with domain assignments
- 100% novel rate (14/14 clusters, no literature match)

### B4: Multi-Level Pruning ✅
```
B4_multi_level_pruning/outputs/
├── B4_full_schema.json                # 290 nodes, 507 edges
├── B4_professional_schema.json        # 116 nodes, 71 edges
├── B4_simplified_schema.json          # 167 nodes, 150 edges
├── B4_shap_scores.pkl                 # Importance scores
├── B4_comprehensive_validation.json   # 8/8 checks passed (100%)
└── B4_export_manifest.json            # Graph metadata
```

**Key Data**:
- 3 graph versions (Full, Professional, Simplified)
- SHAP scores for all 290 mechanisms
- Domain balance: 40/40/20 (Gov/Edu/Other)
- Validation: 8/8 checks passed

---

## B5 Task Breakdown

### Task 1: Load & Integrate B1-B4 Outputs (30 min)
```python
# Load all Phase B outputs
b1_outcomes = load_b1_outcomes()       # 9 factors
b2_mechanisms = load_b2_mechanisms()   # 290 mechanisms
b3_domains = load_b3_domains()         # 14 clusters, 5 domains
b4_graphs = load_b4_graphs()           # 3 graph versions

# Validate consistency
assert b2_mechanisms ⊆ b4_graphs.full_nodes
assert b3_clusters.all_nodes == b4_graphs.full_nodes
```

### Task 2: Create Unified V2 Schema (1-2 hours)
```json
{
  "metadata": {
    "version": "2.0",
    "timestamp": "2025-11-20",
    "phase": "B_complete",
    "validation_scores": {...}
  },
  "outcomes": [
    {
      "id": "health_outcome",
      "label": "Health & Longevity",
      "factor_loadings": [...],
      "r_squared": 0.83,
      "validation": "B1"
    }
  ],
  "mechanisms": [
    {
      "id": "physicians_per_1000",
      "label": "Physicians per 1,000 population",
      "domain": "Health",
      "subdomain": "Healthcare Access",
      "cluster_id": 2,
      "centrality": {...},
      "shap_score": 0.0089,
      "visible_in": ["full", "professional"]
    }
  ],
  "domains": [...],
  "graphs": {
    "full": {...},
    "professional": {...},
    "simplified": {...}
  }
}
```

### Task 3: Add Dashboard Metadata (1-2 hours)
```json
{
  "filters": {
    "domain": ["Governance", "Education", "Economic", "Health", "Mixed"],
    "shap_threshold": [0.001, 0.013],
    "graph_level": ["full", "professional", "simplified"]
  },
  "tooltips": {
    "mechanisms": {
      "physicians_per_1000": {
        "description": "Number of physicians per 1,000 population",
        "source": "WHO Global Health Observatory",
        "citation": "WHO (2024)",
        "temporal_coverage": "1990-2024"
      }
    }
  },
  "interactive_features": {
    "zoom": true,
    "pan": true,
    "node_selection": true,
    "path_highlighting": true,
    "subgraph_filtering": true
  }
}
```

### Task 4: Validate Schema Completeness (30 min)
```python
# Validation checks
assert all(node['has_tooltip'] for node in schema['nodes'])
assert all(edge['has_citation'] for edge in schema['edges'])
assert schema['metadata']['version'] == '2.0'

# Cross-reference checks
assert set(schema['mechanisms']) == set(b4_full_nodes)
assert all(m['domain'] in b3_domains for m in schema['mechanisms'])
```

### Task 5: Export Final Schema (30 min)
```
B5_output_schema/outputs/
├── causal_graph_v2.json               # Unified schema (primary)
├── causal_graph_v2.graphml            # NetworkX format
├── mechanisms_v2.csv                  # Flat mechanism list
├── outcomes_v2.csv                    # Flat outcome list
├── data_dictionary_v2.md              # Field descriptions
└── B5_export_manifest.json            # Export metadata
```

---

## Success Criteria

| Criterion | Target | Validation |
|-----------|--------|------------|
| **Schema Completeness** | 100% | All B1-B4 data integrated |
| **Node Coverage** | 290 mechanisms | All B2/B3/B4 mechanisms included |
| **Outcome Coverage** | 9 factors | All B1 outcomes included |
| **Graph Versions** | 3 levels | Full, Professional, Simplified |
| **Metadata Coverage** | 100% | All nodes/edges have tooltips |
| **Export Formats** | 4 formats | JSON, GraphML, CSV, MD |
| **Validation Pass** | 100% | All cross-checks pass |

---

## Timeline

| Task | Duration | Output |
|------|----------|--------|
| Task 1: Load & Integrate | 30 min | Validated B1-B4 data |
| Task 2: Unified Schema | 1-2 hours | causal_graph_v2_base.json |
| Task 3: Dashboard Metadata | 1-2 hours | causal_graph_v2_full.json |
| Task 4: Validation | 30 min | B5_validation_results.json |
| Task 5: Export | 30 min | 4 export formats |
| **TOTAL** | **3-5 hours** | Complete V2 schema |

---

## Key Design Decisions

### 1. Single Unified Schema vs Separate Files

**Decision**: Single JSON file with nested structure

**Rationale**:
- Dashboard loads faster (1 request vs 4)
- Easier version control (atomic updates)
- Simpler deployment (single artifact)

**Trade-off**: Larger file size (~2-5 MB) but acceptable for modern browsers

### 2. SHAP Score Inclusion

**Decision**: Include SHAP scores in mechanism metadata

**Rationale**:
- Enables dynamic filtering (e.g., "Show top 10% mechanisms")
- Supports interactive pruning (user can adjust threshold)
- Documented in B4: RF importance proxy, sums to 1.0

### 3. Graph Level Selection

**Decision**: Embed all 3 graph versions in single schema

**Rationale**:
- Dashboard supports level toggling (Expert → Professional → Simplified)
- Precomputed pruning (no client-side computation)
- Maintains SHAP retention metadata

---

## Expected Output Structure

```json
{
  "metadata": {...},
  "outcomes": [9 factors],
  "mechanisms": [290 items with domain, SHAP, centrality],
  "domains": [5 domains with hierarchical taxonomy],
  "graphs": {
    "full": {290 nodes, 507 edges},
    "professional": {116 nodes, 71 edges},
    "simplified": {167 nodes, 150 edges}
  },
  "filters": {...},
  "tooltips": {...},
  "citations": {...}
}
```

**Estimated file size**: 2-5 MB (JSON), 1-3 MB (GraphML)

---

## Validation Checklist

### v2.1-FULL Schema ✅

- [x] All 8,126 A6 nodes included
- [x] All 22,521 edges included
- [x] All 21 causal layers assigned
- [x] 9,759 edges with A4 effect sizes
- [x] 4,254 A5 interactions included
- [x] 9 B1 outcomes included
- [x] 329 mechanisms with domain classifications
- [x] 290 mechanisms with SHAP scores
- [x] Centrality scores included (betweenness, pagerank)
- [x] Node types correctly assigned (driver/mechanism/intermediate/outcome)
- [x] JSON exports successfully (12.24 MB)

### v2.0 Schema ✅

- [x] All 290 B2/B3/B4 mechanisms included
- [x] All 3 B4 graph versions embedded
- [x] Domain taxonomy consistent (B3 labels)
- [x] SHAP scores match B4

---

## Output Files

```
phaseB/B5_output_schema/outputs/exports/
├── causal_graph_v2_FULL.json    # 12.24 MB - Complete 8,126 node graph
└── causal_graph_v2_final.json   # ~2 MB - 290 mechanism subset
```

---

## Next Steps After B5

1. **Dashboard Integration** - Load v2.1-FULL schema into React/D3 visualization
2. **Layer Visualization** - Implement 21-layer radial/concentric layout
3. **Compression Testing** - Test 5-band mobile compression
4. **Performance Optimization** - Lazy loading for 12MB JSON
5. **Documentation** - User guide, API docs, methodology paper

---

**Status**: ✅ Complete
**Last Updated**: November 30, 2025
**Dependencies**: A4 ✅, A5 ✅, A6 ✅, B1 ✅, B2 ✅, B3 ✅, B4 ✅

### Scripts

| Script | Description |
|--------|-------------|
| `task1_load_and_integrate_CORRECTED.py` | Load B1-B4 outputs |
| `task2_unified_schema.py` | Create v2.0 mechanism schema |
| `task3_dashboard_metadata.py` | Add dashboard metadata |
| `task4_validate_completeness.py` | Validate schema |
| `task5_export_schema.py` | Export v2.0 final |
| `task6_export_full_graph.py` | **NEW**: Export v2.1-FULL |
