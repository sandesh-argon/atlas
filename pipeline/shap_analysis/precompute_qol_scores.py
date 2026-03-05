"""
Precompute QoL Scores for All Countries and Years

Run-once script that:
  A. Loads baselines, computes norm stats, determines empirical indicator directions
  B. Computes raw QoL for every country-year
  C. Fits HDI calibration from panel HDI data
  D. Applies calibration, saves final scores

Usage:
    source api/venv/bin/activate
    python -m simulation.precompute_qol_scores
"""

import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from simulation.qol_definition import (
    DEFINITION_ID,
    apply_hdi_calibration,
    apply_qol_calibration,
    compute_domain_means,
    compute_normalization_stats,
    load_indicator_metadata,
    predict_residual_correction,
)

DATA_ROOT = PROJECT_ROOT / "data"
BASELINES_DIR = DATA_ROOT / "v31" / "baselines"
METADATA_DIR = DATA_ROOT / "v31" / "metadata"
OUTPUT_DIR = DATA_ROOT / "v31" / "qol_scores"
PANEL_PATH = DATA_ROOT / "raw" / "v21_panel_data_for_v3.parquet"

# Mapping from panel country names → baseline directory names
PANEL_TO_BASELINE_NAME: Dict[str, str] = {
    "Bolivia (Plurinational State of)": "Bolivia",
    "Cabo Verde": "Cape Verde",
    "Central African Republic (the)": "Central African Republic",
    "Comoros (the)": "Comoros",
    "Congo (the Democratic Republic of the)": "Congo, Dem. Rep.",
    "Congo (the)": "Republic of the Congo",
    "CÃ\u00b4te d'Ivoire": "Ivory Coast",
    "Dominican Republic (the)": "Dominican Republic",
    "Gambia (the)": "The Gambia",
    "Iran (Islamic Republic of)": "Iran, Islamic Rep.",
    "Korea (the Republic of)": "Korea, Rep.",
    "Lao People's Democratic Republic (the)": "Laos",
    "Moldova (the Republic of)": "Moldova",
    "Netherlands (the)": "Netherlands",
    "Niger (the)": "Niger",
    "Philippines (the)": "Philippines",
    "Russian Federation (the)": "Russia",
    "Syrian Arab Republic (the)": "Syria",
    "Tanzania, the United Republic of": "Tanzania",
    "Turkey": "Türkiye",
    "United Arab Emirates (the)": "United Arab Emirates",
    "United Kingdom of Great Britain and Northern Ireland (the)": "United Kingdom",
    "United States of America (the)": "United States",
    "Venezuela (Bolivarian Republic of)": "Venezuela, RB",
}

# QoL robustness configuration
N_CALIBRATION_BREAKPOINTS = 50
Z_SCORE_CLIP = 1.5
MIN_INDICATORS_PER_DOMAIN = 10
RESIDUAL_KNN_K = 8
RESIDUAL_KNN_BANDWIDTH = 0.5
RESIDUAL_CLIP = 0.2


def aggregate_domain_score(
    domain_means: Dict[str, float],
    domain_weights: Optional[Dict[str, float]] = None,
) -> float:
    """
    Aggregate domain means into a raw QoL score.
    """
    if domain_weights:
        weighted_terms = []
        weight_total = 0.0
        for domain, mean_value in domain_means.items():
            weight = float(domain_weights.get(domain, 0.0))
            if weight <= 0:
                continue
            weighted_terms.append(weight * mean_value)
            weight_total += weight
        if weight_total > 0:
            return sum(weighted_terms) / weight_total
    return sum(domain_means.values()) / len(domain_means)


def load_all_baselines() -> Dict[str, Dict[str, Dict[str, float]]]:
    """
    Load all baseline files from data/v31/baselines/{country}/{year}.json.

    Returns:
        { country: { year_str: { indicator_id: value } } }
    """
    all_baselines: Dict[str, Dict[str, Dict[str, float]]] = {}
    skip_dirs = {"regional", "stratified", "unified"}

    for country_dir in sorted(BASELINES_DIR.iterdir()):
        if not country_dir.is_dir() or country_dir.name in skip_dirs:
            continue
        country = country_dir.name
        all_baselines[country] = {}
        for year_file in sorted(country_dir.glob("*.json")):
            year_str = year_file.stem
            with open(year_file) as f:
                data = json.load(f)
            all_baselines[country][year_str] = data.get("values", {})

    return all_baselines


