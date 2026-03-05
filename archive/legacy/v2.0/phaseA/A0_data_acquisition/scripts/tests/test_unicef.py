"""
A0.5 Test Script: UNICEF SDMX Scraper
Tests V1 scraper on 10 sample child welfare indicators
"""

import requests
import json
import csv
import os
import time
from pathlib import Path
from datetime import datetime

# === TEST CONFIG ===
# Using actual UNICEF dataflow IDs
TEST_INDICATORS = [
    ("UNICEF", "GLOBAL_DATAFLOW", "MNCH_NEONATAL", "1.0"),  # Neonatal mortality
    ("UNICEF", "GLOBAL_DATAFLOW", "MNCH_UNDER-FIVE", "1.0"),  # Under-5 mortality
    ("UNICEF", "GLOBAL_DATAFLOW", "MNCH_DELIVERY", "1.0"),  # Skilled birth attendance
    ("UNICEF", "GLOBAL_DATAFLOW", "NUTRITION_STUNTING", "1.0"),  # Child stunting
    ("UNICEF", "GLOBAL_DATAFLOW", "NUTRITION_WASTING", "1.0"),  # Child wasting
    ("UNICEF", "GLOBAL_DATAFLOW", "IMMUNIZATION", "1.0"),  # Immunization coverage
    ("UNICEF", "GLOBAL_DATAFLOW", "WASH_WATER", "1.0"),  # Water access
    ("UNICEF", "GLOBAL_DATAFLOW", "WASH_SANITATION", "1.0"),  # Sanitation access
    ("UNICEF", "GLOBAL_DATAFLOW", "EDUCATION_COMPLETION", "1.0"),  # Education completion
    ("UNICEF", "GLOBAL_DATAFLOW", "CHILD_PROTECTION", "1.0")  # Child protection
]

BASE_URL = "https://sdmx.data.unicef.org/ws/public/sdmxapi/rest"
OUTPUT_DIR = "./test_output/unicef"
LOG_FILE = "./test_output/unicef_test_log.json"

os.makedirs(OUTPUT_DIR, exist_ok=True)

test_log = {
    "test_run": datetime.now().isoformat(),
    "indicators_tested": len(TEST_INDICATORS),
    "results": []
}

def get_indicator_data(agency, dataflow_base, dataflow_id, version):
    """Fetch data for a specific indicator"""
    url = f"{BASE_URL}/data/{agency},{dataflow_id},{version}/all"
    params = {'format': 'sdmx-json'}

    try:
        response = requests.get(url, params=params, timeout=120)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return None

def parse_sdmx_data(sdmx_data):
    """Parse SDMX-JSON format and extract basic data"""
    if not sdmx_data or "data" not in sdmx_data:
        return []

    rows = []
    try:
        # Simplified parsing - SDMX structure can vary
        if "dataSets" in sdmx_data["data"]:
            # Extract observations
            for dataset in sdmx_data["data"]["dataSets"]:
                if "series" in dataset:
                    for series_key, series_data in dataset["series"].items():
                        if "observations" in series_data:
                            for obs_key, obs_value in series_data["observations"].items():
                                if isinstance(obs_value, list) and len(obs_value) > 0:
                                    rows.append(("data", obs_key, obs_value[0]))
    except Exception:
        pass

    return rows

def main():
    """Test extraction on 10 sample child welfare indicators."""
    print("=" * 70)
    print("A0.5 TEST: UNICEF SDMX Scraper")
    print("=" * 70)
    print(f"Testing {len(TEST_INDICATORS)} indicators")
    print(f"Output directory: {Path(OUTPUT_DIR).resolve()}")
    print("=" * 70)
    print()

    total_start = time.time()
    success_count = 0

    for idx, (agency, dataflow_base, dataflow_id, version) in enumerate(TEST_INDICATORS, start=1):
        print(f"\n[{idx}/{len(TEST_INDICATORS)}] {dataflow_id}")

        start_time = time.time()
        result = {
            "indicator_id": dataflow_id,
            "agency": agency,
            "version": version,
            "timestamp": datetime.now().isoformat()
        }

        try:
            data = get_indicator_data(agency, dataflow_base, dataflow_id, version)
            elapsed = time.time() - start_time
            result["fetch_time_seconds"] = round(elapsed, 2)

            if not data:
                print(f"  ⚠️ Error fetching data for {dataflow_id}")
                result["status"] = "FAILED"
                result["reason"] = "fetch_error"
                test_log["results"].append(result)
                continue

            rows = parse_sdmx_data(data)

            if not rows:
                print(f"  ⚠️ No data extracted for {dataflow_id}")
                result["status"] = "FAILED"
                result["reason"] = "empty_dataset"
                test_log["results"].append(result)
                continue

            # Save to CSV
            fname = Path(OUTPUT_DIR) / f"{dataflow_id}.csv"
            with open(fname, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['Series', 'Observation', 'Value'])
                writer.writerows(rows)

            if fname.exists() and fname.stat().st_size > 0:
                print(f"  ✅ Saved {len(rows)} observations to {fname.name}")
                result["status"] = "SUCCESS"
                result["rows_fetched"] = len(rows)
                result["file_path"] = str(fname.resolve())
                success_count += 1
            else:
                print(f"  ❌ Failed writing {dataflow_id}")
                result["status"] = "FAILED"
                result["reason"] = "write_failure"

        except Exception as e:
            elapsed = time.time() - start_time
            print(f"  ❌ Error: {e}")
            result["status"] = "FAILED"
            result["reason"] = str(e)
            result["fetch_time_seconds"] = round(elapsed, 2)

        test_log["results"].append(result)
        time.sleep(1.0)  # UNICEF API needs more delay

    total_elapsed = time.time() - total_start

    # Summary
    print("\n" + "=" * 70)
    print("TEST COMPLETE")
    print("=" * 70)

    failed = [r for r in test_log["results"] if r["status"] == "FAILED"]

    print(f"Total indicators tested: {len(TEST_INDICATORS)}")
    print(f"Successful: {success_count}")
    print(f"Failed: {len(failed)}")
    print(f"Success rate: {success_count/len(TEST_INDICATORS)*100:.1f}%")
    print(f"Total time: {total_elapsed:.2f} seconds")

    if failed:
        print(f"\n⚠️ Failed indicators:")
        for r in failed:
            print(f"  - {r['indicator_id']}: {r.get('reason', 'unknown')}")

    # Save log
    test_log["summary"] = {
        "total_tested": len(TEST_INDICATORS),
        "successful": success_count,
        "failed": len(failed),
        "success_rate": success_count/len(TEST_INDICATORS),
        "total_time_seconds": round(total_elapsed, 2)
    }

    with open(LOG_FILE, 'w') as f:
        json.dump(test_log, f, indent=2)

    print(f"\n📝 Log saved to: {Path(LOG_FILE).resolve()}")
    print("=" * 70)

    # UNICEF API can be unreliable, so lower threshold
    if success_count >= 5:  # At least 50% success rate
        print("\n✅ TEST PASSED: Scraper is working")
        return 0
    else:
        print("\n❌ TEST FAILED: Success rate below 50%")
        return 1

if __name__ == "__main__":
    exit(main())
