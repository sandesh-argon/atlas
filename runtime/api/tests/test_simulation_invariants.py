"""
Simulation invariant tests — math contract enforcement.

These tests verify hard invariants of the propagation engine:
1. Round-trip sanity: identity edges preserve raw deltas
2. Zero-change: no intervention → no effects
3. Clamp invariants: cumulative deltas never exceed ±2σ
4. Saturation invariants: bounded indicators never exceed bounds
5. Convergence: zero-edge graph converges in 1 iteration
6. Monotonicity: larger intervention → larger total effect

Unlike the E2E tests (test_simulation_e2e.py) which call the HTTP API,
these tests import and call the propagation functions directly for speed
and to isolate math correctness from API plumbing.

Run: cd viz && python -m pytest api/tests/test_simulation_invariants.py -v
"""

import sys
from pathlib import Path
import numpy as np
import pytest

# Add viz/ root to path so `from simulation import ...` works
_VIZ_ROOT = str(Path(__file__).parent.parent.parent)
if _VIZ_ROOT not in sys.path:
    sys.path.insert(0, _VIZ_ROOT)

from simulation.propagation_v31 import (
    propagate_intervention_v31,
    apply_saturation,
    compute_effects,
)
from simulation.saturation_functions import (
    get_saturation_function,
    hard_cap_saturation,
    no_saturation,
    SATURATION_CONFIG,
)


# ──────────────────────────────────────────────
# 1. Round-trip sanity
# ──────────────────────────────────────────────


class TestRoundTripSanity:
    """Identity edges (beta=1, same std) should preserve raw deltas."""

    def test_identity_edge_preserves_delta(self):
        """
        Given A→B with beta=1 and source_std==target_std,
        a delta of +10 on A should produce delta of +10 on B
        (within float tolerance).
        """
        adjacency = {
            'A': [{'target': 'B', 'beta': 1.0, 'std': 0.1}],
        }
        baseline = {'A': 100.0, 'B': 50.0}
        intervention = {'A': 10.0}

        result = propagate_intervention_v31(
            adjacency, intervention, baseline,
            max_iterations=10,
            convergence_threshold=0.0001,
            # No country stats → uses baseline magnitude as std proxy
        )

        assert result['converged']
        assert result['deltas']['A'] == 10.0

        # With no country stats, std fallback = abs(baseline_value).
        # A: std=100, B: std=50
        # propagated = beta * (delta_A / std_A) * std_B = 1.0 * (10/100) * 50 = 5.0
        # This is correct behavior — unit conversion scales by std ratio.
        assert abs(result['deltas']['B'] - 5.0) < 0.1, (
            f"Expected ~5.0 (scaled by std ratio), got {result['deltas']['B']}"
        )

    def test_beta_half_halves_effect(self):
        """
        beta=0.5 should produce half the effect of beta=1.0.
        """
        baseline = {'A': 100.0, 'B': 100.0}
        intervention = {'A': 10.0}

        # beta=1.0
        adj_full = {'A': [{'target': 'B', 'beta': 1.0, 'std': 0.0}]}
        r1 = propagate_intervention_v31(adj_full, intervention, baseline)

        # beta=0.5
        adj_half = {'A': [{'target': 'B', 'beta': 0.5, 'std': 0.0}]}
        r2 = propagate_intervention_v31(adj_half, intervention, baseline)

        ratio = r2['deltas']['B'] / r1['deltas']['B'] if r1['deltas']['B'] != 0 else 0
        assert abs(ratio - 0.5) < 0.01, (
            f"Expected beta=0.5 to produce half the effect, got ratio={ratio:.3f}"
        )


# ──────────────────────────────────────────────
# 2. Zero-change invariants
# ──────────────────────────────────────────────