def build_hdi_map() -> Dict[str, Dict[str, float]]:
    """
    Load HDI values from panel, mapped to baseline country names.

    Returns:
        { baseline_country_name: { year_str: hdi_value } }
    """
    df = pd.read_parquet(PANEL_PATH)
    hdi_df = df[df["indicator_id"] == "undp_hdi"][["country", "year", "value"]].copy()
    hdi_df = hdi_df.dropna(subset=["value"])

    result: Dict[str, Dict[str, float]] = {}
    for _, row in hdi_df.iterrows():
        bl_name = PANEL_TO_BASELINE_NAME.get(row["country"], row["country"])
        result.setdefault(bl_name, {})[str(int(row["year"]))] = float(row["value"])

    return result


def determine_direction_overrides(
    all_baselines: Dict[str, Dict[str, Dict[str, float]]],
    metadata: Dict[str, dict],
    norm_stats: Dict[str, dict],
    hdi_map: Dict[str, Dict[str, float]],
) -> Dict[str, str]:
    """
    Empirically determine indicator directions by correlating z-scored values
    with HDI. If an indicator's z-score correlates negatively with HDI,
    it should be flipped (higher raw value = worse QoL).

    Returns:
        { indicator_id: 'positive' | 'negative' } only for indicators where
        empirical direction differs from metadata direction.
    """
    # Collect (z_score, hdi) pairs per indicator
    from collections import defaultdict
    ind_pairs: Dict[str, List[Tuple[float, float]]] = defaultdict(list)

    for country, years in all_baselines.items():
        hdi_years = hdi_map.get(country, {})
        for year_str, values in years.items():
            hdi_val = hdi_years.get(year_str)
            if hdi_val is None:
                continue
            for ind_id, value in values.items():
                if ind_id not in norm_stats:
                    continue
                if value is None or (isinstance(value, float) and math.isnan(value)):
                    continue
                stats = norm_stats[ind_id]
                z = (float(value) - stats["mean"]) / stats["std"]
                ind_pairs[ind_id].append((z, hdi_val))

    overrides: Dict[str, str] = {}
    for ind_id, pairs in ind_pairs.items():
        if ind_id not in metadata:
            continue
        if len(pairs) < 30:
            continue
        z_arr = [p[0] for p in pairs]
        h_arr = [p[1] for p in pairs]
        # Simple correlation sign
        n = len(z_arr)
        mean_z = sum(z_arr) / n
        mean_h = sum(h_arr) / n
        cov = sum((z - mean_z) * (h - mean_h) for z, h in zip(z_arr, h_arr))
        empirical_dir = "positive" if cov >= 0 else "negative"
        default_dir = metadata.get(ind_id, {}).get("direction", "positive")
        if empirical_dir != default_dir:
            overrides[ind_id] = empirical_dir

    return overrides


def build_direction_override_diagnostics(
    all_baselines: Dict[str, Dict[str, Dict[str, float]]],
    metadata: Dict[str, dict],
    norm_stats: Dict[str, dict],
    direction_overrides: Dict[str, str],
    year: str = "2020",
) -> Dict[str, object]:
    """
    Build diagnostics for flipped indicator directions to support manual review.
    """
    diagnostics: List[dict] = []
    for ind_id, empirical_dir in direction_overrides.items():
        default_dir = metadata.get(ind_id, {}).get("direction", "positive")
        if empirical_dir == default_dir:
            continue

        stats = norm_stats.get(ind_id)
        if stats is None:
            continue

        z_values: List[float] = []
        for years in all_baselines.values():
            value = years.get(year, {}).get(ind_id)
            if value is None or (isinstance(value, float) and math.isnan(value)):
                continue
            z = (float(value) - stats["mean"]) / stats["std"]
            z_values.append(z)

        if not z_values:
            continue

        arr = np.array(z_values)
        diagnostics.append({
            "indicator_id": ind_id,
            "domain": metadata.get(ind_id, {}).get("domain"),
            "default_direction": default_dir,
            "empirical_direction": empirical_dir,
            "n_country_values": int(len(arr)),
            "mean_abs_z": float(np.mean(np.abs(arr))),
            "mean_z": float(np.mean(arr)),
            "median_z": float(np.median(arr)),
        })

    diagnostics_sorted = sorted(diagnostics, key=lambda d: d["mean_abs_z"], reverse=True)
    return {
        "year": year,
        "n_flipped_indicators": len(direction_overrides),
        "top_impactful_flips": diagnostics_sorted[:25],
    }


