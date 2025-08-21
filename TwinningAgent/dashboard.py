#!/usr/bin/env python3
import sys
import json
import time
import psutil
import paho.mqtt.client as mqtt
import cv2
from datetime import datetime
from PyQt5 import QtWidgets, QtCore, QtGui
import pyqtgraph as pg

# ---------------- CONFIG ----------------
STREAM_URL = "rtsp://192.168.20.2:8554/proxied"   # <-- set your RTSP stream URL here
MQTT_BROKER = "192.168.20.2"
MQTT_USER = "admin"
MQTT_PASS = "admin123"
MQTT_TOPIC = "sensors/digital/data"

# -------------------- Data Buffers --------------------
time_stamps = []
temperature_values = []
humidity_values = []

# Hover settings
HOVER_HIDE_SECONDS = 2.0  # hide crosshair after this many seconds of no mouse movement

# -------------------- MQTT Callback --------------------
def on_message(client, userdata, msg):
    try:
        data = json.loads(msg.payload.decode())
        timestamp = datetime.fromisoformat(data["timestamp"])
        temp = float(data["temperature"])
        hum = float(data["humidity"])

        time_stamps.append(timestamp)
        temperature_values.append(temp)
        humidity_values.append(hum)

        # Keep only last 5 minutes of data
        while len(time_stamps) > 1 and (time_stamps[-1] - time_stamps[0]).total_seconds() > 300:
            time_stamps.pop(0)
            temperature_values.pop(0)
            humidity_values.pop(0)

    except Exception as e:
        print("Error parsing message:", e)

# -------------------- Video Thread --------------------
class VideoThread(QtCore.QThread):
    frame_received = QtCore.pyqtSignal(QtGui.QImage)
    status_changed = QtCore.pyqtSignal(bool)

    def __init__(self, url, parent=None):
        super().__init__(parent)
        self.url = url
        self.running = True
        self._cap = None

    def run(self):
        while self.running:
            try:
                # Try to open capture
                self._cap = cv2.VideoCapture(self.url)
                # sometimes you need transport option for rtsp; OpenCV supports 'rtsp' backend if compiled with FFmpeg/gstreamer
                opened = self._cap.isOpened()
                self.status_changed.emit(opened)
                if not opened:
                    # wait and retry
                    self._safe_release()
                    time.sleep(2)
                    continue

                # read loop
                while self.running and self._cap.isOpened():
                    ret, frame = self._cap.read()
                    if not ret or frame is None:
                        self.status_changed.emit(False)
                        # break to reopen
                        break
                    # Convert BGR -> RGB
                    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    h, w, ch = rgb.shape
                    bytes_per_line = ch * w
                    qt_image = QtGui.QImage(rgb.data, w, h, bytes_per_line, QtGui.QImage.Format_RGB888)
                    scaled = qt_image.copy()  # copy to safe memory
                    self.frame_received.emit(scaled)
                    self.status_changed.emit(True)
                    # small sleep to avoid hogging CPU (playback sync is controlled by frame read rate)
                    # if you want exact FPS, use time.sleep(1/fps)
                    QtCore.QThread.msleep(20)
                # release and retry
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
        self.wait(timeout=2000)

    def _safe_release(self):
        try:
            if self._cap:
                try:
                    self._cap.release()
                except Exception:
                    pass
            self._cap = None
        finally:
            pass

# -------------------- Custom Time Axis --------------------
class TimeAxisItem(pg.AxisItem):
    """Custom X-axis to show clock time instead of seconds."""
    def tickStrings(self, values, scale, spacing):
        return [datetime.fromtimestamp(v).strftime("%H:%M:%S") for v in values]

