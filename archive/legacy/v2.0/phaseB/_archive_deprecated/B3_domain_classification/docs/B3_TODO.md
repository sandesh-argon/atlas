# B3 TODO: Domain Classification

**Phase**: B3 - Domain Classification
**Input**: 15 semantic clusters from B2 (329 mechanisms)
**Goal**: Add metadata, refine domain labels, validate against literature
**Timeline**: 5-8 hours

---

## Pre-B3 Validation ✅

**Status**: Ready to start (B2 completed with 5/8 validations passed)

**B2 Handoff**:
- [x] 15 clusters created (target: 15-30)
- [x] Mean coherence: 90.6% (target: ≥60%)
- [x] All 329 mechanisms assigned
- [x] Validation results documented
- [x] B2→B3 instructions created

**Known Issues to Address**:
- [ ] 80% clusters labeled "Mixed" (need better domain classification)
- [ ] Silhouette score 0.168 (borderline, can improve with full names)
- [ ] ARI 0.655 (acceptable, but can improve)

---

## 🚨 **PRE-EXECUTION CHECKS (CRITICAL - RUN FIRST)** (25 min)

### Pre-Check 1: Metadata Availability (15 min)

**Purpose**: Verify metadata sources exist before starting Task 1.1

**Why This Matters**: Prevents spending 2 hours trying to load metadata that doesn't exist

**Implementation**: `scripts/run_b3_prechecks.py`

**Checks**:
- A0 metadata files exist (wdi_metadata.json, vdem_codebook.json, etc.)
- Each file has full_name and description fields
- Estimate expected coverage (% of 329 mechanisms)

**Success Criteria**: Expected coverage ≥80%

**Fallback**: If <80%, fetch from online APIs (World Bank, V-Dem) - adds 30-60 min

**Output**: `B3_metadata_availability_report.txt`

---

### Pre-Check 2: Literature Constructs Validation (10 min)

**Purpose**: Verify literature DB exists and has minimum content before Task 3.2

**Why This Matters**: Prevents TF-IDF similarity from failing due to missing constructs

**Implementation**: Part of `scripts/run_b3_prechecks.py`

**Checks**:
- `literature_db/literature_constructs.json` exists
- ≥8 constructs (minimum for meaningful comparison)
- 4 domains covered (Governance, Economic, Health, Education)

**Success Criteria**: ≥8 constructs, 4 domains

**Fallback**: Auto-generate minimal literature DB with 8 core constructs

**Output**: `literature_db/literature_constructs.json` (created if missing)

---

### Pre-Check Decision Gate

**After pre-checks complete, STOP and report**:
1. Metadata coverage: X% expected (sources available: Y/5)
2. Literature constructs: X available (domains covered: Y/4)
3. Decision needed: Proceed with partial metadata OR fetch online?

**If both ≥80%** → Proceed to Part 1
**If either <80%** → Apply fallbacks before continuing

---

## Phase B3 Tasks

### 🎯 **PART 1: Metadata Acquisition** (2-3 hours)

#### Task 1.1: Load Indicator Metadata
**Goal**: Get full indicator names, descriptions, sources for all 329 mechanisms

**Sources**:
- A0 data acquisition scripts (metadata captured during download)
- V-Dem codebook (for v2* variables)
- World Bank WDI metadata (for wdi_* variables)
- UNESCO metadata (for GER*, REPR*, etc.)
- Penn World Tables (for pwt_* variables)

**Output**: `B3_indicator_metadata.json`
```json
{
  "v2dlencmps": {
    "full_name": "Deliberative Component Index",
    "description": "Extent to which the political process is characterized by respectful debate",
    "source": "V-Dem v13",
    "domain": "Governance",
    "sub_domain": "Deliberative Democracy"
  },
  "25056": {
    "full_name": "Primary school completion rate",
    "description": "Percentage of students completing primary education",
    "source": "UNESCO UIS",
    "domain": "Education",
    "sub_domain": "Educational Attainment"
  },
  ...
}
```

