#!/usr/bin/env python3
"""
Classify all 8,126 nodes into domains using:
1. Code prefix patterns (V-Dem, WDI, UNESCO, etc.)
2. Label keyword matching
3. Interaction term component classification

Output: Updated causal_graph_v2_FULL.json with domain assignments
"""

import json
import re
from pathlib import Path
from collections import Counter

# ============================================================================
# DOMAIN CLASSIFICATION RULES
# ============================================================================

# Code prefix → Domain mappings
CODE_PREFIX_DOMAINS = {
    # V-Dem (Governance)
    'v2x': 'Governance', 'v2ex': 'Governance', 'v2lg': 'Governance',
    'v2el': 'Governance', 'v2ps': 'Governance', 'v2ju': 'Governance',
    'v2dl': 'Governance', 'v2cl': 'Governance', 'v2cs': 'Governance',
    'v2sm': 'Governance', 'v2me': 'Governance', 'v2pe': 'Governance',
    'v2pa': 'Governance', 'v2ca': 'Governance', 'v2re': 'Governance',
    'v2ed': 'Governance', 'v3pe': 'Governance', 'v3el': 'Governance',
    'vdem': 'Governance', 'e_v2': 'Governance', 'e_v3': 'Governance',

    # Quality of Government / Governance datasets
    'ccp': 'Governance', 'ciri': 'Governance', 'cbie': 'Governance',
    'cbi': 'Governance', 'wgov': 'Governance', 'wbgi': 'Governance',
    'ipu': 'Governance', 'ross': 'Governance', 'qar': 'Governance',

    # UNESCO (Education)
    'CR': 'Education', 'EA': 'Education', 'REPR': 'Education',
    'PRYA': 'Education', 'SCHBSP': 'Education', 'NERT': 'Education',
    'ROFST': 'Education', 'GER': 'Education', 'NER': 'Education',
    'QUTP': 'Education', 'SAP': 'Education', 'LR': 'Education',
    'OFST': 'Education', 'TRTP': 'Education', 'PTRHC': 'Education',
    'FOSGP': 'Education', 'MOGER': 'Education', 'NART': 'Education',
    'FTP': 'Education', 'FRESP': 'Education', 'une': 'Education',
    'EV': 'Education',  # Education vocational

    # World Bank WDI (various)
    'wdi': 'Economic',  # Default, refined by label
    'SP': 'Demographics', 'SG': 'Demographics', 'npopul': 'Demographics',
    'wpp': 'Demographics',
    'NY': 'Economic', 'NE': 'Economic', 'NV': 'Economic',
    'BX': 'Economic', 'BM': 'Economic', 'BN': 'Economic',
    'TX': 'Economic', 'TM': 'Economic', 'DT': 'Economic',
    'EN': 'Environment', 'AG': 'Environment', 'fao': 'Environment',
    'SH': 'Health', 'ihme': 'Health', 'MOR': 'Health',
    'SE': 'Education',
    'SL': 'Economic',  # Labor
    'IC': 'Economic', 'IT': 'Technology', 'ictd': 'Technology',
    'AIR': 'Infrastructure', 'GFDD': 'Economic',

    # Penn World Table (Economic)
    'pwt': 'Economic',

    # OECD / Economic
    'opri': 'Economic', 'OE': 'Economic', 'OECD': 'Economic',
    'gol': 'Economic', 'gea': 'Economic',
    'XSPENDP': 'Economic', 'XUNIT': 'Economic', 'X': 'Economic',
    'GTVP': 'Economic', 'OAEPG': 'Economic', 'ETOIP': 'Economic',
    'SLE': 'Economic',

    # International relations
    'warc': 'International', 'csh': 'International',
    'atop': 'International', 'cow': 'International',

    # Environmental/Climate
    'gain': 'Environment',

    # Finance
    'fi': 'Economic',

    # Health-specific
    'h_': 'Health',

    # WDI specific codes
    'NW': 'Environment',  # Natural resources
}