def fit_domain_weights(
    all_baselines: Dict[str, Dict[str, Dict[str, float]]],
    metadata: Dict[str, dict],
    norm_stats: Dict[str, dict],
    direction_overrides: Dict[str, str],
    hdi_map: Dict[str, Dict[str, float]],
    z_clip: float = Z_SCORE_CLIP,
    min_indicators_per_domain: int = MIN_INDICATORS_PER_DOMAIN,
) -> Tuple[Dict[str, float], Dict[str, object]]:
    """
    Fit non-negative domain weights against HDI using country-year domain means.

    This reduces sensitivity to domain imbalance and outlier indicators.
    """
    domains = sorted({m["domain"] for m in metadata.values() if m.get("domain") != "Security"})
    rows: List[Tuple[dict, float]] = []

    for country, years in all_baselines.items():
        hdi_years = hdi_map.get(country, {})
        for year_str, values in years.items():
            hdi_val = hdi_years.get(year_str)
            if hdi_val is None:
                continue

            computed = compute_domain_means(
                indicator_values=values,
                metadata=metadata,  # type: ignore[arg-type]
                norm_stats=norm_stats,  # type: ignore[arg-type]
                direction_overrides=direction_overrides,
                z_clip=z_clip,
                min_indicators_per_domain=min_indicators_per_domain,
            )
            if computed is None:
                continue
            domain_means, _ = computed
            # Exclude Security domain from HDI alignment fit (sparse/noisy in baselines).
            domain_means = {d: v for d, v in domain_means.items() if d != "Security"}
            if len(domain_means) < 3:
                continue
            rows.append((domain_means, float(hdi_val)))

    if len(rows) < 100:
        raise ValueError(f"Insufficient domain-mean rows for weight fit: {len(rows)}")

    # Fill missing domains with global medians so all rows share same feature space.
    domain_medians = {}
    for d in domains:
        vals = [dm[d] for dm, _ in rows if d in dm]
        if not vals:
            domain_medians[d] = 0.0
        else:
            domain_medians[d] = float(np.median(vals))

    X = np.array([
        [dm.get(d, domain_medians[d]) for d in domains]
        for dm, _ in rows
    ], dtype=float)
    y = np.array([hdi for _, hdi in rows], dtype=float)

    model = LinearRegression(positive=True)
    model.fit(X, y)
    coefs = np.maximum(model.coef_, 0.0)
    coef_sum = float(np.sum(coefs))
    if coef_sum <= 1e-12:
        coefs = np.ones_like(coefs)
        coef_sum = float(np.sum(coefs))
    weights = coefs / coef_sum
    domain_weights = {d: round(float(w), 6) for d, w in zip(domains, weights)}

    preds = np.clip(model.predict(X), 0.0, 1.0)
    fit_stats = {
        "n_pairs": len(rows),
        "train_mae": round(float(np.mean(np.abs(y - preds))), 4),
        "domains": domains,
        "weights": domain_weights,
    }
    return domain_weights, fit_stats


