#!/bin/bash
# Monitor memory-safe Granger testing (v2)

cd "$(dirname "$0")/.."

echo "=========================================="
echo "   GRANGER TESTING MONITOR (V2)"
echo "=========================================="
echo ""

# Get start time from v2 log
START_TIME=$(grep "Started:" logs/step3_granger_v2.log 2>/dev/null | tail -1 | sed 's/Started: //')
if [ -n "$START_TIME" ]; then
    echo "Started: $START_TIME"
else
    echo "Started: Not yet started"
fi

# Check process status
PID=$(pgrep -f "step3_granger_testing_v2.py" | head -1)
if [ -n "$PID" ]; then
    echo "Status:  ✅ RUNNING (PID: $PID)"
    RUNNING=true
else
    echo "Status:  ⏸️  COMPLETED or STOPPED"
    RUNNING=false
fi

echo ""

# Read checkpoint (v2 uses lightweight checkpoint)
TOTAL_PAIRS=15889478
CHECKPOINT_FILE="checkpoints/granger_progress_v2.pkl"

if [ -f "$CHECKPOINT_FILE" ]; then
    CHECKPOINT_DATA=$(python3 -c "
import pickle
try:
    with open('$CHECKPOINT_FILE', 'rb') as f:
        cp = pickle.load(f)
    print(f'{cp[\"last_index\"]}|{cp[\"total_successful\"]}|{cp[\"timestamp\"]}')
except Exception as e:
    print(f'ERROR: {e}')
" 2>/dev/null)

    if [[ "$CHECKPOINT_DATA" != ERROR* ]] && [ -n "$CHECKPOINT_DATA" ]; then
        COMPLETED=$(echo $CHECKPOINT_DATA | cut -d'|' -f1)
        SUCCESS_COUNT=$(echo $CHECKPOINT_DATA | cut -d'|' -f2)
        CHECKPOINT_TIME=$(echo $CHECKPOINT_DATA | cut -d'|' -f3)

        PERCENT=$(awk "BEGIN {printf \"%.2f\", ($COMPLETED / $TOTAL_PAIRS) * 100}")
        SUCCESS_RATE=$(awk "BEGIN {printf \"%.1f\", ($SUCCESS_COUNT / $COMPLETED) * 100}")

        echo "=========================================="
        echo "PROGRESS"
        echo "=========================================="
        echo "Pairs tested:     $(printf "%'d" $COMPLETED) / $(printf "%'d" $TOTAL_PAIRS)"
        echo "Progress:         $PERCENT%"

        # Progress bar
        FILLED=$(awk "BEGIN {printf \"%.0f\", ($COMPLETED / $TOTAL_PAIRS) * 40}")
        BAR=$(printf "%${FILLED}s" | tr ' ' '█')
        EMPTY=$(printf "%$((40-FILLED))s" | tr ' ' '░')
        echo "[$BAR$EMPTY] $PERCENT%"

        echo ""
        echo "Successful tests: $(printf "%'d" $SUCCESS_COUNT) (${SUCCESS_RATE}% success rate)"
        echo "Last checkpoint:  $CHECKPOINT_TIME"

        # Time estimates
        if [ -n "$START_TIME" ]; then
            NOW=$(date +%s)
            START_SEC=$(date -d "$START_TIME" +%s 2>/dev/null || echo "0")
            if [ "$START_SEC" -gt 0 ]; then
                ELAPSED_SEC=$((NOW - START_SEC))
                ELAPSED_HOURS=$(awk "BEGIN {printf \"%.2f\", $ELAPSED_SEC / 3600}")

                if [ "$COMPLETED" -gt 0 ]; then
                    RATE=$(awk "BEGIN {printf \"%.2f\", $COMPLETED / $ELAPSED_SEC}")
                    REMAINING_SEC=$(awk "BEGIN {printf \"%.0f\", ($TOTAL_PAIRS - $COMPLETED) / $RATE}")
                    REMAINING_HOURS=$(awk "BEGIN {printf \"%.2f\", $REMAINING_SEC / 3600}")

                    echo ""
                    echo "Time elapsed:     ${ELAPSED_HOURS} hours"
                    echo "Est. remaining:   ${REMAINING_HOURS} hours"
                    echo "Processing rate:  $(printf "%'d" $(awk "BEGIN {printf \"%.0f\", $RATE * 3600}")) pairs/hour"
                fi
            fi
        fi
    else
        echo "=========================================="
        echo "PROGRESS"
        echo "=========================================="
        echo "Checkpoint error: $CHECKPOINT_DATA"
    fi
else
    echo "=========================================="
    echo "PROGRESS"
    echo "=========================================="
    echo "No checkpoint yet - initializing..."
fi

echo ""
echo "=========================================="
echo "SYSTEM RESOURCES"
echo "=========================================="

# Memory
MEM_LINE=$(free -h | grep "Mem:")
MEM_USED=$(echo $MEM_LINE | awk '{print $3}')
MEM_TOTAL=$(echo $MEM_LINE | awk '{print $2}')
MEM_PERCENT=$(free | grep Mem | awk '{printf "%.1f", ($3/$2) * 100.0}')
echo "Memory:  $MEM_USED / $MEM_TOTAL ($MEM_PERCENT%)"

# CPU
if [ "$RUNNING" = true ]; then
    CPU_USAGE=$(ps -p $PID -o %cpu | tail -1 | xargs)
    echo "CPU:     ${CPU_USAGE}%"

    CHILDREN=$(pgrep -P $PID 2>/dev/null | wc -l)
    if [ "$CHILDREN" -gt 0 ]; then
        echo "Workers: $CHILDREN parallel processes"
    fi
fi

# Incremental files
if [ -d "checkpoints/incremental_results" ]; then
    CHUNK_COUNT=$(ls checkpoints/incremental_results/chunk_*.pkl 2>/dev/null | wc -l)
    if [ "$CHUNK_COUNT" -gt 0 ]; then
        CHUNK_SIZE=$(du -sh checkpoints/incremental_results 2>/dev/null | awk '{print $1}')
        echo "Saved:   $CHUNK_COUNT chunk files ($CHUNK_SIZE)"
    fi
fi

echo ""
echo "=========================================="
echo "LATEST LOG OUTPUT"
echo "=========================================="
tail -15 logs/step3_granger_v2.log 2>/dev/null | grep -v "RuntimeWarning" | grep -v "FutureWarning" | grep -v "warnings.warn" | tail -8

echo ""
echo "=========================================="
if [ "$RUNNING" = true ]; then
    echo "📊 Refresh: bash scripts/monitor_v2.sh"
else
    echo "✅ Check results: outputs/granger_test_results.pkl"
fi
echo "=========================================="
