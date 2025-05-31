#!/bin/bash
# IoT C2 Server - Installation and Setup Script
echo "==================================================="
echo "IoT C2 Server - Installation and Setup"
echo "==================================================="
echo ""

# Check for Python installation
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed or not in PATH"
    echo "Please install Python 3.9+ and try again"
    exit 1
fi

echo "Installing required dependencies..."
pip3 install -r requirements.txt

if [ $? -ne 0 ]; then
    echo "ERROR: Failed to install dependencies"
    exit 1
fi

echo ""
echo "Dependencies installed successfully!"
echo ""
echo "==================================================="
echo "Starting C2 Server..."
echo "==================================================="
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

python3 c2_server.py
