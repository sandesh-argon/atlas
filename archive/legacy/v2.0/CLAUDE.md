# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**V2 Research Specification: Global Causal Discovery System**

This project implements a bottom-up causal network reconstruction for development economics, analyzing 5,000-6,000 variables across 150+ countries over 25-40 years. The goal is to discover validated causal relationships and create a multi-level visualization dashboard for academic and public use.

**Philosophy**: Hybrid bottom-up approach that discovers causal networks from data, then validates outcome clusters against known quality-of-life constructs.

**Key Outputs**:
- Research: 2,000-8,000 node validated causal network
- Visualization: Multi-level graphs (Full: 2K-8K nodes, Professional: 300-800 nodes, Simplified: 30-50 nodes)
- Academic paper: Journal-ready with full methodology
- Dashboard: 5-level progressive disclosure system

## Project Structure

```
v2.0/
├── phaseA/           # Statistical Network Discovery (Weeks 1-4)
│   ├── A0_data_acquisition/
│   ├── A1_missingness_analysis/
│   ├── A2_granger_causality/
│   ├── A3_conditional_independence/
│   ├── A4_effect_quantification/
│   ├── A5_interaction_discovery/
│   └── A6_hierarchical_layers/
├── phaseB/           # Interpretability Layer (Week 5)
│   ├── B1_outcome_discovery/
│   ├── B2_mechanism_identification/
│   ├── B3_domain_classification/
│   ├── B4_multi_level_pruning/
│   └── B5_output_schema/
└── v2_master_instructions.md  # Complete specification (1,750+ lines)
```

## Key Technical Architecture

### Two-Phase Pipeline

**Phase A: Statistical Discovery**
1. **A0**: Data acquisition from 11 sources (World Bank, WHO, UNESCO, etc.)
2. **A1**: Missingness sensitivity analysis (25 parallel configs)
3. **A2**: Granger causality with prefiltering (6.2M → 200K tests)
4. **A3**: PC-Stable conditional independence (remove spurious correlations)
5. **A4**: Effect size quantification with bootstrap validation
6. **A5**: Interaction discovery (constrained search: 2M tests)
6. **A6**: Hierarchical layer assignment via topological sort

**Phase B: Interpretability**
1. **B1**: Outcome discovery with 3-part validation (domain coherence, literature alignment, R² > 0.40)
2. **B2**: Semantic clustering (two-stage: keyword + embedding clustering)
3. **B3.5**: Semantic hierarchy builder (Domain → Subdomain → Cluster → Indicator)
4. ~~**B3/B4**: DEPRECATED - replaced by semantic hierarchy approach~~
5. **B5**: Output schema generation with dashboard metadata + edge index

**⚠️ CRITICAL FIX (December 2025):**
- A6 was corrected to remove 4,254 virtual INTERACT_ nodes
- Interactions are now stored as **edge metadata** (`edge['moderators']`)
- Real nodes: 3,872 (not 8,126)

### Critical V1 Lessons Integrated

**See `V1_LESSONS.md` for complete documentation**

### ✅ V1 Validated Utilities (REUSE EXACTLY)

**Location**: `shared_utilities/`

1. **Saturation Transforms** (`data_processing/saturation_transforms.py`)
   - Evidence: +5.6% mean R² improvement
   - V2 Timing: Apply at B1 (after factor analysis), NOT A0
   - Functions: saturate_life_expectancy(), saturate_gdp_per_capita(), etc.

2. **Imputation Weighting** (`data_processing/imputation_weighting.py`)
   - Evidence: +0.92pp mean R², improved 8/8 V1 metrics
   - Tier weights: 1.0 (observed), 0.85 (interpolation), 0.70 (MICE <40%), 0.50 (MICE >40%)
   - V2 Integration: A2 (SHAP downweighting), A4 (effect downweighting), B1 (factor validation)

3. **Backdoor Adjustment** (`causal_methods/backdoor_adjustment.py`)
   - Evidence: 51/80 edges significant (63.7%), stable under 1000 bootstrap iterations
   - V2 Scaling: Use n_bootstrap=100 for intermediate (A4), 1000 for final validation
   - V2 Application: A4 effect quantification

4. **V1 Data Scrapers** (`phaseA/A0_data_acquisition/`)
   - 5 validated scripts: World Bank, WHO, UNESCO, IMF, UNICEF
   - Runtime: 12-18 hours, fetch 5,340 indicators
   - V2 Addition: Write 6 new scrapers (V-Dem, QoG, OECD, Penn, WID, Transparency) for +4,010 indicators

### ❌ V1 Critical Failures to Avoid (8 Mistakes)

**See `V1_LESSONS.md` for full details**

1. ❌ **NEVER Normalize Before Saturation**: Destroys saturation curves → Always saturate → normalize
2. ❌ **NEVER Use Global Coverage**: 80-94% data loss → Use 80% per-country temporal coverage
3. ❌ **NEVER Domain-Balance Selection**: 0/8 metrics improved → Pure statistical selection
4. ❌ **NEVER Use Neural Nets for n<5K**: Val R² = -2.35 → Use LightGBM/XGBoost
5. ❌ **NEVER Exclude Disaggregations**: Lost 87.5% of drivers → Only exclude self-lagged
6. ❌ Imputation without weighting (V1 fixed with tier system)
7. ❌ Granger testing all pairs (V2 MUST prefilter: 6.2M → 200K)
8. ❌ PC-Stable on dense graphs (V2 early stopping: switch to GES if >50K edges)

