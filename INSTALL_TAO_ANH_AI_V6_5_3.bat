@echo off
setlocal
cd /d "%~dp0"
title AI VIDEO FACTORY V6.5.3 - TAO ANH AI ANTI SHEET FIX

echo ============================================================
echo   AI VIDEO FACTORY V6.5.3 - TAO ANH AI ANTI SHEET FIX
echo ============================================================
echo.
echo Fix dung 1 module: TAO ANH AI
echo Muc tieu: 1 nhan vat, full body, co kiem, chong lineup / character sheet / multi-view.
echo Tu dong BACKUP + COMPILE + VERIFY + ROLLBACK neu loi.
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\INSTALL_TAO_ANH_AI_V6_5_3.ps1"
set "ERR=%ERRORLEVEL%"

echo.
if not "%ERR%"=="0" (
  echo [LOI] Cai dat that bai. Chup man hinh nay gui Ga.
) else (
  echo [PASS] Tao Anh AI V6.5.3 da cai xong. Khoi dong lai app roi test.
)
echo.
pause
exit /b %ERR%
