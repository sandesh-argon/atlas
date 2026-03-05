#!/usr/bin/env python3
"""
Methodology Validation - Three Critical Tests

Test 1: Failure Bias Analysis
- Are low-income countries systematically excluded?
- What % of global poor is excluded?

Test 2: Arithmetic vs Geometric Mean Sensitivity
- Do SHAP rankings change with aggregation method?
- If yes, which theory of development does our choice encode?

Test 3: Cross-Country Heterogeneity
- Do causal relationships differ by income group?
- Universal patterns vs context-dependent complexity?
"""

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

# === PATHS ===
PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
PANEL_PATH = DATA_DIR / "raw" / "v21_panel_data_for_v3.parquet"
V21_HIERARCHY_PATH = Path("<repo-root>/v2.1/outputs/B5/v2_1_visualization.json")
INDICATOR_PROPS_PATH = DATA_DIR / "metadata" / "indicator_properties.json"
CANONICAL_COUNTRIES_DIR = DATA_DIR / "v3_1_temporal_graphs" / "countries"
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "methodology_validation"

# === WORLD BANK INCOME GROUPS (2024 Classification) ===
# Source: https://datahelpdesk.worldbank.org/knowledgebase/articles/906519
INCOME_GROUPS = {
    'Low income': [
        'Afghanistan', 'Burkina Faso', 'Burundi', 'Central African Republic', 'Chad',
        'Congo, Dem. Rep.', 'Eritrea', 'Ethiopia', 'Gambia, The', 'Guinea',
        'Guinea-Bissau', 'Korea, Dem. People\'s Rep.', 'Liberia', 'Madagascar',
        'Malawi', 'Mali', 'Mozambique', 'Niger', 'Rwanda', 'Sierra Leone',
        'Somalia', 'South Sudan', 'Sudan', 'Syrian Arab Republic', 'Togo',
        'Uganda', 'Yemen, Rep.'
    ],
    'Lower middle income': [
        'Angola', 'Algeria', 'Bangladesh', 'Benin', 'Bhutan', 'Bolivia',
        'Cabo Verde', 'Cambodia', 'Cameroon', 'Comoros', 'Congo, Rep.',
        'Cote d\'Ivoire', 'Djibouti', 'Egypt, Arab Rep.', 'El Salvador',
        'Eswatini', 'Ghana', 'Haiti', 'Honduras', 'India', 'Indonesia',
        'Iran, Islamic Rep.', 'Kenya', 'Kiribati', 'Kyrgyz Republic',
        'Lao PDR', 'Lebanon', 'Lesotho', 'Mauritania', 'Micronesia, Fed. Sts.',
        'Mongolia', 'Morocco', 'Myanmar', 'Nepal', 'Nicaragua', 'Nigeria',
        'Pakistan', 'Papua New Guinea', 'Philippines', 'Samoa', 'Sao Tome and Principe',
        'Senegal', 'Solomon Islands', 'Sri Lanka', 'Tanzania', 'Tajikistan',
        'Timor-Leste', 'Tunisia', 'Ukraine', 'Uzbekistan', 'Vanuatu',
        'Vietnam', 'Zambia', 'Zimbabwe'
    ],
    'Upper middle income': [
        'Albania', 'Argentina', 'Armenia', 'Azerbaijan', 'Belarus', 'Belize',
        'Bosnia and Herzegovina', 'Botswana', 'Brazil', 'Bulgaria', 'China',
        'Colombia', 'Costa Rica', 'Cuba', 'Dominica', 'Dominican Republic',
        'Ecuador', 'Equatorial Guinea', 'Fiji', 'Gabon', 'Georgia', 'Grenada',
        'Guatemala', 'Guyana', 'Iraq', 'Jamaica', 'Jordan', 'Kazakhstan',
        'Kosovo', 'Libya', 'Malaysia', 'Maldives', 'Marshall Islands',
        'Mauritius', 'Mexico', 'Moldova', 'Montenegro', 'Namibia', 'North Macedonia',
        'Palau', 'Panama', 'Paraguay', 'Peru', 'Romania', 'Russian Federation',
        'Serbia', 'South Africa', 'St. Lucia', 'St. Vincent and the Grenadines',
        'Suriname', 'Thailand', 'Tonga', 'Turkey', 'Turkmenistan', 'Tuvalu'
    ],
    'High income': [
        'Andorra', 'Antigua and Barbuda', 'Australia', 'Austria', 'Bahamas, The',
        'Bahrain', 'Barbados', 'Belgium', 'Bermuda', 'Brunei Darussalam',
        'Canada', 'Cayman Islands', 'Channel Islands', 'Chile', 'Croatia',
        'Cyprus', 'Czech Republic', 'Denmark', 'Estonia', 'Finland', 'France',
        'Germany', 'Greece', 'Greenland', 'Hong Kong SAR, China', 'Hungary',
        'Iceland', 'Ireland', 'Isle of Man', 'Israel', 'Italy', 'Japan',
        'Korea, Rep.', 'Kuwait', 'Latvia', 'Liechtenstein', 'Lithuania',
        'Luxembourg', 'Macao SAR, China', 'Malta', 'Monaco', 'Nauru',
        'Netherlands', 'New Caledonia', 'New Zealand', 'Norway', 'Oman',
        'Poland', 'Portugal', 'Puerto Rico', 'Qatar', 'San Marino',
        'Saudi Arabia', 'Seychelles', 'Singapore', 'Slovak Republic', 'Slovenia',
        'Spain', 'St. Kitts and Nevis', 'Sweden', 'Switzerland', 'Taiwan, China',
        'Trinidad and Tobago', 'United Arab Emirates', 'United Kingdom',
        'United States', 'Uruguay', 'Virgin Islands (U.S.)'
    ]
}

