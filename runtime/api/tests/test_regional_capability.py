"""Regional capability and regression tests for V3.1 simulation pipeline."""

import importlib.util
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

# Add viz/ root to path so `from simulation import ...` works
_VIZ_ROOT = str(Path(__file__).parent.parent.parent)
if _VIZ_ROOT not in sys.path:
    sys.path.insert(0, _VIZ_ROOT)
_API_ROOT = str(Path(__file__).parent.parent)
if _API_ROOT not in sys.path:
    sys.path.insert(0, _API_ROOT)

from simulation.region_mapping import validate_region_mapping, get_region_for_country
from simulation.graph_loader_v31 import load_temporal_graph, build_adjacency_v31
from simulation.simulation_runner_v31 import run_simulation_v31
from models.requests import SimulationRequestV31, TemporalSimulationRequestV31

_SIM_SERVICE_PATH = Path(_API_ROOT) / "services" / "simulation_service.py"
_SIM_SPEC = importlib.util.spec_from_file_location("simulation_service_for_test", _SIM_SERVICE_PATH)
_SIM_MODULE = importlib.util.module_from_spec(_SIM_SPEC)
assert _SIM_SPEC and _SIM_SPEC.loader
_SIM_SPEC.loader.exec_module(_SIM_MODULE)
SimulationService = _SIM_MODULE.SimulationService


def test_region_mapping_has_full_coverage():
    report = validate_region_mapping(strict=False)
    assert report["mapped_countries"] == report["total_countries"]
    assert len(report["missing_countries"]) == 0


def test_region_mapping_alias_derivation():
    assert get_region_for_country("United States") == "north_america"
    assert get_region_for_country("United States of America") == "north_america"
    assert get_region_for_country("USA") == "north_america"
    assert get_region_for_country("Canada") == "north_america"
    assert get_region_for_country("Mexico") == "latin_america_caribbean"


@pytest.mark.parametrize("view_type", ["country", "stratified"])
def test_request_requires_country_for_country_and_stratified(view_type: str):
    with pytest.raises(ValidationError):
        SimulationRequestV31(
            country=None,
            interventions=[{"indicator": "v2x_polyarchy", "change_percent": 10}],
            year=2020,
            view_type=view_type,
        )


@pytest.mark.parametrize("model_cls,year_field", [
    (SimulationRequestV31, "year"),
    (TemporalSimulationRequestV31, "base_year"),
])
def test_request_requires_region_or_country_for_regional(model_cls, year_field: str):
    kwargs = {
        "country": None,
        "region": None,
        "interventions": [{"indicator": "v2x_polyarchy", "change_percent": 10}],
        "view_type": "regional",
    }
    kwargs[year_field] = 2020

    with pytest.raises(ValidationError):
        model_cls(**kwargs)


def test_unified_null_country_percentage_regression():
    graph = load_temporal_graph(country=None, year=2024, view_type="unified", p_value_threshold=0.05)
    if graph is None or not graph.get("edges"):
        pytest.skip("Unified graph unavailable in local data")

    indicator = graph["edges"][0]["source"]
    result = run_simulation_v31(
        country=None,
        interventions=[{"indicator": indicator, "change_percent": 5}],
        year=2024,
        view_type="unified",
        mode="percentage",
    )

    assert result["status"] == "success"
    assert result["view_used"] in {"unified", "regional", "stratified", "country"}


def test_adjacency_preserves_nonlinearity_and_marginal_effects():
    graph = {
        "edges": [
            {
                "source": "education",
                "target": "gdp",
                "beta": 0.12,
                "relationship_type": "threshold",
                "nonlinearity": {
                    "type": "threshold",
                    "detected": True,
                    "marginal_effects": {"p25": 0.08, "p50": 0.1, "p75": 0.12},
                },
            }
        ]
    }

    adj = build_adjacency_v31(graph)
    edge = adj["education"][0]
    assert edge["nonlinearity"]["detected"] is True
    assert edge["marginal_effects"]["p50"] == pytest.approx(0.1)


def test_temporal_debug_is_forwarded_to_runner(monkeypatch):
    svc = SimulationService()
    captured = {}

    def fake_runner(**kwargs):
        captured.update(kwargs)
        return {"status": "success"}

    monkeypatch.setattr(svc, "_get_v31_temporal_runner", lambda: fake_runner)

    svc.run_temporal_simulation_v31(
        country="Australia",
        interventions=[],
        base_year=2020,
        debug=True,
    )

    assert captured.get("debug") is True


def test_instant_debug_is_forwarded_to_runner(monkeypatch):
    svc = SimulationService()
    captured = {}

    def fake_runner(**kwargs):
        captured.update(kwargs)
        return {"status": "success"}

    monkeypatch.setattr(svc, "_get_v31_simulation_runner", lambda: fake_runner)

    svc.run_instant_simulation_v31(
        country="Australia",
        interventions=[],
        year=2020,
        debug=True,
    )

    assert captured.get("debug") is True
