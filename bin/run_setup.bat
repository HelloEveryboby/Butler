@echo off
REM Butler Setup Script for Windows
REM This script handles first-time setup with proper feedback

cd %~dp0\..

echo.
echo ========================================
echo Butler - First Time Setup
echo ========================================
echo.

REM 1. Check Python installation
echo [1/3] Checking Python installation...
python --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.8+ and add it to PATH
    pause
    exit /b 1
)
echo OK: Python found

REM 2. Ensure .env exists
echo [2/3] Initializing configuration...
if not exist .env (
    if exist .env.example (
        echo Creating .env from .env.example...
        copy .env.example .env >nul
    ) else (
        echo Creating empty .env...
        type nul > .env
    )
)
echo OK: Configuration ready

REM 3. Install dependencies
echo [3/3] Installing dependencies...
if not exist lib_external (
    if not exist venv (
        echo This may take a few minutes on first run...
        python -m package.core_utils.dependency_manager install_all
        if %ERRORLEVEL% neq 0 (
            echo WARNING: Dependency installation had issues, but continuing...
        )
    )
)
echo OK: Dependencies ready

echo.
echo ========================================
echo Setup Complete!
echo ========================================
echo.
echo Starting Butler application...
echo.

REM Launch enhanced app with setup
python -m butler.butler_app_enhanced
if %ERRORLEVEL% neq 0 pause
