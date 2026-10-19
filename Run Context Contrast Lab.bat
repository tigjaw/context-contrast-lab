@echo off
setlocal
cd /d "%~dp0"

set "PYTHON="
where py >nul 2>nul
if not errorlevel 1 set "PYTHON=py -3"
if not defined PYTHON (
    where python >nul 2>nul
    if not errorlevel 1 set "PYTHON=python"
)

if not defined PYTHON (
    echo Python 3.10 or newer is required.
    echo Install Python from https://www.python.org/downloads/windows/ and enable Add Python to PATH.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo Setting up the app's private Python environment...
    %PYTHON% -m venv .venv
    if errorlevel 1 goto failed
)

echo Checking for and installing or updating required packages...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check --upgrade -r requirements.txt
if errorlevel 1 goto failed

echo Starting Context Contrast Lab...
".venv\Scripts\python.exe" main.py
if errorlevel 1 goto failed
exit /b 0

:failed
echo.
echo The app could not start. Check the message above and try again.
pause
exit /b 1
