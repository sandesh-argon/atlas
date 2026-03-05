# V2.1 Global Causal Discovery System

## Project Overview

V2.1 is the completed visualization-ready output of the Global Causal Discovery System for development economics. It contains a 6-layer hierarchical causal network with 2,583 nodes and 9,950 edges, representing quality-of-life indicators and their causal relationships across 150+ countries.

## Current Status: COMPLETE

All phases are complete. The final output is ready for visualization.

## Key Output Files

### Primary Visualization JSON
```
outputs/B5/v2_1_visualization_final.json        # 3.0 MB - Full formatted JSON
outputs/B5/v2_1_visualization_final_compact.json # 2.5 MB - Compact version
```

### Supporting Data
```
outputs/B1/indicator_labels_comprehensive_v2.json  # All 1,962 indicator descriptions
outputs/B36/B36_semantic_hierarchy_llm.pkl         # 6-layer semantic hierarchy
outputs/A6/A6_hierarchical_graph.pkl               # Causal graph with 7,368 edges
outputs/B35/B35_shap_scores.pkl                    # SHAP importance scores
```

## Visualization JSON Schema

```json
{
  "nodes": [...],      // 2,583 nodes
  "edges": [...],      // 9,950 edges (7,368 causal + 2,582 hierarchical)
  "hierarchy": {},     // Parent-child relationships
  "metadata": {
    "version": "2.1",
    "statistics": {
      "layers": {
        "0": 1,        // root
        "1": 9,        // outcome_category (Quality of Life dimensions)
        "2": 45,       // coarse_domain
        "3": 196,      // fine_domain
        "4": 569,      // indicator groups
        "5": 1763      // individual indicators
      }
    }
  }
}
```

### Node Structure
```json
{
  "id": "string",
  "label": "Human-readable name",
  "description": "Plain English description (9-12th grade reading level)",
  "layer": 0-5,
  "node_type": "root|outcome_category|coarse_domain|fine_domain|indicator",
  "domain": "Health|Education|Economic|Governance|Environment|Demographics|Security|Development|Research",
  "shap_importance": 0.0-1.0,
  "in_degree": number,
  "out_degree": number,
  "parent": "parent_node_id",
  "children": ["child_ids"]
}
```

### Edge Structure
```json
{
  "source": "node_id",
  "target": "node_id",
  "weight": 0.0-1.0,
  "relationship": "causal|hierarchical"
}
```

## Layer Hierarchy

| Layer | Type | Count | Description |
|-------|------|-------|-------------|
| 0 | root | 1 | "Quality of Life" - central node |
| 1 | outcome_category | 9 | Major QoL dimensions (Health, Education, etc.) |
| 2 | coarse_domain | 45 | Broad indicator groupings |
| 3 | fine_domain | 196 | Refined groupings |
| 4 | indicator | 569 | Indicator groups (promoted aggregates) |
| 5 | indicator | 1,763 | Individual indicators |

## 9 Outcome Categories (Layer 1)

1. Health & Longevity
2. Education & Knowledge
3. Economic Prosperity
4. Governance & Institutions
5. Environmental Quality
6. Demographics & Population
7. Security & Stability
8. Development & Infrastructure
9. Research & Innovation

## Directory Structure

```
v2.1/
├── CLAUDE.md                 # This file
├── outputs/
│   ├── A2/                   # Granger causality results
│   ├── A3/                   # PC-Stable conditional independence
│   ├── A4/                   # Effect quantification
│   ├── A5/                   # Interaction discovery
│   ├── A6/                   # Hierarchical layering (causal graph)
│   ├── B1/                   # Outcome discovery + indicator labels
│   ├── B1_indicator_descriptions/  # LLM-generated descriptions
│   ├── B2/                   # Semantic clustering
│   ├── B25/                  # SHAP scores
│   ├── B35/                  # 6-layer semantic hierarchy
│   ├── B36/                  # LLM-named hierarchy
│   └── B5/                   # Final visualization JSON
├── scripts/
│   ├── phaseA/               # Phase A scripts (A2-A6)
│   ├── phaseB/               # Phase B scripts (B1, B2, B35)
│   ├── create_final_visualization_json.py
│   ├── generate_indicator_descriptions.py
│   └── run_full_description_generation.py
└── logs/                     # Processing logs
```

## Data Sources

The 1,962 indicators come from:
- V-Dem Institute (458) - Democracy & governance
- UNESCO Institute for Statistics (456) - Education
- World Inequality Database (346) - Income inequality
- World Bank WDI (237) - Development indicators
- Quality of Government (85) - Institutional quality
- Penn World Table (26) - Economic comparisons
- Other sources (354) - Health, environment, etc.

## Processing Pipeline (Completed)

### Phase A: Statistical Discovery
- **A2**: Granger causality testing (15.9M pairs → 3.7M significant)
- **A3**: PC-Stable conditional independence (removed spurious correlations)
- **A4**: Effect size quantification with bootstrap validation
- **A5**: Interaction discovery (moderator effects)
- **A6**: Hierarchical layer assignment (21 causal layers → 6 viz layers)

### Phase B: Interpretability
- **B1**: Outcome discovery (9 validated QoL factors)
- **B2**: Semantic clustering (keyword + embedding)
- **B25**: SHAP importance scoring
- **B35**: 6-layer semantic hierarchy builder
- **B36**: LLM-assisted naming (Claude API)
- **B5**: Final JSON export with descriptions

## Key Statistics

| Metric | Value |
|--------|-------|
| Total Nodes | 2,583 |
| Total Edges | 9,950 |
| Causal Edges | 7,368 |
| Hierarchical Edges | 2,582 |
| Indicators | 1,962 |
| Indicators with Descriptions | 1,962 (100%) |
| Avg Description Reading Level | 13.5 (high school+) |

## Usage

### Load Visualization JSON
```python
import json

with open('outputs/B5/v2_1_visualization_final.json', 'r') as f:
    data = json.load(f)

nodes = data['nodes']
edges = data['edges']
metadata = data['metadata']

# Filter by layer
layer_1_nodes = [n for n in nodes if n['layer'] == 1]
causal_edges = [e for e in edges if e['relationship'] == 'causal']
```

### Load Indicator Descriptions
```python
import json

with open('outputs/B1/indicator_labels_comprehensive_v2.json', 'r') as f:
    descriptions = json.load(f)

# Get description for an indicator
indicator_id = "SP.DYN.LE00.IN"
desc = descriptions[indicator_id]
print(f"Label: {desc['label']}")
print(f"Description: {desc['description']}")
```

## Visualization Requirements

The JSON is designed for a radial/hierarchical visualization where:
- Layer 0 (root) is at the center
- Layers 1-5 radiate outward in concentric rings
- Hierarchical edges connect parents to children
- Causal edges show discovered causal relationships
- Node color = domain (9 colors)
- Node size = SHAP importance
- Edge opacity = weight/strength

## Regenerating the Final JSON

If you need to regenerate the visualization JSON:
```bash
cd /path/to/v2.1
python3 scripts/create_final_visualization_json.py
```

## Regenerating Indicator Descriptions

If you need to regenerate descriptions (requires Claude API key):
```bash
# Edit scripts/run_full_description_generation.py to add API key
python3 scripts/run_full_description_generation.py
```

## Contact / Attribution

This is part of the V2.0 Global Causal Discovery Research Project.
See parent directory `v2.0/CLAUDE.md` for full methodology and V1 lessons learned.

## Version History

- **v2.1** (Dec 2024): Final visualization-ready output with LLM descriptions
- **v2.0**: Full causal discovery pipeline
- **v1.0**: Initial proof-of-concept with 8 pre-selected outcomes
