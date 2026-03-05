import requests
import json
import csv
import os
import time
from pathlib import Path

# Base configuration
BASE_URL = "https://sdmx.data.unicef.org/ws/public/sdmxapi/rest"
OUTPUT_DIR = "./raw_data/unicef"
INDICATORS_CSV = "<repo-root>/v1.0/Indicators/unicef_indicators_list.csv"
LOG_FILE = "./extraction_logs/unicef_extraction_log.json"

def create_output_directory():
    """Create output directory if it doesn't exist"""
    Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
    print(f"✓ Output directory created: {OUTPUT_DIR}")

def get_all_dataflows():
    """Fetch all available dataflows (indicators) from UNICEF API"""
    url = f"{BASE_URL}/dataflow/all/all/latest/"
    params = {
        'format': 'sdmx-json',
        'detail': 'full',
        'references': 'none'
    }
    
    print("Fetching list of all indicators...")
    response = requests.get(url, params=params)
    response.raise_for_status()
    
    data = response.json()
    dataflows = data['data']['dataflows']
    print(f"✓ Found {len(dataflows)} indicators")
    
    return dataflows

def save_indicators_metadata(dataflows):
    """Save all indicators with descriptions to a CSV file"""
    csv_path = os.path.join(OUTPUT_DIR, INDICATORS_CSV)
    
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['indicator_id', 'indicator_name', 'agency', 'version', 'description'])
        
        for df in dataflows:
            indicator_id = df.get('id', '')
            # Get English name, fallback to first available name
            names = df.get('names', {})
            indicator_name = names.get('en', list(names.values())[0] if names else '')
            agency = df.get('agencyID', '')
            version = df.get('version', '')
            # Get English description if available
            descriptions = df.get('descriptions', {})
            description = descriptions.get('en', list(descriptions.values())[0] if descriptions else '')
            
            writer.writerow([indicator_id, indicator_name, agency, version, description])
    
    print(f"✓ Indicators metadata saved to: {csv_path}")
    return csv_path

def get_indicator_data(agency, dataflow_id, version):
    """Fetch data for a specific indicator"""
    # Request all dimensions (using 'all' selector)
    url = f"{BASE_URL}/data/{agency},{dataflow_id},{version}/all"
    params = {
        'format': 'sdmx-json'
    }
    
    try:
        response = requests.get(url, params=params, timeout=120)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"  ⚠ Error fetching data: {str(e)}")
        return None

def parse_sdmx_data_to_csv(sdmx_data, indicator_id):
    """Parse SDMX-JSON format and extract country, year, value"""
    if not sdmx_data:
        return []
    
    try:
        # Navigate the SDMX-JSON structure
        data_container = sdmx_data.get('data', {})
        datasets = data_container.get('dataSets', [])
        if not datasets:
            return []
        
        dataset = datasets[0]
        series = dataset.get('series', {})
        structure = data_container.get('structure', {})
        dimensions = structure.get('dimensions', {})
        
        # Get series dimensions (country, indicator, sex, age, etc.)
        series_dims = dimensions.get('series', [])
        
        # Get observation dimensions (usually TIME_PERIOD)
        obs_dims = dimensions.get('observation', [])
        
        # Build lookup dictionaries for each dimension
        dim_lookups = {}
        for dim in series_dims:
            dim_id = dim.get('id')
            dim_index = dim.get('keyPosition')
            dim_values = dim.get('values', [])
            dim_lookups[dim_index] = {
                'id': dim_id,
                'values': dim_values
            }
        
        # Get time period values (from observation dimension)
        time_values = []
        if obs_dims:
            time_values = obs_dims[0].get('values', [])
        
        # Find which dimension is the geographic area (country)
        country_dim_index = None
        for idx, info in dim_lookups.items():
            if info['id'] in ['REF_AREA', 'GEOGRAPHIC_AREA', 'GEO_PICT']:
                country_dim_index = idx
                break
        
        # Extract data rows
        rows = []
        for series_key, series_data in series.items():
            # Parse series key (format: "0:1:2:3:4:5...")
            key_parts = [int(x) for x in series_key.split(':')]
            
            # Extract all dimension values for this series
            row_dims = {}
            for dim_idx, dim_info in dim_lookups.items():
                if dim_idx < len(key_parts):
                    value_idx = key_parts[dim_idx]
                    if value_idx < len(dim_info['values']):
                        value_obj = dim_info['values'][value_idx]
                        # Get name, fallback to id
                        value_name = value_obj.get('name', value_obj.get('id', ''))
                        row_dims[dim_info['id']] = value_name
            
            # Get country name
            country = ''
            if country_dim_index is not None and country_dim_index in dim_lookups:
                country_idx = key_parts[country_dim_index] if country_dim_index < len(key_parts) else 0
                country_values = dim_lookups[country_dim_index]['values']
                if country_idx < len(country_values):
                    country = country_values[country_idx].get('name', 
                                                             country_values[country_idx].get('id', ''))
            
            # Extract observations (time period and values)
            observations = series_data.get('observations', {})
            
            for obs_key, obs_data in observations.items():
                obs_idx = int(obs_key)
                
                # Get the value (first element in observation array)
                value = obs_data[0] if isinstance(obs_data, list) else obs_data
                
                # Get time period
                time_period = ''
                if obs_idx < len(time_values):
                    time_period = time_values[obs_idx].get('name', 
                                                          time_values[obs_idx].get('id', ''))
                
                # Create row with country, year, value, and all other dimensions
                row = {
                    'country': country,
                    'year': time_period,
                    'value': value,
                }
                
                # Add all other dimensions as additional columns
                for dim_id, dim_value in row_dims.items():
                    if dim_id not in ['REF_AREA', 'GEOGRAPHIC_AREA', 'GEO_PICT', 'TIME_PERIOD']:
                        row[dim_id] = dim_value
                
                rows.append(row)
        
        return rows
    
    except Exception as e:
        print(f"  ⚠ Error parsing data: {str(e)}")
        import traceback
        traceback.print_exc()
        return []

