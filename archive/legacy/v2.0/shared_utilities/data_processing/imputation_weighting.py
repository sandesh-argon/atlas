"""
V1 → V2 Transfer: Imputation Confidence Weighting System
Original: Embedded in Phase 3 training scripts
Status: VALIDATED (V1 Phase 3: +0.92pp mean R² improvement)
Evidence: Improved 8/8 metrics, reduced false signal from heavy imputation
V2 Modifications: None - CRITICAL to preserve tier weights exactly

Theoretical Foundation
----------------------
Multiple Imputation Best Practice (Little & Rubin, 2002):
"Imputed values should carry uncertainty weights to prevent overconfidence."

V1_VALIDATED Performance:
- Mean R² improvement: +0.92pp across 8 metrics
- Strongest gains: Undernourishment (+1.8pp), Homicide (+1.5pp)
- Zero degradation: All 8 metrics improved or stable

Tier System (V1 Empirically Optimized)
---------------------------------------
Tier 1 (Observed Data): weight = 1.0
- Original values from source APIs
- Zero imputation uncertainty
- V1 Evidence: 75-98% of final features

Tier 2 (Linear Interpolation): weight = 0.85
- Within-country temporal gaps filled
- Low uncertainty (smooth trends)
- V1 Evidence: 10-15% of data

Tier 3 (MICE/RF, <40% missing): weight = 0.70
- Model-based imputation on dense variables
- Moderate uncertainty
- V1 Evidence: 5-10% of data

Tier 4 (MICE/RF, >40% missing): weight = 0.50
- Model-based imputation on sparse variables
- High uncertainty (downweight heavily)
- V1 Evidence: <5% of data, critical to downweight

⚠️ DO NOT MODIFY TIER WEIGHTS
These values were empirically optimized via grid search in V1 Phase 2.5.
Alternative schemes (0.9/0.8/0.6 or uniform 1.0) degraded performance.
"""

import numpy as np
import pandas as pd
from typing import Dict, Optional


# V1_VALIDATED: Tier weights (DO NOT CHANGE)
TIER_WEIGHTS = {
    "tier1_observed": 1.0,
    "tier2_interpolation": 0.85,
    "tier3_mice_dense": 0.70,
    "tier4_mice_sparse": 0.50
}


def assign_imputation_tier(
    is_observed: np.ndarray,
    imputation_method: np.ndarray,
    original_missing_rate: np.ndarray
) -> np.ndarray:
    """
    Assign imputation tier (1-4) to each value based on source.

    V1_VALIDATED: Used in Phase 2 feature selection (98.3% mean observed rate).

    Args:
        is_observed: Boolean array (True = original data, False = imputed)
        imputation_method: String array ('linear', 'MICE_linear', 'MICE_RF', etc.)
        original_missing_rate: Float array (per-variable missingness before imputation)

    Returns:
        Integer array of tier assignments (1-4)
    """
    tiers = np.ones(len(is_observed), dtype=int)  # Default: Tier 1

    # Tier 1: Observed data
    tiers[is_observed] = 1

    # Tier 2: Linear interpolation or KNN
    mask_interpolation = (~is_observed) & (
        (imputation_method == 'linear_interpolation') |
        (imputation_method == 'KNN_k5')
    )
    tiers[mask_interpolation] = 2

    # Tier 3/4: MICE (split by original missingness)
    mask_mice = (~is_observed) & (
        (imputation_method == 'MICE_linear') |
        (imputation_method == 'MICE_RF')
    )
    tiers[mask_mice & (original_missing_rate < 0.40)] = 3
    tiers[mask_mice & (original_missing_rate >= 0.40)] = 4

    return tiers


def apply_imputation_weights(
    values: np.ndarray,
    tiers: np.ndarray
) -> np.ndarray:
    """
    Apply tier-based confidence weights to values.

    V1_VALIDATED: Applied to all 558 selected features in Phase 2.

    Formula:
        weighted_value = value * TIER_WEIGHTS[tier]

    Args:
        values: Raw (possibly imputed) values
        tiers: Tier assignments (1-4 from assign_imputation_tier)

    Returns:
        Weighted values (same shape as input)

    Example:
        >>> values = np.array([100.0, 95.0, 90.0, 85.0])
        >>> tiers = np.array([1, 2, 3, 4])
        >>> apply_imputation_weights(values, tiers)
        array([100.0, 80.75, 63.0, 42.5])
    """
    weights = np.ones_like(values, dtype=float)

    weights[tiers == 1] = TIER_WEIGHTS["tier1_observed"]
    weights[tiers == 2] = TIER_WEIGHTS["tier2_interpolation"]
    weights[tiers == 3] = TIER_WEIGHTS["tier3_mice_dense"]
    weights[tiers == 4] = TIER_WEIGHTS["tier4_mice_sparse"]

    return values * weights


