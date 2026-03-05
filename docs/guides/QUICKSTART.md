# Quickstart (10 Minutes)

## Prerequisites

- Python 3.12 (recommended)
- Node 20+
- `pip`, `npm`

## 1. Clone and Setup

```bash
git clone https://github.com/sandesh-argon/atlas.git
cd atlas
./scripts/setup.sh
```

## 2. Download Sample Data

```bash
python data/download.py --sample-only
```

## 3. Run API

```bash
python -m uvicorn runtime.api.main:app --host 127.0.0.1 --port 8000
```

Default API URL: `http://localhost:8000`

## 4. Run Frontend (new terminal)

```bash
cd frontend
npm run dev
```

Default frontend URL: `http://localhost:5173`

## Notes

- Full dataset reproduction requires Zenodo DOI and artifacts.
- If Zenodo placeholders are not filled yet, sample mode still validates local wiring.
