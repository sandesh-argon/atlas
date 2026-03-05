#!/bin/bash
# Run this LOCALLY to download results from AWS instance
# Usage: ./aws_download_results.sh <user>@<ip> [ssh-key]

set -e

if [ -z "$1" ]; then
    echo "Usage: $0 <user>@<ip> [ssh-key]"
    exit 1
fi

TARGET=$1
SSH_KEY=""
if [ -n "$2" ]; then
    SSH_KEY="-i $2"
fi

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "=============================================="
echo "Downloading results from AWS instance: $TARGET"
echo "=============================================="

# Check status first
echo "Checking computation status..."
ssh $SSH_KEY $TARGET "cat ~/v3.1/data/v3_1_temporal_shap/checkpoint.json 2>/dev/null || echo 'No checkpoint found'"

echo ""
read -p "Download results? (y/n) " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Downloading SHAP files..."

    # Create local directory
    mkdir -p "$PROJECT_DIR/data/v3_1_temporal_shap"

    # Download with rsync for efficiency
    rsync -avz --progress $SSH_KEY "$TARGET:~/v3.1/data/v3_1_temporal_shap/" "$PROJECT_DIR/data/v3_1_temporal_shap/"

    echo ""
    echo "Download complete!"
    echo "Files saved to: $PROJECT_DIR/data/v3_1_temporal_shap/"

    # Count files
    echo ""
    echo "File counts:"
    find "$PROJECT_DIR/data/v3_1_temporal_shap" -name "*.json" | wc -l
fi
