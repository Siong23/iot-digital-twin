#!/bin/bash

# Run using ./relayrtsp.sh

# Loop and forward stream from Digital IP Camera to Digital IoT Broker
ffmpeg -re -stream_loop -1 \
 -rtsp_transport tcp \
 -rtsp_flags +keepalive \
 -stimeout 5000000 \
 -reconnect 1 \
 -reconnect_streamed 1 \
 -reconnect_delay_max 2 \
 -i rtsp://admin:admin@localhost:8554/proxied \
 -fflags nobuffer -flags low_delay \
 -c copy -f rtsp rtsp://10.10.10.10:8554/ip_camera
 -loglevel error > /dev/null 2>&1 &
echo $! > ffmpeg_pid.txt  # Save PID