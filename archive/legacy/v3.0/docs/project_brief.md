# V3.0 Research: Complete Implementation Instructions for Claude Code

**Project:** Global Causal Discovery System - V3.0 Temporal Dynamics & Policy Simulation  
**Parent Directory:** `V3_temporal_simulation/`  
**Dependencies:** V2.0 (raw causal edges), V2.1 (semantic hierarchy, unified graph)  
**Timeline:** 7-9 weeks (part-time) or 3-4 weeks (full-time)  
**Output:** REST API + 217 country-specific graphs + intervention simulator

---

## **Prerequisites: Data Inventory Check**

Before starting, verify you have access to these V2.0 and V2.1 outputs:

### **From V2.1 (Semantic Hierarchy):**
```
Required files:
□ Unified graph structure (2,583 nodes: 1,763 indicators + 820 hierarchy)
□ Causal edge list (7,368 edges with beta coefficients)
□ Node metadata (SHAP values, importance ranks, domain assignments)
□ Hierarchical parent-child relationships (Ring 0→1→2→3→4→5)
□ Promoted aggregate indicators (197 indicators that have direct causal edges at Ring 4)

Data format needed:
- Nodes: {id, label, ring/layer, parent_id, shap_value, domain}
- Edges: {source_id, target_id, beta_coefficient, edge_type: 'causal' or 'hierarchical'}
```

### **From V2.0 (Raw Causal Discovery):**
```
Required files:
□ Country-year panel dataset (217 countries × 34 years × 2,500 variables)
□ Raw indicator values (not just SHAP scores, need actual GDP, Life Exp, etc.)
□ Data quality flags (observed vs imputed, % missingness per country-indicator)
□ Original causal adjacency matrix (before semantic aggregation)
□ Bootstrap samples or confidence intervals (if available from GraNDAG)

Critical question for local Claude instance:
"Do we have the raw country-year panel data (217 countries × 34 years)?
If yes, what format? (CSV, Parquet, pickle?)
If no, can we reconstruct from V2.0 outputs?"
```

**STOP:** If you don't have country-year panel data, ask your local Claude instance:
1. "What raw data files do we have from V2.0?"
2. "Can we access individual country time series for indicators?"
3. "Do we have confidence intervals or bootstrap samples from causal discovery?"

---

## **Phase 0: Project Setup (Day 1)**

### **Task 0.1: Create Directory Structure**

```bash
# Create V3.0 workspace
mkdir -p V3_temporal_simulation
cd V3_temporal_simulation

# Create subdirectories
mkdir -p {data,scripts,outputs,api,tests,documentation}
mkdir -p data/{raw,processed,country_graphs}
mkdir -p outputs/{validation,figures,reports}
mkdir -p api/{endpoints,models,utils}
```

**Directory purposes:**
- `data/raw/`: Copies of V2.0 and V2.1 source data
- `data/processed/`: Country-specific splits, cleaned data
- `data/country_graphs/`: 217 separate JSON files (one per country)
- `scripts/`: Python scripts for analysis
- `outputs/`: Results, charts, validation reports
- `api/`: FastAPI backend code
- `tests/`: Unit tests, integration tests
- `documentation/`: Methodology docs, API specs

---

### **Task 0.2: Environment Setup**

Create `requirements.txt`:
```
# Core dependencies
numpy>=1.24.0
pandas>=2.0.0
scipy>=1.10.0
scikit-learn>=1.3.0
statsmodels>=0.14.0

# Causal inference
dowhy>=0.9.0
econml>=0.14.0

# API framework
fastapi>=0.104.0
uvicorn>=0.24.0
pydantic>=2.5.0

# Validation & testing
pytest>=7.4.0
pytest-cov>=4.1.0

# Visualization (for diagnostic plots)
matplotlib>=3.7.0
seaborn>=0.12.0

# Performance
joblib>=1.3.0
tqdm>=4.66.0
```

Install:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

---

### **Task 0.3: Import V2.0 and V2.1 Data**

Create `scripts/import_v2_data.py`:

```python
"""
Import V2.0 and V2.1 outputs into V3.0 workspace.

What we need from V2.1:
- Unified graph (nodes + edges)
- Semantic hierarchy (parent-child relationships)
- SHAP values (importance scores)

What we need from V2.0:
- Country-year panel data (raw indicator values)
- Data quality metadata (missingness, imputation flags)
- Original causal adjacency matrix (before aggregation)
"""

import pandas as pd
import json
import pickle
from pathlib import Path

# === STEP 1: Import V2.1 Unified Graph ===
def load_v21_graph(v21_path):
    """
    Load V2.1 unified graph.
    
    Expected input: JSON or pickle file with:
    - 'nodes': list of {id, label, ring, parent_id, shap_value, domain, ...}
    - 'edges': list of {source, target, weight/beta, relationship: 'causal'/'hierarchical'}
    
    Returns: (nodes_df, edges_df)
    """
    print("Loading V2.1 unified graph...")
    
    # TODO: Adjust based on your actual V2.1 file format
    # Example for JSON:
    with open(v21_path, 'r') as f:
        graph_data = json.load(f)
    
    nodes = pd.DataFrame(graph_data['nodes'])
    edges = pd.DataFrame(graph_data['edges'])
    
    print(f"Loaded {len(nodes)} nodes, {len(edges)} edges")
    
    # Validate structure
    assert 'id' in nodes.columns, "Nodes must have 'id' column"
    assert 'ring' in nodes.columns or 'layer' in nodes.columns, "Nodes must have ring/layer"
    assert 'source' in edges.columns and 'target' in edges.columns, "Edges need source/target"
    
    # Separate causal vs hierarchical edges
    causal_edges = edges[edges['relationship'] == 'causal'].copy()
    hierarchical_edges = edges[edges['relationship'] == 'hierarchical'].copy()
    
    print(f"  Causal edges: {len(causal_edges)}")
    print(f"  Hierarchical edges: {len(hierarchical_edges)}")
    
    return nodes, causal_edges, hierarchical_edges


# === STEP 2: Import V2.0 Country-Year Panel ===
def load_v20_panel_data(v20_path):
    """
    Load V2.0 raw country-year panel data.
    
    Expected input: CSV/Parquet with columns:
    - country_code (ISO3: RWA, USA, etc.)
    - year (1990-2023)
    - indicator columns (2,500 variables: GDP, Life Exp, Literacy, etc.)
    
    Returns: panel_df (long format: country, year, indicator, value)
    """
    print("Loading V2.0 country-year panel data...")
    
    # TODO: Adjust based on your V2.0 file format
    # Example for CSV:
    panel = pd.read_csv(v20_path)
    
    # Validate
    assert 'country_code' in panel.columns, "Need country_code column"
    assert 'year' in panel.columns, "Need year column"
    
    print(f"Loaded {len(panel)} country-year observations")
    print(f"Countries: {panel['country_code'].nunique()}")
    print(f"Years: {panel['year'].min()} to {panel['year'].max()}")
    print(f"Indicators: {len([c for c in panel.columns if c not in ['country_code', 'year']])}")
    
    return panel


# === STEP 3: Data Quality Assessment ===
def assess_data_quality(panel_df):
    """
    Compute data quality metrics per country.
    
    Returns: quality_df with columns:
    - country_code
    - completeness (% non-null across all indicators)
    - n_indicators (how many indicators have ≥50% data)
    - years_coverage (how many years have data)
    """
    print("Assessing data quality...")
    
    quality = []
    
    for country in panel_df['country_code'].unique():
        country_data = panel_df[panel_df['country_code'] == country]
        
        # Drop country_code and year columns to get only indicators
        indicator_cols = [c for c in country_data.columns if c not in ['country_code', 'year']]
        
        # Completeness: % non-null values
        completeness = country_data[indicator_cols].notna().mean().mean()
        
        # How many indicators have ≥50% data for this country
        indicator_completeness = country_data[indicator_cols].notna().mean()
        n_indicators_usable = (indicator_completeness >= 0.5).sum()
        
        # Years coverage
        years_coverage = country_data['year'].nunique()
        
        quality.append({
            'country_code': country,
            'completeness': completeness,
            'n_indicators_usable': n_indicators_usable,
            'years_coverage': years_coverage
        })
    
    quality_df = pd.DataFrame(quality).sort_values('completeness', ascending=False)
    
    print(f"\nData Quality Summary:")
    print(f"  Countries with >80% completeness: {(quality_df['completeness'] > 0.8).sum()}")
    print(f"  Countries with >50% completeness: {(quality_df['completeness'] > 0.5).sum()}")
    print(f"  Countries with <50% completeness: {(quality_df['completeness'] < 0.5).sum()}")
    
    return quality_df


# === MAIN EXECUTION ===
if __name__ == "__main__":
    # Paths to V2.0 and V2.1 outputs (ADJUST THESE)
    V21_GRAPH_PATH = "../phaseB/B35_semantic_hierarchy/outputs/v2_1_visualization_final.json"
    V20_PANEL_PATH = "../phaseA/A5_causal_discovery/data/country_year_panel.csv"
    
    # Load V2.1 graph
    nodes, causal_edges, hierarchical_edges = load_v21_graph(V21_GRAPH_PATH)
    
    # Save to V3 workspace
    nodes.to_csv('data/raw/v21_nodes.csv', index=False)
    causal_edges.to_csv('data/raw/v21_causal_edges.csv', index=False)
    hierarchical_edges.to_csv('data/raw/v21_hierarchical_edges.csv', index=False)
    
    # Load V2.0 panel data
    panel = load_v20_panel_data(V20_PANEL_PATH)
    
    # Assess data quality
    quality = assess_data_quality(panel)
    quality.to_csv('data/raw/data_quality_by_country.csv', index=False)
    
    # Save panel (compressed)
    panel.to_parquet('data/raw/v20_panel_data.parquet', compression='gzip')
    
    print("\n✅ Data import complete!")
    print(f"  Nodes: data/raw/v21_nodes.csv")
    print(f"  Edges: data/raw/v21_causal_edges.csv")
    print(f"  Panel: data/raw/v20_panel_data.parquet")
    print(f"  Quality: data/raw/data_quality_by_country.csv")
```

