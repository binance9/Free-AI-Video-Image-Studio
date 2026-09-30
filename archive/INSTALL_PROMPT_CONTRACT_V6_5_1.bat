@echo off
setlocal
cd /d "%~dp0"
title AI VIDEO FACTORY V6.5.1 - SHARED PROMPT CONTRACT

echo ============================================================
echo   AI VIDEO FACTORY V6.5.1 - SHARED PROMPT CONTRACT
echo ============================================================
echo.
echo Dong bo: ANH AI + 2D + 3D + VIDEO + MAP + DIRECTOR
echo Tu dong BACKUP + COMPILE + VERIFY + ROLLBACK neu loi.
echo HOTFIX: sua xung dot PowerShell alias RP.
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\INSTALL_PROMPT_CONTRACT_V6_5_1.ps1"
set "ERR=%ERRORLEVEL%"

echo.
if not "%ERR%"=="0" (
    echo [LOI] Cai dat that bai.
    echo Chup man hinh nay gui Ga.
) else (
    echo [PASS] V6.5.1 da cai xong.
    echo Khoi dong lai AI Video Factory va test prompt.
)
echo.
pause
exit /b %ERR%
