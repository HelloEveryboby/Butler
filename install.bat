@echo off
setlocal

echo Starting Butler installation...
echo This script will guide you through the setup process.
echo -----------------------------------------------------

REM --- Check for dependencies ---
echo Step 1: Checking for Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: Python is not installed or not in your PATH.
    echo Please install Python and try again.
    pause
    exit /b 1
)
echo Python found.

pip --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: pip is not installed or not in your PATH.
    echo Please install pip and try again.
    pause
    exit /b 1
)
echo pip found.

echo -----------------------------------------------------

REM --- Install Python packages ---
echo Step 2: Installing Python dependencies from setup.py...
pip install .
if %errorlevel% neq 0 (
    echo Error: Failed to install Python dependencies. Please check the output above for errors.
    pause
    exit /b 1
)
echo Python dependencies installed successfully.

echo -----------------------------------------------------

REM --- Configure API Keys ---
echo Step 3: Configuring API keys...

if exist ".env" (
    choice /c yn /m "An .env file already exists. Do you want to overwrite it?"
    if errorlevel 2 (
        echo Skipping API key configuration.
        echo -----------------------------------------------------
        echo Butler installation is complete!
        echo You can start the assistant by running run.bat
        pause
        exit /b 0
    )
)

echo Please enter your DeepSeek API Key:
set /p DEEPSEEK_API_KEY=
echo Please enter your Azure Speech API Key:
set /p AZURE_SPEECH_KEY=
echo Please enter your Azure Speech Service Region (e.g., chinaeast2):
set /p AZURE_SERVICE_REGION=

echo Creating .env file...
(
    echo DEEPSEEK_API_KEY="%DEEPSEEK_API_KEY%"
    echo AZURE_SPEECH_KEY="%AZURE_SPEECH_KEY%"
    echo AZURE_SERVICE_REGION="%AZURE_SERVICE_REGION%"
) > .env

echo .env file created successfully.
echo -----------------------------------------------------

echo Butler installation and configuration is complete!
echo You can now start the assistant by running run.bat.
pause
exit /b 0
