$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Show-AivfBanner {
    param(
        [Parameter(Mandatory=$true)][string]$Text,
        [ConsoleColor]$Color = [ConsoleColor]::Cyan
    )
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor $Color
    Write-Host ("  " + $Text) -ForegroundColor $Color
    Write-Host "============================================================" -ForegroundColor $Color
}

function Join-AivfRelativePath {
    param(
        [Parameter(Mandatory=$true)][string]$Base,
        [Parameter(Mandatory=$true)][string]$Relative
    )
    $child = $Relative -replace '/', '\'
    return (Join-Path -Path $Base -ChildPath $child)
}

$Root = $PSScriptRoot
$Payload = Join-Path -Path $Root -ChildPath "_PATCH_PAYLOAD"

Show-AivfBanner -Text "AI VIDEO FACTORY V6.5.1 - SHARED PROMPT CONTRACT"

if (-not (Test-Path -LiteralPath (Join-Path -Path $Root -ChildPath "app") -PathType Container)) {
    Write-Host "[LOI] Khong thay thu muc app." -ForegroundColor Red
    Write-Host "Giai nen TOAN BO ZIP truc tiep vao thu muc goc ai_video_factory." -ForegroundColor Yellow
    exit 2
}

$ProbePayload = Join-Path -Path $Payload -ChildPath "app\core\prompt_contract.py"
if (-not (Test-Path -LiteralPath $ProbePayload -PathType Leaf)) {
    Write-Host "[LOI] Thieu _PATCH_PAYLOAD." -ForegroundColor Red
    Write-Host "Khong copy rieng BAT/PS1. Hay giai nen day du ZIP vao thu muc goc." -ForegroundColor Yellow
    exit 3
}

$Targets = @(
    "app/core/prompt_contract.py",
    "app/modules/tao_anh_ai/service.py",
    "app/modules/nhan_vat_2d/prompt_builder.py",
    "app/modules/nhan_vat_2d/image_runtime.py",
    "app/modules/nhan_vat_3d/service.py",
    "app/modules/tao_video_ai/service.py",
    "app/modules/ban_do_3d/khoa_bo_cuc.py",
    "app/modules/ban_do_3d/tao_o_ban_do.py",
    "app/modules/ai_video_director/service.py"
)

$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupRoot = Join-Path -Path $Root -ChildPath ("_BACKUP_PROMPT_CONTRACT_V6_5_1_" + $Stamp)
New-Item -ItemType Directory -Path $BackupRoot -Force | Out-Null
$NewFiles = New-Object System.Collections.Generic.List[string]
$PatchStarted = $false

function Restore-AivfBackup {
    param([Parameter(Mandatory=$true)][string]$Reason)

    Show-AivfBanner -Text "ROLLBACK" -Color Red
    Write-Host $Reason -ForegroundColor Red

    foreach ($Rel in $Targets) {
        $Target = Join-AivfRelativePath -Base $Root -Relative $Rel
        $Backup = Join-AivfRelativePath -Base $BackupRoot -Relative $Rel

        if (Test-Path -LiteralPath $Backup -PathType Leaf) {
            $Parent = Split-Path -Parent $Target
            if (-not (Test-Path -LiteralPath $Parent -PathType Container)) {
                New-Item -ItemType Directory -Path $Parent -Force | Out-Null
            }
            Copy-Item -LiteralPath $Backup -Destination $Target -Force
        }
    }

    foreach ($Rel in $NewFiles) {
        $Target = Join-AivfRelativePath -Base $Root -Relative $Rel
        if (Test-Path -LiteralPath $Target -PathType Leaf) {
            Remove-Item -LiteralPath $Target -Force -ErrorAction SilentlyContinue
        }
    }

    Write-Host ""
    if ($PatchStarted) {
        Write-Host "Da khoi phuc source cu." -ForegroundColor Yellow
    } else {
        Write-Host "Patch chua ghi file nao; source cu van nguyen." -ForegroundColor Yellow
    }
    Write-Host ("Backup: " + $BackupRoot) -ForegroundColor Yellow
    exit 10
}

