"""
E2E tests for the V3.1 temporal simulation endpoint.

These tests call the API exactly as the frontend does (POST to /api/simulate/v31/temporal).
Requires the API to be running on localhost:8000.

Run: cd viz && python -m pytest api/tests/test_simulation_e2e.py -v
"""

import pytest
import httpx

BASE_URL = "http://localhost:8000"
ENDPOINT = f"{BASE_URL}/api/simulate/v31/temporal"
TIMEOUT = 120.0  # seconds — temporal sims can be slow


def _post_simulation(payload: dict) -> dict:
    """Helper to POST a simulation request and return parsed JSON."""
    resp = httpx.post(ENDPOINT, json=payload, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def _make_payload(
    country: str = "United States",
    interventions: list | None = None,
    base_year: int = 2013,
    horizon_years: int = 16,
    top_n_effects: int = 50,
) -> dict:
    """Build a standard simulation payload."""
    if interventions is None:
        interventions = [{"indicator": "rconna", "change_percent": 20}]
    return {
        "country": country,
        "interventions": interventions,
        "base_year": base_year,
        "horizon_years": horizon_years,
        "view_type": "country",
        "use_nonlinear": True,
        "use_dynamic_graphs": True,
        "top_n_effects": top_n_effects,
    }


# ──────────────────────────────────────────────
# Core functionality
# ──────────────────────────────────────────────


class TestResponseStructure:
    """Verify the response has the expected shape."""

    def test_response_structure(self):
        """Response has timeline, effects, metadata with correct shapes."""
        data = _post_simulation(_make_payload())

        assert data["status"] == "success"
        assert data["country"] == "United States"
        assert "timeline" in data
        assert "effects" in data
        assert "metadata" in data
        assert "affected_per_year" in data

        # Timeline should have entries for each year
        timeline = data["timeline"]
        assert len(timeline) >= 1

        # Effects should have year keys
        effects = data["effects"]
        assert len(effects) >= 1

        # Each effect entry should have the right fields
        for year_key, year_effects in effects.items():
            for indicator, effect in year_effects.items():
                assert "percent_change" in effect


class TestUSBaseline:
    """Test US + rconna baseline scenario."""

    def test_us_rconna_baseline(self):
        """US + rconna +20%, 2013→2029: should have >30 non-zero effects."""
        data = _post_simulation(_make_payload())

        # Collect all unique indicators with non-zero effects across all years
        affected_indicators = set()
        for year_key, year_effects in data["effects"].items():
            for indicator, effect in year_effects.items():
                if abs(effect.get("percent_change", 0)) > 0.01:
                    affected_indicators.add(indicator)

        assert len(affected_indicators) > 30, (
            f"Expected >30 affected indicators, got {len(affected_indicators)}"
        )


class TestSaturationNoMisfires:
    """Verify saturation doesn't produce absurd values."""

    def test_saturation_no_misfires(self):
        """No effect should have simulated value absurdly far from baseline."""
        data = _post_simulation(_make_payload(top_n_effects=100))

        for year_key, year_effects in data["effects"].items():
            for indicator, effect in year_effects.items():
                baseline = effect.get("baseline")
                simulated = effect.get("simulated")

                if baseline is None or simulated is None:
                    continue
                if baseline == 0:
                    continue

                ratio = abs(simulated / baseline) if baseline != 0 else 0

                # No value should be >100x its baseline from a 20% intervention
                assert ratio < 100, (
                    f"Year {year_key}, {indicator}: simulated={simulated}, "
                    f"baseline={baseline}, ratio={ratio:.1f}x — likely saturation misfire"
                )


class TestPopulationIndicators:
    """Ensure population indicators aren't wrongly capped at 100."""

    def test_population_indicators(self):
        """SP.POP.* indicators should have realistic values (>1000), NOT capped at 100."""
        data = _post_simulation(_make_payload(top_n_effects=200))

        for year_key, year_effects in data["effects"].items():
            for indicator, effect in year_effects.items():
                if not indicator.startswith("SP.POP"):
                    continue

                simulated = effect.get("simulated")
                baseline = effect.get("baseline")

                if baseline is not None and baseline > 1000:
                    # Population indicators with large baselines should NOT be 100
                    assert simulated is None or simulated > 1000, (
                        f"Year {year_key}, {indicator}: baseline={baseline}, "
                        f"simulated={simulated} — population wrongly capped at 100!"
                    )


class TestVdemBounds:
    """Verify V-Dem indicators stay in valid ranges."""

    def test_vdem_bounds(self):
        """V-Dem _ord effects stay in [0,4], v2x_* stay in [0,1]."""
        # Use a valid V-Dem indicator as intervention to get V-Dem effects
        payload = _make_payload(
            interventions=[{"indicator": "v2medentrain", "change_percent": 50}],
        )
        data = _post_simulation(payload)

        for year_key, year_effects in data["effects"].items():
            for indicator, effect in year_effects.items():
                simulated = effect.get("simulated")
                if simulated is None:
                    continue

                # v2x_* aggregate indices should be in [0, 1]
                if indicator.startswith("v2x_") and not indicator.startswith("v2x_regime"):
                    assert -0.01 <= simulated <= 1.01, (
                        f"Year {year_key}, {indicator}: simulated={simulated}, "
                        f"expected [0,1]"
                    )

                # _ord suffix should be in [0, 5] (some V-Dem ordinals use 0-5 scale)
                if indicator.endswith("_ord"):
                    assert -0.01 <= simulated <= 5.01, (
                        f"Year {year_key}, {indicator}: simulated={simulated}, "
                        f"expected [0,5]"
                    )


class TestStaggeredInterventions:
    """Test per-intervention year support."""

    def test_staggered_interventions(self):
        """Two interventions at different years both produce effects."""
        payload = _make_payload(
            interventions=[
                {"indicator": "rconna", "change_percent": 20, "year": 2015},
                {"indicator": "v2medentrain", "change_percent": 30, "year": 2018},
            ],
            base_year=2013,
            horizon_years=16,
        )
        data = _post_simulation(payload)

        assert data["status"] == "success"

        # Should have effects across multiple years
        effects = data["effects"]
        assert len(effects) >= 2, "Expected effects for multiple years"

        # Both interventions should contribute
        all_indicators = set()
        for year_key, year_effects in effects.items():
            all_indicators.update(year_effects.keys())

        assert len(all_indicators) > 5, (
            f"Expected >5 affected indicators from staggered interventions, "
            f"got {len(all_indicators)}"
        )


class TestMultipleCountries:
    """Verify simulation works for diverse countries."""

    @pytest.mark.parametrize("country", ["United States", "India", "Norway"])
    def test_multiple_countries(self, country: str):
        """Run for USA, India, Norway — all return >0 effects."""
        payload = _make_payload(country=country, horizon_years=10)
        data = _post_simulation(payload)

        assert data["status"] == "success"
        assert data["country"] == country

        total_effects = sum(len(v) for v in data["effects"].values())
        assert total_effects > 0, f"{country}: no effects returned"


class TestChangePercentRange:
    """Test extreme change percentages."""

    def test_change_percent_range(self):
        """+500% intervention doesn't crash, produces larger effects than +20%."""
        # +20% baseline
        data_20 = _post_simulation(_make_payload(
            interventions=[{"indicator": "rconna", "change_percent": 20}]
        ))

        # +500% extreme
        data_500 = _post_simulation(_make_payload(
            interventions=[{"indicator": "rconna", "change_percent": 500}]
        ))

        assert data_500["status"] == "success"

        # 500% should generally produce larger total effects than 20%
        def _total_abs_pct(data):
            total = 0.0
            for year_effects in data["effects"].values():
                for effect in year_effects.values():
                    total += abs(effect.get("percent_change", 0))
            return total

        total_20 = _total_abs_pct(data_20)
        total_500 = _total_abs_pct(data_500)

        assert total_500 > total_20, (
            f"+500% total effect ({total_500:.1f}) should exceed "
            f"+20% total effect ({total_20:.1f})"
        )


class TestEffectMagnitudesSane:
    """Sanity check on effect magnitudes."""

    def test_effect_magnitudes_sane(self):
        """No single effect should have >1000% change from a +20% intervention."""
        data = _post_simulation(_make_payload(top_n_effects=100))

        for year_key, year_effects in data["effects"].items():
            for indicator, effect in year_effects.items():
                pct = abs(effect.get("percent_change", 0))
                assert pct < 1000, (
                    f"Year {year_key}, {indicator}: {pct:.1f}% change "
                    f"from +20% intervention — suspiciously large"
                )
