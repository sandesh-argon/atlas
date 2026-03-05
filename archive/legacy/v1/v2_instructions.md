V2 Research Specification: Global Causal Discovery System
Bottom-Up Network Reconstruction with Validated Interpretability

Executive Summary
Philosophy Evolution:
V1: Top-down (8 pre-selected outcomes → find drivers)
V2: Hybrid bottom-up (discover causal network → validate outcome clusters against known QOL constructs)
Critical V1 Lessons Integrated:
Granger prefiltering prevents network sparsity crisis (6.2M → 200K tests)
Factor interpretability validation prevents junk dimensions
Realistic compute estimates with parallelization strategy
Progressive disclosure dashboard for academic credibility
Two-Phase Approach:
Phase A (Statistical): Extract validated causal signal with efficient filtering
Phase B (Interpretability): Apply validated clustering/pruning for multi-level visualization
Target Outputs:
Research: 2,000-8,000 node validated causal network with full documentation
Visualization: 300-800 node network (Level 3) + simplified 50-node view (Levels 4-5)
Paper: Development economics journal-ready with methodological rigor
Dashboard: 5-level progressive disclosure system with academic citation capability

# BEFORE Phase A, create literature reference database
LITERATURE_DB = {
    'health_outcomes': {
        'keywords': ['mortality', 'morbidity', 'life expectancy', 'disease'],
        'canonical_papers': [
            'Preston (1975) - mortality-income relationship',
            'Bloom et al. (2004) - health and economic growth',
            'Deaton (2003) - health, inequality, and development'
        ],
        'typical_indicators': ['infant_mortality', 'life_expectancy', 'u5_mortality']
    },
    'education_outcomes': {
        'keywords': ['schooling', 'literacy', 'enrollment', 'attainment'],
        'canonical_papers': [
            'Barro (1991) - education and growth',
            'Hanushek & Woessmann (2012) - education quality',
            'Psacharopoulos & Patrinos (2018) - returns to education'
        ],
        'typical_indicators': ['years_schooling', 'completion_rates', 'test_scores']
    },
    # ... 8 more known constructs
}

def find_best_matching_construct(top_variables, known_constructs, literature_db):
    """
    Uses TF-IDF similarity between variable descriptions and construct keywords.
    Returns: {'label': 'health_outcomes', 'confidence': 0.87}
    """
    # 1. Extract variable descriptions
    descriptions = [get_variable_full_description(var) for var in top_variables]
    
    # 2. Compute TF-IDF similarity to each construct's keywords
    from sklearn.feature_extraction.text import TfidfVectorizer
    vectorizer = TfidfVectorizer()
    
    similarities = {}
    for construct, metadata in literature_db.items():
        construct_text = ' '.join(metadata['keywords'])
        corpus = descriptions + [construct_text]
        tfidf_matrix = vectorizer.fit_transform(corpus)
        
        # Cosine similarity between variables and construct
        from sklearn.metrics.pairwise import cosine_similarity
        sim = cosine_similarity(tfidf_matrix[:-1], tfidf_matrix[-1:]).mean()
        similarities[construct] = sim
    
    best_match = max(similarities, key=similarities.get)
    confidence = similarities[best_match]
    
    return {'label': best_match, 'confidence': confidence}


Phase A: Statistical Network Discovery
A0: Data Acquisition
Sources (All Free/Signup):
Source
Indicators
Access
Priority
World Bank WDI + Poverty
~2,040
wbgapi
Essential
WHO GHO
~2,000
API
Essential
UNESCO UIS
~200
API
Essential
UNICEF
~300
API
High
V-Dem
~450
Download
High
QoG Institute
~2,000
Download
High
IMF IFS
~800
API
Medium
OECD.Stat
~1,200
Signup
Medium
Penn World Tables
~180
Download
Medium
World Inequality DB
~150
API
Medium
Transparency Intl
~30
Download
Low
Total
~9,350





Initial Filter (Permissive but Realistic):
python
keep if:
    country_coverage >= 80 countries AND
    temporal_span >= 10 years AND
    per_country_temporal_coverage >= 0.80 AND  # V1 lesson: within-country density matters
    missing_rate <= 0.70  # Relaxed from V1's 0.60 for broader coverage
Expected: 5,000-6,000 variables
Temporal Window Selection:
python
# Test windows: 1960-2024, 1970-2024, 1980-2024, 1990-2024, 2000-2024
# Select earliest window where:
#   - mean_missing < 0.40 AND
#   - n_vars > 4000 AND
#   - n_countries > 150

# Likely result: 1990-2024 (34 years, ~200 countries)

A1: Missingness Sensitivity Analysis
Parallel Experiment Grid:
python
thresholds = [0.30, 0.40, 0.50, 0.60, 0.70]  # Reduced from 7 to 5 for efficiency
strategies = ["listwise", "linear_interpolation", "KNN_k5", "MICE_linear", "MICE_RF"]

# 25 parallel pipelines (manageable vs. 35)
V1-Validated Imputation Weighting:
python
# Apply confidence weights to imputed values (V1 Phase 2 success)
def apply_imputation_weights(value, method, original_missing_rate):
    """V1 proved this prevents false signal from heavy imputation"""
    if method == "observed":
        return value * 1.0
    elif method in ["linear_interpolation", "KNN_k5"]:
        return value * 0.85  # Tier 2
    elif method in ["MICE_linear", "MICE_RF"]:
        if original_missing_rate < 0.40:
            return value * 0.70  # Tier 3
        else:
            return value * 0.50  # Tier 4
Evaluation per config:
python
# Multi-criteria scoring (V1 validated weights)
score = (
    0.25 * coverage_score +           # # variables surviving
    0.30 * stability_score +          # Bootstrap correlation of graph structure
    0.25 * interpretability_score +   # % edges with known mechanisms
    0.20 * predictive_score           # Mean R² on held-out countries
)

best_config = argmax(score)
Validation Checkpoint:
python
assert 3500 <= n_variables_survived <= 6000, "Coverage collapse or no filtering"
assert stability_score > 0.70, "Unstable under resampling"
assert mean_r2_holdout > 0.45, "Worse than V1's worst metric (R²=0.49)"
Expected: 4,000-5,000 variables, optimal missing threshold ~0.45-0.55

A2: Granger Causality with Intelligent Prefiltering
CRITICAL FIX: Prevent Network Sparsity Crisis
python
# V1 Lesson: Testing all 6.2M pairs creates uninterpretable dense graphs
# Solution: Multi-stage prefiltering before Granger tests

def prefilter_candidate_pairs(var_X, var_Y, data, literature_db):
    """
    Reduces 6.2M potential pairs to 200K-500K plausible candidates
    V1 Phase 3 Approach C validated this logic
    """
    
    # Stage 1: Correlation threshold (weak relationships unlikely causal)
    pearson_r = correlation(var_X, var_Y)
    if abs(pearson_r) < 0.10:
        return False, "correlation_too_weak"
    
    # Stage 2: Multicollinearity check (likely measuring same construct)
    if abs(pearson_r) > 0.95:
        return False, "autocorrelation_proxy"
    
    # Stage 3: Domain compatibility matrix
PLAUSIBLE_CONNECTIONS = {
    ('Health', 'Education'): True,      # Well-documented
    ('Health', 'Economic'): True,       # Income → health
    ('Economic', 'Governance'): True,   # Institutions → growth
    ('Environment', 'Trade'): False,    # Implausible direct link
    ('Technology', 'Security'): False,  # No known mechanism
    # ... define 13×13=169 domain pairs
}

