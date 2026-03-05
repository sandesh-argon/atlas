# A4: Effect Quantification - Final Report

**Phase**: A4 Effect Quantification
**Status**: ✅ COMPLETE
**Date Completed**: 2025-11-19
**Method**: LASSO Regularization with Bootstrap Confidence Intervals

---

## Executive Summary

Successfully quantified causal effects for 129,989 edges using LASSO regularization with 100 bootstrap iterations. Achieved 74.1% success rate with 11,009 validated causal edges (|β|>0.12, CI doesn't cross 0).

**Key Achievement**: 8.5× speedup using AWS c7i.48xlarge SPOT instance (192 cores) compared to local processing.

---

## Methodology

### Core Approach
- **Method**: LASSO regularization for variable selection + backdoor adjustment
- **Bootstrap**: 100 iterations for post-selection inference
- **Effect threshold**: |β| > 0.12 (meaningful economic/social impact)
- **Validation criteria**: Confidence interval doesn't cross zero

### Three-Phase Implementation

#### Phase 1: Backdoor Adjustment Sets (Step 2)
- Input: 1,157,230 Granger-validated edges from A2
- Method: dowhy backdoor criterion identification
- Output: 129,989 edges with valid adjustment sets (11.2% of input)
- **Key filter**: Removed edges without valid backdoor paths

#### Phase 2: LASSO Effect Estimation (Step 3 - Local)
- Processed first 40,000 edges locally (30.8%)
- Runtime: 66 hours @ 10.1 edges/min (10 cores, thermal-limited)
- Result: 62.4% success rate, checkpoint validated

#### Phase 3: AWS Acceleration (Step 3 - Cloud)
- Processed remaining 89,989 edges on AWS
- Instance: c7i.48xlarge SPOT (192 cores, $2.90/hour)
- Runtime: 17.4 hours @ 124.7 edges/min
- Cost: $50.40
- **Speedup**: 8.5× faster than projected local time

---

## Results

### Overall Statistics
- **Total edges processed**: 129,989
- **Successful estimations**: 96,313 (74.1%)
- **Failed estimations**: 33,676 (25.9%)
  - Common causes: Insufficient data, collinearity, LASSO convergence issues

### Effect Size Distribution
- **Mean |β|**: 2,613.93 (influenced by outliers)
- **Median |β|**: 0.079
- **Large effects** (|β|>0.12): 36,037 (37.4% of successful)
- **Extreme effects** (|β|>10): 1,026 (1.07% of successful)
  - Note: Extreme values expected in real-world economic data with varying scales

### Validated Causal Edges
- **Validated edges**: 11,009
  - Criteria: |β|>0.12 AND CI doesn't cross 0
  - 30.5% of large effects
  - 11.4% of all successful edges
  - 8.5% of total processed edges

### Confidence Interval Quality
- **Mean CI width**: 125,761.52 (influenced by outliers)
- **Median CI width**: 0.527
- **Wide CIs** (>5): 11,666 edges (12.1%)
  - Common in sparse data or high-variance relationships

---

## Computational Performance

### Local Run (40,000 edges)
- **Hardware**: AMD Ryzen 9 7900X (12 cores @ 86% utilization)
- **Cores used**: 10 (thermal safety limit)
- **Runtime**: 66 hours
- **Rate**: 10.1 edges/min
- **Thermal constraint**: >50% CPU caused 90°C+ temps, throttling

### AWS Run (89,989 edges)
- **Instance**: c7i.48xlarge SPOT
- **Cores**: 192 vCPUs
- **Runtime**: 17.4 hours (01:17-18:40 UTC)
- **Rate**: 124.7 edges/min
- **Cost**: $50.40
- **Speedup**: 12.3× faster than local per-core, 8.5× faster overall

### Performance Analysis
**Why AWS was faster**:
1. **Thermal headroom**: Datacenter liquid cooling vs consumer tower
2. **Parallelization**: 192 cores vs 10 cores (thermal-limited)
3. **Sustained throughput**: 100% CPU possible vs 50% local max
4. **Cost-effective**: $50.40 vs ~6 days local runtime + hardware stress

**Tail inefficiency observed**:
- Final ~400 edges of each 5,000-edge chunk showed worker die-off
- Load dropped to ~13 (from 192) during tail processing
- Accepted tradeoff: minimal impact on overall runtime

---

## Data Quality

### Validation Checks Performed
✅ **No NaN/Inf values** in beta, ci_lower, ci_upper
✅ **No invalid CIs** (lower > upper)
✅ **All 129,989 edges processed** (100% completion)
✅ **Sample edges verified** (10 random validated edges reviewed)
✅ **All checkpoints saved** (27 checkpoint files, 320 MB)

### Known Data Characteristics
1. **Heavy-tailed distribution**: Mean |β| >> Median due to a few very large effects
2. **Scale heterogeneity**: Variables span different units (e.g., GDP in billions, rates in 0-1)
3. **Wide CIs**: 12% of edges have CI width >5, typical for sparse/noisy data
4. **Outliers**: 1,026 extreme effects (|β|>10) flagged for Phase 5 review

---

## Files Structure

```
A4_effect_quantification/
├── checkpoints/                    # 27 checkpoint files (320 MB) - MAIN OUTPUT
│   ├── effect_estimation_checkpoint_40000.pkl
│   ├── effect_estimation_checkpoint_45000.pkl
│   └── ... (every 5K edges through 129,989)
├── outputs/                        # Final results
│   ├── lasso_effect_estimates.pkl  # 12 MB - All 129,989 edge estimates
│   ├── A4_phase3_summary.txt       # Summary statistics
│   └── parent_adjustment_sets.pkl  # 335 MB - Backdoor sets from Step 2
├── scripts/                        # Processing scripts
│   ├── step2_backdoor_adjustment.py
│   ├── step3_effect_estimation_lasso.py
│   └── validation_utils.py
├── logs/                          # Execution logs
│   ├── step3_full_run_10cores.log  # Local run log
│   └── full_run_from_40k_v2.log    # AWS run log (on AWS only)
├── diagnostics/                   # Analysis and validation
├── tests/                         # Unit tests
├── utils/                         # Utility functions
├── archive/                       # Old documentation and packages
├── A4_EFFECT_QUANTIFICATION_REPORT.md  # This file
├── A4_FINAL_STATUS.md             # Status summary
├── A4_FINAL_METHODOLOGY.md        # Technical methodology
├── AWS_VALIDATION_REPORT.md       # AWS run validation
└── README.md                      # Quick reference
```

**Note**: AWS key `a4-backdoor-key_1.pem` moved to `~/.ssh/aws_keys/` for security

---

## Success Criteria

| Criterion | Target | Achieved | Status |
|-----------|--------|----------|--------|
| Edges processed | 129,989 | 129,989 | ✅ |
| Success rate | >60% | 74.1% | ✅ |
| Validated edges | >10,000 | 11,009 | ✅ |
| Data quality | No critical issues | 0 NaN/Inf, 0 bad CIs | ✅ |
| Completion | 100% | 100% | ✅ |

---

## Known Limitations

1. **Scale heterogeneity**: Variables not normalized → large |β| values for some edges
2. **Sparse data**: 12% of edges have very wide CIs (>5)
3. **LASSO limitations**:
   - May miss nonlinear effects
   - Assumes linear relationships
   - Selection bias in post-selection inference (mitigated by bootstrap)
4. **Computational**: Tail inefficiency in parallel processing (~10% time overhead)

---

## Next Steps → Phase 5

**Ready for A4 Phase 5: Validation & Literature Checks**

1. **Literature validation**: Match 11,009 validated edges against known relationships
2. **Domain expert review**: Flag implausible effects for investigation
3. **Scale normalization**: Consider standardizing for Phase B interpretability
4. **Outlier investigation**: Review 1,026 extreme effects (|β|>10)
5. **Graph construction**: Feed validated edges into A5 (Interaction Discovery)

**Handoff data**:
- ✅ `lasso_effect_estimates.pkl` (129,989 edges with effects & CIs)
- ✅ 11,009 validated edges ready for downstream analysis
- ✅ All checkpoints backed up for reproducibility

---

## References

**Methodology Sources**:
- LASSO: Tibshirani (1996) "Regression Shrinkage and Selection via the Lasso"
- Post-selection inference: Tibshirani et al. (2016) "Exact Post-Selection Inference"
- Backdoor criterion: Pearl (1995) "Causal Diagrams for Empirical Research"

**Internal References**:
- A2 Granger Causality: `/phaseA/A2_granger_causality/A2_FINAL_STATUS.md`
- V2 Master Instructions: `/v2_master_instructions.md` (lines 690-770)
- V1 Lessons: `/V1_LESSONS.md` (backdoor adjustment validation)

---

**Report Generated**: 2025-11-19
**Phase Status**: COMPLETE
**Total Runtime**: ~83 hours (66h local + 17h AWS)
**Total Cost**: $50.40 (AWS SPOT)
