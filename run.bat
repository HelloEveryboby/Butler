@echo off
REM This script starts the Butler application.
REM It ensures that the script is run from its own directory
REM to handle relative paths correctly.

echo Starting Butler application...

REM Change directory to the script's location
cd /d "%~dp0"

REM Check if .env file exists. If not, run the installation script.
if not exist ".env" (
    echo Configuration file (.env) not found.
    echo Running setup script...
    call install.bat
)

REM Detect and use portable runtime if available
set PYTHON_CMD=python
if exist "runtime\python.exe" (
    set PYTHON_CMD=runtime\python.exe
    echo Using portable Python runtime (Windows).
    set PYTHONPATH=%PYTHONPATH%;.
)

REM Run the main application using the python module flag
echo Launching main application...
%PYTHON_CMD% -m butler.main

echo Application closed.
pause
