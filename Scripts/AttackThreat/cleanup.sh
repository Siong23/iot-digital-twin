#!/bin/bash
# Clean Database and Logs Script
echo "==================================================="
echo "IoT C2 Server - Cleanup Utility"
echo "==================================================="
echo ""

echo "This script will remove:"
echo "- C2 server database (c2_server/c2_database.db)"
echo "- All log files (*.log)"
echo "- Cache files (__pycache__ directories)"
echo ""

read -p "Are you sure you want to proceed? (y/n): " CONFIRM
if [[ "$CONFIRM" != "y" && "$CONFIRM" != "Y" ]]; then
    echo "Operation cancelled."
    exit 0
fi

echo ""
echo "Step 1: Stopping any running C2 server instances..."
pkill -f "python3 run_c2_server.py" > /dev/null 2>&1
echo "Any running C2 server instances have been stopped."
echo ""

echo "Step 2: Removing database file..."
if [ -f "c2_server/c2_database.db" ]; then
    rm -f "c2_server/c2_database.db"
    echo "Database file removed."
else
    echo "Database file not found."
fi
echo ""

echo "Step 3: Removing log files..."
find . -name "*.log" -type f -delete
echo "Log files removed."
echo ""

echo "Step 4: Removing cache files..."
find . -name "__pycache__" -type d -exec rm -rf {} +
find . -name "*.pyc" -type f -delete
echo "Cache files removed."
echo ""

echo "==================================================="
echo "Cleanup Complete!"
echo "==================================================="
echo ""
echo "The system has been reset to a clean state."
echo "You can now start the C2 server with a fresh database."
echo ""
echo "Press Enter to exit..."
read
