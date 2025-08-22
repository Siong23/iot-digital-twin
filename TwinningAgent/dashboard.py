#!/usr/bin/env python3
# dashboard.py
# Full IoT Consumer dashboard: RTSP video + temperature (red) + humidity (yellow)
# Hardened for long runs: MQTT auto-reconnect, clean shutdown, bounded buffers, video watchdog.

import os
import sys
import json
import time
import psutil
import paho.mqtt.client as mqtt
import cv2
from datetime import datetime, timedelta

# -------- Optional: use software OpenGL to avoid GPU/driver issues on some boxes --------
# os.environ.setdefault("QT_OPENGL", "software")

# Make Qt pick up system plugins (try common paths)
_possible_qt_paths = [
    "/usr/lib/x86_64-linux-gnu/qt5/plugins/platforms",
    "/usr/lib/qt5/plugins/platforms",
    "/usr/lib64/qt5/plugins/platforms",
    "/usr/local/lib/qt5/plugins/platforms",
]
for _p in _possible_qt_paths:
    if os.path.isdir(_p):
        os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = _p
        break
# Force XCB platform by default (works for most X11 setups)
os.environ.setdefault("QT_QPA_PLATFORM", "xcb")

from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QPushButton, QHBoxLayout, QVBoxLayout
from PyQt5 import QtCore, QtGui
import pyqtgraph as pg

# ---------------- CONFIG ----------------
STREAM_URL = "rtsp://192.168.20.2:8554/proxied"
MQTT_BROKER = "192.168.20.2"
MQTT_USER = "admin"
MQTT_PASS = "admin123"
MQTT_TOPIC = "sensors/digital/data"
MQTT_PORT = 1883
MQTT_KEEPALIVE = 30  # seconds

# Data buffer limits
HISTORY_SECONDS = 300        # 5 minutes
MAX_POINTS = 2000            # hard cap to prevent creep

# Hover timeout
HOVER_HIDE_SECONDS = 5.0

# No-frame watchdog (video)
NO_FRAME_TIMEOUT_S = 10

# -------------------- Data Buffers --------------------
time_stamps = []
temperature_values = []
humidity_values = []

# -------------------- MQTT Callbacks --------------------
class MqttState:
    connected = False
mqtt_state = MqttState()

def trim_buffers():
    """Enforce time-based (5 min) and count-based (MAX_POINTS) limits."""
    # Time-based
    if len(time_stamps) > 1:
        while time_stamps and (time_stamps[-1] - time_stamps[0]).total_seconds() > HISTORY_SECONDS:
            time_stamps.pop(0); temperature_values.pop(0); humidity_values.pop(0)
    # Count-based
    excess = len(time_stamps) - MAX_POINTS
    if excess > 0:
        del time_stamps[:excess]; del temperature_values[:excess]; del humidity_values[:excess]

def on_connect(client, userdata, flags, rc):
    mqtt_state.connected = (rc == 0)
    if mqtt_state.connected:
        client.subscribe(MQTT_TOPIC, qos=0)

def on_disconnect(client, userdata, rc):
    mqtt_state.connected = False
    # paho will auto-reconnect because we use loop_start + reconnect_delay_set

def on_message(client, userdata, msg):
    try:
        data = json.loads(msg.payload.decode())
        # guard: tolerate timestamp with/without fractional seconds
        ts_raw = data.get("timestamp")
        if isinstance(ts_raw, str):
            # fromisoformat handles "YYYY-mm-ddTHH:MM:SS[.ffffff]"
            timestamp = datetime.fromisoformat(ts_raw)
        else:
            timestamp = datetime.utcnow()

        temp = float(data["temperature"])
        hum = float(data["humidity"])

        time_stamps.append(timestamp)
        temperature_values.append(temp)
        humidity_values.append(hum)
        trim_buffers()

    except Exception as e:
        print("Error parsing MQTT message:", e)

