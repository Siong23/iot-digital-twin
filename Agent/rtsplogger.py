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

# FFmpeg command
ffmpeg_cmd = [
    "ffmpeg", "-loglevel", "info", "-rtsp_transport", "tcp", "-i", RTSP_URL,
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
codec = ""
resolution = ""
fps = ""
bitrate = ""
last_log_time = time.time()

# Regex patterns
stream_info_pattern = re.compile(r"Stream #\\d+:\\d+: Video: (\\w+).*?, (\\d+x\\d+).*?, (\\d+) fps")
frame_line_pattern = re.compile(r"frame=\\s*(\\d+)\\s+fps=\\s*(\\d+).*?bitrate=\\s*(\\d+(?:\\.\\d+)?)kbits/s")

try:
    for line in process.stdout:
        now = time.time()

        # Extract stream info once
        if not codec and "Stream #" in line:
            match = stream_info_pattern.search(line)
            if match:
                codec, resolution, fps = match.groups()

        # Parse live frame line
        match = frame_line_pattern.search(line)
        if match:
            frame_count = int(match.group(1))
            fps = match.group(2)
            bitrate = match.group(3)

        # Log once per second
        if now - last_log_time >= 1:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(csv_file, "a", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([timestamp, bitrate, fps, resolution, codec, frame_count])
            last_log_time = now

except KeyboardInterrupt:
    print("Interrupted. Cleaning up...")
    process.terminate()
    process.wait()

print("Telemetry logging finished.")
