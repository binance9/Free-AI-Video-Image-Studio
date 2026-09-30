@echo off
setlocal
cd /d "%~dp0"
title AI VIDEO FACTORY V6.5.4 - TAO ANH AI SINGLE SUBJECT FIX

echo ============================================================
echo   AI VIDEO FACTORY V6.5.4 - TAO ANH AI SINGLE SUBJECT FIX
echo ============================================================
echo.
echo Chi sua module TAO ANH AI.
echo Fix: 1 nguoi / 1 pose / 1 camera, anti character-sheet, full-body preserve.
echo Tu dong BACKUP + COMPILE + VERIFY + ROLLBACK neu loi.
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\INSTALL_TAO_ANH_AI_V6_5_4.ps1"
set "ERR=%ERRORLEVEL%"

echo.
if not "%ERR%"=="0" (
  echo [LOI] Cai dat that bai. Chup man hinh nay gui Ga.
) else (
  echo [PASS] Tao Anh AI V6.5.4 da cai xong. Khoi dong lai app roi test.
)
echo.
pause
exit /b %ERR%
