#!/bin/bash
# Monitor the backdoor test progress

echo "================================================================================================"
echo "BACKDOOR TEST MONITOR"
echo "================================================================================================"
echo ""

# Check if test is running
PID=$(ps aux | grep "step2b_full_backdoor_test.py" | grep -v grep | awk '{print $2}')

if [ -z "$PID" ]; then
    echo "❌ Test not running"
    echo ""
    echo "Check if completed:"
    ls -lh tests/backdoor_test*.pkl 2>/dev/null
    echo ""
    echo "Last log entries:"
    tail -20 logs/step2b_test_*.log 2>/dev/null
    exit 0
fi

# Get runtime and CPU usage
RUNTIME=$(ps -o etime -p $PID | tail -1 | xargs)
TOTAL_CPU=$(ps aux | grep -E "python.*step2b|LokyProcess" | grep -v grep | awk '{sum+=$3} END {print sum}')
NUM_WORKERS=$(ps aux | grep -E "LokyProcess|python.*step2b" | grep -v grep | wc -l)

echo "✅ Test Status: RUNNING"
echo "   PID: $PID"
echo "   Runtime: $RUNTIME"
echo "   Workers: $NUM_WORKERS (1 main + 10 parallel)"
echo "   Total CPU: ${TOTAL_CPU}%"
echo ""

# Show last log entries
echo "Recent Log Output:"
echo "---"
tail -15 logs/step2b_test_*.log 2>/dev/null | grep -E "INFO|Progress|Complete|ERROR"
echo "---"
echo ""

# Check for output file
if [ -f tests/backdoor_test.pkl ]; then
    SIZE=$(ls -lh tests/backdoor_test.pkl | awk '{print $5}')
    echo "✅ Output file created: tests/backdoor_test.pkl ($SIZE)"
else
    echo "⏳ Output file not yet created (test still processing)"
fi

echo ""
echo "================================================================================================"
echo "Refresh this monitor: bash scripts/monitor_test.sh"
echo "View live log: tail -f logs/step2b_test_*.log"
echo "================================================================================================"
