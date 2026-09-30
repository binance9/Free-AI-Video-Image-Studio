@echo off
setlocal
cd /d "%~dp0"
title AI VIDEO DIRECTOR V3 FORCE UPDATE
where python >nul 2>nul
if errorlevel 1 (
 echo [LOI] Khong tim thay python trong PATH.
 pause
 exit /b 1
)
echo ============================================================
echo AI VIDEO DIRECTOR V3 - FORCE UPDATE V1/V2
echo ============================================================
python INSTALL_AI_VIDEO_DIRECTOR_V3.py
if errorlevel 1 (
 echo.
 echo [LOI] Cai dat that bai.
 pause
 exit /b 1
)
echo.
echo [OK] V3 da force update.
echo Tat AI Video Factory HOAN TOAN, mo lai, roi nhan Ctrl+F5.
echo Kiem tra: http://127.0.0.1:8123/api/ai-video-director/status
pause
