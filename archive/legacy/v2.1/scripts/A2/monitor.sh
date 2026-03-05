#!/bin/bash
# A2 Monitor - Usage: ./monitor.sh (or: watch -n 10 ./monitor.sh)
PROGRESS_FILE="<repo-root>/v2.0/v2.1/outputs/A2/progress.json"
echo "=========================================="
echo "A2 GRANGER CAUSALITY MONITOR"
echo "=========================================="
if [ -f "$PROGRESS_FILE" ]; then
    cat "$PROGRESS_FILE" | python3 -c "
import json, sys
data = json.load(sys.stdin)
print(f\"Step: {data.get('step', 'N/A')}\")
print(f\"Progress: {data.get('pct', 0):.1f}%\")
print(f\"Items: {data.get('items_done', 0):,} / {data.get('items_total', 0):,}\")
print(f\"Elapsed: {data.get('elapsed_min', 0):.1f} min\")
print(f\"ETA: {data.get('eta_min', 0):.1f} min\")
if 'significant' in data:
    print(f\"Significant: {data.get('significant', 0):,}\")
if 'rate_per_sec' in data:
    print(f\"Rate: {data.get('rate_per_sec', 0):.1f}/sec\")
print(f\"Updated: {data.get('updated', 'N/A')}\")
"
else
    echo "Progress file not found: $PROGRESS_FILE"
    echo ""
    echo "Checking if A2 process is running..."
    ps aux | grep -E "step[0-9].*\.py|granger|prefilter" | grep -v grep | head -5
fi
echo ""
echo "=========================================="
echo "CPU Temps:"
sensors 2>/dev/null | grep -E "Tctl|Tccd" | head -3
echo ""
echo "Memory:"
free -h | head -2
echo ""
echo "Python processes:"
ps aux | grep python | grep -v grep | wc -l
