# Simulation API Documentation

## Architecture Overview

The simulation system follows a layered architecture that separates concerns across four tiers:

```
Frontend (React/TypeScript)
    |
    |  HTTP POST (JSON)
    v
API Router (FastAPI)                   /api/simulate/v31, /api/simulate/v31/temporal
    |
    |  Delegates to service layer
    v
Simulation Service                     Lazy-loads V3.1 modules, translates request fields
    |
    |  Calls V3.1 runner functions
    v
V3.1 Simulation Runner                Loads year-specific graph, builds adjacency, resolves baselines
    |
    |  Invokes propagation engine
    v
Propagation Engine                     Iterative multi-hop propagation with unit conversion, saturation, and clamping
```

**Key files:**

| Layer | File |
|-------|------|
| Router | `api/routers/simulation.py` |
| Models | `api/models/requests.py`, `api/models/responses.py` |
| Service | `api/services/simulation_service.py` |
| Runner | `simulation/simulation_runner_v31.py`, `simulation/temporal_simulation_v31.py` |
| Propagation | `simulation/propagation_v31.py` |
| Saturation | `simulation/saturation_functions.py` |
| Indicator Stats | `simulation/indicator_stats.py` |
| Region Mapping | `simulation/region_mapping.py`, `simulation/regional_spillovers.py` |

---

## Regional Integration (2026-03-01)

- `view_type` now supports `regional` in both instant and temporal endpoints.
- Request validation contract:
  - `view_type=country|stratified`: `country` required
  - `view_type=regional`: `region` or `country` required (`country` derives `region`)
  - `view_type=unified`: `country` optional
- Regional view is gated by `ENABLE_REGIONAL_VIEW` (default `false`).
- Adaptive-year behavior: if requested year is unavailable for a scope, nearest available year in that scope is used and returned via warnings.

### Precompute Commands

Run before enabling `regional` in production:

```bash
python -m simulation.precompute_regional_graphs
python -m simulation.precompute_regional_baselines
python -m simulation.precompute_regional_shap
```

Coverage reports are written under `data/v31/metadata/` as:
- `regional_graph_coverage.json`
- `regional_baseline_coverage.json`
- `regional_shap_coverage.json`

---

## Data Flow

An intervention like "increase `rconna` by 20% in Australia, 2020" follows this path:

### 1. Frontend submits request

```json
{
  "country": "Australia",
  "interventions": [{"indicator": "rconna", "change_percent": 20}],
  "year": 2020,
  "mode": "percentage"
}
```

### 2. Router validates and dispatches

The FastAPI router (`/api/simulate/v31`) validates the request against `SimulationRequestV31`, converts `InterventionInput` objects into plain dicts, and calls `simulation_service.run_instant_simulation_v31()` inside an `asyncio.wait_for` timeout wrapper.

### 3. Service delegates to V3.1 runner

The `SimulationService` lazy-loads the V3.1 simulation module and passes all parameters through. For temporal simulations, per-intervention `year` fields are renamed to `intervention_year` for the backend.

### 4. Runner loads graph and baseline

The V3.1 runner:
- Loads the pre-computed temporal causal graph for the requested country and year
- Filters edges by p-value threshold (default 0.05)
- Builds an adjacency dict: `{source_indicator: [{target, beta, std, ...}, ...]}`
- Resolves baseline indicator values for the country/year (absolute mode only)

### 5. Propagation engine computes effects

Two simulation modes exist:

**Percentage mode (fast path):** Works entirely in percentage space. No baseline loading required. A 20% change in the source propagates as `20% * beta` to each target. Since betas are standardized coefficients bounded roughly by [-1, 1], cascading naturally attenuates.

**Absolute mode (full path):** Converts between raw units and standardized units using within-country temporal standard deviations:

```
standardized_delta = raw_delta / source_std
raw_effect = beta * standardized_delta * target_std
```

Or equivalently:

```
raw_effect = beta * (source_delta / source_temporal_std) * target_temporal_std
```

The engine iterates through the graph, accumulating effects until convergence or max iterations.

### 6. Response returned

Effects are ranked by magnitude, and the top N (default 20) are returned alongside propagation metadata, spillover effects, and optional ensemble confidence intervals.

