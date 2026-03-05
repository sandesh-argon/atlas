#!/bin/bash
# Quick cycle removal status check

echo "Process status:"
ps aux | grep "step3_remove_cycles" | grep -v grep || echo "  NOT RUNNING"

echo ""
echo "Latest log (last 5 lines):"
tail -5 logs/remove_cycles.log 2>/dev/null || echo "  No log yet"

echo ""
echo "Runtime: $(ps -p $(pgrep -f step3_remove_cycles) -o etime= 2>/dev/null || echo 'N/A')"
