#!/usr/bin/env python3
"""
Test stratification options: Income-based vs Geographic-based
With dynamic classification (countries move between groups over time)
"""

import sys
import json
import warnings
from pathlib import Path
from collections import defaultdict

import numpy as np
import pandas as pd
import lightgbm as lgb
import shap
from scipy.stats import spearmanr

warnings.filterwarnings('ignore')

def log(msg):
    print(msg, flush=True)

# Paths
PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
PANEL_PATH = DATA_DIR / "raw" / "v21_panel_data_for_v3.parquet"
V21_HIERARCHY_PATH = Path("<repo-root>/v2.1/outputs/B5/v2_1_visualization.json")
INDICATOR_PROPS_PATH = DATA_DIR / "metadata" / "indicator_properties.json"

# Fixed 2024 World Bank income classification (since GDP per capita not in panel)
INCOME_CLASSIFICATION_2024 = {
    'Developing': [  # Low + Lower-middle income
        'Afghanistan', 'Bangladesh', 'Benin', 'Bhutan', 'Burkina Faso', 'Burundi',
        'Cambodia', 'Cameroon', 'Central African Republic', 'Chad', 'Comoros',
        'Congo, Dem. Rep.', 'Congo, Rep.', 'Cote d\'Ivoire', 'Djibouti', 'Egypt, Arab Rep.',
        'El Salvador', 'Eritrea', 'Eswatini', 'Ethiopia', 'Gambia, The', 'Ghana',
        'Guinea', 'Guinea-Bissau', 'Haiti', 'Honduras', 'India', 'Indonesia',
        'Kenya', 'Kiribati', 'Kyrgyz Republic', 'Lao PDR', 'Lesotho', 'Liberia',
        'Madagascar', 'Malawi', 'Mali', 'Mauritania', 'Micronesia, Fed. Sts.',
        'Mongolia', 'Morocco', 'Mozambique', 'Myanmar', 'Nepal', 'Nicaragua',
        'Niger', 'Nigeria', 'Pakistan', 'Papua New Guinea', 'Philippines', 'Rwanda',
        'Samoa', 'Sao Tome and Principe', 'Senegal', 'Sierra Leone', 'Solomon Islands',
        'Somalia', 'South Sudan', 'Sri Lanka', 'Sudan', 'Syrian Arab Republic',
        'Tajikistan', 'Tanzania', 'Timor-Leste', 'Togo', 'Tunisia', 'Uganda',
        'Ukraine', 'Uzbekistan', 'Vanuatu', 'Vietnam', 'Yemen, Rep.', 'Zambia', 'Zimbabwe'
    ],
    'Emerging': [  # Upper-middle income
        'Albania', 'Algeria', 'Argentina', 'Armenia', 'Azerbaijan', 'Belarus',
        'Belize', 'Bosnia and Herzegovina', 'Botswana', 'Brazil', 'Bulgaria',
        'China', 'Colombia', 'Costa Rica', 'Cuba', 'Dominica', 'Dominican Republic',
        'Ecuador', 'Equatorial Guinea', 'Fiji', 'Gabon', 'Georgia', 'Grenada',
        'Guatemala', 'Guyana', 'Iran, Islamic Rep.', 'Iraq', 'Jamaica', 'Jordan',
        'Kazakhstan', 'Kosovo', 'Lebanon', 'Libya', 'Malaysia', 'Maldives',
        'Marshall Islands', 'Mauritius', 'Mexico', 'Moldova', 'Montenegro',
        'Namibia', 'North Macedonia', 'Palau', 'Panama', 'Paraguay', 'Peru',
        'Romania', 'Russian Federation', 'Serbia', 'South Africa', 'St. Lucia',
        'St. Vincent and the Grenadines', 'Suriname', 'Thailand', 'Tonga',
        'Turkey', 'Turkmenistan', 'Tuvalu'
    ],
    'Advanced': [  # High income
        'Andorra', 'Antigua and Barbuda', 'Australia', 'Austria', 'Bahamas, The',
        'Bahrain', 'Barbados', 'Belgium', 'Brunei Darussalam', 'Canada', 'Chile',
        'Croatia', 'Cyprus', 'Czech Republic', 'Denmark', 'Estonia', 'Finland',
        'France', 'Germany', 'Greece', 'Hong Kong SAR, China', 'Hungary', 'Iceland',
        'Ireland', 'Israel', 'Italy', 'Japan', 'Korea, Rep.', 'Kuwait', 'Latvia',
        'Lithuania', 'Luxembourg', 'Macao SAR, China', 'Malta', 'Monaco', 'Nauru',
        'Netherlands', 'New Zealand', 'Norway', 'Oman', 'Poland', 'Portugal',
        'Puerto Rico', 'Qatar', 'San Marino', 'Saudi Arabia', 'Seychelles',
        'Singapore', 'Slovak Republic', 'Slovenia', 'Spain', 'St. Kitts and Nevis',
        'Sweden', 'Switzerland', 'Trinidad and Tobago', 'United Arab Emirates',
        'United Kingdom', 'United States', 'Uruguay'
    ]
}

