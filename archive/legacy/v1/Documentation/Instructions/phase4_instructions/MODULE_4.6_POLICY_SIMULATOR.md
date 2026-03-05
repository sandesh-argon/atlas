# MODULE 4.6: Policy Simulation Framework

## OBJECTIVE
Implement Pearl's do-calculus to create a `PolicySimulator` class that answers "what-if" policy questions, predicts direct and spillover effects across QOL metrics, and exports API-ready artifacts for Phase 6 dashboard integration.

## CONTEXT
Modules 4.2-4.5 discovered causal structure (DAGs) and quantified effects. Module 4.6 operationalizes this knowledge into a policy simulation engine. The simulator implements do-calculus intervention logic: `P(Y | do(X=x))` differs from `P(Y | X=x)` by removing confounding. Example: "If we increase health expenditure by 20% (intervention), infant mortality decreases by X% with spillover to life expectancy +Y years." This provides policymakers with evidence-based forecasts for development interventions.

## INPUTS

### From Module 4.3
- **Refined Causal Graphs**: `<repo-root>/v1.0/models/causal_graphs/tier1/{metric}_pc_refined.pkl`
  - DAG structure for within-metric propagation

### From Module 4.4
- **Inter-Metric Graph**: `<repo-root>/v1.0/models/causal_graphs/inter_metric_graph.pkl`
  - Metric→metric relationships for spillover effects

### From Module 4.5
- **Quantified Effects**: `<repo-root>/v1.0/models/causal_graphs/tier1/causal_effects_quantified.json`
  - Effect sizes and confidence intervals

### Configuration
- **Intervention Types**: Additive (+/- X%) or multiplicative (×1.2)
- **Time Horizon**: 1-10 years (for multi-step propagation)
- **Uncertainty Mode**: Point estimate or confidence interval

## TASK DIRECTIVE

### Step 1: Implement PolicySimulator Class

**Script**: `policy_simulator.py`

Create the core simulator class:

