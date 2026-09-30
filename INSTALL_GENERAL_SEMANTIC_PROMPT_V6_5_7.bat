@echo off
setlocal
cd /d "%~dp0"
title AI VIDEO FACTORY V6.5.7 - GENERAL SEMANTIC PROMPT FIX

echo ============================================================
echo   AI VIDEO FACTORY V6.5.7 - GENERAL SEMANTIC PROMPT FIX
echo ============================================================
echo.
echo Fix Tong Quat Tao Anh AI: prompt phai hieu tu nhien cho con vat, do vat,
echo xe co, nguoi, tre nho, nguoi gia, vu khi, quan ao, robot, may moc, canh,
echo ban do, mua nang, ngay dem... khong hard-code mot loai nhan vat.
echo Tu dong BACKUP + COMPILE + VERIFY + ROLLBACK neu loi.
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\INSTALL_GENERAL_SEMANTIC_PROMPT_V6_5_7.ps1"
set "ERR=%ERRORLEVEL%"

echo.
if not "%ERR%"=="0" (
  echo [LOI] Cai dat that bai. Chup man hinh nay gui Ga.
) else (
  echo [PASS] V6.5.7 da cai xong. Restart app va test Tao Anh AI.
)
echo.
pause
exit /b %ERR%
