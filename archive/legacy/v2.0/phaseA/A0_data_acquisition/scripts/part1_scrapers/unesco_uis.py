import os
import csv
import requests
import time
from pathlib import Path

# === CONFIG ===
INPUT_INDICATORS = "<repo-root>/v1.0/Indicators/UISIndicators.csv"  # your CSV listing UIS indicator IDs (first column)
OUTPUT_DIR = "<repo-root>/v1.0/Data/UIS_Data/"
BASE_ENDPOINT = "https://api.uis.unesco.org/api/public/data/indicators"

# You might need to chunk by entity or year if large
CHUNK_SIZE = 50000  # safe chunk size below cap

os.makedirs(OUTPUT_DIR, exist_ok=True)
session = requests.Session()
session.headers.update({"Accept": "application/json"})

def read_indicator_codes(csv_path):
    codes = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader)  # skip header
        for r in reader:
            if len(r) > 0 and r[0].strip():
                codes.append(r[0].strip())
    return codes

def fetch_indicator_data(indicator_id, offset=0, limit=CHUNK_SIZE):
    """
    Fetch a chunk of data from the UIS API for a given indicator.
    Returns JSON response.
    """
    params = {
        "indicator": indicator_id,
        "offset": offset,
        "limit": limit
    }
    resp = session.get(BASE_ENDPOINT, params=params)
    resp.raise_for_status()
    return resp.json()

def save_rows_to_csv(indicator_id, rows):
    if not rows:
        print(f"⚠️ No rows for {indicator_id}, skip.")
        return None
    fname = Path(OUTPUT_DIR) / f"{indicator_id}.csv"
    with open(fname, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        # header
        writer.writerow(["Entity", "Year", "Value"])
        for rec in rows:
            # The JSON record might have fields like "entity_id", "year", "value"
            ent = rec.get("entity_id") or rec.get("geoUnit") or rec.get("entity") or rec.get("entityId")
            yr = rec.get("year")
            val = rec.get("value")
            writer.writerow([ent, yr, val])

    # verify file write
    if fname.exists() and fname.stat().st_size > 0:
        print(f"✅ Wrote {indicator_id} to {fname.resolve()}")
        return fname.resolve()
    else:
        print(f"❌ Failed writing {indicator_id}")
        return None

def scrape_all():
    codes = read_indicator_codes(INPUT_INDICATORS)
    print(f"Found {len(codes)} indicators to fetch.")

    for idx, code in enumerate(codes, start=1):
        print(f"[{idx}/{len(codes)}] Indicator: {code}")
        all_rows = []
        offset = 0

        while True:
            try:
                data = fetch_indicator_data(code, offset=offset, limit=CHUNK_SIZE)
            except Exception as e:
                print(f"Error fetching {code} at offset {offset}: {e}")
                break

            # The JSON structure is likely: { "data": [ ... ] , "count": ..., "offset": ..., ... }
            recs = data.get("data") or data.get("records") or []
            if not recs:
                break

            all_rows.extend(recs)
            print(f"  → got {len(recs)} recs (offset {offset})")

            # If recs length less than limit, presumably last page
            if len(recs) < CHUNK_SIZE:
                break
            offset += CHUNK_SIZE
            time.sleep(0.2)

        save_rows_to_csv(code, all_rows)
        time.sleep(0.5)

if __name__ == "__main__":
    scrape_all()

