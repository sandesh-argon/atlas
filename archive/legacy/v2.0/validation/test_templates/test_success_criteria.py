"""
Validation Template: Success Criteria Gates

Purpose: Enforce success criteria from master instructions before allowing
         progression to next step.

Usage:
    from validation.test_templates.test_success_criteria import validate_step_output

    results = validate_step_output(
        step_name="A2_granger_causality",
        output_data=validated_edges,
        success_criteria=SUCCESS_CRITERIA_A2
    )

Reference: v2_master_instructions.md lines 278-283 (A2 example)
"""

import json
import numpy as np
from pathlib import Path
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


# Success criteria from master instructions
SUCCESS_CRITERIA = {
    "A0_data_acquisition": {
        "n_variables": (5000, 6000),
        "n_countries": (150, 220),
        "temporal_span_years": (25, 40),
        "mean_missingness": (0.30, 0.70)
    },
    "A1_missingness_analysis": {
        "n_variables_clean": (4000, 6000),
        "stability_score": (0.70, 1.0),
        "mean_r2_holdout": (0.45, 1.0)
    },
    "A2_granger_causality": {
        "n_validated_edges": (30000, 80000),
        "mean_p_adjusted": (None, 0.01),  # None means no lower bound
        "bidirectional_pct": (None, 0.15)
    },
    "A3_conditional_independence": {
        "n_final_edges": (10000, 30000),
        "is_dag": (True, True),  # Must be exactly True
        "connected_component_pct": (0.80, 1.0)
    },
    "A4_effect_quantification": {
        "n_effects": (2000, 10000),
        "mean_abs_beta": (0.15, None),  # Lower bound only
        "all_ci_non_zero": (True, True)  # All CIs must not cross zero
    },
    "A5_interaction_discovery": {
        "n_interactions": (50, 200),
        "mean_interaction_coef": (0.15, None),
        "all_p_values": (None, 0.001)
    },
    "B1_outcome_discovery": {
        "n_outcomes": (12, 25),
        "v1_reproduction": (6, 8),  # Must reproduce ≥6 out of 8
        "all_r2": (0.40, 1.0),
        "mean_domain_coherence": (0.70, 1.0)
    },
    "B4_multi_level_pruning": {
        "professional_nodes": (300, 800),
        "simplified_nodes": (30, 50),
        "shap_retention_professional": (0.85, 1.0),
        "shap_retention_simplified": (0.70, 1.0)
    }
}


def validate_step_output(step_name, output_data, success_criteria=None):
    """
    Validates step output against success criteria.

    Args:
        step_name: Name of step (e.g., "A2_granger_causality")
        output_data: Dict with computed metrics
        success_criteria: Optional override of default criteria

    Returns:
        Dict with validation results

    Raises:
        ValidationError if any criterion fails
    """
    if success_criteria is None:
        if step_name not in SUCCESS_CRITERIA:
            logger.warning(f"No success criteria defined for {step_name}")
            return {"all_passed": True, "message": "No criteria to validate"}
        success_criteria = SUCCESS_CRITERIA[step_name]

    results = {}
    all_passed = True

    for criterion, (min_val, max_val) in success_criteria.items():
        if criterion not in output_data:
            logger.error(f"Missing metric: {criterion}")
            results[criterion] = {
                'actual': None,
                'expected': f"[{min_val}, {max_val}]",
                'passed': False,
                'error': f"Metric {criterion} not found in output_data"
            }
            all_passed = False
            continue

        actual = output_data[criterion]

        # Check bounds
        passed = True
        if min_val is not None and actual < min_val:
            passed = False
        if max_val is not None and actual > max_val:
            passed = False

        results[criterion] = {
            'actual': actual,
            'expected': f"[{min_val}, {max_val}]",
            'passed': passed
        }

        if not passed:
            all_passed = False
            logger.error(
                f"❌ {criterion}: {actual} NOT IN [{min_val}, {max_val}]"
            )
        else:
            logger.info(
                f"✅ {criterion}: {actual} IN [{min_val}, {max_val}]"
            )

    results['all_passed'] = all_passed
    results['timestamp'] = datetime.now().isoformat()

    if not all_passed:
        logger.critical(f"🚨 VALIDATION FAILED FOR {step_name}")
        logger.critical("STOPPING EXECUTION - HUMAN REVIEW REQUIRED")

        save_validation_report(step_name, results, output_data)

        raise ValidationError(
            f"{step_name} failed validation criteria. "
            f"See validation/reports/{step_name}_FAILED.json for details."
        )

    logger.info(f"✅ All validation criteria passed for {step_name}")
    save_validation_report(step_name, results, output_data)

    return results


def save_validation_report(step_name, results, output_data):
    """Save validation report to file"""
    report_dir = Path("validation/reports")
    report_dir.mkdir(parents=True, exist_ok=True)

    status = "PASSED" if results['all_passed'] else "FAILED"
    report_file = report_dir / f"{step_name}_{status}.json"

    report = {
        'step': step_name,
        'status': status,
        'timestamp': results.get('timestamp', datetime.now().isoformat()),
        'validation_results': results,
        'output_data': output_data
    }

    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2)

    logger.info(f"Validation report saved: {report_file}")


class ValidationError(Exception):
    """Raised when validation criteria are not met"""
    pass


# Example usage
if __name__ == "__main__":
    # Example: Validating A2 output
    a2_output = {
        'n_validated_edges': 47832,
        'mean_p_adjusted': 0.0043,
        'bidirectional_pct': 0.12
    }

    try:
        results = validate_step_output("A2_granger_causality", a2_output)
        print("✅ Validation passed!")
        print(json.dumps(results, indent=2))
    except ValidationError as e:
        print(f"❌ Validation failed: {e}")
