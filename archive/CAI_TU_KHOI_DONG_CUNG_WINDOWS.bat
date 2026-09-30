@echo off
setlocal
cd /d "%~dp0"
set "TARGET=%~dp0BAT_DAU_GA_AI.bat"
set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "VBS=%STARTUP%\GaMaintenance.vbs"
> "%VBS%" echo Set WshShell = CreateObject("WScript.Shell")
>>"%VBS%" echo WshShell.Run chr(34) ^& "%TARGET%" ^& chr(34), 0
>>"%VBS%" echo Set WshShell = Nothing
echo Da cai GA MAINTENANCE tu khoi dong cung Windows.
pause
