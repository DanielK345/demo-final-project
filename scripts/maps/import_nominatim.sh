#!/usr/bin/env bash
# Import Vietnam OSM data into Nominatim (§12)
#
# Usage:
#   bash scripts/maps/import_nominatim.sh [--data-dir DIR]
#
# Prerequisites:
#   - Docker installed and running
#   - vietnam-latest.osm.pbf downloaded

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
DATA_DIR="${1:-$PROJECT_ROOT/data/osm/raw}"
NOM_DATA="$PROJECT_ROOT/infra/maps/nominatim/data"
PBF_FILE="$DATA_DIR/vietnam-latest.osm.pbf"
NOMINATIM_IMAGE="mediagis/nominatim:4.4"

if [ ! -f "$PBF_FILE" ]; then
    echo "[ERROR] OSM data not found: $PBF_FILE"
    echo "        Run: python scripts/maps/download_osm_vietnam.py"
    exit 1
fi

echo "[INFO] Importing OSM data into Nominatim"
echo "[INFO] PBF: $PBF_FILE"
echo "[INFO] Nominatim data: $NOM_DATA"

mkdir -p "$NOM_DATA/postgresql" "$NOM_DATA/flatnode"

# Copy PBF
cp "$PBF_FILE" "$NOM_DATA/vietnam-latest.osm.pbf"

echo ""
echo "Starting Nominatim import container..."
echo "This may take 30-60 minutes depending on hardware."
echo ""

docker run --rm \
    -e PBF_PATH=/data/vietnam-latest.osm.pbf \
    -e REPLICATION_URL=https://download.geofabrik.de/asia/vietnam-updates \
    -e NOMINATIM_PASSWORD=nominatim_dev_password \
    -v "$NOM_DATA:/data" \
    -v "$NOM_DATA/postgresql:/var/lib/postgresql/14/main" \
    -v "$NOM_DATA/flatnode:/nominatim/flatnode" \
    -p 8088:8080 \
    "$NOMINATIM_IMAGE"
