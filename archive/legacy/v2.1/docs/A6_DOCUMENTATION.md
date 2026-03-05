# A6: Hierarchical Layering - Technical Documentation

## Overview

**A6 Hierarchical Layering** assigns hierarchical layers to all nodes in the combined causal graph (A4 direct effects + A5 interactions) using topological sort. This creates a layered causal structure where:
- Layer 0 = Root drivers (no incoming edges)
- Higher layers = Increasing distance from drivers
- Top layers = Outcomes and endpoints

**Location**: `<repo-root>/v2.0/v2.1/scripts/A6/`

**Runtime**: 2-3 hours

**Key Output**: `A6_hierarchical_graph.pkl` - Complete graph with layer assignments and centrality metrics

---

## Critical Architectural Decision (December 2025 Fix)

### The Interaction Node Problem

**Original Issue**: Early implementations incorrectly created 4,254 virtual `INTERACT_` nodes as actual graph nodes, inflating the total from 3,872 real indicators to 8,126 nodes (52.4% were fake).

**Correct Implementation**: Interactions are stored as **edge metadata** (`edge['moderators']`), not as separate nodes. This preserves the true causal structure where interactions modify edge effects rather than acting as independent variables.

```python
# CORRECT: Interaction as edge metadata
edge = {
    'source': 'mechanism_1',
    'target': 'outcome',
    'weight': 0.34,
    'moderators': [
        {
            'moderator': 'mechanism_2',
            'beta_interaction': 0.12,
            'r_squared': 0.45,
            'p_value': 0.001
        }
    ]
}

# WRONG: Virtual interaction nodes (DO NOT USE)
# INTERACT_M1_M2 → outcome  # This inflates node count artificially
```

---

## Input Data

### A4: Direct Causal Effects
**Source**: `<repo-root>/v2.0/v2.1/outputs/A4/lasso_effect_estimates.pkl`

**Structure**:
```python
{
    'validated_edges': [
        {
            'source': 'wdi_physicians_per_1000',
            'target': 'wdi_life_expectancy',
            'beta': 0.34,
            'ci_lower': 0.29,
            'ci_upper': 0.39,
            'p_value': 3.4e-12
        },
        ...
    ]
}
```

**Expected**: 8,000-12,000 validated edges from LASSO effect estimation

### A5: Mechanism Interactions
**Source**: `<repo-root>/v2.0/v2.1/outputs/A5/A5_interaction_results.pkl`

**Structure**:
```python
{
    'validated_interactions': [
        {
            'mechanism_1': 'wdi_physicians',
            'mechanism_2': 'wdi_health_expenditure',
            'outcome': 'wdi_life_expectancy',
            'beta_interaction': 0.12,
            'r_squared': 0.45,
            'p_value': 0.001,
            't_statistic': 3.8
        },
        ...
    ]
}
```

**Expected**: 1,000-3,000 validated interaction effects

---

## Algorithm: Topological Sort Layer Assignment

### Core Logic

```python
def assign_layers(G):
    """
    Assigns hierarchical layers using topological sort.

    Algorithm:
    1. Find root nodes (in_degree == 0) → Layer 0
    2. For each node in topological order:
       - Layer = max(predecessor layers) + 1
    3. Validate: All edges must go from lower to higher layer
    """
    layers = {}

    # Step 1: Root nodes
    roots = [n for n in G.nodes() if G.in_degree(n) == 0]
    for root in roots:
        layers[root] = 0

    # Step 2: Topological traversal
    for node in nx.topological_sort(G):
        if node not in layers:
            pred_layers = [layers[pred] for pred in G.predecessors(node)]
            if pred_layers:
                layers[node] = max(pred_layers) + 1
            else:
                layers[node] = 0

    return layers
```

### Properties Guaranteed

1. **Acyclic**: All edges go from layer L to layer L' where L < L'
2. **Longest Path**: Layer assignment represents longest path from any root node
3. **Causal Ordering**: Layer k cannot influence layer j if k > j

### Example Layer Distribution (V2.1)

```
Layer 0:    245 nodes  (root drivers - no causes)
Layer 1:    183 nodes  (direct effects of drivers)
Layer 2:    198 nodes
...
Layer 19:    42 nodes  (penultimate outcomes)
Layer 20:    28 nodes  (ultimate outcomes)
```

---

## Centrality Metrics

### 1. PageRank (Weighted)

**Purpose**: Identifies nodes that are "important" based on incoming edge weights

**Computation**:
```python
pagerank = nx.pagerank(G, weight='weight', max_iter=100)
# weight = |beta| from A4
```

**Interpretation**:
- High PageRank = Many strong incoming effects
- Used to identify key outcome indicators
- Normalized to [0, 1]

### 2. Betweenness Centrality

