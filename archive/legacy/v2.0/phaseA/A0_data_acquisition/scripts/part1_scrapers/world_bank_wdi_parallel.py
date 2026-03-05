"""
World Bank WDI Parallel Scraper - Speed Optimized
Uses 8 parallel workers to extract remaining indicators
"""

import os
import csv
import requests
import time
import json
from pathlib import Path
from datetime import datetime
from multiprocessing import Pool, Manager
from functools import partial

# === CONFIG ===
INPUT_FILE = "<repo-root>/v1.0/Indicators/world_bank_indicators.csv"
OUTPUT_DIR = "./raw_data/world_bank"
BASE_URL = "https://api.worldbank.org/v2/country/all/indicator/{indicator}?format=json&per_page=20000"
CHECKPOINT_FILE = "./extraction_logs/wb_progress.json"
LOG_FILE = "./extraction_logs/world_bank_parallel_log.json"
NUM_WORKERS = 8  # Parallel workers

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs("./extraction_logs", exist_ok=True)

# Create a session for each worker
def create_session():
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0 (data fetch script)"})
    return session

def fetch_indicator_data(indicator_id, session, max_retries=3):
    """Fetch all pages for one indicator"""
    url = BASE_URL.format(indicator=indicator_id)
    page = 1
    all_rows = []

    while True:
        retry_count = 0
        while retry_count < max_retries:
            try:
                resp = session.get(url + f"&page={page}", timeout=30)

                if resp.status_code == 429:
                    wait_time = 2 ** retry_count
                    time.sleep(wait_time)
                    retry_count += 1
                    continue

                if resp.status_code != 200:
                    return None

                break
            except:
                retry_count += 1
                if retry_count >= max_retries:
                    return None
                time.sleep(2 ** retry_count)

        if retry_count >= max_retries:
            return None

        try:
            data = resp.json()
        except:
            return None

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
        time.sleep(0.1)  # Reduced delay

    return all_rows

def save_csv(indicator_id, rows):
    """Save rows to CSV"""
    if not rows:
        return None

    filename = Path(OUTPUT_DIR) / f"{indicator_id}.csv"
    try:
        with open(filename, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Country", "Year", "Value"])
            writer.writerows(rows)

        if filename.exists() and filename.stat().st_size > 0:
            return filename.resolve()
    except:
        return None
    return None

def process_indicator(indicator_id, progress_dict, completed_list):
    """Process single indicator (worker function)"""
    # Check if already completed
    if indicator_id in completed_list:
        return {"indicator": indicator_id, "status": "skipped", "rows": 0}

    # Check if file exists
    outfile = Path(OUTPUT_DIR) / f"{indicator_id}.csv"
    if outfile.exists() and outfile.stat().st_size > 0:
        return {"indicator": indicator_id, "status": "exists", "rows": 0}

    # Create session for this worker
    session = create_session()

    # Fetch data
    rows = fetch_indicator_data(indicator_id, session)

    if rows is not None:
        save_csv(indicator_id, rows)
        progress_dict['completed'] = progress_dict.get('completed', 0) + 1

        # Progress update every 50 indicators
        if progress_dict['completed'] % 50 == 0:
            print(f"Progress: {progress_dict['completed']} indicators completed")

        return {"indicator": indicator_id, "status": "success", "rows": len(rows)}
    else:
        progress_dict['failed'] = progress_dict.get('failed', 0) + 1
        return {"indicator": indicator_id, "status": "failed", "rows": 0}

def main():
    """Main parallel extraction"""
    start_time = datetime.now()
    print("=" * 70)
    print("WORLD BANK WDI PARALLEL EXTRACTION")
    print(f"Workers: {NUM_WORKERS}")
    print("=" * 70)

    # Load indicators
    indicators = []
    with open(INPUT_FILE, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            indicators.append(row["id"] if "id" in row else row["indicator_id"])

    print(f"Total indicators: {len(indicators)}")

    # Load checkpoint
    checkpoint = {"completed": [], "failed": []}
    if Path(CHECKPOINT_FILE).exists():
        with open(CHECKPOINT_FILE, 'r') as f:
            checkpoint = json.load(f)

    # Check existing files
    existing = set()
    for ind in indicators:
        outfile = Path(OUTPUT_DIR) / f"{ind}.csv"
        if outfile.exists() and outfile.stat().st_size > 0:
            existing.add(ind)

    # Filter to remaining indicators
    completed_set = set(checkpoint.get("completed", [])) | existing
    remaining = [ind for ind in indicators if ind not in completed_set]

    print(f"Already completed: {len(completed_set)}")
    print(f"Remaining: {len(remaining)}")
    print(f"\nStarting parallel extraction with {NUM_WORKERS} workers...")
    print("=" * 70)

    if not remaining:
        print("All indicators already extracted!")
        return

    # Shared progress tracking
    manager = Manager()
    progress_dict = manager.dict()
    progress_dict['completed'] = len(completed_set)
    progress_dict['failed'] = len(checkpoint.get("failed", []))
    completed_list_shared = manager.list(list(completed_set))

    # Process in parallel
    with Pool(NUM_WORKERS) as pool:
        process_func = partial(process_indicator, progress_dict=progress_dict, completed_list=completed_list_shared)
        results = pool.map(process_func, remaining)

    # Update checkpoint
    all_completed = [r["indicator"] for r in results if r["status"] in ["success", "exists", "skipped"]]
    all_failed = [r["indicator"] for r in results if r["status"] == "failed"]

    checkpoint["completed"] = list(set(checkpoint.get("completed", []) + all_completed + list(existing)))
    checkpoint["failed"] = list(set(checkpoint.get("failed", []) + all_failed))

    with open(CHECKPOINT_FILE, 'w') as f:
        json.dump(checkpoint, f, indent=2)

    # Summary
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()

    print("\n" + "=" * 70)
    print("EXTRACTION COMPLETE")
    print("=" * 70)
    print(f"Total indicators: {len(indicators)}")
    print(f"Successfully extracted: {len(checkpoint['completed'])}")
    print(f"Failed: {len(checkpoint['failed'])}")
    print(f"Duration: {duration:.1f} seconds ({duration/60:.1f} minutes)")
    print(f"Speed: {len(remaining)/duration*60:.1f} indicators/minute")
    print("=" * 70)

if __name__ == "__main__":
    main()
