# Label Quality Report

**Date:** November 21, 2025
**Status:** ⚠️ CRITICAL - Labels Need Improvement

---

## 🚨 Issue Summary

**Problem:** 89% of mechanism labels are poor quality (258/290)

**Root Cause:** Original A0 data acquisition did not preserve full indicator names from source APIs. The unified metadata only contains truncated or generic labels.

**Impact:** Visualization will show codes or single-word labels instead of meaningful names:
- ❌ `"wdi_mobile"` → `"Mobile"` (should be "Mobile cellular subscriptions per 100 people")
- ❌ `"wdi_lfpedubm"` → `"Lfpedubm"` (should be "Labor force participation rate, male, basic education")
- ✅ `"REPR.1.G6.M.CP"` → `"Repetition rate in Grade 6 of primary education, male (%)"` (UNESCO labels are good)

---

## 📊 Current Label Quality

| Source | Total | Good | Poor | Good % |
|--------|-------|------|------|--------|
| UNESCO | 32 | 32 | 0 | 100% |
| World Bank WDI | 156 | 0 | 156 | 0% |
| V-Dem | 58 | 0 | 58 | 0% |
| WHO | 23 | 0 | 23 | 0% |
| Others | 21 | 0 | 21 | 0% |
| **TOTAL** | **290** | **32** | **258** | **11%** |

---

## ✅ Immediate Solution (Implemented)

The visualization package now includes:

1. **Best-effort labels** from available metadata (unified_metadata.json)
2. **Label quality flag** (`label_quality`: "good" or "poor") for each mechanism
3. **Label mapping files**:
   - `data/label_mapping.json` (human-readable)
   - `data/label_mapping.pkl` (Python pickle)

**Current schema structure:**
```json
{
  "id": "wdi_mobile",
  "label": "Mobile",
  "label_quality": "poor",
  "description": "World Bank World Development Indicators indicator: Mobile",
  "domain": "Economic",
  "source": "World Bank World Development Indicators"
}
```

---

## 🔧 Recommended Solutions (For Implementation Team)

### Option 1: API Fetch (Recommended - 2-3 hours)

Fetch proper names from source APIs for the 258 poor-quality labels.

**Script template:**
```python
import requests
import json
import time

# Load current schema
with open('data/causal_graph_v2_final.json', 'r') as f:
    schema = json.load(f)

# Fetch WDI labels (156 indicators)
wdi_codes = [m['id'] for m in schema['mechanisms'] if m['id'].startswith('wdi_')]
for code in wdi_codes:
    # Extract original WDI code (remove 'wdi_' prefix)
    wdi_id = code.replace('wdi_', '').upper()

    # Fetch from World Bank API
    url = f"https://api.worldbank.org/v2/indicator/{wdi_id}?format=json"
    response = requests.get(url)

    if response.ok:
        data = response.json()
        if len(data) > 1 and data[1]:
            full_name = data[1][0]['name']
            # Update schema
            for m in schema['mechanisms']:
                if m['id'] == code:
                    m['label'] = full_name
                    m['label_quality'] = 'good'
                    break

    time.sleep(0.5)  # Rate limiting

# Fetch V-Dem labels (58 indicators)
# URL: https://v-dem.net/data/reference-materials/
# Download codebook CSV and match codes

# Save updated schema
with open('data/causal_graph_v2_final_IMPROVED.json', 'w') as f:
    json.dump(schema, f, indent=2)
```

**Estimated time:** 2-3 hours (with rate limiting)

**Pros:**
- Authoritative names from official sources
- Free (public APIs)
- One-time effort

**Cons:**
- Requires API access (may hit rate limits)
- Some indicators may be deprecated/not found
- Needs manual review

---

### Option 2: Manual Curation (High-quality - 1-2 days)

Manually review and improve all 258 labels using source documentation.

**Resources:**
- World Bank WDI: https://datacatalog.worldbank.org/
- V-Dem Codebook: https://v-dem.net/data/reference-materials/
- WHO GHO: https://www.who.int/data/gho/indicator-metadata-registry
- UNICEF: https://data.unicef.org/resources/resource-type/guidance/

**Process:**
1. Export poor-quality labels: `python extract_poor_labels.py`
2. Look up each code in source documentation
3. Update label_mapping.json
4. Re-run schema update script
5. Validate with domain experts

**Estimated time:** 1-2 days (4-16 hours)

**Pros:**
- Highest quality (human-verified)
- Can add context and clarifications
- Catches deprecated indicators

**Cons:**
- Labor-intensive
- Requires domain knowledge
- Time-consuming

---

### Option 3: Hybrid (Recommended - 3-4 hours)

Combine automated API fetch with manual review of critical indicators.

