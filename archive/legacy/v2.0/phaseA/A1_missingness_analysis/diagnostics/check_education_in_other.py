#!/usr/bin/env python3
"""
Education Classification Check
==============================
Checks if education indicators are being misclassified as "Other"
"""

import pandas as pd
from pathlib import Path
import json

BASE_DIR = Path(__file__).parent
FILTERED_DATA = BASE_DIR / "filtered_data"

# Education keywords
EDUCATION_KEYWORDS = [
    'school', 'education', 'literacy', 'enrollment', 'enrolment',
    'pupil', 'teacher', 'student', 'completion', 'attainment',
    'graduate', 'tertiary', 'primary', 'secondary', 'university',
    'learning', 'educational', 'academic', 'pedagog'
]

def classify_domain(indicator_name, source):
    """Same classification logic as diagnostic"""
    name_lower = indicator_name.lower()
    source_lower = source.lower()

    # Economic indicators
    if any(kw in name_lower for kw in ['gdp', 'income', 'poverty', 'employment', 'wage', 'trade', 'export', 'import', 'inflation', 'price']):
        return 'Economic'

    # Health indicators
    if any(kw in name_lower for kw in ['health', 'mortality', 'life_expectancy', 'disease', 'nutrition', 'malnutrition', 'medical', 'hospital', 'immunization', 'vaccination']):
        return 'Health'

    # Education indicators
    if any(kw in name_lower for kw in EDUCATION_KEYWORDS):
        return 'Education'

    # Democracy indicators
    if any(kw in name_lower for kw in ['democracy', 'election', 'electoral', 'vote', 'suffrage', 'party', 'civil_liberties']) or 'vdem' in source_lower:
        return 'Democracy'

    # Governance indicators
    if any(kw in name_lower for kw in ['governance', 'government', 'regulation', 'rule_of_law', 'political', 'stability', 'accountability']):
        return 'Governance'

    # Corruption indicators
    if any(kw in name_lower for kw in ['corruption', 'transparency', 'bribe']):
        return 'Corruption'

    # Inequality indicators
    if any(kw in name_lower for kw in ['inequality', 'gini', 'wealth_distribution', 'income_distribution']) or 'wid' in source_lower:
        return 'Inequality'

    # Infrastructure indicators
    if any(kw in name_lower for kw in ['infrastructure', 'road', 'electricity', 'water', 'sanitation', 'internet', 'mobile', 'phone']):
        return 'Infrastructure'

    # Environment indicators
    if any(kw in name_lower for kw in ['environment', 'emission', 'co2', 'pollution', 'forest', 'renewable', 'energy']):
        return 'Environment'

    # Gender indicators
    if any(kw in name_lower for kw in ['gender', 'female', 'women', 'maternal']):
        return 'Gender'

    # Social indicators
    if any(kw in name_lower for kw in ['social', 'welfare', 'pension', 'security']):
        return 'Social'

    return 'Other'


def main():
    print("=" * 80)
    print("EDUCATION CLASSIFICATION CHECK")
    print("=" * 80)
    print()

    # Get all filtered indicators
    all_files = list(FILTERED_DATA.rglob("*.csv"))
    print(f"Total filtered indicators: {len(all_files):,}")
    print()

    # Classify each indicator
    domain_counts = {}
    education_in_other = []
    all_education = []

    print("Classifying indicators...")
    for csv_file in all_files:
        indicator_name = csv_file.stem
        source = csv_file.parent.name

        domain = classify_domain(indicator_name, source)

        domain_counts[domain] = domain_counts.get(domain, 0) + 1

        # Check if education indicator
        is_education = any(kw in indicator_name.lower() for kw in EDUCATION_KEYWORDS)

        if is_education:
            all_education.append({'indicator': indicator_name, 'source': source, 'classified_as': domain})

            if domain == 'Other':
                education_in_other.append({'indicator': indicator_name, 'source': source})

    # Results
    print("=" * 80)
    print("DOMAIN DISTRIBUTION")
    print("=" * 80)
    for domain in sorted(domain_counts.keys()):
        count = domain_counts[domain]
        pct = count / len(all_files) * 100
        print(f"{domain:20s}: {count:6,} ({pct:5.1f}%)")

    print()
    print("=" * 80)
    print("EDUCATION INDICATOR ANALYSIS")
    print("=" * 80)
    print(f"Total education-related indicators: {len(all_education):,}")
    print(f"  Classified as 'Education': {domain_counts.get('Education', 0):,}")
    print(f"  Classified as 'Other': {len(education_in_other):,}")
    print()

    if len(all_education) > 0:
        print("EDUCATION INDICATORS BY CLASSIFICATION:")
        classification_breakdown = {}
        for edu in all_education:
            cls = edu['classified_as']
            classification_breakdown[cls] = classification_breakdown.get(cls, 0) + 1

        for cls, count in sorted(classification_breakdown.items(), key=lambda x: -x[1]):
            print(f"  {cls:20s}: {count:,} indicators")

    print()

    if len(education_in_other) > 0:
        print("=" * 80)
        print(f"⚠️  FOUND {len(education_in_other):,} EDUCATION INDICATORS IN 'OTHER'")
        print("=" * 80)
        print()
        print("Sample indicators (first 20):")
        for item in education_in_other[:20]:
            print(f"  {item['source']:15s} | {item['indicator']}")

        print()
        print("RECOMMENDATION: Reclassify these indicators as 'Education'")
        print("This will recover education indicators for A1 analysis")

    else:
        print("=" * 80)
        print("✅ CLASSIFICATION OK - Education indicators correctly classified")
        print("=" * 80)
        print()
        print("The 0 education indicators is NOT a classification problem.")
        print("Running deeper diagnostic to understand root cause...")
        print()
        print("Next steps:")
        print("1. Check if UNESCO files exist and are valid")
        print("2. Analyze why education indicators fail filters")
        print("3. Consider differential thresholds for education domain")

    # Save results
    results = {
        'total_filtered': len(all_files),
        'domain_counts': domain_counts,
        'total_education_keywords': len(all_education),
        'education_in_other': len(education_in_other),
        'education_properly_classified': domain_counts.get('Education', 0),
        'sample_education_in_other': education_in_other[:50]
    }

    with open(BASE_DIR / "education_classification_check.json", 'w') as f:
        json.dump(results, f, indent=2)

    print()
    print(f"✅ Results saved to: education_classification_check.json")


if __name__ == "__main__":
    main()
