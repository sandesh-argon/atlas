# A3: Conditional Independence Testing (PC-Stable)

**Phase**: A3 - Conditional Independence Validation
**Status**: ✅ Complete
**Input**: 1,157,230 Granger causality edges from A2
**Output**: 74,646 validated causal edges (valid DAG)
**Runtime**: ~1 hour

---

## Overview

A3 validates Granger causality edges using PC-Stable conditional independence testing to remove spurious correlations caused by confounding variables. The output is a directed acyclic graph (DAG) ready for effect quantification in A4.

**Key Innovation**: Custom PC-Stable implementation with pairwise deletion to handle 80% missing data, using Fisher-Z statistical testing (alpha=0.001).

---

## Pipeline Steps

### 1. Smart Pre-Pruning (1.16M → 114K edges)
**Purpose**: Reduce computational burden while retaining highest-confidence edges

**Filters**:
- FDR p-value < 1e-06 (ultra-strict)
- F-statistic > 40
- Result: 90.1% reduction

**Script**: `scripts/step1c_smart_prepruning.py`

**Output**: `outputs/smart_prepruned_edges.pkl` (114,274 edges)

---

### 2. Pairwise PC-Stable Testing (114K → 96K edges)
**Purpose**: Test conditional independence X ⊥ Y | Z to remove confounded edges

**Method**:
- Fisher-Z transformation for partial correlation testing
- Pairwise deletion for missing data (not complete case)
- Max conditioning set size: 2 (individual + pairs of confounders)
- Alpha = 0.001 (99.9% confidence)

**Configuration**:
```python
max_cond_size = 2
max_confounders = 10
min_obs = 30
alpha = 0.001
n_cores = 8
```

**Script**: `scripts/step2_custom_pairwise_pc.py`

**Output**: `outputs/A3_validated_fisher_z_alpha_0.001.pkl` (95,939 edges)

**Runtime**: 45 minutes

---

### 3. Cycle Removal (96K → 75K edges)
**Purpose**: Convert to valid DAG by removing cycles

**Method**: Memory-safe greedy feedback arc set (FAS)
1. Find one cycle using DFS
2. Identify weakest edge (lowest F-statistic)
3. Remove it
4. Repeat until acyclic

**Script**: `scripts/step3_remove_cycles.py`

**Output**: `outputs/A3_final_dag.pkl` (74,646 edges, valid DAG)

**Runtime**: 5 minutes

---

## Output Files

### Primary Outputs (Use These for A4)

**1. `outputs/A3_final_dag.pkl`** ← **PRIMARY OUTPUT**
- NetworkX DiGraph with 74,646 edges, 4,505 nodes
- Valid DAG (acyclic, 99.5% connectivity)
- Contains: graph object, edge DataFrame, validation metrics, metadata

**Load in Python**:
```python
import pickle
with open('outputs/A3_final_dag.pkl', 'rb') as f:
    data = pickle.load(f)

G = data['graph']  # NetworkX DiGraph
edges_df = data['edges']  # pandas DataFrame
validation = data['validation']  # Dict with validation metrics
metadata = data['metadata']  # Dict with processing metadata
```

**2. `outputs/A3_final_edge_list.csv`**
- Human-readable edge list
- Columns: `source`, `target`, `f_statistic`, `p_value`, `best_lag`

**3. `outputs/A3_final_dag.graphml`**
- GraphML format for visualization (Gephi, Cytoscape, etc.)

---

### Intermediate Outputs (For Reference)

**4. `outputs/smart_prepruned_edges.pkl`**
- 114,274 pre-pruned edges (after Step 1)
- Contains: edges DataFrame, metadata

**5. `outputs/A3_validated_fisher_z_alpha_0.001.pkl`**
- 95,939 PC-Stable validated edges (after Step 2, before cycle removal)
- Contains: validated edges, removed edges, metadata

---

## Quick Start

### Running the Full Pipeline

```bash
# Step 1: Smart pre-pruning
python scripts/step1c_smart_prepruning.py

# Step 2: Pairwise PC-Stable testing (45 min)
python scripts/step2_custom_pairwise_pc.py

# Monitor progress (in separate terminal)
./monitor.sh

# Step 3: Remove cycles (5 min)
python scripts/step3_remove_cycles.py
```

### Loading Results

```python
import pickle
import pandas as pd
import networkx as nx

# Load final DAG
with open('outputs/A3_final_dag.pkl', 'rb') as f:
    a3_output = pickle.load(f)

# Access components
G = a3_output['graph']
edges_df = a3_output['edges']

print(f"Nodes: {G.number_of_nodes():,}")
print(f"Edges: {G.number_of_edges():,}")
print(f"Is DAG: {nx.is_directed_acyclic_graph(G)}")

# Example: Get edges for a specific variable
var = 'life_expectancy'
incoming = [(u, data) for u, v, data in G.in_edges(var, data=True)]
outgoing = [(v, data) for u, v, data in G.out_edges(var, data=True)]
```

---

## Key Statistics

### Final Output
- **Nodes**: 4,505 variables
- **Edges**: 74,646 validated causal edges
- **DAG Valid**: ✅ Yes (acyclic)
- **Connectivity**: 99.5%
- **Mean F-statistic**: 84.32
- **Graph Density**: 0.37% (very sparse)

### Reduction Pipeline
| Step | Edges | Reduction |
|------|-------|-----------|
| A2 Input | 1,157,230 | - |
| After Pre-pruning | 114,274 | 90.1% |
| After PC-Stable | 95,939 | 16.0% |
| After Cycle Removal | 74,646 | 22.2% |
| **Total** | **74,646** | **93.5%** |

---

## Technical Details

### Fisher-Z Test for Conditional Independence

**Hypothesis**: X ⊥ Y | Z (X and Y are independent given Z)

