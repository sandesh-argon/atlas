# A2: Granger Causality Testing

## Status: ✅ COMPLETE (November 14, 2025)

Establishes temporal precedence between indicators using Granger causality tests with FDR correction.

---

## Quick Summary

| Metric | Value |
|--------|-------|
| **Input** | 6,368 preprocessed indicators (A1 output) |
| **Tests Run** | 9,256,206 Granger causality tests |
| **Output** | 1,157,230 validated edges (q<0.01) |
| **Runtime** | ~7 hours (10 cores) |
| **Memory** | 12-15 GB peak |

---

## File Structure

```
A2_granger_causality/
├── scripts/              # All analysis scripts
│   ├── step1_validate_checkpoint.py
│   ├── step2_prefiltering.py
│   ├── step3_granger_testing_v2.py  # Memory-safe version
│   ├── step4_fdr_correction.py
│   ├── diagnose_fdr_pvalues.py
│   ├── monitor_v2.sh
│   └── progress.py
├── outputs/              # Results
│   ├── granger_fdr_corrected.pkl    # 1.3 GB - For A3 input
│   ├── significant_edges_fdr.pkl    # 343 MB
│   └── fdr_diagnostic.png           # P-value distribution
├── checkpoints/          # Incremental saves
│   ├── granger_progress_v2.pkl
│   └── incremental_results/
│       └── chunk_*.pkl              # 159 files
├── logs/                 # Execution logs
│   ├── step3_granger_v2.log
│   └── fdr_diagnostic.log
├── README.md             # This file
├── A2_FINAL_STATUS.md    # Complete summary
└── A2_READY_FOR_A3.md    # A3 handoff details
```

---

## Pipeline Steps

1. **Checkpoint Validation** → 6,368 indicators validated
2. **Prefiltering** → 40.6M pairs → 15.9M pairs (correlation filter)
3. **Granger Testing** → 9.26M successful tests
4. **FDR Correction** → 1.16M edges @ q<0.01
5. **Diagnostic Analysis** → Healthy distribution, proceed to A3

---

## Key Outputs

### For A3 (Next Phase)
- **File**: `outputs/granger_fdr_corrected.pkl`
- **Edges**: 1,157,230 (filter to `significant_fdr_001 == True`)
- **Data**: `../A1_missingness_analysis/outputs/A2_preprocessed_data.pkl`

### Decisions Made
- ✅ Use q<0.01 threshold (stricter FDR)
- ✅ Skip bootstrap at this stage (moved to after A3)
- ✅ 10 cores for thermal safety

---

## Documentation

- **A2_FINAL_STATUS.md** - Complete results, metrics, lessons learned
- **A2_READY_FOR_A3.md** - A3 configuration, handoff details, troubleshooting

---

## Quick Start (A3 Handoff)

```python
import pickle

# Load FDR-corrected edges
with open('outputs/granger_fdr_corrected.pkl', 'rb') as f:
    fdr_data = pickle.load(f)

# Filter to q<0.01 for A3
edges_q01 = fdr_data['results'][fdr_data['results']['significant_fdr_001']]
print(f"A3 input: {len(edges_q01):,} edges")  # 1,157,230

# Load imputed data
with open('../A1_missingness_analysis/outputs/A2_preprocessed_data.pkl', 'rb') as f:
    a1_data = pickle.load(f)
```

---

**Completion Date**: November 14, 2025
**Next Phase**: A3 Conditional Independence (PC-Stable)
**Estimated A3 Runtime**: 2-4 days
