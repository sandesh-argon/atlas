# Validation Logs Directory

This directory contains detailed logs of all indicators removed or flagged during A0.6 validation.

## Files Generated (After Validation)

### 1. REMOVED_INDICATORS_EMPTY.json / .csv
**Purpose**: Track all indicators removed for being empty

**Content Structure (JSON)**:
```json
{
  "timestamp": "2025-11-12T18:50:00",
  "total_count": 127,
  "by_source": {
    "world_bank": [
      {
        "source": "world_bank",
        "indicator_id": "NY.GDP.COAL.RT.CD",
        "filename": "NY.GDP.COAL.RT.CD.csv",
        "file_size_bytes": 42,
        "reason": "File size < 100 bytes"
      }
    ],
    "who": [
      {
        "source": "who",
        "indicator_id": "WHOSIS_000123",
        "filename": "WHOSIS_000123.csv",
        "file_size_bytes": 87,
        "reason": "DataFrame has 0 rows"
      }
    ]
  },
  "all_indicators": [...]
}
```

**CSV Columns**:
- `source`: Data source (world_bank, who, imf, unicef, unesco)
- `indicator_id`: Indicator code/ID
- `filename`: CSV filename
- `file_size_bytes`: File size in bytes
- `reason`: Why removed ("File size < 100 bytes" or "DataFrame has 0 rows")

---

### 2. REMOVED_INDICATORS_CORRUPTED.json / .csv
**Purpose**: Track all indicators removed for corruption/parsing errors

**Content Structure (JSON)**:
```json
{
  "timestamp": "2025-11-12T18:50:00",
  "total_count": 15,
  "by_source": {
    "imf": [
      {
        "source": "imf",
        "indicator_id": "PCPIPCH",
        "filename": "PCPIPCH.csv",
        "file_size_bytes": 4521,
        "error": "ParserError: Error tokenizing data. C error: Expected 3 fields, saw 5",
        "error_type": "ParserError"
      }
    ],
    "unicef": [
      {
        "source": "unicef",
        "indicator_id": "NUTRITION_BAD",
        "filename": "NUTRITION_BAD.csv",
        "file_size_bytes": 1234,
        "error": "UnicodeDecodeError: 'utf-8' codec can't decode byte 0xff",
        "error_type": "UnicodeDecodeError"
      }
    ]
  },
  "all_indicators": [...]
}
```

**CSV Columns**:
- `source`: Data source
- `indicator_id`: Indicator code/ID
- `filename`: CSV filename
- `file_size_bytes`: File size in bytes
- `error`: Full error message
- `error_type`: Python exception type

**Common Error Types**:
- `ParserError`: Malformed CSV (inconsistent columns)
- `UnicodeDecodeError`: Encoding issues
- `EmptyDataError`: File exists but no data
- `PermissionError`: File permission issues

---

### 3. INDICATORS_INVALID_YEARS.json
**Purpose**: Flag indicators with data outside 1960-2024 (NOT removed, just flagged)

**Content Structure**:
```json
{
  "timestamp": "2025-11-12T18:50:00",
  "total_count": 43,
  "note": "These indicators have some data outside 1960-2024 range but may still be usable",
  "by_source": {
    "world_bank": [
      {
        "source": "world_bank",
        "indicator_id": "SP.POP.TOTL",
        "filename": "SP.POP.TOTL.csv",
        "invalid_year_count": 3,
        "sample_years": [1950, 1955, 1957, 1960, 1965]
      }
    ]
  },
  "all_indicators": [...]
}
```

**Note**: These indicators are **flagged but NOT removed**. They may contain useful data (e.g., historical data before 1960). Final filtering happens in A0.16-A0.18.

---

## Usage Examples

### View Empty Indicators in Excel/Google Sheets
```bash
# Open CSV in spreadsheet
libreoffice validation_logs/REMOVED_INDICATORS_EMPTY.csv
# or
open validation_logs/REMOVED_INDICATORS_EMPTY.csv
```

### Query Specific Source Issues (JSON)
```bash
# Count empty indicators by source
cat REMOVED_INDICATORS_EMPTY.json | jq '.by_source | keys[] as $k | "\($k): \(.[$k] | length)"'

# Get all World Bank empty indicators
cat REMOVED_INDICATORS_EMPTY.json | jq '.by_source.world_bank[] | .indicator_id'

# Find all ParserError corruptions
cat REMOVED_INDICATORS_CORRUPTED.json | jq '.all_indicators[] | select(.error_type == "ParserError")'
```

### Count Total Removed
```bash
# Empty + Corrupted = Total removed
EMPTY=$(cat REMOVED_INDICATORS_EMPTY.json | jq '.total_count')
CORRUPTED=$(cat REMOVED_INDICATORS_CORRUPTED.json | jq '.total_count')
echo "Total removed: $((EMPTY + CORRUPTED))"
```

---

## Why This Matters

### Audit Trail
- **Research integrity**: Document every removal decision
- **Reproducibility**: Other researchers can verify our filtering
- **Debugging**: Identify API issues or scraper bugs

### Quality Control
- **Pattern detection**: Are certain sources more problematic?
- **API monitoring**: Did a source change their format?
- **Re-scraping**: Know exactly which indicators to retry

### Phase A1 Integration
- **Missingness analysis**: Empty indicators inform missingness strategy
- **Source reliability**: Factor into source weighting
- **Coverage optimization**: Guide Part 2 scraper prioritization

---

## Expected Ranges (from V1 experience)

Based on V1 extraction, expect:
- **Empty indicators**: 50-150 (1-3% of total)
  - IMF IFS: ~370 empty expected (50% of 743 indicators)
  - Others: <50 each
- **Corrupted indicators**: <20 (0.05% of total)
  - Usually encoding issues or API format changes
- **Invalid years**: 30-80 (flagged, not removed)
  - Historical data (pre-1960) common in World Bank

**Thresholds**:
- ✅ GOOD: <100 empty, <10 corrupted
- ⚠️ REVIEW: 100-200 empty, 10-50 corrupted
- ❌ CRITICAL: >200 empty, >50 corrupted (investigate before Part 2)

---

## Retention Policy

These logs are **permanent artifacts** for the research paper:
- Include in supplementary materials
- Reference in methodology section
- Archive with final dataset

Do NOT delete these files. They document data provenance.

---

**Directory Status**: 📁 Ready to receive validation logs (will be created during validation)