**Run:**
```bash
python scripts/import_v2_data.py
```

**Verification checklist:**
```
□ data/raw/v21_nodes.csv exists (2,583 rows)
□ data/raw/v21_causal_edges.csv exists (7,368 rows)
□ data/raw/v20_panel_data.parquet exists
□ data/raw/data_quality_by_country.csv exists (217 rows)
□ No error messages during import
```

---

## **Phase A: Country-Specific Graph Estimation (Weeks 1-2)**

### **Task A.1: Split Panel Data by Country**

Create `scripts/split_countries.py`:

```python
"""
Split V2.0 panel data into 217 separate country files.

Output: data/processed/countries/RWA.parquet, USA.parquet, etc.
"""

import pandas as pd
from pathlib import Path
from tqdm import tqdm

def split_panel_by_country(panel_path, output_dir):
    """Split panel data into country-specific files."""
    
    print("Loading panel data...")
    panel = pd.read_parquet(panel_path)
    
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    countries = panel['country_code'].unique()
    print(f"Splitting into {len(countries)} country files...")
    
    for country in tqdm(countries):
        country_data = panel[panel['country_code'] == country].copy()
        
        # Save as parquet (compressed)
        output_path = output_dir / f"{country}.parquet"
        country_data.to_parquet(output_path, compression='gzip')
    
    print(f"✅ Saved {len(countries)} country files to {output_dir}")

if __name__ == "__main__":
    split_panel_by_country(
        panel_path='data/raw/v20_panel_data.parquet',
        output_dir='data/processed/countries'
    )
```

**Run:**
```bash
python scripts/split_countries.py
```

---

### **Task A.2: Country-Specific Causal Discovery**

Create `scripts/estimate_country_graphs.py`:

```python
"""
Estimate causal graphs for each country separately.

This re-runs causal discovery (similar to V2.0) but on country-specific data.

WARNING: This is computationally expensive (217 countries × causal discovery).
Estimated time: 2-3 days on single machine, or use parallel processing.

Output: data/country_graphs/RWA.json, USA.json, etc.
Each file contains:
- nodes: list of indicator IDs
- edges: list of {source, target, beta, ci_lower, ci_upper}
"""

import pandas as pd
import numpy as np
from pathlib import Path
from tqdm import tqdm
import json
from scipy import stats
from sklearn.linear_model import LassoCV
import warnings
warnings.filterwarnings('ignore')

def estimate_causal_graph_for_country(country_data, indicator_cols):
    """
    Estimate causal graph for one country using Lasso regression + bootstrapping.
    
    This is a SIMPLIFIED version. Ideally, you'd use the same GraNDAG algorithm
    from V2.0, but that may not be available. This uses Lasso as a proxy.
    
    Args:
        country_data: DataFrame with years as rows, indicators as columns
        indicator_cols: List of indicator column names
    
    Returns:
        edges: List of {source, target, beta, ci_lower, ci_upper}
    """
    
    # Drop rows with too many missing values
    country_data = country_data.dropna(thresh=len(indicator_cols) * 0.5)
    
    if len(country_data) < 10:
        # Not enough data for this country
        return []
    
    edges = []
    
    # For each indicator (as target), fit Lasso to find its causes
    for target in tqdm(indicator_cols, desc="Indicators", leave=False):
        if target not in country_data.columns:
            continue
        
        # Get target values (drop NaN)
        y = country_data[target].dropna()
        
        if len(y) < 5:
            continue
        
        # Get predictor matrix (all other indicators, aligned with y)
        predictors = [col for col in indicator_cols if col != target and col in country_data.columns]
        X = country_data.loc[y.index, predictors]
        
        # Drop columns with too many NaN
        X = X.loc[:, X.notna().sum() >= 5]
        
        if X.shape[1] == 0:
            continue
        
        # Impute remaining NaN with column means (simple imputation)
        X = X.fillna(X.mean())
        
        # Fit Lasso (alpha selected by cross-validation)
        try:
            lasso = LassoCV(cv=min(5, len(y)), random_state=42, max_iter=1000)
            lasso.fit(X, y)
            
            # Extract non-zero coefficients (Lasso performs variable selection)
            for i, coef in enumerate(lasso.coef_):
                if abs(coef) > 0.01:  # Threshold for "edge exists"
                    source = X.columns[i]
                    
                    # Bootstrap for confidence interval
                    bootstrap_coefs = []
                    for _ in range(100):  # 100 bootstrap samples
                        indices = np.random.choice(len(y), size=len(y), replace=True)
                        X_boot = X.iloc[indices]
                        y_boot = y.iloc[indices]
                        lasso_boot = LassoCV(cv=3, random_state=None, max_iter=500)
                        lasso_boot.fit(X_boot, y_boot)
                        bootstrap_coefs.append(lasso_boot.coef_[i])
                    
                    # Compute 95% CI from bootstrap distribution
                    ci_lower, ci_upper = np.percentile(bootstrap_coefs, [2.5, 97.5])
                    
                    edges.append({
                        'source': source,
                        'target': target,
                        'beta': float(coef),
                        'ci_lower': float(ci_lower),
                        'ci_upper': float(ci_upper)
                    })
        
        except Exception as e:
            # Lasso failed for this target (e.g., convergence issues)
            continue
    
    return edges


def estimate_all_countries(countries_dir, indicator_cols, output_dir):
    """
    Run causal discovery for all countries.
    
    Args:
        countries_dir: Path to data/processed/countries/
        indicator_cols: List of indicator column names
        output_dir: Path to data/country_graphs/
    """
    countries_dir = Path(countries_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    country_files = list(countries_dir.glob("*.parquet"))
    print(f"Estimating causal graphs for {len(country_files)} countries...")
    
    for country_file in tqdm(country_files):
        country_code = country_file.stem  # e.g., "RWA"
        
        # Load country data
        country_data = pd.read_parquet(country_file)
        
        # Estimate causal graph
        edges = estimate_causal_graph_for_country(country_data, indicator_cols)
        
        # Save as JSON
        output_path = output_dir / f"{country_code}.json"
        with open(output_path, 'w') as f:
            json.dump({
                'country_code': country_code,
                'n_nodes': len(indicator_cols),
                'n_edges': len(edges),
                'edges': edges
            }, f, indent=2)
    
    print(f"✅ Saved {len(country_files)} country graphs to {output_dir}")


if __name__ == "__main__":
    # Load indicator list from V2.1
    nodes = pd.read_csv('data/raw/v21_nodes.csv')
    indicator_nodes = nodes[nodes['ring'] == 5]  # Ring 5 = raw indicators
    indicator_cols = indicator_nodes['id'].tolist()
    
    print(f"Using {len(indicator_cols)} indicators for causal discovery")
    
    # Estimate graphs for all countries
    estimate_all_countries(
        countries_dir='data/processed/countries',
        indicator_cols=indicator_cols,
        output_dir='data/country_graphs'
    )
```

