#!/usr/bin/env python3
"""
V2.1 Step 3: Validation and Comparison

Compares V2 and V2.1 outputs to validate domain balancing success.

Author: Claude Code
Date: December 2025
"""

import pickle
import json
from pathlib import Path
from datetime import datetime
from collections import defaultdict
import logging

# ============================================================================
# CONFIGURATION
# ============================================================================

PROJECT_ROOT = Path(__file__).parent.parent.parent
V21_OUTPUT_DIR = PROJECT_ROOT / 'v2.1/outputs'
LOG_DIR = PROJECT_ROOT / 'v2.1/logs'

# V2 paths (original)
V2_A6_GRAPH = PROJECT_ROOT / 'phaseA/A6_hierarchical_layering/outputs/A6_hierarchical_graph.pkl'
V2_B35_HIERARCHY = PROJECT_ROOT / 'phaseB/B35_semantic_hierarchy/outputs/B35_semantic_hierarchy.pkl'
V2_SHAP_SCORES = PROJECT_ROOT / 'phaseB/B35_semantic_hierarchy/outputs/B35_shap_scores.pkl'

# V2.1 paths (after rerun - same locations but with V2.1 data)
# Note: V2.1 overwrites these files, so we compare against sampling_report.json

# Backup paths
V2_BACKUP_A2 = PROJECT_ROOT / 'phaseA/A1_missingness_analysis/outputs/A2_preprocessed_data_V2_BACKUP.pkl'

# ============================================================================
# LOGGING SETUP
# ============================================================================

LOG_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / 'validation.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============================================================================
# VALIDATION FUNCTIONS
# ============================================================================

def load_v2_stats():
    """Load V2 original statistics from backup or calculate from current."""
    stats = {}

    # Try to load from backup
    if V2_BACKUP_A2.exists():
        logger.info("Loading V2 stats from backup...")
        with open(V2_BACKUP_A2, 'rb') as f:
            v2_data = pickle.load(f)
        stats['total_indicators'] = len(v2_data.get('metadata', {}))

        # Calculate domain distribution
        domain_map = {
            'vdem': 'Governance', 'qog': 'Governance',
            'unesco': 'Education',
            'wid': 'Economic', 'world_bank': 'Economic', 'imf': 'Economic', 'penn': 'Economic',
            'who': 'Health'
        }

        domain_counts = defaultdict(int)
        for ind, meta in v2_data.get('metadata', {}).items():
            source = meta.get('source', 'unknown')
            domain = domain_map.get(source, 'Unknown')
            domain_counts[domain] += 1

        stats['domain_distribution'] = dict(domain_counts)

    else:
        # Use known V2 stats
        logger.info("Using known V2 statistics...")
        stats = {
            'total_indicators': 6368,
            'domain_distribution': {
                'Governance': 2633,
                'Education': 1557,
                'Economic': 2056,
                'Health': 122
            }
        }

    # Load graph stats
    if V2_A6_GRAPH.exists():
        with open(V2_A6_GRAPH, 'rb') as f:
            v2_graph_data = pickle.load(f)
        G = v2_graph_data['graph']
        stats['nodes'] = G.number_of_nodes()
        stats['edges'] = G.number_of_edges()
        stats['layers'] = v2_graph_data.get('n_layers', 0)

    return stats


def load_v21_stats():
    """Load V2.1 statistics from sampling report and outputs."""
    stats = {}

    # Load from sampling report
    sampling_report = V21_OUTPUT_DIR / 'sampling_report.json'
    if sampling_report.exists():
        with open(sampling_report, 'r') as f:
            report = json.load(f)
        stats['total_indicators'] = report['summary']['sampled_indicators']
        stats['domain_distribution'] = report['final_distribution']
        stats['retention_rate'] = report['summary']['retention_rate']
    else:
        logger.warning("V2.1 sampling report not found")
        return None

    # Load graph stats (if Phase A completed)
    if V2_A6_GRAPH.exists():
        with open(V2_A6_GRAPH, 'rb') as f:
            v21_graph_data = pickle.load(f)
        G = v21_graph_data['graph']
        stats['nodes'] = G.number_of_nodes()
        stats['edges'] = G.number_of_edges()
        stats['layers'] = v21_graph_data.get('n_layers', 0)

    return stats


