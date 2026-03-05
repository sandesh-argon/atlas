#!/usr/bin/env python3
"""
Validation 2: Pre-Pruning Mechanism Loss Analysis

Verifies that pre-pruning didn't lose critical mechanisms
by analyzing characteristics of removed edges.
"""

import pickle
import pandas as pd
import numpy as np
from pathlib import Path
from collections import Counter
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def load_data():
    """Load A2 and A3 outputs"""
    logger.info("Loading A2 Granger edges and A3 final DAG...")

    # Load A2 FDR-corrected edges (q<0.01)
    with open('../../A2_granger_causality/outputs/granger_fdr_corrected.pkl', 'rb') as f:
        a2_data = pickle.load(f)

    # Filter to q<0.01 (A3 input)
    a2_edges = a2_data['results'][a2_data['results']['p_value_fdr'] < 0.01].copy()

    # Load pre-pruned edges
    with open('../outputs/smart_prepruned_edges.pkl', 'rb') as f:
        prepruned_data = pickle.load(f)

    prepruned_edges = prepruned_data['edges']

    # Load PC-Stable validated edges
    with open('../outputs/A3_validated_fisher_z_v2.pkl', 'rb') as f:
        pc_data = pickle.load(f)

    pc_validated = pc_data['validated_edges']

    # Load final DAG
    with open('../outputs/A3_final_dag_v2.pkl', 'rb') as f:
        a3_data = pickle.load(f)

    final_edges = a3_data['edges']

    return a2_edges, prepruned_edges, pc_validated, final_edges

def categorize_edge(source, target):
    """
    Infer domain from variable name
    Simple heuristic based on common keywords
    """
    domains = {
        'Economic': ['gdp', 'gni', 'income', 'trade', 'export', 'import', 'tax', 'debt', 'investment', 'fdi'],
        'Health': ['health', 'life_expectancy', 'mortality', 'disease', 'nutrition', 'malnutrition', 'hospital', 'physician'],
        'Education': ['education', 'school', 'literacy', 'enrollment', 'teacher', 'university'],
        'Governance': ['government', 'democracy', 'corruption', 'rule_of_law', 'political', 'civil_liberties'],
        'Environment': ['co2', 'emission', 'renewable', 'forest', 'energy', 'climate'],
        'Social': ['population', 'urban', 'rural', 'employment', 'unemployment', 'poverty', 'inequality', 'gini']
    }

    source_lower = source.lower()
    target_lower = target.lower()

    source_domain = 'Other'
    target_domain = 'Other'

    for domain, keywords in domains.items():
        if any(kw in source_lower for kw in keywords):
            source_domain = domain
        if any(kw in target_lower for kw in keywords):
            target_domain = domain

    return source_domain, target_domain

