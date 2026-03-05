# Non-Linear Detection Methodology for Phase 2B

**Research Date:** 2026-01-15
**Purpose:** Enhanced causal graph computation with comprehensive non-linearity detection

---

## Literature Review: Non-Linear Patterns in Development Economics

### 1. Logarithmic/Diminishing Returns

**Evidence:** [Education and Economic Growth](https://www.emerald.com/insight/content/doi/10.1108/aea-06-2019-0005/full/html) shows education-growth relationships exhibit diminishing returns. The [Solow model](https://opened.cuny.edu/courseware/lesson/520/overview) predicts capital investment has diminishing marginal returns.

**Pattern:** Effect decreases as source increases
**Examples:** Education → GDP, Investment → Growth, Aid → Development
**Model:** `y = a + b*log(x)`

### 2. Saturation/Ceiling Effects (Preston Curve)

**Evidence:** The [Preston Curve](https://en.wikipedia.org/wiki/Preston_curve) shows life expectancy and income have a concave relationship - flattens at high income levels. [Recent research](https://cepr.org/voxeu/columns/health-income-and-preston-curve) confirms this holds across centuries.

**Pattern:** Approaches asymptotic ceiling
**Examples:** Income → Life Expectancy, Literacy → near 100%, Internet Access → saturation
**Model:** `y = L / (1 + exp(-k*(x-x0)))` or `y = a - b*exp(-cx)`

### 3. Threshold Effects

**Evidence:** [Panel threshold regression](https://link.springer.com/chapter/10.1007/978-3-662-45402-2_179) shows GDP thresholds change insurance-development relationships. [Institutional research](https://www.democracy.uci.edu/files/docs/conferences/grad/boudreauwellerpaper.pdf) finds growth-institution relationships are discontinuous.

**Pattern:** Relationship regime-shifts at critical values
**Examples:** GDP → Financial Development, Institutions → Growth
**Model:** Piecewise: `y = a1 + b1*x if x < threshold, else a2 + b2*x`

### 4. Inverted-U (Kuznets Curve)

**Evidence:** The [Environmental Kuznets Curve](https://www.nature.com/articles/s41599-024-02736-9) shows emissions rise then fall with development. Similar patterns found for inequality.

**Pattern:** Increases then decreases past peak
**Examples:** Development → Emissions, Growth → Inequality (classic Kuznets)
**Model:** `y = a + bx - cx²` (c > 0)

### 5. U-Shaped

**Evidence:** [Technology-inequality research](https://www.kci.go.kr/kciportal/landing/article.kci?arti_id=ART003122480) finds innovation first reduces then increases inequality at high tech levels.

**Pattern:** Decreases then increases past trough
**Examples:** Technology → Inequality, Development stage transitions
**Model:** `y = a + bx + cx²` (c > 0, b < 0)

### 6. S-Curve (Logistic)

**Evidence:** [GPT diffusion research](https://www.generali.com/doc/jcr:e37b5f1d-6c9c-4978-94c4-6609efffd112/WP01_16.pdf/lang:en/WP01_16.pdf) shows technology adoption follows S-curves with emergence, inflection, and saturation phases.

**Pattern:** Slow start, rapid middle, saturation
**Examples:** Technology Adoption, Structural Transformation, Urbanization
**Model:** `y = L / (1 + exp(-k*(x-x0)))`

---

## Detection Methodology

### Model Comparison Framework

For each edge, fit 5 models and select best by AIC:

| Model | Formula | Parameters | Interpretation |
|-------|---------|------------|----------------|
| Linear | `y = a + bx` | 2 | Constant marginal effect |
| Logarithmic | `y = a + b*log(x)` | 2 | Diminishing returns |
| Quadratic | `y = a + bx + cx²` | 3 | U or inverted-U |
| Saturation | `y = L*(1 - exp(-kx))` | 2 | Ceiling effect |
| Threshold | Piecewise linear | 4 | Regime shift |

### Selection Criteria

1. **AIC (Akaike Information Criterion)**: Balance fit vs. complexity
   - `AIC = 2k - 2ln(L)` where k = parameters, L = likelihood
   - Lower is better

2. **Improvement Threshold**: Non-linear selected only if:
   - R² improvement > 5% over linear
   - AIC improvement > 2 (substantial evidence)

3. **Parameter Validity**:
   - Logarithmic: Only if x > 0 for all observations
   - Saturation: Only if estimated ceiling is realistic
   - Threshold: Only if threshold is within data range (10th-90th percentile)

### Edge Output Schema (Enhanced)

```json
{
  "source": "education_spending",
  "target": "gdp_growth",
  "beta": 0.35,
  "ci_lower": 0.28,
  "ci_upper": 0.42,
  "p_value": 0.0001,
  "lag": 3,
  "r_squared": 0.42,
  "n_samples": 35,

  "relationship_type": "logarithmic",
  "nonlinearity": {
    "type": "logarithmic",
    "r2_linear": 0.35,
    "r2_nonlinear": 0.42,
    "improvement": 0.07,
    "aic_linear": 125.3,
    "aic_nonlinear": 118.7,
    "parameters": {
      "a": 2.5,
      "b": 0.8
    },
    "interpretation": "diminishing_returns",
    "effect_at_low": 0.52,
    "effect_at_median": 0.35,
    "effect_at_high": 0.18
  },

  "saturation": {
    "has_saturation": true,
    "source_threshold": 15000,
    "source_current_pct": 0.72,
    "effect_reduction": 0.45
  }
}
```

### Indicator-Specific Priors

Based on literature, apply domain-specific priors:

| Domain | Expected Pattern | Indicators |
|--------|------------------|------------|
| Education → Growth | Logarithmic | School enrollment, literacy, years of schooling |
| Income → Health | Saturation (Preston) | Life expectancy, infant mortality |
| Development → Environment | Inverted-U (Kuznets) | CO2 emissions, deforestation |
| Tech Adoption | S-curve | Internet access, mobile phones |
| Governance | Threshold | Democracy → growth effects |
| Infrastructure | Saturation | Electricity access, roads |

---

## Implementation Plan

### Phase 1: Enhanced Detection (All Edges)
- Test all 5 models for every edge (not just top 500)
- Store full nonlinearity metadata
- Runtime estimate: ~3x current (includes more model fitting)

### Phase 2: Propagation Parameters
For simulation API, compute:
- Marginal effect at 25th, 50th, 75th percentiles
- Saturation thresholds where effect < 10% of peak
- Threshold breakpoints for piecewise relationships

### Phase 3: Validation
- Cross-validate non-linearity detection
- Verify patterns match literature (education-growth should be logarithmic)
- Check temporal stability (pattern shouldn't flip year-to-year)

---

## Computational Considerations

### Performance
- Current: ~8s per (country, year) case
- Enhanced: ~15-20s per case (5 model fits vs. 2)
- Total: 4,768 files × 20s = ~26 hours at 4 cores

### Parallelization
- Edge-level parallelization not efficient (too many small tasks)
- Case-level parallelization (current approach) remains optimal
- Can increase to 8 cores for 2x speedup (~13 hours)

### Memory
- No significant increase (model fitting is streaming)
- Peak memory ~4GB per worker

---

## References

1. Preston, S.H. (1975). "The changing relation between mortality and level of economic development"
2. Kuznets, S. (1955). "Economic Growth and Income Inequality"
3. Hanushek, E. & Woessmann, L. (2021). "Education and Economic Growth"
4. Dalgaard, C.J. & Strulik, H. (2013). "Optimal Aging and Death: Understanding the Preston Curve"
5. Prados de la Escosura, L. (2022). "Health, income, and the Preston curve: A long view"
