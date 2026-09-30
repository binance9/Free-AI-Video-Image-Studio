@echo off
cd /d "%~dp0"
echo ============================================
echo AI VIDEO FACTORY - CAI DAT BAN DO HD TILE
echo ============================================
where python >nul 2>&1
if %errorlevel%==0 (
  python CAI_DAT_BAN_DO_3D.py
) else (
  py CAI_DAT_BAN_DO_3D.py
)
echo.
pause