### ⚠️ V1↔V2 Architecture Differences

**Scale**: V2 is 10-50× larger than V1
- Variables: 2,480 (V1) → 4,000-5,000 (V2)
- Outcomes: 8 pre-selected (V1) → 12-20 discovered (V2)
- Graph: 162 nodes (V1) → 2,000-8,000 nodes (V2)
- Granger tests: 56 pairs (V1) → 200,000 pairs (V2)

**Approach**: V2 discovers what V1 assumed
- V1: Pre-selected 8 outcomes by domain experts
- V2: Discover 12-20 outcomes via factor analysis (B1)
- V1: Apply saturation at Phase 0 (knew which were deficiency needs)
- V2: Apply saturation at B1 (after discovering deficiency needs)
- V1: Models are end product (deployable LightGBM)
- V2: Models for validation only (factor R² check, SHAP ranking)

## Tech Stack

**Core Libraries**:
- `causallearn`: PC-Stable, GES algorithms for causal discovery
- `dowhy`: Backdoor adjustment set identification
- `statsmodels`: Granger causality tests
- `networkx`: Graph operations, topological sorting
- `scikit-learn`: Random forests, cross-validation, clustering
- `shap`: Explainability for pruning validation
- `sentence-transformers`: Semantic clustering for domain classification
- `factor_analyzer`: Factor analysis for outcome discovery

**Infrastructure**:
- Local workstation (Linux)
- CPU: AMD Ryzen 9 7900X (12 cores, 24 threads @ 86% base clock)
- RAM: 31 GB total (23 GB available)
- GPU: NVIDIA GeForce RTX 4080 (16 GB VRAM)
- Storage: 1.8 TB available
- Parallelization: `joblib` + `ray`
- Estimated runtime: 14-21 days

## System Resource Allocation Strategy

### ⚙️ Actual System Specifications

**CPU**: AMD Ryzen 9 7900X
- Physical cores: 12
- Logical threads: 24
- Architecture: Zen 4
- Base frequency: ~4.7 GHz (running at 86% = ~4.0 GHz)

**Memory**:
- Total RAM: 31 GB
- Available: 23 GB (after OS and background processes)
- Swap: 4 GB

**GPU**:
- Model: NVIDIA GeForce RTX 4080
- VRAM: 16 GB
- CUDA cores: 9728
- Tensor cores: 304 (4th gen)

**Storage**:
- Available: 1.8 TB (plenty for checkpoints)
- Type: High-speed SSD (based on system specs)

### 🎯 CPU Resource Allocation Policy

**IMPORTANT - Thermal Constraints**: System experiences CPU thermal throttling above 90°C with sustained load.

**CPU Parallelization** (12 cores MAX for thermal safety):
```python
import joblib
from joblib import Parallel, delayed

# Use 12 cores MAX for CPU-bound operations (50% of 24 threads)
# CRITICAL: Higher values (15-20 cores) cause thermal shutdowns
N_JOBS = 12

# Example: Parallel Granger causality tests
results = Parallel(n_jobs=N_JOBS, verbose=10, backend='loky')(
    delayed(granger_causality_test)(X, Y, maxlag=5, data=data)
    for X, Y in candidate_pairs
)
```

**Thermal History**:
- 20 cores: System crash (thermal emergency shutdown)
- 15 cores: System crash (thermal emergency shutdown)
- 12 cores: Safe operation (temps <85°C)
- 10 cores: Very safe (used for A2 Granger testing - completed successfully)

**Memory Management** (19.5 GB @ 85% of available):
```python
import numpy as np

# Calculate safe chunk size to stay within 19.5 GB
MAX_MEMORY_GB = 19.5
BYTES_PER_GB = 1024**3

# For 6,368 indicators × 180 countries × 35 years = ~40M data points
# With float64 (8 bytes): 40M × 8 = 320 MB per full dataset
# Safe to load full dataset + 60× working memory for operations

# Chunk strategy for large operations
def get_chunk_size(n_pairs, memory_per_pair_mb=2.0):
    """Calculate optimal chunk size given memory constraints"""
    max_pairs_in_memory = int((MAX_MEMORY_GB * 1024) / memory_per_pair_mb)
    return min(max_pairs_in_memory, n_pairs)
```

**GPU Utilization** (13.6 GB VRAM @ 85% of 16 GB):
```python
import torch

# Reserve 85% of GPU memory for compute operations
GPU_MEMORY_FRACTION = 0.85

# Set PyTorch memory allocation
torch.cuda.set_per_process_memory_fraction(GPU_MEMORY_FRACTION)

# For semantic embeddings in B3 (sentence-transformers)
# RTX 4080 can batch ~200-300 indicators at once with large models
EMBEDDING_BATCH_SIZE = 256

# For LightGBM/XGBoost GPU acceleration in B1 validation
# RTX 4080 provides 5-10× speedup vs CPU for tree boosting
USE_GPU = True
GPU_PARAMS = {
    'device': 'cuda',
    'gpu_id': 0,
    'max_bin': 255  # RTX 4080 can handle larger bins
}
```

### 📊 Phase-Specific Resource Profiles

**A1: Missingness Analysis** (COMPLETED)
- CPU: 22 cores (91% utilization - used for KNN imputation experiment)
- RAM: ~8 GB peak
- Runtime: 14 hours

