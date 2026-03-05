# Long-Running Task Monitor Guide (V2.1)

This document describes the monitoring system for long-running parallel tasks in the V2.1 pipeline.

## The Problem

Long-running tasks using `joblib.Parallel` have three issues:
1. **No progress visibility until chunk completes**: If you process 5000 items per chunk at 5 items/sec, you wait 16+ minutes before seeing any progress update
2. **Joblib writes to stderr, not stdout**: The verbose output (`Done 201 tasks | elapsed: 6.2min`) goes to stderr, not to your log file
3. **Inaccurate ETA after restarts**: If you restart a task, the "time from start" calculation gives wrong elapsed time and bad ETA

## The Solution

We implemented a three-part solution:

### Part 1: TeeStderr Class (Python Script)

Add this to your Python script after the logging setup to capture joblib's stderr output in your log file:

```python
# Redirect stderr to log file so joblib verbose output is captured
# This enables intra-chunk progress monitoring via monitor.sh
class TeeStderr:
    """Tee stderr to both console and log file for joblib verbose output"""
    def __init__(self, log_file):
        self.terminal = sys.stderr
        self.log = open(log_file, 'a')
    def write(self, message):
        self.terminal.write(message)
        self.log.write(message)
        self.log.flush()
    def flush(self):
        self.terminal.flush()
        self.log.flush()

sys.stderr = TeeStderr(LOG_FILE)
```

### Part 2: progress.json with Accurate Rate

Your Python script should write a `progress.json` file after each chunk with the **actual rate** calculated from processing time:

```python
import json
from datetime import datetime

# After each chunk completes:
progress_file = OUTPUT_DIR / 'progress.json'
with open(progress_file, 'w') as f:
    json.dump({
        'step': 'step_name',
        'pct': 100.0 * items_done / total_items,
        'elapsed_min': elapsed_seconds / 60,
        'eta_min': remaining_items / rate / 60,  # rate from actual processing
        'items_done': items_done,
        'items_total': total_items,
        'updated': datetime.now().isoformat(),
        'rate_per_sec': rate  # CRITICAL: Store the actual rate
    }, f, indent=2)
```

### Part 3: monitor.sh with Dual Sources

The monitor script parses both sources and uses the more accurate one:
1. **progress.json** - Has accurate rate from actual processing time (use for ETA)
2. **Log file** - Has real-time intra-chunk progress (use for current chunk status)

Key features:
- Shows chunk-level progress from progress.json with **accurate ETA**
- Shows intra-chunk progress from joblib verbose output
- Uses rate from progress.json (avoids restart time errors)
- Shows CPU temps and memory usage

## Requirements for Your Python Script

### 1. Enable joblib verbose output
```python
from joblib import Parallel, delayed

results = Parallel(n_jobs=10, verbose=10, batch_size='auto')(
    delayed(process_item)(item) for item in items
)
```

### 2. Log a "Started:" line with timestamp
```python
logger.info(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
```

### 3. Log total items
```python
logger.info(f"Processing all {len(items):,} items")
```

### 4. Log chunk info with consistent format
```python
logger.info(f"Chunk {chunk_num}/{total_chunks}: Edges {start} - {end}")
# OR
logger.info(f"Chunk {chunk_num}/{total_chunks}: Items {start} - {end}")
```

### 5. Write progress.json with rate_per_sec
```python
with open(progress_file, 'w') as f:
    json.dump({
        'pct': percentage,
        'items_done': done,
        'items_total': total,
        'rate_per_sec': actual_rate,  # CRITICAL!
        'eta_min': eta_minutes,
        'updated': datetime.now().isoformat()
    }, f, indent=2)
```

### 6. Include TeeStderr class (as shown above)

## Updated monitor.sh Template

Create a `monitor.sh` in your script directory:

