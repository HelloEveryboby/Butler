@echo off
title Butler-Runner Pro Portable
set SERVER_IP=127.0.0.1
set TOKEN=BUTLER_SECRET_2026
set RUNNER_ID=%COMPUTERNAME%

echo ---------------------------------------------------
echo  Butler-Runner Pro Portable Launcher
echo  Host: %SERVER_IP%
echo  Runner ID: %RUNNER_ID%
echo ---------------------------------------------------

if not exist runner.exe (
    echo [ERROR] runner.exe not found! Please compile it first.
    pause
    exit /b
)

echo [INFO] Starting runner in background...
start /min runner.exe -server ws://%SERVER_IP%:8000/ws/butler -token %TOKEN% -id %RUNNER_ID%

echo [SUCCESS] Runner is now running in the background.
echo You can close this window.
timeout /t 5
