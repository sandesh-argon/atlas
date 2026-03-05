"""
API Configuration

Paths, settings, and environment configuration for the V3.1 API.
"""

import os
from pathlib import Path

# Environment
ENV = os.getenv("API_ENV", "development").strip().lower()  # development, staging, production

# Project paths
VIZ_ROOT = Path(__file__).parent.parent  # viz/
DATA_ROOT = Path(os.getenv("DATA_ROOT", VIZ_ROOT / "data"))

# V3.1 Temporal Data
V31_TEMPORAL_SHAP_DIR = DATA_ROOT / "v31" / "temporal_shap"
V31_TEMPORAL_GRAPHS_DIR = DATA_ROOT / "v31" / "temporal_graphs"
V31_CLUSTERS_DIR = DATA_ROOT / "v31" / "development_clusters"
V31_FEEDBACK_LOOPS_DIR = DATA_ROOT / "v31" / "feedback_loops"
V31_INCOME_CLASSIFICATIONS = DATA_ROOT / "v31" / "metadata" / "income_classifications.json"
V31_COUNTRY_TRANSITIONS = DATA_ROOT / "v31" / "metadata" / "country_transitions.json"
V31_COUNTRY_DATA_QUALITY = DATA_ROOT / "v31" / "metadata" / "country_data_quality.json"
V31_BASELINES_DIR = DATA_ROOT / "v31" / "baselines"

# Country graphs now come from V3.1 temporal graphs (use latest year by default)
GRAPHS_DIR = V31_TEMPORAL_GRAPHS_DIR / "countries"
COUNTRY_SHAP_DIR = V31_TEMPORAL_SHAP_DIR / "countries"
DEFAULT_GRAPH_YEAR = 2024  # Default year for non-temporal country graph requests

# Panel data for simulations (raw research data - needed for baseline values)
RAW_DIR = Path(os.getenv("RAW_DATA_ROOT", DATA_ROOT / "raw"))
PANEL_PATH = RAW_DIR / "v21_panel_data_for_v3.parquet"
NODES_PATH = RAW_DIR / "v21_nodes.csv"
EDGES_PATH = RAW_DIR / "v21_causal_edges.csv"

# V2.1 unified graph (for indicator metadata - hierarchy structure)
V21_GRAPH_PATH = Path(os.getenv(
    "V21_GRAPH_PATH",
    VIZ_ROOT / "public" / "data" / "v2_1_visualization_final.json"
))

# Income strata for stratified views
INCOME_STRATA = ["developing", "emerging", "advanced"]


def _discover_temporal_targets(default_targets: list[str]) -> list[str]:
    """
    Discover available temporal SHAP targets from filesystem.

    Prefer unified target folders. Fallback to first country with target folders.
    """
    unified_dir = V31_TEMPORAL_SHAP_DIR / "unified"
    if unified_dir.exists():
        targets = sorted([d.name for d in unified_dir.iterdir() if d.is_dir()])
        if targets:
            return targets

    countries_dir = V31_TEMPORAL_SHAP_DIR / "countries"
    if countries_dir.exists():
        for country_dir in sorted(countries_dir.iterdir()):
            if not country_dir.is_dir():
                continue
            targets = sorted([d.name for d in country_dir.iterdir() if d.is_dir()])
            if targets:
                return targets

    return default_targets


def _discover_country_graph_count() -> int:
    countries_dir = V31_TEMPORAL_GRAPHS_DIR / "countries"
    if not countries_dir.exists():
        return 0
    return len([d for d in countries_dir.iterdir() if d.is_dir()])


# Temporal data settings
TEMPORAL_YEAR_MIN = 1990
TEMPORAL_YEAR_MAX = 2024
TEMPORAL_TARGETS = _discover_temporal_targets([
    "quality_of_life", "health", "education", "economic", "governance",
    "environment", "demographics", "security", "development"
])

AVAILABLE_COUNTRY_GRAPH_COUNT = _discover_country_graph_count()
ENABLE_REGIONAL_VIEW = os.getenv("ENABLE_REGIONAL_VIEW", "true").lower() == "true"

# API settings
API_VERSION = "3.1.0"
API_TITLE = "Global Causal Discovery API"
API_DESCRIPTION = f"""
## V3.1 Policy Intervention Simulator

Country-specific causal simulation for policy analysis.

### Features
- **{AVAILABLE_COUNTRY_GRAPH_COUNT} country-specific causal graph directories**
- **Instant simulation**: Propagate interventions through causal network
- **Temporal simulation**: Project effects over 1-20 year horizons with lag effects
- **2,583 development indicators** across economic, social, and governance domains
- **Available temporal targets**: {', '.join(TEMPORAL_TARGETS)}

### Rate Limits
- 100 requests/minute per IP
- 1,000 requests/hour per IP

### Timeouts
- Instant simulation: 10 seconds
- Temporal simulation: 15 seconds

### Support
- Documentation: https://docs.argonanalytics.com
- Issues: https://github.com/argonanalytics/v3-api/issues
"""

# CORS settings
DEFAULT_CORS_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:5174",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
]
CORS_ALLOW_WILDCARD = os.getenv("CORS_ALLOW_WILDCARD", "false").lower() == "true"
_default_cors = DEFAULT_CORS_ORIGINS + (["*"] if ENV != "production" else [])
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", ",".join(_default_cors)).split(",")
    if origin.strip()
]

if "*" in CORS_ORIGINS and ENV == "production" and not CORS_ALLOW_WILDCARD:
    CORS_ORIGINS = [origin for origin in CORS_ORIGINS if origin != "*"]
    if not CORS_ORIGINS:
        CORS_ORIGINS = DEFAULT_CORS_ORIGINS