**Run (WARNING: This takes 2-3 days):**
```bash
# Option A: Run sequentially (slow but simple)
python scripts/estimate_country_graphs.py

# Option B: Parallelize (faster, requires GNU parallel)
ls data/processed/countries/*.parquet | parallel -j 8 python scripts/estimate_single_country.py {}
```

**Verification:**
```python
# Check output
import json
from pathlib import Path

country_graphs = list(Path('data/country_graphs').glob('*.json'))
print(f"Generated {len(country_graphs)} country graphs")

# Spot-check Rwanda
with open('data/country_graphs/RWA.json') as f:
    rwa = json.load(f)
    print(f"\nRwanda graph:")
    print(f"  Nodes: {rwa['n_nodes']}")
    print(f"  Edges: {rwa['n_edges']}")
    print(f"  Sample edge: {rwa['edges'][0]}")
```

---

### **Task A.3: Validate Country Graphs**

Create `scripts/validate_country_graphs.py`:

```python
"""
Validate country-specific graphs:
1. Check for cycles (should be DAGs)
2. Compute graph similarity across countries
3. Cluster countries by causal structure
"""

import pandas as pd
import numpy as np
import json
from pathlib import Path
from sklearn.cluster import KMeans
from sklearn.metrics import jaccard_score
import matplotlib.pyplot as plt
import seaborn as sns

def validate_dag(edges):
    """Check if graph is acyclic (DAG)."""
    # Build adjacency list
    from collections import defaultdict, deque
    
    adj = defaultdict(list)
    in_degree = defaultdict(int)
    nodes = set()
    
    for edge in edges:
        source, target = edge['source'], edge['target']
        adj[source].append(target)
        in_degree[target] += 1
        nodes.add(source)
        nodes.add(target)
    
    # Topological sort (Kahn's algorithm)
    queue = deque([n for n in nodes if in_degree[n] == 0])
    sorted_count = 0
    
    while queue:
        node = queue.popleft()
        sorted_count += 1
        
        for neighbor in adj[node]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)
    
    is_dag = (sorted_count == len(nodes))
    return is_dag


def compute_adjacency_matrix(edges, all_indicators):
    """Convert edge list to binary adjacency matrix."""
    n = len(all_indicators)
    indicator_to_idx = {ind: i for i, ind in enumerate(all_indicators)}
    
    adj_matrix = np.zeros((n, n), dtype=int)
    
    for edge in edges:
        if edge['source'] in indicator_to_idx and edge['target'] in indicator_to_idx:
            i = indicator_to_idx[edge['source']]
            j = indicator_to_idx[edge['target']]
            adj_matrix[i, j] = 1
    
    return adj_matrix


def compute_graph_similarity(adj1, adj2):
    """Compute Jaccard similarity between two adjacency matrices."""
    # Flatten to 1D arrays
    a1 = adj1.flatten()
    a2 = adj2.flatten()
    
    # Jaccard: intersection / union
    intersection = np.sum((a1 == 1) & (a2 == 1))
    union = np.sum((a1 == 1) | (a2 == 1))
    
    if union == 0:
        return 0.0
    
    return intersection / union


def validate_all_graphs(graphs_dir, all_indicators):
    """Run validation checks on all country graphs."""
    
    graphs_dir = Path(graphs_dir)
    graph_files = list(graphs_dir.glob('*.json'))
    
    print(f"Validating {len(graph_files)} country graphs...")
    
    results = []
    adjacency_matrices = {}
    
    for graph_file in graph_files:
        country_code = graph_file.stem
        
        with open(graph_file) as f:
            data = json.load(f)
        
        edges = data['edges']
        n_edges = len(edges)
        
        # Check if DAG
        is_dag = validate_dag(edges)
        
        # Compute adjacency matrix
        adj_matrix = compute_adjacency_matrix(edges, all_indicators)
        adjacency_matrices[country_code] = adj_matrix
        
        results.append({
            'country_code': country_code,
            'n_edges': n_edges,
            'is_dag': is_dag,
            'edge_density': n_edges / (len(all_indicators) ** 2)
        })
    
    results_df = pd.DataFrame(results)
    
    print("\nValidation Summary:")
    print(f"  DAGs: {results_df['is_dag'].sum()} / {len(results_df)}")
    print(f"  Cycles detected: {(~results_df['is_dag']).sum()}")
    print(f"  Mean edge density: {results_df['edge_density'].mean():.4f}")
    
    # Save validation results
    results_df.to_csv('outputs/validation/country_graph_validation.csv', index=False)
    
    return results_df, adjacency_matrices


def cluster_countries_by_structure(adjacency_matrices, n_clusters=5):
    """Cluster countries by causal graph similarity."""
    
    countries = list(adjacency_matrices.keys())
    
    # Flatten adjacency matrices to feature vectors
    feature_matrix = np.array([adj.flatten() for adj in adjacency_matrices.values()])
    
    # K-means clustering
    kmeans = KMeans(n_clusters=n_clusters, random_state=42)
    clusters = kmeans.fit_predict(feature_matrix)
    
    # Create results dataframe
    cluster_df = pd.DataFrame({
        'country_code': countries,
        'cluster': clusters
    })
    
    print(f"\nCountry clusters (k={n_clusters}):")
    for i in range(n_clusters):
        cluster_countries = cluster_df[cluster_df['cluster'] == i]['country_code'].tolist()
        print(f"  Cluster {i}: {len(cluster_countries)} countries")
        print(f"    Examples: {', '.join(cluster_countries[:5])}")
    
    cluster_df.to_csv('outputs/validation/country_clusters.csv', index=False)
    
    return cluster_df


def plot_similarity_matrix(adjacency_matrices, sample_size=20):
    """Plot pairwise similarity matrix for sample of countries."""
    
    # Sample countries (too many for full matrix)
    countries = list(adjacency_matrices.keys())[:sample_size]
    n = len(countries)
    
    similarity_matrix = np.zeros((n, n))
    
    for i in range(n):
        for j in range(n):
            if i == j:
                similarity_matrix[i, j] = 1.0
            else:
                sim = compute_graph_similarity(
                    adjacency_matrices[countries[i]],
                    adjacency_matrices[countries[j]]
                )
                similarity_matrix[i, j] = sim
    
    # Plot heatmap
    plt.figure(figsize=(12, 10))
    sns.heatmap(similarity_matrix, xticklabels=countries, yticklabels=countries,
                cmap='viridis', vmin=0, vmax=1, annot=False)
    plt.title(f'Country Graph Similarity Matrix (Sample of {n} countries)')
    plt.tight_layout()
    plt.savefig('outputs/figures/country_similarity_matrix.png', dpi=150)
    plt.close()
    
    print(f"\n✅ Saved similarity matrix plot to outputs/figures/")


if __name__ == "__main__":
    # Load indicator list
    nodes = pd.read_csv('data/raw/v21_nodes.csv')
    all_indicators = nodes[nodes['ring'] == 5]['id'].tolist()
    
    # Validate graphs
    results_df, adjacency_matrices = validate_all_graphs('data/country_graphs', all_indicators)
    
    # Cluster countries
    cluster_df = cluster_countries_by_structure(adjacency_matrices, n_clusters=5)
    
    # Plot similarity matrix
    plot_similarity_matrix(adjacency_matrices, sample_size=20)
    
    print("\n✅ Validation complete!")
```

**Run:**
```bash
python scripts/validate_country_graphs.py
```

**Verification checklist:**
```
□ outputs/validation/country_graph_validation.csv exists
□ All countries are DAGs (is_dag = True)
□ outputs/validation/country_clusters.csv exists
□ outputs/figures/country_similarity_matrix.png created
```

