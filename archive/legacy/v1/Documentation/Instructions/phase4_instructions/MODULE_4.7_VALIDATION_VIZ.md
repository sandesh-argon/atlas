# MODULE 4.7: Validation & Visualization

## OBJECTIVE
Validate all causal discovery outputs (DAG acyclicity, effect sign consistency, simulation reasonableness) and generate publication-quality visualizations (causal graphs, effect plots, inter-metric network) for Phase 6 dashboard and academic communication.

## CONTEXT
Module 4.7 is the quality assurance checkpoint before extending to all 8 metrics (Module 4.8). Validates: (1) DAGs have no cycles (mathematical requirement), (2) Effect signs match theory (education→GDP is positive, not negative), (3) Simulations produce reasonable magnitudes (not 500% effects from 10% intervention). Visualizations enable stakeholder communication: policymakers need intuitive causal diagrams, not adjacency matrices.

## INPUTS

### From All Previous Modules
- **Refined Causal Graphs**: `<repo-root>/v1.0/models/causal_graphs/tier1/{metric}_pc_refined.pkl`
- **Causal Effects**: `<repo-root>/v1.0/models/causal_graphs/tier1/causal_effects_quantified.json`
- **Inter-Metric Graph**: `<repo-root>/v1.0/models/causal_graphs/inter_metric_graph.pkl`
- **Policy Simulator**: `<repo-root>/v1.0/models/policy_simulator/policy_simulator.pkl`
- **Literature Validation**: `<repo-root>/v1.0/models/causal_graphs/tier1/literature_validation.json`

## TASK DIRECTIVE

### Step 1: Automated Validation Tests

**Script**: `phase4_validation_tests.py`