def analyze_prepruning_loss(a2_edges, prepruned_edges):
    """Analyze edges lost during pre-pruning"""
    logger.info("="*80)
    logger.info("ANALYZING PRE-PRUNING STAGE")
    logger.info("="*80)

    # Create edge identifiers
    a2_edges['edge_id'] = a2_edges['source'] + '→' + a2_edges['target']
    prepruned_edges['edge_id'] = prepruned_edges['source'] + '→' + prepruned_edges['target']

    # Identify lost edges
    a2_edge_ids = set(a2_edges['edge_id'])
    prepruned_edge_ids = set(prepruned_edges['edge_id'])

    lost_edge_ids = a2_edge_ids - prepruned_edge_ids
    lost_edges = a2_edges[a2_edges['edge_id'].isin(lost_edge_ids)].copy()

    logger.info(f"\nA2 edges (q<0.01): {len(a2_edges):,}")
    logger.info(f"Pre-pruned edges: {len(prepruned_edges):,}")
    logger.info(f"Lost edges: {len(lost_edges):,} ({len(lost_edges)/len(a2_edges)*100:.1f}%)")

    # Analyze lost edges by strength
    logger.info("\n" + "="*80)
    logger.info("LOST EDGE CHARACTERISTICS")
    logger.info("="*80)

    # F-statistic distribution
    moderate_strength = lost_edges[(lost_edges['f_statistic'] >= 10) & (lost_edges['f_statistic'] < 40)]
    high_strength = lost_edges[lost_edges['f_statistic'] >= 40]

    logger.info(f"\nF-statistic distribution of lost edges:")
    logger.info(f"  F < 10: {len(lost_edges[lost_edges['f_statistic'] < 10]):,} ({len(lost_edges[lost_edges['f_statistic'] < 10])/len(lost_edges)*100:.1f}%)")
    logger.info(f"  10 ≤ F < 40: {len(moderate_strength):,} ({len(moderate_strength)/len(lost_edges)*100:.1f}%)")
    logger.info(f"  F ≥ 40: {len(high_strength):,} ({len(high_strength)/len(lost_edges)*100:.1f}%)")

    moderate_pct = len(moderate_strength) / len(lost_edges) * 100 if len(lost_edges) > 0 else 0

    # P-value distribution
    mid_pvalue = lost_edges[(lost_edges['p_value_fdr'] >= 1e-6) & (lost_edges['p_value_fdr'] < 1e-3)]
    low_pvalue = lost_edges[lost_edges['p_value_fdr'] < 1e-6]

    logger.info(f"\nP-value distribution of lost edges:")
    logger.info(f"  p < 1e-06: {len(low_pvalue):,} ({len(low_pvalue)/len(lost_edges)*100:.1f}%)")
    logger.info(f"  1e-06 ≤ p < 1e-03: {len(mid_pvalue):,} ({len(mid_pvalue)/len(lost_edges)*100:.1f}%)")

    mid_pvalue_pct = len(mid_pvalue) / len(lost_edges) * 100 if len(lost_edges) > 0 else 0

    # Domain analysis
    logger.info("\n" + "="*80)
    logger.info("DOMAIN REPRESENTATION ANALYSIS")
    logger.info("="*80)

    # Categorize all edges
    a2_domains = []
    lost_domains = []
    kept_domains = []

    for _, edge in a2_edges.iterrows():
        src_dom, tgt_dom = categorize_edge(edge['source'], edge['target'])
        domain_pair = f"{src_dom}→{tgt_dom}"
        a2_domains.append(domain_pair)

    for _, edge in lost_edges.iterrows():
        src_dom, tgt_dom = categorize_edge(edge['source'], edge['target'])
        domain_pair = f"{src_dom}→{tgt_dom}"
        lost_domains.append(domain_pair)

    for _, edge in prepruned_edges.iterrows():
        src_dom, tgt_dom = categorize_edge(edge['source'], edge['target'])
        domain_pair = f"{src_dom}→{tgt_dom}"
        kept_domains.append(domain_pair)

    a2_domain_counts = Counter(a2_domains)
    lost_domain_counts = Counter(lost_domains)
    kept_domain_counts = Counter(kept_domains)

    logger.info("\nDomain pair retention rates:")
    domain_loss_rates = []

    for domain_pair in sorted(a2_domain_counts.keys(), key=lambda x: a2_domain_counts[x], reverse=True)[:10]:
        a2_count = a2_domain_counts[domain_pair]
        lost_count = lost_domain_counts.get(domain_pair, 0)
        kept_count = kept_domain_counts.get(domain_pair, 0)
        loss_rate = (lost_count / a2_count * 100) if a2_count > 0 else 0

        logger.info(f"  {domain_pair:30s}: {kept_count:>6,} / {a2_count:>6,} kept ({100-loss_rate:>5.1f}% retention)")
        domain_loss_rates.append(loss_rate)

    max_domain_loss = max(domain_loss_rates) if domain_loss_rates else 0

    # Sample high-value lost edges
    logger.info("\n" + "="*80)
    logger.info("HIGH-VALUE LOST EDGES (F=15-40, p<1e-04)")
    logger.info("="*80)

    high_value_lost = lost_edges[
        (lost_edges['f_statistic'] >= 15) &
        (lost_edges['f_statistic'] < 40) &
        (lost_edges['p_value_fdr'] < 1e-4)
    ].sort_values('f_statistic', ascending=False)

    logger.info(f"\nTotal high-value lost edges: {len(high_value_lost)}")

    if len(high_value_lost) > 0:
        logger.info("\nTop 20 examples:")
        for idx, (_, edge) in enumerate(high_value_lost.head(20).iterrows(), 1):
            logger.info(f"  {idx:2d}. {edge['source']:40s} → {edge['target']:40s} | F={edge['f_statistic']:6.1f}, p={edge['p_value_fdr']:.2e}")

    return {
        'moderate_pct': moderate_pct,
        'mid_pvalue_pct': mid_pvalue_pct,
        'max_domain_loss': max_domain_loss,
        'high_value_lost_count': len(high_value_lost)
    }

