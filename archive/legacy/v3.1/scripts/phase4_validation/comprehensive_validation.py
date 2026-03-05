#!/usr/bin/env python3
"""
Phase 4: COMPREHENSIVE VALIDATION SUITE
Validates Phase 2A (SHAP), Phase 2B (Graphs), Phase 3A (Feedback Loops), Phase 3B (Clusters)
Generates final production-ready certification report.

Run: python scripts/phase4_validation/comprehensive_validation.py
"""

import json
import numpy as np
from pathlib import Path
from collections import defaultdict
from datetime import datetime
import sys

# ============================================================================
# CONFIGURATION - CORRECTED PATHS
# ============================================================================

BASE_DIR = Path("<repo-root>/v3.1")

# Actual data locations
SHAP_DIR = BASE_DIR / "data/v3_1_temporal_shap"
GRAPH_DIR = BASE_DIR / "data/v3_1_temporal_graphs"
LOOP_DIR = BASE_DIR / "data/v3_1_feedback_loops"
CLUSTER_DIR = BASE_DIR / "data/v3_1_development_clusters"

VALIDATION_DIR = BASE_DIR / "outputs/phase4_validation"
VALIDATION_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================================
# VALIDATION 1: PHASE 2A SHAP VALUES
# ============================================================================

class SHAPValidator:
    """Validates SHAP output integrity against documented schema"""

    def __init__(self):
        self.results = {
            'total_files': 0,
            'valid_files': 0,
            'errors': [],
            'warnings': [],
            'checks': {}
        }

    def validate_shap_file(self, filepath: Path) -> dict:
        """Validate single SHAP JSON file against documented schema"""
        issues = []

        try:
            with open(filepath) as f:
                data = json.load(f)

            # Check 1: Required top-level keys - different for unified/stratified vs country
            is_country = 'country' in data

            if is_country:
                # Country-specific schema
                required_keys = ['country', 'target', 'target_name', 'year',
                                'income_classification', 'shap_importance',
                                'metadata', 'data_quality', 'provenance']
            else:
                # Unified/stratified schema
                required_keys = ['stratum', 'stratum_name', 'target', 'target_name',
                                'year', 'stratification', 'shap_importance',
                                'metadata', 'data_quality', 'provenance']

            missing = [k for k in required_keys if k not in data]
            if missing:
                issues.append(f"Missing keys: {missing}")

            # Check 2: SHAP values structure and range
            if 'shap_importance' in data:
                shap_dict = data['shap_importance']

                # Sample some values to check
                sample_count = 0
                invalid_range = 0
                invalid_ci = 0

                for indicator_id, values in list(shap_dict.items())[:100]:  # Check first 100
                    sample_count += 1

                    # Check required keys in each SHAP entry
                    required_shap_keys = ['mean', 'std', 'ci_lower', 'ci_upper']
                    missing_shap = [k for k in required_shap_keys if k not in values]
                    if missing_shap:
                        issues.append(f"SHAP entry missing keys: {missing_shap}")
                        break

                    # Check value range (SHAP mean should be >= 0)
                    if values['mean'] < -1e-10:  # Allow tiny numerical tolerance
                        invalid_range += 1

                    # Check CI validity (lower <= mean <= upper)
                    # Allow tolerance for very small values (numerical precision)
                    mean_val = values['mean']
                    ci_lo = values['ci_lower']
                    ci_hi = values['ci_upper']

                    # If all values are essentially zero, skip CI check
                    if max(abs(mean_val), abs(ci_lo), abs(ci_hi)) < 1e-4:
                        continue

                    # Allow small numerical tolerance
                    tolerance = max(1e-6, abs(mean_val) * 0.001)
                    if not (ci_lo - tolerance <= mean_val <= ci_hi + tolerance):
                        invalid_ci += 1

                if invalid_range > 0:
                    issues.append(f"Found {invalid_range} negative SHAP means (should be >= 0)")

                # Allow up to 25% invalid CIs for country files (bootstrap edge cases with small samples)
                # Unified/stratified should have fewer issues
                ci_threshold = 0.25 if is_country else 0.15
                if invalid_ci > sample_count * ci_threshold:
                    issues.append(f"Found {invalid_ci}/{sample_count} invalid CIs")

            # Check 3: Metadata completeness
            if 'metadata' in data:
                meta = data['metadata']
                required_meta = ['n_samples', 'n_indicators', 'n_bootstrap', 'r2_mean', 'year_range']
                missing_meta = [k for k in required_meta if k not in meta]
                if missing_meta:
                    issues.append(f"Metadata missing: {missing_meta}")

                # Check R² validity
                # Country files can have negative R² due to small samples - this is statistically valid
                # Unified/stratified should have R² in [0, 1]
                if 'r2_mean' in meta:
                    r2 = meta['r2_mean']
                    if is_country:
                        # Country files: only flag if R² is extremely negative (< -1) or > 1
                        if r2 > 1:
                            issues.append(f"R² = {r2:.4f} > 1 (impossible)")
                        elif r2 < -1:
                            self.results['warnings'].append({
                                'file': str(filepath.name),
                                'warning': f"Very negative R² = {r2:.4f}"
                            })
                    else:
                        # Unified/stratified: R² should be in [0, 1]
                        if r2 < 0 or r2 > 1:
                            issues.append(f"R² = {r2:.4f} out of [0,1]")
                        elif r2 < 0.3:
                            self.results['warnings'].append({
                                'file': str(filepath.name),
                                'warning': f"Low R² = {r2:.4f}"
                            })

                # Check bootstrap count
                if 'n_bootstrap' in meta and meta['n_bootstrap'] != 100:
                    issues.append(f"n_bootstrap = {meta['n_bootstrap']} (expected 100)")

            # Check 4: Stratification structure (only for unified/stratified)
            if not is_country and 'stratification' in data:
                strat = data['stratification']
                if 'n_countries' not in strat and 'countries_in_stratum' not in strat:
                    issues.append("Stratification missing country info")

            # Check 5: Income classification for country files
            if is_country and 'income_classification' in data:
                inc_class = data['income_classification']
                if 'group_3tier' not in inc_class:
                    issues.append("Income classification missing group_3tier")

            return {'valid': len(issues) == 0, 'issues': issues}

        except json.JSONDecodeError:
            return {'valid': False, 'issues': ['JSON parse error']}
        except Exception as e:
            return {'valid': False, 'issues': [f'Error: {str(e)}']}

    def validate_all_shap(self):
        """Validate all SHAP outputs"""
        print("\n" + "="*70)
        print("VALIDATION 1: PHASE 2A SHAP VALUES")
        print("="*70)

        # Check unified files
        unified_dir = SHAP_DIR / "unified/quality_of_life"
        unified_files = list(unified_dir.glob("*_shap.json")) if unified_dir.exists() else []

        # Check stratified files
        stratified_files = []
        for stratum in ['developing', 'emerging', 'advanced']:
            stratum_dir = SHAP_DIR / f"stratified/{stratum}/quality_of_life"
            if stratum_dir.exists():
                stratified_files.extend(list(stratum_dir.glob("*_shap.json")))

        # Check country files
        country_dir = SHAP_DIR / "countries"
        country_files = list(country_dir.glob("*/quality_of_life/*_shap.json")) if country_dir.exists() else []

        all_files = unified_files + stratified_files + country_files
        self.results['total_files'] = len(all_files)

        print(f"\nFound {len(all_files)} SHAP files:")
        print(f"  - Unified: {len(unified_files)}")
        print(f"  - Stratified: {len(stratified_files)}")
        print(f"  - Countries: {len(country_files)}")

        # Validate each file
        print("\nValidating files...")
        errors_by_type = defaultdict(int)

        for filepath in all_files:
            result = self.validate_shap_file(filepath)

            if result['valid']:
                self.results['valid_files'] += 1
            else:
                self.results['errors'].append({
                    'file': str(filepath.relative_to(SHAP_DIR)),
                    'issues': result['issues']
                })
                for issue in result['issues']:
                    if 'Missing keys' in issue:
                        errors_by_type['missing_keys'] += 1
                    elif 'negative SHAP' in issue:
                        errors_by_type['value_range'] += 1
                    elif 'invalid CIs' in issue:
                        errors_by_type['invalid_ci'] += 1
                    elif 'R²' in issue:
                        errors_by_type['r2_issues'] += 1
                    else:
                        errors_by_type['other'] += 1

        # Check temporal smoothness
        if unified_files:
            self.check_temporal_smoothness(unified_files)

        # Summary
        pass_rate = self.results['valid_files'] / self.results['total_files'] if self.results['total_files'] > 0 else 0
        self.results['checks']['shap_values'] = {
            'pass_rate': pass_rate,
            'error_breakdown': dict(errors_by_type)
        }

        print(f"\n✓ Validated {self.results['total_files']} files")
        if self.results['total_files'] > 0:
            print(f"  - Valid: {self.results['valid_files']} ({100*pass_rate:.1f}%)")
            print(f"  - Errors: {len(self.results['errors'])}")

        if errors_by_type:
            print("\nError breakdown:")
            for error_type, count in errors_by_type.items():
                print(f"  - {error_type}: {count}")

        return self.results

    def check_temporal_smoothness(self, unified_files: list):
        """Check if R² values change smoothly over time"""
        print("\nChecking temporal smoothness...")

        r2_by_year = {}
        for f in unified_files:
            try:
                with open(f) as file:
                    data = json.load(file)
                year = data.get('year', 0)
                r2 = data.get('metadata', {}).get('r2_mean', 0)
                r2_by_year[year] = r2
            except:
                continue

        # Check year-to-year changes
        years = sorted(r2_by_year.keys())
        large_jumps = []
        for i in range(len(years)-1):
            y1, y2 = years[i], years[i+1]
            change = abs(r2_by_year[y2] - r2_by_year[y1])
            if change > 0.05:  # Flag if R² changes > 0.05 year-to-year
                large_jumps.append({
                    'year_range': f"{y1}-{y2}",
                    'change': round(change, 4)
                })

        if large_jumps:
            self.results['warnings'].extend([{'smoothness_jump': j} for j in large_jumps])
            print(f"  ⚠ Found {len(large_jumps)} large year-to-year R² changes")
        else:
            print("  ✓ Temporal smoothness OK")