**Validation**:
- Coverage: ≥90% of 329 mechanisms have metadata
- Full names: ≥80% have human-readable names
- Sources: All have data source attribution

---

#### Task 1.2: Create Variable Name Enrichment Function
**Goal**: Map variable codes to enriched text for re-embedding

**Implementation**:
```python
def enrich_variable_text(variable_code, metadata):
    """Convert variable code to rich text for embeddings"""

    if variable_code in metadata:
        meta = metadata[variable_code]
        # Combine: full_name + description + domain keywords
        text = f"{meta['full_name']} {meta['description']} {meta['domain']} {meta['sub_domain']}"
        return text
    else:
        # Fallback to enhanced code (like B2)
        return enhance_variable_name(variable_code)
```

**Validation**:
- Test on 10 sample variables
- Verify text is more semantic than codes
- Check embedding quality improves

---

### 🏷️ **PART 2: Domain Classification Refinement** (1-2 hours)

#### Task 2.1: Re-Classify Domains with Metadata
**Goal**: Reduce "Mixed" from 80% to <40% using full indicator names

**Method**:
```python
def classify_domain_with_metadata(variable_code, metadata):
    """Classify domain using full metadata"""

    if variable_code in metadata:
        # Use metadata domain (authoritative)
        return metadata[variable_code]['domain']
    else:
        # Fallback to keyword inference
        return infer_domain(variable_code)
```

**Expected Improvement**:
- Mixed domain: 80% → 30-40%
- Governance: 20% → 30-40%
- Economic: 0% → 15-25%
- Health: 0% → 10-20%
- Education: 0% → 10-15%

**Validation**:
- Check domain distribution across 15 clusters
- Verify ≥60% clusters have clear primary domain
- Accept "Multi-Domain" for cross-cutting clusters (≤30%)

---

#### Task 2.2: Create Hierarchical Domain Structure
**Goal**: Organize domains into parent/sub-domain taxonomy

**Structure**:
```json
{
  "Governance": {
    "sub_domains": ["Judicial", "Legislative", "Executive", "Electoral", "Civil Liberties"],
    "clusters": [1, 9, 16, 20],
    "n_mechanisms": 121
  },
  "Economic": {
    "sub_domains": ["Fiscal", "Monetary", "Trade", "Development", "Labor"],
    "clusters": [0, 4, 11, 13],
    "n_mechanisms": 102
  },
  "Health": {
    "sub_domains": ["Maternal Health", "Child Health", "Life Expectancy", "Disease Burden"],
    "clusters": [6],
    "n_mechanisms": 10
  },
  "Education": {
    "sub_domains": ["Primary", "Secondary", "Tertiary", "Enrollment", "Quality"],
    "clusters": [5, 8, 12, 21],
    "n_mechanisms": 53
  },
  "Multi-Domain": {
    "themes": ["Human Capital", "Inequality", "Conflict"],
    "clusters": [5, 7],
    "n_mechanisms": 43
  }
}
```

**Validation**:
- All 15 clusters assigned to parent domain or multi-domain
- Sub-domains match literature constructs (World Bank, OECD, WHO)
- Multi-domain ≤30% of clusters

---

### 📚 **PART 3: Literature Alignment** (2-3 hours)

#### Task 3.1: Load Literature Constructs Database
**Goal**: Reference known quality-of-life constructs for validation

**Sources**:
- World Bank WGI (Worldwide Governance Indicators)
- OECD Better Life Index
- WHO Global Health Observatory
- UNESCO SDG 4 Education Indicators
- UN Human Development Index

**Structure**: `literature_db/literature_constructs.json`
```json
{
  "rule_of_law": {
    "source": "World Bank WGI",
    "keywords": ["judicial", "courts", "legal", "independence", "corruption"],
    "indicators": ["v2jucomp", "v2jucorrdc", "v2juhcind"],
    "citation": "Kaufmann et al. (2010)"
  },
  "educational_attainment": {
    "source": "UNESCO",
    "keywords": ["enrollment", "completion", "literacy", "school"],
    "indicators": ["GER.4", "REPR.1.G2.CP", "NER.01.F.CP"],
    "citation": "UNESCO (2023)"
  },
  ...
}
```

