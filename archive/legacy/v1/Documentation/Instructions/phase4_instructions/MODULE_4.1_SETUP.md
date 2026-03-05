# MODULE 4.1: Environment Setup & Data Loading

## OBJECTIVE
Install causal discovery libraries, load Phase 3 optimized models and SHAP values, verify data integrity, and establish metric prioritization tiers for incremental execution.

## CONTEXT
Phase 4 requires specialized causal discovery libraries (causal-learn, pgmpy) not installed in the Phase 2/3 environment. This module establishes the computational environment and loads all Phase 3 artifacts as inputs for causal structure learning. Metric prioritization (Tier 1: high R², Tier 2: medium R², Tier 3: low R²) enables iterative validation—start with high-confidence metrics to validate methodology before extending to all 8 metrics.

## INPUTS

### Phase 3 Model Artifacts
- **Optimized Models**: `<repo-root>/v1.0/models/causal_optimized/model_lightgbm_{metric}.txt` (8 files)
- **SHAP Importance**: `<repo-root>/v1.0/models/causal_optimized/shap_importance_{metric}.csv` (8 files)
- **Feature Importance**: `<repo-root>/v1.0/models/causal_optimized/feature_importance_lightgbm_{metric}.csv` (8 files)
- **Model Metadata**: `<repo-root>/v1.0/models/causal_optimized/model_metadata_master.json`

### Training Data
- **Normalized Training Set**: `<repo-root>/v1.0/Data/Processed/normalized/train_normalized.csv` (7,200 rows × 12,426 cols)
- **Feature Selection Metadata**: `<repo-root>/v1.0/Data/Processed/feature_selection/phase3/features_causal_{metric}.csv` (8 files)

## TASK DIRECTIVE

### Step 1: Install Causal Discovery Libraries

Activate the Phase 2 environment and install required packages:

```bash
source <repo-root>/v1.0/phase2_env/bin/activate

# Causal discovery core libraries
pip install causal-learn==0.1.3.5      # PC, FCI, GES algorithms
pip install pgmpy==0.1.23              # Bayesian networks, do-calculus
pip install networkx==3.2              # Graph operations
pip install graphviz==0.20.1           # DAG visualization
pip install pydot==2.0.0               # Graphviz Python interface

# Statistical testing for causal discovery
pip install statsmodels==0.14.1        # Granger causality, VAR models
```

**Validation**: Verify imports work without errors:
```python
from causallearn.search.ConstraintBased.PC import pc
from causallearn.utils.cit import fisherz
from pgmpy.models import SEM, BayesianNetwork
from pgmpy.inference import CausalInference
import networkx as nx
import graphviz
```

### Step 2: Create Output Directory Structure

```bash
mkdir -p <repo-root>/v1.0/models/causal_graphs/{tier1,tier2,tier3,visualizations}
mkdir -p <repo-root>/v1.0/models/policy_simulator
mkdir -p <repo-root>/v1.0/Data/Processed/causal_discovery
```

### Step 3: Load Phase 3 Outputs

**Script**: `phase4_setup.py`

Create a setup script that:
1. Loads all 8 LightGBM models from Phase 3
2. Loads SHAP importance values for each metric
3. Loads feature lists (Approach C - strict causal features)
4. Loads training data with only causal features per metric
5. Validates data integrity (no NaN in target variables, expected feature counts)

**Key Data Structures**:
```python
# Global dictionaries to be used across all modules
models = {}          # {metric: lightgbm.Booster}
shap_importance = {} # {metric: DataFrame[feature, shap_value]}
feature_sets = {}    # {metric: List[str]}
training_data = {}   # {metric: DataFrame[features + target]}

# Tier classification (from Phase 3 test results)
TIER1_METRICS = ['mean_years_schooling', 'infant_mortality', 'undernourishment']
TIER2_METRICS = ['internet_users', 'gini', 'gdp_per_capita']
TIER3_METRICS = ['life_expectancy', 'homicide']
```

### Step 4: Validate Data Integrity

For each metric, verify:
- ✓ Model file exists and loads without error
- ✓ SHAP importance has matching feature count
- ✓ Feature list matches model's expected features
- ✓ Training data has no NaN in target variable
- ✓ Training data has expected shape (7,200 rows after dropna)
- ✓ Feature counts match Phase 3 expectations (23-52 per metric)

