"""
V3.0 Global Causal Discovery API

FastAPI backend for policy intervention simulation.
Production-ready with rate limiting, logging, and timeout protection.
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.openapi.utils import get_openapi
import logging

from .config import (
    API_VERSION, API_TITLE, API_DESCRIPTION,
    CORS_ORIGINS, RATE_LIMIT_ENABLED,
    CONTACT_NAME, CONTACT_URL, CONTACT_EMAIL,
    LOG_LEVEL
)
from .routers import (
    countries_router,
    graphs_router,
    simulation_router,
    indicators_router,
    health_router
)
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
    docs_url="/docs",
    redoc_url="/redoc",
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

# CORS middleware (must be first)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request logging middleware
@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    """Log all requests."""
    return await log_requests_middleware(request, call_next)


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
            "details": str(exc) if app.debug else None
        }
    )


# Include routers
app.include_router(health_router)
app.include_router(countries_router, prefix="/api")
app.include_router(graphs_router, prefix="/api")
app.include_router(simulation_router, prefix="/api")
app.include_router(indicators_router, prefix="/api")


# Root endpoint
@app.get("/", tags=["root"])
async def root():
    """
    API root - returns basic info and available endpoints.
    """
    return {
        "name": API_TITLE,
        "version": API_VERSION,
        "docs": "/docs",
        "health": "/health",
        "endpoints": {
            "countries": "/api/countries",
            "graph": "/api/graph/{country}",
            "simulate": "/api/simulate",
            "temporal": "/api/simulate/temporal",
            "indicators": "/api/indicators",
            "indicator_detail": "/api/indicators/{id}",
            "metadata": "/api/metadata"
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

    # Add example for SimulationRequest
    if "SimulationRequest" in openapi_schema.get("components", {}).get("schemas", {}):
        openapi_schema["components"]["schemas"]["SimulationRequest"]["example"] = {
            "country": "Australia",
            "interventions": [
                {"indicator": "v2elvotbuy", "change_percent": 20}
            ]
        }

    # Add example for TemporalSimulationRequest
    if "TemporalSimulationRequest" in openapi_schema.get("components", {}).get("schemas", {}):
        openapi_schema["components"]["schemas"]["TemporalSimulationRequest"]["example"] = {
            "country": "Australia",
            "interventions": [
                {"indicator": "v2elvotbuy", "change_percent": 20}
            ],
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
        host="0.0.0.0",
        port=8000,
        reload=True
    )
