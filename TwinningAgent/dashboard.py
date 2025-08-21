#!/usr/bin/env python3
import sys
import json
import psutil
import paho.mqtt.client as mqtt
from datetime import datetime, timedelta
from PyQt5 import QtWidgets, QtCore
import pyqtgraph as pg

# ------------------- Global Data Buffers -------------------
time_stamps = []
temperature_values = []
humidity_values = []

# ------------------- MQTT Client -------------------
BROKER_IP = "192.168.20.2"
BROKER_PORT = 1883
MQTT_USER = "admin"
MQTT_PASS = "admin123"
TOPIC = "sensors/digital/data"

def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode())
        ts = datetime.fromisoformat(payload["timestamp"])
        temperature = payload.get("temperature")
        humidity = payload.get("humidity")

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

# ------------------- Dashboard Class -------------------
class Dashboard(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("IoT Digital Twin Dashboard")
        self.resize(900, 700)

        layout = QtWidgets.QVBoxLayout(self)

        # Temperature graph
        self.temp_plot = pg.PlotWidget(title="Temperature (°C)")
        self.temp_plot.showGrid(x=True, y=True)
        self.temp_curve = self.temp_plot.plot(pen=pg.mkPen('r', width=2))
        layout.addWidget(self.temp_plot)

        # Humidity graph
        self.hum_plot = pg.PlotWidget(title="Humidity (%)")
        self.hum_plot.showGrid(x=True, y=True)
        self.hum_curve = self.hum_plot.plot(pen=pg.mkPen('b', width=2))
        layout.addWidget(self.hum_plot)

        # Status label
        self.status_label = QtWidgets.QLabel("Status: Initializing...")
        layout.addWidget(self.status_label)

        # Crosshair lines + labels
        self.vLine_temp = pg.InfiniteLine(angle=90, movable=False, pen="y")
        self.hLine_temp = pg.InfiniteLine(angle=0, movable=False, pen="r")
        self.temp_plot.addItem(self.vLine_temp, ignoreBounds=True)
        self.temp_plot.addItem(self.hLine_temp, ignoreBounds=True)
        self.label_temp = pg.TextItem(anchor=(0,1))
        self.temp_plot.addItem(self.label_temp)

        self.vLine_hum = pg.InfiniteLine(angle=90, movable=False, pen="y")
        self.hLine_hum = pg.InfiniteLine(angle=0, movable=False, pen="b")
        self.hum_plot.addItem(self.vLine_hum, ignoreBounds=True)
        self.hum_plot.addItem(self.hLine_hum, ignoreBounds=True)
        self.label_hum = pg.TextItem(anchor=(0,1))
        self.hum_plot.addItem(self.label_hum)

        # Hover tracking
        self.hover_active = False
        self.temp_plot.scene().sigMouseMoved.connect(self.on_mouse_moved_temp)
        self.hum_plot.scene().sigMouseMoved.connect(self.on_mouse_moved_hum)

        # Timer update
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_dashboard)
        self.timer.start(1000)

    # ------------------- Hover Handlers -------------------
    def on_mouse_moved_temp(self, pos):
        if self.temp_plot.sceneBoundingRect().contains(pos):
            self.hover_active = True
            self._update_crosshair_from_mouse(self.temp_plot, pos)

    def on_mouse_moved_hum(self, pos):
        if self.hum_plot.sceneBoundingRect().contains(pos):
            self.hover_active = True
            self._update_crosshair_from_mouse(self.hum_plot, pos)

    def _update_crosshair_from_mouse(self, plot, pos):
        vb = plot.plotItem.vb
        mousePoint = vb.mapSceneToView(pos)
        if not time_stamps:
            return
        times_epoch = [t.timestamp() for t in time_stamps]
        idx = min(range(len(times_epoch)), key=lambda i: abs(times_epoch[i] - mousePoint.x()))
        self._set_crosshair(idx)

    # ------------------- Auto Update -------------------
    def update_dashboard(self):
        if not time_stamps:
            return
        times_epoch = [t.timestamp() for t in time_stamps]

        self.temp_curve.setData(times_epoch, temperature_values)
        self.hum_curve.setData(times_epoch, humidity_values)

        # Auto-scroll X axis
        self.temp_plot.setXRange(times_epoch[-1] - 300, times_epoch[-1])
        self.hum_plot.setXRange(times_epoch[-1] - 300, times_epoch[-1])

        # Lock to 5th newest if not hovering
        if not self.hover_active:
            idx = max(0, len(time_stamps) - 5)
            self._set_crosshair(idx)

        # Update system status
        cpu = psutil.cpu_percent(interval=0.1)
        ram = psutil.virtual_memory().percent
        self.status_label.setText(
            f"Router: UP | Broker: UP | Sensor: UP\nCPU: {cpu}%   RAM: {ram}%"
        )
        # Reset hover flag each cycle
        self.hover_active = False

    # ------------------- Crosshair Drawer -------------------
    def _set_crosshair(self, idx):
        ts_epoch = time_stamps[idx].timestamp()

        # Temp
        self.vLine_temp.setPos(ts_epoch)
        self.hLine_temp.setPos(temperature_values[idx])
        anchor_y = 0 if temperature_values[idx] < (max(temperature_values) + min(temperature_values)) / 2 else 1
        self.label_temp.setAnchor((0, anchor_y))
        self.label_temp.setHtml(
            f"<span style='color:red'>Time: {time_stamps[idx].strftime('%H:%M:%S')}<br>"
            f"Temp: {temperature_values[idx]:.2f}°C</span>"
        )
        self.label_temp.setPos(ts_epoch, temperature_values[idx])

        # Humidity
        self.vLine_hum.setPos(ts_epoch)
        self.hLine_hum.setPos(humidity_values[idx])
        anchor_y = 0 if humidity_values[idx] < (max(humidity_values) + min(humidity_values)) / 2 else 1
        self.label_hum.setAnchor((0, anchor_y))
        self.label_hum.setHtml(
            f"<span style='color:blue'>Time: {time_stamps[idx].strftime('%H:%M:%S')}<br>"
            f"Humidity: {humidity_values[idx]:.2f}%</span>"
        )
        self.label_hum.setPos(ts_epoch, humidity_values[idx])

# ------------------- Main -------------------
def main():
    client = mqtt.Client()
    client.username_pw_set(MQTT_USER, MQTT_PASS)
    client.on_message = on_message
    client.connect(BROKER_IP, BROKER_PORT, 60)
    client.subscribe(TOPIC)
    client.loop_start()

    app = QtWidgets.QApplication(sys.argv)
    dash = Dashboard()
    dash.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
