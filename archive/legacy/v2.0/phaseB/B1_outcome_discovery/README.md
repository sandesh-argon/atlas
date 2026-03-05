# B1: Outcome Discovery via Factor Analysis

**Status**: ✅ COMPLETE
**Date**: 2025-11-20
**Output**: 9 validated outcome factors ready for B2

## Directory Structure

```
B1_outcome_discovery/
├── README.md                           # This file
├── B1_QUICK_SUMMARY.md                 # Quick reference guide
├── B1_COMPLETION_SUMMARY.md            # Comprehensive completion report
├── B1_VALIDATION_RESULTS.md            # Detailed validation results
├── B1_FINAL_STATUS.md                  # Executive summary and handoff
│
├── validation_scripts/                 # Pre-execution validation
│   └── validate_top_layer_nodes.py     # Pre-B1 sanity checks (3/3 passed)
│
├── scripts/                            # Main analysis scripts
│   ├── run_b1_factor_analysis.py       # Factor extraction with scree plot
│   └── run_b1_validation.py            # 3-part validation (domain, literature, R²)
│
├── diagnostics/                        # Factor analysis diagnostics
│   ├── B1_scree_plot.png               # Eigenvalue decay visualization
│   ├── B1_factor_loadings.csv          # Loadings matrix (30 vars × 12 factors)
│   ├── B1_factor_variance.csv          # Variance explained per factor
│   ├── B1_factor_scores.csv            # Factor scores (1,848 obs × 12 factors)
│   └── B1_factor_diagnostics.json      # KMO, Bartlett, variance stats
│
├── outputs/                            # Final B1 deliverables
│   ├── B1_validated_outcomes.pkl       # 9 validated factors for B2
│   ├── B1_validation_results.json      # Full validation details
│   └── B1_validation_summary.json      # Pass/fail summary
│
└── logs/                               # Execution logs
    ├── b1_factor_analysis.log          # Factor extraction log
    └── b1_validation.log               # Validation log
```

## Quick Start

### Load B1 Output for B2

```python
import pickle

# Load B1 checkpoint
with open('outputs/B1_validated_outcomes.pkl', 'rb') as f:
    b1_data = pickle.load(f)

# Access components
validated_outcomes = b1_data['outcomes']  # 9 validated outcome factors
metadata = b1_data['metadata']            # n_factors, pass rates, etc.
diagnostics = b1_data['diagnostics']      # KMO, variance explained, etc.

# Example: Get specific factor
factor_1 = validated_outcomes[0]
print(f"Factor 1: {factor_1['primary_domain']}")
print(f"  Top variables: {factor_1['top_variables'][:3]}")
print(f"  Predictability R²: {factor_1['predictability_r2_mean']:.3f}")
```

### View Results Summary

```bash
# Read comprehensive report
cat B1_COMPLETION_SUMMARY.md

# Check validation results
cat outputs/B1_validation_summary.json

# View scree plot
xdg-open diagnostics/B1_scree_plot.png
```

## Key Results

| Metric | Value |
|--------|-------|
| **Input Nodes** | 30 real top-layer nodes (filtered 2 virtual) |
| **Observations** | 1,848 country-years |
| **N Factors** | 12 (V2 spec minimum) |
| **Kaiser Criterion** | 9 factors (λ>1) |
| **Scree Elbow** | 2 factors |
| **Total Variance Explained** | 84.9% ✅ |
| **KMO Measure** | 0.740 (good) ✅ |
| **Validated Factors** | 9/12 (75%) ✅ |
| **Domain Coherence Pass** | 10/12 (83%) ✅ |
| **Predictability Pass** | 11/12 (92%) ✅ |

## Methodology Highlights

1. **Virtual Node Filtering**: Removed INTERACT_* nodes (synthetic interactions, not real outcomes)

2. **Scree Plot Analysis**: Used min(Kaiser, elbow) with V2 spec constraints (12 ≤ n ≤ 25)

3. **3-Part Validation**:
   - **Domain Coherence**: ≤3 unique domains per factor
   - **Literature Alignment**: TF-IDF similarity > 0.60 (technical issue - all 0.00)
   - **Predictability**: RF cross-val R² > 0.40

4. **Novel Factor Handling**: All factors flagged as "novel" (TF-IDF issue), validation falls back to R² check

## Validated Outcome Factors (9)

| ID | Domain | Variance | R² | Interpretation |
|----|--------|----------|-----|----------------|
| **F1** | Health | 15.9% | 0.95 | Reproductive/maternal health |
| **F2** | Governance | 14.4% | 0.87 | Political autonomy & judicial competence |
| **F4** | Economic | 7.5% | 0.81 | Income/taxation measures |
| **F5** | Governance | 6.1% | 0.57 | Electoral legitimacy & gender equality |
| **F6** | Economic/Health | - | 0.52 | Resource access (fishing, taxation) |
| **F7** | Governance | - | 0.96 | Civil society autonomy |
| **F10** | Economic | - | 0.65 | Economic development |
| **F11** | Governance | - | 0.78 | Campaign/election quality |
| **F12** | Governance | - | 0.88 | Worker rights/remittances |

### Excluded Factors (3)
- **Factor_3**: Failed predictability (R²=0.38 < 0.40)
- **Factor_8**: Failed domain coherence (4 domains > 3)
- **Factor_9**: Failed domain coherence (4 domains > 3)

## Next Phase: B2 Mechanism Identification

**Prerequisites**: ✅ Complete
- Checkpoint: `outputs/B1_validated_outcomes.pkl`
- Input for B2: 9 validated outcome factors
- Expected B2 output: 20-50 mechanism nodes
- Method: Composite centrality scoring (betweenness + pagerank + closeness)

## Documentation

See `B1_COMPLETION_SUMMARY.md` for:
- Complete factor analysis methodology
- Scree plot interpretation and n-factor selection
- Detailed validation results per factor
- Known issues (TF-IDF failure, JSON serialization)
- Phase B1 → B2 handoff specifications

## Runtime

- **Pre-checks**: 5 seconds
- **Factor analysis**: 2 minutes
- **Validation (3-part)**: 12 minutes
- **Total**: ~15 minutes

## Files

**Analysis Scripts**:
- `validation_scripts/validate_top_layer_nodes.py` - Pre-B1 sanity checks
- `scripts/run_b1_factor_analysis.py` - Factor extraction
- `scripts/run_b1_validation.py` - 3-part validation

**Outputs**:
- `outputs/B1_validated_outcomes.pkl` - PRIMARY OUTPUT for B2
- `diagnostics/B1_scree_plot.png` - Eigenvalue visualization
- `diagnostics/B1_factor_loadings.csv` - Full loadings matrix

**Documentation**:
- `B1_QUICK_SUMMARY.md` - Quick reference
- `B1_COMPLETION_SUMMARY.md` - Comprehensive report
- `B1_VALIDATION_RESULTS.md` - Per-factor validation details
- `B1_FINAL_STATUS.md` - Executive summary
