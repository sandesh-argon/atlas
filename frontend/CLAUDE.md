# CLAUDE.md

## SSH Session Safety Rules

**CRITICAL**: Follow these rules to prevent session crashes:

1. **Never pipe curl directly** - save to file first: `curl -s -m 5 url > /tmp/out.json`
2. **Always use timeouts**: `curl -m 5`
3. **Limit output**: `head -c 500` or `head -20`
4. **Kill before starting**: `pkill -9 -f pattern` and verify
5. **Start servers with nohup**: `nohup uvicorn api.main:app --host 0.0.0.0 --port 8000 > /tmp/api.log 2>&1 &`

## Build & Dev

```bash
# Frontend (localhost:5173/global-viz/)
npm run dev

# Backend API (localhost:8000)
source api/venv/bin/activate
python -m uvicorn api.main:app --port 8000
```

Toggle API endpoint in `src/services/api.ts`: `API_MODE = 'local' | 'public'`

## Project Overview

Interactive causal graph visualization for development economics research. React + TypeScript + Vite + D3.js with simulation mode for country-specific causal graphs.

**Tech Stack**: Zustand (state), D3 (viz), Fuse.js (search)

## Repository Structure

```
viz/
├── src/                          # Frontend application code
│   ├── components/
│   │   ├── simulation/           # CountrySelector, SimulationPanel, InterventionBuilder,
│   │   │                         # SimulationRunner, TimelinePlayer, ResultsPanel, TemplateSelector
│   │   ├── LocalView/            # DAG flow view (structural + sim modes)
│   │   ├── ViewTabs.tsx          # Global/Local/Split view switcher
│   │   └── StrataTabs.tsx        # Income stratification tabs
│   ├── stores/simulationStore.ts # Zustand state (panel, country, interventions, playback)
│   ├── services/api.ts           # API client
│   ├── utils/causalEdges.ts      # buildLocalViewData + buildSimLocalViewData
│   ├── layouts/                  # RadialLayout.ts, LocalViewLayout.ts
│   ├── styles/App.css            # CSS animations (edge pulse, node flash, intervention glow)
│   └── App.tsx                   # Main app + D3 radial rendering (~4500 lines)
│
├── simulation/                   # V3.1 simulation engine (self-contained)
│   ├── graph_loader_v31.py       # Year-specific graph loading with fallback
│   ├── simulation_runner_v31.py  # Instant simulation runner
│   ├── temporal_simulation_v31.py # Multi-year temporal simulation
│   ├── propagation_v31.py        # Causal propagation engine
│   ├── indicator_stats.py        # Country-specific statistics
│   ├── income_classifier.py      # World Bank income classification
│   ├── regional_spillovers.py    # Regional spillover effects
│   └── saturation_functions.py   # Indicator saturation bounds
│
├── api/                          # FastAPI backend
│   ├── main.py                   # Entry point
│   ├── routers/                  # Route handlers
│   ├── services/                 # Business logic
│   └── config.py                 # Paths, CORS, timeouts
│
├── data/                         # Research data (~19GB, gitignored)
│   ├── v31/                      # V3.1 temporal outputs
│   │   ├── temporal_graphs/      # 17GB - year-specific causal graphs
│   │   ├── temporal_shap/        # 1.2GB - SHAP importance values
│   │   ├── baselines/            # 305MB - precomputed baselines
│   │   ├── development_clusters/
│   │   ├── feedback_loops/
│   │   └── metadata/
│   └── raw/                      # 70MB - from original research data
│       ├── v21_panel_data_for_v3.parquet
│       ├── v21_nodes.csv
│       └── v21_causal_edges.csv
│
├── docs/                         # Documentation
│   ├── architecture/             # CLAUDE_CODE_REPO_REFERENCE.md
│   ├── plans/                    # roadmap.md, phase plans, 3d-sandbox-spec.md
│   ├── reports/                  # phase4-progress.md, performance-report.md
│   ├── runbooks/                 # Operational runbooks
│   └── phases/                   # Historical phase implementation notes
│
├── deploy/                       # Deployment scaffolding
│   ├── docker/                   # Dockerfiles
│   ├── nginx/                    # SPA routing + reverse proxy
│   └── env/                      # .env.staging.example, .env.prod.example
│
├── scripts/                      # Automation
│   ├── dev/                      # analyze.cjs, test-layout.cjs
│   └── ci/                       # CI scripts
│
└── .github/workflows/            # CI/CD pipelines (ci.yml, deploy.yml)
```

**File placement rules** (see `docs/architecture/CLAUDE_CODE_REPO_REFERENCE.md`):
- Plans/RFCs → `docs/plans/`
- Progress/status reports → `docs/reports/`
- Utility scripts → `scripts/dev/`
- No ad-hoc docs at repo root

## Key API Endpoints

| Endpoint | Purpose |
|----------|---------|
| `/health` | Health check |
| `/api/countries` | List 203 countries |
| `/api/graph/{country}` | Country graph + SHAP + baseline |
| `/api/temporal/shap/{target}/timeline` | Unified SHAP all years |
| `/api/temporal/shap/{country}/{target}/timeline` | Country SHAP timeline |
| `/api/temporal/graph/{year}` | Unified graph for year |
| `/api/temporal/graph/{country}/{year}` | Country graph for year |
| `/api/simulate/v31` | V3.1 instant simulation |
| `/api/simulate/v31/temporal` | V3.1 temporal simulation |

## Roadmap & Progress

See `docs/plans/roadmap.md` for full phase history and feature details.

**Completed**: Phases 2–9A (Core Sim → Sim Polish → Sim UX → Pre-Launch → Map → Regional → Polish → Accessibility → Desktop Adaptive Layout)

**Next**: Phase 9B/C — Tablet & Mobile

**Pending fix**: Layout stability on single-node collapse — see `docs/plans/codex-layout-stability-fix.md`

## Key Constants

```typescript
DOMAIN_COLORS       // 9 domain color mappings
RING_LABELS         // ['Quality of Life', 'Outcomes', 'Coarse Domains', 'Fine Domains', 'Indicator Groups', 'Indicators']
MAX_INTERVENTIONS   // 5
API_MODE            // 'local' | 'public'
SIM_MS_PER_YEAR     // Animation speed per sim year
```

## Data Structure

- **Temporal SHAP**: 35 years (1990-2024) x 178 countries
- **Income Strata**: Unified, Developing (<$4.5k), Emerging ($4.5k-$14k), Advanced (>$14k)
- **Graph edges**: Year-specific, country-specific, stratum-specific variants
- **Indicator domains**: Development (38), Economic (24), Education (12), Environment (20), Governance (5)

## Backlog (unscheduled)

See `docs/plans/roadmap.md` → "Future Phases (BACKLOG)" for full list.
