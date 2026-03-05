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

## Build Upload Bundles (Maintainers)

From the private workspace root, generate Zenodo-ready archives and checksums:

```bash
./atlas-public/scripts/prepare_zenodo_export.sh /home/sandesh/Documents/Global_Project
```

This creates `zenodo_exports/atlas_v31_<timestamp>/` with:

- `atlas_v31_data_bundle.tar.gz`
- `atlas_v31_precomputed_bundle.tar.gz`
- `atlas_sample_bundle.zip`
- `SHA256SUMS.txt` and size manifests

After upload, update the placeholders in:

- `data/download.py`
- top-level `README.md`
- `CITATION.cff` (if needed)
