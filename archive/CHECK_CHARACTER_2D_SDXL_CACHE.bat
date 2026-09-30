@echo off
setlocal
cd /d "%~dp0"
echo === SDXL cache folders ===
dir /s /b "data\models\image\models--stabilityai--stable-diffusion-xl-base-1.0" 2>nul
echo.
echo === Lightning cache folders ===
dir /s /b "data\models\image\models--ByteDance--SDXL-Lightning" 2>nul
echo.
echo If both sections show paths, cached files exist.
pause
