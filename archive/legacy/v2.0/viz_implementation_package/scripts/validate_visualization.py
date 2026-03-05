#!/usr/bin/env python3
"""
Visualization Package Validation Script

Validates the integrity and completeness of the visualization implementation package.

Usage:
    python validate_visualization.py

Author: V2.0 Global Causal Discovery Team
Date: November 21, 2025
"""

import json
import csv
from pathlib import Path
from typing import Dict, List, Tuple


class VisualizationValidator:
    """Validates visualization package data integrity."""

    def __init__(self, package_dir: Path):
        """
        Initialize validator.

        Args:
            package_dir: Path to viz_implementation_package directory
        """
        self.package_dir = package_dir
        self.data_dir = package_dir / 'data'
        self.results = []

    def run_all_checks(self) -> Tuple[int, int]:
        """
        Run all validation checks.

        Returns:
            Tuple of (passed_checks, total_checks)
        """
        print("=" * 80)
        print("VISUALIZATION PACKAGE VALIDATION")
        print("=" * 80)
        print()

        # File existence checks
        self._check_file_existence()

        # Schema integrity checks
        self._check_schema_integrity()

        # CSV consistency checks
        self._check_csv_consistency()

        # Graph integrity checks
        self._check_graph_integrity()

        # Metadata completeness checks
        self._check_metadata_completeness()

        # Print summary
        self._print_summary()

        passed = sum(1 for r in self.results if r['status'] == 'PASS')
        total = len(self.results)

        return passed, total

    def _check_file_existence(self):
        """Check all required files exist."""
        print("📁 Checking file existence...")

        required_files = [
            'data/causal_graph_v2_final.json',
            'data/causal_graph_v2.graphml',
            'data/mechanisms.csv',
            'data/outcomes.csv',
            'data/edges_full.csv',
            'data/data_dictionary.md',
            'scripts/generate_hierarchical_tree_ascii.py',
            'scripts/validate_visualization.py',
            'docs/PROJECT_COMPLETE.md',
            'docs/FINAL_PROJECT_VALIDATION.md',
            'README.md'
        ]

        for file_path in required_files:
            full_path = self.package_dir / file_path
            status = 'PASS' if full_path.exists() else 'FAIL'
            self.results.append({
                'check': f"File exists: {file_path}",
                'status': status,
                'detail': str(full_path) if status == 'PASS' else 'NOT FOUND'
            })

    def _check_schema_integrity(self):
        """Check JSON schema integrity."""
        print("📊 Checking schema integrity...")

        schema_path = self.data_dir / 'causal_graph_v2_final.json'

        try:
            with open(schema_path) as f:
                schema = json.load(f)

            # Check top-level keys
            required_keys = ['metadata', 'mechanisms', 'outcomes', 'graphs', 'dashboard_metadata']
            for key in required_keys:
                status = 'PASS' if key in schema else 'FAIL'
                self.results.append({
                    'check': f"Schema has '{key}' key",
                    'status': status,
                    'detail': f"Found" if status == 'PASS' else 'Missing'
                })

            # Check mechanisms count
            mech_count = len(schema.get('mechanisms', []))
            status = 'PASS' if mech_count == 290 else 'WARN'
            self.results.append({
                'check': "Mechanisms count = 290",
                'status': status,
                'detail': f"Found {mech_count}"
            })

            # Check outcomes count
            outcome_count = len(schema.get('outcomes', []))
            status = 'PASS' if outcome_count == 9 else 'WARN'
            self.results.append({
                'check': "Outcomes count = 9",
                'status': status,
                'detail': f"Found {outcome_count}"
            })

            # Check graph levels
            graphs = schema.get('graphs', {})
            expected_levels = ['full', 'professional', 'simplified']
            for level in expected_levels:
                status = 'PASS' if level in graphs else 'FAIL'
                self.results.append({
                    'check': f"Graph level '{level}' exists",
                    'status': status,
                    'detail': f"Nodes: {len(graphs.get(level, {}).get('nodes', []))}" if status == 'PASS' else 'Missing'
                })

        except Exception as e:
            self.results.append({
                'check': "Schema JSON parsing",
                'status': 'FAIL',
                'detail': str(e)
            })

    def _check_csv_consistency(self):
        """Check CSV file consistency with JSON schema."""
        print("📋 Checking CSV consistency...")

        try:
            # Load schema
            with open(self.data_dir / 'causal_graph_v2_final.json') as f:
                schema = json.load(f)

            # Check mechanisms.csv
            mech_csv_path = self.data_dir / 'mechanisms.csv'
            with open(mech_csv_path) as f:
                reader = csv.DictReader(f)
                mech_csv = list(reader)

            json_mech_count = len(schema['mechanisms'])
            csv_mech_count = len(mech_csv)
            status = 'PASS' if json_mech_count == csv_mech_count else 'WARN'
            self.results.append({
                'check': "Mechanisms: JSON count = CSV count",
                'status': status,
                'detail': f"JSON: {json_mech_count}, CSV: {csv_mech_count}"
            })

            # Check outcomes.csv
            outcome_csv_path = self.data_dir / 'outcomes.csv'
            with open(outcome_csv_path) as f:
                reader = csv.DictReader(f)
                outcome_csv = list(reader)

            json_outcome_count = len(schema['outcomes'])
            csv_outcome_count = len(outcome_csv)
            status = 'PASS' if json_outcome_count == csv_outcome_count else 'WARN'
            self.results.append({
                'check': "Outcomes: JSON count = CSV count",
                'status': status,
                'detail': f"JSON: {json_outcome_count}, CSV: {csv_outcome_count}"
            })

            # Check edges_full.csv
            edges_csv_path = self.data_dir / 'edges_full.csv'
            with open(edges_csv_path) as f:
                reader = csv.DictReader(f)
                edges_csv = list(reader)

            json_edges_count = len(schema['graphs']['full']['edges'])
            csv_edges_count = len(edges_csv)
            status = 'PASS' if json_edges_count == csv_edges_count else 'WARN'
            self.results.append({
                'check': "Edges (full): JSON count = CSV count",
                'status': status,
                'detail': f"JSON: {json_edges_count}, CSV: {csv_edges_count}"
            })

        except Exception as e:
            self.results.append({
                'check': "CSV consistency",
                'status': 'FAIL',
                'detail': str(e)
            })

    def _check_graph_integrity(self):
        """Check graph structural integrity."""
        print("🕸️  Checking graph integrity...")

        try:
            with open(self.data_dir / 'causal_graph_v2_final.json') as f:
                schema = json.load(f)

            # Check for orphan edges (edges referencing non-existent nodes)
            for graph_level in ['full', 'professional', 'simplified']:
                graph = schema['graphs'][graph_level]
                nodes = {node['id'] for node in graph['nodes']}
                edges = graph['edges']

                orphan_edges = []
                for edge in edges:
                    if edge['source'] not in nodes or edge['target'] not in nodes:
                        orphan_edges.append(edge)

                status = 'PASS' if len(orphan_edges) == 0 else 'FAIL'
                self.results.append({
                    'check': f"No orphan edges in '{graph_level}' graph",
                    'status': status,
                    'detail': f"Orphans: {len(orphan_edges)}"
                })

            # Check for duplicate edges
            for graph_level in ['full', 'professional', 'simplified']:
                graph = schema['graphs'][graph_level]
                edges = graph['edges']

                edge_pairs = [(e['source'], e['target']) for e in edges]
                unique_pairs = set(edge_pairs)

                status = 'PASS' if len(edge_pairs) == len(unique_pairs) else 'WARN'
                self.results.append({
                    'check': f"No duplicate edges in '{graph_level}' graph",
                    'status': status,
                    'detail': f"Total: {len(edge_pairs)}, Unique: {len(unique_pairs)}"
                })

        except Exception as e:
            self.results.append({
                'check': "Graph integrity",
                'status': 'FAIL',
                'detail': str(e)
            })

    def _check_metadata_completeness(self):
        """Check dashboard metadata completeness."""
        print("🎨 Checking metadata completeness...")

        try:
            with open(self.data_dir / 'causal_graph_v2_final.json') as f:
                schema = json.load(f)

            metadata = schema.get('dashboard_metadata', {})

            # Check filters
            filters = metadata.get('filters', {})
            required_filters = ['domains', 'subdomains', 'layers', 'shap_range', 'graph_level']
            for filter_type in required_filters:
                status = 'PASS' if filter_type in filters else 'FAIL'
                self.results.append({
                    'check': f"Filter exists: {filter_type}",
                    'status': status,
                    'detail': 'Found' if status == 'PASS' else 'Missing'
                })

            # Check tooltips
            tooltips = metadata.get('tooltips', [])
            expected_tooltip_count = len(schema['mechanisms']) + len(schema['outcomes'])
            status = 'PASS' if len(tooltips) == expected_tooltip_count else 'WARN'
            self.results.append({
                'check': "Tooltip count matches nodes",
                'status': status,
                'detail': f"Expected: {expected_tooltip_count}, Found: {len(tooltips)}"
            })

            # Check citations
            citations = metadata.get('citations', {})
            status = 'PASS' if 'sources' in citations and 'methods' in citations else 'FAIL'
            self.results.append({
                'check': "Citations include sources and methods",
                'status': status,
                'detail': f"Sources: {len(citations.get('sources', []))}, Methods: {len(citations.get('methods', []))}"
            })

        except Exception as e:
            self.results.append({
                'check': "Metadata completeness",
                'status': 'FAIL',
                'detail': str(e)
            })

    def _print_summary(self):
        """Print validation summary."""
        print()
        print("=" * 80)
        print("VALIDATION RESULTS")
        print("=" * 80)
        print()

        # Group by status
        passed = [r for r in self.results if r['status'] == 'PASS']
        warned = [r for r in self.results if r['status'] == 'WARN']
        failed = [r for r in self.results if r['status'] == 'FAIL']

        # Print failed checks
        if failed:
            print("❌ FAILED CHECKS:")
            for r in failed:
                print(f"  - {r['check']}: {r['detail']}")
            print()

        # Print warnings
        if warned:
            print("⚠️  WARNINGS:")
            for r in warned:
                print(f"  - {r['check']}: {r['detail']}")
            print()

        # Print summary
        print(f"✅ PASSED: {len(passed)}/{len(self.results)}")
        print(f"⚠️  WARNINGS: {len(warned)}/{len(self.results)}")
        print(f"❌ FAILED: {len(failed)}/{len(self.results)}")
        print()

        if len(failed) == 0:
            print("🎉 All critical checks passed! Package is ready for implementation.")
        else:
            print("⚠️  Some checks failed. Please review before implementation.")
        print()


def main():
    """Main entry point."""
    # Find package directory
    script_dir = Path(__file__).parent
    package_dir = script_dir.parent

    print(f"📦 Validating package at: {package_dir}")
    print()

    validator = VisualizationValidator(package_dir)
    passed, total = validator.run_all_checks()

    # Exit code
    exit_code = 0 if passed == total else 1
    return exit_code


if __name__ == '__main__':
    exit(main())
