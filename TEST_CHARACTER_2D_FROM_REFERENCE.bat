@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "PY="
if exist "C:\Python314\python.exe" set "PY=C:\Python314\python.exe"
if not defined PY for /f "delims=" %%P in ('where python 2^>nul') do if not defined PY set "PY=%%P"
if not defined PY (
  echo [ERROR] Python not found.
  pause
  exit /b 1
)
set /p "IMG=Paste full path to reference image: "
set /p "PROMPT=Describe the target character/change: "
"%PY%" "%~dp0tools\test_character_2d_from_reference.py" --image "%IMG%" --prompt "%PROMPT%"
pause
