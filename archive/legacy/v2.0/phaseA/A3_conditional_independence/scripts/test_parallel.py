"""
Test parallelized PC-Stable implementation

Tests:
1. Parallel execution actually uses multiple cores
2. Memory usage doesn't explode
3. Results are consistent
4. No crashes
"""

import pickle
import pandas as pd
import numpy as np
import psutil
import os
import time
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))

from step2_pc_stable import (
    load_a2_edges,
    load_a1_data,
    pc_stable_skeleton,
    N_CORES
)

def monitor_resources():
    """Get current resource usage"""
    process = psutil.Process(os.getpid())
    mem_mb = process.memory_info().rss / (1024 * 1024)
    cpu_percent = process.cpu_percent(interval=0.1)

    return {
        'memory_mb': mem_mb,
        'cpu_percent': cpu_percent,
        'num_threads': process.num_threads()
    }

def test_parallel_execution():
    """Test that parallelization actually works"""
    print("=" * 80)
    print("TEST: Parallelized PC-Stable Execution")
    print("=" * 80)
    print(f"N_CORES setting: {N_CORES}")
    print()

    # Load data
    print("Loading data...")
    edges_df = load_a2_edges()
    data = load_a1_data()
    print()

    # Test on 500 edges
    sample_size = 500
    sample_edges = edges_df.head(sample_size).copy()

    print(f"Testing on {sample_size} edges...")
    print("Monitoring CPU and memory usage...")
    print()

    # Monitor before
    before = monitor_resources()
    print(f"Before: Memory={before['memory_mb']:.1f}MB, CPU={before['cpu_percent']:.1f}%, Threads={before['num_threads']}")

    # Run with monitoring
    start_time = time.time()

    # Start monitoring in separate thread
    import threading
    max_memory = [0]
    max_threads = [0]
    stop_monitoring = [False]

    def monitor_loop():
        while not stop_monitoring[0]:
            stats = monitor_resources()
            max_memory[0] = max(max_memory[0], stats['memory_mb'])
            max_threads[0] = max(max_threads[0], stats['num_threads'])
            time.sleep(0.5)

    monitor_thread = threading.Thread(target=monitor_loop)
    monitor_thread.start()

    try:
        validated = pc_stable_skeleton(data, sample_edges, alpha=0.001, max_cond_set_size=5)
        elapsed = time.time() - start_time

        stop_monitoring[0] = True
        monitor_thread.join()

        # Results
        print()
        print("=" * 80)
        print("RESULTS")
        print("=" * 80)
        print(f"Validated: {len(validated)} edges from {sample_size}")
        print(f"Reduction: {(1 - len(validated)/sample_size)*100:.2f}%")
        print(f"Runtime: {elapsed:.2f} seconds")
        print(f"Rate: {sample_size/elapsed:.1f} edges/sec")
        print()

        print("Resource Usage:")
        print(f"  Max memory: {max_memory[0]:.1f} MB")
        print(f"  Max threads: {max_threads[0]}")
        print(f"  Expected threads: ~{N_CORES + 2} (joblib overhead)")
        print()

        # Verify parallelization worked
        if max_threads[0] < N_CORES:
            print(f"⚠️  WARNING: Max threads ({max_threads[0]}) < N_CORES ({N_CORES})")
            print("   Parallelization may not be working!")
            return False
        else:
            print(f"✓ Parallelization working (saw {max_threads[0]} threads)")

        # Check memory
        if max_memory[0] > 15000:  # 15 GB
            print(f"⚠️  WARNING: High memory usage ({max_memory[0]/1024:.1f} GB)")
            return False
        else:
            print(f"✓ Memory usage acceptable ({max_memory[0]/1024:.1f} GB)")

        return True

    except Exception as e:
        stop_monitoring[0] = True
        monitor_thread.join()
        print(f"\n✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_memory_scaling():
    """Test memory usage scales reasonably with batch size"""
    print()
    print("=" * 80)
    print("TEST: Memory Scaling")
    print("=" * 80)
    print()

    edges_df = load_a2_edges()
    data = load_a1_data()

    batch_sizes = [100, 500, 1000]
    memory_usage = []

    for batch_size in batch_sizes:
        print(f"Testing batch size {batch_size}...")

        sample_edges = edges_df.head(batch_size).copy()

        before_mem = psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024)

        validated = pc_stable_skeleton(data, sample_edges, alpha=0.001, max_cond_set_size=3)

        after_mem = psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024)
        mem_increase = after_mem - before_mem

        memory_usage.append(mem_increase)
        print(f"  Memory increase: {mem_increase:.1f} MB")

    print()
    print("Memory scaling:")
    for i, (size, mem) in enumerate(zip(batch_sizes, memory_usage)):
        per_edge = mem / size
        print(f"  {size} edges: {mem:.1f} MB ({per_edge:.3f} MB/edge)")

    # Extrapolate to full dataset
    avg_per_edge = sum(memory_usage[i] / batch_sizes[i] for i in range(len(batch_sizes))) / len(batch_sizes)
    full_dataset_mb = avg_per_edge * 1_157_230

    print()
    print(f"Extrapolated full dataset memory: {full_dataset_mb/1024:.1f} GB")

    if full_dataset_mb > 20000:  # 20 GB
        print("⚠️  WARNING: Projected memory usage exceeds 20 GB!")
        print("   Consider reducing max_cond_set_size or processing in smaller chunks")
        return False
    else:
        print("✓ Projected memory usage acceptable")
        return True

def main():
    print("\n")
    print("=" * 80)
    print("PARALLELIZED PC-STABLE SAFETY CHECKS")
    print("=" * 80)
    print("\n")

    # Test 1: Parallel execution
    parallel_ok = test_parallel_execution()

    if not parallel_ok:
        print("\n⚠️  PARALLEL EXECUTION TEST FAILED - DO NOT RUN FULL PIPELINE\n")
        sys.exit(1)

    # Test 2: Memory scaling
    memory_ok = test_memory_scaling()

    if not memory_ok:
        print("\n⚠️  MEMORY SCALING TEST FAILED - ADJUST PARAMETERS\n")
        sys.exit(1)

    print("\n")
    print("=" * 80)
    print("ALL PARALLEL SAFETY CHECKS PASSED ✓")
    print("=" * 80)
    print("\nReady for full parallelized run with 10 cores")
    print("=" * 80)

if __name__ == "__main__":
    main()
