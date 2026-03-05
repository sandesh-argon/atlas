#!/usr/bin/env python
"""
Phase E.2: Backtest Framework

Core framework for validating simulations against historical outcomes.

The validation approach:
1. Take a known historical change (intervention) at time t
2. Get baseline values at t-1
3. Run simulation with the observed change magnitude
4. Compare predicted downstream effects to actual outcomes at t+lag
5. Calculate correlation metrics
"""

import json
import sys
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from scipy import stats

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / 'scripts' / 'phaseB' / 'B3_simulation'))
sys.path.insert(0, str(PROJECT_ROOT / 'scripts' / 'phaseC' / 'C2_temporal_simulation'))

DATA_DIR = PROJECT_ROOT / "data"
GRAPHS_DIR = DATA_DIR / "country_graphs"
PANEL_PATH = DATA_DIR / "raw" / "v21_panel_data_for_v3.parquet"


@dataclass
class BacktestResult:
    """Result of a single backtest."""
    case_id: str
    country: str
    indicator: str
    intervention_year: int
    change_percent: float

    # Prediction accuracy
    n_indicators_compared: int
    r_squared: float
    pearson_r: float
    mae: float
    rmse: float

    # Details
    predicted_changes: Dict[str, float]
    actual_changes: Dict[str, float]
    success: bool
    error_message: Optional[str] = None


class BacktestFramework:
    """Framework for running historical validation backtests."""

    def __init__(self):
        self._panel_df: Optional[pd.DataFrame] = None
        self._simulation_runner = None
        self._temporal_runner = None

    def _load_panel(self) -> pd.DataFrame:
        """Load panel data."""
        if self._panel_df is None:
            self._panel_df = pd.read_parquet(PANEL_PATH)
        return self._panel_df

    def _get_simulation_runner(self):
        """Lazy load simulation module."""
        if self._simulation_runner is None:
            from simulation_runner import run_simulation
            self._simulation_runner = run_simulation
        return self._simulation_runner

    def _get_temporal_runner(self):
        """Lazy load temporal simulation module."""
        if self._temporal_runner is None:
            from temporal_simulation import run_temporal_simulation
            self._temporal_runner = run_temporal_simulation
        return self._temporal_runner

    def get_indicator_values(
        self,
        country: str,
        year: int,
        indicators: Optional[List[str]] = None
    ) -> Dict[str, float]:
        """Get indicator values for a country-year."""
        df = self._load_panel()
        data = df[(df['country'] == country) & (df['year'] == year)]

        if indicators:
            data = data[data['indicator_id'].isin(indicators)]

        return dict(zip(data['indicator_id'], data['value']))

    def get_downstream_indicators(self, country: str, source_indicator: str) -> List[str]:
        """Get indicators that are downstream of source in the causal graph."""
        graph_path = GRAPHS_DIR / f"{country}.json"
        if not graph_path.exists():
            return []

        with open(graph_path) as f:
            graph = json.load(f)

        # Find direct downstream targets
        downstream = set()
        for edge in graph.get('edges', []):
            if edge.get('source') == source_indicator:
                downstream.add(edge.get('target'))

        # Also add 2-hop downstream
        for edge in graph.get('edges', []):
            if edge.get('source') in downstream:
                downstream.add(edge.get('target'))

        downstream.discard(source_indicator)
        return list(downstream)

    def run_backtest(
        self,
        country: str,
        indicator: str,
        intervention_year: int,
        observed_change_percent: float,
        validation_lag: int = 3
    ) -> BacktestResult:
        """
        Run a single backtest.

        Args:
            country: Country code
            indicator: Indicator that changed (intervention)
            intervention_year: Year of the intervention
            observed_change_percent: Actual percent change observed
            validation_lag: Years after intervention to compare

        Returns:
            BacktestResult with accuracy metrics
        """
        case_id = f"{country}_{indicator}_{intervention_year}"

        try:
            # 1. Get baseline values (year before intervention)
            baseline_year = intervention_year - 1
            baseline = self.get_indicator_values(country, baseline_year)

            if not baseline:
                return BacktestResult(
                    case_id=case_id, country=country, indicator=indicator,
                    intervention_year=intervention_year,
                    change_percent=observed_change_percent,
                    n_indicators_compared=0, r_squared=0, pearson_r=0,
                    mae=0, rmse=0, predicted_changes={}, actual_changes={},
                    success=False, error_message="No baseline data"
                )

            # 2. Get actual outcome values (intervention_year + lag)
            outcome_year = intervention_year + validation_lag
            actual_outcome = self.get_indicator_values(country, outcome_year)

            if not actual_outcome:
                return BacktestResult(
                    case_id=case_id, country=country, indicator=indicator,
                    intervention_year=intervention_year,
                    change_percent=observed_change_percent,
                    n_indicators_compared=0, r_squared=0, pearson_r=0,
                    mae=0, rmse=0, predicted_changes={}, actual_changes={},
                    success=False, error_message="No outcome data"
                )

            # 3. Run temporal simulation
            run_temporal = self._get_temporal_runner()
            sim_result = run_temporal(
                country_code=country,
                interventions=[{
                    'indicator': indicator,
                    'change_percent': observed_change_percent
                }],
                horizon_years=validation_lag,
                graphs_dir=str(GRAPHS_DIR),
                panel_path=str(PANEL_PATH),
                base_year=baseline_year
            )

            if sim_result.get('status') != 'success':
                return BacktestResult(
                    case_id=case_id, country=country, indicator=indicator,
                    intervention_year=intervention_year,
                    change_percent=observed_change_percent,
                    n_indicators_compared=0, r_squared=0, pearson_r=0,
                    mae=0, rmse=0, predicted_changes={}, actual_changes={},
                    success=False, error_message=sim_result.get('message', 'Simulation failed')
                )

            # 4. Get predicted values at outcome year
            timeline = sim_result.get('timeline', {})
            predicted_values = timeline.get(str(validation_lag), timeline.get(validation_lag, {}))

            # 5. Calculate actual vs predicted changes
            predicted_changes = {}
            actual_changes = {}

            # Get downstream indicators to compare
            downstream = self.get_downstream_indicators(country, indicator)

            for ind in downstream:
                if ind in baseline and ind in actual_outcome and ind in predicted_values:
                    base_val = baseline[ind]
                    if base_val != 0:
                        actual_pct = ((actual_outcome[ind] - base_val) / abs(base_val)) * 100
                        pred_pct = ((predicted_values[ind] - base_val) / abs(base_val)) * 100

                        actual_changes[ind] = actual_pct
                        predicted_changes[ind] = pred_pct

            # 6. Calculate accuracy metrics
            if len(predicted_changes) < 3:
                return BacktestResult(
                    case_id=case_id, country=country, indicator=indicator,
                    intervention_year=intervention_year,
                    change_percent=observed_change_percent,
                    n_indicators_compared=len(predicted_changes),
                    r_squared=0, pearson_r=0, mae=0, rmse=0,
                    predicted_changes=predicted_changes,
                    actual_changes=actual_changes,
                    success=False, error_message="Insufficient comparable indicators"
                )

            pred_vals = np.array([predicted_changes[k] for k in predicted_changes])
            actual_vals = np.array([actual_changes[k] for k in predicted_changes])

            # Correlation
            if np.std(pred_vals) > 0 and np.std(actual_vals) > 0:
                pearson_r, _ = stats.pearsonr(pred_vals, actual_vals)
                r_squared = pearson_r ** 2
            else:
                pearson_r = 0
                r_squared = 0

            # Error metrics
            mae = np.mean(np.abs(pred_vals - actual_vals))
            rmse = np.sqrt(np.mean((pred_vals - actual_vals) ** 2))

            return BacktestResult(
                case_id=case_id, country=country, indicator=indicator,
                intervention_year=intervention_year,
                change_percent=observed_change_percent,
                n_indicators_compared=len(predicted_changes),
                r_squared=float(r_squared),
                pearson_r=float(pearson_r),
                mae=float(mae),
                rmse=float(rmse),
                predicted_changes=predicted_changes,
                actual_changes=actual_changes,
                success=True
            )

        except Exception as e:
            return BacktestResult(
                case_id=case_id, country=country, indicator=indicator,
                intervention_year=intervention_year,
                change_percent=observed_change_percent,
                n_indicators_compared=0, r_squared=0, pearson_r=0,
                mae=0, rmse=0, predicted_changes={}, actual_changes={},
                success=False, error_message=str(e)
            )


