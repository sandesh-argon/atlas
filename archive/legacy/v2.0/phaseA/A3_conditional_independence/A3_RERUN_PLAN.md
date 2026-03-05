# A3 Re-Run Plan (November 16, 2025)

## Why Re-Running A3

The first A3 attempt (November 15, 2025) **failed critical validation checks**. Files from that attempt are archived in `archive_failed_attempt/`.

### Validation Failures Summary

| Validation | Result | Issue |
|------------|--------|-------|
| **Validation 2: Pre-Pruning** | ❌ FAILED | Lost 72.3% of moderate-strength edges (F=10-40) |
| **Validation 3: Cycle Removal** | ❌ FAILED | Deleted 84.5% of strong edges (F≥50) including F>100K feedback loops |

**Critical Problems**:
1. Pre-pruning (F>40, p<1e-06) was **too aggressive** → Lost 127K important mechanisms
2. Greedy cycle removal **broke causal logic** → Deleted 18K strong edges
3. Final 75K edges were **incomplete** → Missing developmental pathways

---

## Corrected Approach: Option B+ (Hybrid Strategy)

### Step 1: Relaxed Pre-Pruning
**Old filters** (too strict):
- FDR p-value < 1e-06
- F-statistic > 40
- Result: 114,274 edges (90.1% reduction)

**New filters** (balanced):
- FDR p-value < 1e-04 (still 99.99% confidence)
- F-statistic > 20 (captures moderate mechanisms)
- Expected: ~350,000 edges (70% reduction)

**Rationale**: F=20-40 edges are **real causal mechanisms** in development economics (e.g., education→health, governance→growth). Original filters were calibrated for ultra-strong effects only.

---

### Step 2: PC-Stable (Same Pairwise Approach)
**No changes to methodology** - proven sound:
- Custom pairwise deletion for 80% missing data
- Fisher-Z test with alpha=0.001
- Max conditioning set size: 2
- Min observations: 30 per test

**Expected**:
- Input: ~350K edges
- Output: ~200K validated edges (43% reduction)
- Runtime: 2-3 hours (8 cores, threading backend)

---

### Step 3: Hybrid Cycle Removal (NEW)
**Old approach** (greedy FAS):
```python
while has_cycles(G):
    cycle = find_one_cycle(G)
    weakest = min(cycle, key=lambda e: e['f_statistic'])
    remove_edge(weakest)
```
**Problem**: Removes edges one-by-one regardless of strength → Deleted F>100K feedback loops

**New approach** (hybrid):
```python
# Step 3A: Handle Bidirectional Granger Pairs (Feedback Loops)
feedback_loops = find_bidirectional_pairs(granger_edges)
for (X, Y) in feedback_loops:
    if f_statistic(X→Y) > f_statistic(Y→X):
        keep(X→Y); remove(Y→X)  # Keep stronger direction
    else:
        keep(Y→X); remove(X→Y)

# Step 3B: Weighted FAS on Remaining Cycles
# Minimize sum of F-statistics removed (not count)
weighted_fas(G, weight='f_statistic', objective='minimize_sum')
```

**Benefits**:
1. **Preserves feedback loops** by keeping stronger causal direction
2. **Minimizes signal loss** (weighted FAS prefers removing weak edges)
3. **Faster runtime** (feedback loops handled first, ~20K edges resolved)
4. **Mechanistically sound** (development economics HAS feedback: GDP↔health)

**Expected**:
- Input: ~200K edges
- Output: ~150K edges (after removing weaker cycle directions)
- Runtime: 30-45 minutes

---

## Expected Final Output

### Comparison: Old vs New

| Metric | Old (Failed) | New (Expected) | Change |
|--------|--------------|----------------|--------|
| Pre-pruned edges | 114K | 350K | +3.1× |
| PC-Stable validated | 96K | 200K | +2.1× |
| Final DAG edges | 75K | 150K | +2.0× |
| Graph density | 0.37% | 0.74% | +2.0× |
| Moderate edges (F=20-40) | Missing | Included | ✅ |
| Feedback loops | Broken | Preserved | ✅ |

### Quality Improvements
- ✅ **Captures moderate mechanisms** (F=20-40) that were lost
- ✅ **Preserves feedback loops** (GDP↔health, education↔productivity)
- ✅ **2× more comprehensive** network (150K vs 75K edges)
- ✅ **Still very sparse** (0.74% density, interpretable)
- ✅ **Methodologically rigorous** (PC-Stable + weighted FAS)

---

## Timeline

| Step | Task | Expected Runtime |
|------|------|------------------|
| 1 | Relaxed pre-pruning | 10 minutes |
| 2 | PC-Stable (pairwise) | 2-3 hours |
| 3 | Hybrid cycle removal | 30-45 minutes |
| 4 | Validation (3 checks) | 30 minutes |
| **Total** | **Complete A3 re-run** | **3-4 hours** |

---

## Implementation Plan

### Script Updates

**1. step1c_smart_prepruning.py** (MODIFIED)
```python
# Change thresholds
fdr_cutoff = 1e-04  # Was: 1e-06
f_stat_min = 20     # Was: 40
```

**2. step2_custom_pairwise_pc.py** (NO CHANGE)
- Same pairwise Fisher-Z approach
- Proven sound methodology

**3. step3_hybrid_cycle_removal.py** (NEW)
- Implement feedback loop handling
- Implement weighted FAS
- Use networkx + custom logic

---

## Validation Criteria (Must Pass)

### Validation 1: Pairwise Deletion Consistency
- Consistency ≥90%: PASS
- Mean overlap ≥60%: PASS

### Validation 2: Pre-Pruning Loss
- Lost edges with F=10-40: <30%: PASS
- Max domain loss: <50%: PASS
- High-value lost edges: <50: PASS

### Validation 3: Cycle Removal
- Median F-stat of removed edges: <40: PASS
- Strong edges (F≥50) removed: <10%: PASS
- Stronger direction kept: ≥90%: PASS
- Max domain removal: <30%: PASS

**If any validation fails**: Adjust thresholds and re-run that specific step

---

## File Naming Convention

**Old outputs** (archived):
- `archive_failed_attempt/A3_final_dag.pkl` (75K edges, DO NOT USE)

**New outputs** (use these):
- `outputs/smart_prepruned_edges_v2.pkl` (350K edges)
- `outputs/A3_validated_fisher_z_v2.pkl` (200K edges)
- `outputs/A3_final_dag_v2.pkl` (150K edges) ← PRIMARY OUTPUT FOR A4

---

## Success Criteria

✅ **A3 is complete when**:
1. All 3 validation checks pass
2. Final DAG has 120K-180K edges (target: 150K)
3. Graph density 0.6-0.9% (sparse but comprehensive)
4. Moderate mechanisms (F=20-40) included
5. Feedback loops preserved (stronger direction kept)
6. Ready for A4 effect quantification

---

## Next Steps (After A3 Re-Run)

**A4: Effect Quantification**
- Input: `outputs/A3_final_dag_v2.pkl` (150K edges)
- Tasks: Beta coefficients, confidence intervals, bootstrap
- Runtime: 4-6 days

---

**Status**: Ready to begin re-run
**Date**: November 16, 2025
**Approval**: Pending user confirmation
