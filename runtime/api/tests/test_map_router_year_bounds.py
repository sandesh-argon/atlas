"""Regression tests for map QoL year validation."""

import asyncio
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

# Add viz root so package import `api.routers.map` works.
_VIZ_ROOT = str(Path(__file__).parent.parent.parent)
if _VIZ_ROOT not in sys.path:
    sys.path.insert(0, _VIZ_ROOT)

from api.routers import map as map_router


def test_get_qol_scores_rejects_out_of_range_year(monkeypatch):
    monkeypatch.setattr(
        map_router.map_service,
        "get_qol_metadata",
        lambda: {"definition_id": "qol_v2", "year_min": 1999, "year_max": 2024},
    )
    monkeypatch.setattr(map_router.map_service, "get_scores_for_year", lambda year: {})

    with pytest.raises(HTTPException) as exc:
        asyncio.run(map_router.get_qol_scores(1990))

    assert exc.value.status_code == 400
    assert "1999" in exc.value.detail
    assert "2024" in exc.value.detail


def test_get_qol_scores_includes_year_range_metadata(monkeypatch):
    monkeypatch.setattr(
        map_router.map_service,
        "get_qol_metadata",
        lambda: {"definition_id": "qol_v2", "year_min": 1999, "year_max": 2024},
    )
    monkeypatch.setattr(
        map_router.map_service,
        "get_scores_for_year",
        lambda year: {"Australia": {"iso3": "AUS", "qol": 0.81}},
    )

    response = asyncio.run(map_router.get_qol_scores(2020))

    assert response["year"] == 2020
    assert response["year_min"] == 1999
    assert response["year_max"] == 2024
    assert response["scores"]["Australia"]["qol"] == 0.81
