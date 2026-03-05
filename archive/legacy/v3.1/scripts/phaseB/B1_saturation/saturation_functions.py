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
    # Hard-capped rates (0-100%)
    'rate': {
        'function': hard_cap_saturation,
        'params': {'min_val': 0.0, 'max_val': 100.0},
        'patterns': [
            'literacy', 'enrollment', 'completion', 'attendance',
            'coverage', 'rate', 'ratio', 'percent', 'pct',
            'SE.', 'SH.', 'SP.POP', 'mortality', 'fertility'
        ]
    },

    # GDP and income indicators (sigmoid)
    'gdp': {
        'function': sigmoid_saturation,
        'params': {'L': 200000, 'k': 0.00005},  # $200k ceiling
        'patterns': [
            'gdp', 'GDP', 'income', 'gni', 'GNI', 'NY.GDP', 'NY.GNP'
        ]
    },

    # Life expectancy (hard cap at ~90)
    'life_expectancy': {
        'function': hard_cap_saturation,
        'params': {'min_val': 0.0, 'max_val': 90.0},
        'patterns': [
            'life_expectancy', 'SP.DYN.LE', 'life expectancy'
        ]
    },

    # Spending indicators (diminishing returns)
    'spending': {
        'function': linear_diminishing_returns,
        'params': {'threshold': 5000, 'decay_rate': 0.3},
        'patterns': [
            'expenditure', 'spending', 'health_exp', 'edu_exp',
            'SH.XPD', 'SE.XPD', 'per_capita'
        ]
    },

    # Index scores (0-1 or 0-10)
    'index': {
        'function': hard_cap_saturation,
        'params': {'min_val': 0.0, 'max_val': 1.0},
        'patterns': [
            'index', 'score', 'v2x_', 'e_v2x_', 'hdi', 'HDI'
        ]
    },

    # V-Dem indices (typically -5 to 5 or 0 to 1)
    'vdem': {
        'function': hard_cap_saturation,
        'params': {'min_val': -5.0, 'max_val': 5.0},
        'patterns': [
            'v2', 'e_polity', 'polity'
        ]
    }
}


def get_saturation_function(indicator: str) -> tuple[Callable, dict]:
    """
    Get appropriate saturation function for an indicator.

    Args:
        indicator: Indicator ID/name

    Returns:
        (function, params) tuple

    Example:
        >>> func, params = get_saturation_function('SE.PRM.ENRR')
        >>> func(105, baseline=90, **params)
        100.0
    """
    indicator_lower = indicator.lower()

    for config_type, config in SATURATION_CONFIG.items():
        for pattern in config['patterns']:
            if pattern.lower() in indicator_lower:
                return config['function'], config['params']

    # Default: no saturation
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
    # Rate indicator
    func, params = get_saturation_function('SE.PRM.ENRR')
    assert func == hard_cap_saturation
    assert params['max_val'] == 100.0

    # GDP indicator
    func, params = get_saturation_function('NY.GDP.PCAP.CD')
    assert func == sigmoid_saturation

    # V-Dem indicator
    func, params = get_saturation_function('v2x_polyarchy')
    assert func == hard_cap_saturation

    # Unknown indicator
    func, params = get_saturation_function('random_indicator_xyz')
    assert func == no_saturation

    print("  indicator_mapping: PASS")


def test_apply_saturation():
    """Test the main apply_saturation function."""
    # Literacy rate capped at 100
    result = apply_saturation('literacy_rate', 110, baseline=85)
    assert result == 100.0, f"Expected 100, got {result}"

    # GDP saturated
    result = apply_saturation('NY.GDP.PCAP.CD', 150000, baseline=50000)
    assert result < 200000, f"Expected <200000, got {result}"

    print("  apply_saturation: PASS")


def run_all_tests():
    """Run all unit tests."""
    print("\nRunning saturation function tests...")
    print("-" * 40)

    test_sigmoid_saturation()
    test_hard_cap_saturation()
    test_linear_diminishing()
    test_indicator_mapping()
    test_apply_saturation()

    print("-" * 40)
    print("✅ All saturation tests PASSED\n")


if __name__ == "__main__":
    run_all_tests()
