#!/usr/bin/env bash
# Check Nominatim health (§13)
#
# Usage:
#   bash scripts/maps/check_nominatim.sh [URL]

set -euo pipefail

BASE_URL="${1:-http://localhost:8088}"

echo "=== Nominatim Health Check ==="
echo "URL: $BASE_URL"
echo ""

echo "--- /status ---"
STATUS=$(curl -s "$BASE_URL/status?format=json" 2>&1) || true
echo "$STATUS" | python3 -m json.tool 2>/dev/null || echo "$STATUS"
echo ""

echo "--- Search test: Bưu điện Hà Nội ---"
SEARCH=$(curl -s "$BASE_URL/search?q=B%C6%B0u+%C4%91i%E1%BB%87n+H%C3%A0+N%E1%BB%99i&format=jsonv2&limit=3&countrycodes=vn" 2>&1) || true
echo "$SEARCH" | python3 -m json.tool 2>/dev/null || echo "$SEARCH"
echo ""

echo "--- Reverse test: 21.0285, 105.8542 (Hanoi) ---"
REVERSE=$(curl -s "$BASE_URL/reverse?lat=21.0285&lon=105.8542&format=jsonv2" 2>&1) || true
echo "$REVERSE" | python3 -m json.tool 2>/dev/null || echo "$REVERSE"
echo ""

echo "[DONE] Nominatim check complete."
