#!/bin/bash

# relayrtsp.sh - Compatible RTSP relay (Debian-safe)

ffmpeg -re -stream_loop -1 \
 -rtsp_transport tcp \
 -stimeout 5000000 \
 -i rtsp://admin:admin@localhost:8554/proxied \
 -fflags nobuffer -flags low_delay \
 -c copy -f rtsp rtsp://10.10.10.10:8554/ip_camera \
 -loglevel error > /dev/null 2>&1 &

echo $! > ffmpeg_pid.txt