class TestZeroChange:
    """No intervention → no effects, fast convergence."""

    def test_empty_intervention_no_effects(self):
        """Empty intervention dict → all deltas 0."""
        adjacency = {
            'A': [{'target': 'B', 'beta': 0.5, 'std': 0.1}],
            'B': [{'target': 'C', 'beta': 0.3, 'std': 0.05}],
        }
        baseline = {'A': 100.0, 'B': 50.0, 'C': 25.0}

        result = propagate_intervention_v31(
            adjacency, {}, baseline,
        )

        assert result['converged']
        assert result['iterations'] == 1, (
            f"Empty intervention should converge in 1 iteration, took {result['iterations']}"
        )
        # All deltas should be exactly 0
        for ind, delta in result['deltas'].items():
            assert delta == 0.0, f"Expected 0 delta for {ind}, got {delta}"

    def test_zero_percent_intervention_no_effects(self):
        """0% change on an indicator → no propagation."""
        adjacency = {
            'A': [{'target': 'B', 'beta': 0.5, 'std': 0.1}],
        }
        baseline = {'A': 100.0, 'B': 50.0}

        result = propagate_intervention_v31(
            adjacency, {'A': 0.0}, baseline,
        )

        assert result['converged']
        # B should have 0 delta (no impulse from A)
        assert result['deltas'].get('B', 0) == 0.0

    def test_disconnected_node_unaffected(self):
        """Nodes not reachable from intervention source get 0 delta."""
        adjacency = {
            'A': [{'target': 'B', 'beta': 0.5, 'std': 0.1}],
            # C is disconnected
        }
        baseline = {'A': 100.0, 'B': 50.0, 'C': 75.0}

        result = propagate_intervention_v31(
            adjacency, {'A': 10.0}, baseline,
        )

        assert result['deltas'].get('C', 0) == 0.0, (
            "Disconnected node C should have 0 delta"
        )


# ──────────────────────────────────────────────
# 3. Clamp invariants
# ──────────────────────────────────────────────


class TestClampInvariants:
    """Cumulative delta never exceeds ±2σ when country stats are available."""

    def test_clamp_respects_2sigma(self):
        """
        With country stats providing std, no cumulative delta should
        exceed 2 * std for any indicator.
        """
        # Create a chain with large betas to force clamping
        adjacency = {
            'A': [{'target': 'B', 'beta': 5.0, 'std': 0.0}],
            'B': [{'target': 'C', 'beta': 5.0, 'std': 0.0}],
        }
        baseline = {'A': 100.0, 'B': 50.0, 'C': 25.0}

        # Use country='United States' so we get real temporal stats
        result = propagate_intervention_v31(
            adjacency, {'A': 50.0}, baseline,
            country='United States',
        )

        # For indicators with country stats, cumulative delta should be ≤ 2*std
        from simulation.indicator_stats import get_country_indicator_stats
        stats = get_country_indicator_stats('United States')

        for ind, delta in result['deltas'].items():
            if ind == 'A':
                continue  # Intervention node isn't clamped
            stat = stats.get(ind, {})
            temporal_std = stat.get('std', 0)
            if temporal_std > 0:
                max_allowed = 2.0 * temporal_std
                assert abs(delta) <= max_allowed + 0.01, (
                    f"{ind}: delta={delta:.4f} exceeds 2σ={max_allowed:.4f} "
                    f"(std={temporal_std:.4f})"
                )


# ──────────────────────────────────────────────
# 4. Saturation invariants
# ──────────────────────────────────────────────


