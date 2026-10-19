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
    goto python_missing
)

%PYTHON% -c "import sys; raise SystemExit(sys.version_info < (3, 10))" >nul 2>nul
if errorlevel 1 goto python_missing

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

:python_missing
echo Python 3.10 or newer was not found, or the detected version is too old.
echo Install or update Python from https://www.python.org/downloads/windows/
echo During installation, enable Add Python to PATH. Then close this window and run this file again.
echo Press any key to close this message.
pause >nul
exit /b 1