**A2: Granger Causality** (COMPLETED)
- CPU: 10 cores (thermal safety - higher values caused crashes)
- RAM: 12-15 GB peak (memory-safe design with incremental saves)
- GPU: Not used (statsmodels Granger test is CPU-only)
- Actual runtime: 7 hours (15.9M pairs)
- Results: 9.2M successful tests, 3.7M significant at p<0.05
- Checkpoint every: 100K pairs (~6 minutes)

**A3: PC-Stable Conditional Independence**
- CPU: 12 cores MAX (thermal safety)
- RAM: 18-20 GB (graph structure in memory)
- GPU: Not used (causallearn is CPU-only)
- Estimated runtime: 3-5 days
- Early stopping: Switch to GES if >50K edges

**A4: Effect Quantification**
- CPU: 12 cores MAX (parallel bootstrap iterations)
- RAM: 15-18 GB
- GPU: Not used (dowhy/econml use CPU)
- Estimated runtime: 4-6 days

**A5: Interaction Discovery**
- CPU: 12 cores MAX (constrained search space)
- RAM: 16-19 GB
- GPU: Not used
- Estimated runtime: 3-4 days

**B1: Outcome Discovery**
- CPU: 12 cores MAX (factor analysis is memory-bound, not CPU-bound)
- RAM: 18-20 GB (correlation matrices for 6K variables)
- GPU: YES - RTX 4080 for LightGBM validation models
  - Tree boosting: 5-10× speedup
  - Cross-validation: Fit 5 models in parallel on GPU
- Estimated runtime: 8-12 hours

**B3: Domain Classification**
- CPU: 8 cores (sentence-transformers has limited CPU parallelization)
- RAM: 10-12 GB
- GPU: YES - RTX 4080 for semantic embeddings
  - Model: all-mpnet-base-v2 (768 dim, 420M params)
  - Batch size: 256 indicators at once
  - Speedup: 20-50× vs CPU
- Estimated runtime: 2-3 hours (vs 1-2 days on CPU)

**B4: Multi-Level Pruning**
- CPU: 20 cores (SHAP tree explainer can parallelize)
- RAM: 16-18 GB
- GPU: YES - RTX 4080 for SHAP computation
  - GPU-accelerated tree SHAP for LightGBM models
  - Speedup: 10-15× vs CPU
- Estimated runtime: 4-6 hours

### 🔧 Optimization Strategies

**1. Memory-Efficient Data Loading**
```python
import pickle
import mmap

def load_checkpoint_memory_mapped(checkpoint_path):
    """Load large checkpoints without full memory load"""
    with open(checkpoint_path, 'rb') as f:
        # Memory-map the file
        mmapped_file = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
        data = pickle.loads(mmapped_file)
    return data
```

**2. Adaptive Chunk Sizing**
```python
import psutil

def adaptive_chunk_size(base_chunk=10000):
    """Adjust chunk size based on available memory"""
    available_gb = psutil.virtual_memory().available / (1024**3)

    if available_gb > 20:
        return base_chunk * 2
    elif available_gb > 15:
        return base_chunk
    else:
        return base_chunk // 2
```

**3. GPU Memory Clearing**
```python
import gc
import torch

def clear_gpu_memory():
    """Aggressively clear GPU memory between phases"""
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        torch.cuda.synchronize()
```

**4. Checkpoint Compression**
```python
import pickle
import lzma

def save_compressed_checkpoint(data, filepath):
    """Save checkpoints with LZMA compression (3-5× smaller)"""
    with lzma.open(filepath, 'wb') as f:
        pickle.dump(data, f)

def load_compressed_checkpoint(filepath):
    """Load compressed checkpoints"""
    with lzma.open(filepath, 'rb') as f:
        return pickle.load(f)
```

### 🚨 Resource Monitoring

**Automatic monitoring during long operations**:
```python
import psutil
import time
from datetime import datetime

class ResourceMonitor:
    def __init__(self, log_interval=300):  # Log every 5 minutes
        self.log_interval = log_interval
        self.start_time = time.time()

    def log_resources(self, operation_name):
        """Log current resource usage"""
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()

        if torch.cuda.is_available():
            gpu_memory = torch.cuda.memory_allocated() / (1024**3)
            gpu_memory_cached = torch.cuda.memory_reserved() / (1024**3)
        else:
            gpu_memory = gpu_memory_cached = 0

        elapsed = time.time() - self.start_time

        print(f"[{datetime.now().strftime('%H:%M:%S')}] {operation_name}")
        print(f"  CPU: {cpu_percent:.1f}% | RAM: {memory.percent:.1f}% ({memory.used/(1024**3):.1f}/{memory.total/(1024**3):.1f} GB)")
        print(f"  GPU: {gpu_memory:.2f} GB allocated, {gpu_memory_cached:.2f} GB cached")
        print(f"  Elapsed: {elapsed/3600:.2f} hours")

    def check_memory_warning(self):
        """Warn if approaching memory limits"""
        memory = psutil.virtual_memory()
        if memory.percent > 90:
            print("⚠️  WARNING: RAM usage >90% - consider reducing chunk size")
            return True
        return False
```

### 💾 Storage Management

**Checkpoint size estimates**:
- A1 output: ~530 MB (compressed pickle)
- A2 output: ~200-300 MB (edge list with metadata)
- A3 output: ~150-200 MB (pruned graph)
- A4 output: ~300-400 MB (effect sizes + CIs)
- B4 output: ~100-150 MB (3 pruned graphs)

