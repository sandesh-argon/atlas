#!/usr/bin/env python3
"""
V2.1 Pre-Run Validation

Checks all required files and scripts exist before running V2.1 pipeline.
Run this BEFORE starting the pipeline to avoid mid-run failures.
"""

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).parent.parent.parent

# Required input files
REQUIRED_INPUTS = [
    'phaseA/A1_missingness_analysis/outputs/A2_preprocessed_data.pkl',
    'phaseA/A6_hierarchical_layering/outputs/A6_hierarchical_graph.pkl',
]

# Required scripts (from phase READMEs)
REQUIRED_SCRIPTS = {
    'A2': [
        'phaseA/A2_granger_causality/scripts/step1_validate_checkpoint.py',
        'phaseA/A2_granger_causality/scripts/step2_prefiltering.py',
        'phaseA/A2_granger_causality/scripts/step3_granger_testing_v2.py',
        'phaseA/A2_granger_causality/scripts/step4_fdr_correction.py',
    ],
    'A3': [
        'phaseA/A3_conditional_independence/scripts/step1c_smart_prepruning.py',
        'phaseA/A3_conditional_independence/scripts/step2_custom_pairwise_pc.py',
        'phaseA/A3_conditional_independence/scripts/step3_remove_cycles.py',
    ],
    'A4': [
        'phaseA/A4_effect_quantification/scripts/step1_input_validation.py',
        'phaseA/A4_effect_quantification/scripts/step3_effect_estimation_lasso.py',
    ],
    'A5': [
        'phaseA/A5_interaction_discovery/scripts/run_interaction_discovery.py',
    ],
    'A6': [
        'phaseA/A6_hierarchical_layering/scripts/run_hierarchical_layering.py',
    ],
    'B1': [
        'phaseB/B1_outcome_discovery/scripts/run_b1_factor_analysis.py',
    ],
    'B2': [
        'phaseB/B2_mechanism_identification/scripts/run_b2_full_clustering.py',
    ],
    'B35': [
        'phaseB/B35_semantic_hierarchy/scripts/run_b35_semantic_hierarchy.py',
        'phaseB/B35_semantic_hierarchy/scripts/compute_shap_scores.py',
        'phaseB/B35_semantic_hierarchy/scripts/export_final_visualization.py',
    ],
}

def check_file(path: str) -> bool:
    """Check if file exists."""
    full_path = PROJECT_ROOT / path
    return full_path.exists()

def main():
    print("="*80)
    print("V2.1 PRE-RUN VALIDATION")
    print("="*80)
    print()

    all_ok = True

    # Check inputs
    print("[1/3] Checking required input files...")
    for path in REQUIRED_INPUTS:
        exists = check_file(path)
        status = "OK" if exists else "MISSING"
        symbol = "" if exists else ""
        print(f"  {symbol} {path}: {status}")
        if not exists:
            all_ok = False

    print()

    # Check scripts
    print("[2/3] Checking required scripts...")
    for phase, scripts in REQUIRED_SCRIPTS.items():
        missing = []
        for script in scripts:
            if not check_file(script):
                missing.append(script)
                all_ok = False

        if missing:
            print(f"  {phase}: MISSING {len(missing)} scripts")
            for s in missing:
                print(f"      {s}")
        else:
            print(f"  {phase}: OK ({len(scripts)} scripts)")

    print()

    # Check V2.1 specific files
    print("[3/3] Checking V2.1 files...")
    v21_files = [
        'v2.1/V21_INSTRUCTIONS.md',
        'v2.1/scripts/step0_stratified_sampling.py',
        'v2.1/scripts/step3_validate_v21.py',
    ]
    for path in v21_files:
        exists = check_file(path)
        status = "OK" if exists else "MISSING"
        symbol = "" if exists else ""
        print(f"  {symbol} {path}: {status}")
        if not exists:
            all_ok = False

    print()
    print("="*80)

    if all_ok:
        print("VALIDATION PASSED - Ready to run V2.1 pipeline")
        print("="*80)
        print()
        print("Next step:")
        print("  python v2.1/scripts/step0_stratified_sampling.py")
        return 0
    else:
        print("VALIDATION FAILED - Fix missing files before proceeding")
        print("="*80)
        return 1


if __name__ == '__main__':
    sys.exit(main())
