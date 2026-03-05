#!/bin/bash
# Monitor AWS SHAP computation
# Usage: ./aws_monitor.sh [download]

KEY=~/Downloads/Final.pem
HOST=ubuntu@98.83.114.6
LOCAL_DIR=~/Documents/Global_Project/v3.1/data/v3_1_temporal_shap

echo "=== AWS SHAP Monitor - $(date) ==="
echo ""

# Check if process is running
echo "Process status:"
ssh -i $KEY $HOST "ps aux | grep 'compute_temporal' | grep -v grep | awk '{print \"PID:\", \$2, \"CPU:\", \$3\"%\", \"MEM:\", \$4\"%\"}'" || echo "NOT RUNNING!"

echo ""
echo "Latest progress:"
ssh -i $KEY $HOST "tail -3 ~/v3.1/shap_output.log 2>/dev/null"

echo ""
echo "Files generated:"
ssh -i $KEY $HOST "echo 'Unified:' && find ~/v3.1/data/v3_1_temporal_shap/unified -name '*.json' 2>/dev/null | wc -l && echo 'Countries:' && find ~/v3.1/data/v3_1_temporal_shap/countries -name '*.json' 2>/dev/null | wc -l"

echo ""
echo "Checkpoint:"
ssh -i $KEY $HOST "cat ~/v3.1/data/v3_1_temporal_shap/checkpoint.json 2>/dev/null || echo 'No checkpoint yet'"

# Download if requested
if [ "$1" == "download" ]; then
    echo ""
    echo "=== Downloading results ==="
    mkdir -p $LOCAL_DIR
    rsync -avz --progress -e "ssh -i $KEY" $HOST:~/v3.1/data/v3_1_temporal_shap/ $LOCAL_DIR/
    echo "Downloaded to: $LOCAL_DIR"
fi
