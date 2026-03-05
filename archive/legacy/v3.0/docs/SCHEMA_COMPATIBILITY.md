# V3.0 Schema Compatibility with V2.1 Visualization

## V2.1 Visualization Schema (Current)

### Nodes (2,583)
| Field | Type | Required |
|-------|------|----------|
| id | string | Yes |
| label | string | Yes |
| description | string | Yes |
| layer | int | Yes (0-5) |
| node_type | string | Yes |
| domain | string | Yes |
| shap_importance | float | Yes |
| in_degree | int | Yes |
| out_degree | int | Yes |
| parent | string | Layers 1-5 |
| children | array | Layers 0-4 |
| label_source | string | Optional |

### Edges (9,950 = 7,368 causal + 2,582 hierarchical)
| Field | Type | Required |
|-------|------|----------|
| source | string | Yes |
| target | string | Yes |
| weight | float | Yes |
| relationship | string | Yes (causal/hierarchical) |

## V3.0 Country Graph Schema (Current)

### Per-Country JSON Structure
```json
{
  "country_code": "USA",
  "n_edges": 7368,
  "n_edges_with_data": 4521,
  "edges": [...]
}
```

### Edge Fields
| Field | Type | Description |
|-------|------|-------------|
| source | string | Source node ID |
| target | string | Target node ID |
| beta | float | Country-specific standardized coefficient |
| ci_lower | float | 2.5th percentile (bootstrap) |
| ci_upper | float | 97.5th percentile (bootstrap) |
| global_beta | float | V2.1 global weight (fallback) |
| data_available | bool | Whether country had data for this edge |

## Compatibility Mapping

### For API/Visualization Export

V3.0 country graphs should export with V2.1-compatible format:

```json
{
  "nodes": [...],  // From v21_nodes.csv
  "edges": [
    {
      "source": "indicator_a",
      "target": "indicator_b",
      "weight": 0.45,           // = beta (renamed)
      "relationship": "causal",
      "beta": 0.45,             // Keep original
      "ci_lower": 0.32,
      "ci_upper": 0.58,
      "global_beta": 0.42,
      "data_available": true,
      "country_specific": true  // Flag for V3.0 data
    }
  ],
  "hierarchy": {...},  // From V2.1
  "metadata": {
    "version": "3.0",
    "country": "USA",
    "source": "v3_country_estimation"
  }
}
```

### Key Mappings
| V3.0 Field | V2.1 Field | Notes |
|------------|------------|-------|
| beta | weight | Rename for compatibility |
| (add) | relationship | Always "causal" for estimated edges |
| (merge) | nodes | Import from v21_nodes.csv |
| (merge) | hierarchy | Import from V2.1 |

## Implementation Plan

1. **Post-estimation script**: `scripts/phaseA/A3_validate_graphs/export_v21_format.py`
   - Merge country edges with V2.1 nodes
   - Add hierarchical edges
   - Rename beta → weight
   - Add relationship field

2. **API endpoint**: `/api/country/{country_code}/graph`
   - Returns V2.1-compatible JSON
   - Includes country-specific betas with CIs