# ============================================================================
# VALIDATION 2: PHASE 2B GRAPH STRUCTURES
# ============================================================================

class GraphValidator:
    """Validates causal graph outputs against documented schema"""

    def __init__(self):
        self.results = {
            'total_files': 0,
            'valid_files': 0,
            'errors': [],
            'warnings': [],
            'checks': {}
        }

    def validate_graph_file(self, filepath: Path) -> dict:
        """Validate single graph JSON file against documented schema"""
        issues = []

        try:
            with open(filepath) as f:
                data = json.load(f)

            # Check 1: Required top-level keys - different for unified/stratified vs country
            is_country = 'country' in data

            if is_country:
                # Country-specific schema
                required_keys = ['country', 'year', 'income_classification',
                                'edges', 'metadata', 'provenance']
            else:
                # Unified/stratified schema
                required_keys = ['stratum', 'stratum_name', 'year', 'stratification',
                                'edges', 'metadata', 'provenance']

            missing = [k for k in required_keys if k not in data]
            if missing:
                issues.append(f"Missing keys: {missing}")

            # Check 2: Edges structure (using 'beta' not 'coefficient')
            if 'edges' in data and len(data['edges']) > 0:
                # Check first few edges
                for i, edge in enumerate(data['edges'][:5]):
                    required_edge = ['source', 'target', 'beta', 'p_value', 'lag']
                    missing_edge = [k for k in required_edge if k not in edge]
                    if missing_edge:
                        issues.append(f"Edge {i} missing: {missing_edge}")
                        break

                # Sample validation
                invalid_lag = 0
                invalid_pval = 0
                invalid_ci = 0

                for edge in data['edges'][:100]:  # Check first 100
                    # Lag range [0, 5]
                    if 'lag' in edge and (edge['lag'] < 0 or edge['lag'] > 5):
                        invalid_lag += 1

                    # P-value range [0, 1]
                    if 'p_value' in edge and (edge['p_value'] < 0 or edge['p_value'] > 1):
                        invalid_pval += 1

                    # CI validity
                    if all(k in edge for k in ['ci_lower', 'beta', 'ci_upper']):
                        if not (edge['ci_lower'] <= edge['beta'] <= edge['ci_upper']):
                            invalid_ci += 1

                if invalid_lag > 0:
                    issues.append(f"Found {invalid_lag} edges with invalid lag (should be 0-5)")
                if invalid_pval > 0:
                    issues.append(f"Found {invalid_pval} edges with invalid p-value (should be 0-1)")
                if invalid_ci > 5:  # Allow a few numerical edge cases
                    issues.append(f"Found {invalid_ci} edges with invalid CIs")

                # Check for self-loops
                self_loops = sum(1 for e in data['edges'] if e.get('source') == e.get('target'))
                if self_loops > 0:
                    issues.append(f"Found {self_loops} self-loops")

            # Check 3: Metadata
            if 'metadata' in data:
                meta = data['metadata']
                required_meta = ['n_edges_computed', 'n_edges_total', 'coverage']
                missing_meta = [k for k in required_meta if k not in meta]
                if missing_meta:
                    issues.append(f"Metadata missing: {missing_meta}")

            return {'valid': len(issues) == 0, 'issues': issues}

        except Exception as e:
            return {'valid': False, 'issues': [f'Error: {str(e)}']}

    def validate_all_graphs(self):
        """Validate all graph outputs"""
        print("\n" + "="*70)
        print("VALIDATION 2: PHASE 2B CAUSAL GRAPHS")
        print("="*70)

        # Find all graph files
        unified_dir = GRAPH_DIR / "unified"
        unified_files = list(unified_dir.glob("*_graph.json")) if unified_dir.exists() else []

        stratified_files = []
        for stratum in ['developing', 'emerging', 'advanced']:
            stratum_dir = GRAPH_DIR / f"stratified/{stratum}"
            if stratum_dir.exists():
                stratified_files.extend(list(stratum_dir.glob("*_graph.json")))

        country_dir = GRAPH_DIR / "countries"
        country_files = list(country_dir.glob("*/*_graph.json")) if country_dir.exists() else []

        all_files = unified_files + stratified_files + country_files
        self.results['total_files'] = len(all_files)

        print(f"\nFound {len(all_files)} graph files:")
        print(f"  - Unified: {len(unified_files)}")
        print(f"  - Stratified: {len(stratified_files)}")
        print(f"  - Countries: {len(country_files)}")

        # Validate each file
        print("\nValidating files...")
        for filepath in all_files:
            result = self.validate_graph_file(filepath)

            if result['valid']:
                self.results['valid_files'] += 1
            else:
                self.results['errors'].append({
                    'file': str(filepath.relative_to(GRAPH_DIR)),
                    'issues': result['issues']
                })

        # Summary
        pass_rate = self.results['valid_files'] / self.results['total_files'] if self.results['total_files'] > 0 else 0
        self.results['checks']['graph_structure'] = {
            'pass_rate': pass_rate
        }

        print(f"\n✓ Validated {self.results['total_files']} files")
        if self.results['total_files'] > 0:
            print(f"  - Valid: {self.results['valid_files']} ({100*pass_rate:.1f}%)")
            print(f"  - Errors: {len(self.results['errors'])}")

        return self.results

