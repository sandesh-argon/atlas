#!/usr/bin/env python3
"""
Phase B1: 3-Part Outcome Validation
====================================

Validates discovered factors against:
1. Domain coherence (≤3 domains per factor)
2. Literature alignment (TF-IDF similarity > 0.60)
3. Predictability (RF cross-val R² > 0.40)

Author: Phase B1
Date: November 2025
"""

import pickle
import sys
import json
from pathlib import Path
import pandas as pd
import numpy as np
from datetime import datetime
from collections import Counter

# Machine learning
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import cross_val_score
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# Add project root to path
project_root = Path(__file__).resolve().parents[3]  # Go up to v2.0/ directory
sys.path.insert(0, str(project_root))

print("="*80)
print("PHASE B1: 3-PART VALIDATION")
print("="*80)
print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# Directories
b1_dir = Path(__file__).resolve().parent.parent  # B1_outcome_discovery directory
diag_dir = b1_dir / "diagnostics"
output_dir = b1_dir / "outputs"
log_dir = b1_dir / "logs"

# ============================================================================
# STEP 1: Load Factor Analysis Results
# ============================================================================

print("\n[STEP 1] Loading factor analysis results...")

# Load factor loadings
loadings_df = pd.read_csv(diag_dir / "B1_factor_loadings.csv", index_col=0)
print(f"✅ Loaded factor loadings: {loadings_df.shape}")

# Load factor scores
factor_scores_df = pd.read_csv(diag_dir / "B1_factor_scores.csv", index_col=[0, 1])
print(f"✅ Loaded factor scores: {factor_scores_df.shape}")

# Load diagnostics
with open(diag_dir / "B1_factor_diagnostics.json", 'r') as f:
    diagnostics = json.load(f)

n_factors = diagnostics['n_factors']
print(f"✅ Number of factors: {n_factors}")

# Load literature database
lit_db_path = project_root / "literature_db/literature_constructs.json"
with open(lit_db_path, 'r') as f:
    literature_db = json.load(f)

print(f"✅ Loaded literature database: {len(literature_db)} known constructs")

# Load A1 data for domain mapping
a1_path = project_root / "phaseA/A1_missingness_analysis/outputs/A2_preprocessed_data.pkl"
with open(a1_path, 'rb') as f:
    a1_data = pickle.load(f)

# Get indicator metadata if available
if 'metadata' in a1_data and 'indicator_sources' in a1_data['metadata']:
    indicator_metadata = a1_data['metadata']['indicator_sources']
    print(f"✅ Loaded indicator metadata: {len(indicator_metadata)} indicators")
else:
    print("⚠️  No indicator metadata found - will use heuristic domain mapping")
    indicator_metadata = {}

# ============================================================================
# STEP 2: Domain Coherence Validation
# ============================================================================

print("\n[STEP 2] Validating domain coherence (≤3 domains per factor)...")

def infer_domain_from_name(indicator_name):
    """Infer domain from indicator name using prefixes and keywords"""
    indicator_lower = indicator_name.lower()

    # V-Dem indicators (v2*)
    if indicator_name.startswith('v2'):
        return 'Governance'

    # World Bank indicators
    if any(indicator_lower.startswith(prefix) for prefix in ['wdi_', 'wb_', 'ny.gdp', 'sp.pop', 'sh.', 'se.']):
        if 'mort' in indicator_lower or 'health' in indicator_lower or 'sh.' in indicator_lower:
            return 'Health'
        elif 'educ' in indicator_lower or 'school' in indicator_lower or 'se.' in indicator_lower:
            return 'Education'
        elif 'gdp' in indicator_lower or 'income' in indicator_lower or 'poverty' in indicator_lower:
            return 'Economic'
        elif 'pop' in indicator_lower or 'birth' in indicator_lower or 'fertility' in indicator_lower:
            return 'Demographic'
        else:
            return 'Economic'  # Default for World Bank

    # OECD/Penn indicators
    if any(indicator_lower.startswith(prefix) for prefix in ['ger.', 'ner.', 'oaep', 'repr.']):
        if 'repr' in indicator_lower or 'mort' in indicator_lower:
            return 'Health'
        elif 'ger' in indicator_lower or 'ner' in indicator_lower:
            return 'Education'
        else:
            return 'Demographic'

    # IMF/taxation indicators (*xi999, *di999)
    if indicator_name.endswith('xi999') or indicator_name.endswith('di999'):
        return 'Economic'

    # Keyword-based mapping
    if 'mort' in indicator_lower or 'health' in indicator_lower or 'disease' in indicator_lower:
        return 'Health'
    elif 'educ' in indicator_lower or 'school' in indicator_lower or 'literacy' in indicator_lower:
        return 'Education'
    elif 'gdp' in indicator_lower or 'income' in indicator_lower or 'tax' in indicator_lower or 'poverty' in indicator_lower:
        return 'Economic'
    elif 'democr' in indicator_lower or 'gov' in indicator_lower or 'polit' in indicator_lower:
        return 'Governance'
    elif 'environ' in indicator_lower or 'emiss' in indicator_lower or 'climat' in indicator_lower:
        return 'Environment'
    elif 'inequal' in indicator_lower or 'gini' in indicator_lower:
        return 'Inequality'

    # Default
    return 'Unknown'