```python
import networkx as nx
import numpy as np
import pickle
import json
from typing import Dict, List, Tuple, Optional

class PolicySimulator:
    """
    Policy intervention simulator using Pearl's do-calculus.

    Capabilities:
    1. Direct effect estimation: X → Y
    2. Propagated effects: X → Z → Y
    3. Spillover effects: Metric A → Metric B
    4. Uncertainty quantification: Confidence intervals
    5. Counterfactual queries: "What if we had intervened?"
    """

    def __init__(
        self,
        causal_graphs: Dict[str, nx.DiGraph],
        causal_effects: Dict[str, Dict[str, Dict]],
        inter_metric_graph: nx.DiGraph
    ):
        """
        Initialize with causal knowledge from Modules 4.2-4.5.

        Parameters:
        -----------
        causal_graphs : Dict[str, nx.DiGraph]
            Within-metric causal DAGs {metric: graph}
        causal_effects : Dict[str, Dict[str, Dict]]
            Quantified effects {metric: {driver: {effect, ci_lower, ci_upper}}}
        inter_metric_graph : nx.DiGraph
            Between-metric relationships
        """
        self.causal_graphs = causal_graphs
        self.causal_effects = causal_effects
        self.inter_metric_graph = inter_metric_graph

        # Pre-compute topological orderings for propagation
        self.topo_orders = {
            metric: list(nx.topological_sort(graph))
            for metric, graph in causal_graphs.items()
        }

    def simulate_intervention(
        self,
        target_metric: str,
        intervention_feature: str,
        change_pct: float,
        time_horizon: int = 5,
        uncertainty: bool = True
    ) -> Dict:
        """
        Simulate policy intervention using do-calculus.

        Example:
        >>> sim.simulate_intervention(
        ...     target_metric='infant_mortality',
        ...     intervention_feature='health_expenditure_gdp_lag2',
        ...     change_pct=0.20,  # +20% increase
        ...     time_horizon=5
        ... )
        {
            'direct_effect': {
                'infant_mortality': -0.058,  # 5.8% reduction
                'ci_lower': -0.072,
                'ci_upper': -0.044
            },
            'spillover_effects': {
                'life_expectancy': +0.021,  # 2.1% increase
                'ci_lower': +0.010,
                'ci_upper': +0.032
            },
            'time_to_full_effect': 3  # years
        }

        Parameters:
        -----------
        target_metric : str
            QOL metric to analyze
        intervention_feature : str
            Causal driver to intervene on
        change_pct : float
            Intervention magnitude (-1.0 to 1.0, e.g., 0.20 = +20%)
        time_horizon : int
            Years to propagate effects (1-10)
        uncertainty : bool
            If True, return confidence intervals

        Returns:
        --------
        results : Dict
            Direct effect, spillover effects, confidence intervals
        """
        # Step 1: Direct effect on target metric
        if intervention_feature not in self.causal_effects[target_metric]:
            raise ValueError(f"{intervention_feature} not a causal driver of {target_metric}")

        effect_data = self.causal_effects[target_metric][intervention_feature]
        direct_effect = effect_data['causal_effect'] * change_pct

        results = {
            'intervention': {
                'metric': target_metric,
                'feature': intervention_feature,
                'change_pct': change_pct
            },
            'direct_effect': {
                target_metric: direct_effect
            }
        }

        if uncertainty:
            ci_lower = effect_data['ci_lower'] * change_pct
            ci_upper = effect_data['ci_upper'] * change_pct
            results['direct_effect']['ci_lower'] = ci_lower
            results['direct_effect']['ci_upper'] = ci_upper

        # Step 2: Propagate through within-metric DAG
        # (For simplicity, assume first-order effects only)
        # Advanced: Multi-step propagation using topological order

        # Step 3: Check for spillover to other metrics
        spillover_effects = {}

        if self.inter_metric_graph.has_node(target_metric):
            for other_metric in self.inter_metric_graph.successors(target_metric):
                # Get cross-metric coefficient from VAR/Granger
                edge_data = self.inter_metric_graph[target_metric][other_metric]
                var_coef = edge_data.get('var_coefficient', 0)

                # Spillover = direct_effect × var_coefficient
                spillover = direct_effect * var_coef
                spillover_effects[other_metric] = spillover

                if uncertainty:
                    # Propagate uncertainty (simplified: assume independence)
                    spillover_effects[f'{other_metric}_ci_lower'] = ci_lower * var_coef
                    spillover_effects[f'{other_metric}_ci_upper'] = ci_upper * var_coef

        if spillover_effects:
            results['spillover_effects'] = spillover_effects

        # Step 4: Time-to-full-effect (based on lag structure)
        # Extract best lag from intervention feature name
        if '_lag' in intervention_feature:
            lag = int(intervention_feature.split('_lag')[-1])
            results['time_to_full_effect'] = lag
        else:
            results['time_to_full_effect'] = 1  # Contemporaneous

        return results

    def counterfactual_query(
        self,
        country: str,
        year: int,
        intervention: Dict,
        observed_outcome: float
    ) -> Dict:
        """
        Answer: "What would Y have been if we had done X?"

        Uses Pearl's counterfactual logic (3-step process):
        1. Abduction: Infer unobserved variables from observed data
        2. Action: Apply intervention (set X = x*)
        3. Prediction: Compute counterfactual outcome Y*

        Parameters:
        -----------
        country : str
            Country code
        year : int
            Year of intervention
        intervention : Dict
            {'metric': str, 'feature': str, 'change_pct': float}
        observed_outcome : float
            Actual observed value of target metric

        Returns:
        --------
        counterfactual : Dict
            Counterfactual outcome, treatment effect
        """
        # Simplified implementation (full version requires structural equations)
        metric = intervention['metric']
        feature = intervention['feature']
        change_pct = intervention['change_pct']

        # Estimate counterfactual using causal effect
        causal_effect = self.causal_effects[metric][feature]['causal_effect']
        counterfactual_outcome = observed_outcome + (causal_effect * change_pct)

        treatment_effect = counterfactual_outcome - observed_outcome

        return {
            'observed_outcome': observed_outcome,
            'counterfactual_outcome': counterfactual_outcome,
            'treatment_effect': treatment_effect,
            'intervention': intervention
        }

    def get_available_interventions(self, metric: str) -> List[str]:
        """
        List available intervention features for a metric.

        Returns:
        --------
        features : List[str]
            Causal drivers with quantified effects
        """
        return list(self.causal_effects.get(metric, {}).keys())

    def export_for_dashboard(self) -> Dict:
        """
        Export simulator API specification for Phase 6 dashboard.

        Returns:
        --------
        api_spec : Dict
            Available interventions, parameters, example queries
        """
        api_spec = {
            'version': '1.0',
            'available_metrics': list(self.causal_effects.keys()),
            'available_interventions': {
                metric: self.get_available_interventions(metric)
                for metric in self.causal_effects.keys()
            },
            'endpoint': '/api/simulate_intervention',
            'parameters': {
                'target_metric': 'str - QOL metric to analyze',
                'intervention_feature': 'str - Causal driver to intervene on',
                'change_pct': 'float - Percent change (-1.0 to 1.0)',
                'time_horizon': 'int - Years to simulate (1-10)',
                'uncertainty': 'bool - Include confidence intervals'
            },
            'example_query': {
                'target_metric': 'infant_mortality',
                'intervention_feature': 'health_expenditure_gdp_lag2',
                'change_pct': 0.20,
                'time_horizon': 5,
                'uncertainty': True
            },
            'example_response': {
                'direct_effect': {
                    'infant_mortality': -0.058,
                    'ci_lower': -0.072,
                    'ci_upper': -0.044
                },
                'spillover_effects': {
                    'life_expectancy': 0.021
                },
                'time_to_full_effect': 2
            }
        }

        return api_spec
```

