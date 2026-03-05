"""
A0.1 Test Script: World Bank WDI Scraper
Tests V1 scraper on 10 sample indicators to verify API compatibility
"""

import os
import sys
import csv
import requests
import time
import json
from pathlib import Path
from datetime import datetime

# === TEST CONFIG ===
TEST_INDICATORS = [
    "SP.POP.TOTL",        # Population, total
    "NY.GDP.MKTP.CD",     # GDP (current US$)
    "SP.DYN.LE00.IN",     # Life expectancy at birth, total (years)
    "SE.PRM.ENRR",        # School enrollment, primary (% gross)
    "SH.DYN.MORT",        # Mortality rate, under-5 (per 1,000 live births)
    "SI.POV.GINI",        # GINI index (World Bank estimate)
    "SP.URB.TOTL.IN.ZS",  # Urban population (% of total population)
    "SH.XPD.CHEX.GD.ZS",  # Current health expenditure (% of GDP)
    "EN.ATM.CO2E.PC",     # CO2 emissions (metric tons per capita)
    "IT.NET.USER.ZS"      # Individuals using the Internet (% of population)
]

OUTPUT_DIR = "./test_output/world_bank"
BASE_URL = "https://api.worldbank.org/v2/country/all/indicator/{indicator}?format=json&per_page=20000"
LOG_FILE = "./test_output/wb_test_log.json"

# === SETUP ===
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs("./test_output", exist_ok=True)
session = requests.Session()
session.headers.update({"User-Agent": "Mozilla/5.0 (data fetch script)"})

test_log = {
    "test_run": datetime.now().isoformat(),
    "indicators_tested": len(TEST_INDICATORS),
    "results": []
}

def fetch_indicator_data(indicator_id, max_retries=3):
    """
    Fetch all pages for one indicator and return list of rows (country, year, value).

    V2_NEW: Added exponential backoff for rate limiting
    """
    url = BASE_URL.format(indicator=indicator_id)
    page = 1
    all_rows = []

    start_time = time.time()

    while True:
        retry_count = 0
        while retry_count < max_retries:
            resp = session.get(url + f"&page={page}")

            # V2_NEW: Handle rate limiting
            if resp.status_code == 429:
                wait_time = 2 ** retry_count  # Exponential backoff
                print(f"⏳ Rate limited, waiting {wait_time}s...")
                time.sleep(wait_time)
                retry_count += 1
                continue

            if resp.status_code != 200:
                print(f"❌ HTTP {resp.status_code} for {indicator_id}")
                return None, time.time() - start_time

            break

        if retry_count >= max_retries:
            print(f"❌ Max retries exceeded for {indicator_id}")
            return None, time.time() - start_time

        data = resp.json()

        # if invalid or no data
        if not isinstance(data, list) or len(data) < 2:
            break
        if not isinstance(data[1], list) or len(data[1]) == 0:
            break

        entries = data[1]
        for e in entries:
            country = e.get("country", {}).get("value")
            date = e.get("date")
            value = e.get("value")
            if country and date:
                all_rows.append((country, date, value))

        if page >= data[0]["pages"]:
            break
        page += 1
        time.sleep(0.2)  # prevent rate-limit (V1_VALIDATED: Sufficient delay)

    elapsed = time.time() - start_time
    return all_rows, elapsed

def save_csv(indicator_id, rows):
    """Save rows to CSV under output folder and verify write success."""
    if not rows:
        print(f"⚠️ No data for {indicator_id}, skipping save.")
        return None

    filename = Path(OUTPUT_DIR) / f"{indicator_id}.csv"
    try:
        with open(filename, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Country", "Year", "Value"])
            writer.writerows(rows)

        # Verify the file was written and is not empty
        if filename.exists() and filename.stat().st_size > 0:
            abs_path = filename.resolve()
            print(f"✅ Saved {len(rows)} rows → {abs_path}")
            return abs_path
        else:
            print(f"❌ File {filename.name} was not written correctly.")
            return None
    except Exception as e:
        print(f"❌ Error saving {indicator_id}: {e}")
        return None

def main():
    """Test extraction on 10 sample indicators."""
    print("=" * 70)
    print("A0.1 TEST: World Bank WDI Scraper")
    print("=" * 70)
    print(f"Testing {len(TEST_INDICATORS)} indicators")
    print(f"Output directory: {Path(OUTPUT_DIR).resolve()}")
    print("=" * 70)
    print()

    total_start = time.time()

    for i, ind in enumerate(TEST_INDICATORS, 1):
        print(f"\n[{i}/{len(TEST_INDICATORS)}] Fetching {ind}...")

        rows, elapsed = fetch_indicator_data(ind)

        result = {
            "indicator_id": ind,
            "timestamp": datetime.now().isoformat(),
            "fetch_time_seconds": round(elapsed, 2)
        }

        if rows is not None:
            filepath = save_csv(ind, rows)
            result["status"] = "SUCCESS"
            result["rows_fetched"] = len(rows)
            result["file_path"] = str(filepath) if filepath else None

            # Sample data analysis
            if rows:
                non_null = [r for r in rows if r[2] is not None]
                result["non_null_values"] = len(non_null)
                result["null_values"] = len(rows) - len(non_null)

                # Get year range
                years = [int(r[1]) for r in rows if r[1]]
                if years:
                    result["year_range"] = [min(years), max(years)]
                    result["temporal_span"] = max(years) - min(years) + 1
        else:
            result["status"] = "FAILED"
            result["rows_fetched"] = 0
            result["file_path"] = None

        test_log["results"].append(result)
        time.sleep(0.5)  # gentle pacing

    total_elapsed = time.time() - total_start

    # Summary
    print("\n" + "=" * 70)
    print("TEST COMPLETE")
    print("=" * 70)

    successful = [r for r in test_log["results"] if r["status"] == "SUCCESS"]
    failed = [r for r in test_log["results"] if r["status"] == "FAILED"]

    print(f"Total indicators tested: {len(TEST_INDICATORS)}")
    print(f"Successful: {len(successful)}")
    print(f"Failed: {len(failed)}")
    print(f"Success rate: {len(successful)/len(TEST_INDICATORS)*100:.1f}%")
    print(f"Total time: {total_elapsed:.2f} seconds")
    print(f"Average time per indicator: {total_elapsed/len(TEST_INDICATORS):.2f} seconds")

    if successful:
        total_rows = sum(r["rows_fetched"] for r in successful)
        print(f"\nTotal rows fetched: {total_rows:,}")
        print(f"Average rows per indicator: {total_rows/len(successful):.0f}")

    if failed:
        print(f"\n⚠️ Failed indicators:")
        for r in failed:
            print(f"  - {r['indicator_id']}")

    # Save log
    test_log["summary"] = {
        "total_tested": len(TEST_INDICATORS),
        "successful": len(successful),
        "failed": len(failed),
        "success_rate": len(successful)/len(TEST_INDICATORS),
        "total_time_seconds": round(total_elapsed, 2),
        "avg_time_per_indicator": round(total_elapsed/len(TEST_INDICATORS), 2)
    }

    with open(LOG_FILE, 'w') as f:
        json.dump(test_log, f, indent=2)

    print(f"\n📝 Log saved to: {Path(LOG_FILE).resolve()}")
    print("=" * 70)

    # Validation
    if len(successful) >= 8:  # At least 80% success rate
        print("\n✅ TEST PASSED: Scraper is working correctly")
        return 0
    else:
        print("\n❌ TEST FAILED: Success rate below 80%")
        return 1

if __name__ == "__main__":
    sys.exit(main())
