#!/bin/bash
# Sync country SHAP data from AWS instance(s) every 10 minutes
# Usage: ./sync_country_shap.sh [single-ip] [country-range]
#    or: ./sync_country_shap.sh --all (to sync from all instances in instances.csv)

set -e

KEY_PATH="$HOME/Downloads/Final.pem"
LOCAL_DIR="<repo-root>/v3.1/data/v3_1_temporal_shap/countries"
SYNC_INTERVAL=600  # 10 minutes in seconds

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

sync_instance() {
    local IP=$1
    local RANGE=$2
    local REMOTE_DIR="ubuntu@${IP}:~/v3.1/data/v3_1_temporal_shap/countries/"

    echo -e "${YELLOW}[$(date '+%H:%M:%S')] Syncing ${RANGE} from ${IP}...${NC}"

    # Count remote files
    REMOTE_COUNT=$(ssh -i ${KEY_PATH} -o StrictHostKeyChecking=no -o ConnectTimeout=10 ubuntu@${IP} \
        "find ~/v3.1/data/v3_1_temporal_shap/countries -name '*.json' 2>/dev/null | wc -l" 2>/dev/null || echo "0")

    # Sync files
    rsync -avz --progress \
        -e "ssh -i ${KEY_PATH} -o StrictHostKeyChecking=no -o ConnectTimeout=10" \
        ${REMOTE_DIR} ${LOCAL_DIR}/ 2>/dev/null || true

    # Count local files for this range
    LOCAL_COUNT=$(find ${LOCAL_DIR} -name '*.json' 2>/dev/null | wc -l)

    # Get latest log line
    LATEST_LOG=$(ssh -i ${KEY_PATH} -o StrictHostKeyChecking=no ubuntu@${IP} \
        "tail -1 ~/v3.1/country_shap_${RANGE}.log 2>/dev/null" 2>/dev/null || echo "No log")

    # Get CPU usage
    CPU=$(ssh -i ${KEY_PATH} -o StrictHostKeyChecking=no ubuntu@${IP} \
        "top -bn1 | grep 'Cpu(s)' | awk '{print \$2}'" 2>/dev/null || echo "?")

    echo -e "${GREEN}  ${RANGE}: ${REMOTE_COUNT} remote files, CPU: ${CPU}%${NC}"
    echo "  Latest: ${LATEST_LOG}"
    echo ""
}

print_summary() {
    echo "=============================================="
    echo "     COUNTRY SHAP SYNC STATUS"
    echo "     $(date '+%Y-%m-%d %H:%M:%S')"
    echo "=============================================="

    TOTAL_LOCAL=$(find ${LOCAL_DIR} -name '*.json' 2>/dev/null | wc -l)
    TOTAL_EXPECTED=$((252 * 9 * 30))  # 252 countries × 9 domains × 30 years

    echo "Total local files: ${TOTAL_LOCAL} / ${TOTAL_EXPECTED}"
    PERCENT=$((TOTAL_LOCAL * 100 / TOTAL_EXPECTED))
    echo "Progress: ${PERCENT}%"
    echo ""
}

# Main logic
if [ "$1" == "--all" ]; then
    # Sync from all instances in instances.csv
    if [ ! -f "instances.csv" ]; then
        echo "No instances.csv found. Launch instances first."
        exit 1
    fi

    echo "Syncing from all instances every ${SYNC_INTERVAL} seconds..."
    echo "Press Ctrl+C to stop"
    echo ""

    while true; do
        print_summary

        while IFS=',' read -r INSTANCE_ID IP RANGE; do
            if [ ! -z "$IP" ]; then
                sync_instance "$IP" "$RANGE"
            fi
        done < instances.csv

        echo "Next sync in ${SYNC_INTERVAL} seconds..."
        echo ""
        sleep ${SYNC_INTERVAL}
    done

elif [ ! -z "$1" ] && [ ! -z "$2" ]; then
    # Sync from single instance
    IP=$1
    RANGE=$2

    echo "Syncing from ${IP} (${RANGE}) every ${SYNC_INTERVAL} seconds..."
    echo "Press Ctrl+C to stop"
    echo ""

    while true; do
        print_summary
        sync_instance "$IP" "$RANGE"

        echo "Next sync in ${SYNC_INTERVAL} seconds..."
        sleep ${SYNC_INTERVAL}
    done

else
    echo "Usage:"
    echo "  ./sync_country_shap.sh <ip> <country-range>  # Sync from single instance"
    echo "  ./sync_country_shap.sh --all                 # Sync from all instances"
    echo ""
    echo "Examples:"
    echo "  ./sync_country_shap.sh 54.123.45.67 A-D"
    echo "  ./sync_country_shap.sh --all"
fi
