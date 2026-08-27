@echo off
setlocal
cd /d "%~dp0"
title AI Video Factory 0.8 - Setup Free Local AI
where python >nul 2>&1
if errorlevel 1 (echo [LOI] Khong tim thay Python trong PATH.& pause & exit /b 1)
python tools\install_local_ai.py
echo.
pause
