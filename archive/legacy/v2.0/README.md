# V2 Global Causal Discovery System

**Bottom-Up Network Reconstruction with Validated Interpretability**

## Overview

This project implements a large-scale causal discovery system for development economics, analyzing ~5,000 variables across 150+ countries over 25-40 years to extract validated causal relationships.

**Key Innovation**: Hybrid bottom-up approach that discovers causal networks from data, then validates outcome clusters against known quality-of-life constructs from development economics literature.

## Quick Start

### Prerequisites
- Python 3.9+
- 32+ CPU cores recommended (or AWS p3.8xlarge instance)
- 128+ GB RAM
- ~500 GB storage for checkpoints

### Installation
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Running the Pipeline

**Phase A: Statistical Discovery** (Weeks 1-4)
```bash
# Step-by-step execution
python phaseA/A0_data_acquisition/collect_data.py
python phaseA/A1_missingness_analysis/run_sensitivity.py
python phaseA/A2_granger_causality/prefilter_and_test.py
python phaseA/A3_conditional_independence/pc_stable.py
python phaseA/A4_effect_quantification/backdoor_adjustment.py
python phaseA/A5_interaction_discovery/constrained_search.py
python phaseA/A6_hierarchical_layers/topological_sort.py
```

**Phase B: Interpretability** (Week 5)
```bash
python phaseB/B1_outcome_discovery/factor_analysis.py
python phaseB/B2_mechanism_identification/centrality_clustering.py
python phaseB/B3_domain_classification/semantic_clustering.py
python phaseB/B4_multi_level_pruning/prune_and_validate.py
python phaseB/B5_output_schema/generate_json.py
```

**Validation**
```bash
python validation/bootstrap_stability.py
python validation/holdout_test.py
python validation/literature_reproduction.py
```

## Project Structure

```
v2.0/
├── phaseA/                 # Statistical Network Discovery (Weeks 1-4)
│   ├── A0_data_acquisition/          # 8-12 hours: Fetch from 11 sources
│   ├── A1_missingness_analysis/      # 12-18 hours: 25 parallel configs
│   ├── A2_granger_causality/         # 4-6 days: Prefiltered temporal tests
│   ├── A3_conditional_independence/  # 2-4 days: PC-Stable + backdoor sets
│   ├── A4_effect_quantification/     # 2-3 days: Bootstrap effect sizes
│   ├── A5_interaction_discovery/     # 3-5 days: Constrained synergy search
│   └── A6_hierarchical_layers/       # 4-6 hours: Topological sorting
│
├── phaseB/                 # Interpretability Layer (Week 5)
│   ├── B1_outcome_discovery/         # 6-8 hours: Factor analysis + validation
│   ├── B2_mechanism_identification/  # 2-4 hours: Centrality-based clustering
│   ├── B3_domain_classification/     # 4-6 hours: Semantic + human validation
│   ├── B4_multi_level_pruning/       # 6-8 hours: 3 graph versions + SHAP
│   └── B5_output_schema/             # 2-3 hours: Unified JSON generation
│
├── validation/             # Validation scripts
│   ├── bootstrap_stability.py
│   ├── holdout_test.py
│   └── literature_reproduction.py
│
├── checkpoints/            # Intermediate results (not in git)
├── outputs/                # Final JSON outputs
├── literature_db/          # Known construct definitions
│
├── v2_master_instructions.md  # Complete 1,750-line specification
├── CLAUDE.md                  # AI assistant context
└── requirements.txt           # Python dependencies
```

## Key Outputs

1. **Validated Causal Network**:
   - Full graph: 2,000-8,000 nodes with quantified effects (β, CI)
   - Professional graph: 300-800 nodes (key mechanisms only)
   - Simplified graph: 30-50 nodes (public-facing)

2. **Academic Paper** (journal-ready):
   - 30+ pages with appendices
   - Target: World Development, J. Development Economics
   - Full methodology, validation results, policy implications