Show-AivfBanner -Text "1/4 - BACKUP"
try {
    foreach ($Rel in $Targets) {
        $Target = Join-AivfRelativePath -Base $Root -Relative $Rel
        $Backup = Join-AivfRelativePath -Base $BackupRoot -Relative $Rel

        if (Test-Path -LiteralPath $Target -PathType Leaf) {
            $Parent = Split-Path -Parent $Backup
            if (-not (Test-Path -LiteralPath $Parent -PathType Container)) {
                New-Item -ItemType Directory -Path $Parent -Force | Out-Null
            }
            Copy-Item -LiteralPath $Target -Destination $Backup -Force
            Write-Host ("BACKUP  " + $Rel)
        } else {
            $NewFiles.Add($Rel)
            Write-Host ("NEW     " + $Rel)
        }
    }
} catch {
    Restore-AivfBackup -Reason ("Backup that bai: " + $_.Exception.Message)
}

Show-AivfBanner -Text "2/4 - PATCH"
try {
    $PatchStarted = $true
    foreach ($Rel in $Targets) {
        $Source = Join-AivfRelativePath -Base $Payload -Relative $Rel
        $Target = Join-AivfRelativePath -Base $Root -Relative $Rel

        if (-not (Test-Path -LiteralPath $Source -PathType Leaf)) {
            Restore-AivfBackup -Reason ("Thieu payload: " + $Rel)
        }

        $Parent = Split-Path -Parent $Target
        if (-not (Test-Path -LiteralPath $Parent -PathType Container)) {
            New-Item -ItemType Directory -Path $Parent -Force | Out-Null
        }

        Copy-Item -LiteralPath $Source -Destination $Target -Force
        Write-Host ("PATCH   " + $Rel) -ForegroundColor Green
    }
} catch {
    Restore-AivfBackup -Reason ("Copy patch that bai: " + $_.Exception.Message)
}

Show-AivfBanner -Text "3/4 - COMPILE + VERIFY"
$Py = Get-Command python -ErrorAction SilentlyContinue
if ($null -eq $Py) {
    Restore-AivfBackup -Reason "Khong tim thay python trong PATH."
}

$CompileTargets = @()
foreach ($Rel in $Targets) {
    $CompileTargets += (Join-AivfRelativePath -Base $Root -Relative $Rel)
}

& $Py.Source -m py_compile @CompileTargets
if ($LASTEXITCODE -ne 0) {
    Restore-AivfBackup -Reason "PY_COMPILE FAIL."
}
Write-Host "PY_COMPILE: PASS" -ForegroundColor Green

$VerifyScript = Join-Path -Path $Root -ChildPath "VERIFY_PROMPT_CONTRACT_V6_5.py"
if (-not (Test-Path -LiteralPath $VerifyScript -PathType Leaf)) {
    Restore-AivfBackup -Reason "Thieu VERIFY_PROMPT_CONTRACT_V6_5.py."
}

Push-Location $Root
try {
    & $Py.Source $VerifyScript
    if ($LASTEXITCODE -ne 0) {
        Restore-AivfBackup -Reason "PROMPT CONTRACT VERIFY FAIL."
    }
} finally {
    Pop-Location
}

Show-AivfBanner -Text "4/4 - INSTALLED" -Color Green
Write-Host "PROMPT CONTRACT V6.5.1: PASS" -ForegroundColor Green
Write-Host "Dong bo: Anh AI + 2D + 3D + Video + Map + AI Video Director" -ForegroundColor Cyan
Write-Host ""
Write-Host ("Backup source cu: " + $BackupRoot) -ForegroundColor Yellow
Write-Host "Khoi dong lai AI Video Factory roi test." -ForegroundColor Yellow
exit 0
