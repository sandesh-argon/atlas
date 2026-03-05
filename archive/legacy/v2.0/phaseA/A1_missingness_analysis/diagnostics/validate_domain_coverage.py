#!/usr/bin/env python3
"""
A1 Validation 3: Domain Coverage Sanity Check
=============================================
Samples "Other" category to identify mislabeled indicators and estimate true domain distribution.
"""

import pandas as pd
import numpy as np
import pickle
from pathlib import Path
from collections import defaultdict
import re

# Paths
BASE_DIR = Path(__file__).parent.parent
CHECKPOINT = BASE_DIR / "outputs" / "A1_imputed_data.pkl"
FILTERED_INDICATORS = BASE_DIR / "step1_quality_filtering" / "step1_filter_results.csv"

# Domain keyword mappings (comprehensive)
DOMAIN_KEYWORDS = {
    'Economic': [
        'gdp', 'gnp', 'gni', 'inflation', 'deflator', 'trade', 'export', 'import', 'tariff',
        'investment', 'fdi', 'capital', 'debt', 'deficit', 'surplus', 'budget', 'fiscal',
        'employment', 'unemployment', 'labor', 'labour', 'wage', 'salary', 'income', 'poverty',
        'consumption', 'expenditure', 'saving', 'credit', 'loan', 'interest', 'exchange rate',
        'currency', 'monetary', 'finance', 'financial', 'bank', 'stock', 'market', 'economy',
        'economic', 'industrial', 'manufacturing', 'agriculture', 'service sector', 'productivity',
        'output', 'production', 'sales', 'revenue', 'tax', 'taxation', 'subsidy', 'price',
        'cost', 'value added'
    ],
    'Health': [
        'mortality', 'death', 'life expectancy', 'infant', 'maternal', 'disease', 'illness',
        'hiv', 'aids', 'malaria', 'tuberculosis', 'cancer', 'diabetes', 'vaccination', 'immunization',
        'malnutrition', 'nutrition', 'stunting', 'wasting', 'underweight', 'obesity', 'bmi',
        'healthcare', 'health care', 'hospital', 'clinic', 'physician', 'doctor', 'nurse',
        'medical', 'medicine', 'drug', 'pharmaceutical', 'surgery', 'treatment', 'therapy',
        'epidemic', 'pandemic', 'outbreak', 'mental health', 'disability', 'morbidity'
    ],
    'Education': [
        'school', 'education', 'literacy', 'enrollment', 'enrolment', 'attendance', 'dropout',
        'completion', 'attainment', 'pupil', 'student', 'teacher', 'instructor', 'classroom',
        'primary', 'secondary', 'tertiary', 'university', 'college', 'graduate', 'degree',
        'learning', 'academic', 'curriculum', 'pedagog', 'training', 'skill', 'vocational',
        'educational', 'tuition', 'scholarship'
    ],
    'Infrastructure': [
        'road', 'highway', 'railway', 'railroad', 'airport', 'port', 'transport', 'transportation',
        'electricity', 'power', 'energy', 'electric', 'grid', 'water', 'sanitation', 'sewage',
        'toilet', 'latrine', 'drinking water', 'access to water', 'internet', 'broadband',
        'telecommunication', 'telephone', 'mobile', 'cell phone', 'connectivity', 'infrastructure',
        'construction', 'building', 'housing', 'urban', 'rural infrastructure'
    ],
    'Demographics': [
        'population', 'fertility', 'birth', 'age', 'aging', 'elderly', 'youth', 'child',
        'migration', 'emigration', 'immigration', 'refugee', 'urbanization', 'urban population',
        'rural population', 'density', 'household', 'family', 'demographic', 'sex ratio',
        'dependency ratio', 'median age'
    ],
    'Democracy': [
        'democracy', 'democratic', 'election', 'vote', 'voting', 'suffrage', 'electoral',
        'political rights', 'civil liberties', 'freedom', 'voice', 'accountability',
        'participation', 'representation', 'parliament', 'legislature', 'assembly',
        'multiparty', 'opposition', 'regime', 'authoritarian', 'autocracy', 'polyarchy'
    ],
    'Governance': [
        'governance', 'government', 'public', 'bureaucracy', 'regulation', 'regulatory',
        'rule of law', 'judicial', 'court', 'justice', 'legal', 'legislation', 'policy',
        'administration', 'institutional', 'capacity', 'effectiveness', 'efficiency',
        'transparency', 'accountability', 'stability', 'fragility', 'conflict'
    ],
    'Corruption': [
        'corruption', 'bribery', 'embezzlement', 'fraud', 'graft', 'rent-seeking',
        'transparency', 'integrity', 'accountability', 'anti-corruption'
    ],
    'Inequality': [
        'inequality', 'gini', 'wealth distribution', 'income distribution', 'disparity',
        'gap', 'quintile', 'decile', 'share', 'concentration', 'equity', 'inequitable'
    ],
    'Gender': [
        'gender', 'women', 'female', 'girl', 'maternal', 'maternity', 'sex ratio',
        'gender parity', 'gender gap', 'empowerment', 'discrimination', 'violence against women'
    ],
    'Social': [
        'social', 'welfare', 'protection', 'pension', 'safety net', 'assistance',
        'insurance', 'security', 'benefit', 'transfer', 'subsidy', 'program', 'programme'
    ],
    'Environment': [
        'environment', 'climate', 'emission', 'co2', 'carbon', 'pollution', 'air quality',
        'deforestation', 'forest', 'biodiversity', 'ecosystem', 'conservation', 'renewable',
        'sustainability', 'green', 'ecological', 'waste', 'recycling'
    ]
}

