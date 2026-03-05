"""
V2.1 Path Configuration

All V2.1 scripts import this to get correct input/output paths.
This ensures V2.1 runs independently without touching V2 outputs.
"""

from pathlib import Path

# V2.1 root directory
V21_ROOT = Path(__file__).parent.parent  # v2.1/

# Project root (v2.0/)
PROJECT_ROOT = V21_ROOT.parent

# =============================================================================
# INPUT PATHS (read from V2.1 sampled data or V2 intermediate outputs)
# =============================================================================

# Primary input: V2.1 sampled data (created by step0)
A1_INPUT = V21_ROOT / "outputs" / "A2_preprocessed_data_V21.pkl"

# Fallback to V2 if V2.1 not yet created
A1_INPUT_V2 = PROJECT_ROOT / "phaseA" / "A1_missingness_analysis" / "outputs" / "A2_preprocessed_data.pkl"

# A6 graph for sampling (read from V2)
A6_GRAPH_V2 = PROJECT_ROOT / "phaseA" / "A6_hierarchical_layering" / "outputs" / "A6_hierarchical_graph.pkl"

# =============================================================================
# OUTPUT PATHS (all V2.1 outputs go to v2.1/outputs/)
# =============================================================================

# Main output directory
OUTPUT_ROOT = V21_ROOT / "outputs"

# Phase-specific output directories
A2_OUTPUT = OUTPUT_ROOT / "A2"
A3_OUTPUT = OUTPUT_ROOT / "A3"
A4_OUTPUT = OUTPUT_ROOT / "A4"
A5_OUTPUT = OUTPUT_ROOT / "A5"
A6_OUTPUT = OUTPUT_ROOT / "A6"
B1_OUTPUT = OUTPUT_ROOT / "B1"
B2_OUTPUT = OUTPUT_ROOT / "B2"
B25_OUTPUT = OUTPUT_ROOT / "B25"
B35_OUTPUT = OUTPUT_ROOT / "B35"

# Checkpoint directories
A2_CHECKPOINTS = OUTPUT_ROOT / "A2" / "checkpoints"
A4_CHECKPOINTS = OUTPUT_ROOT / "A4" / "checkpoints"

# Log directory
LOG_DIR = V21_ROOT / "logs"

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def ensure_dirs():
    """Create all output directories."""
    for d in [OUTPUT_ROOT, A2_OUTPUT, A3_OUTPUT, A4_OUTPUT, A5_OUTPUT,
              A6_OUTPUT, B1_OUTPUT, B2_OUTPUT, B25_OUTPUT, B35_OUTPUT,
              A2_CHECKPOINTS, A4_CHECKPOINTS, LOG_DIR]:
        d.mkdir(parents=True, exist_ok=True)

def get_input_path():
    """Get the correct input path (V2.1 if exists, else V2)."""
    if A1_INPUT.exists():
        return A1_INPUT
    elif A1_INPUT_V2.exists():
        return A1_INPUT_V2
    else:
        raise FileNotFoundError(f"No input data found at {A1_INPUT} or {A1_INPUT_V2}")

# Create directories on import
ensure_dirs()
