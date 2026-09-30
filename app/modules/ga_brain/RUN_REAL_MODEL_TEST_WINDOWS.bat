@echo off
setlocal
cd /d "%~dp0\..\..\.."
set PYTHONPATH=%CD%
python -m app.modules.ga_brain.tests.real_model_behavior
set RC=%ERRORLEVEL%
echo.
if %RC%==2 echo REAL_MODEL_TEST_NOT_RUN
if %RC%==0 echo REAL MODEL TEST FINISHED
exit /b %RC%