def get_indicator_domain(indicator_name):
    """Get domain for indicator (from metadata or heuristic)"""
    if indicator_name in indicator_metadata:
        return indicator_metadata[indicator_name].get('domain', infer_domain_from_name(indicator_name))
    else:
        return infer_domain_from_name(indicator_name)

# Validate domain coherence for each factor
domain_coherence_results = []

for i in range(n_factors):
    factor_col = f'Factor_{i+1}'

    # Get top 5 variables by absolute loading
    top_vars = loadings_df[factor_col].abs().sort_values(ascending=False).head(5)

    # Get domains for top variables
    domains = [get_indicator_domain(var) for var in top_vars.index]
    domain_counts = Counter(domains)

    # Count unique domains (excluding 'Unknown')
    unique_domains = [d for d in domain_counts.keys() if d != 'Unknown']
    n_unique_domains = len(unique_domains)

    # Check if ≤3 domains
    passes_coherence = n_unique_domains <= 3 and n_unique_domains > 0

    result = {
        'factor_id': i,
        'factor_name': factor_col,
        'top_variables': top_vars.index.tolist(),
        'domains': domains,
        'domain_counts': {k: int(v) for k, v in domain_counts.items()},  # Convert numpy.int64 to int
        'n_unique_domains': n_unique_domains,
        'primary_domain': domain_counts.most_common(1)[0][0] if domain_counts else 'Unknown',
        'passes_coherence': passes_coherence
    }

    domain_coherence_results.append(result)

    # Print result
    status = "✅ PASS" if passes_coherence else "❌ FAIL"
    print(f"\n   {factor_col}: {status}")
    print(f"      Primary domain: {result['primary_domain']}")
    print(f"      Unique domains: {n_unique_domains} ({', '.join(unique_domains)})")
    print(f"      Top variables:")
    for var, domain in zip(top_vars.index[:3], domains[:3]):
        print(f"         - {var[:50]:50s} [{domain}]")

# Summary
n_passed_coherence = sum(r['passes_coherence'] for r in domain_coherence_results)
print(f"\n   ✅ Domain coherence: {n_passed_coherence}/{n_factors} factors passed (≤3 domains)")

# ============================================================================
# STEP 3: Literature Alignment Validation
# ============================================================================

print("\n[STEP 3] Validating literature alignment (TF-IDF similarity > 0.60)...")

# Prepare literature corpus
lit_corpus = []
lit_construct_names = []

for construct_name, construct_data in literature_db.items():
    # Combine keywords and typical indicators
    text = ' '.join(construct_data['keywords'] + construct_data.get('typical_indicators', []))
    lit_corpus.append(text)
    lit_construct_names.append(construct_name)

# Fit TF-IDF vectorizer on literature corpus
vectorizer = TfidfVectorizer(max_features=200)
lit_tfidf = vectorizer.fit_transform(lit_corpus)

# Validate literature alignment for each factor
literature_alignment_results = []

