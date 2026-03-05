#!/bin/bash
# Monitor custom pairwise PC-Stable progress

clear
echo "==============================================================================="
echo "                  CUSTOM PAIRWISE PC-STABLE MONITOR"
echo "==============================================================================="
echo ""

# Check if process is running
PID=$(ps aux | grep "step2_custom_pairwise_pc.py" | grep -v grep | awk '{print $2}')

if [ -z "$PID" ]; then
    echo "⚠️  Process NOT running"
    echo ""

    # Check if completed
    if [ -f "outputs/A3_validated_edges.pkl" ]; then
        echo "✅ PROCESS COMPLETED!"
        echo ""
        echo "Final Results:"
        echo "-------------------------------------------------------------------------------"
        tail -30 logs/pairwise_pc.log | grep -A 20 "A3 COMPLETE"
        echo "==============================================================================="
    else
        echo "❌ Process died without completing"
        echo ""
        echo "Last 15 log entries:"
        echo "-------------------------------------------------------------------------------"
        tail -15 logs/pairwise_pc.log
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

# Check for checkpoint
if [ -f "checkpoints/pairwise_pc_checkpoint.pkl" ]; then
    echo "Progress:"
    echo "-------------------------------------------------------------------------------"
    python3 << EOF
import pickle
try:
    with open('checkpoints/pairwise_pc_checkpoint.pkl', 'rb') as f:
        cp = pickle.load(f)

    processed = cp['edges_processed']
    total = cp['total_edges']
    validated = len(cp['validated_edges'])
    elapsed = cp['elapsed_seconds']

    progress = processed / total * 100
    rate = processed / elapsed if elapsed > 0 else 0
    eta_seconds = (total - processed) / rate if rate > 0 else 0
    eta_hours = eta_seconds / 3600

    retention = validated / processed * 100 if processed > 0 else 0

    print(f"  Processed: {processed:,} / {total:,} edges ({progress:.1f}%)")
    print(f"  Validated: {validated:,} edges ({retention:.1f}% retention)")
    print(f"  Rate: {rate:.1f} edges/sec")
    print(f"  Elapsed: {elapsed/3600:.2f} hours")
    print(f"  ETA: {eta_hours:.2f} hours")
    print("")
    print(f"  Failed edges:")
    failed = cp.get('failed_stats', {})
    print(f"    Insufficient obs: {failed.get('insufficient_obs', 0):,}")
    print(f"    Missing variables: {failed.get('missing_variable', 0):,}")
    print(f"    Confounded: {failed.get('confounded', 0):,}")

    # Projected final count
    projected_final = int(validated / processed * total) if processed > 0 else 0
    print(f"\n  Projected final edges: {projected_final:,}")

    if 30_000 <= projected_final <= 80_000:
        print(f"  ✅ Projected within target range (30K-80K)")
    elif projected_final < 30_000:
        print(f"  ⚠️  Projected below target (<30K)")
    else:
        print(f"  ⚠️  Projected above target (>80K)")

except Exception as e:
    print(f"  Error reading checkpoint: {e}")
EOF
else
    echo "No checkpoint yet (first checkpoint at 5,000 edges)"
fi

echo ""
echo "Latest Log Entries:"
echo "-------------------------------------------------------------------------------"
tail -10 logs/pairwise_pc.log | grep -v "^$"
echo ""
echo "==============================================================================="
echo "Monitor script: ./monitor_pairwise_pc.sh"
echo "Full logs: tail -f logs/pairwise_pc.log"
echo "==============================================================================="
