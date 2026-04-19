@echo off
REM Butler startup script for Windows
cd %~dp0\..
python -m butler.butler_app
pause
