#!/bin/bash
# A2 Granger Testing Monitor
# Usage: ./monitor.sh (or: watch -n 5 ./monitor.sh)

PROGRESS_FILE="<repo-root>/v2.0/v2.1/outputs/A2/progress.json"

echo "=========================================="
echo "A2 GRANGER TESTING MONITOR"
echo "=========================================="
echo ""

# Check if progress file exists
if [ -f "$PROGRESS_FILE" ]; then
    cat "$PROGRESS_FILE" | python3 -c "
import json, sys
data = json.load(sys.stdin)
print(f\"Step: {data.get('step', 'N/A')}\")
print(f\"Progress: {data.get('pct', 0):.1f}%\")
print(f\"Items: {data.get('items_done', 0):,} / {data.get('items_total', 0):,}\")
print(f\"Elapsed: {data.get('elapsed_min', 0):.1f} min\")
print(f\"ETA: {data.get('eta_min', 0):.1f} min\")
if 'successful_tests' in data:
    print(f\"Successful tests: {data.get('successful_tests', 0):,}\")
if 'chunk' in data:
    print(f\"Chunk: {data.get('chunk', 'N/A')}\")
print(f\"Updated: {data.get('updated', 'N/A')}\")
"
else
    echo "Progress file not found: $PROGRESS_FILE"
    echo ""
    echo "Checking if Granger process is running..."
    ps aux | grep -E "step3_granger|loky" | grep -v grep | head -5
fi

echo ""
echo "=========================================="
echo "CPU Temps:"
sensors 2>/dev/null | grep -E "Tctl|Tccd" | head -3

echo ""
echo "Memory:"
free -h | head -2
