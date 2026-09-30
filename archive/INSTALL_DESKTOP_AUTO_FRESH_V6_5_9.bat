@echo off
setlocal
cd /d "%~dp0"
title AI VIDEO FACTORY V6.5.9 - DESKTOP AUTO FRESH

echo ====================================================================
echo   AI VIDEO FACTORY V6.5.9 - DESKTOP APP + AUTO FRESH
echo ====================================================================
echo.
echo - Mo AI Video Factory bang icon tren Desktop.
echo - Khong can go 127.0.0.1.
echo - Neu code/UI vua sua, lan mo tiep theo se tu nap ban moi.
echo - Neu dang render, KHONG tu giet job.
echo - Co BACKUP + COMPILE + VERIFY + ROLLBACK.
echo.

python ".\INSTALL_DESKTOP_AUTO_FRESH_V6_5_9.py"
set "ERR=%ERRORLEVEL%"

echo.
if not "%ERR%"=="0" (
  echo [LOI] Cai dat that bai. Chup man hinh nay gui Ga.
) else (
  echo [PASS] V6.5.9 da cai xong.
  echo Bay gio bam icon "AI Video Factory" ngoai Desktop.
)
echo.
pause
exit /b %ERR%
