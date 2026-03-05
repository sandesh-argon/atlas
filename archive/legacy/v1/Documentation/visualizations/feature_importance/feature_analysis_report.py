import pandas as pd
import numpy as np
from pathlib import Path
import json

# Load all CSV files
data_dir = Path("<repo-root>/v1.0/Documentation/visualizations/feature_importance")

metrics = {
    'life_expectancy': 'Life Expectancy',
    'infant_mortality': 'Infant Mortality',
    'gdp_per_capita': 'GDP per Capita',
    'mean_years_schooling': 'Mean Years of Schooling',
    'gini': 'Gini Coefficient',
    'homicide': 'Homicide Rate',
    'undernourishment': 'Undernourishment',
    'internet_users': 'Internet Users'
}

# Load all datasets
datasets = {}
for key, name in metrics.items():
    file_path = data_dir / f"{key}_top25_features.csv"
    datasets[key] = pd.read_csv(file_path)

# Analysis Functions
def analyze_feature_types(df):
    """Analyze distribution of feature types"""
    return df['feature_type'].value_counts().to_dict()

def analyze_domains(df):
    """Analyze domain distribution"""
    return df['domain'].value_counts().to_dict()

def analyze_data_quality(df):
    """Analyze observed data rates"""
    return {
        'mean': df['observed_data_rate'].mean(),
        'median': df['observed_data_rate'].median(),
        'min': df['observed_data_rate'].min(),
        'max': df['observed_data_rate'].max(),
        'below_95': (df['observed_data_rate'] < 0.95).sum(),
        'below_90': (df['observed_data_rate'] < 0.90).sum()
    }

def analyze_importance_distribution(df):
    """Analyze importance score distribution"""
    return {
        'mean': df['relative_importance_pct'].mean(),
        'median': df['relative_importance_pct'].median(),
        'min': df['relative_importance_pct'].min(),
        'max': df['relative_importance_pct'].max(),
        'std': df['relative_importance_pct'].std(),
        'top_5_avg': df.head(5)['relative_importance_pct'].mean(),
        'bottom_5_avg': df.tail(5)['relative_importance_pct'].mean()
    }

def identify_common_features(datasets):
    """Identify features that appear across multiple metrics"""
    feature_appearances = {}
    for metric, df in datasets.items():
        for feature in df['feature_code'].unique():
            if feature not in feature_appearances:
                feature_appearances[feature] = []
            feature_appearances[feature].append(metric)

    # Filter features appearing in multiple metrics
    common = {k: v for k, v in feature_appearances.items() if len(v) >= 3}
    return dict(sorted(common.items(), key=lambda x: len(x[1]), reverse=True))

# Generate Report
print("=" * 100)
print("FEATURE IMPORTANCE ANALYSIS REPORT")
print("Global Development Indicators - Phase 2 Feature Selection")
print("=" * 100)
print()

# Overall Statistics
print("## OVERVIEW")
print("-" * 100)
total_features = sum(len(df) for df in datasets.values())
print(f"Total Features Analyzed: {total_features} (25 per metric × 8 metrics)")
print(f"Metrics Covered: {len(metrics)}")
print()

