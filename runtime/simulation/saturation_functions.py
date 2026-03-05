"""
B1: Saturation Functions for Realistic Intervention Effects

Implements diminishing returns and hard caps to prevent unrealistic
simulation outputs (e.g., literacy > 100%, infinite GDP growth).

Three saturation types:
1. sigmoid_saturation: S-curve for GDP-like indicators
2. hard_cap_saturation: Hard limits for rates (0-100%)
3. linear_diminishing: Effectiveness drops after threshold
"""

import numpy as np
from typing import Callable, Optional


# =============================================================================
# SATURATION FUNCTIONS
# =============================================================================

def sigmoid_saturation(
    value: float,
    baseline: float,
    L: float = 100.0,
    k: float = 0.05,
    x0: Optional[float] = None
) -> float:
    """
    Sigmoid (logistic) saturation for GDP-like indicators.

    Models diminishing returns: growth slows as value approaches ceiling.

    Args:
        value: Current/proposed value
        baseline: Starting value before intervention
        L: Maximum possible value (ceiling)
        k: Steepness of curve (higher = sharper transition)
        x0: Midpoint of sigmoid (default: L/2)

    Returns:
        Saturated value, always < L

    Example:
        >>> sigmoid_saturation(95, baseline=50, L=100)
        94.26  # Growth dampened near ceiling
    """
    if x0 is None:
        x0 = L / 2

    # Logistic function: L / (1 + exp(-k(x - x0)))
    saturated = L / (1 + np.exp(-k * (value - x0)))

    # Ensure we don't go below baseline if value > baseline
    if value > baseline:
        return max(saturated, baseline)
    return min(saturated, baseline)


def hard_cap_saturation(
    value: float,
    baseline: float,
    min_val: float = 0.0,
    max_val: float = 100.0
) -> float:
    """
    Hard cap saturation for bounded rates (literacy, enrollment, etc.).

    Simply clips values to [min_val, max_val] range.

    Args:
        value: Current/proposed value
        baseline: Starting value (unused, for API consistency)
        min_val: Minimum allowed value (default: 0)
        max_val: Maximum allowed value (default: 100)

    Returns:
        Clipped value in [min_val, max_val]

    Example:
        >>> hard_cap_saturation(105, baseline=90, max_val=100)
        100.0
    """
    return float(np.clip(value, min_val, max_val))


def linear_diminishing_returns(
    value: float,
    baseline: float,
    threshold: float = 50.0,
    decay_rate: float = 0.5
) -> float:
    """
    Linear diminishing returns for spending-like indicators.

    Full effect below threshold, reduced effect above.

    Args:
        value: Current/proposed value
        baseline: Starting value
        threshold: Value above which returns diminish
        decay_rate: How much to reduce gains above threshold (0-1)

    Returns:
        Value with diminished returns applied

    Example:
        >>> linear_diminishing_returns(80, baseline=40, threshold=50, decay_rate=0.5)
        65.0  # Full gain to 50, then half gain from 50-80
    """
    if value <= threshold:
        return value

    # Full effect up to threshold
    base_gain = threshold - baseline if baseline < threshold else 0

    # Diminished effect above threshold
    excess = value - threshold
    diminished_excess = excess * decay_rate

    return threshold + diminished_excess


def floor_zero_saturation(
    value: float,
    baseline: float,
    **kwargs
) -> float:
    """
    Floor at zero for inherently non-negative quantities (GDP, population, etc.).

    Prevents simulation from producing negative values for indicators that
    cannot be negative by definition. No upper bound is applied — the ±2σ
    clamp handles runaway growth.

    Args:
        value: Current/proposed value
        baseline: Starting value (unused, for API consistency)

    Returns:
        max(0, value)
    """
    return max(0.0, value)


def no_saturation(value: float, baseline: float, **kwargs) -> float:
    """
    Identity function - no saturation applied.

    Use for indicators without natural bounds.
    """
    return value


