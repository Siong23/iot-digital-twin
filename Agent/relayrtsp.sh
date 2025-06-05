#!/bin/bash

# Loop and forward stream from Digital IP Camera to Digital IoT Broker
ffmpeg -re -stream_loop -1 \
  -i rtsp://admin:admin@11.10.10.10:8554/proxied \
  -c copy -f rtsp rtsp://10.10.10.10:8554/ip_camera
