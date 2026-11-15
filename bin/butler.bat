@echo off
rem ==============================================================================
rem Butler 统一命令入口 (Windows / clone 模式)
rem   用法: bin\butler <command> [args...]
rem   示例: bin\butler doctor / bin\butler start / bin\butler skills list
rem ==============================================================================
setlocal
set "PROJECT_ROOT=%~dp0.."

set "PYTHON_CMD=python"
if exist "%PROJECT_ROOT%\runtime\python.exe" set "PYTHON_CMD=%PROJECT_ROOT%\runtime\python.exe"

where %PYTHON_CMD% >nul 2>nul
if errorlevel 1 (
    echo [ERROR] 未找到 python。请先安装 Python 3.10/3.11，或运行 bin\install.bat 配置便携运行时。
    exit /b 1
)

"%PYTHON_CMD%" "%PROJECT_ROOT%\butler_launcher.py" %*
