#!/usr/bin/env bash
# Run OSRM routing service (§7)
# Expects built OSRM graph in infra/maps/osrm/data/
#
# Usage:
#   bash scripts/maps/run_osrm.sh [--port PORT]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
OSRM_DATA="$PROJECT_ROOT/infra/maps/osrm/data"
OSRM_IMAGE="ghcr.io/project-osrm/osrm-backend:v5.27.1"
PORT="${1:-5000}"

OSRM_FILE="$OSRM_DATA/vietnam-latest.osrm"
if [ ! -f "$OSRM_FILE.datasource_names" ] && [ ! -f "$OSRM_FILE.cell_metrics" ]; then
    echo "[ERROR] OSRM graph not found in $OSRM_DATA"
    echo "        Run: bash scripts/maps/build_osrm.sh"
    exit 1
fi

echo "[INFO] Starting OSRM on port $PORT (MLD algorithm)"
echo "[INFO] Data: $OSRM_DATA"
echo ""
echo "  Test: curl http://localhost:$PORT/route/v1/driving/105.8542,21.0285;105.8341,21.0278"
echo ""

docker run --rm -p "$PORT:5000" -v "$OSRM_DATA:/data" "$OSRM_IMAGE" \
    osrm-routed --algorithm mld /data/vietnam-latest.osrm
