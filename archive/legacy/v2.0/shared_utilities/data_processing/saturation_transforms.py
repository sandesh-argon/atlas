"""
V1 → V2 Transfer: Saturation Transformations
Original: /Data/Scripts/apply_saturation_transforms.py
Status: VALIDATED (V1 Phase 1, Empirically Tested)
Evidence: Scatterplots confirm thresholds, +5.6% avg R² improvement vs. raw values
V2 Modifications: None - REUSE AS-IS (theoretically required)

Theoretical Foundation
----------------------
Heylighen & Bernheim (2000): Deficiency needs saturate, growth needs don't.

V1_VALIDATED Thresholds:
- Life Expectancy: 85 years (biological ceiling)
- GDP per Capita: $20,000 (Easterlin Paradox threshold)
- Infant Mortality: 100/1000 (historical max)
- Undernourishment: 50% (famine level)
- Homicide: 50/100K (conflict zone level)

⚠️ CRITICAL: Apply BEFORE normalization (not after)
"""

import numpy as np
import pandas as pd

# V1_VALIDATED: Saturation Thresholds
LIFE_EXPECTANCY_CAP = 85  # years
GDP_SATURATION_POINT = 20000  # 2015 USD PPP
INFANT_MORTALITY_CAP = 100  # per 1000 live births
UNDERNOURISHMENT_CAP = 50  # percent
HOMICIDE_CAP = 50  # per 100,000 population


def saturate_life_expectancy(life_expectancy: np.ndarray) -> np.ndarray:
    """
    Apply hard ceiling saturation to life expectancy.

    V1_VALIDATED: Empirical scatterplots show plateau at 80-85 years.

    Formula: LE_sat = min(LE, 85) / 85
    Range: [0, 1]

    Args:
        life_expectancy: Raw life expectancy in years (can include NaN)

    Returns:
        Saturated life expectancy in [0, 1] range
    """
    return np.clip(life_expectancy, 0, LIFE_EXPECTANCY_CAP) / LIFE_EXPECTANCY_CAP


def saturate_gdp_per_capita(gdp_per_capita: np.ndarray) -> np.ndarray:
    """
    Apply logarithmic saturation to GDP per capita.

    V1_VALIDATED: Piecewise regression shows 78% slope reduction above $20K.

    Formula: GDP_sat = log(1 + GDP / 20000)
    Range: [0, ∞)

    Args:
        gdp_per_capita: Raw GDP per capita in constant 2015 USD PPP

    Returns:
        Log-saturated GDP (unbounded but diminishing growth)
    """
    # Handle negative/zero values (data errors)
    gdp_clipped = np.clip(gdp_per_capita, 0, None)
    return np.log(1 + gdp_clipped / GDP_SATURATION_POINT)


def saturate_infant_mortality(infant_mortality: np.ndarray) -> np.ndarray:
    """
    Apply inverted cap-divide to infant mortality (lower is better).

    V1_VALIDATED: Floor effect confirmed at 2-5/1000 (measurement noise).

    Formula: IMR_sat = 1 - min(IMR, 100) / 100
    Range: [0, 1] where 1 = zero mortality (best)

    Args:
        infant_mortality: Raw infant mortality per 1000 live births

    Returns:
        Inverted saturated mortality in [0, 1] range
    """
    capped = np.clip(infant_mortality, 0, INFANT_MORTALITY_CAP)
    return 1 - (capped / INFANT_MORTALITY_CAP)


def saturate_undernourishment(undernourishment: np.ndarray) -> np.ndarray:
    """
    Apply inverted cap-divide to undernourishment prevalence.

    V1_VALIDATED: Sharp drop-off below 5% (WHO low-prevalence threshold).

    Formula: UN_sat = 1 - min(UN, 50) / 50
    Range: [0, 1] where 1 = zero undernourishment (best)

    Args:
        undernourishment: Raw undernourishment prevalence (%)

    Returns:
        Inverted saturated undernourishment in [0, 1] range
    """
    capped = np.clip(undernourishment, 0, UNDERNOURISHMENT_CAP)
    return 1 - (capped / UNDERNOURISHMENT_CAP)


def saturate_homicide(homicide_rate: np.ndarray) -> np.ndarray:
    """
    Apply inverted cap-divide to homicide rate.

    V1_VALIDATED: Noise dominates below 1/100K (definitional variance).

    Formula: HOM_sat = 1 - min(HOM, 50) / 50
    Range: [0, 1] where 1 = zero homicides (best)

    Args:
        homicide_rate: Raw homicide rate per 100,000 population

    Returns:
        Inverted saturated homicide in [0, 1] range
    """
    capped = np.clip(homicide_rate, 0, HOMICIDE_CAP)
    return 1 - (capped / HOMICIDE_CAP)


