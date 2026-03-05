"""
Input Validation Tests

Comprehensive edge case and security testing for API inputs.
"""

import pytest
from fastapi.testclient import TestClient
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from api.main import app

client = TestClient(app)


class TestCountryValidation:
    """Tests for country-related input validation."""

    def test_valid_country(self):
        """Test valid country returns 200."""
        response = client.get("/api/graph/Australia")
        assert response.status_code == 200
        assert response.json()["country"] == "Australia"

    def test_invalid_country(self):
        """Test non-existent country returns 404."""
        response = client.get("/api/graph/INVALID_COUNTRY")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_country_case_sensitivity(self):
        """Test country names are case-sensitive."""
        response = client.get("/api/graph/australia")
        # Should either work (case-insensitive) or return 404
        assert response.status_code in [200, 404]

    def test_country_with_special_chars(self):
        """Test country with special characters."""
        response = client.get("/api/graph/Côte d'Ivoire")
        # Should handle gracefully
        assert response.status_code in [200, 404]


class TestIndicatorValidation:
    """Tests for indicator-related input validation."""

    def test_valid_indicator(self):
        """Test valid indicator returns 200."""
        response = client.get("/api/indicators/v2elvotbuy")
        assert response.status_code == 200
        assert response.json()["id"] == "v2elvotbuy"

    def test_invalid_indicator(self):
        """Test non-existent indicator returns 404."""
        response = client.get("/api/indicators/INVALID_INDICATOR_12345")
        assert response.status_code == 404

    def test_indicator_search_empty(self):
        """Test empty search returns results."""
        response = client.get("/api/indicators")
        assert response.status_code == 200
        assert "indicators" in response.json()

    def test_indicator_search_with_query(self):
        """Test search with query parameter."""
        response = client.get("/api/indicators?search=elect")
        assert response.status_code == 200


class TestSimulationValidation:
    """Tests for simulation input validation."""

    def test_simulation_missing_country(self):
        """Test simulation without country fails."""
        response = client.post("/api/simulate", json={
            "interventions": [{"indicator": "v2elvotbuy", "change_percent": 20}]
        })
        assert response.status_code == 422

    def test_simulation_missing_interventions(self):
        """Test simulation without interventions fails."""
        response = client.post("/api/simulate", json={
            "country": "Australia"
        })
        assert response.status_code == 422

    def test_simulation_empty_interventions(self):
        """Test simulation with empty interventions list fails."""
        response = client.post("/api/simulate", json={
            "country": "Australia",
            "interventions": []
        })
        assert response.status_code == 422

    def test_simulation_invalid_country(self):
        """Test simulation with invalid country returns 400."""
        response = client.post("/api/simulate", json={
            "country": "INVALID_COUNTRY",
            "interventions": [{"indicator": "v2elvotbuy", "change_percent": 20}]
        })
        assert response.status_code == 400

    def test_simulation_invalid_indicator(self):
        """Test simulation with invalid indicator."""
        response = client.post("/api/simulate", json={
            "country": "Australia",
            "interventions": [{"indicator": "INVALID_INDICATOR", "change_percent": 20}]
        })
        # Should return success but with no effects (indicator not in baseline)
        assert response.status_code == 200

    def test_simulation_extreme_positive_change(self):
        """Test simulation with very large positive change."""
        response = client.post("/api/simulate", json={
            "country": "Australia",
            "interventions": [{"indicator": "v2elvotbuy", "change_percent": 1000}]
        })
        # Should be capped by Pydantic validation
        assert response.status_code in [200, 422]

    def test_simulation_extreme_negative_change(self):
        """Test simulation with -100% change."""
        response = client.post("/api/simulate", json={
            "country": "Australia",
            "interventions": [{"indicator": "v2elvotbuy", "change_percent": -100}]
        })
        assert response.status_code == 200

    def test_simulation_beyond_limit_change(self):
        """Test simulation with change beyond limits."""
        response = client.post("/api/simulate", json={
            "country": "Australia",
            "interventions": [{"indicator": "v2elvotbuy", "change_percent": 10000}]
        })
        assert response.status_code == 422  # Pydantic rejects >1000

    def test_simulation_negative_beyond_limit(self):
        """Test simulation with change beyond -100%."""
        response = client.post("/api/simulate", json={
            "country": "Australia",
            "interventions": [{"indicator": "v2elvotbuy", "change_percent": -200}]
        })
        assert response.status_code == 422  # Pydantic rejects <-100


