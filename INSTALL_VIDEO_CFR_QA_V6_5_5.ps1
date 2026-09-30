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
$Targets = @(
    "app/modules/tao_video_ai/service.py",
    "app/modules/ai_video_director/auto_producer.py",
    "app/modules/ai_video_director/quality.py"
)

Show-AivfBanner -Text "AI VIDEO FACTORY V6.5.5 - VIDEO CFR QA FIX"

if (-not (Test-Path -LiteralPath (Join-Path -Path $Root -ChildPath "app") -PathType Container)) {
    Write-Host "[LOI] Khong thay thu muc app. Giai nen TOAN BO ZIP vao thu muc goc ai_video_factory." -ForegroundColor Red
    exit 2
}
foreach ($Rel in $Targets) {
    $Src = Join-AivfPath -Base $Payload -Relative $Rel
    if (-not (Test-Path -LiteralPath $Src -PathType Leaf)) {
        Write-Host ("[LOI] Thieu payload: " + $Rel) -ForegroundColor Red
        exit 3
    }
}

$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupRoot = Join-Path -Path $Root -ChildPath ("_BACKUP_VIDEO_CFR_QA_V6_5_5_" + $Stamp)
New-Item -ItemType Directory -Path $BackupRoot -Force | Out-Null
$NewFiles = New-Object System.Collections.Generic.List[string]

function Restore-AivfBackup {
    param([Parameter(Mandatory=$true)][string]$Reason)
    Show-AivfBanner -Text "ROLLBACK" -Color Red
    Write-Host $Reason -ForegroundColor Red
    foreach ($Rel in $Targets) {
        $Target = Join-AivfPath -Base $Root -Relative $Rel
        $Backup = Join-AivfPath -Base $BackupRoot -Relative $Rel
        if (Test-Path -LiteralPath $Backup -PathType Leaf) {
            New-Item -ItemType Directory -Path (Split-Path -Parent $Target) -Force | Out-Null
            Copy-Item -LiteralPath $Backup -Destination $Target -Force
        }
    }
    foreach ($Rel in $NewFiles) {
        $Target = Join-AivfPath -Base $Root -Relative $Rel
        if (Test-Path -LiteralPath $Target -PathType Leaf) {
            Remove-Item -LiteralPath $Target -Force -ErrorAction SilentlyContinue
        }
    }
    Write-Host "Da khoi phuc source cu." -ForegroundColor Yellow
    Write-Host ("Backup: " + $BackupRoot) -ForegroundColor Yellow
    exit 10
}

Show-AivfBanner -Text "1/4 - BACKUP"
foreach ($Rel in $Targets) {
    $Target = Join-AivfPath -Base $Root -Relative $Rel
    $Backup = Join-AivfPath -Base $BackupRoot -Relative $Rel
    if (Test-Path -LiteralPath $Target -PathType Leaf) {
        New-Item -ItemType Directory -Path (Split-Path -Parent $Backup) -Force | Out-Null
        Copy-Item -LiteralPath $Target -Destination $Backup -Force
        Write-Host ("BACKUP  " + $Rel)
    } else {
        $NewFiles.Add($Rel)
        Write-Host ("NEW     " + $Rel)
    }
}

Show-AivfBanner -Text "2/4 - PATCH"
try {
    foreach ($Rel in $Targets) {
        $Source = Join-AivfPath -Base $Payload -Relative $Rel
        $Target = Join-AivfPath -Base $Root -Relative $Rel
        New-Item -ItemType Directory -Path (Split-Path -Parent $Target) -Force | Out-Null
        Copy-Item -LiteralPath $Source -Destination $Target -Force
        Write-Host ("PATCH   " + $Rel) -ForegroundColor Green
    }
} catch {
    Restore-AivfBackup -Reason ("Copy patch that bai: " + $_.Exception.Message)
}

Show-AivfBanner -Text "3/4 - COMPILE + REAL CFR VERIFY"
$Py = Get-Command python -ErrorAction SilentlyContinue
if ($null -eq $Py) { Restore-AivfBackup -Reason "Khong tim thay python trong PATH." }

$Compile = @()
foreach ($Rel in $Targets) { $Compile += (Join-AivfPath -Base $Root -Relative $Rel) }
& $Py.Source -m py_compile @Compile
if ($LASTEXITCODE -ne 0) { Restore-AivfBackup -Reason "PY_COMPILE FAIL." }
Write-Host "PY_COMPILE: PASS" -ForegroundColor Green

$Verify = Join-Path -Path $Root -ChildPath "VERIFY_VIDEO_CFR_QA_V6_5_5.py"
Push-Location $Root
try {
    & $Py.Source $Verify
    if ($LASTEXITCODE -ne 0) { Restore-AivfBackup -Reason "VIDEO CFR REAL VERIFY FAIL." }
} finally {
    Pop-Location
}

Show-AivfBanner -Text "4/4 - INSTALLED" -Color Green
Write-Host "VIDEO CFR QA V6.5.5: PASS" -ForegroundColor Green
Write-Host "Fix: SVD low native cadence -> strict CFR 30fps -> QA on normalized master" -ForegroundColor Cyan
Write-Host "Khong ha nguong QA va khong bo qua loi. FPS output duoc ffprobe kiem tra." -ForegroundColor Cyan
Write-Host ("Backup source cu: " + $BackupRoot) -ForegroundColor Yellow
Write-Host "Khoi dong lai AI Video Factory roi chay AUTO PRODUCE lai." -ForegroundColor Yellow
exit 0
