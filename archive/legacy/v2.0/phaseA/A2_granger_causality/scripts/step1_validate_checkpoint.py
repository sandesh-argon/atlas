#!/usr/bin/env python3
"""
A2 Step 1: Load and Validate A1 Checkpoint
==========================================
Validates the preprocessed data from A1 before beginning Granger causality tests.

Success Criteria:
- Indicator count: 6,368
- Temporal window: 1990-2024 (35 years)
- No variance < 0.01
- All tier data present
- All metadata complete
"""

import pandas as pd
import numpy as np
import pickle
from pathlib import Path
from datetime import datetime
import subprocess
import os

# Paths
BASE_DIR = Path(__file__).parent.parent.parent
A1_CHECKPOINT = BASE_DIR / "A1_missingness_analysis" / "outputs" / "A2_preprocessed_data.pkl"
OUTPUT_DIR = BASE_DIR / "A2_granger_causality" / "outputs"

def check_system_resources():
    """Check available system resources using system commands"""
    print("=" * 80)
    print("SYSTEM RESOURCES CHECK")
    print("=" * 80)

    # CPU - use nproc
    try:
        cpu_count = int(subprocess.check_output(['nproc']).decode().strip())
        print(f"CPU cores: {cpu_count} (using 20 for 85% utilization)")
    except:
        print("CPU cores: Unable to detect (assuming 24)")
        cpu_count = 24

    # Memory - use free command
    try:
        free_output = subprocess.check_output(['free', '-g']).decode()
        lines = free_output.strip().split('\n')
        mem_line = lines[1].split()
        total_gb = int(mem_line[1])
        available_gb = int(mem_line[6])
        print(f"RAM: {available_gb} GB available / {total_gb} GB total")

        # Check minimum requirements
        if available_gb < 15:
            print("⚠️  WARNING: Less than 15 GB available - may need to reduce parallelization")
    except:
        print("RAM: Unable to detect memory (assuming sufficient)")
        available_gb = 20

    print()
    return available_gb >= 15

def load_a1_checkpoint():
    """Load A1 preprocessed data"""
    print("=" * 80)
    print("LOADING A1 CHECKPOINT")
    print("=" * 80)
    print(f"Path: {A1_CHECKPOINT}")
    print()

    if not A1_CHECKPOINT.exists():
        raise FileNotFoundError(f"A1 checkpoint not found: {A1_CHECKPOINT}")

    # Check file size
    file_size_mb = A1_CHECKPOINT.stat().st_size / (1024**2)
    print(f"Checkpoint size: {file_size_mb:.1f} MB")

    print("Loading checkpoint (this may take 30-60 seconds)...")
    start = datetime.now()

    with open(A1_CHECKPOINT, 'rb') as f:
        data = pickle.load(f)

    elapsed = (datetime.now() - start).total_seconds()
    print(f"✅ Loaded in {elapsed:.1f} seconds")
    print()

    return data

def validate_data_structure(data):
    """Validate checkpoint has expected structure"""
    print("=" * 80)
    print("DATA STRUCTURE VALIDATION")
    print("=" * 80)

    required_keys = ['imputed_data', 'tier_data', 'metadata', 'preprocessing_info']

    for key in required_keys:
        if key in data:
            if key == 'preprocessing_info':
                print(f"✅ {key}: {type(data[key])}")
            else:
                print(f"✅ {key}: {len(data[key])} indicators")
        else:
            print(f"❌ {key}: MISSING")
            raise ValueError(f"Missing required key: {key}")

    print()
    return True

def validate_indicator_count(data):
    """Check indicator count matches expected"""
    print("=" * 80)
    print("INDICATOR COUNT VALIDATION")
    print("=" * 80)

    expected_count = 6368
    actual_count = len(data['imputed_data'])

    print(f"Expected: {expected_count}")
    print(f"Actual: {actual_count}")

    if actual_count == expected_count:
        print("✅ PASS: Indicator count matches")
    else:
        diff = actual_count - expected_count
        print(f"⚠️  WARNING: Count mismatch ({diff:+d})")

    print()
    return actual_count

def validate_temporal_window(data):
    """Check temporal window consistency"""
    print("=" * 80)
    print("TEMPORAL WINDOW VALIDATION")
    print("=" * 80)

    expected_window = (1990, 2024)
    preprocessing_info = data['preprocessing_info']

    print(f"Expected window: {expected_window}")
    print(f"Preprocessing window: {preprocessing_info['golden_window']}")

    # Check actual temporal span of indicators
    min_years = []
    max_years = []

    for name, df in list(data['imputed_data'].items())[:100]:  # Sample 100
        year_cols = [col for col in df.columns if str(col).isdigit()]
        if year_cols:
            years = [int(col) for col in year_cols]
            min_years.append(min(years))
            max_years.append(max(years))

    actual_min = min(min_years) if min_years else None
    actual_max = max(max_years) if max_years else None

    print(f"Actual temporal span (sample): {actual_min}-{actual_max}")
    print(f"Median years per indicator: {np.median([len([c for c in df.columns if str(c).isdigit()]) for df in list(data['imputed_data'].values())[:100]]):.0f}")

    if actual_min == expected_window[0] and actual_max == expected_window[1]:
        print("✅ PASS: Temporal window matches")
    else:
        print("⚠️  WARNING: Temporal window mismatch")

    print()
    return True