CORS_ALLOW_CREDENTIALS = "*" not in CORS_ORIGINS
CORS_METHODS = [
    method.strip().upper()
    for method in os.getenv("CORS_METHODS", "GET,POST,OPTIONS").split(",")
    if method.strip()
]
if not CORS_METHODS:
    CORS_METHODS = ["GET", "POST", "OPTIONS"]

CORS_HEADERS = [
    header.strip()
    for header in os.getenv(
        "CORS_HEADERS",
        "Accept,Accept-Language,Authorization,CF-Access-Client-Id,"
        "CF-Access-Client-Secret,Content-Language,Content-Type,X-API-Key"
    ).split(",")
    if header.strip()
]
if not CORS_HEADERS:
    CORS_HEADERS = ["Accept", "Authorization", "Content-Type"]

CORS_EXPOSE_HEADERS = [
    header.strip()
    for header in os.getenv(
        "CORS_EXPOSE_HEADERS",
        "Retry-After,X-Process-Time,X-RateLimit-Limit-Hour,X-RateLimit-Limit-Minute,"
        "X-RateLimit-Remaining-Hour,X-RateLimit-Remaining-Minute"
    ).split(",")
    if header.strip()
]
CORS_MAX_AGE = int(os.getenv("CORS_MAX_AGE", "600"))

# Trusted proxy IPs (used to safely read client IP headers)
TRUST_PROXY_IPS = [
    ip.strip()
    for ip in os.getenv("TRUST_PROXY_IPS", "127.0.0.1,::1").split(",")
    if ip.strip()
]

# Rate limiting
RATE_LIMIT_ENABLED = os.getenv(
    "RATE_LIMIT_ENABLED",
    "true" if ENV == "production" else "false"
).lower() == "true"
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "100"))
RATE_LIMIT_PER_HOUR = int(os.getenv("RATE_LIMIT_PER_HOUR", "1000"))
RATE_LIMIT_MAX_TRACKED_IPS = int(os.getenv("RATE_LIMIT_MAX_TRACKED_IPS", "10000"))
RATE_LIMIT_EVICT_FRACTION = float(os.getenv("RATE_LIMIT_EVICT_FRACTION", "0.10"))

# Security toggles
API_ENABLE_DOCS = os.getenv(
    "API_ENABLE_DOCS",
    "false" if ENV == "production" else "true"
).lower() == "true"
HEALTH_DETAILED_ENABLED = os.getenv(
    "HEALTH_DETAILED_ENABLED",
    "false" if ENV == "production" else "true"
).lower() == "true"
ENFORCE_PRODUCTION_ENV = os.getenv(
    "ENFORCE_PRODUCTION_ENV",
    "true" if ENV == "production" else "false"
).lower() == "true"
SECURITY_HEADERS_ENABLED = os.getenv(
    "SECURITY_HEADERS_ENABLED",
    "true" if ENV == "production" else "false"
).lower() == "true"
SECURITY_HEADER_HSTS_MAX_AGE = int(os.getenv("SECURITY_HEADER_HSTS_MAX_AGE", "31536000"))

# Simulation endpoint authentication (recommended for public exposure)
SIMULATION_AUTH_ENABLED = os.getenv(
    "SIMULATION_AUTH_ENABLED",
    "true" if ENV == "production" else "false"
).lower() == "true"
SIMULATION_BROWSER_ORIGIN_REQUIRED = os.getenv(
    "SIMULATION_BROWSER_ORIGIN_REQUIRED",
    "true" if ENV == "production" else "false"
).lower() == "true"
SIMULATION_AUTH_TOKEN = os.getenv("SIMULATION_AUTH_TOKEN", "").strip()
CF_ACCESS_CLIENT_ID = os.getenv("CF_ACCESS_CLIENT_ID", "").strip()
CF_ACCESS_CLIENT_SECRET = os.getenv("CF_ACCESS_CLIENT_SECRET", "").strip()

# Timeouts (seconds)
SIMULATION_TIMEOUT = int(os.getenv("SIMULATION_TIMEOUT", "10"))
TEMPORAL_TIMEOUT = int(os.getenv("TEMPORAL_TIMEOUT", "60"))

# Simulation limits
DEFAULT_HORIZON_YEARS = 10
MAX_HORIZON_YEARS = 40
MAX_INTERVENTIONS = 20

# Service cache bounds (LRU max entries)
GRAPH_SERVICE_GRAPH_CACHE_MAX = max(1, int(os.getenv("GRAPH_SERVICE_GRAPH_CACHE_MAX", "64")))
GRAPH_SERVICE_SHAP_CACHE_MAX = max(1, int(os.getenv("GRAPH_SERVICE_SHAP_CACHE_MAX", "128")))
TEMPORAL_SERVICE_SHAP_CACHE_MAX = max(1, int(os.getenv("TEMPORAL_SERVICE_SHAP_CACHE_MAX", "256")))
TEMPORAL_SERVICE_GRAPH_CACHE_MAX = max(1, int(os.getenv("TEMPORAL_SERVICE_GRAPH_CACHE_MAX", "192")))
TEMPORAL_SERVICE_CLUSTER_CACHE_MAX = max(1, int(os.getenv("TEMPORAL_SERVICE_CLUSTER_CACHE_MAX", "128")))

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_DIR = VIZ_ROOT / "api" / "logs"

# Contact info
CONTACT_NAME = "Argon Analytics"
CONTACT_URL = "https://argonanalytics.com"
CONTACT_EMAIL = "support@argonanalytics.com"
