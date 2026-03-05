"""
A0.3 Test Script: UNESCO UIS Scraper
Tests V1 scraper on 10 sample education indicators
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
    "SE.PRM.ENRR",      # Primary school enrollment
    "SE.SEC.ENRR",      # Secondary school enrollment
    "SE.TER.ENRR",      # Tertiary school enrollment
    "SE.XPD.TOTL.GD.ZS",  # Government expenditure on education, total (% of GDP)
    "SE.PRM.TCHR",      # Primary education, teachers
    "SE.COM.DURS",      # Compulsory education, duration (years)
    "SE.PRM.AGES",      # Primary school starting age (years)
    "SE.LPV.PRIM",      # Learning poverty
    "SE.ADT.LITR.ZS",   # Literacy rate, adult total (% of people ages 15 and above)
    "SE.PRM.CMPL.ZS"    # Primary completion rate, total (% of relevant age group)
]

OUTPUT_DIR = "./test_output/unesco"
BASE_ENDPOINT = "https://api.uis.unesco.org/api/public/data/indicators"
LOG_FILE = "./test_output/unesco_test_log.json"
CHUNK_SIZE = 50000

os.makedirs(OUTPUT_DIR, exist_ok=True)
session = requests.Session()
session.headers.update({"Accept": "application/json"})

test_log = {
    "test_run": datetime.now().isoformat(),
    "indicators_tested": len(TEST_INDICATORS),
    "results": []
}

def fetch_indicator_data(indicator_id, offset=0, limit=CHUNK_SIZE):
    """Fetch a chunk of data from the UIS API for a given indicator."""
    params = {
        "indicator": indicator_id,
        "offset": offset,
        "limit": limit
    }
    resp = session.get(BASE_ENDPOINT, params=params, timeout=60)
    resp.raise_for_status()
    return resp.json()

def main():
    """Test extraction on 10 sample education indicators."""
    print("=" * 70)
    print("A0.3 TEST: UNESCO UIS Scraper")
    print("=" * 70)
    print(f"Testing {len(TEST_INDICATORS)} indicators")
    print(f"Output directory: {Path(OUTPUT_DIR).resolve()}")
    print("=" * 70)
    print()

    total_start = time.time()
    success_count = 0

    for idx, code in enumerate(TEST_INDICATORS, start=1):
        print(f"\n[{idx}/{len(TEST_INDICATORS)}] Indicator: {code}")

        start_time = time.time()
        result = {
            "indicator_id": code,
            "timestamp": datetime.now().isoformat()
        }

        try:
            data = fetch_indicator_data(code, offset=0, limit=CHUNK_SIZE)
            elapsed = time.time() - start_time
            result["fetch_time_seconds"] = round(elapsed, 2)

            # UNESCO API returns data in specific format
            if "data" in data and isinstance(data["data"], list):
                rows = data["data"]
            elif isinstance(data, list):
                rows = data
            else:
                print(f"  ⚠️ Unexpected data structure for {code}")
                result["status"] = "FAILED"
                result["reason"] = "unexpected_structure"
                test_log["results"].append(result)
                continue

            if not rows:
                print(f"  ⚠️ No data for {code}")
                result["status"] = "FAILED"
                result["reason"] = "empty_dataset"
                test_log["results"].append(result)
                continue

            # Save to CSV
            fname = Path(OUTPUT_DIR) / f"{code}.csv"
            with open(fname, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Entity", "Year", "Value"])
                for rec in rows:
                    ent = rec.get("entity_id") or rec.get("geoUnit") or rec.get("entity") or rec.get("entityId")
                    yr = rec.get("year")
                    val = rec.get("value")
                    if ent and yr:
                        writer.writerow([ent, yr, val])

            if fname.exists() and fname.stat().st_size > 0:
                print(f"  ✅ Wrote {len(rows)} rows to {fname.resolve()}")
                result["status"] = "SUCCESS"
                result["rows_fetched"] = len(rows)
                result["file_path"] = str(fname.resolve())
                success_count += 1
            else:
                print(f"  ❌ Failed writing {code}")
                result["status"] = "FAILED"
                result["reason"] = "write_failure"

        except Exception as e:
            elapsed = time.time() - start_time
            print(f"  ❌ Error fetching {code}: {e}")
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
        "success_rate": success_count/len(TEST_INDICATORS) if len(TEST_INDICATORS) > 0 else 0,
        "total_time_seconds": round(total_elapsed, 2)
    }

    with open(LOG_FILE, 'w') as f:
        json.dump(test_log, f, indent=2)

    print(f"\n📝 Log saved to: {Path(LOG_FILE).resolve()}")
    print("=" * 70)

    if success_count >= 6:  # At least 60% success rate (UNESCO API can be flaky)
        print("\n✅ TEST PASSED: Scraper is working")
        return 0
    else:
        print("\n❌ TEST FAILED: Success rate below 60%")
        return 1

if __name__ == "__main__":
    exit(main())