def domains_plausibly_connected(domain_X, domain_Y):
    """
    Returns True if domains have documented causal pathways
    in development economics literature.
    
    Conservative: If unsure, return True (filter later in A3).
    """
    return PLAUSIBLE_CONNECTIONS.get((domain_X, domain_Y), True)

    
    # Stage 4: Temporal precedence possible
    # (V1 Phase 3: Critical for removing "GDP causes GDP_lag1" nonsense)
    if is_same_indicator_lagged(var_X, var_Y):
        return False, "self_lagged"
    
    # Stage 5: Literature plausibility check
    # Keep if: (a) documented in literature OR (b) novel but theoretically plausible
    if not (in_literature(var_X, var_Y, literature_db) or 
            theoretically_plausible(var_X, var_Y)):
        return False, "implausible_mechanism"
    
    return True, "candidate_approved"

# Apply prefiltering
candidate_pairs = []
for X, Y in combinations(variables, 2):
    approved, reason = prefilter_candidate_pairs(X, Y, data, lit_db)
    if approved:
        candidate_pairs.append((X, Y))

# Expected reduction: 5000*(5000-1)/2 = 12.5M → 200K-500K pairs (98% reduction)
print(f"Prefiltering: {12.5M} → {len(candidate_pairs)} pairs ({len(candidate_pairs)/12.5M:.1%} retained)")
Granger Testing on Filtered Candidates:
python
lags = [1, 2, 3, 5]  # T-1 through T-5
n_tests = len(candidate_pairs) * len(lags) * 2  # Both directions
# ~200K pairs * 4 lags * 2 directions = 1.6M tests (vs 120M unfiltered)

# False Discovery Rate correction (more powerful than Bonferroni for large-scale tests)
from statsmodels.stats.multitest import multipletests

p_values = []
for X, Y, lag in all_combinations(candidate_pairs, lags):
    p = granger_test(X, Y, lag, data)
    p_values.append(p)

# FDR correction at q=0.05 (expect 5% false positives among discoveries)
reject, p_adjusted, _, _ = multipletests(p_values, alpha=0.05, method='fdr_bh')

validated_edges = [(X, Y, lag) for (X, Y, lag), r in zip(test_combinations, reject) if r]
Bidirectional Edge Handling:
python
# If both X→Y and Y→X significant, flag for expert review
bidirectional = [(X, Y) for X, Y in validated_edges 
                 if (Y, X) in validated_edges]

# Likely causes: feedback loops (GDP ↔ education) or unmeasured confounders
# Keep both directions but mark for A3 conditional independence test
Expected: 30,000-80,000 edges (manageable vs. 6.2M)
Validation Checkpoint:
python
assert 10_000 <= len(validated_edges) <= 100_000, "Edge count unrealistic"
assert mean(p_adjusted) < 0.01, "Too many weak relationships survived"
assert len(bidirectional) / len(validated_edges) < 0.15, "Excessive feedback loops"

A3: Conditional Independence (Remove Spurious Correlations)
Method: PC-Stable algorithm with Granger priors
python
from causallearn.search.ConstraintBased.PC import pc

# Use Granger results to inform edge orientation
background_knowledge = convert_granger_to_temporal_tiers(validated_edges)

causal_graph = pc(
    data,
    alpha=0.001,  # Stricter than A2 (removes residual spurious correlations)
    indep_test='fisherz',
    stable=True,  # Order-independent (critical for reproducibility)
    background_knowledge=background_knowledge,  # Temporal precedence from Granger
    uc_rule=1,  # Conservative orientation
    uc_priority=3  # Prioritize background knowledge
)

# Keep only edges validated by BOTH Granger AND conditional independence
final_edges = granger_edges ∩ pc_edges
Early Stopping for Computational Efficiency:
python
# If edge count exceeds interpretability threshold, switch to score-based method
if len(causal_graph.edges) > 50_000:
    print("⚠️  Graph too dense for PC-Stable, switching to GES")
    from causallearn.search.ScoreBased.GES import ges
    causal_graph = ges(data, score_func='local_score_BIC')
Backdoor Set Identification:
python
from causallearn.utils.DAG2CPDAG import dag2cpdag
from dowhy import CausalModel

for (X, Y) in final_edges:
    model = CausalModel(
        data=data,
        treatment=X,
        outcome=Y,
        graph=causal_graph
    )
    
    adjustment_set = model.identify_effect(proceed_when_unidentifiable=False)
    
    if adjustment_set is None:
        print(f"⚠️  Cannot identify causal effect {X}→{Y}, removing edge")
        final_edges.remove((X, Y))
    else:
        backdoor_sets[(X, Y)] = adjustment_set
Expected: 10,000-30,000 validated edges with adjustment sets
Validation Checkpoint:
python
import networkx as nx
G = nx.DiGraph(final_edges)

assert nx.is_directed_acyclic_graph(G), "❌ CYCLES DETECTED - INVALID CAUSAL GRAPH"
largest_component = max(nx.weakly_connected_components(G), key=len)
assert len(largest_component) / len(G.nodes) > 0.80, "Graph too fragmented"

A4: Effect Size Quantification with Bootstrap Validation
Backdoor Adjustment Regression:
python
from sklearn.linear_model import LinearRegression
from scipy.stats import zscore

effect_estimates = []

for (X, Y), Z in backdoor_sets.items():
    # Standardize for interpretable effect sizes
    X_std = zscore(data[X])
    Y_std = zscore(data[Y])
    Z_std = zscore(data[Z])
    
    # Regression: Y ~ X + Z (controlling for confounders)
    model = LinearRegression()
    model.fit(np.column_stack([X_std, Z_std]), Y_std)
    beta = model.coef_[0]  # Effect of X on Y
    
    # Bootstrap 95% CI (1000 iterations)
    bootstrap_betas = []
    for _ in range(1000):
        sample_idx = resample(range(len(data)), replace=True)
        boot_model = LinearRegression()
        boot_model.fit(
            np.column_stack([X_std[sample_idx], Z_std[sample_idx]]),
            Y_std[sample_idx]
        )
        bootstrap_betas.append(boot_model.coef_[0])
    
    ci_lower, ci_upper = np.percentile(bootstrap_betas, [2.5, 97.5])
    
    # V1 threshold: abs(beta) > 0.1 for meaningful effects
    # V2: Slightly stricter for cleaner graph
    if abs(beta) > 0.12 and ci_lower * ci_upper > 0:  # CI doesn't cross zero
        effect_estimates.append({
            'source': X,
            'target': Y,
            'beta': beta,
            'ci': [ci_lower, ci_upper],
            'se': np.std(bootstrap_betas),
            'backdoor_set': Z
        })
Expected: 2,000-8,000 validated causal edges with quantified effects
Validation Checkpoint:
python
assert 2000 <= len(effect_estimates) <= 10000, "Network too sparse or too dense"
assert np.mean([abs(e['beta']) for e in effect_estimates]) > 0.15, "Weak effects dominate"
assert all(e['ci'][0] * e['ci'][1] > 0 for e in effect_estimates), "CIs cross zero"

A5: Interaction Discovery (Constrained Search)
V1 Lesson: Don't test all 12M interactions blindly
python
# Constraint 1: Only test interactions between mechanisms that passed A4
mechanism_nodes = [e['source'] for e in effect_estimates 
                   if centrality_score(e['source']) > percentile_75]

# Constraint 2: Only test for effects on high-priority outcomes
priority_outcomes = get_priority_outcomes()  # Will define in B1

# Reduced search space: ~500 mechanisms * 500 mechanisms * 8 outcomes
# = 2M tests (vs 12M for all pairs)

interaction_effects = []

