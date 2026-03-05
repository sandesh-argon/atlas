# MODULE 4.5: Causal Effect Quantification

## OBJECTIVE
Quantify causal effects of discovered drivers on QOL metrics using backdoor adjustment, compute bootstrapped confidence intervals, and validate effect signs/magnitudes against development economics literature.

## CONTEXT
Modules 4.2-4.3 identified *which* features causally affect QOL metrics (graph structure). Module 4.5 quantifies *how much* each driver affects the outcome. This uses Pearl's backdoor criterion: to estimate the causal effect of X on Y, regress Y on X while controlling for confounders (features that affect both X and Y). Bootstrapping provides 95% confidence intervals for policy-relevant questions: "A 10% increase in health expenditure causes infant mortality to decrease by X% [95% CI: Y%, Z%]."

## INPUTS

### From Module 4.3
- **VIF-Filtered Drivers**: `<repo-root>/v1.0/models/causal_graphs/tier1/vif_filtering_results.json`
  - Top 15-18 non-collinear drivers per metric
- **Refined Causal Graphs**: `<repo-root>/v1.0/models/causal_graphs/tier1/{metric}_pc_refined.pkl`

### From Module 4.1
- **Training Data**: `<repo-root>/v1.0/models/causal_graphs/loaded_training_data.pkl`
- **SHAP Importance**: For ranking drivers

### Configuration
- **Bootstrap Iterations**: 1,000 (standard for 95% CI)
- **Confidence Level**: 95% (2.5th-97.5th percentile)
- **Significance Threshold**: CI must not cross zero for "significant" effect

## TASK DIRECTIVE

### Step 1: Implement Backdoor Adjustment

**Script**: `phase4_quantify_effects.py`

Create causal effect estimation function:

```python
from sklearn.linear_model import LinearRegression
import numpy as np
import pandas as pd

def estimate_causal_effect_backdoor(X, y, treatment_feature, confounder_features, n_bootstrap=1000):
    """
    Estimate causal effect using backdoor adjustment with bootstrapped CI.

    Backdoor Criterion (Pearl, 2009):
    To estimate causal effect of T on Y, control for confounders Z:

    P(Y | do(T=t)) = Σ_z P(Y | T=t, Z=z) P(Z=z)

    In linear case: Regress Y ~ T + Z, coefficient of T is causal effect.

    Parameters:
    -----------
    X : pd.DataFrame
        Feature matrix (must include treatment + confounders)
    y : pd.Series
        Target variable
    treatment_feature : str
        Feature to estimate causal effect for
    confounder_features : List[str]
        Features to control for (backdoor set)
    n_bootstrap : int
        Bootstrap iterations for CI

    Returns:
    --------
    causal_effect : float
        Estimated causal effect (regression coefficient)
    ci_lower : float
        2.5th percentile (lower bound of 95% CI)
    ci_upper : float
        97.5th percentile (upper bound of 95% CI)
    p_value : float
        Two-tailed p-value (H0: effect = 0)
    """
    # Prepare data
    features = [treatment_feature] + confounder_features
    X_adjusted = X[features].copy()
    y_clean = y.copy()

    # Remove NaN
    valid_idx = X_adjusted.notna().all(axis=1) & y_clean.notna()
    X_adjusted = X_adjusted[valid_idx]
    y_clean = y_clean[valid_idx]

    # Point estimate
    model = LinearRegression()
    model.fit(X_adjusted, y_clean)
    causal_effect = model.coef_[0]  # Coefficient of treatment feature

    # Bootstrap confidence interval
    bootstrap_effects = []
    n_samples = len(X_adjusted)

    for _ in range(n_bootstrap):
        # Resample with replacement
        boot_idx = np.random.choice(n_samples, n_samples, replace=True)
        X_boot = X_adjusted.iloc[boot_idx]
        y_boot = y_clean.iloc[boot_idx]

        # Fit model
        model_boot = LinearRegression()
        model_boot.fit(X_boot, y_boot)
        bootstrap_effects.append(model_boot.coef_[0])

    # Compute CI
    ci_lower = np.percentile(bootstrap_effects, 2.5)
    ci_upper = np.percentile(bootstrap_effects, 97.5)

    # Compute p-value (two-tailed)
    # H0: effect = 0
    # p = 2 * min(P(effect < 0), P(effect > 0))
    p_negative = np.mean(np.array(bootstrap_effects) < 0)
    p_positive = np.mean(np.array(bootstrap_effects) > 0)
    p_value = 2 * min(p_negative, p_positive)

    return causal_effect, ci_lower, ci_upper, p_value
```