---

## Key Concepts

### Within-Country Temporal Standardization

Betas are estimated from **within-country temporal variation**, not cross-country variation. Each country's time series is independently z-scored before regression:

```
X_std = (X - X_country_mean) / X_country_temporal_std
y_std = (y - y_country_mean) / y_country_temporal_std
beta = Ridge(X_std, y_std).coef_
```

This is critical for unit conversion during propagation. The same temporal std used during estimation must be used to convert effects back to raw units. Using cross-country std would amplify effects by orders of magnitude (e.g., wealth indicators: cross-country std = 209M vs. India temporal std = 48K).

### Beta Estimation

Betas are **standardized regression coefficients** estimated via Ridge regression on z-scored within-country time series. They represent the expected change in the target (in target standard deviations) per one standard deviation change in the source. Their values are bounded roughly by [-1, 1] due to standardization, which provides natural attenuation during multi-hop propagation.

Each edge also stores:
- `std`: Standard error of the beta estimate (used for ensemble resampling)
- `p_value`: Statistical significance (edges filtered at default threshold 0.05)
- `marginal_effects`: Non-linear effects at p25, p50, p75 percentiles (when detected)

### Lag Structure

Causal edges can have temporal lags, meaning a change in the source indicator at year *t* affects the target at year *t + lag*. Lags are estimated during graph construction and stored per-edge. In temporal simulations, this spreads effects across time rather than concentrating them in a single step.

### Multi-Hop Propagation

Effects cascade through the graph iteratively. In each iteration:

1. For every node that changed in the previous iteration, find all outgoing edges
2. Compute the propagated effect for each target using the beta coefficient
3. Accumulate effects across all incoming edges for each target
4. Apply saturation bounds and the +-2 sigma cumulative clamp
5. Track which nodes changed significantly (above convergence threshold)
6. Repeat with the newly changed nodes as the next wavefront

This continues until either no nodes change significantly or `max_iterations` is reached.

### Convergence

Propagation stops when one of two conditions is met:
- **Convergence threshold:** The maximum absolute change across all indicators in an iteration falls below the threshold (default 0.001 for absolute mode, 1e-6 for percentage mode)
- **Max iterations:** The iteration count reaches the limit (default 10 for absolute mode, 100 for percentage mode)

The response includes both `iterations` (how many were performed) and `converged` (whether the threshold condition was met).

---

## Natural Attenuation

A common concern with iterative graph propagation is runaway effects. Four mechanisms prevent this:

### 1. Beta Decay

Standardized betas are typically |beta| < 0.5. At each hop, the effect is multiplied by the next beta, causing exponential decay:

```
Hop 1:  effect = delta * beta_1           (e.g., 20% * 0.4 = 8%)
Hop 2:  effect = delta * beta_1 * beta_2  (e.g., 8% * 0.3 = 2.4%)
Hop 3:  effect = delta * beta_1 * beta_2 * beta_3  (e.g., 2.4% * 0.2 = 0.48%)
```

After 3-4 hops, effects are typically negligible.

### 2. Lag Structure

In temporal simulations, lagged edges spread effects across multiple years rather than concentrating them. A 2-year lag means the effect arrives two projection steps later, preventing instantaneous amplification.

### 3. Cumulative Clamp (+-2 sigma)

No indicator can move more than 2 standard deviations from its baseline value. This is enforced as a cumulative clamp on the total delta:

```python
max_delta = 2.0 * target_temporal_std
proposed_delta = np.clip(proposed_delta, -max_delta, max_delta)
```

This prevents unrealistic shifts regardless of graph topology.

### 4. Convergence Threshold

When the maximum update across all indicators drops below the threshold, iteration stops. Combined with beta decay, this typically occurs within 3-5 iterations.

---

## Saturation

Saturation functions enforce domain-specific bounds on indicator values to prevent physically impossible results (e.g., enrollment rate > 100%, V-Dem index > 1.0).

### Matching Strategy

Indicators are matched to saturation rules using **conservative prefix/suffix matching** -- not broad substring matching. This prevents false positives where unrelated indicators accidentally trigger bounds.

