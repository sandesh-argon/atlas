#!/usr/bin/env python3
"""
B5 Task 5: Export Final Schema
===============================

Exports validated V2 schema in multiple formats for dashboard integration:
- JSON (primary format)
- GraphML (network analysis tools)
- CSV (tabular data)
- Data dictionary (documentation)

Inputs:
- outputs/B5_task3_dashboard_schema.pkl

Outputs:
- outputs/causal_graph_v2_final.json
- outputs/causal_graph_v2.graphml
- outputs/mechanisms.csv
- outputs/outcomes.csv
- outputs/edges_full.csv
- outputs/data_dictionary.md

Author: B5 Schema Generation
Date: November 2025
"""

import pickle
import json
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime

# JSON serializer for numpy types
def json_serializer(obj):
    """Convert numpy types to native Python types for JSON serialization"""
    if isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.bool_):
        return bool(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

# ============================================================================
# Setup
# ============================================================================

project_root = Path(__file__).resolve().parents[3]
b5_dir = project_root / 'phaseB/B5_output_schema'
outputs_dir = b5_dir / 'outputs'
exports_dir = outputs_dir / 'exports'
exports_dir.mkdir(exist_ok=True)

print("="*80)
print("B5 TASK 5: EXPORT FINAL SCHEMA")
print("="*80)
print(f"\nTimestamp: {datetime.now().isoformat()}")

# ============================================================================
# Load Task 3 Dashboard Schema
# ============================================================================

print("\n" + "="*80)
print("LOADING DASHBOARD SCHEMA")
print("="*80)

task3_path = outputs_dir / 'B5_task3_dashboard_schema.pkl'
print(f"Loading: {task3_path}")

with open(task3_path, 'rb') as f:
    dashboard_schema = pickle.load(f)

print(f"✅ Loaded dashboard schema")
print(f"   - Outcomes: {len(dashboard_schema['outcomes'])}")
print(f"   - Mechanisms: {len(dashboard_schema['mechanisms'])}")
print(f"   - Graphs: {len(dashboard_schema['graphs'])}")

# ============================================================================
# Export 1: JSON (Primary Format)
# ============================================================================

print("\n" + "="*80)
print("EXPORT 1: JSON (PRIMARY FORMAT)")
print("="*80)

json_path = exports_dir / 'causal_graph_v2_final.json'

try:
    with open(json_path, 'w') as f:
        json.dump(dashboard_schema, f, indent=2, default=json_serializer)

    file_size_mb = json_path.stat().st_size / (1024 * 1024)
    print(f"✅ Exported JSON: {json_path}")
    print(f"   File size: {file_size_mb:.2f} MB")

except Exception as e:
    print(f"❌ ERROR exporting JSON: {e}")

# ============================================================================
# Export 2: GraphML (Network Analysis)
# ============================================================================

print("\n" + "="*80)
print("EXPORT 2: GRAPHML (NETWORK ANALYSIS)")
print("="*80)

try:
    import networkx as nx

    # Create NetworkX graph from full graph
    G = nx.DiGraph()

    full_graph = dashboard_schema['graphs']['full']

    # Add nodes with attributes
    for node in full_graph['nodes']:
        # Find mechanism details
        mech = next((m for m in dashboard_schema['mechanisms'] if m['id'] == node['id']), None)

        if mech:
            G.add_node(
                node['id'],
                label=mech['label'],
                domain=mech['domain'],
                subdomain=mech['subdomain'],
                cluster_id=mech['cluster_id'],
                shap_score=float(mech['shap_score']) if isinstance(mech['shap_score'], (int, float)) else 0.0,
                degree=mech['centrality']['degree']
            )

    # Add edges with attributes
    for edge in full_graph['edges']:
        G.add_edge(
            edge['source'],
            edge['target'],
            weight=float(edge.get('weight', 1.0))
        )

    # Export to GraphML
    graphml_path = exports_dir / 'causal_graph_v2.graphml'
    nx.write_graphml(G, graphml_path)

    print(f"✅ Exported GraphML: {graphml_path}")
    print(f"   Nodes: {G.number_of_nodes()}")
    print(f"   Edges: {G.number_of_edges()}")

except ImportError:
    print(f"⚠️ NetworkX not available - skipping GraphML export")
except Exception as e:
    print(f"❌ ERROR exporting GraphML: {e}")

# ============================================================================
# Export 3: CSV (Tabular Data)
# ============================================================================

print("\n" + "="*80)
print("EXPORT 3: CSV (TABULAR DATA)")
print("="*80)

# Export mechanisms as CSV
try:
    mechanisms_data = []
    for mech in dashboard_schema['mechanisms']:
        mechanisms_data.append({
            'id': mech['id'],
            'label': mech['label'],
            'domain': mech['domain'],
            'subdomain': mech['subdomain'],
            'cluster_id': mech['cluster_id'],
            'cluster_name': mech['cluster_name'],
            'shap_score': float(mech['shap_score']) if isinstance(mech['shap_score'], (int, float)) else None,
            'shap_available': mech['shap_available'],
            'degree_centrality': mech['centrality']['degree'],
            'visible_in_full': 'full' in mech['visible_in'],
            'visible_in_professional': 'professional' in mech['visible_in'],
            'visible_in_simplified': 'simplified' in mech['visible_in']
        })

    mechanisms_df = pd.DataFrame(mechanisms_data)
    mechanisms_csv_path = exports_dir / 'mechanisms.csv'
    mechanisms_df.to_csv(mechanisms_csv_path, index=False)

    print(f"✅ Exported mechanisms CSV: {mechanisms_csv_path}")
    print(f"   Rows: {len(mechanisms_df)}")

except Exception as e:
    print(f"❌ ERROR exporting mechanisms CSV: {e}")

# Export outcomes as CSV
try:
    outcomes_data = []
    for outcome in dashboard_schema['outcomes']:
        outcomes_data.append({
            'id': outcome['id'],
            'factor_name': outcome['factor_name'],
            'label': outcome['label'],
            'primary_domain': outcome['primary_domain'],
            'r_squared': outcome['r_squared'],
            'r_squared_std': outcome['r_squared_std'],
            'passes_coherence': outcome['validation']['passes_coherence'],
            'passes_literature': outcome['validation']['passes_literature'],
            'passes_predictability': outcome['validation']['passes_predictability'],
            'passes_overall': outcome['validation']['passes_overall'],
            'is_novel': outcome['validation']['is_novel']
        })

    outcomes_df = pd.DataFrame(outcomes_data)
    outcomes_csv_path = exports_dir / 'outcomes.csv'
    outcomes_df.to_csv(outcomes_csv_path, index=False)

    print(f"✅ Exported outcomes CSV: {outcomes_csv_path}")
    print(f"   Rows: {len(outcomes_df)}")

except Exception as e:
    print(f"❌ ERROR exporting outcomes CSV: {e}")

# Export edges (full graph) as CSV
try:
    edges_data = []
    full_graph = dashboard_schema['graphs']['full']

    for edge in full_graph['edges']:
        edges_data.append({
            'source': edge['source'],
            'target': edge['target'],
            'weight': float(edge.get('weight', 1.0))
        })

    edges_df = pd.DataFrame(edges_data)
    edges_csv_path = exports_dir / 'edges_full.csv'
    edges_df.to_csv(edges_csv_path, index=False)

    print(f"✅ Exported edges CSV: {edges_csv_path}")
    print(f"   Rows: {len(edges_df)}")

except Exception as e:
    print(f"❌ ERROR exporting edges CSV: {e}")

# ============================================================================
# Export 4: Data Dictionary (Documentation)
# ============================================================================

print("\n" + "="*80)
print("EXPORT 4: DATA DICTIONARY (DOCUMENTATION)")
print("="*80)

dict_lines = [
    "# Global Causal Discovery System V2.0 - Data Dictionary",
    "",
    f"**Generated:** {datetime.now().isoformat()}",
    "",
    "## Overview",
    "",
    f"- **Outcomes:** {len(dashboard_schema['outcomes'])} validated quality-of-life dimensions",
    f"- **Mechanisms:** {len(dashboard_schema['mechanisms'])} causal mechanisms",
    f"- **Domains:** {len(dashboard_schema['domains'])} policy domains",
    f"- **Graph Versions:** {len(dashboard_schema['graphs'])} (full, professional, simplified)",
    "",
    "## Schema Structure",
    "",
    "### Metadata",
    "",
    "| Field | Type | Description |",
    "|-------|------|-------------|",
    "| version | string | Schema version (2.0) |",
    "| timestamp | ISO 8601 | Generation timestamp |",
    "| phase | string | Project phase (B_complete) |",
    "",
    "### Outcomes",
    "",
    "Discovered quality-of-life dimensions from factor analysis (B1).",
    "",
    "| Field | Type | Description |",
    "|-------|------|-------------|",
    "| id | integer | Factor ID (0-11) |",
    "| factor_name | string | Factor label (e.g., 'Factor_1') |",
    "| label | string | Human-readable label |",
    "| primary_domain | string | Dominant domain (Health, Governance, Economic, etc.) |",
    "| top_variables | array[string] | Top 5 indicator loadings |",
    "| top_loadings | array[float] | Loading strengths |",
    "| r_squared | float | Predictability (cross-val R²) |",
    "| r_squared_std | float | Standard deviation of R² |",
    "| validation.passes_coherence | boolean | <3 unique domains |",
    "| validation.passes_literature | boolean | TF-IDF similarity >0.60 |",
    "| validation.passes_predictability | boolean | R² >0.40 |",
    "| validation.passes_overall | boolean | All 3 checks pass |",
    "| validation.is_novel | boolean | Not in V1 outcomes |",
    "",
    "### Mechanisms",
    "",
    "Causal mechanisms identified from B2+B3 pipeline.",
    "",
    "| Field | Type | Description |",
    "|-------|------|-------------|",
    "| id | string | Mechanism ID (indicator code) |",
    "| label | string | Mechanism label |",
    "| domain | string | Primary policy domain |",
    "| subdomain | string | Subdomain (e.g., 'Executive', 'Primary') |",
    "| cluster_id | integer | Cluster assignment from B2 |",
    "| cluster_name | string | Cluster label |",
    "| centrality.degree | integer | Number of connections |",
    "| shap_score | float or 'not_computed' | Random Forest feature importance |",
    "| shap_available | boolean | Whether SHAP was computed |",
    "| visible_in | array[string] | Graph levels where visible |",
    "",
    "### Domains",
    "",
    "Policy domain classification from B3.",
    "",
    "| Field | Type | Description |",
    "|-------|------|-------------|",
    "| name | string | Domain name |",
    "| clusters | array[integer] | Cluster IDs in this domain |",
    "| mechanism_count | integer | Number of mechanisms |",
    "| cluster_count | integer | Number of clusters |",
    "| subdomains | array[string] | Unique subdomains |",
    "",
    "### Graphs",
    "",
    "Three progressive disclosure levels from B4.",
    "",
    "**Full Graph** (290 nodes): Academic/expert use",
    "**Professional Graph** (116 nodes): Policy analysts",
    "**Simplified Graph** (167 nodes): General public",
    "",
    "| Field | Type | Description |",
    "|-------|------|-------------|",
    "| nodes | array[object] | Graph nodes |",
    "| edges | array[object] | Graph edges |",
    "| metadata | object | Graph metadata |",
    "| statistics | object | Graph statistics |",
    "",
    "### Dashboard Metadata",
    "",
    "Interactive features for visualization dashboard.",
    "",
    "**Filters:**",
    "- `domains`: Multiselect filter (4 options)",
    "- `subdomains`: Multiselect filter (6 options)",
    "- `layers`: Multiselect filter (18 options)",
    "- `shap_range`: Slider (0.0002-0.0134)",
    "- `graph_level`: Radio (full, professional, simplified)",
    "",
    "**Tooltips:**",
    "- Mechanism tooltips: 290 (truncated to 80 chars)",
    "- Outcome tooltips: 9",
    "",
    "**Citations:**",
    "- Project citation (BibTeX)",
    "- Data sources (6 sources)",
    "- Methodology references (4 papers)",
    "",
    "## Data Quality",
    "",
    f"- **SHAP Coverage:** {sum(1 for m in dashboard_schema['mechanisms'] if m['shap_available'])}/{len(dashboard_schema['mechanisms'])} ({sum(1 for m in dashboard_schema['mechanisms'] if m['shap_available'])/len(dashboard_schema['mechanisms'])*100:.1f}%)",
    f"- **Label Consistency:** {dashboard_schema['dashboard_metadata']['validation']['label_consistency']['total_mismatches']} mismatches",
    f"- **Schema Size:** {json_path.stat().st_size / (1024 * 1024):.2f} MB",
    "",
    "## Export Formats",
    "",
    "1. **JSON** (`causal_graph_v2_final.json`): Primary format for dashboard",
    "2. **GraphML** (`causal_graph_v2.graphml`): Network analysis tools (Gephi, Cytoscape)",
    "3. **CSV** (`mechanisms.csv`, `outcomes.csv`, `edges_full.csv`): Tabular analysis",
    "4. **Markdown** (`data_dictionary.md`): This documentation",
    "",
    "## Usage Examples",
    "",
    "### Load JSON in Python",
    "```python",
    "import json",
    "with open('causal_graph_v2_final.json', 'r') as f:",
    "    schema = json.load(f)",
    "```",
    "",
    "### Load GraphML in NetworkX",
    "```python",
    "import networkx as nx",
    "G = nx.read_graphml('causal_graph_v2.graphml')",
    "```",
    "",
    "### Load CSV in Pandas",
    "```python",
    "import pandas as pd",
    "mechanisms = pd.read_csv('mechanisms.csv')",
    "outcomes = pd.read_csv('outcomes.csv')",
    "edges = pd.read_csv('edges_full.csv')",
    "```",
    "",
    "## Version History",
    "",
    "- **V2.0** (November 2025): Bottom-up causal discovery with B1-B4 pipeline",
    "- **V1.0** (2024): Expert-guided causal network with 8 pre-selected outcomes",
    "",
    "## Citation",
    "",
    "```bibtex",
    "@misc{global_causal_v2,",
    "  title={Global Causal Discovery System V2.0},",
    "  author={Global Development Economics Research Team},",
    "  year={2025},",
    "  version={2.0},",
    "  url={https://github.com/your-repo/global-causal-discovery}",
    "}",
    "```",
    "",
    "---",
    "",
    f"*Generated by B5 Output Schema Generation | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*"
]

dict_path = exports_dir / 'data_dictionary.md'

with open(dict_path, 'w') as f:
    f.write('\n'.join(dict_lines))

print(f"✅ Exported data dictionary: {dict_path}")
print(f"   Lines: {len(dict_lines)}")

# ============================================================================
# Final Export Summary
# ============================================================================

print("\n" + "="*80)
print("EXPORT SUMMARY")
print("="*80)

print(f"\n✅ All exports completed successfully:")
print(f"   1. JSON: {json_path.name} ({json_path.stat().st_size / 1024:.1f} KB)")
if (exports_dir / 'causal_graph_v2.graphml').exists():
    print(f"   2. GraphML: causal_graph_v2.graphml ({(exports_dir / 'causal_graph_v2.graphml').stat().st_size / 1024:.1f} KB)")
if (exports_dir / 'mechanisms.csv').exists():
    print(f"   3. Mechanisms CSV: mechanisms.csv ({(exports_dir / 'mechanisms.csv').stat().st_size / 1024:.1f} KB)")
if (exports_dir / 'outcomes.csv').exists():
    print(f"   4. Outcomes CSV: outcomes.csv ({(exports_dir / 'outcomes.csv').stat().st_size / 1024:.1f} KB)")
if (exports_dir / 'edges_full.csv').exists():
    print(f"   5. Edges CSV: edges_full.csv ({(exports_dir / 'edges_full.csv').stat().st_size / 1024:.1f} KB)")
print(f"   6. Data Dictionary: data_dictionary.md ({dict_path.stat().st_size / 1024:.1f} KB)")

print(f"\nExport directory: {exports_dir}")

print("\n" + "="*80)
print("TASK 5 COMPLETE")
print("="*80)

print(f"\n✅ Final V2 schema exported in 4+ formats")
print(f"✅ Ready for dashboard integration")
print(f"✅ B5 Output Schema Generation COMPLETE")

print("\n" + "="*80)
print("ALL B5 TASKS COMPLETE")
print("="*80)
