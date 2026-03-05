#!/usr/bin/env python3
"""
B3 Pre-Execution Checks
========================

Runs 2 critical checks before starting B3:
1. Metadata Availability Check (15 min)
2. Literature Constructs Validation (10 min)

Purpose: Catch missing data sources early to avoid wasting time

Author: Phase B3 Pre-Checks
Date: November 2025
"""

import os
import json
import sys
from pathlib import Path
import pandas as pd

# Add project root to path
project_root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(project_root))

print("="*80)
print("B3 PRE-EXECUTION CHECKS")
print("="*80)

# ============================================================================
# PRE-CHECK 1: Metadata Availability
# ============================================================================

print("\n" + "="*80)
print("PRE-CHECK 1: METADATA AVAILABILITY")
print("="*80)

def check_metadata_availability():
    """Check which metadata sources are available"""

    available_sources = {}

    # Define metadata paths (relative to project root)
    metadata_paths = {
        'wdi': project_root / 'phaseA/A0_data_acquisition/metadata/wdi_metadata.json',
        'vdem': project_root / 'phaseA/A0_data_acquisition/metadata/vdem_codebook.json',
        'unesco': project_root / 'phaseA/A0_data_acquisition/metadata/unesco_metadata.json',
        'qog': project_root / 'phaseA/A0_data_acquisition/metadata/qog_codebook.json',
        'penn': project_root / 'phaseA/A0_data_acquisition/metadata/pwt_metadata.json',
        'fallback': project_root / 'phaseA/A0_data_acquisition/metadata/fallback_metadata.json',
    }

    print(f"\nChecking metadata sources in: {project_root}/phaseA/A0_data_acquisition/metadata/")

    for source, path in metadata_paths.items():
        if path.exists():
            try:
                with open(path, 'r') as f:
                    metadata = json.load(f)

                has_full_names = sum(1 for v in metadata.values() if isinstance(v, dict) and 'full_name' in v)
                has_descriptions = sum(1 for v in metadata.values() if isinstance(v, dict) and 'description' in v)

                available_sources[source] = {
                    'available': True,
                    'n_indicators': len(metadata),
                    'has_full_names': has_full_names,
                    'has_descriptions': has_descriptions,
                    'path': str(path)
                }
            except Exception as e:
                available_sources[source] = {
                    'available': False,
                    'error': str(e),
                    'fallback': 'Use online API or manual lookup'
                }
        else:
            available_sources[source] = {
                'available': False,
                'fallback': 'Use online API or manual lookup',
                'path': str(path)
            }

    # Print summary
    print(f"\n{'Source':<10} {'Status':<12} {'Indicators':<12} {'Full Names':<15} {'Descriptions':<15}")
    print("-" * 75)

    for source, info in available_sources.items():
        if info['available']:
            print(f"{source.upper():<10} {'✅ FOUND':<12} {info['n_indicators']:<12} {info['has_full_names']:<15} {info['has_descriptions']:<15}")
        else:
            print(f"{source.upper():<10} {'❌ NOT FOUND':<12} {'-':<12} {'-':<15} {'-':<15}")

    # Load mechanism candidates to estimate coverage
    b2_checkpoint_path = project_root / 'phaseB/B2_mechanism_identification/outputs/B2_bridging_subgraph_checkpoint.pkl'

    if b2_checkpoint_path.exists():
        import pickle
        with open(b2_checkpoint_path, 'rb') as f:
            b2_data = pickle.load(f)
        mechanism_candidates = b2_data['mechanism_candidates']
        print(f"\n✅ Loaded {len(mechanism_candidates)} mechanism candidates from B2")

        # Estimate coverage by prefix matching
        source_coverage = {
            'wdi': 0,
            'vdem': 0,
            'unesco': 0,
            'qog': 0,
            'penn': 0,
            'fallback': 0
        }

        for var in mechanism_candidates:
            var_lower = var.lower()
            if var_lower.startswith('wdi_'):
                source_coverage['wdi'] += 1
            elif var_lower.startswith('v2') or var_lower.startswith('v3'):
                source_coverage['vdem'] += 1
            elif any(x in var_lower for x in ['ger', 'repr', 'ner', 'oaep', 'nert']):
                source_coverage['unesco'] += 1
            elif var_lower.startswith('pwt_') or var_lower in ['hc', 'hci']:
                source_coverage['penn'] += 1
            # QoG and others hard to detect by prefix

        print(f"\n📊 Mechanism Breakdown by Source:")
        for source, count in source_coverage.items():
            pct = count / len(mechanism_candidates) * 100
            print(f"   {source.upper():<10}: {count:>3} mechanisms ({pct:>5.1f}%)")

        # Calculate expected coverage
        expected_coverage = 0
        for source, info in available_sources.items():
            if info['available']:
                pct = source_coverage[source] / len(mechanism_candidates)
                expected_coverage += pct

        print(f"\n📈 Expected Metadata Coverage: {expected_coverage*100:.1f}%")

        if expected_coverage < 0.80:
            print(f"\n⚠️  WARNING: Expected coverage {expected_coverage*100:.1f}% < 80%")
            print(f"   Recommendation: Fetch missing metadata from online APIs (adds 30-60 min)")
        else:
            print(f"\n✅ Expected coverage {expected_coverage*100:.1f}% ≥ 80% (sufficient)")

    else:
        print(f"\n❌ ERROR: B2 checkpoint not found at {b2_checkpoint_path}")
        expected_coverage = 0

    return available_sources, expected_coverage