def main():
    logger.info("\n" + "="*80)
    logger.info("A3 VALIDATION 2: PRE-PRUNING MECHANISM LOSS ANALYSIS")
    logger.info("="*80)

    # Load data
    a2_edges, prepruned_edges, pc_validated, final_edges = load_data()

    # Analyze pre-pruning
    stats = analyze_prepruning_loss(a2_edges, prepruned_edges)

    # Validation thresholds
    logger.info("\n" + "="*80)
    logger.info("VALIDATION ASSESSMENT")
    logger.info("="*80)

    passes = []

    # Check 1: Moderate F-stat edges
    if stats['moderate_pct'] < 30:
        logger.info(f"✅ PASS: Lost edges with F=10-40: {stats['moderate_pct']:.1f}% (<30%)")
        passes.append(True)
    elif stats['moderate_pct'] < 40:
        logger.info(f"⚠️  WARNING: Lost edges with F=10-40: {stats['moderate_pct']:.1f}% (30-40%)")
        passes.append(True)
    else:
        logger.info(f"❌ FAIL: Lost edges with F=10-40: {stats['moderate_pct']:.1f}% (≥40%)")
        passes.append(False)

    # Check 2: Domain representation
    if stats['max_domain_loss'] < 50:
        logger.info(f"✅ PASS: Max domain loss: {stats['max_domain_loss']:.1f}% (<50%)")
        passes.append(True)
    elif stats['max_domain_loss'] < 60:
        logger.info(f"⚠️  WARNING: Max domain loss: {stats['max_domain_loss']:.1f}% (50-60%)")
        passes.append(True)
    else:
        logger.info(f"❌ FAIL: Max domain loss: {stats['max_domain_loss']:.1f}% (≥60%)")
        passes.append(False)

    # Check 3: High-value lost edges
    if stats['high_value_lost_count'] < 50:
        logger.info(f"✅ PASS: High-value lost edges: {stats['high_value_lost_count']} (<50)")
        passes.append(True)
    elif stats['high_value_lost_count'] < 100:
        logger.info(f"⚠️  WARNING: High-value lost edges: {stats['high_value_lost_count']} (50-100)")
        passes.append(True)
    else:
        logger.info(f"❌ FAIL: High-value lost edges: {stats['high_value_lost_count']} (≥100)")
        passes.append(False)

    logger.info("\n" + "="*80)

    if all(passes):
        logger.info("✅ VALIDATION 2: PASSED")
        logger.info("Pre-pruning did not lose critical mechanisms.")
    else:
        logger.info("❌ VALIDATION 2: FAILED")
        logger.info("Pre-pruning may have lost important moderate-strength mechanisms.")
        logger.info("\nRecommendation: Relax pre-pruning (F>20, p<1e-04) and re-run PC-Stable")

    logger.info("="*80)

    # Save results
    output_file = Path('../diagnostics/validation2_prepruning_loss.pkl')

    validation_output = {
        'statistics': stats,
        'passed': all(passes)
    }

    with open(output_file, 'wb') as f:
        pickle.dump(validation_output, f)

    logger.info(f"\n✅ Saved: {output_file}")

if __name__ == '__main__':
    main()
