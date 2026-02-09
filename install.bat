@echo off
echo Installing Image Classification Desktop App...
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python is not installed or not in PATH
    echo Please install Python 3.8+ from https://python.org
    pause
    exit /b 1
)

echo Python found. Installing requirements...
echo.

REM Install requirements
pip install -r requirements.txt

if errorlevel 1 (
    echo.
    echo Error: Failed to install some requirements
    echo Please check your internet connection and try again
    pause
    exit /b 1
)

echo.
echo Installation complete!
echo.
echo To run the application, use: python src/main.py
echo.
pause
