#!/bin/bash
# Quick progress checker for PC-Stable run

echo "==============================================="
echo "PC-STABLE PROGRESS CHECK"
echo "==============================================="
echo ""

# Check if process is running
PID=$(ps aux | grep "step2_pc_stable.py" | grep -v grep | awk '{print $2}')

if [ -z "$PID" ]; then
    echo "⚠️  Process not running"
    echo ""
    echo "Check if completed:"
    ls -lh outputs/A3_validated_edges.pkl 2>/dev/null && echo "✓ Output file exists" || echo "✗ Output file not found"
    exit 1
fi

echo "✓ Process running (PID: $PID)"
echo ""

# Process runtime and resource usage
echo "Process Status:"
ps -p $PID -o pid,pcpu,pmem,etime,cmd --no-headers
echo ""

# Check for checkpoint
if [ -f "checkpoints/a3_pc_stable_progress.pkl" ]; then
    echo "Checkpoint Progress:"
    python3 << EOF
import pickle
try:
    with open('checkpoints/a3_pc_stable_progress.pkl', 'rb') as f:
        cp = pickle.load(f)

    processed = cp['edges_processed']
    total = cp['total_edges']
    validated = cp['validated_edges']
    elapsed = cp['elapsed_seconds']

    progress = processed / total * 100
    rate = processed / elapsed if elapsed > 0 else 0
    eta_seconds = (total - processed) / rate if rate > 0 else 0
    eta_hours = eta_seconds / 3600

    print(f"  Processed: {processed:,} / {total:,} edges ({progress:.2f}%)")
    print(f"  Validated: {validated:,} edges")
    print(f"  Reduction: {(1 - validated/processed)*100:.2f}%")
    print(f"  Rate: {rate:.1f} edges/sec")
    print(f"  Elapsed: {elapsed/3600:.2f} hours")
    print(f"  ETA: {eta_hours:.2f} hours")
except Exception as e:
    print(f"  Error reading checkpoint: {e}")
EOF
else
    echo "No checkpoint yet (first checkpoint at 10,000 edges)"
fi

echo ""
echo "Latest log entries:"
tail -5 logs/step2_pc_stable.log
echo ""
echo "==============================================="