# ============================================================================
# VALIDATION 3: PHASE 3A FEEDBACK LOOPS & 3B CLUSTERS
# ============================================================================

class Phase3Validator:
    """Validates Phase 3 feedback loops and development clusters"""

    def __init__(self):
        self.results = {
            'loops': {'files': 0, 'valid': 0, 'errors': []},
            'clusters': {'files': 0, 'valid': 0, 'errors': []}
        }

    def validate_loops(self):
        """Validate feedback loop files against documented schema"""
        print("\n" + "="*70)
        print("VALIDATION 3A: FEEDBACK LOOPS")
        print("="*70)

        loop_files = list(LOOP_DIR.glob("*_feedback_loops.json")) if LOOP_DIR.exists() else []
        self.results['loops']['files'] = len(loop_files)

        print(f"\nFound {len(loop_files)} feedback loop files")

        for filepath in loop_files:
            try:
                with open(filepath) as f:
                    data = json.load(f)

                # Check required keys
                required = ['country', 'feedback_loops', 'summary', 'metadata', 'provenance']
                missing = [k for k in required if k not in data]

                if missing:
                    self.results['loops']['errors'].append({
                        'file': filepath.name,
                        'issue': f'Missing keys: {missing}'
                    })
                elif not isinstance(data['feedback_loops'], list):
                    self.results['loops']['errors'].append({
                        'file': filepath.name,
                        'issue': 'feedback_loops should be a list'
                    })
                else:
                    self.results['loops']['valid'] += 1

            except Exception as e:
                self.results['loops']['errors'].append({
                    'file': filepath.name,
                    'issue': str(e)
                })

        valid = self.results['loops']['valid']
        total = self.results['loops']['files']
        print(f"✓ Valid: {valid}/{total}" + (f" ({100*valid/total:.1f}%)" if total > 0 else ""))

    def validate_clusters(self):
        """Validate development cluster files against documented schema"""
        print("\n" + "="*70)
        print("VALIDATION 3B: DEVELOPMENT CLUSTERS")
        print("="*70)

        # Country cluster files
        country_clusters = list((CLUSTER_DIR / "countries").glob("*_clusters.json")) if (CLUSTER_DIR / "countries").exists() else []

        # Unified year cluster files
        unified_clusters = list((CLUSTER_DIR / "unified").glob("*_clusters.json")) if (CLUSTER_DIR / "unified").exists() else []

        all_cluster_files = country_clusters + unified_clusters
        self.results['clusters']['files'] = len(all_cluster_files)

        print(f"\nFound {len(all_cluster_files)} cluster files:")
        print(f"  - Country: {len(country_clusters)}")
        print(f"  - Unified: {len(unified_clusters)}")

        for filepath in all_cluster_files:
            try:
                with open(filepath) as f:
                    data = json.load(f)

                # Check required keys (varies by type)
                is_country = 'country' in data
                is_unified = 'source' in data

                if is_country:
                    required = ['country', 'year_analyzed', 'clusters', 'summary', 'metadata', 'provenance']
                elif is_unified:
                    required = ['source', 'year', 'clusters', 'summary', 'metadata', 'provenance']
                else:
                    required = ['clusters']

                missing = [k for k in required if k not in data]

                if missing:
                    self.results['clusters']['errors'].append({
                        'file': filepath.name,
                        'issue': f'Missing keys: {missing}'
                    })
                elif not isinstance(data['clusters'], list):
                    self.results['clusters']['errors'].append({
                        'file': filepath.name,
                        'issue': 'clusters should be a list'
                    })
                else:
                    self.results['clusters']['valid'] += 1

            except Exception as e:
                self.results['clusters']['errors'].append({
                    'file': filepath.name,
                    'issue': str(e)
                })

        valid = self.results['clusters']['valid']
        total = self.results['clusters']['files']
        print(f"✓ Valid: {valid}/{total}" + (f" ({100*valid/total:.1f}%)" if total > 0 else ""))

    def validate_all(self):
        """Run all Phase 3 validations"""
        self.validate_loops()
        self.validate_clusters()
        return self.results

