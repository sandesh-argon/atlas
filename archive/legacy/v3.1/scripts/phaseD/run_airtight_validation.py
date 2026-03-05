#!/usr/bin/env python
"""
Phase D Airtight Validation

Comprehensive validation of API production readiness.
"""

import subprocess
import sys
import time
import requests
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
API_URL = "http://localhost:8000"


def print_header(title: str):
    """Print section header."""
    print()
    print("=" * 60)
    print(f"  {title}")
    print("=" * 60)


def print_result(name: str, passed: bool, details: str = ""):
    """Print test result."""
    status = "[PASS]" if passed else "[FAIL]"
    print(f"  {status} {name}")
    if details and not passed:
        print(f"         {details}")


def check_server_running() -> bool:
    """Check if API server is running."""
    try:
        response = requests.get(f"{API_URL}/health", timeout=5)
        return response.status_code == 200
    except:
        return False


def start_server():
    """Start the API server in background."""
    print("Starting API server...")
    venv_python = PROJECT_ROOT / "venv" / "bin" / "uvicorn"
    process = subprocess.Popen(
        [str(venv_python), "api.main:app", "--host", "0.0.0.0", "--port", "8000"],
        cwd=str(PROJECT_ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    time.sleep(3)
    return process


def test_core_endpoints() -> tuple:
    """Test all core endpoints."""
    tests = []

    # Test root
    try:
        r = requests.get(f"{API_URL}/")
        tests.append(("Root endpoint", r.status_code == 200, ""))
    except Exception as e:
        tests.append(("Root endpoint", False, str(e)))

    # Test health
    try:
        r = requests.get(f"{API_URL}/health")
        tests.append(("Health check", r.status_code == 200, ""))
    except Exception as e:
        tests.append(("Health check", False, str(e)))

    # Test detailed health
    try:
        r = requests.get(f"{API_URL}/health/detailed")
        data = r.json()
        tests.append(("Detailed health", r.status_code == 200 and data.get("status") in ["healthy", "degraded"], ""))
    except Exception as e:
        tests.append(("Detailed health", False, str(e)))

    # Test countries
    try:
        r = requests.get(f"{API_URL}/api/countries")
        data = r.json()
        tests.append(("Countries list", r.status_code == 200 and data["total"] > 0, ""))
    except Exception as e:
        tests.append(("Countries list", False, str(e)))

    # Test graph
    try:
        r = requests.get(f"{API_URL}/api/graph/Australia")
        data = r.json()
        tests.append(("Graph endpoint", r.status_code == 200 and len(data["edges"]) > 0, ""))
    except Exception as e:
        tests.append(("Graph endpoint", False, str(e)))

    # Test indicators
    try:
        r = requests.get(f"{API_URL}/api/indicators?limit=5")
        data = r.json()
        tests.append(("Indicators list", r.status_code == 200 and len(data["indicators"]) > 0, ""))
    except Exception as e:
        tests.append(("Indicators list", False, str(e)))

    # Test indicator detail
    try:
        r = requests.get(f"{API_URL}/api/indicators/v2elvotbuy")
        data = r.json()
        tests.append(("Indicator detail", r.status_code == 200 and "id" in data, ""))
    except Exception as e:
        tests.append(("Indicator detail", False, str(e)))

    # Test simulation
    try:
        r = requests.post(f"{API_URL}/api/simulate", json={
            "country": "Australia",
            "interventions": [{"indicator": "v2elvotbuy", "change_percent": 20}]
        })
        data = r.json()
        tests.append(("Instant simulation", r.status_code == 200 and data["status"] == "success", ""))
    except Exception as e:
        tests.append(("Instant simulation", False, str(e)))

    # Test temporal simulation
    try:
        r = requests.post(f"{API_URL}/api/simulate/temporal", json={
            "country": "Australia",
            "interventions": [{"indicator": "v2elvotbuy", "change_percent": 20}],
            "horizon_years": 5
        })
        data = r.json()
        tests.append(("Temporal simulation", r.status_code == 200 and "timeline" in data, ""))
    except Exception as e:
        tests.append(("Temporal simulation", False, str(e)))

    # Test metadata
    try:
        r = requests.get(f"{API_URL}/api/metadata")
        data = r.json()
        tests.append(("Metadata endpoint", r.status_code == 200 and data["total_countries"] > 0, ""))
    except Exception as e:
        tests.append(("Metadata endpoint", False, str(e)))

    return tests


def test_rate_limiting() -> tuple:
    """Test rate limiting functionality."""
    tests = []

    # Check rate limit headers
    try:
        r = requests.get(f"{API_URL}/api/countries")
        has_headers = (
            "X-RateLimit-Limit-Minute" in r.headers and
            "X-RateLimit-Remaining-Minute" in r.headers
        )
        tests.append(("Rate limit headers present", has_headers, ""))
    except Exception as e:
        tests.append(("Rate limit headers present", False, str(e)))

    # Verify remaining decreases
    try:
        r1 = requests.get(f"{API_URL}/api/countries")
        remaining1 = int(r1.headers.get("X-RateLimit-Remaining-Minute", 0))
        r2 = requests.get(f"{API_URL}/api/countries")
        remaining2 = int(r2.headers.get("X-RateLimit-Remaining-Minute", 0))
        tests.append(("Rate limit counter decrements", remaining2 < remaining1, f"{remaining1} -> {remaining2}"))
    except Exception as e:
        tests.append(("Rate limit counter decrements", False, str(e)))

    return tests


def test_input_validation() -> tuple:
    """Test input validation edge cases."""
    tests = []

    # Invalid country returns 404
    try:
        r = requests.get(f"{API_URL}/api/graph/INVALID_COUNTRY_XYZ")
        tests.append(("Invalid country -> 404", r.status_code == 404, f"Got {r.status_code}"))
    except Exception as e:
        tests.append(("Invalid country -> 404", False, str(e)))

    # Missing required field
    try:
        r = requests.post(f"{API_URL}/api/simulate", json={"country": "Australia"})
        tests.append(("Missing interventions -> 422", r.status_code == 422, f"Got {r.status_code}"))
    except Exception as e:
        tests.append(("Missing interventions -> 422", False, str(e)))

    # Empty interventions
    try:
        r = requests.post(f"{API_URL}/api/simulate", json={
            "country": "Australia",
            "interventions": []
        })
        tests.append(("Empty interventions -> 422", r.status_code == 422, f"Got {r.status_code}"))
    except Exception as e:
        tests.append(("Empty interventions -> 422", False, str(e)))

    # Extreme change value
    try:
        r = requests.post(f"{API_URL}/api/simulate", json={
            "country": "Australia",
            "interventions": [{"indicator": "v2elvotbuy", "change_percent": 10000}]
        })
        tests.append(("Extreme change -> 422", r.status_code == 422, f"Got {r.status_code}"))
    except Exception as e:
        tests.append(("Extreme change -> 422", False, str(e)))

    # Negative beyond limit
    try:
        r = requests.post(f"{API_URL}/api/simulate", json={
            "country": "Australia",
            "interventions": [{"indicator": "v2elvotbuy", "change_percent": -200}]
        })
        tests.append(("Change < -100% -> 422", r.status_code == 422, f"Got {r.status_code}"))
    except Exception as e:
        tests.append(("Change < -100% -> 422", False, str(e)))

    # Invalid horizon
    try:
        r = requests.post(f"{API_URL}/api/simulate/temporal", json={
            "country": "Australia",
            "interventions": [{"indicator": "v2elvotbuy", "change_percent": 20}],
            "horizon_years": 100
        })
        tests.append(("Invalid horizon -> 422", r.status_code == 422, f"Got {r.status_code}"))
    except Exception as e:
        tests.append(("Invalid horizon -> 422", False, str(e)))

    # Too many interventions
    try:
        interventions = [{"indicator": f"ind_{i}", "change_percent": 10} for i in range(25)]
        r = requests.post(f"{API_URL}/api/simulate", json={
            "country": "Australia",
            "interventions": interventions
        })
        tests.append(("Too many interventions -> 422", r.status_code == 422, f"Got {r.status_code}"))
    except Exception as e:
        tests.append(("Too many interventions -> 422", False, str(e)))

    return tests


def test_security() -> tuple:
    """Test security-related inputs."""
    tests = []

    # SQL injection attempt
    try:
        r = requests.get(f"{API_URL}/api/graph/Australia'; DROP TABLE x; --")
        tests.append(("SQL injection handled", r.status_code in [404, 400], f"Got {r.status_code}"))
    except Exception as e:
        tests.append(("SQL injection handled", False, str(e)))

    # XSS attempt
    try:
        r = requests.get(f"{API_URL}/api/indicators?search=<script>alert('x')</script>")
        tests.append(("XSS attempt handled", r.status_code == 200, f"Got {r.status_code}"))
    except Exception as e:
        tests.append(("XSS attempt handled", False, str(e)))

    # Path traversal
    try:
        r = requests.get(f"{API_URL}/api/graph/../../../etc/passwd")
        tests.append(("Path traversal blocked", r.status_code in [404, 400], f"Got {r.status_code}"))
    except Exception as e:
        tests.append(("Path traversal blocked", False, str(e)))

    return tests


def test_logging() -> tuple:
    """Test logging functionality."""
    tests = []

    log_file = PROJECT_ROOT / "logs" / "api_requests.log"

    # Check log directory exists
    tests.append(("Log directory exists", (PROJECT_ROOT / "logs").exists(), ""))

    # Make request and check log grows
    try:
        initial_size = log_file.stat().st_size if log_file.exists() else 0
        requests.get(f"{API_URL}/api/countries")
        time.sleep(0.5)  # Wait for log write
        final_size = log_file.stat().st_size if log_file.exists() else 0
        tests.append(("Requests logged", final_size > initial_size, f"{initial_size} -> {final_size}"))
    except Exception as e:
        tests.append(("Requests logged", False, str(e)))

    return tests


def test_documentation() -> tuple:
    """Test API documentation availability."""
    tests = []

    # OpenAPI docs
    try:
        r = requests.get(f"{API_URL}/docs")
        tests.append(("Swagger UI available", r.status_code == 200, ""))
    except Exception as e:
        tests.append(("Swagger UI available", False, str(e)))

    # ReDoc
    try:
        r = requests.get(f"{API_URL}/redoc")
        tests.append(("ReDoc available", r.status_code == 200, ""))
    except Exception as e:
        tests.append(("ReDoc available", False, str(e)))

    # OpenAPI JSON
    try:
        r = requests.get(f"{API_URL}/openapi.json")
        data = r.json()
        has_contact = "contact" in data.get("info", {})
        tests.append(("OpenAPI schema has contact", has_contact, ""))
    except Exception as e:
        tests.append(("OpenAPI schema has contact", False, str(e)))

    return tests


def main():
    """Run all airtight validation tests."""
    print_header("Phase D Airtight Validation")
    print(f"  API URL: {API_URL}")
    print(f"  Project: {PROJECT_ROOT}")

    # Check if server is running
    server_process = None
    if not check_server_running():
        server_process = start_server()
        if not check_server_running():
            print("[FAIL] Could not start API server")
            return 1

    all_tests = []

    # 1. Core Endpoints
    print_header("1. Core Endpoints (10 tests)")
    tests = test_core_endpoints()
    for name, passed, details in tests:
        print_result(name, passed, details)
    all_tests.extend(tests)

    # 2. Rate Limiting
    print_header("2. Rate Limiting (2 tests)")
    tests = test_rate_limiting()
    for name, passed, details in tests:
        print_result(name, passed, details)
    all_tests.extend(tests)

    # 3. Input Validation
    print_header("3. Input Validation (7 tests)")
    tests = test_input_validation()
    for name, passed, details in tests:
        print_result(name, passed, details)
    all_tests.extend(tests)

    # 4. Security
    print_header("4. Security (3 tests)")
    tests = test_security()
    for name, passed, details in tests:
        print_result(name, passed, details)
    all_tests.extend(tests)

    # 5. Logging
    print_header("5. Logging (2 tests)")
    tests = test_logging()
    for name, passed, details in tests:
        print_result(name, passed, details)
    all_tests.extend(tests)

    # 6. Documentation
    print_header("6. Documentation (3 tests)")
    tests = test_documentation()
    for name, passed, details in tests:
        print_result(name, passed, details)
    all_tests.extend(tests)

    # Summary
    passed = sum(1 for _, p, _ in all_tests if p)
    failed = sum(1 for _, p, _ in all_tests if not p)

    print_header("Summary")
    print(f"  Passed: {passed}")
    print(f"  Failed: {failed}")
    print(f"  Total:  {len(all_tests)}")
    print()

    if failed == 0:
        print("  [SUCCESS] All airtight validation tests passed!")
        print("  Phase D is production-ready for Phase E.")
    else:
        print("  [FAILURE] Some tests failed. Fix before proceeding.")

    # Cleanup
    if server_process:
        server_process.terminate()

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
