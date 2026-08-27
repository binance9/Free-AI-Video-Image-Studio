@echo off
setlocal
chcp 65001 >nul
title AI Video Factory - Setup Game Ready 3D

echo ======================================================
echo   AI VIDEO FACTORY - GAME READY 3D SETUP
echo   Blender local for Optimize + Rig + Animation
 echo ======================================================
echo.

where blender >nul 2>nul
if %errorlevel%==0 goto :found

for /d %%D in ("C:\Program Files\Blender Foundation\Blender *") do (
  if exist "%%~fD\blender.exe" goto :foundlocal
)

echo Blender chua duoc tim thay.
echo Dang thu cai Blender bang Windows Package Manager (winget)...
where winget >nul 2>nul
if not %errorlevel%==0 goto :manual
winget install --id BlenderFoundation.Blender -e --accept-package-agreements --accept-source-agreements
if not %errorlevel%==0 goto :manual

echo.
echo Cai dat hoan tat. Dong va mo lai AI Video Factory.
pause
exit /b 0

:foundlocal
echo Tim thay Blender trong Program Files.
echo Khong can cai them. Mo lai AI Video Factory neu bot dang chay.
pause
exit /b 0

:found
echo Blender da co trong PATH.
echo Khong can cai them. Mo lai AI Video Factory neu bot dang chay.
pause
exit /b 0

:manual
echo.
echo Khong the tu cai Blender bang winget tren may nay.
echo Cai Blender 4.x tu trang chinh thuc Blender, sau do mo lai bot.
echo Neu blender.exe nam o vi tri rieng, dat bien moi truong AIVF_BLENDER tro toi blender.exe.
pause
exit /b 1