# Geographic regions (UN classification)
GEOGRAPHIC_REGIONS = {
    'Sub-Saharan Africa': [
        'Angola', 'Benin', 'Botswana', 'Burkina Faso', 'Burundi', 'Cabo Verde',
        'Cameroon', 'Central African Republic', 'Chad', 'Comoros', 'Congo, Dem. Rep.',
        'Congo, Rep.', 'Cote d\'Ivoire', 'Equatorial Guinea', 'Eritrea', 'Eswatini',
        'Ethiopia', 'Gabon', 'Gambia, The', 'Ghana', 'Guinea', 'Guinea-Bissau',
        'Kenya', 'Lesotho', 'Liberia', 'Madagascar', 'Malawi', 'Mali', 'Mauritania',
        'Mauritius', 'Mozambique', 'Namibia', 'Niger', 'Nigeria', 'Rwanda',
        'Sao Tome and Principe', 'Senegal', 'Seychelles', 'Sierra Leone', 'Somalia',
        'South Africa', 'South Sudan', 'Sudan', 'Tanzania', 'Togo', 'Uganda',
        'Zambia', 'Zimbabwe'
    ],
    'East Asia & Pacific': [
        'Australia', 'Brunei Darussalam', 'Cambodia', 'China', 'Fiji', 'Hong Kong SAR, China',
        'Indonesia', 'Japan', 'Kiribati', 'Korea, Dem. People\'s Rep.', 'Korea, Rep.',
        'Lao PDR', 'Macao SAR, China', 'Malaysia', 'Marshall Islands', 'Micronesia, Fed. Sts.',
        'Mongolia', 'Myanmar', 'Nauru', 'New Zealand', 'Palau', 'Papua New Guinea',
        'Philippines', 'Samoa', 'Singapore', 'Solomon Islands', 'Taiwan, China',
        'Thailand', 'Timor-Leste', 'Tonga', 'Tuvalu', 'Vanuatu', 'Vietnam'
    ],
    'Europe & Central Asia': [
        'Albania', 'Armenia', 'Austria', 'Azerbaijan', 'Belarus', 'Belgium',
        'Bosnia and Herzegovina', 'Bulgaria', 'Croatia', 'Cyprus', 'Czech Republic',
        'Denmark', 'Estonia', 'Finland', 'France', 'Georgia', 'Germany', 'Greece',
        'Hungary', 'Iceland', 'Ireland', 'Italy', 'Kazakhstan', 'Kosovo',
        'Kyrgyz Republic', 'Latvia', 'Lithuania', 'Luxembourg', 'Malta', 'Moldova',
        'Monaco', 'Montenegro', 'Netherlands', 'North Macedonia', 'Norway', 'Poland',
        'Portugal', 'Romania', 'Russian Federation', 'San Marino', 'Serbia',
        'Slovak Republic', 'Slovenia', 'Spain', 'Sweden', 'Switzerland', 'Tajikistan',
        'Turkey', 'Turkmenistan', 'Ukraine', 'United Kingdom', 'Uzbekistan'
    ],
    'Latin America & Caribbean': [
        'Antigua and Barbuda', 'Argentina', 'Bahamas, The', 'Barbados', 'Belize',
        'Bolivia', 'Brazil', 'Chile', 'Colombia', 'Costa Rica', 'Cuba', 'Dominica',
        'Dominican Republic', 'Ecuador', 'El Salvador', 'Grenada', 'Guatemala',
        'Guyana', 'Haiti', 'Honduras', 'Jamaica', 'Mexico', 'Nicaragua', 'Panama',
        'Paraguay', 'Peru', 'Puerto Rico', 'St. Kitts and Nevis', 'St. Lucia',
        'St. Vincent and the Grenadines', 'Suriname', 'Trinidad and Tobago',
        'Uruguay', 'Venezuela'
    ],
    'Middle East & North Africa': [
        'Algeria', 'Bahrain', 'Djibouti', 'Egypt, Arab Rep.', 'Iran, Islamic Rep.',
        'Iraq', 'Israel', 'Jordan', 'Kuwait', 'Lebanon', 'Libya', 'Morocco', 'Oman',
        'Qatar', 'Saudi Arabia', 'Syrian Arab Republic', 'Tunisia',
        'United Arab Emirates', 'Yemen, Rep.'
    ],
    'South Asia': [
        'Afghanistan', 'Bangladesh', 'Bhutan', 'India', 'Maldives', 'Nepal',
        'Pakistan', 'Sri Lanka'
    ],
    'North America': [
        'Canada', 'United States'
    ]
}