# =============================================================================
# INDICATOR-SPECIFIC CONFIGURATION
# =============================================================================

# Mapping of indicator patterns to saturation functions and parameters
SATURATION_CONFIG = {
    # True percentage rates (0-100%) — match specific WDI prefixes
    'rate': {
        'function': hard_cap_saturation,
        'params': {'min_val': 0.0, 'max_val': 100.0},
        'patterns': [
            'SE.PRM.ENRR', 'SE.SEC.ENRR', 'SE.TER.ENRR',     # enrollment rates
            'SE.PRM.CMPT', 'SE.SEC.CMPT',                       # completion rates
            'SH.DYN.MORT', 'SH.DYN.NMRT', 'SP.DYN.CDRT',      # mortality rates per 1000
            'SP.DYN.TFRT',                                       # fertility rate
            'SH.STA.MMRT',                                       # maternal mortality
            'SH.H2O.', 'SH.STA.HYGN', 'SH.STA.BASS',          # WASH coverage %
        ]
    },

    # Life expectancy (hard cap 25-95)
    'life_expectancy': {
        'function': hard_cap_saturation,
        'params': {'min_val': 25.0, 'max_val': 95.0},
        'patterns': ['SP.DYN.LE00']
    },

    # V-Dem aggregate indices — normalized [0, 1]
    'vdem_index': {
        'function': hard_cap_saturation,
        'params': {'min_val': 0.0, 'max_val': 1.0},
        'patterns': [
            'v2x_polyarchy', 'v2x_libdem', 'v2x_partipdem', 'v2x_delibdem',
            'v2x_egaldem', 'v2x_liberal', 'v2x_cspart', 'v2x_rule',
            'v2x_freexp', 'v2x_frassoc', 'v2x_suffr', 'v2x_elecoff',
            'v2xel_frefair', 'v2xed_ed_', 'v2xpe_exl', 'v2xcl_rol',
            'e_v2x_',
        ]
    },

    # V-Dem ordinal responses (suffix _ord) — [0, 5] (some use 0-5 scale)
    'vdem_ordinal': {
        'function': hard_cap_saturation,
        'params': {'min_val': 0.0, 'max_val': 5.0},
        'patterns': ['_ord']  # suffix match
    },

    # V-Dem posterior means (suffix _mean) — [0, 4]
    'vdem_mean': {
        'function': hard_cap_saturation,
        'params': {'min_val': 0.0, 'max_val': 4.0},
        'patterns': ['_mean']  # suffix match
    },

    # V-Dem original-scale posteriors (suffix _osp) — [0, 4]
    'vdem_osp': {
        'function': hard_cap_saturation,
        'params': {'min_val': 0.0, 'max_val': 4.0},
        'patterns': ['_osp']  # suffix match
    },

    # V-Dem latent variables (Bayesian IRT) — [-4, 4]
    'vdem_latent': {
        'function': hard_cap_saturation,
        'params': {'min_val': -4.0, 'max_val': 4.0},
        'patterns': [
            'v2el', 'v2pe', 'v2cs', 'v2me', 'v2ju', 'v2lg',
            'v2cl', 'v2ex', 'v2ca', 'v2dl', 'v2dd', 'v2ed',
            'v2ps', 'v2sm', 'v2st', 'v2sv', 'v2reg'
        ]
    },

    # Polity scores — [-10, 10]
    'polity': {
        'function': hard_cap_saturation,
        'params': {'min_val': -10.0, 'max_val': 10.0},
        'patterns': ['e_polity']  # prefix match only
    },

    # Non-negative quantities — floor at 0, no ceiling (±2σ handles growth)
    # Only for indicators that CANNOT be negative by definition.
    # Excludes: growth rates (.ZG), net flows (BN.), net migration, balances.
    'non_negative': {
        'function': floor_zero_saturation,
        'params': {},
        'patterns': [
            # GDP levels (not growth rates)
            'NY.GDP.MKTP.CD', 'NY.GDP.MKTP.KD', 'NY.GDP.MKTP.PP',
            'NY.GDP.PCAP.CD', 'NY.GDP.PCAP.KD', 'NY.GDP.PCAP.PP',
            'NY.GNP.MKTP', 'NY.GNP.PCAP',
            # Value added
            'NV.AGR', 'NV.IND', 'NV.SRV',
            # Population (all counts are non-negative)
            'SP.POP',
            # Trade volumes (absolute, not net)
            'BX.GSR.GNFS', 'BM.GSR.GNFS',
            # Household and government consumption levels
            'NE.CON.PRVT', 'NE.CON.GOVT',
            # Human capital value
            'NW.HCA',
            # Produced capital
            'NW.PCA',
            # Total national wealth
            'NW.TOW',
            # School expectancy
            'SLE.',
            # Manufacturing output
            'NV.IND.MANF',
        ],
        # Exclude growth rates and other legitimately-negative derivatives
        'exclude_suffixes': ['.zg', '.zs'],
    }
}