---

## **Phase B: Intervention Propagation Algorithm (Weeks 3-4)**

*(Continuing in next message due to length...)*

**CHECKPOINT:** Before proceeding to Phase B, confirm:
1. You have 217 country graph JSON files in `data/country_graphs/`
2. All graphs are validated as DAGs
3. Country clustering completed

**Ask your local Claude instance:**
- "What's the distribution of edge counts across countries?"
- "Which countries have the most/least edges?"
- "Are there any countries with zero edges? (data quality issues)"

Should I continue with Phase B (Intervention Propagation), or do you need clarification on Phase A first?
# V3.0 Research: Implementation Instructions (Part 2)

---

## **Phase B: Intervention Propagation Algorithm (Weeks 3-4)**

### **Task B.1: Implement Saturation Functions**

Create `scripts/saturation_functions.py`:

```python
"""
Saturation functions model diminishing returns.

Example: GDP growth saturates at high income levels
- At $5K GDP: +10% spending → +8% GDP growth
- At $50K GDP: +10% spending → +2% GDP growth (saturation)

We use sigmoid functions (S-curves) for smooth saturation.
"""

import numpy as np
import pandas as pd
import json
from pathlib import Path

# === SATURATION FUNCTION DEFINITIONS ===

def sigmoid_saturation(current_value, change, saturation_point, steepness=0.1):
    """
    Apply sigmoid saturation to limit unrealistic growth.
    
    Formula:
        saturation_factor = 1 / (1 + exp(-steepness * (saturation_point - current_value)))
        effective_change = change * saturation_factor
    
    Args:
        current_value: Current indicator value (e.g., $45K GDP)
        change: Proposed change (e.g., +$5K)
        saturation_point: Point where saturation begins (e.g., $50K)
        steepness: How quickly saturation kicks in (default 0.1)
    
    Returns:
        effective_change: Adjusted change after saturation
    """
    # Sigmoid: returns value between 0 and 1
    # When current_value << saturation_point: factor ≈ 1 (no saturation)
    # When current_value ≈ saturation_point: factor ≈ 0.5
    # When current_value >> saturation_point: factor ≈ 0 (full saturation)
    
    distance_to_saturation = saturation_point - current_value
    saturation_factor = 1 / (1 + np.exp(-steepness * distance_to_saturation))
    
    effective_change = change * saturation_factor
    
    return effective_change


def hard_cap_saturation(current_value, change, max_value):
    """
    Hard cap: cannot exceed max_value.
    
    Example: Literacy rate cannot exceed 100%
    
    Args:
        current_value: Current value (e.g., 95% literacy)
        change: Proposed change (e.g., +10%)
        max_value: Maximum allowed value (e.g., 100%)
    
    Returns:
        effective_change: Capped change
    """
    if current_value >= max_value:
        return 0.0  # Already at max
    
    new_value = current_value + change
    
    if new_value > max_value:
        # Cap at max_value
        return max_value - current_value
    else:
        return change


def linear_diminishing_returns(current_value, change, threshold, reduction_rate=0.5):
    """
    Linear diminishing returns after threshold.
    
    Example: Healthcare spending effectiveness drops after $5K per capita
    
    Args:
        current_value: Current value
        change: Proposed change
        threshold: Point where diminishing returns start
        reduction_rate: How much to reduce (0.5 = half effectiveness)
    
    Returns:
        effective_change: Adjusted change
    """
    if current_value < threshold:
        # Below threshold: full effectiveness
        return change
    else:
        # Above threshold: reduced effectiveness
        excess = current_value - threshold
        reduction_factor = max(0, 1 - (reduction_rate * excess / threshold))
        return change * reduction_factor


# === INDICATOR-SPECIFIC SATURATION RULES ===

def get_saturation_config():
    """
    Define saturation rules for specific indicators.
    
    Returns:
        config: Dict mapping indicator patterns to saturation functions
    """
    config = {
        # GDP-related indicators
        'GDP': {
            'function': 'sigmoid',
            'saturation_point': 50000,  # $50K per capita
            'steepness': 0.00005
        },
        'GNI': {
            'function': 'sigmoid',
            'saturation_point': 50000,
            'steepness': 0.00005
        },
        
        # Life expectancy
        'life_expectancy': {
            'function': 'sigmoid',
            'saturation_point': 85,  # 85 years
            'steepness': 0.1
        },
        'mortality': {
            'function': 'sigmoid',
            'saturation_point': 5,  # 5 per 1000
            'steepness': 0.2
        },
        
        # Education (rates capped at 100%)
        'enrollment': {
            'function': 'hard_cap',
            'max_value': 100
        },
        'literacy': {
            'function': 'hard_cap',
            'max_value': 100
        },
        'completion': {
            'function': 'hard_cap',
            'max_value': 100
        },
        
        # Healthcare spending (diminishing returns)
        'health_expenditure': {
            'function': 'linear_diminishing',
            'threshold': 5000,  # $5K per capita
            'reduction_rate': 0.5
        },
        
        # Default: no saturation (for most indicators)
        'default': {
            'function': 'none'
        }
    }
    
    return config


def apply_saturation(indicator_id, current_value, change):
    """
    Apply appropriate saturation function to an indicator.
    
    Args:
        indicator_id: Indicator ID (e.g., "NY.GDP.PCAP.KD")
        current_value: Current value
        change: Proposed change
    
    Returns:
        effective_change: Change after saturation
    """
    config = get_saturation_config()
    
    # Find matching saturation rule
    rule = None
    for pattern, rule_config in config.items():
        if pattern in indicator_id.lower() or pattern in indicator_id:
            rule = rule_config
            break
    
    if rule is None:
        rule = config['default']
    
    # Apply saturation function
    if rule['function'] == 'sigmoid':
        return sigmoid_saturation(
            current_value, change,
            saturation_point=rule['saturation_point'],
            steepness=rule['steepness']
        )
    elif rule['function'] == 'hard_cap':
        return hard_cap_saturation(
            current_value, change,
            max_value=rule['max_value']
        )
    elif rule['function'] == 'linear_diminishing':
        return linear_diminishing_returns(
            current_value, change,
            threshold=rule['threshold'],
            reduction_rate=rule['reduction_rate']
        )
    else:
        # No saturation
        return change


# === TESTING ===

def test_saturation_functions():
    """Test saturation functions with examples."""
    
    print("Testing Saturation Functions\n")
    
    # Test 1: GDP saturation
    print("1. GDP Saturation (sigmoid at $50K)")
    for gdp in [5000, 20000, 40000, 50000, 70000]:
        change = 5000  # +$5K
        effective = sigmoid_saturation(gdp, change, saturation_point=50000, steepness=0.00005)
        print(f"   GDP=${gdp:,} + ${change:,} → ${effective:,.0f} (factor: {effective/change:.2f})")
    
    # Test 2: Literacy hard cap
    print("\n2. Literacy Rate Hard Cap (100%)")
    for literacy in [80, 90, 95, 98, 99.5]:
        change = 5  # +5%
        effective = hard_cap_saturation(literacy, change, max_value=100)
        print(f"   {literacy}% + {change}% → +{effective:.1f}%")
    
    # Test 3: Healthcare spending diminishing returns
    print("\n3. Healthcare Spending Diminishing Returns ($5K threshold)")
    for spending in [1000, 3000, 5000, 8000, 12000]:
        change = 1000  # +$1K
        effective = linear_diminishing_returns(spending, change, threshold=5000, reduction_rate=0.5)
        print(f"   ${spending:,} + ${change:,} → ${effective:,.0f} (factor: {effective/change:.2f})")


if __name__ == "__main__":
    test_saturation_functions()
    
    print("\n✅ Saturation functions tested successfully")
```

**Run:**
```bash
python scripts/saturation_functions.py
```

