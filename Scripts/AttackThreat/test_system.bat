@echo off
REM Full System Test Script
echo ===================================================
echo IoT C2 and Exploit System Test
echo ===================================================
echo.

REM Check for Python installation
python --version > nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.9+ and try again
    exit /b 1
)

echo Step 1: Installing dependencies...
pip install -r requirements.txt

if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Failed to install dependencies
    exit /b 1
)

echo.
echo Step 2: Testing C2 server startup...
start "C2 Server" /MIN cmd /c "python run_c2_server.py"
echo Started C2 server in the background
echo.

REM Wait for server to start
echo Waiting 5 seconds for server to initialize...
timeout /t 5 /nobreak > nul

echo Step 3: Running system tests...
python test_c2_and_exploit.py 127.0.0.1
if %ERRORLEVEL% NEQ 0 (
    echo WARNING: Tests completed with some errors
) else (
    echo All tests completed successfully!
)
echo.

echo Step 4: Creating example simulated devices...
python -c "import socket, threading, time; [threading.Thread(target=lambda ip: socket.socket().connect_ex(('127.0.0.1', 5000)) or print(f'Connected to C2 from {ip}'), args=[f'192.168.1.{i}']).start() for i in range(10, 15)]; time.sleep(5)"
echo Created 5 simulated device connections

echo.
echo ===================================================
echo System Test Complete
echo ===================================================
echo.
echo C2 server is still running in the background.
echo You can access the dashboard at: http://127.0.0.1:5000
echo.
echo Press any key to stop the C2 server and exit...
pause > nul

REM Kill the C2 server process
taskkill /F /FI "WINDOWTITLE eq C2 Server*" > nul 2>&1
echo C2 server stopped

echo.
echo System test completed.
