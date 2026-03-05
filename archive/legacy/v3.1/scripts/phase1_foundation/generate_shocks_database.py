#!/usr/bin/env python3
"""
Phase 1: Generate External Shocks Database

Creates database of major historical events that could cause structural breaks:
- Armed conflicts and wars
- Economic/financial crises
- Pandemics and epidemics
- Regime changes and political transitions
- Major policy changes (WTO, EU accession)

Output: data/metadata/external_shocks.json

Note: This database is curated from historical records.
"""

import json
from pathlib import Path
from datetime import datetime

# Paths
PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_PATH = DATA_DIR / "metadata" / "external_shocks.json"


# === EXTERNAL SHOCKS DATABASE ===
# Curated list of major events that could cause structural breaks in development indicators

SHOCKS = [
    # === GLOBAL EVENTS ===
    {
        'id': 'global_2008_financial_crisis',
        'year': 2008,
        'end_year': 2010,
        'country': 'global',
        'affected_countries': ['United States', 'United Kingdom', 'Germany', 'France', 'Spain', 'Greece', 'Ireland', 'Iceland'],
        'type': 'economic_crisis',
        'severity': 'high',
        'name': 'Global Financial Crisis',
        'description': 'Subprime mortgage crisis leading to global recession',
        'affected_domains': ['economic', 'governance'],
        'expected_effects': {
            'gdp': 'negative',
            'unemployment': 'increase',
            'trade': 'decrease'
        },
        'source': 'IMF World Economic Outlook'
    },
    {
        'id': 'global_2020_covid',
        'year': 2020,
        'end_year': 2022,
        'country': 'global',
        'affected_countries': 'all',
        'type': 'pandemic',
        'severity': 'extreme',
        'name': 'COVID-19 Pandemic',
        'description': 'Global pandemic causing health and economic disruption',
        'affected_domains': ['health', 'economic', 'education'],
        'expected_effects': {
            'life_expectancy': 'negative',
            'gdp': 'negative',
            'school_enrollment': 'negative'
        },
        'source': 'WHO, World Bank'
    },
    {
        'id': 'global_1997_asian_crisis',
        'year': 1997,
        'end_year': 1998,
        'country': 'global',
        'affected_countries': ['Thailand', 'Indonesia', 'South Korea', 'Malaysia', 'Philippines', 'Hong Kong', 'Singapore'],
        'type': 'economic_crisis',
        'severity': 'high',
        'name': 'Asian Financial Crisis',
        'description': 'Currency and debt crisis in East Asia',
        'affected_domains': ['economic'],
        'expected_effects': {
            'gdp': 'negative',
            'currency': 'depreciate'
        },
        'source': 'IMF'
    },

    # === AFRICAN CONFLICTS ===
    {
        'id': 'rwa_1994_genocide',
        'year': 1994,
        'end_year': 1994,
        'country': 'Rwanda',
        'type': 'conflict',
        'severity': 'extreme',
        'name': 'Rwandan Genocide',
        'description': 'Genocide against Tutsi population',
        'affected_domains': ['all'],
        'expected_effects': {
            'life_expectancy': 'extreme_negative',
            'gdp': 'negative',
            'all_indicators': 'disrupted'
        },
        'should_exclude_from_training': True,
        'source': 'UN, Human Rights Watch'
    },
    {
        'id': 'eth_1983_famine',
        'year': 1983,
        'end_year': 1985,
        'country': 'Ethiopia',
        'type': 'famine',
        'severity': 'extreme',
        'name': 'Ethiopian Famine',
        'description': 'Major famine causing mass mortality',
        'affected_domains': ['health', 'demographics'],
        'expected_effects': {
            'life_expectancy': 'extreme_negative',
            'infant_mortality': 'increase'
        },
        'source': 'UN OCHA'
    },
    {
        'id': 'ssd_2011_independence',
        'year': 2011,
        'country': 'South Sudan',
        'type': 'regime_change',
        'severity': 'medium',
        'name': 'South Sudan Independence',
        'description': 'Independence from Sudan, new country formation',
        'affected_domains': ['all'],
        'expected_effects': {
            'data_availability': 'new_series'
        },
        'source': 'UN'
    },
    {
        'id': 'ssd_2013_civil_war',
        'year': 2013,
        'end_year': 2020,
        'country': 'South Sudan',
        'type': 'conflict',
        'severity': 'high',
        'name': 'South Sudanese Civil War',
        'description': 'Civil war causing humanitarian crisis',
        'affected_domains': ['all'],
        'expected_effects': {
            'life_expectancy': 'negative',
            'gdp': 'negative'
        },
        'source': 'UN, ACLED'
    },
    {
        'id': 'cod_1998_war',
        'year': 1998,
        'end_year': 2003,
        'country': 'Congo, Dem. Rep.',
        'type': 'conflict',
        'severity': 'extreme',
        'name': 'Second Congo War',
        'description': 'Deadliest conflict since WWII',
        'affected_domains': ['all'],
        'expected_effects': {
            'life_expectancy': 'extreme_negative',
            'all_indicators': 'disrupted'
        },
        'should_exclude_from_training': True,
        'source': 'UN, IRC'
    },
    {
        'id': 'som_1991_civil_war',
        'year': 1991,
        'end_year': 2012,
        'country': 'Somalia',
        'type': 'conflict',
        'severity': 'extreme',
        'name': 'Somali Civil War',
        'description': 'State collapse and ongoing conflict',
        'affected_domains': ['all'],
        'expected_effects': {
            'all_indicators': 'disrupted'
        },
        'should_exclude_from_training': True,
        'source': 'UN, ACLED'
    },

    # === MIDDLE EAST CONFLICTS ===
    {
        'id': 'syr_2011_civil_war',
        'year': 2011,
        'end_year': None,
        'country': 'Syria',
        'type': 'conflict',
        'severity': 'extreme',
        'name': 'Syrian Civil War',
        'description': 'Ongoing civil war causing mass displacement',
        'affected_domains': ['all'],
        'expected_effects': {
            'life_expectancy': 'extreme_negative',
            'gdp': 'extreme_negative',
            'population': 'decrease'
        },
        'should_exclude_from_training': True,
        'source': 'UN, Syrian Observatory'
    },
    {
        'id': 'irq_2003_war',
        'year': 2003,
        'end_year': 2011,
        'country': 'Iraq',
        'type': 'conflict',
        'severity': 'high',
        'name': 'Iraq War',
        'description': 'US invasion and subsequent insurgency',
        'affected_domains': ['all'],
        'expected_effects': {
            'life_expectancy': 'negative',
            'gdp': 'mixed'
        },
        'source': 'UN, DoD'
    },
    {
        'id': 'yem_2014_civil_war',
        'year': 2014,
        'end_year': None,
        'country': 'Yemen',
        'type': 'conflict',
        'severity': 'extreme',
        'name': 'Yemeni Civil War',
        'description': 'Ongoing civil war and humanitarian crisis',
        'affected_domains': ['all'],
        'expected_effects': {
            'life_expectancy': 'extreme_negative',
            'famine': True
        },
        'should_exclude_from_training': True,
        'source': 'UN OCHA'
    },

    # === EUROPEAN EVENTS ===
    {
        'id': 'ussr_1991_collapse',
        'year': 1991,
        'end_year': 1991,
        'country': 'global',
        'affected_countries': ['Russia', 'Ukraine', 'Belarus', 'Kazakhstan', 'Uzbekistan', 'Turkmenistan',
                               'Kyrgyzstan', 'Tajikistan', 'Armenia', 'Azerbaijan', 'Georgia', 'Moldova',
                               'Latvia', 'Lithuania', 'Estonia'],
        'type': 'regime_change',
        'severity': 'high',
        'name': 'Soviet Union Collapse',
        'description': 'Dissolution of USSR, formation of new states',
        'affected_domains': ['all'],
        'expected_effects': {
            'gdp': 'negative',
            'life_expectancy': 'negative',
            'data_availability': 'new_series'
        },
        'source': 'World Bank'
    },
    {
        'id': 'yug_1991_breakup',
        'year': 1991,
        'end_year': 2001,
        'country': 'global',
        'affected_countries': ['Serbia', 'Croatia', 'Bosnia and Herzegovina', 'Slovenia', 'Montenegro',
                               'North Macedonia', 'Kosovo'],
        'type': 'conflict',
        'severity': 'high',
        'name': 'Yugoslav Wars',
        'description': 'Series of ethnic conflicts during Yugoslavia breakup',
        'affected_domains': ['all'],
        'expected_effects': {
            'life_expectancy': 'negative',
            'gdp': 'negative'
        },
        'source': 'UN, ICTY'
    },
    {
        'id': 'ukr_2022_war',
        'year': 2022,
        'end_year': None,
        'country': 'Ukraine',
        'type': 'conflict',
        'severity': 'extreme',
        'name': 'Russia-Ukraine War',
        'description': 'Full-scale Russian invasion of Ukraine',
        'affected_domains': ['all'],
        'expected_effects': {
            'life_expectancy': 'negative',
            'gdp': 'extreme_negative',
            'population': 'decrease'
        },
        'should_exclude_from_training': True,
        'source': 'UN, World Bank'
    },
    {
        'id': 'grc_2010_debt_crisis',
        'year': 2010,
        'end_year': 2018,
        'country': 'Greece',
        'type': 'economic_crisis',
        'severity': 'high',
        'name': 'Greek Debt Crisis',
        'description': 'Sovereign debt crisis and austerity measures',
        'affected_domains': ['economic', 'health'],
        'expected_effects': {
            'gdp': 'negative',
            'unemployment': 'increase'
        },
        'source': 'IMF, ECB'
    },

    # === ASIAN EVENTS ===
    {
        'id': 'chn_2001_wto',
        'year': 2001,
        'country': 'China',
        'type': 'policy_change',
        'severity': 'medium',
        'name': 'China WTO Accession',
        'description': 'China joins World Trade Organization',
        'affected_domains': ['economic'],
        'expected_effects': {
            'trade': 'increase',
            'gdp': 'positive'
        },
        'source': 'WTO'
    },
    {
        'id': 'khm_1975_genocide',
        'year': 1975,
        'end_year': 1979,
        'country': 'Cambodia',
        'type': 'conflict',
        'severity': 'extreme',
        'name': 'Cambodian Genocide (Khmer Rouge)',
        'description': 'Mass killings under Pol Pot regime',
        'affected_domains': ['all'],
        'expected_effects': {
            'life_expectancy': 'extreme_negative',
            'population': 'decrease'
        },
        'should_exclude_from_training': True,
        'source': 'UN, DC-Cam'
    },
    {
        'id': 'mmr_2021_coup',
        'year': 2021,
        'end_year': None,
        'country': 'Myanmar',
        'type': 'regime_change',
        'severity': 'high',
        'name': 'Myanmar Military Coup',
        'description': 'Military coup and subsequent civil unrest',
        'affected_domains': ['governance', 'economic'],
        'expected_effects': {
            'democracy': 'negative',
            'gdp': 'negative'
        },
        'source': 'UN, ASEAN'
    },
    {
        'id': 'lka_1983_civil_war',
        'year': 1983,
        'end_year': 2009,
        'country': 'Sri Lanka',
        'type': 'conflict',
        'severity': 'high',
        'name': 'Sri Lankan Civil War',
        'description': 'Ethnic conflict between government and Tamil Tigers',
        'affected_domains': ['security', 'economic'],
        'expected_effects': {
            'gdp': 'negative',
            'tourism': 'negative'
        },
        'source': 'UN'
    },
    {
        'id': 'afg_2001_invasion',
        'year': 2001,
        'end_year': 2021,
        'country': 'Afghanistan',
        'type': 'conflict',
        'severity': 'high',
        'name': 'War in Afghanistan',
        'description': 'US-led invasion following 9/11',
        'affected_domains': ['all'],
        'expected_effects': {
            'mixed': True
        },
        'source': 'UN, DoD'
    },
    {
        'id': 'afg_2021_taliban',
        'year': 2021,
        'end_year': None,
        'country': 'Afghanistan',
        'type': 'regime_change',
        'severity': 'high',
        'name': 'Taliban Takeover',
        'description': 'Taliban regains control, international isolation',
        'affected_domains': ['all'],
        'expected_effects': {
            'gdp': 'extreme_negative',
            'education': 'negative',
            'womens_rights': 'negative'
        },
        'source': 'UN, World Bank'
    },

    # === LATIN AMERICA ===
    {
        'id': 'arg_2001_crisis',
        'year': 2001,
        'end_year': 2002,
        'country': 'Argentina',
        'type': 'economic_crisis',
        'severity': 'high',
        'name': 'Argentine Economic Crisis',
        'description': 'Currency board collapse and default',
        'affected_domains': ['economic'],
        'expected_effects': {
            'gdp': 'negative',
            'poverty': 'increase'
        },
        'source': 'IMF'
    },
    {
        'id': 'ven_2014_crisis',
        'year': 2014,
        'end_year': None,
        'country': 'Venezuela',
        'type': 'economic_crisis',
        'severity': 'extreme',
        'name': 'Venezuelan Crisis',
        'description': 'Hyperinflation and economic collapse',
        'affected_domains': ['economic', 'health'],
        'expected_effects': {
            'gdp': 'extreme_negative',
            'inflation': 'extreme',
            'emigration': 'increase'
        },
        'source': 'IMF, UN'
    },
    {
        'id': 'hti_2010_earthquake',
        'year': 2010,
        'country': 'Haiti',
        'type': 'natural_disaster',
        'severity': 'extreme',
        'name': 'Haiti Earthquake',
        'description': 'Magnitude 7.0 earthquake devastating Port-au-Prince',
        'affected_domains': ['all'],
        'expected_effects': {
            'gdp': 'negative',
            'infrastructure': 'destroyed'
        },
        'source': 'UN, USGS'
    },

    # === PANDEMICS/EPIDEMICS ===
    {
        'id': 'global_hiv_peak',
        'year': 1995,
        'end_year': 2005,
        'country': 'global',
        'affected_countries': ['South Africa', 'Botswana', 'Zimbabwe', 'Lesotho', 'Eswatini',
                               'Namibia', 'Zambia', 'Malawi', 'Mozambique', 'Uganda', 'Kenya', 'Tanzania'],
        'type': 'epidemic',
        'severity': 'extreme',
        'name': 'HIV/AIDS Epidemic Peak',
        'description': 'Peak of HIV/AIDS epidemic in Sub-Saharan Africa',
        'affected_domains': ['health', 'demographics'],
        'expected_effects': {
            'life_expectancy': 'extreme_negative',
            'infant_mortality': 'increase'
        },
        'source': 'UNAIDS, WHO'
    },
    {
        'id': 'waf_2014_ebola',
        'year': 2014,
        'end_year': 2016,
        'country': 'global',
        'affected_countries': ['Sierra Leone', 'Liberia', 'Guinea'],
        'type': 'epidemic',
        'severity': 'high',
        'name': 'West African Ebola Outbreak',
        'description': 'Largest Ebola outbreak in history',
        'affected_domains': ['health', 'economic'],
        'expected_effects': {
            'health_system': 'overwhelmed',
            'gdp': 'negative'
        },
        'source': 'WHO, CDC'
    },

    # === MAJOR POLICY CHANGES ===
    {
        'id': 'eu_2004_expansion',
        'year': 2004,
        'country': 'global',
        'affected_countries': ['Poland', 'Czech Republic', 'Hungary', 'Slovakia', 'Slovenia',
                               'Estonia', 'Latvia', 'Lithuania', 'Malta', 'Cyprus'],
        'type': 'policy_change',
        'severity': 'medium',
        'name': 'EU Eastern Expansion',
        'description': 'Major EU expansion to Eastern Europe',
        'affected_domains': ['economic', 'governance'],
        'expected_effects': {
            'gdp': 'positive',
            'migration': 'increase'
        },
        'source': 'European Commission'
    },
    {
        'id': 'gbr_2016_brexit',
        'year': 2016,
        'end_year': 2020,
        'country': 'United Kingdom',
        'type': 'policy_change',
        'severity': 'medium',
        'name': 'Brexit',
        'description': 'UK referendum and withdrawal from EU',
        'affected_domains': ['economic', 'governance'],
        'expected_effects': {
            'trade': 'decrease',
            'gdp': 'mixed'
        },
        'source': 'UK Government, EU'
    },
    {
        'id': 'zaf_1994_apartheid_end',
        'year': 1994,
        'country': 'South Africa',
        'type': 'regime_change',
        'severity': 'medium',
        'name': 'End of Apartheid',
        'description': 'First democratic elections, end of apartheid',
        'affected_domains': ['governance', 'economic'],
        'expected_effects': {
            'democracy': 'positive',
            'equality': 'positive'
        },
        'source': 'South African Government'
    },
]


