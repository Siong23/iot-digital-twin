#!/bin/bash

# telemetry_control.sh
# Usage: ./telemetry_control.sh start|stop

ACTION=$1
FFMPEG_PID_FILE="ffmpeg_pid.txt"
LABEL_FILE="labels.csv"
LOG_TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Ensure psrecord is installed
command -v psrecord >/dev/null 2>&1 || { echo >&2 "psrecord is required. Install with: pip install psrecord"; exit 1; }

# Validate PID file
if [ ! -f "$FFMPEG_PID_FILE" ]; then
    echo "Error: FFmpeg PID file not found. Please start your stream first and save PID to $FFMPEG_PID_FILE."
    exit 1
fi

FFMPEG_PID=$(cat $FFMPEG_PID_FILE)

if [ "$ACTION" == "start" ]; then
    echo "[+] Starting telemetry logging..."
    echo "$(date -Iseconds),telemetry_start" >> $LABEL_FILE

    psrecord $FFMPEG_PID --interval 1 --log telemetry_usage_$LOG_TIMESTAMP.csv &
    echo $! > psrecord_pid.txt

    strace -ttt -s 500 -p $FFMPEG_PID -e trace=write -o telemetry_internal_$LOG_TIMESTAMP.log &
    echo $! > strace_pid.txt

    echo "[+] Logging started. Output files: telemetry_usage_$LOG_TIMESTAMP.csv, telemetry_internal_$LOG_TIMESTAMP.log"

elif [ "$ACTION" == "stop" ]; then
    echo "[+] Stopping telemetry logging..."
    echo "$(date -Iseconds),telemetry_stop" >> $LABEL_FILE

    # Kill psrecord and strace using stored PIDs
    if [ -f psrecord_pid.txt ]; then
        kill $(cat psrecord_pid.txt) 2>/dev/null && rm psrecord_pid.txt
    fi
    if [ -f strace_pid.txt ]; then
        kill $(cat strace_pid.txt) 2>/dev/null && rm strace_pid.txt
    fi

    echo "[+] Logging stopped."

else
    echo "Usage: $0 start|stop"
    exit 1
fi
