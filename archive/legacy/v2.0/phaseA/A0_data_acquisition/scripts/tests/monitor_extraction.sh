#!/bin/bash
# Monitor A0.6 Data Extraction Progress
# Tracks all 5 scrapers: UNESCO, World Bank, WHO, IMF, UNICEF

echo "========================================"
echo "A0.6 DATA EXTRACTION MONITORING"
echo "========================================"
echo ""
echo "Timestamp: $(date)"
echo ""

# Check if processes are running
echo "--- PROCESS STATUS ---"
echo -n "World Bank: "
if pgrep -f "world_bank_wdi_parallel.py" > /dev/null; then
    wb_count=$(pgrep -f "world_bank_wdi_parallel.py" | wc -l)
    echo "✓ RUNNING (${wb_count} workers)"
elif pgrep -f "world_bank_wdi.py" > /dev/null; then
    echo "✓ RUNNING (sequential)"
else
    echo "○ STOPPED"
fi

echo -n "WHO GHO: "
if pgrep -f "who_gho_parallel.py" > /dev/null; then
    who_count=$(pgrep -f "who_gho_parallel.py" | wc -l)
    echo "✓ RUNNING (${who_count} workers)"
elif pgrep -f "who_gho.py" > /dev/null; then
    echo "✓ RUNNING (sequential)"
else
    echo "○ STOPPED"
fi

echo -n "IMF IFS: "
pgrep -f "imf_ifs.py" > /dev/null && echo "✓ RUNNING" || echo "○ STOPPED"

echo -n "UNICEF: "
pgrep -f "unicef.py" > /dev/null && echo "✓ RUNNING" || echo "○ STOPPED"

echo ""

# Count output files
echo "--- OUTPUT FILES CREATED ---"
wb_count=$(ls -1 raw_data/world_bank/*.csv 2>/dev/null | wc -l)
who_count=$(ls -1 raw_data/who/*.csv 2>/dev/null | wc -l)
imf_count=$(ls -1 raw_data/imf/*.csv 2>/dev/null | wc -l)
unicef_count=$(ls -1 raw_data/unicef/*.csv 2>/dev/null | wc -l)
unesco_count=$(ls -1 raw_data/unesco/*.csv 2>/dev/null | wc -l)

echo "UNESCO:     $unesco_count / 4,553 (COMPLETE)"
echo "World Bank: $wb_count / ~29,213 (expected)"
echo "WHO GHO:    $who_count / ~3,038 (expected)"
echo "IMF IFS:    $imf_count / ~132 (expected)"
echo "UNICEF:     $unicef_count / ~133 (expected)"

total=$((wb_count + who_count + imf_count + unicef_count + unesco_count))
expected=$((29213 + 3038 + 132 + 133 + 4553))
echo ""
echo "TOTAL: $total / $expected (~$((total * 100 / expected))%)"

echo ""

# Disk usage
echo "--- DISK USAGE ---"
du -sh raw_data/* 2>/dev/null

echo ""

# Last modified files (check if still active)
echo "--- RECENT ACTIVITY (last 30 seconds) ---"
find raw_data -name "*.csv" -mmin -0.5 2>/dev/null | head -5 | while read file; do
    echo "$(date -r "$file" '+%H:%M:%S') - $(basename $file)"
done

echo ""
echo "========================================"
