#!/usr/bin/env python3
"""
Phase 1: Generate Regional Groups

Creates regional groupings for aggregate analysis:
- 6 Geographic regions (World Bank classification)
- 3 Income groups (World Bank classification)
- 2 Special groups (OECD, G20)

Output: data/metadata/regional_groups.json
"""

import json
from pathlib import Path
from datetime import datetime

import pandas as pd

# Paths
PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
GRAPHS_DIR = DATA_DIR / "country_graphs"
OUTPUT_PATH = DATA_DIR / "metadata" / "regional_groups.json"


# === REGIONAL DEFINITIONS ===
# Based on World Bank classifications with some adjustments

REGIONS = {
    # Geographic regions (World Bank)
    'sub_saharan_africa': {
        'name': 'Sub-Saharan Africa',
        'type': 'geographic',
        'countries': [
            'Angola', 'Benin', 'Botswana', 'Burkina Faso', 'Burundi',
            'Cameroon', 'Cape Verde', 'Central African Republic', 'Chad', 'Comoros',
            'Congo, Dem. Rep.', 'Republic of the Congo', "Cote d'Ivoire", 'Djibouti', 'Equatorial Guinea',
            'Eritrea', 'Eswatini', 'Ethiopia', 'Gabon', 'Gambia',
            'Ghana', 'Guinea', 'Guinea-Bissau', 'Kenya', 'Lesotho',
            'Liberia', 'Madagascar', 'Malawi', 'Mali', 'Mauritania',
            'Mauritius', 'Mozambique', 'Namibia', 'Niger', 'Nigeria',
            'Rwanda', 'Sao Tome and Principe', 'Senegal', 'Seychelles', 'Sierra Leone',
            'Somalia', 'South Africa', 'South Sudan', 'Sudan', 'Tanzania',
            'Togo', 'Uganda', 'Zambia', 'Zimbabwe',
            # Alternative names
            'Ivory Coast', 'The Gambia', 'DR Congo', 'Democratic Republic of the Congo'
        ]
    },

    'east_asia_pacific': {
        'name': 'East Asia & Pacific',
        'type': 'geographic',
        'countries': [
            'Australia', 'Brunei', 'Cambodia', 'China', 'Fiji',
            'Hong Kong', 'Indonesia', 'Japan', 'Kiribati', 'South Korea',
            'Laos', 'Malaysia', 'Marshall Islands', 'Micronesia', 'Mongolia',
            'Myanmar', 'Nauru', 'New Zealand', 'North Korea', 'Palau',
            'Papua New Guinea', 'Philippines', 'Samoa', 'Singapore', 'Solomon Islands',
            'Taiwan', 'Thailand', 'Timor-Leste', 'Tonga', 'Tuvalu',
            'Vanuatu', 'Vietnam',
            # Alternative names
            'Burma_Myanmar', 'Korea, Rep.', 'Korea, Dem. Rep.'
        ]
    },

    'europe_central_asia': {
        'name': 'Europe & Central Asia',
        'type': 'geographic',
        'countries': [
            'Albania', 'Armenia', 'Austria', 'Azerbaijan', 'Belarus',
            'Belgium', 'Bosnia and Herzegovina', 'Bulgaria', 'Croatia', 'Cyprus',
            'Czech Republic', 'Denmark', 'Estonia', 'Finland', 'France',
            'Georgia', 'Germany', 'Greece', 'Hungary', 'Iceland',
            'Ireland', 'Italy', 'Kazakhstan', 'Kosovo', 'Kyrgyzstan',
            'Latvia', 'Lithuania', 'Luxembourg', 'Malta', 'Moldova',
            'Monaco', 'Montenegro', 'Netherlands', 'North Macedonia', 'Norway',
            'Poland', 'Portugal', 'Romania', 'Russia', 'San Marino',
            'Serbia', 'Slovakia', 'Slovenia', 'Spain', 'Sweden',
            'Switzerland', 'Tajikistan', 'Turkey', 'Turkmenistan', 'Ukraine',
            'United Kingdom', 'Uzbekistan',
            # Alternative names
            'Türkiye', 'Russian Federation', 'Czechia', 'UK'
        ]
    },

    'latin_america_caribbean': {
        'name': 'Latin America & Caribbean',
        'type': 'geographic',
        'countries': [
            'Antigua and Barbuda', 'Argentina', 'Bahamas', 'Barbados', 'Belize',
            'Bolivia', 'Brazil', 'Chile', 'Colombia', 'Costa Rica',
            'Cuba', 'Dominica', 'Dominican Republic', 'Ecuador', 'El Salvador',
            'Grenada', 'Guatemala', 'Guyana', 'Haiti', 'Honduras',
            'Jamaica', 'Mexico', 'Nicaragua', 'Panama', 'Paraguay',
            'Peru', 'Puerto Rico', 'Saint Kitts and Nevis', 'Saint Lucia', 'Saint Vincent and the Grenadines',
            'Suriname', 'Trinidad and Tobago', 'Uruguay', 'Venezuela'
        ]
    },

    'middle_east_north_africa': {
        'name': 'Middle East & North Africa',
        'type': 'geographic',
        'countries': [
            'Algeria', 'Bahrain', 'Egypt', 'Iran', 'Iraq',
            'Israel', 'Jordan', 'Kuwait', 'Lebanon', 'Libya',
            'Morocco', 'Oman', 'Palestine', 'Qatar', 'Saudi Arabia',
            'Syria', 'Tunisia', 'United Arab Emirates', 'Yemen',
            # Alternative names
            'UAE', 'West Bank and Gaza'
        ]
    },

    'south_asia': {
        'name': 'South Asia',
        'type': 'geographic',
        'countries': [
            'Afghanistan', 'Bangladesh', 'Bhutan', 'India', 'Maldives',
            'Nepal', 'Pakistan', 'Sri Lanka'
        ]
    },

    'north_america': {
        'name': 'North America',
        'type': 'geographic',
        'countries': [
            'Canada', 'United States',
            # Alternative names
            'USA'
        ]
    },

    # Income groups (World Bank 2023 classification)
    'low_income': {
        'name': 'Low Income',
        'type': 'income',
        'description': 'GNI per capita < $1,135 (2023)',
        'countries': [
            'Afghanistan', 'Burkina Faso', 'Burundi', 'Central African Republic', 'Chad',
            'Congo, Dem. Rep.', 'Eritrea', 'Ethiopia', 'Gambia', 'Guinea',
            'Guinea-Bissau', 'Liberia', 'Madagascar', 'Malawi', 'Mali',
            'Mozambique', 'Niger', 'North Korea', 'Rwanda', 'Sierra Leone',
            'Somalia', 'South Sudan', 'Sudan', 'Syria', 'Togo',
            'Uganda', 'Yemen',
            # Alternative names
            'The Gambia', 'DR Congo'
        ]
    },

    'middle_income': {
        'name': 'Middle Income',
        'type': 'income',
        'description': 'GNI per capita $1,136-$13,845 (2023)',
        'countries': [
            # Lower middle income
            'Angola', 'Bangladesh', 'Benin', 'Bhutan', 'Bolivia',
            'Cambodia', 'Cameroon', 'Cape Verde', 'Comoros', "Cote d'Ivoire",
            'Djibouti', 'Egypt', 'El Salvador', 'Eswatini', 'Ghana',
            'Haiti', 'Honduras', 'India', 'Indonesia', 'Kenya',
            'Kiribati', 'Kyrgyzstan', 'Laos', 'Lesotho', 'Mauritania',
            'Micronesia', 'Mongolia', 'Morocco', 'Myanmar', 'Nepal',
            'Nicaragua', 'Nigeria', 'Pakistan', 'Papua New Guinea', 'Philippines',
            'Samoa', 'Sao Tome and Principe', 'Senegal', 'Solomon Islands', 'Sri Lanka',
            'Tajikistan', 'Tanzania', 'Timor-Leste', 'Tunisia', 'Ukraine',
            'Uzbekistan', 'Vanuatu', 'Vietnam', 'Zambia', 'Zimbabwe',
            # Upper middle income
            'Albania', 'Algeria', 'Argentina', 'Armenia', 'Azerbaijan',
            'Belarus', 'Belize', 'Bosnia and Herzegovina', 'Botswana', 'Brazil',
            'Bulgaria', 'China', 'Colombia', 'Costa Rica', 'Cuba',
            'Dominica', 'Dominican Republic', 'Ecuador', 'Equatorial Guinea', 'Fiji',
            'Gabon', 'Georgia', 'Grenada', 'Guatemala', 'Guyana',
            'Iran', 'Iraq', 'Jamaica', 'Jordan', 'Kazakhstan',
            'Kosovo', 'Lebanon', 'Libya', 'Malaysia', 'Maldives',
            'Marshall Islands', 'Mauritius', 'Mexico', 'Moldova', 'Montenegro',
            'Namibia', 'North Macedonia', 'Palau', 'Panama', 'Paraguay',
            'Peru', 'Romania', 'Russia', 'Serbia', 'South Africa',
            'Saint Lucia', 'Saint Vincent and the Grenadines', 'Suriname', 'Thailand', 'Tonga',
            'Turkey', 'Turkmenistan', 'Tuvalu',
            # Alternative names
            'Ivory Coast', 'Burma_Myanmar', 'Türkiye'
        ]
    },

    'high_income': {
        'name': 'High Income',
        'type': 'income',
        'description': 'GNI per capita > $13,845 (2023)',
        'countries': [
            'Andorra', 'Antigua and Barbuda', 'Australia', 'Austria', 'Bahamas',
            'Bahrain', 'Barbados', 'Belgium', 'Brunei', 'Canada',
            'Chile', 'Croatia', 'Cyprus', 'Czech Republic', 'Denmark',
            'Estonia', 'Finland', 'France', 'Germany', 'Greece',
            'Hong Kong', 'Hungary', 'Iceland', 'Ireland', 'Israel',
            'Italy', 'Japan', 'South Korea', 'Kuwait', 'Latvia',
            'Liechtenstein', 'Lithuania', 'Luxembourg', 'Malta', 'Monaco',
            'Netherlands', 'New Zealand', 'Norway', 'Oman', 'Poland',
            'Portugal', 'Puerto Rico', 'Qatar', 'Saint Kitts and Nevis', 'San Marino',
            'Saudi Arabia', 'Seychelles', 'Singapore', 'Slovakia', 'Slovenia',
            'Spain', 'Sweden', 'Switzerland', 'Taiwan', 'Trinidad and Tobago',
            'United Arab Emirates', 'United Kingdom', 'United States', 'Uruguay',
            # Alternative names
            'UAE', 'USA', 'UK', 'Korea, Rep.', 'Czechia'
        ]
    },

    # Special groupings
    'oecd': {
        'name': 'OECD',
        'type': 'organization',
        'description': 'Organisation for Economic Co-operation and Development members',
        'countries': [
            'Australia', 'Austria', 'Belgium', 'Canada', 'Chile',
            'Colombia', 'Costa Rica', 'Czech Republic', 'Denmark', 'Estonia',
            'Finland', 'France', 'Germany', 'Greece', 'Hungary',
            'Iceland', 'Ireland', 'Israel', 'Italy', 'Japan',
            'South Korea', 'Latvia', 'Lithuania', 'Luxembourg', 'Mexico',
            'Netherlands', 'New Zealand', 'Norway', 'Poland', 'Portugal',
            'Slovakia', 'Slovenia', 'Spain', 'Sweden', 'Switzerland',
            'Turkey', 'United Kingdom', 'United States',
            # Alternative names
            'Türkiye', 'USA', 'UK', 'Korea, Rep.', 'Czechia'
        ]
    }
}


