@echo off
setlocal
cd /d "%~dp0"
title AI Video Factory Free Local Studio 0.8

echo ========================================================
echo       AI VIDEO FACTORY - FREE LOCAL STUDIO 0.8
echo ========================================================
echo.
where python >nul 2>&1
if errorlevel 1 (echo [LOI] Khong tim thay Python trong PATH.& pause & exit /b 1)
where ffmpeg >nul 2>&1
if errorlevel 1 (echo [LOI] Khong tim thay FFmpeg trong PATH.& pause & exit /b 1)
python -c "import fastapi,uvicorn,multipart,PIL,yt_dlp" >nul 2>&1
if errorlevel 1 (
  echo Dang cai thu vien editor lan dau...
  python -m pip install -r requirements.txt
  if errorlevel 1 (echo [LOI] Cai thu vien editor that bai.& pause & exit /b 1)
)
python START_VIDEO_FACTORY.py
echo.
echo Free Local Studio da dung.
pause
