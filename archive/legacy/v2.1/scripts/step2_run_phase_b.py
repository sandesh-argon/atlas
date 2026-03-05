#!/usr/bin/env python3
"""
V2.1 Step 2: Run Phase B Pipeline (B1-B3.5)

Re-runs the interpretability layer with V2.1 causal graph.

Author: Claude Code
Date: December 2025
"""

import subprocess
import sys
from pathlib import Path
from datetime import datetime
import logging

# ============================================================================
# CONFIGURATION
# ============================================================================

PROJECT_ROOT = Path(__file__).parent.parent.parent
LOG_DIR = PROJECT_ROOT / 'v2.1/logs'

# Phase B scripts (in order)
PHASE_B_STEPS = [
    {
        'name': 'B1 Outcome Discovery',
        'script': 'phaseB/B1_outcome_discovery/scripts/run_b1_factor_analysis.py',
        'runtime_estimate': '30-60 minutes'
    },
    {
        'name': 'B2 Semantic Clustering',
        'script': 'phaseB/B2_mechanism_identification/scripts/run_b2_full_clustering.py',
        'runtime_estimate': '15-30 minutes'
    },
    {
        'name': 'B3.5 Semantic Hierarchy',
        'script': 'phaseB/B35_semantic_hierarchy/scripts/build_semantic_hierarchy.py',
        'runtime_estimate': '10-20 minutes'
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
        logging.FileHandler(LOG_DIR / 'phase_b.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def check_phase_a_outputs():
    """Verify Phase A outputs exist before running Phase B."""
    required_files = [
        'phaseA/A6_hierarchical_layering/outputs/A6_hierarchical_graph.pkl',
        'phaseA/A6_hierarchical_layering/outputs/A6_edge_index.pkl'
    ]

    missing = []
    for file_path in required_files:
        full_path = PROJECT_ROOT / file_path
        if not full_path.exists():
            missing.append(file_path)

    if missing:
        logger.error("Missing Phase A outputs:")
        for f in missing:
            logger.error(f"  - {f}")
        logger.error("Run step1_run_phase_a.py first!")
        return False

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
            capture_output=False,
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
    logger.info("V2.1 PHASE B PIPELINE")
    logger.info("="*80)
    logger.info(f"Started: {datetime.now().isoformat()}")

    # Check Phase A outputs
    logger.info("\n[PREP] Checking Phase A outputs...")
    if not check_phase_a_outputs():
        logger.error("Phase A outputs not found. Aborting.")
        return False

    logger.info("  Phase A outputs OK")

    # Run each Phase B step
    successful_steps = []
    failed_steps = []

    for i, step in enumerate(PHASE_B_STEPS, 1):
        step_name = step['name']
        script_path = PROJECT_ROOT / step['script']
        runtime = step['runtime_estimate']

        logger.info(f"\n[{i}/{len(PHASE_B_STEPS)}] {step_name}")
        logger.info(f"  Estimated runtime: {runtime}")

        if not script_path.exists():
            logger.warning(f"  Script not found: {script_path}")
            logger.warning(f"  This step may need manual execution")
            failed_steps.append(step_name)
            continue

        success = run_script(script_path, step_name)

        if success:
            successful_steps.append(step_name)
        else:
            failed_steps.append(step_name)
            logger.error(f"Step {step_name} failed.")
            break

    # Summary
    logger.info("\n" + "="*80)
    logger.info("PHASE B SUMMARY")
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
        logger.info("SUCCESS: PHASE B COMPLETE")
        logger.info("="*80)
        logger.info("\nNext step: Run step3_validate_v21.py to compare V2 vs V2.1")
        logger.info("Check: phaseB/B35_semantic_hierarchy/outputs/")
    else:
        logger.warning("\n" + "="*80)
        logger.warning("WARNING: Some steps failed")
        logger.warning("="*80)

    return all_success


if __name__ == '__main__':
    success = main()
    exit(0 if success else 1)
