# Quick Start Guide

**Visualization Implementation Package**
**Date:** November 21, 2025

---

## ⚡ 5-Minute Quick Start

### Step 1: Validate Package (30 seconds)

```bash
cd viz_implementation_package
python scripts/validate_visualization.py
```

**Expected output:** ✅ All critical checks passed!

---

### Step 2: Load Schema in Your Environment

#### JavaScript/TypeScript

```javascript
fetch('data/causal_graph_v2_final.json')
  .then(response => response.json())
  .then(schema => {
    console.log('Loaded:', schema.mechanisms.length, 'mechanisms');
    // Your code here
  });
```

#### Python

```python
import json

with open('data/causal_graph_v2_final.json') as f:
    schema = json.load(f)

print(f"Loaded: {len(schema['mechanisms'])} mechanisms")
```

#### R

```r
library(jsonlite)

schema <- fromJSON('data/causal_graph_v2_final.json')
cat("Loaded:", length(schema$mechanisms$id), "mechanisms\n")
```

---

### Step 3: Explore the Data

#### Access Graph Levels

```javascript
// Full graph: 290 nodes, 507 edges (academic)
const fullGraph = schema.graphs.full;

// Professional: 116 nodes, 71 edges (policy)
const professionalGraph = schema.graphs.professional;

// Simplified: 167 nodes, 150 edges (public)
const simplifiedGraph = schema.graphs.simplified;
```

#### Filter by Domain

```javascript
const educationNodes = schema.mechanisms.filter(m =>
  m.domain === "Education" && m.shap_available
);
```

#### Get Tooltips

```javascript
const tooltips = schema.dashboard_metadata.tooltips;
const tooltip = tooltips.find(t => t.id === 'SE.PRM.ENRR');
console.log(tooltip.text); // 80-char truncated
console.log(tooltip.full_text); // Complete description
```

---

## 📊 Understanding the Data Structure

### Schema Anatomy

```json
{
  "metadata": {
    "version": "2.0",
    "n_nodes": {"full": 290, "professional": 116, "simplified": 167}
  },
  "mechanisms": [
    {
      "id": "SE.PRM.ENRR",
      "label": "Primary School Enrollment Rate",
      "domain": "Education",
      "subdomain": "Access to Education",
      "cluster_name": "Education Access & Enrollment",
      "shap_score": 0.0134,
      "shap_available": true,
      "centrality": 0.034,
      "visible_in": ["full", "professional", "simplified"]
    }
  ],
  "outcomes": [
    {
      "id": "Factor_2",
      "label": "Educational Access & Quality",
      "primary_domain": "Education",
      "r_squared": 0.71
    }
  ],
  "graphs": {
    "full": {
      "nodes": [...],  // 290 nodes
      "edges": [...]   // 507 edges
    }
  },
  "dashboard_metadata": {
    "filters": {...},
    "tooltips": [...],
    "citations": {...}
  }
}
```

---

## 🎯 Common Use Cases

### Use Case 1: Build a Filterable Dashboard

```javascript
// Get filter options
const filters = schema.dashboard_metadata.filters;

// Domains: ["Governance", "Education", "Economic", "Mixed"]
const domains = filters.domains;

// SHAP threshold slider
const shapMin = filters.shap_range.min;      // 0.0
const shapMax = filters.shap_range.max;      // 0.0134
const shapBaseline = filters.shap_range.baseline;  // 0.00345

// Filter nodes by criteria
function filterNodes(domain, minSHAP) {
  return schema.mechanisms.filter(m =>
    m.domain === domain &&
    m.shap_available &&
    m.shap_score >= minSHAP
  );
}
```

### Use Case 2: Network Analysis

```python
import networkx as nx

# Load GraphML (alternative to JSON)
G = nx.read_graphml('data/causal_graph_v2.graphml')

# Compute metrics
pagerank = nx.pagerank(G)
betweenness = nx.betweenness_centrality(G)

# Top 10 most important nodes
top_nodes = sorted(pagerank.items(), key=lambda x: x[1], reverse=True)[:10]
```

### Use Case 3: Generate Hierarchical Trees

```bash
# ASCII tree visualization
python scripts/generate_hierarchical_tree_ascii.py

# Custom parameters
python scripts/generate_hierarchical_tree_ascii.py \
  --max-depth 5 \
  --max-children 10 \
  --mode outcome-centric \
  --output my_trees.txt
```

---

## 📁 File Reference

### Essential Data Files

| File | Format | Purpose | Size |
|------|--------|---------|------|
| `causal_graph_v2_final.json` | JSON | Primary schema | 516 KB |
| `causal_graph_v2.graphml` | GraphML | Network analysis | 132 KB |
| `mechanisms.csv` | CSV | Tabular mechanisms | 34 KB |
| `outcomes.csv` | CSV | Tabular outcomes | 1 KB |
| `edges_full.csv` | CSV | Tabular edges | 17 KB |
| `data_dictionary.md` | Markdown | Field reference | - |