# Population data (millions, approximate 2023)
POPULATION = {
    'China': 1412, 'India': 1408, 'United States': 335, 'Indonesia': 277,
    'Pakistan': 235, 'Brazil': 216, 'Nigeria': 224, 'Bangladesh': 173,
    'Russian Federation': 144, 'Mexico': 130, 'Japan': 124, 'Ethiopia': 126,
    'Philippines': 117, 'Egypt, Arab Rep.': 112, 'Vietnam': 100,
    'Congo, Dem. Rep.': 102, 'Turkey': 86, 'Iran, Islamic Rep.': 89,
    'Germany': 84, 'Thailand': 72, 'United Kingdom': 68, 'France': 68,
    'Tanzania': 67, 'South Africa': 60, 'Italy': 59, 'Kenya': 55,
    'Myanmar': 55, 'Korea, Rep.': 52, 'Colombia': 52, 'Spain': 48,
    'Uganda': 48, 'Argentina': 46, 'Algeria': 45, 'Sudan': 47,
    'Iraq': 44, 'Afghanistan': 42, 'Poland': 38, 'Canada': 40,
    'Morocco': 37, 'Saudi Arabia': 36, 'Uzbekistan': 35, 'Peru': 34,
    'Angola': 36, 'Malaysia': 34, 'Mozambique': 33, 'Ghana': 34,
    'Yemen, Rep.': 34, 'Nepal': 30, 'Venezuela': 28, 'Madagascar': 30,
    'Cameroon': 28, 'Cote d\'Ivoire': 28, 'Australia': 26, 'Niger': 27,
    'Sri Lanka': 22, 'Burkina Faso': 23, 'Mali': 23, 'Romania': 19,
    'Malawi': 20, 'Chile': 20, 'Kazakhstan': 20, 'Zambia': 20,
    'Guatemala': 18, 'Ecuador': 18, 'Syria': 23, 'Netherlands': 18,
    'Senegal': 18, 'Cambodia': 17, 'Chad': 18, 'Somalia': 18,
    'Zimbabwe': 16, 'Guinea': 14, 'Rwanda': 14, 'Benin': 13,
    'Burundi': 13, 'Tunisia': 12, 'Bolivia': 12, 'Belgium': 12,
    'Haiti': 12, 'Cuba': 11, 'South Sudan': 11, 'Dominican Republic': 11,
    'Czech Republic': 11, 'Greece': 10, 'Jordan': 11, 'Portugal': 10,
    'Azerbaijan': 10, 'Sweden': 10, 'Honduras': 10, 'United Arab Emirates': 10,
    'Hungary': 10, 'Tajikistan': 10, 'Belarus': 9, 'Austria': 9,
    'Papua New Guinea': 10, 'Serbia': 7, 'Israel': 10, 'Switzerland': 9,
    'Togo': 9, 'Sierra Leone': 9, 'Laos': 8, 'Paraguay': 7,
    'Bulgaria': 7, 'Libya': 7, 'Lebanon': 5, 'Nicaragua': 7,
    'Kyrgyz Republic': 7, 'El Salvador': 6, 'Turkmenistan': 6, 'Singapore': 6,
    'Denmark': 6, 'Finland': 6, 'Congo, Rep.': 6, 'Slovakia': 5,
    'Norway': 5, 'Oman': 5, 'Palestine': 5, 'Costa Rica': 5,
    'Liberia': 5, 'Ireland': 5, 'Central African Republic': 5, 'New Zealand': 5,
    'Mauritania': 5, 'Panama': 4, 'Kuwait': 4, 'Croatia': 4,
    'Moldova': 3, 'Georgia': 4, 'Eritrea': 4, 'Uruguay': 4,
    'Bosnia and Herzegovina': 3, 'Mongolia': 3, 'Armenia': 3, 'Jamaica': 3,
    'Qatar': 3, 'Albania': 3, 'Puerto Rico': 3, 'Lithuania': 3,
    'Namibia': 3, 'Gambia, The': 3, 'Botswana': 3, 'Gabon': 2,
    'Lesotho': 2, 'North Macedonia': 2, 'Slovenia': 2, 'Guinea-Bissau': 2,
    'Latvia': 2, 'Bahrain': 2, 'Equatorial Guinea': 2, 'Trinidad and Tobago': 1,
    'Estonia': 1, 'Timor-Leste': 1, 'Mauritius': 1, 'Eswatini': 1,
    'Djibouti': 1, 'Fiji': 1, 'Comoros': 1, 'Guyana': 1,
    'Bhutan': 1, 'Solomon Islands': 1, 'Montenegro': 1, 'Luxembourg': 1,
    'Suriname': 1, 'Cabo Verde': 1, 'Maldives': 1, 'Malta': 1,
    'Brunei Darussalam': 0.5, 'Belize': 0.4, 'Bahamas, The': 0.4,
    'Iceland': 0.4, 'Vanuatu': 0.3, 'Barbados': 0.3, 'Samoa': 0.2,
    'St. Lucia': 0.2, 'Kiribati': 0.1, 'Grenada': 0.1, 'St. Vincent and the Grenadines': 0.1,
    'Tonga': 0.1, 'Seychelles': 0.1, 'Antigua and Barbuda': 0.1,
    'Dominica': 0.1, 'Micronesia, Fed. Sts.': 0.1
}