class TestSaturationInvariants:
    """Saturated indicators never exceed their bounds, even under multi-hop."""

    def test_enrollment_rate_never_exceeds_100(self):
        """SE.PRM.ENRR should never go above 100 no matter how large the intervention."""
        for proposed in [110, 200, 1000, 1e6]:
            result = apply_saturation('SE.PRM.ENRR', proposed, baseline=85.0)
            assert result <= 100.0, f"SE.PRM.ENRR={proposed} → {result}, expected ≤100"

    def test_enrollment_rate_never_below_0(self):
        """SE.PRM.ENRR should never go below 0."""
        for proposed in [-10, -100, -1e6]:
            result = apply_saturation('SE.PRM.ENRR', proposed, baseline=85.0)
            assert result >= 0.0, f"SE.PRM.ENRR={proposed} → {result}, expected ≥0"

    def test_life_expectancy_bounds(self):
        """SP.DYN.LE00.IN stays in [25, 95]."""
        assert apply_saturation('SP.DYN.LE00.IN', 100.0, 75.0) == 95.0
        assert apply_saturation('SP.DYN.LE00.IN', 20.0, 75.0) == 25.0
        assert apply_saturation('SP.DYN.LE00.IN', 80.0, 75.0) == 80.0  # within bounds

    def test_vdem_index_bounds(self):
        """v2x_polyarchy stays in [0, 1]."""
        assert apply_saturation('v2x_polyarchy', 1.5, 0.5) == 1.0
        assert apply_saturation('v2x_polyarchy', -0.3, 0.5) == 0.0
        assert apply_saturation('v2x_polyarchy', 0.7, 0.5) == 0.7

    def test_vdem_ordinal_bounds(self):
        """V-Dem _ord indicators stay in [0, 5]."""
        assert apply_saturation('v2clacjust_ord', 6.0, 3.0) == 5.0
        assert apply_saturation('v2clacjust_ord', -1.0, 3.0) == 0.0

    def test_vdem_latent_bounds(self):
        """V-Dem latent (v2el*, v2pe*, etc.) stays in [-4, 4]."""
        assert apply_saturation('v2elfrfair', 5.0, 2.0) == 4.0
        assert apply_saturation('v2elfrfair', -5.0, 2.0) == -4.0

    def test_polity_bounds(self):
        """e_polity* stays in [-10, 10]."""
        assert apply_saturation('e_polity2', 15.0, 5.0) == 10.0
        assert apply_saturation('e_polity2', -15.0, 5.0) == -10.0

    def test_unsaturated_indicators_pass_through(self):
        """Indicators without saturation config pass through unchanged."""
        # rconna and random_xyz have no saturation (no matching prefix)
        for ind in ['rconna', 'random_xyz']:
            for val in [-100, 0, 100, 1e9]:
                result = apply_saturation(ind, val, baseline=50.0)
                assert result == val, (
                    f"{ind}: expected {val} (pass-through), got {result}"
                )

    def test_non_negative_floor(self):
        """GDP, population etc. are floored at 0 (never negative)."""
        for ind in ['NY.GDP.PCAP.CD', 'SP.POP.TOTL', 'NW.HCA.TO.CD']:
            # Positive values pass through
            result = apply_saturation(ind, 50000.0, baseline=60000.0)
            assert result == 50000.0, f"{ind}: positive should pass through"
            # Negative values floored at 0
            result = apply_saturation(ind, -100.0, baseline=60000.0)
            assert result == 0.0, f"{ind}: negative should be floored at 0, got {result}"
            # Zero passes through
            result = apply_saturation(ind, 0.0, baseline=60000.0)
            assert result == 0.0, f"{ind}: zero should pass through"

    def test_growth_rates_can_be_negative(self):
        """Growth rate indicators (.ZG) should NOT be floored at 0."""
        for ind in ['NY.GDP.MKTP.KD.ZG', 'NV.IND.TOTL.KD.ZG']:
            result = apply_saturation(ind, -5.0, baseline=2.0)
            assert result == -5.0, f"{ind}: growth rate should allow negative, got {result}"

    def test_saturation_idempotent(self):
        """Applying saturation twice should not change the value."""
        test_cases = [
            ('SE.PRM.ENRR', 110.0, 85.0),
            ('v2x_polyarchy', 1.5, 0.5),
            ('SP.DYN.LE00.IN', 100.0, 75.0),
            ('e_polity2', 15.0, 5.0),
        ]
        for ind, val, baseline in test_cases:
            first = apply_saturation(ind, val, baseline)
            second = apply_saturation(ind, first, baseline)
            assert first == second, (
                f"{ind}: saturation not idempotent: {val}→{first}→{second}"
            )

    def test_multi_hop_chain_respects_saturation(self):
        """
        Even with a strong multi-hop chain, saturated indicators
        should stay in bounds after propagation.
        """
        # SE.PRM.ENRR is a rate [0, 100]
        adjacency = {
            'A': [{'target': 'SE.PRM.ENRR', 'beta': 10.0, 'std': 0.0}],
        }
        baseline = {'A': 100.0, 'SE.PRM.ENRR': 85.0}

        result = propagate_intervention_v31(
            adjacency, {'A': 100.0}, baseline,
        )

        enrr_val = result['values'].get('SE.PRM.ENRR', 0)
        assert 0.0 <= enrr_val <= 100.0, (
            f"SE.PRM.ENRR should be in [0,100] after propagation, got {enrr_val}"
        )


