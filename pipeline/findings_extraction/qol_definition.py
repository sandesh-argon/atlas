"""
Quality of Life (QoL) Composite Score Definition

Pure computation module for building a HDI-calibrated QoL composite
from leaf-level indicator values. All core functions are pure (no I/O);
only `load_indicator_metadata()` reads files.

Score pipeline:
  raw values → z-score normalize (flip negatives) → domain means → overall mean → HDI calibration

DEFINITION_ID tracks the scoring version so cached scores can be invalidated
when the methodology changes.
"""

import csv
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, TypedDict


DEFINITION_ID = "qol_v1_hdi_calibrated"


class IndicatorMeta(TypedDict):
    domain: str
    direction: str  # 'positive' | 'negative'


class NormStats(TypedDict):
    mean: float
    std: float
    n: int


class QoLResult(TypedDict):
    raw: float
    calibrated: float
    n_indicators: int
    n_domains: int


def _aggregate_domain_score(
    domain_means_map: Dict[str, float],
    domain_weights: Optional[Dict[str, float]] = None,
) -> float:
    """
    Aggregate domain means into a single raw QoL value.
    """
    if not domain_means_map:
        raise ValueError("domain_means_map cannot be empty")

    if domain_weights:
        weighted_terms = []
        weight_total = 0.0
        for domain, mean_value in domain_means_map.items():
            w = float(domain_weights.get(domain, 0.0))
            if w <= 0:
                continue
            weighted_terms.append(w * mean_value)
            weight_total += w
        if weight_total > 0:
            return sum(weighted_terms) / weight_total

    return sum(domain_means_map.values()) / len(domain_means_map)


def compute_domain_means(
    indicator_values: Dict[str, float],
    metadata: Dict[str, IndicatorMeta],
    norm_stats: Dict[str, NormStats],
    direction_overrides: Optional[Dict[str, str]] = None,
    z_clip: Optional[float] = None,
    min_indicators_per_domain: int = 1,
) -> Optional[Tuple[Dict[str, float], int]]:
    """
    Compute per-domain normalized means from raw indicator values.

    Returns:
        ({domain: mean_z, ...}, n_indicators_used) or None when fewer than
        3 domains pass `min_indicators_per_domain`.
    """
    domain_scores: Dict[str, List[float]] = {}
    n_indicators = 0

    for ind_id, value in indicator_values.items():
        meta = metadata.get(ind_id)
        if meta is None:
            continue

        if value is None or (isinstance(value, float) and math.isnan(value)):
            continue

        normalized = normalize_indicator(float(value), ind_id, norm_stats, metadata, direction_overrides)
        if normalized is None:
            continue

        if z_clip is not None:
            normalized = max(-z_clip, min(z_clip, normalized))

        domain = meta["domain"]
        domain_scores.setdefault(domain, []).append(normalized)
        n_indicators += 1

    filtered_domain_means = {
        domain: (sum(scores) / len(scores))
        for domain, scores in domain_scores.items()
        if len(scores) >= min_indicators_per_domain
    }

    if len(filtered_domain_means) < 3:
        return None

    return filtered_domain_means, n_indicators


# ---------------------------------------------------------------------------
# I/O — the only function that touches the filesystem
# ---------------------------------------------------------------------------