# Create reverse lookup
def get_income_group(country):
    for group, countries in INCOME_GROUPS.items():
        if country in countries:
            return group
    return 'Unknown'


def load_indicator_directions():
    """Load indicator directions from properties file."""
    if not INDICATOR_PROPS_PATH.exists():
        return {}
    with open(INDICATOR_PROPS_PATH) as f:
        props = json.load(f)
    indicators = props.get('indicators', props)
    directions = {}
    for ind_id, info in indicators.items():
        if isinstance(info, dict):
            directions[ind_id] = info.get('direction', 'positive')
    return directions


def load_v21_domains():
    """Load V2.1 outcome domains from hierarchy."""
    with open(V21_HIERARCHY_PATH) as f:
        data = json.load(f)

    # Build domain mapping from outcomes list
    domains = {}

    # Map domain names to keys
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

    # Map short domain names (from nodes) to outcome names
    DOMAIN_SHORT_MAP = {
        'Health': 'Health & Longevity',
        'Education': 'Education & Knowledge',
        'Economic': 'Income & Living Standards',
        'Equality': 'Equality & Fairness',
        'Security': 'Safety & Security',
        'Governance': 'Governance & Democracy',
        'Infrastructure': 'Infrastructure & Access',
        'Employment': 'Employment & Work',
        'Environment': 'Environment & Sustainability'
    }

    # Get all indicator nodes grouped by domain
    domain_indicators = defaultdict(list)
    for node in data['nodes']:
        if isinstance(node.get('id'), str) and node.get('domain'):
            short_domain = node['domain']
            full_domain = DOMAIN_SHORT_MAP.get(short_domain, short_domain)
            domain_indicators[full_domain].append(node['id'])

    # Also add top_indicators from outcomes (in case some are missing)
    for outcome in data.get('outcomes', []):
        domain_name = outcome['name']
        for ind in outcome.get('top_indicators', []):
            if ind not in domain_indicators[domain_name]:
                domain_indicators[domain_name].append(ind)

    # Build final domains dict
    for domain_name, indicators in domain_indicators.items():
        domain_key = DOMAIN_KEY_MAP.get(domain_name)
        if domain_key and len(indicators) > 0:
            domains[domain_key] = {
                'name': domain_name,
                'indicators': indicators
            }

    return domains