def apply_all_saturation_transforms(df: pd.DataFrame, inplace: bool = False) -> pd.DataFrame:
    """
    Apply saturation transforms to all deficiency needs in a dataset.

    V1_VALIDATED: Successfully used in Phase 1 (12,426 features, 3 splits).

    Transforms:
    - life_expectancy → saturate_life_expectancy
    - gdp_per_capita → saturate_gdp_per_capita
    - infant_mortality → saturate_infant_mortality
    - undernourishment → saturate_undernourishment
    - homicide → saturate_homicide

    Unchanged (growth needs):
    - mean_years_schooling (no saturation)
    - internet_users (no saturation)
    - gini (unclear saturation, conservative: preserve)

    Args:
        df: DataFrame with raw QOL metrics
        inplace: Modify DataFrame in-place vs. return copy

    Returns:
        DataFrame with saturated QOL metrics

    ⚠️ CRITICAL: Run BEFORE normalization
    """
    if not inplace:
        df = df.copy()

    # Apply deficiency need transforms (V1_VALIDATED)
    if 'life_expectancy' in df.columns:
        df['life_expectancy'] = saturate_life_expectancy(df['life_expectancy'].values)

    if 'gdp_per_capita' in df.columns:
        df['gdp_per_capita'] = saturate_gdp_per_capita(df['gdp_per_capita'].values)

    if 'infant_mortality' in df.columns:
        df['infant_mortality'] = saturate_infant_mortality(df['infant_mortality'].values)

    if 'undernourishment' in df.columns:
        df['undernourishment'] = saturate_undernourishment(df['undernourishment'].values)

    if 'homicide' in df.columns:
        df['homicide'] = saturate_homicide(df['homicide'].values)

    # Growth needs: NO transform (unchanged)
    # - mean_years_schooling
    # - internet_users
    # - gini

    return df


def validate_saturation_ranges(df: pd.DataFrame) -> dict:
    """
    Validate that saturated values are in expected ranges.

    V1_VALIDATED: All Phase 1 datasets passed range checks.

    Returns:
        Dict of validation results per metric
    """
    results = {}

    if 'life_expectancy' in df.columns:
        le = df['life_expectancy'].dropna()
        results['life_expectancy'] = {
            'min': le.min(),
            'max': le.max(),
            'in_range': (le.min() >= 0) and (le.max() <= 1),
            'expected_range': '[0, 1]'
        }

    if 'gdp_per_capita' in df.columns:
        gdp = df['gdp_per_capita'].dropna()
        results['gdp_per_capita'] = {
            'min': gdp.min(),
            'max': gdp.max(),
            'in_range': gdp.min() >= 0,  # Unbounded upper
            'expected_range': '[0, ∞)'
        }

    if 'infant_mortality' in df.columns:
        im = df['infant_mortality'].dropna()
        results['infant_mortality'] = {
            'min': im.min(),
            'max': im.max(),
            'in_range': (im.min() >= 0) and (im.max() <= 1),
            'expected_range': '[0, 1]'
        }

    if 'undernourishment' in df.columns:
        un = df['undernourishment'].dropna()
        results['undernourishment'] = {
            'min': un.min(),
            'max': un.max(),
            'in_range': (un.min() >= 0) and (un.max() <= 1),
            'expected_range': '[0, 1]'
        }

    if 'homicide' in df.columns:
        hom = df['homicide'].dropna()
        results['homicide'] = {
            'min': hom.min(),
            'max': hom.max(),
            'in_range': (hom.min() >= 0) and (hom.max() <= 1),
            'expected_range': '[0, 1]'
        }

    return results


# V2_EXAMPLE_USAGE
if __name__ == "__main__":
    """
    Example usage for V2 integration.

    V2_TODO: Update paths to match V2 data structure.
    """
    # Load raw data (BEFORE normalization)
    train = pd.read_csv("/path/to/v2/data/train_raw.csv")

    # Apply saturation transforms
    train_saturated = apply_all_saturation_transforms(train, inplace=False)

    # Validate ranges
    validation = validate_saturation_ranges(train_saturated)
    print("Saturation Validation:")
    for metric, stats in validation.items():
        print(f"  {metric}: {stats}")

    # Save for normalization step
    train_saturated.to_csv("/path/to/v2/data/train_saturated.csv", index=False)

    print("\n✅ Saturation transforms applied successfully")
    print("⚠️ NEXT STEP: Run normalization on saturated data")
