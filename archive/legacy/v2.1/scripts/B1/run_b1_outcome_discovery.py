#!/usr/bin/env python3
"""
B1: Outcome Discovery (V2.1 - Hybrid Approach)
==============================================

Try data-driven factor analysis first, fallback to theory-driven if uninterpretable.

STRATEGY:
1. Run factor analysis on ALL 1,962 indicators (not just top layer)
2. Check interpretability of each factor (domain coherence + loading strength)
3. If ≥7/9 interpretable: Use data-driven outcomes
4. If <7/9 interpretable: Fallback to theory-driven outcomes (HDI-style)

INTERPRETABILITY CRITERIA:
- Domain coherence: ≥70% of top 10 indicators from same domain
- Loading strength: ≥50% of top 10 loadings > 0.5

Author: Phase B1 V2.1
Date: December 2025
"""

import pickle
import json
import sys
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime
from collections import Counter

# V2.1 Configuration
sys.path.insert(0, str(Path(__file__).parent.parent))
from v21_config import A6_OUTPUT, B1_OUTPUT, get_input_path

# Machine learning
from sklearn.decomposition import FactorAnalysis
from sklearn.preprocessing import StandardScaler

output_dir = B1_OUTPUT
output_dir.mkdir(exist_ok=True, parents=True)

print("=" * 80)
print("B1: OUTCOME DISCOVERY (V2.1 - Hybrid Approach)")
print("=" * 80)

start_time = datetime.now()
print(f"Start time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")

# ============================================================================
# THEORY-DRIVEN FALLBACK DEFINITIONS
# ============================================================================

THEORY_OUTCOMES = {
    1: {'name': 'Health', 'keywords': ['life_expectancy', 'mortality', 'health', 'SH.', 'life.expect', 'death']},
    2: {'name': 'Education', 'keywords': ['education', 'school', 'literacy', 'SE.', 'enrollment', 'attainment']},
    3: {'name': 'Income', 'keywords': ['gdp', 'income', 'gni', 'NY.GDP', 'NY.GNP', 'capita']},
    4: {'name': 'Inequality', 'keywords': ['gini', 'inequality', 'palma', 'share', 'poverty', 'SI.POV']},
    5: {'name': 'Safety', 'keywords': ['homicide', 'crime', 'violence', 'conflict', 'security']},
    6: {'name': 'Governance', 'keywords': ['democracy', 'corruption', 'v2x', 'rule_of_law', 'v2', 'polity']},
    7: {'name': 'Infrastructure', 'keywords': ['internet', 'electricity', 'water', 'sanitation', 'EG.ELC', 'SH.H2O']},
    8: {'name': 'Employment', 'keywords': ['unemployment', 'labor', 'employment', 'SL.', 'workforce']},
    9: {'name': 'Environment', 'keywords': ['air', 'pollution', 'forest', 'emission', 'EN.', 'co2', 'carbon']}
}

# Domain classification keywords (for interpretability check)
DOMAIN_KEYWORDS = {
    'Education': ['SE.', 'education', 'school', 'literacy', 'enrollment', 'attainment', 'pupil', 'teacher'],
    'Health': ['SH.', 'health', 'mortality', 'life.expect', 'disease', 'medical', 'birth', 'death', 'immuniz'],
    'Economic': ['NY.', 'gdp', 'gni', 'income', 'trade', 'export', 'import', 'FI.', 'BX.', 'BM.'],
    'Governance': ['v2', 'democracy', 'corruption', 'polity', 'electoral', 'executive', 'judicial', 'rule'],
    'Infrastructure': ['EG.', 'IT.', 'electricity', 'internet', 'mobile', 'transport', 'road'],
    'Environment': ['EN.', 'emission', 'forest', 'pollution', 'climate', 'carbon', 'co2'],
    'Social': ['SP.', 'population', 'gender', 'poverty', 'SI.', 'inequality', 'gini'],
    'Security': ['VC.', 'conflict', 'homicide', 'violence', 'crime', 'military']
}

# ============================================================================
# STEP 1: Load Data
# ============================================================================

print("\n[STEP 1/4] Loading A6 graph and indicator data...")

# Load A6 graph
a6_path = A6_OUTPUT / "A6_hierarchical_graph.pkl"
with open(a6_path, 'rb') as f:
    a6_data = pickle.load(f)

G = a6_data['graph']
layers = a6_data['layers']
all_nodes = list(G.nodes())

print(f"   Loaded graph: {len(all_nodes)} nodes, {G.number_of_edges()} edges")

# Load imputed data
input_path = get_input_path()
with open(input_path, 'rb') as f:
    data = pickle.load(f)

imputed_data = data['imputed_data']
print(f"   Loaded imputed data: {len(imputed_data)} indicators")

# Build indicator matrix (countries × indicators)
print("\n   Building indicator matrix...")

indicator_dfs = []
valid_nodes = []

