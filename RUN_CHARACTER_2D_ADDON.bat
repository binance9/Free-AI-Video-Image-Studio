@echo off
setlocal EnableExtensions
set "ROOT=%~dp0"
set "APPROOT=%ROOT%app"
set "PY="
if exist "C:\Python314\python.exe" set "PY=C:\Python314\python.exe"
if not defined PY for /f "delims=" %%P in ('where python 2^>nul') do if not defined PY set "PY=%%P"
if not defined PY (
  echo [ERROR] Khong tim thay Python.
  pause
  exit /b 1
)
if not exist "%APPROOT%\app\modules\character_2d_addon\__init__.py" (
  echo [ERROR] Khong tim thay addon tai: %APPROOT%\app\modules\character_2d_addon
  echo Hay giai nen ZIP vao thu muc goc ai_video_factory.
  pause
  exit /b 1
)
cd /d "%APPROOT%"
set "PYTHONPATH=%APPROOT%;%PYTHONPATH%"
echo [Character 2D Addon] Project: %ROOT%
echo [Character 2D Addon] Python package root: %APPROOT%
echo [Character 2D Addon V12.3 From-Reference] Starting: http://127.0.0.1:8012/docs
"%PY%" -c "import sys; print('[Character 2D Addon] Python:', sys.executable); import app.modules.character_2d_addon; print('[Character 2D Addon V12.3 From-Reference] Import OK')" || goto :fail
"%PY%" -m uvicorn app.api.character_2d_standalone:app --host 127.0.0.1 --port 8012
goto :end
:fail
echo.
echo [ERROR] Addon import that bai. Chup man hinh nay gui cho Ga.
:end
pause
