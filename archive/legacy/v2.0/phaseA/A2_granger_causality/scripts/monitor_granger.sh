#!/bin/bash
# Monitor Granger causality testing progress

cd "$(dirname "$0")/.."

echo "=========================================="
echo "   GRANGER TESTING PROGRESS MONITOR"
echo "=========================================="
echo ""

# Get start time
START_TIME=$(grep "Started:" logs/step3_granger.log 2>/dev/null | head -1 | sed 's/Started: //')
if [ -n "$START_TIME" ]; then
    echo "Started: $START_TIME"
else
    echo "Started: Not yet started or log not found"
fi

# Check if still running
PID=$(cat logs/step3_granger.pid 2>/dev/null)
if [ -n "$PID" ] && kill -0 $PID 2>/dev/null; then
    echo "Status:  ✅ RUNNING (PID: $PID)"
    RUNNING=true
else
    echo "Status:  ⏸️  COMPLETED or STOPPED"
    RUNNING=false
fi

echo ""

# Extract progress from log
TOTAL_PAIRS=15889478

# Look for progress lines like: "Progress: 100,000 / 15,889,478 (0.6%)"
PROGRESS_LINE=$(grep -oP "Progress: \K[\d,]+(?= /)" logs/step3_granger.log 2>/dev/null | tail -1)

if [ -n "$PROGRESS_LINE" ]; then
    COMPLETED=$(echo $PROGRESS_LINE | tr -d ',')
    PERCENT=$(awk "BEGIN {printf \"%.1f\", ($COMPLETED / $TOTAL_PAIRS) * 100}")

    echo "=========================================="
    echo "STEP 3: GRANGER CAUSALITY TESTING"
    echo "=========================================="
    echo "Pairs tested: $(printf "%'d" $COMPLETED) / $(printf "%'d" $TOTAL_PAIRS)"
    echo "Progress:     $PERCENT%"

    # Progress bar
    FILLED=$(awk "BEGIN {printf \"%.0f\", ($COMPLETED / $TOTAL_PAIRS) * 40}")
    BAR=$(printf "%${FILLED}s" | tr ' ' '█')
    EMPTY=$(printf "%$((40-FILLED))s" | tr ' ' '░')
    echo "[$BAR$EMPTY] $PERCENT%"

    # Extract timing info
    ELAPSED_LINE=$(grep "Elapsed:" logs/step3_granger.log 2>/dev/null | tail -1)
    if [ -n "$ELAPSED_LINE" ]; then
        ELAPSED=$(echo "$ELAPSED_LINE" | grep -oP "Elapsed: \K[\d.]+")
        REMAINING=$(echo "$ELAPSED_LINE" | grep -oP "remaining: \K[\d.]+")

        echo ""
        echo "Time elapsed:    ${ELAPSED} hours"
        if [ -n "$REMAINING" ]; then
            echo "Est. remaining:  ${REMAINING} hours"
        fi
    fi

    # Successful tests
    SUCCESS_LINE=$(grep "successful tests" logs/step3_granger.log 2>/dev/null | tail -1)
    if [ -n "$SUCCESS_LINE" ]; then
        SUCCESS_COUNT=$(echo "$SUCCESS_LINE" | grep -oP "\K[\d,]+(?= successful)")
        if [ -n "$SUCCESS_COUNT" ]; then
            echo ""
            echo "Successful tests: $SUCCESS_COUNT"
        fi
    fi
else
    echo "=========================================="
    echo "STEP 3: GRANGER CAUSALITY TESTING"
    echo "=========================================="
    echo "Progress: Initializing or no data yet..."
fi

echo ""
echo "=========================================="
echo "SYSTEM RESOURCES"
echo "=========================================="

# Memory usage
MEM_LINE=$(free -h | grep "Mem:")
MEM_USED=$(echo $MEM_LINE | awk '{print $3}')
MEM_TOTAL=$(echo $MEM_LINE | awk '{print $2}')
MEM_PERCENT=$(free | grep Mem | awk '{printf "%.1f", ($3/$2) * 100.0}')
echo "Memory:  $MEM_USED / $MEM_TOTAL ($MEM_PERCENT%)"

# CPU usage
if [ "$RUNNING" = true ]; then
    CPU_USAGE=$(ps -p $PID -o %cpu | tail -1 | xargs)
    echo "CPU (main): ${CPU_USAGE}%"

    CHILDREN=$(pgrep -P $PID 2>/dev/null | wc -l)
    if [ "$CHILDREN" -gt 0 ]; then
        echo "Workers: $CHILDREN parallel processes"
    fi
else
    CPU_USAGE=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}')
    echo "CPU (overall): ${CPU_USAGE}%"
fi

echo ""
echo "=========================================="
echo "LATEST LOG OUTPUT"
echo "=========================================="
tail -20 logs/step3_granger.log 2>/dev/null | grep -v "RuntimeWarning" | tail -15

echo ""
echo "=========================================="
if [ "$RUNNING" = true ]; then
    echo "📊 Refresh: bash scripts/monitor_granger.sh"
else
    echo "✅ Check results: logs/step3_granger.log"
fi
echo "=========================================="