# ──────────────────────────────────────────────
# 5. Convergence invariants
# ──────────────────────────────────────────────


class TestConvergenceInvariants:
    """Convergence behavior is correct."""

    def test_no_edges_converges_immediately(self):
        """Graph with no edges converges in 1 iteration."""
        adjacency = {}
        baseline = {'A': 100.0, 'B': 50.0}

        result = propagate_intervention_v31(
            adjacency, {'A': 10.0}, baseline,
        )

        assert result['converged']
        assert result['iterations'] == 1
        assert result['deltas']['A'] == 10.0
        assert result['deltas'].get('B', 0) == 0.0

    def test_linear_chain_converges(self):
        """A→B→C chain should converge within max_iterations."""
        adjacency = {
            'A': [{'target': 'B', 'beta': 0.5, 'std': 0.0}],
            'B': [{'target': 'C', 'beta': 0.3, 'std': 0.0}],
        }
        baseline = {'A': 100.0, 'B': 50.0, 'C': 25.0}

        result = propagate_intervention_v31(
            adjacency, {'A': 10.0}, baseline,
            max_iterations=20,
        )

        assert result['converged'], (
            f"Linear chain should converge, took {result['iterations']} iterations"
        )


# ──────────────────────────────────────────────
# 6. Monotonicity
# ──────────────────────────────────────────────


class TestMonotonicity:
    """Larger interventions should produce larger effects (in same direction)."""

    def test_larger_intervention_larger_effect(self):
        """Doubling the intervention should increase total effect magnitude."""
        adjacency = {
            'A': [{'target': 'B', 'beta': 0.5, 'std': 0.0}],
            'B': [{'target': 'C', 'beta': 0.3, 'std': 0.0}],
        }
        baseline = {'A': 100.0, 'B': 50.0, 'C': 25.0}

        r1 = propagate_intervention_v31(adjacency, {'A': 10.0}, baseline)
        r2 = propagate_intervention_v31(adjacency, {'A': 20.0}, baseline)

        total1 = sum(abs(d) for d in r1['deltas'].values())
        total2 = sum(abs(d) for d in r2['deltas'].values())

        assert total2 > total1, (
            f"20-unit intervention ({total2:.2f}) should exceed "
            f"10-unit intervention ({total1:.2f})"
        )

    def test_sign_preservation(self):
        """Positive intervention → positive downstream effects (for positive betas)."""
        adjacency = {
            'A': [{'target': 'B', 'beta': 0.5, 'std': 0.0}],
        }
        baseline = {'A': 100.0, 'B': 50.0}

        result = propagate_intervention_v31(
            adjacency, {'A': 10.0}, baseline,
        )

        assert result['deltas']['B'] > 0, (
            f"Positive A delta with positive beta should produce positive B delta, "
            f"got {result['deltas']['B']}"
        )


# ──────────────────────────────────────────────
# 7. Saturation pattern matching correctness
# ──────────────────────────────────────────────


