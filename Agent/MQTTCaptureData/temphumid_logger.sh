#!/bin/bash
# Usage: ./temphumid_logger.sh start|stop

ACTION=$1
PID_FILE="temphumid_logger.pid"

if [ "$ACTION" == "start" ]; then
    echo "[+] Starting digital temp/humid telemetry logger..."
    python3 mqtt_logger.py > /dev/null 2>&1 &
    echo $! > $PID_FILE
    echo "[+] Logger started with PID $(cat $PID_FILE)"

elif [ "$ACTION" == "stop" ]; then
    if [ -f "$PID_FILE" ]; then
        echo "[+] Stopping telemetry logger..."
        kill $(cat $PID_FILE) && rm $PID_FILE
        echo "[+] Logger stopped."
    else
        echo "[-] PID file not found. Is the logger running?"
    fi

else
    echo "Usage: $0 start|stop"
fi
