$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Show-AivfBanner {
    param([Parameter(Mandatory=$true)][string]$Text, [ConsoleColor]$Color = [ConsoleColor]::Cyan)
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor $Color
    Write-Host ("  " + $Text) -ForegroundColor $Color
    Write-Host "============================================================" -ForegroundColor $Color
}

function Join-AivfPath {
    param([Parameter(Mandatory=$true)][string]$Base, [Parameter(Mandatory=$true)][string]$Relative)
    return (Join-Path -Path $Base -ChildPath ($Relative -replace '/', '\'))
}

$Root = $PSScriptRoot
$Payload = Join-Path -Path $Root -ChildPath "_PATCH_PAYLOAD"
$TargetRel = "app/modules/tao_anh_ai/service.py"
$Target = Join-AivfPath -Base $Root -Relative $TargetRel
$Source = Join-AivfPath -Base $Payload -Relative $TargetRel

Show-AivfBanner -Text "AI VIDEO FACTORY V6.5.3 - TAO ANH AI ANTI SHEET FIX"

if (-not (Test-Path -LiteralPath (Join-Path -Path $Root -ChildPath 'app') -PathType Container)) {
    Write-Host "[LOI] Khong thay thu muc app." -ForegroundColor Red
    Write-Host "Giai nen TOAN BO ZIP truc tiep vao thu muc goc ai_video_factory." -ForegroundColor Yellow
    exit 2
}
if (-not (Test-Path -LiteralPath $Source -PathType Leaf)) {
    Write-Host "[LOI] Thieu _PATCH_PAYLOAD." -ForegroundColor Red
    Write-Host "Khong copy rieng BAT/PS1." -ForegroundColor Yellow
    exit 3
}

$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupRoot = Join-Path -Path $Root -ChildPath ("_BACKUP_TAO_ANH_AI_V6_5_3_" + $Stamp)
$Backup = Join-AivfPath -Base $BackupRoot -Relative $TargetRel
New-Item -ItemType Directory -Path (Split-Path -Parent $Backup) -Force | Out-Null
$Patched = $false

function Rollback-Aivf {
    param([Parameter(Mandatory=$true)][string]$Reason)
    Show-AivfBanner -Text "ROLLBACK" -Color Red
    Write-Host $Reason -ForegroundColor Red
    if (Test-Path -LiteralPath $Backup -PathType Leaf) {
        New-Item -ItemType Directory -Path (Split-Path -Parent $Target) -Force | Out-Null
        Copy-Item -LiteralPath $Backup -Destination $Target -Force
        Write-Host "Da khoi phuc file cu." -ForegroundColor Yellow
    } elseif ($Patched -and (Test-Path -LiteralPath $Target -PathType Leaf)) {
        Remove-Item -LiteralPath $Target -Force -ErrorAction SilentlyContinue
        Write-Host "Da xoa file moi de rollback." -ForegroundColor Yellow
    }
    Write-Host ("Backup: " + $BackupRoot) -ForegroundColor Yellow
    exit 10
}

Show-AivfBanner -Text "1/4 - BACKUP"
if (Test-Path -LiteralPath $Target -PathType Leaf) {
    Copy-Item -LiteralPath $Target -Destination $Backup -Force
    Write-Host ("BACKUP  " + $TargetRel)
} else {
    Write-Host ("NEW     " + $TargetRel)
}

Show-AivfBanner -Text "2/4 - PATCH"
try {
    New-Item -ItemType Directory -Path (Split-Path -Parent $Target) -Force | Out-Null
    Copy-Item -LiteralPath $Source -Destination $Target -Force
    $Patched = $true
    Write-Host ("PATCH   " + $TargetRel) -ForegroundColor Green
} catch {
    Rollback-Aivf -Reason ("Copy patch that bai: " + $_.Exception.Message)
}

Show-AivfBanner -Text "3/4 - COMPILE + VERIFY"
$Py = Get-Command python -ErrorAction SilentlyContinue
if ($null -eq $Py) {
    Rollback-Aivf -Reason "Khong tim thay python trong PATH."
}

& $Py.Source -m py_compile $Target
if ($LASTEXITCODE -ne 0) {
    Rollback-Aivf -Reason "PY_COMPILE FAIL."
}
Write-Host "PY_COMPILE: PASS" -ForegroundColor Green

$VerifyScript = Join-Path -Path $Root -ChildPath 'VERIFY_TAO_ANH_AI_V6_5_3.py'
Push-Location $Root
try {
    & $Py.Source $VerifyScript
    if ($LASTEXITCODE -ne 0) {
        Rollback-Aivf -Reason "VERIFY FAIL."
    }
} finally {
    Pop-Location
}

Show-AivfBanner -Text "4/4 - INSTALLED" -Color Green
Write-Host "TAO ANH AI V6.5.3: PASS" -ForegroundColor Green
Write-Host "Fix: anti character-sheet / anti lineup / anti multi-view mạnh hơn" -ForegroundColor Cyan
Write-Host ("Backup source cu: " + $BackupRoot) -ForegroundColor Yellow
Write-Host "Khoi dong lai AI Video Factory roi test lai module Tao Anh AI." -ForegroundColor Yellow
exit 0
