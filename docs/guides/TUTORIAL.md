# Atlas Tutorial

## Goal

Run a complete smoke test from sample data to simulation endpoint and inspect one anchor finding.

## Steps

1. Setup environment with `./scripts/setup.sh`.
2. Fetch sample data: `python data/download.py --sample-only`.
3. Start API (`runtime/api`) and frontend (`frontend`).
4. Open the simulation panel and run a sample intervention.
5. Compare behavior with anchor finding metadata from:
   - `data/registries/atlas_anchor_findings_from_package.json`
   - `docs/research/atlas_findings_package.json`

## Suggested Walkthrough Assets

Use screenshots in `docs/figures/tutorial-screenshots/` to mirror the UI path.

## What to Validate

- API returns healthy responses.
- Simulation endpoints accept canonical payloads.
- Frontend renders and can call the API.
- Findings metadata is available and parseable.
