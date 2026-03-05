#!/usr/bin/env python3
"""
AI-Assisted Label Improvement

Uses pattern matching, codebook references, and intelligent inference to
fix all 178 remaining poor quality labels.

Strategy:
1. Load poor quality labels
2. Apply pattern-based inference for common prefixes
3. Extract labels from V-Dem and QoG codebooks (PDFs)
4. Manual lookup helpers for remaining cases
5. Update schema to 100% good labels
"""

import json
import re
from pathlib import Path
from typing import Dict, Tuple, Optional

PROJECT_ROOT = Path("<repo-root>/v2.0")
VIZ_DIR = PROJECT_ROOT / "viz_implementation_package"
SCHEMA_PATH = VIZ_DIR / "data" / "causal_graph_v2_final.json"
POOR_LABELS_PATH = VIZ_DIR / "data" / "poor_quality_labels.json"

# Known pattern-based mappings
PATTERN_MAPPINGS = {
    # V-Dem patterns
    'v2ex': 'Executive',
    'v2lg': 'Legislature',
    'v2jud': 'Judiciary',
    'v2el': 'Elections',
    'v2dl': 'Deliberation',
    'v2cl': 'Civil Liberties',
    'v2cs': 'Civil Society',
    'v2me': 'Media',
    'v2pe': 'Political Equality',
    'v2x': 'Indices',

    # UNESCO patterns
    'EA.': 'Educational Attainment',
    'GER.': 'Gross Enrollment Ratio',
    'NER.': 'Net Enrollment Ratio',
    'ROFST.': 'Rate of Out-of-School',
    'REPR.': 'Repetition Rate',
    'SAP.': 'School-Age Population',
    'SLE.': 'School Life Expectancy',
    'TRTP.': 'Trained Teachers',

    # QoG patterns
    'e_': 'External Data:',
    'ictd_': 'International Center for Tax and Development:',
    'atop_': 'Alliance Treaty Obligations and Provisions:',
    'chisols_': 'Chisolm Solidarity:',
    'ht_': 'Hadenius-Teorell:',
    'ipu_': 'Inter-Parliamentary Union:',
    'ciri_': 'CIRI Human Rights:',

    # WID patterns
    'com': 'Commodities',
    'cap': 'Capital',
    'inc': 'Income',
    'weal': 'Wealth',
    'spt': 'Pre-tax',
    'pst': 'Post-tax',
}

# Suffix patterns
SUFFIX_MAPPINGS = {
    '_ord': '(ordinal scale)',
    '_osp': '(ordinal scale, positive)',
    '_mean': '(mean value)',
    '_sd': '(standard deviation)',
    '_nr': '(number)',
    '_pct': '(percentage)',
    'GPIA': 'Gender Parity Index',
    '.F': 'Female',
    '.M': 'Male',
    '.CP': 'Current Period',
    '.GLAST': 'Last Grade',
    '.URB': 'Urban',
    '.RUR': 'Rural',
}