# Income thresholds (World Bank 2024, but we'll use historical GDP for dynamic)
INCOME_THRESHOLDS = {
    'Developing': (0, 4500),        # Low + Lower-middle
    'Emerging': (4500, 14000),      # Upper-middle
    'Advanced': (14000, float('inf'))  # High
}


def load_indicator_directions():
    if not INDICATOR_PROPS_PATH.exists():
        return {}
    with open(INDICATOR_PROPS_PATH) as f:
        props = json.load(f)
    indicators = props.get('indicators', props)
    return {k: v.get('direction', 'positive') for k, v in indicators.items() if isinstance(v, dict)}


def load_v21_domains():
    with open(V21_HIERARCHY_PATH) as f:
        data = json.load(f)

    DOMAIN_KEY_MAP = {
        'Health & Longevity': 'health_longevity',
        'Education & Knowledge': 'education_knowledge',
        'Income & Living Standards': 'income_living_standards',
        'Equality & Fairness': 'equality_fairness',
        'Safety & Security': 'safety_security',
        'Governance & Democracy': 'governance_democracy',
        'Infrastructure & Access': 'infrastructure_access',
        'Employment & Work': 'employment_work',
        'Environment & Sustainability': 'environment_sustainability'
    }

    DOMAIN_SHORT_MAP = {
        'Health': 'Health & Longevity', 'Education': 'Education & Knowledge',
        'Economic': 'Income & Living Standards', 'Equality': 'Equality & Fairness',
        'Security': 'Safety & Security', 'Governance': 'Governance & Democracy',
        'Infrastructure': 'Infrastructure & Access', 'Employment': 'Employment & Work',
        'Environment': 'Environment & Sustainability'
    }

    domain_indicators = defaultdict(list)
    for node in data['nodes']:
        if isinstance(node.get('id'), str) and node.get('domain'):
            full_domain = DOMAIN_SHORT_MAP.get(node['domain'], node['domain'])
            domain_indicators[full_domain].append(node['id'])

    for outcome in data.get('outcomes', []):
        for ind in outcome.get('top_indicators', []):
            if ind not in domain_indicators[outcome['name']]:
                domain_indicators[outcome['name']].append(ind)

    domains = {}
    for domain_name, indicators in domain_indicators.items():
        domain_key = DOMAIN_KEY_MAP.get(domain_name)
        if domain_key and indicators:
            domains[domain_key] = {'name': domain_name, 'indicators': indicators}
    return domains


def get_country_gdp_by_year(panel):
    """Extract GDP per capita for each country-year for dynamic classification."""
    gdp_data = {}

    for gdp_ind in GDP_INDICATORS:
        subset = panel[panel['indicator_id'] == gdp_ind][['country', 'year', 'value']]
        if len(subset) > 0:
            for _, row in subset.iterrows():
                key = (row['country'], int(row['year']))
                if key not in gdp_data or pd.isna(gdp_data[key]):
                    gdp_data[key] = row['value']

    return gdp_data


def classify_country_by_income(gdp, thresholds=INCOME_THRESHOLDS):
    """Classify country into income group based on GDP per capita."""
    if pd.isna(gdp) or gdp is None:
        return 'Unknown'
    for group, (low, high) in thresholds.items():
        if low <= gdp < high:
            return group
    return 'Unknown'


def get_country_region(country):
    """Get geographic region for a country."""
    for region, countries in GEOGRAPHIC_REGIONS.items():
        if country in countries:
            return region
    return 'Unknown'


def create_domain_aggregates(wide, domains, indicator_directions, use_geometric=False):
    domain_aggregates = {}
    for domain_key, info in domains.items():
        available = [ind for ind in info['indicators'] if ind in wide.columns]
        if len(available) < 3:
            continue

        normalized_parts = []
        for ind in available:
            col = wide[ind]
            if col.notna().sum() < 10:
                continue
            min_val, max_val = col.min(), col.max()
            if max_val - min_val < 1e-10:
                continue
            normalized = (col - min_val) / (max_val - min_val)
            if indicator_directions.get(ind, 'positive') == 'negative':
                normalized = 1.0 - normalized
            normalized_parts.append(normalized)

        if len(normalized_parts) < 3:
            continue

        stacked = np.column_stack([p.values for p in normalized_parts])
        if use_geometric:
            stacked_safe = np.clip(stacked, 1e-10, 1.0)
            domain_agg = np.exp(np.nanmean(np.log(stacked_safe), axis=1))
        else:
            domain_agg = np.nanmean(stacked, axis=1)
        domain_aggregates[domain_key] = domain_agg
    return domain_aggregates


