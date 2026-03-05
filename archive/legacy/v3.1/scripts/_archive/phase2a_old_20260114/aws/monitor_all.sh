#!/bin/bash
# Monitor all AWS instances for country SHAP computation
# Usage: ./monitor_all.sh

KEY_PATH="$HOME/Downloads/Final.pem"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

check_instance() {
    local IP=$1
    local RANGE=$2

    # Check if instance is reachable
    if ! ssh -i ${KEY_PATH} -o StrictHostKeyChecking=no -o ConnectTimeout=5 ubuntu@${IP} "echo ok" &>/dev/null; then
        echo -e "${RED}✗ ${RANGE} (${IP}): UNREACHABLE${NC}"
        return
    fi

    # Get stats
    STATS=$(ssh -i ${KEY_PATH} -o StrictHostKeyChecking=no ubuntu@${IP} << 'REMOTE'
        # File count
        FILES=$(find ~/v3.1/data/v3_1_temporal_shap/countries -name '*.json' 2>/dev/null | wc -l)

        # CPU usage
        CPU=$(top -bn1 | grep 'Cpu(s)' | awk '{print $2}')

        # Memory
        MEM=$(free -m | awk 'NR==2{printf "%.1f", $3*100/$2}')

        # Latest log
        LOG=$(tail -1 ~/v3.1/country_shap_*.log 2>/dev/null | head -c 80)

        # Process running?
        if pgrep -f "compute_country_shap" > /dev/null; then
            STATUS="RUNNING"
        else
            STATUS="STOPPED"
        fi

        echo "${FILES}|${CPU}|${MEM}|${STATUS}|${LOG}"
REMOTE
    )

    IFS='|' read -r FILES CPU MEM STATUS LOG <<< "$STATS"

    if [ "$STATUS" == "RUNNING" ]; then
        echo -e "${GREEN}✓ ${RANGE} (${IP}): ${STATUS}${NC}"
    else
        echo -e "${RED}✗ ${RANGE} (${IP}): ${STATUS}${NC}"
    fi
    echo "    Files: ${FILES} | CPU: ${CPU}% | MEM: ${MEM}%"
    echo "    Latest: ${LOG}"
    echo ""
}

# Main
clear
echo "=============================================="
echo "    COUNTRY SHAP - MULTI-INSTANCE MONITOR"
echo "    $(date '+%Y-%m-%d %H:%M:%S')"
echo "=============================================="
echo ""

if [ ! -f "${SCRIPT_DIR}/instances.csv" ]; then
    echo "No instances.csv found in ${SCRIPT_DIR}"
    echo "Launch instances first with launch_spot_instance.sh"
    exit 1
fi

# Local file count
LOCAL_FILES=$(find <repo-root>/v3.1/data/v3_1_temporal_shap/countries -name '*.json' 2>/dev/null | wc -l)
TOTAL_EXPECTED=$((252 * 9 * 30))
PERCENT=$((LOCAL_FILES * 100 / TOTAL_EXPECTED))

echo -e "${BLUE}LOCAL STATUS:${NC}"
echo "  Files synced: ${LOCAL_FILES} / ${TOTAL_EXPECTED} (${PERCENT}%)"
echo ""
echo -e "${BLUE}INSTANCE STATUS:${NC}"
echo ""

while IFS=',' read -r INSTANCE_ID IP RANGE; do
    if [ ! -z "$IP" ]; then
        check_instance "$IP" "$RANGE"
    fi
done < "${SCRIPT_DIR}/instances.csv"

echo "=============================================="
echo "Refresh: ./monitor_all.sh"
echo "Logs: ssh -i ${KEY_PATH} ubuntu@<IP> 'tail -f ~/v3.1/country_shap_*.log'"
