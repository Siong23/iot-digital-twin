#!/usr/bin/env python3
"""
dashboard_grid.py

2x2 IoT Dashboard:
 - Top-left: RTSP video (OpenCV -> Tkinter)
 - Top-right: Temperature (large)
 - Bottom-left: Humidity (large)
 - Bottom-right: Status/Log (scrollable) + small indicators

Features:
 - MQTT subscriber with auto-reconnect
 - Thread-safe UI updates via queue
 - Video reader thread with watchdog / reconnect
 - Clean shutdown on window close / Ctrl-C
 - Bounded queues to avoid memory growth
"""

import tkinter as tk
from tkinter.scrolledtext import ScrolledText
from PIL import Image, ImageTk
import cv2
import threading
import queue
import time
import json
import logging
import signal
import sys
import paho.mqtt.client as mqtt

# -------- CONFIG (edit to match your env) ----------
RTSP_URL = "rtsp://192.168.20.2:8554/proxied"  # example
MQTT_HOST = "192.168.20.2"
MQTT_PORT = 1883
MQTT_USER = "admin"
MQTT_PASS = "admin123"
MQTT_TOPIC = "health/#"  # listens to health updates
VIDEO_RECONNECT_SEC = 5
VIDEO_WATCHDOG_THRESHOLD = 8.0  # seconds of no frames before reconnect
FRAME_MAX_QUEUE = 2
UI_UPDATE_INTERVAL_MS = 200  # how often UI pulls updates from queue
WINDOW_TITLE = "IoT 2x2 Dashboard"

# -------- LOGGING ----------
logging.basicConfig(level=logging.INFO, filename="dashboard_grid.log",
                    format="%(asctime)s [%(levelname)s] %(message)s")

# -------- THREAD-TO-UI QUEUES ----------
ui_queue = queue.Queue(maxsize=256)     # events to UI (mqtt updates, logs)
frame_queue = queue.Queue(maxsize=FRAME_MAX_QUEUE)  # latest video frames

# -------- GLOBAL CONTROL ----------
_stop_event = threading.Event()

# -------- MQTT HANDLER ----------
def mqtt_on_connect(client, userdata, flags, rc):
    if rc == 0:
        msg = f"MQTT connected to {MQTT_HOST}:{MQTT_PORT}"
        logging.info(msg)
        try:
            client.subscribe(MQTT_TOPIC)
            ui_queue.put_nowait(("log", msg))
        except Exception as e:
            logging.exception("Failed subscribe")
            ui_queue.put_nowait(("log", f"MQTT subscribe error: {e}"))
    else:
        ui_queue.put_nowait(("log", f"MQTT connect failed rc={rc}"))

def mqtt_on_message(client, userdata, msg):
    # Expecting topics like health/sensor/broker and JSON payload {"status":"DOWN"} or others.
    try:
        payload = msg.payload.decode(errors="ignore")
        topic = msg.topic
        data = None
        try:
            data = json.loads(payload)
        except Exception:
            data = payload
        ui_queue.put_nowait(("mqtt", (topic, data)))
    except queue.Full:
        # drop if UI too slow
        logging.warning("ui_queue is full, dropping mqtt message")

def mqtt_thread():
    client = mqtt.Client()
    if MQTT_USER:
        client.username_pw_set(MQTT_USER, MQTT_PASS)
    client.on_connect = mqtt_on_connect
    client.on_message = mqtt_on_message

    # auto-reconnect loop
    while not _stop_event.is_set():
        try:
            client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
            client.loop_start()
            # run until disconnected or stop
            while not _stop_event.is_set():
                time.sleep(0.5)
            client.loop_stop()
            try:
                client.disconnect()
            except Exception:
                pass
            break
        except Exception as e:
            logging.exception("MQTT connect error")
            ui_queue.put_nowait(("log", f"MQTT connect error: {e}"))
            # wait and retry
            for _ in range(10):
                if _stop_event.is_set():
                    break
                time.sleep(1)
    logging.info("MQTT thread exiting")