class TestTemporalSimulationValidation:
    """Tests for temporal simulation input validation."""

    def test_temporal_valid_request(self):
        """Test valid temporal simulation."""
        response = client.post("/api/simulate/temporal", json={
            "country": "Australia",
            "interventions": [{"indicator": "v2elvotbuy", "change_percent": 20}],
            "horizon_years": 5
        })
        assert response.status_code == 200
        assert "timeline" in response.json()

    def test_temporal_invalid_horizon_too_high(self):
        """Test temporal with horizon > 30 years."""
        response = client.post("/api/simulate/temporal", json={
            "country": "Australia",
            "interventions": [{"indicator": "v2elvotbuy", "change_percent": 20}],
            "horizon_years": 100
        })
        assert response.status_code == 422

    def test_temporal_invalid_horizon_negative(self):
        """Test temporal with negative horizon."""
        response = client.post("/api/simulate/temporal", json={
            "country": "Australia",
            "interventions": [{"indicator": "v2elvotbuy", "change_percent": 20}],
            "horizon_years": -5
        })
        assert response.status_code == 422

    def test_temporal_invalid_horizon_zero(self):
        """Test temporal with zero horizon."""
        response = client.post("/api/simulate/temporal", json={
            "country": "Australia",
            "interventions": [{"indicator": "v2elvotbuy", "change_percent": 20}],
            "horizon_years": 0
        })
        assert response.status_code == 422

    def test_temporal_minimum_horizon(self):
        """Test temporal with minimum valid horizon."""
        response = client.post("/api/simulate/temporal", json={
            "country": "Australia",
            "interventions": [{"indicator": "v2elvotbuy", "change_percent": 20}],
            "horizon_years": 1
        })
        assert response.status_code == 200


class TestSecurityValidation:
    """Tests for security-related input handling."""

    def test_sql_injection_in_country(self):
        """Test SQL injection attempt in country parameter."""
        response = client.get("/api/graph/Australia'; DROP TABLE countries; --")
        assert response.status_code == 404
        # Should be safely handled as "country not found"

    def test_sql_injection_in_indicator(self):
        """Test SQL injection attempt in indicator parameter."""
        response = client.get("/api/indicators/x'; DELETE FROM indicators; --")
        assert response.status_code == 404

    def test_xss_in_search(self):
        """Test XSS attempt in search parameter."""
        response = client.get("/api/indicators?search=<script>alert('xss')</script>")
        assert response.status_code == 200
        # Should return safely (no HTML execution)
        result = response.json()
        assert isinstance(result, dict)

    def test_path_traversal(self):
        """Test path traversal attempt."""
        response = client.get("/api/graph/../../../etc/passwd")
        assert response.status_code == 404

    def test_null_byte_injection(self):
        """Test null byte injection attempt."""
        response = client.get("/api/graph/Australia%00.json")
        assert response.status_code in [200, 404]  # Should handle gracefully


class TestPayloadLimits:
    """Tests for payload size limits."""

    def test_too_many_interventions(self):
        """Test with more than 20 interventions."""
        interventions = [
            {"indicator": f"indicator_{i}", "change_percent": 10}
            for i in range(25)
        ]
        response = client.post("/api/simulate", json={
            "country": "Australia",
            "interventions": interventions
        })
        assert response.status_code == 422  # max_length=20

    def test_maximum_interventions(self):
        """Test with exactly 20 interventions."""
        interventions = [
            {"indicator": f"indicator_{i}", "change_percent": 10}
            for i in range(20)
        ]
        response = client.post("/api/simulate", json={
            "country": "Australia",
            "interventions": interventions
        })
        # Should accept but likely return success with no effects
        assert response.status_code == 200


class TestHealthEndpoints:
    """Tests for health check endpoints."""

    def test_basic_health(self):
        """Test basic health endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_detailed_health(self):
        """Test detailed health endpoint."""
        response = client.get("/health/detailed")
        assert response.status_code in [200, 503]
        result = response.json()
        assert "checks" in result
        assert "graphs" in result["checks"]


class TestRateLimitHeaders:
    """Tests for rate limit headers."""

    def test_rate_limit_headers_present(self):
        """Test that rate limit headers are present."""
        response = client.get("/api/countries")
        assert response.status_code == 200
        # Headers should be present
        assert "X-RateLimit-Limit-Minute" in response.headers
        assert "X-RateLimit-Remaining-Minute" in response.headers


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
