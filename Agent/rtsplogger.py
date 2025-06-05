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

# Run FFmpeg as subprocess
ffmpeg_cmd = [
    "ffmpeg", "-hide_banner", "-rtsp_transport", "tcp", "-i", RTSP_URL,
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

# Pattern to extract stream info
stream_info_pattern = re.compile(r"Stream #\\d+:\\d+: Video: (\\w+).*?, (\\d+x\\d+).*?(\\d+) fps")
bitrate_pattern = re.compile(r"bitrate=\\s*(\\d+)kbits/s")

try:
    for line in process.stdout:
        now = time.time()

        # Extract metadata once at start
        if not codec and "Stream #" in line:
            match = stream_info_pattern.search(line)
            if match:
                codec, resolution, fps = match.groups()

        # Update bitrate if available
        if "bitrate=" in line:
            match = bitrate_pattern.search(line)
            if match:
                bitrate = match.group(1)

        if "frame=" in line:
            frame_count += 1

        # Log every 1 second
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