# -------- VIDEO THREAD ----------
def video_reader(rtsp_url):
    """
    Continuously attempts to read frames and put the latest into frame_queue.
    Watchdog reconnect if no frames for VIDEO_WATCHDOG_THRESHOLD seconds.
    """
    cap = None
    last_frame_ts = 0
    while not _stop_event.is_set():
        try:
            if cap is None or not cap.isOpened():
                logging.info("Opening video capture: %s", rtsp_url)
                cap = cv2.VideoCapture(rtsp_url)
                # small delay for some RTSP servers
                time.sleep(0.5)

            ret, frame = cap.read()
            if not ret or frame is None:
                # no frame, maybe transient; check watchdog
                if last_frame_ts and (time.time() - last_frame_ts) > VIDEO_WATCHDOG_THRESHOLD:
                    logging.warning("Video watchdog triggered, reconnecting capture")
                    try:
                        cap.release()
                    except Exception:
                        pass
                    cap = None
                    last_frame_ts = 0
                    time.sleep(VIDEO_RECONNECT_SEC)
                else:
                    time.sleep(0.1)
                continue

            last_frame_ts = time.time()
            # convert BGR -> RGB for PIL
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            # enqueue latest frame (drop older if full)
            try:
                # keep only the latest frame by emptying the queue first if full
                if frame_queue.full():
                    try:
                        frame_queue.get_nowait()
                    except Exception:
                        pass
                frame_queue.put_nowait(frame_rgb)
            except queue.Full:
                pass

            # small throttle
            time.sleep(0.02)
        except Exception as e:
            logging.exception("Video reader exception")
            ui_queue.put_nowait(("log", f"Video reader error: {e}"))
            try:
                if cap:
                    cap.release()
            except Exception:
                pass
            cap = None
            time.sleep(VIDEO_RECONNECT_SEC)
    # cleanup
    try:
        if cap:
            cap.release()
    except Exception:
        pass
    logging.info("Video thread exiting")