for X, Y in combinations(mechanism_nodes, 2):
    for outcome in priority_outcomes:
        # Model 1: outcome ~ X + Y + confounders
        # Model 2: outcome ~ X + Y + X*Y + confounders
        
        confounders = get_confounders(X, Y, outcome, backdoor_sets)
        
        model1 = fit_regression(outcome, [X, Y] + confounders, data)
        model2 = fit_regression(outcome, [X, Y, f'{X}_x_{Y}'] + confounders, data)
        
        # Likelihood ratio test
        lr_stat = -2 * (model1.loglikelihood - model2.loglikelihood)
        p_value = chi2.sf(lr_stat, df=1)
        
        interaction_coef = model2.coef_[f'{X}_x_{Y}']
        
        if p_value < 0.001 and abs(interaction_coef) > 0.15:
            interaction_effects.append({
                'mechanism': f'{X}_x_{Y}',
                'outcome': outcome,
                'beta': interaction_coef,
                'p': p_value,
                'main_effects': {'X': model2.coef_[X], 'Y': model2.coef_[Y]}
            })
Expected: 50-200 validated interaction mechanisms
Validation Checkpoint:
python
# V1 validation: health_x_education → life_expectancy had β=1.366
known_interactions = [
    ('physicians_per_1000', 'secondary_enrollment', 'life_expectancy'),
    ('gdp_per_capita', 'governance_quality', 'infant_mortality'),
    # ... other literature-validated interactions
]

reproduced = sum(1 for known in known_interactions 
                 if known in [i['mechanism'].split('_x_') + [i['outcome']] 
                             for i in interaction_effects])

assert reproduced / len(known_interactions) > 0.60, "Failed to reproduce known synergies"

A6: Hierarchical Layer Assignment
Data-Driven Topological Depth:
python
import networkx as nx

G = nx.DiGraph()
G.add_edges_from([(e['source'], e['target']) for e in effect_estimates])

# Assign layers via topological sort
layer_assignment = {}

for node in nx.topological_sort(G):
    predecessors = list(G.predecessors(node))
    
    if len(predecessors) == 0:
        # Root cause (no incoming edges)
        layer_assignment[node] = 0
    else:
        # Layer = max parent layer + 1
        layer_assignment[node] = max(layer_assignment[p] for p in predecessors) + 1

# Compute centrality measures for mechanism identification (Phase B)
betweenness = nx.betweenness_centrality(G)
pagerank = nx.pagerank(G)

node_metadata = []
for node in G.nodes():
    node_metadata.append({
        'node_id': node,
        'layer': layer_assignment[node],
        'in_degree': G.in_degree(node),
        'out_degree': G.out_degree(node),
        'betweenness': betweenness[node],
        'pagerank': pagerank[node]
    })
Expected: 4-8 layers depending on graph structure
Validation Checkpoint:
python
assert 4 <= max(layer_assignment.values()) <= 10, "Hierarchy too flat or too deep"
assert all(layer_assignment[e['target']] > layer_assignment[e['source']] 
           for e in effect_estimates), "Layer order violated"

Phase B: Validated Interpretability Layer
B1: Outcome Discovery with Validation
Hybrid Approach (V1 Lessons + V2 Discovery):
python
# Start with V1's validated 8 QOL metrics
v1_outcomes = [
    'life_expectancy', 'years_schooling', 'gdp_per_capita', 
    'infant_mortality', 'gini_index', 'homicide_rate',
    'nutrition_index', 'internet_access'
]

# Identify all leaf nodes (candidates for outcome status)
leaf_nodes = [n for n in G.nodes() if G.out_degree(n) == 0]

# Exploratory Factor Analysis on leaf nodes
from factor_analyzer import FactorAnalyzer

fa = FactorAnalyzer(n_factors=None, rotation='varimax')
fa.fit(data[leaf_nodes])

eigenvalues, _ = fa.get_eigenvalues()
n_factors = sum(eigenvalues > 1)  # Kaiser criterion

# Extract factor loadings
loadings = fa.loadings_

# CRITICAL: Validate each discovered factor
validated_factors = []

for i in range(n_factors):
    factor_loadings = loadings[:, i]
    top_vars = [leaf_nodes[j] for j in np.argsort(np.abs(factor_loadings))[-10:]]
    
    validation_result = validate_factor(
        factor_index=i,
        top_variables=top_vars,
        loadings=factor_loadings,
        data=data,
        literature_db=literature_db
    )
    
    if validation_result['status'] == 'ACCEPT':
        validated_factors.append({
            'factor_id': i,
            'label': validation_result['suggested_label'],
            'top_vars': top_vars,
            'eigenvalue': eigenvalues[i],
            'variance_explained': eigenvalues[i] / sum(eigenvalues)
        })

def validate_factor(factor_index, top_variables, loadings, data, literature_db):
    """
    Three-part validation (from Confidence Assessment doc):
    1. Domain coherence check
    2. Literature alignment check  
    3. Predictability check
    """
    
    # Check 1: Domain coherence
    domains = [get_domain(var) for var in top_variables]
    unique_domains = len(set(domains))
    
    if unique_domains > 3:
        return {'status': 'REJECT', 'reason': 'Domain too scattered'}
    
    # Check 2: Literature alignment
    known_constructs = [
        'health_outcomes', 'education_outcomes', 'economic_prosperity',
        'security', 'equity', 'infrastructure', 'environment', 
        'governance', 'nutrition', 'connectivity'
    ]
    
    construct_match = find_best_matching_construct(top_variables, known_constructs, literature_db)
    
    if construct_match['confidence'] < 0.60:
        return {'status': 'CAUTION', 
                'reason': 'Novel factor, needs expert validation',
                'suggested_label': construct_match['label']}
    
    # Check 3: Predictability (V1's R² > 0.55 threshold)
    # Quick random forest test
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.model_selection import cross_val_score
    
    # Create composite factor score
    factor_score = np.dot(data[top_variables], loadings[top_variables])
    
    # Test predictability using all non-leaf variables
    predictors = [v for v in data.columns if v not in leaf_nodes]
    X = data[predictors]
    y = factor_score
    
    rf = RandomForestRegressor(n_estimators=100, max_depth=10, random_state=42)
    r2_scores = cross_val_score(rf, X, y, cv=5, scoring='r2')
    mean_r2 = np.mean(r2_scores)
    
    if mean_r2 < 0.40:  # Lower than V1's worst passing metric (R²=0.49)
        return {'status': 'REJECT', 
                'reason': f'Unpredictable outcome (R²={mean_r2:.2f})'}
    
    return {
        'status': 'ACCEPT',
        'suggested_label': construct_match['label'],
        'r2': mean_r2,
        'domain_coherence': 1 - (unique_domains / len(domains))
    }

# Select 1-2 representative metrics per validated factor
priority_outcomes = []

for factor in validated_factors:
    # Choose metric with: (highest loading) * (1 - missingness)
    scores = [(var, 
               abs(loadings[leaf_nodes.index(var), factor['factor_id']]) * 
               (1 - data[var].isna().mean()))
              for var in factor['top_vars']]
    
    best_metric = max(scores, key=lambda x: x[1])[0]
    priority_outcomes.append(best_metric)

# Merge with V1 outcomes (union, removing duplicates)
final_outcomes = list(set(v1_outcomes + priority_outcomes))
Expected: 12-20 validated outcome dimensions (8 from V1 + 4-12 discovered)
Validation Checkpoint:
python
assert 10 <= len(final_outcomes) <= 25, "Too few or too many outcome dimensions"
assert all(data[outcome].isna().mean() < 0.30 for outcome in final_outcomes), "High missingness"

# Ensure we reproduced V1's validated outcomes
v1_reproduced = sum(1 for v1 in v1_outcomes if v1 in final_outcomes)
assert v1_reproduced >= 6, f"Lost {8-v1_reproduced} V1 outcomes"