for i, domain_result in enumerate(domain_coherence_results):
    factor_col = domain_result['factor_name']
    top_vars = domain_result['top_variables']

    # Create factor "document" from top variable names
    factor_text = ' '.join(top_vars)

    # Transform to TF-IDF
    factor_tfidf = vectorizer.transform([factor_text])

    # Compute cosine similarity to all literature constructs
    similarities = cosine_similarity(factor_tfidf, lit_tfidf)[0]

    # Get best match
    best_match_idx = np.argmax(similarities)
    best_match_construct = lit_construct_names[best_match_idx]
    best_match_similarity = similarities[best_match_idx]

    # Check if ≥0.60
    passes_literature = best_match_similarity >= 0.60

    result = {
        **domain_result,  # Include domain coherence results
        'best_match_construct': best_match_construct,
        'best_match_similarity': float(best_match_similarity),
        'passes_literature': passes_literature,
        'is_novel': not passes_literature  # Novel if no good match
    }

    literature_alignment_results.append(result)

    # Print result
    status = "✅ PASS" if passes_literature else "⚠️  NOVEL"
    print(f"\n   {factor_col}: {status}")
    print(f"      Best match: {best_match_construct} (similarity: {best_match_similarity:.3f})")
    if not passes_literature:
        print(f"      ⚠️  Novel factor (no literature match >0.60)")

# Summary
n_passed_literature = sum(r['passes_literature'] for r in literature_alignment_results)
n_novel = sum(r['is_novel'] for r in literature_alignment_results)
print(f"\n   ✅ Literature alignment: {n_passed_literature}/{n_factors} factors matched (≥0.60)")
print(f"   ⚠️  Novel factors: {n_novel}/{n_factors} (will require R²>0.40 for validation)")

# ============================================================================
# STEP 4: Predictability Validation (Random Forest Cross-Val)
# ============================================================================

print("\n[STEP 4] Validating predictability (RF cross-val R² > 0.40)...")
print("   (This may take 10-20 minutes for 12 factors...)")

# Load original data matrix
a6_path = project_root / "phaseA/A6_hierarchical_layering/outputs/A6_hierarchical_graph.pkl"
with open(a6_path, 'rb') as f:
    a6_data = pickle.load(f)

layers = a6_data['layers']
max_layer = max(layers.values())
top_layer_nodes = [n for n, layer in layers.items() if layer >= max_layer - 1]
real_nodes = [n for n in top_layer_nodes if not n.startswith('INTERACT_')]

# Reconstruct data matrix (same as factor analysis)
imputed_data = a1_data['imputed_data']
data_frames = []
for node in real_nodes:
    df = imputed_data[node]
    stacked = df.stack().reset_index()
    stacked.columns = ['Country', 'Year', node]
    stacked = stacked.set_index(['Country', 'Year'])
    data_frames.append(stacked[[node]])

data_matrix = pd.concat(data_frames, axis=1).dropna()

# Validate predictability for each factor
predictability_results = []

for i, lit_result in enumerate(literature_alignment_results):
    factor_col = lit_result['factor_name']
    top_vars = lit_result['top_variables']

    # Get factor scores (target)
    y = factor_scores_df[factor_col].values

    # Get top variables (features)
    X = data_matrix[top_vars].values

    # Train Random Forest with cross-validation
    rf = RandomForestRegressor(
        n_estimators=100,
        max_depth=10,
        min_samples_split=20,
        random_state=42,
        n_jobs=6  # Thermal safety
    )

    # 5-fold cross-validation
    cv_scores = cross_val_score(rf, X, y, cv=5, scoring='r2', n_jobs=1)  # Sequential CV
    mean_r2 = np.mean(cv_scores)
    std_r2 = np.std(cv_scores)

    # Check if ≥0.40
    passes_predictability = mean_r2 >= 0.40

    result = {
        **lit_result,  # Include previous results
        'predictability_r2_mean': float(mean_r2),
        'predictability_r2_std': float(std_r2),
        'passes_predictability': passes_predictability
    }

    predictability_results.append(result)

    # Print result
    status = "✅ PASS" if passes_predictability else "❌ FAIL"
    print(f"\n   {factor_col}: {status}")
    print(f"      R² = {mean_r2:.3f} ± {std_r2:.3f}")

