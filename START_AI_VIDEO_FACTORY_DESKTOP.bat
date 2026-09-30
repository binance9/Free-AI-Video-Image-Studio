@echo off
setlocal
cd /d "%~dp0"
title AI Video Factory Desktop
set "PYTHONPATH=C:\Users\BAOAN\AppData\Roaming\Python\Python314\site-packages"
C:\Python314\python.exe ".\AI_VIDEO_FACTORY_DESKTOP.py"
if errorlevel 1 (
  echo.
  echo [LOI] Desktop launcher that bai.
  echo Xem: data\ga_maintenance\desktop_launcher.log
  echo.
  pause
)