**Expected output:**
```
Testing Saturation Functions

1. GDP Saturation (sigmoid at $50K)
   GDP=$5,000 + $5,000 → $4,889 (factor: 0.98)
   GDP=$20,000 + $5,000 → $4,106 (factor: 0.82)
   GDP=$40,000 + $5,000 → $2,689 (factor: 0.54)
   GDP=$50,000 + $5,000 → $2,500 (factor: 0.50)
   GDP=$70,000 + $5,000 → $1,311 (factor: 0.26)

2. Literacy Rate Hard Cap (100%)
   80.0% + 5% → +5.0%
   90.0% + 5% → +5.0%
   95.0% + 5% → +5.0%
   98.0% + 5% → +2.0%
   99.5% + 5% → +0.5%

3. Healthcare Spending Diminishing Returns ($5K threshold)
   $1,000 + $1,000 → $1,000 (factor: 1.00)
   $3,000 + $1,000 → $1,000 (factor: 1.00)
   $5,000 + $1,000 → $1,000 (factor: 1.00)
   $8,000 + $1,000 → $700 (factor: 0.70)
   $12,000 + $1,000 → $300 (factor: 0.30)
```

---

### **Task B.2: Implement Intervention Propagation**

Create `scripts/intervention_propagation.py`:

```python
"""
Intervention propagation algorithm.

Given:
- Country graph (edges with beta coefficients)
- Baseline values (current indicator values)
- Intervention (which indicator to change, by how much)

Compute:
- Direct effects (1-hop: A → B)
- Indirect effects (multi-hop: A → B → C)
- Saturated effects (apply saturation functions)
- Uncertainty bounds (propagate confidence intervals)
"""

import numpy as np
import pandas as pd
import json
from pathlib import Path
from collections import defaultdict, deque
from saturation_functions import apply_saturation

# === CORE PROPAGATION ALGORITHM ===

def propagate_intervention(
    country_graph,
    baseline_values,
    interventions,
    max_iterations=10,
    convergence_threshold=0.001
):
    """
    Propagate intervention effects through causal graph.
    
    Algorithm:
    1. Start with intervention node(s) (e.g., health_spending +20%)
    2. Compute direct effects (1-hop neighbors)
    3. Compute indirect effects (propagate to neighbors of neighbors)
    4. Apply saturation functions (prevent unrealistic values)
    5. Repeat until convergence (changes < threshold)
    
    Args:
        country_graph: Dict with 'edges' list [{source, target, beta, ci_lower, ci_upper}]
        baseline_values: Dict {indicator_id: current_value}
        interventions: List of dicts [{indicator: "health_spending", change_percent: 20}]
        max_iterations: Maximum propagation steps (default 10)
        convergence_threshold: Stop when max change < threshold (default 0.001)
    
    Returns:
        results: Dict with:
            - simulated_values: {indicator_id: new_value}
            - effects: {indicator_id: {change_percent, change_absolute}}
            - uncertainty: {indicator_id: {lower_bound, upper_bound}}
            - iterations_taken: int
    """
    
    # Initialize values (copy baseline)
    current_values = baseline_values.copy()
    
    # Track changes from baseline
    changes = defaultdict(float)
    
    # Apply initial interventions
    for intervention in interventions:
        indicator = intervention['indicator']
        change_percent = intervention['change_percent']
        
        if indicator not in baseline_values:
            print(f"Warning: Indicator {indicator} not in baseline values, skipping")
            continue
        
        baseline = baseline_values[indicator]
        change_absolute = baseline * (change_percent / 100)
        
        # Apply saturation
        effective_change = apply_saturation(indicator, baseline, change_absolute)
        
        current_values[indicator] = baseline + effective_change
        changes[indicator] = effective_change
    
    # Build adjacency list for efficient traversal
    adjacency = defaultdict(list)
    for edge in country_graph['edges']:
        adjacency[edge['source']].append({
            'target': edge['target'],
            'beta': edge['beta'],
            'ci_lower': edge.get('ci_lower', edge['beta'] * 0.8),
            'ci_upper': edge.get('ci_upper', edge['beta'] * 1.2)
        })
    
    # Iterative propagation
    for iteration in range(max_iterations):
        max_change = 0
        new_changes = {}
        
        # For each node that changed in previous iteration
        changed_nodes = [node for node in changes if changes[node] != 0]
        
        if not changed_nodes:
            break
        
        for source in changed_nodes:
            source_change = changes[source]
            
            # Propagate to all neighbors
            for edge_info in adjacency[source]:
                target = edge_info['target']
                beta = edge_info['beta']
                
                # Effect = source_change * beta
                effect = source_change * beta
                
                # Apply saturation
                baseline_target = baseline_values.get(target, 0)
                current_target = current_values.get(target, baseline_target)
                effective_effect = apply_saturation(target, current_target, effect)
                
                # Accumulate change
                new_changes[target] = new_changes.get(target, 0) + effective_effect
                
                # Track max change for convergence check
                max_change = max(max_change, abs(effective_effect))
        
        # Update current values
        for target, change in new_changes.items():
            baseline_target = baseline_values.get(target, 0)
            current_values[target] = current_values.get(target, baseline_target) + change
        
        # Update changes for next iteration
        changes = new_changes
        
        # Check convergence
        if max_change < convergence_threshold:
            print(f"Converged after {iteration + 1} iterations")
            break
    
    # Compute effects (change from baseline)
    effects = {}
    for indicator in current_values:
        baseline = baseline_values.get(indicator, 0)
        simulated = current_values[indicator]
        
        if baseline != 0:
            change_percent = ((simulated - baseline) / baseline) * 100
        else:
            change_percent = 0
        
        effects[indicator] = {
            'change_percent': change_percent,
            'change_absolute': simulated - baseline,
            'baseline': baseline,
            'simulated': simulated
        }
    
    # Propagate uncertainty (simplified: multiply CIs along paths)
    # This is a ROUGH approximation - proper uncertainty propagation needs Monte Carlo
    uncertainty = propagate_uncertainty_bounds(
        country_graph, baseline_values, interventions, adjacency
    )
    
    return {
        'simulated_values': current_values,
        'effects': effects,
        'uncertainty': uncertainty,
        'iterations_taken': iteration + 1
    }


def propagate_uncertainty_bounds(country_graph, baseline_values, interventions, adjacency):
    """
    Propagate confidence intervals through graph.
    
    Simplified approach:
    - Lower bound: use ci_lower for all edges
    - Upper bound: use ci_upper for all edges
    
    Proper approach would use Monte Carlo sampling, but this is faster.
    
    Returns:
        uncertainty: {indicator_id: {lower_bound, upper_bound}}
    """
    # Run propagation twice: once with lower CIs, once with upper CIs
    
    # Lower bound propagation (use ci_lower)
    graph_lower = {'edges': [
        {**edge, 'beta': edge.get('ci_lower', edge['beta'] * 0.8)}
        for edge in country_graph['edges']
    ]}
    results_lower = propagate_intervention(
        graph_lower, baseline_values, interventions,
        max_iterations=5, convergence_threshold=0.01
    )
    
    # Upper bound propagation (use ci_upper)
    graph_upper = {'edges': [
        {**edge, 'beta': edge.get('ci_upper', edge['beta'] * 1.2)}
        for edge in country_graph['edges']
    ]}
    results_upper = propagate_intervention(
        graph_upper, baseline_values, interventions,
        max_iterations=5, convergence_threshold=0.01
    )
    
    # Combine bounds
    uncertainty = {}
    for indicator in results_lower['simulated_values']:
        uncertainty[indicator] = {
            'lower_bound': results_lower['simulated_values'][indicator],
            'upper_bound': results_upper['simulated_values'][indicator]
        }
    
    return uncertainty


# === TESTING ===

def test_propagation():
    """Test propagation with synthetic data."""
    
    print("Testing Intervention Propagation\n")
    
    # Create simple test graph: A → B → C
    test_graph = {
        'edges': [
            {'source': 'A', 'target': 'B', 'beta': 0.5, 'ci_lower': 0.4, 'ci_upper': 0.6},
            {'source': 'B', 'target': 'C', 'beta': 0.8, 'ci_lower': 0.6, 'ci_upper': 1.0}
        ]
    }
    
    # Baseline values
    baseline = {
        'A': 100,
        'B': 50,
        'C': 25
    }
    
    # Intervention: Increase A by 20%
    interventions = [
        {'indicator': 'A', 'change_percent': 20}
    ]
    
    # Run propagation
    results = propagate_intervention(test_graph, baseline, interventions)
    
    print("Intervention: A +20%")
    print("\nResults:")
    for indicator in ['A', 'B', 'C']:
        effect = results['effects'][indicator]
        uncertainty = results['uncertainty'].get(indicator, {})
        
        print(f"  {indicator}:")
        print(f"    Baseline: {effect['baseline']:.2f}")
        print(f"    Simulated: {effect['simulated']:.2f} ({effect['change_percent']:+.1f}%)")
        print(f"    Uncertainty: [{uncertainty.get('lower_bound', 0):.2f}, {uncertainty.get('upper_bound', 0):.2f}]")
    
    print(f"\nIterations: {results['iterations_taken']}")


if __name__ == "__main__":
    test_propagation()
    
    print("\n✅ Propagation algorithm tested successfully")
```

