#!/usr/bin/env bash
set -euo pipefail

# Build Zenodo-ready Atlas data bundles from local source data.
#
# Usage:
#   ./scripts/prepare_zenodo_export.sh
#   ./scripts/prepare_zenodo_export.sh /path/to/project_root
#
# Output:
#   <project_root>/zenodo_exports/atlas_v31_<timestamp>/
#     - atlas_v31_data_bundle.tar.gz
#     - atlas_v31_precomputed_bundle.tar.gz
#     - atlas_sample_bundle.zip
#     - SHA256SUMS.txt
#     - FILE_SIZES.csv
#     - SOURCE_SIZES.csv
#     - ZENODO_UPLOAD_NOTES.md

PROJECT_ROOT="${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)}"
OUT_BASE="$PROJECT_ROOT/zenodo_exports"
STAMP="$(date +%Y%m%d_%H%M%S)"
OUT_DIR="$OUT_BASE/atlas_v31_$STAMP"

SRC_RAW="$PROJECT_ROOT/viz/data/raw"
SRC_V31="$PROJECT_ROOT/viz/data/v31"
SRC_SAMPLE="$PROJECT_ROOT/atlas-public/data/sample"

if [[ ! -d "$SRC_RAW" || ! -d "$SRC_V31" || ! -d "$SRC_SAMPLE" ]]; then
  echo "Missing required source directories." >&2
  echo "Expected:" >&2
  echo "  $SRC_RAW" >&2
  echo "  $SRC_V31" >&2
  echo "  $SRC_SAMPLE" >&2
  exit 1
fi

mkdir -p "$OUT_DIR/staging/full" "$OUT_DIR/staging/sample"

echo "[1/6] Staging raw + v31 data..."
rsync -a --delete "$SRC_RAW/" "$OUT_DIR/staging/full/raw/"
rsync -a --delete "$SRC_V31/" "$OUT_DIR/staging/full/v31/"

echo "[2/6] Staging sample data..."
rsync -a --delete "$SRC_SAMPLE/" "$OUT_DIR/staging/sample/"

echo "[3/6] Building archives..."
(
  cd "$OUT_DIR/staging/full"
  tar -czf "$OUT_DIR/atlas_v31_data_bundle.tar.gz" raw
  tar -czf "$OUT_DIR/atlas_v31_precomputed_bundle.tar.gz" v31
)
(
  cd "$OUT_DIR/staging/sample"
  zip -qr "$OUT_DIR/atlas_sample_bundle.zip" .
)

echo "[4/6] Generating checksums..."
(
  cd "$OUT_DIR"
  sha256sum atlas_v31_data_bundle.tar.gz atlas_v31_precomputed_bundle.tar.gz atlas_sample_bundle.zip > SHA256SUMS.txt
)

echo "[5/6] Writing metadata files..."
{
  echo "file,size_bytes"
  for f in atlas_v31_data_bundle.tar.gz atlas_v31_precomputed_bundle.tar.gz atlas_sample_bundle.zip; do
    printf "%s,%s\n" "$f" "$(stat -c%s "$OUT_DIR/$f")"
  done
} > "$OUT_DIR/FILE_SIZES.csv"

{
  echo "path,size_human"
  du -sh "$SRC_RAW" "$SRC_V31" "$SRC_SAMPLE" | awk '{print $2","$1}'
} > "$OUT_DIR/SOURCE_SIZES.csv"

cat > "$OUT_DIR/ZENODO_UPLOAD_NOTES.md" <<'EOF'
# Atlas v31 Zenodo Upload Notes

Artifacts in this folder:
- atlas_v31_data_bundle.tar.gz (contains: raw/)
- atlas_v31_precomputed_bundle.tar.gz (contains: v31/)
- atlas_sample_bundle.zip (contains sample files)
- SHA256SUMS.txt
- FILE_SIZES.csv
- SOURCE_SIZES.csv

Expected downloader mapping in atlas-public/data/download.py:
- atlas_v31_data_bundle.tar.gz
- atlas_v31_precomputed_bundle.tar.gz
- atlas_sample_bundle.zip
EOF

echo "[6/6] Done."
echo "$OUT_DIR"

