#!/bin/bash
# Monitor Phase 2: Backdoor Identification Progress

echo "======================================================================"
echo "A4 Phase 2: Backdoor Identification Progress Monitor"
echo "======================================================================"
echo ""

# Check if process is running
if ps -p 308416 > /dev/null 2>&1; then
    echo "✅ Process Status: RUNNING (PID: 308416)"
else
    echo "⚠️  Process Status: NOT RUNNING"
fi

echo ""

# Check checkpoint
CHECKPOINT_FILE="../checkpoints/backdoor_sets_checkpoint.pkl"

if [ -f "$CHECKPOINT_FILE" ]; then
    echo "📊 Progress from checkpoint:"
    python3 << 'EOF'
import pickle
import sys

try:
    with open('../checkpoints/backdoor_sets_checkpoint.pkl', 'rb') as f:
        cp = pickle.load(f)

    processed = cp.get('processed_count', 0)
    total = 129989  # Total edges from Phase 1
    progress_pct = (processed / total) * 100

    print(f"  Processed: {processed:>10,} / {total:,} edges")
    print(f"  Progress:  {progress_pct:>10.1f}%")

    n_results = len(cp.get('results', []))
    print(f"  Results:   {n_results:>10,} backdoor sets identified")

    if n_results > 0:
        import pandas as pd
        df = pd.DataFrame(cp['results'])

        successful = df[df['status'] == 'identified']
        failed = df[df['status'] == 'failed']

        print(f"\n  Success rate: {len(successful)/len(df)*100:.1f}%")
        print(f"  Mean adjustment set size: {successful['backdoor_size'].mean():.1f}")

except Exception as e:
    print(f"Error reading checkpoint: {e}")
    sys.exit(1)
EOF
else
    echo "⏳ No checkpoint yet - process just started"
fi

echo ""
echo "======================================================================"
echo "Last 20 lines of log:"
echo "======================================================================"
tail -20 ../logs/step2_backdoor_identification.log
