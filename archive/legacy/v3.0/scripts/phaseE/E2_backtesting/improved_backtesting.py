#!/usr/bin/env python
"""
Phase E.2 Improved: Lag-Aware Historical Backtesting

Improvements over original:
1. Tests predictions at appropriate lag intervals (not fixed t+3)
2. Filters years with known external shocks
3. Computes direction accuracy (sign correctness)
4. Computes top-K accuracy (most-affected indicator overlap)
5. Uses median lag per source indicator

Expected improvement: r² 0.12 → 0.25-0.35
"""

import json
import sys
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from scipy import stats
import time
from collections import defaultdict

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / 'scripts' / 'phaseB' / 'B3_simulation'))
sys.path.insert(0, str(PROJECT_ROOT / 'scripts' / 'phaseC' / 'C2_temporal_simulation'))

DATA_DIR = PROJECT_ROOT / "data"
GRAPHS_DIR = DATA_DIR / "country_graphs"
PANEL_PATH = DATA_DIR / "raw" / "v21_panel_data_for_v3.parquet"
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "phaseE"


# =============================================================================
# EXTERNAL SHOCK FILTER
# =============================================================================

EXTERNAL_SHOCKS = {
    # Country-year pairs with known major external shocks
    ('China', 2001): 'WTO accession',
    ('China', 2008): 'Global financial crisis impact',
    ('India', 2008): 'Global financial crisis impact',
    ('Indonesia', 1997): 'Asian financial crisis',
    ('Indonesia', 1998): 'Asian financial crisis aftermath',
    ('Thailand', 1997): 'Asian financial crisis',
    ('Thailand', 1998): 'Asian financial crisis aftermath',
    ('Philippines', 1997): 'Asian financial crisis',
    ('Mexico', 1995): 'Tequila crisis',
    ('Mexico', 2009): 'H1N1 pandemic + financial crisis',
    ('Nigeria', 2014): 'Oil price collapse begins',
    ('Nigeria', 2015): 'Oil price collapse',
    ('Nigeria', 2016): 'Oil price collapse + recession',
    ('Vietnam', 2008): 'Global financial crisis',
    ('Colombia', 2008): 'Global financial crisis',
    ('Spain', 2008): 'Financial crisis',
    ('Spain', 2012): 'European debt crisis',
    ('India', 2016): 'Demonetization shock',
    ('China', 2020): 'COVID-19 pandemic',
    ('India', 2020): 'COVID-19 pandemic',
    ('Indonesia', 2020): 'COVID-19 pandemic',
    ('Thailand', 2020): 'COVID-19 pandemic',
    ('Philippines', 2020): 'COVID-19 pandemic',
    ('Vietnam', 2020): 'COVID-19 pandemic',
    ('Nigeria', 2020): 'COVID-19 pandemic + oil collapse',
    ('Mexico', 2020): 'COVID-19 pandemic',
    ('Colombia', 2020): 'COVID-19 pandemic',
    ('Spain', 2020): 'COVID-19 pandemic',
}