def create_domain_aggregates(wide, domains, indicator_directions, use_geometric=False):
    """Create domain aggregates from wide-format data."""
    domain_aggregates = {}

    for domain_key, domain_info in domains.items():
        domain_indicators = domain_info['indicators']
        available = [ind for ind in domain_indicators if ind in wide.columns]

        if len(available) < 3:
            continue

        normalized_parts = []
        for ind in available:
            col = wide[ind]
            non_nan = col.notna().sum()
            if non_nan < 10:
                continue

            min_val, max_val = col.min(), col.max()
            if max_val - min_val < 1e-10:
                continue

            normalized = (col - min_val) / (max_val - min_val)

            direction = indicator_directions.get(ind, 'positive')
            if direction == 'negative':
                normalized = 1.0 - normalized

            normalized_parts.append(normalized)

        if len(normalized_parts) < 3:
            continue

        stacked = np.column_stack([p.values for p in normalized_parts])

        if use_geometric:
            # Geometric mean (add small epsilon to avoid log(0))
            stacked_safe = np.clip(stacked, 1e-10, 1.0)
            domain_agg = np.exp(np.nanmean(np.log(stacked_safe), axis=1))
        else:
            # Arithmetic mean
            domain_agg = np.nanmean(stacked, axis=1)

        domain_aggregates[domain_key] = domain_agg

    return domain_aggregates


def compute_shap_rankings(X, y, n_bootstrap=20):
    """Compute SHAP importance with bootstrap."""
    model_params = {
        'n_estimators': 100,
        'max_depth': 5,
        'learning_rate': 0.1,
        'subsample': 0.8,
        'random_state': 42,
        'verbose': -1,
        'n_jobs': -1
    }

    shap_results = []
    r2_scores = []

    for seed in range(n_bootstrap):
        np.random.seed(seed)
        idx = np.random.choice(len(X), size=len(X), replace=True)
        X_boot = X.iloc[idx]
        y_boot = y.iloc[idx]

        model = lgb.LGBMRegressor(**model_params)
        model.fit(X_boot, y_boot)

        # Get R² on full data
        y_pred = model.predict(X)
        ss_res = np.sum((y - y_pred) ** 2)
        ss_tot = np.sum((y - np.mean(y)) ** 2)
        r2 = 1 - (ss_res / ss_tot)
        r2_scores.append(r2)

        explainer = shap.TreeExplainer(model)
        shap_values = explainer.shap_values(X)
        shap_results.append(np.abs(shap_values).mean(axis=0))

    shap_matrix = np.array(shap_results)
    mean_importance = shap_matrix.mean(axis=0)

    # Create ranking
    ranking = pd.Series(mean_importance, index=X.columns).sort_values(ascending=False)

    return ranking, np.mean(r2_scores), np.std(r2_scores)