def generate_shocks_database():
    """Generate external shocks database."""
    print("=" * 60)
    print("Phase 1: Generate External Shocks Database")
    print("=" * 60)

    # Organize shocks by type
    by_type = {}
    by_country = {}
    by_year = {}

    for shock in SHOCKS:
        # By type
        shock_type = shock['type']
        if shock_type not in by_type:
            by_type[shock_type] = []
        by_type[shock_type].append(shock['id'])

        # By country
        country = shock['country']
        if country not in by_country:
            by_country[country] = []
        by_country[country].append(shock['id'])

        # By year
        year = shock['year']
        if year not in by_year:
            by_year[year] = []
        by_year[year].append(shock['id'])

    # Build output
    output = {
        'generated_date': datetime.now().isoformat(),
        'total_shocks': len(SHOCKS),
        'summary': {
            'by_type': {k: len(v) for k, v in by_type.items()},
            'countries_affected': len(by_country),
            'years_covered': len(by_year),
            'exclude_from_training': sum(1 for s in SHOCKS if s.get('should_exclude_from_training', False))
        },
        'shocks': {s['id']: s for s in SHOCKS},
        'indices': {
            'by_type': by_type,
            'by_country': by_country,
            'by_year': {str(k): v for k, v in sorted(by_year.items())}
        }
    }

    # Save
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, 'w') as f:
        json.dump(output, f, indent=2)

    # Print summary
    print(f"\nTotal shocks documented: {len(SHOCKS)}")
    print("\nBy type:")
    for shock_type, count in sorted(by_type.items(), key=lambda x: -len(x[1])):
        print(f"  {shock_type}: {len(count)}")

    print(f"\nCountries with documented shocks: {len(by_country)}")
    print(f"Shocks to exclude from training: {output['summary']['exclude_from_training']}")

    print(f"\nSaved to: {OUTPUT_PATH}")
    print("=" * 60)

    return output


if __name__ == "__main__":
    generate_shocks_database()
