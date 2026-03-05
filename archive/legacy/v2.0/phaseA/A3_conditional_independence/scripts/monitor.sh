#!/bin/bash
# Simple PC-Stable progress monitor with % completion

clear
echo "==============================================================================="
echo "                     PC-STABLE PROGRESS MONITOR"
echo "==============================================================================="
echo ""

# Check if process is running
PID=$(ps aux | grep "step2_custom_pairwise_pc.py" | grep -v grep | awk '{print $2}')

if [ -z "$PID" ]; then
    echo "❌ Process NOT running"
    echo ""

    # Check if completed
    if [ -f "outputs/A3_validated_edges.pkl" ]; then
        echo "✅ COMPLETED!"
        echo ""
        tail -20 logs/pairwise_pc.log | grep -A 15 "COMPLETE"
    else
        echo "Check logs for errors:"
        tail -10 logs/pairwise_pc.log
    fi
    exit 1
fi

echo "✅ Process Running (PID: $PID)"
echo ""

# Check for checkpoint
if [ -f "checkpoints/pairwise_pc_checkpoint.pkl" ]; then
    python3 << 'EOF'
import pickle
import sys

try:
    with open('checkpoints/pairwise_pc_checkpoint.pkl', 'rb') as f:
        cp = pickle.load(f)

    processed = cp['edges_processed']
    total = cp['total_edges']
    validated = len(cp['validated_edges'])
    elapsed = cp['elapsed_seconds']

    # Progress
    progress_pct = (processed / total) * 100

    # Rate and ETA
    rate = processed / elapsed if elapsed > 0 else 0
    remaining = total - processed
    eta_seconds = remaining / rate if rate > 0 else 0
    eta_hours = eta_seconds / 3600
    eta_minutes = eta_seconds / 60

    # Retention rate
    retention_pct = (validated / processed) * 100 if processed > 0 else 0

    # Reduction rate
    reduction_pct = 100 - retention_pct

    # Projected final
    projected_final = int((validated / processed) * total) if processed > 0 else 0

    # Display
    print("="*79)
    print(f"PROGRESS: {progress_pct:.1f}% Complete")
    print("="*79)
    print(f"  Processed:  {processed:>8,} / {total:,} edges")
    print(f"  Validated:  {validated:>8,} edges ({retention_pct:.1f}% kept)")
    print(f"  Removed:    {processed - validated:>8,} edges ({reduction_pct:.1f}% filtered)")
    print("")
    print(f"PERFORMANCE:")
    print(f"  Rate:       {rate:>8.1f} edges/sec")
    print(f"  Elapsed:    {elapsed/3600:>8.2f} hours")
    if eta_hours > 1:
        print(f"  ETA:        {eta_hours:>8.2f} hours")
    else:
        print(f"  ETA:        {eta_minutes:>8.1f} minutes")
    print("")
    print(f"PROJECTION:")
    print(f"  Final edges: ~{projected_final:,}")

    if 30_000 <= projected_final <= 80_000:
        print(f"  ✅ Within target range (30K-80K)")
    elif projected_final < 30_000:
        print(f"  ⚠️  Below target (<30K) - may need looser alpha")
    else:
        print(f"  ⚠️  Above target (>80K) - may need stricter alpha")

    print("")
    print(f"REMOVAL BREAKDOWN:")
    failed = cp.get('failed_stats', {})
    print(f"  Confounded:     {failed.get('confounded', 0):>8,}")
    print(f"  Insufficient:   {failed.get('insufficient_obs', 0):>8,}")
    print(f"  Missing vars:   {failed.get('missing_variable', 0):>8,}")

except Exception as e:
    print(f"Error reading checkpoint: {e}", file=sys.stderr)
    sys.exit(1)
EOF
else
    echo "Waiting for first checkpoint (5,000 edges)..."
    echo ""
    echo "Recent log:"
    tail -5 logs/pairwise_pc.log
fi

echo ""
echo "==============================================================================="
echo "Refresh: ./monitor.sh  |  Full logs: tail -f logs/pairwise_pc.log"
echo "==============================================================================="
