#!/bin/bash
# Monitor causallearn PC-Stable progress

clear
echo "==============================================================================="
echo "                    CAUSALLEARN PC-STABLE MONITOR"
echo "==============================================================================="
echo ""

# Check if process is running
PID=$(ps aux | grep "step2_pc_stable_causallearn.py" | grep -v grep | awk '{print $2}')

if [ -z "$PID" ]; then
    echo "⚠️  Process NOT running"
    echo ""

    # Check if completed
    if [ -f "outputs/A3_validated_edges.pkl" ]; then
        echo "✅ PROCESS COMPLETED!"
        echo ""

        # Show final results from log
        echo "Final Results:"
        echo "-------------------------------------------------------------------------------"
        tail -20 logs/pc_causallearn.log | grep -A 10 "A3 COMPLETE"
        echo "==============================================================================="
    else
        echo "❌ Process died without completing"
        echo ""
        echo "Last 10 log entries:"
        echo "-------------------------------------------------------------------------------"
        tail -10 logs/pc_causallearn.log
        echo "==============================================================================="
    fi
    exit 1
fi

echo "✅ Process Running (PID: $PID)"
echo ""

# Process stats
echo "Process Status:"
echo "-------------------------------------------------------------------------------"
ps -p $PID -o pid,pcpu,pmem,etime,cmd --no-headers
echo ""

# Memory usage
MEM=$(ps -p $PID -o rss --no-headers)
MEM_GB=$(echo "scale=2; $MEM / 1048576" | bc)
echo "Memory Usage: ${MEM_GB} GB"
echo ""

# Check what stage we're at
echo "Current Stage:"
echo "-------------------------------------------------------------------------------"

# Parse log for stage info
if grep -q "Running PC-Stable" logs/pc_causallearn.log 2>/dev/null; then
    PC_START=$(grep "Running PC-Stable" logs/pc_causallearn.log | tail -1 | awk '{print $1, $2}')
    echo "✓ Data preparation complete"
    echo "✓ PC-Stable algorithm running (started: $PC_START)"
    echo ""

    # Try to estimate progress from causallearn verbose output
    # Note: causallearn doesn't give granular progress, so we show elapsed time
    START_TIME=$(grep "⏳ Starting at" logs/pc_causallearn.log | tail -1 | sed 's/.*Starting at //')
    CURRENT_TIME=$(date +"%Y-%m-%d %H:%M:%S")

    # Calculate elapsed hours
    START_EPOCH=$(date -d "$START_TIME" +%s 2>/dev/null)
    CURRENT_EPOCH=$(date +%s)

    if [ ! -z "$START_EPOCH" ]; then
        ELAPSED_SECONDS=$((CURRENT_EPOCH - START_EPOCH))
        ELAPSED_HOURS=$(echo "scale=2; $ELAPSED_SECONDS / 3600" | bc)

        echo "  Started: $START_TIME"
        echo "  Elapsed: ${ELAPSED_HOURS} hours"
        echo ""

        # Progress estimate (4-8 hour expected runtime)
        PROGRESS_MIN=$(echo "scale=1; ($ELAPSED_HOURS / 8) * 100" | bc)
        PROGRESS_MAX=$(echo "scale=1; ($ELAPSED_HOURS / 4) * 100" | bc)

        if (( $(echo "$PROGRESS_MIN > 100" | bc -l) )); then
            echo "  Progress: >100% (taking longer than expected 4-8 hours)"
        else
            echo "  Estimated Progress: ${PROGRESS_MIN}% - ${PROGRESS_MAX}%"
            echo "  (Based on 4-8 hour expected runtime)"
        fi

        # ETA
        if (( $(echo "$ELAPSED_HOURS < 4" | bc -l) )); then
            REMAINING_MIN=$(echo "scale=1; 4 - $ELAPSED_HOURS" | bc)
            REMAINING_MAX=$(echo "scale=1; 8 - $ELAPSED_HOURS" | bc)
            echo "  ETA: ${REMAINING_MIN} - ${REMAINING_MAX} hours remaining"
        fi
    fi

elif grep -q "Preparing data matrix" logs/pc_causallearn.log 2>/dev/null; then
    echo "⏳ Data preparation in progress..."

    # Check for indicator processing progress
    LAST_PROCESSED=$(grep "Processed.*indicators" logs/pc_causallearn.log | tail -1 | sed 's/.*Processed //' | sed 's/ indicators.*//')
    if [ ! -z "$LAST_PROCESSED" ]; then
        echo "  $LAST_PROCESSED"
    fi

elif grep -q "Loading" logs/pc_causallearn.log 2>/dev/null; then
    echo "⏳ Loading data..."
else
    echo "⏳ Starting up..."
fi

echo ""
echo "Latest Log Entries:"
echo "-------------------------------------------------------------------------------"
tail -15 logs/pc_causallearn.log | grep -v "^$"
echo ""
echo "==============================================================================="
echo "Monitor script: ./monitor_causallearn.sh"
echo "Full logs: tail -f logs/pc_causallearn.log"
echo "==============================================================================="