### Step 2: Select Confounders (Backdoor Set)

For each driver, identify confounders from VIF-filtered features:

**Confounder Selection Strategy**:
1. Use all other VIF-retained features as potential confounders
2. Exclude features that are descendants of the treatment (would introduce collider bias)
3. For simplicity: Use top-10 VIF-retained features (excluding treatment itself)

**Alternative (Advanced)**: Use causal graph to identify minimal backdoor set
- Requires PC graph from Module 4.3
- Find all backdoor paths from treatment to target
- Include only features that block those paths

### Step 3: Quantify Effects for All Drivers

**Script**: `phase4_run_effect_quantification.py`

```python
import pickle
import json
import pandas as pd
from datetime import datetime

# Load data
with open('<repo-root>/v1.0/models/causal_graphs/tier1/vif_filtering_results.json') as f:
    vif_results = json.load(f)

with open('<repo-root>/v1.0/models/causal_graphs/loaded_training_data.pkl', 'rb') as f:
    training_data = pickle.load(f)

TIER1_METRICS = ['mean_years_schooling', 'infant_mortality', 'undernourishment']
N_BOOTSTRAP = 1000

causal_effects_all = {}

for metric in TIER1_METRICS:
    print(f"\n{'='*60}")
    print(f"Quantifying Causal Effects: {metric}")
    print(f"{'='*60}")

    # Get VIF-retained drivers
    retained_features = vif_results[metric]['retained_features']

    # Load data
    df = training_data[metric].dropna()
    y = df[metric]

    metric_effects = {}

    # Quantify effect for top 10 drivers
    for i, treatment_feature in enumerate(retained_features[:10]):
        # Confounders: Other top-10 features (excluding treatment)
        confounders = [f for f in retained_features[:10] if f != treatment_feature]

        # Estimate causal effect
        start_time = datetime.now()
        effect, ci_lower, ci_upper, p_value = estimate_causal_effect_backdoor(
            df, y, treatment_feature, confounders, n_bootstrap=N_BOOTSTRAP
        )
        runtime = (datetime.now() - start_time).total_seconds()

        # Check significance (CI doesn't cross zero)
        significant = (ci_lower * ci_upper > 0)

        metric_effects[treatment_feature] = {
            'causal_effect': float(effect),
            'ci_lower': float(ci_lower),
            'ci_upper': float(ci_upper),
            'p_value': float(p_value),
            'significant': significant,
            'confounders': confounders,
            'samples_used': int(df.shape[0]),
            'bootstrap_iterations': N_BOOTSTRAP,
            'runtime_seconds': runtime
        }

        # Print results
        sig_marker = "✓" if significant else "✗"
        print(f"{sig_marker} {treatment_feature}")
        print(f"    Effect: {effect:.4f} [95% CI: {ci_lower:.4f}, {ci_upper:.4f}]")
        print(f"    p-value: {p_value:.4f}")

    causal_effects_all[metric] = metric_effects

# Save results
with open('<repo-root>/v1.0/models/causal_graphs/tier1/causal_effects_quantified.json', 'w') as f:
    json.dump(causal_effects_all, f, indent=2)

# Create summary CSV for each metric
for metric, effects in causal_effects_all.items():
    effect_df = pd.DataFrame([
        {
            'feature': feat,
            'causal_effect': data['causal_effect'],
            'ci_lower': data['ci_lower'],
            'ci_upper': data['ci_upper'],
            'p_value': data['p_value'],
            'significant': data['significant']
        }
        for feat, data in effects.items()
    ])

    # Sort by absolute effect size
    effect_df['abs_effect'] = effect_df['causal_effect'].abs()
    effect_df = effect_df.sort_values('abs_effect', ascending=False)

    effect_df.to_csv(
        f'<repo-root>/v1.0/models/causal_graphs/tier1/{metric}_causal_effects.csv',
        index=False
    )

print("\n" + "="*60)
print("Causal Effect Quantification Complete")
print("="*60)
```