def save_indicator_csv(indicator_id, rows):
    """Save indicator data to individual CSV file"""
    if not rows:
        print(f"  ⚠ No data to save for {indicator_id}")
        return
    
    csv_path = os.path.join(OUTPUT_DIR, f"{indicator_id}.csv")
    
    # Get all unique keys across all rows for headers
    all_keys = set()
    for row in rows:
        all_keys.update(row.keys())
    
    # Prioritize country, year, value columns first
    priority_cols = ['country', 'year', 'value']
    other_cols = sorted(all_keys - set(priority_cols))
    headers = [col for col in priority_cols if col in all_keys] + other_cols
    
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=headers, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)
    
    print(f"  ✓ Saved {len(rows)} rows to: {csv_path}")

def main():
    """Main execution function"""
    print("=" * 60)
    print("UNICEF Data Extraction Script")
    print("=" * 60)
    
    # Create output directory
    create_output_directory()
    
    # Step 1: Get all indicators
    dataflows = get_all_dataflows()
    
    # Step 2: Save indicators metadata
    save_indicators_metadata(dataflows)
    
    # Step 3: Extract data for each indicator
    print("\nStarting data extraction for each indicator...")
    print("(This may take a while depending on the number of indicators)")
    print("-" * 60)
    
    success_count = 0
    error_count = 0
    
    for idx, df in enumerate(dataflows, 1):
        indicator_id = df.get('id', '')
        indicator_name = df.get('names', {}).get('en', '')
        agency = df.get('agencyID', 'UNICEF')
        version = df.get('version', '1.0')
        
        print(f"\n[{idx}/{len(dataflows)}] Processing: {indicator_id}")
        print(f"  Name: {indicator_name}")
        
        # Fetch data
        sdmx_data = get_indicator_data(agency, indicator_id, version)
        
        if sdmx_data:
            # Parse and save
            rows = parse_sdmx_data_to_csv(sdmx_data, indicator_id)
            if rows:
                save_indicator_csv(indicator_id, rows)
                success_count += 1
            else:
                print(f"  ⚠ No data rows extracted for {indicator_id}")
                error_count += 1
        else:
            error_count += 1
        
        # Be respectful with API calls
        time.sleep(0.5)
    
    # Summary
    print("\n" + "=" * 60)
    print("EXTRACTION COMPLETE")
    print("=" * 60)
    print(f"Total indicators: {len(dataflows)}")
    print(f"Successfully extracted: {success_count}")
    print(f"Errors: {error_count}")
    print(f"\nOutput location: {OUTPUT_DIR}/")
    print("=" * 60)

if __name__ == "__main__":
    main()