### Step 2: Instantiate Simulator with Phase 4 Outputs

**Script**: `phase4_create_simulator.py`

```python
import pickle
import json
import networkx as nx

# Load causal graphs (Tier 1)
causal_graphs = {}
TIER1_METRICS = ['mean_years_schooling', 'infant_mortality', 'undernourishment']

for metric in TIER1_METRICS:
    with open(f'<repo-root>/v1.0/models/causal_graphs/tier1/{metric}_pc_refined.pkl', 'rb') as f:
        cg = pickle.load(f)
        # Convert to NetworkX DiGraph
        causal_graphs[metric] = nx.DiGraph(cg.G.get_graph_edges())

# Load causal effects
with open('<repo-root>/v1.0/models/causal_graphs/tier1/causal_effects_quantified.json') as f:
    causal_effects = json.load(f)

# Load inter-metric graph
inter_metric_graph = nx.read_gpickle(
    '<repo-root>/v1.0/models/causal_graphs/inter_metric_graph.pkl'
)

# Instantiate simulator
simulator = PolicySimulator(
    causal_graphs=causal_graphs,
    causal_effects=causal_effects,
    inter_metric_graph=inter_metric_graph
)

# Save simulator (pickle)
with open('<repo-root>/v1.0/models/policy_simulator/policy_simulator.pkl', 'wb') as f:
    pickle.dump(simulator, f)

print("PolicySimulator created and saved successfully")
```

### Step 3: Test Simulator with Example Scenarios

**Script**: `phase4_test_simulator.py`

```python
import pickle

# Load simulator
with open('<repo-root>/v1.0/models/policy_simulator/policy_simulator.pkl', 'rb') as f:
    simulator = pickle.load(f)

# Test scenarios
scenarios = [
    {
        'name': 'Increase Health Expenditure',
        'target_metric': 'infant_mortality',
        'intervention_feature': 'health_expenditure_gdp_lag2',
        'change_pct': 0.20  # +20%
    },
    {
        'name': 'Increase Education Spending',
        'target_metric': 'mean_years_schooling',
        'intervention_feature': 'government_expenditure_education_lag2',
        'change_pct': 0.15  # +15%
    },
    {
        'name': 'Improve Agricultural Productivity',
        'target_metric': 'undernourishment',
        'intervention_feature': 'agricultural_productivity_lag2',
        'change_pct': 0.25  # +25%
    }
]

print("="*60)
print("POLICY SIMULATION TEST SCENARIOS")
print("="*60)

for scenario in scenarios:
    print(f"\n{scenario['name']}")
    print("-"*60)

    result = simulator.simulate_intervention(
        target_metric=scenario['target_metric'],
        intervention_feature=scenario['intervention_feature'],
        change_pct=scenario['change_pct'],
        time_horizon=5,
        uncertainty=True
    )

    # Display results
    metric = scenario['target_metric']
    direct = result['direct_effect'][metric]
    ci_lower = result['direct_effect']['ci_lower']
    ci_upper = result['direct_effect']['ci_upper']

    print(f"Intervention: {scenario['intervention_feature']} +{scenario['change_pct']*100:.0f}%")
    print(f"Direct Effect on {metric}: {direct:.3f}")
    print(f"95% CI: [{ci_lower:.3f}, {ci_upper:.3f}]")
    print(f"Time to full effect: {result['time_to_full_effect']} years")

    if 'spillover_effects' in result:
        print("\nSpillover Effects:")
        for other_metric, spillover in result['spillover_effects'].items():
            if not other_metric.endswith('_ci_lower') and not other_metric.endswith('_ci_upper'):
                print(f"  {other_metric}: {spillover:+.3f}")

print("\n" + "="*60)
```

### Step 4: Export API Specification

```python
# Export for Phase 6 dashboard
api_spec = simulator.export_for_dashboard()

with open('<repo-root>/v1.0/models/policy_simulator/api_specification.json', 'w') as f:
    json.dump(api_spec, f, indent=2)

print("\nAPI Specification exported for Phase 6 dashboard")
```

## OUTPUTS

### Primary Outputs

