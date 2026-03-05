# V2.1 Results Executive Summary

**Generated:** 2025-12-06 17:17

## Quick Stats

| Metric | Value |
|--------|-------|
| Total Nodes | 2,583 |
| Total Edges | 9,959 |
| Causal Edges | 7,368 |
| Hierarchical Edges | 2,591 |
| Indicators (Layer 5) | 1,763 |
| Outcomes | 9 |
| Domains | 7 |

## Key Findings

### 1. Network Structure
- **Network density:** 0.11% (sparse, as expected for causal graphs)
- **Average path length:** 4.19 (most nodes reachable in ~4 hops)
- **Largest connected component:** 73.7% of nodes
- **No feedback loops** detected (valid DAG)

### 2. Domain Distribution
1. Education: 604 nodes (23.4%)
2. Economic: 583 nodes (22.6%)
3. Governance: 466 nodes (18.0%)
4. Environment: 385 nodes (14.9%)
5. Development: 297 nodes (11.5%)
6. Health: 191 nodes (7.4%)
7. Security: 56 nodes (2.2%)

### 3. Cross-Domain Causation
- **72.5% of causal edges cross domains** (strong interdependence)
- Top domain pathway: **Economic → Education** (534 edges)
- Education is the most influenced domain (958 intra + many cross-domain)

### 4. Hub Indicators (Most Central)
1. Civil Society: Nuni (PageRank 0.013, 212 in-degree)
2. Households Final Consumption Expenditure
3. Governance: Est Spec
4. School-Based Support Programs
5. Full-Time Teachers - Lower Secondary

### 5. Driver Indicators (Most Causal)
1. Financial: Index Pd (49 outgoing edges)
2. School Life Expectancy - Primary, Male (46)
3. Net Enrollment Rate Tertiary (41)
4. PWT: Csppp (41)
5. Gross Mixed Income (41)

### 6. SHAP Importance
- Top indicator: Human capital, male (SHAP=1.000)
- Most important domains: Development, Economic, Environment
- Employment & Work has highest average SHAP (0.017)

## Data Quality

| Metric | Coverage |
|--------|----------|
| Indicators with SHAP scores | 100% |
| Indicators in causal graph | 100% |
| Indicators in hierarchy | 100% |
| Indicators with proper labels | 100% |

## Visualization Recommendations

1. **Emphasize:** Education domain as primary target
2. **Highlight:** Economic→Education pathway
3. **Default expansion:** 4 levels
4. **Color palette:** 7 distinct colors for domains
5. **Hub emphasis:** Show Civil Society indicators prominently

---

*Full details in results_v21_findings.md*
