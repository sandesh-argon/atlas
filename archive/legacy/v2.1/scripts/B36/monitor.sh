#!/bin/bash
# B36 Monitor - Usage: ./monitor.sh (or: watch -n 10 ./monitor.sh)
PROGRESS_FILE="<repo-root>/v2.0/v2.1/outputs/B36/progress.json"
LOG_FILE="<repo-root>/v2.0/v2.1/logs/B36_semantic_hierarchy_llm.log"

echo "=========================================="
echo "B36 SEMANTIC HIERARCHY WITH LLM MONITOR"
echo "=========================================="

if [ -f "$PROGRESS_FILE" ]; then
    cat "$PROGRESS_FILE" | python3 -c "
import json, sys
data = json.load(sys.stdin)
print(f\"Step: {data.get('step', 'N/A')}\")
print(f\"Progress: {data.get('pct', 0):.1f}%\")
if 'layer' in data:
    print(f\"Layer: {data.get('layer')} | Done: {data.get('done', 0)}/{data.get('total', 0)}\")
print(f\"Updated: {data.get('updated', 'N/A')}\")
"
else
    echo "Progress file not found - waiting for script to start..."
fi

echo ""
echo "Recent log entries:"
if [ -f "$LOG_FILE" ]; then
    tail -10 "$LOG_FILE"
else
    echo "Log file not found"
fi

echo ""
echo "CPU/Memory:"
ps aux | grep -E "run_b36" | grep -v grep | head -3
free -h | head -2
