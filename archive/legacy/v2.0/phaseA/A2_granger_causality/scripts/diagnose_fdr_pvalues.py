#!/usr/bin/env python3
"""
FDR Diagnostic: Analyze P-Value Distribution
==============================================
Check if 2.3M edges is reasonable or a red flag
"""

import pickle
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
from pathlib import Path

# Configuration
BASE_DIR = Path(__file__).parent.parent
FDR_RESULTS = BASE_DIR / "outputs" / "granger_fdr_corrected.pkl"
OUTPUT_DIR = BASE_DIR / "outputs"

def load_data():
    """Load FDR-corrected results"""
    print("Loading FDR results...")
    with open(FDR_RESULTS, 'rb') as f:
        data = pickle.load(f)

    results_df = data['results']
    print(f"✅ Loaded {len(results_df):,} test results\n")

    return results_df

def analyze_distribution(results_df):
    """Analyze p-value and q-value distributions"""
    print("=" * 80)
    print("P-VALUE DISTRIBUTION ANALYSIS")
    print("=" * 80)

    raw_p = results_df['p_value'].values
    fdr_q = results_df['p_value_fdr'].values
    f_stats = results_df['f_statistic'].values

    # Basic statistics
    print(f"\nRaw P-values:")
    print(f"  Total tests: {len(raw_p):,}")
    print(f"  p < 0.001:   {(raw_p < 0.001).sum():,} ({(raw_p < 0.001).sum()/len(raw_p)*100:.1f}%)")
    print(f"  p < 0.01:    {(raw_p < 0.01).sum():,} ({(raw_p < 0.01).sum()/len(raw_p)*100:.1f}%)")
    print(f"  p < 0.05:    {(raw_p < 0.05).sum():,} ({(raw_p < 0.05).sum()/len(raw_p)*100:.1f}%)")
    print(f"  p < 0.10:    {(raw_p < 0.10).sum():,} ({(raw_p < 0.10).sum()/len(raw_p)*100:.1f}%)")

    print(f"\nFDR Q-values:")
    print(f"  q < 0.001:   {(fdr_q < 0.001).sum():,} ({(fdr_q < 0.001).sum()/len(fdr_q)*100:.1f}%)")
    print(f"  q < 0.01:    {(fdr_q < 0.01).sum():,} ({(fdr_q < 0.01).sum()/len(fdr_q)*100:.1f}%)")
    print(f"  q < 0.05:    {(fdr_q < 0.05).sum():,} ({(fdr_q < 0.05).sum()/len(fdr_q)*100:.1f}%)")
    print(f"  q < 0.10:    {(fdr_q < 0.10).sum():,} ({(fdr_q < 0.10).sum()/len(fdr_q)*100:.1f}%)")

    # Percentiles
    print(f"\nP-value Percentiles:")
    percentiles = [1, 5, 10, 25, 50, 75, 90, 95, 99]
    for p in percentiles:
        val = np.percentile(raw_p, p)
        print(f"  {p:2d}th: {val:.6f}")

    # F-statistic analysis
    print(f"\nF-Statistic Distribution (for p<0.05 edges):")
    sig_f_stats = f_stats[raw_p < 0.05]
    print(f"  Mean:   {sig_f_stats.mean():.2f}")
    print(f"  Median: {np.median(sig_f_stats):.2f}")
    print(f"  F > 5:  {(sig_f_stats > 5).sum():,} ({(sig_f_stats > 5).sum()/len(sig_f_stats)*100:.1f}%)")
    print(f"  F > 10: {(sig_f_stats > 10).sum():,} ({(sig_f_stats > 10).sum()/len(sig_f_stats)*100:.1f}%)")
    print(f"  F > 20: {(sig_f_stats > 20).sum():,} ({(sig_f_stats > 20).sum()/len(sig_f_stats)*100:.1f}%)")

    return raw_p, fdr_q, f_stats