def calculate_balance_score(distribution: dict) -> float:
    """
    Calculate domain balance score.
    Lower = more balanced (0 = perfect balance for major domains)
    """
    major_domains = ['Governance', 'Education', 'Economic']
    counts = [distribution.get(d, 0) for d in major_domains]

    if sum(counts) == 0:
        return 1.0

    # Normalize to percentages
    total = sum(counts)
    pcts = [c / total for c in counts]

    # Calculate standard deviation (lower = more balanced)
    mean_pct = sum(pcts) / len(pcts)
    variance = sum((p - mean_pct) ** 2 for p in pcts) / len(pcts)
    std = variance ** 0.5

    return std


def validate_success_criteria(v2_stats: dict, v21_stats: dict) -> dict:
    """Check all success criteria and return results."""
    results = {
        'passed': [],
        'failed': [],
        'warnings': []
    }

    # Criterion 1: Total indicators in range
    if v21_stats:
        total = v21_stats.get('total_indicators', 0)
        if 3000 <= total <= 3500:
            results['passed'].append(f"Total indicators: {total} (in range 3000-3500)")
        else:
            results['failed'].append(f"Total indicators: {total} (outside range 3000-3500)")

    # Criterion 2: Major domain balance
    if v21_stats and 'domain_distribution' in v21_stats:
        dist = v21_stats['domain_distribution']
        major = ['Governance', 'Education', 'Economic']
        counts = [dist.get(d, 0) for d in major]

        max_diff = max(counts) - min(counts)
        if max_diff <= 200:
            results['passed'].append(f"Major domain balance: max diff = {max_diff} (<=200)")
        else:
            results['failed'].append(f"Major domain balance: max diff = {max_diff} (>200)")

        # Check each is close to 1000
        for domain in major:
            count = dist.get(domain, 0)
            diff = abs(count - 1000)
            if diff <= 100:
                results['passed'].append(f"{domain}: {count} (within 100 of target 1000)")
            else:
                results['warnings'].append(f"{domain}: {count} (diff from target: {diff})")

    # Criterion 3: Health retention
    if v21_stats and 'domain_distribution' in v21_stats:
        health = v21_stats['domain_distribution'].get('Health', 0)
        if health >= 100:
            results['passed'].append(f"Health retention: {health} (>=100)")
        else:
            results['failed'].append(f"Health retention: {health} (<100)")

    # Criterion 4: Balance improvement
    if v2_stats and v21_stats:
        v2_balance = calculate_balance_score(v2_stats.get('domain_distribution', {}))
        v21_balance = calculate_balance_score(v21_stats.get('domain_distribution', {}))

        if v21_balance < v2_balance:
            improvement = ((v2_balance - v21_balance) / v2_balance) * 100
            results['passed'].append(f"Balance improved: {v2_balance:.4f} -> {v21_balance:.4f} ({improvement:.1f}% better)")
        else:
            results['warnings'].append(f"Balance not improved: V2={v2_balance:.4f}, V2.1={v21_balance:.4f}")

    return results


# ============================================================================
# MAIN
# ============================================================================

