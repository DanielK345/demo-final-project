# Automated Docker build & push script to GitHub Container Registry (GHCR)
# Usage:
#   .\scripts\deploy_to_ghcr.ps1 -GithubUser "NamKhanh2128" -Token "ghp_..."

param(
    [string]$GithubUser = "NamKhanh2128",
    [string]$ImageName = "alosm-backend",
    [string]$Tag = "latest",
    [string]$Token = $env:GHCR_PAT
)

$ErrorActionPreference = "Stop"

if (-not $Token) {
    Write-Host "Vui long cung cap GitHub Personal Access Token (PAT) co quyen write:packages va read:packages:" -ForegroundColor Yellow
    $Token = Read-Host -Prompt "GitHub Token (ghp_...)"
}

$FullImageName = "ghcr.io/$($GithubUser.ToLower())/$($ImageName.ToLower()):$Tag"

Write-Host "==> [1/3] Logging in to GitHub Container Registry (ghcr.io)..." -ForegroundColor Cyan
$Token | wsl -d Ubuntu-24.04 docker login ghcr.io -u $GithubUser --password-stdin

if ($LASTEXITCODE -ne 0) {
    Write-Host "Loi dang nhap GHCR! Vui long kiem tra token." -ForegroundColor Red
    exit 1
}

Write-Host "==> [2/3] Building Docker image: $FullImageName..." -ForegroundColor Cyan
wsl -d Ubuntu-24.04 docker build -t $FullImageName -f /mnt/c/Users/KHANH/Documents/GitHub/P-160/Dockerfile /mnt/c/Users/KHANH/Documents/GitHub/P-160

if ($LASTEXITCODE -ne 0) {
    Write-Host "Loi build Docker image!" -ForegroundColor Red
    exit 1
}

Write-Host "==> [3/3] Pushing image to GHCR..." -ForegroundColor Cyan
wsl -d Ubuntu-24.04 docker push $FullImageName

if ($LASTEXITCODE -eq 0) {
    Write-Host "`nSUCCESS: Docker image pushed to GHCR successfully!" -ForegroundColor Green
    Write-Host "Image URL: https://github.com/$GithubUser/$ImageName/pkgs/container/$ImageName" -ForegroundColor Yellow
    Write-Host "Pull command: docker pull $FullImageName" -ForegroundColor Cyan
} else {
    Write-Host "Loi khi push image len GHCR!" -ForegroundColor Red
}
