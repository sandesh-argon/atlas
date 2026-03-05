# V2.1 Documentation Index

## Overview

This directory contains comprehensive technical documentation for the V2.1 Global Causal Discovery System, focusing on the A6 Hierarchical Layering and Phase B Interpretability Layer components.

**Created**: December 5, 2025

**Total Documentation**: ~6,900 lines across 8 files

---

## New Documentation (December 5, 2025)

### A6_DOCUMENTATION.md (678 lines, 17 KB)

**Covers**: A6 Hierarchical Layering - Complete technical documentation

**Key Topics**:
- Topological sort layer assignment algorithm
- Critical interaction node fix (December 2025)
- Centrality metrics (PageRank, Betweenness, Degree)
- DAG validation and known outcome placement
- Output schema with edge moderator metadata
- Performance benchmarks and optimization strategies

**Use When**: Understanding layer assignment, debugging cycles, optimizing betweenness computation

**Location**: `<repo-root>/v2.0/v2.1/docs/A6_DOCUMENTATION.md`

---

### PHASE_B_DOCUMENTATION.md (1,894 lines, 55 KB)

**Covers**: Complete Phase B Interpretability Layer (B1, B2, B2.5, B3.5)

**Major Sections**:

#### B1: Outcome Discovery (450 lines)
- Hybrid approach (data-driven factor analysis + theory-driven fallback)
- Interpretability criteria (domain coherence + loading strength)
- Factor analysis methodology
- Output schema with 9 validated outcomes

#### B2: Semantic Clustering (520 lines)
- Two-stage clustering strategy
- Keyword-based coarse clustering (73 clusters, 55-60% coverage)
- Embedding-based assignment (remaining 40-45%)
- Sub-clustering to 168 fine clusters
- 100% coverage guarantee

#### B2.5: SHAP Computation (380 lines)
- LightGBM TreeSHAP methodology
- Panel data construction
- Aggregation across outcomes
- Normalization and scoring
- Checkpointing and resume logic

#### B3.5: Semantic Hierarchy Builder (540 lines)
- 7-level hierarchy architecture
- Composite SHAP scoring
- Edge moderator metadata integration
- Layer compression presets
- Top-K lists
- Visualization-ready JSON export

**Use When**: Understanding interpretability layer, debugging clustering, optimizing SHAP computation

**Location**: `<repo-root>/v2.0/v2.1/docs/PHASE_B_DOCUMENTATION.md`

---

## Existing Documentation

### architecture_overview.md (650 lines, 20 KB)
High-level system architecture and pipeline flow

### README.md (552 lines, 18 KB)
Quick start guide and project introduction

### A0_data_acquisition.md (533 lines, 16 KB)
Data source documentation and acquisition pipeline

### A1_missingness_analysis.md (301 lines, 9.4 KB)
Missingness sensitivity analysis and imputation strategy

### A2_granger_causality.md (1,237 lines, 38 KB)
Granger causality testing with prefiltering

### A3_conditional_independence.md (1,048 lines, 31 KB)
PC-Stable algorithm and edge orientation

---

## Quick Navigation

### By Task

**Setting up the project**:
- Start with: `README.md`
- Then: `architecture_overview.md`

**Understanding Phase A (Statistical Discovery)**:
1. `A0_data_acquisition.md` - Data sources
2. `A1_missingness_analysis.md` - Imputation
3. `A2_granger_causality.md` - Temporal causation
4. `A3_conditional_independence.md` - Spurious edge removal
5. `A6_DOCUMENTATION.md` - Layer assignment

**Understanding Phase B (Interpretability)**:
- Complete guide: `PHASE_B_DOCUMENTATION.md`
- Quick reference: See "Major Sections" above

**Debugging Issues**:
- A6 cycles: `A6_DOCUMENTATION.md` → "Common Issues" section
- B1 factor analysis: `PHASE_B_DOCUMENTATION.md` → "B1 Validation"
- B2 unclassified nodes: `PHASE_B_DOCUMENTATION.md` → "B2 Validation"
- B2.5 SHAP timeout: `PHASE_B_DOCUMENTATION.md` → "Common Issues"

**Optimizing Performance**:
- A6 betweenness: `A6_DOCUMENTATION.md` → "Performance Characteristics"
- B2.5 parallelization: `PHASE_B_DOCUMENTATION.md` → "Optimization Opportunities"

---

## Documentation Statistics

