#!/bin/bash
# Monitor Granger causality testing progress (reads from checkpoint file)

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

# Extract progress from checkpoint file (most reliable method)
TOTAL_PAIRS=15889478
CHECKPOINT_FILE="checkpoints/granger_progress.pkl"

if [ -f "$CHECKPOINT_FILE" ]; then
    # Read checkpoint using Python
    CHECKPOINT_DATA=$(python3 -c "
import pickle
try:
    with open('$CHECKPOINT_FILE', 'rb') as f:
        cp = pickle.load(f)
    print(f'{cp[\"last_index\"]}|{len(cp[\"results\"])}|{cp[\"timestamp\"]}')
except:
    print('ERROR')
" 2>/dev/null)

    if [ "$CHECKPOINT_DATA" != "ERROR" ] && [ -n "$CHECKPOINT_DATA" ]; then
        COMPLETED=$(echo $CHECKPOINT_DATA | cut -d'|' -f1)
        SUCCESS_COUNT=$(echo $CHECKPOINT_DATA | cut -d'|' -f2)
        CHECKPOINT_TIME=$(echo $CHECKPOINT_DATA | cut -d'|' -f3)

        PERCENT=$(awk "BEGIN {printf \"%.2f\", ($COMPLETED / $TOTAL_PAIRS) * 100}")
        SUCCESS_RATE=$(awk "BEGIN {printf \"%.1f\", ($SUCCESS_COUNT / $COMPLETED) * 100}")

        echo "=========================================="
        echo "STEP 3: GRANGER CAUSALITY TESTING"
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

        # Calculate time estimates
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
        echo "STEP 3: GRANGER CAUSALITY TESTING"
        echo "=========================================="
        echo "Progress: Checkpoint file unreadable..."
    fi
else
    echo "=========================================="
    echo "STEP 3: GRANGER CAUSALITY TESTING"
    echo "=========================================="
    echo "Progress: No checkpoint file yet..."
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

# GPU usage (if available)
if command -v nvidia-smi &> /dev/null; then
    GPU_INFO=$(nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total --format=csv,noheader,nounits 2>/dev/null | head -1)
    if [ -n "$GPU_INFO" ]; then
        GPU_UTIL=$(echo $GPU_INFO | cut -d',' -f1)
        GPU_MEM=$(echo $GPU_INFO | cut -d',' -f2 | xargs)
        GPU_TOTAL=$(echo $GPU_INFO | cut -d',' -f3 | xargs)
        echo "GPU:     ${GPU_UTIL}% (${GPU_MEM}MB / ${GPU_TOTAL}MB) [NOT USED - CPU-only task]"
    fi
fi

echo ""
echo "=========================================="
echo "LATEST LOG OUTPUT"
echo "=========================================="
tail -20 logs/step3_granger.log 2>/dev/null | grep -v "RuntimeWarning" | grep -v "FutureWarning" | grep -v "warnings.warn" | tail -10

echo ""
echo "=========================================="
if [ "$RUNNING" = true ]; then
    echo "📊 Refresh: bash scripts/monitor_granger_v2.sh"
else
    echo "✅ Check results: logs/step3_granger.log"
fi
echo "=========================================="