def test1_failure_bias(panel, canonical_countries):
    """Test 1: Analyze failure patterns by income group."""
    print("\n" + "=" * 70)
    print("TEST 1: FAILURE BIAS ANALYSIS")
    print("=" * 70)

    results = {
        'by_income_group': {},
        'by_country': {},
        'population_coverage': {}
    }

    MIN_INDICATORS = 20

    # Count indicators per country
    country_indicator_counts = {}
    for country in canonical_countries:
        country_data = panel[panel['country'] == country]
        n_indicators = country_data['indicator_id'].nunique()
        country_indicator_counts[country] = n_indicators

    # Classify by income group
    income_stats = defaultdict(lambda: {'total': 0, 'pass': 0, 'fail': 0, 'countries': []})

    for country, n_ind in country_indicator_counts.items():
        income_group = get_income_group(country)
        income_stats[income_group]['total'] += 1

        if n_ind >= MIN_INDICATORS:
            income_stats[income_group]['pass'] += 1
            income_stats[income_group]['countries'].append((country, n_ind, 'PASS'))
        else:
            income_stats[income_group]['fail'] += 1
            income_stats[income_group]['countries'].append((country, n_ind, 'FAIL'))

    # Print results
    print(f"\nMinimum indicators threshold: {MIN_INDICATORS}")
    print(f"\nFailure Rate by Income Group:")
    print("-" * 60)
    print(f"{'Income Group':<25} {'Total':<8} {'Pass':<8} {'Fail':<8} {'Fail %':<10}")
    print("-" * 60)

    total_pass, total_fail = 0, 0
    for group in ['Low income', 'Lower middle income', 'Upper middle income', 'High income', 'Unknown']:
        stats = income_stats[group]
        if stats['total'] > 0:
            fail_pct = stats['fail'] / stats['total'] * 100
            print(f"{group:<25} {stats['total']:<8} {stats['pass']:<8} {stats['fail']:<8} {fail_pct:<10.1f}%")
            total_pass += stats['pass']
            total_fail += stats['fail']
            results['by_income_group'][group] = {
                'total': stats['total'],
                'pass': stats['pass'],
                'fail': stats['fail'],
                'fail_rate': fail_pct / 100
            }

    print("-" * 60)
    overall_fail = total_fail / (total_pass + total_fail) * 100
    print(f"{'OVERALL':<25} {total_pass + total_fail:<8} {total_pass:<8} {total_fail:<8} {overall_fail:<10.1f}%")

    # Population coverage
    print(f"\n\nPopulation Coverage Analysis:")
    print("-" * 60)

    pop_covered = 0
    pop_total = 0
    pop_low_income_covered = 0
    pop_low_income_total = 0

    for country, n_ind in country_indicator_counts.items():
        pop = POPULATION.get(country, 0)
        pop_total += pop
        income = get_income_group(country)

        if income in ['Low income', 'Lower middle income']:
            pop_low_income_total += pop

        if n_ind >= MIN_INDICATORS:
            pop_covered += pop
            if income in ['Low income', 'Lower middle income']:
                pop_low_income_covered += pop

    # Without top 5
    top5 = ['China', 'India', 'United States', 'Indonesia', 'Pakistan']
    pop_covered_no_top5 = pop_covered - sum(POPULATION.get(c, 0) for c in top5 if country_indicator_counts.get(c, 0) >= MIN_INDICATORS)
    pop_total_no_top5 = pop_total - sum(POPULATION.get(c, 0) for c in top5)

    print(f"Total population covered: {pop_covered:.0f}M / {pop_total:.0f}M ({pop_covered/pop_total*100:.1f}%)")
    print(f"Without top 5 countries: {pop_covered_no_top5:.0f}M / {pop_total_no_top5:.0f}M ({pop_covered_no_top5/pop_total_no_top5*100:.1f}%)")
    print(f"Low/Lower-middle income: {pop_low_income_covered:.0f}M / {pop_low_income_total:.0f}M ({pop_low_income_covered/pop_low_income_total*100:.1f}%)")

    results['population_coverage'] = {
        'total': {'covered': pop_covered, 'total': pop_total, 'pct': pop_covered/pop_total},
        'without_top5': {'covered': pop_covered_no_top5, 'total': pop_total_no_top5, 'pct': pop_covered_no_top5/pop_total_no_top5},
        'low_income': {'covered': pop_low_income_covered, 'total': pop_low_income_total, 'pct': pop_low_income_covered/pop_low_income_total}
    }

    # List failed low-income countries
    print(f"\n\nFailed Low-Income Countries:")
    print("-" * 60)
    for country, n_ind, status in income_stats['Low income']['countries']:
        if status == 'FAIL':
            print(f"  {country}: {n_ind} indicators")

    return results


