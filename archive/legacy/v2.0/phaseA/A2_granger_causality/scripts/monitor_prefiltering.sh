#!/bin/bash
# Monitor prefiltering progress

cd "$(dirname "$0")/.."

echo "=========================================="
echo "     PREFILTERING PROGRESS MONITOR"
echo "=========================================="
echo ""

# Get start time
START_TIME=$(head -4 logs/step2_prefiltering.log 2>/dev/null | grep "Started:" | sed 's/Started: //')
if [ -n "$START_TIME" ]; then
    echo "Started: $START_TIME"
else
    echo "Started: Unknown"
fi

# Check if still running
PID=$(cat logs/step2_prefiltering.pid 2>/dev/null)
if [ -n "$PID" ] && kill -0 $PID 2>/dev/null; then
    echo "Status:  ✅ RUNNING (PID: $PID)"
    RUNNING=true
else
    echo "Status:  ⏸️  COMPLETED or STOPPED"
    RUNNING=false
fi

echo ""

# Extract progress from joblib output
# Joblib prints: [Parallel(n_jobs=20)]: Done   1 tasks      | elapsed:   10.5s
COMPLETED=$(grep -oP "Done\s+\K\d+" logs/step2_prefiltering.log 2>/dev/null | tail -1)
TOTAL=128  # Total chunks

if [ -n "$COMPLETED" ]; then
    PERCENT=$(awk "BEGIN {printf \"%.1f\", ($COMPLETED / $TOTAL) * 100}")
    echo "=========================================="
    echo "STAGE 1: CORRELATION FILTER"
    echo "=========================================="
    echo "Chunks completed: $COMPLETED / $TOTAL"
    echo "Progress:         $PERCENT%"

    # Progress bar
    FILLED=$(awk "BEGIN {printf \"%.0f\", ($COMPLETED / $TOTAL) * 40}")
    BAR=$(printf "%${FILLED}s" | tr ' ' '█')
    EMPTY=$(printf "%$((40-FILLED))s" | tr ' ' '░')
    echo "[$BAR$EMPTY] $PERCENT%"

    # Estimate time remaining
    if [ "$COMPLETED" -gt 0 ]; then
        ELAPSED_LINE=$(grep "elapsed:" logs/step2_prefiltering.log 2>/dev/null | tail -1)
        if [ -n "$ELAPSED_LINE" ]; then
            # Extract elapsed time (format could be: 10.5s, 2.3min, 1.2h)
            ELAPSED=$(echo "$ELAPSED_LINE" | grep -oP "elapsed:\s+\K[\d.]+[smh]+" | tail -1)
            echo ""
            echo "Last chunk time:  $ELAPSED"
            echo "Estimated total:  3-5 hours"
        fi
    fi
else
    echo "=========================================="
    echo "STAGE 1: CORRELATION FILTER"
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
    # Get CPU usage of the Python process
    CPU_USAGE=$(ps -p $PID -o %cpu | tail -1 | xargs)
    echo "CPU (main): ${CPU_USAGE}%"

    # Check for child processes
    CHILDREN=$(ps --ppid $PID -o pid= 2>/dev/null | wc -l)
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
# Show last meaningful lines (skip repetitive warnings)
tail -30 logs/step2_prefiltering.log | grep -v "RuntimeWarning" | grep -v "invalid value" | grep -v "divide" | tail -15

echo ""
echo "=========================================="
if [ "$RUNNING" = true ]; then
    echo "📊 Refresh this monitor: bash scripts/monitor_prefiltering.sh"
else
    echo "✅ Check final results in logs/step2_prefiltering.log"
fi
echo "=========================================="
