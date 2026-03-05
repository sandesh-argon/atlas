# Execution Framework & Safeguards

## Pre-A0 Requirements Checklist

### 1. Literature Reference Database (REQUIRED BEFORE A0)
**Status**: ⚠️ MUST CREATE BEFORE PHASE A
**Location**: `literature_db/literature_constructs.json`
**Purpose**: Validation baseline for B1 outcome discovery
**Time**: 2-4 hours

**Contents Required**:
- 10+ known QOL constructs with:
  - Keywords (for TF-IDF matching)
  - Typical indicators
  - Canonical papers
  - Domain classification

**Action**: Create `literature_db/literature_constructs.json` with all 10 constructs from master instructions (lines 22-43)

### 2. Domain Compatibility Matrix (REQUIRED FOR A2)
**Status**: ⚠️ MUST CREATE BEFORE A2
**Location**: `phaseA/A2_granger_causality/domain_compatibility_matrix.json`
**Purpose**: Prefiltering logic to reduce 6.2M → 200K tests
**Time**: 1-2 hours

**Contents**: 13×13 matrix of plausible domain connections
- Example: (Health, Education) = True (well-documented)
- Example: (Environment, Trade) = False (no direct mechanism)

### 3. V1 Validated Outcomes Reference (ANCHOR)
**Status**: ⚠️ MUST CREATE BEFORE B1
**Location**: `phaseB/B1_outcome_discovery/v1_validated_outcomes.json`
**Purpose**: Assert that V2 reproduces ≥6 out of 8 V1 outcomes
**Time**: 15 minutes

**Contents**:
```json
{
  "v1_outcomes": [
    "life_expectancy",
    "years_schooling",
    "gdp_per_capita",
    "infant_mortality",
    "gini_index",
    "homicide_rate",
    "nutrition_index",
    "internet_access"
  ],
  "minimum_reproduction": 6
}
```

### 4. Validation Test Templates
**Status**: ⚠️ CREATE BEFORE PHASE A
**Location**: `validation/test_templates/`
**Purpose**: Pre-defined validation functions to prevent scope creep
**Time**: 2-3 hours

**Required tests** (from master instructions validation framework):
- `test_bootstrap_stability.py` (target: >75% edge retention)
- `test_dag_validity.py` (assert no cycles)
- `test_literature_reproduction.py` (target: >70% known links)
- `test_holdout_r2.py` (target: >0.55 mean)
- `test_shap_retention.py` (target: >85% for pruning)

---

## Execution Safeguards: Preventing Rabbit Holes

### 1. Time-Boxing Strategy

**Rule**: Each step has STRICT time limits from master instructions

```python
# Built into every script header
STEP_NAME = "A2_granger_causality"
MAX_WALL_CLOCK_TIME = timedelta(days=6)  # From master instructions
START_TIME = datetime.now()

def check_time_limit():
    elapsed = datetime.now() - START_TIME
    if elapsed > MAX_WALL_CLOCK_TIME:
        logger.critical(f"⏰ TIME LIMIT EXCEEDED: {elapsed} > {MAX_WALL_CLOCK_TIME}")
        logger.critical("Triggering early stopping condition...")
        return True
    return False
```

**Human Validation Trigger**: If time limit exceeded, PAUSE and ask user:
- "A2 exceeded 6-day limit. Current status: {progress}. Options: (1) Continue with relaxed thresholds, (2) Stop and review, (3) Switch to alternative method (GES)."

### 2. Success Criteria Gates

**Rule**: MUST pass validation before proceeding to next step

```python
# At end of every step
def validate_step_output(step_name, output_data, success_criteria):
    """
    Enforces success criteria from master instructions.
    Blocks progression if criteria not met.
    """
    results = {}
    all_passed = True

    for criterion, (min_val, max_val) in success_criteria.items():
        actual = compute_metric(output_data, criterion)
        passed = (min_val is None or actual >= min_val) and \
                 (max_val is None or actual <= max_val)

        results[criterion] = {
            'actual': actual,
            'expected': f"{min_val}-{max_val}",
            'passed': passed
        }

        if not passed:
            all_passed = False
            logger.error(f"❌ {criterion}: {actual} NOT IN [{min_val}, {max_val}]")

    if not all_passed:
        logger.critical(f"🚨 VALIDATION FAILED FOR {step_name}")
        logger.critical("STOPPING EXECUTION - HUMAN REVIEW REQUIRED")
        save_validation_report(step_name, results)
        raise ValidationError(f"{step_name} failed validation criteria")

    logger.info(f"✅ All validation criteria passed for {step_name}")
    return results
```

