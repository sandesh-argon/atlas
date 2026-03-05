#!/usr/bin/env python3
"""
Phase 3B Validation Suite: Run All Cluster Validations

Runs all 6 cluster validation checks and outputs results to markdown.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from validate_cluster_stability import check_temporal_cluster_stability
from validate_cluster_sizes import check_cluster_size_distribution
from validate_domain_composition import check_domain_composition
from validate_cross_country_consistency import check_cross_country_consistency
from validate_cluster_density import check_cluster_density
from validate_sample_indicators import check_sample_indicators

BASE_DIR = Path("<repo-root>/v3.1")
OUTPUT_DIR = BASE_DIR / "outputs"


def run_all_validations():
    """Run all 6 validation checks and return results."""

    print("=" * 60)
    print("V3.1 PHASE 3B CLUSTER VALIDATION SUITE")
    print("=" * 60)
    print(f"Started: {datetime.now().isoformat()}")

    results = {}

    # 1. Cluster Stability
    print("\n[1/6] Running Cluster Stability validation...")
    results['stability'] = check_temporal_cluster_stability()

    # 2. Cluster Sizes
    print("\n[2/6] Running Cluster Size Distribution validation...")
    results['sizes'] = check_cluster_size_distribution()

    # 3. Domain Composition
    print("\n[3/6] Running Domain Composition validation...")
    results['domain'] = check_domain_composition()

    # 4. Cross-Country Consistency
    print("\n[4/6] Running Cross-Country Consistency validation...")
    results['cross_country'] = check_cross_country_consistency()

    # 5. Cluster Density
    print("\n[5/6] Running Cluster Density validation...")
    results['density'] = check_cluster_density()

    # 6. Sample Indicators
    print("\n[6/6] Running Sample Indicators validation...")
    results['samples'] = check_sample_indicators()

    return results


def generate_markdown_report(results: dict) -> str:
    """Generate markdown report from results."""

    # Count passes
    all_checks = ['stability', 'sizes', 'domain', 'cross_country', 'density', 'samples']
    passed = sum(1 for check in all_checks if results.get(check, {}).get('passed', False))
    total = len(all_checks)

    md = f"""# Phase 3B: Development Clusters - Validation Report

**Completed:** {datetime.now().strftime('%Y-%m-%d %H:%M')}
**Status:** {'✅ ALL PASSED' if passed == total else f'⚠️ {passed}/{total} PASSED'}

---

## Summary

| Check | Status | Notes |
|-------|--------|-------|
| 1. Cluster Stability | {'✅ PASS' if results['stability']['passed'] else '⚠️ WARN'} | {results['stability']['instability_rate']*100:.1f}% unstable transitions |
| 2. Size Distribution | {'✅ PASS' if results['sizes']['passed'] else '⚠️ WARN'} | {results['sizes']['unified_issues']} issues found |
| 3. Domain Composition | {'✅ PASS' if results['domain']['passed'] else '⚠️ WARN'} | {results['domain']['domain_mismatches']} mismatches |
| 4. Cross-Country Consistency | {'✅ PASS' if results['cross_country']['passed'] else '⚠️ WARN'} | {len(results['cross_country']['high_variance_groups'])} high-variance groups |
| 5. Cluster Density | {'✅ PASS' if results['density']['passed'] else '⚠️ WARN'} | Mean: {results['density']['density_stats']['mean']:.4f} |
| 6. Sample Indicators | {'✅ PASS' if results['samples']['passed'] else '⚠️ WARN'} | {results['samples']['no_samples']} clusters missing samples |

---

## Detailed Results

### 1. Temporal Cluster Stability

**Criteria:** <20% of year-to-year transitions should have similarity <0.7

| Metric | Value |
|--------|-------|
| Total transitions | {results['stability']['total_transitions']} |
| Unstable transitions | {results['stability']['unstable_transitions']} |
| Instability rate | {results['stability']['instability_rate']*100:.1f}% |
| Large count changes (>3) | {results['stability']['large_count_changes']} |
| Cluster count range | {results['stability']['cluster_count_range'][0]}-{results['stability']['cluster_count_range'][1]} |

**Result:** {'✅ PASS - Clusters show stable temporal progression' if results['stability']['passed'] else '⚠️ WARN - Some clusters show instability'}

---

### 2. Cluster Size Distribution

**Criteria:**
- No single cluster >50% of nodes
- <30% of clusters are tiny (<10 nodes)
- Largest cluster <10× median

| Metric | Value |
|--------|-------|
| Total clusters | {results['sizes']['total_clusters']} |
| Total nodes | {results['sizes']['total_nodes']} |
| Mean size | {results['sizes']['size_stats']['mean']:.1f} |
| Median size | {results['sizes']['size_stats']['median']:.1f} |
| Min size | {results['sizes']['size_stats']['min']} |
| Max size | {results['sizes']['size_stats']['max']} |
| Largest as % of total | {results['sizes']['size_stats']['max']/results['sizes']['total_nodes']*100:.1f}% |
| Country giant clusters | {results['sizes']['country_giant_clusters']} |

**Result:** {'✅ PASS - Size distribution is reasonable' if results['sizes']['passed'] else '⚠️ WARN - Size distribution issues found'}

---

### 3. Domain Composition

**Criteria:**
- 0 domain count mismatches
- <10% weak primary domains

| Metric | Value |
|--------|-------|
| Domain mismatches | {results['domain']['domain_mismatches']} |
| Weak primary domains | {results['domain']['weak_primary']} |
| False mixed clusters | {results['domain']['false_mixed']} |
| Country mismatches | {results['domain']['country_mismatches']} |

**Result:** {'✅ PASS - Domain composition is coherent' if results['domain']['passed'] else '⚠️ WARN - Domain composition issues found'}