**Validation**:
- ≥20 literature constructs loaded
- Cover all major domains (Governance, Economic, Health, Education)
- Include citations for academic credibility

---

#### Task 3.2: Compute TF-IDF Similarity
**Goal**: Match B3 clusters to known literature constructs

**Method**:
```python
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# For each cluster
for cluster_id, metadata in cluster_metadata.items():
    # Get cluster text (full names of all variables)
    cluster_text = " ".join([
        enriched_metadata[var]['full_name']
        for var in metadata['nodes']
    ])

    # Compute similarity to all constructs
    similarities = []
    for construct_name, construct in literature_constructs.items():
        construct_text = " ".join(construct['keywords'] + construct['indicators'])

        # TF-IDF similarity
        vectorizer = TfidfVectorizer()
        tfidf = vectorizer.fit_transform([cluster_text, construct_text])
        similarity = cosine_similarity(tfidf[0:1], tfidf[1:2])[0][0]

        similarities.append({
            'construct': construct_name,
            'similarity': similarity,
            'source': construct['source']
        })

    # Top 3 matches
    top_matches = sorted(similarities, key=lambda x: x['similarity'], reverse=True)[:3]
```

**Validation**:
- ≥70% of clusters match known construct (similarity >0.60)
- High confidence: ≥60% of clusters (similarity >0.70)
- Document novel clusters (similarity <0.60) for human review

---

#### Task 3.3: Validate Novel Clusters
**Goal**: Review clusters that don't match literature (potential new discoveries)

**Method**:
- Identify clusters with TF-IDF <0.60 to all constructs
- Manual inspection: Do they represent coherent themes?
- Assign "Novel" label with human-written description
- Flag for deeper investigation in B4/B5

**Expected**: 20-30% of clusters are "novel" (acceptable, not all mechanisms in literature)

**Validation**:
- Novel clusters have ≥60% coherence (structurally valid)
- Novel clusters have clear theme (even if not in literature)
- Document potential new research contributions

---

### 🔬 **PART 4: Cluster Metadata Enrichment** (1-2 hours)

#### Task 4.1: Add Full Metadata to Each Cluster
**Goal**: Complete all fields for B4 pruning and B5 visualization

**Schema** (per cluster):
```json
{
  "cluster_id": 0,
  "cluster_name": "Economic Development: Human Capital",
  "primary_domain": "Economic",
  "sub_domain": "Development",
  "multi_domain_flag": true,
  "secondary_domains": ["Health", "Education"],
  "size": 39,
  "coherence": 0.923,
  "nodes": ["25056", "yprinfi999", ...],
  "top_variables": {
    "by_centrality": [
      {"code": "25056", "name": "Primary school completion rate", "score": 0.436}
    ],
    "by_loading": [...]
  },
  "domain_distribution": {
    "Economic": 20,
    "Health": 10,
    "Education": 9
  },
  "literature_alignment": {
    "matched_construct": "Human Capital Development",
    "tfidf_similarity": 0.72,
    "confidence": "high",
    "source": "World Bank HCI",
    "citation": "Kraay (2018)"
  },
  "metadata": {
    "sources": ["World Bank WDI", "UNESCO", "Penn World Tables"],
    "keywords": ["education", "health", "human capital", "development"],
    "examples": [
      "Primary school completion rate",
      "Human capital index",
      "Life expectancy at birth"
    ],
    "description": "Mechanisms related to building human capital through education and health investments"
  },
  "cross_cutting_themes": ["Inequality", "Sustainability"],
  "visualization_props": {
    "color": "#FF6B6B",
    "icon": "graduation-cap",
    "priority": "high"
  }
}
```