def test2_aggregation_sensitivity(panel, domains, indicator_directions, year=2020):
    """Test 2: Compare arithmetic vs geometric mean aggregation."""
    print("\n" + "=" * 70)
    print("TEST 2: ARITHMETIC VS GEOMETRIC MEAN SENSITIVITY")
    print("=" * 70)

    # Prepare data
    mask = panel['year'] <= year
    subset = panel[mask]

    wide = subset.pivot_table(
        index=['country', 'year'],
        columns='indicator_id',
        values='value',
        aggfunc='first'
    )

    print(f"\nData: {len(wide)} observations, {len(wide.columns)} indicators")

    # Create both targets
    domain_agg_arith = create_domain_aggregates(wide, domains, indicator_directions, use_geometric=False)
    domain_agg_geom = create_domain_aggregates(wide, domains, indicator_directions, use_geometric=True)

    print(f"Domains with data: {len(domain_agg_arith)}")

    # Create composite targets
    if len(domain_agg_arith) < 3:
        print("ERROR: Not enough domains with data")
        return None

    domain_matrix_arith = np.column_stack(list(domain_agg_arith.values()))
    domain_matrix_geom = np.column_stack(list(domain_agg_geom.values()))

    y_arith = pd.Series(np.nanmean(domain_matrix_arith, axis=1), index=wide.index, name='qol_arithmetic')
    y_geom = pd.Series(np.nanmean(domain_matrix_geom, axis=1), index=wide.index, name='qol_geometric')

    # Prepare features
    feature_cols = [c for c in wide.columns if wide[c].notna().sum() >= 10]
    X = wide[feature_cols].copy()

    # Remove rows with NaN target
    valid_mask = ~np.isnan(y_arith.values) & ~np.isnan(y_geom.values)
    X = X[valid_mask]
    y_arith = y_arith[valid_mask]
    y_geom = y_geom[valid_mask]

    X = X.fillna(X.median())
    X = X.dropna(axis=1, how='all')

    print(f"Clean samples: {len(X)}, features: {len(X.columns)}")

    # Compute SHAP rankings for both
    print(f"\nComputing SHAP for arithmetic mean target...")
    ranking_arith, r2_arith, r2_std_arith = compute_shap_rankings(X, y_arith, n_bootstrap=20)
    print(f"  Model R²: {r2_arith:.3f} ± {r2_std_arith:.3f}")

    print(f"Computing SHAP for geometric mean target...")
    ranking_geom, r2_geom, r2_std_geom = compute_shap_rankings(X, y_geom, n_bootstrap=20)
    print(f"  Model R²: {r2_geom:.3f} ± {r2_std_geom:.3f}")

    # Compare rankings
    top_n = 50
    top_arith = set(ranking_arith.head(top_n).index)
    top_geom = set(ranking_geom.head(top_n).index)
    overlap = len(top_arith & top_geom)

    # Spearman correlation on full rankings
    common_indicators = list(set(ranking_arith.index) & set(ranking_geom.index))
    spearman_corr, p_value = spearmanr(
        [ranking_arith[ind] for ind in common_indicators],
        [ranking_geom[ind] for ind in common_indicators]
    )

    print(f"\n\nRanking Comparison:")
    print("-" * 60)
    print(f"Top-{top_n} overlap: {overlap}/{top_n} ({overlap/top_n*100:.1f}%)")
    print(f"Spearman correlation: {spearman_corr:.3f} (p={p_value:.2e})")

    # Show divergent indicators
    print(f"\n\nTop 20 indicators by each method:")
    print("-" * 60)
    print(f"{'Rank':<6} {'Arithmetic':<40} {'Geometric':<40}")
    print("-" * 60)
    for i in range(20):
        arith_ind = ranking_arith.index[i][:38]
        geom_ind = ranking_geom.index[i][:38]
        marker = "*" if arith_ind != geom_ind else ""
        print(f"{i+1:<6} {arith_ind:<40} {geom_ind:<40} {marker}")

    # Interpretation
    print(f"\n\nINTERPRETATION:")
    print("-" * 60)
    if spearman_corr > 0.9:
        print("HIGH correlation (>0.9): Rankings are robust to aggregation method.")
        print("Choice of arithmetic vs geometric has minimal impact on policy conclusions.")
    elif spearman_corr > 0.7:
        print("MODERATE correlation (0.7-0.9): Some sensitivity to aggregation method.")
        print("Core findings are similar, but specific rankings differ.")
        print("Recommend: Report sensitivity analysis in final results.")
    else:
        print("LOW correlation (<0.7): Rankings are SENSITIVE to aggregation method.")
        print("Choice encodes different theories of development:")
        print("  - Arithmetic: All improvements equally valuable")
        print("  - Geometric: Fixing weak dimensions more valuable (HDI logic)")
        print("CRITICAL: Must justify choice theoretically or report both.")

    return {
        'spearman_correlation': spearman_corr,
        'p_value': p_value,
        'top_50_overlap': overlap / top_n,
        'r2_arithmetic': r2_arith,
        'r2_geometric': r2_geom,
        'ranking_arithmetic': ranking_arith.head(50).to_dict(),
        'ranking_geometric': ranking_geom.head(50).to_dict()
    }


