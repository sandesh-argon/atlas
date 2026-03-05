# A1 Critical Validation Results

**Date**: 2025-11-13
**Status**: 🚨 **3 CRITICAL ISSUES FOUND** - A2 prep required

---

## Summary of Findings

| Validation | Status | Critical Finding |
|------------|--------|------------------|
| **1. Temporal Alignment** | ❌ FAIL | Only 72.9% of pairs have ≥20 year overlap |
| **2. Zero Variance** | ❌ FAIL | 329 indicators (4.21%) near-zero variance + 7 constant |
| **3. Domain Coverage** | ⚠️ WARNING | 80.1% indicators in "Other" category (keyword matching too narrow) |

---

## Validation 1: Temporal Alignment ❌ FAIL

### Critical Finding
**Only 72.9% of indicator pairs have ≥20 years overlap** (target: ≥90%)

### Details
- **Mean overlap**: 43.1 years
- **Median overlap**: 27.0 years
- **≥20 years**: 72.9% of pairs ⚠️
- **≥30 years**: 41.6% of pairs
- **≥40 years**: 37.9% of pairs

### Root Cause
- 3,016 indicators start before 1960 (V-Dem historical data: 1789-2024)
- World Bank indicators typically start 1960-1990
- Effective overlap for many pairs: 1990-2024 (34 years) NOT full span

### Golden Temporal Windows
| Window | Indicators with ≥80% Coverage | % of Total |
|--------|------------------------------|-----------|
| 1990-2024 | 5,050 | 64.6% |
| 1995-2024 | 6,199 | 79.3% |
| 2000-2024 | 6,421 | 82.1% |

### Impact on A2
**Problem**: 27% of Granger tests will fail due to insufficient temporal overlap (<20 years)

**Estimated waste**:
- Total pairs: 61M (7,818²)
- After prefiltering: 1.8M tests (97% reduction)
- Failed due to <20 year overlap: ~486,000 tests (27% of 1.8M)
- Runtime waste: ~13.5 hours @ 0.1s per test

### Recommendation
✅ **APPLY GOLDEN WINDOW FILTER (1990-2024) IN A2 PREPROCESSING**

Benefits:
- Ensures all pairs have ≥20 year overlap
- Retains 5,050 indicators (64.6% of total, well above 4K-6K target)
- Reduces total pairs: 5,050² = 25.5M → 750K after prefiltering
- Saves ~13.5 hours by avoiding failed tests

Implementation:
```python
# In A2 preprocessing (before Granger tests)
GOLDEN_WINDOW = (1990, 2024)

for name, df in imputed_data.items():
    # Filter to golden window
    year_cols = [c for c in df.columns if 1990 <= int(c) <= 2024]
    imputed_data[name] = df[year_cols]
```

---

## Validation 2: Zero Variance ❌ FAIL

### Critical Finding
**329 indicators (4.21%) have near-zero variance** (target: <1%)
**7 indicators perfectly constant** (variance = 0.0)

### Constant Indicators (MUST REMOVE)
1. `NW.NCA.MTIN.PC` - All values = 0.000
2. `NW.NCA.MTIN.TO` - All values = 0.000
3. `v2ddadmpl` - All values = 0.000
4. `v3pechilabl` - All values = 0.000
5. `tdiincj999` - All values = 0.000
6. `tptincj999` - All values = 0.000
7. `tptincj992` - All values = 0.000

### Near-Zero Variance Examples
- Many WID (World Inequality Database) indicators: `ytiwnpi999`, `ytaxnpi999`
- World Bank capital formation indicators: `NW.NCA.MTIN.*`
- V-Dem administrative indicators: `v2ddadmpl`, `v3pechilabl`

### Variance Distribution
- **Mean variance**: 4.29e32 (highly skewed)
- **Median variance**: 81.6 (healthy)
- **1st percentile**: 0.0003 (problematic)
- **5th percentile**: 0.013

