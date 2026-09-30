@echo off
setlocal
cd /d "%~dp0"
title AI VIDEO FACTORY V6.5 - SHARED PROMPT CONTRACT

echo ============================================================
echo   AI VIDEO FACTORY V6.5 - SHARED PROMPT CONTRACT
echo ============================================================
echo.
echo Dong bo: ANH AI + 2D + 3D + VIDEO + MAP + DIRECTOR
echo Tu dong BACKUP + COMPILE + VERIFY + ROLLBACK neu loi.
echo.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\INSTALL_PROMPT_CONTRACT_V6_5.ps1"
set "ERR=%ERRORLEVEL%"
echo.
if not "%ERR%"=="0" (
  echo [LOI] Cai dat that bai. Neu patch da bat dau thi source cu da duoc rollback.
  echo Chup man hinh nay gui Ga.
) else (
  echo [PASS] V6.5 da cai xong. Khoi dong lai AI Video Factory.
)
echo.
pause
exit /b %ERR%