# -------- UI ----------
class Dashboard(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(WINDOW_TITLE)
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.create_widgets()
        # state
        self.temp_val = tk.StringVar(value="-- °C")
        self.hum_val = tk.StringVar(value="-- %")
        self.mqtt_status = tk.StringVar(value="MQTT: -")
        self.video_image = None  # keep reference to avoid GC
        # schedule UI update
        self.after(UI_UPDATE_INTERVAL_MS, self.consume_queues)

    def create_widgets(self):
        # use grid 2x2
        # top-left: video frame
        self.video_frame = tk.Frame(self, bd=2, relief=tk.SUNKEN, width=480, height=320)
        self.video_frame.grid(row=0, column=0, padx=4, pady=4, sticky="nsew")
        self.video_label = tk.Label(self.video_frame)
        self.video_label.pack(expand=True, fill="both")

        # top-right: temperature big label
        self.temp_frame = tk.Frame(self, bd=2, relief=tk.SUNKEN, width=240, height=160)
        self.temp_frame.grid(row=0, column=1, padx=4, pady=4, sticky="nsew")
        tk.Label(self.temp_frame, text="Temperature", font=("Helvetica", 12)).pack()
        self.temp_display = tk.Label(self.temp_frame, textvariable=self.temp_val,
                                     font=("Helvetica", 36), fg="red")
        self.temp_display.pack(expand=True)

        # bottom-left: humidity
        self.hum_frame = tk.Frame(self, bd=2, relief=tk.SUNKEN, width=240, height=160)
        self.hum_frame.grid(row=1, column=0, padx=4, pady=4, sticky="nsew")
        tk.Label(self.hum_frame, text="Humidity", font=("Helvetica", 12)).pack()
        self.hum_display = tk.Label(self.hum_frame, textvariable=self.hum_val,
                                    font=("Helvetica", 36), fg="orange")
        self.hum_display.pack(expand=True)

        # bottom-right: status/log
        self.log_frame = tk.Frame(self, bd=2, relief=tk.SUNKEN, width=240, height=160)
        self.log_frame.grid(row=1, column=1, padx=4, pady=4, sticky="nsew")
        tk.Label(self.log_frame, text="Status / Log", font=("Helvetica", 12)).pack()
        self.log_text = ScrolledText(self.log_frame, height=8, state="disabled")
        self.log_text.pack(expand=True, fill="both")

        # make grid expand reasonably
        self.grid_rowconfigure(0, weight=3)
        self.grid_rowconfigure(1, weight=2)
        self.grid_columnconfigure(0, weight=3)
        self.grid_columnconfigure(1, weight=2)

        # small bottom bar for indicators
        self.indicator_frame = tk.Frame(self, bd=0)
        self.indicator_frame.grid(row=2, column=0, columnspan=2, sticky="ew", padx=4, pady=2)
        tk.Label(self.indicator_frame, textvariable=self.mqtt_status).pack(side="left")

    def consume_queues(self):
        # pop frames and display the latest
        try:
            while True:
                frame = frame_queue.get_nowait()
                # convert to PIL Image and resize to video_label size
                try:
                    pil = Image.fromarray(frame)
                    # get current label size (fallback to defaults)
                    w = max(160, self.video_label.winfo_width() or 480)
                    h = max(120, self.video_label.winfo_height() or 320)
                    pil = pil.resize((w, h), Image.BILINEAR)
                    self.video_image = ImageTk.PhotoImage(pil)
                    self.video_label.config(image=self.video_image)
                except Exception:
                    logging.exception("Failed to render video frame")
        except queue.Empty:
            pass

        # process UI events (mqtt/log)
        processed = 0
        while processed < 20:
            try:
                kind, payload = ui_queue.get_nowait()
            except queue.Empty:
                break
            processed += 1
            if kind == "log":
                self.append_log(str(payload))
            elif kind == "mqtt":
                topic, data = payload
                # very basic parsing: if topic includes 'temperature' or 'temp' update, likewise humidity
                t = topic.lower()
                if "temp" in t or ("sensor" in t and "temp" in json.dumps(data).lower()):
                    # try extract numeric
                    v = extract_numeric_from_payload(data)
                    if v is not None:
                        self.temp_val.set(f"{v} °C")
                    self.append_log(f"{topic}: {data}")
                elif "hum" in t or "humidity" in t or "sensor" in t:
                    v = extract_numeric_from_payload(data)
                    if v is not None:
                        self.hum_val.set(f"{v} %")
                    self.append_log(f"{topic}: {data}")
                else:
                    # generic health update
                    self.append_log(f"{topic}: {data}")
                # update mqtt status
                self.mqtt_status.set(f"MQTT last: {topic}")

        # reschedule
        if not _stop_event.is_set():
            self.after(UI_UPDATE_INTERVAL_MS, self.consume_queues)

    def append_log(self, text):
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"[{timestamp}] {text}\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def on_close(self):
        logging.info("Shutdown requested by UI")
        _stop_event.set()
        # short delay to let threads exit gracefully
        try:
            self.after(200, self.destroy)
        except Exception:
            self.destroy()

def extract_numeric_from_payload(payload):
    """
    Try to find a numeric value in JSON or string payloads.
    """
    try:
        if isinstance(payload, dict):
            for k in ("value", "temp", "temperature", "t"):
                if k in payload:
                    try:
                        return float(payload[k])
                    except Exception:
                        pass
            # fallback: search all values
            for v in payload.values():
                try:
                    return float(v)
                except Exception:
                    pass
        else:
            # try parse simple JSON numeric or raw number
            s = str(payload)
            try:
                j = json.loads(s)
                if isinstance(j, (int, float)):
                    return float(j)
                if isinstance(j, dict):
                    return extract_numeric_from_payload(j)
            except Exception:
                pass
            # fallback: extract first number in text
            import re
            m = re.search(r"(-?\d+(\.\d+)?)", s)
            if m:
                return float(m.group(1))
    except Exception:
        pass
    return None

# -------- START / STOP helpers ----------
def start_background_tasks():
    # start video thread
    vt = threading.Thread(target=video_reader, args=(RTSP_URL,), daemon=True)
    vt.start()
    # start mqtt thread
    mt = threading.Thread(target=mqtt_thread, daemon=True)
    mt.start()
    return [vt, mt]

def install_signal_handlers(app):
    def handler(signum, frame):
        logging.info("Signal received, shutting down: %s", signum)
        _stop_event.set()
        try:
            app.destroy()
        except Exception:
            pass
    signal.signal(signal.SIGINT, handler)
    signal.signal(signal.SIGTERM, handler)

# -------- MAIN ----------
def main():
    app = Dashboard()
    install_signal_handlers(app)
    threads = start_background_tasks()
    try:
        app.mainloop()
    finally:
        _stop_event.set()
        # wait a little for threads to exit
        time.sleep(0.3)
        logging.info("Dashboard stopped")

if __name__ == "__main__":
    main()
