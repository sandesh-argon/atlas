# A6 Hierarchical Layering

**Phase**: A6 - Final Phase A Step
**Status**: COMPLETE
**Date**: December 2025
**Runtime**: ~30 minutes

---

## Quick Summary

A6 assigns hierarchical layers to all nodes in the combined causal graph (A4 + A5) using topological sort. Creates a 21-layer DAG with 3,872 nodes and 11,003 edges.

**Key Result**: 3,872 indicators organized into 21 hierarchical layers with centrality scores

---

## Results

| Metric | Value |
|--------|-------|
| **Total nodes** | 3,872 |
| **Total edges** | 11,003 |
| **Causal layers** | 21 (0-20) |
| **Layer 0 (Drivers)** | 810 nodes |
| **Layer 19-20 (Outcomes)** | 26 nodes |

### Layer Distribution
- Layers 0-5: Early mechanisms (2,043 nodes)
- Layers 6-14: Middle mechanisms (1,369 nodes)
- Layers 15-18: Late mechanisms (434 nodes)
- Layers 19-20: Outcomes (26 nodes)

---

## Inputs

| Input | Source | Count |
|-------|--------|-------|
| **A4 Direct Effects** | `lasso_effect_estimates_WITH_WARNINGS.pkl` | 9,759 edges |
| **A5 Interactions** | `A5_interaction_results_FILTERED_STRICT.pkl` | 4,254 interactions |

---

## Outputs

### Primary Output
**`outputs/A6_hierarchical_graph.pkl`**
```python
{
    'graph': networkx.DiGraph,       # Full causal graph
    'layers': {node_id: layer},      # Layer assignments (0-20)
    'centrality': {
        'pagerank': {...},
        'betweenness': {...},
        'in_degree': {...},
        'out_degree': {...}
    },
    'metadata': {
        'n_nodes': 3872,
        'n_edges': 11003,
        'n_layers': 21
    }
}
```

### Secondary Outputs
- `outputs/A6_layer_assignments.csv` - Node-layer mapping

---

## Method

1. **Graph Construction**: Combine A4 edges + A5 interactions
2. **Cycle Removal**: Remove weak edges causing cycles (maintained DAG property)
3. **Topological Sort**: Kahn's algorithm for layer assignment
4. **Centrality Computation**: PageRank, betweenness, degree centrality

---

## Validation

- DAG validity: `nx.is_directed_acyclic_graph(G) == True`
- Layer consistency: All edges satisfy `layers[source] < layers[target]`
- No interaction nodes in final graph (clean indicator-only structure)

---

## Files

```
A6_hierarchical_layering/
├── README.md
├── scripts/
│   └── run_hierarchical_layering.py
└── outputs/
    ├── A6_hierarchical_graph.pkl
    └── A6_layer_assignments.csv
```

---

## Next Steps

Outputs feed into Phase B:
- **B1**: Uses layers for outcome identification (top layers = outcomes)
- **B2**: Uses centrality for mechanism identification
- **B2.5**: Uses graph for SHAP context
- **B3.5**: Uses layers + centrality for visualization hierarchy

---

**Last Updated**: December 2025
**Status**: COMPLETE