**Human Validation Required When**:
- Any success criterion fails
- Output outside expected ranges
- Novel patterns not in literature

### 3. Scope Limitation Guards

**Rule**: Only implement what's in master instructions, nothing more

```python
# scope_guard.py - Imported at top of every script
ALLOWED_OPERATIONS = {
    'A0': ['fetch_data', 'apply_coverage_filters', 'select_temporal_window'],
    'A1': ['run_imputation_configs', 'compute_multi_criteria_score', 'select_optimal_config'],
    'A2': ['prefilter_pairs', 'run_granger_tests', 'fdr_correction'],
    # ... etc per master instructions
}

def scope_guard(step_name, operation_name):
    """Prevents scope creep by blocking undefined operations"""
    if operation_name not in ALLOWED_OPERATIONS[step_name]:
        logger.error(f"🚫 SCOPE VIOLATION: {operation_name} not in {step_name} spec")
        logger.error(f"Allowed operations: {ALLOWED_OPERATIONS[step_name]}")
        raise ScopeViolationError(f"Operation {operation_name} not in master instructions")
```

### 4. Early Stopping Conditions

**Rule**: Pre-defined exit strategies (from master instructions lines 1240-1256)

```python
# Built into long-running steps (A2, A3, A5)
EARLY_STOPPING_CONDITIONS = {
    'A2_granger': {
        'trigger': 'elapsed_time > 7 days AND completion < 0.50',
        'action': 'increase_correlation_threshold(from=0.10, to=0.15)'
    },
    'A3_pc_stable': {
        'trigger': 'edge_count > 50000',
        'action': 'switch_to_ges_algorithm()'
    },
    'B4_pruning': {
        'trigger': 'shap_retention < 0.85',
        'action': 'relax_to_top30_mechanisms(from_top=20)'
    }
}

def check_early_stopping(step_name, current_state):
    condition = EARLY_STOPPING_CONDITIONS.get(step_name)
    if condition and eval(condition['trigger']):
        logger.warning(f"⚠️  EARLY STOPPING TRIGGERED: {condition['trigger']}")
        logger.warning(f"Executing fallback: {condition['action']}")
        exec(condition['action'])
        return True
    return False
```

---

## Context Management Strategy

### Problem: Claude Code context windows auto-compact after ~150K tokens

### Solution: Progressive Context Preservation

#### 1. Step-Level Context Files

**Create at start of each step**:
```
phaseA/A2_granger_causality/
├── CONTEXT.md              # ← Generated at step start
├── INPUT_MANIFEST.json     # What came from A1
├── OUTPUT_MANIFEST.json    # What A2 produces
└── VALIDATION_REPORT.json  # Success criteria results
```

**CONTEXT.md Template**:
```markdown
# A2 Granger Causality - Context Summary

## Inputs from A1
- Clean variables: 4,523
- Optimal imputation: MICE_RF with threshold=0.48
- Data shape: (7,123 observations × 4,523 variables)

## Current Step Objective
Reduce 6.2M candidate pairs → 200K using prefiltering, then Granger test

## Success Criteria (from master instructions line 278-283)
- [ ] Validated edges: 30,000-80,000
- [ ] Mean p-value (adjusted): <0.01
- [ ] Bidirectional edges: <15% of total

## Key Parameters
- Prefilter correlation: 0.10 < |r| < 0.95
- Granger lags: [1, 2, 3, 5]
- FDR alpha: 0.05

## Progress Tracking
- [x] Prefiltering complete: 6.2M → 187K pairs (97% reduction)
- [ ] Granger tests: 0% (0 / 748K tests)
- [ ] FDR correction: pending
- [ ] Bidirectional flagging: pending

## Critical V1 Lessons for This Step
- ❌ DON'T test all pairs → Use domain compatibility matrix
- ✅ DO exclude self-lagged variables
- ✅ DO apply imputation weighting to test statistics
```

#### 2. Inter-Step Handoff Protocol