def load_indicator_metadata(
    nodes_csv_path: str | Path,
    properties_json_path: str | Path,
) -> Dict[str, IndicatorMeta]:
    """
    Build indicator metadata by joining v21_nodes.csv (domain) with
    indicator_properties.json (direction).

    Only layer-5 nodes are included (leaf indicators with real data).

    Returns:
        { indicator_id: { domain: str, direction: 'positive'|'negative' } }
    """
    # Read nodes CSV for layer-5 indicator IDs and their domains
    layer5_domain: Dict[str, str] = {}
    with open(nodes_csv_path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["layer"] == "5":
                layer5_domain[row["id"]] = row["domain"]

    # Read indicator_properties.json for direction
    with open(properties_json_path) as f:
        props = json.load(f)

    indicators_props: Dict[str, dict] = props.get("indicators", {})

    result: Dict[str, IndicatorMeta] = {}
    for ind_id, domain in layer5_domain.items():
        prop = indicators_props.get(ind_id, {})
        direction = prop.get("direction", "positive")
        if direction not in ("positive", "negative"):
            direction = "positive"
        result[ind_id] = {"domain": domain, "direction": direction}

    return result


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------

def compute_normalization_stats(
    all_baselines: Dict[str, Dict[str, Dict[str, float]]],
) -> Dict[str, NormStats]:
    """
    Compute per-indicator mean and std across all country-years using
    Welford's online algorithm (numerically stable single-pass).

    Args:
        all_baselines: { country: { year: { indicator_id: value } } }

    Returns:
        { indicator_id: { mean, std, n } }
    """
    count: Dict[str, int] = {}
    mean_acc: Dict[str, float] = {}
    m2_acc: Dict[str, float] = {}

    for country_years in all_baselines.values():
        for year_values in country_years.values():
            for ind_id, value in year_values.items():
                if value is None or (isinstance(value, float) and math.isnan(value)):
                    continue
                val = float(value)
                n = count.get(ind_id, 0) + 1
                count[ind_id] = n
                old_mean = mean_acc.get(ind_id, 0.0)
                new_mean = old_mean + (val - old_mean) / n
                mean_acc[ind_id] = new_mean
                m2_acc[ind_id] = m2_acc.get(ind_id, 0.0) + (val - old_mean) * (val - new_mean)

    result: Dict[str, NormStats] = {}
    for ind_id, n in count.items():
        if n < 2:
            continue
        std = math.sqrt(m2_acc[ind_id] / (n - 1))
        if std < 1e-12:
            continue
        result[ind_id] = {"mean": mean_acc[ind_id], "std": std, "n": n}

    return result


def normalize_indicator(
    value: float,
    indicator_id: str,
    norm_stats: Dict[str, NormStats],
    metadata: Dict[str, IndicatorMeta],
    direction_overrides: Optional[Dict[str, str]] = None,
) -> Optional[float]:
    """
    Z-score normalize a single indicator value, inverting sign for
    negative-direction indicators so that higher = better for all.

    If direction_overrides is provided, it takes precedence over metadata
    direction labels. This allows using empirically-determined directions
    (e.g., from HDI correlation analysis).

    Returns None if the indicator has no normalization stats.
    """
    stats = norm_stats.get(indicator_id)
    if stats is None:
        return None

    z = (value - stats["mean"]) / stats["std"]

    # Check override first, then metadata
    direction = None
    if direction_overrides is not None:
        direction = direction_overrides.get(indicator_id)
    if direction is None:
        meta = metadata.get(indicator_id)
        if meta is not None:
            direction = meta["direction"]

    if direction == "negative":
        z = -z

    return z


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

def compute_raw_qol(
    indicator_values: Dict[str, float],
    metadata: Dict[str, IndicatorMeta],
    norm_stats: Dict[str, NormStats],
    direction_overrides: Optional[Dict[str, str]] = None,
    domain_weights: Optional[Dict[str, float]] = None,
    z_clip: Optional[float] = None,
    min_indicators_per_domain: int = 1,
) -> Optional[Tuple[float, int, int]]:
    """
    Compute raw (uncalibrated) QoL score from indicator values.

    Steps:
      1. Normalize each indicator (z-score, sign-flipped for negatives)
      2. Group by domain, take mean per domain
      3. Take equal-weighted mean across domains

    Requires >= 3 domains with at least one indicator each, else returns None.

    Returns:
        (raw_qol, n_indicators, n_domains) or None
    """
    computed = compute_domain_means(
        indicator_values=indicator_values,
        metadata=metadata,
        norm_stats=norm_stats,
        direction_overrides=direction_overrides,
        z_clip=z_clip,
        min_indicators_per_domain=min_indicators_per_domain,
    )
    if computed is None:
        return None

    domain_means_map, n_indicators = computed
    raw_qol = _aggregate_domain_score(domain_means_map, domain_weights)

    return raw_qol, n_indicators, len(domain_means_map)


# ---------------------------------------------------------------------------
# HDI calibration
# ---------------------------------------------------------------------------

def apply_hdi_calibration(
    raw_qol: float,
    calibration: Dict[str, List[float]],
) -> float:
    """
    Monotonic piecewise-linear mapping from raw_qol to 0-1 HDI-like scale.

    calibration = {
        "breakpoints": [raw_1, raw_2, ...],   # sorted ascending
        "hdi_values":  [hdi_1, hdi_2, ...],    # corresponding HDI values
    }

    Values outside the breakpoint range are clamped to the nearest endpoint.
    """
    breakpoints = calibration["breakpoints"]
    hdi_values = calibration["hdi_values"]

    if len(breakpoints) < 2 or len(breakpoints) != len(hdi_values):
        raise ValueError(
            f"Calibration requires >= 2 matching breakpoints/hdi_values, "
            f"got {len(breakpoints)}/{len(hdi_values)}"
        )

    # Clamp to range
    if raw_qol <= breakpoints[0]:
        return float(hdi_values[0])
    if raw_qol >= breakpoints[-1]:
        return float(hdi_values[-1])

    # Find the segment
    for i in range(len(breakpoints) - 1):
        if breakpoints[i] <= raw_qol <= breakpoints[i + 1]:
            t = (raw_qol - breakpoints[i]) / (breakpoints[i + 1] - breakpoints[i])
            return float(hdi_values[i] + t * (hdi_values[i + 1] - hdi_values[i]))

    # Fallback (should not reach here)
    return float(hdi_values[-1])


def _build_residual_feature_vector(
    base_calibrated: float,
    domain_means: Dict[str, float],
    n_indicators: int,
    n_domains: int,
    residual_model: Dict[str, Any],
) -> Optional[List[float]]:
    """
    Build feature vector for residual correction model from calibration metadata.
    """
    feature_names = residual_model.get("feature_names")
    if not isinstance(feature_names, list) or not feature_names:
        return None

    feature_fill = residual_model.get("feature_fill", [])
    vector: List[float] = []
    for idx, name in enumerate(feature_names):
        value: Optional[float]
        if name == "base_calibrated":
            value = float(base_calibrated)
        elif isinstance(name, str) and name.startswith("domain:"):
            domain = name.split(":", 1)[1]
            raw_value = domain_means.get(domain)
            value = float(raw_value) if raw_value is not None else None
        elif name == "n_indicators":
            value = float(n_indicators)
        elif name == "n_domains":
            value = float(n_domains)
        else:
            value = None

        if value is None or not math.isfinite(value):
            fill_value = 0.0
            if isinstance(feature_fill, list) and idx < len(feature_fill):
                try:
                    fill_value = float(feature_fill[idx])
                except (TypeError, ValueError):
                    fill_value = 0.0
            value = fill_value

        vector.append(float(value))

    return vector


def predict_residual_correction(
    base_calibrated: float,
    domain_means: Dict[str, float],
    n_indicators: int,
    n_domains: int,
    residual_model: Dict[str, Any],
) -> Optional[float]:
    """
    Predict additive residual correction using a serialized KNN model.
    """
    if residual_model.get("type") != "knn_gaussian_v1":
        return None

    vector = _build_residual_feature_vector(
        base_calibrated=base_calibrated,
        domain_means=domain_means,
        n_indicators=n_indicators,
        n_domains=n_domains,
        residual_model=residual_model,
    )
    if vector is None:
        return None

    feature_mean = residual_model.get("feature_mean")
    feature_std = residual_model.get("feature_std")
    train_features = residual_model.get("train_features_scaled")
    train_residuals = residual_model.get("train_residuals")
    if (
        not isinstance(feature_mean, list)
        or not isinstance(feature_std, list)
        or not isinstance(train_features, list)
        or not isinstance(train_residuals, list)
        or not train_features
        or len(train_features) != len(train_residuals)
        or len(feature_mean) != len(vector)
        or len(feature_std) != len(vector)
    ):
        return None

    # Standardize request feature vector.
    scaled = []
    for value, mu, std in zip(vector, feature_mean, feature_std):
        try:
            mu_f = float(mu)
            std_f = float(std)
            value_f = float(value)
        except (TypeError, ValueError):
            return None
        if not math.isfinite(mu_f) or not math.isfinite(std_f) or std_f <= 0:
            return None
        scaled.append((value_f - mu_f) / std_f)

    try:
        k = int(residual_model.get("k", 8))
    except (TypeError, ValueError):
        k = 8
    try:
        bandwidth = float(residual_model.get("bandwidth", 1.0))
    except (TypeError, ValueError):
        bandwidth = 1.0
    if bandwidth <= 0:
        bandwidth = 1.0
    k = max(1, min(k, len(train_features)))
    denom = 2.0 * (bandwidth ** 2)

    # Brute-force nearest-neighbor search over serialized training rows.
    distances: List[Tuple[float, int]] = []
    for idx, train_vec in enumerate(train_features):
        if not isinstance(train_vec, list) or len(train_vec) != len(scaled):
            continue
        d2 = 0.0
        valid = True
        for a, b in zip(scaled, train_vec):
            try:
                b_f = float(b)
            except (TypeError, ValueError):
                valid = False
                break
            diff = a - b_f
            d2 += diff * diff
        if valid:
            distances.append((d2, idx))

    if not distances:
        return None

    distances.sort(key=lambda item: item[0])
    nearest = distances[:k]

    weighted_sum = 0.0
    weight_total = 0.0
    for d2, idx in nearest:
        try:
            residual = float(train_residuals[idx])
        except (TypeError, ValueError):
            continue
        weight = math.exp(-d2 / denom) if denom > 0 else 1.0
        weighted_sum += weight * residual
        weight_total += weight

    if weight_total <= 1e-12:
        try:
            fallback = float(residual_model.get("global_mean_residual", 0.0))
        except (TypeError, ValueError):
            fallback = 0.0
        correction = fallback
    else:
        correction = weighted_sum / weight_total

    try:
        residual_clip = float(residual_model.get("residual_clip", 0.2))
    except (TypeError, ValueError):
        residual_clip = 0.2
    residual_clip = max(0.0, residual_clip)
    correction = max(-residual_clip, min(residual_clip, correction))
    return correction


def apply_qol_calibration(
    raw_qol: float,
    calibration: Dict[str, object],
    domain_means: Optional[Dict[str, float]] = None,
    n_indicators: Optional[int] = None,
    n_domains: Optional[int] = None,
) -> float:
    """
    Apply primary HDI calibration plus optional residual correction.
    """
    base_calibrated = apply_hdi_calibration(raw_qol, calibration)  # type: ignore[arg-type]

    residual_model = calibration.get("residual_model")
    if (
        isinstance(residual_model, dict)
        and domain_means is not None
        and n_indicators is not None
        and n_domains is not None
    ):
        correction = predict_residual_correction(
            base_calibrated=base_calibrated,
            domain_means=domain_means,
            n_indicators=n_indicators,
            n_domains=n_domains,
            residual_model=residual_model,
        )
        if correction is not None:
            base_calibrated += correction

    return max(0.0, min(1.0, float(base_calibrated)))


# ---------------------------------------------------------------------------
# Full pipeline
# ---------------------------------------------------------------------------

def compute_qol(
    indicator_values: Dict[str, float],
    metadata: Dict[str, IndicatorMeta],
    norm_stats: Dict[str, NormStats],
    calibration: Dict[str, object],
    direction_overrides: Optional[Dict[str, str]] = None,
) -> Optional[QoLResult]:
    """
    Full QoL pipeline: normalize → aggregate by domain → calibrate to 0-1.

    Returns:
        { raw, calibrated, n_indicators, n_domains } or None if insufficient data.
    """
    domain_weights = calibration.get("domain_weights") if isinstance(calibration.get("domain_weights"), dict) else None
    z_clip = calibration.get("z_clip")
    if z_clip is not None:
        try:
            z_clip = float(z_clip)
        except (TypeError, ValueError):
            z_clip = None
    min_indicators_per_domain = calibration.get("min_indicators_per_domain", 1)
    try:
        min_indicators_per_domain = int(min_indicators_per_domain)
    except (TypeError, ValueError):
        min_indicators_per_domain = 1

    computed = compute_domain_means(
        indicator_values=indicator_values,
        metadata=metadata,
        norm_stats=norm_stats,
        direction_overrides=direction_overrides,
        z_clip=z_clip,
        min_indicators_per_domain=min_indicators_per_domain,
    )
    if computed is None:
        return None

    domain_means_map, n_indicators = computed
    n_domains = len(domain_means_map)
    raw_qol = _aggregate_domain_score(
        domain_means_map,
        domain_weights=domain_weights,  # type: ignore[arg-type]
    )
    calibrated = apply_qol_calibration(
        raw_qol=raw_qol,
        calibration=calibration,
        domain_means=domain_means_map,
        n_indicators=n_indicators,
        n_domains=n_domains,
    )

    return {
        "raw": raw_qol,
        "calibrated": calibrated,
        "n_indicators": n_indicators,
        "n_domains": n_domains,
    }
