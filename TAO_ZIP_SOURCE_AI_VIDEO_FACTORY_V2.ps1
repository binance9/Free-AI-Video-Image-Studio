$ErrorActionPreference = "Stop"

function Write-Step([string]$Text) {
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host $Text -ForegroundColor Cyan
    Write-Host "============================================================" -ForegroundColor Cyan
}

# LUON lay thu muc dang chua file PS1. Khong truyen -Root de tranh loi
# duong dan Unicode / dau cach / dau \ cuoi tren Windows.
$Root = $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($Root)) {
    $Root = (Get-Location).Path
}

Write-Step "AI VIDEO FACTORY - SOURCE COLLECTOR V2"
Write-Host "Root: $Root"

$appPath = Join-Path $Root "app"
if (-not (Test-Path -LiteralPath $appPath -PathType Container)) {
    Write-Host ""
    Write-Host "[LOI] Khong thay thu muc app trong:" -ForegroundColor Red
    Write-Host $Root -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Dat BAT + PS1 V2 truc tiep vao thu muc goc ai_video_factory roi chay BAT." -ForegroundColor Yellow
    exit 2
}

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$temp = Join-Path $env:TEMP ("AI_VIDEO_FACTORY_SOURCE_" + $stamp)
$stage = Join-Path $temp "ai_video_factory"
$zipPath = Join-Path $Root ("AI_VIDEO_FACTORY_SOURCE_FOR_GA_" + $stamp + ".zip")

New-Item -ItemType Directory -Path $stage -Force | Out-Null

$includeDirs = @(
    "app",
    "web",
    "frontend",
    "static",
    "templates",
    "tests",
    "scripts",
    "tools"
)

$rootPatterns = @(
    "*.py","*.bat","*.cmd","*.ps1",
    "*.json","*.toml","*.yaml","*.yml",
    "*.ini","*.cfg","*.txt","*.md"
)

$excludeDirNames = @(
    ".git",".idea",".vscode",
    "__pycache__",".pytest_cache",".mypy_cache",".ruff_cache",
    "venv",".venv","env","node_modules",
    "data","models","model","checkpoints","weights",
    "outputs","output","results","result","renders","render",
    "cache",".cache","logs","log","tmp","temp",
    "dist","build"
)

$excludeExtensions = @(
    ".ckpt",".safetensors",".pt",".pth",".bin",".onnx",
    ".mp4",".mov",".avi",".mkv",".webm",
    ".wav",".mp3",".flac",
    ".zip",".7z",".rar",
    ".png",".jpg",".jpeg",".webp",".gif"
)

function Test-ExcludedRelativePath([string]$RelativePath) {
    $parts = $RelativePath -split '[\\/]'
    foreach ($p in $parts) {
        if ($excludeDirNames -contains $p) { return $true }
    }
    return $false
}

function Copy-CodeTree([string]$SourceDir, [string]$DestDir) {
    if (-not (Test-Path -LiteralPath $SourceDir -PathType Container)) { return }

    New-Item -ItemType Directory -Path $DestDir -Force | Out-Null
    $sourcePrefix = $SourceDir.TrimEnd('\','/')

    Get-ChildItem -LiteralPath $SourceDir -File -Recurse -Force -ErrorAction SilentlyContinue | ForEach-Object {
        $f = $_
        $rel = $f.FullName.Substring($sourcePrefix.Length).TrimStart('\','/')

        if (Test-ExcludedRelativePath $rel) { return }

        $ext = $f.Extension.ToLowerInvariant()
        if ($excludeExtensions -contains $ext) { return }
        if ($f.Length -gt 20MB) { return }

        $dst = Join-Path $DestDir $rel
        $dstParent = Split-Path -Parent $dst
        if (-not (Test-Path -LiteralPath $dstParent)) {
            New-Item -ItemType Directory -Path $dstParent -Force | Out-Null
        }
        Copy-Item -LiteralPath $f.FullName -Destination $dst -Force
    }
}

Write-Step "1/4 - COPY CODE"

foreach ($d in $includeDirs) {
    $src = Join-Path $Root $d
    if (Test-Path -LiteralPath $src -PathType Container) {
        Write-Host ("+ " + $d)
        Copy-CodeTree $src (Join-Path $stage $d)
    }
}

foreach ($pattern in $rootPatterns) {
    Get-ChildItem -LiteralPath $Root -File -Filter $pattern -Force -ErrorAction SilentlyContinue | ForEach-Object {
        $ext = $_.Extension.ToLowerInvariant()
        if ($_.Length -le 20MB -and -not ($excludeExtensions -contains $ext)) {
            Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $stage $_.Name) -Force
        }
    }
}

Write-Step "2/4 - TAO THONG TIN GOI SOURCE"

$info = @()
$info += "AI VIDEO FACTORY SOURCE PACKAGE V2"
$info += "Created: $((Get-Date).ToString('yyyy-MM-dd HH:mm:ss'))"
$info += "Original root: $Root"
$info += ""
$info += "Included if present: app, web, frontend, static, templates, tests, scripts, tools"
$info += "Excluded: models/data/venv/cache/output/media/archives and files > 20 MB"
$info += ""
$info += "=== LIKELY MODULE PATHS: image / 2d / 3d / video / map / director ==="

$keywords = @("image","anh","2d","3d","video","map","director","tao_anh","tao_video")
Get-ChildItem -LiteralPath $stage -Directory -Recurse -ErrorAction SilentlyContinue | ForEach-Object {
    $lower = $_.Name.ToLowerInvariant()
    foreach ($k in $keywords) {
        if ($lower.Contains($k)) {
            $info += $_.FullName.Substring($stage.Length).TrimStart('\','/')
            break
        }
    }
}

$info | Set-Content -LiteralPath (Join-Path $stage "_SOURCE_PACKAGE_INFO.txt") -Encoding UTF8

Write-Step "3/4 - NEN ZIP"

if (Test-Path -LiteralPath $zipPath) {
    Remove-Item -LiteralPath $zipPath -Force
}

Compress-Archive -LiteralPath $stage -DestinationPath $zipPath -CompressionLevel Optimal

Write-Step "4/4 - HOAN TAT"

$sizeMB = [math]::Round((Get-Item -LiteralPath $zipPath).Length / 1MB, 2)
Write-Host ("ZIP: " + $zipPath) -ForegroundColor Green
Write-Host ("Size: " + $sizeMB + " MB") -ForegroundColor Green
Write-Host ""
Write-Host "GUI FILE ZIP NAY CHO GA." -ForegroundColor Yellow

try {
    Start-Process explorer.exe -ArgumentList "/select,`"$zipPath`""
} catch {}

Remove-Item -LiteralPath $temp -Recurse -Force -ErrorAction SilentlyContinue
