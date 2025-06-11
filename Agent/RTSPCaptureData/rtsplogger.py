import subprocess
import csv
import time
from datetime import datetime
import re

# RTSP stream URL
RTSP_URL = "rtsp://admin:admin@localhost:8554/proxied"

# Output CSV file
csv_file = "rtsp_stream_telemetry.csv"

# Initialize CSV file with header
with open(csv_file, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["ts", "bitrate_kbps", "fps", "resolution", "codec", "frame_count"])

# FFmpeg command with verbose logging and 1s stats interval
ffmpeg_cmd = [
    "ffmpeg", "-stats_period", "1", "-loglevel", "verbose",
    "-rtsp_transport", "tcp", "-i", RTSP_URL,
    "-f", "null", "-"
]

process = subprocess.Popen(
    ffmpeg_cmd,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    universal_newlines=True,
    bufsize=1
)

frame_count = 0
codec = "unknown"
resolution = "unknown"
fps = "0"
bitrate = "0"
last_log_time = time.time()
metadata_found = False
start_time = time.time()

# Regex patterns
stream_info_pattern = re.compile(r"Stream #\\d+:\\d+: Video: (\\w+).*?, (\\d+x\\d+).*?, (\\d+) fps")
frame_pattern = re.compile(r"frame=\\s*(\\d+)")
fps_pattern = re.compile(r"fps=\\s*(\\d+)")
bitrate_pattern = re.compile(r"bitrate=\\s*(\\d+(?:\\.\\d+)?)kbits/s")

try:
    for line in process.stdout:
        now = time.time()
        line = line.strip()

        # Print for debug
        print(line)

        # Extract stream info once
        if not metadata_found and "Stream #" in line:
            match = stream_info_pattern.search(line)
            if match:
                codec, resolution, fps = match.groups()
                metadata_found = True

        # Fallback: apply default values if metadata not found after 5s
        if not metadata_found and (now - start_time > 5):
            codec = "h264"
            resolution = "704x576"
            fps = "15"
            metadata_found = True

        # Extract real-time values
        match = frame_pattern.search(line)
        if match:
            frame_count = int(match.group(1))

        match = fps_pattern.search(line)
        if match:
            fps = match.group(1)

        match = bitrate_pattern.search(line)
        if match:
            bitrate = match.group(1)

        # Log every second
        if now - last_log_time >= 1:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(csv_file, "a", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([timestamp, bitrate, fps, resolution, codec, frame_count])
            print(f"[LOG] {timestamp} | bitrate={bitrate} kbps | fps={fps} | frame={frame_count} | res={resolution} | codec={codec}")
            last_log_time = now

except KeyboardInterrupt:
    print("Interrupted. Cleaning up...")
    process.terminate()
    process.wait()

print("Telemetry logging finished.")