# Label keyword → Domain mappings (case-insensitive)
LABEL_KEYWORDS = {
    # Governance
    'Governance': [
        'governance', 'democracy', 'election', 'parliament', 'legislature',
        'judicial', 'court', 'corruption', 'political', 'vote', 'voting',
        'civil society', 'freedom', 'rights', 'executive', 'government',
        'constitution', 'law', 'legal', 'regulation', 'censorship',
        'opposition', 'party', 'parties', 'regime', 'autocra', 'democra',
        'civil liberties', 'press freedom', 'media freedom', 'rule of law',
        'transparency', 'accountability', 'bureaucra', 'public sector',
        'state capacity', 'institutional', 'clientelism', 'patronage'
    ],
    # Economic
    'Economic': [
        'gdp', 'income', 'trade', 'export', 'import', 'employment',
        'unemployment', 'labor', 'labour', 'wage', 'salary', 'economic',
        'economy', 'market', 'business', 'industry', 'manufactur',
        'agriculture', 'financial', 'bank', 'credit', 'debt', 'tax',
        'fiscal', 'monetary', 'inflation', 'price', 'cost', 'investment',
        'capital', 'productivity', 'growth', 'poverty', 'inequality',
        'gini', 'wealth', 'consumption', 'expenditure', 'budget',
        'remittance', 'fdi', 'foreign direct', 'stock market'
    ],
    # Education
    'Education': [
        'education', 'school', 'student', 'teacher', 'enrollment',
        'enrolment', 'literacy', 'primary', 'secondary', 'tertiary',
        'university', 'college', 'vocational', 'training', 'learning',
        'attainment', 'graduation', 'dropout', 'pupil', 'academic',
        'curriculum', 'classroom', 'educational', 'reading', 'math',
        'science score', 'pisa', 'years of schooling'
    ],
    # Health
    'Health': [
        'health', 'mortality', 'death', 'life expectancy', 'disease',
        'hospital', 'doctor', 'physician', 'nurse', 'medical', 'medicine',
        'vaccine', 'immunization', 'malaria', 'hiv', 'aids', 'tuberculosis',
        'infant', 'child mortality', 'maternal', 'birth', 'fertility',
        'nutrition', 'malnutrition', 'stunting', 'sanitation', 'water',
        'drinking water', 'hygiene', 'healthcare', 'epidemic', 'pandemic'
    ],
    # Demographics
    'Demographics': [
        'population', 'demographic', 'age', 'gender', 'sex', 'male',
        'female', 'urban', 'rural', 'migration', 'immigrant', 'refugee',
        'birth rate', 'death rate', 'fertility rate', 'life expectancy',
        'median age', 'dependency ratio', 'working age'
    ],
    # Environment
    'Environment': [
        'environment', 'climate', 'emission', 'carbon', 'co2', 'greenhouse',
        'pollution', 'air quality', 'water quality', 'forest', 'deforest',
        'biodiversity', 'species', 'ecosystem', 'renewable', 'energy',
        'electricity', 'natural resource', 'mining', 'oil', 'gas',
        'sustainable', 'waste', 'recycl'
    ],
    # Technology
    'Technology': [
        'technology', 'internet', 'mobile', 'phone', 'computer', 'digital',
        'broadband', 'telecommunication', 'ict', 'innovation', 'patent',
        'research', 'r&d', 'scientific', 'tech'
    ],
    # Infrastructure
    'Infrastructure': [
        'infrastructure', 'road', 'transport', 'rail', 'airport', 'port',
        'electricity access', 'power grid', 'construction', 'housing'
    ],
    # International
    'International': [
        'international', 'foreign', 'diplomatic', 'treaty', 'alliance',
        'war', 'conflict', 'military', 'defense', 'defence', 'peacekeep',
        'united nations', 'un ', 'nato', 'bilateral', 'multilateral'
    ],
    # Social
    'Social': [
        'social', 'welfare', 'pension', 'insurance', 'safety net',
        'assistance', 'benefit', 'protection', 'housing', 'homeless'
    ]
}


def classify_by_code(node_id: str) -> str:
    """Classify node by its code prefix."""
    node_lower = node_id.lower()

    # Check each prefix pattern
    for prefix, domain in CODE_PREFIX_DOMAINS.items():
        prefix_lower = prefix.lower()
        # Check if starts with prefix (with common separators)
        if (node_lower.startswith(prefix_lower + '_') or
            node_lower.startswith(prefix_lower + '.') or
            node_lower.startswith(prefix_lower) and len(prefix) >= 3):
            return domain

    # Special case for e_ prefixed V-Dem
    if node_lower.startswith('e_') and len(node_id) > 3:
        rest = node_id[2:]
        for prefix, domain in CODE_PREFIX_DOMAINS.items():
            if rest.lower().startswith(prefix.lower()):
                return domain

    return None


def classify_by_label(label: str) -> str:
    """Classify node by label keywords."""
    if not label:
        return None

    label_lower = label.lower()

    # Count keyword matches per domain
    domain_scores = Counter()

    for domain, keywords in LABEL_KEYWORDS.items():
        for keyword in keywords:
            if keyword.lower() in label_lower:
                domain_scores[domain] += 1

    if domain_scores:
        # Return domain with most keyword matches
        return domain_scores.most_common(1)[0][0]

    return None