def get_available_countries() -> set:
    """Get list of countries with V3.0 graphs."""
    if not GRAPHS_DIR.exists():
        return set()

    countries = set()
    for f in GRAPHS_DIR.glob('*.json'):
        countries.add(f.stem)

    return countries


def match_countries(region_countries: list, available: set) -> dict:
    """
    Match region country names to available V3.0 countries.

    Returns dict with matched countries and unmatched ones.
    """
    matched = []
    unmatched = []

    for country in region_countries:
        if country in available:
            matched.append(country)
        else:
            # Try common variations
            variations = [
                country.replace(' ', '_'),
                country.replace('_', ' '),
                country.replace(',', ''),
                country.replace('.', ''),
            ]
            found = False
            for var in variations:
                if var in available:
                    matched.append(var)
                    found = True
                    break
            if not found:
                unmatched.append(country)

    return {
        'matched': sorted(set(matched)),
        'unmatched': sorted(set(unmatched))
    }


def generate_regional_groups():
    """Generate regional groups metadata."""
    print("=" * 60)
    print("Phase 1: Generate Regional Groups")
    print("=" * 60)

    # Get available countries
    available = get_available_countries()
    print(f"Available V3.0 countries: {len(available)}")

    # Process each region
    output_regions = {}
    total_matched = 0
    total_unmatched = 0

    for region_id, region_data in REGIONS.items():
        result = match_countries(region_data['countries'], available)

        output_regions[region_id] = {
            'name': region_data['name'],
            'type': region_data['type'],
            'description': region_data.get('description', ''),
            'countries': result['matched'],
            'country_count': len(result['matched']),
            'unmatched_countries': result['unmatched']
        }

        total_matched += len(result['matched'])
        total_unmatched += len(result['unmatched'])

        print(f"\n{region_data['name']}:")
        print(f"  Matched: {len(result['matched'])}")
        print(f"  Unmatched: {len(result['unmatched'])}")

    # Build output
    output = {
        'generated_date': datetime.now().isoformat(),
        'total_regions': len(output_regions),
        'summary': {
            'geographic_regions': sum(1 for r in output_regions.values() if r['type'] == 'geographic'),
            'income_groups': sum(1 for r in output_regions.values() if r['type'] == 'income'),
            'organization_groups': sum(1 for r in output_regions.values() if r['type'] == 'organization'),
            'total_country_assignments': total_matched,
            'unmatched_entries': total_unmatched
        },
        'regions': output_regions
    }

    # Save
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, 'w') as f:
        json.dump(output, f, indent=2)

    # Print summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total regions: {len(output_regions)}")
    print(f"  Geographic: {output['summary']['geographic_regions']}")
    print(f"  Income: {output['summary']['income_groups']}")
    print(f"  Organization: {output['summary']['organization_groups']}")
    print(f"Total matched country assignments: {total_matched}")
    print(f"Unmatched entries: {total_unmatched}")
    print(f"\nSaved to: {OUTPUT_PATH}")
    print("=" * 60)

    return output


if __name__ == "__main__":
    generate_regional_groups()
