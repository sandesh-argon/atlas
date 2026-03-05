#!/bin/bash
# A3 Monitor - Usage: ./monitor.sh (or: watch -n 10 ./monitor.sh)
PROGRESS_FILE="<repo-root>/v2.0/v2.1/outputs/A3/progress.json"
echo "=========================================="
echo "A3 PC-STABLE MONITOR"
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
if 'validated_edges' in data:
    print(f\"Validated edges: {data.get('validated_edges', 0):,}\")
if 'rate_per_sec' in data:
    print(f\"Rate: {data.get('rate_per_sec', 0):.1f}/sec\")
print(f\"Updated: {data.get('updated', 'N/A')}\")
"
else
    echo "Progress file not found"
    ps aux | grep -E "step[0-9]|pc_stable" | grep -v grep | head -3
fi
echo ""
echo "CPU Temps:"
sensors 2>/dev/null | grep -E "Tctl|Tccd" | head -3
echo ""
echo "Memory:"
free -h | head -2
echo ""
echo "Python processes:"
ps aux | grep python | grep -v grep | wc -l
