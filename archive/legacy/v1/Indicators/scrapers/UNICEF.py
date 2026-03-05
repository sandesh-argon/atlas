import requests
import csv

# Target URL for all dataflows
url = "https://sdmx.data.unicef.org/ws/public/sdmxapi/rest/dataflow/all/all/latest/?format=sdmx-json&detail=full&references=none"

response = requests.get(url)
data = response.json()

dataflows = data.get("data", {}).get("dataflows", [])

if not dataflows:
    print("No dataflows found!")
else:
    output_file = "unicef_indicators_list.csv"
    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["indicator_id", "indicator_name"])
        for df in dataflows:
            ind_id = df.get("id")
            name_field = df.get("name", "")
            
            # Handle string vs dict for name
            if isinstance(name_field, dict):
                ind_name = name_field.get("en", "")
            else:
                ind_name = str(name_field)
            
            writer.writerow([ind_id, ind_name])
    
    print(f"Wrote {len(dataflows)} indicator records to {output_file}")