B2: Mechanism Identification via Multi-Criteria Centrality
Composite Centrality Score:
python
from sklearn.preprocessing import MinMaxScaler

scaler = MinMaxScaler()

# Normalize centrality measures to [0, 1]
betweenness_norm = scaler.fit_transform(list(betweenness.values()).reshape(-1, 1))
pagerank_norm = scaler.fit_transform(list(pagerank.values()).reshape(-1, 1))
out_degree_norm = scaler.fit_transform([G.out_degree(n) for n in G.nodes()].reshape(-1, 1))

# Weighted composite (validated weights from network analysis literature)
mechanism_scores = {}

for i, node in enumerate(G.nodes()):
    mechanism_scores[node] = (
        0.40 * betweenness_norm[i][0] +  # Bridges different domains
        0.30 * pagerank_norm[i][0] +     # Important in graph structure
        0.30 * out_degree_norm[i][0]     # Influences many outcomes
    )

# Top 10% = mechanism candidates
threshold = np.percentile(list(mechanism_scores.values()), 90)
mechanism_candidates = [node for node, score in mechanism_scores.items() 
                        if score > threshold]
Community Detection for Grouping:
python
from networkx.algorithms import community

# Detect communities using Louvain method (modularity optimization)
communities = community.greedy_modularity_communities(G.to_undirected())

mechanism_clusters = {}

for i, comm in enumerate(communities):
    # Find highest-scoring mechanism in this community
    comm_scores = {node: mechanism_scores[node] for node in comm 
                   if node in mechanism_candidates}
    
    if len(comm_scores) > 0:
        lead_mechanism = max(comm_scores, key=comm_scores.get)
        
        mechanism_clusters[lead_mechanism] = {
            'members': list(comm),
            'domain': assign_domain(comm, literature_db),  # AI + human review
            'size': len(comm),
            'avg_centrality': np.mean([mechanism_scores[n] for n in comm])
        }
Expected: 20-40 mechanism clusters

B3: Domain Classification with Semantic Clustering
Automated Domain Assignment with Human Validation:
python
from sentence_transformers import SentenceTransformer
from sklearn.cluster import AgglomerativeClustering

# Load pre-trained semantic model
model = SentenceTransformer('all-MiniLM-L6-v2')

# Encode variable names and descriptions
variable_texts = [get_variable_full_description(var) for var in G.nodes()]
embeddings = model.encode(variable_texts)

# Hierarchical clustering
clusterer = AgglomerativeClustering(
    n_clusters=None,
    distance_threshold=0.7,  # Tune based on domain separation
    linkage='ward'
)
cluster_labels = clusterer.fit_predict(embeddings)

# AI suggests domain label per cluster
domain_assignments = {}

for cluster_id in np.unique(cluster_labels):
    cluster_vars = [var for var, label in zip(G.nodes(), cluster_labels) 
                    if label == cluster_id]
    
    # Use LLM to suggest coherent domain label
    suggested_label = llm_suggest_domain(
        variables=cluster_vars,
        candidate_domains=[
            'Health', 'Education', 'Economic Development', 'Infrastructure',
            'Governance', 'Social Equity', 'Environment', 'Security',
            'Technology', 'Demographics', 'Nutrition', 'Energy', 'Trade'
        ]
    )
    
    # Human validation (flag for review if confidence < 0.80)
    confidence = compute_label_confidence(cluster_vars, suggested_label)
    
    if confidence > 0.80:
        domain_assignments[cluster_id] = suggested_label
    else:
        domain_assignments[cluster_id] = human_review_domain(cluster_vars, suggested_label)

# Assign domains to nodes
for node, label in zip(G.nodes(), cluster_labels):
    node_metadata[node]['domain'] = domain_assignments[label]
Expected: 12-18 coherent domain labels

B4: Multi-Level Pruning for Progressive Disclosure
V1 Lesson: Single pruned graph insufficient for 5 user paths
python
# Create 3 graph versions with different complexity levels

# Level 1-2 (Expert/Researcher): FULL GRAPH
graph_full = {
    'nodes': list(G.nodes()),
    'edges': effect_estimates,
    'metadata': node_metadata,
    'description': 'Complete validated causal network'
}

# Level 3 (Professional): PRUNED GRAPH (300-800 nodes)
def prune_for_professionals(G, effect_estimates, final_outcomes):
    """Retain interpretable network with key mechanisms"""
    
    # Keep all outcome nodes
    keep_nodes = set(final_outcomes)
    
    # Keep top 20% by mechanism score
    threshold_mech = np.percentile(list(mechanism_scores.values()), 80)
    keep_nodes.update([n for n, s in mechanism_scores.items() if s > threshold_mech])
    
    # For remaining nodes, keep only if:
    # (a) Strong direct effect on outcome (|β| > 0.20), OR
    # (b) High betweenness (bridges communities)
    for node in G.nodes():
        if node in keep_nodes:
            continue
        
        # Check (a): Strong outcome effect
        strong_outcome_effect = any(
            e['source'] == node and e['target'] in final_outcomes and abs(e['beta']) > 0.20
            for e in effect_estimates
        )
        
        # Check (b): High betweenness
        high_betweenness = betweenness[node] > np.percentile(list(betweenness.values()), 85)
        
        if strong_outcome_effect or high_betweenness:
            keep_nodes.add(node)
    
    # Filter edges: Keep only edges between retained nodes, top-5 in/out per node
    pruned_edges = []
    
    for node in keep_nodes:
        # Incoming edges
        incoming = [e for e in effect_estimates if e['target'] == node and e['source'] in keep_nodes]
        top_incoming = sorted(incoming, key=lambda x: abs(x['beta']), reverse=True)[:5]
        pruned_edges.extend(top_incoming)
        
        # Outgoing edges
        outgoing = [e for e in effect_estimates if e['source'] == node and e['target'] in keep_nodes]
        top_outgoing = sorted(outgoing, key=lambda x: abs(x['beta']), reverse=True)[:10]
        pruned_edges.extend(top_outgoing)
    
    return list(keep_nodes), pruned_edges

nodes_L3, edges_L3 = prune_for_professionals(G, effect_estimates, final_outcomes)

graph_professional = {
    'nodes': nodes_L3,
    'edges': edges_L3,
    'metadata': {n: node_metadata[n] for n in nodes_L3},
    'description': 'Pruned network showing key mechanisms'
}

# Level 4-5 (Engaged Public/Casual): SIMPLIFIED GRAPH (30-50 nodes)
def prune_for_public(G, effect_estimates, final_outcomes, mechanism_clusters):
    """Ultra-simplified: outcomes + top mechanisms only"""
    
    # Keep all outcomes
    keep_nodes = set(final_outcomes)
    
    # Keep only lead mechanism from each cluster (20-40 mechanisms)
    keep_nodes.update(mechanism_clusters.keys())
    
    # Keep only strongest direct edges to outcomes (|β| > 0.25)
    simplified_edges = [
        e for e in effect_estimates
        if e['source'] in keep_nodes and 
           e['target'] in final_outcomes and 
           abs(e['beta']) > 0.25
    ]
    
    return list(keep_nodes), simplified_edges

nodes_L45, edges_L45 = prune_for_public(G, effect_estimates, final_outcomes, mechanism_clusters)

graph_simplified = {
    'nodes': nodes_L45,
    'edges': edges_L45,
    'metadata': {n: node_metadata[n] for n in nodes_L45},
    'description': 'Simplified network for public engagement'
}
Validation: SHAP Mass Retention
python
import shap
from sklearn.ensemble import RandomForestRegressor

