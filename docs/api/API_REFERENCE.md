# Atlas API Reference (v31)

This document describes the public API surface shipped in `runtime/api`.

## Base

- Local default: `http://localhost:8000`
- Docs endpoint (dev): `/docs`

## Health

- `GET /health` — liveness probe
- `GET /health/detailed` — detailed health (config-gated)

## Core Data Endpoints

- `GET /api/countries` — available countries list
- `GET /api/countries/{code}` — country baseline/metadata
- `GET /api/graph/{code}` — country graph payload
- `GET /api/indicators` — indicator catalog
- `GET /api/map` — map view payload (year-bounded)

## Simulation Endpoints

Canonical:

- `POST /api/simulate/v31`
- `POST /api/simulate/v31/temporal`

Compatibility aliases (deprecated but currently supported):

- `POST /api/simulate`
- `POST /api/simulate/temporal`

## Simulation Request Highlights

- `view_type`: `country | stratified | unified | regional`
- `country`: required for `country|stratified`, optional for `unified`, optional fallback for `regional`
- `region`: optional; required for `regional` if `country` omitted

## Security/Rate Limit Controls

- Optional simulation auth token (`X-API-Key` or `Authorization: Bearer`)
- Optional Cloudflare Access service-token mode
- Per-minute and per-hour request limits

See `runtime/api/config.py` for full environment variable controls.
