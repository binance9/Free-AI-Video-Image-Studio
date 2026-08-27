@echo off
setlocal
cd /d "%~dp0"
title AI Video Factory - Setup Video Cleanup AI 0.8.7.7
where python >nul 2>&1
if errorlevel 1 (echo [LOI] Khong tim thay Python.& pause & exit /b 1)
python tools\install_video_cleanup.py
echo.
pause
