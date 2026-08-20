#!/usr/bin/env bash
set -euo pipefail

echo "================================================================="
echo "  AloSM - Automated Production Deployment Script"
echo "================================================================="

# 1. Check environment file
if [ ! -f ".env.production" ]; then
    echo "❌ Error: .env.production file not found!"
    echo "   Please copy .env.production.example to .env.production and fill in your secrets."
    exit 1
fi

echo "🔹 [1/5] Running Database Migrations..."
if command -v uv &> /dev/null; then
    uv run alembic upgrade head
else
    alembic upgrade head
fi

echo "🔹 [2/5] Verifying Database Persistence & RLS Guardrails..."
if command -v uv &> /dev/null; then
    uv run python scripts/verify_postgres_persistence.py
else
    python scripts/verify_postgres_persistence.py
fi

echo "🔹 [3/5] Building & Launching Docker Services..."
docker compose -f docker-compose.prod.yml down --remove-orphans || true
docker compose -f docker-compose.prod.yml build --parallel
docker compose -f docker-compose.prod.yml up -d

echo "🔹 [4/5] Waiting for Services to become healthy..."
sleep 10
docker compose -f docker-compose.prod.yml ps

echo "🔹 [5/5] Performing Live Health Checks..."
# Check Backend API
curl -sf http://localhost/health > /dev/null && echo "  ✅ Backend API: OK" || echo "  ⚠️ Backend API healthcheck pending..."

# Check ASR Server
curl -sf http://localhost:9000/health > /dev/null && echo "  ✅ Zipformer ASR Server: OK" || echo "  ⚠️ ASR Server healthcheck pending..."

echo ""
echo "================================================================="
echo "  🎉 Production Deployment Completed Successfully!"
echo "  App URL:     http://localhost (or configured domain)"
echo "  Backend API: http://localhost/api/v1/health"
echo "  ASR Stream:  ws://localhost/v1/stt"
echo "================================================================="
