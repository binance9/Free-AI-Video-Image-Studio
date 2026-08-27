@echo off
setlocal
cd /d "%~dp0"
title AI Video Factory - Setup Character HD

echo ==============================================
echo   AI VIDEO FACTORY - CHARACTER HD SETUP
echo   Hunyuan3D-2mini - isolated Python 3.12 env
echo ==============================================
echo.

where py >nul 2>nul
if %errorlevel%==0 (
  py -3.12 -c "import sys; print(sys.version)" >nul 2>nul
  if %errorlevel%==0 (
    py -3.12 tools\install_character_hd.py
    goto :done
  )
)

if exist "%LocalAppData%\Programs\Python\Python312\python.exe" (
  "%LocalAppData%\Programs\Python\Python312\python.exe" tools\install_character_hd.py
  goto :done
)

if exist "C:\Python312\python.exe" (
  "C:\Python312\python.exe" tools\install_character_hd.py
  goto :done
)

echo [LOI] Khong tim thay Python 3.12 tren may.
echo Character HD duoc tach rieng va khong dung Python 3.14.

:done
echo.
pause
endlocal
