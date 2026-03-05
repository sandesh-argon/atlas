# V2.1 Output Requirements

## 6-Layer Hierarchy Structure

### Target Structure

```
Layer 0: Root                          →     1 node
Layer 1: Outcomes (B1)                 →     9 nodes  (9 children from root)
Layer 2: Coarse Domains                →    36 nodes  (4 children each)
Layer 3: Fine Domains                  →   144 nodes  (4 children each)
Layer 4: Indicator Groups (NEW)        →   576 nodes  (4 children each)
Layer 5: Indicators                    → 1,962 nodes  (3-4 per group)
```

**Total: 6 layers (0-5)**

### 3-5 Children Rule

Every non-leaf node must have 3-5 children (except root which has 9 outcomes):

```
Layer 0 → Layer 1:  1 → 9          (9 children - acceptable for outcomes)
Layer 1 → Layer 2:  9 → 36         (4 children each)
Layer 2 → Layer 3:  36 → 144       (4 children each)
Layer 3 → Layer 4:  144 → 576      (4 children each)
Layer 4 → Layer 5:  576 → 1,962    (3.4 indicators each)
```

### Why Layer 4 (Indicator Groups) is Critical

**Without Layer 4:**
```
Fine Domain: "Health_Access_Workforce"
  ↓ 13+ indicators appear at once (TOO MANY)
```

**With Layer 4:**
```
Fine Domain: "Health_Access_Workforce"
  ↓ 4 Indicator Groups
    ↓ 3-4 indicators each (MANAGEABLE)
```

### User Experience

```
Click 1: Root → 9 outcomes
Click 2: "Health & Longevity" → 4 coarse domains
Click 3: "Health_Access" → 4 fine domains
Click 4: "Health_Access_Workforce" → 4 indicator groups
Click 5: "Physicians_Group" → 3-4 indicators

Total: 5 clicks to reach indicators
Each step shows 3-5 options (scannable)
```

---

## Required JSON Fields

### Top-Level Keys
- `metadata` - Version, statistics, generation info
- `nodes` - All 2,728 nodes (1 + 9 + 36 + 144 + 576 + 1,962)
- `edges` - Causal (7,368) + Hierarchical (2,727)
- `hierarchy` - Items per layer with parent/children
- `outcomes` - 9 B1 outcomes metadata
- `interactions` - Top 100 from A5
- `clusters` - Fine domains (Layer 3) as clusters

### Node Fields (Required)
```json
{
  "id": "indicator_code",
  "label": "Human readable name",
  "layer": 5,
  "node_type": "outcome|driver|mechanism|intermediate|root|outcome_category|coarse_domain|fine_domain|indicator_group",
  "domain": "Health",
  "subdomain": "Health_Access",
  "shap_importance": 0.00123,
  "in_degree": 5,
  "out_degree": 3,
  "label_source": "World Development Indicators",
  "parent": "group_id",
  "children": [],
  "causal_layer": 3,
  "semantic_path": "Health & Longevity > Health_Access > Workforce > Physicians"
}
```

### Edge Fields (Required)
```json
{
  "source": "indicator_A",
  "target": "indicator_B",
  "relationship": "causal|hierarchical",
  "lag": 2,
  "effect_size": 0.34,
  "p_value": 0.001,
  "ci_lower": 0.29,
  "ci_upper": 0.39,
  "bootstrap_stability": 0.85,
  "sample_size": 4500
}
```

### Hierarchy Structure (Required)
```json
{
  "0": [{"id": "root", "label": "Quality of Life", "parent": null, "children": [...]}],
  "1": [{"id": "outcome_1", "label": "Health & Longevity", "parent": "root", "children": [...]}],
  "2": [...],
  "3": [...],
  "4": [...],
  "5": [...]
}
```

---

## Validation Criteria

### Structure Validation
- [ ] Layer 0: Exactly 1 node (root)
- [ ] Layer 1: Exactly 9 nodes (outcomes)
- [ ] Layer 2: ~36 nodes (4 per outcome)
- [ ] Layer 3: ~144 nodes (4 per coarse)
- [ ] Layer 4: ~576 nodes (4 per fine)
- [ ] Layer 5: 1,962 nodes (indicators)

### 3-5 Children Rule
- [ ] Layer 1-4: Each node has 3-5 children
- [ ] Layer 4→5: Each group has 3-5 indicators
- [ ] Exceptions documented if <3 children unavoidable

### Field Completeness
- [ ] All nodes have required fields
- [ ] All edges have required fields
- [ ] Hierarchy has items for all 6 layers
- [ ] Interactions included (top 100)
- [ ] Clusters included

---

## Output Files

### Primary Output
- `outputs/B5/v2_1_visualization.json` - Full JSON (target ~25MB)
- `outputs/B5/v2_1_visualization_compact.json` - Minified

### Intermediate Outputs
- `outputs/B35/B35_semantic_hierarchy_6layer.pkl` - Hierarchy pickle
- `outputs/B35/B35_node_semantic_paths.json` - Semantic paths lookup

### Cleanup Required
- Delete old 5-layer outputs
- Delete old B35 outputs
- Keep only latest iteration files