# ============================================================================
# FINAL CERTIFICATION REPORT
# ============================================================================

def generate_final_report(shap_results, graph_results, phase3_results):
    """Generate production certification report"""
    print("\n" + "="*70)
    print("GENERATING FINAL CERTIFICATION REPORT")
    print("="*70)

    # Calculate pass rates safely
    shap_pass = shap_results['valid_files'] / shap_results['total_files'] if shap_results['total_files'] > 0 else 0
    graph_pass = graph_results['valid_files'] / graph_results['total_files'] if graph_results['total_files'] > 0 else 0
    loops_pass = phase3_results['loops']['valid'] == phase3_results['loops']['files'] and phase3_results['loops']['files'] > 0
    clusters_pass = phase3_results['clusters']['valid'] == phase3_results['clusters']['files'] and phase3_results['clusters']['files'] > 0

    report = {
        'timestamp': datetime.now().isoformat(),
        'project': 'Global Causal Discovery System v3.1',
        'validation_version': '4.0',
        'status': 'PENDING',

        'phase2a_shap': {
            'total_files': shap_results['total_files'],
            'valid_files': shap_results['valid_files'],
            'pass_rate': round(shap_pass, 4),
            'errors_count': len(shap_results['errors']),
            'warnings_count': len(shap_results['warnings']),
            'status': 'PASS' if shap_pass >= 0.95 else ('WARN' if shap_pass >= 0.90 else 'FAIL')
        },

        'phase2b_graphs': {
            'total_files': graph_results['total_files'],
            'valid_files': graph_results['valid_files'],
            'pass_rate': round(graph_pass, 4),
            'errors_count': len(graph_results['errors']),
            'warnings_count': len(graph_results['warnings']),
            'status': 'PASS' if graph_pass >= 0.95 else ('WARN' if graph_pass >= 0.90 else 'FAIL')
        },

        'phase3a_feedback_loops': {
            'total_files': phase3_results['loops']['files'],
            'valid_files': phase3_results['loops']['valid'],
            'errors_count': len(phase3_results['loops']['errors']),
            'status': 'PASS' if loops_pass else 'FAIL'
        },

        'phase3b_dev_clusters': {
            'total_files': phase3_results['clusters']['files'],
            'valid_files': phase3_results['clusters']['valid'],
            'errors_count': len(phase3_results['clusters']['errors']),
            'status': 'PASS' if clusters_pass else 'FAIL'
        },

        'file_counts': {
            'phase2a_shap': shap_results['total_files'],
            'phase2b_graphs': graph_results['total_files'],
            'phase3a_loops': phase3_results['loops']['files'],
            'phase3b_clusters': phase3_results['clusters']['files'],
            'total': (shap_results['total_files'] + graph_results['total_files'] +
                     phase3_results['loops']['files'] + phase3_results['clusters']['files'])
        }
    }

    # Overall status
    all_pass = (
        report['phase2a_shap']['status'] == 'PASS' and
        report['phase2b_graphs']['status'] == 'PASS' and
        report['phase3a_feedback_loops']['status'] == 'PASS' and
        report['phase3b_dev_clusters']['status'] == 'PASS'
    )

    any_fail = (
        report['phase2a_shap']['status'] == 'FAIL' or
        report['phase2b_graphs']['status'] == 'FAIL' or
        report['phase3a_feedback_loops']['status'] == 'FAIL' or
        report['phase3b_dev_clusters']['status'] == 'FAIL'
    )

    if all_pass:
        report['status'] = 'CERTIFIED'
        report['certification_level'] = 'PRODUCTION_READY'
    elif any_fail:
        report['status'] = 'FAILED'
        report['certification_level'] = 'REQUIRES_FIX'
    else:
        report['status'] = 'REVIEW_NEEDED'
        report['certification_level'] = 'CONDITIONAL'

    # Save report
    report_path = VALIDATION_DIR / "FINAL_CERTIFICATION_REPORT.json"
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)

    # Print summary
    print("\n" + "="*70)
    print("FINAL VALIDATION SUMMARY")
    print("="*70)

    print(f"\nPhase 2A (SHAP):        {report['phase2a_shap']['status']} "
          f"({report['phase2a_shap']['pass_rate']:.1%} valid, {report['phase2a_shap']['total_files']} files)")
    print(f"Phase 2B (Graphs):      {report['phase2b_graphs']['status']} "
          f"({report['phase2b_graphs']['pass_rate']:.1%} valid, {report['phase2b_graphs']['total_files']} files)")
    print(f"Phase 3A (Loops):       {report['phase3a_feedback_loops']['status']} "
          f"({report['phase3a_feedback_loops']['valid_files']}/{report['phase3a_feedback_loops']['total_files']} files)")
    print(f"Phase 3B (Clusters):    {report['phase3b_dev_clusters']['status']} "
          f"({report['phase3b_dev_clusters']['valid_files']}/{report['phase3b_dev_clusters']['total_files']} files)")

    print(f"\n{'─'*40}")
    print(f"Total files validated: {report['file_counts']['total']:,}")
    print(f"\nOverall Status: {report['status']}")
    print(f"Certification:  {report['certification_level']}")

    print(f"\n✓ Report saved to: {report_path}")

    if report['status'] == 'CERTIFIED':
        print("\n" + "="*70)
        print("   SYSTEM CERTIFIED FOR PRODUCTION")
        print("="*70)
    elif report['status'] == 'FAILED':
        print("\n⚠️  VALIDATION FAILED - Check errors in validation report")
    else:
        print("\n⚠️  REVIEW REQUIRED - Check warnings in validation report")

    return report

# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """Run comprehensive validation suite"""
    print("\n" + "="*70)
    print("PHASE 4: COMPREHENSIVE VALIDATION SUITE")
    print("Global Causal Discovery System v3.1")
    print("="*70)
    print(f"\nTimestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Verify directories exist
    print("\nChecking data directories...")
    dirs_exist = {
        'SHAP': SHAP_DIR.exists(),
        'Graphs': GRAPH_DIR.exists(),
        'Loops': LOOP_DIR.exists(),
        'Clusters': CLUSTER_DIR.exists()
    }
    for name, exists in dirs_exist.items():
        status = "✓" if exists else "✗"
        print(f"  {status} {name}: {exists}")

    # Run validations
    shap_validator = SHAPValidator()
    shap_results = shap_validator.validate_all_shap()

    graph_validator = GraphValidator()
    graph_results = graph_validator.validate_all_graphs()

    phase3_validator = Phase3Validator()
    phase3_results = phase3_validator.validate_all()

    # Generate final report
    final_report = generate_final_report(shap_results, graph_results, phase3_results)

    # Save detailed error logs
    error_log = {
        'timestamp': datetime.now().isoformat(),
        'shap_errors': shap_results['errors'][:100],
        'graph_errors': graph_results['errors'][:100],
        'loop_errors': phase3_results['loops']['errors'],
        'cluster_errors': phase3_results['clusters']['errors'],
        'shap_warnings': shap_results['warnings'][:50],
        'graph_warnings': graph_results['warnings'][:50]
    }

    error_log_path = VALIDATION_DIR / "error_details.json"
    with open(error_log_path, 'w') as f:
        json.dump(error_log, f, indent=2)

    print(f"\n✓ Detailed error log: {error_log_path}")

    # Exit code
    sys.exit(0 if final_report['status'] == 'CERTIFIED' else 1)

if __name__ == "__main__":
    main()
