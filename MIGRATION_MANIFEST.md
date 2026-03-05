# Migration Manifest

Public export source: private Atlas workspace snapshot (2026-03-05).

## Major Mappings

- `viz/api` -> `runtime/api`
- `viz/simulation` -> `runtime/simulation`
- `viz/src` + frontend configs -> `frontend/`
- `v2.1/scripts/A2|A3|A4` + selected viz pipeline scripts -> `pipeline/`
- `research_workspace/*narrative*.md` -> `docs/research/`
- `research_workspace/*registry*` -> `data/registries/`
- `research_workspace/NARRATIVE_*` -> `validation/consistency/`
- `viz/api/tests` -> `validation/tests/api`

## Exclusions

- any `data/`, `Data/`, `outputs/`, `models/` trees from source repos
- virtual environments, caches, build artifacts, logs
- binaries and files larger than 10MB
- private deploy workflow details and host-specific absolute paths
