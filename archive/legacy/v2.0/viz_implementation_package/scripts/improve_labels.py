#!/usr/bin/env python3
"""
Label Improvement Script

Fetches proper indicator names from source APIs and updates the schema.

Usage:
    python improve_labels.py --source wdi
    python improve_labels.py --source all --output improved_schema.json

Author: V2.0 Global Causal Discovery Team
Date: November 21, 2025
"""

import argparse
import json
import requests
import time
from pathlib import Path
from typing import Dict, List


def fetch_wdi_label(code: str) -> Dict[str, str]:
    """
    Fetch World Bank WDI indicator name.

    Args:
        code: Indicator code (e.g., 'wdi_mobile')

    Returns:
        Dict with 'label' and 'description' keys
    """
    # Remove 'wdi_' prefix and convert to uppercase
    wdi_id = code.replace('wdi_', '').upper()

    url = f"https://api.worldbank.org/v2/indicator/{wdi_id}?format=json"

    try:
        response = requests.get(url, timeout=10)
        if response.ok:
            data = response.json()
            if len(data) > 1 and data[1]:
                indicator = data[1][0]
                return {
                    'label': indicator.get('name', code),
                    'description': indicator.get('sourceNote', ''),
                    'source': indicator.get('source', {}).get('value', 'World Bank WDI')
                }
    except Exception as e:
        print(f"    Error: {e}")

    return {'label': code, 'description': '', 'source': 'World Bank WDI'}


def improve_wdi_labels(schema: dict, verbose: bool = True) -> dict:
    """
    Improve all World Bank WDI labels by fetching from API.

    Args:
        schema: The causal graph schema
        verbose: Print progress

    Returns:
        Updated schema
    """
    wdi_mechanisms = [m for m in schema['mechanisms'] if m['id'].startswith('wdi_')]

    if verbose:
        print(f"\n📊 Improving {len(wdi_mechanisms)} WDI labels...")
        print(f"   (Estimated time: {len(wdi_mechanisms) * 0.5 / 60:.1f} minutes)")

    improved = 0
    failed = 0

    for i, mech in enumerate(wdi_mechanisms, 1):
        code = mech['id']

        if verbose:
            print(f"  [{i}/{len(wdi_mechanisms)}] {code}... ", end='', flush=True)

        result = fetch_wdi_label(code)

        if result['label'] != code and len(result['label']) > len(code):
            mech['label'] = result['label']
            mech['label_quality'] = 'good'
            if result['description']:
                mech['description'] = result['description']
            improved += 1
            if verbose:
                label_preview = result['label'][:60] + ('...' if len(result['label']) > 60 else '')
                print(f"✅ {label_preview}")
        else:
            failed += 1
            if verbose:
                print(f"❌ Not found")

        # Rate limiting
        time.sleep(0.5)

    if verbose:
        print(f"\n✅ Improved: {improved}/{len(wdi_mechanisms)} ({improved/len(wdi_mechanisms)*100:.1f}%)")
        print(f"❌ Failed: {failed}/{len(wdi_mechanisms)} ({failed/len(wdi_mechanisms)*100:.1f}%)")

    return schema


def export_poor_labels(schema: dict, output_path: str):
    """
    Export all poor-quality labels to CSV for manual review.

    Args:
        schema: The causal graph schema
        output_path: Output CSV file path
    """
    poor_labels = [
        {
            'id': m['id'],
            'current_label': m['label'],
            'domain': m['domain'],
            'source': m.get('source', 'Unknown'),
            'description': m.get('description', ''),
            'improved_label': ''  # For manual entry
        }
        for m in schema['mechanisms']
        if m.get('label_quality') == 'poor'
    ]

    import csv
    with open(output_path, 'w', newline='') as f:
        if poor_labels:
            writer = csv.DictWriter(f, fieldnames=poor_labels[0].keys())
            writer.writeheader()
            writer.writerows(poor_labels)

    print(f"\n📋 Exported {len(poor_labels)} poor labels to {output_path}")
    print(f"   Review and fill in 'improved_label' column, then use --import-csv")


def import_improved_labels(schema: dict, csv_path: str) -> dict:
    """
    Import manually improved labels from CSV.

    Args:
        schema: The causal graph schema
        csv_path: Path to CSV with improved labels

    Returns:
        Updated schema
    """
    import csv

    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        improved_map = {
            row['id']: row['improved_label']
            for row in reader
            if row['improved_label'].strip()
        }

    updated = 0
    for mech in schema['mechanisms']:
        if mech['id'] in improved_map:
            new_label = improved_map[mech['id']]
            if new_label != mech['label']:
                mech['label'] = new_label
                mech['label_quality'] = 'good'
                updated += 1

    print(f"\n✅ Updated {updated} labels from CSV")

    return schema