# -------------------- Dashboard --------------------
class Dashboard(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Digital Twin IoT Dashboard")
        self.resize(1200, 700)

        main_layout = QtWidgets.QVBoxLayout(self)

        # Top area: horizontal split -> left video, right graphs
        top_h = QtWidgets.QHBoxLayout()
        main_layout.addLayout(top_h, stretch=6)

        # --- Video panel (left) ---
        video_widget = QtWidgets.QWidget()
        video_layout = QtWidgets.QVBoxLayout(video_widget)
        video_layout.setContentsMargins(0,0,0,0)
        self.video_label = QtWidgets.QLabel("Stream loading...")
        self.video_label.setAlignment(QtCore.Qt.AlignCenter)
        self.video_label.setMinimumSize(480, 360)
        self.video_label.setStyleSheet("background-color: black; color: white;")
        video_layout.addWidget(self.video_label)

        # Stream status label & controls
        ctrl_row = QtWidgets.QHBoxLayout()
        self.stream_status_label = QtWidgets.QLabel("Stream: Unknown")
        ctrl_row.addWidget(self.stream_status_label)
        self.btn_toggle_stream = QtWidgets.QPushButton("Pause")
        self.btn_toggle_stream.setCheckable(True)
        self.btn_toggle_stream.clicked.connect(self.toggle_stream)
        ctrl_row.addWidget(self.btn_toggle_stream)
        video_layout.addLayout(ctrl_row)

        top_h.addWidget(video_widget, stretch=5)

        # --- Right side: graphs ---
        right_widget = QtWidgets.QWidget()
        right_layout = QtWidgets.QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0,0,0,0)

        self.graph_widget = pg.GraphicsLayoutWidget()
        right_layout.addWidget(self.graph_widget)

        # Temperature plot (top)
        self.temp_plot = self.graph_widget.addPlot(
            title="Temperature (°C)", axisItems={'bottom': TimeAxisItem(orientation='bottom')}
        )
        self.temp_plot.setLabel('left', 'Temperature (°C)', color='red')
        self.temp_plot.showGrid(x=True, y=True, alpha=0.3)
        self.temp_curve = self.temp_plot.plot(pen=pg.mkPen('r', width=2))

        # Newest label under temp
        self.temp_latest_label = QtWidgets.QLabel("Latest Temp: --")
        right_layout.addWidget(self.temp_latest_label)

        self.graph_widget.nextRow()

        # Humidity plot (bottom)
        self.hum_plot = self.graph_widget.addPlot(
            title="Humidity (%)", axisItems={'bottom': TimeAxisItem(orientation='bottom')}
        )
        self.hum_plot.setLabel('left', 'Humidity (%)', color='orange')
        self.hum_plot.showGrid(x=True, y=True, alpha=0.3)
        # yellow color - use RGB gold-ish
        self.hum_curve = self.hum_plot.plot(pen=pg.mkPen(color=(255,215,0), width=2))

        # Newest label under hum
        self.hum_latest_label = QtWidgets.QLabel("Latest Humidity: --")
        right_layout.addWidget(self.hum_latest_label)

        top_h.addWidget(right_widget, stretch=5)

        # Bottom area: status + usage
        self.status_label = QtWidgets.QLabel("Initializing device statuses...")
        main_layout.addWidget(self.status_label, stretch=1)

        # Hover crosshairs (temp)
        self.vLine_temp = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen('r', style=QtCore.Qt.DashLine))
        self.hLine_temp = pg.InfiniteLine(angle=0, movable=False, pen=pg.mkPen('r', style=QtCore.Qt.DashLine))
        self.label_temp = pg.TextItem(anchor=(0,1), border='w', fill=(30,30,30,200))
        self.vLine_temp.hide(); self.hLine_temp.hide(); self.label_temp.hide()
        self.temp_plot.addItem(self.vLine_temp, ignoreBounds=True)
        self.temp_plot.addItem(self.hLine_temp, ignoreBounds=True)
        self.temp_plot.addItem(self.label_temp)

        # Hover crosshairs (hum)
        self.vLine_hum = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen(color=(255,215,0), style=QtCore.Qt.DashLine))
        self.hLine_hum = pg.InfiniteLine(angle=0, movable=False, pen=pg.mkPen(color=(255,215,0), style=QtCore.Qt.DashLine))
        self.label_hum = pg.TextItem(anchor=(0,1), border='w', fill=(30,30,30,200))
        self.vLine_hum.hide(); self.hLine_hum.hide(); self.label_hum.hide()
        self.hum_plot.addItem(self.vLine_hum, ignoreBounds=True)
        self.hum_plot.addItem(self.hLine_hum, ignoreBounds=True)
        self.hum_plot.addItem(self.label_hum)

        # Timer for updates
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_dashboard)
        self.timer.start(1000)  # update every 1s

        # Anti-alias
        pg.setConfigOptions(antialias=True)

        # Connect mouse move signals
        self.temp_plot.scene().sigMouseMoved.connect(self.on_mouse_moved_temp)
        self.hum_plot.scene().sigMouseMoved.connect(self.on_mouse_moved_hum)

        self.last_mouse_time_temp = 0.0
        self.last_mouse_time_hum = 0.0

        # Video thread
        self.video_thread = VideoThread(STREAM_URL)
        self.video_thread.frame_received.connect(self.on_frame)
        self.video_thread.status_changed.connect(self.on_stream_status)
        self.video_thread.start()
        self.stream_paused = False

    def toggle_stream(self, checked):
        # Pause/resume the thread’s frame updates by ignoring updates in on_frame
        self.stream_paused = checked
        self.btn_toggle_stream.setText("Resume" if checked else "Pause")

    def on_frame(self, qimage):
        if self.stream_paused:
            return
        # scale pixmap to label size while keeping aspect ratio
        pix = QtGui.QPixmap.fromImage(qimage)
        pix = pix.scaled(self.video_label.size(), QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
        self.video_label.setPixmap(pix)

    def on_stream_status(self, up: bool):
        self.stream_status_label.setText("Stream: UP" if up else "Stream: DOWN")
        if not up:
            # show placeholder
            self.video_label.setText("Stream unavailable")
            # optionally clear pixmap
            self.video_label.setPixmap(QtGui.QPixmap())

    # ---------------- UI Update ----------------
    def update_dashboard(self):
        if not time_stamps:
            self.temp_latest_label.setText("Latest Temp: --")
            self.hum_latest_label.setText("Latest Humidity: --")
            return

        # Convert timestamps to epoch seconds
        times_epoch = [t.timestamp() for t in time_stamps]

        # Update plots data
        self.temp_curve.setData(times_epoch, temperature_values)
        self.hum_curve.setData(times_epoch, humidity_values)

        # Update newest-data labels (only newest)
        newest_time = time_stamps[-1].strftime("%H:%M:%S")
        newest_temp = temperature_values[-1]
        newest_hum = humidity_values[-1]
        self.temp_latest_label.setText(f"Latest Temp: {newest_temp:.2f} °C    at {newest_time}")
        self.hum_latest_label.setText(f"Latest Humidity: {newest_hum:.2f}%    at {newest_time}")

        # Auto-scroll X range (last 5 min) when not hovering
        now_ts = time.time()
        if (now_ts - self.last_mouse_time_temp) > HOVER_HIDE_SECONDS and (now_ts - self.last_mouse_time_hum) > HOVER_HIDE_SECONDS:
            if times_epoch:
                self.temp_plot.setXRange(times_epoch[-1] - 300, times_epoch[-1])
                self.hum_plot.setXRange(times_epoch[-1] - 300, times_epoch[-1])

        # Auto-scale Y when not hovering
        self.temp_plot.enableAutoRange(axis=pg.ViewBox.YAxis, enable=True)
        self.hum_plot.enableAutoRange(axis=pg.ViewBox.YAxis, enable=True)

        # Hide crosshairs/labels if hover timeout passed
        if (now_ts - self.last_mouse_time_temp) > HOVER_HIDE_SECONDS:
            self.vLine_temp.hide(); self.hLine_temp.hide(); self.label_temp.hide()
        if (now_ts - self.last_mouse_time_hum) > HOVER_HIDE_SECONDS:
            self.vLine_hum.hide(); self.hLine_hum.hide(); self.label_hum.hide()

        # System usage (this machine)
        cpu = psutil.cpu_percent(interval=0.1)
        ram = psutil.virtual_memory().percent
        self.status_label.setText(
            f"Router: UP | Broker: UP | Sensor: UP    CPU: {cpu}%   RAM: {ram}%"
        )

    # ---------------- Hover Handlers ----------------
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
            # clamp label
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
        # stop video thread cleanly
        try:
            self.video_thread.stop()
        except Exception:
            pass
        event.accept()

# -------------------- Main --------------------
def main():
    app = QtWidgets.QApplication(sys.argv)
    dashboard = Dashboard()
    dashboard.show()

    client = mqtt.Client()
    client.username_pw_set(MQTT_USER, MQTT_PASS)
    client.on_message = on_message
    client.connect(MQTT_BROKER, 1883, 60)
    client.subscribe(MQTT_TOPIC)
    client.loop_start()

    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