# -------------------- Video Thread --------------------
class VideoThread(QtCore.QThread):
    frame_received = QtCore.pyqtSignal(QtGui.QImage)
    status_changed = QtCore.pyqtSignal(bool)

    def __init__(self, url, parent=None):
        super().__init__(parent)
        self.url = url
        self.running = True
        self._cap = None
        self._last_frame_ts = 0.0

    def run(self):
        while self.running:
            try:
                self._cap = cv2.VideoCapture(self.url)
                opened = self._cap.isOpened()
                self.status_changed.emit(opened)
                if not opened:
                    self._safe_release()
                    time.sleep(2)
                    continue

                self._last_frame_ts = time.time()
                while self.running and self._cap.isOpened():
                    ret, frame = self._cap.read()
                    if not ret or frame is None:
                        self.status_changed.emit(False)
                        break

                    self._last_frame_ts = time.time()

                    # Convert BGR -> RGB
                    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    h, w, ch = rgb.shape
                    bytes_per_line = ch * w
                    qt_image = QtGui.QImage(rgb.data, w, h, bytes_per_line, QtGui.QImage.Format_RGB888)
                    self.frame_received.emit(qt_image.copy())
                    self.status_changed.emit(True)

                    # Watchdog: if no frame for too long, restart capture
                    if time.time() - self._last_frame_ts > NO_FRAME_TIMEOUT_S:
                        break

                    QtCore.QThread.msleep(20)

                self._safe_release()
                time.sleep(1)
            except Exception as e:
                print("VideoThread error:", e)
                self.status_changed.emit(False)
                self._safe_release()
                time.sleep(2)

    def stop(self):
        self.running = False
        self._safe_release()
        try:
            self.wait(timeout=2000)
        except Exception:
            pass

    def _safe_release(self):
        try:
            if self._cap:
                try:
                    self._cap.release()
                except Exception:
                    pass
        finally:
            self._cap = None

# -------------------- Custom Time Axis --------------------
class TimeAxisItem(pg.AxisItem):
    """X axis shows clock time HH:MM:SS"""
    def tickStrings(self, values, scale, spacing):
        return [datetime.fromtimestamp(v).strftime("%H:%M:%S") for v in values]

