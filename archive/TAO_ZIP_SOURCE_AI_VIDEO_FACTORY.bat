@echo off
setlocal
cd /d "%~dp0"
title AI VIDEO FACTORY - TAO ZIP SOURCE GUI GA

echo ============================================================
echo   AI VIDEO FACTORY - TAO ZIP SOURCE NHE GUI GA
echo ============================================================
echo.
echo Dat BAT + PS1 vao THU MUC GOC ai_video_factory.
echo Sau do chay file BAT nay.
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0TAO_ZIP_SOURCE_AI_VIDEO_FACTORY.ps1" -Root "%~dp0"
set ERR=%ERRORLEVEL%
echo.
if not "%ERR%"=="0" (
  echo [LOI] Collector dung voi ma %ERR%.
  echo Chup man hinh nay gui Ga.
) else (
  echo HOAN TAT. Explorer se mo va chon file ZIP vua tao.
)
echo.
pause
exit /b %ERR%
