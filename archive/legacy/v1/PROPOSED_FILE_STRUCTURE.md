# PROPOSED FILE STRUCTURE
## Organized by Workflow Phases (Data → Models → Visualizations → Deliverables)

```
Global_Project/v1.0/
│
├── README.md                          # Project overview
├── CLAUDE.md                          # AI assistant guidance (current)
├── WORKFLOW_PLAN.md                   # Your comprehensive 10-phase plan
├── requirements.txt                   # Python dependencies
├── .gitignore
│
├── Documentation/                     # 📚 All documentation
│   ├── framework/
│   │   └── Global_Progress_Heylighen_Bernheim.md
│   ├── data_sources/
│   │   ├── world_bank_api.md
│   │   ├── unesco_uis_api.md
│   │   ├── who_api.md
│   │   ├── imf_api.md
│   │   └── unicef_api.md
│   ├── qol_metrics/
│   │   ├── qol_metrics_final_recommendation.md  # Move from Data/
│   │   └── qol_metrics_justification.md
│   └── methodology/
│       ├── feature_selection_methodology.md
│       ├── model_architecture.md
│       └── validation_strategy.md
│
├── Indicators/                        # 🔖 KEEP AS IS (metadata)
│   ├── world_bank_indicators.csv
│   ├── UISIndicators.csv
│   ├── WHO Global Health Observatory (GHO).csv
│   ├── IMFIndicators.csv
│   ├── unicef_indicators_list.csv
│   ├── HumanDevReportIndicators.csv
│   └── scrapers/
│       └── (existing scraper scripts)
│
├── Data/                              # 📊 DATA PIPELINE (PHASES 0-1)
│   │
│   ├── Extraction_Scripts/            # 🔄 PHASE 0: DATA EXTRACTION ✅ COMPLETE
│   │   ├── WorldBank.py               # ~1,800 indicators, 4-6h runtime
│   │   ├── WHO.py                     # ~180 indicators, 30-60min
│   │   ├── UIS.py                     # ~455 indicators, 1-2h
│   │   ├── IMF.py                     # ~56 indicators, 15-30min
│   │   ├── UNICEF.py                  # ~21 indicators, 30-60min
│   │   ├── fetch_mean_years_schooling.py  # Special: OWID MYS extraction
│   │   └── process_mean_years_schooling.py  # ISO3 mapping
│   │
│   ├── Raw_Data/                      # 📦 PHASE 0: RAW API DATA ✅ COMPLETE
│   │   ├── World_Bank_Data/           # 2,526 CSV files (one per indicator)
│   │   ├── UIS_Data/                  # Standardized format: [Country, Year, Value]
│   │   ├── WHO_Data/
│   │   ├── IMF_Data/
│   │   ├── UNICEF_Data/
│   │   └── External_Data/
│   │       ├── SWIID/                 # Gini coefficient (v9.9)
│   │       └── FAO/                   # Undernourishment data
│   │
│   ├── filtered_data/                 # 🔍 PHASE 0: COVERAGE FILTERING ✅ COMPLETE
│   │   ├── criteria.md                # ≥100 countries, ≥20 years, 1990-2023 window
│   │   ├── World_Bank_Data/           # 2,517 files passed filtering (99.6%)
│   │   ├── UIS_Data/                  # 1,797 World Bank indicators retained
│   │   ├── WHO_Data/
│   │   ├── IMF_Data/
│   │   ├── UNICEF_Data/
│   │   └── QOL_Metrics/               # 8 target variables (selected via framework)
│   │       ├── legend.md
│   │       ├── SP.DYN.LE00.IN.csv         # Life Expectancy
│   │       ├── MYS.1T8.AG25T99.csv        # Mean Years Schooling
│   │       ├── NY.GDP.PCAP.PP.KD.csv      # GDP per Capita PPP
│   │       ├── SP.DYN.IMRT.IN.csv         # Infant Mortality
│   │       ├── SI.POV.GINI.csv            # Gini (replaced with SWIID)
│   │       ├── VC.IHR.PSRC.P5.csv         # Homicide Rate
│   │       ├── SN.ITK.DEFC.ZS.csv         # Undernourishment
│   │       └── IT.NET.USER.ZS.csv         # Internet Users
│   │
│   ├── filtered_data_cleaned/         # 🧹 PHASE 0: DATA CLEANING ✅ COMPLETE
│   │   ├── World_Bank_Data/           # Standardized schema, duplicates removed
│   │   ├── UIS_Data/                  # Missing values encoded as NaN
│   │   ├── WHO_Data/                  # Zero-variance files excluded (2)
│   │   ├── IMF_Data/                  # Success rate: 99.6% (2,517/2,526)
│   │   ├── UNICEF_Data/
│   │   └── cleaning_report_*.md       # Per-source cleaning summaries
│   │
│   ├── Processed/qol_imputed/         # 💉 PHASE 0: QOL IMPUTATION ✅ COMPLETE
│   │   ├── master_panel_imputed_wide.csv      # 11,310 rows × 18 cols (174 countries × 65 years)
│   │   ├── master_panel_imputed_long.csv      # 90,480 rows (8 metrics stacked)
│   │   ├── imputation_mask.csv                # Binary flags: 0=observed, 1=imputed
│   │   ├── imputation_quality_report.json     # Per-metric validation, correlations
│   │   └── IMPUTATION_SUMMARY.md              # 99.81% completeness, tiered methods
│   │
│   ├── Processed/imputation_inputs/   # 🎯 PHASE 0: ORCHESTRATOR SETUP
│   │   ├── master_panel.csv           # Unified 174-country panel
│   │   ├── country_list.csv           # Countries meeting ≥40% coverage
│   │   └── auxiliary_*.csv (×8)       # Top 15 correlated variables per metric
│   │
│   ├── Processed/imputation_outputs/  # 📊 PHASE 0: AGENT OUTPUTS
│   │   ├── life_expectancy_imputed.csv        # Tier 1: Cubic spline (2.1% missing)
│   │   ├── infant_mortality_imputed.csv       # Tier 2: MICE (23.5%)
│   │   ├── gdp_per_capita_imputed.csv         # Tier 3: Time-series + MICE (51.1%)
│   │   ├── internet_users_imputed.csv         # Tier 3: (61.0%)
│   │   ├── gini_imputed.csv                   # Tier 4: K-NN (51.7% via SWIID)
│   │   ├── homicide_imputed.csv               # Tier 4: K-NN (74.4%)
│   │   ├── undernourishment_imputed.csv       # Tier 4: MICE (72.2%)
│   │   └── mean_years_schooling_imputed.csv   # Special: Real + K-NN (86.9%)
│   │
│   ├── Processed/master_dataset/      # 🔗 PHASE 1: VARIABLE INTEGRATION ✅ COMPLETE
│   │   ├── master_panel_full.csv              # 11,310 rows × 2,498 cols (137 MB)
│   │   │                                      # Combined: 8 QOL + 8 flags + 2,480 causal variables
│   │   ├── master_panel_with_lags.csv         # 10,440 rows × 12,418 cols (647 MB)
│   │   │                                      # After lag creation: 2,480 base × 4 lags = 9,920 new features
│   │   └── variable_loading_log.json          # 2,480 merged, 24 duplicates, 5 failed
│   │
│   ├── Processed/train_test_split/    # 🎲 PHASE 1: COUNTRY-AGNOSTIC SPLIT ✅ COMPLETE
│   │   ├── train_raw.csv                      # 120 countries (69.0%), 7,200 rows
│   │   ├── val_raw.csv                        # 26 countries (14.9%), 1,560 rows
│   │   ├── test_raw.csv                       # 28 countries (16.1%), 1,680 rows
│   │   ├── train_saturated.csv                # After saturation transforms (Step 1.8)
│   │   ├── val_saturated.csv
│   │   ├── test_saturated.csv
│   │   ├── train_countries.csv                # Metadata: region, income level
│   │   ├── val_countries.csv
│   │   ├── test_countries.csv
│   │   └── train_test_split_report.json       # Stratification stats, distribution checks
│   │
│   ├── Processed/normalized/          # 🎯 PHASE 1: ML-READY DATASETS ✅ COMPLETE ⭐ USE THESE
│   │   ├── train_normalized.csv               # 7,200 rows × 12,426 cols (697 MB)
│   │   ├── val_normalized.csv                 # 1,560 rows × 12,426 cols (143 MB)
│   │   ├── test_normalized.csv                # 1,680 rows × 12,426 cols (158 MB)
│   │   │                                      # Features: 12,418 core + 3 temporal + 5 interactions
│   │   │                                      # Normalization: Within-country z-score + min-max
│   │   │                                      # Saturation: Applied to 5 deficiency needs (H&B 2000)
│   │   ├── normalization_params.json          # Mean/std per country (train only)
│   │   ├── normalization_quality_report.json  # QOL targets: 100% perfect
│   │   └── NORMALIZATION_QUALITY_ANALYSIS.md  # Detailed quality assessment
│   │
│   ├── Processed/temporal_features/   # ⏰ PHASE 1: DELTA FEATURES (OPTIONAL)
│   │   ├── train_with_deltas.csv              # 7,200 rows × 12,450 cols
│   │   ├── val_with_deltas.csv                # +24 features: Δ1yr, Δ3yr, Δ5yr per QOL metric
│   │   └── test_with_deltas.csv
│   │
│   ├── Processed/saturation_validation/  # 📈 PHASE 1 EXTENSION: EMPIRICAL VALIDATION
│   │   ├── gdp_per_capita_saturation_curves.png      # $20K threshold validated
│   │   ├── life_expectancy_saturation_curves.png     # 85-year ceiling (limited data)
│   │   ├── infant_mortality_saturation_curves.png    # 2/1000 threshold validated
│   │   ├── undernourishment_saturation_curves.png    # 2.5% threshold validated
│   │   ├── homicide_saturation_curves.png            # 1/100K threshold validated
│   │   ├── threshold_sensitivity_report.json         # Slope comparisons, R² values
│   │   └── interaction_validation_report.json        # 5 interactions validated
│   │
│   ├── Processed/metadata/            # 📋 PHASE 1: FEATURE DOCUMENTATION
│   │   ├── feature_registry.csv               # 12,426 features documented
│   │   ├── feature_summary.json               # Breakdown by type (base, lag, QOL, etc.)
│   │   └── country_metadata.csv               # Region, income level per country
│   │
│   ├── Processed/reports/             # 📊 PHASE 1: QUALITY REPORTS
│   │   ├── phase1_quality_report.json         # Overall pipeline quality metrics
│   │   ├── validation_test_results.json       # 8/8 tests PASSED
│   │   ├── saturation_report.json             # Threshold coverage, transform validation
│   │   └── train_test_validation_report.md    # Distribution similarity checks
│   │
│   └── Scripts/                       # 🛠️ PROCESSING SCRIPTS
│       ├── filter_data_by_coverage.py         # Phase 0: Coverage criteria filtering
│       ├── data_cleaner.py                    # Phase 0: Schema standardization
│       ├── qol_imputation_orchestrator.py     # Phase 0: Imputation setup (8 agents)
│       ├── impute_agent_*.py (×8)             # Phase 0: Parallel imputation
│       ├── integrate_imputed_metrics.py       # Phase 0: Merge imputed outputs
│       ├── combine_all_variables.py           # Phase 1: Step 0
│       ├── create_lag_features.py             # Phase 1: Step 1.1
│       ├── train_test_split.py                # Phase 1: Step 1.2
│       ├── apply_saturation_transforms.py     # Phase 1: Step 1.8 (BEFORE normalization)
│       ├── normalize_features.py              # Phase 1: Step 1.3
│       ├── create_feature_registry.py         # Phase 1: Step 1.4
│       ├── create_temporal_features.py        # Phase 1: Step 1.5 (optional deltas)
│       ├── phase1_validation_tests.py         # Phase 1: Step 1.7 (8 tests)
│       ├── add_temporal_features.py           # Phase 1 Extension: Step 1.9a
│       ├── add_interaction_features.py        # Phase 1 Extension: Step 1.9b
│       ├── validate_saturation_thresholds.py  # Phase 1 Extension: Step 1.9c
│       └── phase1_extension_validation.py     # Phase 1 Extension: 3 additional tests
│
├── Analysis/                          # 🔬 EXPLORATORY ANALYSIS
│   ├── EDA/
│   │   ├── notebooks/
│   │   │   ├── 01_data_exploration.ipynb
│   │   │   ├── 02_qol_correlations.ipynb
│   │   │   ├── 03_temporal_trends.ipynb
│   │   │   └── 04_country_clustering.ipynb
│   │   └── reports/
│   │       └── eda_summary.md
│   │
│   ├── Correlation_Analysis/
│   │   ├── pearson_correlations.csv
│   │   ├── spearman_correlations.csv
│   │   ├── mutual_information.csv
│   │   └── correlation_heatmaps/
│   │
│   └── Statistical_Tests/
│       ├── granger_causality_results.csv
│       ├── stationarity_tests.csv
│       └── normality_tests.csv
│
├── Data/Scripts/phase2_modules/       # 📐 PHASE 2 SCRIPTS ✅ COMPLETE
│   ├── README.md                      # Phase 2 execution guide
│   │
│   ├── run_module_2_0_prefiltering.py      # M2_0A: 40% coverage filter
│   ├── run_module_2_0b_coverage_filter.py  # M2_0B: 80% per-country filter
│   ├── run_module_2_1a_correlation.py      # M2_1A: Correlation analysis
│   ├── run_module_2_1b_xgboost.py          # M2_1B: XGBoost importance
│   ├── run_module_2_1c_shap.py             # M2_1C: SHAP values
│   ├── run_module_2_1d_voting.py           # M2_1D: Borda voting
│   ├── classify_features_api.py            # M2_2B: Domain classification
│   ├── run_module_2_3_thematic_selection.py # M2_3: Thematic selection
│   ├── run_module_2_4_hybrid_synthesis.py  # M2_4: Hybrid synthesis
│   ├── run_module_2_5_validation.py        # M2_5: Final validation
│   │
│   ├── run_all_m2_1a.sh               # Batch runner for correlation
│   ├── run_all_m2_1b.sh               # Batch runner for XGBoost
│   ├── run_all_m2_1c.sh               # Batch runner for SHAP
│   ├── run_all_m2_1d.sh               # Batch runner for voting
│   └── run_classification.sh          # API classification wrapper
│
├── Data/Processed/feature_selection/ # 📐 PHASE 2 OUTPUTS ✅ COMPLETE
│   │
│   ├── train_prefiltered.csv          # M2_0A: 6,311 features (40% coverage)
│   ├── train_coverage_filtered.csv    # M2_0B: 1,976 features (80% coverage)
│   ├── coverage_filter_report.json
│   │
│   ├── correlation_rankings_{metric}.csv (×8)    # M2_1A outputs
│   ├── xgboost_importance_{metric}.csv (×8)      # M2_1B outputs
│   ├── shap_rankings_{metric}.csv (×8)           # M2_1C outputs
│   ├── top_200_features_{metric}.csv (×8)        # M2_1D outputs
│   ├── correlation_analysis_summary.json
│   │
│   ├── xgboost_models/                # M2_1B: Trained models
│   │   ├── {metric}_model.pkl (×8)
│   │   └── xgboost_summary_{metric}.json (×8)
│   │
│   ├── shap_values/                   # M2_1C: SHAP value matrices
│   │   └── {metric}_shap.pkl (×8)     # 1,000 × 1,976 matrices
│   │
│   ├── feature_classifications.csv    # M2_2: All 6,311 features classified
│   ├── domain_taxonomy_validated.json # M2_2A: 18 domain definitions
│   ├── classification_summary.json
│   │
│   ├── thematic_features_{metric}.csv (×8)  # M2_3 outputs (20-50 features)
│   ├── thematic_summary_{metric}.json (×8)
│   │
│   ├── hybrid_features_{metric}.csv (×8)    # M2_4 outputs (40 features) ⭐ FINAL
│   ├── hybrid_summary_{metric}.json (×8)
│   │
│   ├── coverage_validation_{metric}.json (×8)      # M2_5A outputs
│   ├── validation_performance_{metric}.json (×8)   # M2_5B outputs
│   ├── stability_report.json                       # M2_5C output
│   └── phase2_final_summary.json                   # Overall summary
│
├── Documentation/phase_reports/       # 📚 COMPREHENSIVE PHASE DOCUMENTATION ✅
│   ├── phase0_report.md               # Phase 0: Data Acquisition & Preparation
│   │                                  # - Extraction (5 APIs, 2,526 indicators)
│   │                                  # - Filtering (≥100 countries, ≥20 years, 1990-2023)
│   │                                  # - Cleaning (99.6% success, schema standardization)
│   │                                  # - Imputation (99.81% complete, tiered methods)
│   │                                  # - Full dataset strategy (174 countries)
│   │
│   ├── phase1_report.md               # Phase 1: Temporal Engineering & Train-Test Split
│   │                                  # - Variable integration (2,480 causal + 8 QOL)
│   │                                  # - Lag features (T-1,2,3,5 → 9,920 features)
│   │                                  # - Country-agnostic split (120/26/28 countries)
│   │                                  # - Saturation transforms (5 deficiency needs, H&B 2000)
│   │                                  # - Normalization (within-country, data leakage prevention)
│   │                                  # - Phase 1 Extension (temporal + interactions + validation)
│   │                                  # - Final: 12,426 features, 8/8 validation tests passed
│   │
│   └── phase2_report.md               # Phase 2: Feature Selection (Statistical + Hybrid)
│                                      # - Version 3.0 with coverage filter success
│                                      # - M2_0B: 80% per-country temporal coverage filter
│                                      # - M2_1: Statistical selection (correlation + XGBoost + SHAP)
│                                      # - M2_2: Domain classification (18 thematic domains)
│                                      # - M2_3: Thematic selection (interpretability)
│                                      # - M2_4: Hybrid synthesis (40 features per metric)
│                                      # - M2_5: Validation (5/8 metrics passed R² > 0.55)
│                                      # - Critical fix: 5x increase in usable training data
│
├── Models/                            # 🤖 PHASES 3, 4, 5
│   ├── README.md                      # Model architecture overview
│   │
│   ├── Individual_Metrics/            # PHASE 3: 8 separate models
│   │   ├── scripts/
│   │   │   ├── train_individual_model.py
│   │   │   └── evaluate_individual_model.py
│   │   ├── life_expectancy/
│   │   │   ├── model_config.yaml
│   │   │   ├── model_weights.h5
│   │   │   ├── feature_weights.json       # Normalized importance
│   │   │   ├── training_history.csv
│   │   │   ├── performance_metrics.json   # R², RMSE, MAE
│   │   │   └── predictions/
│   │   │       ├── train_predictions.csv
│   │   │       └── test_predictions.csv
│   │   ├── mean_years_schooling/
│   │   ├── gdp_per_capita/
│   │   ├── infant_mortality/
│   │   ├── gini/
│   │   ├── homicide_rate/
│   │   ├── undernourishment/
│   │   ├── internet_users/
│   │   └── summary_individual_models.csv
│   │
│   ├── Inter_Metric_Analysis/         # PHASE 4: Relationships between metrics
│   │   ├── scripts/
│   │   │   ├── correlation_matrix.py
│   │   │   ├── granger_causality.py
│   │   │   ├── structural_equation_modeling.py
│   │   │   └── var_model.py
│   │   ├── outputs/
│   │   │   ├── metric_correlations.csv
│   │   │   ├── granger_causality_results.csv
│   │   │   ├── sem_path_coefficients.csv
│   │   │   ├── var_coefficients.csv
│   │   │   └── causal_dag.json
│   │   └── visualizations/
│   │       ├── correlation_heatmap.png
│   │       ├── causal_network.png
│   │       └── temporal_precedence.png
│   │
│   ├── Integrated_Model/              # PHASE 5: Master multi-output NN
│   │   ├── scripts/
│   │   │   ├── train_master_model.py
│   │   │   └── evaluate_master_model.py
│   │   ├── architecture/
│   │   │   ├── model_diagram.png
│   │   │   └── architecture_spec.yaml
│   │   ├── checkpoints/
│   │   │   ├── best_model.h5
│   │   │   └── epoch_*.h5
│   │   ├── weights/
│   │   │   ├── master_model_weights.h5
│   │   │   ├── attention_matrix_8x8.csv
│   │   │   ├── jacobian_sensitivity_8x8.csv
│   │   │   └── ablation_influence_8x8.csv
│   │   ├── performance/
│   │   │   ├── training_history.csv
│   │   │   ├── validation_curves.png
│   │   │   └── per_metric_performance.csv
│   │   └── predictions/
│   │       ├── train_all_metrics.csv
│   │       └── test_all_metrics.csv
│   │
│   └── Model_Exports/                 # PHASE 7: Mathematical model files
│       ├── individual_models/
│       │   ├── model_weights_life_expectancy.json
│       │   ├── model_weights_mean_years_schooling.json
│       │   └── (etc. for all 8 metrics)
│       ├── master_model/
│       │   ├── master_model_weights.pkl
│       │   ├── normalization_params.json
│       │   └── input_feature_list.txt
│       ├── relationship_matrices/
│       │   ├── causal_feature_to_metric_weights.csv
│       │   ├── inter_metric_relationships.csv
│       │   └── metric_correlations.csv
│       ├── feature_metadata.csv
│       └── predict.py                 # Prediction API script
│
├── Hierarchy/                         # 📊 PHASE 6: Deduplication & Structure
│   ├── scripts/
│   │   ├── deduplicate_features.py
│   │   ├── build_hierarchy.py
│   │   └── assign_edge_weights.py
│   ├── outputs/
│   │   ├── deduplicated_features.csv     # ~100-150 unique
│   │   ├── feature_to_metric_edges.csv
│   │   ├── metric_to_metric_edges.csv
│   │   └── hierarchical_structure.json
│   └── visualizations/
│       ├── per_metric_flowcharts/        # 8 individual hierarchies
│       │   ├── life_expectancy_hierarchy.json
│       │   ├── life_expectancy_flowchart.png
│       │   └── (etc.)
│       └── master_web/
│           ├── master_network.json
│           └── master_causal_web.html     # Interactive D3.js
│
├── Temporal_Analysis/                 # ⏰ PHASE 8: Trends over time
│   ├── scripts/
│   │   ├── relationship_stability.py
│   │   ├── regime_change_detection.py
│   │   └── epoch_analysis.py
│   ├── outputs/
│   │   ├── feature_importance_timeseries.csv
│   │   ├── structural_breaks.csv
│   │   └── epoch_models/               # Models per 5-year period
│   │       ├── 1990-1995/
│   │       ├── 1995-2000/
│   │       └── (etc.)
│   └── visualizations/
│       ├── importance_evolution.png
│       └── regime_shifts.png
│
├── Validation/                        # ✅ PHASE 9: Testing & robustness
│   ├── scripts/
│   │   ├── out_of_sample_testing.py
│   │   ├── sensitivity_analysis.py
│   │   └── counterfactual_validation.py
│   ├── outputs/
│   │   ├── test_set_results/
│   │   │   ├── per_country_errors.csv
│   │   │   ├── outlier_countries.csv
│   │   │   └── performance_by_region.csv
│   │   ├── sensitivity/
│   │   │   ├── perturbation_10pct.csv
│   │   │   ├── perturbation_20pct.csv
│   │   │   └── robustness_scores.csv
│   │   └── counterfactuals/
│   │       ├── historical_case_studies.csv
│   │       └── prediction_validation.csv
│   └── reports/
│       ├── validation_summary.md
│       └── robustness_report.md
│
├── Deliverables/                      # 📦 PHASE 10: Final outputs
│   ├── README.md                      # How to use deliverables
│   │
│   ├── Models/                        # Trained models
│   │   ├── individual_models/         # 8 models (.h5 or .pkl)
│   │   ├── master_model/              # Integrated model
│   │   ├── model_card.md              # Model documentation
│   │   └── requirements.txt
│   │
│   ├── Data/                          # Clean data exports
│   │   ├── final_dataset.parquet
│   │   ├── feature_list.csv
│   │   └── data_dictionary.md
│   │
│   ├── Visualizations/                # Ready-to-publish graphics
│   │   ├── flowcharts/                # 8 metric-specific
│   │   ├── master_web/                # Interactive network
│   │   ├── correlation_matrices/
│   │   ├── temporal_trends/
│   │   └── validation_plots/
│   │
│   ├── Reports/                       # Documentation
│   │   ├── technical_report.pdf       # Complete methodology
│   │   ├── executive_summary.pdf
│   │   ├── feature_dictionary.pdf     # All selected features
│   │   ├── api_documentation.md       # How to use predict.py
│   │   └── validation_report.pdf
│   │
│   ├── API/                           # Deployment-ready
│   │   ├── predict.py                 # Prediction API
│   │   ├── requirements.txt
│   │   ├── Dockerfile
│   │   └── example_usage.ipynb
│   │
│   └── Presentations/                 # For stakeholders
│       ├── slides.pdf
│       └── demo_notebook.ipynb
│
├── Notebooks/                         # 📓 Jupyter notebooks (working)
│   ├── 00_setup_and_overview.ipynb
│   ├── 01_phase1_data_preparation.ipynb
│   ├── 02_phase2_feature_selection.ipynb
│   ├── 03_phase3_individual_models.ipynb
│   ├── 04_phase4_inter_metric_analysis.ipynb
│   ├── 05_phase5_master_model.ipynb
│   ├── 06_phase6_hierarchy.ipynb
│   ├── 07_phase8_temporal_analysis.ipynb
│   ├── 08_phase9_validation.ipynb
│   └── 09_final_demo.ipynb
│
├── Tests/                             # 🧪 Unit tests
│   ├── test_data_processing.py
│   ├── test_feature_selection.py
│   ├── test_models.py
│   └── test_predictions.py
│
├── Config/                            # ⚙️ Configuration files
│   ├── data_config.yaml               # Data paths, parameters
│   ├── model_config.yaml              # Model architectures
│   ├── training_config.yaml           # Hyperparameters
│   └── visualization_config.yaml      # Plot settings
│
└── Logs/                              # 📝 Execution logs
    ├── data_extraction.log
    ├── training_logs/
    │   ├── life_expectancy_training.log
    │   └── (etc.)
    └── validation_logs/
```

