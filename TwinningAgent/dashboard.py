#!/usr/bin/env python3
"""
dashboard.py

RTSP video dashboard with a bottom 2x2 device status grid.

Usage:
    python3 dashboard.py --rtsp rtsp://192.168.20.2:8554/proxied --mqtt-host 192.168.20.2

Requirements:
    pip install opencv-python paho-mqtt numpy
"""

import argparse
import logging
import json
import threading
import time
import queue
import signal
from collections import defaultdict, deque
from datetime import datetime
import cv2
import numpy as np
import paho.mqtt.client as mqtt

# ---------------- CONFIG & ARGS ----------------
DEFAULT_RTSP = "rtsp://192.168.20.2:8554/proxied"
DEFAULT_MQTT_HOST = "192.168.20.2"
DEFAULT_MQTT_PORT = 1883
FRAME_QUEUE_MAX = 2  # bounded buffer
VIDEO_WATCHDOG_TIMEOUT = 6.0  # seconds without new frame => restart capture

DEVICE_LIST = ["broker", "ipcam", "sensor", "router"]  # order for 2x2 grid

parser = argparse.ArgumentParser()
parser.add_argument("--rtsp", default=DEFAULT_RTSP, help="RTSP URL for the camera")
parser.add_argument("--mqtt-host", default=DEFAULT_MQTT_HOST, help="MQTT broker host")
parser.add_argument("--mqtt-port", type=int, default=DEFAULT_MQTT_PORT, help="MQTT broker port")
parser.add_argument("--mqtt-user", default=None, help="MQTT username (optional)")
parser.add_argument("--mqtt-pass", default=None, help="MQTT password (optional)")
parser.add_argument("--win-name", default="Dashboard", help="OpenCV window name")
parser.add_argument("--scale", type=float, default=1.0, help="Scale display (0.5 = half size)")
args = parser.parse_args()

