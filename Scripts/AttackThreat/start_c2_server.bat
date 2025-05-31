@echo off
REM IoT C2 Server - Installation and Setup Script
echo ===================================================
echo IoT C2 Server - Installation and Setup
echo ===================================================
echo.

REM Check for Python installation
python --version > nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.9+ and try again
    exit /b 1
)

echo Installing required dependencies...
pip install -r requirements.txt

if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Failed to install dependencies
    exit /b 1
)

echo.
echo Dependencies installed successfully!
echo.
echo ===================================================
echo Starting C2 Server...
echo ===================================================
echo.
echo Press Ctrl+C to stop the server
echo.

python c2_server.py
