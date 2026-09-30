@echo off
setlocal
cd /d "%~dp0"
title TAO ZIP SOURCE NHE - AI VIDEO FACTORY

echo ==================================================
echo  TAO ZIP SOURCE NHE DE GUI CHO GA
echo ==================================================
echo.
echo File nay se:
echo - Lay code Python / JS / TS / HTML / CSS / config
echo - Bo .venv, node_modules, models, checkpoints
echo - Bo video, anh, output, cache
echo - Bo .env va file credentials
echo.
echo QUAN TRONG:
echo Thu muc hien tai phai la THU MUC GOC AI Video Factory.
echo.
pause

where python >nul 2>nul
if errorlevel 1 (
    echo [LOI] Khong tim thay Python trong PATH.
    echo Neu app co .venv, hay bao Ga de tao ban dung Python cua app.
    pause
    exit /b 1
)

python collector_source_ga.py
if errorlevel 1 (
    echo.
    echo [LOI] Tao ZIP that bai.
    pause
    exit /b 1
)

echo.
echo XONG. Gui file:
echo AI_VIDEO_FACTORY_SOURCE_NHE_GUI_GA.zip
pause
