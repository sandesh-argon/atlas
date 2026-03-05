#!/bin/bash
# Setup AWS instance for country SHAP computation
# Usage: ./setup_instance.sh <ip-address> <country-range>

set -e

IP=$1
COUNTRY_RANGE=$2
KEY_PATH="$HOME/Downloads/Final.pem"
PROJECT_DIR="<repo-root>/v3.1"

if [ -z "$IP" ] || [ -z "$COUNTRY_RANGE" ]; then
    echo "Usage: ./setup_instance.sh <ip-address> <country-range>"
    echo "Example: ./setup_instance.sh 54.123.45.67 A-D"
    exit 1
fi

echo "=== Setting up instance ${IP} for ${COUNTRY_RANGE} ==="

SSH_CMD="ssh -i ${KEY_PATH} -o StrictHostKeyChecking=no ubuntu@${IP}"
SCP_CMD="scp -i ${KEY_PATH} -o StrictHostKeyChecking=no"

# Wait for SSH to be ready
echo "Waiting for SSH..."
for i in {1..30}; do
    if $SSH_CMD "echo 'SSH ready'" 2>/dev/null; then
        break
    fi
    sleep 5
done

# Install dependencies
echo "Installing dependencies..."
$SSH_CMD << 'REMOTE_SETUP'
sudo apt-get update
sudo apt-get install -y python3-pip python3-venv htop

# Create project directory
mkdir -p ~/v3.1/data/raw
mkdir -p ~/v3.1/data/metadata
mkdir -p ~/v3.1/data/v3_1_temporal_shap/countries
mkdir -p ~/v3.1/scripts/phase2_compute/phase2A/country

# Create venv
cd ~/v3.1
python3 -m venv venv
source venv/bin/activate

# Install Python packages
pip install --upgrade pip
pip install pandas pyarrow numpy lightgbm shap scikit-learn joblib
REMOTE_SETUP

echo "Uploading data files..."
# Upload panel data
$SCP_CMD ${PROJECT_DIR}/data/raw/v21_panel_data_for_v3.parquet ubuntu@${IP}:~/v3.1/data/raw/

# Upload metadata
$SCP_CMD ${PROJECT_DIR}/data/metadata/indicator_properties.json ubuntu@${IP}:~/v3.1/data/metadata/

# Upload V2.1 hierarchy
$SSH_CMD "mkdir -p ~/v2.1/outputs/B5"
$SCP_CMD <repo-root>/v2.1/outputs/B5/v2_1_visualization.json ubuntu@${IP}:~/v2.1/outputs/B5/

# Upload compute script
$SCP_CMD ${PROJECT_DIR}/scripts/phase2_compute/phase2A/country/compute_country_shap_v21.py ubuntu@${IP}:~/v3.1/scripts/phase2_compute/phase2A/country/

# Upload country list for this range
$SCP_CMD ${PROJECT_DIR}/data/country_list_${COUNTRY_RANGE}.txt ubuntu@${IP}:~/v3.1/data/

# Create run script on remote
echo "Creating run script..."
$SSH_CMD << REMOTE_RUN
cat > ~/v3.1/run_country_shap.sh << 'EOF'
#!/bin/bash
cd ~/v3.1
source venv/bin/activate

# Set thread limits to prevent contention
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1

# Run with 32 cores
nohup python -u scripts/phase2_compute/phase2A/country/compute_country_shap_v21.py \
    --cores 32 \
    --country-list data/country_list_\${1}.txt \
    > country_shap_\${1}.log 2>&1 &

echo "Started! PID: \$!"
echo "Monitor with: tail -f country_shap_\${1}.log"
EOF
chmod +x ~/v3.1/run_country_shap.sh
REMOTE_RUN

echo ""
echo "=== Setup Complete ==="
echo "Instance: ${IP}"
echo "Country Range: ${COUNTRY_RANGE}"
echo ""
echo "To start computation:"
echo "  ssh -i ${KEY_PATH} ubuntu@${IP}"
echo "  cd ~/v3.1 && ./run_country_shap.sh ${COUNTRY_RANGE}"
echo ""
echo "To monitor:"
echo "  ssh -i ${KEY_PATH} ubuntu@${IP} 'tail -f ~/v3.1/country_shap_${COUNTRY_RANGE}.log'"
