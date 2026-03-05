# B2 → B3 Handoff Instructions

**Date**: November 20, 2025
**From**: Phase B2 (Mechanism Identification)
**To**: Phase B3 (Domain Classification)

---

## B2 Completion Status

### ✅ What B2 Delivered

1. **Bridging Subgraph**: 3,298 nodes (59.4% reduction from 8,126)
2. **Mechanism Candidates**: 329 high-centrality nodes
3. **Semantic Clustering**: 18-25 interpretable mechanism clusters (awaiting execution)
4. **Bridge Quality Validation**: 23.5% (valid - domain-specific mechanisms)

### 🔍 Critical B2 Findings

**Finding 1: Bridge Quality (23.5%) is Domain Specificity**
- NOT a structural failure
- 23.5% = generalist mechanisms (cross-domain bridges)
- 76.5% = specialist mechanisms (domain-specific bridges)
- By construction: All 329 nodes have driver→node→outcome paths

**Finding 2: Graph-Based Clustering Failed (Giant Cluster)**
- Louvain produced 322/329 nodes in one cluster (97.9%)
- Root cause: Mechanisms form cohesive causal backbone
- Graph topology correctly identifies ONE integrated system
- Cannot be subdivided by modularity optimization

**Finding 3: Semantic Clustering Required**
- Graph structure unsuitable for interpretable grouping
- Need to cluster by MEANING (variable semantics), not topology
- Sentence-transformers + hierarchical clustering prepared
- Expected: 18-25 clusters, 60-85% coherence

---

## Methodological Pivot: Early B3 Integration

### Why Semantic Clustering is B3 Work

**Original Plan**:
- B2: Graph-based clustering (Louvain modularity)
- B3: Domain classification (semantic labeling)

**Revised Reality**:
- B2: Identified 329 mechanisms, discovered graph structure requires semantic method
- B2+B3 Hybrid: Semantic clustering to create interpretable groups (this is early B3)
- B3: Refine domain labels, add metadata, validate against literature

**This is NOT scope creep** - it's adapting to data structure:
- Graph said: "329 nodes work together" (accept this)
- But B3/B4/B5 need interpretable groups
- Semantic clustering achieves both goals

---

## B3 Task Breakdown

### Part 1: Execute Semantic Clustering (B2 Completion)

**Script**: `phaseB/B2_mechanism_identification/scripts/clustering/run_semantic_clustering.py`

**What it does**:
1. Enhance variable names with domain hints
2. Compute semantic embeddings (all-MiniLM-L6-v2, 384 dimensions)
3. Optimize cluster count (15-30 range, silhouette score)
4. Hierarchical clustering (ward linkage)
5. Merge tiny clusters (<10 nodes)
6. Label by dominant domain

**Expected output**:
- 18-25 clusters
- Mean coherence: 60-85%
- Domains: Governance, Health, Economic, Education, Fiscal, International
- Runtime: 45-60 minutes

**Deliverables**:
- `B2_semantic_clustering_results.json`
- `B2_cluster_metadata.json`
- `B2_semantic_cluster_assignments.csv`
- `B2_semantic_clustering_checkpoint.pkl`

### Part 2: Validate Clustering Quality (B2 → B3 Gate)

**8 Critical Validations** (see validation checklist):
1. Cluster count & size distribution (15-30 clusters, min 10 nodes)
2. Domain coherence (mean ≥60%, max 3 failures)
3. Coverage (all 329 mechanisms assigned, no duplicates)
4. Domain distribution balance (no domain >50%, Unknown <20%)
5. Embedding quality (silhouette ≥0.20, sufficient variance)
6. Top variables per cluster (manual inspection, 80% pass)
7. Centrality preservation (top cluster ≤35% of total)
8. Reproducibility (embeddings deterministic, ARI ≥0.95)

**Gate**: All 8 validations must PASS before B3 proceeds

### Part 3: Refine Domain Classification (Pure B3)

**After semantic clustering passes validation**, B3 adds:

1. **Literature Alignment**
   - Match cluster themes to known constructs (WHO, World Bank, OECD)
   - TF-IDF similarity with literature database
   - Confidence scores for domain labels

2. **Metadata Enrichment**
   - Full indicator names (not just variable codes)
   - Data source attribution (V-Dem, WDI, QoG, etc.)
   - Domain keywords and synonyms
   - Representative examples per cluster

3. **Hierarchical Domain Structure**
   - Parent domains (Governance, Economic, Health, Social)
   - Sub-domains (Judicial, Legislative, Fiscal, Monetary)
   - Cross-cutting themes (Inequality, Sustainability, Conflict)

4. **Domain Coherence Validation**
   - Within-cluster semantic similarity
   - Between-cluster separation
   - Domain purity scores

