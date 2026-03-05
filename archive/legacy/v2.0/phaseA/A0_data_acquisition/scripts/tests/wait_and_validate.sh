#!/bin/bash

# Wait for World Bank extraction to complete, then auto-run validation
# Usage: ./wait_and_validate.sh

cd "$(dirname "$0")"

echo "========================================="
echo "  A0.6 EXTRACTION AUTO-VALIDATOR"
echo "========================================="
echo ""
echo "Monitoring World Bank extraction progress..."
echo "Validation will run automatically when complete."
echo ""
echo "Press Ctrl+C to stop monitoring (extraction will continue)"
echo ""

# Check every 60 seconds
LAST_COUNT=0
NO_CHANGE_COUNT=0

while true; do
    # Check if World Bank process is still running
    if ! pgrep -f "world_bank_wdi_parallel.py" > /dev/null; then
        echo ""
        echo "✅ World Bank extraction process completed!"
        echo ""
        break
    fi

    # Get current count
    CURRENT_COUNT=$(ls raw_data/world_bank/*.csv 2>/dev/null | wc -l)

    # Check if count is still changing
    if [ "$CURRENT_COUNT" -eq "$LAST_COUNT" ]; then
        NO_CHANGE_COUNT=$((NO_CHANGE_COUNT + 1))

        # If no change for 5 minutes (5 checks), assume complete
        if [ $NO_CHANGE_COUNT -ge 5 ]; then
            echo ""
            echo "⚠️  No progress detected for 5 minutes - assuming complete"
            echo ""
            break
        fi
    else
        NO_CHANGE_COUNT=0
    fi

    LAST_COUNT=$CURRENT_COUNT

    # Show progress
    PERCENT=$((CURRENT_COUNT * 100 / 29213))
    echo -ne "\r[$(date +%H:%M:%S)] World Bank: $CURRENT_COUNT / 29,213 ($PERCENT%) | No change: ${NO_CHANGE_COUNT}x60s"

    # Wait 60 seconds
    sleep 60
done

echo "========================================="
echo "  STARTING VALIDATION"
echo "========================================="
echo ""

# Run validation
python validate_a06_extraction.py

# Check exit code
if [ $? -eq 0 ]; then
    echo ""
    echo "========================================="
    echo "  ✅ VALIDATION PASSED"
    echo "========================================="
    echo ""
    echo "Next step: Proceed to Part 2 (A0.7-A0.14: Write 6 new scrapers)"
    echo ""
else
    echo ""
    echo "========================================="
    echo "  ⚠️  VALIDATION NEEDS REVIEW"
    echo "========================================="
    echo ""
    echo "Check A06_VALIDATION_REPORT.json for details"
    echo ""
fi

echo "Full report saved to: A06_VALIDATION_REPORT.json"
echo ""
