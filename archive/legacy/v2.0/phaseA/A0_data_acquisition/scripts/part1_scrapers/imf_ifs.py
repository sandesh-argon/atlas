import os
import csv
import requests
import time
from pathlib import Path

# === CONFIG ===
INPUT_INDICATORS_CSV = "<repo-root>/v1.0/Indicators/IMFIndicators.csv"
OUTPUT_DIR = "./raw_data/imf"
BASE_IMF_URL = "https://www.imf.org/external/datamapper/api/v1"
LOG_FILE = "./extraction_logs/imf_extraction_log.json"

# HTTP session
session = requests.Session()
session.headers.update({
    "Accept": "application/json",
    "User-Agent": "imf-data-fetcher/1.0"
})

os.makedirs(OUTPUT_DIR, exist_ok=True)

def read_indicator_ids(csv_path):
    ids = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader)  # skip header
        for row in reader:
            if row and row[0].strip():
                ids.append(row[0].strip())
    return ids

def fetch_indicator_json(indicator_id, country_ids=None, periods=None):
    # Build the URL
    url = f"{BASE_IMF_URL}/{indicator_id}"
    # If country IDs are provided, append e.g. "/USA+CHN"
    if country_ids:
        joined = "+".join(country_ids)
        url = f"{url}/{joined}"
    # If years restriction
    if periods:
        url = url + "?periods=" + ",".join(str(p) for p in periods)
    resp = session.get(url)
    resp.raise_for_status()
    return resp.json()

def parse_indicator_json(indicator_id, j):
    """
    Parse JSON from IMF API, return (country, year, value) rows.
    According to blog, j["values"][indicator_id] gives country → {year: value}
    """
    rows = []
    values = j.get("values")
    if not values:
        return rows

    # Try direct mapping
    block = values.get(indicator_id)
    if block is None:
        # fallback — maybe values is already the mapping
        block = values

    for country_id, year_map in block.items():
        if not isinstance(year_map, dict):
            # sometimes a single value or nested differently
            continue
        for year_str, val in year_map.items():
            rows.append((country_id, year_str, val))
    return rows

def save_rows_to_csv(indicator_id, rows):
    if not rows:
        print(f"⚠️ {indicator_id} has no data, skipping save.")
        return None
    fname = Path(OUTPUT_DIR) / f"{indicator_id}.csv"
    with open(fname, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Country", "Year", "Value"])
        for country, year, value in rows:
            writer.writerow([country, year, value])
    # Verify
    if fname.exists() and fname.stat().st_size > 0:
        print(f"✅ Saved {indicator_id} → {fname.resolve()}")
        return fname.resolve()
    else:
        print(f"❌ Failed to save {indicator_id}")
        return None

def main():
    indicator_ids = read_indicator_ids(INPUT_INDICATORS_CSV)
    print(f"Found {len(indicator_ids)} IMF indicators.")

    for idx, ind in enumerate(indicator_ids, start=1):
        print(f"[{idx}/{len(indicator_ids)}] Fetching {ind}")
        try:
            j = fetch_indicator_json(ind)
        except Exception as e:
            print(f"Error fetching {ind}: {e}")
            continue

        rows = parse_indicator_json(ind, j)
        save_rows_to_csv(ind, rows)
        time.sleep(0.5)

if __name__ == "__main__":
    main()