def get_saturation_function(indicator: str) -> tuple[Callable, dict]:
    """
    Get appropriate saturation function for an indicator.

    Uses conservative prefix/suffix matching to avoid false positives.
    Indicators without an explicit match get no saturation — the ±2σ
    cumulative clamp in propagation_v31.py handles them safely.

    Args:
        indicator: Indicator ID/name

    Returns:
        (function, params) tuple
    """
    ind_lower = indicator.lower()

    for config_type, config in SATURATION_CONFIG.items():
        # Check exclusions first (e.g., .ZG growth rates excluded from non_negative)
        exclude_suffixes = config.get('exclude_suffixes', [])
        if any(ind_lower.endswith(s) for s in exclude_suffixes):
            continue

        for pattern in config['patterns']:
            pat_lower = pattern.lower()
            # Suffix patterns (V-Dem suffixes like _ord, _mean, _osp)
            if pat_lower.startswith('_'):
                if ind_lower.endswith(pat_lower):
                    return config['function'], config['params']
            # Prefix/startswith matching (everything else)
            else:
                if ind_lower.startswith(pat_lower):
                    return config['function'], config['params']

    # Default: no saturation (±2σ clamp in propagation handles bounds)
    return no_saturation, {}


def apply_saturation(
    indicator: str,
    value: float,
    baseline: float
) -> float:
    """
    Apply appropriate saturation to an indicator value.

    Args:
        indicator: Indicator ID
        value: Proposed new value
        baseline: Original value before intervention

    Returns:
        Saturated value
    """
    func, params = get_saturation_function(indicator)
    return func(value, baseline, **params)


# =============================================================================
# UNIT TESTS
# =============================================================================

def test_sigmoid_saturation():
    """Test sigmoid saturation behavior."""
    # Value near ceiling should be dampened
    result = sigmoid_saturation(95, baseline=50, L=100)
    assert 90 < result < 100, f"Expected ~94, got {result}"

    # Value at midpoint should be L/2
    result = sigmoid_saturation(50, baseline=0, L=100)
    assert 45 < result < 55, f"Expected ~50, got {result}"

    print("  sigmoid_saturation: PASS")


def test_hard_cap_saturation():
    """Test hard cap saturation."""
    # Above max
    assert hard_cap_saturation(105, baseline=90) == 100.0

    # Below min
    assert hard_cap_saturation(-5, baseline=10) == 0.0

    # Within range
    assert hard_cap_saturation(50, baseline=40) == 50.0

    print("  hard_cap_saturation: PASS")


def test_linear_diminishing():
    """Test linear diminishing returns."""
    # Below threshold - no change
    result = linear_diminishing_returns(40, baseline=30, threshold=50)
    assert result == 40, f"Expected 40, got {result}"

    # Above threshold - diminished
    result = linear_diminishing_returns(80, baseline=30, threshold=50, decay_rate=0.5)
    expected = 50 + (80 - 50) * 0.5  # 50 + 15 = 65
    assert abs(result - expected) < 0.01, f"Expected {expected}, got {result}"

    print("  linear_diminishing_returns: PASS")