# Summary
n_passed_predictability = sum(r['passes_predictability'] for r in predictability_results)
print(f"\n   ✅ Predictability: {n_passed_predictability}/{n_factors} factors predicted (R²≥0.40)")

# ============================================================================
# STEP 5: Overall Validation Summary
# ============================================================================

print("\n" + "="*80)
print("VALIDATION SUMMARY")
print("="*80)

# Determine overall pass/fail
final_results = []
for result in predictability_results:
    # Factor passes if:
    # - Domain coherence: ✅
    # - Literature: ✅ OR (Novel + Predictability ✅)
    # - Predictability: ✅

    passes_overall = (
        result['passes_coherence'] and
        result['passes_predictability'] and
        (result['passes_literature'] or result['is_novel'])  # Novel factors need R²>0.40
    )

    final_result = {
        **result,
        'passes_overall': passes_overall
    }
    final_results.append(final_result)

# Count passes
n_passed_overall = sum(r['passes_overall'] for r in final_results)

print(f"\n✅ OVERALL: {n_passed_overall}/{n_factors} factors validated")
print(f"\nBreakdown:")
print(f"   Domain coherence: {n_passed_coherence}/{n_factors} passed")
print(f"   Literature match: {n_passed_literature}/{n_factors} passed")
print(f"   Novel factors: {n_novel}/{n_factors}")
print(f"   Predictability: {n_passed_predictability}/{n_factors} passed")

# Detailed results
print(f"\nDetailed results:")
for r in final_results:
    status = "✅" if r['passes_overall'] else "❌"
    novelty = "(NOVEL)" if r['is_novel'] else ""
    print(f"   {status} {r['factor_name']:10s}: {r['primary_domain']:15s} | "
          f"Lit={r['best_match_similarity']:.2f} {novelty:8s} | R²={r['predictability_r2_mean']:.2f}")

# Save validation results
validation_output = {
    'metadata': {
        'timestamp': datetime.now().isoformat(),
        'n_factors': n_factors,
        'n_passed_overall': n_passed_overall,
        'n_passed_coherence': n_passed_coherence,
        'n_passed_literature': n_passed_literature,
        'n_novel': n_novel,
        'n_passed_predictability': n_passed_predictability
    },
    'factors': final_results
}

# Create validated outcomes checkpoint (SAVE PKL FIRST - doesn't require JSON serialization)
validated_outcomes = [r for r in final_results if r['passes_overall']]

checkpoint = {
    'outcomes': validated_outcomes,
    'metadata': validation_output['metadata'],
    'diagnostics': diagnostics
}

with open(output_dir / "B1_validated_outcomes.pkl", 'wb') as f:
    pickle.dump(checkpoint, f)

print(f"\n✅ Validated outcomes checkpoint saved: {output_dir}/B1_validated_outcomes.pkl")

# Try to save JSON (may fail due to numpy types, but PKL is already saved)
try:
    with open(output_dir / "B1_validation_results.json", 'w') as f:
        json.dump(validation_output, f, indent=2)
    print(f"✅ Validation results saved: {output_dir}/B1_validation_results.json")
except TypeError as e:
    print(f"⚠️ WARNING: Could not save JSON due to numpy types: {e}")
    print(f"   (PKL file saved successfully - JSON is optional)")

print(f"✅ Validated outcomes checkpoint saved: {output_dir}/B1_validated_outcomes.pkl")

# Final verdict
print("\n" + "="*80)
if n_passed_overall >= 10:
    print("🎉 EXCELLENT: ≥10 factors validated - Phase B1 SUCCESS")
elif n_passed_overall >= 8:
    print("✅ GOOD: 8-9 factors validated - Phase B1 acceptable, proceed to B2")
elif n_passed_overall >= 6:
    print("⚠️  MARGINAL: 6-7 factors validated - Consider re-running with n=9 (Kaiser)")
else:
    print("❌ INSUFFICIENT: <6 factors validated - Re-run with n=9 or investigate data")

print("="*80)