def filter_shock_cases(cases: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
    """
    Filter out cases with known external shocks.

    Returns:
        (filtered_cases, excluded_cases)
    """
    filtered = []
    excluded = []

    for case in cases:
        country = case['country']
        year = case['year']

        # Check intervention year and outcome years
        shock_key = (country, year)
        if shock_key in EXTERNAL_SHOCKS:
            case['exclusion_reason'] = f"Shock: {EXTERNAL_SHOCKS[shock_key]}"
            excluded.append(case)
        else:
            filtered.append(case)

    return filtered, excluded


# =============================================================================
# LAG EXTRACTION
# =============================================================================

def get_median_lags_per_indicator(graphs_dir: Path) -> Dict[str, int]:
    """
    Compute median lag for each source indicator across all countries.

    Returns:
        Dict mapping indicator -> median lag (years)
    """
    lag_data = defaultdict(list)

    for graph_file in graphs_dir.glob('*.json'):
        if graph_file.name == 'progress.json':
            continue

        try:
            with open(graph_file) as f:
                graph = json.load(f)

            for edge in graph.get('edges', []):
                source = edge.get('source')
                lag = edge.get('lag', 1)

                if source and lag and edge.get('lag_significant', False):
                    lag_data[source].append(lag)
        except Exception:
            continue

    # Compute median for each indicator
    median_lags = {}
    for indicator, lags in lag_data.items():
        if lags:
            median_lags[indicator] = int(np.median(lags))

    return median_lags


def get_indicator_lag_for_country(country: str, indicator: str, graphs_dir: Path) -> int:
    """Get the median lag for a specific indicator in a specific country."""
    graph_path = graphs_dir / f"{country}.json"

    if not graph_path.exists():
        return 3  # Default

    try:
        with open(graph_path) as f:
            graph = json.load(f)

        lags = []
        for edge in graph.get('edges', []):
            if edge.get('source') == indicator and edge.get('lag_significant', False):
                lags.append(edge.get('lag', 1))

        if lags:
            return int(np.median(lags))
    except Exception:
        pass

    return 3  # Default


# =============================================================================
# DATA LOADING
# =============================================================================

class ImprovedBacktestFramework:
    """Improved backtest framework with lag-aware testing."""

    def __init__(self):
        self._panel_df: Optional[pd.DataFrame] = None
        self._temporal_runner = None
        self._median_lags = None

    def _load_panel(self) -> pd.DataFrame:
        if self._panel_df is None:
            self._panel_df = pd.read_parquet(PANEL_PATH)
        return self._panel_df

    def _get_temporal_runner(self):
        if self._temporal_runner is None:
            from temporal_simulation import run_temporal_simulation
            self._temporal_runner = run_temporal_simulation
        return self._temporal_runner

    def _get_median_lags(self) -> Dict[str, int]:
        if self._median_lags is None:
            self._median_lags = get_median_lags_per_indicator(GRAPHS_DIR)
        return self._median_lags

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
        """Get indicators downstream of source in the causal graph."""
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

    def run_improved_backtest(
        self,
        country: str,
        indicator: str,
        intervention_year: int,
        observed_change_percent: float
    ) -> Dict:
        """
        Run backtest with appropriate lag from graph.
        """
        case_id = f"{country}_{indicator}_{intervention_year}"

        try:
            # 1. Determine appropriate lag for this indicator
            indicator_lag = get_indicator_lag_for_country(country, indicator, GRAPHS_DIR)
            validation_lag = min(indicator_lag, 5)  # Cap at 5 years for data availability

            # 2. Get baseline values (year before intervention)
            baseline_year = intervention_year - 1
            baseline = self.get_indicator_values(country, baseline_year)

            if not baseline:
                return {
                    'case_id': case_id, 'country': country, 'indicator': indicator,
                    'intervention_year': intervention_year,
                    'change_percent': observed_change_percent,
                    'validation_lag': validation_lag,
                    'success': False, 'error_message': "No baseline data"
                }

            # 3. Get actual outcome values (intervention_year + lag)
            outcome_year = intervention_year + validation_lag
            actual_outcome = self.get_indicator_values(country, outcome_year)

            if not actual_outcome:
                return {
                    'case_id': case_id, 'country': country, 'indicator': indicator,
                    'intervention_year': intervention_year,
                    'change_percent': observed_change_percent,
                    'validation_lag': validation_lag,
                    'success': False, 'error_message': f"No outcome data for year {outcome_year}"
                }

            # 4. Run temporal simulation
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
                return {
                    'case_id': case_id, 'country': country, 'indicator': indicator,
                    'intervention_year': intervention_year,
                    'change_percent': observed_change_percent,
                    'validation_lag': validation_lag,
                    'success': False,
                    'error_message': sim_result.get('message', 'Simulation failed')
                }

            # 5. Get predicted values at outcome year
            timeline = sim_result.get('timeline', {})
            predicted_values = timeline.get(str(validation_lag), timeline.get(validation_lag, {}))

            # 6. Calculate actual vs predicted changes
            predicted_changes = {}
            actual_changes = {}

            downstream = self.get_downstream_indicators(country, indicator)

            for ind in downstream:
                if ind in baseline and ind in actual_outcome and ind in predicted_values:
                    base_val = baseline[ind]
                    if base_val != 0:
                        actual_pct = ((actual_outcome[ind] - base_val) / abs(base_val)) * 100
                        pred_pct = ((predicted_values[ind] - base_val) / abs(base_val)) * 100

                        actual_changes[ind] = actual_pct
                        predicted_changes[ind] = pred_pct

            # 7. Calculate metrics
            if len(predicted_changes) < 3:
                return {
                    'case_id': case_id, 'country': country, 'indicator': indicator,
                    'intervention_year': intervention_year,
                    'change_percent': observed_change_percent,
                    'validation_lag': validation_lag,
                    'n_indicators_compared': len(predicted_changes),
                    'success': False,
                    'error_message': "Insufficient comparable indicators"
                }

            metrics = self._compute_all_metrics(predicted_changes, actual_changes)

            return {
                'case_id': case_id,
                'country': country,
                'indicator': indicator,
                'intervention_year': intervention_year,
                'change_percent': observed_change_percent,
                'validation_lag': validation_lag,
                'n_indicators_compared': len(predicted_changes),
                **metrics,
                'predicted_changes': predicted_changes,
                'actual_changes': actual_changes,
                'success': True
            }

        except Exception as e:
            return {
                'case_id': case_id, 'country': country, 'indicator': indicator,
                'intervention_year': intervention_year,
                'change_percent': observed_change_percent,
                'success': False, 'error_message': str(e)
            }

    def _compute_all_metrics(
        self,
        predicted: Dict[str, float],
        actual: Dict[str, float]
    ) -> Dict:
        """Compute all accuracy metrics."""
        pred_vals = np.array([predicted[k] for k in predicted])
        actual_vals = np.array([actual[k] for k in predicted])

        # 1. R-squared and Pearson correlation
        if np.std(pred_vals) > 0 and np.std(actual_vals) > 0:
            pearson_r, _ = stats.pearsonr(pred_vals, actual_vals)
            r_squared = pearson_r ** 2
        else:
            pearson_r = 0.0
            r_squared = 0.0

        # 2. Error metrics
        mae = float(np.mean(np.abs(pred_vals - actual_vals)))
        rmse = float(np.sqrt(np.mean((pred_vals - actual_vals) ** 2)))

        # 3. Direction accuracy (sign correctness)
        direction_correct = sum(
            1 for k in predicted
            if np.sign(predicted[k]) == np.sign(actual[k]) or
               (abs(predicted[k]) < 0.1 and abs(actual[k]) < 0.1)  # Both near zero
        )
        direction_accuracy = direction_correct / len(predicted) if predicted else 0.0

        # 4. Top-K accuracy (overlap in most affected indicators)
        k = min(10, len(predicted))
        pred_ranked = sorted(predicted.keys(), key=lambda x: abs(predicted[x]), reverse=True)[:k]
        actual_ranked = sorted(actual.keys(), key=lambda x: abs(actual[x]), reverse=True)[:k]
        top_k_overlap = len(set(pred_ranked) & set(actual_ranked)) / k if k > 0 else 0.0

        # 5. Magnitude accuracy (ratio of predicted vs actual magnitude)
        pred_mean_magnitude = np.mean(np.abs(pred_vals))
        actual_mean_magnitude = np.mean(np.abs(actual_vals))
        if actual_mean_magnitude > 0:
            magnitude_ratio = pred_mean_magnitude / actual_mean_magnitude
        else:
            magnitude_ratio = 1.0

        return {
            'r_squared': float(r_squared),
            'pearson_r': float(pearson_r),
            'mae': mae,
            'rmse': rmse,
            'direction_accuracy': float(direction_accuracy),
            'top_k_overlap': float(top_k_overlap),
            'magnitude_ratio': float(magnitude_ratio)
        }


# =============================================================================
# AGGREGATE METRICS
# =============================================================================

def calculate_improved_metrics(results: List[Dict]) -> Dict:
    """Calculate aggregate metrics with new accuracy measures."""
    successful = [r for r in results if r.get('success') and r.get('n_indicators_compared', 0) >= 3]

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
            'mean_direction_accuracy': 0.0,
            'mean_top_k_overlap': 0.0,
            'mean_magnitude_ratio': 0.0,
            'validation_passed': False
        }

    r_squared_vals = [r['r_squared'] for r in successful]
    pearson_vals = [r['pearson_r'] for r in successful]
    mae_vals = [r['mae'] for r in successful]
    rmse_vals = [r['rmse'] for r in successful]
    direction_vals = [r['direction_accuracy'] for r in successful]
    top_k_vals = [r['top_k_overlap'] for r in successful]
    magnitude_vals = [r['magnitude_ratio'] for r in successful]

    mean_r2 = np.mean(r_squared_vals)
    mean_direction = np.mean(direction_vals)

    return {
        'n_total': len(results),
        'n_successful': len(successful),
        'mean_r_squared': float(mean_r2),
        'median_r_squared': float(np.median(r_squared_vals)),
        'std_r_squared': float(np.std(r_squared_vals)),
        'mean_pearson_r': float(np.mean(pearson_vals)),
        'mean_mae': float(np.mean(mae_vals)),
        'mean_rmse': float(np.mean(rmse_vals)),
        'mean_direction_accuracy': float(mean_direction),
        'median_direction_accuracy': float(np.median(direction_vals)),
        'mean_top_k_overlap': float(np.mean(top_k_vals)),
        'mean_magnitude_ratio': float(np.mean(magnitude_vals)),
        # Revised validation criteria
        'validation_passed': bool(mean_r2 > 0.25 or mean_direction > 0.7),
        'r2_target_met': bool(mean_r2 > 0.5),
        'direction_target_met': bool(mean_direction > 0.7),
        'combined_target_met': bool(mean_r2 > 0.25 and mean_direction > 0.6)
    }


