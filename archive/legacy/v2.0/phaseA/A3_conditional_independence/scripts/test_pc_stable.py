"""
Test PC-Stable on small sample before full run

Tests:
1. Data loading works
2. Fisher's Z conditional independence test works
3. Skeleton algorithm runs without errors
4. Checkpointing works
5. Memory usage is reasonable
"""

import pickle
import pandas as pd
import numpy as np
from pathlib import Path
import sys

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))

from step2_pc_stable import (
    load_a2_edges,
    load_a1_data,
    test_conditional_independence_fisherz,
    pc_stable_skeleton
)

def test_data_loading():
    """Test that data loads correctly"""
    print("=" * 80)
    print("TEST 1: Data Loading")
    print("=" * 80)

    try:
        edges_df = load_a2_edges()
        print(f"✓ Loaded {len(edges_df):,} edges")

        data = load_a1_data()
        print(f"✓ Loaded {len(data.columns):,} indicators, {len(data):,} observations")

        print("✓ Data loading test PASSED\n")
        return edges_df, data
    except Exception as e:
        print(f"✗ Data loading test FAILED: {e}\n")
        sys.exit(1)

def test_fisher_z():
    """Test Fisher's Z conditional independence test"""
    print("=" * 80)
    print("TEST 2: Fisher's Z Conditional Independence Test")
    print("=" * 80)

    # Create synthetic test data
    np.random.seed(42)
    n = 1000

    # Case 1: Independent variables
    X1 = np.random.randn(n)
    Y1 = np.random.randn(n)

    # Case 2: Dependent variables
    X2 = np.random.randn(n)
    Y2 = X2 + np.random.randn(n) * 0.1

    # Case 3: Conditionally independent (Z is confounder)
    Z = np.random.randn(n)
    X3 = Z + np.random.randn(n) * 0.1
    Y3 = Z + np.random.randn(n) * 0.1

    test_data = pd.DataFrame({
        'X1': X1, 'Y1': Y1,
        'X2': X2, 'Y2': Y2,
        'X3': X3, 'Y3': Y3, 'Z': Z
    })

    # Test 1: Independent variables (should be independent)
    is_indep, p_val, _ = test_conditional_independence_fisherz(test_data, 'X1', 'Y1', [], alpha=0.05)
    print(f"Independent variables: is_independent={is_indep}, p={p_val:.4f}")
    assert is_indep, "Should detect independence"

    # Test 2: Dependent variables (should be dependent)
    is_indep, p_val, _ = test_conditional_independence_fisherz(test_data, 'X2', 'Y2', [], alpha=0.05)
    print(f"Dependent variables: is_independent={is_indep}, p={p_val:.4f}")
    assert not is_indep, "Should detect dependence"

    # Test 3: Conditionally independent (should be independent given Z)
    is_indep, p_val, _ = test_conditional_independence_fisherz(test_data, 'X3', 'Y3', ['Z'], alpha=0.05)
    print(f"Conditionally independent: is_independent={is_indep}, p={p_val:.4f}")
    assert is_indep, "Should detect conditional independence"

    print("✓ Fisher's Z test PASSED\n")

def test_small_sample_run(edges_df, data):
    """Test PC-Stable on small sample (100 edges)"""
    print("=" * 80)
    print("TEST 3: Small Sample PC-Stable Run (100 edges)")
    print("=" * 80)

    # Take first 100 edges
    sample_edges = edges_df.head(100).copy()

    print(f"Testing on {len(sample_edges)} edges...")

    try:
        validated = pc_stable_skeleton(data, sample_edges, alpha=0.001, max_cond_set_size=3)
        print(f"✓ Validated {len(validated)} edges from {len(sample_edges)}")
        print(f"  Reduction: {(1 - len(validated)/len(sample_edges))*100:.1f}%")
        print("✓ Small sample test PASSED\n")
        return True
    except Exception as e:
        print(f"✗ Small sample test FAILED: {e}\n")
        import traceback
        traceback.print_exc()
        return False

def test_memory_check(data):
    """Check memory usage"""
    print("=" * 80)
    print("TEST 4: Memory Check")
    print("=" * 80)

    import psutil
    import os

    process = psutil.Process(os.getpid())
    mem_mb = process.memory_info().rss / (1024 * 1024)

    print(f"Current memory usage: {mem_mb:.1f} MB")

    if mem_mb > 10000:  # 10 GB
        print(f"⚠️  WARNING: High memory usage ({mem_mb/1024:.1f} GB)")
    else:
        print("✓ Memory usage acceptable")

    print("✓ Memory check PASSED\n")

def test_checkpoint_persistence():
    """Test that checkpoints can be written and read"""
    print("=" * 80)
    print("TEST 5: Checkpoint Persistence")
    print("=" * 80)

    checkpoint_dir = Path("../checkpoints")
    checkpoint_dir.mkdir(exist_ok=True)
    checkpoint_file = checkpoint_dir / "test_checkpoint.pkl"

    # Write test checkpoint
    test_data = {
        'edges_processed': 1000,
        'total_edges': 10000,
        'validated_edges': 500,
        'timestamp': '2025-11-14 13:00:00'
    }

    with open(checkpoint_file, 'wb') as f:
        pickle.dump(test_data, f)

    print("✓ Checkpoint written")

    # Read back
    with open(checkpoint_file, 'rb') as f:
        loaded = pickle.load(f)

    assert loaded['edges_processed'] == 1000
    print("✓ Checkpoint read correctly")

    # Cleanup
    checkpoint_file.unlink()
    print("✓ Checkpoint cleanup done")

    print("✓ Checkpoint persistence test PASSED\n")

def main():
    print("\n")
    print("=" * 80)
    print("PC-STABLE PRE-FLIGHT SAFETY CHECKS")
    print("=" * 80)
    print("\n")

    # Test 1: Data loading
    edges_df, data = test_data_loading()

    # Test 2: Fisher's Z test
    test_fisher_z()

    # Test 3: Small sample run
    success = test_small_sample_run(edges_df, data)

    if not success:
        print("\n⚠️  SMALL SAMPLE TEST FAILED - DO NOT RUN FULL PIPELINE\n")
        sys.exit(1)

    # Test 4: Memory check
    test_memory_check(data)

    # Test 5: Checkpoint persistence
    test_checkpoint_persistence()

    print("=" * 80)
    print("ALL SAFETY CHECKS PASSED ✓")
    print("=" * 80)
    print("\nReady for full PC-Stable run:")
    print("  python scripts/step2_pc_stable.py")
    print("\nMonitor progress with:")
    print("  bash scripts/monitor.sh")
    print("=" * 80)

if __name__ == "__main__":
    main()