# For each outcome, verify pruned graphs retain predictive power
for outcome in final_outcomes:
    # Train RF on FULL feature set
    X_full = data[[e['source'] for e in effect_estimates]]
    y = data[outcome]
    
    rf_full = RandomForestRegressor(n_estimators=100, random_state=42)
    rf_full.fit(X_full, y)
    
    # SHAP values on full model
    explainer_full = shap.TreeExplainer(rf_full)
    shap_full = explainer_full.shap_values(X_full)
    total_shap_mass = np.sum(np.abs(shap_full))
    
    # Train RF on PRUNED feature set (Level 3)
    X_pruned = data[[e['source'] for e in edges_L3 if e['target'] == outcome]]
    rf_pruned = RandomForestRegressor(n_estimators=100, random_state=42)
    rf_pruned.fit(X_pruned, y)
    
    explainer_pruned = shap.TreeExplainer(rf_pruned)
    shap_pruned = explainer_pruned.shap_values(X_pruned)
    pruned_shap_mass = np.sum(np.abs(shap_pruned))
    
    retention_rate = pruned_shap_mass / total_shap_mass
    
    assert retention_rate > 0.85, f"Pruning lost {1-retention_rate:.1%} explanatory power for {outcome}"
    print(f"✓ {outcome}: Retained {retention_rate:.1%} of SHAP mass")
Expected Sizes:
Full (L1-2): 2,000-8,000 nodes, 2,000-8,000 edges
Professional (L3): 300-800 nodes, 500-1,500 edges
Simplified (L4-5): 30-50 nodes, 40-80 edges

B5: Output Schema with Dashboard Metadata
Unified JSON Schema:
json
{
  "metadata": {
    "version": "2.0",
    "generated_date": "2025-11-11",
    "n_nodes": {
      "full": 4872,
      "professional": 487,
      "simplified": 43
    },
    "n_edges": {
      "full": 6234,
      "professional": 1243,
      "simplified": 68
    },
    "n_layers": 6,
    "temporal_window": [1990, 2024],
    "n_countries": 217,
    "optimal_missingness_threshold": 0.48,
    "imputation_method": "MICE_RF",
    "validation_scores": {
      "bootstrap_stability": 0.84,
      "literature_reproduction": 0.76,
      "mean_r2_holdout": 0.63
    }
  },
  
  "graph_levels": {
    "full": {
      "nodes": [...],
      "edges": [...],
      "target_audience": "Academic researchers, peer review"
    },
    "professional": {
      "nodes": [...],
      "edges": [...],
      "target_audience": "Policy analysts, consultants"
    },
    "simplified": {
      "nodes": [...],
      "edges": [...],
      "target_audience": "General public, media"
    }
  },
  
  "nodes": [
    {
      "id": "life_expectancy",
      "label": "Life Expectancy at Birth",
      "layer": 5,
      "type": "outcome_metric",
      "domain": "Health",
      "factor_loading": 0.87,
      "centrality": {
        "betweenness": 0.042,
        "pagerank": 0.0031,
        "mechanism_score": 0.15
      },
      "stats": {
        "mean": 71.3,
        "std": 8.7,
        "missingness": 0.03,
        "n_observations": 7123
      },
      "visible_in": ["full", "professional", "simplified"],
      "description": "Average years a newborn is expected to live (WHO definition)",
      "data_sources": ["WHO GHO", "World Bank WDI"],
      "citation_key": "who_life_expectancy_2024"
    }
  ],
  
  "edges": [
    {
      "source": "physicians_per_1000",
      "target": "life_expectancy",
      "lag": 3,
      "effect": {
        "beta": 0.34,
        "ci": [0.29, 0.39],
        "se": 0.025,
        "p": 1.2e-15
      },
      "tests": {
        "granger_p": 3.4e-12,
        "conditional_independence": "validated",
        "backdoor_set": ["gdp_per_capita", "urbanization_rate", "education_years"]
      },
      "visible_in": ["full", "professional"],
      "interpretation": "Increasing physician density by 1 SD → +0.34 SD life expectancy after 3 years",
      "mechanism_description": "Healthcare workforce capacity → improved treatment outcomes"
    }
  ],
  
  "interactions": [
    {
      "mechanism": "physicians_per_1000_x_secondary_enrollment",
      "outcome": "life_expectancy",
      "effect": {
        "beta": 0.28,
        "ci": [0.21, 0.35],
        "p": 2.1e-9
      },
      "main_effects": {
        "physicians_per_1000": 0.34,
        "secondary_enrollment": 0.22
      },
      "interpretation": "Synergy: Healthcare × Education amplifies life expectancy gains"
    }
  ],
  
  "mechanism_clusters": [
    {
      "lead_mechanism": "physicians_per_1000",
      "domain": "Health",
      "members": [
        "physicians_per_1000",
        "hospital_beds_per_1000",
        "healthcare_expenditure_pct_gdp",
        "nurses_per_1000"
      ],
      "avg_centrality": 0.67,
      "description": "Healthcare system capacity indicators"
    }
  ],
  
  "outcomes": [
    {
      "id": "life_expectancy",
      "label": "Life Expectancy",
      "factor_id": 1,
      "eigenvalue": 4.32,
      "variance_explained": 0.18,
      "validation": {
        "domain_coherence": 0.91,
        "literature_match": "health_outcomes",
        "predictive_r2": 0.68
      },
      "v1_validated": true
    }
  ],
  
  "dashboard_config": {
    "progressive_disclosure_levels": [
      {
        "level": 1,
        "name": "Expert Mode",
        "graph": "full",
        "features": ["Download data", "Methodology docs", "Statistical details", "Citation generator"]
      },
      {
        "level": 3,
        "name": "Professional Mode",
        "graph": "professional",
        "features": ["Interactive filtering", "Scenario testing", "Mechanism explorer"]
      },
      {
        "level": 5,
        "name": "Simplified Mode",
        "graph": "simplified",
        "features": ["Storytelling mode", "Guided tour", "Plain language"],
        "warning_banner": "⚠️ Simplified view active - showing only strongest relationships"
      }
    ],
    "credibility_features": {
      "citation_generator": true,
      "methodology_links": true,
      "data_download": true,
      "peer_review_status": "preprint"
    }
  }
}

Validation Framework
Internal Validity
python
# 1. Stability Testing
from sklearn.utils import resample

def bootstrap_stability_test(data, effect_estimates, n_iter=1000):
    """Bootstrap graph structure to test stability"""
    edge_retention_rates = []
    
    for i in range(n_iter):
        # Resample with replacement
        sample_idx = resample(range(len(data)), replace=True)
        data_boot = data.iloc[sample_idx]
        
        # Re-run A4 (backdoor adjustment) on bootstrap sample
        boot_edges = compute_effects(data_boot, backdoor_sets)
        
        # Measure edge overlap
        retained = len(set(boot_edges) & set(effect_estimates))
        retention_rate = retained / len(effect_estimates)
        edge_retention_rates.append(retention_rate)
    
    mean_retention = np.mean(edge_retention_rates)
    assert mean_retention > 0.75, f"Unstable graph: {mean_retention:.1%} retention"
    return mean_retention

stability_score = bootstrap_stability_test(data, effect_estimates)
print(f"✓ Bootstrap stability: {stability_score:.1%}")

# 2. Predictive Validation (Hold-out Countries)
from sklearn.model_selection import GroupKFold

countries = data['country'].unique()
gkf = GroupKFold(n_splits=5)

r2_scores = {}