**Total storage needed**: ~2-3 GB for all checkpoints (well within 1.8 TB available)

### 🎯 Execution Protocol with Resource Constraints

**Before each phase**:
1. Check available memory: `psutil.virtual_memory().available`
2. Adjust parallelization: N_JOBS based on available RAM
3. Clear GPU cache if using GPU
4. Set checkpoint intervals based on estimated runtime

**During execution**:
1. Monitor resources every 5 minutes
2. Log warnings if RAM >90% or CPU <50% (underutilization)
3. Auto-checkpoint if memory warning triggered
4. Throttle parallelization if memory pressure detected

**After each phase**:
1. Clear all temporary data structures
2. Run garbage collection
3. Verify checkpoint size and integrity
4. Log final resource usage statistics

## Key Algorithms

### 1. Granger Prefiltering (A2)
```python
# Reduces 6.2M → 200K candidate pairs before testing
def prefilter_candidate_pairs(var_X, var_Y, data, literature_db):
    # Stage 1: Correlation threshold (0.10 < |r| < 0.95)
    # Stage 2: Domain compatibility matrix (13×13 plausibility map)
    # Stage 3: Temporal precedence (exclude self-lagged)
    # Stage 4: Literature plausibility check
    # Stage 5: Theoretical plausibility
```

### 2. Factor Validation (B1)
```python
# Three-part validation prevents junk dimensions
def validate_factor(factor_index, top_variables, loadings, data, literature_db):
    # Check 1: Domain coherence (max 3 unique domains)
    # Check 2: Literature alignment (TF-IDF similarity > 0.60)
    # Check 3: Predictability (RF cross-val R² > 0.40)
```

### 3. Multi-Level Pruning (B4)
```python
# Creates 3 graph versions with SHAP mass retention validation
# Full (L1-2): 2K-8K nodes (academic/expert)
# Professional (L3): 300-800 nodes (policy analysts)
# Simplified (L4-5): 30-50 nodes (general public)
# Constraint: Pruned graphs must retain ≥85% of SHAP explanatory power
```

## Common Commands

**No package.json exists yet** - this is a Python research project. Commands will be:

```bash
# Setup (not yet implemented)
pip install -r requirements.txt

# Phase A: Statistical Discovery
python phaseA/A0_data_acquisition/collect_data.py
python phaseA/A1_missingness_analysis/run_sensitivity.py
python phaseA/A2_granger_causality/prefilter_and_test.py
# ... etc

# Phase B: Interpretability
python phaseB/B1_outcome_discovery/factor_analysis.py
# ... etc

# Validation
python validation/bootstrap_stability.py
python validation/holdout_test.py
```

## Data Schema

### Input Data Sources (A0)
- World Bank WDI + Poverty (~2,040 indicators)
- WHO GHO (~2,000 indicators)
- UNESCO UIS (~200 indicators)
- UNICEF (~300 indicators)
- V-Dem (~450 indicators)
- QoG Institute (~2,000 indicators)
- IMF IFS (~800 indicators)
- OECD.Stat (~1,200 indicators)
- Penn World Tables (~180 indicators)
- World Inequality DB (~150 indicators)
- Transparency International (~30 indicators)

**Initial Filter**:
- Country coverage ≥ 80 countries
- Temporal span ≥ 10 years
- Per-country temporal coverage ≥ 0.80 (V1 lesson)
- Missing rate ≤ 0.70

### Output Schema (B5)
```json
{
  "metadata": {
    "version": "2.0",
    "n_nodes": {"full": 4872, "professional": 487, "simplified": 43},
    "temporal_window": [1990, 2024],
    "validation_scores": {
      "bootstrap_stability": 0.84,
      "literature_reproduction": 0.76,
      "mean_r2_holdout": 0.63
    }
  },
  "nodes": [
    {
      "id": "life_expectancy",
      "label": "Life Expectancy at Birth",
      "layer": 5,
      "type": "outcome_metric",
      "domain": "Health",
      "centrality": {"betweenness": 0.042, "pagerank": 0.0031},
      "visible_in": ["full", "professional", "simplified"]
    }
  ],
  "edges": [
    {
      "source": "physicians_per_1000",
      "target": "life_expectancy",
      "lag": 3,
      "effect": {"beta": 0.34, "ci": [0.29, 0.39]},
      "tests": {"granger_p": 3.4e-12, "conditional_independence": "validated"}
    }
  ]
}
```

## Validation Framework

### Success Criteria

**Phase A Targets**:
- Variables: 4,000-6,000 (after filters)
- Validated edges: 2,000-10,000
- Mean effect size: |β| > 0.15
- Bootstrap retention: >75%
- DAG validity: No cycles

**Phase B Targets**:
- Outcomes: 12-25 validated dimensions
- Mechanisms: 20-50 clusters
- Domains: 12-20 coherent labels
- SHAP retention: >85% (pruned vs full)

**Overall Validation**:
- Literature reproduction: >70%
- Holdout R²: >0.55
- Regional generalization: >0.45
- Specification robustness: >65% edge overlap

### Checkpoint Strategy
```python
# Save checkpoints after each phase for resume capability
CHECKPOINT_DIR = Path('/mnt/checkpoints')

# Checkpoints saved at:
# - A1_missingness_optimal_config.pkl
# - A2_granger_validated_edges.pkl
# - A3_pc_stable_graph.pkl
# - A4_effect_estimates_with_ci.pkl
# - B4_pruned_graphs.pkl
```