### Variance by Tier
| Tier | Mean Variance | % Near-Zero (<0.01) |
|------|--------------|---------------------|
| Observed | 2.08e32 | 3.83% |
| Interpolated | 8.02e32 | 4.84% |

**Interpretation**: Interpolation actually INCREASES low-variance proportion (4.84% vs 3.83%)

### Root Cause
**KNN parameter (k=5) too aggressive for sparse indicators**
- When indicator has mostly missing data, KNN finds 5 most similar countries
- If all 5 neighbors are similar developing countries → imputed values converge to mean
- Result: Low variance after imputation

### Impact on A2
**Problem**: Granger causality requires variance to detect temporal precedence

**Technical issue**:
```python
# Granger test computes F-statistic
F = (RSS_restricted - RSS_unrestricted) / (k * RSS_unrestricted / (n - k))
```

If variance ≈ 0 → RSS ≈ 0 → division by near-zero → numerical instability or error

### Recommendation
✅ **REMOVE 336 flagged indicators (329 near-zero + 7 constant) before A2**

Benefits:
- Prevents division-by-zero errors
- Avoids numerical instability in Granger tests
- Loss: 4.3% of indicators (acceptable)
- Updated count: 7,818 → 7,482 indicators (still well above 4K-6K target)

Alternative (NOT RECOMMENDED):
- Re-run Step 3 with k=3 (fewer neighbors, more variance)
- Risk: May not fully resolve issue, adds 8 hours runtime

Implementation:
```python
# In A2 preprocessing
VARIANCE_THRESHOLD = 0.01

for name, df in imputed_data.items():
    variance = df.values.flatten().var()
    if variance < VARIANCE_THRESHOLD:
        del imputed_data[name]
```

---

## Validation 3: Domain Coverage ⚠️ WARNING

### Finding
**80.1% of indicators classified as "Other"** (19,893 out of 24,823 total)

### Current Domain Distribution (Step 1 Keyword Classification)
| Domain | Count | % of Total |
|--------|-------|------------|
| Other | 19,893 | 80.1% |
| Democracy | 2,222 | 9.0% |
| Inequality | 2,175 | 8.8% |
| **Economic** | **226** | **0.9%** ❌ |
| Infrastructure | 125 | 0.5% |
| **Education** | **60** | **0.2%** ❌ |
| **Health** | **56** | **0.2%** ❌ |
| Environment | 38 | 0.2% |
| Gender | 12 | 0.0% |
| Corruption | 7 | 0.0% |
| Governance | 5 | 0.0% |
| Social | 4 | 0.0% |

### Root Cause
**Keyword matching too narrow** for complex indicator names

Examples of mislabeled "Other" indicators:
- World Bank GDP/trade indicators with long technical names
- OECD infrastructure indicators with codes
- Penn World Tables economic indicators with abbreviations

### Why This Matters for A2
**A2 prefiltering uses domain compatibility matrix** (13×13 plausibility map)