- **Prefix match:** Most patterns (e.g., `SE.PRM.ENRR` matches enrollment rates starting with that WDI code)
- **Suffix match:** V-Dem response types (e.g., `_ord`, `_mean`, `_osp` match ordinal, posterior mean, and original-scale posterior suffixes)

### Saturation Rules

| Category | Patterns | Bounds | Examples |
|----------|----------|--------|----------|
| Percentage rates | `SE.PRM.ENRR`, `SE.SEC.ENRR`, `SE.TER.ENRR`, `SE.PRM.CMPT`, `SE.SEC.CMPT`, `SH.DYN.MORT`, `SH.DYN.NMRT`, `SP.DYN.CDRT`, `SP.DYN.TFRT`, `SH.STA.MMRT`, `SH.H2O.*`, `SH.STA.HYGN`, `SH.STA.BASS` | [0, 100] | Enrollment rates, mortality rates, WASH coverage |
| Life expectancy | `SP.DYN.LE00` | [25, 95] | Life expectancy at birth |
| V-Dem aggregate indices | `v2x_polyarchy`, `v2x_libdem`, `v2x_partipdem`, `v2x_delibdem`, `v2x_egaldem`, `v2x_liberal`, `v2x_cspart`, `v2x_rule`, `v2x_freexp`, `v2x_frassoc`, `v2x_suffr`, `v2x_elecoff`, `v2xel_frefair`, `v2xed_ed_`, `v2xpe_exl`, `v2xcl_rol`, `e_v2x_` | [0, 1] | Electoral democracy, liberal democracy |
| V-Dem ordinal/mean/osp | `_ord`, `_mean`, `_osp` (suffix) | [0, 4] | Expert survey ordinal responses |
| V-Dem latent variables | `v2el`, `v2pe`, `v2cs`, `v2me`, `v2ju`, `v2lg`, `v2cl`, `v2ex`, `v2ca`, `v2dl`, `v2dd`, `v2ed`, `v2ps`, `v2sm`, `v2st`, `v2sv`, `v2reg` | [-4, 4] | Bayesian IRT latent trait estimates |
| Polity scores | `e_polity` | [-10, 10] | Polity IV composite scores |

### Indicators Without Explicit Bounds

Indicators that don't match any saturation pattern (e.g., GDP per capita, population) receive **no domain-specific saturation**. Instead, the +-2 sigma cumulative clamp in the propagation engine prevents unrealistic shifts. This is intentional -- applying arbitrary bounds to unbounded indicators (like GDP) would be worse than the statistical clamp.

### The Saturation Misfire Bug

An earlier version used **broad substring matching** for saturation patterns. This caused false positives where indicators like `v2excrptps` (executive corruption) matched the `cr` or `rate` substring patterns and were incorrectly clamped to [0, 100]. The fix was switching to conservative prefix/suffix matching, where only indicators with known natural bounds are saturated.

---

## API Contract

### POST /api/simulate/v31

Run an instant simulation for a single country and year.

#### Request Schema

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `country` | string or null | `null` | Required for `country|stratified`; optional for `unified`; optional fallback for `regional` |
| `region` | string or null | `null` | Region key for `regional` view (e.g., `sub_saharan_africa`) |
| `interventions` | array | *required* | 1-20 interventions (see below) |
| `year` | integer | *required* | Graph and baseline year (1990-2024) |
| `mode` | string | `"percentage"` | `"percentage"` (fast) or `"absolute"` (includes real values) |
| `view_type` | string | `"country"` | `"country"`, `"stratified"`, `"unified"`, or `"regional"` |
| `p_value_threshold` | float | `0.05` | Edge significance filter (0.001-0.10) |
| `use_nonlinear` | boolean | `true` | Use non-linear marginal effects when available |
| `n_ensemble_runs` | integer | `0` | Bootstrap ensemble runs (0 = point estimate, 100 recommended for CIs, max 500) |
| `include_spillovers` | boolean | `true` | Include regional spillover effects |
| `top_n_effects` | integer | `20` | Number of top effects to return (1-500) |
| `debug` | boolean | `false` | Include debug metadata in response |

