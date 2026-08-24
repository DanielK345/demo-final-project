#!/usr/bin/env bash
set -euo pipefail

# Automated Docker build & push script to GitHub Container Registry (GHCR)
# Usage:
#   GHCR_PAT="ghp_..." ./scripts/deploy_to_ghcr.sh
#   ./scripts/deploy_to_ghcr.sh <GITHUB_USER> <IMAGE_NAME> <TAG> <TOKEN>

GITHUB_USER="${1:-${GHCR_USER:-NamKhanh2128}}"
IMAGE_NAME="${2:-${GHCR_IMAGE:-alosm-backend}}"
TAG="${3:-${GHCR_TAG:-latest}}"
TOKEN="${4:-${GHCR_PAT:-}}"

if [ -z "$TOKEN" ]; then
    echo -n "Nhập GitHub Token (cần quyền write:packages): "
    read -rs TOKEN
    echo ""
fi

# Convert to lowercase as required by GHCR
LOWER_USER=$(echo "$GITHUB_USER" | tr '[:upper:]' '[:lower:]')
LOWER_IMAGE=$(echo "$IMAGE_NAME" | tr '[:upper:]' '[:lower:]')
FULL_IMAGE_NAME="ghcr.io/${LOWER_USER}/${LOWER_IMAGE}:${TAG}"

echo "==> [1/3] Đăng nhập vào GitHub Container Registry (ghcr.io)..."
echo "$TOKEN" | docker login ghcr.io -u "$GITHUB_USER" --password-stdin

echo "==> [2/3] Đóng gói Docker image: $FULL_IMAGE_NAME..."
docker build -t "$FULL_IMAGE_NAME" -f Dockerfile .

echo "==> [3/3] Đang push image lên GHCR..."
docker push "$FULL_IMAGE_NAME"

echo ""
echo "✅ ĐÃ HOÀN TẤT ĐÓNG GÓI VÀ PUSH LÊN GHCR THÀNH CÔNG!"
echo "Image: $FULL_IMAGE_NAME"
echo "Pull command: docker pull $FULL_IMAGE_NAME"
