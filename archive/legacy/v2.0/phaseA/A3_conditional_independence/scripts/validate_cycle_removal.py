#!/usr/bin/env python3
"""
Validation 3: Cycle Removal Causal Logic Check

Verifies that cycle removal didn't break causal logic
by analyzing characteristics of removed cycle edges.
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
    """Load PC-Stable and final DAG outputs"""
    logger.info("Loading PC-Stable validated edges and final DAG...")

    # Load PC-Stable validated (before cycle removal)
    with open('../outputs/A3_validated_fisher_z_v2.pkl', 'rb') as f:
        pc_data = pickle.load(f)

    pc_validated = pc_data['validated_edges']

    # Load final DAG (after cycle removal)
    with open('../outputs/A3_final_dag_v2.pkl', 'rb') as f:
        a3_data = pickle.load(f)

    final_edges = a3_data['edges']

    return pc_validated, final_edges

def categorize_edge(source, target):
    """Infer domain from variable name"""
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

def analyze_cycle_removal(pc_validated, final_edges):
    """Analyze edges removed during cycle removal"""
    logger.info("="*80)
    logger.info("ANALYZING CYCLE REMOVAL STAGE")
    logger.info("="*80)

    # Create edge identifiers
    pc_validated['edge_id'] = pc_validated['source'] + '→' + pc_validated['target']
    final_edges['edge_id'] = final_edges['source'] + '→' + final_edges['target']

    # Identify removed edges
    pc_edge_ids = set(pc_validated['edge_id'])
    final_edge_ids = set(final_edges['edge_id'])

    removed_edge_ids = pc_edge_ids - final_edge_ids
    removed_edges = pc_validated[pc_validated['edge_id'].isin(removed_edge_ids)].copy()

    logger.info(f"\nPC-Stable edges: {len(pc_validated):,}")
    logger.info(f"Final DAG edges: {len(final_edges):,}")
    logger.info(f"Removed edges: {len(removed_edges):,} ({len(removed_edges)/len(pc_validated)*100:.1f}%)")

    # Analyze removed edges by strength
    logger.info("\n" + "="*80)
    logger.info("REMOVED EDGE STRENGTH DISTRIBUTION")
    logger.info("="*80)

    weak_removed = removed_edges[removed_edges['f_statistic'] < 30]
    moderate_removed = removed_edges[(removed_edges['f_statistic'] >= 30) & (removed_edges['f_statistic'] < 50)]
    strong_removed = removed_edges[removed_edges['f_statistic'] >= 50]

    logger.info(f"\nF-statistic distribution of removed edges:")
    logger.info(f"  F < 30 (weak): {len(weak_removed):,} ({len(weak_removed)/len(removed_edges)*100:.1f}%)")
    logger.info(f"  30 ≤ F < 50 (moderate): {len(moderate_removed):,} ({len(moderate_removed)/len(removed_edges)*100:.1f}%)")
    logger.info(f"  F ≥ 50 (strong): {len(strong_removed):,} ({len(strong_removed)/len(removed_edges)*100:.1f}%)")

    logger.info(f"\nStatistics:")
    logger.info(f"  Mean F-stat (removed): {removed_edges['f_statistic'].mean():.2f}")
    logger.info(f"  Median F-stat (removed): {removed_edges['f_statistic'].median():.2f}")
    logger.info(f"  Mean F-stat (kept): {final_edges['f_statistic'].mean():.2f}")
    logger.info(f"  Median F-stat (kept): {final_edges['f_statistic'].median():.2f}")

    median_removed = removed_edges['f_statistic'].median()
    strong_removed_pct = len(strong_removed) / len(removed_edges) * 100 if len(removed_edges) > 0 else 0

    # Check bidirectional pairs
    logger.info("\n" + "="*80)
    logger.info("BIDIRECTIONAL PAIR ANALYSIS")
    logger.info("="*80)

    # Find bidirectional pairs in PC-Stable
    bidirectional_pairs = []
    pc_edges_set = set((row['source'], row['target']) for _, row in pc_validated.iterrows())

    for _, edge in pc_validated.iterrows():
        reverse_edge = (edge['target'], edge['source'])
        if reverse_edge in pc_edges_set:
            # Found bidirectional pair
            pair = tuple(sorted([edge['source'], edge['target']]))
            if pair not in [p[0] for p in bidirectional_pairs]:
                # Get F-stats for both directions
                fwd_f = edge['f_statistic']
                rev_row = pc_validated[
                    (pc_validated['source'] == edge['target']) &
                    (pc_validated['target'] == edge['source'])
                ]
                rev_f = rev_row['f_statistic'].values[0] if len(rev_row) > 0 else 0

                bidirectional_pairs.append((pair, fwd_f, rev_f))

    logger.info(f"\nBidirectional pairs found: {len(bidirectional_pairs)}")

    if len(bidirectional_pairs) > 0:
        # Check which direction was kept
        correct_direction = 0
        for (var1, var2), f1, f2 in bidirectional_pairs[:50]:  # Check first 50
            # Determine stronger direction
            if f1 > f2:
                stronger_edge = (var1, var2)
            else:
                stronger_edge = (var2, var1)

            # Check if stronger edge is in final DAG
            stronger_in_final = final_edges[
                (final_edges['source'] == stronger_edge[0]) &
                (final_edges['target'] == stronger_edge[1])
            ]

            if len(stronger_in_final) > 0:
                correct_direction += 1

        correct_direction_pct = correct_direction / min(50, len(bidirectional_pairs)) * 100
        logger.info(f"Stronger direction kept: {correct_direction} / {min(50, len(bidirectional_pairs))} ({correct_direction_pct:.1f}%)")
    else:
        correct_direction_pct = 100.0  # No bidirectional pairs = trivially correct

    # Domain impact analysis
    logger.info("\n" + "="*80)
    logger.info("DOMAIN IMPACT ANALYSIS")
    logger.info("="*80)

    pc_domains = []
    removed_domains = []
    kept_domains = []

    for _, edge in pc_validated.iterrows():
        src_dom, tgt_dom = categorize_edge(edge['source'], edge['target'])
        domain_pair = f"{src_dom}→{tgt_dom}"
        pc_domains.append(domain_pair)

    for _, edge in removed_edges.iterrows():
        src_dom, tgt_dom = categorize_edge(edge['source'], edge['target'])
        domain_pair = f"{src_dom}→{tgt_dom}"
        removed_domains.append(domain_pair)

    for _, edge in final_edges.iterrows():
        src_dom, tgt_dom = categorize_edge(edge['source'], edge['target'])
        domain_pair = f"{src_dom}→{tgt_dom}"
        kept_domains.append(domain_pair)

    pc_domain_counts = Counter(pc_domains)
    removed_domain_counts = Counter(removed_domains)

    logger.info("\nDomain pair removal rates:")
    domain_removal_rates = []

    for domain_pair in sorted(pc_domain_counts.keys(), key=lambda x: pc_domain_counts[x], reverse=True)[:10]:
        pc_count = pc_domain_counts[domain_pair]
        removed_count = removed_domain_counts.get(domain_pair, 0)
        removal_rate = (removed_count / pc_count * 100) if pc_count > 0 else 0

        logger.info(f"  {domain_pair:30s}: {removed_count:>6,} / {pc_count:>6,} removed ({removal_rate:>5.1f}%)")
        domain_removal_rates.append(removal_rate)

    max_domain_removal = max(domain_removal_rates) if domain_removal_rates else 0

    # Sample strong removed edges
    logger.info("\n" + "="*80)
    logger.info("STRONG REMOVED EDGES (F≥50)")
    logger.info("="*80)

    if len(strong_removed) > 0:
        logger.info(f"\nTotal strong removed edges: {len(strong_removed)}")
        logger.info("\nTop 20 examples:")

        for idx, (_, edge) in enumerate(strong_removed.sort_values('f_statistic', ascending=False).head(20).iterrows(), 1):
            logger.info(f"  {idx:2d}. {edge['source']:40s} → {edge['target']:40s} | F={edge['f_statistic']:6.1f}")
    else:
        logger.info("\n✅ No strong edges (F≥50) were removed")

    return {
        'median_removed_f': median_removed,
        'strong_removed_pct': strong_removed_pct,
        'correct_direction_pct': correct_direction_pct,
        'max_domain_removal': max_domain_removal
    }

def main():
    logger.info("\n" + "="*80)
    logger.info("A3 VALIDATION 3: CYCLE REMOVAL CAUSAL LOGIC CHECK")
    logger.info("="*80)

    # Load data
    pc_validated, final_edges = load_data()

    # Analyze cycle removal
    stats = analyze_cycle_removal(pc_validated, final_edges)

    # Validation thresholds
    logger.info("\n" + "="*80)
    logger.info("VALIDATION ASSESSMENT")
    logger.info("="*80)

    passes = []

    # Check 1: Median F-stat of removed edges
    if stats['median_removed_f'] < 40:
        logger.info(f"✅ PASS: Median F-stat of removed edges: {stats['median_removed_f']:.1f} (<40)")
        passes.append(True)
    elif stats['median_removed_f'] < 50:
        logger.info(f"⚠️  WARNING: Median F-stat of removed edges: {stats['median_removed_f']:.1f} (40-50)")
        passes.append(True)
    else:
        logger.info(f"❌ FAIL: Median F-stat of removed edges: {stats['median_removed_f']:.1f} (≥50)")
        passes.append(False)

    # Check 2: Strong edges removed
    if stats['strong_removed_pct'] < 10:
        logger.info(f"✅ PASS: Strong edges (F≥50) removed: {stats['strong_removed_pct']:.1f}% (<10%)")
        passes.append(True)
    elif stats['strong_removed_pct'] < 20:
        logger.info(f"⚠️  WARNING: Strong edges (F≥50) removed: {stats['strong_removed_pct']:.1f}% (10-20%)")
        passes.append(True)
    else:
        logger.info(f"❌ FAIL: Strong edges (F≥50) removed: {stats['strong_removed_pct']:.1f}% (≥20%)")
        passes.append(False)

    # Check 3: Bidirectional pairs
    if stats['correct_direction_pct'] >= 90:
        logger.info(f"✅ PASS: Stronger direction kept: {stats['correct_direction_pct']:.1f}% (≥90%)")
        passes.append(True)
    elif stats['correct_direction_pct'] >= 80:
        logger.info(f"⚠️  WARNING: Stronger direction kept: {stats['correct_direction_pct']:.1f}% (80-90%)")
        passes.append(True)
    else:
        logger.info(f"❌ FAIL: Stronger direction kept: {stats['correct_direction_pct']:.1f}% (<80%)")
        passes.append(False)

    # Check 4: Domain impact
    if stats['max_domain_removal'] < 30:
        logger.info(f"✅ PASS: Max domain removal rate: {stats['max_domain_removal']:.1f}% (<30%)")
        passes.append(True)
    elif stats['max_domain_removal'] < 40:
        logger.info(f"⚠️  WARNING: Max domain removal rate: {stats['max_domain_removal']:.1f}% (30-40%)")
        passes.append(True)
    else:
        logger.info(f"❌ FAIL: Max domain removal rate: {stats['max_domain_removal']:.1f}% (≥40%)")
        passes.append(False)

    logger.info("\n" + "="*80)

    if all(passes):
        logger.info("✅ VALIDATION 3: PASSED")
        logger.info("Cycle removal did not break causal logic.")
    else:
        logger.info("❌ VALIDATION 3: FAILED")
        logger.info("Cycle removal may have removed mechanistically important edges.")
        logger.info("\nRecommendation: Use weighted FAS (minimize sum of F-stats removed)")

    logger.info("="*80)

    # Save results
    output_file = Path('../diagnostics/validation3_cycle_removal.pkl')

    validation_output = {
        'statistics': stats,
        'passed': all(passes)
    }

    with open(output_file, 'wb') as f:
        pickle.dump(validation_output, f)

    logger.info(f"\n✅ Saved: {output_file}")

if __name__ == '__main__':
    main()