def calculate_aggregate_metrics(results: List[BacktestResult]) -> Dict:
    """Calculate aggregate metrics across all backtests."""
    successful = [r for r in results if r.success and r.n_indicators_compared >= 3]

    if not successful:
        return {
            'n_total': len(results),
            'n_successful': 0,
            'mean_r_squared': 0.0,
            'median_r_squared': 0.0,
            'std_r_squared': 0.0,
            'mean_pearson_r': 0.0,
            'mean_mae': 0.0,
            'mean_rmse': 0.0,
            'validation_passed': False
        }

    r_squared_vals = [r.r_squared for r in successful]
    pearson_vals = [r.pearson_r for r in successful]
    mae_vals = [r.mae for r in successful]
    rmse_vals = [r.rmse for r in successful]

    mean_r2 = np.mean(r_squared_vals)

    return {
        'n_total': len(results),
        'n_successful': len(successful),
        'mean_r_squared': float(mean_r2),
        'median_r_squared': float(np.median(r_squared_vals)),
        'std_r_squared': float(np.std(r_squared_vals)),
        'mean_pearson_r': float(np.mean(pearson_vals)),
        'mean_mae': float(np.mean(mae_vals)),
        'mean_rmse': float(np.mean(rmse_vals)),
        'validation_passed': bool(mean_r2 > 0.5)
    }


# Singleton instance
backtest_framework = BacktestFramework()
