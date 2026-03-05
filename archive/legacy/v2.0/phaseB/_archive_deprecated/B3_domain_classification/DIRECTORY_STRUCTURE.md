# B3 Directory Structure

**Last Updated**: November 20, 2025

---

## Root Directory (5 files)

```
B3_domain_classification/
├── README.md                          # Quick start guide, integration examples
├── B3_QUICK_SUMMARY.md                # 1-page summary (results, metrics, next steps)
├── B3_COMPLETION_SUMMARY.md           # Full methodology, timeline, improvements
├── B3_FINAL_STATUS.md                 # B4 handoff instructions, pruning strategy
└── B3_VALIDATION_RESULTS.md           # Detailed validation report (5/6 checks)
```

---

## Subdirectories

### `outputs/` - All B3 Results

**Primary Files**:
- `B3_part4_enriched.pkl` (0.87 MB) - **PRIMARY INPUT FOR B4**
- `B3_cluster_metadata_complete.json` - Full cluster metadata (human-readable)
- `B3_hierarchical_domains.json` - Domain taxonomy summary
- `B3_validation_results.json` - Structured validation data

**Classifications**:
- `B3_final_classifications.json` - Final domain assignments with overrides
- `B3_final_domain_assignments.csv` - Mechanism-to-domain mapping
- `B3_manual_overrides.json` - Manual override documentation

**Cluster Reports**:
- `B3_cluster_reports/` - 15 individual cluster markdown reports

**Intermediate Checkpoints**:
- `B3_task1_metadata_enriched.pkl` - Part 1 output
- `B3_part2_domain_classified.pkl` - Part 2 output
- `B3_part3_literature_aligned.pkl` - Part 3 output
- `B3_part3_manual_overrides.pkl` - After manual overrides

---

### `scripts/` - Execution Scripts (13 files)

**Pre-Execution**:
- `run_b3_prechecks.py` - Metadata availability and literature validation checks

**Part 1: Metadata Acquisition**:
- `fetch_metadata_from_apis.py` - Fetch from WDI, V-Dem, UNESCO, Penn APIs
- `match_v1_metadata.py` - Match against V1.0 indicator databases
- `create_fallback_metadata.py` - Create inferred metadata from patterns
- `merge_all_metadata.py` - Unify all metadata sources
- `task1_load_metadata.py` - Main Part 1 script (merge metadata with B2 clusters)

**Part 2: Domain Classification**:
- `part2_domain_classification.py` - TF-IDF matching + source hints

**Part 3: Literature Alignment**:
- `part3_literature_alignment.py` - Deep TF-IDF analysis, keyword matching

**Manual Analysis**:
- `apply_manual_overrides.py` - Apply pattern-based manual overrides

**Part 4: Metadata Enrichment**:
- `part4_metadata_enrichment.py` - Hierarchical labels, descriptions, cluster reports

**Part 5: Validation**:
- `part5_validation.py` - 6 validation checks, generate reports

**Part 6: Documentation**:
- `part6_documentation.py` - Create completion summary, final status, README

---

### `logs/` - Execution Logs (11 files)

- `b3_prechecks_final.log` - Pre-execution checks
- `metadata_fetch.log` - API metadata fetching
- `v1_metadata_matching.log` - V1.0 database matching
- `b3_task1_load_metadata.log` - Part 1 execution
- `b3_part2_domain_classification.log` - Part 2 execution
- `b3_part3_literature_alignment.log` - Part 3 execution
- `b3_manual_overrides.log` - Manual override application
- `b3_part4_enrichment.log` - Part 4 execution
- `b3_part5_validation.log` - Part 5 execution
- `b3_part6_documentation.log` - Part 6 execution

---

### `docs/` - Planning & Intermediate Documentation (5 files)

**Planning**:
- `B3_TODO.md` - Original task plan (6 parts, pre-checks, timeline)
- `B2_TO_B3_INSTRUCTIONS.md` - B2→B3 handoff instructions

**Intermediate Summaries**:
- `B3_PART1_SUMMARY.md` - Part 1 metadata coverage details
- `B3_METADATA_FETCH_SUMMARY.md` - API fetching results
- `B3_metadata_availability_report.txt` - Pre-check results

---

## File Sizes

### Checkpoints
```
B3_task1_metadata_enriched.pkl        0.82 MB
B3_part2_domain_classified.pkl        0.85 MB
B3_part3_literature_aligned.pkl       0.86 MB
B3_part3_manual_overrides.pkl         0.86 MB
B3_part4_enriched.pkl                 0.87 MB  ← PRIMARY B4 INPUT
```

### JSON Outputs
```
B3_cluster_metadata_complete.json     55 KB
B3_final_domain_assignments.csv       48 KB
B3_hierarchical_domains.json          2 KB
B3_validation_results.json            1.3 KB
```

---

## Quick Access

### For B4 Integration
**Start here**: `B3_FINAL_STATUS.md`
**Load checkpoint**: `outputs/B3_part4_enriched.pkl`

### For Validation Review
**Start here**: `B3_VALIDATION_RESULTS.md`
**Data**: `outputs/B3_validation_results.json`

### For Cluster Details
**Reports**: `outputs/B3_cluster_reports/cluster_XX.md` (15 files)
**Metadata**: `outputs/B3_cluster_metadata_complete.json`

### For Methodology
**Full details**: `B3_COMPLETION_SUMMARY.md`
**Quick summary**: `B3_QUICK_SUMMARY.md`

---

## Comparison to Previous Phases

### B1 Structure
```
B1_outcome_discovery/
├── README.md
├── B1_QUICK_SUMMARY.md
├── B1_COMPLETION_SUMMARY.md
├── B1_FINAL_STATUS.md
├── B1_VALIDATION_RESULTS.md
├── diagnostics/
├── logs/
├── outputs/
├── scripts/
└── validation_scripts/
```

### B2 Structure
```
B2_mechanism_identification/
├── README.md
├── B2_QUICK_SUMMARY.md
├── B2_COMPLETION_SUMMARY.md
├── B2_FINAL_STATUS.md
├── B2_VALIDATION_RESULTS.md
├── diagnostics/
├── logs/
├── outputs/
└── scripts/
```

### B3 Structure (Current)
```
B3_domain_classification/
├── README.md
├── B3_QUICK_SUMMARY.md
├── B3_COMPLETION_SUMMARY.md
├── B3_FINAL_STATUS.md
├── B3_VALIDATION_RESULTS.md
├── docs/           ← Planning & intermediate docs
├── logs/
├── outputs/
└── scripts/
```

**Note**: B3 adds `docs/` subdirectory for planning materials and intermediate summaries, as B3 had more iterative metadata work than B1/B2.

---

**Total Files**: ~50 (5 root MDs + 13 scripts + 11 logs + 5 docs + 16 outputs)
**Total Size**: ~5 MB (mostly checkpoints)
**Structure**: Clean, matches B1/B2 patterns
