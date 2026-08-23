# Automated Docker build & push script to GitHub Container Registry (GHCR)
# Usage:
#   .\scripts\deploy_to_ghcr.ps1 -GithubUser "NamKhanh2128" -Token "ghp_..."
#   or set $env:GHCR_PAT and run .\scripts\deploy_to_ghcr.ps1

param(
    [string]$GithubUser = "NamKhanh2128",
    [string]$ImageName = "alosm-backend",
    [string]$Tag = "latest",
    [string]$Token = $env:GHCR_PAT
)

$ErrorActionPreference = "Stop"

if (-not $Token) {
    Write-Host "Vui lòng cung cấp GitHub Personal Access Token (PAT) có quyền 'write:packages' & 'read:packages':" -ForegroundColor Yellow
    $Token = Read-Host -Prompt "GitHub Token (ghp_...)" -AsSecureString
    $BSTR = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($Token)
    $Token = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($BSTR)
}

$FullImageName = "ghcr.io/$($GithubUser.ToLower())/$($ImageName.ToLower()):$Tag"

Write-Host "==> [1/3] Đăng nhập vào GitHub Container Registry (ghcr.io)..." -ForegroundColor Cyan
$loginProcess = Start-Process -FilePath "docker" -ArgumentList "login ghcr.io -u $GithubUser --password-stdin" -NoNewWindow -PassThru -RedirectStandardInput ([System.IO.Path]::GetTempFileName())
$Token | docker login ghcr.io -u $GithubUser --password-stdin

if ($LASTEXITCODE -ne 0) {
    Write-Host "Lỗi đăng nhập GHCR! Hãy đảm bảo token có scope 'write:packages' và 'read:packages'." -ForegroundColor Red
    exit 1
}

Write-Host "==> [2/3] Đang đóng gói Docker image: $FullImageName..." -ForegroundColor Cyan
docker build -t $FullImageName -f Dockerfile .

if ($LASTEXITCODE -ne 0) {
    Write-Host "Lỗi build Docker image!" -ForegroundColor Red
    exit 1
}

Write-Host "==> [3/3] Đang đẩy (push) image lên GHCR..." -ForegroundColor Cyan
docker push $FullImageName

if ($LASTEXITCODE -eq 0) {
    Write-Host "`nĐÃ HOÀN TẤT ĐÓNG GÓI VÀ PUSH LÊN GHCR THÀNH CÔNG!" -ForegroundColor Green
    Write-Host "Image URL: https://github.com/$GithubUser/$ImageName/pkgs/container/$ImageName" -ForegroundColor Yellow
    Write-Host "Pull command: docker pull $FullImageName" -ForegroundColor Cyan
} else {
    Write-Host "Lỗi khi push image lên GHCR!" -ForegroundColor Red
}
