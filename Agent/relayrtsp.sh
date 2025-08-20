#!/bin/bash

# relayrtsp.sh - Compatible RTSP relay (Debian-safe)

SOURCE_URL="rtsp://admin:admin@localhost:8554/proxied"
DEST_URL="rtsp://192.168.20.2:8554/ip_camera"
RETRY_DELAY=5

while true; do
        echo "[*] Starting stream relay at $(date)"

        #Loop and forward stream from Digital IP Camera To Digital Iot Broker
        ffmpeg -re -stream_loop -1 \
         -rtsp_transport tcp \
         -stimeout 5000000 \
         -i "$SOURCE_URL" \
         -fflags nobuffer -flags low_delay \
         -c copy -f rtsp "$DEST_URL" \

        echo "[!] FFmpeg exited. Retrying in $RETRY_DELAY seconds..."
        sleep $RETRY_DELAY
done