def validate_labels(schema: dict):
    """
    Validate label quality and print summary.

    Args:
        schema: The causal graph schema
    """
    total = len(schema['mechanisms'])
    good = sum(1 for m in schema['mechanisms'] if m.get('label_quality') == 'good')
    poor = total - good

    print(f"\n📊 Label Quality Summary:")
    print(f"   Total mechanisms: {total}")
    print(f"   Good labels: {good} ({good/total*100:.1f}%)")
    print(f"   Poor labels: {poor} ({poor/total*100:.1f}%)")

    # By source
    by_source = {}
    for m in schema['mechanisms']:
        source = m.get('source', 'Unknown')
        if source not in by_source:
            by_source[source] = {'total': 0, 'good': 0}
        by_source[source]['total'] += 1
        if m.get('label_quality') == 'good':
            by_source[source]['good'] += 1

    print(f"\n📊 By Source:")
    for source, counts in sorted(by_source.items()):
        pct = counts['good'] / counts['total'] * 100
        print(f"   {source}: {counts['good']}/{counts['total']} ({pct:.1f}%)")


def main():
    parser = argparse.ArgumentParser(
        description="Improve indicator labels by fetching from source APIs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Improve World Bank WDI labels only
  python improve_labels.py --source wdi

  # Export poor labels for manual review
  python improve_labels.py --export-csv poor_labels.csv

  # Import manually improved labels
  python improve_labels.py --import-csv poor_labels_IMPROVED.csv

  # Improve all sources (if implemented)
  python improve_labels.py --source all
        """
    )

    parser.add_argument(
        '--source',
        choices=['wdi', 'vdem', 'who', 'all'],
        default='wdi',
        help='Which source to improve (currently only WDI implemented)'
    )
    parser.add_argument(
        '--output',
        type=str,
        default='causal_graph_v2_final_IMPROVED.json',
        help='Output file name (saved to data/ directory)'
    )
    parser.add_argument(
        '--export-csv',
        type=str,
        help='Export poor labels to CSV for manual review'
    )
    parser.add_argument(
        '--import-csv',
        type=str,
        help='Import manually improved labels from CSV'
    )
    parser.add_argument(
        '--validate',
        action='store_true',
        help='Only validate label quality (no changes)'
    )
    parser.add_argument(
        '--quiet',
        action='store_true',
        help='Suppress progress output'
    )

    args = parser.parse_args()

    # Find schema file
    script_dir = Path(__file__).parent
    schema_path = script_dir.parent / 'data' / 'causal_graph_v2_final.json'

    if not schema_path.exists():
        print(f"❌ Error: Schema file not found at {schema_path}")
        return 1

    # Load schema
    with open(schema_path, 'r') as f:
        schema = json.load(f)

    verbose = not args.quiet

    # Validate only mode
    if args.validate:
        validate_labels(schema)
        return 0

    # Export poor labels mode
    if args.export_csv:
        export_poor_labels(schema, args.export_csv)
        return 0

    # Import improved labels mode
    if args.import_csv:
        schema = import_improved_labels(schema, args.import_csv)
        validate_labels(schema)

        # Save
        output_path = script_dir.parent / 'data' / args.output
        with open(output_path, 'w') as f:
            json.dump(schema, f, indent=2)

        print(f"\n✅ Saved improved schema to {output_path}")
        return 0

    # Improve labels mode
    print(f"🔧 Improving labels from source: {args.source}")

    if args.source in ['wdi', 'all']:
        schema = improve_wdi_labels(schema, verbose=verbose)

    if args.source in ['vdem', 'all']:
        print(f"\n⚠️  V-Dem fetcher not yet implemented")
        print(f"    Use --export-csv to manually review V-Dem labels")

    if args.source in ['who', 'all']:
        print(f"\n⚠️  WHO fetcher not yet implemented")
        print(f"    Use --export-csv to manually review WHO labels")

    # Validate results
    validate_labels(schema)

    # Save
    output_path = script_dir.parent / 'data' / args.output
    with open(output_path, 'w') as f:
        json.dump(schema, f, indent=2)

    print(f"\n✅ Saved improved schema to {output_path}")
    print(f"\nNext steps:")
    print(f"  1. Review improved labels in {output_path}")
    print(f"  2. If satisfied, replace causal_graph_v2_final.json with improved version")
    print(f"  3. For remaining poor labels, use --export-csv for manual review")

    return 0


if __name__ == '__main__':
    exit(main())
