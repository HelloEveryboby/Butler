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

REM Check for dependency updates
echo Checking for dependency updates...
%PYTHON_CMD% -c "from package.core_utils.dependency_manager import check_dependencies_update; import sys; sys.exit(0 if not check_dependencies_update() else 1)"
if %errorlevel% neq 0 (
    echo.
    echo *********************************************************
    echo  Requirements.txt has been updated.
    echo  Would you like to update your local dependencies now?
    echo *********************************************************
    set /p CHOICE="Enter Y to update, or any other key to skip: "
    if /I "%CHOICE%"=="Y" (
        echo Updating dependencies...
        %PYTHON_CMD% -m package.dependency_manager install_all
    )
)

REM Run the main application using the python module flag
echo Launching main application...
%PYTHON_CMD% -m butler.butler_app

echo Application closed.
pause
