# V3.1 Simulation Runner Update Specification

## Objective

Update `simulation_runner_v31.py` and `temporal_simulation_v31.py` to support **two simulation modes**:
1. **Percentage Mode** (default) - Fast, no baseline loading required
2. **Absolute Mode** - Uses baseline values for real-world units

---

## Current Problem

The current implementation **always loads baseline values** from a 65MB parquet file:

```python
# simulation_runner_v31.py:162
baseline, year_used, percentiles = load_baseline_values(country, year, panel_path)
```

This causes 30+ second load times, making the API timeout.

---

## Solution: Dual-Mode Simulation

### Mode 1: Percentage Mode (Default)

**Input:**
```json
{
  "country": "Australia",
  "interventions": [{"indicator": "health_spending", "change_percent": 20}],
  "year": 2020,
  "mode": "percentage"  // NEW - default
}
```

**Propagation Logic:**
```python
# No baseline needed - work entirely in percentages
delta_percent = intervention["change_percent"]  # 20%

for target in adjacency[source]:
    beta = edge["beta"]
    # Propagate percentage through beta
    target_change_percent = delta_percent * beta
    # If beta = 0.38, then 20% × 0.38 = 7.6% change in target
```

**Output:**
```json
{
  "effects": {
    "gdp_per_capita": {
      "percent_change": 7.6,
      "propagation_path": ["health_spending → gdp_per_capita"]
    }
  }
}
```

**Benefits:**
- No baseline loading (instant startup)
- No 65MB parquet dependency
- Sufficient for most "what-if" explorations

---

### Mode 2: Absolute Mode

**Input:**
```json
{
  "country": "Australia",
  "interventions": [{"indicator": "health_spending", "change_percent": 20}],
  "year": 2020,
  "mode": "absolute"  // Explicit request for absolute values
}
```

**Requires:** Pre-computed baseline files at `data/v3_1_baselines/{Country}/{year}.json`

**Propagation Logic:**
```python
# Load lightweight baseline (50-200KB JSON, not 65MB parquet)
baseline = load_precomputed_baseline(country, year)

base_val = baseline[indicator]  # e.g., $5,200
delta_absolute = base_val * (change_percent / 100)  # $1,040

for target in adjacency[source]:
    beta = edge["beta"]
    target_change_absolute = delta_absolute * beta  # $395.20
```

**Output:**
```json
{
  "effects": {
    "gdp_per_capita": {
      "baseline": 45000,
      "simulated": 45395.20,
      "absolute_change": 395.20,
      "percent_change": 0.88
    }
  }
}
```

---

## Implementation Changes

### 1. Update `run_simulation_v31()` signature

```python
def run_simulation_v31(
    country: str,
    interventions: List[dict],
    year: int,
    view_type: ViewType = 'country',
    mode: Literal['percentage', 'absolute'] = 'percentage',  # NEW
    p_value_threshold: float = 0.05,
    use_nonlinear: bool = True,
    n_ensemble_runs: int = 0,
    include_spillovers: bool = True,
    top_n_effects: int = 20,
    baseline_dir: Optional[Path] = None  # NEW - for absolute mode
) -> dict:
```

### 2. Add percentage-mode propagation function

Create `propagate_intervention_percentage()` in `propagation_v31.py`:

```python
def propagate_intervention_percentage(
    adjacency: Dict[str, List[dict]],
    intervention: Dict[str, float],  # {indicator: change_percent}
    use_nonlinear: bool = True,
    max_iterations: int = 100,
    convergence_threshold: float = 1e-6
) -> dict:
    """
    Propagate percentage changes through causal graph.

    No baseline values needed - works entirely in percentages.

    Args:
        adjacency: Graph adjacency dict with beta coefficients
        intervention: {indicator_id: change_percent}
        use_nonlinear: Use marginal_effects when available

    Returns:
        {
            'percent_changes': {indicator: percent_change},
            'iterations': int,
            'converged': bool
        }
    """
    percent_changes = dict(intervention)  # Start with interventions

    for iteration in range(max_iterations):
        updates = {}

        for source, change_pct in percent_changes.items():
            if source not in adjacency:
                continue

            for edge in adjacency[source]:
                target = edge['target']
                beta = edge['beta']

                # Non-linear: use marginal effects if available
                if use_nonlinear and 'nonlinearity' in edge:
                    nl = edge['nonlinearity']
                    if nl.get('detected') and 'marginal_effects' in nl:
                        # Use median marginal effect (p50)
                        beta = nl['marginal_effects'].get('p50', beta)

                # Propagate percentage
                target_delta = change_pct * beta

                if target in updates:
                    updates[target] += target_delta
                else:
                    updates[target] = target_delta

        # Check convergence
        max_update = max(abs(v) for v in updates.values()) if updates else 0
        if max_update < convergence_threshold:
            return {
                'percent_changes': percent_changes,
                'iterations': iteration + 1,
                'converged': True
            }

        # Apply updates
        for target, delta in updates.items():
            percent_changes[target] = percent_changes.get(target, 0) + delta

    return {
        'percent_changes': percent_changes,
        'iterations': max_iterations,
        'converged': False
    }
```

### 3. Update main simulation function