**Test Statistic**:
```python
def fisher_z_test(partial_r, n, alpha=0.001):
    """Test if partial correlation is significantly different from 0"""
    # Fisher-Z transformation
    z = 0.5 * np.log((1 + partial_r) / (1 - partial_r))

    # Standard error
    se = 1 / np.sqrt(n - 3)

    # Z-statistic
    z_stat = abs(z / se)

    # Two-tailed p-value
    p_value = 2 * (1 - norm.cdf(z_stat))

    # Independent if p > alpha
    return (p_value > alpha)
```

**Interpretation**:
- If `p_value > 0.001`: X and Y are conditionally independent → Remove edge
- If `p_value ≤ 0.001`: X and Y remain dependent → Keep edge

---

### Pairwise Deletion for Missing Data

**Challenge**: 80% missing rate means no (Country, Year) has all 4,400+ variables

**Solution**: For each test X ⊥ Y | Z, use only observations where X, Y, Z are all present

```python
def test_single_edge(X, Y, Z, data_dict):
    # Get pairwise data (only X, Y, Z)
    df = pd.DataFrame({
        'X': data_dict[X],
        'Y': data_dict[Y],
        'Z': data_dict[Z]
    }).dropna()  # Drop only rows where X, Y, or Z is missing

    # Compute partial correlation
    partial_r = compute_partial_correlation(df['X'], df['Y'], df['Z'])

    # Fisher-Z test
    is_independent = fisher_z_test(partial_r, len(df), alpha=0.001)

    return is_independent
```

**Advantages**:
- Maximizes available data for each test
- Different tests use different subsets (all with sufficient overlap)
- Minimum 30 observations required per test

---

### Memory-Safe Cycle Removal

**Challenge**: `nx.simple_cycles()` enumerates ALL cycles (exponential memory)

**Solution**: Find one cycle at a time using DFS

```python
def remove_cycles(G):
    while not nx.is_directed_acyclic_graph(G):
        # Find ONE cycle (O(V+E) memory)
        cycle = nx.find_cycle(G, orientation='original')

        # Find weakest edge in cycle
        weakest = min(cycle_edges, key=lambda e: e['f_statistic'])

        # Remove it
        G.remove_edge(weakest['source'], weakest['target'])

    return G
```

**Complexity**:
- Time: O(E × V) in worst case (remove one edge per iteration)
- Memory: O(V + E) (constant per iteration)

---

## Validation Metrics

### DAG Validity
- ✅ **Acyclic**: No cycles (verified with `nx.is_directed_acyclic_graph()`)
- ✅ **Connectivity**: 99.5% of nodes in largest weakly connected component
- ✅ **Edge Count**: 74,646 (within 30K-100K target range)

### Signal Strength
- ✅ **Mean F-statistic**: 84.32 (strong signals)
- ✅ **Median F-statistic**: 69.58
- ✅ **90th percentile**: 131.47

### Degree Distribution
- **Mean in-degree**: 16.6
- **Mean out-degree**: 16.6
- **Max in-degree**: 478 (highly influenced variable)
- **Max out-degree**: 423 (broad influencer)

---

## Troubleshooting

### Issue: PC-Stable returns 0 complete observations
**Cause**: Using complete case deletion with 80% missing rate

**Solution**: Use pairwise deletion (custom implementation in `step2_custom_pairwise_pc.py`)

---

### Issue: Cycle removal crashes (OOM error)
**Cause**: `nx.simple_cycles()` tries to enumerate all cycles

**Solution**: Use `nx.find_cycle()` to find one cycle at a time (`step3_remove_cycles.py`)

---

### Issue: Too many edges remain after PC-Stable
**Cause**: Pre-pruning filters too lenient

**Solution**: Adjust filters in `step1c_smart_prepruning.py`:
- Increase `fdr_cutoff` (lower p-value threshold)
- Increase `f_stat_min` (higher F-statistic threshold)

---

## Logs

All execution logs saved in `logs/`:
- `pairwise_pc_fisher_z.log` - PC-Stable execution log
- `remove_cycles.log` - Cycle removal log
- `step2_pc_stable.log` - Earlier PC-Stable attempts

**Monitor progress**:
```bash
tail -f logs/pairwise_pc_fisher_z.log
```

---

## Checkpoints

Checkpoints saved in `checkpoints/`:
- `pairwise_pc_checkpoint.pkl` - Resume point for PC-Stable (saved every 5K edges)

**Resume from checkpoint**:
```python
# Automatically detected by step2_custom_pairwise_pc.py
# Will prompt: "Checkpoint found. Resume from edge X? (yes/no)"
```

---

## Next Steps (A4)

**Input**: `outputs/A3_final_dag.pkl`

**A4 Tasks**:
1. Quantify effect sizes (beta coefficients)
2. Compute confidence intervals (bootstrap)
3. Apply backdoor adjustment for confounding
4. Prepare metadata for A5 interaction discovery

**Expected Runtime**: 4-6 days

---

## References

- **PC-Stable**: Colombo & Maathuis (2014). "Order-independent constraint-based causal structure learning." JMLR.
- **Fisher-Z**: Fisher (1921). "On the probable error of a coefficient of correlation." Metron.
- **Feedback Arc Set**: Eades et al. (1993). "A fast and effective heuristic for the feedback arc set problem." IPL.

---

## Contact

For questions about A3 methodology or outputs, see:
- **A3_FINAL_STATUS.md** - Detailed results and validation
- **V2 Master Instructions**: `<repo-root>/v2.0/v2_master_instructions.md`
- **CLAUDE.md**: `<repo-root>/v2.0/CLAUDE.md`

---

**Last Updated**: November 15, 2025
**Status**: ✅ Complete - Ready for A4
