# A0.6 Validation Quick Reference

## When World Bank Extraction Completes

### Step 1: Run Validation
```bash
cd <repo-root>/v2.0/phaseA/A0_data_acquisition
python validate_a06_extraction.py
```

### Step 2: Review Output

The script will display 5 validation sections:

1. **Output Structure Validation**
   - Confirms all 5 data source directories exist
   - Counts CSV files per source
   - Checks for extraction logs

2. **CSV Format Validation**
   - Samples 10 files per source
   - Verifies standard columns (Country, Year, Value)
   - Reports any formatting issues

3. **Coverage Verification**
   - Shows indicator counts vs expected
   - Estimates total row counts
   - Calculates completion percentages

4. **Data Integrity Checks**
   - Scans all files for empty/corrupted data
   - Validates year ranges (1960-2024)
   - Lists any problematic files

5. **Readiness for Part 2**
   - Tests pandas load capability
   - Assesses readiness for new scrapers
   - Provides go/no-go decision

### Step 3: Check Final Status

Look for the final report section:

```
✅ PASSED = Ready to proceed to Part 2 (write 6 new scrapers)
⚠️ NEEDS REVIEW = Minor issues to investigate first
❌ FAILED = Critical issues, must fix before Part 2
```

### Step 4: Review JSON Report

Check the detailed report:
```bash
cat A06_VALIDATION_REPORT.json | jq .
```

## Expected Results (if all goes well)

```
Overall Status:                ✅ PASSED
Total Indicators:              35,216+ / 37,069 (≥95%)
Estimated Total Rows:          ~6,000,000+
Files Checked:                 ~37,000
Empty Files:                   <50
Corrupted Files:               <10
```

## Next Steps After ✅ PASSED

Proceed to **Part 2: New Scrapers (A0.7-A0.14)**

Write 6 new data acquisition scripts:
1. **A0.7**: V-Dem (Varieties of Democracy) - ~450 indicators
2. **A0.8**: QoG Institute - ~2,000 indicators
3. **A0.9**: OECD.Stat - ~1,200 indicators
4. **A0.10**: Penn World Tables - ~180 indicators
5. **A0.11**: World Inequality Database - ~150 indicators
6. **A0.12**: Transparency International - ~30 indicators

**Target**: Add 4,010 indicators to reach 5,000-6,000 total (exceeds A0 requirements)

## Troubleshooting

### If validation shows < 95% indicators:
```bash
# Check which scrapers had issues
ls -lh raw_data/*/
# Re-run failed scrapers if needed
```

### If too many corrupted files (>10):
```bash
# List corrupted files
cat A06_VALIDATION_REPORT.json | jq '.integrity.corrupted_files'
# Investigate specific source
```

### If pandas load fails:
```bash
# Test manual load
python -c "import pandas as pd; df = pd.read_csv('raw_data/world_bank/SP.POP.TOTL.csv'); print(df.head())"
```

## Critical Questions for Claude Code (Post-Validation)

After running validation, ask Claude Code:

> "Claude Code: A0.6 validation complete. Report shows:
> - [X] indicators collected ([Y]% of expected)
> - [Z] corrupted files
> - Pandas load: [PASS/FAIL]
> - Overall status: [PASSED/NEEDS REVIEW/FAILED]
>
> Questions:
> 1. Are we ready to proceed to Part 2 (6 new scrapers)?
> 2. Any issues that need addressing first?
> 3. What's the priority order for the 6 new scrapers?"

## Files Generated

After validation completes, you'll have:

### Main Reports
- `A06_VALIDATION_REPORT.json` - Full structured report with all metrics
- Console output with color-coded status indicators

### Detailed Removal Logs (validation_logs/)
**All removed/problematic indicators are logged for tracking:**

1. **REMOVED_INDICATORS_EMPTY.json** / **.csv**
   - All indicators with empty files (<100 bytes or 0 rows)
   - Includes: source, indicator_id, filename, file_size, reason
   - Organized by source for easy review

2. **REMOVED_INDICATORS_CORRUPTED.json** / **.csv**
   - All indicators with corrupted/unreadable files
   - Includes: source, indicator_id, filename, error message, error type
   - Helps identify API/parsing issues

3. **INDICATORS_INVALID_YEARS.json**
   - Indicators with data outside 1960-2024 range
   - **Note**: These are flagged but NOT removed (may still be usable)
   - Includes: sample years, count of invalid records

### Format Options
- **JSON files**: Full details with nested structure, error messages
- **CSV files**: Easy to open in Excel/Google Sheets for review

---

**Current Status**: ⏸️ READY - Validation script prepared, waiting for extraction to complete
