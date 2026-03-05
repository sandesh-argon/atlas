#!/bin/bash
# V2.0 PHASE A COMPLETE EXPORT
# Creates disaster recovery backup with all critical checkpoints and documentation
# Date: November 20, 2025

set -e  # Exit on error

EXPORT_DIR="<repo-root>/v2.0/phaseA_export"
PHASE_A_DIR="<repo-root>/v2.0/phaseA"

echo "========================================================================"
echo "V2.0 PHASE A EXPORT - DISASTER RECOVERY BACKUP"
echo "========================================================================"
echo "Export directory: $EXPORT_DIR"
echo ""

# Clean and create export directory
rm -rf "$EXPORT_DIR"
mkdir -p "$EXPORT_DIR"

# ============================================================================
# 01: A1 MISSINGNESS ANALYSIS
# ============================================================================
echo "📦 [1/7] Exporting A1: Missingness Analysis..."
mkdir -p "$EXPORT_DIR/01_A1_missingness"

# Critical outputs (preprocessed data for A2)
cp "$PHASE_A_DIR/A1_missingness_analysis/outputs/A2_preprocessed_data.pkl" \
   "$EXPORT_DIR/01_A1_missingness/" 2>/dev/null || echo "  ⚠️  A2_preprocessed_data.pkl not found"

# Imputed data (if exists)
cp "$PHASE_A_DIR/A1_missingness_analysis/outputs/A1_imputed_data.pkl" \
   "$EXPORT_DIR/01_A1_missingness/" 2>/dev/null || echo "  ⚠️  A1_imputed_data.pkl not found"

