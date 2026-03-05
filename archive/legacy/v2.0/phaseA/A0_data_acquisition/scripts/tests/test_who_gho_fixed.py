"""
A0.2 FIXED: WHO Global Health Observatory Scraper
Uses verified working indicator codes from WHO GHO API
"""

import pandas as pd
import requests
import os
import json
import time
from pathlib import Path
from datetime import datetime

# === TEST CONFIG - FIXED WITH VERIFIED CODES ===
TEST_INDICATORS = [
    "WHOSIS_000001",    # Life expectancy at birth (VERIFIED WORKING)
    "WHOSIS_000015",    # Infant mortality rate (VERIFIED WORKING)
    "MDG_0000000001",   # Under-five mortality rate (VERIFIED WORKING)
    "WHS4_100",         # Total health expenditure as % of GDP (VERIFIED WORKING)
    "WHS4_543",         # Out-of-pocket expenditure (VERIFIED WORKING)
    "MDG_0000000026",   # Prevalence of underweight children (VERIFIED WORKING)
    "SA_0000001688",    # Physicians density (VERIFIED WORKING)
    "WHS9_86",          # Hospital beds (EXISTS IN API)
    "MDG_0000000007",   # Births attended by skilled health personnel
    "WHOSIS_000008"     # Healthy life expectancy at birth
]

OUTPUT_DIR = "./test_output/who_fixed"
BASE_URL = "https://ghoapi.azureedge.net/api/"
LOG_FILE = "./test_output/who_fixed_test_log.json"

os.makedirs(OUTPUT_DIR, exist_ok=True)

test_log = {
    "test_run": datetime.now().isoformat(),
    "indicators_tested": len(TEST_INDICATORS),
    "results": []
}

def validate_who_data(data):
    """Validate WHO API response structure"""
    if not isinstance(data, dict):
        return False
    if "value" not in data:
        return False
    if not isinstance(data["value"], list):
        return False
    return len(data["value"]) > 0

def retry_request(max_attempts=3, delay=2):
    """Retry failed requests with exponential backoff"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except requests.RequestException as e:
                    if attempt == max_attempts - 1:
                        raise
                    wait_time = delay * (2 ** attempt)
                    print(f"  ⏳ Retry {attempt + 1}/{max_attempts} after {wait_time}s: {e}")
                    time.sleep(wait_time)
            return None
        return wrapper
    return decorator

@retry_request(max_attempts=3, delay=2)
def fetch_indicator(code):
    """Fetch indicator data with retry logic"""
    url = f"{BASE_URL}{code}"
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    return response.json()

def main():
    """Test extraction on 10 sample health indicators."""
    print("=" * 70)
    print("A0.2 FIXED TEST: WHO Global Health Observatory Scraper")
    print("=" * 70)
    print(f"Testing {len(TEST_INDICATORS)} indicators (verified codes)")
    print(f"Output directory: {Path(OUTPUT_DIR).resolve()}")
    print("=" * 70)
    print()

    total_start = time.time()
    success_count = 0

    for idx, code in enumerate(TEST_INDICATORS, 1):
        print(f"\n[{idx}/{len(TEST_INDICATORS)}] Fetching {code}...")

        start_time = time.time()
        result = {
            "indicator_code": code,
            "timestamp": datetime.now().isoformat()
        }

        try:
            data = fetch_indicator(code)
            elapsed = time.time() - start_time
            result["fetch_time_seconds"] = round(elapsed, 2)

            if not validate_who_data(data):
                print(f"  ⚠️ Invalid data structure for {code}")
                result["status"] = "FAILED"
                result["reason"] = "invalid_structure"
                test_log["results"].append(result)
                continue

            records = data.get("value", [])

            if not records:
                print(f"  ⚠️ No data for {code}")
                result["status"] = "FAILED"
                result["reason"] = "empty_dataset"
                test_log["results"].append(result)
                continue

            df = pd.json_normalize(records)

            required_cols = ["SpatialDim", "TimeDim", "NumericValue"]
            if not all(col in df.columns for col in required_cols):
                print(f"  ⚠️ Missing required columns for {code}")
                result["status"] = "FAILED"
                result["reason"] = "missing_columns"
                result["available_columns"] = df.columns.tolist()
                test_log["results"].append(result)
                continue

            keep_cols = {
                "SpatialDim": "Country",
                "TimeDim": "Year",
                "NumericValue": "Value"
            }
            filtered = df[list(keep_cols.keys())].rename(columns=keep_cols)

            out_path = os.path.join(OUTPUT_DIR, f"{code}.csv")
            filtered.to_csv(out_path, index=False)

            print(f"  ✓ Saved {len(filtered)} rows to {out_path}")

            result["status"] = "SUCCESS"
            result["rows_fetched"] = len(filtered)
            result["file_path"] = out_path

            # Data analysis
            non_null = filtered[filtered['Value'].notna()]
            result["non_null_values"] = len(non_null)
            result["null_values"] = len(filtered) - len(non_null)

            success_count += 1

        except Exception as e:
            elapsed = time.time() - start_time
            print(f"  ❌ Error fetching {code}: {e}")
            result["status"] = "FAILED"
            result["reason"] = str(e)
            result["fetch_time_seconds"] = round(elapsed, 2)

        test_log["results"].append(result)
        time.sleep(0.3)

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

    if success_count > 0:
        successful = [r for r in test_log["results"] if r["status"] == "SUCCESS"]
        total_rows = sum(r["rows_fetched"] for r in successful)
        print(f"\nTotal rows fetched: {total_rows:,}")
        print(f"Average rows per indicator: {total_rows/success_count:.0f}")

    if failed:
        print(f"\n⚠️ Failed indicators:")
        for r in failed:
            print(f"  - {r['indicator_code']}: {r.get('reason', 'unknown')}")

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

    if success_count >= 8:  # At least 80% success rate
        print("\n✅ TEST PASSED: Scraper is working correctly")
        return 0
    else:
        print("\n❌ TEST FAILED: Success rate below 80%")
        return 1

if __name__ == "__main__":
    exit(main())