for outcome in final_outcomes:
    fold_r2 = []
    
    for train_idx, test_idx in gkf.split(data, groups=data['country']):
        train_countries = countries[train_idx]
        test_countries = countries[test_idx]
        
        train_data = data[data['country'].isin(train_countries)]
        test_data = data[data['country'].isin(test_countries)]
        
        # Train predictive model
        X_train = train_data[[e['source'] for e in effect_estimates if e['target'] == outcome]]
        y_train = train_data[outcome]
        
        X_test = test_data[[e['source'] for e in effect_estimates if e['target'] == outcome]]
        y_test = test_data[outcome]
        
        rf = RandomForestRegressor(n_estimators=200, max_depth=15, random_state=42)
        rf.fit(X_train, y_train)
        
        fold_r2.append(rf.score(X_test, y_test))
    
    r2_scores[outcome] = np.mean(fold_r2)
    assert r2_scores[outcome] > 0.50, f"Poor predictive power for {outcome}: R²={r2_scores[outcome]:.2f}"

print(f"✓ Mean holdout R²: {np.mean(list(r2_scores.values())):.2f}")

# 3. Causal Structure Validation
assert nx.is_directed_acyclic_graph(G), "❌ CYCLES DETECTED"
print("✓ Valid DAG structure")
External Validity
python
# 1. Literature Reproduction Test
literature_links = load_known_causal_relationships()  # From meta-analyses

reproduced = []
for (X, Y, expected_direction) in literature_links:
    edge = next((e for e in effect_estimates 
                 if e['source'] == X and e['target'] == Y), None)
    
    if edge and np.sign(edge['beta']) == expected_direction:
        reproduced.append((X, Y))

reproduction_rate = len(reproduced) / len(literature_links)
assert reproduction_rate > 0.70, f"Failed to reproduce {1-reproduction_rate:.1%} of known links"
print(f"✓ Literature reproduction: {reproduction_rate:.1%}")

# 2. Out-of-Sample Regional Validation
regions = ['Sub-Saharan Africa', 'East Asia', 'Europe', 'Latin America', 'MENA']

for held_out_region in regions:
    train_data = data[data['region'] != held_out_region]
    test_data = data[data['region'] == held_out_region]
    
    # Re-train and test
    regional_r2 = test_predictive_performance(train_data, test_data, final_outcomes)
    
    assert regional_r2 > 0.45, f"Poor generalization to {held_out_region}"
    print(f"✓ {held_out_region}: R²={regional_r2:.2f}")

# 3. Robustness to Specification Changes
def robustness_test(data, specs):
    """Test edge stability across different analysis choices"""
    baseline_edges = set(effect_estimates)
    
    overlaps = []
    for spec_name, spec_params in specs.items():
        # Re-run pipeline with different params
        alt_edges = run_pipeline(data, **spec_params)
        
        overlap = len(baseline_edges & set(alt_edges)) / len(baseline_edges)
        overlaps.append(overlap)
        print(f"  {spec_name}: {overlap:.1%} edge overlap")
    
    mean_overlap = np.mean(overlaps)
    assert mean_overlap > 0.65, "Results not robust to specification changes"
    return mean_overlap

specs = {
    'different_lags': {'lags': [2, 3, 4, 6]},
    'stricter_threshold': {'beta_threshold': 0.15},
    'alternative_imputation': {'imputation': 'KNN_k5'},
    'fdr_q01': {'fdr_alpha': 0.01}
}

robustness_score = robustness_test(data, specs)
print(f"✓ Specification robustness: {robustness_score:.1%}")

Computational Strategy
Resource Requirements
python
# Infrastructure
compute_platform = "AWS EC2 or Google Cloud Compute"
instance_type = "p3.8xlarge (32 vCPUs, 244 GB RAM, 4x V100 GPUs)"
spot_instances = True  # 70% cost savings

# Parallelization
n_cores_cpu = 32
n_gpus = 4
parallel_framework = "joblib + ray"

# Estimated Runtimes (with optimizations)
timeline = {
    'A0_data_collection': '8-12 hours',
    'A1_missingness_analysis': '12-18 hours (25 parallel configs)',
    'A2_granger_prefiltered': '4-6 days (200K tests, 32 cores)',  # NOT 24-36 hours
    'A3_pc_stable': '2-4 days (10K-30K nodes)',
    'A4_backdoor_bootstrap': '2-3 days (bootstrap intensive)',
    'A5_interactions': '3-5 days (2M tests, constrained search)',
    'A6_hierarchy': '4-6 hours',
    'B1_factor_analysis': '6-8 hours (validation intensive)',
    'B2_mechanisms': '2-4 hours',
    'B3_domains': '4-6 hours (LLM + human review)',
    'B4_pruning': '6-8 hours (SHAP validation)',
    'B5_output_generation': '2-3 hours',
    'TOTAL_WALL_CLOCK': '14-21 days',
    'TOTAL_COMPUTE': '10-15 days'
}

# Cost Estimate
cost_estimate = {
    'spot_p3_8xlarge': '$3.00/hour',
    'total_hours': 240-360,
    'total_cost': '$720-$1,080',
    'storage_s3': '$50-$100',
    'TOTAL': '$770-$1,180'
}
Checkpointing Strategy
python
import pickle
from pathlib import Path

CHECKPOINT_DIR = Path('/mnt/checkpoints')

def save_checkpoint(phase, data, metadata):
    """Save intermediate results for resume capability"""
    checkpoint = {
        'phase': phase,
        'timestamp': datetime.now(),
        'data': data,
        'metadata': metadata
    }
    
    filepath = CHECKPOINT_DIR / f'{phase}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pkl'
    with open(filepath, 'wb') as f:
        pickle.dump(checkpoint, f)
    
    print(f"✓ Checkpoint saved: {filepath}")

def load_checkpoint(phase):
    """Load most recent checkpoint for given phase"""
    checkpoints = list(CHECKPOINT_DIR.glob(f'{phase}_*.pkl'))
    
    if not checkpoints:
        return None
    
    latest = max(checkpoints, key=lambda p: p.stat().st_mtime)
    with open(latest, 'rb') as f:
        return pickle.load(f)

# Usage in pipeline
if __name__ == '__main__':
    # Try to resume from checkpoint
    checkpoint = load_checkpoint('A2_granger')
    
    if checkpoint:
        print(f"Resuming from {checkpoint['phase']} at {checkpoint['timestamp']}")
        validated_edges = checkpoint['data']
    else:
        # Run from scratch
        validated_edges = run_granger_tests(...)
        save_checkpoint('A2_granger', validated_edges, {'n_tests': len(validated_edges)})
Early Stopping Conditions
python
# A3: If PC-Stable graph becomes too dense
if len(causal_graph.edges) > 50_000:
    print("⚠️  Switching to score-based GES due to edge density")
    causal_graph = run_ges_alternative(data)

# A2: If Granger tests taking >7 days
if elapsed_time > timedelta(days=7) and tests_completed < 0.50:
    print("⚠️  Increasing prefilter stringency to meet deadline")
    correlation_threshold = 0.15  # Was 0.10
    candidate_pairs = refilter(candidate_pairs, correlation_threshold)

# B4: If SHAP validation fails
if shap_retention < 0.85:
    print("⚠️  Pruning too aggressive, relaxing to top-30% mechanisms")
    nodes_L3, edges_L3 = prune_for_professionals(G, effect_estimates, final_outcomes, 
                                                   percentile=70)  # Was 80

Lessons from V1: What NOT to Repeat
Documented Failure Modes
markdown
# V1 Mistakes to Avoid

## ❌ DON'T: Domain-Balanced Feature Selection
- V1 Approach B: Force 20 features per domain
- Result: 0/8 metrics improved, lost causal signal
- ✅ V2: Pure statistical selection, domain tagging post-hoc

