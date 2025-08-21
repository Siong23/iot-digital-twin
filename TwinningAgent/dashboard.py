#!/usr/bin/env python3
import sys
import json
import time
import psutil
import paho.mqtt.client as mqtt
from datetime import datetime, timedelta
from PyQt5 import QtWidgets, QtCore
import pyqtgraph as pg

# ------------------- Config -------------------
BROKER_IP = "192.168.20.2"
BROKER_PORT = 1883
MQTT_USER = "admin"
MQTT_PASS = "admin123"
TOPIC = "sensors/digital/data"

# ------------------- Global Data Buffers -------------------
time_stamps = []          # list[datetime]
temperature_values = []   # list[float]
humidity_values = []      # list[float]

# ------------------- MQTT Callback -------------------
def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode())
        ts = datetime.fromisoformat(payload["timestamp"])
        temperature = float(payload.get("temperature", 0.0))
        humidity = float(payload.get("humidity", 0.0))

        time_stamps.append(ts)
        temperature_values.append(temperature)
        humidity_values.append(humidity)

        # Keep only last 5 minutes
        cutoff = datetime.now() - timedelta(minutes=5)
        while time_stamps and time_stamps[0] < cutoff:
            time_stamps.pop(0)
            temperature_values.pop(0)
            humidity_values.pop(0)
    except Exception as e:
        print("Error parsing MQTT:", e)

# ------------------- Time Axis -------------------
class TimeAxisItem(pg.AxisItem):
    """X-axis that shows human-readable times from epoch seconds."""
    def tickStrings(self, values, scale, spacing):
        return [datetime.fromtimestamp(v).strftime("%H:%M:%S") for v in values]

