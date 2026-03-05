# Atlas Data Access

Atlas data artifacts are hosted on Zenodo and are intentionally not committed to this repository.

## Why

- GitHub is used for code, docs, and small metadata only.
- Large panel and precomputed artifacts are distributed via Zenodo for stable DOI-based citation and preservation.

## What is on Zenodo

- Full panel dataset (18.3M+ rows)
- Temporal graph artifacts (country/stratified/unified/regional)
- SHAP artifacts
- Baselines and metadata bundles

## What is in this repo

- `data/registries/` metadata registries (small, tracked)
- `data/sample/` tiny sample for smoke tests
- `data/download.py` automated downloader

## Usage

```bash
# Download sample assets only
python data/download.py --sample-only

# Download full datasets (after DOI/URLs are filled)
python data/download.py

# Verify already-downloaded files
python data/download.py --check
```

## Zenodo DOI

- Dataset DOI: `PLACEHOLDER`
- Record URL: `https://doi.org/PLACEHOLDER`

After upload, update the placeholders in:

- `data/download.py`
- top-level `README.md`
- `CITATION.cff` (if needed)
