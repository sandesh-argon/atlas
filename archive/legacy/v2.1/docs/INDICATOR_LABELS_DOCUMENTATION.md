# V2.1 Indicator Label Generation Documentation

**Generated:** December 5, 2025
**Coverage:** 100% (1,962/1,962 indicators)
**Descriptions:** 97.2% have meaningful descriptions (>20 chars)

---

## Overview

This document describes the indicator label generation process for V2.1, which provides human-readable names and descriptions for all 1,962 indicators in the causal graph.

## Problem Statement

V2.1 Phase A and B pipelines produced a causal graph with 1,962 indicator nodes, but these were identified only by their cryptic codes (e.g., `NY.GDP.MKTP.KD.ZG`, `v2x_polyarchy`). For visualization and interpretation, human-readable labels and descriptions are essential.

## Solution

Adapted the V2.0 label generation methodology (`phaseB/B5_output_schema/scripts/generate_indicator_labels.py`) for V2.1, using multiple data sources and pattern-based generation.

---

## Data Sources (8 Sources)

### 1. World Bank Indicators (Primary Source)
- **File:** `/v2.0/indicators/world_bank_indicators.csv`
- **Records:** 29,201 indicators
- **V2.1 Matches:** 313 direct matches
- **Fields Used:** `id`, `name`, `sourceNote` (description)

### 2. V-Dem Institute (Governance/Democracy)
- **Pattern:** Codes starting with `v2` or `v3`
- **V2.1 Matches:** 456 indicators
- **Method:** Parse prefix codes (v2x = Index, v2cl = Civil Liberties, etc.)
- **Example:** `v2x_polyarchy` → "Index: Polyarchy"

### 3. UNESCO UIS (Education)
- **Pattern:** Codes starting with `EA`, `CR`, `GER`, `NER`, `OFST`, etc.
- **V2.1 Matches:** 445 indicators
- **Method:** Parse education level, age group, gender, location codes
- **Example:** `CR.3.URB.Q5.F` → "Completion Rate - Upper Secondary, Urban, Female, Quintile 5"

### 4. World Inequality Database (WID)
- **Pattern:** Codes starting with `shweal`, `sptinc`, `aptinc`, etc.
- **V2.1 Matches:** 133 indicators
- **Method:** Match WID variable prefixes, add demographic suffixes
- **Example:** `sptinci999` → "Share of Pre-Tax Income (Individual)"

### 5. Quality of Government (QoG)
- **Pattern:** Codes starting with `e_polity`, `ht_regtype`, etc.
- **V2.1 Matches:** 84 indicators
- **Method:** Match QoG dataset patterns
- **Example:** `e_polity2` → "Polity Score: 2"

### 6. Penn World Tables
- **Pattern:** Codes starting with `pwt_`
- **V2.1 Matches:** 7 indicators
- **Example:** `pwt_hci` → "PWT: Human Capital Index"

### 7. WHO Indicators
- **Pattern:** Codes starting with `who_`
- **V2.1 Matches:** 2 indicators
- **Example:** `who_lifexp` → "WHO: Life Expectancy"

### 8. Pattern-Based Fallback
- **For remaining:** 522 indicators
- **Method:** Parse code structure, apply abbreviation expansions
- **Improved by V2.0:** 287 labels upgraded from V2.0's comprehensive database

---

## Label Distribution by Source

| Source | Count | Percentage |
|--------|-------|------------|
| V-Dem Institute | 456 | 23.2% |
| UNESCO Institute for Statistics | 446 | 22.7% |
| World Inequality Database | 296 | 15.1% |
| World Development Indicators | 169 | 8.6% |
| International Comparison Program | 91 | 4.6% |
| Quality of Government | 85 | 4.3% |
| World Bank | 68 | 3.5% |
| Derived (pattern-based) | 60 | 3.1% |
| Wealth Accounts | 58 | 3.0% |
| Other sources | 233 | 11.9% |

---

## Output Files