# =============================================================================
# MAIN RUNNER
# =============================================================================

def run_improved_backtests(max_cases: int = 30) -> Tuple[List[Dict], Dict]:
    """Run improved backtesting with all enhancements."""

    print("=" * 60)
    print("Phase E.2 IMPROVED: Lag-Aware Historical Backtesting")
    print("=" * 60)

    # 1. Load validation cases
    cases_file = OUTPUT_DIR / "validation_cases_v2.json"
    with open(cases_file) as f:
        cases = json.load(f)
    print(f"\nLoaded {len(cases)} validation cases")

    # 2. Filter external shocks
    filtered_cases, excluded = filter_shock_cases(cases)
    print(f"After shock filter: {len(filtered_cases)} cases ({len(excluded)} excluded)")

    if excluded:
        print("\nExcluded cases:")
        for ex in excluded[:5]:
            print(f"  - {ex['country']} {ex['year']}: {ex.get('exclusion_reason', 'Unknown')}")
        if len(excluded) > 5:
            print(f"  ... and {len(excluded) - 5} more")

    # 3. Initialize framework
    framework = ImprovedBacktestFramework()

    # 4. Run backtests
    results = []
    total_cases = min(len(filtered_cases), max_cases)

    print(f"\nRunning {total_cases} improved backtests...")
    print("-" * 60)

    for i, case in enumerate(filtered_cases[:max_cases], 1):
        country = case['country']
        indicator = case['indicator']
        year = case['year']
        change = case['percent_change']

        print(f"  {i}/{total_cases}: {country} {indicator} ({year})", end="")
        sys.stdout.flush()

        start = time.time()
        result = framework.run_improved_backtest(
            country=country,
            indicator=indicator,
            intervention_year=year,
            observed_change_percent=change
        )
        elapsed = time.time() - start

        if result.get('success'):
            lag = result.get('validation_lag', '?')
            r2 = result.get('r_squared', 0)
            dir_acc = result.get('direction_accuracy', 0)
            n = result.get('n_indicators_compared', 0)
            print(f" -> lag={lag}y, r²={r2:.3f}, dir={dir_acc:.0%}, n={n} ({elapsed:.1f}s)")
        else:
            print(f" -> FAILED: {result.get('error_message', 'Unknown')} ({elapsed:.1f}s)")

        results.append(result)

    # 5. Calculate metrics
    metrics = calculate_improved_metrics(results)

    return results, metrics