def test_indicator_mapping():
    """Test indicator-to-function mapping."""
    # Rate indicator (prefix match)
    func, params = get_saturation_function('SE.PRM.ENRR')
    assert func == hard_cap_saturation
    assert params['max_val'] == 100.0

    # GDP indicator — now uses non-negative floor (can't go below 0)
    func, params = get_saturation_function('NY.GDP.PCAP.CD')
    assert func == floor_zero_saturation, f"GDP should use floor_zero, got {func.__name__}"

    # V-Dem aggregate index (explicit prefix)
    func, params = get_saturation_function('v2x_polyarchy')
    assert func == hard_cap_saturation
    assert params['max_val'] == 1.0

    # V-Dem ordinal (suffix match)
    func, params = get_saturation_function('v2clacjust_ord')
    assert func == hard_cap_saturation
    assert params['max_val'] == 5.0

    # Population indicator — should match non_negative (floor at 0)
    func, params = get_saturation_function('SP.POP.3539.FE')
    assert func == floor_zero_saturation, f"SP.POP should use floor_zero, got {func.__name__}"

    # GDP — should match non_negative (floor at 0)
    func, params = get_saturation_function('NY.GDP.PCAP.CD')
    assert func == floor_zero_saturation, f"GDP should use floor_zero, got {func.__name__}"

    # GDP growth rate — should NOT match (ends in .ZG, doesn't start with non-neg prefix)
    func, params = get_saturation_function('NY.GDP.MKTP.KD.ZG')
    assert func == no_saturation, "GDP growth rate can be negative"

    # Unknown indicator
    func, params = get_saturation_function('random_indicator_xyz')
    assert func == no_saturation

    print("  indicator_mapping: PASS")


def test_floor_zero_saturation():
    """Test floor-at-zero saturation for non-negative quantities."""
    # Positive value passes through
    assert floor_zero_saturation(50000, baseline=60000) == 50000

    # Negative value floored at 0
    assert floor_zero_saturation(-5000, baseline=60000) == 0.0

    # Zero passes through
    assert floor_zero_saturation(0, baseline=100) == 0.0

    print("  floor_zero_saturation: PASS")


def test_apply_saturation():
    """Test the main apply_saturation function."""
    # Enrollment rate capped at 100
    result = apply_saturation('SE.PRM.ENRR', 110, baseline=85)
    assert result == 100.0, f"Expected 100, got {result}"

    # Life expectancy capped at 95
    result = apply_saturation('SP.DYN.LE00.IN', 98, baseline=75)
    assert result == 95.0, f"Expected 95, got {result}"

    # GDP — floored at 0 (non-negative), positive passes through
    result = apply_saturation('NY.GDP.PCAP.CD', 150000, baseline=50000)
    assert result == 150000, f"Expected 150000, got {result}"

    # GDP — negative value floored at 0
    result = apply_saturation('NY.GDP.PCAP.CD', -5000, baseline=50000)
    assert result == 0.0, f"Expected 0 (non-negative floor), got {result}"

    # Population — floored at 0, positive passes through
    result = apply_saturation('SP.POP.TOTL', 330000000, baseline=320000000)
    assert result == 330000000, f"Population should pass through, got {result}"

    # Population — negative floored at 0
    result = apply_saturation('SP.POP.TOTL', -100, baseline=1000000)
    assert result == 0.0, f"Population should be floored at 0, got {result}"

    print("  apply_saturation: PASS")


def run_all_tests():
    """Run all unit tests."""
    print("\nRunning saturation function tests...")
    print("-" * 40)

    test_sigmoid_saturation()
    test_hard_cap_saturation()
    test_linear_diminishing()
    test_floor_zero_saturation()
    test_indicator_mapping()
    test_apply_saturation()

    print("-" * 40)
    print("✅ All saturation tests PASSED\n")


if __name__ == "__main__":
    run_all_tests()