def test3_cross_country_heterogeneity(panel, domains, indicator_directions, year=2020):
    """Test 3: Compare SHAP rankings across income groups."""
    print("\n" + "=" * 70)
    print("TEST 3: CROSS-COUNTRY HETEROGENEITY")
    print("=" * 70)

    results = {}
    rankings_by_group = {}

    # Define income group splits
    groups = {
        'Low & Lower-middle': INCOME_GROUPS['Low income'] + INCOME_GROUPS['Lower middle income'],
        'Upper-middle': INCOME_GROUPS['Upper middle income'],
        'High': INCOME_GROUPS['High income']
    }

    for group_name, countries in groups.items():
        print(f"\n\nProcessing {group_name} income countries...")

        # Filter panel to this group
        group_panel = panel[panel['country'].isin(countries)]

        if len(group_panel) < 1000:
            print(f"  Insufficient data: {len(group_panel)} rows")
            continue

        mask = group_panel['year'] <= year
        subset = group_panel[mask]

        wide = subset.pivot_table(
            index=['country', 'year'],
            columns='indicator_id',
            values='value',
            aggfunc='first'
        )

        print(f"  Data: {len(wide)} observations, {len(wide.columns)} indicators")

        if len(wide) < 50:
            print(f"  Insufficient observations")
            continue

        # Create domain aggregates
        domain_agg = create_domain_aggregates(wide, domains, indicator_directions, use_geometric=False)

        if len(domain_agg) < 3:
            print(f"  Insufficient domains: {len(domain_agg)}")
            continue

        # Create composite target
        domain_matrix = np.column_stack(list(domain_agg.values()))
        y = pd.Series(np.nanmean(domain_matrix, axis=1), index=wide.index)

        # Prepare features
        feature_cols = [c for c in wide.columns if wide[c].notna().sum() >= 10]
        X = wide[feature_cols].copy()

        valid_mask = ~np.isnan(y.values)
        X = X[valid_mask]
        y = y[valid_mask]

        X = X.fillna(X.median())
        X = X.dropna(axis=1, how='all')

        if len(X) < 30 or len(X.columns) < 20:
            print(f"  Insufficient clean data: {len(X)} obs, {len(X.columns)} features")
            continue

        print(f"  Clean: {len(X)} observations, {len(X.columns)} features")

        # Compute SHAP
        ranking, r2, r2_std = compute_shap_rankings(X, y, n_bootstrap=15)
        print(f"  Model R²: {r2:.3f} ± {r2_std:.3f}")

        rankings_by_group[group_name] = ranking
        results[group_name] = {'r2': r2, 'n_obs': len(X), 'n_features': len(X.columns)}

    # Compare rankings across groups
    print(f"\n\nCross-Group Comparison:")
    print("-" * 60)

    group_names = list(rankings_by_group.keys())
    if len(group_names) < 2:
        print("ERROR: Not enough groups with valid data")
        return None

    correlations = {}
    for i, g1 in enumerate(group_names):
        for g2 in group_names[i+1:]:
            r1 = rankings_by_group[g1]
            r2 = rankings_by_group[g2]

            common = list(set(r1.index) & set(r2.index))
            if len(common) < 20:
                print(f"{g1} vs {g2}: Insufficient common indicators ({len(common)})")
                continue

            corr, p = spearmanr([r1[ind] for ind in common], [r2[ind] for ind in common])
            correlations[f"{g1} vs {g2}"] = corr
            print(f"{g1} vs {g2}: Spearman = {corr:.3f} (p={p:.2e}, n={len(common)})")

    # Show top indicators by group
    print(f"\n\nTop 15 Indicators by Income Group:")
    print("-" * 80)

    headers = group_names[:3]
    print(f"{'Rank':<6}", end="")
    for h in headers:
        print(f"{h[:25]:<28}", end="")
    print()
    print("-" * 80)

    for i in range(15):
        print(f"{i+1:<6}", end="")
        for g in headers:
            if g in rankings_by_group:
                ind = rankings_by_group[g].index[i][:25]
                print(f"{ind:<28}", end="")
            else:
                print(f"{'N/A':<28}", end="")
        print()

    # Interpretation
    mean_corr = np.mean(list(correlations.values())) if correlations else 0

    print(f"\n\nINTERPRETATION:")
    print("-" * 60)
    print(f"Mean cross-group correlation: {mean_corr:.3f}")

    if mean_corr > 0.8:
        print("\nHIGH correlation (>0.8): Universal patterns exist.")
        print("The same indicators matter across income levels.")
        print("Finding: Development drivers are broadly consistent.")
    elif mean_corr > 0.6:
        print("\nMODERATE correlation (0.6-0.8): Partial universality.")
        print("Core drivers are similar, but importance differs by context.")
        print("Finding: General playbook exists, but weights vary.")
    else:
        print("\nLOW correlation (<0.6): Context-dependent relationships.")
        print("What matters in low-income ≠ what matters in high-income.")
        print("Finding: Need country/region-specific models.")
        print("CRITICAL: Unified global model may be inappropriate.")

    results['correlations'] = correlations
    results['mean_correlation'] = mean_corr
    results['rankings'] = {g: r.head(30).to_dict() for g, r in rankings_by_group.items()}

    return results


