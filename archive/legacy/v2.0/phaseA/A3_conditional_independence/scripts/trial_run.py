"""
Trial run of PC-Stable on 1000 edges to estimate runtime

This will help us get a realistic time estimate before launching the full 1.16M edge run.
"""

import pickle
import pandas as pd
import time
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))

from step2_pc_stable import (
    load_a2_edges,
    load_a1_data,
    pc_stable_skeleton
)

def main():
    print("=" * 80)
    print("TRIAL RUN: PC-Stable on 1,000 edges")
    print("=" * 80)
    print()

    # Load data
    print("Loading data...")
    edges_df = load_a2_edges()
    data = load_a1_data()
    print()

    # Sample 1000 edges
    sample_size = 1000
    sample_edges = edges_df.head(sample_size).copy()

    print(f"Trial run on {sample_size:,} edges (from {len(edges_df):,} total)")
    print()

    # Run PC-Stable
    start_time = time.time()

    validated = pc_stable_skeleton(data, sample_edges, alpha=0.001, max_cond_set_size=5)

    elapsed = time.time() - start_time

    # Results
    print()
    print("=" * 80)
    print("TRIAL RUN RESULTS")
    print("=" * 80)
    print(f"Sample size: {sample_size:,} edges")
    print(f"Validated: {len(validated):,} edges")
    print(f"Reduction: {(1 - len(validated)/sample_size)*100:.2f}%")
    print(f"Runtime: {elapsed:.2f} seconds ({elapsed/60:.2f} minutes)")
    print()

    # Extrapolate to full dataset
    total_edges = len(edges_df)
    edges_per_second = sample_size / elapsed

    total_seconds = total_edges / edges_per_second
    total_hours = total_seconds / 3600
    total_days = total_hours / 24

    print("=" * 80)
    print("EXTRAPOLATED FULL RUN ESTIMATES")
    print("=" * 80)
    print(f"Total edges: {total_edges:,}")
    print(f"Processing rate: {edges_per_second:.2f} edges/second")
    print()
    print(f"Estimated total runtime:")
    print(f"  Seconds: {total_seconds:,.0f}")
    print(f"  Minutes: {total_seconds/60:,.0f}")
    print(f"  Hours: {total_hours:,.1f}")
    print(f"  Days: {total_days:.2f}")
    print()

    # Conservative estimate (account for slowdown with larger conditioning sets)
    conservative_days = total_days * 1.5
    print(f"Conservative estimate (1.5× slowdown): {conservative_days:.2f} days")
    print()

    # Checkpointing
    checkpoint_interval = 10000
    checkpoints_total = total_edges // checkpoint_interval
    time_per_checkpoint = checkpoint_interval / edges_per_second / 60  # minutes

    print(f"Checkpointing:")
    print(f"  Total checkpoints: {checkpoints_total}")
    print(f"  Time per checkpoint: {time_per_checkpoint:.1f} minutes")
    print()

    print("=" * 80)
    print("RECOMMENDATION")
    print("=" * 80)

    if total_days < 1:
        print(f"✓ Expected runtime: {total_hours:.1f} hours - FAST")
        print("  Can run in single session")
    elif total_days < 3:
        print(f"✓ Expected runtime: {total_days:.1f} days - REASONABLE")
        print("  Safe to proceed with full run")
    elif total_days < 7:
        print(f"⚠️  Expected runtime: {total_days:.1f} days - LONG")
        print("  Consider increasing sample size for better estimate")
    else:
        print(f"⚠️  Expected runtime: {total_days:.1f} days - VERY LONG")
        print("  May need to optimize algorithm or reduce edge count")

    print("=" * 80)

if __name__ == "__main__":
    main()
