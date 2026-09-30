@echo off
setlocal
cd /d "%~dp0"
title GA MAINTENANCE - SAFE SYSTEM CLEANER

where python >nul 2>nul
if errorlevel 1 (
  echo [LOI] Chua tim thay Python.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\pythonw.exe" (
  echo [1/3] Tao moi truong rieng...
  python -m venv .venv || goto :fail
  echo [2/3] Cai thu vien...
  call ".venv\Scripts\activate.bat"
  python -m pip install --upgrade pip
  pip install -r requirements.txt || goto :fail
)

echo [3/3] Mo GA MAINTENANCE...
start "" ".venv\Scripts\pythonw.exe" main.py
exit /b 0
:fail
echo [LOI] Cai dat that bai.
pause
exit /b 1
