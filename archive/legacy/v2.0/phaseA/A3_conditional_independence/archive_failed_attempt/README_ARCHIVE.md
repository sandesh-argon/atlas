# Archive: Failed A3 Attempt (November 15, 2025)

## Why These Outputs Were Archived

These files represent the **first A3 attempt** that failed critical validation checks. They are archived here to prevent confusion with the corrected re-run.

### Validation Failures

**Validation 2: Pre-Pruning Loss - ❌ FAILED**
- Lost edges with F=10-40: 72.3% (threshold: <30%)
- Max domain loss: 94.6% (threshold: <50%)
- High-value lost edges: 127,454 (threshold: <50)
- **Issue**: Pre-pruning filters (F>40, p<1e-06) were far too aggressive

**Validation 3: Cycle Removal - ❌ FAILED**
- Median F-stat of removed edges: 80.0 (threshold: <40)
- Strong edges (F≥50) removed: 84.5% (threshold: <10%)
- **Issue**: Greedy cycle removal deleted 18K strong edges including feedback loops with F>100K

### Archived Files

| File | Description | Size |
|------|-------------|------|
| A3_final_dag.pkl | Final DAG (75K edges) - TOO FEW | 7.4 MB |
| A3_final_edge_list.csv | Edge list CSV | 5.3 MB |
| A3_final_dag.graphml | GraphML for viz | 15 MB |
| A3_validated_fisher_z_alpha_0.001.pkl | PC-Stable output (96K edges) | 14 MB |
| A3_validated_edges.pkl | Early PC-Stable attempt | 16 MB |
| A3_edge_list.csv | Early edge list | 6.7 MB |
| A3_summary_stats.pkl | Summary statistics | 197 B |

### Corrected Approach (Re-Run)

**Changes Made**:
1. **Relaxed pre-pruning**: F>20 (was 40), p<1e-04 (was 1e-06)
2. **Hybrid cycle removal**: Handle feedback loops first, then weighted FAS
3. **Expected output**: ~150K edges (2× more comprehensive)

**Date of re-run**: November 16, 2025

### Do Not Use These Files

These outputs should **NOT** be used for A4 or any downstream analysis. They represent an incomplete causal network that missed important moderate-strength mechanisms and deleted critical feedback loops.

For the correct A3 outputs, see: `../outputs/A3_final_dag_v2.pkl` (created after re-run)

---

**Archived by**: Claude Code
**Date**: November 16, 2025
**Reason**: Failed validation checks (pre-pruning too strict, cycle removal too aggressive)
