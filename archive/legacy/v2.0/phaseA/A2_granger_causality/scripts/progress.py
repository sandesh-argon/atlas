#!/usr/bin/env python3
"""Quick progress check for Granger causality testing"""

import pickle
from datetime import datetime, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent

# Read checkpoint
checkpoint_file = BASE_DIR / "checkpoints" / "granger_progress.pkl"
log_file = BASE_DIR / "logs" / "step3_granger.log"

if not checkpoint_file.exists():
    print("No checkpoint file found yet. Process may still be initializing.")
    exit(0)

with open(checkpoint_file, 'rb') as f:
    cp = pickle.load(f)

# Get start time from log
start_time_str = None
with open(log_file, 'r') as f:
    for line in f:
        if 'Started:' in line:
            start_time_str = line.split('Started: ')[1].strip()
            break

if not start_time_str:
    print("Could not find start time in log")
    exit(1)

start_time = datetime.strptime(start_time_str, '%Y-%m-%d %H:%M:%S')
now = datetime.now()
elapsed = (now - start_time).total_seconds()

completed = cp['last_index']
total_pairs = 15889478
success_count = len(cp['results'])

# Calculate estimates
pairs_per_sec = completed / elapsed
pairs_per_hour = pairs_per_sec * 3600
remaining_pairs = total_pairs - completed
est_remaining_sec = remaining_pairs / pairs_per_sec
est_remaining_hours = est_remaining_sec / 3600
completion_time = now + timedelta(seconds=est_remaining_sec)

# Progress bar
percent = completed / total_pairs * 100
bar_width = 40
filled = int(bar_width * completed / total_pairs)
bar = '█' * filled + '░' * (bar_width - filled)

print(f"\n{'='*60}")
print(f"GRANGER CAUSALITY PROGRESS")
print(f"{'='*60}")
print(f"Pairs tested:     {completed:,} / {total_pairs:,} ({percent:.2f}%)")
print(f"[{bar}] {percent:.2f}%")
print(f"")
print(f"Successful tests: {success_count:,} ({success_count/completed*100:.1f}% success rate)")
print(f"Processing rate:  {pairs_per_hour:,.0f} pairs/hour")
print(f"")
print(f"Elapsed:          {elapsed/3600:.2f} hours")
print(f"Remaining:        {est_remaining_hours:.2f} hours (~{est_remaining_sec/60:.0f} minutes)")
print(f"Est. completion:  {completion_time.strftime('%Y-%m-%d %H:%M:%S')}")
print(f"{'='*60}\n")
