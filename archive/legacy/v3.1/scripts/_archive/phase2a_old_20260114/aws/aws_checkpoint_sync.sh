#!/bin/bash
# Automatically sync checkpoints from AWS every 10 minutes
# Run this locally: ./aws_checkpoint_sync.sh
# Stop with Ctrl+C

KEY=~/Downloads/Final.pem
HOST=ubuntu@98.83.114.6
LOCAL_DIR=~/Documents/Global_Project/v3.1/data/v3_1_temporal_shap
SYNC_INTERVAL=600  # 10 minutes

mkdir -p "$LOCAL_DIR"

echo "=============================================="
echo "AWS Checkpoint Sync - Started $(date)"
echo "Syncing every $((SYNC_INTERVAL/60)) minutes"
echo "Local backup: $LOCAL_DIR"
echo "Press Ctrl+C to stop"
echo "=============================================="

sync_checkpoint() {
    echo ""
    echo "[$(date '+%H:%M:%S')] Syncing..."

    # Get current progress
    PROGRESS=$(ssh -i $KEY -o ConnectTimeout=10 $HOST "tail -1 ~/v3.1/shap_output.log 2>/dev/null" 2>/dev/null)
    echo "Progress: $PROGRESS"

    # Sync checkpoint file
    scp -i $KEY -q $HOST:~/v3.1/data/v3_1_temporal_shap/checkpoint.json "$LOCAL_DIR/" 2>/dev/null

    # Count remote files
    REMOTE_COUNT=$(ssh -i $KEY -o ConnectTimeout=10 $HOST "find ~/v3.1/data/v3_1_temporal_shap -name '*.json' 2>/dev/null | wc -l" 2>/dev/null)
    echo "Remote files: $REMOTE_COUNT"

    # Sync all SHAP files (incremental - only new files)
    rsync -az --progress -e "ssh -i $KEY" $HOST:~/v3.1/data/v3_1_temporal_shap/ "$LOCAL_DIR/" 2>/dev/null

    LOCAL_COUNT=$(find "$LOCAL_DIR" -name "*.json" 2>/dev/null | wc -l)
    echo "Local backup: $LOCAL_COUNT files"

    # Check if process is still running
    RUNNING=$(ssh -i $KEY -o ConnectTimeout=10 $HOST "pgrep -f compute_temporal" 2>/dev/null)
    if [ -z "$RUNNING" ]; then
        echo ""
        echo "!!! PROCESS NOT RUNNING - Computation may have finished or crashed !!!"
        echo "Check with: ssh -i $KEY $HOST 'tail -50 ~/v3.1/shap_output.log'"
    fi
}

# Initial sync
sync_checkpoint

# Loop forever
while true; do
    sleep $SYNC_INTERVAL
    sync_checkpoint
done