3. **Dashboard Assets**:
   - `causal_graph_full.json`
   - `causal_graph_professional.json`
   - `causal_graph_simplified.json`
   - Variable codebook, methodology docs, trained models

## Methodology Overview

### Phase A: Statistical Discovery
1. Acquire data from 11 sources (World Bank, WHO, UNESCO, etc.)
2. Optimal imputation strategy from 25 parallel configs
3. **Granger causality with intelligent prefiltering** (6.2M → 200K tests)
4. PC-Stable conditional independence (remove spurious correlations)
5. Backdoor adjustment with bootstrap confidence intervals
6. Constrained interaction discovery (2M tests for synergies)
7. Hierarchical layer assignment via topological sort

### Phase B: Interpretability
1. **Validated outcome discovery** (3-part check: domain, literature, R²)
2. Mechanism identification via composite centrality (betweenness + PageRank + degree)
3. Domain classification using semantic embeddings + human validation
4. **Multi-level pruning with SHAP validation** (≥85% retention)
5. Unified output schema with progressive disclosure metadata

## Validation Framework

### Success Criteria
- ✅ 2,000-10,000 validated causal edges
- ✅ Bootstrap stability >75%
- ✅ Literature reproduction >70%
- ✅ Holdout R² >0.55
- ✅ SHAP retention >85% (pruned vs full)
- ✅ No cycles (valid DAG)

### Checkpoints
Each phase saves intermediate results for resume capability:
- `A0_raw_data.pkl` → `A6_hierarchy.pkl`
- `B1_validated_outcomes.pkl` → `B5_dashboard_schema.json`

## Critical V1 Lessons

**What NOT to repeat**:
- ❌ Testing all 6.2M pairs → Use prefiltering (correlation, domain compatibility, literature)
- ❌ Accepting unvalidated factors → Use 3-part validation (domain coherence, literature match, R² > 0.40)
- ❌ Domain-balanced feature selection → Pure statistical selection, domain tagging post-hoc
- ❌ Normalize before transforms → Correct order: Saturation → Normalization

**What to keep**:
- ✅ Imputation confidence weighting (Tier 1-4 system)
- ✅ Three-pronged causal validation (Granger + PC-Stable + backdoor)
- ✅ Mechanism interaction discovery (health × education synergies)
- ✅ Bootstrap validation for stability

## Computational Requirements

**Infrastructure**:
- AWS EC2 p3.8xlarge (32 vCPUs, 244 GB RAM, 4x V100 GPUs)
- Spot instances recommended (70% cost savings)
- Parallelization: `joblib` + `ray`

**Timeline & Cost**:
- Wall-clock time: 14-21 days
- Compute time: 10-15 days
- Estimated cost: $770-$1,180 (spot pricing)

## Dashboard Integration

**5-Level Progressive Disclosure**:
| Level | Audience | Graph | Nodes | Features |
|-------|----------|-------|-------|----------|
| 1 | Experts | Full | 2K-8K | Data download, methodology, citations |
| 2 | Researchers | Full | 2K-8K | Interactive filtering, mechanism explorer |
| 3 | Professionals | Pruned | 300-800 | Scenario testing, policy simulator |
| 4 | Engaged Public | Simple | 30-50 | Storytelling mode, plain language |
| 5 | Casual | Simple | 30-50 | Pre-built narratives, video explainers |

## References

- **Full Specification**: `v2_master_instructions.md`
- **AI Context**: `CLAUDE.md`
- **Phase Details**: `phaseA/README.md`, `phaseB/README.md`

## License

- Code: MIT License
- Data/Outputs: CC-BY-4.0
- Paper: Traditional academic copyright (journal-dependent)

## Contact

For questions about methodology, data access, or collaboration:
- See `v2_master_instructions.md` for detailed technical documentation
- See `CLAUDE.md` for development context and architectural decisions