**Expected Feature Counts** (from Phase 3):
```
mean_years_schooling: 38 features
infant_mortality: 42 features
undernourishment: 40 features
internet_users: 47 features
gini: 23 features
gdp_per_capita: 31 features
life_expectancy: 52 features
homicide: 43 features
```

### Step 5: Create Phase 4 Configuration File

**Output**: `<repo-root>/v1.0/models/causal_graphs/phase4_config.json`

```json
{
  "phase4_version": "1.0",
  "created_date": "2025-10-23",
  "tier1_metrics": ["mean_years_schooling", "infant_mortality", "undernourishment"],
  "tier2_metrics": ["internet_users", "gini", "gdp_per_capita"],
  "tier3_metrics": ["life_expectancy", "homicide"],
  "pc_algorithm_config": {
    "alpha": 0.05,
    "indep_test": "fisherz",
    "stable": true,
    "uc_rule": 0
  },
  "vif_threshold": 10,
  "bootstrap_iterations": 1000,
  "random_seed": 42
}
```

## OUTPUTS

### Primary Outputs
1. **Setup Verification Report**: `<repo-root>/v1.0/models/causal_graphs/setup_verification.json`
   - Library versions installed
   - Model load status (8/8 successful)
   - Feature count validation
   - Data integrity checks

2. **Configuration File**: `<repo-root>/v1.0/models/causal_graphs/phase4_config.json`

3. **Loaded Data Artifacts**: Pickled data structures for downstream modules
   - `<repo-root>/v1.0/models/causal_graphs/loaded_models.pkl`
   - `<repo-root>/v1.0/models/causal_graphs/loaded_shap_importance.pkl`
   - `<repo-root>/v1.0/models/causal_graphs/loaded_training_data.pkl`

### Success Criteria
- [ ] All 5 causal discovery libraries install without dependency conflicts
- [ ] All 8 LightGBM models load successfully
- [ ] All 8 SHAP importance files load with expected feature counts
- [ ] Training data for all 8 metrics has 0 NaN in target variables
- [ ] Feature counts match Phase 3 metadata (23-52 per metric)
- [ ] Tier classification complete (3 Tier 1, 3 Tier 2, 2 Tier 3)
- [ ] Configuration file created with default parameters
- [ ] Output directory structure created

## INTEGRATION NOTES

### Handoff to Module 4.2
- Loaded data structures (models, SHAP, training_data) are serialized and ready for PC algorithm execution
- Tier 1 metrics identified for initial causal discovery
- Configuration parameters (alpha=0.05) established for PC algorithm

### Error Handling
- **Library installation conflicts**: Use `pip install --no-deps` if dependency version conflicts arise
- **Model load failures**: Verify LightGBM version matches Phase 3 (4.5.x)
- **Missing SHAP files**: Re-run Phase 3 SHAP extraction if files missing
- **Data integrity issues**: If dropna reduces samples below 5,000, flag for investigation

## VERIFICATION COMMANDS

After running setup, verify success:

```bash
# Check directory structure
ls -l <repo-root>/v1.0/models/causal_graphs/

# Verify setup report
cat <repo-root>/v1.0/models/causal_graphs/setup_verification.json

# Check loaded data sizes
python3 -c "
import pickle
with open('<repo-root>/v1.0/models/causal_graphs/loaded_training_data.pkl', 'rb') as f:
    data = pickle.load(f)
    for metric, df in data.items():
        print(f'{metric}: {df.shape}')
"
```

## SCRIPT TEMPLATE

**File**: `<repo-root>/v1.0/Data/Scripts/phase4_modules/phase4_setup.py`

Key functions to implement:
- `install_libraries()` - Run pip install commands
- `load_lightgbm_models()` - Load all 8 models
- `load_shap_importance()` - Load SHAP values
- `load_feature_sets()` - Load causal feature lists
- `load_training_data()` - Load normalized training data
- `validate_data_integrity()` - Run integrity checks
- `create_config_file()` - Generate phase4_config.json
- `serialize_loaded_data()` - Pickle data for downstream modules

## ESTIMATED RUNTIME
**5 minutes** (2 min library install, 3 min data loading/validation)

## DEPENDENCIES
- None (entry point module)

## PRIORITY
**HIGH** - Blocking all downstream modules
