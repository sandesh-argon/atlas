# A0 Data Acquisition

**Status**: ✅ COMPLETE
**Total Indicators**: 43,376
**Achievement**: 723% of target (6,000 indicators)

---

## Quick Reference

### Extracted Data

All extracted indicators are in standardized CSV format (Country, Year, Value):

- `raw_data/world_bank_wdi/` - 16,934 indicators (World Bank)
- `raw_data/world_bank_poverty/` - 3,055 indicators (World Bank)
- `raw_data/who_gho/` - 10,738 indicators (WHO)
- `raw_data/unesco/` - 2,229 indicators (UNESCO)
- `raw_data/imf_ifs/` - 1,082 indicators (IMF)
- `raw_data/unicef/` - 521 indicators (UNICEF)
- `raw_data/qog/` - 2,004 indicators (QoG Institute)
- `raw_data/penn/` - 48 indicators (Penn World Tables)
- `raw_data/vdem/` - 4,587 indicators (V-Dem)
- `raw_data/wid/` - 2,178 indicators (World Inequality DB)

**Total**: 43,376 indicators across ~220 countries, 1800-2024

### Documentation

- **`A0_COMPLETION_REPORT.md`** - Full completion report with statistics, validation, next steps

### Scripts

- `scripts/part1_scrapers/` - World Bank, WHO, UNESCO, IMF, UNICEF extraction scripts
- `scripts/part2_scrapers/` - QoG, Penn, V-Dem, WID extraction scripts
- `scripts/tests/` - Validation and test scripts

### Source Data

Original downloaded files:
- `source_data/wid_raw/` - World Inequality Database (814 MB zip + 423 country CSVs)
- `source_data/vdem_raw/` - V-Dem (402 MB CSV + zip)
- `source_data/penn_raw/` - Penn World Tables (Excel file)
- `source_data/ti_raw/` - Transparency International (not extracted - cross-sectional only)

### Progress Logs

- `extraction_logs/` - JSON checkpoint files for each source extraction

---

## Key Statistics

| Metric | Value |
|--------|-------|
| **Total Indicators** | 43,376 |
| **Countries Covered** | ~220 |
| **Temporal Span** | 1800-2024 (224 years) |
| **Data Sources** | 9 (World Bank, WHO, UNESCO, IMF, UNICEF, QoG, Penn, V-Dem, WID) |
| **Success Rate** | 99.8% |
| **Disk Usage** | 14.3 GB |

---

## Domain Coverage

✅ Economic (World Bank, IMF, Penn, WID)
✅ Health (WHO, UNICEF)
✅ Education (UNESCO, QoG)
✅ Democracy (V-Dem, QoG)
✅ Governance (QoG, V-Dem)
✅ Corruption (QoG, V-Dem)
✅ Rule of Law (QoG, V-Dem)
✅ Civil Liberties (V-Dem)
✅ Inequality (WID)
✅ Productivity (Penn)

---

## Next Steps

1. **A0.15**: Merge all datasets into master file
2. **A0.16-A0.18**: Apply filters (coverage, temporal, missingness)
3. **Phase A1**: Missingness sensitivity analysis

---

For complete details, see `A0_COMPLETION_REPORT.md`
