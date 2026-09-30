@echo off
set "VBS=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\GaMaintenance.vbs"
if exist "%VBS%" del "%VBS%"
echo Da go GA MAINTENANCE khoi Startup.
pause
