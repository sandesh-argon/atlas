#!/usr/bin/env python3
"""
V2.1 Step 1: Run Phase A Pipeline (A2-A6)

Re-runs the causal discovery pipeline with V2.1 sampled data.

IMPORTANT: A2 (Granger causality) is computationally intensive.
- Local (12 cores): ~6-8 hours
- Cloud (96 cores): ~45 minutes

See V21_INSTRUCTIONS.md for cloud setup details.

Author: Claude Code
Date: December 2025
"""

import subprocess
import sys
import shutil
from pathlib import Path
from datetime import datetime
import logging

# ============================================================================
# CONFIGURATION
# ============================================================================

PROJECT_ROOT = Path(__file__).parent.parent.parent
V21_OUTPUT_DIR = PROJECT_ROOT / 'v2.1/outputs'
LOG_DIR = PROJECT_ROOT / 'v2.1/logs'

# Phase A scripts (in order)
PHASE_A_STEPS = [
    {
        'name': 'A2 Granger Causality',
        'script': 'phaseA/A2_granger_causality/scripts/run_a2_granger.py',
        'runtime_estimate': '2-6 hours (depends on cores)',
        'cloud_recommended': True
    },
    {
        'name': 'A3 Conditional Independence',
        'script': 'phaseA/A3_conditional_independence/scripts/run_a3_pc_stable.py',
        'runtime_estimate': '30-60 minutes',
        'cloud_recommended': False
    },
    {
        'name': 'A4 Effect Quantification',
        'script': 'phaseA/A4_effect_quantification/scripts/run_a4_effects.py',
        'runtime_estimate': '1-2 hours',
        'cloud_recommended': False
    },
    {
        'name': 'A5 Interaction Discovery',
        'script': 'phaseA/A5_interaction_discovery/scripts/run_a5_interactions.py',
        'runtime_estimate': '1-2 hours',
        'cloud_recommended': False
    },
    {
        'name': 'A6 Hierarchical Layering',
        'script': 'phaseA/A6_hierarchical_layering/scripts/run_a6_layering.py',
        'runtime_estimate': '15-30 minutes',
        'cloud_recommended': False
    }
]

# ============================================================================
# LOGGING SETUP
# ============================================================================

LOG_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / 'phase_a.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def prepare_v21_input():
    """Copy V2.1 sampled data to A1 output location for Phase A to use."""
    source = V21_OUTPUT_DIR / 'A2_preprocessed_data_V21.pkl'

    # Create backup of original
    original = PROJECT_ROOT / 'phaseA/A1_missingness_analysis/outputs/A2_preprocessed_data.pkl'
    backup = PROJECT_ROOT / 'phaseA/A1_missingness_analysis/outputs/A2_preprocessed_data_V2_BACKUP.pkl'

    if not source.exists():
        logger.error(f"V2.1 sampled data not found: {source}")
        logger.error("Run step0_stratified_sampling.py first!")
        return False

    if original.exists() and not backup.exists():
        logger.info(f"Backing up original V2 data to: {backup}")
        shutil.copy2(original, backup)

    logger.info(f"Copying V2.1 data to A1 output location...")
    shutil.copy2(source, original)

    return True


def run_script(script_path: Path, step_name: str) -> bool:
    """Run a Python script and capture output."""
    logger.info(f"\n{'='*60}")
    logger.info(f"Running: {step_name}")
    logger.info(f"Script: {script_path}")
    logger.info(f"{'='*60}")

    if not script_path.exists():
        logger.error(f"Script not found: {script_path}")
        logger.warning("You may need to create this script or update the path")
        return False

    start_time = datetime.now()

    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=str(script_path.parent),
            capture_output=False,  # Show output in real-time
            text=True
        )

        elapsed = datetime.now() - start_time

        if result.returncode == 0:
            logger.info(f"\n{step_name} completed in {elapsed}")
            return True
        else:
            logger.error(f"\n{step_name} failed with exit code {result.returncode}")
            return False

    except Exception as e:
        logger.error(f"Error running {step_name}: {e}")
        return False


# ============================================================================
# MAIN
# ============================================================================

def main():
    logger.info("="*80)
    logger.info("V2.1 PHASE A PIPELINE")
    logger.info("="*80)
    logger.info(f"Started: {datetime.now().isoformat()}")

    # Step 0: Prepare V2.1 input
    logger.info("\n[PREP] Preparing V2.1 input data...")
    if not prepare_v21_input():
        logger.error("Failed to prepare V2.1 input. Aborting.")
        return False

    # Run each Phase A step
    successful_steps = []
    failed_steps = []

    for i, step in enumerate(PHASE_A_STEPS, 1):
        step_name = step['name']
        script_path = PROJECT_ROOT / step['script']
        runtime = step['runtime_estimate']
        cloud = step['cloud_recommended']

        logger.info(f"\n[{i}/{len(PHASE_A_STEPS)}] {step_name}")
        logger.info(f"  Estimated runtime: {runtime}")
        if cloud:
            logger.warning(f"  CLOUD RECOMMENDED for faster execution")

        # Check if script exists
        if not script_path.exists():
            logger.warning(f"  Script not found: {script_path}")
            logger.warning(f"  This step may need manual execution or the script path needs updating")

            # For now, mark as needing attention but continue
            # In production, you might want to fail here
            failed_steps.append(step_name)
            continue

        success = run_script(script_path, step_name)

        if success:
            successful_steps.append(step_name)
        else:
            failed_steps.append(step_name)
            logger.error(f"Step {step_name} failed. Review logs and decide whether to continue.")

            # Ask whether to continue (in interactive mode)
            # For now, we'll stop on failure
            break

    # Summary
    logger.info("\n" + "="*80)
    logger.info("PHASE A SUMMARY")
    logger.info("="*80)
    logger.info(f"\nCompleted: {datetime.now().isoformat()}")
    logger.info(f"\nSuccessful steps ({len(successful_steps)}):")
    for step in successful_steps:
        logger.info(f"  OK {step}")

    if failed_steps:
        logger.warning(f"\nFailed/Skipped steps ({len(failed_steps)}):")
        for step in failed_steps:
            logger.warning(f"  FAIL {step}")

    all_success = len(failed_steps) == 0

    if all_success:
        logger.info("\n" + "="*80)
        logger.info("SUCCESS: PHASE A COMPLETE")
        logger.info("="*80)
        logger.info("\nNext step: Review A6 outputs and approve before proceeding to Phase B")
        logger.info("Check: phaseA/A6_hierarchical_layering/outputs/")
    else:
        logger.warning("\n" + "="*80)
        logger.warning("WARNING: Some steps failed or were skipped")
        logger.warning("="*80)
        logger.warning("\nReview logs and fix issues before proceeding")

    return all_success


if __name__ == '__main__':
    success = main()
    exit(0 if success else 1)
