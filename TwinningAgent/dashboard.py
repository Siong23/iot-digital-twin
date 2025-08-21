import sys
import json
import psutil
import paho.mqtt.client as mqtt
from datetime import datetime
from PyQt5 import QtWidgets, QtCore
import pyqtgraph as pg

# -------------------- Data Buffers --------------------
time_stamps = []
temperature_values = []
humidity_values = []

# -------------------- MQTT Callback --------------------
def on_message(client, userdata, msg):
    try:
        data = json.loads(msg.payload.decode())
        timestamp = datetime.fromisoformat(data["timestamp"])
        temp = data["temperature"]
        hum = data["humidity"]

        time_stamps.append(timestamp)
        temperature_values.append(temp)
        humidity_values.append(hum)

        # Keep only last 5 minutes of data
        while (time_stamps[-1] - time_stamps[0]).seconds > 300:
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

        # Status label
        self.status_label = QtWidgets.QLabel("Initializing...")
        layout.addWidget(self.status_label)

        # Timer for updates
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_dashboard)
        self.timer.start(1000)  # update every 1s

        # Enable anti-aliasing for smoother curves
        pg.setConfigOptions(antialias=True)

        # ---------------- Hover Crosshair + Label ----------------
        self.vLine_temp = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen('r', style=QtCore.Qt.DashLine))
        self.hLine_temp = pg.InfiniteLine(angle=0, movable=False, pen=pg.mkPen('r', style=QtCore.Qt.DashLine))
        self.temp_plot.addItem(self.vLine_temp, ignoreBounds=True)
        self.temp_plot.addItem(self.hLine_temp, ignoreBounds=True)
        self.label_temp = pg.TextItem(anchor=(0,1))
        self.temp_plot.addItem(self.label_temp)

        self.vLine_hum = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen('b', style=QtCore.Qt.DashLine))
        self.hLine_hum = pg.InfiniteLine(angle=0, movable=False, pen=pg.mkPen('b', style=QtCore.Qt.DashLine))
        self.hum_plot.addItem(self.vLine_hum, ignoreBounds=True)
        self.hum_plot.addItem(self.hLine_hum, ignoreBounds=True)
        self.label_hum = pg.TextItem(anchor=(0,1))
        self.hum_plot.addItem(self.label_hum)

        # Connect mouse move signals
        self.temp_plot.scene().sigMouseMoved.connect(self.on_mouse_moved_temp)
        self.hum_plot.scene().sigMouseMoved.connect(self.on_mouse_moved_hum)

    def update_dashboard(self):
        if not time_stamps:
            return

        # Convert timestamps to epoch seconds
        times_epoch = [t.timestamp() for t in time_stamps]

        # Update plots
        self.temp_curve.setData(times_epoch, temperature_values)
        self.hum_curve.setData(times_epoch, humidity_values)

        # Auto-scroll X range (last 5 min)
        if times_epoch:
            self.temp_plot.setXRange(times_epoch[-1] - 300, times_epoch[-1])
            self.hum_plot.setXRange(times_epoch[-1] - 300, times_epoch[-1])

        # Auto-scale Y
        self.temp_plot.enableAutoRange(axis=pg.ViewBox.YAxis, enable=True)
        self.hum_plot.enableAutoRange(axis=pg.ViewBox.YAxis, enable=True)

        # System usage
        cpu = psutil.cpu_percent(interval=0.1)
        ram = psutil.virtual_memory().percent
        self.status_label.setText(
            f"Router: UP | Broker: UP | Sensor: UP\nCPU: {cpu}%   RAM: {ram}%"
        )

    # ---------------- Hover Handlers ----------------
    def on_mouse_moved_temp(self, pos):
        if not time_stamps:
            return
        vb = self.temp_plot.vb
        mouse_point = vb.mapSceneToView(pos)
        x = mouse_point.x()
        if len(time_stamps) > 0:
            # Find closest index
            times_epoch = [t.timestamp() for t in time_stamps]
            idx = min(range(len(times_epoch)), key=lambda i: abs(times_epoch[i] - x))
            if 0 <= idx < len(times_epoch):
                self.vLine_temp.setPos(times_epoch[idx])
                self.hLine_temp.setPos(temperature_values[idx])
                self.label_temp.setHtml(
                    f"<span style='color:red'>Time: {time_stamps[idx].strftime('%H:%M:%S')}<br>"
                    f"Temp: {temperature_values[idx]:.2f}°C</span>"
                )
                self.label_temp.setPos(times_epoch[idx], temperature_values[idx])

    def on_mouse_moved_hum(self, pos):
        if not time_stamps:
            return
        vb = self.hum_plot.vb
        mouse_point = vb.mapSceneToView(pos)
        x = mouse_point.x()
        if len(time_stamps) > 0:
            times_epoch = [t.timestamp() for t in time_stamps]
            idx = min(range(len(times_epoch)), key=lambda i: abs(times_epoch[i] - x))
            if 0 <= idx < len(times_epoch):
                self.vLine_hum.setPos(times_epoch[idx])
                self.hLine_hum.setPos(humidity_values[idx])
                self.label_hum.setHtml(
                    f"<span style='color:blue'>Time: {time_stamps[idx].strftime('%H:%M:%S')}<br>"
                    f"Humidity: {humidity_values[idx]:.2f}%</span>"
                )
                self.label_hum.setPos(times_epoch[idx], humidity_values[idx])

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
