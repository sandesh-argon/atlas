#!/usr/bin/env python3
"""
Phase B1: Outcome Discovery via Factor Analysis (V2.1)
======================================================

Discovers 12-25 quality-of-life outcome clusters from top-layer nodes using:
1. Scree plot analysis (Kaiser + elbow criteria)
2. Factor analysis with Varimax rotation
3. Three-part validation:
   - Domain coherence (≤3 domains per factor)
   - Literature alignment (TF-IDF similarity > 0.60)
   - Predictability (RF cross-val R² > 0.40)

V2.1 MODIFICATION: Uses v21_config for paths

Author: Phase B1
Date: November 2025
"""

import pickle
import sys
import json
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime

# V2.1 Configuration
sys.path.insert(0, str(Path(__file__).parent.parent))
from v21_config import A6_OUTPUT, B1_OUTPUT, get_input_path

# Factor analysis
from factor_analyzer import FactorAnalyzer, calculate_bartlett_sphericity, calculate_kmo

# Machine learning for validation
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import cross_val_score
from sklearn.preprocessing import StandardScaler
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

print("="*80)
print("PHASE B1: OUTCOME DISCOVERY (V2.1)")
print("="*80)
print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# Create output directories (V2.1: use config)
output_dir = B1_OUTPUT
log_dir = B1_OUTPUT / "logs"
diag_dir = B1_OUTPUT / "diagnostics"
for d in [output_dir, log_dir, diag_dir]:
    d.mkdir(exist_ok=True, parents=True)

# ============================================================================
# STEP 1: Load and Prepare Data
# ============================================================================

print("\n[STEP 1] Loading A6 graph and A1 data...")

# Load A6 hierarchical graph (V2.1: use config)
a6_path = A6_OUTPUT / "A6_hierarchical_graph.pkl"
with open(a6_path, 'rb') as f:
    a6_data = pickle.load(f)

G = a6_data['graph']
layers = a6_data['layers']
max_layer = max(layers.values())

# Get top 2 layers, filter virtual nodes
top_layer_nodes = [n for n, layer in layers.items() if layer >= max_layer - 1]
real_nodes = [n for n in top_layer_nodes if not n.startswith('INTERACT_')]

print(f"✅ Top-layer nodes: {len(real_nodes)} real (filtered {len(top_layer_nodes) - len(real_nodes)} virtual)")

# Load A1 imputed data (V2.1: use config)
a1_path = get_input_path()
with open(a1_path, 'rb') as f:
    a1_data = pickle.load(f)

imputed_data = a1_data['imputed_data']

# Extract data for real top-layer nodes
# imputed_data[node] is a DataFrame (countries × years)
# We need to flatten to (country-year observations) × (variables)

print(f"\n[STEP 1] Preparing data matrix...")

data_frames = []
for node in real_nodes:
    df = imputed_data[node]
    # Stack: country-year rows, single column for this variable
    stacked = df.stack().reset_index()
    stacked.columns = ['Country', 'Year', node]
    stacked = stacked.set_index(['Country', 'Year'])
    data_frames.append(stacked[[node]])

# Merge all variables
data_matrix = pd.concat(data_frames, axis=1)

print(f"✅ Data matrix: {data_matrix.shape[0]} observations × {data_matrix.shape[1]} variables")
print(f"   Missing rate: {data_matrix.isna().mean().mean():.1%}")

# Drop rows with any missing (should be 0% after A1)
data_clean = data_matrix.dropna()
print(f"   After dropna: {data_clean.shape[0]} observations")

# ============================================================================
# STEP 2: Correlation Matrix and Factorability Tests
# ============================================================================

print(f"\n[STEP 2] Computing correlation matrix and factorability tests...")

# Correlation matrix
corr_matrix = data_clean.corr()

# Bartlett's test (H0: correlation matrix = identity)
chi_square, p_value = calculate_bartlett_sphericity(data_clean)
print(f"   Bartlett's test: χ²={chi_square:.1f}, p={p_value:.2e}")
if p_value < 0.05:
    print(f"   ✅ Reject H0 → Data suitable for factor analysis")