**Validation**:
- All 15 clusters have complete metadata
- All fields populated (no missing values)
- Descriptions are human-readable
- Ready for JSON export

---

#### Task 4.2: Export B3 Classification Schema
**Goal**: Create final B3 output for B4 pruning

**Files**:
1. `B3_domain_classification.json` - Full schema with all metadata
2. `B3_cluster_metadata_complete.json` - Per-cluster detailed metadata
3. `B3_hierarchical_domains.json` - Parent/sub-domain structure
4. `B3_literature_alignment.json` - TF-IDF similarity results

**Validation**:
- All files valid JSON
- Schema matches B4 input requirements
- Documentation explains all fields

---

### ✅ **PART 5: B3 Validation** (30 min)

#### Task 5.1: Run B3 Success Criteria Checks

**Checks**:
```python
# 1. Metadata Coverage
assert metadata_coverage >= 0.90, f"Only {metadata_coverage:.1%} have metadata"

# 2. Domain Balance
assert mixed_domain_pct <= 0.40, f"{mixed_domain_pct:.1%} clusters still Mixed"

# 3. Literature Alignment
assert high_confidence_pct >= 0.60, f"Only {high_confidence_pct:.1%} high confidence"

# 4. Coherence Preservation
assert mean_coherence >= 0.85, f"Coherence dropped to {mean_coherence:.1%}"

# 5. Hierarchical Structure Complete
assert all_clusters_assigned, "Some clusters not assigned to parent domain"

# 6. Novel Clusters Documented
assert all_novel_have_desc, "Some novel clusters lack descriptions"
```

**Target**: 6/6 checks pass

---

#### Task 5.2: Create B3 Validation Report
**Goal**: Document all validation results for Phase B handoff

**File**: `B3_VALIDATION_RESULTS.md`

**Contents**:
- Metadata coverage statistics
- Domain distribution (before/after refinement)
- Literature alignment scores (per cluster)
- Novel cluster justifications
- Validation checklist (6/6 passed)
- Ready-for-B4 confirmation

---

### 📄 **PART 6: Documentation** (30 min)

#### Task 6.1: Create B3 Completion Summary
**File**: `B3_FINAL_STATUS.md`

**Sections**:
- Executive summary (what was accomplished)
- Key results (domain distribution, literature matches)
- Methodology (how domains were classified)
- Validation results (6/6 checks)
- Outputs produced (4 JSON files)
- Recommendations for B4

---

#### Task 6.2: Update README
**File**: `README.md`

**Add**:
- How to load B3 output for B4
- Domain classification schema explanation
- Literature alignment interpretation
- Cross-cutting themes documentation

---

## B3 Success Criteria

| Criterion | Target | Critical Threshold |
|-----------|--------|-------------------|
| **Metadata** |
| Coverage | 95-100% | ≥90% |
| Full names | 90-95% | ≥80% |
| Sources | 100% | 100% |
| **Domain Classification** |
| Mixed domain | 25-35% | ≤40% |
| Clear primary | 70-80% | ≥60% |
| Multi-domain | 20-30% | ≤40% |
| **Literature Alignment** |
| High confidence | 70-85% | ≥60% |
| Matched constructs | 80-90% | ≥70% |
| Novel clusters | 20-30% | ≤40% |
| **Quality** |
| Mean coherence | ≥85% | ≥80% |
| Silhouette (optional) | ≥0.22 | ≥0.20 |
| Hierarchical complete | 100% | 100% |

---

## Timeline Estimate

