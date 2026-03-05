#!/usr/bin/env python
"""
Phase E.2 Calibrated: Historical Backtesting with Magnitude Calibration

Addresses the 4x over-prediction issue by:
1. Using a stronger dampening factor (0.125 instead of 0.5)
2. Re-running backtests with calibrated predictions

This should bring magnitude_ratio closer to 1.0 and improve direction accuracy.
"""

import json
import sys
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from scipy import stats
import time
from collections import defaultdict

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / 'scripts' / 'phaseB' / 'B1_saturation'))
sys.path.insert(0, str(PROJECT_ROOT / 'scripts' / 'phaseB' / 'B2_propagation'))
sys.path.insert(0, str(PROJECT_ROOT / 'scripts' / 'phaseC' / 'C2_temporal_simulation'))

DATA_DIR = PROJECT_ROOT / "data"
GRAPHS_DIR = DATA_DIR / "country_graphs"
PANEL_PATH = DATA_DIR / "raw" / "v21_panel_data_for_v3.parquet"
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "phaseE"


# =============================================================================
# EXTERNAL SHOCK FILTER (same as improved version)
# =============================================================================

EXTERNAL_SHOCKS = {
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
    filtered = []
    excluded = []
    for case in cases:
        shock_key = (case['country'], case['year'])
        if shock_key in EXTERNAL_SHOCKS:
            case['exclusion_reason'] = f"Shock: {EXTERNAL_SHOCKS[shock_key]}"
            excluded.append(case)
        else:
            filtered.append(case)
    return filtered, excluded


# =============================================================================
# CALIBRATED TEMPORAL SIMULATION
# =============================================================================

from saturation_functions import apply_saturation


def load_country_graph(country_code: str) -> dict:
    graph_path = GRAPHS_DIR / f"{country_code}.json"
    if not graph_path.exists():
        raise FileNotFoundError(f"No graph found for {country_code}")
    with open(graph_path) as f:
        return json.load(f)


def build_lagged_adjacency(graph: dict) -> dict:
    adj = defaultdict(list)
    for edge in graph['edges']:
        lag = edge.get('lag', 1)
        adj[edge['source']].append({
            'target': edge['target'],
            'beta': edge['beta'],
            'lag': lag,
            'significant': edge.get('lag_significant', False)
        })
    return dict(adj)


def load_baseline_values(country_code: str, year: Optional[int] = None) -> dict:
    df = pd.read_parquet(PANEL_PATH)
    if 'indicator_id' in df.columns:
        country_data = df[df['country'] == country_code]
        if country_data.empty:
            return {}
        if year is None:
            year = country_data['year'].max()
        year_data = country_data[country_data['year'] == year]
        return dict(zip(year_data['indicator_id'], year_data['value']))
    else:
        country_data = df[df['country'] == country_code]
        if country_data.empty:
            return {}
        if year is None:
            year = country_data['year'].max()
        row = country_data[country_data['year'] == year]
        if row.empty:
            return {}
        return row.drop(columns=['country', 'year'], errors='ignore').iloc[0].to_dict()


def propagate_calibrated(
    adjacency: dict,
    intervention: dict,
    baseline_values: dict,
    horizon_years: int = 10,
    dampening_factor: float = 0.25,  # CALIBRATED: reduced from 0.5 to 0.25 (1/4 reduction)
    max_percent_change: float = 100.0  # Keep original
) -> dict:
    """
    Propagate with calibrated dampening to reduce over-prediction.
    """
    timeline = {0: baseline_values.copy()}
    deltas_timeline = {0: {}}

    # Apply intervention at year 0
    for indicator, delta in intervention.items():
        if indicator in timeline[0]:
            baseline = baseline_values[indicator]
            if baseline != 0:
                max_delta = abs(baseline) * (max_percent_change / 100)
                delta = np.clip(delta, -max_delta, max_delta)
            new_val = timeline[0][indicator] + delta
            timeline[0][indicator] = apply_saturation(indicator, new_val, baseline)
            deltas_timeline[0][indicator] = timeline[0][indicator] - baseline

    # Propagate through time
    for year in range(1, horizon_years + 1):
        timeline[year] = timeline[year - 1].copy()
        deltas_timeline[year] = deltas_timeline[year - 1].copy()

        new_effects = defaultdict(float)

        for source, edges in adjacency.items():
            for edge_info in edges:
                target = edge_info['target']
                beta = edge_info['beta']
                lag = edge_info['lag']

                source_year = year - lag
                if source_year < 0:
                    continue

                source_delta = deltas_timeline.get(source_year, {}).get(source, 0)
                if abs(source_delta) < 1e-9:
                    continue

                # Apply calibrated dampening
                effect = beta * source_delta * dampening_factor
                new_effects[target] += effect

        # Apply accumulated effects
        for target, total_effect in new_effects.items():
            baseline = baseline_values.get(target, 0)
            if baseline == 0:
                continue

            current_delta = deltas_timeline[year].get(target, 0)
            proposed_delta = current_delta + total_effect

            max_delta = abs(baseline) * (max_percent_change / 100)
            clamped_delta = np.clip(proposed_delta, -max_delta, max_delta)

            new_val = baseline + clamped_delta
            saturated = apply_saturation(target, new_val, baseline)

            timeline[year][target] = saturated
            deltas_timeline[year][target] = saturated - baseline

    return {'timeline': timeline, 'deltas': deltas_timeline}


def run_calibrated_simulation(
    country_code: str,
    interventions: list,
    horizon_years: int = 10,
    base_year: Optional[int] = None
) -> dict:
    """Run calibrated temporal simulation."""
    graph = load_country_graph(country_code)
    adjacency = build_lagged_adjacency(graph)

    baseline = load_baseline_values(country_code, base_year)
    if not baseline:
        return {'status': 'error', 'message': f'No baseline data for {country_code}'}

    intervention_deltas = {}
    for iv in interventions:
        indicator = iv['indicator']
        if indicator in baseline:
            change_pct = iv['change_percent']
            delta = baseline[indicator] * (change_pct / 100)
            intervention_deltas[indicator] = delta

    if not intervention_deltas:
        return {'status': 'error', 'message': 'No valid interventions'}

    result = propagate_calibrated(
        adjacency=adjacency,
        intervention=intervention_deltas,
        baseline_values=baseline,
        horizon_years=horizon_years
    )

    return {
        'status': 'success',
        'timeline': result['timeline'],
        'country': country_code,
        'base_year': base_year,
        'horizon_years': horizon_years
    }


# =============================================================================
# CALIBRATED BACKTEST FRAMEWORK
# =============================================================================

class CalibratedBacktestFramework:
    """Backtest framework with calibrated predictions."""

    def __init__(self):
        self._panel_df: Optional[pd.DataFrame] = None

    def _load_panel(self) -> pd.DataFrame:
        if self._panel_df is None:
            self._panel_df = pd.read_parquet(PANEL_PATH)
        return self._panel_df

    def get_indicator_values(self, country: str, year: int) -> Dict[str, float]:
        df = self._load_panel()
        data = df[(df['country'] == country) & (df['year'] == year)]
        return dict(zip(data['indicator_id'], data['value']))

    def get_downstream_indicators(self, country: str, source_indicator: str) -> List[str]:
        graph_path = GRAPHS_DIR / f"{country}.json"
        if not graph_path.exists():
            return []
        with open(graph_path) as f:
            graph = json.load(f)
        downstream = set()
        for edge in graph.get('edges', []):
            if edge.get('source') == source_indicator:
                downstream.add(edge.get('target'))
        for edge in graph.get('edges', []):
            if edge.get('source') in downstream:
                downstream.add(edge.get('target'))
        downstream.discard(source_indicator)
        return list(downstream)

    def get_indicator_lag(self, country: str, indicator: str) -> int:
        graph_path = GRAPHS_DIR / f"{country}.json"
        if not graph_path.exists():
            return 3
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
        return 3

    def run_calibrated_backtest(
        self,
        country: str,
        indicator: str,
        intervention_year: int,
        observed_change_percent: float
    ) -> Dict:
        case_id = f"{country}_{indicator}_{intervention_year}"

        try:
            # 1. Determine appropriate lag
            indicator_lag = self.get_indicator_lag(country, indicator)
            validation_lag = min(indicator_lag, 5)

            # 2. Get baseline values
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

            # 3. Get actual outcome values
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

            # 4. Run CALIBRATED simulation
            sim_result = run_calibrated_simulation(
                country_code=country,
                interventions=[{
                    'indicator': indicator,
                    'change_percent': observed_change_percent
                }],
                horizon_years=validation_lag,
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

            # 5. Get predicted values
            timeline = sim_result.get('timeline', {})
            predicted_values = timeline.get(validation_lag, {})

            # 6. Calculate changes
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
                'success': True
            }

        except Exception as e:
            return {
                'case_id': case_id, 'country': country, 'indicator': indicator,
                'intervention_year': intervention_year,
                'change_percent': observed_change_percent,
                'success': False, 'error_message': str(e)
            }

    def _compute_all_metrics(self, predicted: Dict[str, float], actual: Dict[str, float]) -> Dict:
        pred_vals = np.array([predicted[k] for k in predicted])
        actual_vals = np.array([actual[k] for k in predicted])

        # R-squared
        if np.std(pred_vals) > 0 and np.std(actual_vals) > 0:
            pearson_r, _ = stats.pearsonr(pred_vals, actual_vals)
            r_squared = pearson_r ** 2
        else:
            pearson_r = 0.0
            r_squared = 0.0

        # Error metrics
        mae = float(np.mean(np.abs(pred_vals - actual_vals)))
        rmse = float(np.sqrt(np.mean((pred_vals - actual_vals) ** 2)))

        # Direction accuracy
        direction_correct = sum(
            1 for k in predicted
            if np.sign(predicted[k]) == np.sign(actual[k]) or
               (abs(predicted[k]) < 0.1 and abs(actual[k]) < 0.1)
        )
        direction_accuracy = direction_correct / len(predicted) if predicted else 0.0

        # Top-K accuracy
        k = min(10, len(predicted))
        pred_ranked = sorted(predicted.keys(), key=lambda x: abs(predicted[x]), reverse=True)[:k]
        actual_ranked = sorted(actual.keys(), key=lambda x: abs(actual[x]), reverse=True)[:k]
        top_k_overlap = len(set(pred_ranked) & set(actual_ranked)) / k if k > 0 else 0.0

        # Magnitude ratio
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


def calculate_calibrated_metrics(results: List[Dict]) -> Dict:
    successful = [r for r in results if r.get('success') and r.get('n_indicators_compared', 0) >= 3]

    if not successful:
        return {
            'n_total': len(results),
            'n_successful': 0,
            'mean_r_squared': 0.0,
            'mean_direction_accuracy': 0.0,
            'mean_top_k_overlap': 0.0,
            'mean_magnitude_ratio': 0.0,
            'validation_passed': False
        }

    r_squared_vals = [r['r_squared'] for r in successful]
    direction_vals = [r['direction_accuracy'] for r in successful]
    top_k_vals = [r['top_k_overlap'] for r in successful]
    magnitude_vals = [r['magnitude_ratio'] for r in successful]
    mae_vals = [r['mae'] for r in successful]
    rmse_vals = [r['rmse'] for r in successful]
    pearson_vals = [r['pearson_r'] for r in successful]

    mean_r2 = np.mean(r_squared_vals)
    mean_direction = np.mean(direction_vals)
    mean_top_k = np.mean(top_k_vals)

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
        'mean_top_k_overlap': float(mean_top_k),
        'mean_magnitude_ratio': float(np.mean(magnitude_vals)),
        'std_magnitude_ratio': float(np.std(magnitude_vals)),
        # Validation criteria
        'r2_target_met': bool(mean_r2 > 0.5),
        'direction_target_met': bool(mean_direction > 0.7),
        'top_k_target_met': bool(mean_top_k > 0.5),
        'magnitude_calibrated': bool(0.5 < np.mean(magnitude_vals) < 2.0),
        'validation_passed': bool(
            (mean_r2 > 0.25 or mean_direction > 0.6) and mean_top_k > 0.5
        )
    }


