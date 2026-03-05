"""
UNESCO UIS Bulk Data Download Service (BDDS) Parser
Adapted from UIS BDDS Python Tutorial for V2 Global Causal Discovery

Processes UNESCO bulk CSV files and converts to standard format:
- Input: SDG_DATA_NATIONAL.csv, OPRI_DATA_NATIONAL.csv
- Output: Individual indicator CSV files (Country, Year, Value)
- Matches World Bank, WHO, IMF, UNICEF output format

Data Sources:
- SDG: Education SDG indicators (~1.3M rows, 2,662 indicators)
- OPRI: Other Policy-Relevant Indicators (~2.7M rows, additional indicators)
"""

import pandas as pd
import numpy as np
import os
import json
from pathlib import Path
from datetime import datetime

# === CONFIGURATION ===
UNESCO_BULK_DIR = "<repo-root>/v2.0/UIS_Bulk"
OUTPUT_DIR = "./raw_data/unesco"
LOG_FILE = "./extraction_logs/unesco_bdds_log.json"

# Create output directories
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs("./extraction_logs", exist_ok=True)

# === LOGGING ===
extraction_log = {
    "extraction_start": datetime.now().isoformat(),
    "datasets_processed": [],
    "indicators_extracted": 0,
    "total_rows": 0,
    "errors": []
}