```bash
#!/bin/bash
# Monitor Script - Usage: ./monitor.sh (or: watch -n 10 ./monitor.sh)

PROGRESS_FILE="/path/to/outputs/progress.json"
LOG_FILE="/path/to/logs/step_name.log"

echo "=========================================="
echo "TASK NAME MONITOR"
echo "=========================================="

# FIRST: Show progress.json (has ACCURATE rate and ETA)
if [ -f "$PROGRESS_FILE" ]; then
    echo "--- Chunk Progress (ACCURATE ETA) ---"
    cat "$PROGRESS_FILE" | python3 -c "
import json, sys
from datetime import datetime, timedelta

data = json.load(sys.stdin)
pct = data.get('pct', 0)
items_done = data.get('items_done', 0)
items_total = data.get('items_total', 0)
rate = data.get('rate_per_sec', 0)
eta_min = data.get('eta_min', 0)
updated = data.get('updated', 'N/A')

print(f'Progress: {pct:.1f}%')
print(f'Items: {items_done:,} / {items_total:,}')
print(f'Rate: {rate:.2f}/sec')
print(f'ETA: {eta_min:.1f} min ({eta_min/60:.1f} hrs)')

if eta_min > 0:
    completion = datetime.now() + timedelta(minutes=eta_min)
    print(f'Est. Done At: {completion.strftime(\"%Y-%m-%d %H:%M:%S\")}')

print(f'Updated: {updated}')
"
    echo ""
fi

# SECOND: Show intra-chunk progress from log (real-time)
if [ -f "$LOG_FILE" ]; then
    echo "--- Live Intra-Chunk Progress ---"
    python3 -c "
import re
import json

log_file = '$LOG_FILE'
progress_file = '$PROGRESS_FILE'

# Load saved rate from progress.json
saved_rate = None
try:
    with open(progress_file, 'r') as f:
        pdata = json.load(f)
        saved_rate = pdata.get('rate_per_sec', None)
        total_items = pdata.get('items_total', 58837)
except:
    total_items = 58837

# Parse log for current chunk
chunk_info = None
tasks_done = 0

with open(log_file, 'r') as f:
    lines = f.readlines()

for line in lines:
    if 'Chunk' in line and ('Edges' in line or 'Items' in line):
        match = re.search(r'Chunk (\d+)/(\d+):.*?(\d+) - (\d+)', line)
        if match:
            chunk_num, total_chunks = int(match.group(1)), int(match.group(2))
            chunk_start, chunk_end = int(match.group(3)), int(match.group(4))
            chunk_info = (chunk_num, total_chunks, chunk_start, chunk_end)

for line in reversed(lines[-50:]):
    match = re.search(r'Done\s+(\d+)\s+tasks', line)
    if match:
        tasks_done = int(match.group(1))
        break

if chunk_info:
    chunk_num, total_chunks, chunk_start, chunk_end = chunk_info
    total_done = chunk_start + tasks_done
    chunk_size = chunk_end - chunk_start
    pct = 100.0 * total_done / total_items

    print(f'Current Chunk: {chunk_num}/{total_chunks}')
    print(f'Chunk Progress: {tasks_done}/{chunk_size} ({100*tasks_done/chunk_size:.1f}%)')
    print(f'Overall Progress: {total_done:,}/{total_items:,} ({pct:.1f}%)')

    # Use saved rate for ETA (more accurate than calculating from start time)
    if saved_rate and saved_rate > 0:
        from datetime import datetime, timedelta
        remaining = total_items - total_done
        eta_sec = remaining / saved_rate
        print(f'Rate: {saved_rate:.2f}/sec (from checkpoint)')
        print(f'ETA: {eta_sec/60:.1f} min ({eta_sec/3600:.1f} hrs)')
"
fi

echo ""
echo "--- Recent Log ---"
tail -3 \"\$LOG_FILE\" 2>/dev/null

echo ""
echo "--- System ---"
sensors 2>/dev/null | grep -E \"Tctl|Tccd\" | head -3
free -h | head -2
```

## Usage

1. Start your long-running task
2. In another terminal: `watch -n 10 ./monitor.sh`

This will refresh every 10 seconds and show live progress.

## Example Output

```
==========================================
A4 EFFECT ESTIMATION MONITOR
==========================================
--- Chunk Progress (ACCURATE ETA) ---
Progress: 7.6%
Items: 4,500 / 58,837
Rate: 1.07 edges/sec
ETA: 849.8 min (14.2 hrs)
Est. Done At: 2025-12-05 02:33:20
Updated: 2025-12-04T12:09:26.856448

--- Live Intra-Chunk Progress ---
Current Chunk: 10/118
Chunk Progress: 108/500 (21.6%)
Overall Progress: 4,608/58,837 (7.8%)
Rate: 1.07/sec (from checkpoint)
ETA: 845.1 min (14.1 hrs)

--- Recent Log ---
[Parallel(n_jobs=10)]: Done 108 tasks      | elapsed:  2.0min

--- System ---
Tctl:         +90.8°C
               total        used        free
Mem:            31Gi        13Gi        14Gi
```

## Key Implementation Details

### Why TeeStderr?
Joblib's `Parallel` with `verbose=10` writes progress to stderr, not stdout. Python's logging goes to stdout (and your log file), but stderr bypasses both. TeeStderr intercepts stderr and writes it to both the terminal AND your log file.

### Why Parse the Log File?
The progress.json is only written after each chunk completes. For 500-item chunks at 1 item/sec, that's ~8 minutes between updates. Parsing joblib's verbose output gives you progress within seconds.

### Why Use rate_per_sec from progress.json?
If you restart a task, the "time from script start" calculation includes dead time when the process wasn't running. The rate stored in progress.json is calculated from actual processing time and remains accurate across restarts.

### Regex Patterns Used

1. **Start time**: `Started:\s+(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})`
2. **Total items**: `Processing all (\d+[\d,]*) (edges|items)`
3. **Chunk info**: `Chunk (\d+)/(\d+):.*?(\d+) - (\d+)`
4. **Joblib progress**: `Done\s+(\d+)\s+tasks.*elapsed:\s+([\d.]+)\s*(\w+)`

## Zombie Process Prevention

Always kill joblib workers when stopping a task:

```bash
# Kill main process
pkill -9 -f "step_name"

# CRITICAL: Kill joblib workers (they survive when main process dies!)
pkill -9 -f "loky.backend.popen_loky_posix"
pkill -9 -f "resource_tracker"

# Verify clean
ps aux | grep python | grep -E "(loky|step)" | grep -v grep | wc -l  # Should be 0
```

## Resuming from Checkpoint

If your script supports `--resume`:

```bash
# Find latest checkpoint
ls -la outputs/checkpoints/

# Resume from checkpoint
python step.py --resume checkpoints/checkpoint_5000.pkl
```

## Files Reference

- `scripts/A4/monitor.sh` - Example monitor script with all features
- `scripts/A4/step3_effect_estimation_lasso.py` - Example Python script with TeeStderr
- `CLAUDE.md` - Contains the template in "INTRA-CHUNK PROGRESS MONITORING" section