def classify_interaction(node_id: str, label: str, nodes_dict: dict) -> str:
    """Classify interaction term by its component domains."""
    if not node_id.startswith('INTERACT_'):
        return None

    # Parse interaction: INTERACT_var1_X_var2
    parts = node_id.replace('INTERACT_', '').split('_X_')
    if len(parts) != 2:
        # Try alternate parsing
        match = re.match(r'INTERACT_(.+)_X_(.+)', node_id)
        if match:
            parts = [match.group(1), match.group(2)]
        else:
            return None

    # Get domains of component variables
    component_domains = []
    for part in parts:
        # Try to find this variable in nodes_dict
        if part in nodes_dict:
            comp_domain = nodes_dict[part].get('domain')
            if comp_domain and comp_domain != 'Unknown':
                component_domains.append(comp_domain)
        else:
            # Try to classify the component directly
            comp_domain = classify_by_code(part)
            if comp_domain:
                component_domains.append(comp_domain)

    if component_domains:
        # If both same domain, use that
        if len(set(component_domains)) == 1:
            return component_domains[0]
        # If mixed, return "Cross-Domain"
        return 'Cross-Domain'

    # Try label-based classification for interaction
    if label:
        return classify_by_label(label)

    return None


def classify_node(node: dict, nodes_dict: dict) -> str:
    """Main classification function for a node."""
    node_id = node['id']
    label = node.get('label', '')

    # Already classified and not Unknown?
    current_domain = node.get('domain', 'Unknown')
    if current_domain not in ['Unknown', 'Unclassified', None, '']:
        return current_domain

    # 1. Try code-based classification
    domain = classify_by_code(node_id)
    if domain:
        return domain

    # 2. Try interaction classification
    if node_id.startswith('INTERACT_'):
        domain = classify_interaction(node_id, label, nodes_dict)
        if domain:
            return domain

    # 3. Try label-based classification
    domain = classify_by_label(label)
    if domain:
        return domain

    # 4. Check description
    description = node.get('description', '')
    if description:
        domain = classify_by_label(description)
        if domain:
            return domain

    return 'Unclassified'


def main():
    print("="*70)
    print("DOMAIN CLASSIFICATION FOR ALL 8,126 NODES")
    print("="*70)

    # Load current JSON
    json_path = Path('outputs/causal_graph_v2_FULL.json')
    print(f"\nLoading: {json_path}")

    with open(json_path, 'r') as f:
        data = json.load(f)

    nodes = data['nodes']
    print(f"Total nodes: {len(nodes)}")

    # Create lookup dict
    nodes_dict = {n['id']: n for n in nodes}

    # Initial domain distribution
    initial_domains = Counter(n.get('domain', 'Unknown') for n in nodes)
    print(f"\nInitial domain distribution:")
    for domain, count in initial_domains.most_common():
        print(f"  {domain}: {count} ({100*count/len(nodes):.1f}%)")

    # First pass: classify non-interaction nodes
    print(f"\n--- Pass 1: Non-interaction nodes ---")
    for node in nodes:
        if not node['id'].startswith('INTERACT_'):
            new_domain = classify_node(node, nodes_dict)
            node['domain'] = new_domain

    # Update nodes_dict with new domains
    nodes_dict = {n['id']: n for n in nodes}

    # Second pass: classify interaction nodes
    print(f"--- Pass 2: Interaction nodes ---")
    for node in nodes:
        if node['id'].startswith('INTERACT_'):
            new_domain = classify_node(node, nodes_dict)
            node['domain'] = new_domain

    # Final domain distribution
    final_domains = Counter(n.get('domain', 'Unknown') for n in nodes)
    print(f"\nFinal domain distribution:")
    for domain, count in final_domains.most_common():
        print(f"  {domain}: {count} ({100*count/len(nodes):.1f}%)")

    # Calculate improvement
    initial_unknown = initial_domains.get('Unknown', 0) + initial_domains.get('Unclassified', 0)
    final_unclassified = final_domains.get('Unclassified', 0)

    print(f"\n{'='*70}")
    print("CLASSIFICATION SUMMARY")
    print(f"{'='*70}")
    print(f"Initial Unknown/Unclassified: {initial_unknown} ({100*initial_unknown/len(nodes):.1f}%)")
    print(f"Final Unclassified: {final_unclassified} ({100*final_unclassified/len(nodes):.1f}%)")
    print(f"Nodes classified: {initial_unknown - final_unclassified}")

    # Save updated JSON
    print(f"\nSaving to: {json_path}")
    with open(json_path, 'w') as f:
        json.dump(data, f, indent=2)

    print(f"✅ Updated {json_path}")

    # Show sample of each domain
    print(f"\n--- Sample nodes per domain ---")
    for domain in sorted(final_domains.keys()):
        samples = [n for n in nodes if n['domain'] == domain][:2]
        print(f"\n{domain}:")
        for s in samples:
            print(f"  {s['id'][:40]:40} | {s.get('label', '')[:50]}")

    return data


if __name__ == '__main__':
    main()