### Step 4: Literature Validation

**Script**: `phase4_literature_validation.py`

Compare discovered relationships to known findings:

```python
# Known relationships from development economics literature
LITERATURE_RELATIONSHIPS = {
    'mean_years_schooling': {
        'gdp_per_capita_lag3': {
            'expected_sign': '+',
            'expected_magnitude': '0.05-0.15',
            'source': 'Barro & Lee (2013) - Education and Economic Growth'
        },
        'government_expenditure_education_lag2': {
            'expected_sign': '+',
            'expected_magnitude': '0.10-0.25',
            'source': 'Hanushek & Woessmann (2012) - School Resources'
        }
    },
    'infant_mortality': {
        'health_expenditure_gdp_lag2': {
            'expected_sign': '-',
            'expected_magnitude': '0.15-0.35',
            'source': 'Anand & Ravallion (1993) - Public Health Spending'
        },
        'physicians_per_1000_lag3': {
            'expected_sign': '-',
            'expected_magnitude': '0.10-0.30',
            'source': 'Fink et al. (2011) - Health Workforce and Mortality'
        }
    },
    'undernourishment': {
        'agricultural_productivity_lag2': {
            'expected_sign': '-',
            'expected_magnitude': '0.20-0.40',
            'source': 'FAO (2015) - Food Security and Agriculture'
        },
        'rural_development_index_lag3': {
            'expected_sign': '-',
            'expected_magnitude': '0.15-0.30',
            'source': 'IFAD (2016) - Rural Poverty and Hunger'
        }
    }
}

# Load quantified effects
with open('<repo-root>/v1.0/models/causal_graphs/tier1/causal_effects_quantified.json') as f:
    causal_effects = json.load(f)

validation_results = {}

for metric, lit_relationships in LITERATURE_RELATIONSHIPS.items():
    print(f"\n{metric} Literature Validation:")
    metric_validation = {}

    for feature, lit_data in lit_relationships.items():
        if feature in causal_effects.get(metric, {}):
            discovered = causal_effects[metric][feature]

            # Check sign consistency
            discovered_sign = '+' if discovered['causal_effect'] > 0 else '-'
            sign_match = (discovered_sign == lit_data['expected_sign'])

            # Check significance
            is_significant = discovered['significant']

            # Report
            if sign_match and is_significant:
                status = "✓ CONSISTENT"
            elif sign_match and not is_significant:
                status = "~ SIGN MATCHES (not significant)"
            else:
                status = "✗ CONTRADICTS"

            print(f"  {status}: {feature}")
            print(f"    Literature: {lit_data['expected_sign']} ({lit_data['expected_magnitude']})")
            print(f"    Discovered: {discovered_sign} ({discovered['causal_effect']:.3f})")
            print(f"    Source: {lit_data['source']}")

            metric_validation[feature] = {
                'sign_match': sign_match,
                'is_significant': is_significant,
                'discovered_effect': discovered['causal_effect'],
                'literature_source': lit_data['source']
            }
        else:
            print(f"  ? NOT FOUND: {feature}")

    validation_results[metric] = metric_validation

# Save validation report
with open('<repo-root>/v1.0/models/causal_graphs/tier1/literature_validation.json', 'w') as f:
    json.dump(validation_results, f, indent=2)
```

## OUTPUTS

### Primary Outputs

1. **Quantified Causal Effects**: `<repo-root>/v1.0/models/causal_graphs/tier1/causal_effects_quantified.json`
   - For each metric: {feature: {effect, ci_lower, ci_upper, p_value, significant}}
   - Bootstrap iterations: 1,000
   - Confidence level: 95%

2. **Effect Summary CSV** (per metric):
   - `<repo-root>/v1.0/models/causal_graphs/tier1/{metric}_causal_effects.csv`
   - Columns: [feature, causal_effect, ci_lower, ci_upper, p_value, significant]