def log_progress(message, level="INFO"):
    """Log progress with timestamp"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {level}: {message}")

def load_unesco_dataset(dataset_name):
    """
    Load UNESCO BDDS dataset from ZIP or extracted CSV

    Args:
        dataset_name: "SDG" or "OPRI"

    Returns:
        Dictionary with data, labels, countries, metadata
    """
    log_progress(f"Loading UNESCO {dataset_name} dataset...")

    base_path = Path(UNESCO_BULK_DIR)

    # Define file paths
    data_file = base_path / f"{dataset_name}_DATA_NATIONAL.csv"
    label_file = base_path / f"{dataset_name}_LABEL.csv"
    country_file = base_path / f"{dataset_name}_COUNTRY.csv"
    metadata_file = base_path / f"{dataset_name}_METADATA.csv"

    # Check if files exist
    for f in [data_file, label_file, country_file]:
        if not f.exists():
            raise FileNotFoundError(f"Required file not found: {f}")

    # Load CSVs with pandas
    log_progress(f"  Loading {data_file.name} (~1-3M rows)...")
    data = pd.read_csv(data_file)

    log_progress(f"  Loading {label_file.name}...")
    labels = pd.read_csv(label_file)

    log_progress(f"  Loading {country_file.name}...")
    countries = pd.read_csv(country_file)

    # Metadata is optional (large file)
    metadata = None
    if metadata_file.exists():
        log_progress(f"  Loading {metadata_file.name} (large file, may take time)...")
        metadata = pd.read_csv(metadata_file)

    log_progress(f"  ✅ Loaded {len(data):,} data rows, {len(labels):,} indicators, {len(countries):,} countries")

    return {
        "data": data,
        "labels": labels,
        "countries": countries,
        "metadata": metadata,
        "dataset_name": dataset_name
    }

def convert_to_standard_format(unesco_data, output_dir):
    """
    Convert UNESCO BDDS format to standard indicator CSV format

    UNESCO format:
        INDICATOR_ID, COUNTRY_ID, YEAR, VALUE, MAGNITUDE, QUALIFIER

    Standard format (World Bank style):
        Country, Year, Value

    Creates one CSV file per indicator
    """
    data_df = unesco_data["data"]
    labels_df = unesco_data["labels"]
    countries_df = unesco_data["countries"]
    dataset_name = unesco_data["dataset_name"]

    log_progress(f"Converting {dataset_name} data to standard format...")

    # Get unique indicators
    unique_indicators = data_df['INDICATOR_ID'].unique()
    log_progress(f"  Found {len(unique_indicators)} unique indicators")

    # Create country code to name mapping
    country_map = dict(zip(countries_df['COUNTRY_ID'], countries_df['COUNTRY_NAME_EN']))

    indicators_saved = 0
    total_rows_saved = 0
    errors = []

    for idx, indicator_id in enumerate(unique_indicators, 1):
        try:
            # Filter data for this indicator
            indicator_data = data_df[data_df['INDICATOR_ID'] == indicator_id].copy()

            # Skip if no data
            if len(indicator_data) == 0:
                continue

            # Map country codes to names
            indicator_data['Country'] = indicator_data['COUNTRY_ID'].map(country_map)

            # Rename columns to standard format
            indicator_data['Year'] = indicator_data['YEAR']
            indicator_data['Value'] = indicator_data['VALUE']

            # Select only standard columns
            standard_data = indicator_data[['Country', 'Year', 'Value']].copy()

            # Remove rows with missing countries (unmapped codes)
            standard_data = standard_data.dropna(subset=['Country'])

            # Skip indicators with too few data points
            if len(standard_data) < 10:
                continue

            # Save to CSV
            output_file = Path(output_dir) / f"{indicator_id}.csv"
            standard_data.to_csv(output_file, index=False)

            indicators_saved += 1
            total_rows_saved += len(standard_data)

            # Progress update every 100 indicators
            if idx % 100 == 0:
                log_progress(f"  Processed {idx}/{len(unique_indicators)} indicators, saved {indicators_saved} files")

        except Exception as e:
            error_msg = f"Error processing {indicator_id}: {str(e)}"
            log_progress(error_msg, "ERROR")
            errors.append(error_msg)
            continue

    log_progress(f"  ✅ Saved {indicators_saved} indicator files ({total_rows_saved:,} total rows)")

    return {
        "indicators_saved": indicators_saved,
        "total_rows": total_rows_saved,
        "errors": errors
    }

def process_all_unesco_datasets():
    """Process all 6 UNESCO BDDS datasets"""
    log_progress("=" * 70)
    log_progress("UNESCO UIS BDDS EXTRACTION - ALL 6 DATASETS")
    log_progress("=" * 70)

    results = {}

    # List of all datasets to process
    datasets = [
        ("SDG", "Education SDG indicators"),
        ("OPRI", "Other Policy-Relevant Indicators"),
        ("DEM", "Demography"),
        ("SDG11", "SDG 11 indicators"),
        ("SCN-SDG", "Sub-national SDG"),
        ("SCN-OPRI", "Sub-national OPRI")
    ]

    for dataset_name, description in datasets:
        try:
            log_progress(f"\n📊 Processing {dataset_name} ({description})...")
            dataset = load_unesco_dataset(dataset_name)
            dataset_results = convert_to_standard_format(dataset, OUTPUT_DIR)
            results[dataset_name] = dataset_results

            extraction_log["datasets_processed"].append({
                "dataset": dataset_name,
                "description": description,
                "indicators": dataset_results["indicators_saved"],
                "rows": dataset_results["total_rows"],
                "errors": len(dataset_results["errors"])
            })
        except Exception as e:
            log_progress(f"❌ Failed to process {dataset_name}: {e}", "ERROR")
            extraction_log["errors"].append(f"{dataset_name} processing failed: {str(e)}")

    # Calculate totals
    total_indicators = sum(r.get("indicators_saved", 0) for r in results.values())
    total_rows = sum(r.get("total_rows", 0) for r in results.values())

    extraction_log["indicators_extracted"] = total_indicators
    extraction_log["total_rows"] = total_rows
    extraction_log["extraction_end"] = datetime.now().isoformat()

    # Save log
    with open(LOG_FILE, 'w') as f:
        json.dump(extraction_log, f, indent=2)

    # Final summary
    log_progress("\n" + "=" * 70)
    log_progress("EXTRACTION COMPLETE")
    log_progress("=" * 70)
    log_progress(f"Total indicators extracted: {total_indicators}")
    log_progress(f"Total rows: {total_rows:,}")
    log_progress(f"Output directory: {Path(OUTPUT_DIR).resolve()}")
    log_progress(f"Log file: {Path(LOG_FILE).resolve()}")
    log_progress("=" * 70)

    return results

if __name__ == "__main__":
    results = process_all_unesco_datasets()
