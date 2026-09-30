@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "PY="
for %%P in ("C:\Python314\python.exe" "C:\Python313\python.exe") do if exist %%P set "PY=%%~P"
if not defined PY for /f "delims=" %%P in ('where python 2^>nul') do if not defined PY set "PY=%%P"
if not defined PY (
  echo [ERROR] Python not found.
  pause
  exit /b 1
)
echo [V11] Python: %PY%
"%PY%" -m pip install -U "transformers>=4.44" "huggingface_hub>=0.34" "safetensors>=0.4"
if errorlevel 1 goto :fail

echo.
echo [V11] Caching CLIP validator model. DreamShaper cache is reused.
"%PY%" -c "from transformers import CLIPModel,CLIPProcessor; c=r'data\models\validator'; CLIPProcessor.from_pretrained('openai/clip-vit-base-patch32',cache_dir=c); CLIPModel.from_pretrained('openai/clip-vit-base-patch32',cache_dir=c); print('[OK] CLIP validator cache ready')"
if errorlevel 1 goto :fail

echo.
echo [OK] Character 2D V11 Hard Lock setup complete.
pause
exit /b 0
:fail
echo [ERROR] V11 setup failed. Existing model cache was not deleted.
pause
exit /b 1