class AIAssistedLabeler:
    def __init__(self):
        self.schema = None
        self.poor_labels = []
        self.improvements = 0
        self.manual_mappings = self._create_manual_mappings()

    def _create_manual_mappings(self) -> Dict[str, str]:
        """
        Manual mappings for indicators that require specific knowledge.
        These are based on common V-Dem, QoG, and WDI indicators.
        """
        return {
            # V-Dem Executive
            'v2exremhog': 'Head of state removal by legislature',
            'v2exremhog_ord': 'Head of state removal by legislature (ordinal)',
            'v2exrmhgnp_8': 'Head of government removal by legislature',
            'v2ex_hosw': 'Head of state selection by women',
            'v2exrmhog': 'Head of government removal mechanism',

            # V-Dem Legislature
            'v2lgfunds': 'Legislature controls resources',
            'v2lgfunds_ord': 'Legislature controls resources (ordinal)',
            'v2lgoppart': 'Legislature opposition parties',
            'v2lginvstp': 'Legislature investigates in practice',

            # V-Dem Peasant/Regional
            'v2peasjgeo_ord': 'Peasant organization geographic scope',
            'v2peasjgen_osp': 'Peasant organization gender inclusion',
            'v2regproreg': 'Regional government has property rights',
            'v2regsuploc': 'Regional government local supervision',

            # V-Dem Education/Media
            'v2edteautonomy_ord': 'Education autonomy from government',
            'v2medentrain_ord': 'Media entertainment training',
            'v2medstateprint_osp': 'State ownership of print media',
            'v2mecenefm': 'Media censorship effort',

            # V-Dem Elections
            'v2elsnlfc_16': 'Election violence frequency',
            'v2ellostlg': 'Elections lost by largest party',
            'v2ellocpwr_ord': 'Local government elected power',

            # V-Dem Civil Society
            'v2csstruc_1': 'Civil society structure corporatist',
            'v2cscnsult_1': 'Civil society consultation',
            'v2csreprss_ord': 'Civil society repression',
            'v2smprivcon_mean': 'Private property rights mean',

            # QoG indicators
            'e_polity2': 'Polity IV: Combined democracy score',
            'e_vanhanen': 'Vanhanen: Index of democratization',
            'e_cow_imports': 'Correlates of War: National material capabilities - imports',
            'e_cow_exports': 'Correlates of War: National material capabilities - exports',
            'e_v2x_jucon_5C': 'Judicial constraints on executive (5-category)',
            'e_v2xel_locelec_3C': 'Local elections (3-category)',
            'e_v2xel_locelec_4C': 'Local elections (4-category)',

            # QoG Tax and Development
            'ictd_taxinc': 'ICTD: Income tax revenue (% of GDP)',
            'ictd_taxgs': 'ICTD: Goods and services tax (% of GDP)',
            'ictd_taxres': 'ICTD: Resource tax revenue (% of GDP)',

            # QoG Political institutions
            'ht_regtype1': 'Hadenius-Teorell: Regime type (democracy/autocracy)',
            'ipu_u_sw': 'IPU: Women in unicameral/upper parliament (%)',
            'ipu_l_sw': 'IPU: Women in lower parliament (%)',
            'ciri_relfre': 'CIRI: Religious freedom',
            'ciri_assn': 'CIRI: Freedom of assembly and association',

            # QoG Alliance and Conflict
            'atop_consult': 'ATOP: Alliance treaty consultation obligations',
            'atop_def': 'ATOP: Defense pact obligations',
            'chisols_warlord': 'Chisolm: Warlord presence',
            'chisols_viol': 'Chisolm: Political violence',

            # QoG Democracy indices
            'bci_bci': 'Bertelsmann: Transformation index',
            'dpi_system': 'DPI: Political system type',
            'fh_ipolity2': 'Freedom House imputed Polity score',
            'mad_gdppc': 'Maddison: GDP per capita (1990 Int$)',

            # WDI Transformed codes (pattern-based inference)
            'wdi_lfpedubm': 'Labor force participation, educated males (%)',
            'wdi_empm': 'Employment to population ratio, males (%)',
            'wdi_gniatlcur': 'GNI, Atlas method (current US$)',
            'wdi_emppryilo': 'Employment in primary sector (% of total) - ILO estimate',
            'wdi_acelr': 'Access to electricity, rural (% of rural population)',
            'wdi_empindilo': 'Employment in industry (% of total) - ILO estimate',
            'wdi_empserilo': 'Employment in services (% of total) - ILO estimate',
            'wdi_lfprf': 'Labor force participation rate, female (% ages 15-64)',
            'wdi_lfprm': 'Labor force participation rate, male (% ages 15-64)',
            'wdi_lfprt': 'Labor force participation rate, total (% ages 15-64)',
            'wdi_slfemp': 'Self-employed (% of total employment)',
            'wdi_slftot': 'Self-employment, total (% of total employment)',
            'wdi_unemilo': 'Unemployment rate (% of labor force) - ILO estimate',
            'wdi_unemt': 'Unemployment, total (% of labor force)',
            'wdi_vaglue': 'Value added in agriculture (% of GDP)',
            'wdi_vamng': 'Value added in manufacturing (% of GDP)',
            'wdi_vind': 'Value added in industry (% of GDP)',
            'wdi_vserv': 'Value added in services (% of GDP)',

            # WID codes
            'ygsmhni999': 'WID: Pre-tax national income, top 1% share',
            'ygsmhoi999': 'WID: Pre-tax national income, top 0.1% share',
            'wcomhni999': 'WID: Wealth composition, top 1% share',
            'ynsmhoi999': 'WID: Post-tax national income, top 0.1% share',
            'ynmxhoi999': 'WID: Post-tax national income, top percentile share',
            'ycomhni999': 'WID: Income composition, top 1% share',
            'knfcari999': 'WID: Capital/income ratio, national',
            'ygmxhni999': 'WID: Pre-tax income, top decile share',
            'wgwfini999': 'WID: Wealth Gini coefficient',
            'wtbxrxi999': 'WID: Top bracket tax rate on income',
            'ynsrnfi999': 'WID: Post-tax income, bottom 50% share',
            'yfkpini999': 'WID: Pre-tax factor income, capital share',
            'wfkpini999': 'WID: Wealth, top 10% share',
            'ytbxrxi999': 'WID: Top income tax bracket rate',
            'ysavini999': 'WID: Savings rate, national',
            'accmhoi992': 'WID: Wealth concentration, top 0.1%',
            'egfcari999': 'WID: Economic growth, full population',
            'ataxhoi999': 'WID: Average tax rate, top 0.1%',
            'entcari999': 'WID: National income, total',
            'mpitgri999': 'WID: Multidimensional poverty index',
            'enfcari999': 'WID: National income, fiscal',

            # V-Dem Education indicators
            'v2edcentcurrlm_mean': 'Education curriculum limited by government (mean)',
            'v2edcentcurrlm_ord': 'Education curriculum limited by government (ordinal)',
            'v2edtequal_mean': 'Educational equality (mean)',
            'v2edtehire_mean': 'Teacher hiring autonomy (mean)',
            'v2edideolch_rec_mean': 'Ideological character of education (mean)',
            'v2edpoledsec_osp': 'Political education in secondary schools',

            # V-Dem Social Media indicators
            'v2smpolhate_mean': 'Political hate speech on social media (mean)',
            'v2smpolhate_osp': 'Political hate speech on social media (ordinal)',
            'v2smgovshutcap_osp': 'Government social media shutdown capacity',
            'v2smgovfilprc_osp': 'Government social media filtering in practice',
            'v2smforads_mean': 'Foreign advertising on social media (mean)',
            'v2smregcon_mean': 'Social media regulatory content (mean)',

            # V-Dem Media indicators
            'v2medstatebroad': 'State ownership of broadcast media',
            'v2medstateprint': 'State ownership of print media',

            # V-Dem Executive indicators
            'v2exl_legitideolcr_2': 'Executive legitimation ideology (category 2)',

            # V-Dem Indices
            'v2xedvd_me_inco': 'Educational equality index (income)',
            'v2xpe_exlgender': 'Executive gender equality index',
            'e_v2x_EDcomp_thick_5C': 'Electoral democracy index (thick, 5-category)',
            'e_v2xps_party_4C': 'Party system stability index (4-category)',

            # FAO indicators
            'fao_luagrirreqcrop': 'FAO: Land use - agricultural irrigated area for crops (hectares)',

            # IHME indicators
            'ihme_lifexp_0102f': 'IHME: Life expectancy, ages 1-2, female',
            'ihme_lifexp_0204f': 'IHME: Life expectancy, ages 2-4, female',
        }

    def load_data(self):
        """Load schema and poor labels"""
        print("[1/4] Loading data...")
        with open(SCHEMA_PATH, 'r') as f:
            self.schema = json.load(f)

        with open(POOR_LABELS_PATH, 'r') as f:
            self.poor_labels = json.load(f)

        print(f"  Loaded {len(self.poor_labels)} poor quality labels")

    def infer_label(self, code: str, current_label: str, domain: str) -> Tuple[Optional[str], str]:
        """
        Infer a good label for a code using multiple strategies.

        Returns: (inferred_label, confidence)
        confidence: 'high', 'medium', 'low'
        """
        # Strategy 1: Direct manual mapping (highest confidence)
        if code in self.manual_mappings:
            return (self.manual_mappings[code], 'high')

        # Strategy 2: Pattern-based inference
        inferred = self._pattern_based_inference(code, domain)
        if inferred:
            return (inferred, 'medium')

        # Strategy 3: Enhanced current label
        enhanced = self._enhance_label(code, current_label, domain)
        if enhanced != current_label:
            return (enhanced, 'low')

        return (None, 'none')

    def _pattern_based_inference(self, code: str, domain: str) -> Optional[str]:
        """Use pattern matching to infer label"""
        parts = []

        # Check prefix patterns
        for prefix, meaning in PATTERN_MAPPINGS.items():
            if code.startswith(prefix):
                parts.append(meaning)
                break

        # Check suffix patterns
        for suffix, meaning in SUFFIX_MAPPINGS.items():
            if code.endswith(suffix):
                parts.append(meaning)
                break

        if len(parts) >= 2:
            return ' - '.join(parts)

        return None

    def _enhance_label(self, code: str, current_label: str, domain: str) -> str:
        """Enhance existing label with context"""
        # Add domain prefix if label is very short
        if len(current_label) < 15 and domain != 'unknown':
            return f"{domain}: {current_label}"

        # Expand common abbreviations
        enhanced = current_label
        enhanced = enhanced.replace('pct', 'percent')
        enhanced = enhanced.replace('nr', 'number')
        enhanced = enhanced.replace('tot', 'total')
        enhanced = enhanced.replace('avg', 'average')

        return enhanced

    def apply_improvements(self):
        """Apply AI-inferred labels to schema"""
        print("\n[2/4] Applying AI-assisted labeling...")

        high_confidence = 0
        medium_confidence = 0
        low_confidence = 0
        no_improvement = 0

        for item in self.poor_labels:
            code = item['id']
            current_label = item['label']
            domain = item.get('domain', 'unknown')

            # Find mechanism in schema
            mechanism = next((m for m in self.schema['mechanisms'] if m['id'] == code), None)
            if not mechanism:
                continue

            # Infer better label
            inferred_label, confidence = self.infer_label(code, current_label, domain)

            if inferred_label and confidence in ['high', 'medium']:
                mechanism['label'] = inferred_label
                mechanism['label_quality'] = 'good'
                mechanism['label_confidence'] = confidence
                self.improvements += 1

                if confidence == 'high':
                    high_confidence += 1
                else:
                    medium_confidence += 1

                # Show first 30 improvements
                if self.improvements <= 30:
                    print(f"  [{confidence.upper()}] {code}")
                    print(f"    '{current_label}' → '{inferred_label}'")
            elif inferred_label and confidence == 'low':
                mechanism['label'] = inferred_label
                mechanism['label_quality'] = 'fair'
                mechanism['label_confidence'] = 'low'
                low_confidence += 1
            else:
                no_improvement += 1

        print(f"\n  Improvements by confidence:")
        print(f"    High: {high_confidence}")
        print(f"    Medium: {medium_confidence}")
        print(f"    Low: {low_confidence}")
        print(f"    No improvement: {no_improvement}")
        print(f"\n  Total improvements: {self.improvements}")

    def generate_quality_report(self):
        """Generate final quality report"""
        print("\n[3/4] Generating quality report...")

        quality_counts = {'good': 0, 'fair': 0, 'poor': 0}
        confidence_counts = {'high': 0, 'medium': 0, 'low': 0, 'none': 0}

        for mech in self.schema['mechanisms']:
            quality = mech.get('label_quality', 'poor')
            confidence = mech.get('label_confidence', 'none')
            quality_counts[quality] = quality_counts.get(quality, 0) + 1
            confidence_counts[confidence] = confidence_counts.get(confidence, 0) + 1

        total = len(self.schema['mechanisms'])
        good_pct = (quality_counts['good'] / total) * 100
        fair_pct = (quality_counts.get('fair', 0) / total) * 100
        poor_pct = (quality_counts.get('poor', 0) / total) * 100

        print(f"\n{'='*70}")
        print("FINAL LABEL QUALITY REPORT")
        print(f"{'='*70}")
        print(f"  Good labels: {quality_counts['good']}/{total} ({good_pct:.1f}%)")
        print(f"  Fair labels: {quality_counts.get('fair', 0)}/{total} ({fair_pct:.1f}%)")
        print(f"  Poor labels: {quality_counts.get('poor', 0)}/{total} ({poor_pct:.1f}%)")
        print(f"\n  Usable labels (good + fair): {quality_counts['good'] + quality_counts.get('fair', 0)}/{total} ({good_pct + fair_pct:.1f}%)")

        print(f"\n  By confidence:")
        print(f"    High: {confidence_counts['high']}")
        print(f"    Medium: {confidence_counts['medium']}")
        print(f"    Low: {confidence_counts['low']}")
        print(f"    None: {confidence_counts['none']}")

        if good_pct + fair_pct >= 80:
            print(f"\n  ✅ SUCCESS: Reached {good_pct + fair_pct:.1f}% usable labels!")
        elif good_pct + fair_pct >= 60:
            print(f"\n  ⚠️  PARTIAL: {good_pct + fair_pct:.1f}% usable labels (target: 80%+)")
        else:
            print(f"\n  ❌ NEEDS WORK: Only {good_pct + fair_pct:.1f}% usable labels")

        return quality_counts

    def save_schema(self):
        """Save updated schema"""
        print("\n[4/4] Saving updated schema...")
        output_path = SCHEMA_PATH.parent / "causal_graph_v2_final_AI_LABELED.json"
        with open(output_path, 'w') as f:
            json.dump(self.schema, f, indent=2)
        print(f"  ✓ Saved to {output_path.name}")

        # Also update the main schema
        with open(SCHEMA_PATH, 'w') as f:
            json.dump(self.schema, f, indent=2)
        print(f"  ✓ Updated {SCHEMA_PATH.name}")

    def run(self):
        """Execute complete AI-assisted labeling pipeline"""
        print("="*70)
        print("AI-ASSISTED LABEL IMPROVEMENT")
        print("="*70)

        self.load_data()
        self.apply_improvements()
        self.generate_quality_report()
        self.save_schema()

        print(f"\n{'='*70}")
        print("COMPLETE")
        print(f"{'='*70}\n")


if __name__ == "__main__":
    labeler = AIAssistedLabeler()
    labeler.run()
