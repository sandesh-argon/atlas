# Models (Phases 3-5)

This directory contains all machine learning models for the Global Development Indicators project.

## Directory Structure

### Individual_Metrics/ (Phase 3)
**8 Separate Models**
- One model per QOL metric
- Each with its own:
  - Model weights and architecture
  - Feature importance rankings
  - Performance metrics (R², RMSE, MAE)
  - Training history
  - Predictions on train/test sets

Metrics:
1. Life Expectancy
2. Mean Years of Schooling
3. GDP per Capita
4. Infant Mortality
5. Gini Coefficient
6. Homicide Rate
7. Undernourishment
8. Internet Users

### Inter_Metric_Analysis/ (Phase 4)
**Relationship Analysis Between Metrics**
- Correlation matrices between QOL metrics
- Granger causality tests
- Structural equation modeling (SEM)
- Vector autoregression (VAR) models
- Causal network visualization

Outputs:
- Metric correlation matrices
- Temporal precedence relationships
- Causal DAG (Directed Acyclic Graph)
- Path coefficients

### Integrated_Model/ (Phase 5)
**Master Multi-Output Neural Network**
- Single model predicting all 8 metrics simultaneously
- Leverages inter-metric relationships
- Attention mechanisms for metric interactions
- Shared and metric-specific layers

Outputs:
- Model architecture diagrams
- Training checkpoints
- Attention matrices (8×8)
- Jacobian sensitivity analysis
- Ablation study results

### Model_Exports/ (Phase 7)
**Production-Ready Model Files**
- Serialized model weights
- Normalization parameters
- Feature lists
- Prediction API script
- Relationship matrices for visualization

## Model Development Workflow

Individual Models → Inter-Metric Analysis → Integrated Model → Export for Production
