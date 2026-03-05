"""
A0.4 Test Script: IMF IFS Scraper
Tests V1 scraper on 10 sample economic indicators
"""

import os
import csv
import requests
import time
import json
from pathlib import Path
from datetime import datetime

# === TEST CONFIG ===
TEST_INDICATORS = [
    "NGDP_R",       # GDP, constant prices
    "NGDPD",        # GDP, current prices
    "PCPIPCH",      # Inflation rate, average consumer prices
    "LUR",          # Unemployment rate
    "BCA",          # Current account balance
    "GGR",          # General government revenue
    "GGX",          # General government total expenditure
    "GGXCNL",       # General government net lending/borrowing
    "PCPI",         # Consumer prices
    "LP"            # Labor force
]

OUTPUT_DIR = "./test_output/imf"
BASE_IMF_URL = "https://www.imf.org/external/datamapper/api/v1"
LOG_FILE = "./test_output/imf_test_log.json"

session = requests.Session()
session.headers.update({
    "Accept": "application/json",
    "User-Agent": "imf-data-fetcher/1.0"
})

os.makedirs(OUTPUT_DIR, exist_ok=True)

test_log = {
    "test_run": datetime.now().isoformat(),
    "indicators_tested": len(TEST_INDICATORS),
    "results": []
}

def fetch_indicator_json(indicator_id):
    """Fetch IMF data for an indicator"""
    url = f"{BASE_IMF_URL}/{indicator_id}"
    resp = session.get(url, timeout=60)
    resp.raise_for_status()
    return resp.json()

def parse_indicator_json(indicator_id, j):
    """Parse JSON from IMF API, return (country, year, value) rows."""
    rows = []
    values = j.get("values")
    if not values:
        return rows

    # Try direct mapping
    block = values.get(indicator_id)
    if block is None:
        block = values

    for country_id, year_map in block.items():
        if not isinstance(year_map, dict):
            continue
        for year_str, val in year_map.items():
            rows.append((country_id, year_str, val))
    return rows

def main():
    """Test extraction on 10 sample economic indicators."""
    print("=" * 70)
    print("A0.4 TEST: IMF IFS Scraper")
    print("=" * 70)
    print(f"Testing {len(TEST_INDICATORS)} indicators")
    print(f"Output directory: {Path(OUTPUT_DIR).resolve()}")
    print("=" * 70)
    print()

    total_start = time.time()
    success_count = 0

    for idx, ind_id in enumerate(TEST_INDICATORS, start=1):
        print(f"\n[{idx}/{len(TEST_INDICATORS)}] Indicator: {ind_id}")

        start_time = time.time()
        result = {
            "indicator_id": ind_id,
            "timestamp": datetime.now().isoformat()
        }

        try:
            j = fetch_indicator_json(ind_id)
            elapsed = time.time() - start_time
            result["fetch_time_seconds"] = round(elapsed, 2)

            rows = parse_indicator_json(ind_id, j)

            if not rows:
                print(f"  ⚠️ {ind_id} has no data")
                result["status"] = "FAILED"
                result["reason"] = "empty_dataset"
                test_log["results"].append(result)
                continue

            # Save to CSV
            fname = Path(OUTPUT_DIR) / f"{ind_id}.csv"
            with open(fname, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Country", "Year", "Value"])
                for country, year, value in rows:
                    writer.writerow([country, year, value])

            if fname.exists() and fname.stat().st_size > 0:
                print(f"  ✅ Wrote {len(rows)} rows to {fname.resolve()}")
                result["status"] = "SUCCESS"
                result["rows_fetched"] = len(rows)
                result["file_path"] = str(fname.resolve())
                success_count += 1
            else:
                print(f"  ❌ Failed writing {ind_id}")
                result["status"] = "FAILED"
                result["reason"] = "write_failure"

        except Exception as e:
            elapsed = time.time() - start_time
            print(f"  ❌ Error: {e}")
            result["status"] = "FAILED"
            result["reason"] = str(e)
            result["fetch_time_seconds"] = round(elapsed, 2)

        test_log["results"].append(result)
        time.sleep(0.5)

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

    if success_count >= 8:  # At least 80% success rate
        print("\n✅ TEST PASSED: Scraper is working correctly")
        return 0
    else:
        print("\n❌ TEST FAILED: Success rate below 80%")
        return 1

if __name__ == "__main__":
    exit(main())
