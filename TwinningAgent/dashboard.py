#!/usr/bin/env python3
import sys
import json
import time
import psutil
import paho.mqtt.client as mqtt
from datetime import datetime
from PyQt5 import QtWidgets, QtCore, QtGui
import pyqtgraph as pg

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
        # ensure timestamp is parseable (ISO format expected)
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
        self.resize(1100, 650)

        layout = QtWidgets.QVBoxLayout(self)

        # Graph area
        self.graph_widget = pg.GraphicsLayoutWidget()
        layout.addWidget(self.graph_widget)

        # ---------------- Temperature Plot ----------------
        self.temp_plot = self.graph_widget.addPlot(
            title="Temperature (°C)", axisItems={'bottom': TimeAxisItem(orientation='bottom')}
        )
        self.temp_plot.setLabel('left', 'Temperature (°C)', color='red')
        self.temp_plot.showGrid(x=True, y=True, alpha=0.3)
        self.temp_curve = self.temp_plot.plot(
            pen=pg.mkPen('r', width=2),
            name="Temperature"
        )

        # Crosshair/tooltip for temp
        self.vLine_temp = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen('r', style=QtCore.Qt.DashLine))
        self.hLine_temp = pg.InfiniteLine(angle=0, movable=False, pen=pg.mkPen('r', style=QtCore.Qt.DashLine))
        self.label_temp = pg.TextItem(anchor=(0,1), border='w', fill=(30,30,30,200))
        # start hidden
        self.vLine_temp.hide()
        self.hLine_temp.hide()
        self.label_temp.hide()
        self.temp_plot.addItem(self.vLine_temp, ignoreBounds=True)
        self.temp_plot.addItem(self.hLine_temp, ignoreBounds=True)
        self.temp_plot.addItem(self.label_temp)

        # ---------------- Humidity Plot ----------------
        self.graph_widget.nextRow()
        self.hum_plot = self.graph_widget.addPlot(
            title="Humidity (%)", axisItems={'bottom': TimeAxisItem(orientation='bottom')}
        )
        self.hum_plot.setLabel('left', 'Humidity (%)', color='blue')
        self.hum_plot.showGrid(x=True, y=True, alpha=0.3)
        self.hum_curve = self.hum_plot.plot(
            pen=pg.mkPen('b', width=2),
            name="Humidity"
        )

        # Crosshair/tooltip for hum
        self.vLine_hum = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen('b', style=QtCore.Qt.DashLine))
        self.hLine_hum = pg.InfiniteLine(angle=0, movable=False, pen=pg.mkPen('b', style=QtCore.Qt.DashLine))
        self.label_hum = pg.TextItem(anchor=(0,1), border='w', fill=(30,30,30,200))
        self.vLine_hum.hide()
        self.hLine_hum.hide()
        self.label_hum.hide()
        self.hum_plot.addItem(self.vLine_hum, ignoreBounds=True)
        self.hum_plot.addItem(self.hLine_hum, ignoreBounds=True)
        self.hum_plot.addItem(self.label_hum)

        # Status + usage label
        self.status_label = QtWidgets.QLabel("Initializing...")
        layout.addWidget(self.status_label)

        # Timer for updates
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_dashboard)
        self.timer.start(1000)  # update every 1s

        # Enable anti-aliasing for smoother curves
        pg.setConfigOptions(antialias=True)

        # Connect mouse move signals for hover detection
        self.temp_plot.scene().sigMouseMoved.connect(self.on_mouse_moved_temp)
        self.hum_plot.scene().sigMouseMoved.connect(self.on_mouse_moved_hum)

        # Track last hover times (seconds since epoch)
        self.last_mouse_time_temp = 0.0
        self.last_mouse_time_hum = 0.0

        # Ensure view-resize hooks (so we can clamp labels)
        def update_temp_view():
            pass
        self.temp_plot.vb.sigResized.connect(update_temp_view)
        self.hum_plot.vb.sigResized.connect(update_temp_view)

    # ---------------- UI Update ----------------
    def update_dashboard(self):
        if not time_stamps:
            return

        # Convert timestamps to epoch seconds
        times_epoch = [t.timestamp() for t in time_stamps]

        # Update plots data
        self.temp_curve.setData(times_epoch, temperature_values)
        self.hum_curve.setData(times_epoch, humidity_values)

        # Auto-scroll X range (last 5 min) if not hovering recently
        now_ts = time.time()
        # if neither hovered recently, we auto-follow newest
        if (now_ts - self.last_mouse_time_temp) > HOVER_HIDE_SECONDS and (now_ts - self.last_mouse_time_hum) > HOVER_HIDE_SECONDS:
            if times_epoch:
                self.temp_plot.setXRange(times_epoch[-1] - 300, times_epoch[-1])
                self.hum_plot.setXRange(times_epoch[-1] - 300, times_epoch[-1])

        # Auto-scale Y when not hovering (still okay to auto-range)
        self.temp_plot.enableAutoRange(axis=pg.ViewBox.YAxis, enable=True)
        self.hum_plot.enableAutoRange(axis=pg.ViewBox.YAxis, enable=True)

        # Hide crosshairs/labels if hover timeout passed
        if (now_ts - self.last_mouse_time_temp) > HOVER_HIDE_SECONDS:
            self.vLine_temp.hide()
            self.hLine_temp.hide()
            self.label_temp.hide()
        if (now_ts - self.last_mouse_time_hum) > HOVER_HIDE_SECONDS:
            self.vLine_hum.hide()
            self.hLine_hum.hide()
            self.label_hum.hide()

        # System usage (this machine)
        cpu = psutil.cpu_percent(interval=0.1)
        ram = psutil.virtual_memory().percent
        self.status_label.setText(
            f"Router: UP | Broker: UP | Sensor: UP\nCPU: {cpu}%   RAM: {ram}%"
        )

    # ---------------- Hover Handlers ----------------
    def on_mouse_moved_temp(self, pos):
        """Show crosshair and tooltip, clamp tooltip inside view."""
        if not time_stamps:
            return
        vb = self.temp_plot.vb
        mouse_point = vb.mapSceneToView(pos)
        x = mouse_point.x()
        times_epoch = [t.timestamp() for t in time_stamps]

        # find closest index
        idx = min(range(len(times_epoch)), key=lambda i: abs(times_epoch[i] - x))
        if 0 <= idx < len(times_epoch):
            # Update last mouse time
            self.last_mouse_time_temp = time.time()
            # Show lines
            self.vLine_temp.setPos(times_epoch[idx])
            self.hLine_temp.setPos(temperature_values[idx])
            self.vLine_temp.show()
            self.hLine_temp.show()

            # Prepare label text
            txt = f"<span style='color:red'>Time: {time_stamps[idx].strftime('%H:%M:%S')}<br>Temp: {temperature_values[idx]:.2f}°C</span>"
            self.label_temp.setHtml(txt)

            # Clamp label position inside view rect
            x_min, x_max = vb.viewRange()[0]
            y_min, y_max = vb.viewRange()[1]
            # margins (10% of range)
            x_margin = max(1.0, (x_max - x_min) * 0.05)
            y_margin = max(0.1, (y_max - y_min) * 0.05)
            label_x = min(max(times_epoch[idx], x_min + x_margin), x_max - x_margin)
            label_y = min(max(temperature_values[idx], y_min + y_margin), y_max - y_margin)
            self.label_temp.setPos(label_x, label_y)
            self.label_temp.show()

    def on_mouse_moved_hum(self, pos):
        """Show crosshair and tooltip for humidity, clamp tooltip inside view."""
        if not time_stamps:
            return
        vb = self.hum_plot.vb
        mouse_point = vb.mapSceneToView(pos)
        x = mouse_point.x()
        times_epoch = [t.timestamp() for t in time_stamps]

        idx = min(range(len(times_epoch)), key=lambda i: abs(times_epoch[i] - x))
        if 0 <= idx < len(times_epoch):
            self.last_mouse_time_hum = time.time()
            self.vLine_hum.setPos(times_epoch[idx])
            self.hLine_hum.setPos(humidity_values[idx])
            self.vLine_hum.show()
            self.hLine_hum.show()

            txt = f"<span style='color:blue'>Time: {time_stamps[idx].strftime('%H:%M:%S')}<br>Humidity: {humidity_values[idx]:.2f}%</span>"
            self.label_hum.setHtml(txt)

            vb_x_min, vb_x_max = vb.viewRange()[0]
            vb_y_min, vb_y_max = vb.viewRange()[1]
            x_margin = max(1.0, (vb_x_max - vb_x_min) * 0.05)
            y_margin = max(0.1, (vb_y_max - vb_y_min) * 0.05)
            label_x = min(max(times_epoch[idx], vb_x_min + x_margin), vb_x_max - x_margin)
            label_y = min(max(humidity_values[idx], vb_y_min + y_margin), vb_y_max - y_margin)
            self.label_hum.setPos(label_x, label_y)
            self.label_hum.show()

# -------------------- Main --------------------
def main():
    app = QtWidgets.QApplication(sys.argv)

    dashboard = Dashboard()
    dashboard.show()

    # MQTT client
    client = mqtt.Client()
    client.username_pw_set("admin", "admin123")
    client.on_message = on_message
    client.connect("192.168.20.2", 1883, 60)
    client.subscribe("sensors/digital/data")

    # Run MQTT loop in background thread
    client.loop_start()

    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