**Intervention object:**

| Field | Type | Description |
|-------|------|-------------|
| `indicator` | string | Indicator ID (e.g., `"v2elvotbuy"`) |
| `change_percent` | float | Percent change to apply (-100 to +1000) |
| `year` | integer or null | Year for this intervention (1990-2024), or null to use request-level year |

#### Example: Percentage Mode (Fast)

```bash
curl -X POST http://localhost:8000/api/simulate/v31 \
  -H "Content-Type: application/json" \
  -d '{
    "country": "Australia",
    "interventions": [
      {"indicator": "v2pehealth", "change_percent": 20}
    ],
    "year": 2020,
    "mode": "percentage"
  }'
```

#### Example: Absolute Mode with Ensemble

```bash
curl -X POST http://localhost:8000/api/simulate/v31 \
  -H "Content-Type: application/json" \
  -d '{
    "country": "India",
    "interventions": [
      {"indicator": "SE.PRM.ENRR", "change_percent": 10},
      {"indicator": "v2x_polyarchy", "change_percent": 15}
    ],
    "year": 2020,
    "mode": "absolute",
    "view_type": "country",
    "n_ensemble_runs": 100,
    "p_value_threshold": 0.05,
    "top_n_effects": 30
  }'
```

#### Response Schema

```json
{
  "status": "success",
  "mode": "percentage",
  "country": "Australia",
  "base_year": 2020,
  "view_type": "country",
  "view_used": "country",
  "scope_used": "country",
  "region_used": "east_asia_pacific",
  "income_classification": {
    "group_4tier": "High",
    "group_3tier": "Advanced",
    "gni_per_capita": 54910.0
  },
  "interventions": [
    {"indicator": "v2pehealth", "change_percent": 20}
  ],
  "effects": {
    "total_affected": 47,
    "top_effects": {
      "v2pehealth": {"percent_change": 20.0},
      "v2x_polyarchy": {"percent_change": 3.2},
      "...": "..."
    }
  },
  "propagation": {
    "iterations": 4,
    "converged": true
  },
  "spillovers": {
    "regional": {"...": "..."},
    "global": {"...": "..."},
    "region_info": {
      "region_key": "east_asia_pacific",
      "name": "East Asia & Pacific",
      "spillover_strength": 0.15
    },
    "is_global_power": false
  },
  "ensemble": null,
  "warnings": [
    "Requested year 1990 unavailable for 'country', used nearest year 1999"
  ],
  "metadata": {
    "n_edges": 312,
    "p_value_threshold": 0.05,
    "use_nonlinear": true
  }
}
```

In **absolute mode**, each effect includes additional fields:

```json
{
  "baseline": 0.85,
  "simulated": 0.88,
  "absolute_change": 0.03,
  "percent_change": 3.5,
  "ci_lower": 0.82,
  "ci_upper": 0.91,
  "std": 0.02
}
```

The `ci_lower`, `ci_upper`, and `std` fields are only populated when `n_ensemble_runs > 0`.

#### Timeout

Default 30 seconds. Extended automatically for ensemble runs (up to 120s).

---

### POST /api/simulate/v31/temporal

Run a temporal simulation that projects interventions forward year-by-year, optionally using a different causal graph for each projection year.

#### Request Schema

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `country` | string or null | `null` | Required for `country|stratified`; optional for `unified`; optional fallback for `regional` |
| `region` | string or null | `null` | Region key for `regional` view |
| `interventions` | array | *required* | 1-20 interventions |
| `base_year` | integer | *required* | Starting year (1990-2024) |
| `horizon_years` | integer | `10` | Years to project forward (1-40) |
| `view_type` | string | `"country"` | `"country"`, `"stratified"`, `"unified"`, or `"regional"` |
| `p_value_threshold` | float | `0.05` | Edge significance filter |
| `use_nonlinear` | boolean | `true` | Use marginal effects |
| `use_dynamic_graphs` | boolean | `true` | Load year-specific graph per projection year (V3.1 feature). If false, uses base_year graph for all years (V3.0 behavior). |
| `n_ensemble_runs` | integer | `0` | Bootstrap ensemble runs |
| `include_spillovers` | boolean | `true` | Spillover effects for final year |
| `top_n_effects` | integer | `20` | Top effects per year |
| `debug` | boolean | `false` | Include debug trace in response |