1. **PolicySimulator Class**: `<repo-root>/v1.0/Data/Scripts/phase4_modules/policy_simulator.py`
   - Python module with PolicySimulator class

2. **Simulator Instance** (pickled): `<repo-root>/v1.0/models/policy_simulator/policy_simulator.pkl`
   - Pre-loaded with Tier 1 causal knowledge

3. **API Specification**: `<repo-root>/v1.0/models/policy_simulator/api_specification.json`
   - Available interventions, parameters, example queries

4. **Test Results**: `<repo-root>/v1.0/models/policy_simulator/test_scenarios_results.json`
   - Simulation outputs for 3-5 example scenarios

## SUCCESS CRITERIA

- [ ] PolicySimulator class implements all core methods:
  - [ ] `simulate_intervention()` - Direct + spillover effects
  - [ ] `counterfactual_query()` - Retrospective analysis
  - [ ] `get_available_interventions()` - List causal drivers
  - [ ] `export_for_dashboard()` - API spec generation
- [ ] Test scenarios run successfully for all 3 Tier 1 metrics
- [ ] Simulation results have expected properties:
  - [ ] Effect signs match theoretical expectations
  - [ ] Confidence intervals are non-empty
  - [ ] Spillover effects are smaller than direct effects
  - [ ] Time-to-full-effect matches lag structure
- [ ] API specification is valid JSON with all required fields
- [ ] Simulator can be pickled/unpickled without errors

## INTEGRATION NOTES

### Handoff to Phase 6 (Dashboard)
- API specification defines `/api/simulate_intervention` endpoint
- Pickled simulator can be loaded in Flask backend
- Frontend can display:
  - Intervention slider (change_pct: -50% to +50%)
  - Direct effect visualization (bar chart with CI)
  - Spillover network diagram
  - Time-to-effect timeline

### Example Flask Route (Phase 6)
```python
from flask import Flask, request, jsonify
import pickle

app = Flask(__name__)

with open('models/policy_simulator.pkl', 'rb') as f:
    simulator = pickle.load(f)

@app.route('/api/simulate_intervention', methods=['POST'])
def simulate():
    data = request.json
    result = simulator.simulate_intervention(
        target_metric=data['target_metric'],
        intervention_feature=data['intervention_feature'],
        change_pct=data['change_pct'],
        time_horizon=data.get('time_horizon', 5),
        uncertainty=data.get('uncertainty', True)
    )
    return jsonify(result)
```

## ERROR HANDLING

### Common Issues

1. **Feature Not a Causal Driver**:
   - Error: `ValueError: {feature} not a causal driver of {metric}`
   - Solution: Use `simulator.get_available_interventions(metric)` to list valid features

2. **Inter-Metric Graph Missing Edge**:
   - Cause: No Granger-causal relationship discovered
   - Effect: No spillover effects in results (expected for some metrics)

3. **Confidence Intervals Cross Zero**:
   - Cause: Effect not statistically significant
   - Interpretation: Uncertainty is high, recommend larger intervention or more data

## VALIDATION CHECKS

```python
# Verify simulator functionality
assert hasattr(simulator, 'simulate_intervention'), "Missing core method"
assert hasattr(simulator, 'counterfactual_query'), "Missing counterfactual method"

# Test intervention for each Tier 1 metric
for metric in TIER1_METRICS:
    available = simulator.get_available_interventions(metric)
    assert len(available) > 0, f"No interventions for {metric}"
    print(f"{metric}: {len(available)} available interventions ✓")

# Test a simulation
result = simulator.simulate_intervention(
    target_metric='infant_mortality',
    intervention_feature=simulator.get_available_interventions('infant_mortality')[0],
    change_pct=0.10
)
assert 'direct_effect' in result, "Missing direct_effect in result"
assert 'infant_mortality' in result['direct_effect'], "Missing target metric in result"
print("Simulation test: ✓")
```

## ESTIMATED RUNTIME
**60 minutes** (30 min class implementation, 20 min testing, 10 min export)

## DEPENDENCIES
- Module 4.3 (VIF Refinement) - Causal graphs
- Module 4.4 (Inter-Metric Analysis) - Spillover graph
- Module 4.5 (Effect Quantification) - Effect sizes

## PRIORITY
**HIGH** - Core deliverable for policy decision support

## REFERENCES
- Pearl, J. (2009). *Causality* (2nd ed.). Cambridge University Press. (Do-calculus, Chapters 3-4)
- Pearl, J., & Mackenzie, D. (2018). *The Book of Why*. Basic Books. (Causal inference for general audience)
- Bareinboim, E., & Pearl, J. (2016). "Causal Inference and the Data-Fusion Problem." *PNAS*, 113(27), 7345-7352.
