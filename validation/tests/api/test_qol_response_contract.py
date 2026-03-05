"""Regression tests for QoL fields in simulation response models."""

import sys
from pathlib import Path

# Add api root for direct model imports used across this test suite.
_API_ROOT = str(Path(__file__).parent.parent)
if _API_ROOT not in sys.path:
    sys.path.insert(0, _API_ROOT)

from models.responses import SimulationResponseV31, TemporalSimulationResponseV31


def test_instant_response_keeps_qol_payload():
    payload = {
        "status": "success",
        "mode": "absolute",
        "country": "Australia",
        "base_year": 2020,
        "view_type": "country",
        "view_used": "country",
        "scope_used": "country",
        "interventions": [{"indicator": "v2x_polyarchy", "change_percent": 10.0}],
        "effects": {"total_affected": 1, "top_effects": {}},
        "propagation": {"iterations": 2, "converged": True},
        "qol": {
            "baseline": 0.71,
            "simulated": 0.74,
            "delta": 0.03,
            "n_indicators": 700,
            "n_domains": 7,
        },
        "metadata": {"version": "v3.1.3"},
    }

    response = SimulationResponseV31(**payload)

    assert response.qol is not None
    assert response.qol.delta == 0.03
    assert response.qol.n_domains == 7


def test_temporal_response_keeps_qol_timeline_payload():
    payload = {
        "status": "success",
        "country": "Australia",
        "base_year": 2020,
        "horizon_years": 2,
        "view_type": "country",
        "scope_used": "country",
        "interventions": [{"indicator": "v2x_polyarchy", "change_percent": 10.0}],
        "timeline": {"2020": {"v2x_polyarchy": 0.5}},
        "effects": {"2020": {}},
        "affected_per_year": {"2020": 1},
        "graphs_used": {"2020": "country"},
        "qol_timeline": {
            "2020": {
                "baseline": 0.71,
                "simulated": 0.74,
                "delta": 0.03,
                "n_indicators": 700,
                "n_domains": 7,
            }
        },
        "metadata": {"version": "v3.1.3"},
    }

    response = TemporalSimulationResponseV31(**payload)

    assert response.qol_timeline is not None
    assert 2020 in response.qol_timeline
    assert response.qol_timeline[2020].delta == 0.03