def fit_hdi_calibration(
    raw_scores: Dict[str, Dict[str, float]],
    hdi_map: Dict[str, Dict[str, float]],
    n_breakpoints: int = N_CALIBRATION_BREAKPOINTS,
) -> Tuple[Dict[str, List[float]], Dict[str, float]]:
    """
    Fit piecewise-linear calibration from raw QoL → HDI.

    Uses isotonic regression to ensure monotonicity, then samples breakpoints.

    Returns:
        (calibration_dict, fit_stats)
    """
    from sklearn.isotonic import IsotonicRegression

    # Join raw_scores with HDI
    pairs: List[Tuple[float, float]] = []
    for country, years in raw_scores.items():
        hdi_years = hdi_map.get(country, {})
        for year_str, raw_qol in years.items():
            hdi_val = hdi_years.get(year_str)
            if hdi_val is not None:
                pairs.append((raw_qol, hdi_val))

    if len(pairs) < 50:
        raise ValueError(f"Too few QoL-HDI pairs for calibration: {len(pairs)}")

    raw_arr = np.array([p[0] for p in pairs])
    hdi_arr = np.array([p[1] for p in pairs])

    # Fit isotonic regression (monotonic increasing)
    iso = IsotonicRegression(increasing=True, out_of_bounds="clip")
    iso.fit(raw_arr, hdi_arr)

    # Sample breakpoints at quantiles of the raw score distribution
    # to get good resolution where data is dense
    raw_min, raw_max = float(raw_arr.min()), float(raw_arr.max())
    quantiles = np.linspace(0, 100, n_breakpoints)
    bp_raw = np.percentile(raw_arr, quantiles)
    # Ensure endpoints are exact min/max
    bp_raw[0] = raw_min
    bp_raw[-1] = raw_max
    bp_hdi = iso.predict(bp_raw)

    # Fix plateau at the low end: use the actual minimum HDI observed
    # (isotonic clips too aggressively for sparse low-end data)
    hdi_min_actual = float(hdi_arr.min())
    bp_hdi[0] = min(bp_hdi[0], hdi_min_actual)

    calibration = {
        "breakpoints": [round(float(x), 6) for x in bp_raw],
        "hdi_values": [round(float(x), 6) for x in bp_hdi],
    }

    # Compute fit statistics
    predicted = iso.predict(raw_arr)
    residuals = hdi_arr - predicted
    correlation = float(np.corrcoef(raw_arr, hdi_arr)[0, 1])
    mae = float(np.mean(np.abs(residuals)))

    stats = {
        "correlation": round(correlation, 4),
        "mae": round(mae, 4),
        "n_pairs": len(pairs),
        "raw_range": [round(raw_min, 4), round(raw_max, 4)],
        "hdi_range": [round(float(hdi_arr.min()), 4), round(float(hdi_arr.max()), 4)],
    }

    return calibration, stats


def fit_residual_knn_model(
    qol_rows: List[Dict[str, Any]],
    calibration: Dict[str, object],
    feature_domains: List[str],
    k: int = RESIDUAL_KNN_K,
    bandwidth: float = RESIDUAL_KNN_BANDWIDTH,
    residual_clip: float = RESIDUAL_CLIP,
) -> Tuple[Dict[str, object], Dict[str, object]]:
    """
    Fit a deterministic KNN residual-correction model on top of base calibration.
    """
    feature_names = ["base_calibrated"] + [f"domain:{d}" for d in feature_domains] + ["n_indicators", "n_domains"]
    feature_rows: List[List[float]] = []
    residual_targets: List[float] = []

    for row in qol_rows:
        hdi_value = row.get("hdi")
        if hdi_value is None:
            continue
        raw_qol = float(row["raw_qol"])
        domain_means = row["domain_means"]
        n_indicators = int(row["n_indicators"])
        n_domains = int(row["n_domains"])
        base_calibrated = apply_hdi_calibration(raw_qol, calibration)  # type: ignore[arg-type]
        residual = float(hdi_value) - base_calibrated

        feature_row: List[float] = [float(base_calibrated)]
        for domain in feature_domains:
            val = domain_means.get(domain)  # type: ignore[union-attr]
            feature_row.append(float(val) if val is not None else float("nan"))
        feature_row.append(float(n_indicators))
        feature_row.append(float(n_domains))

        feature_rows.append(feature_row)
        residual_targets.append(residual)

    if len(feature_rows) < 50:
        raise ValueError(f"Too few rows for residual model fit: {len(feature_rows)}")

    X = np.array(feature_rows, dtype=float)
    y = np.array(residual_targets, dtype=float)

    feature_fill = np.nanmedian(X, axis=0)
    feature_fill = np.where(np.isnan(feature_fill), 0.0, feature_fill)
    X_filled = np.where(np.isnan(X), feature_fill, X)

    feature_mean = X_filled.mean(axis=0)
    feature_std = X_filled.std(axis=0)
    feature_std[feature_std < 1e-8] = 1.0
    X_scaled = (X_filled - feature_mean) / feature_std

    model = {
        "type": "knn_gaussian_v1",
        "feature_names": feature_names,
        "feature_fill": [round(float(x), 8) for x in feature_fill],
        "feature_mean": [round(float(x), 8) for x in feature_mean],
        "feature_std": [round(float(x), 8) for x in feature_std],
        "train_features_scaled": [
            [round(float(v), 8) for v in row]
            for row in X_scaled.tolist()
        ],
        "train_residuals": [round(float(v), 8) for v in y.tolist()],
        "k": int(max(1, min(k, len(feature_rows)))),
        "bandwidth": float(bandwidth),
        "residual_clip": float(max(0.0, residual_clip)),
        "global_mean_residual": round(float(np.mean(y)), 8),
    }

    # In-sample fit diagnostics for the residual model itself.
    predictions: List[float] = []
    for row in qol_rows:
        hdi_value = row.get("hdi")
        if hdi_value is None:
            continue
        raw_qol = float(row["raw_qol"])
        base_calibrated = apply_hdi_calibration(raw_qol, calibration)  # type: ignore[arg-type]
        correction = predict_residual_correction(
            base_calibrated=base_calibrated,
            domain_means=row["domain_means"],  # type: ignore[arg-type]
            n_indicators=int(row["n_indicators"]),
            n_domains=int(row["n_domains"]),
            residual_model=model,
        )
        correction = 0.0 if correction is None else float(correction)
        predictions.append(base_calibrated + correction)

    y_true = np.array([float(row["hdi"]) for row in qol_rows if row.get("hdi") is not None], dtype=float)
    pred_arr = np.array(predictions, dtype=float)
    residual_stats = {
        "model_type": "knn_gaussian_v1",
        "k": model["k"],
        "bandwidth": model["bandwidth"],
        "residual_clip": model["residual_clip"],
        "n_pairs": len(feature_rows),
        "train_mae": round(float(np.mean(np.abs(y_true - pred_arr))), 4),
        "train_max_abs_delta": round(float(np.max(np.abs(y_true - pred_arr))), 4),
    }
    return model, residual_stats


