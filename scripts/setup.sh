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
  echo "Atlas public setup currently supports Python 3.11 or 3.12." >&2
  exit 1
fi

echo "[1/3] Frontend dependencies"
cd "$ROOT/frontend"
npm ci

echo "[2/3] Runtime Python environment"
echo "Using Python: $PYTHON_BIN"
cd "$ROOT/runtime/api"
"$PYTHON_BIN" -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo "[3/3] Setup complete"
echo "Run sample data download: python $ROOT/data/download.py --sample-only"
