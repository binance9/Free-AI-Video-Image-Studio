param(
    [string]$Root = ""
)

$ErrorActionPreference = "Stop"

function Write-Step([string]$Text) {
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host $Text -ForegroundColor Cyan
    Write-Host "============================================================" -ForegroundColor Cyan
}

if ([string]::IsNullOrWhiteSpace($Root)) {
    $Root = Split-Path -Parent $MyInvocation.MyCommand.Path
}

$Root = [System.IO.Path]::GetFullPath($Root)

Write-Step "AI VIDEO FACTORY - SOURCE COLLECTOR"
Write-Host "Root: $Root"

if (-not (Test-Path -LiteralPath (Join-Path $Root "app"))) {
    Write-Host ""
    Write-Host "[LOI] Khong thay thu muc 'app'." -ForegroundColor Red
    Write-Host "Hay dat 2 file BAT + PS1 nay vao THU MUC GOC ai_video_factory roi chay BAT." -ForegroundColor Yellow
    exit 2
}

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$temp = Join-Path $env:TEMP ("AI_VIDEO_FACTORY_SOURCE_" + $stamp)
$stage = Join-Path $temp "ai_video_factory"
$zipPath = Join-Path $Root ("AI_VIDEO_FACTORY_SOURCE_FOR_GA_" + $stamp + ".zip")

New-Item -ItemType Directory -Path $stage -Force | Out-Null

# Thu muc code can lay. Neu co thi lay, khong co thi bo qua.
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

# File goc nho, phuc vu route/config/startup.
$rootPatterns = @(
    "*.py","*.bat","*.cmd","*.ps1",
    "*.json","*.toml","*.yaml","*.yml",
    "*.ini","*.cfg","*.txt","*.md"
)

# Tuyet doi khong lay model/cache/output/venv.
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

function Is-ExcludedPath([string]$FullPath, [string]$BasePath) {
    $relative = $FullPath.Substring($BasePath.Length).TrimStart('\','/')
    $parts = $relative -split '[\\/]'
    foreach ($p in $parts) {
        if ($excludeDirNames -contains $p) { return $true }
    }
    return $false
}

function Copy-CodeTree([string]$SourceDir, [string]$DestDir) {
    if (-not (Test-Path -LiteralPath $SourceDir)) { return }

    New-Item -ItemType Directory -Path $DestDir -Force | Out-Null

    Get-ChildItem -LiteralPath $SourceDir -File -Recurse -Force -ErrorAction SilentlyContinue | ForEach-Object {
        $f = $_
        if (Is-ExcludedPath $f.FullName $SourceDir) { return }

        $ext = $f.Extension.ToLowerInvariant()
        if ($excludeExtensions -contains $ext) { return }

        # Bo file qua lon > 20 MB de ZIP van nhe.
        if ($f.Length -gt 20MB) { return }

        $rel = $f.FullName.Substring($SourceDir.Length).TrimStart('\','/')
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
    if (Test-Path -LiteralPath $src) {
        Write-Host ("+ " + $d)
        Copy-CodeTree $src (Join-Path $stage $d)
    }
}

foreach ($pattern in $rootPatterns) {
    Get-ChildItem -LiteralPath $Root -File -Filter $pattern -Force -ErrorAction SilentlyContinue | ForEach-Object {
        if ($_.Length -le 20MB -and -not ($excludeExtensions -contains $_.Extension.ToLowerInvariant())) {
            Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $stage $_.Name) -Force
        }
    }
}

Write-Step "2/4 - TAO DANH SACH MODULE LIEN QUAN"

$manifest = New-Object System.Collections.Generic.List[string]
$manifest.Add("AI VIDEO FACTORY SOURCE PACKAGE")
$manifest.Add("Created: " + (Get-Date).ToString("yyyy-MM-dd HH:mm:ss"))
$manifest.Add("Original root: " + $Root)
$manifest.Add("")
$manifest.Add("Thu muc/code duoc gom, neu ton tai: app, web, frontend, static, templates, tests, scripts, tools")
$manifest.Add("Da loai bo: models/data/venv/cache/output/media/archives va file > 20 MB")
$manifest.Add("")
$manifest.Add("=== MODULE/FOLDER MATCH: image / 2d / 3d / video / map / director ===")

$keywords = @("image","anh","2d","3d","video","map","director","tao_anh","tao_video")
Get-ChildItem -LiteralPath $stage -Directory -Recurse -ErrorAction SilentlyContinue | ForEach-Object {
    $n = $_.Name.ToLowerInvariant()
    foreach ($k in $keywords) {
        if ($n.Contains($k)) {
            $manifest.Add($_.FullName.Substring($stage.Length).TrimStart('\','/'))
            break
        }
    }
}

$manifest | Set-Content -LiteralPath (Join-Path $stage "_SOURCE_PACKAGE_INFO.txt") -Encoding UTF8

Write-Step "3/4 - NEN ZIP"

if (Test-Path -LiteralPath $zipPath) {
    Remove-Item -LiteralPath $zipPath -Force
}

Compress-Archive -LiteralPath (Join-Path $temp "ai_video_factory") -DestinationPath $zipPath -CompressionLevel Optimal

Write-Step "4/4 - XONG"

$sizeMB = [math]::Round((Get-Item -LiteralPath $zipPath).Length / 1MB, 2)
Write-Host ("ZIP: " + $zipPath) -ForegroundColor Green
Write-Host ("Size: " + $sizeMB + " MB") -ForegroundColor Green
Write-Host ""
Write-Host "GUI FILE ZIP NAY CHO GA." -ForegroundColor Yellow

try {
    Start-Process explorer.exe -ArgumentList "/select,`"$zipPath`""
} catch {}

Remove-Item -LiteralPath $temp -Recurse -Force -ErrorAction SilentlyContinue
