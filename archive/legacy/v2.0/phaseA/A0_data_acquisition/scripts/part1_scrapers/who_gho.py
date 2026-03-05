"""
V1 → V2 Transfer: WHO Global Health Observatory API Scraper
Original: /Data/Extraction_Scripts/WHO.py
Status: VALIDATED
V1 Performance: Extracted ~2,000 health indicators, 3-4 hours runtime
V2 Modifications:
    - Add error handling for malformed JSON responses
    - Implement retry logic (3 attempts)
    - Add data validation before saving
    - Log missing indicators to separate file
Evidence: V1 successfully collected all WHO indicators, but ~10% had empty datasets
"""

import pandas as pd
import requests
import os
import json
import time
from pathlib import Path

# === CONFIG ===
INPUT_FILE = "<repo-root>/v1.0/Indicators/WHO Global Health Observatory (GHO).csv"
OUTPUT_DIR = "./raw_data/who"
BASE_URL = "https://ghoapi.azureedge.net/api/"
FAILED_LOG = "./extraction_logs/who_failed_indicators.json"
LOG_FILE = "./extraction_logs/who_extraction_log.json"

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs("./extraction_logs", exist_ok=True)

# V2_NEW: Validation function
def validate_who_data(data):
    """Validate WHO API response structure"""
    if not isinstance(data, dict):
        return False
    if "value" not in data:
        return False
    if not isinstance(data["value"], list):
        return False
    return len(data["value"]) > 0

# V2_NEW: Retry decorator
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
    """
    Main extraction loop.

    V1_VALIDATED: Successfully extracted 2,000 health indicators
    V2_NEW: Enhanced error handling and validation
    """
    # Step 1: Read indicator codes
    df_codes = pd.read_csv(INPUT_FILE)
    indicator_codes = df_codes.iloc[:, 1].dropna().unique()  # column A

    print(f"Found {len(indicator_codes)} indicator codes")

    # V2_NEW: Track failures
    failed_indicators = []
    success_count = 0

    # Step 2: Loop through indicator codes
    for idx, code in enumerate(indicator_codes, 1):
        print(f"[{idx}/{len(indicator_codes)}] Fetching {code}")

        try:
            data = fetch_indicator(code)

            # V2_NEW: Validate before processing
            if not validate_who_data(data):
                print(f"  ⚠️ Invalid data structure for {code}")
                failed_indicators.append({"code": code, "reason": "invalid_structure"})
                continue

            # The JSON structure: data["value"] contains rows
            records = data.get("value", [])

            if not records:
                print(f"  ⚠️ No data for {code}")
                failed_indicators.append({"code": code, "reason": "empty_dataset"})
                continue

            # Step 3: Normalize JSON into DataFrame
            df = pd.json_normalize(records)

            # Keep only useful fields: Country, Year, Value
            # Columns vary, but usually: 'SpatialDim', 'TimeDim', 'NumericValue'
            required_cols = ["SpatialDim", "TimeDim", "NumericValue"]

            # V2_NEW: Check if required columns exist
            if not all(col in df.columns for col in required_cols):
                print(f"  ⚠️ Missing required columns for {code}")
                print(f"    Available: {df.columns.tolist()}")
                failed_indicators.append({"code": code, "reason": "missing_columns"})
                continue

            keep_cols = {
                "SpatialDim": "Country",
                "TimeDim": "Year",
                "NumericValue": "Value"
            }
            filtered = df[list(keep_cols.keys())].rename(columns=keep_cols)

            # Step 4: Save to CSV
            out_path = os.path.join(OUTPUT_DIR, f"{code}.csv")
            filtered.to_csv(out_path, index=False)
            print(f"  ✓ Saved {len(filtered)} rows to {out_path}")
            success_count += 1

        except Exception as e:
            print(f"  ❌ Error fetching {code}: {e}")
            failed_indicators.append({"code": code, "reason": str(e)})

        # V1_VALIDATED: Gentle rate limiting
        time.sleep(0.3)

    # V2_NEW: Save failed indicators log
    if failed_indicators:
        with open(FAILED_LOG, 'w') as f:
            json.dump(failed_indicators, f, indent=2)
        print(f"\n⚠️ {len(failed_indicators)} indicators failed, logged to {FAILED_LOG}")

    # V2_NEW: Summary
    print("\n" + "=" * 60)
    print("EXTRACTION COMPLETE")
    print("=" * 60)
    print(f"Total indicators: {len(indicator_codes)}")
    print(f"Successfully extracted: {success_count}")
    print(f"Failed: {len(failed_indicators)}")
    print("=" * 60)

if __name__ == "__main__":
    main()
