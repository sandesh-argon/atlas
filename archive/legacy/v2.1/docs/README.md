# V2.1 Documentation

Comprehensive documentation for the V2.1 Research-Grade Causal Discovery Pipeline, implementing domain-balanced stratified sampling followed by statistical network discovery (Phases A0-A3).

## Documentation Overview

This documentation set covers the complete V2.1 pipeline from data sampling through validated causal graph generation. Total: **3,769 lines** of detailed technical documentation.

### Quick Navigation

| Document | Purpose | Lines | Key Topics |
|----------|---------|-------|------------|
| [architecture_overview.md](architecture_overview.md) | System design & data flow | 650 | Architecture diagrams, component interactions, performance analysis |
| [A0_data_acquisition.md](A0_data_acquisition.md) | Stratified sampling | 533 | Outcome-aware sampling, domain balancing, composite scoring |
| [A1_missingness_analysis.md](A1_missingness_analysis.md) | Data preprocessing (V2 reference) | 301 | Imputation strategies, tier system, V1 lessons |
| [A2_granger_causality.md](A2_granger_causality.md) | Temporal precedence testing | 1,237 | Prefiltering, VAR testing, FDR correction |
| [A3_conditional_independence.md](A3_conditional_independence.md) | Spurious correlation removal | 1,048 | PC-Stable algorithm, Fisher-Z test, cycle removal |

## Pipeline Summary

```
V2 Data (6,368 indicators)
    ↓
[A0] Stratified Sampling (5 min)
    → 3,122 balanced indicators
    ↓
[A2] Granger Causality Testing (2.4 hours)
    → 111,234 temporal precedence edges
    ↓
[A3] Conditional Independence (52 min)
    → 70,841 validated causal edges (DAG)
```

**Total Runtime**: ~3.4 hours (vs 8.7+ hours in V2, which failed to complete)

## Documentation Structure

### 1. Start Here: Architecture Overview

**File**: [architecture_overview.md](architecture_overview.md)

**Contents**:
- System architecture diagrams (Mermaid)
- Complete data flow visualization
- Component interaction sequences
- File system layout
- Performance characteristics
- V2 vs V2.1 comparison

**Best for**: Understanding the big picture, system design, how components fit together

**Key Diagrams**:
- Phase A0-A3 pipeline flow
- Data flow by phase (A0, A2, A3)
- Component interaction sequence
- Multi-level validation framework

### 2. Phase Documentation (A0-A3)

Each phase has comprehensive documentation covering:
- Theoretical background
- Algorithm details
- Implementation specifics
- Input/output formats
- Execution instructions
- Expected output examples
- Troubleshooting guides

#### A0: Data Acquisition and Stratified Sampling

**File**: [A0_data_acquisition.md](A0_data_acquisition.md)

**Key Sections**:
- Rationale for domain balancing
- Composite score calculation (50% SHAP, 25% outcome betweenness, 15% quality, 10% diversity)
- Coverage-based sampling algorithm
- Validation checks (top 100 retention, critical indicators)
- Output files and formats

**Best for**: Understanding how V2.1 creates a balanced subset from V2's 6,368 indicators

**Key Algorithms**:
- `compute_outcome_betweenness()`: Path-based importance to QoL outcomes
- `coverage_based_sampling()`: Ensures semantic cluster diversity within domains

#### A1: Missingness Analysis (Reference)

**File**: [A1_missingness_analysis.md](A1_missingness_analysis.md)

**Important Note**: V2.1 does NOT re-run A1. This document explains V2's preprocessing that V2.1 inherits.

**Key Sections**:
- V2 imputation strategies (MICE, KNN, temporal)
- Tier system for imputation quality (0=observed, 1=temporal, 2-3=MICE, 4=KNN)
- V1 lessons learned (per-country coverage, imputation weighting)
- Data structure reference

**Best for**: Understanding the data quality and imputation metadata in V2.1's input

#### A2: Granger Causality Testing

**File**: [A2_granger_causality.md](A2_granger_causality.md) (Largest: 1,237 lines)

**Comprehensive Coverage**:
- **Step 1**: Data validation (variance, tiers, metadata)
- **Step 2**: Prefiltering (9.7M → 293K pairs via correlation)
- **Step 3**: Parallel Granger testing (memory-safe incremental saves)
- **Step 4**: FDR correction (Benjamini-Hochberg)

**Key Sections**:
- Theoretical background: Granger causality, VAR models, F-tests
- Multiple testing problem and FDR correction
- Memory-safe design for large-scale testing
- Progress monitoring with external monitor.sh script
- Parallelization strategy (10 cores for thermal safety)

**Best for**: Understanding how V2.1 identifies temporal precedence relationships