**Purpose**: Identifies "bridge" nodes that mediate many causal pathways

**Computation**:
```python
betweenness = nx.betweenness_centrality(G, weight='weight')
```

**Interpretation**:
- High betweenness = Node lies on many shortest paths
- Identifies critical mechanism indicators
- Runtime: 30-60 minutes for 3,872 nodes

### 3. Degree Centrality

**Purpose**: Simple connectivity measure

**Metrics**:
- `in_degree`: Number of incoming edges (how many causes)
- `out_degree`: Number of outgoing edges (how many effects)

**Interpretation**:
- High in-degree = Complex outcome with many causes
- High out-degree = Influential driver affecting many outcomes

---

## Validation Framework

### 1. DAG Validation

**Check**: Graph must be a Directed Acyclic Graph (no cycles)

```python
is_dag = nx.is_directed_acyclic_graph(G)
# If False: Find cycles and report
cycles = list(nx.simple_cycles(G))
```

**Why Critical**: Cycles violate causal ordering (A→B→A is logically impossible)

### 2. Known Outcome Placement

**Success Criterion**: ≥70% of known outcomes must be in top 2 layers

**Known Outcomes** (from V1 validation):
```python
KNOWN_OUTCOMES = [
    'wdi_life_expectancy',
    'wdi_years_schooling',
    'wdi_gdp_per_capita',
    'wdi_infant_mortality',
    'wdi_gini_index',
    'wdi_homicides',
    'who_nutrition_index',
    'wdi_internet_access',
    'wdi_unemployment',
    'wdi_poverty_rate'
]
```

**Validation Logic**:
```python
top_2_layers = {n_layers - 1, n_layers - 2}
in_top_2 = sum(1 for outcome in found_outcomes
               if layers[outcome] in top_2_layers)
pct_in_top_2 = in_top_2 / len(found_outcomes)

# PASS: pct_in_top_2 >= 0.70
# FAIL: pct_in_top_2 < 0.70
```

### 3. Connectivity Check

**Success Criterion**: ≤5 weakly connected components

```python
n_components = nx.number_weakly_connected_components(G)
# PASS: n_components <= 5
# WARN: n_components > 5 (too fragmented)
```

### 4. Self-Loop Check

**Requirement**: Zero self-loops (node cannot cause itself)

```python
self_loops = list(nx.selfloop_edges(G))
if len(self_loops) > 0:
    G.remove_edges_from(self_loops)  # Auto-fix
```

---

## Output Schema

### Primary Output: `A6_hierarchical_graph.pkl`

**Structure**:
```python
{
    'graph': networkx.DiGraph(),
    'layers': {
        'node_id': layer_number,
        ...  # All 3,872 nodes
    },
    'n_layers': 21,  # V2.1 example
    'centrality': {
        'pagerank': {'node_id': 0.0031, ...},
        'betweenness': {'node_id': 0.042, ...},
        'in_degree': {'node_id': 12, ...},
        'out_degree': {'node_id': 5, ...}
    },
    'outcome_validation': {
        'found_outcomes': ['wdi_life_expectancy', ...],
        'missing_outcomes': [],
        'pct_in_top_2': 0.83,
        'n_in_bottom_50': 0
    },
    'metadata': {
        'n_nodes': 3872,
        'n_edges': 11003,
        'n_layers': 21,
        'n_components': 1,
        'avg_degree': 5.68,
        'timestamp': '2025-12-05T13:21:00'
    }
}
```

### Graph Edge Structure

**Direct Effect Edge**:
```python
{
    'source': 'mechanism_A',
    'target': 'outcome_X',
    'weight': 0.34,  # |beta| from A4
    'beta': 0.34,
    'ci_lower': 0.29,
    'ci_upper': 0.39,
    'edge_type': 'direct',
    'moderators': []  # Empty list if no interactions
}
```

**Edge with Moderator** (from A5 interaction):
```python
{
    'source': 'mechanism_A',
    'target': 'outcome_X',
    'weight': 0.34,
    'beta': 0.34,
    'edge_type': 'direct',
    'moderators': [
        {
            'moderator': 'mechanism_B',  # The interacting variable
            'partner': 'mechanism_A',
            'beta_interaction': 0.12,
            'r_squared': 0.45,
            'p_value': 0.001,
            't_statistic': 3.8
        }
    ]
}
```

**Interaction-Only Edge** (no direct effect in A4):
```python
{
    'source': 'mechanism_A',
    'target': 'outcome_X',
    'weight': 0.06,  # |beta_interaction| / 2
    'beta': None,  # No direct beta available
    'edge_type': 'interaction_only',
    'moderators': [
        {
            'moderator': 'mechanism_B',
            'beta_interaction': 0.12,
            ...
        }
    ]
}
```

### Secondary Outputs