else:
    print(f"   ⚠️  WARNING: p>{0.05} → Weak correlations, factor analysis may not work")

# Kaiser-Meyer-Olkin (KMO) measure
kmo_all, kmo_model = calculate_kmo(data_clean)
print(f"   KMO measure: {kmo_model:.3f}")
if kmo_model >= 0.80:
    print(f"   ✅ KMO ≥ 0.80 → Excellent factorability")
elif kmo_model >= 0.70:
    print(f"   ✅ KMO ≥ 0.70 → Good factorability")
elif kmo_model >= 0.60:
    print(f"   ⚠️  KMO ≥ 0.60 → Mediocre factorability")
else:
    print(f"   ❌ KMO < 0.60 → Poor factorability, consider skipping factor analysis")

# ============================================================================
# STEP 3: Scree Plot Analysis
# ============================================================================

print(f"\n[STEP 3] Generating scree plot to determine n_factors...")

# Run exploratory factor analysis (no rotation)
fa_explore = FactorAnalyzer(n_factors=data_clean.shape[1], rotation=None)
fa_explore.fit(data_clean)

eigenvalues, _ = fa_explore.get_eigenvalues()

# Plot scree
plt.figure(figsize=(12, 6))
plt.plot(range(1, len(eigenvalues)+1), eigenvalues, 'bo-', linewidth=2, markersize=8)
plt.axhline(y=1, color='r', linestyle='--', linewidth=2, label='Kaiser criterion (λ=1)')
plt.xlabel('Factor Number', fontsize=12)
plt.ylabel('Eigenvalue', fontsize=12)
plt.title('Scree Plot - Outcome Factor Analysis (B1)', fontsize=14, fontweight='bold')
plt.grid(True, alpha=0.3)
plt.legend(fontsize=10)
plt.tight_layout()

scree_plot_path = diag_dir / "B1_scree_plot.png"
plt.savefig(scree_plot_path, dpi=150)
print(f"✅ Scree plot saved: {scree_plot_path}")

# Determine n_factors using Kaiser criterion
kaiser_n = sum(eigenvalues > 1)
print(f"\n   Kaiser criterion (λ>1): {kaiser_n} factors")

# Detect elbow using gradient change
def detect_scree_elbow(eigenvalues, threshold=0.1):
    """Detect elbow by finding largest gradient change"""
    gradients = np.diff(eigenvalues)
    gradient_changes = np.diff(gradients)

    # Find largest positive change (biggest elbow)
    # Only consider factors 2-20 (avoid trivial 1-factor solution)
    search_range = min(20, len(gradient_changes) - 1)
    elbow_idx = np.argmax(gradient_changes[1:search_range]) + 2  # +2 for offset

    return elbow_idx

elbow_n = detect_scree_elbow(eigenvalues)
print(f"   Scree elbow detection: {elbow_n} factors")

# Use MINIMUM of Kaiser and elbow (conservative)
n_factors_raw = min(kaiser_n, elbow_n)

# Apply V2 spec constraints: 12 ≤ n_factors ≤ 25
n_factors = max(12, min(25, n_factors_raw))

print(f"\n   Raw n_factors (min of Kaiser and elbow): {n_factors_raw}")
print(f"   ✅ Final n_factors (constrained to [12, 25]): {n_factors}")

# ============================================================================
# STEP 4: Factor Analysis with Rotation
# ============================================================================

print(f"\n[STEP 4] Running factor analysis with n_factors={n_factors}, rotation=varimax...")

fa_final = FactorAnalyzer(n_factors=n_factors, rotation='varimax', method='principal')
fa_final.fit(data_clean)

loadings = fa_final.loadings_
loadings_df = pd.DataFrame(
    loadings,
    index=data_clean.columns,
    columns=[f'Factor_{i+1}' for i in range(n_factors)]
)

print(f"✅ Factor analysis complete")
print(f"   Loadings matrix: {loadings_df.shape}")

