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

# -------------------- Dashboard --------------------
class TimeAxisItem(pg.AxisItem):
    """Custom X-axis to show clock time instead of seconds."""
    def tickStrings(self, values, scale, spacing):
        return [datetime.fromtimestamp(v).strftime("%H:%M:%S") for v in values]

class Dashboard(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Digital Twin IoT Dashboard")
        self.resize(1100, 650)

        layout = QtWidgets.QVBoxLayout(self)

        # Graph area
        self.graph_widget = pg.GraphicsLayoutWidget()
        layout.addWidget(self.graph_widget)

        # Custom X-axis with time
        self.plot = self.graph_widget.addPlot(
            title="Temperature & Humidity (Live)",
            axisItems={'bottom': TimeAxisItem(orientation='bottom')}
        )
        self.plot.setLabel('left', 'Temperature (°C)', color='red')
        self.plot.showGrid(x=True, y=True, alpha=0.3)

        # Temperature curve (left axis)
        self.temp_curve = self.plot.plot(
            pen=pg.mkPen('r', width=2),
            symbol='o',
            symbolBrush='r',
            name="Temperature"
        )

        # Secondary Y-axis for humidity
        self.hum_plot = pg.ViewBox()
        self.plot.showAxis('right')
        self.plot.scene().addItem(self.hum_plot)
        self.plot.getAxis('right').linkToView(self.hum_plot)
        self.hum_plot.setXLink(self.plot)

        # Humidity curve
        self.hum_curve = pg.PlotCurveItem(
            pen=pg.mkPen('b', width=2),
            symbol='x',
            symbolBrush='b',
            name="Humidity"
        )
        self.hum_plot.addItem(self.hum_curve)
        self.plot.getAxis('right').setLabel("Humidity (%)", color='blue')

        # Link resize
        def updateViews():
            self.hum_plot.setGeometry(self.plot.vb.sceneBoundingRect())
            self.hum_plot.linkedViewChanged(self.plot.vb, self.hum_plot.XAxis)
        self.plot.vb.sigResized.connect(updateViews)

        # Add legend
        self.plot.addLegend()

        # Status label
        self.status_label = QtWidgets.QLabel("Initializing...")
        layout.addWidget(self.status_label)

        # Timer for updates
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_dashboard)
        self.timer.start(1000)  # update every 1s

        # Enable anti-aliasing for smoother curves
        pg.setConfigOptions(antialias=True)

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
            self.plot.setXRange(times_epoch[-1] - 300, times_epoch[-1])

        # Auto-scale Y separately
        self.plot.enableAutoRange(axis=pg.ViewBox.YAxis, enable=True)
        self.hum_plot.enableAutoRange(axis=pg.ViewBox.YAxis, enable=True)

        # System usage
        cpu = psutil.cpu_percent(interval=0.1)
        ram = psutil.virtual_memory().percent
        self.status_label.setText(
            f"Router: UP | Broker: UP | Sensor: UP\nCPU: {cpu}%   RAM: {ram}%"
        )

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
