@echo off
title News Chatbot System Runner
cd /d "%~dp0"

echo ===================================================
echo     STARTING NEWS CHATBOT SERVER WITH NGROK
echo ===================================================
echo.

:: Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in system PATH.
    echo Please install Python 3.8+ and try again.
    pause
    exit /b 1
)

:: Run the unified project runner
python start_project.py

if %errorlevel% neq 0 (
    echo.
    echo [WARNING] Project runner exited with an error.
    pause
)
