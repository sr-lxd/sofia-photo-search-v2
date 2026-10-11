@echo off
chcp 65001 >nul
cd /d "%~dp0"
if /I "%~1"=="--check" exit /b 0
python start_v2.py
if errorlevel 1 pause