## File Organization

**Each phase folder should contain**:
1. Main script (e.g., `run_granger_tests.py`)
2. Utilities (e.g., `prefilter_utils.py`)
3. Validation tests (e.g., `test_granger_stability.py`)
4. Output checkpoints (e.g., `validated_edges.pkl`)
5. Documentation (e.g., `README.md` with phase-specific notes)

**Naming conventions**:
- Scripts: `lowercase_with_underscores.py`
- Classes: `CamelCase`
- Functions: `snake_case`
- Constants: `UPPER_CASE`

## Development Workflow

### Adding New Analysis Steps
1. Create subfolder in appropriate phase (e.g., `phaseA/A2_granger_causality/`)
2. Implement main logic with validation checkpoints
3. Add unit tests for core functions
4. Document assumptions and thresholds in docstrings
5. Save checkpoint with metadata
6. Update this CLAUDE.md if adding new architectural patterns

### Running Experiments
1. Always save checkpoints before long-running operations
2. Use parallel processing for independent computations (joblib/ray)
3. Implement early stopping conditions (see master instructions line 1240-1256)
4. Validate outputs against success criteria before proceeding

### Code Quality Standards
- Type hints for all function parameters and returns
- Docstrings with References to literature where applicable
- Assert statements for critical validation checks
- Logging for long-running operations
- Unit tests for algorithmic components

## Risk Mitigation

**Critical Risks** (from master instructions):
1. **Network sparsity crisis**: Mitigated by prefiltering (6.2M → 200K tests)
2. **Junk outcome factors**: Mitigated by 3-part validation (domain, literature, R²)
3. **Computational bottleneck**: Mitigated by parallelization + checkpointing + early stopping
4. **Interaction explosion**: Mitigated by constrained search (mechanisms × outcomes only)

## References

**Master Specification**: `v2_master_instructions.md` (1,750+ lines)
- Full pipeline details: Lines 74-1239
- Validation framework: Lines 1030-1155
- Computational strategy: Lines 1156-1259
- V1 lessons learned: Lines 1260-1295

**External Resources**:
- PC-Stable algorithm: Zhang (2008) "On the completeness of orientation rules"
- Granger causality: Granger (1969) "Investigating causal relations"
- Backdoor criterion: Pearl (1995) "Causal diagrams for empirical research"
- Progressive disclosure: Nielsen Norman Group UX research

## Dashboard Integration

**5-Level Progressive Disclosure**:
- **Level 1 (Expert)**: Full graph, download data, methodology docs, citation generator
- **Level 2 (Researcher)**: Full graph, interactive filtering, mechanism explorer
- **Level 3 (Professional)**: Pruned graph (300-800 nodes), scenario testing, policy simulator
- **Level 4 (Engaged Public)**: Simplified graph (30-50 nodes), storytelling mode, plain language
- **Level 5 (Casual)**: Simplified graph, pre-built narratives, video explainers

**Academic Credibility Features**:
- Citation generator (BibTeX, APA, Chicago, MLA)
- Methodology transparency (full pipeline documentation)
- Data download (JSON, GraphML, CSV)
- Version control (changelog, archived versions)

## EXECUTION SAFEGUARDS (CRITICAL - READ FIRST)

### ⚠️ Pre-Execution Checklist (DO NOT START PHASE A WITHOUT THESE)

**REQUIRED before A0**:
1. ✅ Literature reference database: `literature_db/literature_constructs.json`
   - 10+ known QOL constructs with keywords, indicators, canonical papers
   - Used for B1 outcome validation (TF-IDF similarity matching)
   - Reference: master instructions lines 22-43

2. ✅ Domain compatibility matrix: `phaseA/A2_granger_causality/domain_compatibility_matrix.json`
   - 13×13 matrix of plausible domain connections
   - Critical for A2 prefiltering (6.2M → 200K reduction)
   - Reference: master instructions lines 211-228

3. ✅ V1 validated outcomes: `phaseB/B1_outcome_discovery/v1_validated_outcomes.json`
   - 8 anchor outcomes from V1 (must reproduce ≥6)
   - Reference: master instructions lines 494-498, 616-619

4. ✅ Validation test templates: `validation/test_templates/`
   - Pre-defined tests to prevent scope creep
   - Reference: master instructions lines 1030-1155

**See `EXECUTION_FRAMEWORK.md` for complete pre-A0 setup guide**

### 🚨 Scope Limitation Rules (PREVENT RABBIT HOLES)

**Rule 1: Time-Boxing**
- Every step has STRICT time limit from master instructions
- Check elapsed time every hour during long operations
- If >1.5x expected time, PAUSE and request human validation
- Example: A2 max 6 days → if at 9 days, stop and reassess

**Rule 2: Success Criteria Gates**
- MUST pass validation before proceeding to next step
- If ANY criterion fails, PAUSE and request human validation
- Do NOT proceed with "good enough" - academic rigor required
- Example: If A2 produces 85K edges but range is 30-80K, investigate before A3

**Rule 3: Scope Guards**
- Only implement operations listed in master instructions
- If tempted to add "improvements", STOP and verify against spec
- No exploratory analysis unless explicitly in master instructions
- Example: Don't add PCA dimensionality reduction (not in spec)

**Rule 4: Early Stopping Conditions**
- Pre-defined fallback strategies from master instructions lines 1240-1256
- Trigger automatically, document decision, continue
- Example: If A3 edges >50K, switch from PC-Stable to GES (per spec)

