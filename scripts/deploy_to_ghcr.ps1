# Automated Docker build & push script to GitHub Container Registry (GHCR)
# Usage:
#   .\scripts\deploy_to_ghcr.ps1 -Namespace "AI20K-Build-Phase-Cohort-3/p-160" -Token "ghp_..."
#   .\scripts\deploy_to_ghcr.ps1 -Namespace "NamKhanh2128" -ImageName "alosm-backend" -Token "ghp_..."

param(
    [string]$Namespace = "ai20k-build-phase-cohort-3/p-160",
    [string]$ImageName = "backend",
    [string]$Tag = "latest",
    [string]$Token = $env:GHCR_PAT,
    [string]$GithubUser = $env:GITHUB_ACTOR
)

$ErrorActionPreference = "Stop"

# Auto-detect GitHub username if not provided
if (-not $GithubUser) {
    if ($Namespace -notmatch "/") {
        $GithubUser = $Namespace
    } else {
        $GithubUser = "NamKhanh2128"
    }
}

if (-not $Token) {
    Write-Host "=================================================================" -ForegroundColor Yellow
    Write-Host "  GHCR Deployment Script" -ForegroundColor Yellow
    Write-Host "  Vui long cung cap GitHub Personal Access Token (PAT)" -ForegroundColor Yellow
    Write-Host "  yeu cau scope: write:packages, read:packages" -ForegroundColor Yellow
    Write-Host "=================================================================" -ForegroundColor Yellow
    $Token = Read-Host -Prompt "GitHub Token (ghp_...)"
}

# GHCR repository names MUST be lowercased
$CleanNamespace = $Namespace.ToLower().Trim()
$CleanImageName = $ImageName.ToLower().Trim()
if ($CleanNamespace -match "/") {
    $FullImageName = "ghcr.io/$CleanNamespace:$Tag"
} else {
    $FullImageName = "ghcr.io/$CleanNamespace/$CleanImageName:$Tag"
}

Write-Host "`nTarget Image: $FullImageName" -ForegroundColor Magenta
Write-Host "==> [1/3] Logging in to GitHub Container Registry (ghcr.io)..." -ForegroundColor Cyan

# Check if native Docker CLI is available
$hasDocker = Get-Command docker -ErrorAction SilentlyContinue

if ($hasDocker) {
    $Token | docker login ghcr.io -u $GithubUser --password-stdin
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Loi dang nhap GHCR bang Docker! Kiem tra lai Token va Username ($GithubUser)." -ForegroundColor Red
        exit 1
    }

    Write-Host "==> [2/3] Building Docker image: $FullImageName..." -ForegroundColor Cyan
    docker build -t $FullImageName -f Dockerfile .
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Loi build Docker image!" -ForegroundColor Red
        exit 1
    }

    Write-Host "==> [3/3] Pushing image to GHCR..." -ForegroundColor Cyan
    docker push $FullImageName
} else {
    Write-Host "[Note] Docker tren Windows khong tim thay, chuyen sang dung WSL..." -ForegroundColor Yellow
    $Token | wsl -d Ubuntu-24.04 docker login ghcr.io -u $GithubUser --password-stdin
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Loi dang nhap GHCR qua WSL! Kiem tra lai Token va Username ($GithubUser)." -ForegroundColor Red
        exit 1
    }

    Write-Host "==> [2/3] Building Docker image qua WSL: $FullImageName..." -ForegroundColor Cyan
    wsl -d Ubuntu-24.04 docker build -t $FullImageName -f Dockerfile .
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Loi build Docker image!" -ForegroundColor Red
        exit 1
    }

    Write-Host "==> [3/3] Pushing image to GHCR qua WSL..." -ForegroundColor Cyan
    wsl -d Ubuntu-24.04 docker push $FullImageName
}

if ($LASTEXITCODE -eq 0) {
    Write-Host "`nSUCCESS: Docker image pushed to GHCR successfully!" -ForegroundColor Green
    Write-Host "Image URI: $FullImageName" -ForegroundColor Yellow
    Write-Host "Pull command: docker pull $FullImageName" -ForegroundColor Cyan
} else {
    Write-Host "Loi khi push image len GHCR! Hay dam bao Token co quyen write:packages cho namespace nay." -ForegroundColor Red
    exit 1
}
