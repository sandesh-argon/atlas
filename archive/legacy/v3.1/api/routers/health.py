"""
Health Check Router

Comprehensive health check with dependency validation.
"""

import json
import sys
from pathlib import Path
from fastapi import APIRouter, HTTPException
from typing import Dict, Any

from ..config import (
    PROJECT_ROOT, GRAPHS_DIR, PANEL_PATH, V21_GRAPH_PATH,
    API_VERSION, ENV
)

router = APIRouter(tags=["health"])


def check_graphs_available() -> Dict[str, Any]:
    """Check if country graphs are accessible."""
    try:
        if not GRAPHS_DIR.exists():
            return {"status": "error", "message": "Graphs directory missing"}

        # Try to load a sample graph
        sample_graphs = list(GRAPHS_DIR.glob("*.json"))[:1]
        if not sample_graphs:
            return {"status": "error", "message": "No graph files found"}

        with open(sample_graphs[0]) as f:
            graph = json.load(f)

        if "edges" not in graph:
            return {"status": "error", "message": "Invalid graph format"}

        graph_count = len(list(GRAPHS_DIR.glob("*.json")))
        return {
            "status": "ok",
            "graphs_available": graph_count
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


def check_panel_data() -> Dict[str, Any]:
    """Check if panel data is accessible."""
    try:
        if not PANEL_PATH.exists():
            return {"status": "error", "message": "Panel data file missing"}

        # Check file size (should be substantial)
        size_mb = PANEL_PATH.stat().st_size / (1024 * 1024)
        if size_mb < 1:
            return {"status": "warning", "message": f"Panel data unusually small ({size_mb:.1f} MB)"}

        return {"status": "ok", "size_mb": round(size_mb, 1)}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def check_simulation_modules() -> Dict[str, Any]:
    """Check if simulation modules can be imported."""
    try:
        # Add paths for import
        sim_path = PROJECT_ROOT / 'scripts' / 'phaseB' / 'B3_simulation'
        temporal_path = PROJECT_ROOT / 'scripts' / 'phaseC' / 'C2_temporal_simulation'

        if str(sim_path) not in sys.path:
            sys.path.insert(0, str(sim_path))
        if str(temporal_path) not in sys.path:
            sys.path.insert(0, str(temporal_path))

        from simulation_runner import run_simulation
        from temporal_simulation import run_temporal_simulation

        return {"status": "ok", "modules": ["simulation_runner", "temporal_simulation"]}
    except ImportError as e:
        return {"status": "error", "message": f"Import failed: {e}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def check_v21_metadata() -> Dict[str, Any]:
    """Check if V2.1 metadata is accessible."""
    try:
        if not V21_GRAPH_PATH.exists():
            return {"status": "warning", "message": "V2.1 graph not found (indicator metadata limited)"}

        with open(V21_GRAPH_PATH) as f:
            graph = json.load(f)

        node_count = len(graph.get("nodes", []))
        return {"status": "ok", "nodes": node_count}
    except Exception as e:
        return {"status": "warning", "message": f"V2.1 access error: {e}"}


@router.get("/health")
def health_check():
    """
    Basic health check.

    Returns simple status for load balancers and monitoring.
    """
    return {"status": "healthy", "version": API_VERSION}


@router.get("/health/detailed")
def detailed_health_check():
    """
    Comprehensive health check with dependency validation.

    Checks:
    - Country graphs accessibility
    - Panel data availability
    - Simulation module imports
    - V2.1 metadata (optional)

    Returns 503 if any critical dependency fails.
    """
    health = {
        "status": "healthy",
        "version": API_VERSION,
        "environment": ENV,
        "checks": {}
    }

    # Check 1: Country graphs
    health["checks"]["graphs"] = check_graphs_available()

    # Check 2: Panel data
    health["checks"]["panel_data"] = check_panel_data()

    # Check 3: Simulation modules
    health["checks"]["simulation_modules"] = check_simulation_modules()

    # Check 4: V2.1 metadata (optional)
    health["checks"]["v21_metadata"] = check_v21_metadata()

    # Determine overall status
    critical_checks = ["graphs", "panel_data", "simulation_modules"]
    errors = [
        name for name in critical_checks
        if health["checks"][name]["status"] == "error"
    ]
    warnings = [
        name for name, result in health["checks"].items()
        if result["status"] == "warning"
    ]

    if errors:
        health["status"] = "unhealthy"
        health["errors"] = errors
        raise HTTPException(status_code=503, detail=health)

    if warnings:
        health["status"] = "degraded"
        health["warnings"] = warnings

    return health