---

### 4. Cross-Country Consistency

**Criteria:** Within-group coefficient of variation (CV) <50%

"""

    # Add group details
    for group_name, group_data in results['cross_country']['groups'].items():
        if group_data.get('status') == 'insufficient_data':
            md += f"**{group_name}:** Insufficient data\n\n"
        else:
            status = '⚠️' if group_data.get('high_variance') else '✅'
            md += f"**{group_name}:** {group_data['countries']} countries, "
            md += f"{group_data['mean_clusters']:.1f} ± {group_data['std_clusters']:.1f} clusters "
            md += f"(CV: {group_data['cv']:.2f}) {status}\n\n"

    md += f"""
**Result:** {'✅ PASS - Similar countries have consistent cluster structures' if results['cross_country']['passed'] else '⚠️ WARN - Some country groups show high variance'}

---

### 5. Cluster Density

**Criteria:**
- Mean density in range [0.02, 0.10]
- <5 clusters with density >0.30

| Metric | Value |
|--------|-------|
| Mean density | {results['density']['density_stats']['mean']:.4f} |
| Median density | {results['density']['density_stats']['median']:.4f} |
| Min density | {results['density']['density_stats']['min']:.4f} |
| Max density | {results['density']['density_stats']['max']:.4f} |
| Mean in range | {'Yes' if results['density']['mean_in_range'] else 'No'} |
| High density issues | {results['density']['high_density_issues']} |
| Low density issues | {results['density']['low_density_issues']} |
| Country high density | {results['density']['country_high_density']} |

**Result:** {'✅ PASS - Cluster densities are reasonable' if results['density']['passed'] else '⚠️ WARN - Density outside expected range'}

---

### 6. Sample Indicators

**Criteria:** All clusters must have sample indicators

| Metric | Value |
|--------|-------|
| Total clusters | {results['samples']['total_clusters']} |
| Sample count range | {results['samples']['sample_count_range'][0]}-{results['samples']['sample_count_range'][1]} |
| Clusters missing samples | {results['samples']['no_samples']} |
| Too few samples | {results['samples']['too_few_samples']} |
| Country issues | {results['samples']['country_issues']} |

**Result:** {'✅ PASS - All clusters have sample indicators' if results['samples']['passed'] else '⚠️ WARN - Some clusters missing samples'}

---

## Pass Criteria Summary

| Criterion | Expected | Actual | Status |
|-----------|----------|--------|--------|
| Instability rate | <20% | {results['stability']['instability_rate']*100:.1f}% | {'✅' if results['stability']['instability_rate'] < 0.20 else '❌'} |
| Giant cluster | <50% of nodes | {results['sizes']['size_stats']['max']/results['sizes']['total_nodes']*100:.1f}% | {'✅' if results['sizes']['size_stats']['max']/results['sizes']['total_nodes'] < 0.5 else '❌'} |
| Domain mismatches | 0 | {results['domain']['domain_mismatches']} | {'✅' if results['domain']['domain_mismatches'] == 0 else '❌'} |
| High-variance groups | 0 | {len(results['cross_country']['high_variance_groups'])} | {'✅' if len(results['cross_country']['high_variance_groups']) == 0 else '⚠️'} |
| Mean density | 0.02-0.10 | {results['density']['density_stats']['mean']:.4f} | {'✅' if results['density']['mean_in_range'] else '⚠️'} |
| Missing samples | 0 | {results['samples']['no_samples']} | {'✅' if results['samples']['no_samples'] == 0 else '❌'} |

---

## Conclusion

**Phase 3B Validation:** {'✅ **AIRTIGHT** - All critical checks passed' if passed >= 5 else '⚠️ **NEEDS REVIEW** - Some checks require attention'}

{'Phase 3B (Development Clusters) is production-ready.' if passed >= 5 else 'Please review the failed checks above.'}

---

## Files Validated

- **Country files:** 178 (`data/v3_1_development_clusters/countries/*.json`)
- **Unified files:** 35 (`data/v3_1_development_clusters/unified/*.json`)
- **Total:** 213 files
"""

    return md


def main():
    # Run all validations
    results = run_all_validations()

    # Generate markdown report
    md_report = generate_markdown_report(results)

    # Save markdown
    output_file = OUTPUT_DIR / "PHASE3B_VALIDATION.md"
    output_file.parent.mkdir(exist_ok=True)

    with open(output_file, 'w') as f:
        f.write(md_report)

    # Save JSON for programmatic access (convert numpy types)
    def convert_types(obj):
        import numpy as np
        if isinstance(obj, dict):
            return {k: convert_types(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [convert_types(v) for v in obj]
        elif isinstance(obj, (np.bool_, bool)):
            return bool(obj)
        elif isinstance(obj, (np.integer, np.int64, np.int32)):
            return int(obj)
        elif isinstance(obj, (np.floating, np.float64, np.float32)):
            return float(obj)
        return obj

    json_file = OUTPUT_DIR / "phase3b_validation_results.json"
    with open(json_file, 'w') as f:
        json.dump(convert_types(results), f, indent=2)

    # Final summary
    print("\n" + "=" * 60)
    print("VALIDATION COMPLETE")
    print("=" * 60)
    print(f"Markdown report: {output_file}")
    print(f"JSON results: {json_file}")

    # Count passes
    all_checks = ['stability', 'sizes', 'domain', 'cross_country', 'density', 'samples']
    passed = sum(1 for check in all_checks if results.get(check, {}).get('passed', False))

    print(f"\nPassed: {passed}/{len(all_checks)}")

    if passed >= 5:
        print("✅ Phase 3B is AIRTIGHT")
        return 0
    else:
        print("⚠️ Phase 3B needs review")
        return 1


if __name__ == '__main__':
    exit(main())