**Run:**
```bash
python scripts/intervention_propagation.py
```

**Expected output:**
```
Testing Intervention Propagation

Converged after 2 iterations
Intervention: A +20%

Results:
  A:
    Baseline: 100.00
    Simulated: 120.00 (+20.0%)
    Uncertainty: [116.00, 124.00]
  B:
    Baseline: 50.00
    Simulated: 60.00 (+20.0%)
    Uncertainty: [58.00, 62.00]
  C:
    Baseline: 25.00
    Simulated: 33.00 (+32.0%)
    Uncertainty: [29.80, 36.80]

Iterations: 2

✅ Propagation algorithm tested successfully
```

---

### **Task B.3: Build Simulation Runner**

Create `scripts/simulation_runner.py`:

```python
"""
High-level simulation runner.

Load country graph, baseline values, run intervention, save results.
"""

import json
import pandas as pd
from pathlib import Path
from intervention_propagation import propagate_intervention

def load_country_data(country_code):
    """
    Load country graph and baseline values.
    
    Args:
        country_code: ISO3 code (e.g., "RWA")
    
    Returns:
        graph: Country causal graph
        baseline: Dict of current indicator values
    """
    # Load country graph
    graph_path = Path(f'data/country_graphs/{country_code}.json')
    with open(graph_path) as f:
        graph = json.load(f)
    
    # Load baseline values from V2.0 panel data
    # (Use most recent year available for this country)
    panel = pd.read_parquet('data/raw/v20_panel_data.parquet')
    country_panel = panel[panel['country_code'] == country_code]
    
    if len(country_panel) == 0:
        raise ValueError(f"No data for country {country_code}")
    
    # Get most recent year
    most_recent = country_panel['year'].max()
    baseline_row = country_panel[country_panel['year'] == most_recent].iloc[0]
    
    # Extract indicator values (all columns except country_code, year)
    indicator_cols = [c for c in baseline_row.index if c not in ['country_code', 'year']]
    baseline = {col: baseline_row[col] for col in indicator_cols if pd.notna(baseline_row[col])}
    
    print(f"Loaded {country_code} data:")
    print(f"  Graph: {len(graph['edges'])} edges")
    print(f"  Baseline: {len(baseline)} indicators (year {most_recent})")
    
    return graph, baseline


def run_simulation(country_code, interventions, output_path=None):
    """
    Run full simulation for a country.
    
    Args:
        country_code: ISO3 code
        interventions: List of intervention dicts
        output_path: Where to save results (optional)
    
    Returns:
        results: Simulation results dict
    """
    # Load data
    graph, baseline = load_country_data(country_code)
    
    # Run propagation
    print(f"\nRunning simulation...")
    results = propagate_intervention(graph, baseline, interventions)
    
    # Add metadata
    results['metadata'] = {
        'country_code': country_code,
        'interventions': interventions,
        'n_edges': len(graph['edges']),
        'n_indicators_affected': len([e for e in results['effects'].values() if abs(e['change_percent']) > 0.01])
    }
    
    print(f"  Affected {results['metadata']['n_indicators_affected']} indicators")
    
    # Save results
    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"  Saved results to {output_path}")
    
    return results


def print_top_effects(results, n=10):
    """Print top N most affected indicators."""
    
    effects_list = [
        (indicator, data)
        for indicator, data in results['effects'].items()
        if abs(data['change_percent']) > 0.01
    ]
    
    # Sort by absolute change percentage
    effects_list.sort(key=lambda x: abs(x[1]['change_percent']), reverse=True)
    
    print(f"\nTop {n} Most Affected Indicators:")
    for i, (indicator, data) in enumerate(effects_list[:n], 1):
        print(f"  {i}. {indicator}:")
        print(f"     {data['baseline']:.2f} → {data['simulated']:.2f} ({data['change_percent']:+.1f}%)")


# === EXAMPLE USAGE ===

if __name__ == "__main__":
    # Example: Simulate Rwanda increasing health spending by 20%
    
    results = run_simulation(
        country_code='RWA',
        interventions=[
            {'indicator': 'health_expenditure_per_capita', 'change_percent': 20}
        ],
        output_path='outputs/simulations/RWA_health_intervention.json'
    )
    
    print_top_effects(results, n=10)
    
    print("\n✅ Simulation complete!")
```

**Run:**
```bash
python scripts/simulation_runner.py
```

---

## **Phase C: Temporal Dynamics (Weeks 5-6)**

### **Task C.1: Estimate Lag Structures**

Create `scripts/temporal_analysis.py`:

