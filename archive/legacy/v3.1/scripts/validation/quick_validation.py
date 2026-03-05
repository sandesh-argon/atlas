#!/usr/bin/env python3
"""Quick methodology validation with fewer bootstrap iterations."""

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
CANONICAL_COUNTRIES_DIR = DATA_DIR / "v3_1_temporal_graphs" / "countries"

# World Bank income groups (abbreviated)
INCOME_GROUPS = {
    'Low income': ['Afghanistan', 'Burkina Faso', 'Burundi', 'Central African Republic', 'Chad',
        'Congo, Dem. Rep.', 'Ethiopia', 'Gambia, The', 'Guinea', 'Liberia', 'Madagascar',
        'Malawi', 'Mali', 'Mozambique', 'Niger', 'Rwanda', 'Sierra Leone', 'Somalia', 
        'South Sudan', 'Sudan', 'Togo', 'Uganda', 'Yemen, Rep.'],
    'Lower middle income': ['Bangladesh', 'Benin', 'Cambodia', 'Cameroon', 'Egypt, Arab Rep.',
        'Ghana', 'Haiti', 'Honduras', 'India', 'Indonesia', 'Kenya', 'Morocco', 'Myanmar',
        'Nepal', 'Nicaragua', 'Nigeria', 'Pakistan', 'Philippines', 'Senegal', 'Sri Lanka',
        'Tanzania', 'Tunisia', 'Ukraine', 'Vietnam', 'Zambia', 'Zimbabwe'],
    'Upper middle income': ['Albania', 'Argentina', 'Brazil', 'Bulgaria', 'China', 'Colombia',
        'Costa Rica', 'Dominican Republic', 'Ecuador', 'Guatemala', 'Jamaica', 'Jordan',
        'Kazakhstan', 'Malaysia', 'Mexico', 'Panama', 'Peru', 'Romania', 'Russia',
        'Serbia', 'South Africa', 'Thailand', 'Turkey'],
    'High income': ['Australia', 'Austria', 'Belgium', 'Canada', 'Chile', 'Czech Republic',
        'Denmark', 'Finland', 'France', 'Germany', 'Greece', 'Hungary', 'Ireland', 'Israel',
        'Italy', 'Japan', 'Korea, Rep.', 'Netherlands', 'New Zealand', 'Norway', 'Poland',
        'Portugal', 'Saudi Arabia', 'Singapore', 'Spain', 'Sweden', 'Switzerland',
        'United Arab Emirates', 'United Kingdom', 'United States', 'Uruguay']
}

POPULATION = {'China': 1412, 'India': 1408, 'United States': 335, 'Indonesia': 277,
    'Pakistan': 235, 'Brazil': 216, 'Nigeria': 224, 'Bangladesh': 173}

def get_income_group(country):
    for group, countries in INCOME_GROUPS.items():
        if country in countries:
            return group
    return 'Unknown'

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

def compute_shap_rankings(X, y, n_bootstrap=10):
    """Compute SHAP with reduced bootstrap for speed."""
    model_params = {'n_estimators': 50, 'max_depth': 4, 'learning_rate': 0.1,
                    'subsample': 0.8, 'random_state': 42, 'verbose': -1, 'n_jobs': -1}
    
    shap_results, r2_scores = [], []
    for seed in range(n_bootstrap):
        np.random.seed(seed)
        idx = np.random.choice(len(X), size=len(X), replace=True)
        model = lgb.LGBMRegressor(**model_params)
        model.fit(X.iloc[idx], y.iloc[idx])
        
        y_pred = model.predict(X)
        ss_res, ss_tot = np.sum((y - y_pred) ** 2), np.sum((y - np.mean(y)) ** 2)
        r2_scores.append(1 - (ss_res / ss_tot))
        
        explainer = shap.TreeExplainer(model)
        shap_results.append(np.abs(explainer.shap_values(X)).mean(axis=0))
    
    shap_matrix = np.array(shap_results)
    ranking = pd.Series(shap_matrix.mean(axis=0), index=X.columns).sort_values(ascending=False)
    return ranking, np.mean(r2_scores), np.std(r2_scores)

