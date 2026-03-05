# Atlas: Causal Discovery and Scenario Simulation for Development Economics

[![DOI](https://zenodo.org/badge/DOI/PLACEHOLDER.svg)](https://doi.org/PLACEHOLDER)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Website](https://img.shields.io/badge/Website-argonanalytics.com-blue)](https://argonanalytics.com)
[![Paper](https://img.shields.io/badge/Paper-Research%20Paper-green)](https://argonanalytics.com/research/paper)

Atlas is a research-grade causal discovery and policy simulation system for development economics. The current v31 corpus covers **3,122 indicators**, **178 countries**, and **1990–2024 (35 years)** with a validated panel of 18.3M observations. Atlas uses staged temporal filtering, structural pruning, and bootstrap validation to surface robust mechanism classes such as reversals, thresholds, and mediation pathways. The platform powers interactive scenario simulation at [argonanalytics.com](https://argonanalytics.com), with explicit uncertainty framing and evidence-linked outputs suitable for academic review and policy use.

## Key Numbers

`18.3M panel observations · 3,122 indicators · 178 countries · 35 years`

`2.16M Granger tests → 564K FDR survivors → 58.8K structural edges → 4,976 validated edges`

## Anchor Findings

- **F01 (`outcome_surprise`)**: `agmxhoi992 -> accmhoi999` is a stable upstream predictor of accumulated income across all strata and years.
- **F02 (`reversal`)**: `GER.5T8.GPIA -> wdi_birth` reverses sign by development stage (negative in unified/developing/emerging, positive in advanced).
- **F06 (`threshold`)**: `v2ellocpwr_ord -> e_v2xel_locelec_4C` exhibits robust threshold dynamics around 3.0.
- **F08 (`mediation`)**: `acfcfci999 -> aptxgoi999 -> agninci999` is fully persistent while the direct `acfcfci999 -> agninci999` edge is absent.

Full details: [docs/research/RESEARCH_PAPER.md](docs/research/RESEARCH_PAPER.md)

## Live Demo

- Production app: [argonanalytics.com](https://argonanalytics.com)
- Example research UI screenshot: [docs/figures/research-hub-final-desktop.png](docs/figures/research-hub-final-desktop.png)

## Quick Start

```bash
git clone https://github.com/[org]/atlas.git
cd atlas
./scripts/setup.sh
python data/download.py --sample-only
python -m uvicorn runtime.api.main:app --host 127.0.0.1 --port 8000
```

For complete setup and run instructions, see [docs/guides/QUICKSTART.md](docs/guides/QUICKSTART.md).

## Repository Structure

```text
atlas/
├── data/              # Zenodo data access + small registries + sample
├── docs/              # Research paper, methodology, API and reproducibility guides
├── pipeline/          # A2/A3/A4, SHAP, findings extraction code
├── runtime/           # API server + simulation engine
├── frontend/          # React/Vite web app
├── validation/        # QA, consistency checks, and tests
├── scripts/           # Setup + reproduction entrypoints
├── environments/      # Pinned runtime environments and Docker
└── archive/legacy/    # Filtered historical lineage (code/docs only)
```

## Data Access

Large datasets and precomputed artifacts are hosted on Zenodo, not in this repository.

- Zenodo DOI: `PLACEHOLDER`
- Download script: `python data/download.py`
- Data access guide: [data/README.md](data/README.md)

The `data/sample/` directory contains a tiny sample for smoke testing and tutorial runs.

## Research Documents

- Paper: [docs/research/RESEARCH_PAPER.md](docs/research/RESEARCH_PAPER.md)
- Methodology: [docs/research/METHODOLOGY.md](docs/research/METHODOLOGY.md)
- Policy brief: [docs/research/POLICY_BRIEF.md](docs/research/POLICY_BRIEF.md)
- Findings package JSON: [docs/research/atlas_findings_package.json](docs/research/atlas_findings_package.json)

Rendered web versions:
- [https://argonanalytics.com/research/paper](https://argonanalytics.com/research/paper)
- [https://argonanalytics.com/research/methodology](https://argonanalytics.com/research/methodology)

## Reproducibility

All published anchor findings are reproducible from this codebase plus Zenodo-hosted artifacts. See [docs/guides/REPRODUCIBILITY.md](docs/guides/REPRODUCIBILITY.md) for exact commands, expected outputs, and verification checkpoints.

## Citation

If you use Atlas in research, please cite:

```bibtex
@article{atlas2026,
  title={Atlas: Causal Discovery and Scenario Simulation for Development Policy Under Mechanism Heterogeneity},
  author={[Author(s)]},
  year={2026},
  url={https://argonanalytics.com/research},
  doi={PLACEHOLDER}
}
```

Machine-readable citation metadata: [CITATION.cff](CITATION.cff)

## License

This project is licensed under the [MIT License](LICENSE).

## Acknowledgments

Atlas integrates and audits indicators from major public research sources including the World Bank, V-Dem Institute, UNESCO UIS, WHO GHO, QoG Institute, Penn World Table, and WID. Narrative synthesis used AI-assisted drafting with mandatory evidence linkage, numeric consistency checks, and human review gates.
