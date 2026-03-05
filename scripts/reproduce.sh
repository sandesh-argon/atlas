#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-}"
VENV_DIR="${VENV_DIR:-.venv-public}"

if [[ -z "$PYTHON_BIN" ]]; then
  for candidate in python3.12 python3.11 python3; do
    if command -v "$candidate" >/dev/null 2>&1; then
      PYTHON_BIN="$candidate"
      break
    fi
  done
fi

if [[ -z "$PYTHON_BIN" ]]; then
  echo "No supported Python interpreter found (tried python3.12/python3.11/python3)." >&2
  exit 1
fi

PYTHON_VER="$("$PYTHON_BIN" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
if [[ "$PYTHON_VER" != "3.11" && "$PYTHON_VER" != "3.12" ]]; then
  echo "Unsupported Python version: $PYTHON_VER (from $PYTHON_BIN)." >&2
  echo "Atlas reproducibility smoke run currently supports Python 3.11 or 3.12." >&2
  exit 1
fi

echo "== Atlas reproducibility smoke run =="

"$PYTHON_BIN" "$ROOT/data/download.py" --sample-only || true

cd "$ROOT/runtime/api"
if [[ ! -d "$VENV_DIR" ]]; then
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi
source "$VENV_DIR/bin/activate"
python -m pip install -r requirements.txt
pytest -q \
  tests/test_map_router_year_bounds.py \
  tests/test_qol_response_contract.py \
  tests/test_simulation_invariants.py

echo "\nExpected artifacts/checkpoints:"
echo "- docs/research/atlas_findings_package.json"
echo "- data/registries/claim_registry.csv"
echo "- validation/consistency/NARRATIVE_QA_REPORT.md"
echo "- validation/consistency/NARRATIVE_CONSISTENCY_REPORT.md"
echo "\nOptional extended tests:"
echo "- pytest runtime/api/tests/test_input_validation.py"
echo "- pytest runtime/api/tests/test_regional_capability.py"
echo "- pytest runtime/api/tests/test_simulation_e2e.py  # requires running API server + full data"
