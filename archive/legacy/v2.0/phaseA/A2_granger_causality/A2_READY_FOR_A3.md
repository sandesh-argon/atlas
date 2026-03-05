# A2 → A3 Handoff Document

**Date**: November 14, 2025
**Status**: ✅ A2 COMPLETE, READY FOR A3

---

## A2 Final Output

### Primary Output for A3
**File**: `outputs/granger_fdr_corrected.pkl`
**Size**: 1.3 GB
**Contents**: 9,256,206 Granger test results with FDR-corrected q-values

**Filter for A3 input**:
```python
import pickle

with open('outputs/granger_fdr_corrected.pkl', 'rb') as f:
    fdr_data = pickle.load(f)

# Extract edges with q<0.01
edges_q01 = fdr_data['results'][fdr_data['results']['significant_fdr_001']]

print(f"A3 input: {len(edges_q01):,} edges")
# Output: 1,157,230 edges
```

### Supporting Data
**File**: `../A1_missingness_analysis/outputs/A2_preprocessed_data.pkl`
**Size**: ~500 MB
**Contents**: 6,368 imputed indicators (1990-2024)

---

## Decision Summary: Skip Bootstrap

### Why Bootstrap is Skipped at This Stage

**Original V2 plan**: A2 → Bootstrap → A3
**Modified plan**: A2 → A3 → Bootstrap

**Rationale**:
1. **Computational cost**: Bootstrap on 1.16M edges = weeks of computation
2. **Redundancy**: A3 will prune 1.16M → 30K-80K anyway
3. **Better placement**: Bootstrap validates FINAL graph stability, not intermediate pruning
4. **Scientific validity**: FDR already controlled false discoveries

**Evidence this is correct**:
- FDR diagnostic shows healthy p-value distribution
- 11.8% very significant (p<0.001) indicates genuine signal
- No "barely significant" spike (ratio 0.63)
- Median F-statistic = 6.55 (good predictive power)

### Modified Workflow
```
A2 (Complete)
  ↓
  9.26M Granger tests
  ↓
  FDR correction (Benjamini-Hochberg)
  ↓
  1.16M edges @ q<0.01
  ↓
A3 (Next) - PC-Stable Conditional Independence
  ↓
  30K-80K validated causal edges
  ↓
A4 - Effect Quantification (Backdoor Adjustment)
  ↓
  20K-60K edges with effect sizes
  ↓
Bootstrap Final Graph (12-24 hours)
  ↓
  Final validated causal network
```

---

## A3 Configuration Recommendations

### Input Configuration
```python
# A3 input edges
n_edges_input = 1,157,230  # q<0.01 from A2
n_variables = 6,368        # Indicators from A1

# Expected computational load
# PC-Stable: O(edges × variables²) conditional independence tests
# With parallelization: ~2-4 days
```

### PC-Stable Parameters
```python
from causallearn.search.ConstraintBased.PC import pc

causal_graph = pc(
    data_matrix,
    alpha=0.001,           # Stricter than A2 (removes residual spurious correlations)
    indep_test='fisherz',  # Fisher's Z for continuous data
    stable=True,           # Order-independent (CRITICAL for reproducibility)
    background_knowledge=granger_edges,  # Temporal precedence from A2
    uc_rule=1,             # Conservative orientation
    uc_priority=3,         # Prioritize background knowledge
    show_progress=True,
    verbose=True
)
```

### Resource Allocation
- **Parallel cores**: 12 MAX (thermal safety)
- **RAM**: 18-20 GB expected
- **Checkpoint interval**: Every 10K edges processed
- **Runtime**: 2-4 days

### Expected Output
- **Edge count**: 30,000 - 80,000 validated causal edges
- **Graph properties**:
  - DAG (no cycles)
  - Connected (>80% in largest component)
  - Hierarchical (clear layer structure)

---

## A3 Success Criteria

### Quantitative Criteria

1. **Edge Count**: 10,000 ≤ n_edges ≤ 100,000
   - Too few (<10K): Over-pruned, lost signal
   - Too many (>100K): Under-pruned, still has confounding

2. **DAG Validity**: `nx.is_directed_acyclic_graph(G) == True`
   - Any cycles indicate methodological error

3. **Graph Connectivity**: Largest component > 80% of nodes
   - Too fragmented indicates poor skeleton estimation

4. **Reduction Ratio**: 95-99% reduction from A2
   - Current: 1.16M → expect 30K-80K (97.4-99.3% reduction)

### Qualitative Criteria

1. **Edges make domain sense**
   - Healthcare → Health outcomes
   - Education → Economic development
   - Governance → Multiple downstream effects

2. **Temporal precedence preserved**
   - Lag structure from A2 maintained
   - No backward causation

3. **Confounding removed**
   - Classical confounders (GDP, population) properly mediated
   - Indirect pathways pruned

---

## A3 Validation Checkpoints

### During Execution

**Every 10K edges processed**:
```python
# Log progress
print(f"Processed: {processed_edges:,} / {total_edges:,}")
print(f"Current graph size: {current_graph.number_of_edges()} edges")
print(f"Elapsed: {elapsed_hours:.2f} hours")
print(f"Estimated remaining: {est_remaining_hours:.2f} hours")
```

**Save checkpoint**:
```python
checkpoint = {
    'partial_graph': current_graph,
    'processed_edges': processed_edges,
    'timestamp': datetime.now(),
    'metadata': {...}
}

with open(f'checkpoints/a3_checkpoint_{processed_edges:08d}.pkl', 'wb') as f:
    pickle.dump(checkpoint, f)
```

### After Completion

