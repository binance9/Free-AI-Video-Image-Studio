@echo off
cd /d "%~dp0"
title AI Video Factory - Setup Free 3D 0.8.2
echo =============================================================
echo AI VIDEO FACTORY 0.8.2 - WINDOWS 3D FIX
echo - Python 3.12 rieng cho AI 3D
echo - Khong dung Python 3.14 cua app
echo - PyMCubes thay torchmcubes de tranh build loi tren Windows
echo =============================================================
python tools\install_local_3d.py
if errorlevel 1 (
  echo.
  echo [LOI] Cai AI 3D that bai. Chup phan LOI CUOI CUNG gui de kiem tra.
) else (
  echo.
  echo [OK] AI 3D local da san sang.
  echo Mo START_VIDEO_FACTORY.bat va test tab AI 3D.
)
pause
