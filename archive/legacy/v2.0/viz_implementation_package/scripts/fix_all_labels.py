#!/usr/bin/env python3
"""
Fix All Labels - Comprehensive Label Improvement Script

This script:
1. Loads mechanism IDs from the schema
2. Loads all indicator databases (WDI, UNESCO, WHO, IMF, UNICEF, HDR)
3. Creates comprehensive mapping from IDs to full names
4. Updates the schema with improved labels
5. Generates quality report

Target: 80%+ good labels (up from current 30%)
"""

import json
import pandas as pd
import pickle
from pathlib import Path
from typing import Dict, List, Tuple
import re

# Paths
PROJECT_ROOT = Path("<repo-root>/v2.0")
INDICATORS_DIR = PROJECT_ROOT / "indicators"
VIZ_DIR = PROJECT_ROOT / "viz_implementation_package"
SCHEMA_PATH = VIZ_DIR / "data" / "causal_graph_v2_final.json"
OUTPUT_PATH = VIZ_DIR / "data" / "causal_graph_v2_final.json"

# Indicator database files
INDICATOR_FILES = {
    'wdi': INDICATORS_DIR / "world_bank_indicators.csv",
    'unesco': INDICATORS_DIR / "UISIndicators.csv",
    'who': INDICATORS_DIR / "WHO Global Health Observatory (GHO).csv",
    'imf': INDICATORS_DIR / "IMFIndicators.csv",
    'unicef': INDICATORS_DIR / "unicef_indicators_list.csv",
    'hdr': INDICATORS_DIR / "HumanDevReportIndicators.csv"
}