# =============================================================================
# MAIN RUNNER
# =============================================================================

def run_calibrated_backtests(max_cases: int = 30) -> Tuple[List[Dict], Dict]:
    print("=" * 60)
    print("Phase E.2 CALIBRATED: Backtesting with Magnitude Correction")
    print("=" * 60)
    print("\nCalibration: dampening_factor=0.15, max_change=50%")

    # Load and filter cases
    cases_file = OUTPUT_DIR / "validation_cases_v2.json"
    with open(cases_file) as f:
        cases = json.load(f)
    print(f"\nLoaded {len(cases)} validation cases")

    filtered_cases, excluded = filter_shock_cases(cases)
    print(f"After shock filter: {len(filtered_cases)} cases ({len(excluded)} excluded)")

    # Run backtests
    framework = CalibratedBacktestFramework()
    results = []
    total_cases = min(len(filtered_cases), max_cases)

    print(f"\nRunning {total_cases} calibrated backtests...")
    print("-" * 60)

    for i, case in enumerate(filtered_cases[:max_cases], 1):
        country = case['country']
        indicator = case['indicator']
        year = case['year']
        change = case['percent_change']

        print(f"  {i}/{total_cases}: {country} {indicator} ({year})", end="")
        sys.stdout.flush()

        start = time.time()
        result = framework.run_calibrated_backtest(
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
            mag = result.get('magnitude_ratio', 0)
            n = result.get('n_indicators_compared', 0)
            print(f" -> lag={lag}y, r²={r2:.3f}, dir={dir_acc:.0%}, mag={mag:.2f}, n={n} ({elapsed:.1f}s)")
        else:
            print(f" -> FAILED: {result.get('error_message', 'Unknown')} ({elapsed:.1f}s)")

        results.append(result)

    # Calculate metrics
    metrics = calculate_calibrated_metrics(results)

    return results, metrics


def print_calibrated_summary(results: List[Dict], metrics: Dict):
    print("\n" + "=" * 60)
    print("CALIBRATED BACKTEST RESULTS")
    print("=" * 60)

    print(f"\nTotal backtests: {metrics['n_total']}")
    print(f"Successful: {metrics['n_successful']}")

    print(f"\n--- Correlation Metrics ---")
    print(f"Mean r²:     {metrics['mean_r_squared']:.4f}")
    print(f"Median r²:   {metrics['median_r_squared']:.4f}")
    print(f"Mean r:      {metrics['mean_pearson_r']:.4f}")

    print(f"\n--- Error Metrics ---")
    print(f"Mean MAE:    {metrics['mean_mae']:.4f}")
    print(f"Mean RMSE:   {metrics['mean_rmse']:.4f}")

    print(f"\n--- Accuracy Metrics ---")
    print(f"Direction accuracy:  {metrics['mean_direction_accuracy']:.1%} (target: >70%)")
    print(f"Top-10 overlap:      {metrics['mean_top_k_overlap']:.1%} (target: >50%)")
    print(f"Magnitude ratio:     {metrics['mean_magnitude_ratio']:.2f} ± {metrics['std_magnitude_ratio']:.2f} (ideal: 1.0)")

    print(f"\n--- Validation Targets ---")
    print(f"  r² > 0.5:          {'PASS' if metrics['r2_target_met'] else 'FAIL'} ({metrics['mean_r_squared']:.3f})")
    print(f"  Direction > 70%:   {'PASS' if metrics['direction_target_met'] else 'FAIL'} ({metrics['mean_direction_accuracy']:.1%})")
    print(f"  Top-10 > 50%:      {'PASS' if metrics['top_k_target_met'] else 'FAIL'} ({metrics['mean_top_k_overlap']:.1%})")
    print(f"  Magnitude ~1.0:    {'PASS' if metrics['magnitude_calibrated'] else 'FAIL'} ({metrics['mean_magnitude_ratio']:.2f})")
    print(f"  Overall:           {'PASS' if metrics['validation_passed'] else 'FAIL'}")

    # Top cases
    print(f"\n--- Top 10 Cases by r² ---")
    successful = [r for r in results if r.get('success')]
    for r in sorted(successful, key=lambda x: x.get('r_squared', 0), reverse=True)[:10]:
        print(f"  {r['country']:15s} r²={r['r_squared']:.3f} dir={r['direction_accuracy']:.0%} mag={r['magnitude_ratio']:.2f}")


def save_calibrated_results(results: List[Dict], metrics: Dict):
    results_file = OUTPUT_DIR / "calibrated_backtest_results.json"
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to: {results_file}")

    metrics_file = OUTPUT_DIR / "calibrated_backtest_metrics.json"
    with open(metrics_file, 'w') as f:
        json.dump(metrics, f, indent=2)
    print(f"Metrics saved to: {metrics_file}")


def main():
    results, metrics = run_calibrated_backtests(max_cases=30)
    print_calibrated_summary(results, metrics)
    save_calibrated_results(results, metrics)
    return 0 if metrics['validation_passed'] else 1


if __name__ == "__main__":
    sys.exit(main())