def compute_shap_rankings(X, y, n_bootstrap=8):
    """Compute SHAP with reduced bootstrap for speed."""
    model_params = {'n_estimators': 50, 'max_depth': 4, 'learning_rate': 0.1,
                    'subsample': 0.8, 'random_state': 42, 'verbose': -1, 'n_jobs': -1}

    shap_results = []
    for seed in range(n_bootstrap):
        np.random.seed(seed)
        idx = np.random.choice(len(X), size=len(X), replace=True)
        model = lgb.LGBMRegressor(**model_params)
        model.fit(X.iloc[idx], y.iloc[idx])

        explainer = shap.TreeExplainer(model)
        shap_results.append(np.abs(explainer.shap_values(X)).mean(axis=0))

    shap_matrix = np.array(shap_results)
    ranking = pd.Series(shap_matrix.mean(axis=0), index=X.columns).sort_values(ascending=False)
    return ranking


def compute_group_shap(panel, group_countries, domains, indicator_directions, year):
    """Compute SHAP for a group of countries."""
    subset = panel[(panel['country'].isin(group_countries)) & (panel['year'] <= year)]

    if len(subset) < 500:
        return None, f"Insufficient data: {len(subset)} rows"

    wide = subset.pivot_table(
        index=['country', 'year'],
        columns='indicator_id',
        values='value',
        aggfunc='first'
    )

    if len(wide) < 30:
        return None, f"Insufficient observations: {len(wide)}"

    agg = create_domain_aggregates(wide, domains, indicator_directions, use_geometric=True)
    if len(agg) < 3:
        return None, f"Insufficient domains: {len(agg)}"

    y = pd.Series(np.nanmean(np.column_stack(list(agg.values())), axis=1), index=wide.index)

    feature_cols = [c for c in wide.columns if wide[c].notna().sum() >= 10]
    X = wide[feature_cols][~np.isnan(y.values)]
    y = y[~np.isnan(y.values)]
    X = X.fillna(X.median()).dropna(axis=1, how='all')

    if len(X) < 30 or len(X.columns) < 20:
        return None, f"Insufficient clean data: {len(X)} obs"

    ranking = compute_shap_rankings(X, y, n_bootstrap=8)
    return ranking, len(X)


