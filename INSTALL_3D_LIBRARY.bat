@echo off
setlocal
cd /d "%~dp0"
echo ================================================
echo AI VIDEO FACTORY - THU VIEN 3D LOCAL
echo ================================================
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 INSTALL_3D_LIBRARY.py
) else (
  python INSTALL_3D_LIBRARY.py
)
if errorlevel 1 (
  echo.
  echo CAI DAT THAT BAI. Chup cua so nay gui Ga Con.
  pause
  exit /b 1
)
echo.
echo Cai dat xong. Dong bot va mo lai, sau do Ctrl+F5.
pause