def main():
    print("=" * 70)
    print("METHODOLOGY VALIDATION - THREE CRITICAL TESTS")
    print("=" * 70)

    # Create output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Load data
    print("\nLoading data...")
    panel = pd.read_parquet(PANEL_PATH)
    print(f"  Panel: {len(panel):,} rows")

    # Get canonical countries
    if CANONICAL_COUNTRIES_DIR.exists():
        canonical_countries = sorted([d.name for d in CANONICAL_COUNTRIES_DIR.iterdir() if d.is_dir()])
    else:
        canonical_countries = sorted([c for c in panel['country'].unique()
                                     if not c.replace('.', '').isdigit()])
    print(f"  Countries: {len(canonical_countries)}")

    indicator_directions = load_indicator_directions()
    print(f"  Indicator directions: {len(indicator_directions)}")

    domains = load_v21_domains()
    print(f"  Domains: {len(domains)}")

    all_results = {}

    # Test 1: Failure Bias
    all_results['test1_failure_bias'] = test1_failure_bias(panel, canonical_countries)

    # Test 2: Aggregation Sensitivity
    all_results['test2_aggregation'] = test2_aggregation_sensitivity(panel, domains, indicator_directions)

    # Test 3: Cross-Country Heterogeneity
    all_results['test3_heterogeneity'] = test3_cross_country_heterogeneity(panel, domains, indicator_directions)

    # Save results
    output_path = OUTPUT_DIR / "methodology_validation_results.json"

    # Convert numpy types for JSON serialization
    def convert_numpy(obj):
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, (np.float32, np.float64)):
            return float(obj)
        elif isinstance(obj, (np.int32, np.int64)):
            return int(obj)
        elif isinstance(obj, dict):
            return {k: convert_numpy(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [convert_numpy(i) for i in obj]
        return obj

    all_results = convert_numpy(all_results)

    with open(output_path, 'w') as f:
        json.dump(all_results, f, indent=2)

    print(f"\n\n{'=' * 70}")
    print("VALIDATION COMPLETE")
    print(f"{'=' * 70}")
    print(f"Results saved to: {output_path}")

    # Summary
    print(f"\n\nSUMMARY:")
    print("-" * 60)

    if all_results.get('test1_failure_bias'):
        low_fail = all_results['test1_failure_bias']['by_income_group'].get('Low income', {}).get('fail_rate', 0)
        high_fail = all_results['test1_failure_bias']['by_income_group'].get('High income', {}).get('fail_rate', 0)
        print(f"Test 1 - Failure Bias: Low-income fail rate {low_fail*100:.1f}% vs High-income {high_fail*100:.1f}%")

    if all_results.get('test2_aggregation'):
        spearman = all_results['test2_aggregation'].get('spearman_correlation', 0)
        print(f"Test 2 - Aggregation: Spearman correlation {spearman:.3f}")

    if all_results.get('test3_heterogeneity'):
        mean_corr = all_results['test3_heterogeneity'].get('mean_correlation', 0)
        print(f"Test 3 - Heterogeneity: Mean cross-group correlation {mean_corr:.3f}")


if __name__ == '__main__':
    main()