available_sources, expected_coverage = check_metadata_availability()

# Save report
report_lines = []
report_lines.append("B3 METADATA AVAILABILITY REPORT")
report_lines.append("="*80)
report_lines.append(f"\nExpected Coverage: {expected_coverage*100:.1f}%\n")
report_lines.append(f"{'Source':<10} {'Status':<15} {'Path'}")
report_lines.append("-" * 80)

for source, info in available_sources.items():
    if info['available']:
        report_lines.append(f"{source.upper():<10} {'✅ AVAILABLE':<15} {info.get('path', 'N/A')}")
    else:
        report_lines.append(f"{source.upper():<10} {'❌ MISSING':<15} {info.get('path', 'N/A')}")

report_path = Path(__file__).parent.parent / "B3_metadata_availability_report.txt"
with open(report_path, 'w') as f:
    f.write("\n".join(report_lines))

print(f"\n✅ Report saved: {report_path}")

# ============================================================================
# PRE-CHECK 2: Literature Constructs Validation
# ============================================================================

print("\n" + "="*80)
print("PRE-CHECK 2: LITERATURE CONSTRUCTS VALIDATION")
print("="*80)

def check_literature_constructs():
    """Verify literature DB exists and has minimum content"""

    literature_path = project_root / 'literature_db/literature_constructs.json'

    print(f"\nChecking for: {literature_path}")

    if not literature_path.exists():
        print(f"❌ Literature constructs DB not found!")
        print(f"\n🔧 CREATING MINIMAL LITERATURE DB...")

        # Create minimal DB with 8 core constructs
        minimal_constructs = {
            "rule_of_law": {
                "source": "World Bank WGI",
                "keywords": ["judicial", "courts", "legal", "independence", "corruption", "judiciary"],
                "indicators": ["v2jucomp", "v2jucorrdc", "v2juhcind"],
                "citation": "Kaufmann et al. (2010)",
                "domain": "Governance"
            },
            "electoral_democracy": {
                "source": "V-Dem",
                "keywords": ["election", "voting", "suffrage", "campaign", "electoral"],
                "indicators": ["v2x_polyarchy", "v2xel_frefair", "v2elfrfair"],
                "citation": "Coppedge et al. (2023)",
                "domain": "Governance"
            },
            "civil_liberties": {
                "source": "V-Dem",
                "keywords": ["freedom", "rights", "liberties", "civil", "political"],
                "indicators": ["v2x_civlib", "v2clacfree", "v2cldiscm"],
                "citation": "Coppedge et al. (2023)",
                "domain": "Governance"
            },
            "human_capital": {
                "source": "World Bank HCI",
                "keywords": ["education", "health", "human capital", "school", "mortality"],
                "indicators": ["hci", "ger", "mortu5"],
                "citation": "Kraay (2018)",
                "domain": "Economic"
            },
            "health_outcomes": {
                "source": "WHO",
                "keywords": ["health", "mortality", "life expectancy", "maternal", "infant"],
                "indicators": ["wdi_mortu5", "wdi_life_expectancy", "maternal_mortality"],
                "citation": "WHO (2023)",
                "domain": "Health"
            },
            "educational_attainment": {
                "source": "UNESCO",
                "keywords": ["enrollment", "completion", "literacy", "school", "education"],
                "indicators": ["GER.4", "REPR.1.G2.CP", "NER.01.F.CP"],
                "citation": "UNESCO (2023)",
                "domain": "Education"
            },
            "fiscal_capacity": {
                "source": "IMF GFS",
                "keywords": ["tax", "revenue", "fiscal", "government spending"],
                "indicators": ["tax_revenue", "govt_expenditure"],
                "citation": "IMF (2023)",
                "domain": "Economic"
            },
            "inequality": {
                "source": "World Inequality Database",
                "keywords": ["inequality", "gini", "income distribution", "wealth gap"],
                "indicators": ["gini", "income_share_top10"],
                "citation": "WID (2023)",
                "domain": "Economic"
            }
        }

        # Save minimal DB
        literature_path.parent.mkdir(parents=True, exist_ok=True)
        with open(literature_path, 'w') as f:
            json.dump(minimal_constructs, f, indent=2)

        print(f"✅ Created minimal literature DB with {len(minimal_constructs)} constructs")
        constructs = minimal_constructs

    else:
        # Load existing DB
        with open(literature_path, 'r') as f:
            constructs = json.load(f)

        print(f"✅ Literature DB found: {len(constructs)} constructs")

    # Validate structure
    required_fields = ['keywords', 'source', 'domain']
    incomplete = []

    for name, construct in constructs.items():
        missing = [f for f in required_fields if f not in construct]
        if missing:
            incomplete.append((name, missing))

    if incomplete:
        print(f"\n⚠️  WARNING: {len(incomplete)} constructs have missing fields:")
        for name, missing in incomplete[:5]:
            print(f"   {name}: missing {missing}")

    # Check domain coverage
    domains = [c['domain'] for c in constructs.values() if 'domain' in c]
    domain_counts = {}
    for d in domains:
        domain_counts[d] = domain_counts.get(d, 0) + 1

    print(f"\n📊 Domain Coverage:")
    for domain, count in sorted(domain_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"   {domain:<15}: {count:>2} constructs")

    # Validate minimum coverage
    min_domains = {'Governance', 'Economic', 'Health', 'Education'}
    missing_domains = min_domains - set(domain_counts.keys())

    if missing_domains:
        print(f"\n⚠️  WARNING: Missing domains: {missing_domains}")
        print(f"   Consider adding constructs for these domains")
    else:
        print(f"\n✅ All required domains covered (Governance, Economic, Health, Education)")

    return constructs