**Rule 5: Long-Running Task Protocol (>1 hour estimated)**

⚠️ **MANDATORY PRE-FLIGHT CHECKLIST** (DO NOT SKIP ANY STEP):
1. ✅ Ensure script writes progress to JSON file (e.g., `outputs/A3/progress.json`)
2. ✅ **CREATE monitor.sh FIRST** - before running the script!
3. ✅ Test that monitor.sh works: `./monitor.sh`
4. ✅ Then and ONLY then start the long-running task

- BEFORE starting any task estimated >1 hour:
  1. Run a test batch with REAL data (e.g., 1000-5000 samples)
  2. Measure actual throughput (items/second)
  3. Calculate updated time estimate based on real measurements
  4. Report estimate to user before full run
  5. **CREATE monitor.sh SCRIPT** (not optional - user needs this!)

- **monitor.sh TEMPLATE** (create in scripts/AX/ directory):
  ```bash
  #!/bin/bash
  # AX Monitor - Usage: ./monitor.sh (or: watch -n 10 ./monitor.sh)
  PROGRESS_FILE="<repo-root>/v2.0/v2.1/outputs/AX/progress.json"
  LOG_FILE="<repo-root>/v2.0/v2.1/logs/step_name.log"
  echo "=========================================="
  echo "AX STEP_NAME MONITOR"
  echo "=========================================="
  if [ -f "$PROGRESS_FILE" ]; then
      cat "$PROGRESS_FILE" | python3 -c "
  import json, sys
  data = json.load(sys.stdin)
  print(f\"Step: {data.get('step', 'N/A')}\")
  print(f\"Progress: {data.get('pct', 0):.1f}%\")
  print(f\"Items: {data.get('items_done', 0):,} / {data.get('items_total', 0):,}\")
  print(f\"Elapsed: {data.get('elapsed_min', 0):.1f} min\")
  print(f\"ETA: {data.get('eta_min', 0):.1f} min\")
  print(f\"Updated: {data.get('updated', 'N/A')}\")
  "
  else
      echo "Progress file not found"
  fi
  echo ""
  echo "CPU Temps:"
  sensors 2>/dev/null | grep -E "Tctl|Tccd" | head -3
  echo ""
  echo "Memory:"
  free -h | head -2
  ```

- **INTRA-CHUNK PROGRESS MONITORING** (for joblib Parallel tasks):
  - Joblib verbose output shows: `[Parallel(n_jobs=10)]: Done 201 tasks | elapsed: 6.2min`
  - Parse this from log file to show LIVE progress BEFORE chunk completes
  - Add this section to monitor.sh for joblib-based tasks:
  ```bash
  # Parse joblib verbose output for INTRA-CHUNK progress
  if [ -f "$LOG_FILE" ]; then
      echo "--- Live Progress (from joblib output) ---"
      python3 -c "
  import re
  log_file = '$LOG_FILE'
  chunk_info = None
  tasks_done = 0
  elapsed = 'N/A'
  total_items = 58837  # SET THIS TO YOUR TOTAL
  chunk_size = 500     # SET THIS TO YOUR CHUNK SIZE

  with open(log_file, 'r') as f:
      lines = f.readlines()

  # Get current chunk: 📦 Chunk 1/118: Edges 0 - 500
  for line in lines:
      if 'Chunk' in line and ('Edges' in line or 'Items' in line):
          match = re.search(r'Chunk (\d+)/(\d+):.*?(\d+) - (\d+)', line)
          if match:
              chunk_num, total_chunks = int(match.group(1)), int(match.group(2))
              chunk_start, chunk_end = int(match.group(3)), int(match.group(4))
              chunk_info = (chunk_num, total_chunks, chunk_start, chunk_end)

  # Get latest joblib progress
  for line in reversed(lines[-50:]):
      match = re.search(r'Done\s+(\d+)\s+tasks.*elapsed:\s+([\d.]+\s*\w+)', line)
      if match:
          tasks_done = int(match.group(1))
          elapsed = match.group(2)
          break

  if chunk_info:
      chunk_num, total_chunks, chunk_start, chunk_end = chunk_info
      total_done = chunk_start + tasks_done
      pct = 100.0 * total_done / total_items
      print(f'Chunk: {chunk_num}/{total_chunks} | Tasks: {tasks_done}/{chunk_end-chunk_start}')
      print(f'Overall: {total_done:,}/{total_items:,} ({pct:.1f}%) | Elapsed: {elapsed}')
  else:
      print('Waiting for first chunk...')
  "
  fi
  ```
  - **CRITICAL**: Always use `verbose=10` in joblib.Parallel to enable this monitoring
  - Example: `Parallel(n_jobs=10, verbose=10, batch_size='auto')(...)`
  - **CRITICAL**: Redirect stderr to log file using TeeStderr class (joblib writes to stderr, not stdout):
  ```python
  # Add this after logging setup to capture joblib verbose output in log file
  class TeeStderr:
      """Tee stderr to both console and log file for joblib verbose output"""
      def __init__(self, log_file):
          self.terminal = sys.stderr
          self.log = open(log_file, 'a')
      def write(self, message):
          self.terminal.write(message)
          self.log.write(message)
          self.log.flush()
      def flush(self):
          self.terminal.flush()
          self.log.flush()

  sys.stderr = TeeStderr(LOG_FILE)
  ```

