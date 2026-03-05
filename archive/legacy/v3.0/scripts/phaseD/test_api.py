#!/usr/bin/env python
"""
API Endpoint Tests

Quick validation of all Phase D API endpoints.
"""

import requests
import json
import sys

BASE_URL = "http://localhost:8000"


def test_endpoint(name, method, path, data=None, expected_keys=None):
    """Test a single endpoint."""
    url = f"{BASE_URL}{path}"
    try:
        if method == "GET":
            response = requests.get(url, timeout=30)
        else:
            response = requests.post(url, json=data, timeout=30)

        if response.status_code == 200:
            result = response.json()
            if expected_keys:
                missing = [k for k in expected_keys if k not in result]
                if missing:
                    print(f"[FAIL] {name}: Missing keys {missing}")
                    return False
            print(f"[PASS] {name}")
            return True
        else:
            print(f"[FAIL] {name}: Status {response.status_code}")
            return False
    except Exception as e:
        print(f"[FAIL] {name}: {e}")
        return False


def main():
    print("=" * 50)
    print("V3.0 API Endpoint Tests")
    print("=" * 50)
    print()

    tests = [
        # Basic endpoints
        ("Root", "GET", "/", ["version", "endpoints"]),
        ("Health", "GET", "/health", ["status"]),
        ("Metadata", "GET", "/api/metadata", ["total_countries", "total_indicators"]),

        # Country endpoints
        ("Countries List", "GET", "/api/countries", ["total", "countries"]),

        # Graph endpoints
        ("Graph (Australia)", "GET", "/api/graph/Australia", ["country", "edges", "baseline"]),

        # Indicator endpoints
        ("Indicators List", "GET", "/api/indicators?limit=5", ["total", "indicators"]),
        ("Indicator Detail", "GET", "/api/indicators/v2elvotbuy", ["id", "in_degree", "out_degree"]),

        # Simulation endpoints
        ("Instant Simulation", "POST", "/api/simulate",
         {"country": "Australia", "interventions": [{"indicator": "v2elvotbuy", "change_percent": 20}]},
         ["status", "effects", "propagation"]),

        ("Temporal Simulation", "POST", "/api/simulate/temporal",
         {"country": "Australia", "interventions": [{"indicator": "v2elvotbuy", "change_percent": 20}], "horizon_years": 5},
         ["status", "timeline", "effects"]),
    ]

    passed = 0
    failed = 0

    for test in tests:
        if len(test) == 4:
            name, method, path, expected = test
            data = None
        else:
            name, method, path, data, expected = test

        if test_endpoint(name, method, path, data, expected):
            passed += 1
        else:
            failed += 1

    print()
    print("=" * 50)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 50)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