**Critical Algorithms**:
- `prepare_time_series()`: Aligns X and Y by country with maximum overlap
- `run_granger_test()`: VAR-based F-test with 5 lags
- `apply_fdr_correction()`: Benjamini-Hochberg procedure

#### A3: Conditional Independence Testing

**File**: [A3_conditional_independence.md](A3_conditional_independence.md) (1,048 lines)

**Comprehensive Coverage**:
- **Step 1**: Smart prepruning (q<0.001, F>10)
- **Step 2**: PC-Stable algorithm (test independence given confounders)
- **Step 3**: Cycle removal (greedy weakest-edge removal)

**Key Sections**:
- Theoretical background: Conditional independence, PC-Stable, Fisher-Z test
- Confounder identification (common causes of X and Y)
- Partial correlation computation (single and multiple confounders)
- Memory-safe cycle removal (DFS-based, not exponential enumeration)

**Best for**: Understanding how V2.1 removes spurious correlations

**Critical Algorithms**:
- `get_top_confounders()`: Identifies Z that causes both X and Y
- `test_single_edge()`: Tests X ⊥ Y | Z via Fisher-Z test
- `remove_cycles()`: Greedy removal of weakest edges in cycles

### 3. Reference Materials

#### Data Structures

All documents include detailed data structure specifications:

**Indicator Data** (from A0/A1):
```python
{
    'imputed_data': {indicator: DataFrame[country × year]},
    'tier_data': {indicator: DataFrame[country × year]},
    'metadata': {indicator: dict},
    'v21_sampling_info': {...}
}
```

**Edge Lists** (from A2/A3):
```python
pd.DataFrame({
    'source': [...],
    'target': [...],
    'f_statistic': [...],
    'p_value': [...],
    'best_lag': [...]
})
```

**Graphs** (from A3):
```python
nx.DiGraph with edge attributes:
{'f_statistic': float, 'p_value': float, 'best_lag': int}
```

#### File Locations

Complete file system layout in [architecture_overview.md](architecture_overview.md):

**Key Input Files**:
- V2 data: `<repo-root>/v2.0/phaseA/A1_missingness_analysis/outputs/A2_preprocessed_data.pkl`
- V2 SHAP: `<repo-root>/v2.0/phaseB/B35_semantic_hierarchy/outputs/B35_shap_scores.pkl`

**V2.1 Output Files**:
- Sampled data: `v2.1/outputs/A2_preprocessed_data_V21.pkl`
- Granger edges: `v2.1/outputs/A2/significant_edges_fdr.pkl`
- Final DAG: `v2.1/outputs/A3/A3_final_dag.pkl`
- CSV export: `v2.1/outputs/A3/A3_final_edge_list.csv`
- GraphML: `v2.1/outputs/A3/A3_final_dag.graphml`

## Quick Start Guide

### For New Users

1. **Start with**: [architecture_overview.md](architecture_overview.md)
   - Read "System Summary" and "System Architecture Diagram"
   - Understand the three phases: A0 (sampling), A2 (Granger), A3 (PC-Stable)

2. **Deep dive by phase**:
   - [A0_data_acquisition.md](A0_data_acquisition.md): How sampling works
   - [A2_granger_causality.md](A2_granger_causality.md): How Granger testing works
   - [A3_conditional_independence.md](A3_conditional_independence.md): How spurious edges are removed

3. **For implementation**:
   - Each phase doc has "Execution" section with exact commands
   - Each phase doc has "Expected Output" section showing what you should see
   - Each phase doc has "Troubleshooting" section for common issues

### For Developers

1. **Understand algorithms**: Read "Theoretical Background" sections in each phase doc

2. **Implement modifications**:
   - Algorithm details in "Key Algorithm" subsections
   - Parameters and tuning in "Configuration" sections
   - Performance implications in [architecture_overview.md](architecture_overview.md)

3. **Debug issues**:
   - Check "Troubleshooting" sections in each phase doc
   - Review "Success Criteria" to validate outputs
   - Examine checkpoint files (locations in each phase doc)

### For Researchers

1. **Methodology validation**:
   - "Theoretical Background" sections cite original papers
   - "Algorithm" sections provide mathematical formulations
   - "Validation Framework" in [architecture_overview.md](architecture_overview.md)

2. **Reproduce results**:
   - "Execution" sections have exact commands
   - "Expected Output" sections show validation metrics
   - "Output Files" sections document data formats

3. **Extend pipeline**:
   - "Future Extensions" in [architecture_overview.md](architecture_overview.md)
   - Phase A4-A6 not yet implemented (documented for reference)

## Common Use Cases

### Use Case 1: Run the Full Pipeline

