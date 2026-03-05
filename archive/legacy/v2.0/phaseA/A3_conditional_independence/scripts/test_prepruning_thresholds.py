#!/usr/bin/env python3
"""
Critical Validation: Test different pre-pruning thresholds
to ensure we didn't discard valid causal edges
"""

import pickle
import pandas as pd
import numpy as np
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_thresholds():
    logger.info("="*80)
    logger.info("CRITICAL VALIDATION: PRE-PRUNING THRESHOLD TEST")
    logger.info("="*80)

    # Load A2 Granger edges
    a2_file = Path(__file__).parent.parent.parent / 'A2_granger_causality' / 'outputs' / 'granger_fdr_corrected.pkl'
    logger.info(f"\nLoading A2 Granger edges from: {a2_file}")

    with open(a2_file, 'rb') as f:
        a2_data = pickle.load(f)

    a2_edges = a2_data['results']
    logger.info(f"  Total A2 edges (all): {len(a2_edges):,}")

    # Filter to q<0.01 (V2 spec input)
    base_edges = a2_edges[a2_edges['significant_fdr_001']].copy()
    logger.info(f"  Base edges (q<0.01): {len(base_edges):,}")

    # Test different thresholds
    thresholds = [
        {'name': 'V1 (Ultra-strict)', 'q': 1e-06, 'F': 40},
        {'name': 'V2 (Current)', 'q': 1e-04, 'F': 20},
        {'name': 'Moderate', 'q': 1e-03, 'F': 15},
        {'name': 'Lenient', 'q': 1e-02, 'F': 10},
    ]

    logger.info("\n" + "="*80)
    logger.info("THRESHOLD COMPARISON")
    logger.info("="*80)

    results = []

    for thresh in thresholds:
        filtered = base_edges[
            (base_edges['p_value_fdr'] < thresh['q']) &
            (base_edges['f_statistic'] > thresh['F'])
        ]

        # Calculate PC-Stable runtime estimate
        # Based on V2 actual: 280K edges in 1.84 hours
        est_hours = len(filtered) / 279975 * 1.84

        results.append({
            'name': thresh['name'],
            'q_threshold': thresh['q'],
            'f_threshold': thresh['F'],
            'edges': len(filtered),
            'reduction_pct': (1 - len(filtered)/len(base_edges)) * 100,
            'est_pc_runtime_hours': est_hours
        })

        logger.info(f"\n{thresh['name']}:")
        logger.info(f"  Thresholds: q < {thresh['q']}, F > {thresh['F']}")
        logger.info(f"  Edges: {len(filtered):,}")
        logger.info(f"  Reduction: {(1-len(filtered)/len(base_edges))*100:.1f}%")
        logger.info(f"  Est. PC-Stable runtime: {est_hours:.1f} hours")

        # Check F-statistic distribution
        logger.info(f"  F-stat median: {filtered['f_statistic'].median():.2f}")
        logger.info(f"  F-stat 25th percentile: {filtered['f_statistic'].quantile(0.25):.2f}")

    # Create comparison table
    logger.info("\n" + "="*80)
    logger.info("SUMMARY TABLE")
    logger.info("="*80)

    df = pd.DataFrame(results)
    logger.info(f"\n{df.to_string(index=False)}")

    # Recommendation
    logger.info("\n" + "="*80)
    logger.info("RECOMMENDATION")
    logger.info("="*80)

    v1_edges = results[0]['edges']
    v2_edges = results[1]['edges']
    moderate_edges = results[2]['edges']

    v2_runtime = results[1]['est_pc_runtime_hours']
    moderate_runtime = results[2]['est_pc_runtime_hours']

    logger.info(f"\nCurrent (V2): {v2_edges:,} edges, {v2_runtime:.1f} hour runtime")
    logger.info(f"Moderate:     {moderate_edges:,} edges, {moderate_runtime:.1f} hour runtime")

    if moderate_edges < v2_edges * 1.5:
        logger.info("\n✅ CONCLUSION: V2 threshold is appropriate")
        logger.info(f"   Moderate threshold only adds {moderate_edges - v2_edges:,} edges")
        logger.info(f"   Runtime increase: {moderate_runtime - v2_runtime:.1f} hours")
        logger.info(f"   Marginal benefit doesn't justify re-run")
    elif moderate_runtime < 3.0:
        logger.info("\n⚠️  RECOMMENDATION: Consider moderate threshold")
        logger.info(f"   Adds {moderate_edges - v2_edges:,} edges ({(moderate_edges/v2_edges - 1)*100:.0f}% more)")
        logger.info(f"   Runtime increase: {moderate_runtime - v2_runtime:.1f} hours (manageable)")
        logger.info(f"   Could capture additional valid causal edges")
    else:
        logger.info("\n✅ CONCLUSION: V2 threshold is optimal")
        logger.info(f"   Moderate threshold adds {moderate_runtime - v2_runtime:.1f} hours")
        logger.info(f"   Runtime cost ({moderate_runtime:.1f}h) too high for marginal benefit")

    # Save results
    output_file = Path(__file__).parent.parent / 'diagnostics' / 'prepruning_threshold_test.pkl'
    output_file.parent.mkdir(exist_ok=True)

    with open(output_file, 'wb') as f:
        pickle.dump({
            'results': df,
            'recommendation': 'v2_optimal' if moderate_edges < v2_edges * 1.5 or moderate_runtime >= 3.0 else 'consider_moderate'
        }, f)

    logger.info(f"\n✅ Saved: {output_file}")
    logger.info("="*80 + "\n")

if __name__ == '__main__':
    test_thresholds()