| Task | Duration | Dependencies |
|------|----------|--------------|
| **Pre-Check 1** | **15 min** | **None (run first)** |
| **Pre-Check 2** | **10 min** | **None (run first)** |
| 1.1 Load metadata | 1.5 hours | Pre-checks pass, A0 data |
| 1.2 Enrichment function | 30 min | 1.1 complete |
| 2.1 Re-classify domains | 1 hour | 1.2 complete |
| 2.2 Hierarchical structure | 1 hour | 2.1 complete |
| 3.1 Load literature DB | 1 hour | - |
| 3.2 TF-IDF similarity | 1.5 hours | 1.1, 3.1 complete |
| 3.3 Validate novel | 30 min | 3.2 complete |
| 4.1 Enrich metadata | 1 hour | 2.2, 3.3 complete |
| 4.2 Export schema | 30 min | 4.1 complete |
| 5.1 Validation checks | 20 min | 4.2 complete |
| 5.2 Validation report | 10 min | 5.1 complete |
| 6.1 Final status | 20 min | 5.2 complete |
| 6.2 Update README | 10 min | 6.1 complete |
| **Total** | **8.5-9.5 hours** | **(+25 min for pre-checks)** |

---

## Outputs Checklist

### Required Files

- [ ] `B3_indicator_metadata.json` - Full metadata for 329 mechanisms
- [ ] `B3_domain_classification.json` - Complete classification schema
- [ ] `B3_cluster_metadata_complete.json` - Per-cluster metadata
- [ ] `B3_hierarchical_domains.json` - Parent/sub-domain structure
- [ ] `B3_literature_alignment.json` - TF-IDF similarity results
- [ ] `B3_VALIDATION_RESULTS.md` - Validation report (6/6 checks)
- [ ] `B3_FINAL_STATUS.md` - Completion summary
- [ ] `README.md` - Updated quick start guide

### Optional (Time Permitting)

- [ ] Re-embed with full names (improve silhouette 0.168 → 0.25+)
- [ ] Create cross-cutting theme analysis
- [ ] Generate cluster visualizations (dendrograms, heatmaps)

---

## Risk Mitigation

### Risk 1: Low Metadata Coverage (<90%)

**Probability**: Medium (30%)

**Mitigation**:
- Priority 1: V-Dem, World Bank WDI (cover 60-70% of mechanisms)
- Priority 2: UNESCO, Penn World Tables (cover 20-30%)
- Priority 3: Manual lookup for remaining 10%

**Fallback**: Accept 85% coverage if >90% infeasible

---

### Risk 2: Literature DB Incomplete

**Probability**: Low (10%)

**Mitigation**:
- Use existing literature from B1 outcome validation
- Supplement with WHO, OECD, World Bank construct databases
- Accept 70% match rate (30% novel acceptable)

**Fallback**: Manual curation of top 10 constructs

---

### Risk 3: Mixed Domain Still High (>40%)

**Probability**: Low (15%)

**Mitigation**:
- Accept "Multi-Domain" as valid category (cross-cutting mechanisms)
- Focus on identifying cross-cutting themes (Human Capital, Inequality, etc.)
- Don't force single-domain labels where inappropriate

**Fallback**: 40% multi-domain acceptable if themes are clear

---

## Next Actions

**IMMEDIATE**:
1. Start Task 1.1: Load indicator metadata from A0 sources
2. Create `literature_db/literature_constructs.json` from B1 materials

**AFTER 1.1**:
3. Test enrichment function on 10 sample variables
4. Proceed to domain re-classification

**GATE**: After Task 2.1, report domain distribution improvement to user

---

## B2 → B3 Handoff

**Input Files** (from B2):
- `B2_semantic_clustering_checkpoint.pkl` - 15 clusters with embeddings
- `B2_cluster_metadata.json` - Initial cluster metadata (80% Mixed)
- `B2_validation_results.json` - 5/8 validations passed

**Known Issues to Fix**:
- 80% clusters labeled "Mixed" → Target: <40%
- Silhouette 0.168 → Target: ≥0.20 (optional)
- Variable codes lack semantic richness → Add full names

**B3 Will Deliver**:
- Complete metadata for all 329 mechanisms
- Refined domain labels (<40% Mixed)
- Literature alignment scores
- Hierarchical domain structure
- Ready for B4 multi-level pruning

---

**Ready to start B3?** Review this TODO and confirm approach before proceeding.