---

## KEY ORGANIZATIONAL PRINCIPLES

### 1. **Separation of Concerns**
- **Data/** = Raw and processed data (inputs)
- **Models/** = Training, weights, predictions (processing)
- **Deliverables/** = Final publishable outputs
- **Analysis/** = Exploration and insights

### 2. **Phase-Based Structure**
Each major phase has its own directory with:
- `scripts/` - Executable code
- `outputs/` - Results
- `visualizations/` - Plots (optional)
- `README.md` - Documentation

### 3. **Per-Metric Organization**
For Phases 2-3, create subdirectories for each of 8 QOL metrics:
- life_expectancy/
- mean_years_schooling/
- gdp_per_capita/
- infant_mortality/
- gini/
- homicide_rate/
- undernourishment/
- internet_users/

### 4. **Consistent Naming**
- Scripts: `verb_noun.py` (e.g., `train_individual_model.py`)
- Outputs: `noun_adjective.csv` (e.g., `features_selected.csv`)
- Reports: `topic_report.md` (e.g., `validation_report.md`)

---

## MIGRATION PLAN (From Current → Proposed)

### Files to Move:
```bash
# 1. Move quality audit files
Data/data_quality_audit.py → Data/Scripts/
Data/quality_report_*.md → Data/filtered_data/Quality_Audits/
Data/country_coverage_*.csv → Data/filtered_data/Quality_Audits/

# 2. Move QOL recommendation files
Data/qol_metrics_recommendation.py → Data/Scripts/
Data/qol_metrics_final_recommendation.md → Documentation/qol_metrics/

# 3. Move data processing scripts
Data/filter_data_by_coverage.py → Data/Scripts/

# 4. Reorganize Phase_1
Phase_1/lagged_features/ → Data/Processed/lagged_features/
Phase_1/* (other files) → Data/Processed/
```

### Directories to Create:
```bash
mkdir -p Documentation/{framework,data_sources,qol_metrics,methodology}
mkdir -p Data/{Processed,Scripts}
mkdir -p Data/Processed/{train_test_split,lagged_features,normalized,master_dataset}
mkdir -p Data/filtered_data/Quality_Audits
mkdir -p Analysis/{EDA/{notebooks,reports},Correlation_Analysis,Statistical_Tests}
mkdir -p Feature_Selection/{01_Statistical,02_Thematic,03_Hybrid,Final_Selection}/{scripts,outputs,visualizations}
mkdir -p Models/{Individual_Metrics,Inter_Metric_Analysis,Integrated_Model,Model_Exports}
mkdir -p Hierarchy/{scripts,outputs,visualizations}
mkdir -p Temporal_Analysis/{scripts,outputs,visualizations}
mkdir -p Validation/{scripts,outputs,reports}
mkdir -p Deliverables/{Models,Data,Visualizations,Reports,API,Presentations}
mkdir -p Notebooks Tests Config Logs
```

---

## WORKFLOW THROUGH DIRECTORY STRUCTURE

```
1. Data Extraction
   Indicators/ → Data/Extraction_Scripts/ → Data/Raw_Data/

2. Data Filtering & Quality
   Data/Raw_Data/ → Data/Scripts/filter_*.py → Data/filtered_data/

3. Data Preparation (PHASE 1)
   Data/filtered_data/ → Data/Scripts/create_lag_*.py → Data/Processed/

4. Feature Selection (PHASE 2)
   Data/Processed/ → Feature_Selection/ → Feature_Selection/Final_Selection/

5. Model Training (PHASES 3-5)
   Feature_Selection/Final_Selection/ → Models/

6. Visualization (PHASE 6)
   Models/ → Hierarchy/

7. Analysis (PHASES 4, 8)
   Models/ → Temporal_Analysis/
   Models/ → Analysis/

8. Validation (PHASE 9)
   Models/ → Validation/

9. Packaging (PHASE 10)
   All sources → Deliverables/
```

---

## BENEFITS OF THIS STRUCTURE

✅ **Clear Phase Progression** - Each directory represents a workflow stage
✅ **Easy Navigation** - Find outputs by phase number
✅ **Reproducibility** - Scripts and outputs co-located
✅ **Scalability** - Easy to add new metrics or experiments
✅ **Clean Separation** - Data/Models/Deliverables distinct
✅ **Per-Metric Tracking** - Individual model outputs organized
✅ **Version Control Friendly** - Logical .gitignore boundaries

---

## RECOMMENDED .gitignore ADDITIONS

```gitignore
# Data (too large for git)
Data/Raw_Data/
Data/Processed/*/
!Data/Processed/README.md

# Model weights (too large)
Models/*/model_weights.*
Models/*/checkpoints/
*.h5
*.pk - Modify any part of this proposal?