Example:
- "Economic → Health" connection: PLAUSIBLE (GDP affects health spending)
- "Other → Health" connection: UNKNOWN (can't assess plausibility)

If 80% of indicators are "Other", domain-based prefiltering loses effectiveness.

### Impact Assessment
**Current A2 Plan**:
1. Correlation filter: 97% reduction (61M → 1.8M pairs)
2. **Domain filter**: Further reduction (1.8M → estimated 500K pairs)
3. Literature plausibility: Final reduction (500K → 200K pairs)

**With 80% "Other"**:
- Step 2 domain filter can't distinguish plausible vs implausible connections
- May retain too many implausible pairs → longer A2 runtime
- OR may reject valid pairs → miss causal relationships

### Recommendation
✅ **OPTION A: Proceed with current classification, re-classify in Phase B3**

Rationale:
- Domain classification is NOT critical for A2 Granger tests (temporal precedence is domain-agnostic)
- Domain filter is OPTIONAL prefiltering heuristic (not required)
- Phase B3 already plans semantic clustering for final domain assignment
- Re-classifying now adds 2-3 hours with minimal A2 benefit

Modified A2 Plan:
1. Correlation filter: 97% reduction (61M → 1.8M pairs)
2. **Skip domain filter** (too many "Other" for effectiveness)
3. Literature plausibility: Aggressive reduction (1.8M → 300K pairs)
4. Temporal precedence: Further reduction (300K → 200K pairs)

Alternative (**NOT RECOMMENDED**):
- **OPTION B**: Re-classify "Other" NOW using semantic embeddings (sentence-transformers)
- Runtime: +2-3 hours
- Benefit: Marginal (domain filter is optional)

---

## Combined Impact on A2 Timeline

### Original A2 Estimate
- Indicators: 7,818
- Candidate pairs: 61M
- After prefiltering: 200K tests
- Runtime: 5-6 days

### After Validation Fixes
**Applying golden window (1990-2024) + removing zero-variance**:
- Indicators: 5,050 (golden window) - 336 (zero-var) = **4,714 indicators**
- Candidate pairs: 4,714² = 22.2M
- After prefiltering (97%): 660K tests
- Runtime estimate: **7-8 days** (within 14-25 day V2 budget)

### Computational Reality Check
Your concern about 18M tests was valid. Here's the corrected math:

**BEFORE golden window**:
- 7,818² = 61M pairs
- 97% prefilter reduction → 1.8M tests
- With 5 lags × 2 directions = 18M Granger operations
- @ 0.1s each = **21 days** ❌

**AFTER golden window + variance filter**:
- 4,714² = 22.2M pairs
- 97% prefilter reduction → 660K tests
- With 5 lags × 2 directions = 6.6M Granger operations
- @ 0.1s each = **7.6 days** ✅

---

## Final Recommendation: OPTION A (PROCEED WITH FIXES)

### Required Preprocessing for A2

**Step 1**: Apply golden temporal window (1990-2024)
- Filters indicators to modern era
- Ensures ≥20 year overlap for all pairs
- Retains 5,050 indicators (64.6%)

**Step 2**: Remove zero-variance indicators
- Remove 7 constant indicators
- Remove 329 near-zero variance indicators (<0.01)
- Updated count: 4,714 indicators

**Step 3**: Skip domain compatibility filter
- 80% "Other" makes it ineffective
- Rely on correlation + literature plausibility instead

### Expected A2 Results
- **Timeline**: 7-8 days (within 14-25 day V2 budget)
- **Tests**: ~660K pairs (manageable)
- **Output**: 20K-60K validated edges (adjusted for smaller indicator set)
- **Quality**: High (only high-overlap, high-variance indicators retained)

### Benefits of This Approach
1. **Avoids failed tests**: Golden window ensures sufficient overlap
2. **Prevents errors**: Zero-variance removal avoids numerical issues
3. **Stays on budget**: 7-8 days vs original 5-6 day estimate (acceptable)
4. **Maintains quality**: Still above 4K-6K target range

### Alternative: OPTION C (TWO-STAGE A2)
If you prefer to maximize indicator coverage:

**Stage 1**: Run A2 on 4,714 "core" indicators (golden window + variance filter)
- Timeline: 7-8 days
- Output: High-quality core causal network

**Stage 2**: Run A2 on remaining 3,104 "extended" indicators (historical + edge cases)
- Timeline: Additional 5-7 days (if time permits)
- Output: Extended network with lower-confidence edges

**Benefit**: Guaranteed high-quality core results, optional extended coverage

---

## Action Items

- [ ] Create A2 preprocessing script with golden window filter
- [ ] Create zero-variance removal script for A2 input
- [ ] Update A2 prefiltering to skip domain compatibility (or make it optional)
- [ ] Update A1_MISSINGNESS_REPORT.md with validation findings
- [ ] Update optimal config metadata with revised indicator count (4,714)
- [ ] Update A2 timeline estimate (7-8 days)

---

**Validation Complete**: 2025-11-13
**Decision**: OPTION A - Apply golden window + variance filter, proceed to A2 with 4,714 indicators
**Estimated A2 Runtime**: 7-8 days (within acceptable range)