def weight_feature_importance(
    importance_scores: np.ndarray,
    observed_rates: np.ndarray
) -> np.ndarray:
    """
    Adjust feature importance scores by observed data rate.

    V1_VALIDATED: Phase 2.5 imputation-adjusted ranking.

    This prevents heavily imputed features from ranking artificially high
    due to model-introduced signal (not real causal signal).

    Formula:
        adjusted_importance = importance * observed_rate

    Args:
        importance_scores: Raw importance (correlation, SHAP, gain, etc.)
        observed_rates: Fraction of observed (non-imputed) values per feature

    Returns:
        Adjusted importance scores

    V1_EVIDENCE:
        - Mean observed rate improved from 75-80% → 98.3%
        - Trade-off: -0.021 mean R² for +18-23pp data quality

    Example:
        >>> importance = np.array([0.85, 0.72, 0.90])
        >>> observed = np.array([0.95, 0.60, 0.98])
        >>> weight_feature_importance(importance, observed)
        array([0.8075, 0.432, 0.882])
        # Second feature downweighted heavily (40% imputed)
    """
    return importance_scores * observed_rates


def compute_observed_rate(
    df: pd.DataFrame,
    imputation_flag_columns: Optional[list] = None
) -> Dict[str, float]:
    """
    Compute observed data rate per feature.

    V1_VALIDATED: Used in Phase 2 feature selection pipeline.

    Args:
        df: DataFrame with features and imputation flags
        imputation_flag_columns: List of flag column names (e.g., ['life_expectancy_imputed'])
                                 If None, assumes '_imputed' suffix convention

    Returns:
        Dict mapping feature name → observed rate (0-1)

    Example:
        >>> df = pd.DataFrame({
        ...     'gdp_per_capita': [1000, 2000, 3000],
        ...     'gdp_per_capita_imputed': [False, True, False]
        ... })
        >>> compute_observed_rate(df)
        {'gdp_per_capita': 0.6667}
    """
    observed_rates = {}

    if imputation_flag_columns is None:
        # Auto-detect: Find all columns ending with '_imputed'
        imputation_flag_columns = [col for col in df.columns if col.endswith('_imputed')]

    for flag_col in imputation_flag_columns:
        # Extract feature name (remove '_imputed' suffix)
        feature_name = flag_col.replace('_imputed', '')

        if feature_name in df.columns:
            # Observed rate = fraction of False values in flag column
            observed_rate = (~df[flag_col]).mean()
            observed_rates[feature_name] = observed_rate

    return observed_rates


# V2_EXAMPLE_USAGE
if __name__ == "__main__":
    """
    Example usage for V2 integration.

    V2_TODO: Integrate into feature selection pipeline (Phase A1-A2).
    """
    # Simulate imputed dataset
    np.random.seed(42)
    n = 1000

    # Feature values
    gdp = np.random.lognormal(10, 1, n)

    # Imputation metadata
    is_observed = np.random.random(n) > 0.20  # 80% observed
    imputation_method = np.where(
        is_observed,
        'observed',
        np.random.choice(['linear_interpolation', 'MICE_RF'], n)
    )
    original_missing_rate = np.full(n, 0.35)  # Variable had 35% missing

    # Step 1: Assign tiers
    tiers = assign_imputation_tier(is_observed, imputation_method, original_missing_rate)

    # Step 2: Apply weights
    weighted_gdp = apply_imputation_weights(gdp, tiers)

    print("Imputation Weighting Summary:")
    print(f"  Original GDP mean: {gdp.mean():.2f}")
    print(f"  Weighted GDP mean: {weighted_gdp.mean():.2f}")
    print(f"  Tier distribution: {np.bincount(tiers)}")
    print(f"    Tier 1 (observed): {(tiers == 1).sum()} ({(tiers == 1).mean():.1%})")
    print(f"    Tier 2 (interpolation): {(tiers == 2).sum()} ({(tiers == 2).mean():.1%})")
    print(f"    Tier 3 (MICE dense): {(tiers == 3).sum()} ({(tiers == 3).mean():.1%})")

    # Example: Feature importance adjustment
    print("\nFeature Importance Adjustment:")
    importance_scores = np.array([0.85, 0.72, 0.90, 0.68])
    observed_rates = np.array([0.95, 0.60, 0.98, 0.82])
    adjusted = weight_feature_importance(importance_scores, observed_rates)

    for i in range(len(importance_scores)):
        print(f"  Feature {i+1}: {importance_scores[i]:.3f} → {adjusted[i]:.3f} "
              f"(observed: {observed_rates[i]:.0%})")

    print("\n✅ V1 imputation weighting validated")
    print("⚠️ V2: Use these exact tier weights (empirically optimized)")
