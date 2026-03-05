# Reproducibility Guide

This guide describes how to reproduce Atlas core pipeline outputs and verify public anchor findings.

## 1. Prerequisites

- Python 3.12 (recommended)
- Node 20+
- `pip`, `npm`
- Enough disk for Zenodo bundles

## 2. Data Acquisition

```bash
python data/download.py
```

For quick verification only:

```bash
python data/download.py --sample-only
```

## 3. Pipeline Reproduction (A2 -> A3 -> A4)

From repo root:

```bash
python pipeline/a2_granger/step1_validate_checkpoint.py
python pipeline/a2_granger/step2_prefiltering.py
python pipeline/a2_granger/step3_granger_testing_v2.py
python pipeline/a2_granger/step4_fdr_correction.py

python pipeline/a3_structure/step1c_smart_prepruning.py
python pipeline/a3_structure/step2_custom_pairwise_pc.py
python pipeline/a3_structure/step3_remove_cycles.py

python pipeline/a4_bootstrap/step1_input_validation.py
python pipeline/a4_bootstrap/step2_parent_adjustment.py
python pipeline/a4_bootstrap/step3_effect_estimation_lasso.py
```

## 4. Findings Verification (F01/F02/F06/F08)

1. Open `docs/research/atlas_findings_package.json`.
2. Confirm top-4 IDs include `F02,F08,F06,F01`.
3. Verify key constraints:
   - F02 availability `140/140` and `35/35`.
   - F06 threshold near `3.0` latest year `2024`.
   - F08 direct edge `0/140`, indirect path `140/140`.
   - F01 availability `140/140` and `35/35`.

## 5. Expected Outputs

Expected canonical counts (v31/v2.1 lineage claims):

- A2 tests: `2,159,672`
- A2 FDR survivors: `564,545`
- A3 edges: `58,837`
- A4 validated edges: `4,976`

Reference registries:

- `data/registries/claim_registry.csv`
- `data/registries/evidence_ledger.csv`
- `data/registries/failure_registry.csv`

## 6. Known Differences

- Minor floating-point variation can occur across platforms.
- Timing and cache behavior differ by CPU/storage.
- Any major count divergence indicates configuration/data mismatch.

## 7. Verification Checklist

- [ ] Environment setup successful
- [ ] Data download completed and checksums verified
- [ ] A2/A3/A4 scripts executed without fatal errors
- [ ] Canonical counts match registries
- [ ] Anchor findings match package JSON
- [ ] API smoke tests passed:
  - `pytest runtime/api/tests/test_map_router_year_bounds.py`
  - `pytest runtime/api/tests/test_qol_response_contract.py`
  - `pytest runtime/api/tests/test_simulation_invariants.py`
- [ ] Frontend build smoke test completed (`cd frontend && npm run build`)

### Extended API tests (optional)

These require full runtime artifacts and/or a running API instance on localhost:

- `runtime/api/tests/test_input_validation.py`
- `runtime/api/tests/test_regional_capability.py`
- `runtime/api/tests/test_simulation_e2e.py`
