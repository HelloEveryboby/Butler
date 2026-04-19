@echo off
REM Butler Modern UI startup script for Windows
cd %~dp0\..
python -m frontend.program.modern_app
pause
