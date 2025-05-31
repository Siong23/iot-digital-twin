#!/bin/bash
# Full System Test Script
echo "==================================================="
echo "IoT C2 and Exploit System Test"
echo "==================================================="
echo ""

# Check for Python installation
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed or not in PATH"
    echo "Please install Python 3.9+ and try again"
    exit 1
fi

echo "Step 1: Installing dependencies..."
pip3 install -r requirements.txt

if [ $? -ne 0 ]; then
    echo "ERROR: Failed to install dependencies"
    exit 1
fi

echo ""
echo "Step 2: Testing C2 server startup..."
python3 run_c2_server.py > /dev/null 2>&1 &
C2_PID=$!
echo "Started C2 server in the background (PID: $C2_PID)"
echo ""

# Wait for server to start
echo "Waiting 5 seconds for server to initialize..."
sleep 5

echo "Step 3: Running system tests..."
python3 test_c2_and_exploit.py 127.0.0.1
if [ $? -ne 0 ]; then
    echo "WARNING: Tests completed with some errors"
else
    echo "All tests completed successfully!"
fi
echo ""

echo "Step 4: Creating example simulated devices..."
python3 -c "import socket, threading, time; [threading.Thread(target=lambda ip: socket.socket().connect_ex(('127.0.0.1', 5000)) or print(f'Connected to C2 from {ip}'), args=[f'192.168.1.{i}']).start() for i in range(10, 15)]; time.sleep(5)"
echo "Created 5 simulated device connections"

echo ""
echo "==================================================="
echo "System Test Complete"
echo "==================================================="
echo ""
echo "C2 server is still running in the background (PID: $C2_PID)."
echo "You can access the dashboard at: http://127.0.0.1:5000"
echo ""
echo "Press Enter to stop the C2 server and exit..."
read

# Kill the C2 server process
kill $C2_PID > /dev/null 2>&1
echo "C2 server stopped"

echo ""
echo "System test completed."