### When to Use Which Format?

- **JSON** (`causal_graph_v2_final.json`): Web dashboards, JavaScript apps, complete metadata
- **GraphML** (`causal_graph_v2.graphml`): NetworkX, Gephi, Cytoscape, network analysis
- **CSV** (`*.csv`): R, pandas, Excel, simple filtering/analysis

---

## 🔍 Data Exploration Tips

### Tip 1: Start with Simplified Graph

```javascript
// Too overwhelming to see all 290 nodes at once
// Start with simplified (167 nodes, more digestible)
const simplified = schema.graphs.simplified;
```

### Tip 2: Use SHAP to Rank Importance

```python
# Get top 20 most important mechanisms
top_mechanisms = mechanisms_df[mechanisms_df['shap_available']] \
    .nlargest(20, 'shap_score')
```

### Tip 3: Explore by Domain

```r
# Group mechanisms by domain
library(dplyr)

domain_summary <- mechanisms_df %>%
  group_by(domain) %>%
  summarise(
    count = n(),
    mean_shap = mean(shap_score[shap_available], na.rm = TRUE)
  )
```

### Tip 4: Check Edge Effects

```javascript
// Find strongest causal effects
const strongEffects = schema.graphs.full.edges
  .filter(e => Math.abs(e.effect) > 0.3)
  .sort((a, b) => Math.abs(b.effect) - Math.abs(a.effect));
```

---

## 🚨 Common Pitfalls

### Pitfall 1: Expecting 100% SHAP Coverage

**Issue:** Some mechanisms show `shap_score: "not_computed"`

**Why:** SHAP requires the mechanism to influence at least one outcome in the predictive model. Mechanisms with no direct causal paths to outcomes have no SHAP scores.

**Solution:** Always check `shap_available === true` before using `shap_score`.

```javascript
// ❌ Bad: Will crash on "not_computed"
const score = mechanism.shap_score;

// ✅ Good: Check availability first
const score = mechanism.shap_available ? mechanism.shap_score : null;
```

### Pitfall 2: Using Full Text in Tooltips

**Issue:** `tooltip.full_text` is too long for most UIs (100-200 chars)

**Why:** Dashboard needs short, scannable tooltips

**Solution:** Use `tooltip.text` (80-char truncated) for display, `full_text` for expanded view.

```javascript
// ✅ Good: Use truncated text for UI
<div class="tooltip">{tooltip.text}</div>

// Show full text on click/expand
<div class="expanded">{tooltip.full_text}</div>
```

### Pitfall 3: Ignoring Graph Levels

**Issue:** Rendering all 290 nodes at once is overwhelming

**Why:** Full graph is for experts, not general users

**Solution:** Default to `simplified` (167 nodes), allow toggling to `professional` (116) or `full` (290).

```javascript
// ✅ Good: Start with simplified
let currentLevel = 'simplified';
const graph = schema.graphs[currentLevel];

// Allow user to switch levels
function switchLevel(newLevel) {
  currentLevel = newLevel;
  renderGraph(schema.graphs[currentLevel]);
}
```

### Pitfall 4: Forgetting Edge Direction

**Issue:** Treating graph as undirected

**Why:** Causal graphs are **directed** (cause → effect)

**Solution:** Always respect `source → target` direction in edges.

```python
# ✅ Good: Directed graph
G = nx.DiGraph()
for edge in edges:
    G.add_edge(edge['source'], edge['target'], effect=edge['effect'])
```

---

## 📚 Next Steps

1. **Run validation**: `python scripts/validate_visualization.py`
2. **Explore examples**: Check `examples/` for JavaScript, Python, R code
3. **Read data dictionary**: `data/data_dictionary.md` for complete field reference
4. **Generate trees**: `python scripts/generate_hierarchical_tree_ascii.py`
5. **Read implementation guide**: `IMPLEMENTATION_GUIDE.md` for detailed dashboard design

---

## 💡 Pro Tips

**Tip 1:** Use SHAP baseline (0.00345) to identify "above-average" mechanisms

**Tip 2:** Cluster names are human-readable - use them for grouping in UI

**Tip 3:** Edge `lag` field shows temporal dynamics (0-5 years typical)

**Tip 4:** `visible_in` field indicates which graph levels include each node

**Tip 5:** Outcomes (Factor_0 - Factor_8) are the "leaves" of the causal tree

---

## 🆘 Troubleshooting

**Q: JSON won't parse**
A: File is UTF-8 encoded. Ensure your loader supports UTF-8.

**Q: GraphML won't load in Gephi**
A: Use File → Import → GraphML, not "Open Project"

**Q: Too many edges to visualize**
A: Use `professional` (71 edges) or `simplified` (150 edges) instead of `full` (507 edges)

**Q: SHAP scores seem low**
A: They sum to 1.0 across all 290 mechanisms. Baseline = 1/290 = 0.00345. Anything above is "important".

---

**Package Version:** 2.0
**Created:** November 21, 2025
**Status:** Production-ready, validated