def main():
    logger.info("="*80)
    logger.info("V2.1 VALIDATION REPORT")
    logger.info("="*80)
    logger.info(f"Generated: {datetime.now().isoformat()}")

    # Load statistics
    logger.info("\n[1/4] Loading V2 statistics...")
    v2_stats = load_v2_stats()

    logger.info("\n[2/4] Loading V2.1 statistics...")
    v21_stats = load_v21_stats()

    if v21_stats is None:
        logger.error("V2.1 statistics not available. Run step0_stratified_sampling.py first!")
        return False

    # Comparison
    logger.info("\n[3/4] Comparing V2 vs V2.1...")
    logger.info("\n" + "-"*60)
    logger.info("COMPARISON: V2 vs V2.1")
    logger.info("-"*60)

    # Indicator counts
    logger.info("\nIndicator Counts:")
    logger.info(f"  V2:   {v2_stats.get('total_indicators', 'N/A')}")
    logger.info(f"  V2.1: {v21_stats.get('total_indicators', 'N/A')}")
    if v21_stats.get('retention_rate'):
        logger.info(f"  Retention: {v21_stats['retention_rate']*100:.1f}%")

    # Domain distribution
    logger.info("\nDomain Distribution:")
    logger.info(f"{'Domain':<15} {'V2':>10} {'V2.1':>10} {'Change':>10}")
    logger.info("-"*50)

    all_domains = set(v2_stats.get('domain_distribution', {}).keys()) | \
                  set(v21_stats.get('domain_distribution', {}).keys())

    for domain in sorted(all_domains):
        v2_count = v2_stats.get('domain_distribution', {}).get(domain, 0)
        v21_count = v21_stats.get('domain_distribution', {}).get(domain, 0)
        change = v21_count - v2_count
        change_str = f"{change:+d}" if change != 0 else "0"
        logger.info(f"{domain:<15} {v2_count:>10} {v21_count:>10} {change_str:>10}")

    # Balance scores
    v2_balance = calculate_balance_score(v2_stats.get('domain_distribution', {}))
    v21_balance = calculate_balance_score(v21_stats.get('domain_distribution', {}))

    logger.info("\nBalance Score (lower = better):")
    logger.info(f"  V2:   {v2_balance:.4f}")
    logger.info(f"  V2.1: {v21_balance:.4f}")

    # Graph stats (if available)
    if 'nodes' in v21_stats:
        logger.info("\nGraph Statistics:")
        logger.info(f"{'Metric':<15} {'V2':>10} {'V2.1':>10}")
        logger.info("-"*40)
        logger.info(f"{'Nodes':<15} {v2_stats.get('nodes', 'N/A'):>10} {v21_stats.get('nodes', 'N/A'):>10}")
        logger.info(f"{'Edges':<15} {v2_stats.get('edges', 'N/A'):>10} {v21_stats.get('edges', 'N/A'):>10}")
        logger.info(f"{'Layers':<15} {v2_stats.get('layers', 'N/A'):>10} {v21_stats.get('layers', 'N/A'):>10}")

    # Validate success criteria
    logger.info("\n[4/4] Validating success criteria...")
    logger.info("\n" + "-"*60)
    logger.info("SUCCESS CRITERIA CHECK")
    logger.info("-"*60)

    results = validate_success_criteria(v2_stats, v21_stats)

    if results['passed']:
        logger.info("\nPASSED:")
        for item in results['passed']:
            logger.info(f"  OK {item}")

    if results['warnings']:
        logger.info("\nWARNINGS:")
        for item in results['warnings']:
            logger.warning(f"  ? {item}")

    if results['failed']:
        logger.info("\nFAILED:")
        for item in results['failed']:
            logger.error(f"  FAIL {item}")

    # Final verdict
    all_passed = len(results['failed']) == 0

    logger.info("\n" + "="*80)
    if all_passed:
        logger.info("VALIDATION RESULT: SUCCESS")
        logger.info("="*80)
        logger.info("\nV2.1 domain balancing achieved target criteria.")
        logger.info("Proceed to visualization phase with V2.1 outputs.")
    else:
        logger.warning("VALIDATION RESULT: NEEDS REVIEW")
        logger.warning("="*80)
        logger.warning("\nSome criteria not met. Review failed items above.")
        logger.warning("Consider adjusting sampling targets or investigating issues.")

    # Save validation report
    report = {
        'timestamp': datetime.now().isoformat(),
        'v2_stats': v2_stats,
        'v21_stats': v21_stats,
        'v2_balance_score': v2_balance,
        'v21_balance_score': v21_balance,
        'validation_results': results,
        'overall_success': all_passed
    }

    report_path = V21_OUTPUT_DIR / 'validation_report.json'
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2, default=str)

    logger.info(f"\nValidation report saved to: {report_path}")

    return all_passed


if __name__ == '__main__':
    success = main()
    exit(0 if success else 1)