def load_checkpoint():
    """Load A1 imputed data checkpoint"""
    print("Loading A1 checkpoint...")
    with open(CHECKPOINT, 'rb') as f:
        data = pickle.load(f)
    print(f"✅ Loaded {len(data['imputed_data'])} indicators")
    return data

def load_filtered_indicators():
    """Load filtered indicator metadata from Step 1"""
    if FILTERED_INDICATORS.exists():
        df = pd.read_csv(FILTERED_INDICATORS)
        return df
    return None

def classify_indicator(name, keywords_dict):
    """Classify indicator based on keywords in name"""
    name_lower = name.lower()

    # Score each domain
    scores = {}
    for domain, keywords in keywords_dict.items():
        score = sum(1 for kw in keywords if kw.lower() in name_lower)
        if score > 0:
            scores[domain] = score

    if not scores:
        return 'Other', 0

    # Return domain with highest score
    best_domain = max(scores, key=scores.get)
    return best_domain, scores[best_domain]

def main():
    print("=" * 80)
    print("A1 VALIDATION 3: DOMAIN COVERAGE SANITY CHECK")
    print("=" * 80)
    print()

    # Load data
    checkpoint_data = load_checkpoint()
    indicator_names = list(checkpoint_data['imputed_data'].keys())
    print()

    # Load Step 1 metadata if available
    filtered_df = load_filtered_indicators()
    if filtered_df is not None:
        print(f"✅ Loaded Step 1 metadata ({len(filtered_df)} indicators)")

        # Get current domain classification
        domain_counts = filtered_df['domain'].value_counts()
        print()
        print("=" * 80)
        print("CURRENT DOMAIN DISTRIBUTION (Step 1 Classification)")
        print("=" * 80)
        for domain, count in domain_counts.items():
            pct = count / len(filtered_df) * 100
            print(f"{domain:20s}: {count:5,} ({pct:5.1f}%)")
        print()

    # Sample "Other" category
    print("=" * 80)
    print("SAMPLING 'OTHER' CATEGORY (100 random indicators)")
    print("=" * 80)

    if filtered_df is not None:
        other_indicators = filtered_df[filtered_df['domain'] == 'Other']['indicator_name'].tolist()
    else:
        # Classify all indicators
        other_indicators = []
        for name in indicator_names:
            domain, _ = classify_indicator(name, DOMAIN_KEYWORDS)
            if domain == 'Other':
                other_indicators.append(name)

    print(f"Found {len(other_indicators)} indicators in 'Other' category")

    # Sample 100 random
    sample_size = min(100, len(other_indicators))
    sampled = np.random.choice(other_indicators, sample_size, replace=False)

    # Re-classify with comprehensive keywords
    reclassified = {}
    for name in sampled:
        domain, score = classify_indicator(name, DOMAIN_KEYWORDS)
        reclassified[name] = (domain, score)

    # Count reclassified domains
    reclassified_counts = defaultdict(int)
    for domain, score in reclassified.values():
        reclassified_counts[domain] += 1

    print()
    print("Reclassified domain distribution (sample of 100):")
    for domain, count in sorted(reclassified_counts.items(), key=lambda x: -x[1]):
        pct = count / sample_size * 100
        print(f"  {domain:20s}: {count:3d} ({pct:5.1f}%)")
    print()

    # Show examples
    print("=" * 80)
    print("RECLASSIFICATION EXAMPLES (First 20)")
    print("=" * 80)

    for i, (name, (domain, score)) in enumerate(list(reclassified.items())[:20]):
        print(f"{i+1:2d}. {name}")
        print(f"    → {domain} (score: {score})")
    print()

    # Extrapolate to full "Other" category
    print("=" * 80)
    print("ESTIMATED CORRECTED DOMAIN DISTRIBUTION")
    print("=" * 80)

    if filtered_df is not None:
        # Start with current non-Other counts
        estimated_counts = domain_counts.to_dict()

        # Estimate reclassification proportions
        other_count = estimated_counts.get('Other', 0)
        for domain, sample_count in reclassified_counts.items():
            proportion = sample_count / sample_size
            estimated_addition = int(other_count * proportion)

            if domain == 'Other':
                estimated_counts['Other'] = estimated_addition
            else:
                estimated_counts[domain] = estimated_counts.get(domain, 0) + estimated_addition

        print("If we reclassify all 'Other' indicators using comprehensive keywords:")
        print()
        for domain in sorted(estimated_counts.keys()):
            count = estimated_counts[domain]
            pct = count / len(filtered_df) * 100
            print(f"{domain:20s}: {count:5,} ({pct:5.1f}%)")
        print()

    # Critical domain check
    print("=" * 80)
    print("CRITICAL DOMAIN SUFFICIENCY CHECK")
    print("=" * 80)

    critical_domains = ['Economic', 'Health', 'Education', 'Democracy', 'Governance', 'Inequality']
    min_required = 200

    print(f"Minimum required for causal discovery: {min_required} indicators per domain")
    print()

    all_sufficient = True
    for domain in critical_domains:
        if filtered_df is not None:
            current = estimated_counts.get(domain, 0)
            status = "✅ PASS" if current >= min_required else "❌ FAIL"
            if current < min_required:
                all_sufficient = False
            print(f"{domain:20s}: {current:5,} indicators {status}")

    print()

    # Recommendation
    print("=" * 80)
    print("RECOMMENDATION")
    print("=" * 80)

    if all_sufficient:
        print("✅ PASS: All critical domains have sufficient indicators (≥200)")
        print("   → Option A: Proceed with 7,818 indicators")
        print("   → Re-classify 'Other' category in Phase B3 (semantic clustering)")
    else:
        insufficient = [d for d in critical_domains if estimated_counts.get(d, 0) < min_required]
        print(f"⚠️ WARNING: {len(insufficient)} critical domains below threshold:")
        for domain in insufficient:
            print(f"   - {domain}: {estimated_counts.get(domain, 0)} (need {min_required})")
        print()
        print("   → Option A: Re-classify 'Other' NOW using semantic embeddings (adds 2-3 hours)")
        print("   → Option B: Proceed with current classification, fix in B3 (Phase B)")

    print()
    print("Note: Many 'Other' indicators are likely economic/infrastructure/demographics")
    print("      Keyword matching is too narrow for complex indicator names")
    print("      Semantic clustering (Phase B3) will provide accurate classification")
    print()

if __name__ == "__main__":
    main()
