#!/bin/bash
# AWS Instance Setup Script for Phase 2A SHAP Computation
# Run this on a fresh Ubuntu 22.04 instance

set -e  # Exit on error

echo "=============================================="
echo "Phase 2A: AWS Setup Script"
echo "=============================================="

# 1. System updates and Python
echo "[1/6] Installing system dependencies..."
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3.11-dev git htop

# 2. Create project directory
echo "[2/6] Setting up project directory..."
mkdir -p ~/v3.1/data/raw
mkdir -p ~/v3.1/data/country_graphs
mkdir -p ~/v3.1/data/v3_1_temporal_shap
mkdir -p ~/v3.1/scripts/phase2_compute

# 3. Create virtual environment
echo "[3/6] Creating Python virtual environment..."
cd ~/v3.1
python3.11 -m venv venv
source venv/bin/activate

# 4. Install Python dependencies
echo "[4/6] Installing Python packages..."
pip install --upgrade pip
pip install \
    pandas==2.2.0 \
    numpy==1.26.3 \
    lightgbm==4.3.0 \
    shap==0.44.1 \
    joblib==1.3.2 \
    tqdm==4.66.1 \
    pyarrow==15.0.0

# 5. Verify installation
echo "[5/6] Verifying installation..."
python -c "import lightgbm; import shap; import pandas; print('All packages installed successfully')"

# 6. Create run script
echo "[6/6] Creating run script..."
cat > ~/v3.1/run_shap.sh << 'EOF'
#!/bin/bash
cd ~/v3.1
source venv/bin/activate

# Get number of CPUs
NCPUS=$(nproc)
echo "Running with $NCPUS cores..."

# Update script to use all available cores
sed -i "s/n_jobs: int = 20/n_jobs: int = $NCPUS/" scripts/phase2_compute/compute_temporal_shap.py

# Run with nohup so it continues if SSH disconnects
nohup python scripts/phase2_compute/compute_temporal_shap.py > shap_output.log 2>&1 &

echo "Started! Monitor with: tail -f ~/v3.1/shap_output.log"
echo "Process ID: $!"
EOF
chmod +x ~/v3.1/run_shap.sh

echo ""
echo "=============================================="
echo "Setup complete!"
echo "=============================================="
echo ""
echo "Next steps:"
echo "1. Upload data files to ~/v3.1/data/"
echo "2. Upload compute script to ~/v3.1/scripts/phase2_compute/"
echo "3. Run: ~/v3.1/run_shap.sh"
echo ""