```python
def run_simulation_v31(..., mode='percentage', ...):
    # Load graph (always needed)
    graph = load_temporal_graph(country, year, view_type, p_value_threshold)
    adjacency = build_adjacency_v31(graph)

    if mode == 'percentage':
        # Fast path - no baseline loading
        intervention_pct = {i['indicator']: i['change_percent'] for i in interventions}

        result = propagate_intervention_percentage(
            adjacency=adjacency,
            intervention=intervention_pct,
            use_nonlinear=use_nonlinear
        )

        return {
            'status': 'success',
            'mode': 'percentage',
            'country': country,
            'year': year,
            'effects': {
                'total_affected': len(result['percent_changes']),
                'top_effects': get_top_percent_effects(result['percent_changes'], top_n_effects)
            },
            'propagation': {
                'iterations': result['iterations'],
                'converged': result['converged']
            }
        }

    else:  # mode == 'absolute'
        # Load pre-computed baseline (lightweight JSON)
        baseline = load_precomputed_baseline(country, year, baseline_dir)
        if not baseline:
            return {'status': 'error', 'message': f'No baseline data for {country}/{year}'}

        # Existing absolute propagation logic...
        # (current implementation)
```

### 4. Create baseline loading from JSON

Add to `simulation_runner_v31.py`:

```python
BASELINE_DIR = V31_ROOT / "data" / "v3_1_baselines"

def load_precomputed_baseline(
    country: str,
    year: int,
    baseline_dir: Optional[Path] = None
) -> Dict[str, float]:
    """
    Load pre-computed baseline from JSON file.

    Falls back to nearest available year if exact year not found.
    """
    base_dir = baseline_dir or BASELINE_DIR
    baseline_file = base_dir / country / f"{year}.json"

    if not baseline_file.exists():
        # Try nearest year
        country_dir = base_dir / country
        if not country_dir.exists():
            return {}

        available = [int(f.stem) for f in country_dir.glob("*.json") if f.stem.isdigit()]
        if not available:
            return {}

        nearest = min(available, key=lambda y: abs(y - year))
        baseline_file = country_dir / f"{nearest}.json"

    try:
        with open(baseline_file) as f:
            data = json.load(f)
            return data.get("values", {})
    except (json.JSONDecodeError, IOError):
        return {}
```

---

## API Request Schema Updates

Update `api/models/requests.py`:

```python
class SimulationRequestV31(BaseModel):
    country: str
    interventions: List[InterventionInput]
    year: int = Field(..., ge=1990, le=2024)
    mode: Literal['percentage', 'absolute'] = Field(
        default='percentage',
        description="percentage: fast, no baselines; absolute: includes real values"
    )
    view_type: Literal['country', 'stratified', 'unified'] = 'country'
    # ... existing fields
```

---

## API Response Schema Updates

Update `api/models/responses.py`:

```python
class EffectDetailV31(BaseModel):
    # For percentage mode
    percent_change: float

    # For absolute mode (optional)
    baseline: Optional[float] = None
    simulated: Optional[float] = None
    absolute_change: Optional[float] = None

    # Common
    ci_lower: Optional[float] = None
    ci_upper: Optional[float] = None
```

---

## Baseline Pre-computation Script

The script `precompute_baselines.py` has been created at:
`<repo-root>/v3.1/simulation/precompute_baselines.py`

Run to generate baseline JSONs:
```bash
cd <repo-root>/v3.1
python -m simulation.precompute_baselines
```

Output structure:
```
data/v3_1_baselines/
  Australia/
    1999.json
    2000.json
    ...
  Brazil/
    ...
```

Each JSON file (~50-200KB):
```json
{
  "country": "Australia",
  "year": 2020,
  "n_indicators": 1523,
  "values": {
    "indicator_id_1": 45000.0,
    "indicator_id_2": 82.5,
    ...
  }
}
```

---

## Testing Checklist

- [ ] Percentage mode works without any baseline files
- [ ] Percentage mode returns in <1 second
- [ ] Absolute mode loads from JSON baselines (not parquet)
- [ ] Absolute mode returns in <2 seconds
- [ ] Non-linear marginal effects (p25/p50/p75) used in propagation
- [ ] API timeout no longer occurs
- [ ] Frontend receives correct response format for both modes

---

## Files to Modify

1. `v3.1/simulation/simulation_runner_v31.py` - Add mode parameter, percentage propagation
2. `v3.1/simulation/propagation_v31.py` - Add `propagate_intervention_percentage()`
3. `v3.1/simulation/temporal_simulation_v31.py` - Same dual-mode support
4. `viz/phase2/api/models/requests.py` - Add `mode` field
5. `viz/phase2/api/models/responses.py` - Update effect details
6. `viz/phase2/api/services/simulation_service.py` - Pass mode to runner

---

## Summary

| Mode | Baseline Required | Load Time | Output |
|------|-------------------|-----------|--------|
| `percentage` | No | <1s | `percent_change` only |
| `absolute` | Yes (JSON) | <2s | Full `baseline`, `simulated`, `absolute_change`, `percent_change` |

Default to `percentage` mode for fast exploration. Use `absolute` mode when users need real-world values.