# ---------------- LOGGING ----------------
logging.basicConfig(
    filename="dashboard.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logging.getLogger().addHandler(logging.StreamHandler())  # also print to stdout

# ---------------- GLOBAL STATE ----------------
frame_q = queue.Queue(maxsize=FRAME_QUEUE_MAX)
running = threading.Event()
running.set()

last_frame_time = 0.0
last_frame_lock = threading.Lock()

# statuses: dict -> {"status": "UP"/"DOWN"/"UNKNOWN", "ts": epoch}
statuses = {}
for d in DEVICE_LIST:
    statuses[d] = {"status": "UNKNOWN", "ts": 0}

# for optional telemetry (temp/humidity)
telemetry = defaultdict(lambda: {"temp": None, "hum": None, "history": deque(maxlen=120)})

# ---------------- RTSP CAPTURE THREAD ----------------
def rtsp_capture_loop(rtsp_url):
    """Producer: capture frames from RTSP into a bounded queue."""
    global last_frame_time
    cap = None
    while running.is_set():
        try:
            if cap is None or not cap.isOpened():
                logging.info("Opening video capture: %s", rtsp_url)
                cap = cv2.VideoCapture(rtsp_url)
                if not cap.isOpened():
                    logging.warning("Unable to open RTSP stream; retrying in 2s")
                    time.sleep(2)
                    continue
                # read one frame to ensure stream started
                ret, frame = cap.read()
                if not ret or frame is None:
                    logging.warning("RTSP opened but no frame; retrying in 1s")
                    time.sleep(1)
                    continue
                with last_frame_lock:
                    last_frame_time = time.time()
                # push initial frame
                try:
                    frame_q.put_nowait(frame)
                except queue.Full:
                    pass

            # normal capture loop
            ret, frame = cap.read()
            if not ret or frame is None:
                logging.warning("Frame read failed; closing and reopening capture")
                try:
                    cap.release()
                except Exception:
                    pass
                cap = None
                time.sleep(1)
                continue

            # put frame into bounded queue (drop oldest if full)
            try:
                frame_q.put(frame, timeout=0.2)
            except queue.Full:
                try:
                    _ = frame_q.get_nowait()  # drop oldest
                    frame_q.put_nowait(frame)
                except Exception:
                    pass

            with last_frame_lock:
                last_frame_time = time.time()

        except Exception as e:
            logging.exception("RTSP capture exception: %s", e)
            # try to close and reopen
            try:
                if cap:
                    cap.release()
            except Exception:
                pass
            cap = None
            time.sleep(2)

    # cleanup
    try:
        if cap:
            cap.release()
    except Exception:
        pass
    logging.info("RTSP capture loop exited")

# ---------------- VIDEO WATCHDOG THREAD ----------------
def video_watchdog(rtsp_url):
    """Restart capture by clearing the queue if no frames arrive for a while."""
    global last_frame_time
    while running.is_set():
        time.sleep(1.0)
        with last_frame_lock:
            t = last_frame_time
        if t == 0:
            continue
        if time.time() - t > VIDEO_WATCHDOG_TIMEOUT:
            logging.warning("Video watchdog: no frames for %.1fs -> clearing queue to force reopen", time.time() - t)
            # empty queue to trigger capture thread to reopen
            with frame_q.mutex:
                frame_q.queue.clear()
            # set last_frame_time to now so we don't spam
            with last_frame_lock:
                last_frame_time = time.time()

# ---------------- MQTT HANDLERS ----------------
def mqtt_on_connect(client, userdata, flags, rc):
    if rc == 0:
        logging.info("MQTT connected to %s:%d", args.mqtt_host, args.mqtt_port)
        prefix = userdata.get("mqtt_prefix", "health")
        client.subscribe(f"{prefix}/#")
    else:
        logging.warning("MQTT connect failed rc=%s", rc)

def mqtt_on_message(client, userdata, msg):
    try:
        topic = msg.topic
        # expected: health/<src>/<dst>
        parts = topic.split("/")
        if len(parts) >= 3 and parts[0] == userdata.get("mqtt_prefix", "health"):
            _, src, dst = parts[:3]
            try:
                payload = msg.payload.decode("utf-8").strip()
                obj = json.loads(payload) if payload else {}
            except Exception:
                obj = {}
            status = obj.get("status", None)
            if status is None:
                # fallback: if payload is text "UP"/"DOWN"
                txt = payload.upper() if isinstance(payload, str) else ""
                if txt in ("UP", "DOWN"):
                    status = txt
            if status:
                status_val = "UP" if status.upper() == "UP" else "DOWN"
                if src in statuses:
                    statuses[src]["status"] = status_val
                    statuses[src]["ts"] = time.time()
                    logging.info("MQTT: %s -> %s", src, status_val)
                else:
                    # maybe set for dst as well if not known
                    if dst in statuses:
                        statuses[dst]["status"] = status_val
                        statuses[dst]["ts"] = time.time()
                        logging.info("MQTT: %s -> %s (applied to dst %s)", src, status_val, dst)
        else:
            # optional telemetry topics such as telemetry/<device>/temp
            parts = topic.split("/")
            if len(parts) >= 3 and parts[0] in ("telemetry", "telemetery", "tele"):
                _, device, metric = parts[:3]
                try:
                    val = float(msg.payload.decode("utf-8"))
                except Exception:
                    val = None
                if device in telemetry:
                    if metric in ("temp", "temperature"):
                        telemetry[device]["temp"] = val
                        telemetry[device]["history"].append(("temp", time.time(), val))
                    elif metric in ("hum", "humidity"):
                        telemetry[device]["hum"] = val
                        telemetry[device]["history"].append(("hum", time.time(), val))
    except Exception as e:
        logging.exception("Error in mqtt_on_message: %s", e)

def start_mqtt_client():
    client = mqtt.Client(userdata={"mqtt_prefix": "health"})
    if args.mqtt_user:
        client.username_pw_set(args.mqtt_user, args.mqtt_pass or "")
    client.on_connect = mqtt_on_connect
    client.on_message = mqtt_on_message
    try:
        client.connect(args.mqtt_host, args.mqtt_port, keepalive=60)
        client.loop_start()
        return client
    except Exception as e:
        logging.exception("MQTT connect failed: %s", e)
        return None

# ---------------- RENDER / UI ----------------
def draw_status_grid(img, devices, bottom_height_ratio=0.22):
    """
    Draw a 2x2 grid of device statuses at bottom of image.
    devices: list of device names in order -> [0] top-left, [1] top-right, [2] bottom-left, [3] bottom-right
    """
    h, w = img.shape[:2]
    bh = int(h * bottom_height_ratio)
    grid_y0 = h - bh
    # draw a semi-transparent background rectangle
    overlay = img.copy()
    cv2.rectangle(overlay, (0, grid_y0), (w, h), (10, 10, 10), -1)
    alpha = 0.65
    cv2.addWeighted(overlay, alpha, img, 1 - alpha, 0, img)

    # grid: 2 cols x 2 rows
    cols = 2
    rows = 2
    cell_w = w // cols
    cell_h = bh // rows

    for idx, name in enumerate(devices):
        col = idx % cols
        row = idx // cols
        x0 = col * cell_w
        y0 = grid_y0 + row * cell_h
        x1 = x0 + cell_w - 8
        y1 = y0 + cell_h - 8

        # device status
        st = statuses.get(name, {"status": "UNKNOWN", "ts": 0})
        state = st.get("status", "UNKNOWN")
        ts = st.get("ts", 0)
        age = time.time() - ts if ts else None

        # color: UP=green, DOWN=red, UNKNOWN=gray, stale=yellow
        if state == "UP":
            color = (50, 200, 50)  # green
        elif state == "DOWN":
            color = (30, 30, 220)  # red-ish (BGR)
        else:
            color = (180, 180, 180)  # gray

        # if stale (> 90s) treat as UNKNOWN color
        if age is None or age > 90:
            color = (160, 160, 160)
            status_text = "STALE" if age and age > 90 else "UNKNOWN"
        else:
            status_text = state

        # draw box + label
        cv2.rectangle(img, (x0 + 6, y0 + 6), (x1, y1), color, thickness=-1)
        # inner darker rectangle for contrast
        cv2.rectangle(img, (x0 + 10, y0 + 10), (x1 - 4, y1 - 4), (12, 12, 12), thickness=-1)

        # text: device name (top-left of cell)
        name_txt = name.upper()
        status_txt = f"{status_text} " + (f"{int(age)}s" if age is not None else "")

        # font sizes scale with width
        font = cv2.FONT_HERSHEY_SIMPLEX
        name_scale = max(0.6, cell_w / 500.0)
        status_scale = max(0.5, cell_w / 650.0)
        cv2.putText(img, name_txt, (x0 + 18, y0 + 34), font, name_scale, (255, 255, 255), 2, cv2.LINE_AA)
        cv2.putText(img, status_txt, (x0 + 18, y0 + 34 + int(28 * status_scale)), font, status_scale, (220, 220, 220), 1, cv2.LINE_AA)

def render_loop(window_name, scale):
    """Consumer: take frames from queue, overlay info, and display."""
    last_fps_time = time.time()
    frames = 0
    fps = 0.0
    while running.is_set():
        try:
            frame = None
            try:
                frame = frame_q.get(timeout=1.0)
            except queue.Empty:
                # nothing to show; continue to check running flag
                continue

            frames += 1
            now = time.time()
            if now - last_fps_time >= 1.0:
                fps = frames / (now - last_fps_time)
                frames = 0
                last_fps_time = now

            # resize according to scale
            if scale != 1.0:
                h, w = frame.shape[:2]
                frame = cv2.resize(frame, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)

            # overlay timestamp and FPS
            txt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cv2.putText(frame, txt, (12, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (240, 240, 240), 1, cv2.LINE_AA)
            cv2.putText(frame, f"FPS: {fps:.1f}", (12, 46), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (220, 220, 220), 1, cv2.LINE_AA)

            # draw the 2x2 status grid at bottom
            draw_status_grid(frame, DEVICE_LIST, bottom_height_ratio=0.22)

            # show
            cv2.imshow(window_name, frame)
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                logging.info("Q pressed, exiting")
                running.clear()
                break

        except Exception as e:
            logging.exception("Render loop exception: %s", e)
            # small sleep so we don't spin on repeated errors
            time.sleep(0.5)

    try:
        cv2.destroyAllWindows()
    except Exception:
        pass
    logging.info("Render loop exited")

# ---------------- CLEAN SHUTDOWN HANDLER ----------------
def handle_signal(signum, frame):
    logging.info("Signal %s received, shutting down...", signum)
    running.clear()

signal.signal(signal.SIGINT, handle_signal)
signal.signal(signal.SIGTERM, handle_signal)

# ---------------- MAIN START ----------------
def main():
    logging.info("Starting dashboard")
    # start RTSP capture thread
    cap_thread = threading.Thread(target=rtsp_capture_loop, args=(args.rtsp,), daemon=True)
    cap_thread.start()

    # start watchdog
    wd_thread = threading.Thread(target=video_watchdog, args=(args.rtsp,), daemon=True)
    wd_thread.start()

    # start MQTT
    mqtt_client = start_mqtt_client()

    # start renderer (main thread)
    render_loop(args.win_name, args.scale)

    # cleanup
    running.clear()
    time.sleep(0.3)
    if mqtt_client:
        try:
            mqtt_client.loop_stop()
            mqtt_client.disconnect()
        except Exception:
            pass
    logging.info("Dashboard stopped")

if __name__ == "__main__":
    main()