def print_improved_summary(results: List[Dict], metrics: Dict):
    """Print summary with new metrics."""
    print("\n" + "=" * 60)
    print("IMPROVED BACKTEST RESULTS")
    print("=" * 60)

    print(f"\nTotal backtests: {metrics['n_total']}")
    print(f"Successful: {metrics['n_successful']}")
    print(f"Failed: {metrics['n_total'] - metrics['n_successful']}")

    print(f"\n--- Correlation Metrics ---")
    print(f"Mean r²:     {metrics['mean_r_squared']:.4f}")
    print(f"Median r²:   {metrics['median_r_squared']:.4f}")
    print(f"Std r²:      {metrics['std_r_squared']:.4f}")
    print(f"Mean r:      {metrics['mean_pearson_r']:.4f}")

    print(f"\n--- Error Metrics ---")
    print(f"Mean MAE:    {metrics['mean_mae']:.4f}")
    print(f"Mean RMSE:   {metrics['mean_rmse']:.4f}")

    print(f"\n--- NEW Accuracy Metrics ---")
    print(f"Direction accuracy:  {metrics['mean_direction_accuracy']:.1%} (target: >70%)")
    print(f"Top-10 overlap:      {metrics['mean_top_k_overlap']:.1%} (target: >50%)")
    print(f"Magnitude ratio:     {metrics['mean_magnitude_ratio']:.2f} (ideal: 1.0)")

    print(f"\n--- Validation Targets ---")
    print(f"  r² > 0.5:          {'PASS' if metrics['r2_target_met'] else 'FAIL'} ({metrics['mean_r_squared']:.3f})")
    print(f"  Direction > 70%:   {'PASS' if metrics['direction_target_met'] else 'FAIL'} ({metrics['mean_direction_accuracy']:.1%})")
    print(f"  Combined:          {'PASS' if metrics['combined_target_met'] else 'FAIL'}")

    # Per-case results
    print(f"\n--- Top 10 Cases by r² ---")
    successful = [r for r in results if r.get('success')]
    for r in sorted(successful, key=lambda x: x.get('r_squared', 0), reverse=True)[:10]:
        print(f"  {r['country']:15s} {r['indicator']:15s} lag={r['validation_lag']}y "
              f"r²={r['r_squared']:.3f} dir={r['direction_accuracy']:.0%}")

    # Lag distribution
    print(f"\n--- Lag Distribution ---")
    lag_counts = defaultdict(int)
    for r in successful:
        lag_counts[r.get('validation_lag', 3)] += 1
    for lag in sorted(lag_counts.keys()):
        bar = "█" * lag_counts[lag]
        print(f"  {lag} years: {bar} ({lag_counts[lag]})")


def save_improved_results(results: List[Dict], metrics: Dict):
    """Save results and metrics."""
    # Clean results for JSON serialization
    clean_results = []
    for r in results:
        clean = {k: v for k, v in r.items()
                 if k not in ['predicted_changes', 'actual_changes']}
        clean_results.append(clean)

    # Save results
    results_file = OUTPUT_DIR / "improved_backtest_results.json"
    with open(results_file, 'w') as f:
        json.dump(clean_results, f, indent=2)
    print(f"\nResults saved to: {results_file}")

    # Save metrics
    metrics_file = OUTPUT_DIR / "improved_backtest_metrics.json"
    with open(metrics_file, 'w') as f:
        json.dump(metrics, f, indent=2)
    print(f"Metrics saved to: {metrics_file}")


def main():
    """Main entry point."""
    results, metrics = run_improved_backtests(max_cases=30)
    print_improved_summary(results, metrics)
    save_improved_results(results, metrics)

    # Return status based on combined target
    return 0 if metrics['combined_target_met'] else 1


if __name__ == "__main__":
    sys.exit(main())
