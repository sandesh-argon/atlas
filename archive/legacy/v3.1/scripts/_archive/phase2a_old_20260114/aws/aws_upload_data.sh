#!/bin/bash
# Run this LOCALLY to upload data to AWS instance
# Usage: ./aws_upload_data.sh <user>@<ip> [ssh-key]
#
# Example: ./aws_upload_data.sh ubuntu@54.123.45.67 ~/.ssh/my-key.pem

set -e

if [ -z "$1" ]; then
    echo "Usage: $0 <user>@<ip> [ssh-key]"
    echo "Example: $0 ubuntu@54.123.45.67 ~/.ssh/my-key.pem"
    exit 1
fi

TARGET=$1
SSH_KEY=""
if [ -n "$2" ]; then
    SSH_KEY="-i $2"
fi

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "=============================================="
echo "Uploading data to AWS instance: $TARGET"
echo "Project directory: $PROJECT_DIR"
echo "=============================================="

# 1. Upload panel data (largest file)
echo "[1/4] Uploading panel data (~500MB)..."
scp $SSH_KEY "$PROJECT_DIR/data/raw/v21_panel_data_for_v3.parquet" "$TARGET:~/v3.1/data/raw/"

# 2. Upload nodes file
echo "[2/4] Uploading nodes file..."
scp $SSH_KEY "$PROJECT_DIR/data/raw/v21_nodes.csv" "$TARGET:~/v3.1/data/raw/" 2>/dev/null || echo "  (skipped - not found)"

# 3. Upload country graphs
echo "[3/4] Uploading country graphs..."
scp $SSH_KEY -r "$PROJECT_DIR/data/country_graphs/"*.json "$TARGET:~/v3.1/data/country_graphs/"

# 4. Upload compute script
echo "[4/4] Uploading compute script..."
scp $SSH_KEY "$PROJECT_DIR/scripts/phase2_compute/compute_temporal_shap.py" "$TARGET:~/v3.1/scripts/phase2_compute/"

echo ""
echo "=============================================="
echo "Upload complete!"
echo "=============================================="
echo ""
echo "Now SSH into the instance and run:"
echo "  ~/v3.1/run_shap.sh"
echo ""
echo "Monitor progress:"
echo "  tail -f ~/v3.1/shap_output.log"
echo ""