```python
import networkx as nx
import pickle
import json
import numpy as np
from datetime import datetime

TIER1_METRICS = ['mean_years_schooling', 'infant_mortality', 'undernourishment']

validation_report = {
    'timestamp': datetime.now().isoformat(),
    'tests': {},
    'overall_status': 'PENDING'
}

print("="*60)
print("PHASE 4 VALIDATION TESTS")
print("="*60)

# TEST 1: DAG Acyclicity
print("\n[TEST 1] DAG Acyclicity Check")
print("-"*60)

for metric in TIER1_METRICS:
    with open(f'<repo-root>/v1.0/models/causal_graphs/tier1/{metric}_pc_refined.pkl', 'rb') as f:
        cg = pickle.load(f)
        G = nx.DiGraph(cg.G.get_graph_edges())

    is_dag = nx.is_directed_acyclic_graph(G)
    validation_report['tests'][f'{metric}_is_dag'] = is_dag

    if is_dag:
        print(f"  ✓ {metric}: DAG (no cycles)")
    else:
        print(f"  ✗ {metric}: CONTAINS CYCLES")
        cycles = list(nx.simple_cycles(G))
        print(f"    Cycles found: {cycles[:3]}")  # Show first 3

# TEST 2: Effect Sign Consistency
print("\n[TEST 2] Effect Sign Consistency")
print("-"*60)

with open('<repo-root>/v1.0/models/causal_graphs/tier1/causal_effects_quantified.json') as f:
    causal_effects = json.load(f)

sign_inconsistencies = []

for metric, effects in causal_effects.items():
    for feature, data in effects.items():
        # Check if CI crosses zero for significant effects
        if data['significant']:
            crosses_zero = (data['ci_lower'] * data['ci_upper'] < 0)
            if crosses_zero:
                sign_inconsistencies.append(f"{metric} ← {feature}")
                print(f"  ✗ {metric} ← {feature}: CI crosses zero despite significance")

if len(sign_inconsistencies) == 0:
    print("  ✓ All significant effects have consistent sign (CI doesn't cross zero)")
    validation_report['tests']['sign_consistency'] = True
else:
    print(f"  ⚠ {len(sign_inconsistencies)} inconsistencies found")
    validation_report['tests']['sign_consistency'] = False

# TEST 3: Effect Magnitude Reasonableness
print("\n[TEST 3] Effect Magnitude Reasonableness")
print("-"*60)

unreasonable_effects = []

for metric, effects in causal_effects.items():
    for feature, data in effects.items():
        # Check if effect size is within reasonable range (-2 to +2 for normalized data)
        if abs(data['causal_effect']) > 2.0:
            unreasonable_effects.append((metric, feature, data['causal_effect']))
            print(f"  ⚠ {metric} ← {feature}: effect = {data['causal_effect']:.3f} (> 2.0)")

if len(unreasonable_effects) == 0:
    print("  ✓ All effects within reasonable range (|effect| < 2.0)")
    validation_report['tests']['magnitude_reasonable'] = True
else:
    print(f"  ⚠ {len(unreasonable_effects)} unreasonable magnitudes")
    validation_report['tests']['magnitude_reasonable'] = False

# TEST 4: Literature Alignment
print("\n[TEST 4] Literature Alignment")
print("-"*60)

with open('<repo-root>/v1.0/models/causal_graphs/tier1/literature_validation.json') as f:
    lit_validation = json.load(f)

total_comparisons = 0
sign_matches = 0

for metric, validations in lit_validation.items():
    for feature, data in validations.items():
        total_comparisons += 1
        if data['sign_match'] and data['is_significant']:
            sign_matches += 1

if total_comparisons > 0:
    match_rate = sign_matches / total_comparisons
    print(f"  Literature alignment: {sign_matches}/{total_comparisons} ({match_rate:.1%})")

    if match_rate >= 0.70:
        print(f"  ✓ Literature validation passed (≥70% match)")
        validation_report['tests']['literature_alignment'] = True
    else:
        print(f"  ⚠ Literature validation weak (<70% match)")
        validation_report['tests']['literature_alignment'] = False
else:
    print("  ⚠ No literature comparisons available")
    validation_report['tests']['literature_alignment'] = None

# TEST 5: Simulation Bounds
print("\n[TEST 5] Simulation Reasonableness")
print("-"*60)

with open('<repo-root>/v1.0/models/policy_simulator/policy_simulator.pkl', 'rb') as f:
    simulator = pickle.load(f)

simulation_failures = []

# Test 10% intervention on all available features
for metric in TIER1_METRICS:
    interventions = simulator.get_available_interventions(metric)[:5]  # Test first 5

    for feature in interventions:
        try:
            result = simulator.simulate_intervention(
                target_metric=metric,
                intervention_feature=feature,
                change_pct=0.10  # +10%
            )

            direct_effect = result['direct_effect'][metric]

            # Check if effect is unreasonably large (>100% from 10% intervention)
            if abs(direct_effect) > 1.0:
                simulation_failures.append((metric, feature, direct_effect))
                print(f"  ✗ {metric} ← {feature}: 10% intervention → {direct_effect*100:.0f}% effect")

        except Exception as e:
            simulation_failures.append((metric, feature, str(e)))
            print(f"  ✗ {metric} ← {feature}: Simulation failed - {e}")

if len(simulation_failures) == 0:
    print("  ✓ All simulations produce reasonable results")
    validation_report['tests']['simulation_reasonable'] = True
else:
    print(f"  ⚠ {len(simulation_failures)} simulation issues")
    validation_report['tests']['simulation_reasonable'] = False

# Overall Status
all_passed = all(
    v for v in validation_report['tests'].values() if isinstance(v, bool)
)

if all_passed:
    validation_report['overall_status'] = 'PASS'
    print("\n" + "="*60)
    print("✓ ALL VALIDATION TESTS PASSED")
    print("="*60)
else:
    validation_report['overall_status'] = 'FAIL'
    print("\n" + "="*60)
    print("✗ VALIDATION FAILED - Review issues above")
    print("="*60)

# Save validation report
with open('<repo-root>/v1.0/models/causal_graphs/validation_report.json', 'w') as f:
    json.dump(validation_report, f, indent=2)
```

### Step 2: Generate Causal Graph Visualizations

**Script**: `phase4_visualize_dags.py`

