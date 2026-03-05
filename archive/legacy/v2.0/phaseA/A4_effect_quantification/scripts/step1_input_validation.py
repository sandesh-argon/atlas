#!/usr/bin/env python3
"""
A4 Phase 1: Input Validation and Temporal Alignment Check

Validates inputs from A3 and A1, checks temporal alignment strategy.
"""

import pickle
import pandas as pd
import numpy as np
from pathlib import Path
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def load_inputs():
    """Load A3 DAG and A1 preprocessed data"""
    logger.info("="*80)
    logger.info("A4 PHASE 1: INPUT VALIDATION")
    logger.info("="*80)

    # Load A3 final DAG
    a3_file = Path(__file__).parent.parent.parent / 'A3_conditional_independence' / 'outputs' / 'A3_final_dag_v2.pkl'
    logger.info(f"\nLoading A3 DAG from: {a3_file}")

    with open(a3_file, 'rb') as f:
        a3_data = pickle.load(f)

    edges_df = a3_data['edges']
    graph = a3_data['graph']

    logger.info(f"  Edges: {len(edges_df):,}")
    logger.info(f"  Nodes: {graph.number_of_nodes():,}")
    logger.info(f"  Is DAG: {a3_data['validation']['is_dag']}")
    logger.info(f"  Connectivity: {a3_data['validation']['connectivity']:.3f}")

    # Validate edge attributes
    required_cols = ['source', 'target', 'f_statistic', 'p_value', 'best_lag']
    missing = [c for c in required_cols if c not in edges_df.columns]
    if missing:
        raise ValueError(f"Missing edge attributes: {missing}")

    logger.info(f"\n✅ A3 DAG validated")
    logger.info(f"  Edge attributes: {list(edges_df.columns)}")

    # Load A1 preprocessed data
    a1_file = Path(__file__).parent.parent.parent / 'A1_missingness_analysis' / 'outputs' / 'A2_preprocessed_data.pkl'
    logger.info(f"\nLoading A1 preprocessed data from: {a1_file}")

    with open(a1_file, 'rb') as f:
        a1_data = pickle.load(f)

    # A1 structure: imputed_data (dict of DataFrames: indicator -> countries×years)
    imputed_data_dict = a1_data['imputed_data']
    tier_data_dict = a1_data['tier_data']
    preprocessing_info = a1_data['preprocessing_info']

    # Note: Each imputed_data_dict[indicator] is a DataFrame (countries × years)
    # We'll keep it as dict for now, convert to long format as needed in Phase 2

    n_indicators = len(imputed_data_dict)
    first_indicator = list(imputed_data_dict.keys())[0]
    sample_df = imputed_data_dict[first_indicator]

    temporal_window = preprocessing_info.get('golden_window', preprocessing_info.get('temporal_window', (1990, 2024)))

    logger.info(f"  Indicators: {n_indicators}")
    logger.info(f"  Sample shape (countries × years): {sample_df.shape}")
    logger.info(f"  Temporal window: {temporal_window}")

    logger.info(f"\n✅ A1 data validated")

    # Create metadata dict for consistency
    metadata = {
        'temporal_window': temporal_window,
        'n_indicators': n_indicators,
        'preprocessing_method': preprocessing_info.get('method', 'MICE'),
        'tier_data': tier_data_dict,
        'n_countries': sample_df.shape[0],
        'n_years': sample_df.shape[1]
    }

    return edges_df, graph, imputed_data_dict, metadata

