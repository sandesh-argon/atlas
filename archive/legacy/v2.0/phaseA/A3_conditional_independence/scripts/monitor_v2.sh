#!/bin/bash
# Monitor PC-Stable v2 progress with % completion

echo "=========================================="
echo "A3 PC-Stable v2 Progress Monitor"
echo "=========================================="
echo ""

# Check if checkpoint exists
if [ -f "checkpoints/pairwise_pc_checkpoint.pkl" ]; then
    python3 << 'EOF'
import pickle
import sys
from datetime import datetime

try:
    with open('checkpoints/pairwise_pc_checkpoint.pkl', 'rb') as f:
        cp = pickle.load(f)

    processed = cp.get('edges_processed', 0)
    total = cp.get('total_edges', 279975)  # New total
    validated = len(cp.get('validated_edges', []))
    removed = len(cp.get('removed_edges', []))

    progress_pct = (processed / total) * 100
    remaining = total - processed

    # Calculate rates
    if 'start_time' in cp:
        elapsed = (datetime.now() - cp['start_time']).total_seconds()
        rate = processed / elapsed if elapsed > 0 else 0
        eta_seconds = remaining / rate if rate > 0 else 0
        eta_hours = eta_seconds / 3600
    else:
        elapsed = 0
        rate = 0
        eta_hours = 0

    print(f"PROGRESS: {progress_pct:.1f}% Complete")
    print(f"{'='*50}")
    print(f"  Processed:  {processed:>10,} / {total:,} edges")
    print(f"  Remaining:  {remaining:>10,} edges")
    print(f"")
    print(f"RESULTS:")
    print(f"  Validated:  {validated:>10,} edges ({validated/processed*100:.1f}%)")
    print(f"  Removed:    {removed:>10,} edges ({removed/processed*100:.1f}%)")
    print(f"")
    if rate > 0:
        print(f"TIMING:")
        print(f"  Elapsed:    {elapsed/3600:>10.1f} hours")
        print(f"  Rate:       {rate:>10.1f} edges/sec")
        print(f"  ETA:        {eta_hours:>10.1f} hours")

    print(f"{'='*50}")

except Exception as e:
    print(f"Error reading checkpoint: {e}")
    sys.exit(1)
EOF
else
    echo "⚠️  No checkpoint found yet"
    echo ""
    echo "Checking if process is running..."
    if ps aux | grep -q "[s]tep2_custom_pairwise_pc.py"; then
        echo "✅ PC-Stable is running (initializing...)"

        # Check log file
        if [ -f "logs/pairwise_pc_v2.log" ]; then
            echo ""
            echo "Last 10 log lines:"
            echo "----------------------------------------"
            tail -10 logs/pairwise_pc_v2.log
        fi
    else
        echo "❌ PC-Stable is not running"
    fi
fi

echo ""
echo "=========================================="
echo "Run: watch -n 30 ./monitor_v2.sh"
echo "  (updates every 30 seconds)"
echo "=========================================="