- DURING long runs:
  1. Progress must be visible (% complete, ETA, throughput)
  2. Checkpoint every 10-15 minutes for runs >1 hour
  3. Log progress to file for recovery

- **CRITICAL: INTRA-CHUNK PROGRESS REPORTING**:
  - Progress JSON must be written DURING chunk processing, not just after chunk completion
  - If using joblib Parallel, use a callback or periodic update (every 30-60 seconds minimum)
  - User should see progress % update within 1 minute of starting, NOT after first chunk completes
  - Example: For 5000-edge chunks at 5 edges/sec = 16 min per chunk is TOO LONG to wait
  - Use smaller chunks (500-1000) OR add intra-chunk progress updates

- **CRITICAL: Progress tracking must be in a SEPARATE FILE** (not just stdout):
  - Write progress to a JSON file (e.g., `outputs/A2/progress.json`)
  - Format: `{"step": "A2", "pct": 57.1, "elapsed_min": 5.5, "eta_min": 4.1, "items_done": 5312510, "items_total": 9743762, "updated": "2025-12-03T20:24:00"}`
  - User can monitor with: `watch -n 10 ./monitor.sh`
  - This allows monitoring OUTSIDE of the Claude chat session

- This prevents wildly inaccurate time estimates (e.g., "3-4 days" vs actual "4-5 hours")

### 📋 Context Management (CRITICAL FOR LONG PROJECT)

**Problem**: Context window auto-compacts after ~150K tokens

**Solution**: Progressive context preservation

**At START of each step**:
1. Create `CONTEXT.md` summarizing inputs, objectives, success criteria
2. Create `INPUT_MANIFEST.json` with data from previous step
3. Read previous step's `OUTPUT_MANIFEST.json`
4. Verify context continuity with `ensure_context_continuity()`

**At END of each step**:
1. Create `OUTPUT_MANIFEST.json` with results, validation, next inputs
2. Update `PROJECT_STATUS.json` (global progress tracker)
3. Save checkpoint to `checkpoints/`
4. Log to `validation/HUMAN_DECISIONS.json` if review occurred

**If context compacts mid-step**:
1. Read `CONTEXT.md` for current step
2. Read `PROJECT_STATUS.json` for completed steps
3. Load latest checkpoint from `checkpoints/`
4. Read previous step's `OUTPUT_MANIFEST.json`
5. Continue from checkpoint

**See `EXECUTION_FRAMEWORK.md` for detailed context management protocol**

### 🤝 Human Validation Integration

**Request human review when**:
1. ✋ **Validation failure**: Any success criterion fails
2. ✋ **Novelty detection**: Pattern not in literature (confidence <0.60 in B1)
3. ✋ **Time overrun**: Step exceeds 1.5x expected time
4. ✋ **Ambiguity**: Multiple valid paths forward (need decision)
5. ✋ **Low confidence**: Domain classification <0.80 (B3), factor validation <0.60 (B1)
6. ✋ **Critical decision points**:
   - A1: Top 3 imputation configs within 2% score
   - A2: Prefiltering removed >99% of pairs
   - B1: Novel factors discovered (not in literature)
   - B4: SHAP retention <85% after pruning

**Human validation format**:
```python
request_human_validation(
    step="A1_missingness_analysis",
    issue="Config selection ambiguity - top 3 within 2%",
    options=[...],  # Structured choices with pros/cons
    context={...}   # Relevant data, V1 comparison, spec reference
)
```

**Log all decisions** in `validation/HUMAN_DECISIONS.json` with:
- Timestamp, step, issue, options, choice, rationale, impact

### 🔍 Inter-Step Handoff Protocol

**Every step produces**:
- `OUTPUT_MANIFEST.json`: What was produced, validation results, notes
- `CONTEXT.md`: Summary for next step
- Checkpoint in `checkpoints/`

**Every step consumes**:
- Previous step's `OUTPUT_MANIFEST.json`
- `PROJECT_STATUS.json` (global progress)
- Previous step's checkpoint

**Template** (see `EXECUTION_FRAMEWORK.md` for full examples):
```python
# Load previous context
a2_context = load_previous_context("A2_granger_causality")
validated_edges = pd.read_pickle(a2_context['outputs']['validated_edges']['file'])
logger.info(f"Loaded {len(validated_edges)} edges from A2")
```

### 📊 Progress Tracking

**Global status**: `PROJECT_STATUS.json` (root directory)
- Current phase, current step, progress %
- Completed steps with outputs and validation status
- Key metrics accumulating across steps
- Updated after every step completion

**Step-level tracking**:
- `CONTEXT.md`: Current objectives, progress checkboxes
- Checkpoint frequency: Every 4 hours for long operations (A2, A3, A5)

## Current Status

**Project Phase**: Phase B in progress (B2 complete, ready for B3.5)

**Completed Steps**:
- ✅ **A0-A6**: Phase A complete
  - Final graph: 3,872 real indicator nodes, 11,003 edges, 21 layers
  - Interactions stored as edge metadata (4,254 moderator entries on 1,309 edges)

- ✅ **A6 Fix** (December 3, 2025):
  - **Problem**: 4,254 virtual INTERACT_ nodes were incorrectly created as graph nodes
  - **Solution**: Removed virtual nodes, stored interactions as `edge['moderators']` metadata
  - **Result**: 8,126 → 3,872 nodes (52.4% reduction - all removed nodes were fake)
  - Script: `phaseA/A6_hierarchical_layering/scripts/fix_interaction_nodes.py`

