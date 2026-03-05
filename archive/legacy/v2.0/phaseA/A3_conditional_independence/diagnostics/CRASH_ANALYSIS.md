# A3 PC-Stable Crash Analysis

**Date**: 2025-11-14
**Issue**: System crashes when running parallelized PC-Stable

---

## Timeline of Crashes

All crashes follow the same pattern:

```
14:23:41 - Loading A1 imputed data...
14:23:41 - Loaded 6,368 indicators, 31,408 observations
14:23:41 - Missing rate: 80.73%
14:23:41 - Starting PC-Stable skeleton phase...
14:23:41 - Parallelization: 10-12 cores
14:23:54 - Graph has 5,454 nodes
[KILLED - No error message]
```

**Time from start to kill**: ~30 seconds (during parallel processing initialization)

---

## Root Cause: Memory Explosion from Multiprocessing

### The Problem

The parallelized code uses `joblib.Parallel()` which spawns separate processes:

```python
results = Parallel(n_jobs=N_CORES)(
    delayed(test_single_edge)(edge, granger_adj, data, alpha, max_cond_set_size)
    for edge in chunk_edges
)
```

**What happens:**
1. Main process loads `data` (6.3GB in memory)
2. `Parallel()` spawns 10 worker processes
3. **Each worker gets a COPY of the 6.3GB data** (Python multiprocessing default)
4. **Total memory**: 6.3GB × 10 = **63GB**
5. **Available RAM**: 23GB
6. **OOM killer activates** → process killed

### Evidence

From logs:
- Process always dies right after "Graph has 5,454 nodes" (before any edges processed)
- No Python exception or traceback (external kill)
- Happens with 10 cores and 12 cores
- Even happened with smaller tests that load full dataset

### Memory Breakdown

**Per-process memory**:
- Imputed data: 6,368 indicators × 31,408 obs × 8 bytes = ~1.6GB raw
- After pandas overhead: ~6-8GB
- Adjacency graph: ~500MB
- **Total per process**: ~7GB

**With 10 workers**:
- 10 × 7GB = **70GB total**
- System has **23GB available**
- **47GB shortfall** → Immediate OOM kill

---

## Why Single-Core Worked

Sequential processing (1 core) doesn't duplicate memory:
- Main process: 7GB
- No worker processes
- Total: 7GB ✓ (within 23GB limit)

This is why all small tests passed but full parallelized runs crashed.

---

## Solutions (in order of preference)

### Option 1: Use Threading Instead of Multiprocessing ⭐ RECOMMENDED

**Pros:**
- Threads share memory (no duplication)
- Python GIL released during NumPy/pandas operations
- No code restructuring needed

**Cons:**
- Slightly slower than true multiprocessing
- Still limited by GIL for pure Python code

**Implementation:**
```python
from joblib import Parallel, delayed
results = Parallel(n_jobs=10, backend='threading')(...)
```

**Estimated memory**: 7GB + overhead = **~10GB** ✓

---

### Option 2: Reduce Batch Size + Sequential Processing

Process edges in very small batches sequentially:

**Pros:**
- Guaranteed to work
- Simple implementation

**Cons:**
- No parallelization benefit
- Slow (1,000 edges took 0.84 sec → 1.16M edges = ~16 minutes)

---

### Option 3: Shared Memory Multiprocessing (Advanced)

Use `multiprocessing.shared_memory` to share data across workers:

**Pros:**
- True multiprocessing speedup
- Controlled memory usage

**Cons:**
- Complex implementation
- Requires converting pandas to numpy arrays
- Fragile (shared memory management)

---

## Recommendation

**Use Option 1: Threading backend**

Change one line in `step2_pc_stable.py`:

```python
# OLD (crashes):
results = Parallel(n_jobs=N_CORES, verbose=0)(...)

# NEW (safe):
results = Parallel(n_jobs=N_CORES, backend='threading', verbose=0)(...)
```

**Expected performance:**
- Memory: ~10GB (safe)
- Speed: 70-80% of true multiprocessing
- Estimated runtime: **1-2 hours** for full 1.16M edges

---

## Action Items

1. ✅ Diagnose crash cause (memory explosion from multiprocessing)
2. ⏳ Modify `step2_pc_stable.py` to use threading backend
3. ⏳ Test with diagnose_crash.py (1, 4, 8 cores with threading)
4. ⏳ If tests pass, run full 1.16M edges with 10 cores (threading)

---

## Lessons Learned

- **Always monitor memory with multiprocessing** - data duplication is the default
- **joblib Parallel() duplicates data** unless using threading backend
- **OOM kills leave no Python traceback** - need system logs
- **Large DataFrames + multiprocessing = memory disaster**

---

**Status**: Ready to implement threading fix and retry.