def main():
    log("=" * 70)
    log("QUICK METHODOLOGY VALIDATION")
    log("=" * 70)
    
    # Test 1: Failure Bias
    log("\nLoading data...")
    panel = pd.read_parquet(PANEL_PATH)
    log(f"  Panel: {len(panel):,} rows")
    
    if CANONICAL_COUNTRIES_DIR.exists():
        canonical_countries = sorted([d.name for d in CANONICAL_COUNTRIES_DIR.iterdir() if d.is_dir()])
    else:
        canonical_countries = sorted([c for c in panel['country'].unique() if not c.replace('.', '').isdigit()])
    log(f"  Countries: {len(canonical_countries)}")
    
    indicator_directions = load_indicator_directions()
    log(f"  Indicator directions: {len(indicator_directions)}")
    
    domains = load_v21_domains()
    log(f"  Domains: {len(domains)}")
    for k, v in domains.items():
        log(f"    {k}: {len(v['indicators'])} indicators")
    
    # Test 1: Failure Bias
    log("\n" + "=" * 70)
    log("TEST 1: FAILURE BIAS ANALYSIS")
    log("=" * 70)
    
    MIN_INDICATORS = 20
    country_counts = {c: panel[panel['country'] == c]['indicator_id'].nunique() for c in canonical_countries}
    
    income_stats = defaultdict(lambda: {'total': 0, 'pass': 0, 'fail': 0})
    for country, n_ind in country_counts.items():
        group = get_income_group(country)
        income_stats[group]['total'] += 1
        if n_ind >= MIN_INDICATORS:
            income_stats[group]['pass'] += 1
        else:
            income_stats[group]['fail'] += 1
    
    log(f"\nFailure Rate by Income Group (threshold: {MIN_INDICATORS} indicators):")
    log("-" * 60)
    for group in ['Low income', 'Lower middle income', 'Upper middle income', 'High income', 'Unknown']:
        s = income_stats[group]
        if s['total'] > 0:
            fail_pct = s['fail'] / s['total'] * 100
            log(f"{group:<25} {s['total']:<8} Pass: {s['pass']:<6} Fail: {s['fail']:<6} ({fail_pct:.1f}%)")
    
    # Test 2: Aggregation Sensitivity
    log("\n" + "=" * 70)
    log("TEST 2: ARITHMETIC VS GEOMETRIC MEAN")
    log("=" * 70)
    
    year = 2020
    subset = panel[panel['year'] <= year]
    wide = subset.pivot_table(index=['country', 'year'], columns='indicator_id', values='value', aggfunc='first')
    log(f"\nData: {len(wide)} observations, {len(wide.columns)} indicators")
    
    agg_arith = create_domain_aggregates(wide, domains, indicator_directions, use_geometric=False)
    agg_geom = create_domain_aggregates(wide, domains, indicator_directions, use_geometric=True)
    log(f"Domains with data: {len(agg_arith)}")
    
    if len(agg_arith) >= 3:
        y_arith = pd.Series(np.nanmean(np.column_stack(list(agg_arith.values())), axis=1), index=wide.index)
        y_geom = pd.Series(np.nanmean(np.column_stack(list(agg_geom.values())), axis=1), index=wide.index)
        
        feature_cols = [c for c in wide.columns if wide[c].notna().sum() >= 10]
        X = wide[feature_cols].copy()
        valid_mask = ~np.isnan(y_arith.values) & ~np.isnan(y_geom.values)
        X, y_arith, y_geom = X[valid_mask], y_arith[valid_mask], y_geom[valid_mask]
        X = X.fillna(X.median()).dropna(axis=1, how='all')
        log(f"Clean: {len(X)} observations, {len(X.columns)} features")
        
        log("\nComputing SHAP for arithmetic mean target...")
        rank_arith, r2_arith, _ = compute_shap_rankings(X, y_arith, n_bootstrap=10)
        log(f"  R²: {r2_arith:.3f}")
        
        log("Computing SHAP for geometric mean target...")
        rank_geom, r2_geom, _ = compute_shap_rankings(X, y_geom, n_bootstrap=10)
        log(f"  R²: {r2_geom:.3f}")
        
        common = list(set(rank_arith.index) & set(rank_geom.index))
        spearman, p = spearmanr([rank_arith[i] for i in common], [rank_geom[i] for i in common])
        
        top_n = 30
        overlap = len(set(rank_arith.head(top_n).index) & set(rank_geom.head(top_n).index))
        
        log(f"\nResults:")
        log(f"  Spearman correlation: {spearman:.3f} (p={p:.2e})")
        log(f"  Top-{top_n} overlap: {overlap}/{top_n} ({overlap/top_n*100:.1f}%)")
        
        if spearman > 0.9:
            log("  INTERPRETATION: Rankings ROBUST to aggregation choice")
        elif spearman > 0.7:
            log("  INTERPRETATION: MODERATE sensitivity - report both")
        else:
            log("  INTERPRETATION: HIGH sensitivity - must justify choice")
    
    # Test 3: Cross-Country Heterogeneity
    log("\n" + "=" * 70)
    log("TEST 3: CROSS-COUNTRY HETEROGENEITY")
    log("=" * 70)
    
    groups = {
        'Low+Lower-mid': INCOME_GROUPS['Low income'] + INCOME_GROUPS['Lower middle income'],
        'Upper-middle': INCOME_GROUPS['Upper middle income'],
        'High': INCOME_GROUPS['High income']
    }
    
    rankings = {}
    for group_name, countries in groups.items():
        log(f"\nProcessing {group_name}...")
        group_data = panel[panel['country'].isin(countries) & (panel['year'] <= year)]
        
        if len(group_data) < 1000:
            log(f"  Insufficient data: {len(group_data)} rows")
            continue
        
        wide = group_data.pivot_table(index=['country', 'year'], columns='indicator_id', values='value', aggfunc='first')
        log(f"  Data: {len(wide)} obs, {len(wide.columns)} indicators")
        
        agg = create_domain_aggregates(wide, domains, indicator_directions, False)
        if len(agg) < 3:
            log(f"  Insufficient domains: {len(agg)}")
            continue
        
        y = pd.Series(np.nanmean(np.column_stack(list(agg.values())), axis=1), index=wide.index)
        feature_cols = [c for c in wide.columns if wide[c].notna().sum() >= 10]
        X = wide[feature_cols][~np.isnan(y.values)]
        y = y[~np.isnan(y.values)]
        X = X.fillna(X.median()).dropna(axis=1, how='all')
        
        if len(X) < 30:
            log(f"  Insufficient clean data")
            continue
        
        log(f"  Clean: {len(X)} obs, {len(X.columns)} features")
        ranking, r2, _ = compute_shap_rankings(X, y, n_bootstrap=10)
        log(f"  R²: {r2:.3f}")
        rankings[group_name] = ranking
    
    # Compare rankings
    log("\nCross-group correlations:")
    group_names = list(rankings.keys())
    for i, g1 in enumerate(group_names):
        for g2 in group_names[i+1:]:
            common = list(set(rankings[g1].index) & set(rankings[g2].index))
            if len(common) >= 20:
                corr, p = spearmanr([rankings[g1][i] for i in common], [rankings[g2][i] for i in common])
                log(f"  {g1} vs {g2}: {corr:.3f} (n={len(common)})")
    
    log("\n" + "=" * 70)
    log("VALIDATION COMPLETE")
    log("=" * 70)

if __name__ == '__main__':
    main()