for node in all_nodes:
    if node in imputed_data:
        df = imputed_data[node]
        # Average over years for each country
        country_avg = df.mean(axis=1)  # Average across years
        indicator_dfs.append(country_avg)
        valid_nodes.append(node)

if len(indicator_dfs) == 0:
    print("   ERROR: No matching indicators found!")
    sys.exit(1)

indicator_matrix = pd.DataFrame(indicator_dfs).T  # Countries × Indicators
indicator_matrix.columns = valid_nodes

print(f"   Indicator matrix: {indicator_matrix.shape[0]} countries × {indicator_matrix.shape[1]} indicators")
print(f"   Missing rate: {indicator_matrix.isna().mean().mean():.1%}")

# Standardize
scaler = StandardScaler()
X_filled = indicator_matrix.fillna(indicator_matrix.mean())
X_scaled = scaler.fit_transform(X_filled)

print(f"   ✅ Data prepared for factor analysis")

# ============================================================================
# STEP 2: Data-Driven Factor Analysis
# ============================================================================

print("\n[STEP 2/4] Running data-driven factor analysis...")

N_FACTORS = 9

try:
    fa = FactorAnalysis(n_components=N_FACTORS, random_state=42, max_iter=1000)
    factor_scores = fa.fit_transform(X_scaled)
    factor_loadings = fa.components_

    print(f"   ✅ Factor analysis complete")
    print(f"   Factor loadings shape: {factor_loadings.shape}")

    fa_success = True

except Exception as e:
    print(f"   ❌ Factor analysis failed: {e}")
    fa_success = False

# ============================================================================
# STEP 3: Check Interpretability
# ============================================================================

print("\n[STEP 3/4] Checking factor interpretability...")

def classify_indicator_domain(indicator_name):
    """Classify an indicator into a domain based on keywords"""
    indicator_lower = indicator_name.lower()

    for domain, keywords in DOMAIN_KEYWORDS.items():
        for kw in keywords:
            if kw.lower() in indicator_lower:
                return domain

    return 'Other'

def check_interpretability(factor_idx, loadings, node_names):
    """Check if a factor is interpretable"""

    # Get top 10 indicators by absolute loading
    abs_loadings = np.abs(loadings[factor_idx])
    top_10_idx = np.argsort(abs_loadings)[-10:][::-1]  # Descending order
    top_10_indicators = [node_names[i] for i in top_10_idx]
    top_10_loadings = [loadings[factor_idx][i] for i in top_10_idx]

    # Classify domains
    domains = [classify_indicator_domain(ind) for ind in top_10_indicators]

    # Check 1: Domain coherence (≥70% same domain)
    domain_counts = Counter(domains)
    max_domain_count = max(domain_counts.values())
    max_domain_pct = max_domain_count / len(domains)
    dominant_domain = domain_counts.most_common(1)[0][0]

    # Check 2: High loadings (≥50% loadings > 0.5)
    high_loadings_count = sum(1 for l in top_10_loadings if abs(l) > 0.5)
    high_loading_pct = high_loadings_count / len(top_10_loadings)

    # Interpretable if both checks pass
    is_interpretable = (max_domain_pct >= 0.7) and (high_loading_pct >= 0.5)

    return {
        'interpretable': is_interpretable,
        'domain_coherence': max_domain_pct,
        'high_loading_pct': high_loading_pct,
        'dominant_domain': dominant_domain,
        'domain_distribution': dict(domain_counts),
        'top_indicators': list(zip(top_10_indicators, [float(l) for l in top_10_loadings]))
    }

interpretability_results = []
interpretable_count = 0

if fa_success:
    for i in range(N_FACTORS):
        result = check_interpretability(i, factor_loadings, valid_nodes)
        interpretability_results.append(result)

        if result['interpretable']:
            interpretable_count += 1

        status = "✅" if result['interpretable'] else "❌"
        print(f"   {status} Factor {i+1}: {result['dominant_domain']:12s} "
              f"(coherence={result['domain_coherence']:.0%}, "
              f"loadings={result['high_loading_pct']:.0%})")

    print(f"\n   Interpretable factors: {interpretable_count}/9")
else:
    print("   ⚠️  Skipping interpretability check (factor analysis failed)")

# ============================================================================
# STEP 4: Decision - Use Data-Driven or Theory-Driven
# ============================================================================

print("\n[STEP 4/4] Outcome selection decision...")

INTERPRETABILITY_THRESHOLD = 7