**Immediate validation**:
```python
import networkx as nx

# 1. Check DAG validity
assert nx.is_directed_acyclic_graph(G), "ERROR: Graph has cycles!"

# 2. Check edge count
assert 10_000 <= G.number_of_edges() <= 100_000, f"Edge count {G.number_of_edges()} outside expected range"

# 3. Check connectivity
largest_cc = max(nx.weakly_connected_components(G), key=len)
connectivity = len(largest_cc) / G.number_of_nodes()
assert connectivity > 0.80, f"Graph too fragmented: {connectivity:.2%} connectivity"

print("✅ All validation checks passed")
```

---

## A3 Output Schema

### Expected Output Files

1. **`phaseA/A3_conditional_independence/outputs/A3_validated_edges.pkl`**
   - Validated causal edges
   - Edge properties (source, target, lag, test statistics)
   - Metadata (n_edges, reduction ratio, validation status)

2. **`phaseA/A3_conditional_independence/outputs/A3_causal_graph.pkl`**
   - NetworkX DiGraph object
   - Node properties (layer, domain, centrality)
   - Graph-level metadata

3. **`phaseA/A3_conditional_independence/outputs/A3_validation_report.json`**
   - DAG validity
   - Connectivity metrics
   - Edge count statistics
   - Reduction ratios
   - Runtime statistics

### Data Structure

```python
# A3 validated edges
{
    'edges': pd.DataFrame([
        {
            'source': 'indicator_A',
            'target': 'indicator_B',
            'lag': 3,
            'granger_q_value': 1.2e-45,  # From A2
            'ci_p_value': 0.0001,        # From A3 conditional independence
            'test_statistic': 15.2,
            'conditioning_set': ['indicator_C', 'indicator_D']  # Confounders tested
        },
        ...
    ]),
    'metadata': {
        'timestamp': '2025-11-18 14:30:00',
        'n_edges': 45_234,
        'n_input_edges': 1_157_230,
        'reduction_ratio': 0.961,
        'alpha': 0.001,
        'method': 'PC-Stable',
        'dag_valid': True,
        'connectivity': 0.87
    }
}
```

---

## Common Pitfalls to Avoid

### Pitfall 1: Using all 2.3M edges @ q<0.05
**Problem**: Doubles A3 runtime, increases false positives
**Solution**: Use 1.16M edges @ q<0.01 (stricter FDR threshold)

### Pitfall 2: Setting alpha too high in PC-Stable
**Problem**: alpha=0.05 retains too many spurious edges
**Solution**: Use alpha=0.001 (stricter conditional independence)

### Pitfall 3: Not using stable=True
**Problem**: Edge orientation depends on variable ordering → non-reproducible
**Solution**: Always use stable=True in PC algorithm

### Pitfall 4: Ignoring thermal throttling
**Problem**: Using >12 cores causes system crashes
**Solution**: Max 12 cores, monitor CPU temps

### Pitfall 5: No checkpointing
**Problem**: 2-4 day runtime can crash, lose all progress
**Solution**: Checkpoint every 10K edges

---

## Troubleshooting Guide

### Issue: A3 takes >7 days
**Diagnosis**: Too many edges or poor parallelization
**Solution**:
- Check you filtered to q<0.01 (not q<0.05)
- Verify parallelization is working
- Consider early stopping if >100K edges after 2 days

### Issue: Output has cycles
**Diagnosis**: PC-Stable failed, likely alpha too high
**Solution**:
- Verify stable=True was used
- Lower alpha to 0.0001
- Check background knowledge for conflicts

### Issue: <5K edges output
**Diagnosis**: Over-pruning, alpha too strict
**Solution**:
- Increase alpha to 0.005
- Verify input had 1.16M edges (not fewer)
- Check data quality (sufficient overlap)

### Issue: >200K edges output
**Diagnosis**: Under-pruning, alpha too lenient
**Solution**:
- Decrease alpha to 0.0001
- Verify FDR edges are q<0.01 (not q<0.05)
- Check for non-stationarity in data

---

## Post-A3: Next Steps

### Immediate (After A3 Complete)

1. **Validate output**
   - Run all validation checks
   - Generate validation report
   - Visual inspection of graph structure

2. **Prepare for A4**
   - Extract edge list for effect quantification
   - Identify backdoor adjustment sets
   - Plan bootstrap validation strategy

### A4: Effect Quantification

**Input**: 30K-80K validated edges from A3
**Method**: Backdoor adjustment (Pearl's criterion)
**Output**: Effect sizes with confidence intervals
**Runtime**: 4-6 days

### Bootstrap Validation (After A4)

**Input**: 30K-80K edges with effect sizes
**Method**: Resample data 1,000 times, test edge stability
**Output**: Bootstrap-validated final graph (20K-60K edges)
**Runtime**: 12-24 hours

---

## File Checklist for A3

- [x] `outputs/granger_fdr_corrected.pkl` - FDR-corrected edges
- [x] `outputs/significant_edges_fdr.pkl` - Pre-filtered edges
- [x] `outputs/fdr_diagnostic.png` - P-value distribution
- [x] `../A1_missingness_analysis/outputs/A2_preprocessed_data.pkl` - Imputed data
- [x] `A2_COMPLETION_SUMMARY.md` - Complete A2 summary
- [x] `README.md` - A2 documentation
- [x] This file (`A2_READY_FOR_A3.md`) - Handoff documentation

---

## Summary

**A2 Status**: ✅ COMPLETE
**A3 Input**: 1,157,230 edges @ q<0.01
**Expected A3 Output**: 30,000 - 80,000 validated causal edges
**Modified Workflow**: Bootstrap moved to after A3 (more efficient, scientifically sound)

**Ready to launch A3**: Yes, awaiting user approval

---

**Last Updated**: November 14, 2025
**Author**: Claude Code
**Next Phase**: A3 Conditional Independence (PC-Stable)