**At end of each step, create `OUTPUT_MANIFEST.json`**:
```json
{
  "step": "A2_granger_causality",
  "completion_date": "2025-11-15T14:32:00Z",
  "outputs": {
    "validated_edges": {
      "file": "checkpoints/A2_granger_edges.pkl",
      "count": 47832,
      "schema": "List[Dict[source, target, lag, p_value, f_stat]]"
    }
  },
  "validation_results": {
    "edge_count_in_range": true,
    "mean_p_adjusted": 0.0043,
    "bidirectional_pct": 0.12
  },
  "next_step_inputs": {
    "for_A3": ["validated_edges", "data_clean"],
    "required_params": {
      "pc_alpha": 0.001,
      "independence_test": "fisherz"
    }
  },
  "human_review_required": false,
  "notes": "Edge count on lower end (47K) but within spec. Bidirectional edges flagged for A3 conditional independence review."
}
```

**At start of next step, read previous OUTPUT_MANIFEST.json**:
```python
# First lines of A3 script
import json
from pathlib import Path

def load_previous_context(previous_step):
    manifest_path = Path(f"../{previous_step}/OUTPUT_MANIFEST.json")
    with open(manifest_path) as f:
        return json.load(f)

# Load A2 outputs
a2_context = load_previous_context("A2_granger_causality")
validated_edges = pd.read_pickle(a2_context['outputs']['validated_edges']['file'])

logger.info(f"Loaded {len(validated_edges)} edges from A2")
logger.info(f"A2 validation status: {a2_context['validation_results']}")
```

#### 3. Progress Tracking Across Sessions

**Global progress file**: `PROJECT_STATUS.json` (updated after each step)

```json
{
  "project": "V2_Global_Causal_Discovery",
  "current_phase": "A",
  "current_step": "A3_conditional_independence",
  "start_date": "2025-11-11",
  "last_update": "2025-11-16T09:15:00Z",

  "completed_steps": [
    {
      "step": "A0_data_acquisition",
      "completion_date": "2025-11-11",
      "outputs": {"variables": 5234, "countries": 217, "years": "1990-2024"},
      "validation": "PASSED"
    },
    {
      "step": "A1_missingness_analysis",
      "completion_date": "2025-11-12",
      "outputs": {"optimal_config": "MICE_RF_threshold_0.48", "clean_vars": 4523},
      "validation": "PASSED"
    },
    {
      "step": "A2_granger_causality",
      "completion_date": "2025-11-15",
      "outputs": {"validated_edges": 47832},
      "validation": "PASSED"
    }
  ],

  "current_step_progress": {
    "step": "A3_conditional_independence",
    "status": "IN_PROGRESS",
    "progress_pct": 0.35,
    "checkpoint": "pc_stable_iteration_2_of_5",
    "time_elapsed": "18 hours",
    "estimated_remaining": "32 hours"
  },

  "validation_summary": {
    "steps_passed": 3,
    "steps_failed": 0,
    "human_reviews_required": 0
  },

  "key_metrics_so_far": {
    "variables_surviving": 4523,
    "edges_validated": 47832,
    "literature_reproduction_rate": null,
    "bootstrap_stability": null
  }
}
```

**Update command** (run at end of every step):
```python
def update_project_status(step_name, outputs, validation_results):
    status = json.load(open("PROJECT_STATUS.json"))

    status['completed_steps'].append({
        'step': step_name,
        'completion_date': datetime.now().isoformat(),
        'outputs': outputs,
        'validation': 'PASSED' if validation_results['all_passed'] else 'FAILED'
    })

    status['last_update'] = datetime.now().isoformat()

    with open("PROJECT_STATUS.json", 'w') as f:
        json.dump(status, f, indent=2)
```

#### 4. If Context Compacts Mid-Step

**Recovery Protocol**:
1. Read `CONTEXT.md` for current step
2. Read `PROJECT_STATUS.json` for completed steps
3. Read latest checkpoint from `checkpoints/`
4. Read `OUTPUT_MANIFEST.json` from previous step
5. Continue from last checkpoint

**Test recovery** (add to every script):
```python
def ensure_context_continuity():
    """Call at script start to verify all dependencies exist"""
    required = [
        "CONTEXT.md",
        "../PROJECT_STATUS.json",
        "INPUT_MANIFEST.json"
    ]

    for req in required:
        if not Path(req).exists():
            raise ContextError(f"Missing required context file: {req}")

    logger.info("✓ Context continuity verified")
```

