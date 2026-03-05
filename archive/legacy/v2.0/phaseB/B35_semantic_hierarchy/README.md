# B3.5 Semantic Hierarchy & Final Export

**Phase**: B3.5 - Visualization Data Preparation
**Status**: COMPLETE
**Date**: December 2025
**Runtime**: ~2 seconds

---

## Quick Summary

B3.5 creates a 7-level semantic hierarchy for all 3,872 indicators, integrates SHAP scores from B2.5, and exports the final visualization-ready JSON with all metadata.

**Key Result**: Production-ready `causal_graph_v2_FINAL.json` (5.8 MB) with nodes, edges, moderators, and layer compression presets.

---

## Results

| Metric | Value |
|--------|-------|
| **Total nodes** | 3,872 |
| **Total edges** | 11,003 |
| **Edges with moderators** | 1,309 (11.9%) |
| **Total moderator effects** | 4,254 |
| **Hierarchy levels** | 7 |
| **SHAP coverage** | 95.6% computed, 42.5% non-zero |

### Hierarchy Structure
- **Level 0**: 3 Super-domains (Social, Economic, Environmental)
- **Level 1**: 9 Domains
- **Level 2**: 71 Subdomains
- **Level 3**: 73 Coarse clusters
- **Level 4**: 168 Fine clusters
- **Level 5**: 168 Indicator groups (top K per cluster)
- **Level 6**: 3,872 Indicators

### Domain Distribution
| Domain | Count | % |
|--------|-------|---|
| Governance | 1,536 | 39.7% |
| Economic | 1,122 | 29.0% |
| Education | 661 | 17.1% |
| Demographics | 438 | 11.3% |
| Environment | 48 | 1.2% |
| Health | 46 | 1.2% |

---

## Outputs

### Primary Output
**`outputs/causal_graph_v2_FINAL.json`** (5.8 MB)
```json
{
  "metadata": {
    "version": "2.2-B35-FINAL",
    "node_count": 3872,
    "edge_count": 11003,
    "layers": 21,
    "hierarchy_levels": 7,
    "shap_metrics": {
      "computed_coverage": 0.956,
      "nonzero_rate": 0.425
    }
  },
  "nodes": [...],           // Full node metadata
  "edges": [...],           // With moderators
  "hierarchy": {...},       // 7-level semantic tree
  "layer_compression_presets": {...},  // 2/5/7/21 bands
  "top_lists": {...}        // Pre-computed rankings
}
```

### Supporting Outputs
- `B35_semantic_hierarchy.pkl` - Full Python hierarchy object
- `B35_node_semantic_paths.json` - Fast node lookup
- `B35_shap_scores.pkl` - Composite SHAP scores
- `B35_hierarchy_summary_FINAL.json` - Statistics

---

## Key Features

### 1. Edge Moderator Metadata
```json
{
  "source": "health_spending",
  "target": "life_expectancy",
  "weight": 0.12,
  "moderators": [
    {
      "variable": "governance_quality",
      "interaction_beta": 0.26,
      "description": "Effect amplified in high-governance contexts"
    }
  ]
}
```

### 2. Layer Compression Presets
| Preset | Bands | Use Case |
|--------|-------|----------|
| `minimal_2` | 2 | Mobile |
| `standard_5` | 5 | Desktop (default) |
| `detailed_7` | 7 | Academic |
| `full` | 21 | Full resolution |

### 3. Pre-computed Top Lists
- `by_shap` - Top 20 outcome predictors
- `by_betweenness` - Top 20 structural bottlenecks
- `by_composite` - Top 20 combined importance
- `by_degree` - Top 20 most connected
- `drivers` - Top 20 root causes (layer 0)
- `outcomes` - Top 20 outcome variables

---

## Composite Score Formula

```python
composite_score = (
    0.50 * shap_normalized +      # Predictive importance
    0.30 * betweenness_norm +     # Structural importance
    0.15 * (1 - layer/20) +       # Upstream bonus
    0.05 * degree_norm            # Connectivity
)
```

---

## Files

```
B35_semantic_hierarchy/
├── README.md
├── scripts/
│   ├── run_b35_semantic_hierarchy.py    # Main hierarchy builder
│   └── export_final_visualization.py    # Final JSON export
└── outputs/
    ├── causal_graph_v2_FINAL.json       # Main visualization file
    ├── B35_semantic_hierarchy.pkl
    ├── B35_node_semantic_paths.json
    ├── B35_shap_scores.pkl
    └── B35_hierarchy_summary_FINAL.json
```

---

## Usage

### Load in Python
```python
import json

with open('outputs/causal_graph_v2_FINAL.json') as f:
    data = json.load(f)

# Access nodes
nodes = data['nodes']
print(f"Total nodes: {len(nodes)}")

# Access edges with moderators
edges_with_mods = [e for e in data['edges'] if e['moderators']]
print(f"Edges with moderators: {len(edges_with_mods)}")

# Get top 20 by SHAP
top_shap = data['top_lists']['by_shap']
```

### Load in JavaScript
```javascript
fetch('causal_graph_v2_FINAL.json')
  .then(r => r.json())
  .then(data => {
    // Use layer compression preset
    const bands = data.layer_compression_presets.standard_5.bands;

    // Access pre-computed top lists
    const topNodes = data.top_lists.by_composite;
  });
```

---

## Validation

- All nodes have composite scores
- 11.9% of edges have interaction moderators
- Layer compression presets cover all 21 layers
- 6 top-K lists with 120 total entries
- Domain distribution matches B2 clustering

---

**Last Updated**: December 2025
**Status**: COMPLETE - Ready for Visualization
