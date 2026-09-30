@echo off
setlocal
cd /d "%~dp0"
title AI VIDEO FACTORY V6.5.5 - VIDEO CFR QA FIX

echo ============================================================
echo   AI VIDEO FACTORY V6.5.5 - VIDEO CFR QA FIX
echo ============================================================
echo.
echo Fix VIDEO_QA_FAILED: VIDEO_FPS_TOO_LOW
echo Khong tat QA. Raw model clip se duoc chuan hoa CFR 30fps truoc QA.
echo Tu dong BACKUP + COMPILE + REAL FFMPEG VERIFY + ROLLBACK neu loi.
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\INSTALL_VIDEO_CFR_QA_V6_5_5.ps1"
set "ERR=%ERRORLEVEL%"

echo.
if not "%ERR%"=="0" (
  echo [LOI] Cai dat that bai. Chup man hinh nay gui Ga.
) else (
  echo [PASS] VIDEO CFR QA V6.5.5 da cai xong. Restart app va Auto Produce lai.
)
echo.
pause
exit /b %ERR%