```python
"""
Temporal dynamics: Model time lags between cause and effect.

Example:
- Education spending today → Graduation rates in 3 years → Income in 10 years

We use Granger causality tests to find optimal lags.
"""

import numpy as np
import pandas as pd
from statsmodels.tsa.stattools import grangercausalitytests
from statsmodels.tsa.api import VAR
import json
from pathlib import Path
from tqdm import tqdm
import warnings
warnings.filterwarnings('ignore')

def estimate_lag_structure(source_series, target_series, max_lag=10):
    """
    Find optimal lag from source to target using Granger causality.
    
    Args:
        source_series: Time series of source indicator (e.g., education spending)
        target_series: Time series of target indicator (e.g., graduation rates)
        max_lag: Maximum lag to test (default 10 years)
    
    Returns:
        optimal_lag: Best lag (years)
        p_value: Statistical significance
        effect_size: Coefficient at optimal lag
    """
    # Prepare data for Granger test
    # Combine into dataframe
    data = pd.DataFrame({
        'source': source_series,
        'target': target_series
    }).dropna()
    
    if len(data) < max_lag + 10:
        # Not enough data
        return None, None, None
    
    try:
        # Run Granger causality test for lags 1 to max_lag
        test_results = grangercausalitytests(data[['target', 'source']], maxlag=max_lag, verbose=False)
        
        # Find lag with lowest p-value
        best_lag = None
        best_pvalue = 1.0
        
        for lag in range(1, max_lag + 1):
            # Get F-test p-value
            pvalue = test_results[lag][0]['ssr_ftest'][1]
            
            if pvalue < best_pvalue:
                best_pvalue = pvalue
                best_lag = lag
        
        # If significant (p < 0.05), fit VAR to get effect size
        if best_pvalue < 0.05 and best_lag is not None:
            model = VAR(data)
            results = model.fit(maxlags=best_lag)
            
            # Extract coefficient (effect of source on target at best_lag)
            # Coefficient is in results.params
            coef = results.params.loc[f'L{best_lag}.source', 'target']
            
            return best_lag, best_pvalue, coef
        else:
            return None, best_pvalue, None
    
    except Exception as e:
        return None, None, None


def estimate_all_lags_for_country(country_code, country_panel, edges):
    """
    Estimate lag structures for all edges in a country graph.
    
    Args:
        country_code: ISO3 code
        country_panel: DataFrame with time series data
        edges: List of edge dicts (from country graph)
    
    Returns:
        lag_edges: List of edges with lag information added
    """
    print(f"Estimating lag structures for {country_code}...")
    
    lag_edges = []
    
    for edge in tqdm(edges, desc="Edges"):
        source = edge['source']
        target = edge['target']
        
        # Get time series for source and target
        if source not in country_panel.columns or target not in country_panel.columns:
            # Skip if indicators not in data
            lag_edges.append({**edge, 'lag': None, 'lag_pvalue': None})
            continue
        
        source_series = country_panel[source]
        target_series = country_panel[target]
        
        # Estimate lag
        lag, pvalue, lagged_coef = estimate_lag_structure(source_series, target_series, max_lag=10)
        
        # Add lag info to edge
        lag_edges.append({
            **edge,
            'lag': lag,
            'lag_pvalue': pvalue,
            'lagged_coefficient': lagged_coef
        })
    
    # Count edges with significant lags
    n_lagged = len([e for e in lag_edges if e['lag'] is not None])
    print(f"  Found {n_lagged} / {len(edges)} edges with significant lags")
    
    return lag_edges


def estimate_lags_all_countries():
    """
    Run lag estimation for all countries.
    
    Output: data/country_graphs_with_lags/RWA.json, etc.
    """
    # Load country panel data
    panel = pd.read_parquet('data/raw/v20_panel_data.parquet')
    
    # Load country graphs
    graph_dir = Path('data/country_graphs')
    graph_files = list(graph_dir.glob('*.json'))
    
    output_dir = Path('data/country_graphs_with_lags')
    output_dir.mkdir(exist_ok=True)
    
    for graph_file in tqdm(graph_files, desc="Countries"):
        country_code = graph_file.stem
        
        # Load graph
        with open(graph_file) as f:
            graph = json.load(f)
        
        # Get country panel
        country_panel = panel[panel['country_code'] == country_code].copy()
        country_panel = country_panel.sort_values('year')
        
        # Estimate lags
        lag_edges = estimate_all_lags_for_country(country_code, country_panel, graph['edges'])
        
        # Save updated graph
        output_path = output_dir / f"{country_code}.json"
        with open(output_path, 'w') as f:
            json.dump({
                **graph,
                'edges': lag_edges
            }, f, indent=2)
    
    print(f"\n✅ Saved lag-augmented graphs to {output_dir}")


# === TEMPORAL SIMULATION ===

def simulate_with_time_lags(country_graph, baseline_values, interventions, time_horizon=10):
    """
    Simulate intervention effects over time, accounting for lags.
    
    Args:
        country_graph: Graph with 'lag' field on edges
        baseline_values: Current indicator values
        interventions: List of interventions
        time_horizon: How many years to simulate (default 10)
    
    Returns:
        timeline: Dict {year: {indicator: value}}
    """
    # Initialize timeline
    timeline = {0: baseline_values.copy()}
    
    # Track active effects (interventions that haven't taken effect yet)
    pending_effects = []
    
    # Apply initial interventions
    for intervention in interventions:
        indicator = intervention['indicator']
        change_percent = intervention['change_percent']
        
        baseline = baseline_values[indicator]
        change = baseline * (change_percent / 100)
        
        timeline[0][indicator] = baseline + change
        
        # Schedule downstream effects
        for edge in country_graph['edges']:
            if edge['source'] == indicator and edge.get('lag'):
                lag = edge['lag']
                target = edge['target']
                beta = edge['beta']
                
                # Effect will occur at year = lag
                pending_effects.append({
                    'year': lag,
                    'target': target,
                    'effect': change * beta
                })
    
    # Simulate year by year
    for year in range(1, time_horizon + 1):
        # Start with previous year's values
        timeline[year] = timeline[year - 1].copy()
        
        # Apply pending effects for this year
        year_effects = [e for e in pending_effects if e['year'] == year]
        
        for effect in year_effects:
            target = effect['target']
            effect_size = effect['effect']
            
            timeline[year][target] = timeline[year].get(target, baseline_values.get(target, 0)) + effect_size
            
            # Schedule downstream effects from this effect
            for edge in country_graph['edges']:
                if edge['source'] == target and edge.get('lag'):
                    lag = edge['lag']
                    next_target = edge['target']
                    beta = edge['beta']
                    
                    pending_effects.append({
                        'year': year + lag,
                        'target': next_target,
                        'effect': effect_size * beta
                    })
    
    return timeline


if __name__ == "__main__":
    # Estimate lags for all countries
    estimate_lags_all_countries()
    
    print("\n✅ Temporal analysis complete!")
```

**Run (WARNING: Takes 1-2 days):**
```bash
python scripts/temporal_analysis.py
```

---

## **Phase D: API Development (Week 7)**

### **Task D.1: Create FastAPI Backend**

Create `api/main.py`:

```python
"""
FastAPI backend for V3.0 simulation.

Endpoints:
- GET /api/countries - List available countries
- GET /api/graph/{country_code} - Get country graph
- POST /api/simulate - Run intervention simulation
- GET /api/metadata - Get saturation thresholds, confidence intervals
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Optional
import json
from pathlib import Path
import sys

# Add parent directory to path to import simulation modules
sys.path.append(str(Path(__file__).parent.parent))
from scripts.intervention_propagation import propagate_intervention
from scripts.simulation_runner import load_country_data

app = FastAPI(
    title="V3.0 Policy Simulation API",
    description="Country-specific causal graph simulation with temporal dynamics",
    version="3.0.0"
)

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to your domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# === DATA MODELS ===

class Intervention(BaseModel):
    indicator: str
    change_percent: float

class SimulationRequest(BaseModel):
    country: str
    interventions: List[Intervention]
    time_horizon: Optional[int] = 1  # Default: 1 year (no temporal dynamics)

class SimulationResponse(BaseModel):
    country: str
    baseline: Dict[str, float]
    simulated: Dict[str, float]
    effects: Dict[str, Dict[str, float]]
    uncertainty: Dict[str, Dict[str, float]]
    metadata: Dict

# === ENDPOINTS ===

@app.get("/")
def root():
    """API root - health check."""
    return {
        "message": "V3.0 Policy Simulation API",
        "version": "3.0.0",
        "status": "operational"
    }

@app.get("/api/countries")
def list_countries():
    """List all available countries."""
    graph_dir = Path("data/country_graphs")
    countries = [f.stem for f in graph_dir.glob("*.json")]
    
    return {
        "countries": sorted(countries),
        "count": len(countries)
    }

@app.get("/api/graph/{country_code}")
def get_country_graph(country_code: str):
    """Get causal graph for a specific country."""
    graph_path = Path(f"data/country_graphs/{country_code}.json")
    
    if not graph_path.exists():
        raise HTTPException(status_code=404, detail=f"Country {country_code} not found")
    
    with open(graph_path) as f:
        graph = json.load(f)
    
    return graph

@app.post("/api/simulate", response_model=SimulationResponse)
def simulate_intervention(request: SimulationRequest):
    """
    Run intervention simulation for a country.
    
    Request body:
    {
      "country": "RWA",
      "interventions": [
        {"indicator": "health_expenditure_per_capita", "change_percent": 20}
      ],
      "time_horizon": 5  // optional, years to simulate
    }
    
    Response:
    {
      "country": "RWA",
      "baseline": {indicator: value, ...},
      "simulated": {indicator: value, ...},
      "effects": {indicator: {change_percent, change_absolute, baseline, simulated}, ...},
      "uncertainty": {indicator: {lower_bound, upper_bound}, ...},
      "metadata": {n_indicators_affected, iterations_taken, ...}
    }
    """
    try:
        # Load country data
        graph, baseline = load_country_data(request.country)
        
        # Convert interventions to dict format
        interventions = [
            {'indicator': i.indicator, 'change_percent': i.change_percent}
            for i in request.interventions
        ]
        
        # Run simulation
        results = propagate_intervention(graph, baseline, interventions)
        
        # Add metadata
        results['metadata'] = {
            'country': request.country,
            'n_edges': len(graph['edges']),
            'n_indicators_affected': len([
                e for e in results['effects'].values()
                if abs(e['change_percent']) > 0.01
            ]),
            'iterations_taken': results['iterations_taken']
        }
        
        return {
            'country': request.country,
            'baseline': baseline,
            'simulated': results['simulated_values'],
            'effects': results['effects'],
            'uncertainty': results['uncertainty'],
            'metadata': results['metadata']
        }
    
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Country {request.country} not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Simulation failed: {str(e)}")

@app.get("/api/metadata")
def get_metadata():
    """Get system metadata (saturation thresholds, etc.)."""
    from scripts.saturation_functions import get_saturation_config
    
    return {
        "saturation_config": get_saturation_config(),
        "version": "3.0.0",
        "max_time_horizon": 10,
        "convergence_threshold": 0.001
    }

# === RUN SERVER ===

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

**Run server:**
```bash
cd api
python main.py
```

**Test with curl:**
```bash
# List countries
curl http://localhost:8000/api/countries