```python
import matplotlib.pyplot as plt
import networkx as nx
import pickle
from networkx.drawing.nx_agraph import graphviz_layout

TIER1_METRICS = ['mean_years_schooling', 'infant_mortality', 'undernourishment']

for metric in TIER1_METRICS:
    print(f"Visualizing: {metric}")

    # Load refined causal graph
    with open(f'<repo-root>/v1.0/models/causal_graphs/tier1/{metric}_pc_refined.pkl', 'rb') as f:
        cg = pickle.load(f)
        G = nx.DiGraph(cg.G.get_graph_edges())

    # Get node labels (feature names)
    # Assuming cg has feature names stored
    # (Adjust based on actual causal-learn structure)

    # Layout using Graphviz (hierarchical)
    try:
        pos = graphviz_layout(G, prog='dot')
    except:
        # Fallback to spring layout
        pos = nx.spring_layout(G, k=2, iterations=50)

    # Create figure
    plt.figure(figsize=(20, 12))

    # Draw nodes
    nx.draw_networkx_nodes(
        G, pos,
        node_color='lightblue',
        node_size=3000,
        alpha=0.9
    )

    # Draw edges
    nx.draw_networkx_edges(
        G, pos,
        edge_color='gray',
        arrows=True,
        arrowsize=20,
        arrowstyle='->',
        width=2
    )

    # Draw labels
    nx.draw_networkx_labels(
        G, pos,
        font_size=8,
        font_weight='bold'
    )

    plt.title(f'Causal DAG: {metric.replace("_", " ").title()}', fontsize=18, fontweight='bold')
    plt.axis('off')
    plt.tight_layout()

    # Save
    plt.savefig(
        f'<repo-root>/v1.0/models/causal_graphs/visualizations/{metric}_dag.png',
        dpi=300,
        bbox_inches='tight'
    )
    plt.close()

print("DAG visualizations saved")
```

### Step 3: Visualize Causal Effects with Confidence Intervals

**Script**: `phase4_visualize_effects.py`

```python
import pandas as pd
import matplotlib.pyplot as plt
import json

# Load causal effects
with open('<repo-root>/v1.0/models/causal_graphs/tier1/causal_effects_quantified.json') as f:
    causal_effects = json.load(f)

for metric in TIER1_METRICS:
    # Prepare data for plotting
    effects_data = []
    for feature, data in causal_effects[metric].items():
        effects_data.append({
            'feature': feature,
            'effect': data['causal_effect'],
            'ci_lower': data['ci_lower'],
            'ci_upper': data['ci_upper'],
            'significant': data['significant']
        })

    df = pd.DataFrame(effects_data)
    df = df.sort_values('effect', key=abs, ascending=False)[:10]  # Top 10

    # Create plot
    fig, ax = plt.subplots(figsize=(12, 8))

    # Color by significance
    colors = ['green' if sig else 'gray' for sig in df['significant']]

    # Plot bars with error bars
    y_pos = range(len(df))
    ax.barh(y_pos, df['effect'], color=colors, alpha=0.7)

    # Add confidence intervals
    for i, row in df.iterrows():
        ax.plot(
            [row['ci_lower'], row['ci_upper']],
            [y_pos[df.index.get_loc(i)], y_pos[df.index.get_loc(i)]],
            color='black',
            linewidth=2
        )

    # Labels
    ax.set_yticks(y_pos)
    ax.set_yticklabels([f.replace('_', ' ')[:30] for f in df['feature']], fontsize=9)
    ax.set_xlabel('Causal Effect (Standardized)', fontsize=12)
    ax.set_title(f'Causal Effects on {metric.replace("_", " ").title()}', fontsize=14, fontweight='bold')
    ax.axvline(0, color='black', linestyle='--', linewidth=1)
    ax.grid(axis='x', alpha=0.3)

    # Legend
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor='green', alpha=0.7, label='Significant (p < 0.05)'),
        Patch(facecolor='gray', alpha=0.7, label='Not Significant')
    ]
    ax.legend(handles=legend_elements, loc='lower right')

    plt.tight_layout()
    plt.savefig(
        f'<repo-root>/v1.0/models/causal_graphs/visualizations/{metric}_effects.png',
        dpi=300,
        bbox_inches='tight'
    )
    plt.close()

print("Effect visualizations saved")
```

### Step 4: Visualize Inter-Metric Causal Network

**Script**: `phase4_visualize_inter_metric.py`

