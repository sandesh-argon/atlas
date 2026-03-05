#!/bin/bash
# Monitor Phase 2: Backdoor Identification with Thermal Info

echo "======================================================================"
echo "A4 Phase 2: Backdoor Identification Progress (Thermal Safe Mode)"
echo "======================================================================"
echo ""

# Check process status (look for worker processes)
WORKERS=$(ps aux | grep "LokyProcess" | grep -v grep | wc -l)
MAIN_PID=$(ps aux | grep "step2_backdoor_dseparation.py" | grep -v grep | awk '{print $2}' | head -1)

if [ -n "$MAIN_PID" ] && [ "$WORKERS" -gt 0 ]; then
    TOTAL_CPU=$(ps aux | grep "LokyProcess" | grep -v grep | awk '{sum+=$3} END {print sum}')
    echo "✅ Process Status: RUNNING (Main PID: $MAIN_PID, Workers: $WORKERS, Total CPU: ${TOTAL_CPU}%)"
elif [ -n "$MAIN_PID" ]; then
    echo "🔄 Process Status: INITIALIZING (PID: $MAIN_PID)"
else
    echo "⚠️  Process Status: NOT RUNNING"
fi

echo ""

# Temperature check
echo "🌡️  Temperature:"
sensors | grep -E "Tctl|Package" | head -1
echo ""

# Check checkpoint
CHECKPOINT_FILE="../checkpoints/backdoor_dsep_checkpoint.pkl"

if [ -f "$CHECKPOINT_FILE" ]; then
    echo "📊 Progress from checkpoint:"
    python3 << 'EOF'
import pickle
import sys
from datetime import datetime

try:
    with open('../checkpoints/backdoor_sets_minimal_checkpoint.pkl', 'rb') as f:
        cp = pickle.load(f)

    processed = cp.get('processed_count', 0)
    total = 129989  # Total edges from Phase 1
    progress_pct = (processed / total) * 100

    print(f"  Processed: {processed:>10,} / {total:,} edges")
    print(f"  Progress:  {progress_pct:>10.1f}%")

    chunks_done = processed // 10000
    chunks_total = 13
    print(f"  Chunks:    {chunks_done:>10} / {chunks_total} complete")

    n_results = len(cp.get('results', []))
    print(f"  Results:   {n_results:>10,} backdoor sets identified")

    if n_results > 0:
        import pandas as pd
        df = pd.DataFrame(cp['results'])

        successful = df[df['status'] == 'identified']
        failed = df[df['status'] != 'identified']

        print(f"\n  Success rate: {len(successful)/len(df)*100:.1f}%")
        if len(successful) > 0:
            print(f"  Mean backdoor size: {successful['backdoor_size'].mean():.1f}")
            print(f"  Median backdoor size: {successful['backdoor_size'].median():.0f}")
            print(f"  Max backdoor size: {successful['backdoor_size'].max()}")

    # Timestamp
    last_update = cp.get('timestamp', 'Unknown')
    print(f"\n  Last checkpoint: {last_update}")

except Exception as e:
    print(f"Error reading checkpoint: {e}")
    sys.exit(1)
EOF
else
    echo "⏳ No checkpoint yet - process just started"
fi

echo ""
echo "======================================================================"
echo "Last 15 lines of log:"
echo "======================================================================"
tail -15 ../logs/step2_dseparation.log
echo ""
echo "======================================================================"
echo "Run './monitor_phase2_thermal.sh' again to refresh"
echo "======================================================================"
