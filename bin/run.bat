@echo off
REM Butler startup script for Windows
cd %~dp0\..

REM 1. Ensure .env exists
if not exist .env (
    if exist .env.example (
        echo Initializing .env from .env.example...
        copy .env.example .env
    ) else (
        echo Creating empty .env...
        type nul > .env
    )
)

REM 2. Check and install dependencies automatically
if not exist lib_external (
    if not exist venv (
        echo First time setup: Installing dependencies in portable mode...
        python -m package.dependency_manager install_all
    )
)

set PYTHON_CMD=python
if exist runtime\python.exe (
    set PYTHON_CMD=runtime\python.exe
    set PYTHONPATH=%PYTHONPATH%;.
)

echo Launching main application...
%PYTHON_CMD% -m butler.butler_app %*
if %ERRORLEVEL% neq 0 pause