```bash
# Step 0: Stratified sampling
cd <repo-root>/v2.0/v2.1
python scripts/step0_stratified_sampling.py

# Step 1-4: Granger causality (A2)
cd scripts/A2
python step1_validate_checkpoint.py
python step2_prefiltering.py
python step3_granger_testing_v2.py
python step4_fdr_correction.py

# Step 1-3: Conditional independence (A3)
cd ../A3
python step1c_smart_prepruning.py
python step2_custom_pairwise_pc.py
python step3_remove_cycles.py
```

**Documentation**: Follow execution sections in each phase doc for detailed instructions.

### Use Case 2: Monitor Long-Running Tasks

```bash
# Monitor A2 Granger testing
cd <repo-root>/v2.0/v2.1/scripts/A2
watch -n 10 ./monitor.sh

# Monitor A3 PC-Stable
cd ../A3
watch -n 10 ./monitor.sh
```

**Documentation**: See A2 and A3 docs for progress monitoring details.

### Use Case 3: Analyze Output Graph

```python
import pickle
import networkx as nx

# Load final DAG
with open('v2.1/outputs/A3/A3_final_dag.pkl', 'rb') as f:
    data = pickle.load(f)

G = data['graph']

# Analyze
print(f"Nodes: {G.number_of_nodes()}")
print(f"Edges: {G.number_of_edges()}")
print(f"Is DAG: {nx.is_directed_acyclic_graph(G)}")

# Find most important nodes
betweenness = nx.betweenness_centrality(G)
top_10 = sorted(betweenness.items(), key=lambda x: x[1], reverse=True)[:10]
```

**Documentation**: See [architecture_overview.md](architecture_overview.md) "Data Structures" section.

### Use Case 4: Troubleshoot Failed Run

1. Check which step failed:
   ```bash
   ls -lht v2.1/outputs/A*/  # Check most recent outputs
   ```

2. Read relevant troubleshooting section:
   - A0 issues: [A0_data_acquisition.md](A0_data_acquisition.md) "Troubleshooting"
   - A2 issues: [A2_granger_causality.md](A2_granger_causality.md) "Troubleshooting"
   - A3 issues: [A3_conditional_independence.md](A3_conditional_independence.md) "Troubleshooting"

3. Check logs:
   ```bash
   tail -100 v2.1/logs/pairwise_pc.log  # A3 PC-Stable log
   tail -100 v2.1/logs/remove_cycles.log  # A3 cycle removal log
   ```

4. Examine checkpoints:
   ```bash
   ls -lht v2.1/outputs/A2/checkpoints/
   ls -lht v2.1/outputs/A3/checkpoints/
   ```

### Use Case 5: Customize Parameters

Each phase doc has a "Configuration" section with tunable parameters:

**A0 Sampling Targets**:
```python
# In step0_stratified_sampling.py
SAMPLING_TARGETS = {
    'Governance': 1000,  # Adjust these
    'Education': 1000,
    'Economic': 1000,
    'Health': 122
}
```

**A2 Prefiltering Thresholds**:
```python
# In step2_prefiltering.py
CORRELATION_MIN = 0.10  # Adjust for more/fewer pairs
CORRELATION_MAX = 0.95
```

**A3 PC-Stable Parameters**:
```python
# In step2_custom_pairwise_pc.py
max_cond_size = 2  # 1 or 2 confounders
max_confounders = 10  # Top N confounders to test
alpha = 0.001  # Fisher-Z significance threshold
```

## Validation and Testing

### How to Verify Pipeline Success

Each phase has "Success Criteria" documented:

**A0 Success** (from [A0_data_acquisition.md](A0_data_acquisition.md)):
- Total indicators: 3,000-3,500 (Target: 3,122)
- Top 100 retention: ≥80%
- Critical dropped: <20

**A2 Success** (from [A2_granger_causality.md](A2_granger_causality.md)):
- Prefiltered pairs: 200K-500K (Target: 293K)
- FDR edges (q<0.05): 50K-150K (Target: 111K)
- Runtime: <5 hours (Target: 2.4 hours)

**A3 Success** (from [A3_conditional_independence.md](A3_conditional_independence.md)):
- Validated edges: 30K-80K (Target: 72K)
- DAG validity: True
- Connectivity: >80% (Target: 98.5%)
- Runtime: <2 hours (Target: 52 min)

### Multi-Level Validation Framework

See "Validation Framework" section in [architecture_overview.md](architecture_overview.md) for complete validation hierarchy:

1. **Data Quality Validation**: Variance, tiers, metadata
2. **Statistical Validation**: Granger F-test, FDR, Fisher-Z
3. **Graph Validation**: DAG property, connectivity, edge count
4. **Domain Validation**: Retention rates, balance

## Performance and Scalability

### Current Performance (V2.1)

From [architecture_overview.md](architecture_overview.md):

