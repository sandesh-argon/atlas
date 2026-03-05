"""
V3.1 Configuration

Generated from pre-flight audit on 2025-01-12.
Based on v3_1_data_audit.json analysis.
"""

from pathlib import Path

# === PATHS ===
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"

# Input data (symlinked from V3.0)
PANEL_DATA_PATH = DATA_DIR / "raw" / "v21_panel_data_for_v3.parquet"
NODES_PATH = DATA_DIR / "raw" / "v21_nodes.csv"
EDGES_PATH = DATA_DIR / "raw" / "v21_causal_edges.csv"
COUNTRY_GRAPHS_DIR = DATA_DIR / "country_graphs"
COUNTRY_SHAP_DIR = DATA_DIR / "country_shap"

# Output directories
METADATA_DIR = DATA_DIR / "metadata"
TEMPORAL_SHAP_DIR = DATA_DIR / "v3_1_temporal_shap"
TEMPORAL_GRAPHS_DIR = DATA_DIR / "v3_1_temporal_graphs"
SPILLOVERS_DIR = DATA_DIR / "v3_1_spillovers"
FEEDBACK_LOOPS_DIR = DATA_DIR / "v3_1_feedback_loops"


# === YEAR CONFIGURATION ===
# Based on audit: All years have 800+ countries with data
# MIN_YEAR_FOR_SHAP: Need at least 5 years cumulative data
# MIN_YEAR_FOR_GRAPHS: Need at least 10 years for stable betas

MIN_YEAR_FOR_SHAP = 1995      # Start SHAP from 1995 (5 years data: 1990-1995)
MIN_YEAR_FOR_GRAPHS = 2000    # Start graphs from 2000 (10 years data: 1990-2000)
MAX_YEAR = 2024

SHAP_YEARS = list(range(MIN_YEAR_FOR_SHAP, MAX_YEAR + 1))       # 30 years
GRAPH_YEARS = list(range(MIN_YEAR_FOR_GRAPHS, MAX_YEAR + 1))    # 25 years


# === TARGETS ===
# 9 outcome domains for SHAP analysis
TARGETS = [
    'quality_of_life',    # Composite QoL
    'health',             # Health outcomes
    'education',          # Education outcomes
    'economic',           # Economic outcomes
    'governance',         # Governance outcomes
    'environment',        # Environmental outcomes
    'demographics',       # Demographic outcomes
    'security',           # Security outcomes
    'development'         # Development outcomes
]


# === REGIONS ===
# 11 regional aggregations for comparative analysis
REGIONS = {
    'sub_saharan_africa': {
        'name': 'Sub-Saharan Africa',
        'countries': []  # To be populated from regional_groups.json
    },
    'east_asia_pacific': {
        'name': 'East Asia & Pacific',
        'countries': []
    },
    'europe_central_asia': {
        'name': 'Europe & Central Asia',
        'countries': []
    },
    'latin_america_caribbean': {
        'name': 'Latin America & Caribbean',
        'countries': []
    },
    'middle_east_north_africa': {
        'name': 'Middle East & North Africa',
        'countries': []
    },
    'south_asia': {
        'name': 'South Asia',
        'countries': []
    },
    'north_america': {
        'name': 'North America',
        'countries': []
    },
    'oecd': {
        'name': 'OECD',
        'countries': []
    },
    'low_income': {
        'name': 'Low Income',
        'countries': []
    },
    'middle_income': {
        'name': 'Middle Income',
        'countries': []
    },
    'high_income': {
        'name': 'High Income',
        'countries': []
    }
}


# === COMPUTATION PARAMETERS ===

# Bootstrap configuration
BOOTSTRAP_SAMPLES = 100           # Number of bootstrap iterations for CIs
BOOTSTRAP_CI_LEVEL = 0.95         # 95% confidence intervals

# Model hyperparameters (GradientBoosting for SHAP)
MODEL_PARAMS = {
    'n_estimators': 100,
    'max_depth': 5,
    'learning_rate': 0.1,
    'subsample': 0.8,
    'random_state': 42
}

# Regime break detection (Chow test)
CHOW_TEST_ALPHA = 0.05            # Significance level for structural breaks
MIN_YEARS_BEFORE_BREAK = 5        # Need 5+ years data before potential break
MIN_YEARS_AFTER_BREAK = 5         # Need 5+ years data after potential break

# Edge estimation (Ridge regression)
RIDGE_ALPHA = 1.0
EDGE_BOOTSTRAP_SAMPLES = 100


# === PARALLELIZATION ===
# System: AMD Ryzen 9 7900X (24 threads)
# Thermal limit: 12 cores max for long operations

PARALLEL_CORES = 12               # Max cores for parallel processing
CHECKPOINT_INTERVAL = 20          # Save progress every N countries


# === THRESHOLDS ===

# Minimum data requirements
MIN_SAMPLES_FOR_SHAP = 10         # Need 10+ observations to train model
MIN_SAMPLES_FOR_EDGE = 5          # Need 5+ observations for edge estimation
MIN_INDICATORS_FOR_COUNTRY = 50   # Country needs 50+ indicators

# Validation thresholds
MAX_YEAR_OVER_YEAR_CHANGE = 0.3   # Flag if SHAP changes >0.3 between years
MIN_CI_COVERAGE = 0.95            # 95% of values should be within CIs


# === FILE ESTIMATES ===
# Based on V3.0 country list (165 countries + unified) and adjusted years

FILE_ESTIMATES = {
    'temporal_shap': {
        'countries': 166,         # 165 + unified
        'targets': 9,
        'years': len(SHAP_YEARS), # 30 years
        'total': 166 * 9 * len(SHAP_YEARS)  # ~44,820 files
    },
    'regional_shap': {
        'regions': 11,
        'targets': 9,
        'years': len(SHAP_YEARS),
        'total': 11 * 9 * len(SHAP_YEARS)   # ~2,970 files
    },
    'temporal_graphs': {
        'countries': 166,
        'years': len(GRAPH_YEARS),           # 25 years
        'total': 166 * len(GRAPH_YEARS)     # ~4,150 files
    },
    'spillovers': {
        'years': len(SHAP_YEARS),
        'total': len(SHAP_YEARS)            # 30 files
    },
    'feedback_loops': {
        'countries': 166,
        'total': 166                        # 166 files
    }
}

TOTAL_OUTPUT_FILES = sum(f['total'] for f in FILE_ESTIMATES.values())


# === PROVENANCE ===
CODE_VERSION = "v3.1.0"

def get_git_commit():
    """Get current git commit hash."""
    import subprocess
    try:
        result = subprocess.run(
            ['git', 'rev-parse', '--short', 'HEAD'],
            capture_output=True, text=True, cwd=PROJECT_ROOT
        )
        return result.stdout.strip() if result.returncode == 0 else "unknown"
    except Exception:
        return "unknown"