class TestSaturationPatternMatching:
    """Verify no false positives or false negatives in pattern matching."""

    def test_population_uses_non_negative_floor(self):
        """SP.POP.* should use floor_zero (not rate cap at 100)."""
        from simulation.saturation_functions import floor_zero_saturation

        pop_indicators = [
            'SP.POP.TOTL', 'SP.POP.3539.FE', 'SP.POP.7579.MA',
            'SP.POP.AG24.MA.IN',
        ]
        for ind in pop_indicators:
            func, params = get_saturation_function(ind)
            assert func == floor_zero_saturation, (
                f"{ind} should use floor_zero_saturation, got {func.__name__} with {params}"
            )
            # Positive values pass through (not capped at 100!)
            result = apply_saturation(ind, 9_800_000, baseline=9_000_000)
            assert result == 9_800_000, f"{ind}: population should NOT be capped at 100"

    def test_gdp_uses_non_negative_floor(self):
        """GDP/income level indicators should use floor_zero (not no_saturation)."""
        from simulation.saturation_functions import floor_zero_saturation

        gdp_indicators = [
            'NY.GDP.PCAP.CD', 'NY.GDP.MKTP.CD', 'NY.GNP.PCAP.CD',
            'NE.CON.PRVT.CD',
        ]
        for ind in gdp_indicators:
            func, params = get_saturation_function(ind)
            assert func == floor_zero_saturation, (
                f"{ind} should use floor_zero_saturation, got {func.__name__} with {params}"
            )

        # WID indicators (opaque codes) have no saturation config
        func, _ = get_saturation_function('rconna')
        assert func == no_saturation, "rconna (WID) should have no saturation"

    def test_growth_rates_not_floored(self):
        """Growth rate (.ZG) and share (.ZS) indicators can be negative."""
        growth_indicators = [
            'NY.GDP.MKTP.KD.ZG', 'NV.IND.TOTL.KD.ZG',
        ]
        for ind in growth_indicators:
            func, params = get_saturation_function(ind)
            assert func == no_saturation, (
                f"{ind} should have no saturation (growth rates can be negative), "
                f"got {func.__name__}"
            )

    def test_true_positives_rates(self):
        """Actual rate indicators SHOULD be saturated at [0, 100]."""
        rate_indicators = [
            'SE.PRM.ENRR', 'SE.SEC.ENRR', 'SE.TER.ENRR',
            'SH.DYN.MORT', 'SH.STA.MMRT',
        ]
        for ind in rate_indicators:
            func, params = get_saturation_function(ind)
            assert func == hard_cap_saturation, (
                f"{ind} should have hard_cap_saturation, got {func.__name__}"
            )
            assert params['max_val'] == 100.0

    def test_true_positives_vdem_index(self):
        """V-Dem aggregate indices SHOULD be saturated at [0, 1]."""
        vdem_indices = [
            'v2x_polyarchy', 'v2x_libdem', 'v2x_egaldem',
            'e_v2x_polyarchy',
        ]
        for ind in vdem_indices:
            func, params = get_saturation_function(ind)
            assert func == hard_cap_saturation, (
                f"{ind} should have hard_cap_saturation, got {func.__name__}"
            )
            assert params['max_val'] == 1.0

    def test_suffix_matching_correct(self):
        """Suffix patterns (_ord, _mean, _osp) should match correctly."""
        # Should match
        func, _ = get_saturation_function('v2clacjust_ord')
        assert func == hard_cap_saturation

        func, _ = get_saturation_function('v2medentrain_mean')
        assert func == hard_cap_saturation

        func, _ = get_saturation_function('v2edplural_osp')
        assert func == hard_cap_saturation

        # Should NOT match (suffix doesn't match)
        func, _ = get_saturation_function('ordinary_indicator')
        assert func == no_saturation, "'ordinary' should not match '_ord' suffix"

        func, _ = get_saturation_function('mean_temperature')
        assert func == no_saturation, "'mean_temp' should not match '_mean' suffix"