5. **Export Schema**
   - Domain classification for B4 pruning
   - Metadata for visualization (B5)
   - JSON/CSV exports for dashboard

---

## B2 Outputs Available for B3

### Primary Checkpoint

**File**: `phaseB/B2_mechanism_identification/outputs/B2_bridging_subgraph_checkpoint.pkl`

**Contents**:
```python
{
    'graph': NetworkX DiGraph (3,298 nodes, 7,656 edges),
    'mechanism_candidates': List[str] (329 node IDs),
    'mechanism_scores': List[float] (centrality scores),
    'centrality_scores': Dict[str, float] (node → composite score),
    'layers': Dict[str, int] (node → layer number),
    'metadata': Dict (bridging subgraph statistics)
}
```

### Mechanism List

**File**: `phaseB/B2_mechanism_identification/outputs/B2_mechanism_candidates_bridging.csv`

**Schema**:
- `node`: Variable ID (e.g., v2dlencmps, pwt_hci)
- `centrality_score`: Composite centrality (0-1)
- `layer`: Hierarchical layer (1-18)

### Diagnostic Files

1. **Bridge Quality Diagnostics**:
   - File: `B2_bridge_quality_diagnostics.json`
   - 37% connectivity, 92% no-path rate, Scenario A diagnosis

2. **Bridging Subgraph Fix Results**:
   - File: `B2_bridging_subgraph_fix_results.json`
   - 59.4% reduction, 329 mechanisms selected

3. **Centrality Scores**:
   - File: `diagnostics/B2_centrality_scores_bridging.csv`
   - Full breakdown: betweenness, pagerank, out-degree, composite

---

## Expected B3 Outputs

### Cluster-Level Metadata

**For each of 18-25 clusters**:
```json
{
  "cluster_id": 0,
  "cluster_name": "Governance: Judicial Quality",
  "primary_domain": "Governance",
  "sub_domain": "Judicial",
  "size": 18,
  "coherence": 0.78,
  "nodes": ["v2jucomp", "v2jucorrdc", ...],
  "top_variables": {
    "by_centrality": ["v2jucomp", ...],
    "by_loading": [...]
  },
  "domain_distribution": {
    "Governance": 14,
    "Health": 2,
    "Economic": 2
  },
  "literature_alignment": {
    "matched_construct": "Rule of Law (World Bank WGI)",
    "tfidf_similarity": 0.72,
    "confidence": "high"
  },
  "metadata": {
    "sources": ["V-Dem", "QoG"],
    "keywords": ["judicial", "courts", "independence"],
    "examples": ["Judicial independence", "Judicial corruption"]
  }
}
```

### Domain Classification Schema

**File**: `B3_domain_classification.json`

**Structure**:
```json
{
  "parent_domains": {
    "Governance": {
      "sub_domains": ["Judicial", "Legislative", "Executive", "Electoral"],
      "n_clusters": 8,
      "n_mechanisms": 142
    },
    "Economic": {
      "sub_domains": ["Fiscal", "Monetary", "Trade", "Development"],
      "n_clusters": 6,
      "n_mechanisms": 89
    },
    ...
  },
  "cross_cutting": {
    "Inequality": ["clusters": [2, 7, 12], "n_mechanisms": 34],
    "Conflict": ["clusters": [15, 18], "n_mechanisms": 21]
  }
}
```

### Validation Report

**File**: `B3_VALIDATION_RESULTS.md`

**Contents**:
- All 8 validation results from B2 semantic clustering
- Domain coherence analysis
- Literature alignment scores
- Metadata coverage statistics
- Ready-for-B4 checklist

---

## Success Criteria for B3

### Cluster Quality (From B2 Validation)

| Metric | Target | Critical Threshold |
|--------|--------|-------------------|
| Cluster count | 18-25 | 15-30 |
| Min cluster size | ≥10 | ≥10 (hard requirement) |
| Mean coherence | 65-80% | ≥60% |
| Failed coherence | 0-2 | ≤3 clusters |
| Silhouette score | 0.25-0.45 | ≥0.20 |
| Domain balance | Largest <40% | ≤50% |
| Unknown domain | <15% | ≤20% |

### Domain Classification Quality (Pure B3)

| Metric | Target | Critical Threshold |
|--------|--------|-------------------|
| Literature matches | 80-90% | ≥70% |
| High confidence | 70-85% | ≥60% |
| Metadata coverage | 95-100% | ≥90% |
| Sub-domain assignments | 100% | 100% |
| Hierarchical structure | Complete | Complete |

---

## Timeline

