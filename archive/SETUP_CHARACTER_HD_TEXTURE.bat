@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
title AI Video Factory - Setup Character HD Texture 0.8.9.0

echo ==============================================
echo   CHARACTER HD PAINT - WINDOWS AUTO SETUP
echo   0.8.9.0 - Torch hardlink/copy mirror + NVCC USE_CUDA fix
echo   Chi build texture, KHONG cai lai model shape
echo ==============================================
echo.

rem ---- Locate Visual Studio 2022 Build Tools BEFORE entering any parenthesized block.
set "VSROOT=C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools"
set "VCVARS=%VSROOT%\VC\Auxiliary\Build\vcvarsall.bat"

if not exist "%VCVARS%" (
  set "VSWHERE=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe"
  if exist "!VSWHERE!" (
    for /f "usebackq tokens=*" %%I in (`"!VSWHERE!" -products * -version "[17.0,18.0)" -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath`) do (
      if not defined VSFOUND set "VSFOUND=%%I"
    )
    if defined VSFOUND (
      set "VSROOT=!VSFOUND!"
      set "VCVARS=!VSROOT!\VC\Auxiliary\Build\vcvarsall.bat"
    )
  )
)

if not exist "%VCVARS%" (
  echo [LOI] Khong tim thay Visual Studio 2022 C++ Build Tools.
  echo Can Build Tools 2022 ^> Desktop development with C++.
  goto :end
)

rem ---- Prefer CUDA-12.8-supported MSVC 14.39 when installed.
set "HAS1439=0"
for /d %%D in ("%VSROOT%\VC\Tools\MSVC\14.39*") do set "HAS1439=1"

where cl >nul 2>nul
if errorlevel 1 (
  if "!HAS1439!"=="1" (
    echo [TOOLCHAIN] Nap Visual Studio 2022 x64 - MSVC 14.39...
    call "%VCVARS%" x64 -vcvars_ver=14.39
  ) else (
    echo [CANH BAO] Chua thay MSVC v14.39. Thu nap toolset VS2022 hien co...
    call "%VCVARS%" x64
  )
)

where cl >nul 2>nul
if errorlevel 1 (
  echo [LOI] VS2022 da co nhung khong nap duoc cl.exe.
  echo Thu mo x64 Native Tools Command Prompt for VS 2022 va chay lai file nay.
  goto :end
)

rem ---- If 14.39 exists, force it even when the BAT was launched from another VS environment.
if "!HAS1439!"=="1" (
  for /f "tokens=2 delims=:" %%V in ('cl 2^>^&1 ^| findstr /C:"Compiler Version"') do set "CLVER=%%V"
  echo [TOOLCHAIN] MSVC 14.39 da cai, nap lai toolset tuong thich CUDA 12.8...
  call "%VCVARS%" x64 -vcvars_ver=14.39 >nul
)

rem ---- Auto-locate CUDA Toolkit. Prefer 12.8 because Character HD runtime uses cu128.
if not defined CUDA_PATH (
  if exist "C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.8\bin\nvcc.exe" set "CUDA_PATH=C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.8"
)
if defined CUDA_PATH (
  set "CUDA_HOME=%CUDA_PATH%"
  set "PATH=%CUDA_PATH%\bin;%PATH%"
)

set DISTUTILS_USE_SDK=1
set MSSdk=1
set MAX_JOBS=2
set "NVCC_APPEND_FLAGS=%NVCC_APPEND_FLAGS% -DUSE_CUDA"

where cl >nul 2>nul
if errorlevel 1 (
  echo [LOI] Khong tim thay cl.exe sau khi nap VS2022.
  goto :end
)
where nvcc >nul 2>nul
if errorlevel 1 (
  echo [LOI] Khong tim thay nvcc.exe. CUDA Toolkit 12.8 chua san sang.
  goto :end
)

echo [OK] MSVC:
where cl
cl 2>&1 | findstr /C:"Compiler Version"
echo [OK] CUDA:
where nvcc
nvcc --version | findstr /I "release V12"
echo.

if exist "data\runtime_character_hd\venv\Scripts\python.exe" (
  "data\runtime_character_hd\venv\Scripts\python.exe" tools\install_character_hd_texture.py
) else (
  echo [LOI] Chua co runtime Character HD.
  echo Hay chay SETUP_CHARACTER_HD.bat truoc.
)

:end
echo.
echo Build log neu co: data\runtime_character_hd\paint_build.log
pause
endlocal