```python
import networkx as nx
import matplotlib.pyplot as plt

# Load inter-metric graph
inter_metric_graph = nx.read_gpickle(
    '<repo-root>/v1.0/models/causal_graphs/inter_metric_graph.pkl'
)

# Create figure
plt.figure(figsize=(14, 10))

# Layout
pos = nx.spring_layout(inter_metric_graph, k=3, iterations=50, seed=42)

# Draw nodes (sized by degree)
node_sizes = [3000 + 1000 * inter_metric_graph.degree(node) for node in inter_metric_graph.nodes()]

nx.draw_networkx_nodes(
    inter_metric_graph, pos,
    node_color='lightcoral',
    node_size=node_sizes,
    alpha=0.9
)

# Draw edges (width by Granger significance)
edge_widths = [
    5 if inter_metric_graph[u][v].get('granger_p', 1.0) < 0.01 else 2
    for u, v in inter_metric_graph.edges()
]

nx.draw_networkx_edges(
    inter_metric_graph, pos,
    width=edge_widths,
    edge_color='gray',
    arrows=True,
    arrowsize=20,
    arrowstyle='->',
    connectionstyle='arc3,rad=0.1'
)

# Draw labels
labels = {node: node.replace('_', '\n') for node in inter_metric_graph.nodes()}
nx.draw_networkx_labels(
    inter_metric_graph, pos,
    labels=labels,
    font_size=9,
    font_weight='bold'
)

plt.title('Inter-Metric Causal Network\n(QOL Metric → Metric Relationships)', fontsize=16, fontweight='bold')
plt.axis('off')
plt.tight_layout()

plt.savefig(
    '<repo-root>/v1.0/models/causal_graphs/visualizations/inter_metric_graph.png',
    dpi=300,
    bbox_inches='tight'
)
plt.close()

print("Inter-metric graph visualization saved")
```

## OUTPUTS

### Primary Outputs

1. **Validation Report**: `<repo-root>/v1.0/models/causal_graphs/validation_report.json`
   - 5 automated tests with pass/fail status
   - Overall status: PASS/FAIL

2. **DAG Visualizations** (3 PNG files):
   - `<repo-root>/v1.0/models/causal_graphs/visualizations/{metric}_dag.png`
   - Hierarchical layout, directed edges

3. **Effect Visualizations** (3 PNG files):
   - `<repo-root>/v1.0/models/causal_graphs/visualizations/{metric}_effects.png`
   - Top 10 drivers with confidence intervals

4. **Inter-Metric Graph**:
   - `<repo-root>/v1.0/models/causal_graphs/visualizations/inter_metric_graph.png`
   - Network diagram showing spillover paths

## SUCCESS CRITERIA

- [ ] Validation report shows PASS status
- [ ] All 5 validation tests pass:
  - [ ] DAG acyclicity (all 3 metrics)
  - [ ] Effect sign consistency (CI doesn't cross zero for significant effects)
  - [ ] Effect magnitude reasonableness (|effect| < 2.0)
  - [ ] Literature alignment (≥70% sign match)
  - [ ] Simulation reasonableness (no 100%+ effects from 10% intervention)
- [ ] 6 visualizations generated (3 DAGs + 3 effect plots + 1 inter-metric)
- [ ] Visualizations are publication-quality (300 DPI, clear labels)

## INTEGRATION NOTES

### Handoff to Module 4.8
- If validation PASS → proceed to extend to all 8 metrics
- If validation FAIL → review and fix issues before extension

### Handoff to Phase 6
- Visualizations used in dashboard "Causal Discovery" tab
- Validation report displayed in "Data Quality" section

## ERROR HANDLING

### Common Issues

1. **Cycles Detected in DAG**:
   - Cause: PC algorithm failed to orient all edges
   - Solution: Use FCI algorithm (handles latent confounders) or manually break cycles

2. **Low Literature Alignment (<50%)**:
   - Cause: Discovered relationships contradict theory
   - Investigation: Check for data errors, verify feature definitions

3. **Graphviz Layout Fails**:
   - Cause: Graphviz not installed or PATH issue
   - Solution: Fallback to `nx.spring_layout(G)`

## ESTIMATED RUNTIME
**30 minutes** (10 min validation tests, 20 min visualizations)

## DEPENDENCIES
- All Modules 4.1-4.6 must complete successfully

## PRIORITY
**MEDIUM** - Quality assurance before full-scale extension

## REFERENCES
- Tufte, E. R. (2001). *The Visual Display of Quantitative Information* (2nd ed.). Graphics Press.
- Wilkinson, L. (2005). *The Grammar of Graphics* (2nd ed.). Springer.