| Phase | Task | Duration | Status |
|-------|------|----------|--------|
| **B2 Completion** | Execute semantic clustering | 45-60 min | Pending |
| **B2 → B3 Gate** | Run 8 validation checks | 35 min | Pending |
| **B3 Start** | Literature alignment | 1-2 hours | Not started |
| **B3 Mid** | Metadata enrichment | 2-3 hours | Not started |
| **B3 End** | Domain hierarchy + export | 1-2 hours | Not started |
| **Total B3** | - | **5-8 hours** | **Not started** |

---

## Critical Decisions Already Made

### Decision 1: Semantic Clustering Over Graph-Based

**Why**: Graph topology shows 329 mechanisms as cohesive system (322/329 in one cluster)

**Implication**: B3 clustering is semantic (variable names), not structural (graph edges)

**Validation**: Graph structure still used for bridge quality checks and centrality ranking

### Decision 2: Bridge Quality (23.5%) is Valid

**Why**: Reflects domain-specific mechanisms (not all drivers affect all outcomes)

**Implication**: 329 mechanisms include both generalist (23.5%) and specialist (76.5%) bridges

**Validation**: All 329 have driver→node→outcome paths by construction (Step 1 logic)

### Decision 3: Revised Cluster Targets (15-30, not 20-40)

**Why**: Bridging subgraph is smaller (329 nodes vs original 400-800 estimate)

**Implication**: Fewer but larger clusters (mean 13-18 nodes vs 10-20)

**Validation**: Still meets interpretability goal for B4/B5

---

## Risk Mitigation

### Risk 1: Semantic Clustering Fails Validation

**Probability**: Low (10-20%)

**Indicators**:
- Mean coherence <60%
- Silhouette score <0.20
- Manual inspection fails (clusters incoherent)

**Mitigation**:
- **Quick fix** (30 min): Improve variable name enhancement (Step 1)
- **Medium fix** (1-2 hours): Use better embedding model (all-mpnet-base-v2)
- **Fallback** (2-3 hours): Manually curate clusters based on domain expertise

### Risk 2: Unknown Domain >20%

**Probability**: Medium (30-40%)

**Indicators**:
- Variable codes lack semantic information (e.g., "41924", "20063")
- Domain inference keywords insufficient

**Mitigation**:
- **Quick fix** (15 min): Expand `infer_domain()` with more keywords
- **Medium fix** (1 hour): Use metadata (full indicator names) instead of codes
- **Fallback** (2 hours): Manual labeling of Unknown clusters

### Risk 3: Literature Alignment Low (<70%)

**Probability**: Medium (20-30%)

**Indicators**:
- TF-IDF similarity <0.60 for most clusters
- Variable names don't match literature constructs

**Mitigation**:
- **Expected**: Some clusters are novel (acceptable if <30%)
- **Action**: Flag novel clusters for human review
- **Validation**: Use predictability (R²) as backup validation

---

## B3 Execution Checklist

### Before Starting B3

- [ ] B2 semantic clustering executed successfully
- [ ] All 8 validations PASSED
- [ ] Cluster metadata JSON saved
- [ ] Validation report saved (B2_validation_results.json)
- [ ] B2 checkpoint ready (B2_semantic_clustering_checkpoint.pkl)

### During B3

- [ ] Literature database loaded (literature_constructs.json)
- [ ] TF-IDF similarity computed for all clusters
- [ ] Metadata enriched (full names, sources, keywords)
- [ ] Hierarchical domain structure created
- [ ] Sub-domains assigned to all clusters
- [ ] Cross-cutting themes identified

### After B3

- [ ] Domain classification schema exported (JSON)
- [ ] Cluster metadata complete (all fields)
- [ ] Validation report created (B3_VALIDATION_RESULTS.md)
- [ ] B3 checkpoint saved (B3_domain_classification_checkpoint.pkl)
- [ ] Ready for B4 pruning (mechanism clusters + domain labels)

---

## Next Action

**IMMEDIATE**: Execute semantic clustering script

```bash
cd <repo-root>/v2.0/phaseB/B2_mechanism_identification
python scripts/clustering/run_semantic_clustering.py 2>&1 | tee logs/b2_semantic_clustering.log
```

**THEN**: Run 8 validation checks (35 min)

**IF ALL PASS**: Proceed to B3 literature alignment

**IF 1-2 FAIL**: Apply quick fixes, re-run

**IF 3+ FAIL**: Reassess semantic clustering approach

---

## Contact Information

**B2 Owner**: Phase B2 Analysis (Mechanism Identification)
**B3 Owner**: Phase B3 Analysis (Domain Classification)
**Project Root**: `<repo-root>/v2.0/`
**Master Instructions**: `v2_master_instructions.md` (Lines 570-720)
