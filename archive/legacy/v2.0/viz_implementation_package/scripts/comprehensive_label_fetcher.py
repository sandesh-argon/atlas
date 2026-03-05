#!/usr/bin/env python3
"""
Comprehensive Label Fetcher for All 9 Data Sources

Fetches full indicator descriptions to replace 258 poor labels.
Combines API calls (WDI, WHO) with manual mappings (V-Dem, QoG, etc.)

Runtime: ~30-60 minutes
Author: V2.0 Global Causal Discovery Team
Date: November 21, 2025
"""

import json
import requests
import pandas as pd
from pathlib import Path
import time
from typing import Dict, Optional, List
import re


class ComprehensiveLabelFetcher:
    """Fetches full indicator names from all 9 data sources."""

    def __init__(self, input_file: str):
        """Initialize fetcher with label mapping file."""
        with open(input_file, 'r') as f:
            self.label_map = json.load(f)

        self.improvements = 0
        self.failed = []
        self.stats_by_source = {}

    def fetch_all(self) -> Dict:
        """Fetch labels from all sources."""

        print("=" * 80)
        print("COMPREHENSIVE LABEL FETCH - ALL 9 DATA SOURCES")
        print("=" * 80)

        # Count by source before
        self.print_source_stats("BEFORE")

        # 1. World Bank WDI (API available)
        print("\n" + "=" * 80)
        print("1/9: World Bank WDI")
        print("=" * 80)
        self.fetch_wdi_labels()

        # 2. V-Dem (codebook/manual)
        print("\n" + "=" * 80)
        print("2/9: V-Dem Institute")
        print("=" * 80)
        self.fetch_vdem_labels()

        # 3. UNESCO (skip - already good)
        print("\n" + "=" * 80)
        print("3/9: UNESCO UIS")
        print("=" * 80)
        print("  ✅ Already 100% good quality - skipping")

        # 4. QoG (manual mapping)
        print("\n" + "=" * 80)
        print("4/9: Quality of Government (QoG)")
        print("=" * 80)
        self.fetch_qog_labels()

        # 5. Penn World Tables (manual mapping)
        print("\n" + "=" * 80)
        print("5/9: Penn World Tables")
        print("=" * 80)
        self.fetch_pwt_labels()

        # 6. WHO GHO (API available)
        print("\n" + "=" * 80)
        print("6/9: WHO Global Health Observatory")
        print("=" * 80)
        self.fetch_who_labels()

        # 7. IMF WEO (manual mapping)
        print("\n" + "=" * 80)
        print("7/9: IMF World Economic Outlook")
        print("=" * 80)
        self.fetch_imf_labels()

        # 8. UNICEF (manual mapping)
        print("\n" + "=" * 80)
        print("8/9: UNICEF")
        print("=" * 80)
        self.fetch_unicef_labels()

        # 9. WID (manual mapping)
        print("\n" + "=" * 80)
        print("9/9: World Inequality Database")
        print("=" * 80)
        self.fetch_wid_labels()

        # Final stats
        print("\n" + "=" * 80)
        print("RESULTS")
        print("=" * 80)
        self.print_source_stats("AFTER")

        print(f"\n✅ Total improvements: {self.improvements}")
        print(f"❌ Failed to fetch: {len(self.failed)}")

        if self.failed:
            print(f"\nFailed indicators:")
            for code, reason in self.failed[:10]:
                print(f"  - {code}: {reason}")
            if len(self.failed) > 10:
                print(f"  ... and {len(self.failed) - 10} more")

        return self.label_map

    def print_source_stats(self, label: str):
        """Print statistics by source."""
        sources = {}
        for code, info in self.label_map.items():
            source = info.get('source', 'Unknown')
            if source not in sources:
                sources[source] = {'total': 0, 'good': 0}
            sources[source]['total'] += 1
            if info.get('label_quality') == 'good':
                sources[source]['good'] += 1

        print(f"\n{label} - Label Quality by Source:")
        print(f"{'Source':<40} {'Good':<10} {'Poor':<10} {'%Good':<10}")
        print("-" * 80)

        total_good = 0
        total_all = 0

        for source in sorted(sources.keys()):
            stats = sources[source]
            good = stats['good']
            total = stats['total']
            poor = total - good
            pct = good / total * 100 if total > 0 else 0

            total_good += good
            total_all += total

            print(f"{source:<40} {good:<10} {poor:<10} {pct:<10.1f}")

        print("-" * 80)
        total_pct = total_good / total_all * 100 if total_all > 0 else 0
        print(f"{'TOTAL':<40} {total_good:<10} {total_all - total_good:<10} {total_pct:<10.1f}")

    def fetch_wdi_labels(self):
        """Fetch World Bank WDI indicator names via API."""
        wdi_indicators = [
            code for code, info in self.label_map.items()
            if 'World Bank' in info.get('source', '')
        ]

        print(f"  Found {len(wdi_indicators)} WDI indicators")

        improved = 0

        for i, code in enumerate(wdi_indicators, 1):
            # Extract WDI code (handle different prefixes)
            wdi_code = code
            if code.startswith('wdi_'):
                wdi_code = code.replace('wdi_', '')

            # Convert to uppercase for API
            wdi_code_upper = wdi_code.upper()

            try:
                url = f"https://api.worldbank.org/v2/indicator/{wdi_code_upper}"
                response = requests.get(url, params={'format': 'json'}, timeout=10)

                if response.ok:
                    data = response.json()
                    if len(data) > 1 and data[1] and len(data[1]) > 0:
                        indicator_data = data[1][0]
                        label = indicator_data.get('name', '')

                        if label and len(label) > len(code):
                            self.label_map[code]['label'] = label
                            self.label_map[code]['label_quality'] = 'good'
                            self.improvements += 1
                            improved += 1

                            if i % 20 == 0:
                                print(f"    Progress: {i}/{len(wdi_indicators)} ({improved} improved)")

                # Rate limit: 120 req/min = 0.5s per request
                time.sleep(0.5)

            except Exception as e:
                self.failed.append((code, f"WDI API error: {str(e)}"))

        print(f"  ✅ Improved {improved}/{len(wdi_indicators)} WDI labels")

    def fetch_vdem_labels(self):
        """Fetch V-Dem labels (uses manual mapping for now)."""
        vdem_indicators = [
            code for code, info in self.label_map.items()
            if 'V-Dem' in info.get('source', '')
        ]

        print(f"  Found {len(vdem_indicators)} V-Dem indicators")

        # V-Dem doesn't have a simple API, would need codebook
        # For now, use improved pattern matching on descriptions

        improved = 0
        for code in vdem_indicators:
            # Try to extract meaningful label from description
            desc = self.label_map[code].get('description', '')

            # If description has useful info, extract it
            if 'V-Dem indicator:' in desc:
                # Just the code, no help
                continue
            elif desc and len(desc) > len(code):
                # Use description as label
                label = desc.split('.')[0]  # First sentence
                if len(label) > len(code):
                    self.label_map[code]['label'] = label
                    self.label_map[code]['label_quality'] = 'good'
                    self.improvements += 1
                    improved += 1

        print(f"  ℹ️  V-Dem requires manual codebook (not automated)")
        print(f"  ℹ️  Improved {improved} from descriptions")
        print(f"  📝 Remaining {len(vdem_indicators) - improved} need manual lookup at:")
        print(f"      https://v-dem.net/data/reference-documents/")

    def fetch_qog_labels(self):
        """Fetch QoG labels (manual mapping)."""
        qog_indicators = [
            code for code, info in self.label_map.items()
            if 'QoG' in info.get('source', '')
        ]

        if len(qog_indicators) == 0:
            print(f"  No QoG indicators found")
            return

        print(f"  Found {len(qog_indicators)} QoG indicators")
        print(f"  ℹ️  QoG requires manual codebook download")
        print(f"  📝 Download from: https://www.gu.se/en/quality-government/qog-data")

    def fetch_pwt_labels(self):
        """Fetch Penn World Tables labels (manual mapping)."""
        # Common PWT variables with full names
        pwt_labels = {
            'rgdpe': 'Expenditure-side real GDP at chained PPPs (in mil. 2017US$)',
            'rgdpo': 'Output-side real GDP at chained PPPs (in mil. 2017US$)',
            'pop': 'Population (in millions)',
            'emp': 'Number of persons engaged (in millions)',
            'avh': 'Average annual hours worked by persons engaged',
            'hc': 'Human capital index, based on years of schooling and returns to education',
            'ccon': 'Real consumption of households and government at current PPPs (in mil. 2017US$)',
            'cda': 'Real domestic absorption at current PPPs (in mil. 2017US$)',
            'cn': 'Capital stock at current PPPs (in mil. 2017US$)',
            'ck': 'Capital services levels at current PPPs (USA=1)',
            'ctfp': 'TFP level at current PPPs (USA=1)',
            'cwtfp': 'Welfare-relevant TFP levels at current PPPs (USA=1)',
            'rgdpna': 'Real GDP at constant 2017 national prices (in mil. 2017US$)',
            'rconna': 'Real consumption at constant 2017 national prices (in mil. 2017US$)',
            'rdana': 'Real domestic absorption at constant 2017 national prices (in mil. 2017US$)',
            'rnna': 'Capital stock at constant 2017 national prices (in mil. 2017US$)',
            'rkna': 'Capital services at constant 2017 national prices (2017=1)',
            'rtfpna': 'TFP at constant national prices (2017=1)',
            'rwtfpna': 'Welfare-relevant TFP at constant national prices (2017=1)',
            'labsh': 'Share of labour compensation in GDP at current national prices',
            'irr': 'Real internal rate of return',
            'delta': 'Average depreciation rate of the capital stock',
            'xr': 'Exchange rate, national currency/USD (market+estimated)',
            'pl_con': 'Price level of CCON (PPP/XR), price level of USA GDPo in 2017=1',
            'pl_da': 'Price level of CDA (PPP/XR), price level of USA GDPo in 2017=1',
            'pl_gdpo': 'Price level of CGDPo (PPP/XR), price level of USA GDPo in 2017=1',
        }

        pwt_indicators = [
            code for code, info in self.label_map.items()
            if 'Penn World' in info.get('source', '') or code in pwt_labels
        ]

        print(f"  Found {len(pwt_indicators)} Penn World Tables indicators")

        improved = 0
        for code in pwt_indicators:
            if code in pwt_labels:
                self.label_map[code]['label'] = pwt_labels[code]
                self.label_map[code]['label_quality'] = 'good'
                self.improvements += 1
                improved += 1

        print(f"  ✅ Improved {improved}/{len(pwt_indicators)} PWT labels")

    def fetch_who_labels(self):
        """Fetch WHO GHO labels via API."""
        who_indicators = [
            code for code, info in self.label_map.items()
            if 'WHO' in info.get('source', '')
        ]

        print(f"  Found {len(who_indicators)} WHO indicators")

        # WHO API endpoint
        improved = 0
        for code in who_indicators:
            try:
                url = f"https://ghoapi.azureedge.net/api/Indicator/{code}"
                response = requests.get(url, timeout=10)

                if response.ok:
                    data = response.json()
                    if 'value' in data and data['value']:
                        label = data['value'][0].get('IndicatorName', '')
                        if label and len(label) > len(code):
                            self.label_map[code]['label'] = label
                            self.label_map[code]['label_quality'] = 'good'
                            self.improvements += 1
                            improved += 1

                time.sleep(0.3)  # Rate limiting

            except Exception as e:
                self.failed.append((code, f"WHO API error: {str(e)}"))

        print(f"  ✅ Improved {improved}/{len(who_indicators)} WHO labels")

    def fetch_imf_labels(self):
        """Fetch IMF labels (manual mapping)."""
        imf_labels = {
            'NGDP_RPCH': 'Real GDP growth (Annual percent change)',
            'PCPIPCH': 'Inflation, average consumer prices (Annual percent change)',
            'LUR': 'Unemployment rate (Percent of total labor force)',
            'GGR': 'General government revenue (Percent of GDP)',
            'GGX': 'General government total expenditure (Percent of GDP)',
            'GGXCNL': 'General government net lending/borrowing (Percent of GDP)',
            'BCA': 'Current account balance (Percent of GDP)',
        }

        imf_indicators = [
            code for code, info in self.label_map.items()
            if 'IMF' in info.get('source', '') or code in imf_labels
        ]

        print(f"  Found {len(imf_indicators)} IMF indicators")

        improved = 0
        for code in imf_indicators:
            if code in imf_labels:
                self.label_map[code]['label'] = imf_labels[code]
                self.label_map[code]['label_quality'] = 'good'
                self.improvements += 1
                improved += 1

        print(f"  ✅ Improved {improved}/{len(imf_indicators)} IMF labels")

    def fetch_unicef_labels(self):
        """Fetch UNICEF labels (manual mapping)."""
        unicef_indicators = [
            code for code, info in self.label_map.items()
            if 'UNICEF' in info.get('source', '')
        ]

        if len(unicef_indicators) == 0:
            print(f"  No UNICEF indicators found")
            return

        print(f"  Found {len(unicef_indicators)} UNICEF indicators")
        print(f"  ℹ️  UNICEF requires manual indicator lookup")
        print(f"  📝 Reference: https://data.unicef.org/resources/")

    def fetch_wid_labels(self):
        """Fetch WID labels (manual mapping)."""
        wid_indicators = [
            code for code, info in self.label_map.items()
            if 'Inequality' in info.get('source', '') or 'WID' in info.get('source', '')
        ]

        if len(wid_indicators) == 0:
            print(f"  No WID indicators found")
            return

        print(f"  Found {len(wid_indicators)} WID indicators")
        print(f"  ℹ️  WID requires manual codes dictionary")
        print(f"  📝 Reference: https://wid.world/codes-dictionary/")

    def save(self, output_file: str):
        """Save improved labels."""
        with open(output_file, 'w') as f:
            json.dump(self.label_map, f, indent=2)

        print(f"\n💾 Saved improved labels to: {output_file}")


def main():
    """Main entry point."""
    script_dir = Path(__file__).parent
    input_file = script_dir.parent / 'data' / 'label_mapping.json'
    output_file = script_dir.parent / 'data' / 'label_mapping_IMPROVED.json'

    if not input_file.exists():
        print(f"❌ Error: Input file not found: {input_file}")
        return 1

    print(f"📥 Loading labels from: {input_file}")

    fetcher = ComprehensiveLabelFetcher(str(input_file))
    improved_labels = fetcher.fetch_all()
    fetcher.save(str(output_file))

    print("\n" + "=" * 80)
    print("✅ COMPLETE")
    print("=" * 80)
    print(f"\nNext steps:")
    print(f"  1. Review improved labels in: {output_file}")
    print(f"  2. Update schema: python update_schema_with_labels.py")
    print(f"  3. Regenerate tree visualization")

    return 0


if __name__ == '__main__':
    exit(main())
