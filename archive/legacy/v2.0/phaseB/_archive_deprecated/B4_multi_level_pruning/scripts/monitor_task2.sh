#!/bin/bash
# B4 Task 2 Progress Monitor
# Shows real-time progress of SHAP computation

# Get script directory and set absolute path to log
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
B4_DIR="$(dirname "$SCRIPT_DIR")"
LOG_FILE="$B4_DIR/logs/task2_run2.log"
TOTAL_TARGETS=292

# Color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

clear

echo "=========================================================================="
echo "B4 TASK 2: SHAP COMPUTATION MONITOR"
echo "=========================================================================="
echo ""

while true; do
    # Check if log file exists
    if [ ! -f "$LOG_FILE" ]; then
        echo "⏳ Waiting for task to start..."
        echo "   Log file not found: $LOG_FILE"
        sleep 5
        continue
    fi

    # Extract current target number
    CURRENT=$(grep -oP 'Target \K\d+(?=/292)' "$LOG_FILE" | tail -1)

    if [ -z "$CURRENT" ]; then
        echo "⏳ Starting up..."
        sleep 5
        clear
        echo "=========================================================================="
        echo "B4 TASK 2: SHAP COMPUTATION MONITOR"
        echo "=========================================================================="
        echo ""
        continue
    fi

    # Calculate progress
    PROGRESS=$(awk "BEGIN {printf \"%.1f\", ($CURRENT / $TOTAL_TARGETS) * 100}")
    REMAINING=$((TOTAL_TARGETS - CURRENT))

    # Calculate progress bar
    BAR_LENGTH=50
    FILLED=$(awk "BEGIN {printf \"%.0f\", ($CURRENT / $TOTAL_TARGETS) * $BAR_LENGTH}")
    EMPTY=$((BAR_LENGTH - FILLED))

    # Get last few completed targets with R² scores
    RECENT_R2=$(grep -A 3 "Target.*292:" "$LOG_FILE" | grep "Model R²:" | tail -5 | awk '{print $4}')
    AVG_R2=$(echo "$RECENT_R2" | awk '{sum+=$1; count++} END {if (count>0) printf "%.3f", sum/count; else print "N/A"}')

    # Get top features from last completed target
    TOP_FEATURES=$(grep -A 7 "Top 5 features:" "$LOG_FILE" | tail -6 | grep -v "Top 5 features:")

    # Get elapsed time
    START_TIME=$(grep "Timestamp:" "$LOG_FILE" | head -1 | awk '{print $2}')
    if [ ! -z "$START_TIME" ]; then
        START_EPOCH=$(date -d "$START_TIME" +%s 2>/dev/null || echo "0")
        CURRENT_EPOCH=$(date +%s)
        if [ "$START_EPOCH" != "0" ]; then
            ELAPSED=$((CURRENT_EPOCH - START_EPOCH))
            HOURS=$((ELAPSED / 3600))
            MINUTES=$(((ELAPSED % 3600) / 60))
            SECONDS=$((ELAPSED % 60))
            ELAPSED_STR=$(printf "%02d:%02d:%02d" $HOURS $MINUTES $SECONDS)

            # Estimate remaining time
            if [ "$CURRENT" -gt 0 ]; then
                TIME_PER_TARGET=$(awk "BEGIN {printf \"%.1f\", $ELAPSED / $CURRENT}")
                REMAINING_SEC=$(awk "BEGIN {printf \"%.0f\", $TIME_PER_TARGET * $REMAINING}")
                REM_HOURS=$((REMAINING_SEC / 3600))
                REM_MINUTES=$(((REMAINING_SEC % 3600) / 60))
                REMAINING_STR=$(printf "%02d:%02d" $REM_HOURS $REM_MINUTES)
            else
                REMAINING_STR="Calculating..."
            fi
        else
            ELAPSED_STR="Unknown"
            REMAINING_STR="Unknown"
        fi
    else
        ELAPSED_STR="Unknown"
        REMAINING_STR="Unknown"
    fi

    # Clear and redraw
    clear
    echo "=========================================================================="
    echo -e "${BLUE}B4 TASK 2: SHAP COMPUTATION MONITOR${NC}"
    echo "=========================================================================="
    echo ""

    # Progress bar
    echo -e "${CYAN}Progress:${NC}"
    printf "["
    printf "%${FILLED}s" | tr ' ' '█'
    printf "%${EMPTY}s" | tr ' ' '░'
    printf "] ${GREEN}${PROGRESS}%%${NC}\n"
    echo ""

    # Statistics
    echo -e "${CYAN}Status:${NC}"
    echo "  Current Target:  $CURRENT / $TOTAL_TARGETS"
    echo "  Remaining:       $REMAINING targets"
    echo ""
    echo -e "${CYAN}Time:${NC}"
    echo "  Elapsed:         $ELAPSED_STR"
    echo "  Est. Remaining:  $REMAINING_STR"
    echo ""
    echo -e "${CYAN}Model Performance:${NC}"
    echo "  Avg R² (last 5): $AVG_R2"
    echo ""

    # Recent R² scores
    echo -e "${CYAN}Recent R² Scores:${NC}"
    echo "$RECENT_R2" | tail -5 | nl -w2 -s'. ' | sed 's/^/  /'
    echo ""

    # Top features from last target
    echo -e "${CYAN}Top 5 Features (Last Target):${NC}"
    echo "$TOP_FEATURES" | sed 's/^/  /' | head -5
    echo ""

    echo "=========================================================================="
    echo -e "${YELLOW}Press Ctrl+C to exit monitor${NC}"
    echo "=========================================================================="

    # Update every 5 seconds
    sleep 5
done