---

## Human Validation Integration

### When to Request Human Review

**Automatic triggers** (hardcoded in validation functions):

1. **Validation Failure**: Any success criterion fails
2. **Novelty Detection**: Discovered pattern not in literature (confidence < 0.60 in B1)
3. **Time Limit Exceeded**: Step takes >1.5x expected time
4. **Ambiguity**: Multiple valid paths forward (e.g., GES vs PC-Stable)
5. **Domain Classification**: Low confidence (<0.80) in B3 semantic clustering
6. **Critical Decision Points**:
   - A1: Selecting optimal imputation config (review top 3 candidates)
   - A2: If prefiltering removes >99% of pairs (too aggressive?)
   - B1: Novel factors not matching literature (accept/reject/revise?)
   - B4: If SHAP retention <85% (relax pruning or accept?)

### Human Validation Protocol

**Format**: Structured decision request with context

```python
def request_human_validation(step, issue, options, context):
    """
    Pauses execution and prompts human decision with full context
    """
    report = f"""
    ╔═══════════════════════════════════════════════════════════╗
    ║  HUMAN VALIDATION REQUIRED - {step}                       ║
    ╚═══════════════════════════════════════════════════════════╝

    ISSUE: {issue}

    CONTEXT:
    {json.dumps(context, indent=2)}

    OPTIONS:
    {chr(10).join(f"  [{i+1}] {opt['label']}: {opt['description']}"
                   for i, opt in enumerate(options))}

    RECOMMENDATION: {recommend_option(options, context)}

    MASTER INSTRUCTIONS REFERENCE: Line {get_relevant_lines(step, issue)}

    Please select option [1-{len(options)}] or provide custom guidance:
    """

    print(report)
    save_validation_request(step, issue, report)

    # Pause execution
    user_choice = input("Your decision: ")
    return parse_validation_response(user_choice, options)
```

**Example - A1 Optimal Config Selection**:
```python
# At end of A1 after running 25 configs
top_3_configs = sorted(results, key=lambda x: x['score'], reverse=True)[:3]

decision = request_human_validation(
    step="A1_missingness_analysis",
    issue="Multiple configs scored within 2% of each other. Need human judgment.",
    options=[
        {
            'label': 'Config 1: MICE_RF, threshold=0.48',
            'description': f'Score: 0.847, Variables: 4523, Stability: 0.89, R²: 0.61',
            'pros': 'Highest score, good stability',
            'cons': 'Slightly fewer variables than Config 2'
        },
        {
            'label': 'Config 2: MICE_Linear, threshold=0.52',
            'description': f'Score: 0.841, Variables: 4712, Stability: 0.86, R²: 0.59',
            'pros': 'More variables retained',
            'cons': 'Lower stability score'
        },
        {
            'label': 'Config 3: KNN_k5, threshold=0.45',
            'description': f'Score: 0.838, Variables: 4398, Stability: 0.91, R²: 0.63',
            'pros': 'Highest stability and R², faster computation',
            'cons': 'Fewest variables'
        }
    ],
    context={
        'all_25_configs': results,
        'score_breakdown': score_components,
        'v1_comparison': 'V1 used MICE_RF with 3,742 variables'
    }
)
```

### Validation Log

**Track all human decisions**: `validation/HUMAN_DECISIONS.json`

```json
{
  "decisions": [
    {
      "timestamp": "2025-11-12T14:30:00Z",
      "step": "A1_missingness_analysis",
      "issue": "Config selection ambiguity",
      "options_presented": 3,
      "human_choice": "Config 1: MICE_RF, threshold=0.48",
      "rationale": "Prioritized stability over variable count given V1 lesson about imputation quality",
      "impact": "Reduced variable count by 189 vs Config 2, but +0.03 stability"
    }
  ]
}
```

---

## Enhanced CLAUDE.md Integration

These safeguards should be **prominently featured** in CLAUDE.md. Let me update it now.

### Additions Needed:
1. **Execution Safeguards Section**: Time-boxing, validation gates, scope guards
2. **Context Management Section**: Inter-step handoff protocol
3. **Human Validation Section**: When/how to request reviews
4. **Pre-Execution Checklist**: Literature DB, domain matrix, V1 outcomes
5. **Recovery Protocol**: What to do if context compacts
