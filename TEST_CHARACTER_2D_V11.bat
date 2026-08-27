@echo off
setlocal EnableExtensions
set "ROOT=%~dp0"
set "APPROOT=%ROOT%app"
set "PY="
if exist "C:\Python314\python.exe" set "PY=C:\Python314\python.exe"
if not defined PY for /f "delims=" %%P in ('where python 2^>nul') do if not defined PY set "PY=%%P"
if not defined PY (
  echo [ERROR] Khong tim thay Python.
  pause
  exit /b 1
)
cd /d "%APPROOT%"
set "PYTHONPATH=%APPROOT%;%PYTHONPATH%"
"%PY%" "%ROOT%tools\self_test_character_2d_v11.py"
if errorlevel 1 (
  echo [FAILED] V11 strict lock self-test
  pause
  exit /b 1
)
echo [OK] V11 strict lock self-test PASS
pause
