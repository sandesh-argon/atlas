#!/bin/bash
# A4 Effect Estimation Monitor - Usage: ./monitor.sh (or: watch -n 10 ./monitor.sh)

PROGRESS_FILE="<repo-root>/v2.0/v2.1/outputs/A4/progress.json"
LOG_FILE="<repo-root>/v2.0/v2.1/logs/step3_effect_estimation.log"

echo "=========================================="
echo "A4 EFFECT ESTIMATION MONITOR"
echo "=========================================="

# First check progress.json (chunk-level progress) - this has the ACCURATE rate
if [ -f "$PROGRESS_FILE" ]; then
    echo "--- Chunk Progress (from progress.json) ---"
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
print(f'Rate: {rate:.2f} edges/sec')
print(f'ETA: {eta_min:.1f} min ({eta_min/60:.1f} hrs)')

# Calculate completion time
if eta_min > 0:
    completion_time = datetime.now() + timedelta(minutes=eta_min)
    print(f'Est. Done At: {completion_time.strftime(\"%Y-%m-%d %H:%M:%S\")}')

print(f'Updated: {updated}')
"
    echo ""
fi

# Parse joblib verbose output for INTRA-CHUNK progress (real-time within current chunk)
if [ -f "$LOG_FILE" ]; then
    echo "--- Live Intra-Chunk Progress ---"
    python3 -c "
import re
import sys
import json
from datetime import datetime, timedelta

log_file = '$LOG_FILE'
progress_file = '$PROGRESS_FILE'

# Load rate from progress.json if available (more accurate)
saved_rate = None
saved_items_done = 0
try:
    with open(progress_file, 'r') as f:
        pdata = json.load(f)
        saved_rate = pdata.get('rate_per_sec', None)
        saved_items_done = pdata.get('items_done', 0)
except:
    pass

# Find current chunk info from log
chunk_info = None
chunk_size = 500  # default
tasks_done = 0
elapsed_str = 'N/A'
elapsed_seconds = 0
total_edges = 58837  # default
start_time = None

with open(log_file, 'r') as f:
    lines = f.readlines()

# Parse log
for line in lines:
    if 'Processing all' in line:
        match = re.search(r'Processing all (\d+[\d,]*) edges', line)
        if match:
            total_edges = int(match.group(1).replace(',', ''))

    # Get LATEST start time (in case of restarts)
    if 'Started:' in line:
        try:
            ts_match = re.search(r'Started:\s+(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
            if ts_match:
                start_time = datetime.strptime(ts_match.group(1), '%Y-%m-%d %H:%M:%S')
        except:
            pass

    # Get chunk info
    if 'Chunk' in line and 'Edges' in line:
        match = re.search(r'Chunk (\d+)/(\d+): Edges (\d+) - (\d+)', line)
        if match:
            chunk_num = int(match.group(1))
            total_chunks = int(match.group(2))
            chunk_start = int(match.group(3))
            chunk_end = int(match.group(4))
            chunk_size = chunk_end - chunk_start
            chunk_info = (chunk_num, total_chunks, chunk_start, chunk_end)

# Get latest joblib progress
for line in reversed(lines[-50:]):
    match = re.search(r'Done\s+(\d+)\s+tasks.*elapsed:\s+([\d.]+)\s*(\w+)', line)
    if match:
        tasks_done = int(match.group(1))
        elapsed_val = float(match.group(2))
        elapsed_unit = match.group(3)
        elapsed_str = f'{elapsed_val}{elapsed_unit}'
        if 'min' in elapsed_unit:
            elapsed_seconds = elapsed_val * 60
        elif 's' in elapsed_unit:
            elapsed_seconds = elapsed_val
        elif 'h' in elapsed_unit:
            elapsed_seconds = elapsed_val * 3600
        break

if chunk_info:
    chunk_num, total_chunks, chunk_start, chunk_end = chunk_info
    total_done = chunk_start + tasks_done
    pct = 100.0 * total_done / total_edges
    pct_chunk = 100.0 * tasks_done / chunk_size if chunk_size > 0 else 0

    print(f'Current Chunk: {chunk_num}/{total_chunks}')
    print(f'Chunk Progress: {tasks_done}/{chunk_size} ({pct_chunk:.1f}%)')
    print(f'Overall Progress: {total_done:,}/{total_edges:,} ({pct:.1f}%)')

    # Use saved rate from progress.json if available (more accurate than calculating from start time)
    if saved_rate and saved_rate > 0:
        remaining = total_edges - total_done
        eta_sec = remaining / saved_rate
        print(f'Rate: {saved_rate:.2f} edges/sec (from last checkpoint)')
        print(f'ETA: {eta_sec/60:.1f} min ({eta_sec/3600:.1f} hrs)')
        completion = datetime.now() + timedelta(seconds=eta_sec)
        print(f'Est. Done At: {completion.strftime(\"%Y-%m-%d %H:%M:%S\")}')
    elif start_time and total_done > 0:
        # Calculate from current session start
        session_elapsed = (datetime.now() - start_time).total_seconds()
        # Only count progress made in this session
        session_done = total_done - saved_items_done if saved_items_done > 0 else total_done
        if session_done > 0 and session_elapsed > 0:
            rate = session_done / session_elapsed
            remaining = total_edges - total_done
            eta_sec = remaining / rate if rate > 0 else 0
            print(f'Session Elapsed: {session_elapsed/60:.1f} min')
            print(f'Rate: {rate:.2f} edges/sec')
            print(f'ETA: {eta_sec/60:.1f} min ({eta_sec/3600:.1f} hrs)')
        else:
            print(f'Elapsed (chunk): {elapsed_str}')
            print('ETA: Calculating...')
    else:
        print(f'Elapsed (chunk): {elapsed_str}')
        print('ETA: Calculating...')
else:
    print('Waiting for first chunk to start...')
    for line in reversed(lines[-20:]):
        if 'Done' in line and 'tasks' in line:
            print(f'Latest: {line.strip()}')
            break
"
fi

echo ""
echo "--- Recent Log Entries ---"
if [ -f "$LOG_FILE" ]; then
    tail -3 "$LOG_FILE"
fi

echo ""
echo "--- System Status ---"
echo "CPU Temps:"
sensors 2>/dev/null | grep -E "Tctl|Tccd" | head -3

echo ""
echo "Memory:"
free -h | head -2
