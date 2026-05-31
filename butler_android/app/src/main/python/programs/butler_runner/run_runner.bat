@echo off
title Butler-Runner Pro Portable
:: 建议通过环境变量设置以下值，或在此处根据实际情况修改
set SERVER_IP=127.0.0.1
set TOKEN=
set RUNNER_ID=%COMPUTERNAME%

echo ---------------------------------------------------
echo  Butler-Runner Pro Portable Launcher
echo  Host: %SERVER_IP%
echo  Runner ID: %RUNNER_ID%
echo ---------------------------------------------------

if "%TOKEN%" == "" (
    echo [ERROR] Auth TOKEN is missing! Please set it in the script or environment.
    pause
    exit /b
)

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