# Documentation
cp "$PHASE_A_DIR/A1_missingness_analysis"/*.md \
   "$EXPORT_DIR/01_A1_missingness/" 2>/dev/null || true

# Scripts
mkdir -p "$EXPORT_DIR/01_A1_missingness/scripts"
cp -r "$PHASE_A_DIR/A1_missingness_analysis/scripts"/* \
   "$EXPORT_DIR/01_A1_missingness/scripts/" 2>/dev/null || true

echo "  ✅ A1 exported"

# ============================================================================
# 02: A2 GRANGER CAUSALITY
# ============================================================================
echo "📦 [2/7] Exporting A2: Granger Causality..."
mkdir -p "$EXPORT_DIR/02_A2_granger"

# Critical outputs (FDR corrected results)
cp "$PHASE_A_DIR/A2_granger_causality/outputs/granger_fdr_corrected.pkl" \
   "$EXPORT_DIR/02_A2_granger/" 2>/dev/null || echo "  ⚠️  granger_fdr_corrected.pkl not found"

cp "$PHASE_A_DIR/A2_granger_causality/outputs/granger_test_results.pkl" \
   "$EXPORT_DIR/02_A2_granger/" 2>/dev/null || echo "  ⚠️  granger_test_results.pkl not found"

# Significant edges (if exists)
cp "$PHASE_A_DIR/A2_granger_causality/outputs/significant_edges_fdr.pkl" \
   "$EXPORT_DIR/02_A2_granger/" 2>/dev/null || true

# Documentation
cp "$PHASE_A_DIR/A2_granger_causality"/*.md \
   "$EXPORT_DIR/02_A2_granger/" 2>/dev/null || true

# Scripts
mkdir -p "$EXPORT_DIR/02_A2_granger/scripts"
cp -r "$PHASE_A_DIR/A2_granger_causality/scripts"/* \
   "$EXPORT_DIR/02_A2_granger/scripts/" 2>/dev/null || true

echo "  ✅ A2 exported"

# ============================================================================
# 03: A3 CONDITIONAL INDEPENDENCE (SKIPPED - BUT KEEP PLACEHOLDER)
# ============================================================================
echo "📦 [3/7] A3: Conditional Independence (SKIPPED in actual workflow)"
mkdir -p "$EXPORT_DIR/03_A3_conditional_independence"
echo "A3 was skipped - went directly from A2 to A4" > "$EXPORT_DIR/03_A3_conditional_independence/README.txt"

# ============================================================================
# 04: A4 EFFECT QUANTIFICATION
# ============================================================================
echo "📦 [4/7] Exporting A4: Effect Quantification..."
mkdir -p "$EXPORT_DIR/04_A4_effects"

# Critical outputs (validated edges with effect sizes)
cp "$PHASE_A_DIR/A4_effect_quantification/outputs/lasso_effect_estimates_WITH_WARNINGS.pkl" \
   "$EXPORT_DIR/04_A4_effects/" 2>/dev/null || echo "  ⚠️  lasso_effect_estimates_WITH_WARNINGS.pkl not found"

cp "$PHASE_A_DIR/A4_effect_quantification/outputs/lasso_effect_estimates_STANDARDIZED.pkl" \
   "$EXPORT_DIR/04_A4_effects/" 2>/dev/null || true

# All results (if exists)
cp "$PHASE_A_DIR/A4_effect_quantification/outputs/all_results.pkl" \
   "$EXPORT_DIR/04_A4_effects/" 2>/dev/null || true

# Documentation
cp "$PHASE_A_DIR/A4_effect_quantification"/*.md \
   "$EXPORT_DIR/04_A4_effects/" 2>/dev/null || true

# Scripts
mkdir -p "$EXPORT_DIR/04_A4_effects/scripts"
cp -r "$PHASE_A_DIR/A4_effect_quantification/scripts"/* \
   "$EXPORT_DIR/04_A4_effects/scripts/" 2>/dev/null || true

echo "  ✅ A4 exported"

# ============================================================================
# 05: A5 INTERACTION DISCOVERY
# ============================================================================
echo "📦 [5/7] Exporting A5: Interaction Discovery..."
mkdir -p "$EXPORT_DIR/05_A5_interactions"

# Critical outputs (validated interactions)
cp "$PHASE_A_DIR/A5_interaction_discovery/outputs/A5_interaction_results_FILTERED_STRICT.pkl" \
   "$EXPORT_DIR/05_A5_interactions/" 2>/dev/null || echo "  ⚠️  A5_interaction_results_FILTERED_STRICT.pkl not found"

cp "$PHASE_A_DIR/A5_interaction_discovery/outputs/A5_interaction_results.pkl" \
   "$EXPORT_DIR/05_A5_interactions/" 2>/dev/null || true

# Documentation
cp "$PHASE_A_DIR/A5_interaction_discovery"/*.md \
   "$EXPORT_DIR/05_A5_interactions/" 2>/dev/null || true

# Scripts
mkdir -p "$EXPORT_DIR/05_A5_interactions/scripts"
cp -r "$PHASE_A_DIR/A5_interaction_discovery/scripts"/* \
   "$EXPORT_DIR/05_A5_interactions/scripts/" 2>/dev/null || true

echo "  ✅ A5 exported"

# ============================================================================
# 06: A6 HIERARCHICAL LAYERING
# ============================================================================
echo "📦 [6/7] Exporting A6: Hierarchical Layering..."
mkdir -p "$EXPORT_DIR/06_A6_hierarchy"

# Critical outputs (final hierarchical graph - PRIMARY INPUT FOR PHASE B)
cp "$PHASE_A_DIR/A6_hierarchical_layering/outputs/A6_hierarchical_graph.pkl" \
   "$EXPORT_DIR/06_A6_hierarchy/" 2>/dev/null || echo "  ⚠️  A6_hierarchical_graph.pkl not found"

cp "$PHASE_A_DIR/A6_hierarchical_layering/outputs/A6_layer_assignments.csv" \
   "$EXPORT_DIR/06_A6_hierarchy/" 2>/dev/null || true

cp "$PHASE_A_DIR/A6_hierarchical_layering/outputs/A6_graph_statistics.txt" \
   "$EXPORT_DIR/06_A6_hierarchy/" 2>/dev/null || true

# Documentation
cp "$PHASE_A_DIR/A6_hierarchical_layering"/*.md \
   "$EXPORT_DIR/06_A6_hierarchy/" 2>/dev/null || true

# Scripts
mkdir -p "$EXPORT_DIR/06_A6_hierarchy/scripts"
cp -r "$PHASE_A_DIR/A6_hierarchical_layering/scripts"/* \
   "$EXPORT_DIR/06_A6_hierarchy/scripts/" 2>/dev/null || true

echo "  ✅ A6 exported"

# ============================================================================
# 07: PROJECT-LEVEL FILES
# ============================================================================
echo "📦 [7/7] Exporting project-level files..."
mkdir -p "$EXPORT_DIR/00_project_docs"

# Master instructions
cp "<repo-root>/v2.0/v2_master_instructions.md" \
   "$EXPORT_DIR/00_project_docs/" 2>/dev/null || true

# CLAUDE.md
cp "<repo-root>/v2.0/CLAUDE.md" \
   "$EXPORT_DIR/00_project_docs/" 2>/dev/null || true

# Phase A validation
cp "$PHASE_A_DIR/validate_phase_a.py" \
   "$EXPORT_DIR/00_project_docs/" 2>/dev/null || true

cp "$PHASE_A_DIR/PHASE_A_VALIDATION_SUMMARY.md" \
   "$EXPORT_DIR/00_project_docs/" 2>/dev/null || true

# Git info
cd <repo-root>/v2.0
git log --oneline -20 > "$EXPORT_DIR/00_project_docs/git_recent_commits.txt" 2>/dev/null || true
git status > "$EXPORT_DIR/00_project_docs/git_status.txt" 2>/dev/null || true

echo "  ✅ Project docs exported"

# ============================================================================
# CREATE MANIFEST & README
# ============================================================================
echo ""
echo "📝 Creating export manifest..."

cat > "$EXPORT_DIR/EXPORT_MANIFEST.txt" << 'EOF'
V2.0 PHASE A EXPORT - DISASTER RECOVERY BACKUP
===============================================
Export Date: November 20, 2025
Phase A Status: COMPLETE & VALIDATED
Ready for Phase B: YES

CRITICAL FILES FOR RECOVERY
============================

PRIMARY INPUTS FOR PHASE B:
---------------------------
06_A6_hierarchy/A6_hierarchical_graph.pkl (200-300 MB)
  → 8,126 nodes, 22,521 edges, 21 hierarchical layers
  → Load this to start Phase B1 (Outcome Discovery)

PHASE A CHECKPOINTS:
-------------------
01_A1_missingness/A2_preprocessed_data.pkl (530 MB)
  → 6,368 preprocessed indicators (1990-2024)
  → Input for A2 Granger testing

02_A2_granger/granger_fdr_corrected.pkl (200-300 MB)
  → 1,157,230 Granger-validated edges @ FDR q<0.01
  → Input for A4 effect quantification

04_A4_effects/lasso_effect_estimates_WITH_WARNINGS.pkl (300-400 MB)
  → 9,759 effect-quantified edges with confidence intervals
  → Input for A5 interaction discovery

05_A5_interactions/A5_interaction_results_FILTERED_STRICT.pkl (50-100 MB)
  → 4,254 validated mechanism interactions (|β₃| ≥ 5.0)
  → Input for A6 hierarchical layering

VALIDATION:
-----------
00_project_docs/validate_phase_a.py
  → Automated validation script (4 checks)
  → Run: python3 validate_phase_a.py

00_project_docs/PHASE_A_VALIDATION_SUMMARY.md
  → Complete validation results (all 4 checks passed)

RECOVERY PROCEDURE:
===================

1. Copy this export folder to new machine
2. Install dependencies: pip install -r requirements.txt (if exists)
3. Verify Phase A completion:
   python3 00_project_docs/validate_phase_a.py

4. Start Phase B1 (Outcome Discovery):
   - Load: 06_A6_hierarchy/A6_hierarchical_graph.pkl
   - Method: Factor analysis on top-layer nodes
   - Expected: 12-20 outcome dimensions

FILE STRUCTURE:
===============
00_project_docs/          Project-level documentation
01_A1_missingness/        Missingness analysis outputs
02_A2_granger/            Granger causality outputs
03_A3_conditional_independence/  (SKIPPED - placeholder only)
04_A4_effects/            Effect quantification outputs
05_A5_interactions/       Interaction discovery outputs
06_A6_hierarchy/          Hierarchical layering outputs (PHASE B INPUT)

ESTIMATED TOTAL SIZE: 1.5-2.5 GB
EOF

# Create detailed README
cat > "$EXPORT_DIR/README.md" << 'EOF'
# V2.0 PHASE A COMPLETE EXPORT

**Export Date**: November 20, 2025
**Phase A Status**: ✅ COMPLETE & VALIDATED
**Ready for Phase B**: YES

---

## Quick Start

### Verify Export Integrity
```bash
python3 00_project_docs/validate_phase_a.py
```

### Start Phase B1 (Outcome Discovery)
```python
import pickle

# Load hierarchical graph
with open('06_A6_hierarchy/A6_hierarchical_graph.pkl', 'rb') as f:
    a6_data = pickle.load(f)

graph = a6_data['graph']  # 8,126 nodes, 22,521 edges
layers = a6_data['layers']  # {node_id: layer_number (0-20)}
centrality = a6_data['centrality']  # PageRank, Betweenness, Degree
```

---

## Export Contents

### Critical Checkpoints (1.5-2.5 GB total)

| File | Size | Description |
|------|------|-------------|
| `01_A1_missingness/A2_preprocessed_data.pkl` | 530 MB | 6,368 preprocessed indicators |
| `02_A2_granger/granger_fdr_corrected.pkl` | 200-300 MB | 1.16M Granger edges |
| `04_A4_effects/lasso_effect_estimates_WITH_WARNINGS.pkl` | 300-400 MB | 9,759 effect-quantified edges |
| `05_A5_interactions/A5_interaction_results_FILTERED_STRICT.pkl` | 50-100 MB | 4,254 interactions |
| `06_A6_hierarchy/A6_hierarchical_graph.pkl` | 200-300 MB | **PRIMARY PHASE B INPUT** |

### Scripts & Documentation

All Python scripts are included in `*/scripts/` subdirectories for each phase.

Documentation files (README.md, FINAL_STATUS.md, etc.) are included for each phase.

---

## Phase A Final Statistics

- **Indicators**: 6,368 (after filtering)
- **Temporal window**: 1990-2024 (35 years)
- **Granger pairs tested**: 9.26M
- **Granger edges (FDR q<0.01)**: 1,157,230
- **Effect-quantified edges**: 9,759
- **Interactions discovered**: 4,254
- **Final graph**: 8,126 nodes, 22,521 edges, 21 layers
- **Connectivity**: 99.0% in main component

---

## Validation Results

All 4 pre-Phase-B validations **PASSED** ✅

1. ✅ **End-to-End Integrity**: Complete A1→A2→A4→A5→A6 chain
2. ✅ **No Data Leakage**: 0 self-loops, temporal precedence enforced
3. ✅ **Scale Consistency**: A4 median |β| = 0.264, A5 median |β₃| = 6.863
4. ✅ **Literature Sanity**: 9,759 causal edges within expected range

---

## Recovery Instructions

### If Desktop Destroyed

1. **Copy export to new machine**
2. **Install Python dependencies**:
   ```bash
   pip install pandas numpy pickle networkx scikit-learn
   ```

3. **Verify integrity**:
   ```bash
   cd phaseA_export
   python3 00_project_docs/validate_phase_a.py
   ```

4. **Resume from Phase B1**:
   - Primary input: `06_A6_hierarchy/A6_hierarchical_graph.pkl`
   - Expected runtime: 8-12 hours
   - Expected output: 12-20 validated outcome dimensions

### If Need to Re-run Phase A

All scripts are included. To re-run from scratch:
1. Start with `01_A1_missingness/scripts/`
2. Follow chain: A1 → A2 → A4 → A5 → A6
3. Each step's output is the next step's input

**Estimated total Phase A runtime**: 14-21 days

---

## Git Information

Last commits and repository status are saved in:
- `00_project_docs/git_recent_commits.txt`
- `00_project_docs/git_status.txt`

---

**Generated**: November 20, 2025
**Phase A Runtime**: ~4 weeks
**Next Phase**: B1 Outcome Discovery
EOF

# ============================================================================
# CALCULATE EXPORT SIZE
# ============================================================================
echo ""
echo "📊 Calculating export size..."
EXPORT_SIZE=$(du -sh "$EXPORT_DIR" | cut -f1)

echo ""
echo "========================================================================"
echo "✅ EXPORT COMPLETE"
echo "========================================================================"
echo "Location: $EXPORT_DIR"
echo "Total size: $EXPORT_SIZE"
echo ""
echo "Contents:"
ls -lh "$EXPORT_DIR" | tail -n +2
echo ""
echo "Next steps:"
echo "1. Transfer to external storage: rsync -avh phaseA_export/ /path/to/backup/"
echo "2. Verify backup integrity"
echo "3. Remove from local: rm -rf phaseA_export/"
echo ""
echo "To restore: Copy export folder and run validate_phase_a.py"
echo "========================================================================"