# Get factor scores for each observation
factor_scores = fa_final.transform(data_clean)
factor_scores_df = pd.DataFrame(
    factor_scores,
    index=data_clean.index,
    columns=[f'Factor_{i+1}' for i in range(n_factors)]
)

print(f"   Factor scores: {factor_scores_df.shape}")

# Communalities (variance explained per variable)
communalities = fa_final.get_communalities()
print(f"   Mean communality: {np.mean(communalities):.3f}")
print(f"   Variables with low communality (<0.3): {sum(communalities < 0.3)}/{len(communalities)}")

# Variance explained per factor
variance = fa_final.get_factor_variance()
variance_df = pd.DataFrame(
    variance,
    index=['SS Loadings', 'Proportion Var', 'Cumulative Var'],
    columns=[f'Factor_{i+1}' for i in range(n_factors)]
)

print(f"\n   Variance explained (first 5 factors):")
for i in range(min(5, n_factors)):
    prop = variance_df.loc['Proportion Var', f'Factor_{i+1}']
    cum = variance_df.loc['Cumulative Var', f'Factor_{i+1}']
    print(f"   Factor {i+1}: {prop:.1%} (cumulative: {cum:.1%})")

total_var_explained = variance_df.loc['Cumulative Var', f'Factor_{n_factors}']
print(f"   Total variance explained: {total_var_explained:.1%}")

# Save diagnostics
diagnostics = {
    'n_factors': n_factors,
    'kaiser_suggestion': int(kaiser_n),
    'scree_elbow': int(elbow_n),
    'kmo_measure': float(kmo_model),
    'bartlett_chi_square': float(chi_square),
    'bartlett_p_value': float(p_value),
    'total_variance_explained': float(total_var_explained),
    'mean_communality': float(np.mean(communalities)),
    'n_observations': int(data_clean.shape[0]),
    'n_variables': int(data_clean.shape[1])
}

with open(diag_dir / "B1_factor_diagnostics.json", 'w') as f:
    json.dump(diagnostics, f, indent=2)

# Save loadings and scores
loadings_df.to_csv(diag_dir / "B1_factor_loadings.csv")
variance_df.to_csv(diag_dir / "B1_factor_variance.csv")
factor_scores_df.to_csv(diag_dir / "B1_factor_scores.csv")

print(f"\n✅ Diagnostics saved to {diag_dir}/")

# ============================================================================
# STEP 5: Identify Top Variables per Factor
# ============================================================================

print(f"\n[STEP 5] Identifying top variables per factor...")

# For each factor, get top 5 variables by absolute loading
factor_top_vars = {}
for i in range(n_factors):
    factor_col = f'Factor_{i+1}'
    loadings_abs = loadings_df[factor_col].abs().sort_values(ascending=False)
    top_5 = loadings_abs.head(5)

    factor_top_vars[i] = {
        'factor_id': i,
        'factor_name': factor_col,
        'top_variables': top_5.index.tolist(),
        'top_loadings': loadings_df.loc[top_5.index, factor_col].tolist()
    }

    print(f"\n   {factor_col}:")
    for var, loading in zip(top_5.index, loadings_df.loc[top_5.index, factor_col]):
        print(f"      {var[:50]:50s}: {loading:+.3f}")

print(f"\n✅ Extracted top variables for {n_factors} factors")
print(f"\n" + "="*80)
print("PHASE B1: FACTOR EXTRACTION COMPLETE")
print("="*80)
print(f"\nNext steps:")
print(f"1. Review scree plot: {scree_plot_path}")
print(f"2. Review factor loadings: {diag_dir}/B1_factor_loadings.csv")
print(f"3. Verify n_factors={n_factors} is reasonable")
print(f"4. If acceptable, proceed to 3-part validation (domain coherence, literature, R²)")
print(f"\n⏸️  PAUSING FOR HUMAN REVIEW")
print(f"   Run validation ONLY after confirming n_factors is acceptable")