#### Example: Temporal Simulation with Staggered Interventions

```bash
curl -X POST http://localhost:8000/api/simulate/v31/temporal \
  -H "Content-Type: application/json" \
  -d '{
    "country": "Brazil",
    "interventions": [
      {"indicator": "SE.PRM.ENRR", "change_percent": 15, "year": 2015},
      {"indicator": "v2x_polyarchy", "change_percent": 10, "year": 2018}
    ],
    "base_year": 2010,
    "horizon_years": 15,
    "use_dynamic_graphs": true,
    "view_type": "country"
  }'
```

#### Response Schema

```json
{
  "status": "success",
  "country": "Brazil",
  "base_year": 2010,
  "horizon_years": 15,
  "view_type": "country",
  "scope_used": "country",
  "region_used": null,
  "income_classification_evolution": {
    "2010": {"group_3tier": "Emerging", "gni_per_capita": 9800},
    "2015": {"group_3tier": "Emerging", "gni_per_capita": 8600},
    "2020": {"group_3tier": "Emerging", "gni_per_capita": 7850}
  },
  "interventions": [
    {"indicator": "SE.PRM.ENRR", "change_percent": 15, "year": 2015},
    {"indicator": "v2x_polyarchy", "change_percent": 10, "year": 2018}
  ],
  "timeline": {
    "2010": {"SE.PRM.ENRR": 94.2, "v2x_polyarchy": 0.78, "...": "..."},
    "2011": {"SE.PRM.ENRR": 94.2, "v2x_polyarchy": 0.78, "...": "..."},
    "2015": {"SE.PRM.ENRR": 100.0, "v2x_polyarchy": 0.79, "...": "..."},
    "...": "..."
  },
  "effects": {
    "2015": {
      "SE.PRM.ENRR": {"percent_change": 15.0},
      "...": "..."
    },
    "2018": {
      "v2x_polyarchy": {"percent_change": 10.0},
      "...": "..."
    }
  },
  "affected_per_year": {
    "2010": 0,
    "2015": 34,
    "2018": 52,
    "2025": 58
  },
  "graphs_used": {
    "2010": "country",
    "2011": "country",
    "2015": "country",
    "...": "..."
  },
  "spillovers": null,
  "metadata": {
    "total_propagation_iterations": 42,
    "convergence_per_year": {"2015": true, "2016": true, "...": "..."}
  }
}
```

#### Timeout

Default 60 seconds. Extended for large horizons (>15 years: +30s) and ensemble runs (up to 180s).

---

## Graph Statistics

- **Country temporal graphs:** 178 countries across 26 years (1999-2024)
- **Aggregate temporal graphs:** unified + stratified across 35 years (1990-2024)
- **Regional temporal graphs:** generated via `precompute_regional_graphs.py` (11 regions x available years)
- **Edge counts** vary significantly by country and year, typically 100-500 edges per graph after p-value filtering at 0.05
- **Betas** are standardized regression coefficients estimated via Ridge regression on within-country z-scored time series; typically |beta| < 0.5
- **P-value filtering** defaults to 0.05 and can be adjusted per request (range 0.001-0.10); lower thresholds yield sparser, more statistically robust graphs
- **View fallback:** If a graph is unavailable, fallback is by scope:
  - country -> stratified -> unified
  - regional -> unified
- **Adaptive years:** if requested year is missing in a scope, nearest available year in that scope is used with a warning in the response.

---

## Error Handling

| HTTP Status | Error | Cause |
|-------------|-------|-------|
| 400 | Validation error | Invalid request fields (bad country, year out of range, empty interventions) |
| 400 | Simulation error | V3.1 runner returned status "error" (missing graph data, unknown indicator) |
| 504 | Timeout | Simulation exceeded time limit (reduce ensemble runs or horizon) |
| 500 | Internal error | Unexpected failure in propagation engine |

Timeout responses include a `suggestion` field with recommended parameter adjustments.

---

## Frontend Visualization

### Radial Hierarchy

