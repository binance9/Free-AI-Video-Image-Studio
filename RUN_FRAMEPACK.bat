@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo === FRAMEPACK - TAO VIDEO AI DAI TU 1 ANH (LOCAL, FREE) ===
echo Lan dau chay se tai model ~35GB (cho mot luc). Sau do mo: http://127.0.0.1:7890
echo Tat cua so nay = tat tool.
"data\runtime_framepack\venv\Scripts\python.exe" "tools\external\FramePack\demo_gradio.py" --port 7890
pause