| Phase | Runtime | Parallelization |
|-------|---------|-----------------|
| A0 | 5 min | Sequential |
| A2.1 | 5 min | Sequential |
| A2.2 | 1.7 hours | 12 cores |
| A2.3 | 0.6 hours | 10 cores |
| A2.4 | 10 min | Sequential |
| A3.1 | 2 min | Sequential |
| A3.2 | 45 min | Sequential (was parallel, deadlock issue) |
| A3.3 | 5 min | Sequential |
| **Total** | **3.4 hours** | - |

### Scaling Behavior

| Scale | Indicators | A2 Runtime | A3 Runtime | Total |
|-------|------------|------------|------------|-------|
| V2.1 (baseline) | 3,122 | 2.4 hours | 52 min | 3.4 hours |
| 2× scale | 6,244 | 9.6 hours | 3.5 hours | 13.1 hours |
| 10× scale | 31,220 | 240 hours | 87 hours | 327 hours |

**Bottleneck**: A2 Granger causality (quadratic in indicator count)

## Known Issues and Limitations

### Thermal Constraints

**Issue**: CPU throttles at >90°C with 15+ cores

**Solution**: Limited to 10-12 cores (documented in A2 and architecture overview)

**Impact**: Parallel efficiency 85-87% (vs theoretical 100%)

### Memory Constraints

**Issue**: Original Granger implementation caused OOM errors

**Solution**: Memory-safe incremental saves (documented in A2)

**Impact**: Slightly slower due to disk I/O, but reliable

### PC-Stable Parallelization

**Issue**: Parallel processing caused deadlocks with large DataFrame

**Solution**: Sequential processing with progress tracking

**Impact**: Runtime still acceptable (45 min for 114K edges = 42 edges/sec)

## Future Work

From [architecture_overview.md](architecture_overview.md) "Future Extensions":

### Phases A4-A6 (Not Yet Implemented)

**A4: Effect Quantification**
- Backdoor adjustment + LASSO regression
- Bootstrap confidence intervals
- Estimated runtime: 4-6 hours

**A5: Interaction Discovery**
- Moderator effects
- Constrained search space
- Estimated runtime: 30-60 minutes

**A6: Hierarchical Layering**
- Topological sort
- Layer assignment (1=inputs, 5=outcomes)
- Estimated runtime: 30 minutes

### Phase B (Semantic Layer)

**B1-B3.5**: Outcome discovery, clustering, hierarchy
- Factor analysis
- Semantic embeddings
- Multi-level pruning

## Contributing

### How to Extend Documentation

When adding new phases or features:

1. **Follow existing structure**: See any phase doc as template
2. **Include these sections**:
   - Overview (purpose, I/O, runtime, method)
   - Theoretical background
   - Implementation details
   - Execution instructions
   - Expected output
   - Troubleshooting
   - References

3. **Update architecture_overview.md**: Add to data flow diagrams and component descriptions

4. **Add to this README**: Update quick navigation table and use cases

### Documentation Standards

- **Code examples**: Use syntax highlighting (```python, ```bash)
- **File paths**: Use absolute paths, not relative
- **Commands**: Show exact commands users should run
- **Output**: Show realistic expected output, not idealized
- **References**: Cite papers, link to related docs

## References

### External Papers

See "References" sections in each phase doc for citations:

- Granger (1969): Granger causality
- Benjamini & Hochberg (1995): FDR correction
- Spirtes & Glymour (1991): PC algorithm
- Colombo & Maathuis (2014): PC-Stable
- Pearl (2009): Causal inference theory

### Internal Documentation

- V2 master instructions: `<repo-root>/v2.0/v2_master_instructions.md`
- CLAUDE.md: `<repo-root>/v2.0/CLAUDE.md`
- V1 lessons: `<repo-root>/v2.0/V1_LESSONS.md`

### Code Locations

- Scripts: `<repo-root>/v2.0/v2.1/scripts/`
- Outputs: `<repo-root>/v2.0/v2.1/outputs/`
- Logs: `<repo-root>/v2.0/v2.1/logs/`

## Summary Statistics

**Documentation Coverage**:
- Total lines: 3,769
- Total pages (approximate): ~95 pages (40 lines/page)
- Files: 5 markdown documents + this README

**Code Coverage**:
- All A0-A3 scripts documented
- All input/output formats specified
- All key algorithms explained
- All execution commands provided

**Completeness**:
- Theoretical foundations: ✅
- Implementation details: ✅
- Execution instructions: ✅
- Troubleshooting guides: ✅
- Performance analysis: ✅
- Validation framework: ✅

## Changelog

**2025-12-04**: Initial comprehensive documentation release
- Created 5 core documentation files (3,769 lines)
- Documented phases A0-A3 completely
- Added architecture overview with Mermaid diagrams
- Included troubleshooting guides for all phases
- Added performance analysis and scaling behavior