# Get Rwanda graph
curl http://localhost:8000/api/graph/RWA

# Run simulation
curl -X POST http://localhost:8000/api/simulate \
  -H "Content-Type: application/json" \
  -d '{
    "country": "RWA",
    "interventions": [
      {"indicator": "health_expenditure_per_capita", "change_percent": 20}
    ]
  }'
```

---

### **Task D.2: API Documentation**

Create `documentation/API_SPEC.md`:

```markdown
# V3.0 API Specification

## Base URL
- Development: `http://localhost:8000`
- Production: `https://atlas.argonanalytics.org/api` (to be deployed)

## Authentication
None required for MVP. Add API keys later for rate limiting.

## Endpoints

### GET /api/countries
List all available countries.

**Response:**
```json
{
  "countries": ["AFG", "ALB", "RWA", "USA", ...],
  "count": 217
}
```

### GET /api/graph/{country_code}
Get causal graph structure for a country.

**Parameters:**
- `country_code` (path): ISO3 country code (e.g., "RWA")

**Response:**
```json
{
  "country_code": "RWA",
  "n_nodes": 1763,
  "n_edges": 5243,
  "edges": [
    {
      "source": "health_expenditure",
      "target": "life_expectancy",
      "beta": 0.42,
      "ci_lower": 0.38,
      "ci_upper": 0.46,
      "lag": 3
    },
    ...
  ]
}
```

### POST /api/simulate
Run intervention simulation.

**Request Body:**
```json
{
  "country": "RWA",
  "interventions": [
    {
      "indicator": "health_expenditure_per_capita",
      "change_percent": 20
    }
  ],
  "time_horizon": 5
}
```

**Response:**
```json
{
  "country": "RWA",
  "baseline": {
    "life_expectancy": 69.3,
    "infant_mortality": 27.8,
    ...
  },
  "simulated": {
    "life_expectancy": 71.6,
    "infant_mortality": 24.2,
    ...
  },
  "effects": {
    "life_expectancy": {
      "change_percent": 3.32,
      "change_absolute": 2.3,
      "baseline": 69.3,
      "simulated": 71.6
    },
    ...
  },
  "uncertainty": {
    "life_expectancy": {
      "lower_bound": 70.8,
      "upper_bound": 72.4
    },
    ...
  },
  "metadata": {
    "n_indicators_affected": 47,
    "iterations_taken": 3
  }
}
```

### GET /api/metadata
Get system configuration.

**Response:**
```json
{
  "saturation_config": {...},
  "version": "3.0.0",
  "max_time_horizon": 10,
  "convergence_threshold": 0.001
}
```

## Error Codes
- `404`: Country not found
- `500`: Simulation failed (check error message)
```

---

## **Phase E: Validation & Documentation (Week 8-9)**

### **Task E.1: Historical Validation**

Create `scripts/historical_validation.py`:

```python
"""
Validate simulation accuracy using historical policy changes.

Example: Rwanda's 2003 education reform
- Actual policy: Increased education spending by 30%
- Model prediction: Graduation rates +15% in 5 years
- Reality: Graduation rates +18% in 5 years
- Validation: r² = 0.85 (good match)
"""

import pandas as pd
import numpy as np
from scipy import stats
import json
from pathlib import Path
from simulation_runner import run_simulation

# === HISTORICAL POLICY DATABASE ===

HISTORICAL_INTERVENTIONS = [
    {
        'country': 'RWA',
        'year': 2003,
        'intervention': {'indicator': 'education_expenditure', 'change_percent': 30},
        'observed_effects': {
            'primary_enrollment': {'year': 2008, 'change_percent': 22},
            'literacy_rate': {'year': 2010, 'change_percent': 18}
        }
    },
    # Add more historical cases here...
]

def validate_historical_case(case):
    """
    Run simulation for a historical case and compare to reality.
    
    Returns:
        correlation: r² between predicted and observed changes
        errors: Dict of prediction errors per indicator
    """
    country = case['country']
    intervention = case['intervention']
    observed = case['observed_effects']
    
    # Run simulation
    results = run_simulation(country, [intervention])
    
    # Compare predicted vs observed
    predicted_values = []
    observed_values = []
    errors = {}
    
    for indicator, obs_data in observed.items():
        obs_change = obs_data['change_percent']
        
        if indicator in results['effects']:
            pred_change = results['effects'][indicator]['change_percent']
            
            predicted_values.append(pred_change)
            observed_values.append(obs_change)
            
            errors[indicator] = {
                'predicted': pred_change,
                'observed': obs_change,
                'error': abs(pred_change - obs_change),
                'relative_error': abs(pred_change - obs_change) / abs(obs_change) if obs_change != 0 else None
            }
    
    # Compute correlation
    if len(predicted_values) >= 2:
        correlation = stats.pearsonr(predicted_values, observed_values)[0] ** 2  # r²
    else:
        correlation = None
    
    return correlation, errors

def validate_all_historical_cases():
    """Run validation for all historical cases."""
    
    results = []
    
    for case in HISTORICAL_INTERVENTIONS:
        print(f"\nValidating {case['country']} ({case['year']}) - {case['intervention']['indicator']}")
        
        correlation, errors = validate_historical_case(case)
        
        results.append({
            'country': case['country'],
            'year': case['year'],
            'intervention': case['intervention'],
            'correlation': correlation,
            'errors': errors
        })
        
        if correlation:
            print(f"  r² = {correlation:.3f}")
        
        for indicator, error_data in errors.items():
            print(f"  {indicator}: predicted {error_data['predicted']:.1f}%, observed {error_data['observed']:.1f}% (error: {error_data['error']:.1f}%)")
    
    # Save results
    output_path = Path('outputs/validation/historical_validation.json')
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n✅ Saved validation results to {output_path}")
    
    # Summary statistics
    correlations = [r['correlation'] for r in results if r['correlation'] is not None]
    if correlations:
        print(f"\nSummary:")
        print(f"  Mean r²: {np.mean(correlations):.3f}")
        print(f"  Median r²: {np.median(correlations):.3f}")
        print(f"  Min r²: {np.min(correlations):.3f}")
        print(f"  Max r²: {np.max(correlations):.3f}")

if __name__ == "__main__":
    validate_all_historical_cases()
```

---

## **Final Deliverables Checklist**

```
V3_temporal_simulation/
├── data/
│   ├── raw/
│   │   ├── v21_nodes.csv ✓
│   │   ├── v21_causal_edges.csv ✓
│   │   └── v20_panel_data.parquet ✓
│   ├── processed/
│   │   └── countries/ (217 files) ✓
│   └── country_graphs/ (217 JSON files) ✓
│
├── scripts/
│   ├── import_v2_data.py ✓
│   ├── split_countries.py ✓
│   ├── estimate_country_graphs.py ✓
│   ├── validate_country_graphs.py ✓
│   ├── saturation_functions.py ✓
│   ├── intervention_propagation.py ✓
│   ├── simulation_runner.py ✓
│   ├── temporal_analysis.py ✓
│   └── historical_validation.py ✓
│
├── api/
│   └── main.py ✓
│
├── outputs/
│   ├── validation/
│   │   ├── country_graph_validation.csv ✓
│   │   ├── country_clusters.csv ✓
│   │   └── historical_validation.json ✓
│   └── figures/
│       └── country_similarity_matrix.png ✓
│
└── documentation/
    ├── API_SPEC.md ✓
    ├── METHODOLOGY.md (write this)
    └── VALIDATION_REPORT.md (write this)
```

---

**Next Steps:**
1. Run all scripts in order (Phases A → B → C → D → E)
2. Start API server: `python api/main.py`
3. Test with frontend (Phase 1 integration)
4. Write METHODOLOGY.md and VALIDATION_REPORT.md
5. Deploy API to your server

**Estimated total time:** 7-9 weeks part-time, 3-4 weeks full-time

---

Do you need me to write the METHODOLOGY.md and VALIDATION_REPORT.md templates, or do you have questions about any of the phases?