def plot_distributions(raw_p, fdr_q, f_stats, results_df):
    """Create diagnostic plots"""
    print("\n" + "=" * 80)
    print("GENERATING DIAGNOSTIC PLOTS")
    print("=" * 80)

    fig, axes = plt.subplots(2, 3, figsize=(18, 10))

    # Plot 1: Raw p-value histogram (full range)
    ax = axes[0, 0]
    ax.hist(raw_p, bins=100, edgecolor='black', alpha=0.7)
    ax.axvline(0.05, color='red', linestyle='--', linewidth=2, label='p=0.05')
    ax.set_xlabel('Raw P-value', fontsize=12)
    ax.set_ylabel('Frequency', fontsize=12)
    ax.set_title('Raw P-Value Distribution (Full Range)', fontsize=14, fontweight='bold')
    ax.legend()
    ax.grid(alpha=0.3)

    # Plot 2: Raw p-value histogram (zoomed to p<0.1)
    ax = axes[0, 1]
    ax.hist(raw_p[raw_p < 0.1], bins=100, edgecolor='black', alpha=0.7, color='orange')
    ax.axvline(0.05, color='red', linestyle='--', linewidth=2, label='p=0.05')
    ax.set_xlabel('Raw P-value', fontsize=12)
    ax.set_ylabel('Frequency', fontsize=12)
    ax.set_title('Raw P-Value Distribution (p<0.1 zoom)', fontsize=14, fontweight='bold')
    ax.legend()
    ax.grid(alpha=0.3)

    # Plot 3: FDR q-value histogram
    ax = axes[0, 2]
    ax.hist(fdr_q, bins=100, edgecolor='black', alpha=0.7, color='green')
    ax.axvline(0.05, color='red', linestyle='--', linewidth=2, label='q=0.05')
    ax.axvline(0.01, color='darkred', linestyle='--', linewidth=2, label='q=0.01')
    ax.set_xlabel('FDR Q-value', fontsize=12)
    ax.set_ylabel('Frequency', fontsize=12)
    ax.set_title('FDR Q-Value Distribution', fontsize=14, fontweight='bold')
    ax.legend()
    ax.grid(alpha=0.3)

    # Plot 4: Q-Q plot (expected vs observed p-values)
    ax = axes[1, 0]
    n = len(raw_p)
    expected_p = np.linspace(0, 1, n)
    observed_p = np.sort(raw_p)
    ax.plot(expected_p, observed_p, 'b.', alpha=0.3, markersize=1)
    ax.plot([0, 1], [0, 1], 'r--', linewidth=2, label='Uniform (null)')
    ax.set_xlabel('Expected P-value (uniform)', fontsize=12)
    ax.set_ylabel('Observed P-value', fontsize=12)
    ax.set_title('Q-Q Plot: P-Value Distribution', fontsize=14, fontweight='bold')
    ax.legend()
    ax.grid(alpha=0.3)

    # Plot 5: F-statistic distribution (for significant edges)
    ax = axes[1, 1]
    sig_mask = raw_p < 0.05
    sig_f_stats = f_stats[sig_mask]
    ax.hist(sig_f_stats, bins=100, edgecolor='black', alpha=0.7, color='purple')
    ax.axvline(5, color='red', linestyle='--', linewidth=2, label='F=5')
    ax.axvline(10, color='darkred', linestyle='--', linewidth=2, label='F=10')
    ax.set_xlabel('F-Statistic', fontsize=12)
    ax.set_ylabel('Frequency', fontsize=12)
    ax.set_title('F-Statistic Distribution (p<0.05 edges)', fontsize=14, fontweight='bold')
    ax.set_xlim(0, 50)
    ax.legend()
    ax.grid(alpha=0.3)

    # Plot 6: P-value vs F-statistic scatter
    ax = axes[1, 2]
    # Sample for visibility
    sample_idx = np.random.choice(len(raw_p), size=min(50000, len(raw_p)), replace=False)
    ax.scatter(raw_p[sample_idx], f_stats[sample_idx], alpha=0.1, s=1, color='navy')
    ax.axvline(0.05, color='red', linestyle='--', linewidth=2, alpha=0.7, label='p=0.05')
    ax.axhline(5, color='orange', linestyle='--', linewidth=2, alpha=0.7, label='F=5')
    ax.set_xlabel('P-value', fontsize=12)
    ax.set_ylabel('F-Statistic', fontsize=12)
    ax.set_title('P-value vs F-Statistic (50k sample)', fontsize=14, fontweight='bold')
    ax.set_xlim(0, 0.2)
    ax.set_ylim(0, 50)
    ax.legend()
    ax.grid(alpha=0.3)

    plt.tight_layout()

    output_file = OUTPUT_DIR / "fdr_diagnostic.png"
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print(f"✅ Saved diagnostic plot: {output_file}")

    return output_file