# ------------------- Dashboard -------------------
class Dashboard(QtWidgets.QWidget):
    HOVER_TIMEOUT = 1.0   # seconds after last mouse move to consider hover inactive
    WINDOW_SECONDS = 300  # 5 minutes

    def __init__(self):
        super().__init__()
        self.setWindowTitle("IoT Digital Twin Dashboard")
        self.resize(1000, 700)

        self.last_mouse_time = 0.0  # epoch secs for last mouse move
        self.mouse_pos = None

        layout = QtWidgets.QVBoxLayout(self)

        # Temperature plot using TimeAxisItem
        self.temp_plot = pg.PlotWidget(axisItems={'bottom': TimeAxisItem(orientation='bottom')})
        self.temp_plot.setTitle("Temperature (°C)")
        self.temp_plot.showGrid(x=True, y=True, alpha=0.3)
        self.temp_curve = self.temp_plot.plot(pen=pg.mkPen('r', width=2))
        layout.addWidget(self.temp_plot)

        # Humidity plot
        self.hum_plot = pg.PlotWidget(axisItems={'bottom': TimeAxisItem(orientation='bottom')})
        self.hum_plot.setTitle("Humidity (%)")
        self.hum_plot.showGrid(x=True, y=True, alpha=0.3)
        self.hum_curve = self.hum_plot.plot(pen=pg.mkPen('b', width=2))
        layout.addWidget(self.hum_plot)

        # Status label
        self.status_label = QtWidgets.QLabel("Status: Initializing...")
        layout.addWidget(self.status_label)

        # Crosshair lines + labels for temp
        self.vLine_temp = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen('y', width=1, style=QtCore.Qt.DashLine))
        self.hLine_temp = pg.InfiniteLine(angle=0, movable=False, pen=pg.mkPen('r', width=1, style=QtCore.Qt.DashLine))
        self.temp_plot.addItem(self.vLine_temp, ignoreBounds=True)
        self.temp_plot.addItem(self.hLine_temp, ignoreBounds=True)
        self.label_temp = pg.TextItem(anchor=(0,1))
        self.temp_plot.addItem(self.label_temp)

        # Crosshair lines + labels for hum
        self.vLine_hum = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen('y', width=1, style=QtCore.Qt.DashLine))
        self.hLine_hum = pg.InfiniteLine(angle=0, movable=False, pen=pg.mkPen('b', width=1, style=QtCore.Qt.DashLine))
        self.hum_plot.addItem(self.vLine_hum, ignoreBounds=True)
        self.hum_plot.addItem(self.hLine_hum, ignoreBounds=True)
        self.label_hum = pg.TextItem(anchor=(0,1))
        self.hum_plot.addItem(self.label_hum)

        # Connect mouse move on scenes (single handler)
        self.temp_plot.scene().sigMouseMoved.connect(self.on_mouse_moved)
        self.hum_plot.scene().sigMouseMoved.connect(self.on_mouse_moved)

        # Timer: update UI regularly
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_dashboard)
        self.timer.start(1000)  # 1 second tick

        pg.setConfigOptions(antialias=True)

    # ------------------- Mouse movement handler -------------------
    def on_mouse_moved(self, pos):
        # record last mouse time and position; the update loop will pick it up
        self.last_mouse_time = time.time()
        self.mouse_pos = pos

    # ------------------- Main update -------------------
    def update_dashboard(self):
        if not time_stamps:
            # nothing to plot yet
            self.status_label.setText("Waiting for data...")
            return

        # Prepare epoch times
        times_epoch = [t.timestamp() for t in time_stamps]

        # Update plot curves
        try:
            self.temp_curve.setData(times_epoch, temperature_values)
            self.hum_curve.setData(times_epoch, humidity_values)
        except Exception:
            # be robust to boxing errors
            pass

        # Auto-scroll X range to last WINDOW_SECONDS
        last = times_epoch[-1]
        start = max(times_epoch[0], last - self.WINDOW_SECONDS)
        self.temp_plot.setXRange(start, last, padding=0.01)
        self.hum_plot.setXRange(start, last, padding=0.01)

        # If mouse moved recently -> hover mode; otherwise auto-lock to 5th newest
        now = time.time()
        hover_active = (now - self.last_mouse_time) < self.HOVER_TIMEOUT and self.mouse_pos is not None

        if hover_active:
            # determine which plot the mouse is over and update crosshair accordingly
            # try temp_plot first; if not inside, try hum_plot
            if self._scene_contains(self.temp_plot, self.mouse_pos):
                self._crosshair_from_mouse(self.temp_plot, self.mouse_pos)
            elif self._scene_contains(self.hum_plot, self.mouse_pos):
                self._crosshair_from_mouse(self.hum_plot, self.mouse_pos)
            else:
                # fallback to 5th newest
                idx = max(0, len(time_stamps) - 5)
                self._set_crosshair(idx)
        else:
            idx = max(0, len(time_stamps) - 5)
            self._set_crosshair(idx)
            # clear mouse_pos so stale events don't linger
            self.mouse_pos = None

        # Update system usage text (host running IoT consumer)
        cpu = psutil.cpu_percent(interval=0.05)
        ram = psutil.virtual_memory().percent
        self.status_label.setText(f"Router: UP | Broker: UP | Sensor: UP    CPU: {cpu:.1f}%   RAM: {ram:.1f}%")

    # ------------------- Utilities -------------------
    def _scene_contains(self, plot_widget, scene_pos):
        """Return True if scene_pos is inside the plot_widget scene bounding rect."""
        try:
            return plot_widget.sceneBoundingRect().contains(scene_pos)
        except Exception:
            return False

    def _crosshair_from_mouse(self, plot_widget, scene_pos):
        """Map mouse to nearest data index and set crosshair on both plots."""
        try:
            vb = plot_widget.plotItem.vb
            mouse_point = vb.mapSceneToView(scene_pos)
            xval = mouse_point.x()
            if not time_stamps:
                return
            times_epoch = [t.timestamp() for t in time_stamps]
            # find nearest index
            idx = min(range(len(times_epoch)), key=lambda i: abs(times_epoch[i] - xval))
            self._set_crosshair(idx)
        except Exception:
            pass

    def _set_crosshair(self, idx):
        """Set crosshair and labels for both plots at given data index safely."""
        # guard indexes
        n = len(time_stamps)
        if n == 0:
            return
        if idx < 0:
            idx = 0
        if idx >= n:
            idx = n - 1

        ts_epoch = time_stamps[idx].timestamp()
        time_str = time_stamps[idx].strftime("%H:%M:%S")

        # TEMP crosshair + label
        y_temp = temperature_values[idx]
        self.vLine_temp.setPos(ts_epoch)
        self.hLine_temp.setPos(y_temp)

        # determine vertical anchor to avoid clipping
        try:
            yrange = self.temp_plot.viewRange()[1]  # (ymin, ymax)
            ymin, ymax = yrange[0], yrange[1]
            if ymax - ymin <= 0:
                anchor = (0, 1)
            else:
                frac = (y_temp - ymin) / (ymax - ymin)
                anchor = (0, 1) if frac > 0.8 else (0, 0)
        except Exception:
            anchor = (0, 1)
        self.label_temp.setAnchor(anchor)
        self.label_temp.setHtml(f"<div style='color:red'>Time: {time_str}<br>Temp: {y_temp:.2f}°C</div>")
        # shift label left if near right edge
        self._place_label_inside(self.temp_plot, self.label_temp, ts_epoch, y_temp)

        # HUM crosshair + label
        y_hum = humidity_values[idx]
        self.vLine_hum.setPos(ts_epoch)
        self.hLine_hum.setPos(y_hum)
        try:
            yrange_h = self.hum_plot.viewRange()[1]
            ymin_h, ymax_h = yrange_h[0], yrange_h[1]
            if ymax_h - ymin_h <= 0:
                anchor_h = (0, 1)
            else:
                frac_h = (y_hum - ymin_h) / (ymax_h - ymin_h)
                anchor_h = (0, 1) if frac_h > 0.8 else (0, 0)
        except Exception:
            anchor_h = (0, 1)
        self.label_hum.setAnchor(anchor_h)
        self.label_hum.setHtml(f"<div style='color:blue'>Time: {time_str}<br>Hum: {y_hum:.2f}%</div>")
        self._place_label_inside(self.hum_plot, self.label_hum, ts_epoch, y_hum)

    def _place_label_inside(self, plot_widget, label_item, x, y):
        """Place label so it remains visible inside the plot view (shift if necessary)."""
        try:
            vb = plot_widget.plotItem.vb
            view_rect = vb.viewRect()
            # adjust x if label at or beyond right edge (shift left by 5% of view width)
            if x > view_rect.right() - 0.01 * view_rect.width():
                x_adj = x - 0.05 * view_rect.width()
            else:
                x_adj = x
            # adjust y slightly to avoid overlap with crosshair
            label_item.setPos(x_adj, y)
        except Exception:
            label_item.setPos(x, y)

# ------------------- Main -------------------
def main():
    # MQTT setup
    client = mqtt.Client()
    client.username_pw_set(MQTT_USER, MQTT_PASS)
    client.on_message = on_message
    try:
        client.connect(BROKER_IP, BROKER_PORT, 60)
        client.subscribe(TOPIC)
        client.loop_start()
    except Exception as e:
        print("MQTT connect failed:", e)

    # Qt app
    app = QtWidgets.QApplication(sys.argv)
    dash = Dashboard()
    dash.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