def evaluate_alignment(
    qol_rows: List[Dict[str, Any]],
    calibration: Dict[str, object],
    year: Optional[int] = None,
) -> Dict[str, object]:
    """
    Compare calibrated QoL against HDI for rows with available HDI values.
    """
    pairs: List[Tuple[str, int, float, float, float]] = []
    for row in qol_rows:
        hdi_value = row.get("hdi")
        if hdi_value is None:
            continue
        row_year = int(row["year"])
        if year is not None and row_year != year:
            continue
        score = apply_qol_calibration(
            raw_qol=float(row["raw_qol"]),
            calibration=calibration,
            domain_means=row["domain_means"],  # type: ignore[arg-type]
            n_indicators=int(row["n_indicators"]),
            n_domains=int(row["n_domains"]),
        )
        hdi = float(hdi_value)
        pairs.append((str(row["country"]), row_year, score, hdi, score - hdi))

    if not pairs:
        return {"n_pairs": 0}

    abs_delta = np.array([abs(delta) for _, _, _, _, delta in pairs], dtype=float)
    top = sorted(pairs, key=lambda item: abs(item[4]), reverse=True)[:20]
    return {
        "year": year,
        "n_pairs": len(pairs),
        "mae": round(float(np.mean(abs_delta)), 4),
        "p95_abs_delta": round(float(np.percentile(abs_delta, 95)), 4),
        "max_abs_delta": round(float(np.max(abs_delta)), 4),
        "n_over_0_12": int(np.sum(abs_delta > 0.12)),
        "top_20_abs_deltas": [
            {
                "country": country,
                "year": row_year,
                "qol_score": round(score, 4),
                "hdi": round(hdi, 4),
                "delta": round(delta, 4),
            }
            for country, row_year, score, hdi, delta in top
        ],
    }


