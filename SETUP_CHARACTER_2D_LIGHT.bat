@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "PY="
if exist "C:\Python314\python.exe" set "PY=C:\Python314\python.exe"
if not defined PY for /f "delims=" %%P in ('where python 2^>nul') do if not defined PY set "PY=%%P"
if not defined PY (
  echo [ERROR] Khong tim thay Python.
  pause
  exit /b 1
)
echo [V10.1] Python: %PY%

echo.
echo [1/3] Checking CUDA...
"%PY%" -c "import torch; print('torch',torch.__version__); print('cuda_available',torch.cuda.is_available()); print('cuda',torch.version.cuda); print('gpu', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU')"
if errorlevel 1 (
  echo [ERROR] Torch check failed.
  pause
  exit /b 1
)

echo.
echo [2/3] Updating image runtime packages...
"%PY%" -m pip install -U "diffusers>=0.34" "transformers>=4.44,<6" "accelerate>=0.34" "huggingface_hub[hf_xet]>=0.34" "safetensors>=0.4" "sentencepiece>=0.2"
if errorlevel 1 (
  echo [ERROR] Package setup failed.
  pause
  exit /b 1
)

echo.
echo [3/3] Caching DreamShaper 8. Existing Hugging Face cache is reused.
"%PY%" "%~dp0tools\setup_character_2d_v101.py"
if errorlevel 1 (
  echo.
  echo [ERROR] Model cache setup failed. Run this BAT again to resume/reuse cache.
  pause
  exit /b 1
)
echo.
echo [OK] Character 2D V10.1 setup complete.
pause