**1. Layer Assignments CSV** (`A6_layer_assignments.csv`):
```csv
node,layer,pagerank,betweenness,in_degree,out_degree
wdi_life_expectancy,20,0.0031,0.042,12,0
wdi_physicians,5,0.0008,0.015,3,8
...
```

**2. Graph Statistics** (`A6_graph_statistics.txt`):
```
A6 HIERARCHICAL LAYERING - GRAPH STATISTICS
======================================================================

Timestamp: 2025-12-05T13:21:00

Graph Structure:
  Total nodes: 3,872
  Total edges: 11,003
  Hierarchical layers: 21
  Weakly connected components: 1
  Average degree: 5.68

Layer Distribution:
  Layer 0: 245 nodes
  Layer 1: 183 nodes
  ...
  Layer 20: 28 nodes

Known Outcome Validation:
  Outcomes found: 10 / 10
  In top 2 layers: 83.3%
  In bottom 50%: 0
```

---

## Pipeline Integration

### Upstream Dependencies

```
A4 (Effect Estimation) ──┐
                         ├──> A6 (Hierarchical Layering)
A5 (Interactions) ───────┘
```

### Downstream Usage

```
A6 (Hierarchical Graph) ──┬──> B1 (Outcome Discovery)
                          ├──> B2 (Semantic Clustering)
                          └──> B3.5 (Hierarchy Builder)
```

### Data Flow

1. **A4 → A6**: Direct causal edges with effect sizes
2. **A5 → A6**: Interaction effects as edge moderators
3. **A6 → B1**: Node list for factor analysis
4. **A6 → B2**: Graph structure for clustering validation
5. **A6 → B3.5**: Layers, centrality for visualization hierarchy

---

## Performance Characteristics

### V2.1 Benchmark (1,962 nodes)

| Operation | Time | Memory |
|-----------|------|--------|
| Load A4/A5 | 5s | 100 MB |
| Build graph | 30s | 250 MB |
| Validate DAG | 10s | 50 MB |
| Assign layers | 45s | 150 MB |
| PageRank | 15s | 100 MB |
| Betweenness | 40m | 200 MB |
| Export | 20s | 300 MB |
| **Total** | **42-45 min** | **300 MB peak** |

### V2.0 Full Scale (3,872 nodes)

| Operation | Time | Memory |
|-----------|------|--------|
| Betweenness | 90-120m | 400 MB |
| **Total** | **2-3 hours** | **600 MB peak** |

**Bottleneck**: Betweenness centrality is O(n³) in worst case

---

## Key Algorithms

### Topological Sort (NetworkX)

**Algorithm**: Kahn's algorithm with depth-first search

**Complexity**: O(V + E) where V = nodes, E = edges

**Implementation**:
```python
for node in nx.topological_sort(G):
    # Process in causal order
    # Guaranteed: all predecessors processed before node
```

### PageRank (Power Iteration)

**Algorithm**: Iterative matrix multiplication

**Formula**:
```
PR(n) = (1-d)/N + d * Σ(PR(pred) / out_degree(pred))
```

Where:
- d = damping factor (0.85)
- N = total nodes
- Σ over all predecessors of n

**Convergence**: Typically 50-100 iterations

### Betweenness Centrality (Brandes' Algorithm)

**Algorithm**: Single-source shortest paths from every node

**Complexity**: O(VE) for unweighted, O(VE + V²log V) for weighted

**Why Slow**: Must compute shortest paths from all V nodes to all other nodes

---

## Common Issues and Solutions

### Issue 1: Cycles Detected

**Symptom**: `ValueError: Graph contains cycles - cannot proceed`

**Cause**: Bidirectional causation (A→B and B→A) or cyclic paths

**Solution**:
1. Check A3 (PC-Stable) output - should have removed cycles
2. If cycles remain, use `remove_cycles` script from A3
3. Verify A5 interactions don't create reverse causation

### Issue 2: Too Many Components

**Symptom**: `n_components > 5` warning

**Cause**: Graph fragmented into disconnected subgraphs

**Solutions**:
- Check A2 prefiltering - may be too aggressive
- Verify A4 bootstrap validation didn't drop too many edges
- Consider relaxing A4 p-value threshold

### Issue 3: Known Outcomes in Bottom Layers

**Symptom**: `pct_in_top_2 < 0.70` failure

**Cause**: Incorrect causal structure - outcomes should be endpoints

**Investigation**:
1. Check which outcomes are misplaced
2. Verify A4 effect directions (should point TO outcomes, not FROM)
3. Review A3 edge orientation logic

### Issue 4: Betweenness Takes Too Long

**Symptom**: Betweenness computation runs >3 hours

**Solution**:
```python
# Use approximate betweenness for large graphs
betweenness = nx.betweenness_centrality(
    G,
    k=1000,  # Sample 1000 nodes instead of all
    weight='weight'
)
```

