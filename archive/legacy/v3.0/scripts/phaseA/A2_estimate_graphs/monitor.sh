#!/bin/bash
# A2 Monitor - Usage: ./monitor.sh (or: watch -n 10 ./monitor.sh)
PROGRESS_FILE="<repo-root>/v3.0/data/country_graphs/progress.json"

echo "=========================================="
echo "A2 COUNTRY GRAPH ESTIMATION MONITOR"
echo "=========================================="

if [ -f "$PROGRESS_FILE" ]; then
    cat "$PROGRESS_FILE" | python3 -c "
import json, sys
data = json.load(sys.stdin)
print(f\"Progress: {data.get('done', 0)}/{data.get('total', 0)} ({data.get('pct', 0):.1f}%)\")
print(f\"Remaining: {data.get('remaining', 0)}\")
print(f\"Elapsed: {data.get('elapsed_min', 0):.1f} min\")
print(f\"ETA: {data.get('eta_min', 0):.1f} min\")
print(f\"Updated: {data.get('updated', 'N/A')}\")
"
else
    echo "Progress file not found yet..."
fi

echo ""
echo "Output files:"
ls -1 <repo-root>/v3.0/data/country_graphs/*.json 2>/dev/null | wc -l
echo "country graphs created"
