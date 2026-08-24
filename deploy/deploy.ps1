# =================================================================
#   AloSM - Automated Production Deployment Script (PowerShell)
# =================================================================
$ErrorActionPreference = "Continue"

Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host "  AloSM - Automated Production Deployment Script" -ForegroundColor Cyan
Write-Host "=================================================================" -ForegroundColor Cyan

# 1. Check environment file (fallback to .env if .env.production is missing)
if (-not (Test-Path ".env.production")) {
    if (Test-Path ".env") {
        Write-Host "[INFO] Copying .env to .env.production..." -ForegroundColor Yellow
        Copy-Item ".env" ".env.production"
    } else {
        Write-Host "[ERROR] .env.production or .env file not found!" -ForegroundColor Red
        Write-Host "Please copy .env.production.example to .env.production and fill in your secrets." -ForegroundColor Yellow
        Exit 1
    }
}

Write-Host "[1/5] Running Database Migrations..." -ForegroundColor Green
uv run alembic upgrade head

Write-Host "[2/5] Verifying Database Persistence and RLS Guardrails..." -ForegroundColor Green
uv run python scripts/verify_postgres_persistence.py

Write-Host "[3/5] Building and Launching Docker Services..." -ForegroundColor Green
docker compose -f docker-compose.prod.yml down --remove-orphans
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d

Write-Host "[4/5] Waiting for Services to initialize..." -ForegroundColor Green
Start-Sleep -Seconds 10
docker compose -f docker-compose.prod.yml ps

Write-Host ""
Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host "  Production Deployment Completed Successfully!" -ForegroundColor Green
Write-Host "  App URL:     http://localhost" -ForegroundColor White
Write-Host "  Backend API: http://localhost/api/v1/health" -ForegroundColor White
Write-Host "  ASR Stream:  ws://localhost/v1/stt" -ForegroundColor White
Write-Host "=================================================================" -ForegroundColor Cyan