**Trade-off**: 90% faster, ~95% accurate

---

## Configuration

### Layer Validation Thresholds

```python
# Known outcomes in top 2 layers (lines 414-418)
MIN_OUTCOME_PCT_TOP_2 = 0.70  # 70% required

# Connectivity (lines 252-256)
MAX_COMPONENTS = 5  # Warn if exceeded

# Betweenness timeout (lines 341-343)
BETWEENNESS_TIMEOUT = 7200  # 2 hours max
```

### Centrality Parameters

```python
# PageRank (line 337)
PAGERANK_MAX_ITER = 100
PAGERANK_DAMPING = 0.85

# Betweenness (line 343)
BETWEENNESS_WEIGHT = 'weight'  # Use edge weights
```

---

## V2.1 vs V2.0 Differences

| Aspect | V2.0 | V2.1 |
|--------|------|------|
| **Nodes** | 3,872 | 1,962 (stratified sample) |
| **Edges** | 11,003 | ~5,500 |
| **Layers** | 21 | 18-20 |
| **Runtime** | 2-3 hours | 40-45 minutes |
| **Path Config** | Hardcoded | Uses `v21_config.py` |
| **Input** | V2.0 A4/A5 | V2.1 A4/A5 |
| **Output Dir** | `phaseA/A6_hierarchical_layering/outputs/` | `v2.1/outputs/A6/` |

---

## Testing and Validation

### Unit Tests (Recommended)

```python
def test_no_cycles():
    """Verify DAG property"""
    assert nx.is_directed_acyclic_graph(G)

def test_layer_ordering():
    """All edges go from lower to higher layer"""
    for u, v in G.edges():
        assert layers[u] < layers[v]

def test_outcome_placement():
    """Known outcomes in top 2 layers"""
    top_2 = {n_layers - 1, n_layers - 2}
    in_top_2 = sum(1 for o in KNOWN_OUTCOMES
                   if o in layers and layers[o] in top_2)
    assert in_top_2 / len(KNOWN_OUTCOMES) >= 0.70

def test_centrality_ranges():
    """Centrality scores in [0, 1]"""
    for score in centrality['pagerank'].values():
        assert 0 <= score <= 1
    for score in centrality['betweenness'].values():
        assert 0 <= score <= 1
```

### Integration Test

```bash
# Run full A6 pipeline
python <repo-root>/v2.0/v2.1/scripts/A6/run_hierarchical_layering.py

# Verify outputs exist
ls -lh <repo-root>/v2.0/v2.1/outputs/A6/
# Should see:
# - A6_hierarchical_graph.pkl
# - A6_layer_assignments.csv
# - A6_graph_statistics.txt
```

---

## Future Improvements

### 1. Parallel Betweenness Computation
Use `joblib` to parallelize betweenness across multiple nodes:
```python
from joblib import Parallel, delayed

def compute_betweenness_chunk(nodes):
    return nx.betweenness_centrality_subset(G, nodes, G.nodes())

chunks = [nodes[i:i+100] for i in range(0, len(nodes), 100)]
results = Parallel(n_jobs=8)(
    delayed(compute_betweenness_chunk)(chunk) for chunk in chunks
)
```

### 2. Incremental Layer Assignment
Cache layer assignments and only recompute when graph changes:
```python
if checkpoint_exists('A6_layers.pkl'):
    layers = load_checkpoint('A6_layers.pkl')
    new_nodes = set(G.nodes()) - set(layers.keys())
    # Only compute for new_nodes
```

### 3. Dynamic Layer Compression
Auto-detect optimal layer groupings based on layer sizes:
```python
def compress_layers(layer_counts, target_groups=5):
    # Group adjacent layers with similar sizes
    # Use dynamic programming to minimize variance
```

---

## References

1. **Topological Sort**: Kahn, A. B. (1962). "Topological sorting of large networks". Communications of the ACM.
2. **PageRank**: Page, L. et al. (1999). "The PageRank Citation Ranking: Bringing Order to the Web". Stanford InfoLab.
3. **Betweenness**: Brandes, U. (2001). "A faster algorithm for betweenness centrality". Journal of Mathematical Sociology.
4. **DAG Validation**: Tarjan, R. (1972). "Depth-first search and linear graph algorithms". SIAM Journal on Computing.

---

## Contact and Support

**Script Location**: `<repo-root>/v2.0/v2.1/scripts/A6/run_hierarchical_layering.py`

**Log Files**: `<repo-root>/v2.0/v2.1/logs/a6_run.log`

**Output Directory**: `<repo-root>/v2.0/v2.1/outputs/A6/`

**Configuration**: Paths defined in `<repo-root>/v2.0/v2.1/scripts/v21_config.py`
