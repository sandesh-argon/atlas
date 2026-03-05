#!/bin/bash
# Progress checker for A4 Phase 3

echo "========================================="
echo "A4 PHASE 3 PROGRESS CHECK"
echo "$(date)"
echo "========================================="

# Check if process is running
if ps aux | grep "step3_effect_estimation" | grep -v grep > /dev/null; then
    echo "✅ Process is RUNNING"
else
    echo "⚠️  Process is NOT running"
fi

echo ""

# Check latest log entry
if [ -f "logs/step3_local_run.log" ]; then
    echo "Latest progress from log:"
    echo "-----------------------------------------"
    tail -50 logs/step3_local_run.log | grep "Chunk complete" | tail -1
    echo ""
fi

# Check checkpoints
latest_checkpoint=$(ls -t checkpoints/effect_estimation_checkpoint_*.pkl 2>/dev/null | head -1)
if [ -n "$latest_checkpoint" ]; then
    edges_done=$(echo $latest_checkpoint | grep -oP '\d+(?=\.pkl)')
    percent=$((edges_done * 100 / 129989))

    echo "Latest checkpoint: $(basename $latest_checkpoint)"
    echo "Edges completed: $edges_done / 129,989 ($percent%)"
    echo ""

    # Calculate remaining time
    local_remaining=$((129989 - edges_done))
    local_hours=$((local_remaining * 60 / 147 / 60))  # 14.7 edges/min * 10 = 147 edges/10min
    aws_hours=$((local_remaining * 60 / 235 / 60))    # 235 edges/min

    echo "Time estimates:"
    echo "  Local remaining: ~$local_hours hours"
    echo "  AWS remaining: ~$((aws_hours + 1)) hours (+ 1hr setup)"
    echo "  Time saved by switching: ~$((local_hours - aws_hours - 1)) hours"
    echo ""

    # Decision helper
    time_saved=$((local_hours - aws_hours - 1))
    if [ $time_saved -gt 48 ]; then
        echo "💡 RECOMMENDATION: SWITCH TO AWS (saves 2+ days)"
    elif [ $time_saved -gt 24 ]; then
        echo "💡 RECOMMENDATION: Consider AWS (saves 1+ day)"
    elif [ $time_saved -gt 6 ]; then
        echo "💡 RECOMMENDATION: Maybe AWS (saves 6+ hours)"
    else
        echo "💡 RECOMMENDATION: Continue local (almost done)"
    fi
else
    echo "No checkpoints found yet"
fi

echo ""
echo "========================================="
