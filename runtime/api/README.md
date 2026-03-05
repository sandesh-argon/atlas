# Atlas Runtime API

FastAPI server for Atlas simulation and graph-serving endpoints.

## Run

```bash
cd <repo-root>
python -m venv runtime/api/.venv
source runtime/api/.venv/bin/activate
pip install -r runtime/api/requirements.txt
python -m uvicorn runtime.api.main:app --host 127.0.0.1 --port 8000
```

## Canonical Simulation Endpoints

- `POST /api/simulate/v31`
- `POST /api/simulate/v31/temporal`

See `docs/api/API_REFERENCE.md` for complete endpoint coverage.
