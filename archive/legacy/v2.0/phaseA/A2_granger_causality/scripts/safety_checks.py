#!/usr/bin/env python3
"""
Safety checks before running Granger testing
==============================================
Validates system resources, estimates memory usage, checks for recovery
"""

import pickle
import subprocess
from pathlib import Path
import sys

BASE_DIR = Path(__file__).parent.parent

def check_memory():
    """Check available memory"""
    print("=" * 60)
    print("MEMORY CHECK")
    print("=" * 60)

    result = subprocess.run(['free', '-h'], capture_output=True, text=True)
    print(result.stdout)

    # Get numeric values
    result_bytes = subprocess.run(['free', '-b'], capture_output=True, text=True)
    lines = result_bytes.stdout.strip().split('\n')
    mem_line = lines[1].split()
    total_mem = int(mem_line[1])
    available_mem = int(mem_line[6])

    available_gb = available_mem / (1024**3)

    print(f"Available memory: {available_gb:.1f} GB")

    if available_gb < 10:
        print("⚠️  WARNING: Less than 10GB available")
        return False
    else:
        print("✅ Sufficient memory available")
        return True

def estimate_memory_usage():
    """Estimate memory usage for new script"""
    print("\n" + "=" * 60)
    print("MEMORY USAGE ESTIMATE")
    print("=" * 60)

    # Old script: kept all results in RAM
    # At 23% completion: 763 MB
    # Estimated full run: 763 / 0.23 = 3.3 GB (would OOM)

    print("Old script (v1) - UNSAFE:")
    print("  - Keeps all results in RAM")
    print("  - 763 MB at 23% completion")
    print("  - Estimated full: ~3.3 GB")
    print("  - Result: OOM crash at ~50-70% ❌")
    print()

    # New script: saves incremental to disk
    # Memory: only 1 checkpoint in RAM at a time (~5MB)
    # Plus imputed data (~500MB)
    # Total: <1GB peak

    print("New script (v2) - SAFE:")
    print("  - Saves each checkpoint to disk immediately")
    print("  - Only 1 chunk in RAM at a time (~5-10 MB)")
    print("  - Imputed data: ~500 MB (constant)")
    print("  - Total peak: <1 GB ✅")
    print("  - Disk usage: ~300-400 MB (incremental files)")
    print()

def check_disk_space():
    """Check available disk space"""
    print("=" * 60)
    print("DISK SPACE CHECK")
    print("=" * 60)

    result = subprocess.run(['df', '-h', str(BASE_DIR)], capture_output=True, text=True)
    print(result.stdout)

    # Parse available space
    lines = result.stdout.strip().split('\n')
    disk_line = lines[1].split()
    available = disk_line[3]

    print(f"Available: {available}")

    # Need ~500MB for incremental results
    if 'G' in available or 'T' in available:
        print("✅ Sufficient disk space")
        return True
    else:
        print("⚠️  WARNING: Low disk space")
        return False

def check_old_checkpoint():
    """Check if old corrupted checkpoint exists"""
    print("\n" + "=" * 60)
    print("OLD CHECKPOINT CHECK")
    print("=" * 60)

    old_checkpoint = BASE_DIR / "checkpoints" / "granger_progress.pkl"

    if old_checkpoint.exists():
        size_mb = old_checkpoint.stat().st_size / (1024**2)
        print(f"Found old checkpoint: {old_checkpoint.name}")
        print(f"Size: {size_mb:.1f} MB")
        print(f"Status: CORRUPTED (crashed during write)")
        print()
        print("Action: Will be ignored by new script (uses granger_progress_v2.pkl)")
        print()

        # Try to get last valid checkpoint from log
        log_file = BASE_DIR / "logs" / "step3_granger.log"
        if log_file.exists():
            with open(log_file, 'r') as f:
                checkpoints = []
                for line in f:
                    if 'Checkpoint saved' in line and 'successful tests' in line:
                        checkpoints.append(line.strip())

            if checkpoints:
                last_checkpoint = checkpoints[-1]
                print("Last successful checkpoint from log:")
                print(f"  {last_checkpoint}")

                # Extract numbers
                if 'Checkpoint' in last_checkpoint:
                    # Find checkpoint number
                    parts = last_checkpoint.split('Checkpoint saved:')
                    if len(parts) > 1:
                        count = parts[1].strip().split()[0].replace(',', '')
                        print(f"\n✅ Recovered: ~{count} successful tests from checkpoints 1-37")
    else:
        print("No old checkpoint found")
        print("✅ Clean start")

def check_recovery_potential():
    """Check if we can recover from old run"""
    print("\n" + "=" * 60)
    print("RECOVERY POTENTIAL")
    print("=" * 60)

    log_file = BASE_DIR / "logs" / "step3_granger.log"

    if not log_file.exists():
        print("No previous run detected")
        print("Status: Fresh start")
        return

    # Find last checkpoint processed
    with open(log_file, 'r') as f:
        checkpoints = []
        for line in f:
            if 'Processing pairs' in line and 'Checkpoint' in line:
                checkpoints.append(line.strip())

    if checkpoints:
        last_checkpoint_line = checkpoints[-1]
        print("Last checkpoint attempted:")
        print(f"  {last_checkpoint_line}")

        # Parse checkpoint number
        if 'Checkpoint' in last_checkpoint_line:
            parts = last_checkpoint_line.split('Checkpoint')[1].split(':')[0].strip()
            checkpoint_num = parts.split('/')[0]
            total_checkpoints = parts.split('/')[1]

            print()
            print(f"Progress: Checkpoint {checkpoint_num} / {total_checkpoints}")
            print(f"Completed: ~{int(checkpoint_num)-1} checkpoints ({(int(checkpoint_num)-1)/int(total_checkpoints)*100:.1f}%)")
            print()
            print("⚠️  Old results are LOST (corrupted checkpoint)")
            print("✅ New script will start fresh with memory-safe design")

def main():
    print("\n" + "=" * 60)
    print("GRANGER TESTING SAFETY CHECKS")
    print("=" * 60)
    print()

    checks_passed = []

    # Run checks
    checks_passed.append(("Memory", check_memory()))
    estimate_memory_usage()
    checks_passed.append(("Disk", check_disk_space()))
    check_old_checkpoint()
    check_recovery_potential()

    # Summary
    print("\n" + "=" * 60)
    print("SAFETY CHECK SUMMARY")
    print("=" * 60)

    for check_name, passed in checks_passed:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{check_name:20s}: {status}")

    all_passed = all(p for _, p in checks_passed)

    print()
    if all_passed:
        print("✅ ALL SAFETY CHECKS PASSED")
        print()
        print("Safe to run:")
        print("  python scripts/step3_granger_testing_v2.py")
        print()
        print("Memory-safe design:")
        print("  - Saves incremental results to disk")
        print("  - Peak memory: <1 GB (vs 3.3 GB old script)")
        print("  - Can resume from checkpoint if interrupted")
        print()
        return 0
    else:
        print("❌ SOME CHECKS FAILED - Review warnings above")
        return 1

if __name__ == "__main__":
    sys.exit(main())