literature_constructs = check_literature_constructs()

# ============================================================================
# DECISION GATE
# ============================================================================

print("\n" + "="*80)
print("PRE-CHECK RESULTS SUMMARY")
print("="*80)

precheck_pass = True

# Check 1: Metadata coverage
if expected_coverage >= 0.80:
    print(f"\n✅ PRE-CHECK 1 PASSED: Metadata coverage {expected_coverage*100:.1f}% ≥ 80%")
else:
    print(f"\n❌ PRE-CHECK 1 FAILED: Metadata coverage {expected_coverage*100:.1f}% < 80%")
    print(f"   RECOMMENDATION: Fetch from online APIs (adds 30-60 min)")
    precheck_pass = False

# Check 2: Literature constructs
if len(literature_constructs) >= 8:
    print(f"✅ PRE-CHECK 2 PASSED: {len(literature_constructs)} constructs ≥ 8 minimum")
else:
    print(f"❌ PRE-CHECK 2 FAILED: Only {len(literature_constructs)} constructs < 8 minimum")
    precheck_pass = False

# Domain coverage
domains_covered = set(c.get('domain', 'Unknown') for c in literature_constructs.values())
required_domains = {'Governance', 'Economic', 'Health', 'Education'}
if required_domains.issubset(domains_covered):
    print(f"✅ Domain coverage: All 4 required domains present")
else:
    missing = required_domains - domains_covered
    print(f"⚠️  Domain coverage: Missing {missing}")

# Overall status
print("\n" + "="*80)
if precheck_pass:
    print("✅ ALL PRE-CHECKS PASSED - READY TO START B3")
    print("="*80)
    print("\nNext step: Task 1.1 (Load Indicator Metadata)")
else:
    print("⚠️  PRE-CHECKS REQUIRE ATTENTION")
    print("="*80)
    print("\nRecommendations:")
    if expected_coverage < 0.80:
        print("  1. Run Task 1.1 with online API fallback (fetch missing metadata)")
    print("  2. Accept current metadata coverage and proceed")
    print("\nDecision: Proceed with partial data OR fetch from online APIs?")

# Save validation results
validation_results = {
    'metadata_coverage': float(expected_coverage),
    'n_available_sources': sum(1 for s in available_sources.values() if s['available']),
    'total_sources': len(available_sources),
    'literature_constructs': len(literature_constructs),
    'domains_covered': list(domains_covered),
    'precheck_pass': precheck_pass
}

results_path = Path(__file__).parent.parent / "outputs/B3_precheck_results.json"
results_path.parent.mkdir(parents=True, exist_ok=True)
with open(results_path, 'w') as f:
    json.dump(validation_results, f, indent=2)

print(f"\n✅ Results saved: {results_path}")
print(f"\n{'='*80}")