if fa_success and interpretable_count >= INTERPRETABILITY_THRESHOLD:
    print(f"\n   ✅ Using DATA-DRIVEN outcomes ({interpretable_count}/9 interpretable)")
    outcome_type = 'data_driven'

    # Build outcomes from factor analysis
    outcomes = {}
    outcome_indicators = []

    for i, result in enumerate(interpretability_results):
        factor_name = f"Factor_{i+1}_{result['dominant_domain']}"
        top_inds = [ind for ind, _ in result['top_indicators']]

        outcomes[i+1] = {
            'name': factor_name,
            'type': 'factor_analysis',
            'interpretable': result['interpretable'],
            'dominant_domain': result['dominant_domain'],
            'domain_coherence': result['domain_coherence'],
            'top_indicators': top_inds[:10],
            'loadings': result['top_indicators'][:10]
        }

        # Add top 5 indicators to outcome list
        outcome_indicators.extend(top_inds[:5])

    # Remove duplicates
    outcome_indicators = list(set(outcome_indicators))

else:
    reason = "not enough interpretable" if fa_success else "factor analysis failed"
    print(f"\n   ⚠️  Using THEORY-DRIVEN outcomes ({reason})")
    outcome_type = 'theory_driven'

    # Fallback to predefined outcomes
    outcomes = {}
    outcome_indicators = []

    for i, outcome_def in THEORY_OUTCOMES.items():
        # Find matching indicators
        matching = []
        for node in valid_nodes:
            node_lower = node.lower()
            if any(kw.lower() in node_lower for kw in outcome_def['keywords']):
                matching.append(node)

        # Also check by domain from graph layers
        if len(matching) < 5:
            # Add high-layer nodes from this domain
            for node in valid_nodes:
                layer = layers.get(node, 0)
                if layer >= 15 and node not in matching:  # Top 30% of layers
                    node_domain = classify_indicator_domain(node)
                    if node_domain == outcome_def['name'] or outcome_def['name'] in node_domain:
                        matching.append(node)

        outcomes[i] = {
            'name': outcome_def['name'],
            'type': 'theory_driven',
            'keywords': outcome_def['keywords'],
            'indicator_count': len(matching),
            'top_indicators': matching[:10]
        }

        # Add top 5 to outcome list
        outcome_indicators.extend(matching[:5])

    # Remove duplicates
    outcome_indicators = list(set(outcome_indicators))

print(f"\n   Total outcome indicators for SHAP: {len(outcome_indicators)}")

# ============================================================================
# OUTPUT
# ============================================================================

print("\n[OUTPUT] Saving results...")

results = {
    'outcome_type': outcome_type,
    'n_outcomes': N_FACTORS,
    'outcomes': outcomes,
    'outcome_indicators': outcome_indicators,
    'interpretability_check': {
        'fa_success': fa_success,
        'interpretable_count': interpretable_count,
        'total_factors': N_FACTORS,
        'threshold': INTERPRETABILITY_THRESHOLD,
        'results': interpretability_results if fa_success else []
    },
    'metadata': {
        'timestamp': datetime.now().isoformat(),
        'total_graph_nodes': len(all_nodes),
        'valid_nodes_for_fa': len(valid_nodes),
        'indicator_matrix_shape': list(indicator_matrix.shape),
    }
}

# Save pickle
pkl_path = output_dir / "B1_validated_outcomes.pkl"
with open(pkl_path, 'wb') as f:
    pickle.dump(results, f)
print(f"   ✅ Saved: {pkl_path}")

# Save JSON summary
json_output = {
    'outcome_type': outcome_type,
    'interpretable_count': interpretable_count,
    'threshold': INTERPRETABILITY_THRESHOLD,
    'n_outcomes': N_FACTORS,
    'total_outcome_indicators': len(outcome_indicators),
    'outcomes': {
        str(k): {
            'name': v['name'],
            'type': v['type'],
            'top_5_indicators': v['top_indicators'][:5] if 'top_indicators' in v else []
        }
        for k, v in outcomes.items()
    }
}

json_path = output_dir / "B1_outcome_summary.json"
with open(json_path, 'w') as f:
    json.dump(json_output, f, indent=2)
print(f"   ✅ Saved: {json_path}")

# ============================================================================
# SUMMARY
# ============================================================================

elapsed = (datetime.now() - start_time).total_seconds()

print("\n" + "=" * 80)
print("B1 OUTCOME DISCOVERY COMPLETE")
print("=" * 80)

print(f"""
Summary:
   Outcome type: {outcome_type.upper()}
   Interpretable factors: {interpretable_count}/9
   Threshold: {INTERPRETABILITY_THRESHOLD}

   Decision: {"DATA-DRIVEN ✅" if outcome_type == 'data_driven' else "THEORY-DRIVEN ⚠️"}

   Total outcome indicators: {len(outcome_indicators)}
   Runtime: {elapsed:.1f} seconds

Outcome Factors:
""")

for i, outcome in outcomes.items():
    name = outcome['name']
    n_ind = len(outcome.get('top_indicators', []))
    status = "✅" if outcome.get('interpretable', True) else "⚠️"
    print(f"   {status} {i}. {name}: {n_ind} indicators")

print(f"""
Output files:
   - {pkl_path}
   - {json_path}

Next step: Run B2 (semantic clustering)
""")
