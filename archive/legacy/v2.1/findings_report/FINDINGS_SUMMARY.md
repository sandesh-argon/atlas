# V2.1 Global Causal Discovery: Research Findings

**Generated**: 2025-12-05T15:24:38.850544
**Version**: 2.1

## Executive Summary

### Key Findings

- Discovered 1,962 causal mechanisms with 7,368 validated edges
- 98.5% of mechanisms are novel (not in established development indices)
- 24-layer hierarchical structure (layers 0-23)
- Average path length: 4.0 hops (driver→outcome)
- 9 quality-of-life dimensions discovered (data_driven)
- Economic domain dominant (37.1% of indicators)
- 100% indicator classification (0% unclassified)

### V2.1 Improvements

- 100% semantic clustering coverage (vs 44.3% unclassified initially)
- V2.0-compatible output format for visualization
- Comprehensive SHAP importance scoring
- 8-level semantic hierarchy with SHAP-based layer split

---

## Detailed Findings

### 1. Network Topology
- **Nodes**: 1,962
- **Edges**: 7,368
- **Network density**: 0.001915
- **Mean degree**: 7.51
- **Max in-degree**: 212
- **Max out-degree**: 49
- **Average path length**: 3.95 hops

### 2. Effect Sizes
- **Total edges analyzed**: 4,976
- **Mean |β|**: 183.7775
- **Median |β|**: 0.2626
- **Positive effects**: 2,666 (53.6%)
- **Negative effects**: 2,310 (46.4%)

**Top 5 Strongest Effects:**
  1. SAP.01 → npopuli251 (β=485756.8111)
  2. SAP.01.M → npopuli251 (β=-239384.1478)
  3. hc → SP.DYN.TO65.MA.ZS (β=184805.3154)
  4. mseghoi999 → EN.GHG.CO2.BU.MT.CE.AR5 (β=-520.6097)
  5. mprghoi999 → ygmxhni999 (β=-212.3350)

### 3. Interactions
- **Edges with moderators**: 0
- **Total moderator effects**: 30,315
- **Status**: Direct A5 validation

### 4. Novel Discoveries
- **Novelty rate**: 98.5%
- **Novel mechanisms**: 1,933
- **Known mechanisms**: 29
- **Finding**: 98.5% of discovered mechanisms are novel (not matching established development constructs)

**Top Novel High-Impact Indicators:**
  1. NW.HCA.MALE.TO (Economic, SHAP=0.6505)
  2. NW.PCA.TO.EX.CD (Economic, SHAP=0.5661)
  3. NW.PCA.TO.IN.CD (Economic, SHAP=0.4437)
  4. CR.3.RUR.Q5.F (Education, SHAP=0.3829)
  5. NW.DOW.TO (Economic, SHAP=0.3713)

### 5. Domain Analysis
- **Economic**: 728 indicators (37.1%)
- **Governance**: 624 indicators (31.8%)
- **Education**: 336 indicators (17.1%)
- **Demographics**: 140 indicators (7.1%)
- **Health**: 75 indicators (3.8%)
- **Environment**: 36 indicators (1.8%)
- **Security**: 14 indicators (0.7%)
- **Development**: 9 indicators (0.5%)

**Top Cross-Domain Flows:**
  1. Economic → Economic: 1,137 edges
  2. Governance → Governance: 1,014 edges
  3. Economic → Governance: 872 edges
  4. Education → Governance: 691 edges
  5. Economic → Education: 512 edges

### 6. Hierarchical Structure
- **Layers**: 24 (range: 0-23)
- **Root causes (layer 0)**: 20 indicators
- **Terminal outcomes (layer 23)**: 1 indicators

**Example Causal Chain:**
NY.GDP.MINR.RT.ZS → v2smgovcapsec_ord → v2clacjstm → OFST.AGM1.CP → GTVP.3.GPV.GPIA → v2canuni
(Length: 6 steps)

### 7. Outcome Dimensions
- **Approach**: data_driven
- **Factors discovered**: 9
- **Interpretable factors**: 8

**Factors:**
  1. Factor_1_Other (Other) - ✓ interpretable
  2. Factor_2_Social (Social) - ✓ interpretable
  3. Factor_3_Other (Other) - ✓ interpretable
  4. Factor_4_Other (Other) - ✓ interpretable
  5. Factor_5_Environment (Environment) - ✗ interpretable
  6. Factor_6_Other (Other) - ✓ interpretable
  7. Factor_7_Other (Other) - ✓ interpretable
  8. Factor_8_Governance (Governance) - ✓ interpretable
  9. Factor_9_Governance (Governance) - ✓ interpretable

### 8. SHAP Importance
- **Nodes with real SHAP**: 1,708
- **Nodes with composite score**: 1,962
- **Mean composite score**: 0.1302
- **Max real SHAP**: 1.0000

**Top 5 by SHAP:**
  1. NW.HCA.MALE.TO (Economic) - SHAP=1.0000
  2. NW.PCA.TO.EX.CD (Economic) - SHAP=0.8219
  3. NW.PCA.TO.IN.CD (Economic) - SHAP=0.5770
  4. NW.DOW.TO (Economic) - SHAP=0.4379
  5. X.USCONST.4.FSGOV (Economic) - SHAP=0.3712

---

## Files Generated

- `01_network_topology.json` - Graph structure analysis
- `02_effect_sizes.json` - Causal effect distributions
- `03_interactions.json` - Moderator/interaction discovery
- `04_novelty.json` - Novel mechanism identification
- `05_domains.json` - Domain-level analysis
- `06_hierarchy.json` - Hierarchical structure
- `07_outcomes.json` - Quality-of-life dimensions
- `08_shap_importance.json` - SHAP importance scores
- `FINDINGS_REPORT_COMPLETE.json` - Consolidated report
- `FINDINGS_SUMMARY.md` - This document

---

## V2.1 vs V2.0 Comparison

| Metric | V2.0 | V2.1 |
|--------|------|------|
| Nodes | 3,872 | 1,962 |
| Edges | 11,003 | 7,368 |
| Layers | 21 | 24 |
| Unclassified | 0% | 0% |
| Outcome Factors | 9 | 9 |

---

**For academic paper**: Use section-specific JSON files for detailed tables/figures.