3. **Literature Validation**: `<repo-root>/v1.0/models/causal_graphs/tier1/literature_validation.json`
   - Sign consistency with published research
   - Sources for each validated relationship

## SUCCESS CRITERIA

- [ ] Causal effects quantified for top 10 drivers per metric (30 total)
- [ ] 95% confidence intervals computed via bootstrap (1,000 iterations)
- [ ] 60-80% of effects are statistically significant (CI doesn't cross zero)
- [ ] Effect signs match theoretical expectations (e.g., health spending → lower mortality)
- [ ] Magnitudes are reasonable (effect sizes 0.01-0.50 for normalized data)
- [ ] Literature validation: 70%+ consistency with published findings

### Expected Effect Patterns

**Infant Mortality** (negative effects expected):
- health_expenditure_lag2: -0.15 to -0.35 (more spending → lower mortality)
- physicians_per_1000_lag3: -0.10 to -0.30 (more doctors → lower mortality)
- water_sanitation_access_lag2: -0.20 to -0.40 (clean water → lower mortality)

**Mean Years Schooling** (positive effects expected):
- gdp_per_capita_lag3: +0.05 to +0.15 (wealth → more education)
- education_expenditure_lag2: +0.10 to +0.25 (spending → schooling)

**Undernourishment** (negative effects expected):
- agricultural_productivity_lag2: -0.20 to -0.40 (food production → less hunger)
- gdp_per_capita_lag3: -0.10 to -0.25 (wealth → better nutrition)

## INTEGRATION NOTES

### Handoff to Module 4.6 (Policy Simulator)
- Quantified effects become input to do-calculus
- Confidence intervals enable uncertainty quantification in simulations
- Effect dictionary structure: `{metric: {driver: {effect, ci_lower, ci_upper}}}`

### Interpretation Guide
- **Effect = 0.20**: 1 standard deviation increase in driver → 0.20 SD increase in outcome
- **After denormalization**: Convert to real-world units (e.g., $1,000 GDP increase → X years life expectancy)

## ERROR HANDLING

### Common Issues

1. **Wide Confidence Intervals (CI width > 0.5)**:
   - Cause: High variance in bootstrap samples
   - Solution: Increase bootstrap iterations to 5,000 or check for outliers

2. **Counterintuitive Signs** (e.g., health spending → higher mortality):
   - Cause: Omitted variable bias or reverse causality
   - Solution: Check confounders, verify temporal ordering

3. **All Effects Non-Significant**:
   - Cause: Insufficient statistical power or weak true effects
   - Solution: Increase sample size or relax significance threshold (90% CI)

## VALIDATION CHECKS

```python
# Verify effect reasonableness
with open('<repo-root>/v1.0/models/causal_graphs/tier1/causal_effects_quantified.json') as f:
    effects = json.load(f)

for metric, drivers in effects.items():
    significant_count = sum(1 for d in drivers.values() if d['significant'])
    total_count = len(drivers)

    print(f"{metric}: {significant_count}/{total_count} significant effects ({significant_count/total_count:.1%})")

    # Check effect magnitudes
    for feature, data in drivers.items():
        if abs(data['causal_effect']) > 1.0:
            print(f"  ⚠ Large effect: {feature} = {data['causal_effect']:.3f}")
```

## ESTIMATED RUNTIME
**30 minutes** (10 min per metric for 10 drivers × 1,000 bootstrap iterations)

## DEPENDENCIES
- Module 4.3 (VIF Refinement) must complete successfully
- Module 4.1 (Setup) for training data

## PRIORITY
**HIGH** - Provides quantitative inputs for policy simulation

## REFERENCES
- Pearl, J. (2009). *Causality: Models, Reasoning, and Inference* (2nd ed.). Cambridge University Press. (Backdoor criterion)
- Efron, B., & Tibshirani, R. J. (1994). *An Introduction to the Bootstrap*. Chapman & Hall/CRC.
- Angrist, J. D., & Pischke, J. S. (2009). *Mostly Harmless Econometrics*. Princeton University Press. (Causal inference in economics)