def diagnose_scenario(raw_p, fdr_q, f_stats):
    """Diagnose which scenario we're in"""
    print("\n" + "=" * 80)
    print("SCENARIO DIAGNOSIS")
    print("=" * 80)

    # Check for spike near p=0
    very_sig = (raw_p < 0.001).sum() / len(raw_p)

    # Check for spike near p=0.05
    barely_sig = ((raw_p >= 0.03) & (raw_p < 0.05)).sum()
    moderately_sig = ((raw_p >= 0.01) & (raw_p < 0.03)).sum()
    spike_ratio = barely_sig / max(moderately_sig, 1)

    # Check uniformity in high p-values
    high_p = raw_p[raw_p > 0.5]
    high_p_uniformity = np.std(np.histogram(high_p, bins=10)[0])

    # Check F-statistics
    sig_f_stats = f_stats[raw_p < 0.05]
    weak_f_ratio = (sig_f_stats < 5).sum() / len(sig_f_stats)

    print(f"\nDiagnostic Metrics:")
    print(f"  Very significant (p<0.001): {very_sig*100:.1f}%")
    print(f"  Barely significant spike ratio: {spike_ratio:.2f}")
    print(f"  Weak F-statistics (F<5): {weak_f_ratio*100:.1f}%")
    print(f"  High p-value uniformity: {high_p_uniformity:.1f}")

    print(f"\n" + "=" * 80)
    print("RECOMMENDATION")
    print("=" * 80)

    # Scenario A: Healthy distribution
    if very_sig > 0.10 and spike_ratio < 1.5 and weak_f_ratio < 0.30:
        print(f"\n✅ SCENARIO A: Healthy P-Value Distribution")
        print(f"\nEvidence:")
        print(f"  - Strong spike at p~0 ({very_sig*100:.1f}% very significant)")
        print(f"  - No suspicious spike at p~0.05 (ratio: {spike_ratio:.2f})")
        print(f"  - Strong F-statistics ({(1-weak_f_ratio)*100:.1f}% have F≥5)")
        print(f"\n📋 Recommended Action:")
        print(f"  1. Use stricter FDR: q<0.01 → {(fdr_q < 0.01).sum():,} edges")
        print(f"  2. SKIP bootstrap (too expensive for {(fdr_q < 0.01).sum():,} edges)")
        print(f"  3. Proceed directly to A3 (Conditional Independence)")
        print(f"     - A3 will prune {(fdr_q < 0.01).sum():,} → 30K-80K edges")
        print(f"     - Bootstrap AFTER A3 on final 30K-80K edges")
        return "A"

    # Scenario B: Too many barely significant edges
    elif spike_ratio > 2.0 or weak_f_ratio > 0.50:
        print(f"\n⚠️  SCENARIO B: Too Many Weak Edges")
        print(f"\nEvidence:")
        print(f"  - Suspicious spike at p~0.05 (ratio: {spike_ratio:.2f})")
        print(f"  - Many weak F-statistics ({weak_f_ratio*100:.1f}% have F<5)")
        print(f"\n📋 Recommended Action:")
        print(f"  1. Filter by F-statistic > 5.0")
        print(f"     - Current edges @ q<0.05: {(fdr_q < 0.05).sum():,}")
        print(f"     - After F>5 filter: ~{int((fdr_q < 0.05).sum() * (1-weak_f_ratio)):,} edges")
        print(f"  2. Apply q<0.01 threshold")
        print(f"  3. Bootstrap on filtered set (~300K-500K edges)")
        return "B"

    # Scenario C: Possible non-stationarity
    else:
        print(f"\n⚠️  SCENARIO C: Possible Non-Stationarity")
        print(f"\nEvidence:")
        print(f"  - Moderate spike at p~0 ({very_sig*100:.1f}%)")
        print(f"  - Borderline F-statistics")
        print(f"\n📋 Recommended Action:")
        print(f"  1. Apply differencing to time series")
        print(f"  2. Re-run Granger tests on differenced data")
        print(f"  3. OR proceed to A3 with q<0.01 (A3 handles non-stationarity)")
        return "C"

def main():
    print("=" * 80)
    print("FDR P-VALUE DIAGNOSTIC")
    print("=" * 80)
    print()

    # Load data
    results_df = load_data()

    # Analyze distribution
    raw_p, fdr_q, f_stats = analyze_distribution(results_df)

    # Create plots
    plot_file = plot_distributions(raw_p, fdr_q, f_stats, results_df)

    # Diagnose scenario
    scenario = diagnose_scenario(raw_p, fdr_q, f_stats)

    print("\n" + "=" * 80)
    print("DIAGNOSTIC COMPLETE")
    print("=" * 80)
    print(f"\nScenario: {scenario}")
    print(f"Diagnostic plot: {plot_file}")
    print()

if __name__ == "__main__":
    main()
