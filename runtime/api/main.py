"""
V3.1 Global Causal Discovery API

FastAPI backend for policy intervention simulation.
Canonical simulation contract is V3.1; legacy aliases remain for compatibility.
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.openapi.utils import get_openapi
import logging

from .config import (
    API_VERSION, API_TITLE, API_DESCRIPTION,
    CORS_ORIGINS, CORS_ALLOW_CREDENTIALS, CORS_METHODS, CORS_HEADERS,
    CORS_EXPOSE_HEADERS, CORS_MAX_AGE, RATE_LIMIT_ENABLED, ENV,
    CONTACT_NAME, CONTACT_URL, CONTACT_EMAIL,
    LOG_LEVEL, API_ENABLE_DOCS, ENFORCE_PRODUCTION_ENV,
    SECURITY_HEADERS_ENABLED, SECURITY_HEADER_HSTS_MAX_AGE,
    SIMULATION_AUTH_ENABLED, SIMULATION_AUTH_TOKEN,
    CF_ACCESS_CLIENT_ID, CF_ACCESS_CLIENT_SECRET,
    SIMULATION_BROWSER_ORIGIN_REQUIRED,
)
from .routers import (
    countries_router,
    graphs_router,
    simulation_router,
    indicators_router,
    health_router
)
from .routers.temporal import router as temporal_router
from .routers.map import router as map_router
from .middleware.rate_limiter import rate_limit_middleware
from .middleware.logger import log_requests_middleware
from .services import graph_service, indicator_service
from .models import MetadataResponse

# Configure logging
logging.basicConfig(level=getattr(logging, LOG_LEVEL))
logger = logging.getLogger("api")

# Create FastAPI app
app = FastAPI(
    title=API_TITLE,
    description=API_DESCRIPTION,
    version=API_VERSION,
    docs_url="/docs" if API_ENABLE_DOCS else None,
    redoc_url="/redoc" if API_ENABLE_DOCS else None,
    contact={
        "name": CONTACT_NAME,
        "url": CONTACT_URL,
        "email": CONTACT_EMAIL
    },
    license_info={
        "name": "MIT",
        "url": "https://opensource.org/licenses/MIT"
    }
)


def _is_local_origin(origin: str) -> bool:
    local_prefixes = ("http://localhost", "http://127.0.0.1")
    return origin.startswith(local_prefixes)


def _is_simulation_path(path: str) -> bool:
    return path.startswith("/api/simulate")


def _normalize_origin(origin: str) -> str:
    return origin.strip().rstrip("/")


def _is_allowed_origin(origin: str) -> bool:
    normalized = _normalize_origin(origin)
    if not normalized:
        return False
    if "*" in CORS_ORIGINS:
        return True
    allowed = {_normalize_origin(value) for value in CORS_ORIGINS}
    return normalized in allowed


def _is_simulation_request_authorized(request: Request) -> bool:
    has_service_token = bool(CF_ACCESS_CLIENT_ID and CF_ACCESS_CLIENT_SECRET)
    if has_service_token:
        req_id = request.headers.get("CF-Access-Client-Id", "")
        req_secret = request.headers.get("CF-Access-Client-Secret", "")
        if req_id == CF_ACCESS_CLIENT_ID and req_secret == CF_ACCESS_CLIENT_SECRET:
            return True

    if SIMULATION_AUTH_TOKEN:
        api_key = request.headers.get("X-API-Key", "")
        auth_header = request.headers.get("Authorization", "")
        bearer = auth_header[7:] if auth_header.startswith("Bearer ") else ""
        if api_key == SIMULATION_AUTH_TOKEN or bearer == SIMULATION_AUTH_TOKEN:
            return True

    return False


def _validate_security_config() -> None:
    if ENFORCE_PRODUCTION_ENV and ENV != "production":
        raise RuntimeError("ENFORCE_PRODUCTION_ENV is enabled but API_ENV is not 'production'.")

    if SIMULATION_AUTH_ENABLED:
        has_service_token = bool(CF_ACCESS_CLIENT_ID and CF_ACCESS_CLIENT_SECRET)
        has_api_token = bool(SIMULATION_AUTH_TOKEN)
        if not (has_service_token or has_api_token):
            raise RuntimeError(
                "Simulation auth enabled but no credentials configured. "
                "Set SIMULATION_AUTH_TOKEN or CF_ACCESS_CLIENT_ID/CF_ACCESS_CLIENT_SECRET."
            )

    if ENFORCE_PRODUCTION_ENV and ENV == "production":
        if any(origin == "*" for origin in CORS_ORIGINS):
            raise RuntimeError("Wildcard CORS origin is not allowed in enforced production mode.")
        if any(_is_local_origin(origin) for origin in CORS_ORIGINS):
            raise RuntimeError("Localhost CORS origins are not allowed in enforced production mode.")


_validate_security_config()

# CORS middleware (must be first)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=CORS_ALLOW_CREDENTIALS,
    allow_methods=CORS_METHODS,
    allow_headers=CORS_HEADERS,
    expose_headers=CORS_EXPOSE_HEADERS,
    max_age=CORS_MAX_AGE,
)

# GZip compression middleware
# Compresses responses > 1KB, typically 75-90% reduction for JSON
# Order matters: GZip runs AFTER CORS (middleware stack is LIFO)
app.add_middleware(GZipMiddleware, minimum_size=1000, compresslevel=6)


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    """Apply standard response security headers (production by default)."""
    response = await call_next(request)

    if not SECURITY_HEADERS_ENABLED:
        return response

    response.headers.setdefault(
        "Strict-Transport-Security",
        f"max-age={SECURITY_HEADER_HSTS_MAX_AGE}; includeSubDomains"
    )
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("Permissions-Policy", "camera=(), geolocation=(), microphone=()")
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
    )
    return response


# Request logging middleware
@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    """Log all requests."""
    return await log_requests_middleware(request, call_next)


@app.middleware("http")
async def simulation_auth_middleware(request: Request, call_next):
    """Optional auth gate for simulation endpoints."""
    if (
        request.method == "OPTIONS"
        or not _is_simulation_path(request.url.path)
    ):
        return await call_next(request)

    is_authorized = _is_simulation_request_authorized(request)

    if SIMULATION_BROWSER_ORIGIN_REQUIRED and not is_authorized:
        request_origin = request.headers.get("Origin", "")
        if not _is_allowed_origin(request_origin):
            return JSONResponse(
                status_code=403,
                content={
                    "error": "browser_origin_required",
                    "message": "Simulation endpoints require a browser-origin request from an allowed origin."
                },
            )

    if not SIMULATION_AUTH_ENABLED:
        return await call_next(request)

    if is_authorized:
        return await call_next(request)

    return JSONResponse(
        status_code=401,
        content={"error": "unauthorized", "message": "Authentication required"},
        headers={"WWW-Authenticate": "Bearer"},
    )


# Rate limiting middleware
if RATE_LIMIT_ENABLED:
    @app.middleware("http")
    async def rate_limiting_middleware(request: Request, call_next):
        """Enforce rate limits."""
        return await rate_limit_middleware(request, call_next)


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle uncaught exceptions."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_error",
            "message": "An unexpected error occurred",
        }
    )


# Include routers
app.include_router(health_router)
app.include_router(countries_router, prefix="/api")
app.include_router(graphs_router, prefix="/api")
app.include_router(simulation_router, prefix="/api")
app.include_router(indicators_router, prefix="/api")
app.include_router(temporal_router)  # V3.1 temporal data (has own /api/temporal prefix)
app.include_router(map_router, prefix="/api")  # Map QOL scores for choropleth


# Root endpoint
@app.get("/", tags=["root"])
async def root():
    """
    API root - returns basic info and available endpoints.
    """
    return {
        "name": API_TITLE,
        "version": API_VERSION,
        "environment": ENV,
        "docs": "/docs",
        "health": "/health",
        "api_contract": {
            "canonical": {
                "instant": "/api/simulate/v31",
                "temporal": "/api/simulate/v31/temporal",
            },
            "compatibility_aliases": {
                "instant": {
                    "path": "/api/simulate",
                    "status": "deprecated",
                    "forwards_to": "/api/simulate/v31",
                },
                "temporal": {
                    "path": "/api/simulate/temporal",
                    "status": "deprecated",
                    "forwards_to": "/api/simulate/v31/temporal",
                },
            },
        },
        "endpoints": {
            # Core endpoints
            "countries": "/api/countries",
            "graph": "/api/graph/{country}",
            "indicators": "/api/indicators",
            "indicator_detail": "/api/indicators/{id}",
            "metadata": "/api/metadata",
            # Canonical simulation endpoints (V3.1)
            "simulate_v31": "/api/simulate/v31",
            "simulate_v31_temporal": "/api/simulate/v31/temporal",
            # Deprecated compatibility aliases
            "simulate": "/api/simulate",
            "simulate_temporal": "/api/simulate/temporal",
            # V3.1 temporal data endpoints
            "temporal_status": "/api/temporal/status",
            "temporal_shap": "/api/temporal/shap/{target}/{year}",
            "temporal_shap_timeline": "/api/temporal/shap/{target}/timeline",
            "temporal_graph": "/api/temporal/graph/{year}",
            "temporal_clusters": "/api/temporal/clusters/{year}"
        }
    }


@app.get("/api/metadata", response_model=MetadataResponse, tags=["metadata"])
async def get_metadata():
    """
    Get API metadata and aggregate statistics.

    Returns information about available data including:
    - Total countries with graphs
    - Total indicators tracked
    - Total causal edges
    - Lag estimation statistics
    """
    # Get graph stats
    graph_stats = graph_service.get_graph_stats()

    # Get indicator count
    indicators = indicator_service.get_all_indicators()

    return MetadataResponse(
        version=API_VERSION,
        total_countries=graph_stats.get('total_countries', 0),
        total_indicators=len(indicators),
        total_edges=graph_stats.get('total_edges', 0),
        graphs_with_lags=graph_stats.get('graphs_with_lags', 0),
        significant_lags=graph_stats.get('significant_lags', 0)
    )


# Custom OpenAPI schema with examples
def custom_openapi():
    """Generate custom OpenAPI schema with enhanced examples."""
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
        contact=app.contact,
        license_info=app.license_info
    )

    # Add example for SimulationRequestV31
    if "SimulationRequestV31" in openapi_schema.get("components", {}).get("schemas", {}):
        openapi_schema["components"]["schemas"]["SimulationRequestV31"]["example"] = {
            "country": "Australia",
            "interventions": [
                {"indicator": "v2elvotbuy", "change_percent": 20}
            ],
            "year": 2020,
            "mode": "percentage",
            "view_type": "country",
        }

    # Add example for TemporalSimulationRequestV31
    if "TemporalSimulationRequestV31" in openapi_schema.get("components", {}).get("schemas", {}):
        openapi_schema["components"]["schemas"]["TemporalSimulationRequestV31"]["example"] = {
            "country": "Australia",
            "interventions": [
                {"indicator": "v2elvotbuy", "change_percent": 20}
            ],
            "base_year": 2020,
            "horizon_years": 10
        }

    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi


# Run with uvicorn when executed directly
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True
    )