# Per-Metric Analysis
for key, name in metrics.items():
    df = datasets[key]
    print("=" * 100)
    print(f"## {name.upper()}")
    print("-" * 100)

    # Feature Type Distribution
    print("\n### Feature Type Distribution:")
    ft_dist = analyze_feature_types(df)
    for ftype, count in sorted(ft_dist.items(), key=lambda x: x[1], reverse=True):
        pct = (count / len(df)) * 100
        print(f"  - {ftype}: {count} ({pct:.1f}%)")

    # Domain Distribution
    print("\n### Domain Distribution:")
    domain_dist = analyze_domains(df)
    for domain, count in sorted(domain_dist.items(), key=lambda x: x[1], reverse=True):
        pct = (count / len(df)) * 100
        print(f"  - {domain}: {count} ({pct:.1f}%)")

    # Data Quality
    print("\n### Data Quality Metrics:")
    quality = analyze_data_quality(df)
    print(f"  - Mean Observed Rate: {quality['mean']:.4f} ({quality['mean']*100:.2f}%)")
    print(f"  - Median Observed Rate: {quality['median']:.4f} ({quality['median']*100:.2f}%)")
    print(f"  - Range: {quality['min']:.4f} - {quality['max']:.4f}")
    print(f"  - Features with <95% data: {quality['below_95']}")
    print(f"  - Features with <90% data: {quality['below_90']}")

    # Importance Distribution
    print("\n### Importance Distribution:")
    importance = analyze_importance_distribution(df)
    print(f"  - Mean Importance: {importance['mean']:.2f}%")
    print(f"  - Median Importance: {importance['median']:.2f}%")
    print(f"  - Range: {importance['min']:.2f}% - {importance['max']:.2f}%")
    print(f"  - Std Dev: {importance['std']:.2f}%")
    print(f"  - Top 5 Avg: {importance['top_5_avg']:.2f}%")
    print(f"  - Bottom 5 Avg: {importance['bottom_5_avg']:.2f}%")
    print(f"  - Importance Drop (Top to Bottom 5): {importance['top_5_avg'] - importance['bottom_5_avg']:.2f}%")

    # Top Features
    print("\n### Top 5 Most Important Features:")
    top5 = df.head(5)
    for idx, row in top5.iterrows():
        print(f"  {row['rank']}. {row['feature_name']}")
        print(f"     - Type: {row['feature_type']} | Domain: {row['domain']}")
        print(f"     - Importance: {row['relative_importance_pct']:.2f}% | Data Rate: {row['observed_data_rate']:.4f}")

    print()

# Cross-Metric Analysis
print("=" * 100)
print("## CROSS-METRIC ANALYSIS")
print("-" * 100)

# Common Features
print("\n### Features Appearing in Multiple Metrics (3+ occurrences):")
common_features = identify_common_features(datasets)
print(f"\nTotal cross-metric features: {len(common_features)}")
print("\nMost Universal Features:")
for feature, metrics_list in list(common_features.items())[:15]:
    # Get feature name from any dataset
    for df in datasets.values():
        if feature in df['feature_code'].values:
            name = df[df['feature_code'] == feature]['feature_name'].iloc[0]
            break
    print(f"  - {name} ({feature})")
    print(f"    Appears in {len(metrics_list)} metrics: {', '.join(metrics_list)}")

# Feature Type Summary
print("\n### Feature Type Summary Across All Metrics:")
all_types = {}
for key, df in datasets.items():
    for ftype, count in analyze_feature_types(df).items():
        if ftype not in all_types:
            all_types[ftype] = 0
        all_types[ftype] += count

print(f"\nTotal feature-metric combinations: {sum(all_types.values())}")
for ftype, count in sorted(all_types.items(), key=lambda x: x[1], reverse=True):
    pct = (count / sum(all_types.values())) * 100
    print(f"  - {ftype}: {count} ({pct:.1f}%)")

# Domain Summary
print("\n### Domain Summary Across All Metrics:")
all_domains = {}
for key, df in datasets.items():
    for domain, count in analyze_domains(df).items():
        if domain not in all_domains:
            all_domains[domain] = 0
        all_domains[domain] += count

for domain, count in sorted(all_domains.items(), key=lambda x: x[1], reverse=True):
    pct = (count / sum(all_domains.values())) * 100
    print(f"  - {domain}: {count} ({pct:.1f}%)")

# Data Quality Summary
print("\n### Overall Data Quality:")
all_rates = pd.concat([df['observed_data_rate'] for df in datasets.values()])
print(f"  - Mean Observed Data Rate: {all_rates.mean():.4f} ({all_rates.mean()*100:.2f}%)")
print(f"  - Median Observed Data Rate: {all_rates.median():.4f} ({all_rates.median()*100:.2f}%)")
print(f"  - Features with <95% data: {(all_rates < 0.95).sum()} ({(all_rates < 0.95).sum()/len(all_rates)*100:.1f}%)")
print(f"  - Features with <90% data: {(all_rates < 0.90).sum()} ({(all_rates < 0.90).sum()/len(all_rates)*100:.1f}%)")
print(f"  - Features with 100% data: {(all_rates == 1.0).sum()} ({(all_rates == 1.0).sum()/len(all_rates)*100:.1f}%)")

print("\n" + "=" * 100)
print("END OF REPORT")
print("=" * 100)
