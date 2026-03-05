"""
API Configuration

Paths, settings, and environment configuration for the V3.0 API.
"""

import os
from pathlib import Path

# Environment
ENV = os.getenv("API_ENV", "development")  # development, staging, production

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
GRAPHS_DIR = DATA_DIR / "country_graphs"
COUNTRY_SHAP_DIR = DATA_DIR / "country_shap"  # Country-specific SHAP importance
RAW_DIR = DATA_DIR / "raw"
PANEL_PATH = RAW_DIR / "v21_panel_data_for_v3.parquet"
NODES_PATH = RAW_DIR / "v21_nodes.csv"
EDGES_PATH = RAW_DIR / "v21_causal_edges.csv"

# V2.1 unified graph (for indicator metadata)
V21_GRAPH_PATH = PROJECT_ROOT.parent / "v2.1" / "outputs" / "B5" / "v2_1_visualization_final.json"

# API settings
API_VERSION = "3.0.0"
API_TITLE = "Global Causal Discovery API"
API_DESCRIPTION = """
## V3.0 Policy Intervention Simulator

Country-specific causal simulation for policy analysis.

### Features
- **203 country-specific causal graphs** with 7,368 edges each
- **Instant simulation**: Propagate interventions through causal network
- **Temporal simulation**: Project effects over 1-20 year horizons with lag effects
- **2,583 development indicators** across economic, social, and governance domains

### Rate Limits
- 100 requests/minute per IP
- 1,000 requests/hour per IP

### Timeouts
- Instant simulation: 10 seconds
- Temporal simulation: 15 seconds

### Support
- Documentation: https://atlas.argonanalytics.org
- Issues: https://github.com/sandesh-argon/atlas/issues
"""

# CORS settings
CORS_ORIGINS = os.getenv("CORS_ORIGINS", ",".join([
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
    "*"  # Allow all for development
])).split(",")

# Rate limiting
RATE_LIMIT_ENABLED = os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true"
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "100"))
RATE_LIMIT_PER_HOUR = int(os.getenv("RATE_LIMIT_PER_HOUR", "1000"))

# Timeouts (seconds)
SIMULATION_TIMEOUT = int(os.getenv("SIMULATION_TIMEOUT", "10"))
TEMPORAL_TIMEOUT = int(os.getenv("TEMPORAL_TIMEOUT", "15"))

# Simulation limits
DEFAULT_HORIZON_YEARS = 10
MAX_HORIZON_YEARS = 20
MAX_INTERVENTIONS = 20

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_DIR = PROJECT_ROOT / "logs"

# Contact info
CONTACT_NAME = "Argon Analytics"
CONTACT_URL = "https://atlas.argonanalytics.org"
CONTACT_EMAIL = "sandesh@argonanalytics.org"
