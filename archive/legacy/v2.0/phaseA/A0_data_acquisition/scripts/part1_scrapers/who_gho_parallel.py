"""
WHO GHO Parallel Scraper - Speed Optimized
Uses 8 parallel workers to extract remaining indicators
"""

import pandas as pd
import requests
import os
import json
import time
from pathlib import Path
from datetime import datetime
from multiprocessing import Pool, Manager
from functools import partial

# === CONFIG ===
INPUT_FILE = "<repo-root>/v1.0/Indicators/WHO Global Health Observatory (GHO).csv"
OUTPUT_DIR = "./raw_data/who"
BASE_URL = "https://ghoapi.azureedge.net/api/"
FAILED_LOG = "./extraction_logs/who_failed_indicators.json"
LOG_FILE = "./extraction_logs/who_parallel_log.json"
NUM_WORKERS = 8  # Parallel workers

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs("./extraction_logs", exist_ok=True)

def validate_who_data(data):
    """Validate WHO API response structure"""
    if not isinstance(data, dict):
        return False
    if "value" not in data:
        return False
    if not isinstance(data["value"], list):
        return False
    return len(data["value"]) > 0

def fetch_indicator(code, max_attempts=3, delay=2):
    """Fetch indicator data with retry logic"""
    for attempt in range(max_attempts):
        try:
            url = f"{BASE_URL}{code}"
            response = requests.get(url, timeout=60)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            if attempt == max_attempts - 1:
                return None
            wait_time = delay * (2 ** attempt)
            time.sleep(wait_time)
    return None

def process_indicator(code, progress_dict):
    """Process single indicator (worker function)"""
    # Check if already exists
    out_path = os.path.join(OUTPUT_DIR, f"{code}.csv")
    if os.path.exists(out_path):
        progress_dict['skipped'] = progress_dict.get('skipped', 0) + 1
        return {"code": code, "status": "exists", "rows": 0}

    try:
        data = fetch_indicator(code)

        if not validate_who_data(data):
            progress_dict['empty'] = progress_dict.get('empty', 0) + 1
            return {"code": code, "status": "empty", "rows": 0}

        records = data.get("value", [])

        if not records:
            progress_dict['empty'] = progress_dict.get('empty', 0) + 1
            return {"code": code, "status": "empty", "rows": 0}

        # Normalize JSON into DataFrame
        df = pd.json_normalize(records)

        # Keep only useful fields
        required_cols = ["SpatialDim", "TimeDim", "NumericValue"]

        if not all(col in df.columns for col in required_cols):
            progress_dict['missing_cols'] = progress_dict.get('missing_cols', 0) + 1
            return {"code": code, "status": "missing_columns", "rows": 0}

        keep_cols = {
            "SpatialDim": "Country",
            "TimeDim": "Year",
            "NumericValue": "Value"
        }
        filtered = df[list(keep_cols.keys())].rename(columns=keep_cols)

        # Save to CSV
        filtered.to_csv(out_path, index=False)
        progress_dict['success'] = progress_dict.get('success', 0) + 1

        # Progress update every 100 indicators
        if progress_dict['success'] % 100 == 0:
            print(f"Progress: {progress_dict['success']} indicators completed")

        return {"code": code, "status": "success", "rows": len(filtered)}

    except Exception as e:
        progress_dict['error'] = progress_dict.get('error', 0) + 1
        return {"code": code, "status": "error", "error": str(e), "rows": 0}

def main():
    """Main parallel extraction"""
    start_time = datetime.now()
    print("=" * 70)
    print("WHO GHO PARALLEL EXTRACTION")
    print(f"Workers: {NUM_WORKERS}")
    print("=" * 70)

    # Read indicator codes
    df_codes = pd.read_csv(INPUT_FILE)
    indicator_codes = df_codes.iloc[:, 1].dropna().unique().tolist()

    print(f"Total indicators: {len(indicator_codes)}")

    # Check existing files
    existing = []
    for code in indicator_codes:
        out_path = os.path.join(OUTPUT_DIR, f"{code}.csv")
        if os.path.exists(out_path):
            existing.append(code)

    remaining = [code for code in indicator_codes if code not in existing]

    print(f"Already completed: {len(existing)}")
    print(f"Remaining: {len(remaining)}")
    print(f"\nStarting parallel extraction with {NUM_WORKERS} workers...")
    print("=" * 70)

    if not remaining:
        print("All indicators already extracted!")
        return

    # Shared progress tracking
    manager = Manager()
    progress_dict = manager.dict()
    progress_dict['success'] = len(existing)
    progress_dict['skipped'] = 0
    progress_dict['empty'] = 0
    progress_dict['missing_cols'] = 0
    progress_dict['error'] = 0

    # Process in parallel
    with Pool(NUM_WORKERS) as pool:
        process_func = partial(process_indicator, progress_dict=progress_dict)
        results = pool.map(process_func, remaining)

    # Collect failed indicators
    failed_indicators = [
        {"code": r["code"], "reason": r["status"], "error": r.get("error", "")}
        for r in results
        if r["status"] not in ["success", "exists"]
    ]

    if failed_indicators:
        with open(FAILED_LOG, 'w') as f:
            json.dump(failed_indicators, f, indent=2)

    # Summary
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()

    success_count = len([r for r in results if r["status"] == "success"]) + len(existing)

    print("\n" + "=" * 70)
    print("EXTRACTION COMPLETE")
    print("=" * 70)
    print(f"Total indicators: {len(indicator_codes)}")
    print(f"Successfully extracted: {success_count}")
    print(f"Empty datasets: {progress_dict.get('empty', 0)}")
    print(f"Missing columns: {progress_dict.get('missing_cols', 0)}")
    print(f"Errors: {progress_dict.get('error', 0)}")
    print(f"Duration: {duration:.1f} seconds ({duration/60:.1f} minutes)")
    print(f"Speed: {len(remaining)/duration*60:.1f} indicators/minute")
    print("=" * 70)

if __name__ == "__main__":
    main()
