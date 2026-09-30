@echo off
setlocal
cd /d "%~dp0"
title AI VIDEO FACTORY - SOURCE COLLECTOR V2

echo ============================================================
echo   AI VIDEO FACTORY - TAO ZIP SOURCE NHE GUI GA - V2
echo ============================================================
echo.
echo Khong can sua duong dan.
echo Dat BAT + PS1 V2 vao thu muc goc ai_video_factory roi chay BAT.
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\TAO_ZIP_SOURCE_AI_VIDEO_FACTORY_V2.ps1"
set "ERR=%ERRORLEVEL%"

echo.
if not "%ERR%"=="0" (
    echo [LOI] Collector V2 dung voi ma %ERR%.
    echo Chup man hinh nay gui Ga.
) else (
    echo HOAN TAT. Explorer se mo va chon file ZIP vua tao.
)
echo.
pause
exit /b %ERR%
