@echo off
setlocal
cd /d "%~dp0"
title AI VIDEO DIRECTOR - INSTALL
where python >nul 2>nul
if errorlevel 1 (
  echo [LOI] Khong tim thay python trong PATH.
  pause
  exit /b 1
)
python INSTALL_AI_VIDEO_DIRECTOR.py
if errorlevel 1 (
  echo.
  echo [LOI] Cai dat that bai. Doc thong bao o tren.
  pause
  exit /b 1
)
echo.
echo [OK] Cai dat xong. Tat bot va mo lai de nap AI VIDEO DIRECTOR.
pause
