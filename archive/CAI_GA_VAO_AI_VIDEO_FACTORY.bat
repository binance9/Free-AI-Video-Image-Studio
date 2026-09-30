@echo off
setlocal
cd /d "%~dp0"
title CAI GA AI VAO AI VIDEO FACTORY

echo =====================================================
echo  TICH HOP GA AI TRUC TIEP VAO AI VIDEO FACTORY
echo =====================================================
echo - Khong xoa model
echo - Khong xoa output
echo - Backup main.py + index.html truoc khi sua
echo.

if not exist "app\main.py" (
  echo [LOI] Giai nen ZIP vao THU MUC GOC AI Video Factory.
  pause
  exit /b 1
)

where python >nul 2>nul
if errorlevel 1 (
  echo [LOI] Khong tim thay Python trong PATH.
  pause
  exit /b 1
)

echo [1/4] Cai thu vien voiceprint nhe...
python -m pip install "numpy>=1.26" "python_speech_features>=0.6"

echo [2/4] Chen backend + sidebar Ga...
python install_ga_into_factory.py
if errorlevel 1 goto :fail

echo [3/4] Kiem tra Python...
python -m py_compile app\main.py app\modules\ga_owner\api_ga_owner.py app\modules\ga_owner\service.py app\modules\ga_owner\voice_owner.py
if errorlevel 1 goto :fail

echo [4/4] Kiem tra JavaScript neu co Node...
where node >nul 2>nul
if not errorlevel 1 node --check web\core\ga_owner.js

echo.
echo ===============================
echo XONG.
echo ===============================
echo Dong bot neu dang chay, roi mo lai START_VIDEO_FACTORY.bat
echo GÀ AI OWNER se nam ngay sidebar trai Home.
pause
exit /b 0

:fail
echo.
echo [LOI] Patch dung lai. Source cu da duoc backup.
pause
exit /b 1