def main():
    log("=" * 70)
    log("STRATIFICATION TEST: Income vs Geographic")
    log("=" * 70)

    # Load data
    log("\nLoading data...")
    panel = pd.read_parquet(PANEL_PATH)
    log(f"  Panel: {len(panel):,} rows")

    indicator_directions = load_indicator_directions()
    domains = load_v21_domains()
    log(f"  Domains: {len(domains)}")

    # Get unique countries in panel
    panel_countries = set(panel['country'].unique())
    log(f"  Countries in panel: {len(panel_countries)}")

    # =========================================================================
    # PART 1: Show income classification
    # =========================================================================
    log("\n" + "=" * 70)
    log("PART 1: INCOME CLASSIFICATION (2024 World Bank)")
    log("=" * 70)

    # Filter to countries that exist in panel
    income_groups_2024 = {}
    for group, countries in INCOME_CLASSIFICATION_2024.items():
        in_panel = [c for c in countries if c in panel_countries]
        income_groups_2024[group] = in_panel
        log(f"  {group}: {len(in_panel)} countries (in panel)")

    # =========================================================================
    # PART 2: Compare Income vs Geographic stratification
    # =========================================================================
    log("\n" + "=" * 70)
    log("PART 2: INCOME VS GEOGRAPHIC STRATIFICATION (Year 2020)")
    log("=" * 70)

    year = 2020

    # Use fixed 2024 classification
    income_groups_2020 = income_groups_2024

    # Build geographic groups
    geo_groups_2020 = {}
    for region, region_countries in GEOGRAPHIC_REGIONS.items():
        geo_countries = [c for c in region_countries if c in panel_countries]
        if len(geo_countries) >= 10:
            geo_groups_2020[region] = geo_countries

    log(f"\nIncome groups (dynamic 2020):")
    for group, ctries in income_groups_2020.items():
        log(f"  {group}: {len(ctries)} countries")

    log(f"\nGeographic groups:")
    for region, ctries in geo_groups_2020.items():
        log(f"  {region}: {len(ctries)} countries")

    # Compute SHAP for each income group
    log("\n\nComputing SHAP for INCOME groups...")
    income_rankings = {}
    for group, group_countries in income_groups_2020.items():
        log(f"\n  Processing {group} ({len(group_countries)} countries)...")
        ranking, info = compute_group_shap(panel, group_countries, domains, indicator_directions, year)
        if ranking is not None:
            income_rankings[group] = ranking
            log(f"    SUCCESS: {info} observations")
        else:
            log(f"    FAILED: {info}")

    # Compute SHAP for each geographic group
    log("\n\nComputing SHAP for GEOGRAPHIC groups...")
    geo_rankings = {}
    for region, group_countries in geo_groups_2020.items():
        log(f"\n  Processing {region} ({len(group_countries)} countries)...")
        ranking, info = compute_group_shap(panel, group_countries, domains, indicator_directions, year)
        if ranking is not None:
            geo_rankings[region] = ranking
            log(f"    SUCCESS: {info} observations")
        else:
            log(f"    FAILED: {info}")

    # =========================================================================
    # PART 3: Compare within-group consistency
    # =========================================================================
    log("\n" + "=" * 70)
    log("PART 3: WITHIN-GROUP CONSISTENCY COMPARISON")
    log("=" * 70)

    def compute_pairwise_correlations(rankings_dict):
        """Compute average pairwise correlation between group rankings."""
        groups = list(rankings_dict.keys())
        correlations = []
        pairs = []

        for i, g1 in enumerate(groups):
            for g2 in groups[i+1:]:
                r1, r2 = rankings_dict[g1], rankings_dict[g2]
                common = list(set(r1.index) & set(r2.index))
                if len(common) >= 50:
                    corr, _ = spearmanr([r1[ind] for ind in common], [r2[ind] for ind in common])
                    correlations.append(corr)
                    pairs.append((g1, g2, corr))

        return correlations, pairs

    log("\nINCOME-BASED cross-group correlations:")
    income_corrs, income_pairs = compute_pairwise_correlations(income_rankings)
    for g1, g2, corr in income_pairs:
        log(f"  {g1} vs {g2}: {corr:.3f}")
    if income_corrs:
        log(f"  MEAN: {np.mean(income_corrs):.3f}")

    log("\nGEOGRAPHIC cross-group correlations:")
    geo_corrs, geo_pairs = compute_pairwise_correlations(geo_rankings)
    for g1, g2, corr in geo_pairs:
        log(f"  {g1} vs {g2}: {corr:.3f}")
    if geo_corrs:
        log(f"  MEAN: {np.mean(geo_corrs):.3f}")

    # =========================================================================
    # PART 4: Interpretation
    # =========================================================================
    log("\n" + "=" * 70)
    log("INTERPRETATION")
    log("=" * 70)

    income_mean = np.mean(income_corrs) if income_corrs else 0
    geo_mean = np.mean(geo_corrs) if geo_corrs else 0

    log(f"\nIncome stratification mean correlation: {income_mean:.3f}")
    log(f"Geographic stratification mean correlation: {geo_mean:.3f}")

    if income_mean < geo_mean:
        log("\n→ INCOME stratification shows MORE heterogeneity")
        log("  This means income-based groups have more DISTINCT patterns")
        log("  RECOMMENDATION: Use income-based stratification")
    else:
        log("\n→ GEOGRAPHIC stratification shows MORE heterogeneity")
        log("  Regional/cultural factors might matter more than income")
        log("  RECOMMENDATION: Consider geographic stratification")

    log("\n\nFor UNIFIED global view:")
    log("  Lower correlation = groups are more different = stratification more valuable")
    log(f"  Income groups differ by r={income_mean:.3f}")
    log(f"  Geographic groups differ by r={geo_mean:.3f}")

    # Show top indicators by group
    log("\n" + "=" * 70)
    log("TOP 10 INDICATORS BY INCOME GROUP")
    log("=" * 70)

    for group in ['Developing', 'Emerging', 'Advanced']:
        if group in income_rankings:
            log(f"\n{group.upper()}:")
            for i, (ind, val) in enumerate(income_rankings[group].head(10).items()):
                log(f"  {i+1}. {ind[:50]}")

    log("\n" + "=" * 70)
    log("TEST COMPLETE")
    log("=" * 70)


if __name__ == '__main__':
    main()
