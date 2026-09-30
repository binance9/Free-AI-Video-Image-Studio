@echo off
cd /d "%~dp0"
where py >nul 2>nul && (py -3 INSTALL_AI_VIDEO_DIRECTOR_V6_3_1_UI_ONLY.py) || (python INSTALL_AI_VIDEO_DIRECTOR_V6_3_1_UI_ONLY.py)
pause