def evaluate_2020_holdout(
    qol_rows: List[Dict[str, Any]],
    feature_domains: List[str],
) -> Dict[str, object]:
    """
    Holdout protocol:
      - Train base calibration + residual model on years <= 2019
      - Evaluate on year 2020
    """
    train_rows = [
        row for row in qol_rows
        if row.get("hdi") is not None and int(row["year"]) <= 2019
    ]
    eval_rows = [
        row for row in qol_rows
        if row.get("hdi") is not None and int(row["year"]) == 2020
    ]
    if len(train_rows) < 100 or len(eval_rows) < 50:
        return {
            "available": False,
            "reason": f"insufficient rows (train={len(train_rows)}, eval_2020={len(eval_rows)})",
        }

    train_raw_scores: Dict[str, Dict[str, float]] = {}
    train_hdi_map: Dict[str, Dict[str, float]] = {}
    for row in train_rows:
        country = str(row["country"])
        year_str = str(int(row["year"]))
        train_raw_scores.setdefault(country, {})[year_str] = float(row["raw_qol"])
        train_hdi_map.setdefault(country, {})[year_str] = float(row["hdi"])

    base_calibration, _ = fit_hdi_calibration(
        raw_scores=train_raw_scores,
        hdi_map=train_hdi_map,
        n_breakpoints=N_CALIBRATION_BREAKPOINTS,
    )
    baseline_metrics = evaluate_alignment(eval_rows, base_calibration)

    residual_model, residual_stats = fit_residual_knn_model(
        qol_rows=train_rows,
        calibration=base_calibration,
        feature_domains=feature_domains,
        k=RESIDUAL_KNN_K,
        bandwidth=RESIDUAL_KNN_BANDWIDTH,
        residual_clip=RESIDUAL_CLIP,
    )
    corrected_calibration = dict(base_calibration)
    corrected_calibration["residual_model"] = residual_model
    corrected_metrics = evaluate_alignment(eval_rows, corrected_calibration)

    return {
        "available": True,
        "train_rows": len(train_rows),
        "eval_rows_2020": len(eval_rows),
        "baseline_2020": baseline_metrics,
        "corrected_2020": corrected_metrics,
        "residual_model_fit": residual_stats,
    }