| File | Lines | Size | Focus |
|------|-------|------|-------|
| PHASE_B_DOCUMENTATION.md | 1,894 | 55 KB | B1, B2, B2.5, B3.5 complete |
| A2_granger_causality.md | 1,237 | 38 KB | Granger testing |
| A3_conditional_independence.md | 1,048 | 31 KB | PC-Stable |
| A6_DOCUMENTATION.md | 678 | 17 KB | Hierarchical layering |
| architecture_overview.md | 650 | 20 KB | System architecture |
| README.md | 552 | 18 KB | Quick start |
| A0_data_acquisition.md | 533 | 16 KB | Data sources |
| A1_missingness_analysis.md | 301 | 9.4 KB | Imputation |
| **Total** | **6,893** | **204 KB** | **Complete pipeline** |

---

## Key Concepts Cross-Reference

### Interaction Nodes (CRITICAL FIX)
- **What**: A5 interactions should be edge metadata, NOT virtual nodes
- **Why**: Virtual nodes inflated count from 3,872 to 8,126 (52.4% fake)
- **Where documented**: `A6_DOCUMENTATION.md` → "Critical Architectural Decision"
- **Related**: `PHASE_B_DOCUMENTATION.md` → B3.5 edge moderators

### SHAP Scoring
- **What**: Feature importance for outcome prediction
- **Why**: Identifies outcome indicators vs drivers
- **Where documented**: `PHASE_B_DOCUMENTATION.md` → "B2.5: SHAP Computation"
- **Related**: `PHASE_B_DOCUMENTATION.md` → B3.5 composite scoring

### Semantic Clustering
- **What**: Domain-based organization of 1,962 indicators
- **Why**: Enables interpretable visualization hierarchy
- **Where documented**: `PHASE_B_DOCUMENTATION.md` → "B2: Semantic Clustering"
- **Related**: `PHASE_B_DOCUMENTATION.md` → B3.5 hierarchy structure

### Layer Compression
- **What**: Grouping 21 causal layers into 2-7 bands for visualization
- **Why**: Progressive disclosure (minimal → detailed views)
- **Where documented**: `PHASE_B_DOCUMENTATION.md` → "Layer Compression Presets"
- **Related**: `A6_DOCUMENTATION.md` → layer assignment

---

## File Locations

**Documentation Root**: `<repo-root>/v2.0/v2.1/docs/`

**Scripts**:
- A6: `<repo-root>/v2.0/v2.1/scripts/A6/`
- B1: `<repo-root>/v2.0/v2.1/scripts/B1/`
- B2: `<repo-root>/v2.0/v2.1/scripts/B2/`
- B2.5: `<repo-root>/v2.0/v2.1/scripts/B25/`
- B3.5: `<repo-root>/v2.0/v2.1/scripts/B35/`

**Outputs**:
- A6: `<repo-root>/v2.0/v2.1/outputs/A6/`
- B1: `<repo-root>/v2.0/v2.1/outputs/B1/`
- B2: `<repo-root>/v2.0/v2.1/outputs/B2/`
- B2.5: `<repo-root>/v2.0/v2.1/outputs/B25/`
- B3.5: `<repo-root>/v2.0/v2.1/outputs/B35/`

**Final Visualization JSON**: `<repo-root>/v2.0/v2.1/outputs/B35/causal_graph_v2_FINAL.json`

---

## Version History

### December 5, 2025 - A6 and Phase B Documentation
**Added**:
- `A6_DOCUMENTATION.md` (678 lines) - Complete A6 hierarchical layering documentation
- `PHASE_B_DOCUMENTATION.md` (1,894 lines) - Complete Phase B interpretability layer documentation

**Coverage**:
- A6 topological sort and layer assignment
- Interaction node fix (critical architectural decision)
- B1 outcome discovery (hybrid approach)
- B2 semantic clustering (100% coverage)
- B2.5 SHAP computation (LightGBM TreeSHAP)
- B3.5 semantic hierarchy builder (7-level structure)
- Edge moderator metadata integration
- Visualization-ready JSON export

**Total New Documentation**: 2,572 lines, 72 KB

---

## Contributing to Documentation

When adding new documentation:

1. **Follow existing structure**:
   - Overview section
   - Algorithm/methodology details
   - Input/output schemas
   - Examples and code snippets
   - Success criteria
   - Common issues and solutions

2. **Use markdown features**:
   - Code blocks with language tags
   - Tables for comparisons
   - Diagrams using ASCII art or Mermaid
   - Cross-references to other docs

3. **Update this index**:
   - Add new file to "Quick Navigation"
   - Update statistics table
   - Add cross-references if relevant

4. **Include**:
   - File locations (absolute paths)
   - Runtime estimates
   - Memory requirements
   - Validation criteria

---

## Contact

**Project**: V2.1 Global Causal Discovery System

**Documentation Maintainer**: Phase B V2.1 Team

**Last Updated**: December 5, 2025