## ❌ DON'T: Normalize Before Saturation Transform
- V1 Error: Normalized → then applied log/sqrt transforms
- Result: Scientifically invalid, distorted relationships
- ✅ V2: Saturation → Normalization (correct order)

## ❌ DON'T: Use Global Coverage Metrics Only
- V1 Error: Variable had 90% global coverage but 40% per-country
- Result: Many countries dropped from analysis
- ✅ V2: Require 80% within-country temporal coverage

## ❌ DON'T: Apply Neural Networks to n<5K Data
- V1 Error: DNNs on 3,742 observations
- Result: Severe overfitting despite regularization
- ✅ V2: LightGBM/XGBoost for n<5K, reserve NNs for n>50K

## ❌ DON'T: Exclude Self-Disaggregations as "Autocorrelation"
- V1 Error: Removed "female_literacy" when predicting "literacy"
- Result: Lost valid causal pathways
- ✅ V2: Only exclude self-lagged (life_exp_lag1 → life_exp)

## ✅ DO: Keep These Validated Approaches
- Imputation weighting (Tier 1-4 system)
- Three-pronged causal validation (backdoor, Granger, policy sim)
- Saturation transforms for skewed variables
- Mechanism interaction discovery (e.g., health × education)
- Loss curve preservation for animations

Dashboard Integration: Progressive Disclosure System
5-Level User Journey Mapping
python
dashboard_config = {
    'Level_1_Expert': {
        'graph': 'full',
        'node_count': 4872,
        'features': [
            'Download raw data (CSV)',
            'View methodology documentation',
            'Statistical details (β, CI, p-values)',
            'BibTeX citation generator',
            'Backdoor adjustment sets visible',
            'Bootstrap confidence bands',
            'Sensitivity analysis results'
        ],
        'target_users': 'Academic researchers, peer reviewers',
        'complexity': 'Maximum detail'
    },
    
    'Level_2_Researcher': {
        'graph': 'full',
        'node_count': 4872,
        'features': [
            'Interactive filtering by domain',
            'Layer-by-layer exploration',
            'Mechanism cluster view',
            'Export subgraphs',
            'Annotated visualizations'
        ],
        'target_users': 'Graduate students, postdocs',
        'complexity': 'High detail with guidance'
    },
    
    'Level_3_Professional': {
        'graph': 'professional',
        'node_count': 487,
        'features': [
            'Scenario testing tool',
            'Policy intervention simulator',
            'Mechanism comparison',
            'Country-specific pathways',
            'Plain language summaries'
        ],
        'target_users': 'Policy analysts, consultants, NGOs',
        'complexity': 'Moderate detail'
    },
    
    'Level_4_Engaged_Public': {
        'graph': 'simplified',
        'node_count': 43,
        'features': [
            'Storytelling mode (guided tour)',
            'Interactive examples',
            'Plain language only',
            'Contextual help tooltips'
        ],
        'target_users': 'Educated general public, journalists',
        'complexity': 'Low detail',
        'warning_banner': '⚠️ Simplified mode active - showing strongest relationships only'
    },
    
    'Level_5_Casual': {
        'graph': 'simplified',
        'node_count': 43,
        'features': [
            'Pre-built narratives (e.g., "Why do Scandinavians live longer?")',
            'Single-click insights',
            'Minimal text',
            'Video explainers'
        ],
        'target_users': 'Social media users, casual browsers',
        'complexity': 'Minimal detail',
        'warning_banner': '⚠️ Simplified mode active'
    }
}
Academic Credibility Features (Essential for Citations)
python
credibility_features = {
    'citation_generator': {
        'formats': ['BibTeX', 'APA', 'Chicago', 'MLA'],
        'auto_updates': True,  # Updates when new version published
        'doi_integration': True  # Links to preprint/published paper
    },
    
    'methodology_transparency': {
        'full_pipeline_docs': '/methodology/pipeline',
        'code_repository': 'github.com/argon-analytics/causal-discovery',
        'reproducibility_package': 'Available upon request',
        'peer_review_status': 'Preprint (arXiv) → Under Review (Journal TBD)'
    },
    
    'data_access': {
        'download_graphs': ['JSON', 'GraphML', 'CSV'],
        'download_raw_data': 'Requires sign-up (ethical use agreement)',
        'api_access': 'Coming soon (for programmatic queries)'
    },
    
    'version_control': {
        'current_version': '2.0',
        'changelog_visible': True,
        'archived_versions': ['1.0'],  # V1 results remain accessible
        'notification_system': 'Email alerts for major updates'
    }
}

Deliverables
1. Academic Paper
Structure:
markdown
# Global Causal Discovery in Development Economics: 
# A Bottom-Up Network Approach

## Abstract (250 words)
- Problem: Complexity of development outcomes
- Method: 7-step validated causal discovery
- Results: 12-20 outcome dimensions, 2K-8K causal edges
- Impact: Open-source dashboard for policy decisions

## 1. Introduction (4 pages)
- Development economics complexity crisis
- Limitations of theory-driven models
- Bottom-up discovery as alternative
- Research questions

## 2. Related Work (3 pages)
- Existing causal frameworks (Heylighen, Sen, HDI)
- Causal discovery methods (PC, GES, Granger)
- Data-driven development studies
- Gaps in current approaches

## 3. Methods (8 pages)
### 3.1 Data Sources (1 page)
### 3.2 Missingness Analysis (1 page)
### 3.3 Temporal Filtering (Granger) (2 pages)
### 3.4 Structural Filtering (PC-Stable) (1.5 pages)
### 3.5 Effect Quantification (1 page)
### 3.6 Interaction Discovery (1 page)
### 3.7 Interpretability Layer (0.5 pages)

## 4. Results (10 pages)
### 4.1 Outcome Dimensions (2 pages)
- Factor analysis results
- Validation against V1 + literature

### 4.2 Causal Network Structure (3 pages)
- Graph statistics (nodes, edges, layers)
- Domain distribution
- Mechanism clusters

### 4.3 Key Causal Pathways (3 pages)
- Top 20 strongest effects
- Notable synergies
- Regional heterogeneity

### 4.4 Validation Results (2 pages)
- Stability tests
- Literature reproduction
- Predictive performance

## 5. Discussion (6 pages)
### 5.1 Policy Implications (2 pages)
- Leverageable mechanisms
- Context-dependent interventions

### 5.2 Comparison to Existing Frameworks (2 pages)
- HDI, MPI, SDGs
- Advantages of bottom-up approach

### 5.3 Limitations (1 page)
- Observational data constraints
- Missing variable bias
- Temporal resolution

### 5.4 Future Work (1 page)
- Dynamic causal models
- Heterogeneous treatment effects
- Real-time updating

## 6. Conclusion (1 page)
- Summary of contributions
- Call for open-source causal discovery

## Appendices (20 pages)
- A: Complete variable list with sources
- B: Sensitivity analyses (7 specifications)
- C: Regional validation details
- D: Software implementation guide
- E: Dashboard user guide

