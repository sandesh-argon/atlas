#!/usr/bin/env bash
# Real-time progress monitor for imputation experiment

PROGRESS_FILE="imputation_progress.log"

# Clear screen
clear

echo "================================================================================"
echo "A1 IMPUTATION EXPERIMENT - LIVE PROGRESS MONITOR"
echo "================================================================================"
echo ""

# Check if progress file exists
if [[ ! -f "$PROGRESS_FILE" ]]; then
    echo "⏳ Waiting for experiment to start..."
    echo "   Progress file not yet created: $PROGRESS_FILE"
    exit 0
fi

# Parse progress file
TOTAL=$(grep "^TOTAL:" "$PROGRESS_FILE" | awk '{print $2}')
STARTED=$(grep -c "^STARTED:" "$PROGRESS_FILE")
COMPLETED=$(grep -c "^COMPLETED:" "$PROGRESS_FILE")

# Calculate progress
if [[ -n "$TOTAL" ]] && [[ "$TOTAL" -gt 0 ]]; then
    PROGRESS_PCT=$(awk "BEGIN {printf \"%.1f\", ($COMPLETED / $TOTAL) * 100}")
else
    PROGRESS_PCT=0.0
fi

# Display header
echo "Total Configurations: $TOTAL"
echo "Completed: $COMPLETED / $TOTAL ($PROGRESS_PCT%)"
echo ""

# Progress bar
BAR_WIDTH=50
FILLED=$(awk "BEGIN {printf \"%.0f\", ($COMPLETED / $TOTAL) * $BAR_WIDTH}")
EMPTY=$((BAR_WIDTH - FILLED))

printf "["
printf "%${FILLED}s" | tr ' ' '█'
printf "%${EMPTY}s" | tr ' ' '░'
printf "] $PROGRESS_PCT%%\n"

echo ""
echo "================================================================================"
echo "RECENT ACTIVITY (Last 10 events):"
echo "================================================================================"

# Show recent activity
grep -E "^(STARTED|COMPLETED):" "$PROGRESS_FILE" | tail -10 | while read line; do
    if [[ $line == STARTED:* ]]; then
        echo "⏳ $line"
    elif [[ $line == COMPLETED:* ]]; then
        echo "✅ $line"
    fi
done

echo ""
echo "================================================================================"
echo "TOP 5 BEST SCORES SO FAR:"
echo "================================================================================"

# Extract scores and sort
grep "^COMPLETED:" "$PROGRESS_FILE" | \
    awk -F'|' '{print $2, $1}' | \
    awk -F':' '{print $1, $2}' | \
    sort -rn -k2 | \
    head -5 | \
    awk '{printf "%.3f - %s\n", $2, substr($0, index($0,$3))}'

echo ""
echo "================================================================================"
echo "Press Ctrl+C to exit monitor (experiment continues in background)"
echo "Refresh: watch -n 2 ./monitor_progress.sh"
echo "================================================================================"
