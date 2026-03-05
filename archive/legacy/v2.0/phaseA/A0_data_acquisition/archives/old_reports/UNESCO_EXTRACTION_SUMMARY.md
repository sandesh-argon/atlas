# UNESCO UIS Bulk Data Extraction Summary

**Date**: November 12, 2025
**Status**: ✅ COMPLETE - All 6 Datasets Processed
**Total Time**: ~8 minutes

---

## Quick Summary

**Extracted**: 4,553 indicators from 6 UNESCO datasets
**Total Rows**: 5,807,836
**Success Rate**: 100%
**Method**: BDDS CSV processing (not API)

---

## Dataset Breakdown

| Dataset | Description | Indicators | Rows | Size |
|---------|-------------|-----------|------|------|
| **SDG** | Education SDG indicators | 2,464 | 1,372,566 | Primary education data |
| **OPRI** | Other Policy-Relevant Indicators | 2,034 | 4,097,900 | Additional education/social |
| **DEM** | Demography | 35 | 320,056 | Population data |
| **SDG11** | SDG 11 (Cities/Communities) | 8 | 966 | Urban indicators |
| **SCN-SDG** | Sub-national SDG | 2 | 4,255 | Regional SDG data |
| **SCN-OPRI** | Sub-national OPRI | 10 | 12,093 | Regional OPRI data |
| **TOTAL** | **All 6 datasets** | **4,553** | **5,807,836** | **~150MB** |

---

## Comparison to Original Report

**Initial Processing** (SDG + OPRI only):
- Indicators: 4,498
- Rows: 5,470,466

**Final Processing** (All 6 datasets):
- Indicators: **4,553** (+55 additional)
- Rows: **5,807,836** (+337K rows)

**Additional Datasets Added**:
- DEM: +35 demography indicators
- SDG11: +8 urban indicators  
- SCN-SDG: +2 sub-national SDG
- SCN-OPRI: +10 sub-national OPRI

---

## Files & Organization

**Source Data**: `unesco_bulk_source/` (ZIP files preserved)
**Processed Output**: `raw_data/unesco/` (4,553 CSV files)
**Logs**: `extraction_logs/unesco_bdds_log.json`
**Parser Code**: `unesco_bdds_parser.py`

---

## Key Statistics

- **Coverage**: 241 countries
- **Domains**: Education, demography, urban development, policy
- **Format**: Standard (Country, Year, Value) - matches other scrapers
- **Quality**: 100% success rate, 0 errors

---

**Extraction Complete**: November 12, 2025
**Next Step**: Ready for full extraction with other 4 scrapers