# -------------------- Dashboard Widget --------------------
class Dashboard(QWidget):
    def __init__(self, mqtt_client):
        super().__init__()
        self.setWindowTitle("Digital Twin IoT Dashboard")
        self.resize(1200, 720)
        self.mqtt_client = mqtt_client

        main_layout = QVBoxLayout(self)

        # Top row: video (left) and graphs (right)
        top_h = QHBoxLayout()
        main_layout.addLayout(top_h, stretch=6)

        # Video panel
        video_widget = QWidget()
        video_layout = QVBoxLayout(video_widget)
        video_layout.setContentsMargins(0,0,0,0)

        self.video_label = QLabel("Stream loading...")
        self.video_label.setAlignment(QtCore.Qt.AlignCenter)
        self.video_label.setMinimumSize(480, 360)
        self.video_label.setStyleSheet("background-color: black; color: white;")
        video_layout.addWidget(self.video_label)

        ctrl_row = QHBoxLayout()
        self.stream_status_label = QLabel("Stream: Unknown")
        ctrl_row.addWidget(self.stream_status_label)
        self.btn_toggle_stream = QPushButton("Pause")
        self.btn_toggle_stream.setCheckable(True)
        self.btn_toggle_stream.clicked.connect(self.toggle_stream)
        ctrl_row.addWidget(self.btn_toggle_stream)
        ctrl_row.addStretch()
        video_layout.addLayout(ctrl_row)

        top_h.addWidget(video_widget, stretch=5)

        # Right side: graphs
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0,0,0,0)

        self.graph_widget = pg.GraphicsLayoutWidget()
        right_layout.addWidget(self.graph_widget)

        # Temperature plot (top)
        self.temp_plot = self.graph_widget.addPlot(
            title="Temperature (°C)",
            axisItems={'bottom': TimeAxisItem(orientation='bottom')}
        )
        self.temp_plot.setLabel('left', 'Temperature (°C)', color='red')
        self.temp_plot.showGrid(x=True, y=True, alpha=0.3)
        self.temp_curve = self.temp_plot.plot(pen=pg.mkPen('r', width=2))

        # newest label under temp
        self.temp_latest_label = QLabel("Latest Temp: --")
        right_layout.addWidget(self.temp_latest_label)

        self.graph_widget.nextRow()

        # Humidity plot (bottom) - yellow/gold color
        self.hum_plot = self.graph_widget.addPlot(
            title="Humidity (%)",
            axisItems={'bottom': TimeAxisItem(orientation='bottom')}
        )
        self.hum_plot.setLabel('left', 'Humidity (%)', color='orange')
        self.hum_plot.showGrid(x=True, y=True, alpha=0.3)
        self.hum_curve = self.hum_plot.plot(pen=pg.mkPen(color=(255,215,0), width=2))

        # newest label under hum
        self.hum_latest_label = QLabel("Latest Humidity: --")
        right_layout.addWidget(self.hum_latest_label)

        top_h.addWidget(right_widget, stretch=5)

        # bottom: overall status
        self.status_label = QLabel("Initializing device statuses...")
        main_layout.addWidget(self.status_label, stretch=1)

        # Hover crosshairs and labels for temp
        self.vLine_temp = pg.InfiniteLine(angle=90, movable=False,
                                          pen=pg.mkPen('r', style=QtCore.Qt.DashLine))
        self.hLine_temp = pg.InfiniteLine(angle=0, movable=False,
                                          pen=pg.mkPen('r', style=QtCore.Qt.DashLine))
        self.label_temp = pg.TextItem(anchor=(0,1), border='w', fill=(30,30,30,200))
        self.vLine_temp.hide(); self.hLine_temp.hide(); self.label_temp.hide()
        self.temp_plot.addItem(self.vLine_temp, ignoreBounds=True)
        self.temp_plot.addItem(self.hLine_temp, ignoreBounds=True)
        self.temp_plot.addItem(self.label_temp)

        # Hover crosshairs and labels for hum
        self.vLine_hum = pg.InfiniteLine(angle=90, movable=False,
                                         pen=pg.mkPen(color=(255,215,0), style=QtCore.Qt.DashLine))
        self.hLine_hum = pg.InfiniteLine(angle=0, movable=False,
                                         pen=pg.mkPen(color=(255,215,0), style=QtCore.Qt.DashLine))
        self.label_hum = pg.TextItem(anchor=(0,1), border='w', fill=(30,30,30,200))
        self.vLine_hum.hide(); self.hLine_hum.hide(); self.label_hum.hide()
        self.hum_plot.addItem(self.vLine_hum, ignoreBounds=True)
        self.hum_plot.addItem(self.hLine_hum, ignoreBounds=True)
        self.hum_plot.addItem(self.label_hum)

        # Timer
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_dashboard)
        self.timer.start(1000)

        pg.setConfigOptions(antialias=True)

        # Mouse move signals
        self.temp_plot.scene().sigMouseMoved.connect(self.on_mouse_moved_temp)
        self.hum_plot.scene().sigMouseMoved.connect(self.on_mouse_moved_hum)

        self.last_mouse_time_temp = 0.0
        self.last_mouse_time_hum = 0.0

        # Video thread
        self.video_thread = VideoThread(STREAM_URL)
        self.video_thread.frame_received.connect(self.on_frame, QtCore.Qt.QueuedConnection)
        self.video_thread.status_changed.connect(self.on_stream_status, QtCore.Qt.QueuedConnection)
        self.video_thread.start()
        self.stream_paused = False

    def toggle_stream(self, checked):
        self.stream_paused = checked
        self.btn_toggle_stream.setText("Resume" if checked else "Pause")

    def on_frame(self, qimage):
        if self.stream_paused:
            return
        try:
            pix = QtGui.QPixmap.fromImage(qimage)
            pix = pix.scaled(self.video_label.size(), QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
            self.video_label.setPixmap(pix)
        except Exception:
            # Ignore intermittent paint errors
            pass

    def on_stream_status(self, up: bool):
        self.stream_status_label.setText("Stream: UP" if up else "Stream: DOWN")
        if not up:
            self.video_label.setText("Stream unavailable")
            self.video_label.setPixmap(QtGui.QPixmap())

    def update_dashboard(self):
        # MQTT/host status line
        cpu = psutil.cpu_percent(interval=0.05)
        ram = psutil.virtual_memory().percent
        mqtt_txt = "MQTT: UP" if mqtt_state.connected else "MQTT: DOWN (reconnecting)"
        self.status_label.setText(f"Router: UP | Broker: UP | Sensor: UP | {mqtt_txt}    CPU: {cpu}%   RAM: {ram}%")

        if not time_stamps:
            self.temp_latest_label.setText("Latest Temp: --")
            self.hum_latest_label.setText("Latest Humidity: --")
            return

        times_epoch = [t.timestamp() for t in time_stamps]

        # update curves
        self.temp_curve.setData(times_epoch, temperature_values)
        self.hum_curve.setData(times_epoch, humidity_values)

        # update newest-data labels
        newest_time = time_stamps[-1].strftime("%H:%M:%S")
        newest_temp = temperature_values[-1]
        newest_hum = humidity_values[-1]
        self.temp_latest_label.setText(f"Latest Temp: {newest_temp:.2f} °C    at {newest_time}")
        self.hum_latest_label.setText(f"Latest Humidity: {newest_hum:.2f}%    at {newest_time}")

        # auto-scroll if not hovering
        now_ts = time.time()
        if (now_ts - self.last_mouse_time_temp) > HOVER_HIDE_SECONDS and (now_ts - self.last_mouse_time_hum) > HOVER_HIDE_SECONDS:
            if times_epoch:
                self.temp_plot.setXRange(times_epoch[-1] - HISTORY_SECONDS, times_epoch[-1])
                self.hum_plot.setXRange(times_epoch[-1] - HISTORY_SECONDS, times_epoch[-1])

        # auto-range Ys
        self.temp_plot.enableAutoRange(axis=pg.ViewBox.YAxis, enable=True)
        self.hum_plot.enableAutoRange(axis=pg.ViewBox.YAxis, enable=True)

        # hide crosshair if timeout
        if (now_ts - self.last_mouse_time_temp) > HOVER_HIDE_SECONDS:
            self.vLine_temp.hide(); self.hLine_temp.hide(); self.label_temp.hide()
        if (now_ts - self.last_mouse_time_hum) > HOVER_HIDE_SECONDS:
            self.vLine_hum.hide(); self.hLine_hum.hide(); self.label_hum.hide()

    def on_mouse_moved_temp(self, pos):
        if not time_stamps: return
        vb = self.temp_plot.vb
        mouse_point = vb.mapSceneToView(pos)
        x = mouse_point.x()
        times_epoch = [t.timestamp() for t in time_stamps]
        idx = min(range(len(times_epoch)), key=lambda i: abs(times_epoch[i] - x))
        if 0 <= idx < len(times_epoch):
            self.last_mouse_time_temp = time.time()
            self.vLine_temp.setPos(times_epoch[idx]); self.hLine_temp.setPos(temperature_values[idx])
            self.vLine_temp.show(); self.hLine_temp.show()
            txt = f"<span style='color:red'>Time: {time_stamps[idx].strftime('%H:%M:%S')}<br>Temp: {temperature_values[idx]:.2f}°C</span>"
            self.label_temp.setHtml(txt)
            x_min, x_max = vb.viewRange()[0]; y_min, y_max = vb.viewRange()[1]
            x_margin = max(1.0, (x_max - x_min) * 0.05); y_margin = max(0.1, (y_max - y_min) * 0.05)
            label_x = min(max(times_epoch[idx], x_min + x_margin), x_max - x_margin)
            label_y = min(max(temperature_values[idx], y_min + y_margin), y_max - y_margin)
            self.label_temp.setPos(label_x, label_y); self.label_temp.show()

    def on_mouse_moved_hum(self, pos):
        if not time_stamps: return
        vb = self.hum_plot.vb
        mouse_point = vb.mapSceneToView(pos)
        x = mouse_point.x()
        times_epoch = [t.timestamp() for t in time_stamps]
        idx = min(range(len(times_epoch)), key=lambda i: abs(times_epoch[i] - x))
        if 0 <= idx < len(times_epoch):
            self.last_mouse_time_hum = time.time()
            self.vLine_hum.setPos(times_epoch[idx]); self.hLine_hum.setPos(humidity_values[idx])
            self.vLine_hum.show(); self.hLine_hum.show()
            txt = f"<span style='color:orange'>Time: {time_stamps[idx].strftime('%H:%M:%S')}<br>Humidity: {humidity_values[idx]:.2f}%</span>"
            self.label_hum.setHtml(txt)
            vb_x_min, vb_x_max = vb.viewRange()[0]; vb_y_min, vb_y_max = vb.viewRange()[1]
            x_margin = max(1.0, (vb_x_max - vb_x_min) * 0.05); y_margin = max(0.1, (vb_y_max - vb_y_min) * 0.05)
            label_x = min(max(times_epoch[idx], vb_x_min + x_margin), vb_x_max - x_margin)
            label_y = min(max(humidity_values[idx], vb_y_min + y_margin), vb_y_max - y_margin)
            self.label_hum.setPos(label_x, label_y); self.label_hum.show()

    def closeEvent(self, event):
        # Stop video thread
        try:
            self.video_thread.stop()
        except Exception:
            pass
        # Cleanly stop MQTT
        try:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
        except Exception:
            pass
        event.accept()

# -------------------- Main --------------------
def main():
    # Qt app
    app = QApplication(sys.argv)

    # MQTT client
    client = mqtt.Client()
    client.username_pw_set(MQTT_USER, MQTT_PASS)
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message
    # automatic reconnect backoff
    client.reconnect_delay_set(min_delay=1, max_delay=30)
    client.will_set("system/dashboard/status", payload="offline", qos=0, retain=False)

    # initial connect (non-blocking)
    try:
        client.connect(MQTT_BROKER, MQTT_PORT, keepalive=MQTT_KEEPALIVE)
    except Exception as e:
        print("Initial MQTT connect failed:", e)
    client.loop_start()

    dashboard = Dashboard(client)
    dashboard.show()

    rc = app.exec_()

    # Ensure cleanup if not already
    try:
        client.loop_stop()
        client.disconnect()
    except Exception:
        pass

    sys.exit(rc)

if __name__ == "__main__":
    main()