**Steps:**
1. Run API fetch for World Bank WDI (156 indicators) - 1 hour
2. Manual lookup for V-Dem top 20 by SHAP score - 1 hour
3. Manual lookup for WHO/UNICEF critical indicators - 1 hour
4. Validate all "good" labels - 30 minutes

**Estimated time:** 3-4 hours

**Pros:**
- Balances automation and quality
- Focuses effort on high-impact indicators
- Catches major issues

**Cons:**
- Still leaves some poor labels
- Requires both technical and domain skills

---

## 📋 Label Improvement Script (Provided)

```python
#!/usr/bin/env python3
"""
Label Improvement Script

Fetches proper indicator names from source APIs and updates the schema.

Usage:
    python improve_labels.py --source wdi --output improved_schema.json
"""

import argparse
import json
import requests
import time
from pathlib import Path

def fetch_wdi_label(code: str) -> str:
    """Fetch World Bank WDI indicator name."""
    # Remove 'wdi_' prefix
    wdi_id = code.replace('wdi_', '').upper()

    url = f"https://api.worldbank.org/v2/indicator/{wdi_id}?format=json"
    try:
        response = requests.get(url, timeout=10)
        if response.ok:
            data = response.json()
            if len(data) > 1 and data[1]:
                return data[1][0].get('name', code)
    except Exception as e:
        print(f"Error fetching {code}: {e}")

    return code

def improve_wdi_labels(schema: dict) -> dict:
    """Improve all World Bank WDI labels."""
    wdi_mechanisms = [m for m in schema['mechanisms'] if m['id'].startswith('wdi_')]

    print(f"Improving {len(wdi_mechanisms)} WDI labels...")

    for i, mech in enumerate(wdi_mechanisms, 1):
        code = mech['id']
        print(f"  [{i}/{len(wdi_mechanisms)}] {code}... ", end='')

        new_label = fetch_wdi_label(code)
        if new_label != code:
            mech['label'] = new_label
            mech['label_quality'] = 'good'
            print(f"✅ {new_label[:60]}")
        else:
            print(f"❌ Not found")

        time.sleep(0.5)  # Rate limiting

    return schema

def main():
    parser = argparse.ArgumentParser(description="Improve indicator labels")
    parser.add_argument('--source', choices=['wdi', 'vdem', 'all'], default='wdi',
                       help='Which source to improve')
    parser.add_argument('--output', type=str, default='causal_graph_v2_final_IMPROVED.json',
                       help='Output file path')

    args = parser.parse_args()

    # Load schema
    with open('data/causal_graph_v2_final.json', 'r') as f:
        schema = json.load(f)

    # Improve labels
    if args.source in ['wdi', 'all']:
        schema = improve_wdi_labels(schema)

    # TODO: Add V-Dem, WHO, UNICEF fetchers

    # Save
    with open(f'data/{args.output}', 'w') as f:
        json.dump(schema, f, indent=2)

    print(f"\n✅ Improved schema saved to data/{args.output}")

if __name__ == '__main__':
    main()
```

**Save as:** `viz_implementation_package/scripts/improve_labels.py`

---

## 🎯 Recommendations

### For Immediate Use (Next 24 hours)

**Accept current labels with caveats:**
- Document label quality issue in README
- Use `label_quality` flag to show warning icons in UI
- Provide "Report incorrect label" button for user feedback

### For Production Release (1-2 weeks)

**Execute Hybrid Solution (Option 3):**
1. Run `improve_labels.py --source wdi` (1 hour)
2. Manual review of top 50 mechanisms by SHAP score (2 hours)
3. Validate with domain expert (1 hour)
4. Update schema and re-deploy

### Long-term (Future Versions)

**Prevent recurrence:**
1. Update A0 data acquisition scripts to save full indicator names
2. Add metadata validation step (check label quality before A1)
3. Create standardized metadata schema with required fields
4. Implement automated label quality checks in CI/CD

---

## 📎 Files Included

1. **label_mapping.json** - Current label mappings with quality flags
2. **label_mapping.pkl** - Python pickle format for faster loading
3. **improve_labels.py** - Script to fetch proper names from APIs (TODO: add to package)

---

## ✅ Current Status

- [x] Best-effort labels extracted from unified_metadata.json
- [x] Label quality flags added to schema
- [x] Label mapping files created
- [x] Documentation updated
- [ ] **TODO:** Run API fetch for WDI labels (158 indicators)
- [ ] **TODO:** Manual review of V-Dem labels (58 indicators)
- [ ] **TODO:** Validate improved labels with domain experts

---

**Priority:** HIGH - Labels are critical for usability
**Effort:** 2-4 hours (automated fetch) or 1-2 days (manual curation)
**Blocker:** No - visualization can launch with current labels + quality warnings

---

*Last updated: November 21, 2025*
*Contact: Implementation team*