The visualization renders indicators as a radial tree with 6 concentric rings:

| Ring | Label | Description |
|------|-------|-------------|
| 0 | Quality of Life | Root node (single) |
| 1 | Outcomes | Top-level outcome categories |
| 2 | Coarse Domains | Broad thematic groupings |
| 3 | Fine Domains | Narrower thematic groupings |
| 4 | Indicator Groups | Clusters of related indicators |
| 5 | Indicators | Individual measurable indicators (leaf nodes) |

The tree starts collapsed — only Ring 0 (root) is visible. Users drill into branches by clicking nodes to reveal children.

### Branch Expansion and Collapse

Expansion state is tracked as a `Set<string>` of expanded node IDs. A node's children are visible if and only if the node is in the expanded set. The root (Ring 0) is always visible.

**Single-node toggle (`toggleExpansion`):**
- **Expand:** Adds the node ID to the expanded set. Its children become visible on the next layout pass. The camera auto-zooms to frame the entire branch from Ring 1 forward (including the root at origin) with padding.
- **Collapse:** Removes the node ID *and all its descendants* from the expanded set. This ensures collapsing a Ring 1 node hides the entire branch below it, not just its immediate children. The camera zooms out to frame the root and the now-collapsed node.

**Ring-level expand (`expandRing`):** Expands all visible nodes at a given ring depth. A node is "visible" if it is the root or its parent is already expanded. This lets users open an entire tier of the hierarchy at once (e.g., "show all Coarse Domains").

**Ring-level collapse (`collapseRing`):** Collapses all nodes at the given ring and recursively collapses all descendants below them.

**Expand All / Collapse All:** Expand All adds every node with children to the expanded set. Collapse All resets the set to empty.

### Animation Sequencing

Expand and collapse have distinct animation sequences to avoid visual glitches:

**Expand sequence:**
1. Sector rotation (if layout changed) completes first
2. New child nodes enter (fade + scale in)
3. Text labels fade in after nodes finish entering

**Collapse sequence:**
1. Text labels fade out immediately (0-150ms)
2. Child nodes exit (fade + scale out, 150-350ms)
3. Sector rotation begins after collapse completes (~400ms)

A `collapseAnimationRef` prevents re-renders from interrupting an in-progress collapse animation.

### Auto-Expand After Simulation

When simulation results arrive, the visualization automatically expands only the branches containing the intervened indicators. It does **not** expand branches for propagated effects — only the exact intervention targets.

The algorithm:
1. Get indicator IDs from the intervention list (not from results/effects)
2. Build a parent lookup from the raw tree data
3. For each intervention indicator, walk up the tree to root, collecting ancestor IDs
4. Set the expanded set to exactly those ancestors

This focuses the user's attention on the branches they acted on, without overwhelming them with every affected indicator.

### Node Glow Effects

After simulation, nodes glow green (positive effect) or red (negative effect) with intensity proportional to the magnitude of the percent change. Glows apply to the final year's effects.

**Visibility filtering:** Only the top N effects (controlled by the effect filter slider) receive glows, matching exactly what the results table shows. Effects with near-zero baselines (`|baseline| < 0.01`) are excluded to prevent misleading glows from noise.

**Ancestor propagation:** If an affected indicator's node is not currently visible (its branch is collapsed), the glow propagates upward to the nearest visible ancestor. This means a collapsed Ring 1 node can glow to indicate that effects exist somewhere in its subtree.

### Effect Filter

The results panel shows a slider that controls how many effects are displayed (both in the table and as node glows). The filter is count-based via a percentage:

- `effectFilterPct` (0-1) determines the fraction of non-zero effects to show
- The actual count is `round(totalNonZero * effectFilterPct)`, applied as a deterministic `slice(0, N)` on the magnitude-sorted list
- **Auto-set on simulation:** When results arrive, the filter automatically computes a percentage that yields ~20 visible indicators: `min(1, 20 / nonZeroEffects)`. If fewer than 20 effects exist, all are shown.
- The slider label shows both count and percentage: "Show: top 20 (7%)"
- Zero-baseline effects are excluded before ranking to prevent noise from dominating the top positions