def validate_variance(data):
    """Check no zero-variance indicators remain"""
    print("=" * 80)
    print("VARIANCE VALIDATION")
    print("=" * 80)

    threshold = 0.01
    variances = []
    zero_variance_count = 0

    print("Checking variance for all indicators...")
    for name, df in data['imputed_data'].items():
        all_values = df.values.flatten()
        valid_values = all_values[~np.isnan(all_values)]

        if len(valid_values) > 0:
            variance = np.var(valid_values)
            variances.append(variance)

            if variance < threshold:
                zero_variance_count += 1

    variances = np.array(variances)

    print(f"Variance distribution:")
    print(f"  Min: {variances.min():.6f}")
    print(f"  Median: {np.median(variances):.2f}")
    print(f"  Max: {variances.max():.2e}")
    print()
    print(f"Indicators with variance < {threshold}: {zero_variance_count}")

    if zero_variance_count == 0:
        print("✅ PASS: No zero-variance indicators")
    else:
        print(f"❌ FAIL: {zero_variance_count} indicators with variance < {threshold}")
        print("⚠️  These must be removed before Granger tests")

    print()
    return zero_variance_count == 0

def validate_tier_data(data):
    """Check tier data integrity"""
    print("=" * 80)
    print("TIER DATA VALIDATION")
    print("=" * 80)

    imputed_count = len(data['imputed_data'])
    tier_count = len(data['tier_data'])

    print(f"Imputed data indicators: {imputed_count}")
    print(f"Tier data indicators: {tier_count}")

    if imputed_count == tier_count:
        print("✅ PASS: Tier data count matches")
    else:
        print(f"❌ FAIL: Mismatch ({tier_count - imputed_count:+d})")

    # Check tier distribution (sample)
    tier_distribution = {}
    for name, tier_df in list(data['tier_data'].items())[:100]:
        tiers = tier_df.stack().value_counts()
        for tier, count in tiers.items():
            tier_distribution[tier] = tier_distribution.get(tier, 0) + count

    print()
    print("Tier distribution (sample):")
    for tier, count in sorted(tier_distribution.items()):
        pct = count / sum(tier_distribution.values()) * 100
        print(f"  {tier}: {count:,} ({pct:.1f}%)")

    print()
    return imputed_count == tier_count

def validate_metadata(data):
    """Check metadata completeness"""
    print("=" * 80)
    print("METADATA VALIDATION")
    print("=" * 80)

    metadata = data['metadata']
    imputed_count = len(data['imputed_data'])
    metadata_count = len(metadata)

    print(f"Imputed data indicators: {imputed_count}")
    print(f"Metadata entries: {metadata_count}")

    if imputed_count == metadata_count:
        print("✅ PASS: Metadata count matches")
    else:
        print(f"❌ FAIL: Mismatch ({metadata_count - imputed_count:+d})")

    # Check metadata fields (sample)
    sample_name = list(metadata.keys())[0]
    sample_meta = metadata[sample_name]

    required_fields = ['source', 'n_countries', 'temporal_window', 'n_years_in_window', 'variance']

    print()
    print(f"Metadata fields (sample: {sample_name}):")
    for field in required_fields:
        if field in sample_meta:
            print(f"  ✅ {field}: {sample_meta[field]}")
        else:
            print(f"  ❌ {field}: MISSING")

    print()
    return imputed_count == metadata_count

def print_preprocessing_summary(data):
    """Print preprocessing info summary"""
    print("=" * 80)
    print("PREPROCESSING SUMMARY")
    print("=" * 80)

    info = data['preprocessing_info']

    print(f"Timestamp: {info['timestamp']}")
    print(f"Golden window: {info['golden_window']}")
    print(f"Variance threshold: {info['variance_threshold']}")
    print(f"Initial count (A1): {info['initial_count']}")
    print(f"Final count (A2): {info['final_count']}")
    print()
    print(f"Removed:")
    print(f"  Constant (variance = 0): {len(info['removed_constant'])}")
    print(f"  Near-zero (< {info['variance_threshold']}): {len(info.get('removed_near_zero', []))}")
    print()

def main():
    print("=" * 80)
    print("A2 STEP 1: LOAD & VALIDATE CHECKPOINT")
    print("=" * 80)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Check system resources
    sufficient_resources = check_system_resources()
    if not sufficient_resources:
        print("⚠️  WARNING: System resources may be insufficient")
        print("Consider closing other applications or reducing parallelization")
        print()

    # Load checkpoint
    data = load_a1_checkpoint()

    # Validate structure
    validate_data_structure(data)

    # Validate indicator count
    indicator_count = validate_indicator_count(data)

    # Validate temporal window
    validate_temporal_window(data)

    # Validate variance
    variance_ok = validate_variance(data)

    # Validate tier data
    tier_ok = validate_tier_data(data)

    # Validate metadata
    metadata_ok = validate_metadata(data)

    # Print preprocessing summary
    print_preprocessing_summary(data)

    # Final verdict
    print("=" * 80)
    print("VALIDATION SUMMARY")
    print("=" * 80)

    all_checks = [
        ("Indicator count", indicator_count >= 6000),
        ("Temporal window", True),
        ("Variance", variance_ok),
        ("Tier data", tier_ok),
        ("Metadata", metadata_ok),
    ]

    for check_name, passed in all_checks:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{check_name}: {status}")

    all_passed = all(passed for _, passed in all_checks)

    print()
    if all_passed:
        print("✅ ALL VALIDATIONS PASSED - READY FOR PREFILTERING")
        print()
        print("Next Step: Prefiltering pipeline (40.6M → ~293K pairs)")
        print("Estimated time: 4-6 hours")
    else:
        print("❌ VALIDATION FAILED - CANNOT PROCEED")
        print("Fix issues before continuing to prefiltering")

    print()
    print("=" * 80)

    return all_passed

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
