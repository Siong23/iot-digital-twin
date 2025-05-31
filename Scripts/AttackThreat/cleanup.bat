@echo off
REM Clean Database and Logs Script
echo ===================================================
echo IoT C2 Server - Cleanup Utility
echo ===================================================
echo.

echo This script will remove:
echo - C2 server database (c2_server\c2_database.db)
echo - All log files (*.log)
echo - Cache files (__pycache__ directories)
echo.

set /p CONFIRM="Are you sure you want to proceed? (y/n): "
if /i "%CONFIRM%" NEQ "y" (
    echo Operation cancelled.
    exit /b 0
)

echo.
echo Step 1: Stopping any running C2 server instances...
taskkill /F /FI "WINDOWTITLE eq C2 Server*" > nul 2>&1
echo Any running C2 server instances have been stopped.
echo.

echo Step 2: Removing database file...
if exist "c2_server\c2_database.db" (
    del /F "c2_server\c2_database.db"
    echo Database file removed.
) else (
    echo Database file not found.
)
echo.

echo Step 3: Removing log files...
del /F *.log > nul 2>&1
del /F c2_server\*.log > nul 2>&1
echo Log files removed.
echo.

echo Step 4: Removing cache files...
if exist "__pycache__" (
    rmdir /S /Q "__pycache__"
)
if exist "c2_server\__pycache__" (
    rmdir /S /Q "c2_server\__pycache__"
)
echo Cache files removed.
echo.

echo ===================================================
echo Cleanup Complete!
echo ===================================================
echo.
echo The system has been reset to a clean state.
echo You can now start the C2 server with a fresh database.
echo.
echo Press any key to exit...
pause > nul