**Target Journals:**
1. World Development (Elsevier)
2. Journal of Development Economics (Elsevier)
3. Economic Development and Cultural Change (Chicago)
4. World Bank Economic Review (Oxford)
2. Dashboard Assets
python
output_files = {
    'graphs': {
        'causal_graph_full.json': 'Complete 2K-8K node network',
        'causal_graph_professional.json': 'Pruned 300-800 node version',
        'causal_graph_simplified.json': 'Public-facing 30-50 nodes'
    },
    
    'metadata': {
        'methodology.json': 'Full pipeline parameters',
        'validation_results.json': 'All validation test outcomes',
        'variable_codebook.json': 'Descriptions, sources, definitions',
        'domain_classification.json': 'Node-to-domain mappings'
    },
    
    'models': {
        'policy_simulator.pkl': 'Trained intervention models',
        'predictive_models.pkl': 'RF models for all outcomes',
        'interaction_effects.pkl': 'Validated synergy mechanisms'
    },
    
    'documentation': {
        'README.md': 'Quick start guide',
        'API_REFERENCE.md': 'For programmatic access',
        'CITATION.md': 'How to cite in papers',
        'LICENSE.md': 'CC-BY-4.0 for data, MIT for code'
    }
}
3. Consulting Business Foundation
Productization Strategy:
python
consulting_offerings = {
    'Tier_1_Assessment': {
        'deliverable': 'Causal landscape report for client domain',
        'timeline': '2-4 weeks',
        'price': '$15K-$25K',
        'use_case': 'NGO wants to understand education drivers in East Africa'
    },
    
    'Tier_2_Custom_Network': {
        'deliverable': 'Bespoke causal discovery on client data',
        'timeline': '6-12 weeks',
        'price': '$50K-$100K',
        'use_case': 'Foundation wants causal map of their grantee ecosystem'
    },
    
    'Tier_3_Ongoing_Partnership': {
        'deliverable': 'Quarterly updated dashboards + policy recommendations',
        'timeline': 'Annual contract',
        'price': '$200K-$500K/year',
        'use_case': 'Government ministry monitoring development progress'
    },
    
    'Enterprise_License': {
        'deliverable': 'White-label dashboard + training',
        'timeline': '3-6 months',
        'price': '$1M+',
        'use_case': 'World Bank/UN agency internal tool'
    }
}

# Marketing Strategy
brand_positioning = {
    'tagline': 'See What Drives Change',
    'key_differentiators': [
        'Only causal (not correlational) analytics platform',
        'Validated against 100+ peer-reviewed studies',
        'Progressive disclosure (expert → public)',
        '217 countries × 34 years × 2,500 indicators'
    ],
    'proof_points': [
        'Published in [Journal TBD]',
        'Featured in [Media outlet TBD]',
        'Used by [Early adopter client TBD]'
    ]
}

Success Criteria
Phase A Success
python
phase_a_targets = {
    'data_coverage': {
        'n_variables': (4000, 6000),  # Min, Max
        'n_countries': (150, 220),
        'temporal_span': (25, 40),  # years
        'mean_missingness': (0.30, 0.50)
    },
    
    'causal_validation': {
        'validated_edges': (2000, 10000),
        'mean_effect_size': (0.15, None),  # |β| > 0.15
        'dag_validity': True,  # No cycles
        'connected_component_pct': (0.85, 1.0)
    },
    
    'stability': {
        'bootstrap_retention': (0.75, 1.0),
        'specification_overlap': (0.65, 1.0)
    }
}
Phase B Success
python
phase_b_targets = {
    'interpretability': {
        'n_outcomes': (12, 25),
        'n_mechanisms': (20, 50),
        'n_domains': (12, 20),
        'all_nodes_labeled': True
    },
    
    'pruning_quality': {
        'professional_nodes': (300, 800),
        'simplified_nodes': (30, 50),
        'shap_retention': (0.85, 1.0)
    }
}
Overall Success
python
overall_targets = {
    'execution': {
        'pipeline_runtime': (14, 25),  # days
        'compute_cost': (700, 1200),  # USD
        'checkpoint_recovery': True
    },
    
    'validation': {
        'literature_reproduction': (0.70, 1.0),
        'holdout_r2': (0.55, 1.0),
        'regional_generalization': (0.45, 1.0)
    },
    
    'outputs': {
        'paper_drafted': True,
        'dashboard_jsons_generated': True,
        'github_repo_public': True
    }
}

Risk Mitigation
Risk
Probability
Impact
Mitigation
Network sparsity crisis
Medium
High
✅ Prefiltering (200K tests vs 6.2M)
Junk outcome factors
Medium
High
✅ 3-part validation (domain, literature, R²)
Computational bottleneck
Low
High
✅ Parallelization + checkpointing + early stopping
Interaction explosion
Low
Medium
✅ Constrained search (2M tests, not 12M)
Missing data invalidates edges
Low
Medium
✅ A1 sensitivity analysis proves robustness
Dashboard too complex
Medium
Medium
✅ 5-level progressive disclosure
Paper rejection
Medium
Medium
✅ Target multiple journals, iterative review
No consulting clients
High
Low
✅ Free public dashboard builds brand first


Implementation Roadmap
Phase 0: Setup (Week 0)
Set up AWS/GCP compute environment
Install dependencies (causallearn, dowhy, networkx, shap, etc.)
Create GitHub repository with version control
Configure checkpoint system
Phase A: Statistical Discovery (Weeks 1-4)
Week 1:
A0: Collect data from 11 sources (8-12 hours)
A1: Run 25 parallel missingness configs (12-18 hours)
Select optimal config, document decision
Week 2:
A2: Implement prefiltering logic (6.2M → 200K pairs)
Run Granger tests with FDR correction (4-6 days)
Checkpoint: Save validated edges
Week 3:
A3: PC-Stable conditional independence (2-4 days)
Identify backdoor adjustment sets
Checkpoint: Save causal graph with adjustment sets
Week 4:
A4: Backdoor adjustment + bootstrap (2-3 days)
A5: Interaction discovery (3-5 days, constrained search)
A6: Hierarchical layer assignment (4-6 hours)
Milestone: Complete validated causal network
Phase B: Interpretability (Week 5)
Days 1-2:
B1: Factor analysis + validation (8-12 hours)
Merge with V1 outcomes
Days 3-4:
B2: Mechanism clustering (2-4 hours)
B3: Domain classification (4-6 hours, AI + human review)
Days 5-7:
B4: Multi-level pruning (6-8 hours)
SHAP mass validation
B5: Generate output JSONs (2-3 hours)
Milestone: Dashboard-ready assets
Phase C: Validation & Outputs (Week 6)
Days 1-3:
Run all validation tests (bootstrap, holdout, literature)
Document validation results
Days 4-7:
Draft academic paper (introduction through discussion)
Create dashboard mockups
Milestone: Paper submitted for review, dashboard live

Next Immediate Steps
Critical Path (Start Today)
Set up compute environment (4 hours)
bash
  # AWS EC2 p3.8xlarge spot instance
   aws ec2 request-spot-instances \
       --instance-type p3.8xlarge \
       --availability-zone us-east-1a
Begin A0 data collection (2 days)
Write API wrappers for World Bank, WHO, UNESCO
Implement coverage filters
Implement prefiltering logic (1 day)
Code prefilter_candidate_pairs() function
Test on sample of 100 variables
Configure parallel processing (4 hours)
Set up joblib + ray for A2 Granger tests
Test on 1,000 pairs
Week 1 Deliverable
Complete A0 + A1
Document optimal missingness configuration
Have 4,000-5,000 clean variables ready for A2

Document Version Control
yaml
version: 2.0_integrated
date: 2025-11-11
changes_from_v2.0_draft:
  - Added Granger prefiltering (6.2M → 200K tests)
  - Added factor validation (3-part check)
  - Added computational strategy (14-21 day timeline)
  - Added multi-level pruning (3 graph versions)
  - Added V1 lessons learned section
  - Added dashboard progressive disclosure config
  - Added consulting business foundation
  - Revised cost estimate ($770-$1,180)
  - Added checkpoint strategy
  - Added early stopping conditions

Document Complete. Ready for Implementation.
This integrated specification combines the rigor of V2's bottom-up approach with the hard-won lessons from V1's validation process, creating a roadmap that is both ambitious and executable.