### Primary Output
```
outputs/B1/indicator_labels_comprehensive.json
```
- **Format:** JSON object mapping indicator ID → label info
- **Size:** 444.3 KB
- **Structure:**
```json
{
  "NY.GDP.MKTP.KD.ZG": {
    "label": "GDP growth (annual %)",
    "source": "World Development Indicators",
    "description": "Annual percentage growth rate of GDP at market prices..."
  }
}
```

### Coverage Report
```
outputs/B1/label_coverage_report.txt
```

### Updated B35 Outputs
- `outputs/B35/causal_graph_v2_FINAL.json` - Nodes now have `label`, `description`, `source`
- `outputs/B35/B35_node_semantic_paths.json` - Added `indicator_label`, `description`, `source`
- `outputs/B35/B35_semantic_hierarchy.pkl` - Level 6/7 indicators updated with labels

---

## Quality Metrics

| Metric | Value |
|--------|-------|
| Total Indicators | 1,962 |
| Labels Generated | 1,962 (100%) |
| With Descriptions | 1,908 (97.2%) |
| Needing Improvement | 33 (1.7%) |

---

## Script Location

```
v2.1/scripts/generate_indicator_labels.py
```

### Usage
```bash
cd <repo-root>/v2.0/v2.1
python scripts/generate_indicator_labels.py
```

### Runtime
- ~5 seconds
- Memory: <500 MB

---

## Pattern Parsing Examples

### V-Dem Indicators
```
v2x_polyarchy → Index: Polyarchy
v2clacjstm → Civil Liberties: Acjstm
v2elfrfair_ord → Elections: Frfair (Ordinal)
```

### UNESCO UIS Indicators
```
CR.3.URB.Q5.F → Completion Rate - Upper Secondary, Urban, Quintile 5, Female
EA.3T8.AG25T99.Q1.M → Educational Attainment - Upper Secondary to Tertiary, Age 25+, Quintile 1, Male
GER.1.GPIA → Gross Enrollment Rate - Primary, Gender Parity Index
```

### WID Indicators
```
sptinci999 → Share of Pre-Tax Income (Individual)
shweali992 → Share of Wealth (Household)
npopuli251 → Population
```

### World Bank Indicators
```
NY.GDP.MKTP.KD.ZG → GDP growth (annual %)
SP.DYN.LE00.IN → Life expectancy at birth, total (years)
SE.ADT.LITR.ZS → Literacy rate, adult total (% of people ages 15 and above)
```

---

## V2.0 Compatibility

The label generation methodology is identical to V2.0, ensuring:
1. Same pattern parsing logic
2. Same data sources
3. Same fallback mechanisms
4. Improved labels automatically pulled from V2.0's comprehensive database

---

## Integration with Visualization

The visualization JSON (`causal_graph_v2_FINAL.json`) now includes:

```json
{
  "nodes": [
    {
      "id": "NY.GDP.MKTP.KD.ZG",
      "label": "GDP growth (annual %)",
      "description": "Annual percentage growth rate of GDP...",
      "source": "World Development Indicators",
      "semantic_path": {...},
      "causal_layer": 5,
      "scores": {...}
    }
  ]
}
```

This enables:
- Tooltips showing full indicator names
- Search by human-readable terms
- Grouping by data source
- Export with meaningful labels

---

## Maintenance

To regenerate labels after adding new indicators:

```bash
python scripts/generate_indicator_labels.py
```

Then update B35 outputs:
```python
# Run the update script in the B35 regeneration section
python scripts/B35/run_b35_semantic_hierarchy.py
```

---

## Known Limitations

1. **33 indicators** have generic labels derived from code parsing
2. Some descriptions are truncated at 300 characters
3. WID indicators have limited descriptions (pattern-generated)

---

## References

- World Bank API: https://datahelpdesk.worldbank.org/
- V-Dem Codebook: https://www.v-dem.net/
- UNESCO UIS: http://uis.unesco.org/
- World Inequality Database: https://wid.world/
- Quality of Government: https://www.gu.se/en/quality-government