- ✅ **B1**: Outcome discovery
  - 9 validated outcome factors
  - No INTERACT_ references (unaffected by A6 fix)

- ✅ **B2**: Semantic clustering (December 3, 2025)
  - Method: Two-stage (keyword + embedding clustering)
  - 73 coarse clusters → 168 fine clusters
  - 100% coverage (0 unclassified)
  - Domain distribution: Governance (52), Economic (49), Education (26), Demographics (15), Health (11), Environment (8), Security (5)

- ✅ **B3.5**: Semantic hierarchy builder (December 3, 2025)
  - 7-level hierarchy: Super-domain (3) → Domain (9) → Subdomain (71) → Coarse (73) → Fine (168) → Groups → Indicators (3,872)
  - SHAP-like composite scores for all indicators (pagerank=0.35, betweenness=0.25, layer=0.25, degree=0.15)
  - Fixed cluster naming: `Governance_Sovereignty` → `Governance_Direct_Democracy`

**Key Output Files**:
- `phaseA/A6_hierarchical_layering/outputs/A6_hierarchical_graph.pkl` (corrected - 3,872 nodes)
- `phaseA/A6_hierarchical_layering/outputs/A6_edge_index.pkl` (by_source, by_target)
- `phaseB/B2_mechanism_identification/outputs/B2_semantic_clustering.pkl` (168 clusters)
- `phaseB/B35_semantic_hierarchy/outputs/B35_semantic_hierarchy.pkl` (7-level hierarchy)
- `phaseB/B35_semantic_hierarchy/outputs/B35_node_semantic_paths.json` (fast lookup)
- `phaseB/B35_semantic_hierarchy/outputs/B35_shap_scores.pkl` (importance scores)

**Next Step**: B5 output schema / visualization export

## 🚨 CRITICAL: ALWAYS KILL JOBLIB WORKERS FIRST! 🚨

**⚠️ COMMON MISTAKE**: Killing only the main Python process leaves 10-12 zombie worker processes running!

**THE PROBLEM**:
- `pkill -9 -f "step3_effect_estimation"` kills ONLY the main process
- Joblib spawns 10-12 worker processes via `loky.backend.popen_loky_posix`
- **These workers survive when the main process dies!**
- They consume 90-100% CPU EACH (900-1200% total CPU)
- Cause thermal issues (94°C+)
- Interfere with new runs

**✅ CORRECT CLEANUP (ALWAYS DO THIS):**

```bash
# STEP 1: Kill main processes
pkill -9 -f "step2_backdoor"
pkill -9 -f "step2c_validate"
pkill -9 -f "step3_effect_estimation"
pkill -9 -f "step3_hybrid"

# STEP 2: Kill joblib worker processes (CRITICAL - DON'T SKIP!)
pkill -9 -f "loky.backend.popen_loky_posix"
pkill -9 -f "resource_tracker"

# STEP 3: Verify ALL killed (should return 0 or only show unrelated Python)
ps aux | grep python | grep -E "(loky|step2|step3)" | grep -v grep | wc -l

# STEP 4: If any remain, kill by PID
kill -9 <PID>
```

**When to do this**:
- **BEFORE EVERY NEW TEST/RUN** (no exceptions!)
- After any crash or interruption
- When thermal warnings appear (>85°C)
- If uncertain about process state
- When you see >20 Python processes running

**How to verify clean state**:
```bash
# Should show only 1-2 Python processes (system/unrelated)
ps aux | grep python | grep -v grep | wc -l

# Should show 0
ps aux | grep python | grep -E "(loky|step2|step3)" | grep -v grep | wc -l
```

## 🔍 Pause-for-Review Protocol

### User-Requested Review Pauses

**Between each major step outlined in the A2 checklist, PAUSE and wait for user approval:**

1. ⏸️ After Step 1: Load & Validate Checkpoint
   - Present: Indicator count, temporal window, variance stats
   - Verify: All data integrity checks pass

2. ⏸️ After Step 2: Prefiltering Pipeline
   - Present: Reduction statistics (40.6M → 293K pairs)
   - Verify: Prefiltering stages worked as expected
   - Show: Sample of filtered pairs with reasoning

3. ⏸️ After Step 3: Parallel Granger Testing (LONG RUNNING)
   - Present: Progress updates every 50K tests
   - Show: Intermediate results (% significant)
   - Verify: Computational performance matches estimates

4. ⏸️ After Step 4: FDR Correction
   - Present: Before/after correction statistics
   - Show: Significance threshold and retention rate

5. ⏸️ After Step 5: Bootstrap Validation
   - Present: Final validated edge count
   - Verify: Success criteria met (20K-80K edges)
   - Show: Bootstrap stability distribution

**Review Format**:
```
=== STEP X COMPLETE - REVIEW REQUESTED ===

Summary:
- Input: [what was processed]
- Output: [what was produced]
- Statistics: [key metrics]
- Success Criteria: [pass/fail with details]

Next Step: [what comes next]
Estimated Time: [how long next step takes]

Ready to proceed? (yes/no)
```

**Auto-pause triggers** (even without explicit steps):
- ⚠️ Validation failure
- ⚠️ Time overrun (>1.5x expected)
- ⚠️ Memory warning (>90% RAM usage)
- ⚠️ Unexpected results (edge count outside 20K-80K range)
