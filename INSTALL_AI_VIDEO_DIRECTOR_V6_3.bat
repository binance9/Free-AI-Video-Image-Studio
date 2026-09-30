@echo off
setlocal
cd /d "%~dp0"
title AI VIDEO DIRECTOR V6 QUALITY FIRST

echo ============================================================
echo   AI VIDEO DIRECTOR V6 - QUALITY FIRST

echo   Character Lock + QA + Repair + Final 1080p

echo ============================================================
echo.

where python >nul 2>nul
if errorlevel 1 (
  echo [LOI] Khong tim thay python trong PATH.
  pause
  exit /b 1
)

python INSTALL_AI_VIDEO_DIRECTOR_V6_3.py
if errorlevel 1 (
  echo.
  echo [LOI] Cai V6 that bai. Chup cua so nay gui Ga.
  pause
  exit /b 1
)

echo.
echo ============================================================
echo V6 DA CAI XONG.
echo Tat bot hoan toan, mo lai, sau do Ctrl+F5 trinh duyet.
echo Status phai co build=v5-quality-first.
echo ============================================================
pause