class LabelFixer:
    def __init__(self):
        self.indicator_databases = {}
        self.schema = None
        self.improvements = 0
        self.total_mechanisms = 0

    def load_schema(self):
        """Load the visualization schema"""
        print(f"Loading schema from {SCHEMA_PATH}")
        with open(SCHEMA_PATH, 'r') as f:
            self.schema = json.load(f)
        self.total_mechanisms = len(self.schema['mechanisms'])
        print(f"Loaded schema with {self.total_mechanisms} mechanisms")

    def load_indicator_databases(self):
        """Load all indicator databases into memory"""
        print("\n=== Loading Indicator Databases ===")

        # World Bank WDI
        if INDICATOR_FILES['wdi'].exists():
            print(f"Loading WDI indicators...")
            df = pd.read_csv(INDICATOR_FILES['wdi'])
            # Columns: id, name, source, topics, sourceNote, sourceOrganization
            self.indicator_databases['wdi'] = dict(zip(df['id'], df['name']))
            print(f"  Loaded {len(self.indicator_databases['wdi']):,} WDI indicators")

        # UNESCO UIS
        if INDICATOR_FILES['unesco'].exists():
            print(f"Loading UNESCO indicators...")
            df = pd.read_csv(INDICATOR_FILES['unesco'])
            # Columns: indicatorCode, name, theme, ...
            if 'indicatorCode' in df.columns and 'name' in df.columns:
                self.indicator_databases['unesco'] = dict(zip(df['indicatorCode'].astype(str), df['name']))
                print(f"  Loaded {len(self.indicator_databases['unesco']):,} UNESCO indicators")

        # WHO GHO
        if INDICATOR_FILES['who'].exists():
            print(f"Loading WHO indicators...")
            df = pd.read_csv(INDICATOR_FILES['who'])
            # Columns: value__IndicatorCode, value__IndicatorName, value__Language
            if 'value__IndicatorCode' in df.columns and 'value__IndicatorName' in df.columns:
                self.indicator_databases['who'] = dict(zip(df['value__IndicatorCode'], df['value__IndicatorName']))
                print(f"  Loaded {len(self.indicator_databases['who']):,} WHO indicators")

        # IMF
        if INDICATOR_FILES['imf'].exists():
            print(f"Loading IMF indicators...")
            df = pd.read_csv(INDICATOR_FILES['imf'])
            # Columns: indicators__|, indicators__|__label, indicators__|__description, ...
            if 'indicators__|' in df.columns and 'indicators__|__label' in df.columns:
                self.indicator_databases['imf'] = dict(zip(df['indicators__|'], df['indicators__|__label']))
                print(f"  Loaded {len(self.indicator_databases['imf']):,} IMF indicators")

        # UNICEF
        if INDICATOR_FILES['unicef'].exists():
            print(f"Loading UNICEF indicators...")
            df = pd.read_csv(INDICATOR_FILES['unicef'])
            # Columns: indicator_id, indicator_name, agency, version, description
            if 'indicator_id' in df.columns and 'indicator_name' in df.columns:
                self.indicator_databases['unicef'] = dict(zip(df['indicator_id'], df['indicator_name']))
                print(f"  Loaded {len(self.indicator_databases['unicef']):,} UNICEF indicators")

        # Human Development Report
        if INDICATOR_FILES['hdr'].exists():
            print(f"Loading HDR indicators...")
            try:
                df = pd.read_csv(INDICATOR_FILES['hdr'])
                cols = df.columns.tolist()
                # Try to infer structure
                if len(cols) >= 2:
                    self.indicator_databases['hdr'] = dict(zip(df.iloc[:, 0], df.iloc[:, 1]))
                    print(f"  Loaded {len(self.indicator_databases['hdr']):,} HDR indicators")
            except Exception as e:
                print(f"  Warning: Could not load HDR indicators: {e}")

        total_indicators = sum(len(db) for db in self.indicator_databases.values())
        print(f"\nTotal indicators loaded: {total_indicators:,}")

    def identify_source_and_original_id(self, mech_id: str) -> Tuple[str, str]:
        """
        Identify the data source and original indicator ID from a mechanism ID.

        Returns: (source, original_id)
        """
        # Direct ID patterns (not transformed)
        if '.' in mech_id or '_' not in mech_id:
            # Likely an original ID
            # Try to identify source by pattern
            if mech_id.startswith(('SP.', 'SE.', 'SH.', 'IT.', 'NY.', 'AG.', 'EN.', 'SI.', 'SL.', 'TX.', 'TM.', 'BX.', 'DT.', 'GC.', 'IC.', 'FB.', 'FM.', 'FP.', 'FR.', 'FS.', 'CM.', 'EG.')):
                return ('wdi', mech_id)
            elif mech_id.startswith(('CR.', 'REPR.', 'GER.', 'ROFST.', 'EDULIT.')):
                return ('unesco', mech_id)
            elif mech_id.startswith(('WHS', 'MDG', 'GHED', 'SA_')):
                return ('who', mech_id)
            else:
                return ('unknown', mech_id)

        # Transformed IDs (prefix_suffix pattern)
        if '_' in mech_id:
            parts = mech_id.split('_', 1)
            prefix = parts[0]
            suffix = parts[1] if len(parts) > 1 else ''

            if prefix == 'wdi':
                # Try to reverse engineer WDI code
                # Pattern: wdi_mobile -> IT.CEL.SETS.P2
                # This is hard without the original mapping, but we can try common patterns
                # For now, return as-is and we'll do fuzzy matching
                return ('wdi', mech_id)
            elif prefix == 'unesco':
                return ('unesco', suffix)
            elif prefix == 'who':
                return ('who', suffix)
            elif prefix == 'imf':
                return ('imf', suffix)
            elif prefix == 'unicef':
                return ('unicef', suffix)
            elif prefix == 'vdem':
                return ('vdem', suffix)
            elif prefix == 'qog':
                return ('qog', suffix)
            else:
                return ('unknown', mech_id)

        return ('unknown', mech_id)

    def lookup_label(self, mech_id: str, current_label: str) -> Tuple[str, str, bool]:
        """
        Lookup full label for a mechanism ID.

        Returns: (new_label, source, improved)
        """
        source, original_id = self.identify_source_and_original_id(mech_id)

        # Try direct lookup
        if source in self.indicator_databases:
            db = self.indicator_databases[source]

            # Try exact match
            if original_id in db:
                new_label = db[original_id]
                return (new_label, source, True)

            # Try uppercase
            if original_id.upper() in db:
                new_label = db[original_id.upper()]
                return (new_label, source, True)

            # Try lowercase
            if original_id.lower() in db:
                new_label = db[original_id.lower()]
                return (new_label, source, True)

            # For WDI transformed codes, try fuzzy matching
            if source == 'wdi' and mech_id.startswith('wdi_'):
                suffix = mech_id.replace('wdi_', '').upper()
                # Try to find matching indicator by searching for suffix in the name
                for ind_id, ind_name in db.items():
                    if suffix in ind_name.upper():
                        return (ind_name, 'wdi_fuzzy', True)

        # No improvement found
        return (current_label, 'none', False)

    def assess_label_quality(self, label: str) -> str:
        """
        Assess if a label is good quality.

        Good = full descriptive name (>20 chars, has spaces, not mostly uppercase)
        Poor = code-like (short, no spaces, or all caps abbreviation)
        """
        if len(label) < 10:
            return 'poor'
        if ' ' not in label:
            return 'poor'
        if label.isupper() and len(label) < 30:
            return 'poor'
        if re.match(r'^[A-Z0-9._-]+$', label):
            return 'poor'
        return 'good'

    def fix_all_labels(self):
        """Update all mechanism labels in the schema"""
        print("\n=== Fixing Labels ===")

        improvements_by_source = {}

        for i, mech in enumerate(self.schema['mechanisms']):
            mech_id = mech['id']
            current_label = mech.get('label', mech_id)
            current_quality = mech.get('label_quality', 'unknown')

            # Only try to improve if current quality is poor or unknown
            if current_quality in ['poor', 'unknown']:
                new_label, source, improved = self.lookup_label(mech_id, current_label)

                if improved:
                    new_quality = self.assess_label_quality(new_label)

                    if new_quality == 'good':
                        # Update the mechanism
                        mech['label'] = new_label
                        mech['label_quality'] = 'good'
                        self.improvements += 1

                        # Track by source
                        if source not in improvements_by_source:
                            improvements_by_source[source] = 0
                        improvements_by_source[source] += 1

                        if i < 10:  # Show first 10
                            print(f"  ✓ {mech_id}: '{current_label}' -> '{new_label}'")

        print(f"\nTotal improvements: {self.improvements}/{self.total_mechanisms}")
        print("\nImprovements by source:")
        for source, count in sorted(improvements_by_source.items(), key=lambda x: -x[1]):
            print(f"  {source}: {count}")

    def generate_report(self):
        """Generate quality report"""
        print("\n=== Final Label Quality Report ===")

        quality_counts = {'good': 0, 'poor': 0, 'unknown': 0}

        for mech in self.schema['mechanisms']:
            quality = mech.get('label_quality', 'unknown')
            quality_counts[quality] += 1

        total = self.total_mechanisms
        good_pct = (quality_counts['good'] / total) * 100
        poor_pct = (quality_counts['poor'] / total) * 100

        print(f"Good labels: {quality_counts['good']}/{total} ({good_pct:.1f}%)")
        print(f"Poor labels: {quality_counts['poor']}/{total} ({poor_pct:.1f}%)")
        print(f"Unknown: {quality_counts['unknown']}/{total}")

        if good_pct >= 80:
            print("\n✅ SUCCESS: Reached 80%+ good label quality!")
        elif good_pct >= 60:
            print(f"\n⚠️  PARTIAL: {good_pct:.1f}% good labels (target: 80%+)")
        else:
            print(f"\n❌ FAILED: Only {good_pct:.1f}% good labels (target: 80%+)")

        return quality_counts

    def save_schema(self):
        """Save updated schema"""
        print(f"\nSaving updated schema to {OUTPUT_PATH}")
        with open(OUTPUT_PATH, 'w') as f:
            json.dump(self.schema, f, indent=2)
        print("✓ Schema saved")

    def run(self):
        """Execute the complete label fixing pipeline"""
        print("=" * 60)
        print("Label Fixing Pipeline - Comprehensive Update")
        print("=" * 60)

        self.load_schema()
        self.load_indicator_databases()
        self.fix_all_labels()
        quality_counts = self.generate_report()
        self.save_schema()

        print("\n" + "=" * 60)
        print("Pipeline Complete")
        print("=" * 60)

        return quality_counts


if __name__ == "__main__":
    fixer = LabelFixer()
    fixer.run()
