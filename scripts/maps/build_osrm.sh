#!/usr/bin/env bash
# OSRM build pipeline (§7) — extract → partition → customize
# Expects vietnam-latest.osm.pbf in data/osm/raw/
# Output: OSRM graph files in infra/maps/osrm/data/
#
# Usage:
#   bash scripts/maps/build_osrm.sh [--data-dir DIR]
#
# Prerequisites:
#   - Docker installed and running
#   - vietnam-latest.osm.pbf downloaded (see scripts/maps/download_osm_vietnam.py)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

DATA_DIR="${1:-$PROJECT_ROOT/data/osm/raw}"
OSRM_DATA="$PROJECT_ROOT/infra/maps/osrm/data"
PBF_FILE="$DATA_DIR/vietnam-latest.osm.pbf"
OSRM_IMAGE="ghcr.io/project-osrm/osrm-backend:v5.27.1"

if [ ! -f "$PBF_FILE" ]; then
    echo "[ERROR] OSM data not found: $PBF_FILE"
    echo "        Run: python scripts/maps/download_osm_vietnam.py"
    exit 1
fi

echo "[INFO] Using OSM data: $PBF_FILE"
echo "[INFO] OSRM output:    $OSRM_DATA"
mkdir -p "$OSRM_DATA"

# Copy PBF to OSRM data directory
cp "$PBF_FILE" "$OSRM_DATA/vietnam-latest.osm.pbf"

echo ""
echo "=== Step 1/3: osrm-extract (car profile, MLD) ==="
docker run --rm -v "$OSRM_DATA:/data" "$OSRM_IMAGE" \
    osrm-extract -p /opt/car.lua /data/vietnam-latest.osm.pbf

echo ""
echo "=== Step 2/3: osrm-partition ==="
docker run --rm -v "$OSRM_DATA:/data" "$OSRM_IMAGE" \
    osrm-partition /data/vietnam-latest.osrm

echo ""
echo "=== Step 3/3: osrm-customize ==="
docker run --rm -v "$OSRM_DATA:/data" "$OSRM_IMAGE" \
    osrm-customize /data/vietnam-latest.osrm

echo ""
echo "[DONE] OSRM graph built successfully."
echo "       Start with: bash scripts/maps/run_osrm.sh"
echo "       Or: docker compose -f docker-compose.maps.yml up osrm"
