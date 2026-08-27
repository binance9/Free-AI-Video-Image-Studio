@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "PY="
if exist "C:\Python314\python.exe" set "PY=C:\Python314\python.exe"
if not defined PY for /f "delims=" %%P in ('where python 2^>nul') do if not defined PY set "PY=%%P"
if not defined PY (
  echo [ERROR] Python not found.
  pause
  exit /b 1
)
echo [V12.3] Installing upload support only. Existing DreamShaper and CLIP caches are reused.
"%PY%" -m pip install -U "python-multipart>=0.0.20"
if errorlevel 1 (
  echo [ERROR] python-multipart install failed.
  pause
  exit /b 1
)
echo [OK] V12.3 from-reference upload support ready.
pause