def main() -> None:
    print(f"=== QoL Score Precomputation ({DEFINITION_ID}) ===\n")

    # --- Phase A: Load metadata, baselines, compute normalization stats ---
    print("Phase A: Loading indicator metadata...")
    metadata = load_indicator_metadata(
        DATA_ROOT / "raw" / "v21_nodes.csv",
        METADATA_DIR / "indicator_properties.json",
    )
    print(f"  {len(metadata)} indicators loaded")

    print("Phase A: Loading all baselines...")
    all_baselines = load_all_baselines()
    n_countries = len(all_baselines)
    n_files = sum(len(years) for years in all_baselines.values())
    print(f"  {n_countries} countries, {n_files} country-year files")

    print("Phase A: Computing z-score normalization stats (global)...")
    norm_stats = compute_normalization_stats(all_baselines)
    print(f"  Stats for {len(norm_stats)} indicators")

    # Save normalization stats
    METADATA_DIR.mkdir(parents=True, exist_ok=True)
    norm_path = METADATA_DIR / "qol_normalization_stats_v1.json"
    with open(norm_path, "w") as f:
        json.dump(norm_stats, f)
    print(f"  Saved -> {norm_path.relative_to(PROJECT_ROOT)}")

    print("Phase A: Loading HDI data...")
    hdi_map = build_hdi_map()
    print(f"  HDI data for {len(hdi_map)} countries")

    print("Phase A: Determining empirical indicator directions...")
    direction_overrides = determine_direction_overrides(all_baselines, metadata, norm_stats, hdi_map)
    print(f"  {len(direction_overrides)} indicators flipped from metadata direction")

    # Save direction overrides
    dir_path = METADATA_DIR / "qol_direction_overrides_v1.json"
    with open(dir_path, "w") as f:
        json.dump(dict(sorted(direction_overrides.items())), f, indent=2)
    print(f"  Saved -> {dir_path.relative_to(PROJECT_ROOT)}")

    override_diag = build_direction_override_diagnostics(
        all_baselines=all_baselines,
        metadata=metadata,
        norm_stats=norm_stats,
        direction_overrides=direction_overrides,
        year="2020",
    )
    override_diag_path = METADATA_DIR / "qol_direction_override_diagnostics_v1.json"
    with open(override_diag_path, "w") as f:
        json.dump(override_diag, f, indent=2)
    print(f"  Saved override diagnostics -> {override_diag_path.relative_to(PROJECT_ROOT)}")

    print("Phase A: Fitting domain weights against HDI...")
    domain_weights, domain_weight_stats = fit_domain_weights(
        all_baselines=all_baselines,
        metadata=metadata,
        norm_stats=norm_stats,
        direction_overrides=direction_overrides,
        hdi_map=hdi_map,
        z_clip=Z_SCORE_CLIP,
        min_indicators_per_domain=MIN_INDICATORS_PER_DOMAIN,
    )
    print(f"  Domain weights: {domain_weights}")
    print(f"  Domain-weight fit MAE: {domain_weight_stats['train_mae']} over {domain_weight_stats['n_pairs']} pairs")

    # --- Phase B: Compute raw QoL for all country-years ---
    print("\nPhase B: Computing raw QoL scores (robust z + domain weights)...")
    raw_scores: Dict[str, Dict[str, float]] = {}
    qol_rows: List[Dict[str, Any]] = []
    total = 0
    skipped = 0

    for country, years in all_baselines.items():
        raw_scores[country] = {}
        for year_str, values in years.items():
            computed = compute_domain_means(
                indicator_values=values,
                metadata=metadata,  # type: ignore[arg-type]
                norm_stats=norm_stats,  # type: ignore[arg-type]
                direction_overrides=direction_overrides,
                z_clip=Z_SCORE_CLIP,
                min_indicators_per_domain=MIN_INDICATORS_PER_DOMAIN,
            )
            if computed is None:
                skipped += 1
                continue

            domain_means, n_indicators = computed
            raw_qol = aggregate_domain_score(domain_means, domain_weights)
            n_domains = len(domain_means)

            raw_scores[country][year_str] = raw_qol
            total += 1

            hdi_value = hdi_map.get(country, {}).get(year_str)
            qol_rows.append(
                {
                    "country": country,
                    "year": int(year_str),
                    "raw_qol": float(raw_qol),
                    "domain_means": dict(domain_means),
                    "n_indicators": int(n_indicators),
                    "n_domains": int(n_domains),
                    "hdi": float(hdi_value) if hdi_value is not None else None,
                }
            )

    print(f"  {total} scores computed, {skipped} skipped (insufficient domain coverage)")

    # Quick sanity check on raw scores
    raw_2020 = {c: s.get("2020") for c, s in raw_scores.items() if s.get("2020") is not None}
    sorted_2020 = sorted(raw_2020.items(), key=lambda x: x[1])
    print(f"  Raw 2020 range: {sorted_2020[0][0]}={sorted_2020[0][1]:.4f} to {sorted_2020[-1][0]}={sorted_2020[-1][1]:.4f}")
    norway_raw = raw_2020.get("Norway")
    afghan_raw = raw_2020.get("Afghanistan")
    if norway_raw and afghan_raw:
        print(f"  Norway raw={norway_raw:.4f}, Afghanistan raw={afghan_raw:.4f} (Norway should be higher)")

    # --- Phase C: Fit HDI calibration ---
    print("\nPhase C: Fitting HDI calibration...")
    calibration, cal_stats = fit_hdi_calibration(
        raw_scores,
        hdi_map,
        n_breakpoints=N_CALIBRATION_BREAKPOINTS,
    )
    calibration["domain_weights"] = domain_weights
    calibration["z_clip"] = Z_SCORE_CLIP
    calibration["min_indicators_per_domain"] = MIN_INDICATORS_PER_DOMAIN
    feature_domains = sorted(domain_weights.keys())
    residual_model, residual_model_stats = fit_residual_knn_model(
        qol_rows=qol_rows,
        calibration=calibration,
        feature_domains=feature_domains,
        k=RESIDUAL_KNN_K,
        bandwidth=RESIDUAL_KNN_BANDWIDTH,
        residual_clip=RESIDUAL_CLIP,
    )
    calibration["residual_model"] = residual_model
    print(f"  Correlation: {cal_stats['correlation']}")
    print(f"  MAE: {cal_stats['mae']}")
    print(f"  Pairs: {cal_stats['n_pairs']}")
    print(
        f"  Residual correction fit: model={residual_model_stats['model_type']}, "
        f"train_mae={residual_model_stats['train_mae']}, "
        f"train_max_abs_delta={residual_model_stats['train_max_abs_delta']}"
    )

    alignment_2020_baseline = evaluate_alignment(qol_rows, {k: v for k, v in calibration.items() if k != "residual_model"}, year=2020)
    alignment_2020 = evaluate_alignment(qol_rows, calibration, year=2020)
    holdout_2020 = evaluate_2020_holdout(qol_rows, feature_domains=feature_domains)
    print(
        f"  2020 baseline alignment: MAE={alignment_2020_baseline.get('mae')}, "
        f"max_abs_delta={alignment_2020_baseline.get('max_abs_delta')}, "
        f"n_over_0_12={alignment_2020_baseline.get('n_over_0_12')}"
    )
    print(
        f"  2020 corrected alignment: MAE={alignment_2020.get('mae')}, "
        f"max_abs_delta={alignment_2020.get('max_abs_delta')}, "
        f"n_over_0_12={alignment_2020.get('n_over_0_12')}"
    )
    if holdout_2020.get("available"):
        corrected_2020 = holdout_2020["corrected_2020"]
        print(
            f"  2020 holdout corrected: MAE={corrected_2020.get('mae')}, "
            f"max_abs_delta={corrected_2020.get('max_abs_delta')}, "
            f"n_over_0_12={corrected_2020.get('n_over_0_12')}"
        )
    else:
        print(f"  2020 holdout unavailable: {holdout_2020.get('reason')}")

    # Save calibration
    cal_path = METADATA_DIR / "qol_calibration_v1.json"
    with open(cal_path, "w") as f:
        json.dump(
            {
                "calibration": calibration,
                "stats": {
                    **cal_stats,
                    "n_breakpoints": N_CALIBRATION_BREAKPOINTS,
                    "z_clip": Z_SCORE_CLIP,
                    "min_indicators_per_domain": MIN_INDICATORS_PER_DOMAIN,
                    "domain_weight_fit": domain_weight_stats,
                    "residual_model_fit": residual_model_stats,
                    "alignment_2020_baseline": alignment_2020_baseline,
                    "alignment_2020": alignment_2020,
                    "holdout_2020": holdout_2020,
                },
            },
            f,
            indent=2,
        )
    print(f"  Saved -> {cal_path.relative_to(PROJECT_ROOT)}")

    # --- Phase D: Apply calibration and save final scores ---
    print("\nPhase D: Applying calibration to all country-years...")

    # Load ISO3 codes
    with open(METADATA_DIR / "income_classifications.json") as f:
        ic_data = json.load(f)
    ic_countries = ic_data.get("countries", {})

    # Build final output
    scores_output: Dict[str, dict] = {}
    for row in qol_rows:
        country = str(row["country"])
        year_str = str(int(row["year"]))
        raw_qol = float(row["raw_qol"])
        iso3 = ic_countries.get(country, {}).get("iso3", "")
        if country not in scores_output:
            scores_output[country] = {"iso3": iso3, "by_year": {}}
        calibrated = apply_qol_calibration(
            raw_qol=raw_qol,
            calibration=calibration,
            domain_means=row["domain_means"],  # type: ignore[arg-type]
            n_indicators=int(row["n_indicators"]),
            n_domains=int(row["n_domains"]),
        )
        scores_output[country]["by_year"][year_str] = round(calibrated, 4)

    for country in list(scores_output.keys()):
        by_year = scores_output[country]["by_year"]
        scores_output[country]["by_year"] = dict(sorted(by_year.items()))

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / "country_year_qol_v1.json"
    final = {
        "definition_id": DEFINITION_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "calibration": cal_stats,
        "scores": dict(sorted(scores_output.items())),
    }
    with open(output_path, "w") as f:
        json.dump(final, f, indent=2)
    print(f"  {len(scores_output)} countries with scores")
    print(f"  Saved -> {output_path.relative_to(PROJECT_ROOT)}")

    # --- Verification ---
    print("\n=== Verification ===")
    check_year = "2020"
    ranked_2020 = sorted(
        (
            (country, data["by_year"].get(check_year))
            for country, data in scores_output.items()
            if data["by_year"].get(check_year) is not None
        ),
        key=lambda x: x[1],
    )
    print(f"  2020 bottom 5: {[c for c, _ in ranked_2020[:5]]}")
    print(f"  2020 top 5: {[c for c, _ in ranked_2020[-5:]]}")
    print(f"  Calibration correlation(raw->HDI): {cal_stats['correlation']}")
    if alignment_2020.get("top_20_abs_deltas"):
        print("  2020 largest absolute deltas:")
        for row in alignment_2020["top_20_abs_deltas"][:5]:
            print(
                f"    {row['country']}: "
                f"QoL={row['qol_score']:.3f} vs HDI={row['hdi']:.3f} "
                f"(Δ={row['delta']:+.3f})"
            )
    if cal_stats["correlation"] < 0.5:
        print("  WARN: raw-to-HDI correlation is low; review domain coverage and indicator directions.")

    print("\nDone.")


if __name__ == "__main__":
    main()