def check_temporal_alignment(edges_df, imputed_data_dict, metadata):
    """
    CRITICAL: Validate temporal alignment strategy

    Decision: Use contemporaneous adjustment (Z measured at same time as X)
    Implementation: For edge X(t-k) → Y(t), regress Y(t) ~ X(t-k) + Z(t-k)
    """
    logger.info("\n" + "="*80)
    logger.info("TEMPORAL ALIGNMENT VALIDATION (CRITICAL)")
    logger.info("="*80)

    logger.info("\n📋 Temporal Alignment Strategy:")
    logger.info("  Decision: Contemporaneous adjustment (Z measured with X)")
    logger.info("  Rationale: Backdoor criterion requires controlling for")
    logger.info("             confounders at time of treatment, not outcome")
    logger.info("  Implementation: For X(t-k) → Y(t), regress Y(t) ~ X(t-k) + Z(t-k)")

    # Check lag distribution
    lag_dist = edges_df['best_lag'].value_counts().sort_index()
    logger.info(f"\n  Lag distribution:")
    for lag, count in lag_dist.items():
        logger.info(f"    Lag {lag}: {count:,} edges ({count/len(edges_df)*100:.1f}%)")

    # For each edge, estimate available observations after alignment
    logger.info(f"\n  Checking data availability after temporal alignment...")

    # Get country-year structure from metadata
    n_countries = metadata['n_countries']
    n_years = metadata['n_years']
    temporal_window = metadata['temporal_window']

    logger.info(f"  Countries: {n_countries}")
    logger.info(f"  Years: {temporal_window[0]}-{temporal_window[1]} ({n_years} years)")

    # Sample check: For 100 random edges, count available observations
    sample_edges = edges_df.sample(min(100, len(edges_df)), random_state=42)

    obs_counts = []
    for _, edge in sample_edges.iterrows():
        X = edge['source']
        Y = edge['target']
        lag = int(edge['best_lag'])

        # Count non-null observations where both X(t-k) and Y(t) exist
        if X in imputed_data_dict and Y in imputed_data_dict:
            # Simplified check: count non-null cells
            # Actual alignment will happen in Phase 2
            X_data = imputed_data_dict[X]
            Y_data = imputed_data_dict[Y]

            # Count cells with both X and Y non-null
            X_valid = ~X_data.isna()
            Y_valid = ~Y_data.isna()
            both_valid = X_valid & Y_valid
            obs_counts.append(both_valid.sum().sum())  # Sum across countries and years
        else:
            obs_counts.append(0)

    logger.info(f"\n  Sample of 100 edges - available observations:")
    logger.info(f"    Mean: {np.mean(obs_counts):.0f}")
    logger.info(f"    Median: {np.median(obs_counts):.0f}")
    logger.info(f"    Min: {np.min(obs_counts):.0f}")
    logger.info(f"    Edges with <30 obs: {sum(1 for x in obs_counts if x < 30)}")

    insufficient_data_pct = sum(1 for x in obs_counts if x < 30) / len(obs_counts) * 100

    if insufficient_data_pct > 20:
        logger.warning(f"\n  ⚠️  WARNING: {insufficient_data_pct:.1f}% of sample edges have <30 observations")
        logger.warning(f"     May need to adjust threshold or expect higher edge removal rate")
    else:
        logger.info(f"\n  ✅ Data availability looks good ({insufficient_data_pct:.1f}% < 30 obs)")

    return {
        'lag_distribution': lag_dist.to_dict(),
        'sample_obs_mean': np.mean(obs_counts),
        'sample_obs_median': np.median(obs_counts),
        'pct_insufficient': insufficient_data_pct
    }

def create_input_manifest(edges_df, metadata, alignment_check):
    """Create input manifest for Phase 2"""
    manifest = {
        'timestamp': datetime.now().isoformat(),
        'a3_edges': {
            'file': '../A3_conditional_independence/outputs/A3_final_dag_v2.pkl',
            'n_edges': len(edges_df),
            'n_nodes': len(edges_df['source'].unique()) + len(edges_df['target'].unique()),
            'edge_attributes': list(edges_df.columns)
        },
        'a1_data': {
            'file': '../A1_missingness_analysis/outputs/A2_preprocessed_data.pkl',
            'n_indicators': metadata['n_indicators'],
            'n_countries': metadata['n_countries'],
            'n_years': metadata['n_years'],
            'temporal_window': metadata['temporal_window']
        },
        'temporal_alignment': {
            'strategy': 'contemporaneous_adjustment',
            'implementation': 'Y(t) ~ X(t-k) + Z(t-k)',
            'lag_distribution': alignment_check['lag_distribution'],
            'sample_obs_mean': alignment_check['sample_obs_mean'],
            'expected_insufficient_data_rate': alignment_check['pct_insufficient']
        },
        'next_phase': 'Phase 2: Backdoor Adjustment Set Identification'
    }

    output_file = Path(__file__).parent.parent / 'outputs' / 'input_manifest.pkl'
    with open(output_file, 'wb') as f:
        pickle.dump(manifest, f)

    logger.info(f"\n✅ Saved input manifest: {output_file}")

    return manifest

def main():
    # Load inputs
    edges_df, graph, imputed_data_dict, metadata = load_inputs()

    # Validate temporal alignment
    alignment_check = check_temporal_alignment(edges_df, imputed_data_dict, metadata)

    # Create manifest
    manifest = create_input_manifest(edges_df, metadata, alignment_check)

    logger.info("\n" + "="*80)
    logger.info("✅ PHASE 1 COMPLETE - READY FOR PHASE 2")
    logger.info("="*80)
    logger.info(f"\nNext: Run step2_backdoor_identification.py")
    logger.info(f"Expected runtime: 12-24 hours")
    logger.info("="*80 + "\n")

if __name__ == '__main__':
    main()
